#!/usr/bin/env python3
"""
Retornar o DataFrame dos resultados de 2026.

Este módulo processa os arquivos de resultados de corridas e sprints de 2026,
vinculando race_id, driver_id e team_id com os dados padronizados da liga.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .common import list_sessions, read_session_results
    from .load_drivers import load_drivers
    from .load_races import load_races
    from .load_teams import load_teams
    from ..errors import require_dir
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from common import list_sessions, read_session_results
    from load_drivers import load_drivers
    from load_races import load_races
    from load_teams import load_teams
    from errors import require_dir


def load_results(base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Lê os arquivos CSV de 2026 e retorna o DataFrame com os resultados consolidados.

    Gera um DataFrame com as seguintes colunas (mesmo schema de 2025):
    - race_id: ID da corrida/sprint no Cadastro de Sessões
    - driver_id: ID único do piloto
    - team_id: ID único da equipe
    - driver_start_position: Posição de largada no grid
    - driver_final_position: Posição de chegada na sessão
    - grid_result: Diferença de posições (chegada - largada)
    - driver_fastest_lap: Volta mais rápida na sessão

    Args:
        base_path (str): Caminho para a pasta dos dados de 2026.
                         Padrão: './files/2026'
        base_path_2025 (str): Não é mais usado (os IDs vêm do Cadastro). Fica na
                              assinatura porque os chamadores passam os mesmos
                              caminhos a todos os loaders de 2026.

    Returns:
        pd.DataFrame: DataFrame com os resultados das sessões de 2026.

    Raises:
        DataError: Se a pasta de 2026 não existir, algum CSV de sessão for inválido,
                   algum resultado tiver o piloto vazio ou como 'Pessoa' ou algum
                   piloto, equipe ou Sessão não estiver no Cadastro.
    """
    require_dir(base_path)

    # 1. IDs de corridas, pilotos e equipes vêm dos próprios loaders,
    #    para que todos os endpoints usem o mesmo mapeamento
    df_races = load_races(base_path=base_path, base_path_2025=base_path_2025)
    df_drivers = load_drivers(base_path=base_path, base_path_2025=base_path_2025)
    df_teams = load_teams(base_path=base_path, base_path_2025=base_path_2025)

    driver_id_map = dict(zip(df_drivers["driver_name"], df_drivers["driver_id"]))
    team_id_map = dict(zip(df_teams["team_name"], df_teams["team_id"]))

    # 2. Extrair resultados de cada sessão, em ordem cronológica
    #    (load_races devolve uma linha por sessão, na mesma ordem de list_sessions)
    all_results = []
    for session, race_id in zip(list_sessions(base_path), df_races["race_id"]):
        df_session = read_session_results(session["file_path"])
        if df_session is None:
            continue

        for _, row in df_session.iterrows():
            start_pos = int(row["Grid"])
            final_pos = int(row["Pos."])

            all_results.append({
                "race_id": race_id,
                "driver_id": driver_id_map[str(row["Piloto"]).strip()],
                "team_id": team_id_map[str(row["Equipe"]).strip()],
                "driver_start_position": start_pos,
                "driver_final_position": final_pos,
                "grid_result": final_pos - start_pos,
                "driver_fastest_lap": str(row.get("Melhor tempo", "")).strip()
            })

    df_results = pd.DataFrame(all_results)
    df_results["race_id"] = df_results["race_id"].astype(int)
    df_results["driver_id"] = df_results["driver_id"].astype(int)
    df_results["team_id"] = df_results["team_id"].astype(int)
    df_results["driver_start_position"] = df_results["driver_start_position"].astype(int)
    df_results["driver_final_position"] = df_results["driver_final_position"].astype(int)
    df_results["grid_result"] = df_results["grid_result"].astype(int)

    return df_results


# Alias para retrocompatibilidade
load_2026_results = load_results


if __name__ == "__main__":
    results_df = load_results()

    if results_df is not None:
        print(f"\nDataFrame de resultados de 2026 (Total de linhas: {len(results_df)}):")
        print(results_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de resultados de 2026.")
