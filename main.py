#!/usr/bin/env python3
"""
Tiltados API — API REST para dados da liga Tiltados F1.

Serve os dados processados pelas funções existentes em scripts/2025 (temporada consolidada) e scripts/sessions (temporadas por Sessão)
como endpoints JSON via FastAPI.

Para rodar localmente:
    uvicorn main:app --reload

Documentação interativa (Swagger UI):
    http://localhost:8000/docs
"""

import functools
import glob
import logging
import os
import importlib
import re

from fastapi import FastAPI, HTTPException, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from scripts.errors import DataError

logger = logging.getLogger("tiltados_api")

# ── Importar scripts existentes ──────────────────────────────────────────────
# O diretório scripts/2025 tem nome numérico (inválido como módulo Python), então
# usamos importlib para importá-lo; scripts/sessions segue o mesmo padrão.

# 2025, no formato consolidado
load_2025_drivers = importlib.import_module("scripts.2025.load_drivers").load_drivers
load_2025_teams = importlib.import_module("scripts.2025.load_teams").load_teams
load_2025_races = importlib.import_module("scripts.2025.load_races").load_races
load_2025_results = importlib.import_module("scripts.2025.load_results").load_results
calculate_2025_standings = importlib.import_module("scripts.2025.calculate_standings").calculate_standings

# Temporadas por Sessão (2026 em diante): o mesmo código serve qualquer ano (docs/adr/0001)
load_session_drivers = importlib.import_module("scripts.sessions.load_drivers").load_drivers
load_session_teams = importlib.import_module("scripts.sessions.load_teams").load_teams
load_session_races = importlib.import_module("scripts.sessions.load_races").load_races
load_session_results = importlib.import_module("scripts.sessions.load_results").load_results
calculate_session_standings = importlib.import_module("scripts.sessions.calculate_standings").calculate_standings
load_session_punishments = importlib.import_module("scripts.sessions.load_punishments").load_punishments
calculate_session_super_license = importlib.import_module("scripts.sessions.calculate_super_license").calculate_super_license
calculate_session_prediction = importlib.import_module("scripts.sessions.calculate_prediction").calculate_prediction


# ── Helpers ──────────────────────────────────────────────────────────────────

# Caminho absoluto da raiz do projeto (onde main.py está)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Única temporada no formato consolidado (files/2025/, módulos de scripts/2025)
CONSOLIDATED_SEASON = "2025"


def _files_path(season) -> str:
    """Retorna o caminho absoluto para files/{season}."""
    return os.path.join(BASE_DIR, "files", str(season))


def _files_path_sl() -> str:
    """Caminho absoluto para files/super_license."""
    return os.path.join(BASE_DIR, "files", "super_license")


def _season_years():
    """
    Temporadas servidas pela API, em ordem crescente.

    2025 fica no formato consolidado. As demais são descobertas pelas pastas: todo ano
    cuja pasta files/{ano}/ tem Calendário (calendar.csv) é uma temporada por Sessão.
    """
    files_dir = os.path.join(BASE_DIR, "files")
    years = {CONSOLIDATED_SEASON}
    for name in os.listdir(files_dir):
        if re.fullmatch(r"[0-9]{4}", name) and os.path.isfile(os.path.join(files_dir, name, "calendar.csv")):
            years.add(name)
    return sorted(years, key=int)


def _df_to_records(df):
    """Converte um DataFrame para lista de dicts serializáveis em JSON."""
    return df.to_dict(orient="records")


# ── Cache dos dados ──────────────────────────────────────────────────────────
# Evita re-processar CSVs a cada request. O cache é invalidado automaticamente
# quando qualquer CSV em files/ é adicionado, removido ou modificado.

def _files_fingerprint():
    """Assinatura (caminho, mtime, tamanho) de todos os CSVs em files/."""
    fingerprint = []
    for path in sorted(glob.glob(os.path.join(BASE_DIR, "files", "**", "*.csv"), recursive=True)):
        stat = os.stat(path)
        fingerprint.append((path, stat.st_mtime_ns, stat.st_size))
    return tuple(fingerprint)


def _cached_until_files_change(func):
    """
    Mantém o último resultado de func para cada combinação de argumentos
    (ex.: temporada e recurso) e recalcula só quando files/ muda.
    """
    cache = {}

    @functools.wraps(func)
    def wrapper(*args):
        fingerprint = _files_fingerprint()
        entry = cache.get(args)
        if entry is None or entry[0] != fingerprint:
            entry = cache[args] = (fingerprint, func(*args))
        return entry[1]

    return wrapper


# Recursos de cada formato de temporada. Cada loader recebe a pasta e o ano da temporada.
# A temporada consolidada (2025) só tem os recursos das rotas genéricas.
_CONSOLIDATED_LOADERS = {
    "drivers": lambda path, year: load_2025_drivers(base_path=path),
    "teams": lambda path, year: load_2025_teams(base_path=path),
    "races": lambda path, year: load_2025_races(base_path=path),
    "results": lambda path, year: load_2025_results(base_path=path),
    "driver_standings": lambda path, year: calculate_2025_standings(type="drivers", base_path=path),
    "team_standings": lambda path, year: calculate_2025_standings(type="teams", base_path=path),
}

# As temporadas por Sessão também têm Superlicença, punições e Chance de título; as punições ficam
# num arquivo só (files/super_license/), filtrado pelo ano.
_SESSION_LOADERS = {
    "drivers": lambda path, year: load_session_drivers(base_path=path),
    "teams": lambda path, year: load_session_teams(base_path=path),
    "races": lambda path, year: load_session_races(base_path=path),
    "results": lambda path, year: load_session_results(base_path=path),
    "driver_standings": lambda path, year: calculate_session_standings(type="drivers", base_path=path),
    "team_standings": lambda path, year: calculate_session_standings(type="teams", base_path=path),
    "punishments": lambda path, year: load_session_punishments(
        base_path=_files_path_sl(), season_year=year, enriched=True, season_path=path,
    ),
    "super_license": lambda path, year: calculate_session_super_license(
        base_path_sl=_files_path_sl(), base_path=path, season_year=year,
    ),
    # Chance de título de pilotos e construtores, calculada com as mesmas simulações
    "prediction": lambda path, year: calculate_session_prediction(
        base_path=path, base_path_sl=_files_path_sl(), season_year=year,
    ),
}


def _season_loaders(season: str):
    """Os recursos do formato da temporada: consolidado (2025) ou por Sessão."""
    return _CONSOLIDATED_LOADERS if season == CONSOLIDATED_SEASON else _SESSION_LOADERS


@_cached_until_files_change
def _get_season_data(season: str, resource: str):
    """Um recurso de uma temporada, com os módulos do formato dela."""
    return _season_loaders(season)[resource](_files_path(season), int(season))


def _load_data(season: str, resource: str, part: str = None):
    """
    Carrega e retorna os dados como lista de dicts (`part` escolhe a tabela, quando o recurso traz mais
    de uma); 404 se a temporada não existe ou se o recurso só existe nas temporadas por Sessão.
    """
    seasons = _season_years()
    if season not in seasons:
        raise HTTPException(
            status_code=404,
            detail=f"Temporada {season} não encontrada. Temporadas disponíveis: {', '.join(seasons)}.",
        )
    if resource not in _season_loaders(season):
        raise HTTPException(
            status_code=404,
            detail=(
                f"Rota indisponível para {season}: Superlicença, punições e Chance de título só existem "
                f"nas temporadas por Sessão (2026 em diante), e {season} está no formato consolidado."
            ),
        )
    data = _get_season_data(season, resource)
    return _df_to_records(data[part] if part else data)


# ── Aplicação FastAPI ────────────────────────────────────────────────────────

API_VERSION = "v2.26.1029"

app = FastAPI(
    title="Tiltados API",
    description="API REST para dados da liga Tiltados F1 — a temporada 2025 e as temporadas por Sessão, de 2026 em diante.",
    version=API_VERSION,
)

# API pública e somente leitura: qualquer origem pode consultar, sem cookies/credenciais
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(DataError)
async def data_error_handler(request: Request, exc: DataError):
    """Problemas nos arquivos de files/ voltam ao cliente com a causa e o arquivo a corrigir."""
    logger.warning("Erro nos dados em %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# ── Rotas ────────────────────────────────────────────────────────────────────

SEASON_DESCRIPTION = (
    "Ano da temporada (ex.: 2025, 2026). As temporadas disponíveis estão em `seasons`, na rota `/`; "
    "outro valor responde 404."
)


SESSION_SEASON_DESCRIPTION = (
    "Ano de uma temporada por Sessão (2026 em diante). As temporadas disponíveis estão em `seasons`, "
    "na rota `/`; 2025 (formato consolidado) e outro valor respondem 404."
)


def _season_path(description=SEASON_DESCRIPTION):
    """
    Parâmetro {season} documentado no Swagger: das rotas genéricas, ou, com SESSION_SEASON_DESCRIPTION,
    das rotas que só existem nas temporadas por Sessão.
    """
    return Path(..., description=description, examples=["2026"])


@app.get("/")
def root():
    """Informações básicas da API."""
    return {
        "name": "Tiltados API",
        "version": API_VERSION,
        "seasons": [int(year) for year in _season_years()],
        "docs": "/docs",
    }


@app.get("/load/{season}/drivers", summary="Pilotos da temporada")
def get_drivers(season: str = _season_path()):
    """Retorna a lista de pilotos da temporada especificada."""
    return _load_data(season, "drivers")


@app.get("/load/{season}/teams", summary="Equipes da temporada")
def get_teams(season: str = _season_path()):
    """Retorna a lista de equipes da temporada especificada."""
    return _load_data(season, "teams")


@app.get("/load/{season}/races", summary="Corridas da temporada")
def get_races(season: str = _season_path()):
    """Retorna a lista de corridas e sprints da temporada especificada."""
    return _load_data(season, "races")


@app.get("/load/{season}/results", summary="Resultados da temporada")
def get_results(season: str = _season_path()):
    """Retorna todos os resultados de corridas e sprints da temporada."""
    return _load_data(season, "results")


@app.get("/load/{season}/standings/drivers", summary="Classificação de pilotos")
def get_driver_standings(season: str = _season_path()):
    """Retorna a classificação do campeonato de pilotos."""
    return _load_data(season, "driver_standings")


@app.get("/load/{season}/standings/teams", summary="Classificação de construtores")
def get_team_standings(season: str = _season_path()):
    """Retorna a classificação do campeonato de construtores."""
    return _load_data(season, "team_standings")


@app.get("/load/{season}/punishments", summary="Punições da Superlicença")
def get_punishments(season: str = _season_path(SESSION_SEASON_DESCRIPTION)):
    """Retorna as punições da Superlicença registradas na temporada especificada."""
    return _load_data(season, "punishments")


@app.get("/load/{season}/super-license", summary="Status da Superlicença")
def get_super_license(season: str = _season_path(SESSION_SEASON_DESCRIPTION)):
    """Retorna o status da Superlicença de cada piloto na temporada especificada."""
    return _load_data(season, "super_license")


@app.get("/load/{season}/prediction/drivers", summary="Chance de título dos pilotos")
def get_driver_prediction(season: str = _season_path(SESSION_SEASON_DESCRIPTION)):
    """Retorna a situação no título e a Chance de título de cada piloto, simulando as Sessões pendentes da temporada."""
    return _load_data(season, "prediction", "drivers")


@app.get("/load/{season}/prediction/teams", summary="Chance de título dos construtores")
def get_team_prediction(season: str = _season_path(SESSION_SEASON_DESCRIPTION)):
    """Retorna a situação no título e a Chance de título de cada equipe, simulando as Sessões pendentes da temporada."""
    return _load_data(season, "prediction", "teams")
