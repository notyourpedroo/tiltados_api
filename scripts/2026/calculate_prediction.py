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
    from .calculate_super_license import INITIAL_SUPER_LICENSE_POINTS
    from .load_calendar import load_calendar
    from .load_punishments import load_punishments
    from .load_races import load_races
    from .load_results import load_results
    from ..errors import read_csv, require_columns, to_int_column
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from calculate_standings import calculate_driver_standings, calculate_team_standings
    from calculate_super_license import INITIAL_SUPER_LICENSE_POINTS
    from load_calendar import load_calendar
    from load_punishments import load_punishments
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


def _suspended_drivers(driver_ids, df_races, df_punishments):
    """
    Indica, para cada piloto, se ele tem Suspensão a cumprir na próxima Corrida.

    A Suspensão vem da última punição que deixou a Superlicença zerada (ou abaixo de zero)
    e está cumprida se houve alguma Corrida disputada depois da Sessão dessa punição.
    """
    session_order = {race_id: i for i, race_id in enumerate(df_races["race_id"])}
    race_orders = [i for i, is_sprint in enumerate(df_races["is_sprint"]) if not is_sprint]

    punishments = df_punishments.assign(order=df_punishments["race_id"].map(session_order))
    punishments = punishments.sort_values("order", kind="stable")

    suspended = []
    for driver_id in driver_ids:
        driver_punishments = punishments[punishments["driver_id"] == driver_id]
        remaining = INITIAL_SUPER_LICENSE_POINTS
        zeroed_at = None
        for deduction, order in zip(driver_punishments["deduction_points"], driver_punishments["order"]):
            remaining -= deduction
            if remaining <= 0:
                zeroed_at = order
        suspended.append(zeroed_at is not None and not any(order > zeroed_at for order in race_orders))
    return np.array(suspended, dtype=bool)


def _simulate_pending_sessions(histories, presence, suspended, pending, tables, rng, n_simulations):
    """
    Simula as Sessões pendentes e devolve, por simulação (linhas) e piloto (colunas),
    os pontos, as vitórias em Corridas e os pódios conquistados.

    `histories[is_sprint][j]` são as posições que o piloto j sorteia nesse tipo de Sessão,
    `presence[j]` é a probabilidade de ele participar de cada Sessão pendente e `suspended[j]`
    indica se ele fica fora da primeira Corrida pendente (Suspensão).
    """
    n_drivers = len(presence)
    sim_points = np.zeros((n_simulations, n_drivers))
    sim_wins = np.zeros((n_simulations, n_drivers))
    sim_podiums = np.zeros((n_simulations, n_drivers))
    suspension_pending = suspended.any()

    for is_sprint in pending:
        # Cada participante sorteia uma das suas posições; quem não corre fica no fim (inf)
        draws = np.full((n_simulations, n_drivers), np.inf)
        for j, history in enumerate(histories[is_sprint]):
            draws[:, j] = rng.choice(history, n_simulations)
        draws[rng.random((n_simulations, n_drivers)) >= presence] = np.inf
        if suspension_pending and not is_sprint:
            draws[:, suspended] = np.inf
            suspension_pending = False
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


def _simulate_season(base_path, base_path_2025, base_path_sl, n_simulations):
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

    # Posições de cada piloto em Corridas e em Sprints de 2026. Cada tipo de Sessão pendente
    # sorteia das posições do mesmo tipo; quem não tem nenhuma usa as do outro tipo.
    results = df_results.merge(df_races[["race_id", "is_sprint"]], on="race_id")
    positions = {
        is_sprint: [
            results.loc[(results["driver_id"] == driver_id) & (results["is_sprint"] == is_sprint),
                        "driver_final_position"].to_numpy()
            for driver_id in standings["driver_id"]
        ]
        for is_sprint in (False, True)
    }
    histories = {
        is_sprint: [own if own.size else other for own, other in zip(positions[is_sprint], positions[not is_sprint])]
        for is_sprint in (False, True)
    }

    # Presença: Corridas disputadas pelo piloto / Corridas da temporada; sem Corrida, a razão sobre Sessões
    races_played = results.loc[~results["is_sprint"], "race_id"].nunique()
    sessions_played = results["race_id"].nunique()
    presence = np.array([
        races.size / races_played if races.size else sprints.size / sessions_played
        for races, sprints in zip(positions[False], positions[True])
    ])

    # Semente derivada dos dados: os mesmos CSVs dão sempre a mesma resposta
    seed_data = pd.util.hash_pandas_object(results, index=False).to_numpy().tobytes() + repr(pending).encode()
    rng = np.random.default_rng(zlib.crc32(seed_data))

    df_punishments = load_punishments(
        base_path=base_path_sl, season_year=2026, enriched=True,
        base_path_2026=base_path, base_path_2025=base_path_2025,
    )
    suspended = _suspended_drivers(standings["driver_id"], df_races, df_punishments)

    sim_points, sim_wins, sim_podiums = _simulate_pending_sessions(
        histories, presence, suspended, pending, tables, rng, n_simulations
    )
    return {
        "standings": standings,
        "pending": pending,
        "tables": tables,
        "rng": rng,
        "sim_points": sim_points,
        "sim_wins": sim_wins,
        "sim_podiums": sim_podiums,
    }


def _driver_prediction(season):
    """
    Chance de título de cada piloto, a partir da temporada simulada.

    Colunas do DataFrame retornado:
    - position: Posição nesta lista (ordenada pela Chance de título)
    - driver_id, driver_name, team_id, team_name: Piloto e equipe atual
    - points: Pontos atuais
    - max_points: Pontos máximos (atuais + tudo que ainda dá para ganhar)
    - status: Campeao, Na disputa ou Eliminado
    - championship_probability: Chance de título, em porcentagem (1 casa)
    - expected_points: Média dos pontos finais nas simulações
    """
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


def _team_prediction(season, team_standings):
    """
    Chance de título de cada equipe, a partir da temporada simulada.
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
    pending, tables = season["pending"], season["tables"]
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

        scoring_positions = min(int(drivers.sum()), 2)
        max_points.append(points + int(sum(tables[is_sprint][1:scoring_positions + 1].sum() for is_sprint in pending)))

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


def calculate_prediction(
    base_path="./files/2026",
    base_path_2025="./files/2025",
    base_path_sl="./files/super_license",
    n_simulations=N_SIMULATIONS,
):
    """
    Função principal da Chance de título de 2026.

    Simula as Sessões pendentes uma única vez e usa as mesmas simulações
    para o campeonato de pilotos e o de construtores.

    Args:
        base_path (str): Caminho base dos arquivos de 2026.
        base_path_2025 (str): Caminho base dos arquivos de 2025.
        base_path_sl (str): Caminho da pasta de punições da Superlicença.
        n_simulations (int): Quantidade de simulações.

    Returns:
        dict: {'drivers': pd.DataFrame, 'teams': pd.DataFrame} com a Chance de título de pilotos e equipes.
    """
    season = _simulate_season(base_path, base_path_2025, base_path_sl, n_simulations)
    team_standings = calculate_team_standings(base_path=base_path, base_path_2025=base_path_2025)
    return {
        "drivers": _driver_prediction(season),
        "teams": _team_prediction(season, team_standings),
    }


if __name__ == "__main__":
    prediction = calculate_prediction()

    print("\n=== CHANCE DE TITULO DE PILOTOS - TEMPORADA 2026 ===")
    print(prediction["drivers"].to_string(index=False))

    print("\n=== CHANCE DE TITULO DE CONSTRUTORES - TEMPORADA 2026 ===")
    print(prediction["teams"].to_string(index=False))
