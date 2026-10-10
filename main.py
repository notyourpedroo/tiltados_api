#!/usr/bin/env python3
"""
Tiltados API — API REST para dados da liga Tiltados F1.

Serve os dados processados pelas funções existentes em scripts/2025 e scripts/2026
como endpoints JSON via FastAPI.

Para rodar localmente:
    uvicorn main:app --reload

Documentação interativa (Swagger UI):
    http://localhost:8000/docs
"""

import functools
import glob
import os
import importlib
from typing import Literal

from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware

# ── Importar scripts existentes ──────────────────────────────────────────────
# Os diretórios scripts/2025 e scripts/2026 têm nomes numéricos (inválidos como
# módulos Python), então usamos importlib para importá-los.

# 2025
load_2025_drivers = importlib.import_module("scripts.2025.load_drivers").load_drivers
load_2025_teams = importlib.import_module("scripts.2025.load_teams").load_teams
load_2025_races = importlib.import_module("scripts.2025.load_races").load_races
load_2025_results = importlib.import_module("scripts.2025.load_results").load_results
calculate_2025_standings = importlib.import_module("scripts.2025.calculate_standings").calculate_standings

# 2026
load_2026_drivers = importlib.import_module("scripts.2026.load_drivers").load_drivers
load_2026_teams = importlib.import_module("scripts.2026.load_teams").load_teams
load_2026_races = importlib.import_module("scripts.2026.load_races").load_races
load_2026_results = importlib.import_module("scripts.2026.load_results").load_results
calculate_2026_standings = importlib.import_module("scripts.2026.calculate_standings").calculate_standings
load_2026_punishments = importlib.import_module("scripts.2026.load_punishments").load_punishments
calculate_2026_super_license = importlib.import_module("scripts.2026.calculate_super_license").calculate_super_license




# ── Helpers ──────────────────────────────────────────────────────────────────

# Caminho absoluto da raiz do projeto (onde main.py está)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SeasonType = Literal["2025", "2026"]


def _files_path(season: int) -> str:
    """Retorna o caminho absoluto para files/{season}."""
    return os.path.join(BASE_DIR, "files", str(season))


def _files_path_2025() -> str:
    """Caminho absoluto para files/2025 (base de mapeamento)."""
    return os.path.join(BASE_DIR, "files", "2025")


def _files_path_sl() -> str:
    """Caminho absoluto para files/super_license."""
    return os.path.join(BASE_DIR, "files", "super_license")


def _df_to_records(df):
    """Converte um DataFrame para lista de dicts serializáveis em JSON."""
    if df is None:
        return None
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
    """Mantém o último resultado de func e recalcula só quando files/ muda."""
    cache = {}

    @functools.wraps(func)
    def wrapper():
        fingerprint = _files_fingerprint()
        if cache.get("fingerprint") != fingerprint:
            cache["value"] = func()
            cache["fingerprint"] = fingerprint
        return cache["value"]

    return wrapper


@_cached_until_files_change
def _get_2025_drivers():
    return load_2025_drivers(base_path=_files_path(2025))


@_cached_until_files_change
def _get_2025_teams():
    return load_2025_teams(base_path=_files_path(2025))


@_cached_until_files_change
def _get_2025_races():
    return load_2025_races(base_path=_files_path(2025))


@_cached_until_files_change
def _get_2025_results():
    return load_2025_results(base_path=_files_path(2025))


@_cached_until_files_change
def _get_2025_driver_standings():
    return calculate_2025_standings(type="drivers", base_path=_files_path(2025))


@_cached_until_files_change
def _get_2025_team_standings():
    return calculate_2025_standings(type="teams", base_path=_files_path(2025))


@_cached_until_files_change
def _get_2026_drivers():
    return load_2026_drivers(base_path=_files_path(2026), base_path_2025=_files_path_2025())


@_cached_until_files_change
def _get_2026_teams():
    return load_2026_teams(base_path=_files_path(2026), base_path_2025=_files_path_2025())


@_cached_until_files_change
def _get_2026_races():
    return load_2026_races(base_path=_files_path(2026), base_path_2025=_files_path_2025())


@_cached_until_files_change
def _get_2026_results():
    return load_2026_results(base_path=_files_path(2026), base_path_2025=_files_path_2025())


@_cached_until_files_change
def _get_2026_driver_standings():
    return calculate_2026_standings(type="drivers", base_path=_files_path(2026), base_path_2025=_files_path_2025())


@_cached_until_files_change
def _get_2026_team_standings():
    return calculate_2026_standings(type="teams", base_path=_files_path(2026), base_path_2025=_files_path_2025())


@_cached_until_files_change
def _get_2026_punishments():
    return load_2026_punishments(base_path=_files_path_sl(), season_year=2026)


@_cached_until_files_change
def _get_2026_super_license():
    return calculate_2026_super_license(
        base_path_sl=_files_path_sl(),
        base_path_2026=_files_path(2026),
        base_path_2025=_files_path_2025(),
    )


# Dispatcher por temporada
_LOADERS = {
    "2025": {
        "drivers": _get_2025_drivers,
        "teams": _get_2025_teams,
        "races": _get_2025_races,
        "results": _get_2025_results,
        "driver_standings": _get_2025_driver_standings,
        "team_standings": _get_2025_team_standings,
    },
    "2026": {
        "drivers": _get_2026_drivers,
        "teams": _get_2026_teams,
        "races": _get_2026_races,
        "results": _get_2026_results,
        "driver_standings": _get_2026_driver_standings,
        "team_standings": _get_2026_team_standings,
    },
}


def _load_data(season: str, resource: str):
    """Carrega e retorna os dados como lista de dicts."""
    loaders = _LOADERS.get(season)
    if not loaders:
        raise HTTPException(status_code=404, detail=f"Temporada {season} não encontrada. Use 2025 ou 2026.")

    loader = loaders.get(resource)
    if not loader:
        raise HTTPException(status_code=404, detail=f"Recurso '{resource}' não disponível para {season}.")

    try:
        df = loader()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    records = _df_to_records(df)

    if records is None:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar {resource} de {season}.")

    return records


# ── Aplicação FastAPI ────────────────────────────────────────────────────────

app = FastAPI(
    title="Tiltados API",
    description="API REST para dados da liga Tiltados F1 — temporadas 2025 e 2026.",
    version="v2.26.1010",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Rotas ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Informações básicas da API."""
    return {
        "name": "Tiltados API",
        "version": "v2.26.1010",
        "seasons": [2025, 2026],
        "docs": "/docs",
    }


@app.get("/load/{season}/drivers", summary="Pilotos da temporada")
def get_drivers(season: SeasonType = Path(..., description="Ano da temporada (2025 ou 2026)")):
    """Retorna a lista de pilotos da temporada especificada."""
    return _load_data(season, "drivers")


@app.get("/load/{season}/teams", summary="Equipes da temporada")
def get_teams(season: SeasonType = Path(..., description="Ano da temporada (2025 ou 2026)")):
    """Retorna a lista de equipes da temporada especificada."""
    return _load_data(season, "teams")


@app.get("/load/{season}/races", summary="Corridas da temporada")
def get_races(season: SeasonType = Path(..., description="Ano da temporada (2025 ou 2026)")):
    """Retorna a lista de corridas e sprints da temporada especificada."""
    return _load_data(season, "races")


@app.get("/load/{season}/results", summary="Resultados da temporada")
def get_results(season: SeasonType = Path(..., description="Ano da temporada (2025 ou 2026)")):
    """Retorna todos os resultados de corridas e sprints da temporada."""
    return _load_data(season, "results")


@app.get("/load/{season}/standings/drivers", summary="Classificação de pilotos")
def get_driver_standings(season: SeasonType = Path(..., description="Ano da temporada (2025 ou 2026)")):
    """Retorna a classificação do campeonato de pilotos."""
    return _load_data(season, "driver_standings")


@app.get("/load/{season}/standings/teams", summary="Classificação de construtores")
def get_team_standings(season: SeasonType = Path(..., description="Ano da temporada (2025 ou 2026)")):
    """Retorna a classificação do campeonato de construtores."""
    return _load_data(season, "team_standings")


@app.get("/load/2026/punishments", summary="Punições da Superlicença (2026)")
def get_punishments():
    """Retorna as punições da Superlicença registradas na temporada 2026."""
    df = _get_2026_punishments()
    records = _df_to_records(df)
    if records is None:
        raise HTTPException(status_code=500, detail="Erro ao carregar punições de 2026.")
    return records


@app.get("/load/2026/super-license", summary="Status da Superlicença (2026)")
def get_super_license():
    """Retorna o status da Superlicença de cada piloto na temporada 2026."""
    try:
        df = _get_2026_super_license()
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    records = _df_to_records(df)
    if records is None:
        raise HTTPException(status_code=500, detail="Erro ao carregar dados da Superlicença de 2026.")
    return records
