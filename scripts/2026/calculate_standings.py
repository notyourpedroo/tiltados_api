#!/usr/bin/env python3
"""
Calcular a tabela de classificação (standings) de 2026.

Este módulo cruza os resultados das corridas de 2026 com o sistema de pontuação (scores.csv)
para calcular a pontuação total, vitórias, pódios e posições de pilotos e construtores.

Desempate, para pilotos e equipes: pontos; vitórias em Corridas; pódios (Corridas e Sprints);
mais 2ºs lugares em Corridas, depois mais 3ºs, e assim por diante; quem conseguiu primeiro
o seu melhor resultado em Corridas; e, por fim, a ordem do ID.
"""

import os
import sys

import numpy as np

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .load_drivers import load_drivers
    from .load_teams import load_teams
    from .load_races import load_races
    from .load_results import load_results
    from ..errors import read_csv, require_columns, to_int_column
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from load_drivers import load_drivers
    from load_teams import load_teams
    from load_races import load_races
    from load_results import load_results
    from errors import read_csv, require_columns, to_int_column


def _calculate_base_points(base_path="./files/2026", base_path_2025="./files/2025"):
    """Função interna para cruzar resultados de 2026 com a tabela de pontuação (scores.csv)."""
    scores_file = os.path.join(base_path, "scores.csv")
    df_scores = read_csv(scores_file)
    require_columns(df_scores, ["position", "points", "is_sprint"], scores_file)
    df_scores["position"] = to_int_column(df_scores, "position", scores_file)
    df_scores["points"] = to_int_column(df_scores, "points", scores_file)

    df_results = load_results(base_path=base_path, base_path_2025=base_path_2025)
    df_races = load_races(base_path=base_path, base_path_2025=base_path_2025)

    # Cruzar com corridas para obter is_sprint e a ordem cronológica da Sessão (load_races já vem em ordem)
    df_races = df_races[["race_id", "is_sprint"]].assign(session_order=range(len(df_races)))
    merged = df_results.merge(df_races, on="race_id", how="left")

    # Cruzar com pontuações
    merged = merged.merge(
        df_scores,
        left_on=["driver_final_position", "is_sprint"],
        right_on=["position", "is_sprint"],
        how="left"
    )
    merged["points"] = merged["points"].fillna(0).astype(int)

    return merged


def count_race_finishes(race_results, ids, by):
    """
    Conta as posições de cada piloto ou equipe em Corridas, para o desempate da classificação.

    `race_results` tem uma linha por resultado em Corridas (sem Sprints), com as colunas
    `by` (driver_id ou team_id), driver_final_position e session_order (ordem cronológica
    da Sessão). Numa equipe, os resultados de todos os seus pilotos somam.

    Retorna a tupla (finishes, first_best), alinhada a `ids`:
    - finishes: matriz com quantas vezes cada um terminou em 2º, 3º... em Corridas
      (coluna 0 = 2º lugar, até a pior posição registrada);
    - first_best: session_order da primeira Corrida em que conseguiu o seu melhor resultado
      (infinito para quem não disputou Corridas).

    Não lança DataError: recebe dados já validados pelos loaders.
    """
    ids = list(ids)
    row_of = {competitor: i for i, competitor in enumerate(ids)}
    positions = race_results["driver_final_position"].to_numpy(dtype=int)
    worst = int(positions.max()) if len(positions) else 1

    finishes = np.zeros((len(ids), max(worst - 1, 0)), dtype=int)
    first_best = np.full(len(ids), np.inf)
    best = np.full(len(ids), np.inf)

    for competitor, position, order in zip(race_results[by], positions, race_results["session_order"]):
        i = row_of.get(competitor)
        if i is None:
            continue
        if position >= 2:
            finishes[i, position - 2] += 1
        if position < best[i] or (position == best[i] and order < first_best[i]):
            best[i], first_best[i] = position, order

    return finishes, first_best


def standings_order(points, wins, podiums, finishes, first_best, ids):
    """
    Índices dos pilotos ou equipes na ordem da classificação, pela regra completa de desempate.

    Recebe arrays alinhados (um item por piloto ou equipe): pontos, vitórias em Corridas, pódios,
    `finishes` e `first_best` de `count_race_finishes` e os IDs. A ordem é: mais pontos; mais
    vitórias; mais pódios; mais 2ºs em Corridas, depois mais 3ºs, e assim por diante; quem
    conseguiu primeiro o seu melhor resultado em Corridas; e, por fim, o menor ID.

    Não lança DataError.
    """
    finishes = np.asarray(finishes)
    by_position = [-finishes[:, k] for k in reversed(range(finishes.shape[1]))]
    # np.lexsort usa a última chave como a principal
    keys = [np.asarray(ids), np.asarray(first_best)] + by_position + [
        -np.asarray(podiums), -np.asarray(wins), -np.asarray(points)
    ]
    return np.lexsort(keys)


def _sort_standings(stats, merged, by):
    """Ordena a classificação (`stats`, uma linha por `by`) pela regra de desempate e numera as posições."""
    finishes, first_best = count_race_finishes(merged[~merged["is_sprint"]], stats[by], by)
    order = standings_order(
        stats["points"].to_numpy(), stats["wins"].to_numpy(), stats["podiums"].to_numpy(),
        finishes, first_best, stats[by].to_numpy()
    )
    stats = stats.iloc[order].reset_index(drop=True)
    stats["position"] = range(1, len(stats) + 1)
    return stats


def calculate_driver_standings(base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Calcula a classificação completa do campeonato de pilotos de 2026.

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
    merged = _calculate_base_points(base_path=base_path, base_path_2025=base_path_2025)

    df_drivers = load_drivers(base_path=base_path, base_path_2025=base_path_2025)
    df_teams = load_teams(base_path=base_path, base_path_2025=base_path_2025)

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

    driver_stats = _sort_standings(driver_stats, merged, "driver_id")

    cols = [
        "position", "driver_id", "driver_name", "team_id", "team_name",
        "points", "wins", "sprint_wins", "podiums", "races"
    ]
    return driver_stats[cols]


def calculate_team_standings(base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Calcula a classificação completa do campeonato de construtores de 2026.

    Colunas do DataFrame retornado:
    - position: Posição no campeonato (1 a N)
    - team_id: ID da equipe
    - team_name: Nome da equipe
    - points: Total de pontos somados
    - wins: Vitórias em Grandes Prêmios
    - podiums: Total de pódios conquistados pelos pilotos da equipe
    """
    merged = _calculate_base_points(base_path=base_path, base_path_2025=base_path_2025)

    df_teams = load_teams(base_path=base_path, base_path_2025=base_path_2025)

    # Agrupar por equipe
    team_stats = merged.groupby("team_id").agg(
        points=("points", "sum"),
        wins=("driver_final_position", lambda s: ((s == 1) & (~merged.loc[s.index, "is_sprint"])).sum()),
        podiums=("driver_final_position", lambda s: (s <= 3).sum())
    ).reset_index()

    team_stats = team_stats.merge(df_teams[["team_id", "team_name"]], on="team_id")

    team_stats = _sort_standings(team_stats, merged, "team_id")

    cols = ["position", "team_id", "team_name", "points", "wins", "podiums"]
    return team_stats[cols]


def calculate_standings(type="drivers", base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Função principal de cálculo de standings para 2026.

    Args:
        type (str): 'drivers' para pilotos ou 'teams'/'constructors' para equipes.
        base_path (str): Caminho base dos arquivos de 2026.
        base_path_2025 (str): Caminho base dos arquivos de 2025.

    Returns:
        pd.DataFrame: Tabela de classificação solicitada.
    """
    if type in ["teams", "constructors"]:
        return calculate_team_standings(base_path=base_path, base_path_2025=base_path_2025)
    return calculate_driver_standings(base_path=base_path, base_path_2025=base_path_2025)


# Aliases para retrocompatibilidade
load_driver_standings = calculate_driver_standings
load_team_standings = calculate_team_standings
load_standings = calculate_standings
load_2026_standings = calculate_standings


if __name__ == "__main__":
    drivers_standings = calculate_driver_standings()
    teams_standings = calculate_team_standings()

    if drivers_standings is not None:
        print("\n=== CLASSIFICACAO DE PILOTOS - TEMPORADA 2026 ===")
        print(drivers_standings.to_string(index=False))

    if teams_standings is not None:
        print("\n=== CLASSIFICACAO DE CONSTRUTORES - TEMPORADA 2026 ===")
        print(teams_standings.to_string(index=False))
