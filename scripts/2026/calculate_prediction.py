#!/usr/bin/env python3
"""
Calcular a Chance de título de 2026.

Este módulo combina a classificação atual com as Sessões pendentes do Calendário:
- Situação matemática: Pontos máximos e status (Campeao, Na disputa, Eliminado).
- Simulação (Monte Carlo): cada Sessão pendente é sorteada a partir das posições
  que cada piloto já fez em 2026, e a Chance de título é a porcentagem de
  simulações em que o piloto termina como Campeão.
- Motivo da Chance de título: a frase que explica a situação de cada piloto ou
  equipe, montada por templates a partir dos mesmos dados.
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


def _format_number(value):
    """Número no padrão brasileiro: milhar com ponto, decimal com vírgula e inteiro sem ',0'."""
    value = float(value)
    if value.is_integer():
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _count(value, singular, plural):
    """Quantidade com a palavra no singular ou no plural: "1 ponto", "509,5 pontos"."""
    return f"{_format_number(value)} {singular if value == 1 else plural}"


def _ref(preposition, name, is_team):
    """Preposição + nome do rival: "de Matheus", "da Ferrari", "com a Ferrari", "sobre a Ferrari"."""
    if not is_team:
        return f"{preposition} {name}"
    return {"de": f"da {name}", "com": f"com a {name}", "sobre": f"sobre a {name}"}[preposition]


def _tiebreak_sentence(i, names, points, wins, podiums, is_team):
    """Frase do desempate quando a posição final empatou em pontos com o vizinho de cima (ou, senão, o de baixo)."""
    for j, result in ((i - 1, "perdeu"), (i + 1, "venceu")):
        if 0 <= j < len(names) and points[j] == points[i]:
            rival = _ref("com", names[j], is_team)
            if wins[j] != wins[i]:
                return f"Empatou em pontos {rival} e {result} no desempate por vitórias."
            if podiums[j] != podiums[i]:
                return f"Empatou em pontos {rival} e {result} no desempate por pódios."
            return f"Empatou em pontos, vitórias e pódios {rival}."
    return ""


def _final_reason(i, names, points, wins, podiums, is_team):
    """Motivo sem Sessões pendentes: posição final e distância para o campeão."""
    if i == 0:
        text = f"Terminou a temporada em 1º, com {_count(points[0], 'ponto', 'pontos')}."
    elif points[i] == points[0]:
        text = f"Terminou em {i + 1}º, com {_count(points[i], 'ponto', 'pontos')}."
    else:
        gap = _count(points[0] - points[i], "ponto", "pontos")
        text = f"Terminou em {i + 1}º, {gap} atrás {_ref('de', names[0], is_team)}."
    tiebreak = _tiebreak_sentence(i, names, points, wins, podiums, is_team)
    return f"{text} {tiebreak}" if tiebreak else text


def _eliminated_reason(i, names, points, max_points, n_pending, is_team, team_drivers):
    """Motivo de quem está Eliminado com Sessões pendentes: nem os Pontos máximos alcançam o líder."""
    leader = f"abaixo dos {_format_number(points[0])} {_ref('de', names[0], is_team)}"
    reach = f"chega a no máximo {_count(max_points[i], 'ponto', 'pontos')}, {leader}."
    if n_pending == 1:
        sessions, in_sessions = "a única Sessão pendente", "na única Sessão pendente"
    else:
        sessions, in_sessions = f"as {n_pending} Sessões pendentes", f"nas {n_pending} Sessões pendentes"
    if not is_team:
        return f"Mesmo vencendo {sessions}, {reach}"
    if team_drivers[i] == 0:
        return f"Sem nenhum piloto atual, não soma mais pontos e fica com {_format_number(points[i])}, {leader}."
    if team_drivers[i] == 1:
        return f"Com um único piloto, mesmo vencendo {sessions}, {reach}"
    return f"Mesmo fazendo 1º e 2º {in_sessions}, {reach}"


def _champion_reason(i, names, points, max_points, is_team):
    """Motivo do Campeão antecipado: nenhum rival alcança mais os seus pontos."""
    nobody = "Nenhuma equipe" if is_team else "Nenhum rival"
    text = f"{nobody} alcança mais os seus {_count(points[i], 'ponto', 'pontos')}"
    rivals = [j for j in range(len(names)) if j != i]
    if not rivals:
        return f"{text}."
    closest = max(rivals, key=lambda j: max_points[j])  # no empate, o mais bem classificado
    the_closest = "a mais próxima" if is_team else "o mais próximo"
    return f"{text}: {the_closest}, {names[closest]}, chega a no máximo {_format_number(max_points[closest])}."


def _contention_reason(i, names, points, expected_points, n_pending, is_team):
    """Motivo de quem está Na disputa: só fatos (distância, Sessões pendentes e pontos médios nas simulações)."""
    rival = 1 if i == 0 else 0
    sessions = _count(n_pending, "Sessão pendente", "Sessões pendentes")
    gap = int(points[0] - points[max(i, 1)])  # do líder para quem não lidera; do líder para o 2º
    averages = (
        f"nas simulações termina em média com {_count(expected_points[i], 'ponto', 'pontos')}, "
        f"contra {_format_number(expected_points[rival])} {_ref('de', names[rival], is_team)}."
    )
    if gap == 0:
        return f"Divide a liderança em pontos {_ref('com', names[rival], is_team)}, com {sessions}; {averages}"
    if i == 0:
        advantage = _count(gap, "ponto", "pontos")
        return f"Lidera com {advantage} de vantagem {_ref('sobre', names[rival], is_team)} e {sessions}; {averages}"
    return f"Está a {_count(gap, 'ponto', 'pontos')} {_ref('de', names[rival], is_team)} com {sessions}; {averages}"


def _probability_reasons(rows, expected_points, n_pending, is_team, team_drivers=None):
    """
    Motivo da Chance de título de cada linha (pilotos ou equipes).

    `rows` tem as colunas name, points, max_points, status, wins, podiums e extra, na ordem da
    classificação atual: a 1ª linha é o líder, o rival de referência de todos; o próprio
    líder se compara com o 2º. `extra` são as frases extras (Suspensão, presença), que só
    entram depois da frase principal de quem está Na disputa. `expected_points` segue a
    mesma ordem, e `team_drivers[i]` é a quantidade de pilotos atuais da equipe i (só para equipes).
    """
    names = rows["name"].tolist()
    points = rows["points"].to_numpy()
    max_points = rows["max_points"].to_numpy()
    wins = rows["wins"].to_numpy()
    podiums = rows["podiums"].to_numpy()

    reasons = []
    for i, status in enumerate(rows["status"]):
        if not n_pending:
            reasons.append(_final_reason(i, names, points, wins, podiums, is_team))
        elif status == "Eliminado":
            reasons.append(_eliminated_reason(i, names, points, max_points, n_pending, is_team, team_drivers))
        elif status == "Campeao":
            reasons.append(_champion_reason(i, names, points, max_points, is_team))
        else:
            reasons.append(_contention_reason(i, names, points, expected_points, n_pending, is_team))

    # Frases extras (Suspensão, presença) só para quem está Na disputa, depois da frase principal
    return [
        f"{reason} {extra}" if status == "Na disputa" and extra else reason
        for reason, status, extra in zip(reasons, rows["status"], rows["extra"])
    ]


def _driver_extras(suspended, presence_counts):
    """Frases extras de cada piloto: Suspensão pendente na próxima Corrida e, depois, presença abaixo de 100%."""
    extras = []
    for is_suspended, (played, total, sessions) in zip(suspended, presence_counts):
        sentences = ["Fica fora da próxima Corrida por Suspensão."] if is_suspended else []
        if played < total:
            sentences.append(
                f"Disputou {_format_number(played)} das {_format_number(total)} {sessions}, "
                "então nas simulações corre só parte das Sessões pendentes."
            )
        extras.append(" ".join(sentences))
    return extras


def _team_extras(team_ids, standings, suspended):
    """Frases extras de cada equipe: os pilotos atuais dela suspensos na próxima Corrida, na ordem da classificação."""
    extras = []
    for team_id in team_ids:
        names = standings.loc[suspended & (standings["team_id"] == team_id).to_numpy(), "driver_name"].tolist()
        if not names:
            extras.append("")
        elif len(names) == 1:
            extras.append(f"{names[0]} fica fora da próxima Corrida por Suspensão.")
        else:
            extras.append(f"{', '.join(names[:-1])} e {names[-1]} ficam fora da próxima Corrida por Suspensão.")
    return extras


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
    usado (`rng`), por piloto (na ordem da classificação) as posições sorteadas em cada
    tipo de Sessão (`histories[is_sprint][j]`), a presença (`presence`), as contagens que
    formam a presença (`presence_counts[j]` = (disputadas, da temporada, "Corridas" ou "Sessões"))
    e a Suspensão pendente (`suspended`), e, por simulação e piloto, `sim_points`, `sim_wins` e `sim_podiums`.
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
    presence_counts = [
        (races.size, races_played, "Corridas") if races.size else (sprints.size, sessions_played, "Sessões")
        for races, sprints in zip(positions[False], positions[True])
    ]
    presence = np.array([played / total for played, total, _ in presence_counts])

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
        "histories": histories,
        "presence": presence,
        "presence_counts": presence_counts,
        "suspended": suspended,
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
    - probability_reason: Motivo da Chance de título (frase em PT-BR)
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
    expected_points = final_points.mean(axis=0)
    df["probability_reason"] = _probability_reasons(
        df.assign(name=df["driver_name"], wins=standings["wins"], podiums=standings["podiums"],
                  extra=_driver_extras(season["suspended"], season["presence_counts"])),
        np.round(expected_points, 1), len(pending), is_team=False,
    )
    df = _finish(
        df,
        _championship_probability(final_points, final_wins, final_podiums, season["rng"]),
        expected_points,
        sort_key="position",
    )

    cols = [
        "position", "driver_id", "driver_name", "team_id", "team_name", "points",
        "max_points", "status", "championship_probability", "expected_points", "probability_reason"
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
    - probability_reason: Motivo da Chance de título (frase em PT-BR)
    """
    pending, tables = season["pending"], season["tables"]
    current_team = season["standings"]["team_id"].to_numpy()

    # Somar os resultados simulados dos pilotos de cada equipe atual
    final = {"points": [], "wins": [], "podiums": []}
    max_points = []
    team_drivers = []
    for team_id, points, wins, podiums in zip(
        team_standings["team_id"], team_standings["points"], team_standings["wins"], team_standings["podiums"]
    ):
        drivers = current_team == team_id
        final["points"].append(points + season["sim_points"][:, drivers].sum(axis=1))
        final["wins"].append(wins + season["sim_wins"][:, drivers].sum(axis=1))
        final["podiums"].append(podiums + season["sim_podiums"][:, drivers].sum(axis=1))

        team_drivers.append(int(drivers.sum()))
        scoring_positions = min(team_drivers[-1], 2)
        max_points.append(points + int(sum(tables[is_sprint][1:scoring_positions + 1].sum() for is_sprint in pending)))

    final_points, final_wins, final_podiums = (np.column_stack(final[key]) for key in ("points", "wins", "podiums"))

    df = team_standings[["position", "team_id", "team_name", "points"]].copy()
    df["max_points"] = max_points
    df["status"] = _title_status(
        df["points"].to_numpy(), df["max_points"].to_numpy(), bool(pending), df["position"].to_numpy()
    )
    expected_points = final_points.mean(axis=0)
    df["probability_reason"] = _probability_reasons(
        df.assign(name=df["team_name"], wins=team_standings["wins"], podiums=team_standings["podiums"],
                  extra=_team_extras(df["team_id"], season["standings"], season["suspended"])),
        np.round(expected_points, 1), len(pending), is_team=True, team_drivers=team_drivers,
    )
    df = _finish(
        df,
        _championship_probability(final_points, final_wins, final_podiums, season["rng"]),
        expected_points,
        sort_key="position",
    )

    cols = ["position", "team_id", "team_name", "points", "max_points", "status",
            "championship_probability", "expected_points", "probability_reason"]
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

    for title, df, name in (
        ("PILOTOS", prediction["drivers"], "driver_name"),
        ("CONSTRUTORES", prediction["teams"], "team_name"),
    ):
        print(f"\n=== CHANCE DE TITULO DE {title} - TEMPORADA 2026 ===")
        print(df.drop(columns="probability_reason").to_string(index=False))
        print("\nMotivos:")
        for row_name, reason in zip(df[name], df["probability_reason"]):
            print(f"- {row_name}: {reason}")
