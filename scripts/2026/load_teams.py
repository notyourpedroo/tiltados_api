#!/usr/bin/env python3
"""
Retornar o DataFrame das equipes de 2026.

Este módulo extrai as equipes participantes a partir dos arquivos de resultados
de 2026 e retorna um DataFrame com team_id e team_name, mantendo consistência de IDs
com as equipes de 2025.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .common import list_sessions, read_session_results
    from ..errors import DataError, display_path, read_csv, require_columns, require_dir, to_int_column
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from common import list_sessions, read_session_results
    from errors import DataError, display_path, read_csv, require_columns, require_dir, to_int_column


def _normalize_team_name(name):
    """Normaliza o nome da equipe para correspondência entre temporadas."""
    n = name.lower().strip()
    if "red bull" in n and "racing bulls" not in n:
        return "red bull"
    if "ferrari" in n:
        return "ferrari"
    if "mercedes" in n:
        return "mercedes"
    if "racing bulls" in n or "vcarb" in n:
        return "racing bulls"
    if "alpine" in n:
        return "alpine"
    if "mclaren" in n:
        return "mclaren"
    if "sauber" in n or "kick" in n:
        return "sauber"
    if "aston" in n:
        return "aston martin"
    if "williams" in n:
        return "williams"
    if "haas" in n:
        return "haas"
    return n


def load_teams(base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Lê os arquivos de resultados de 2026 e extrai as equipes participantes,
    preservando os IDs de 2025 para equipes existentes e atribuindo novos IDs para estreantes.

    Gera um DataFrame com as seguintes colunas:
    - team_id: ID único da equipe (compatível entre temporadas)
    - team_name: Nome da equipe em 2026

    Args:
        base_path (str): Caminho para a pasta dos dados de 2026.
                         Padrão: './files/2026'
        base_path_2025 (str): Caminho para a pasta dos dados de 2025.
                              Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com as equipes de 2026 (team_id, team_name).

    Raises:
        DataError: Se a pasta de 2026 não existir, não houver resultados,
                   algum CSV de sessão for inválido ou o teams.csv de 2025 for inválido.
    """
    require_dir(base_path)

    # 1. Carregar mapeamento de equipes de 2025 (se existir)
    team_id_map = {}
    norm_to_id = {}
    teams_2025_file = os.path.join(base_path_2025, "teams.csv")
    if os.path.exists(teams_2025_file):
        df_2025_teams = read_csv(teams_2025_file)
        require_columns(df_2025_teams, ["team_id", "team_name"], teams_2025_file)
        df_2025_teams["team_id"] = to_int_column(df_2025_teams, "team_id", teams_2025_file)
        for _, row in df_2025_teams.iterrows():
            tid = int(row["team_id"])
            tname = str(row["team_name"]).strip()
            team_id_map[tname] = tid
            norm_to_id[_normalize_team_name(tname)] = tid

    max_team_id = max(team_id_map.values()) if team_id_map else 0

    # 2. Extrair equipes únicas presentes nos arquivos de 2026
    teams_found = set()

    for session in list_sessions(base_path):
        df_session = read_session_results(session["file_path"])
        if df_session is not None:
            teams_found.update(df_session["Equipe"].astype(str).str.strip())

    if not teams_found:
        raise DataError(f"Nenhum resultado encontrado nos CSVs de {display_path(base_path)}.")

    # 3. Mapear team_id mantendo consistência com 2025
    rows = []
    for team_name in sorted(list(teams_found)):
        norm = _normalize_team_name(team_name)
        if team_name in team_id_map:
            tid = team_id_map[team_name]
        elif norm in norm_to_id:
            tid = norm_to_id[norm]
        else:
            max_team_id += 1
            tid = max_team_id
            team_id_map[team_name] = tid
            norm_to_id[norm] = tid

        rows.append({
            "team_id": tid,
            "team_name": team_name
        })

    df_teams = pd.DataFrame(rows).sort_values("team_id").reset_index(drop=True)
    df_teams["team_id"] = df_teams["team_id"].astype(int)

    return df_teams


# Alias para retrocompatibilidade
load_2026_teams = load_teams


if __name__ == "__main__":
    teams_df = load_teams()

    if teams_df is not None:
        print("\nDataFrame de equipes de 2026:")
        print(teams_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de equipes de 2026.")
