#!/usr/bin/env python3
"""
Retornar o DataFrame dos pilotos de 2026.

Este módulo extrai os pilotos participantes a partir dos arquivos de resultados
de 2026, com o ID e o nome vindos do Cadastro e a equipe da Sessão mais recente.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .common import list_sessions, read_session_results
    from .load_registry import load_registered_drivers, require_registered
    from .load_teams import load_teams
    from ..errors import DataError, display_path, require_dir
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from common import list_sessions, read_session_results
    from load_registry import load_registered_drivers, require_registered
    from load_teams import load_teams
    from errors import DataError, display_path, require_dir


def _is_placeholder_driver(value):
    """Indica se o nome do piloto está vazio ou é o placeholder 'Pessoa' do export."""
    if pd.isna(value):
        return True
    name = str(value).strip()
    return not name or name.lower() == "pessoa"


def load_drivers(base_path="./files/2026", base_path_2025="./files/2025", registry_path=None):
    """
    Lê os arquivos de resultados de uma temporada por Sessão (2026 em diante) e
    extrai os pilotos participantes.

    Gera um DataFrame com as seguintes colunas (vazio se a temporada ainda não tem
    Sessão disputada):
    - driver_id: ID do piloto no Cadastro (o mesmo em todas as temporadas)
    - team_id: ID, no Cadastro, da equipe na sessão mais recente do piloto
    - driver_name: Nome do piloto no Cadastro

    Args:
        base_path (str): Caminho para a pasta da temporada (ex.: './files/2027').
                         Padrão: './files/2026'
        base_path_2025 (str): Não é mais usado (os IDs vêm do Cadastro). Fica na
                              assinatura porque os chamadores passam os mesmos
                              caminhos a todos os loaders de 2026.
        registry_path (str): Pasta do Cadastro. Padrão: a pasta acima de `base_path`.

    Returns:
        pd.DataFrame: DataFrame com os pilotos da temporada (driver_id, team_id, driver_name).

    Raises:
        DataError: Se a pasta da temporada não existir, algum CSV de sessão for inválido,
                   algum resultado tiver o piloto vazio ou como 'Pessoa', algum
                   piloto ou equipe não estiver no Cadastro ou o Cadastro for inválido.
    """
    require_dir(base_path)
    if registry_path is None:
        registry_path = os.path.dirname(os.path.normpath(base_path))

    df_registered = load_registered_drivers(registry_path)
    driver_id_map = dict(zip(df_registered["driver_name"], df_registered["driver_id"]))

    # 1. Extrair pilotos de 2026 em ordem cronológica,
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

        require_registered(df_session, "Piloto", driver_id_map, "um piloto do Cadastro", session["file_path"])

        for _, row in df_session.iterrows():
            driver_team_map[str(row["Piloto"]).strip()] = str(row["Equipe"]).strip()

    # 2. IDs das equipes vêm de load_teams, que também confere o Cadastro de equipes
    df_teams = load_teams(base_path=base_path, registry_path=registry_path)
    team_id_map = dict(zip(df_teams["team_name"], df_teams["team_id"]))

    # 3. Construir o DataFrame de pilotos
    df_drivers = pd.DataFrame([
        {
            "driver_id": int(driver_id_map[driver_name]),
            "team_id": int(team_id_map[team_name]),
            "driver_name": driver_name,
        }
        for driver_name, team_name in driver_team_map.items()
    ], columns=["driver_id", "team_id", "driver_name"])
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
