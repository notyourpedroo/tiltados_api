#!/usr/bin/env python3
"""
Funções e constantes compartilhadas pelos loaders de 2026.

Centraliza a identificação dos arquivos de sessão (local, data e tipo) e a
leitura do bloco de resultados dos CSVs exportados. O nome do GP, a cidade e o
race_id de cada Sessão vêm do Cadastro de Sessões (files/sessions.csv).
"""

import glob
import io
import os
import re
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from ..errors import DataError, display_path, require_columns, to_int_column
except (ImportError, ValueError):
    scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from errors import DataError, display_path, require_columns, to_int_column


# Padrão do nome dos arquivos de sessão: {local}_{race|sprint}_{YYYYMMDD}.csv
SESSION_FILE_PATTERN = re.compile(r"([a-zA-Z_]+)_(race|sprint)_(\d{8})\.csv", re.IGNORECASE)

# Colunas que todo bloco de resultados precisa ter
SESSION_REQUIRED_COLUMNS = ["Pos.", "Piloto", "Equipe", "Grid"]


def _parse_session_file(file_path):
    """Extrai local, data e tipo da sessão do nome do arquivo (None se fora do padrão)."""
    match = SESSION_FILE_PATTERN.match(os.path.basename(file_path))
    if not match:
        return None

    loc_raw, session_type, date_raw = match.groups()
    return {
        "file_path": file_path,
        "local": loc_raw.lower(),
        "race_date": f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}",
        "is_sprint": session_type.lower() == "sprint",
    }


def list_sessions(base_path="./files/2026"):
    """
    Lista as sessões de 2026 (arquivos que seguem o padrão de nome), em ordem cronológica.
    No mesmo dia, o sprint vem antes da corrida.

    Cada sessão é um dict com: file_path, local, race_date, is_sprint.
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

    Raises:
        DataError: Se o arquivo não puder ser lido, faltar coluna obrigatória,
                   'Pos.' ou 'Grid' não forem números inteiros ou a equipe estiver vazia.
    """
    try:
        lines = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip() or line.startswith(",,,,") or line.startswith("Tempo,"):
                    break
                lines.append(line)

        if not lines:
            return None

        df_session = pd.read_csv(io.StringIO("".join(lines)))
    except Exception as e:
        raise DataError(f"Não foi possível ler {display_path(file_path)}: {e}") from e

    require_columns(df_session, SESSION_REQUIRED_COLUMNS, file_path)
    df_session["Pos."] = to_int_column(df_session, "Pos.", file_path)
    df_session["Grid"] = to_int_column(df_session, "Grid", file_path)

    empty_team = df_session["Equipe"].isna() | (df_session["Equipe"].astype(str).str.strip() == "")
    if empty_team.any():
        pos = int(empty_team.to_numpy().argmax())
        raise DataError(f"{display_path(file_path)}, linha {pos + 2}: coluna 'Equipe' vazia.")

    return df_session
