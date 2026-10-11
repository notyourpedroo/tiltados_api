#!/usr/bin/env python3
"""
Funções e constantes compartilhadas pelos loaders de 2026.

Centraliza o mapeamento de locais, a identificação dos arquivos de sessão
(nome, data e tipo) e a leitura do bloco de resultados dos CSVs exportados.
"""

import glob
import io
import os
import re
import pandas as pd


# Mapeamento de locais e nomes canônicos de GP.
# O nome do GP deve ser igual ao de files/2025/races.csv para reaproveitar o race_id de 2025.
LOCATION_MAP = {
    "australia": ("GP da Austrália", "Melbourne"),
    "china": ("GP da China", "Xangai"),
    "japao": ("GP do Japão", "Suzuka"),
    "bahrein": ("GP do Barém", "Sakhir"),
    "arabia_saudita": ("GP da Arábia Saudita", "Gidá"),
    "miami": ("GP de Miami", "Miami Gardens"),
    "emilia_romanha": ("GP da Emília-Romanha", "Ímola"),
    "canada": ("GP do Canadá", "Montreal"),
    "monaco": ("GP de Mônaco", "Monte Carlo"),
    "espanha": ("GP da Espanha", "Montmeló"),
    "silverstone": ("GP da Grã-Bretanha", "Silverstone"),
    "austria": ("GP da Áustria", "Spielberg"),
    "belgica": ("GP da Bélgica", "Spa-Francorchamps"),
    "spa": ("GP da Bélgica", "Spa-Francorchamps"),
    "hungria": ("GP da Hungria", "Mogyoród"),
    "holanda": ("GP dos Países Baixos", "Zandvoort"),
    "italia": ("GP da Itália", "Monza"),
    "azerbaijao": ("GP do Azerbaijão", "Bacu"),
    "singapura": ("GP de Singapura", "Marina Bay"),
    "estados_unidos": ("GP dos Estados Unidos", "Austin"),
    "mexico": ("GP da Cidade do México", "Cidade do México"),
    "brasil": ("GP de São Paulo", "São Paulo"),
    "las_vegas": ("GP de Las Vegas", "Las Vegas"),
    "catar": ("GP do Catar", "Lusail"),
    "abu_dhabi": ("GP de Abu Dhabi", "Abu Dhabi"),
}

# Padrão do nome dos arquivos de sessão: {local}_{race|sprint}_{YYYYMMDD}.csv
SESSION_FILE_PATTERN = re.compile(r"([a-zA-Z_]+)_(race|sprint)_(\d{8})\.csv", re.IGNORECASE)


def _parse_session_file(file_path):
    """Extrai GP, local, data e tipo da sessão do nome do arquivo (None se fora do padrão)."""
    match = SESSION_FILE_PATTERN.match(os.path.basename(file_path))
    if not match:
        return None

    loc_raw, session_type, date_raw = match.groups()
    is_sprint = session_type.lower() == "sprint"
    base_gp_name, location = LOCATION_MAP.get(
        loc_raw.lower(), (f"GP de {loc_raw.capitalize()}", loc_raw.capitalize())
    )

    return {
        "file_path": file_path,
        "race_name": f"{base_gp_name} (SPRINT)" if is_sprint else base_gp_name,
        "race_date": f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}",
        "race_location": location,
        "is_sprint": is_sprint,
    }


def list_sessions(base_path="./files/2026"):
    """
    Lista as sessões de 2026 (arquivos que seguem o padrão de nome), em ordem cronológica.
    No mesmo dia, o sprint vem antes da corrida.

    Cada sessão é um dict com: file_path, race_name, race_date, race_location, is_sprint.
    """
    sessions = [
        session
        for session in (_parse_session_file(p) for p in glob.glob(os.path.join(base_path, "*.csv")))
        if session is not None
    ]
    sessions.sort(key=lambda s: (s["race_date"], not s["is_sprint"], s["file_path"]))
    return sessions


def read_session_results(file_path):
    """
    Lê o bloco de resultados de um CSV de sessão.

    A leitura para na primeira linha em branco, na que começa com ',,,,' ou na que
    começa com 'Tempo,' (início da seção de incidentes). Retorna None se o bloco estiver vazio.
    """
    lines = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.startswith(",,,,") or line.startswith("Tempo,"):
                break
            lines.append(line)

    if not lines:
        return None

    return pd.read_csv(io.StringIO("".join(lines)))
