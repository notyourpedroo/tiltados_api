#!/usr/bin/env python3
"""
Calcular a Chance de título de 2026.

Este módulo combina a classificação atual com as Sessões pendentes do Calendário:
- Situação matemática: Pontos máximos e status (Campeao, Na disputa, Eliminado).
- Simulação (Monte Carlo): cada Sessão pendente é sorteada a partir das posições
  que cada piloto já fez em 2026, e a Chance de título é a porcentagem de
  simulações em que o piloto termina como Campeão.
"""

import os
import sys
import zlib

import numpy as np
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .calculate_standings import calculate_driver_standings, calculate_team_standings
    from .load_calendar import load_calendar
    from .load_races import load_races
    from .load_results import load_results
    from ..errors import read_csv, require_columns, to_int_column
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from calculate_standings import calculate_driver_standings, calculate_team_standings
    from load_calendar import load_calendar
    from load_races import load_races
    from load_results import load_results
    from errors import read_csv, require_columns, to_int_column

N_SIMULATIONS = 10_000


def _load_points_tables(base_path, size):
    """Pontos por posição (índice = posição, até `size`) para corrida e sprint, a partir do scores.csv."""
    scores_file = os.path.join(base_path, "scores.csv")
    df_scores = read_csv(scores_file)
    require_columns(df_scores, ["position", "points", "is_sprint"], scores_file)
    df_scores["position"] = to_int_column(df_scores, "position", scores_file)
    df_scores["points"] = to_int_column(df_scores, "points", scores_file)

    tables = {False: np.zeros(size + 1), True: np.zeros(size + 1)}
    for position, points, is_sprint in zip(df_scores["position"], df_scores["points"], df_scores["is_sprint"]):
        if 1 <= position <= size:
            tables[bool(is_sprint)][position] = points
    return tables


def _title_status(points, max_points, has_pending, positions):
    """Status matemático no título para cada linha (pilotos ou equipes)."""
    if not has_pending:
        return ["Campeao" if position == 1 else "Eliminado" for position in positions]

    leader_points = points.max()
    statuses = []
    for i in range(len(points)):
        rivals_max = np.delete(max_points, i)
        if max_points[i] < leader_points:
            statuses.append("Eliminado")
        elif rivals_max.size == 0 or points[i] > rivals_max.max():
            statuses.append("Campeao")
        else:
            statuses.append("Na disputa")
    return statuses


def _simulate_pending_sessions(histories, pending, tables, rng, n_simulations):
    """
    Simula as Sessões pendentes e devolve, por simulação (linhas) e piloto (colunas),
    os pontos, as vitórias em Corridas e os pódios conquistados.
    """
    n_drivers = len(histories)
    sim_points = np.zeros((n_simulations, n_drivers))
    sim_wins = np.zeros((n_simulations, n_drivers))
    sim_podiums = np.zeros((n_simulations, n_drivers))

    for is_sprint in pending:
        # Cada participante sorteia uma das suas posições; quem não corre fica no fim (inf)
        draws = np.full((n_simulations, n_drivers), np.inf)
        for j, history in enumerate(histories):
            if history.size:
                draws[:, j] = rng.choice(history, n_simulations)
        draws += rng.random((n_simulations, n_drivers))  # desempate aleatório entre posições iguais

        ranks = draws.argsort(axis=1).argsort(axis=1) + 1
        racing = np.isfinite(draws)

        sim_points += np.where(racing, tables[is_sprint][ranks], 0)
        if not is_sprint:
            sim_wins += racing & (ranks == 1)
        sim_podiums += racing & (ranks <= 3)

    return sim_points, sim_wins, sim_podiums


def _championship_probability(points, wins, podiums, rng):
    """Porcentagem de simulações em que cada coluna é campeã (pontos, vitórias, pódios, sorteio)."""
    keys = (points * 1000 + wins) * 1000 + podiums + rng.random(points.shape)
    champions = keys.argmax(axis=1)
    counts = np.bincount(champions, minlength=points.shape[1])
    return counts / points.shape[0] * 100


def _finish(df, probability, expected_points, sort_key):
    """Aplica 0/100 pelo status, arredonda e ordena pela Chance de título."""
    df["championship_probability"] = probability
    df.loc[df["status"] == "Eliminado", "championship_probability"] = 0.0
    df.loc[df["status"] == "Campeao", "championship_probability"] = 100.0
    df["championship_probability"] = df["championship_probability"].round(1)
    df["expected_points"] = np.round(expected_points, 1)

    df = df.sort_values(
        by=["championship_probability", sort_key], ascending=[False, True]
    ).reset_index(drop=True)
    df["position"] = range(1, len(df) + 1)
    return df


def _simulate_season(base_path, base_path_2025, n_simulations):
    """
    Simula as Sessões pendentes para os pilotos da classificação atual.

    Retorna um dict com a classificação de pilotos (`standings`), os tipos das Sessões
    pendentes (`pending`), as tabelas de pontos (`tables`), o gerador aleatório já
    usado (`rng`) e, por simulação e piloto, `sim_points`, `sim_wins` e `sim_podiums`.
    """
    calendar = load_calendar(base_path=base_path)
    standings = calculate_driver_standings(base_path=base_path, base_path_2025=base_path_2025)
    df_results = load_results(base_path=base_path, base_path_2025=base_path_2025)
    df_races = load_races(base_path=base_path, base_path_2025=base_path_2025)

    pending = calendar.loc[~calendar["is_played"], "is_sprint"].tolist()
    tables = _load_points_tables(base_path, size=len(standings))

    # Posições de cada piloto nas Corridas de 2026
    results = df_results.merge(df_races[["race_id", "is_sprint"]], on="race_id")
    races_only = results[~results["is_sprint"]]
    histories = [
        races_only.loc[races_only["driver_id"] == driver_id, "driver_final_position"].to_numpy()
        for driver_id in standings["driver_id"]
    ]

    # Semente derivada dos dados: os mesmos CSVs dão sempre a mesma resposta
    seed_data = pd.util.hash_pandas_object(results, index=False).to_numpy().tobytes() + repr(pending).encode()
    rng = np.random.default_rng(zlib.crc32(seed_data))

    sim_points, sim_wins, sim_podiums = _simulate_pending_sessions(histories, pending, tables, rng, n_simulations)
    return {
        "standings": standings,
        "pending": pending,
        "tables": tables,
        "rng": rng,
        "sim_points": sim_points,
        "sim_wins": sim_wins,
        "sim_podiums": sim_podiums,
    }


def calculate_driver_prediction(
    base_path="./files/2026", base_path_2025="./files/2025", n_simulations=N_SIMULATIONS
):
    """
    Calcula a Chance de título de cada piloto de 2026.

    Colunas do DataFrame retornado:
    - position: Posição nesta lista (ordenada pela Chance de título)
    - driver_id, driver_name, team_id, team_name: Piloto e equipe atual
    - points: Pontos atuais
    - max_points: Pontos máximos (atuais + tudo que ainda dá para ganhar)
    - status: Campeao, Na disputa ou Eliminado
    - championship_probability: Chance de título, em porcentagem (1 casa)
    - expected_points: Média dos pontos finais nas simulações
    """
    season = _simulate_season(base_path, base_path_2025, n_simulations)
    standings, pending, tables = season["standings"], season["pending"], season["tables"]

    final_points = standings["points"].to_numpy() + season["sim_points"]
    final_wins = standings["wins"].to_numpy() + season["sim_wins"]
    final_podiums = standings["podiums"].to_numpy() + season["sim_podiums"]

    df = standings[["position", "driver_id", "driver_name", "team_id", "team_name", "points"]].copy()
    df["max_points"] = df["points"] + int(sum(tables[is_sprint][1] for is_sprint in pending))
    df["status"] = _title_status(
        df["points"].to_numpy(), df["max_points"].to_numpy(), bool(pending), df["position"].to_numpy()
    )
    df = _finish(
        df,
        _championship_probability(final_points, final_wins, final_podiums, season["rng"]),
        final_points.mean(axis=0),
        sort_key="position",
    )

    cols = [
        "position", "driver_id", "driver_name", "team_id", "team_name", "points",
        "max_points", "status", "championship_probability", "expected_points"
    ]
    return df[cols]


def calculate_team_prediction(
    base_path="./files/2026", base_path_2025="./files/2025", n_simulations=N_SIMULATIONS
):
    """
    Calcula a Chance de título de cada equipe no campeonato de construtores de 2026.

    Os pontos simulados de cada piloto vão para a equipe atual dele.

    Colunas do DataFrame retornado:
    - position: Posição nesta lista (ordenada pela Chance de título)
    - team_id, team_name: Equipe
    - points: Pontos atuais
    - max_points: Pontos máximos (atuais + 1º e 2º lugar de cada Sessão pendente,
                  ou só o 1º se a equipe tiver um único piloto)
    - status: Campeao, Na disputa ou Eliminado
    - championship_probability: Chance de título, em porcentagem (1 casa)
    - expected_points: Média dos pontos finais nas simulações
    """
    season = _simulate_season(base_path, base_path_2025, n_simulations)
    pending, tables = season["pending"], season["tables"]
    team_standings = calculate_team_standings(base_path=base_path, base_path_2025=base_path_2025)
    current_team = season["standings"]["team_id"].to_numpy()

    # Somar os resultados simulados dos pilotos de cada equipe atual
    final = {"points": [], "wins": [], "podiums": []}
    max_points = []
    for team_id, points, wins, podiums in zip(
        team_standings["team_id"], team_standings["points"], team_standings["wins"], team_standings["podiums"]
    ):
        drivers = current_team == team_id
        final["points"].append(points + season["sim_points"][:, drivers].sum(axis=1))
        final["wins"].append(wins + season["sim_wins"][:, drivers].sum(axis=1))
        final["podiums"].append(podiums + season["sim_podiums"][:, drivers].sum(axis=1))

        best_positions = min(int(drivers.sum()), 2)
        max_points.append(points + int(sum(tables[s][1:best_positions + 1].sum() for s in pending)))

    final_points, final_wins, final_podiums = (np.column_stack(final[key]) for key in ("points", "wins", "podiums"))

    df = team_standings[["position", "team_id", "team_name", "points"]].copy()
    df["max_points"] = max_points
    df["status"] = _title_status(
        df["points"].to_numpy(), df["max_points"].to_numpy(), bool(pending), df["position"].to_numpy()
    )
    df = _finish(
        df,
        _championship_probability(final_points, final_wins, final_podiums, season["rng"]),
        final_points.mean(axis=0),
        sort_key="position",
    )

    cols = ["position", "team_id", "team_name", "points", "max_points", "status",
            "championship_probability", "expected_points"]
    return df[cols]


def calculate_prediction(type="drivers", base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Função principal da Chance de título de 2026.

    Args:
        type (str): 'drivers' para pilotos ou 'teams'/'constructors' para equipes.
        base_path (str): Caminho base dos arquivos de 2026.
        base_path_2025 (str): Caminho base dos arquivos de 2025.

    Returns:
        pd.DataFrame: Chance de título solicitada.
    """
    if type in ["teams", "constructors"]:
        return calculate_team_prediction(base_path=base_path, base_path_2025=base_path_2025)
    return calculate_driver_prediction(base_path=base_path, base_path_2025=base_path_2025)


if __name__ == "__main__":
    print("\n=== CHANCE DE TITULO DE PILOTOS - TEMPORADA 2026 ===")
    print(calculate_driver_prediction().to_string(index=False))

    print("\n=== CHANCE DE TITULO DE CONSTRUTORES - TEMPORADA 2026 ===")
    print(calculate_team_prediction().to_string(index=False))
