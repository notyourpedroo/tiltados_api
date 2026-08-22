#!/usr/bin/env python3
"""
Calcular a tabela de classificação (standings) de 2025.

Este módulo cruza os resultados das corridas com o sistema de pontuação (scores.csv)
para calcular a pontuação total, vitórias, pódios e posições de pilotos e construtores.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .load_drivers import load_drivers
    from .load_teams import load_teams
    from .load_races import load_races
    from .load_results import load_results
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from load_drivers import load_drivers
    from load_teams import load_teams
    from load_races import load_races
    from load_results import load_results


def _calculate_base_points(base_path="./files/2025"):
    """Função interna para cruzar resultados com a tabela de pontuação (scores.csv)."""
    scores_file = os.path.join(base_path, "scores.csv")
    if not os.path.exists(scores_file):
        raise FileNotFoundError(f"Arquivo de pontuação não encontrado em: {scores_file}")

    df_scores = pd.read_csv(scores_file)
    df_results = load_results(base_path=base_path)
    df_races = load_races(base_path=base_path)

    if df_results is None or df_races is None:
        return None

    # Cruzar com corridas para obter is_sprint
    merged = df_results.merge(
        df_races[["race_id", "is_sprint"]], on="race_id", how="left"
    )

    # Cruzar com pontuações
    merged = merged.merge(
        df_scores,
        left_on=["driver_final_position", "is_sprint"],
        right_on=["position", "is_sprint"],
        how="left"
    )
    merged["points"] = merged["points"].fillna(0).astype(int)

    return merged


def calculate_driver_standings(base_path="./files/2025"):
    """
    Calcula a classificação completa do campeonato de pilotos de 2025.

    Colunas do DataFrame retornado:
    - position: Posição no campeonato (1 a N)
    - driver_id: ID único do piloto
    - driver_name: Nome do piloto
    - team_id: ID da equipe
    - team_name: Nome da equipe
    - points: Total de pontos somados
    - wins: Vitórias em Grandes Prêmios (corridas principais)
    - sprint_wins: Vitórias em corridas Sprint
    - podiums: Total de pódios (1º a 3º lugar)
    - races: Total de sessões disputadas
    """
    merged = _calculate_base_points(base_path=base_path)
    if merged is None:
        return None

    df_drivers = load_drivers(base_path=base_path)
    df_teams = load_teams(base_path=base_path)

    # Agrupar por piloto
    driver_stats = merged.groupby("driver_id").agg(
        points=("points", "sum"),
        wins=("driver_final_position", lambda s: ((s == 1) & (~merged.loc[s.index, "is_sprint"])).sum()),
        sprint_wins=("driver_final_position", lambda s: ((s == 1) & (merged.loc[s.index, "is_sprint"])).sum()),
        podiums=("driver_final_position", lambda s: (s <= 3).sum()),
        races=("race_id", "count")
    ).reset_index()

    driver_stats = driver_stats.merge(df_drivers[["driver_id", "driver_name", "team_id"]], on="driver_id")
    driver_stats = driver_stats.merge(df_teams[["team_id", "team_name"]], on="team_id")

    # Ordenar por pontuação, desempate por vitórias em GP e depois pódios
    driver_stats = driver_stats.sort_values(
        by=["points", "wins", "podiums"], ascending=False
    ).reset_index(drop=True)

    driver_stats["position"] = range(1, len(driver_stats) + 1)

    cols = [
        "position", "driver_id", "driver_name", "team_id", "team_name",
        "points", "wins", "sprint_wins", "podiums", "races"
    ]
    return driver_stats[cols]


def calculate_team_standings(base_path="./files/2025"):
    """
    Calcula a classificação completa do campeonato de construtores de 2025.

    Colunas do DataFrame retornado:
    - position: Posição no campeonato (1 a N)
    - team_id: ID da equipe
    - team_name: Nome da equipe
    - points: Total de pontos somados
    - wins: Vitórias em Grandes Prêmios
    - podiums: Total de pódios conquistados pelos pilotos da equipe
    """
    merged = _calculate_base_points(base_path=base_path)
    if merged is None:
        return None

    df_teams = load_teams(base_path=base_path)

    # Agrupar por equipe
    team_stats = merged.groupby("team_id").agg(
        points=("points", "sum"),
        wins=("driver_final_position", lambda s: ((s == 1) & (~merged.loc[s.index, "is_sprint"])).sum()),
        podiums=("driver_final_position", lambda s: (s <= 3).sum())
    ).reset_index()

    team_stats = team_stats.merge(df_teams[["team_id", "team_name"]], on="team_id")

    team_stats = team_stats.sort_values(
        by=["points", "wins", "podiums"], ascending=False
    ).reset_index(drop=True)

    team_stats["position"] = range(1, len(team_stats) + 1)

    cols = ["position", "team_id", "team_name", "points", "wins", "podiums"]
    return team_stats[cols]


def calculate_standings(type="drivers", base_path="./files/2025"):
    """
    Função principal de cálculo de standings para 2025.

    Args:
        type (str): 'drivers' para pilotos ou 'teams'/'constructors' para equipes.
        base_path (str): Caminho base dos arquivos de 2025.

    Returns:
        pd.DataFrame: Tabela de classificação solicitada.
    """
    if type in ["teams", "constructors"]:
        return calculate_team_standings(base_path=base_path)
    return calculate_driver_standings(base_path=base_path)


# Aliases para retrocompatibilidade
load_driver_standings = calculate_driver_standings
load_team_standings = calculate_team_standings
load_standings = calculate_standings
load_2025_standings = calculate_standings


if __name__ == "__main__":
    drivers_standings = calculate_driver_standings()
    teams_standings = calculate_team_standings()

    if drivers_standings is not None:
        print("\n=== CLASSIFICACAO DE PILOTOS - TEMPORADA 2025 ===")
        print(drivers_standings.to_string(index=False))

    if teams_standings is not None:
        print("\n=== CLASSIFICACAO DE CONSTRUTORES - TEMPORADA 2025 ===")
        print(teams_standings.to_string(index=False))
