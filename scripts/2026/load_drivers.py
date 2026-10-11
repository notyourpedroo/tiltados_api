#!/usr/bin/env python3
"""
Retornar o DataFrame dos pilotos de 2026.

Este módulo extrai os pilotos participantes a partir dos arquivos de resultados
de 2026, associando os IDs das equipes e mantendo a consistência de IDs entre temporadas.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .common import list_sessions, read_session_results
    from .load_teams import load_teams
    from ..errors import DataError, display_path, read_csv, require_columns, require_dir, to_int_column
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from common import list_sessions, read_session_results
    from load_teams import load_teams
    from errors import DataError, display_path, read_csv, require_columns, require_dir, to_int_column


def _is_placeholder_driver(value):
    """Indica se o nome do piloto está vazio ou é o placeholder 'Pessoa' do export."""
    if pd.isna(value):
        return True
    name = str(value).strip()
    return not name or name.lower() == "pessoa"


def load_drivers(base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Lê os arquivos de resultados de 2026 e extrai os pilotos participantes.

    Gera um DataFrame com as seguintes colunas:
    - driver_id: ID único do piloto (mantém consistência com histórico de 2025)
    - team_id: ID da equipe na sessão mais recente do piloto (mantém consistência com histórico de 2025)
    - driver_name: Nome do piloto

    Args:
        base_path (str): Caminho para a pasta dos dados de 2026.
                         Padrão: './files/2026'
        base_path_2025 (str): Caminho para a pasta dos dados de 2025.
                              Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com os pilotos de 2026 (driver_id, team_id, driver_name).

    Raises:
        DataError: Se a pasta de 2026 não existir, algum CSV de sessão for inválido,
                   algum resultado tiver o piloto vazio ou como 'Pessoa' ou o
                   drivers.csv de 2025 for inválido.
    """
    require_dir(base_path)

    # 1. Carregar mapeamento de IDs de pilotos existentes (2025)
    driver_id_map = {}
    drivers_2025_file = os.path.join(base_path_2025, "drivers.csv")
    if os.path.exists(drivers_2025_file):
        df_2025_drivers = read_csv(drivers_2025_file)
        require_columns(df_2025_drivers, ["driver_id", "driver_name"], drivers_2025_file)
        df_2025_drivers["driver_id"] = to_int_column(df_2025_drivers, "driver_id", drivers_2025_file)
        driver_id_map = dict(zip(df_2025_drivers["driver_name"], df_2025_drivers["driver_id"]))

    max_driver_id = max(driver_id_map.values()) if driver_id_map else 0

    # 2. Extrair pilotos de 2026 em ordem cronológica,
    #    para que a equipe de cada piloto seja a da sessão mais recente
    driver_team_map = {}

    for session in list_sessions(base_path):
        df_session = read_session_results(session["file_path"])
        if df_session is None:
            continue

        for i, row in df_session.iterrows():
            if _is_placeholder_driver(row["Piloto"]):
                raise DataError(
                    f"Piloto não identificado em {display_path(session['file_path'])}, "
                    f"linha {i + 2}: '{row['Piloto']}'. Corrija o nome do piloto no CSV."
                )

            driver_team_map[str(row["Piloto"]).strip()] = str(row["Equipe"]).strip()

    if not driver_team_map:
        raise DataError(f"Nenhum resultado encontrado nos CSVs de {display_path(base_path)}.")

    # 3. IDs das equipes vêm de load_teams, a fonte única desse mapeamento
    df_teams = load_teams(base_path=base_path, base_path_2025=base_path_2025)
    team_id_map = dict(zip(df_teams["team_name"], df_teams["team_id"]))

    # 4. Construir o DataFrame de pilotos
    rows = []
    for driver_name in sorted(driver_team_map.keys()):
        if driver_name not in driver_id_map:
            max_driver_id += 1
            driver_id_map[driver_name] = max_driver_id

        rows.append({
            "driver_id": int(driver_id_map[driver_name]),
            "team_id": int(team_id_map[driver_team_map[driver_name]]),
            "driver_name": driver_name
        })

    df_drivers = pd.DataFrame(rows)
    df_drivers = df_drivers.sort_values("driver_id").reset_index(drop=True)
    df_drivers["driver_id"] = df_drivers["driver_id"].astype(int)
    df_drivers["team_id"] = df_drivers["team_id"].astype(int)

    return df_drivers


# Alias para retrocompatibilidade
load_2026_drivers = load_drivers


if __name__ == "__main__":
    drivers_df = load_drivers()

    if drivers_df is not None:
        print("\nDataFrame bruto de pilotos de 2026:")
        print(drivers_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de pilotos de 2026.")
