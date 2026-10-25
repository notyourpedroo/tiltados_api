#!/usr/bin/env python3
"""
Retornar o Calendário de 2026: todas as Sessões previstas, disputadas ou pendentes.

O Calendário fica em calendar.csv (colunas local, tipo, data). Uma Sessão é disputada
quando existe o CSV de resultado com o mesmo local e tipo; senão, é pendente, mesmo
que a data prevista já tenha passado.
"""

import os
import sys
from datetime import date

import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .common import LOCATION_MAP, list_sessions
    from ..errors import DataError, display_path, read_csv, require_columns, require_dir
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from common import LOCATION_MAP, list_sessions
    from errors import DataError, display_path, read_csv, require_columns, require_dir

SESSION_TYPES = {"race": False, "sprint": True}


def _parse_date(value):
    """Converte 'YYYY-MM-DD' em texto normalizado (None se inválido)."""
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        return None


def load_calendar(base_path="./files/2026"):
    """
    Lê o calendar.csv de 2026 e cruza com as Sessões que já têm resultado.

    Gera um DataFrame, em ordem cronológica (no mesmo dia, a sprint antes da corrida), com:
    - local: Local da Etapa, como no nome dos arquivos de sessão e no LOCATION_MAP (ex: 'mexico')
    - is_sprint: Indica se a Sessão é uma Sprint (True/False)
    - race_date: Data do arquivo de resultado, se disputada; senão, a data prevista
    - is_played: Indica se a Sessão já foi disputada (True/False)

    Args:
        base_path (str): Caminho para a pasta dos dados de 2026.
                         Padrão: './files/2026'

    Returns:
        pd.DataFrame: DataFrame com as Sessões do Calendário.

    Raises:
        DataError: Se o calendar.csv não existir, faltar coluna, tiver valor inválido,
                   local fora do LOCATION_MAP ou Sessão repetida, ou se algum CSV de resultado não estiver no Calendário.
    """
    require_dir(base_path)
    calendar_file = os.path.join(base_path, "calendar.csv")
    df_calendar = read_csv(calendar_file)
    require_columns(df_calendar, ["local", "tipo", "data"], calendar_file)

    # 1. Validar cada linha do Calendário
    sessions = {}
    for i, row in df_calendar.iterrows():
        line = f"{display_path(calendar_file)}, linha {i + 2}"
        local = "" if pd.isna(row["local"]) else str(row["local"]).strip().lower()
        session_type = "" if pd.isna(row["tipo"]) else str(row["tipo"]).strip().lower()
        planned_date = _parse_date(row["data"])

        if not local:
            raise DataError(f"{line}: coluna 'local' vazia.")
        if local not in LOCATION_MAP:
            raise DataError(
                f"{line}: local '{row['local']}' não está no LOCATION_MAP (scripts/2026/common.py)."
            )
        if session_type not in SESSION_TYPES:
            raise DataError(f"{line}: coluna 'tipo' com valor '{row['tipo']}' (esperado 'race' ou 'sprint').")
        if planned_date is None:
            raise DataError(f"{line}: coluna 'data' com valor '{row['data']}' (esperado uma data YYYY-MM-DD).")

        key = (local, SESSION_TYPES[session_type])
        if key in sessions:
            raise DataError(f"{line}: Sessão '{local}' ({session_type}) repetida no calendário.")
        sessions[key] = {"local": local, "is_sprint": key[1], "race_date": planned_date, "is_played": False}

    # 2. Marcar as Sessões disputadas; a data do arquivo de resultado prevalece
    for played in list_sessions(base_path):
        key = (played["local"], played["is_sprint"])
        if key not in sessions:
            raise DataError(
                f"{display_path(played['file_path'])}: Sessão não encontrada em "
                f"{display_path(calendar_file)}. Adicione a linha '{key[0]},"
                f"{'sprint' if key[1] else 'race'},{played['race_date']}'."
            )
        sessions[key]["race_date"] = played["race_date"]
        sessions[key]["is_played"] = True

    df = pd.DataFrame(list(sessions.values()), columns=["local", "is_sprint", "race_date", "is_played"])
    df = df.sort_values(by=["race_date", "is_sprint"], ascending=[True, False]).reset_index(drop=True)
    df["is_sprint"] = df["is_sprint"].astype(bool)
    df["is_played"] = df["is_played"].astype(bool)
    return df


if __name__ == "__main__":
    calendar_df = load_calendar()
    print("\nCalendário de 2026:")
    print(calendar_df.to_string(index=False))
