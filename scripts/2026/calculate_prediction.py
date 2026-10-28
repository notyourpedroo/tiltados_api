#!/usr/bin/env python3
"""
Calcular a Chance de título de 2026.

Este módulo combina a classificação atual com as Sessões pendentes do Calendário:
- Situação matemática: Pontos máximos e status (Campeao, Na disputa, Eliminado).
- Simulação (Monte Carlo): cada Sessão pendente é sorteada a partir das posições
  que cada piloto já fez em 2026, e a Chance de título é a porcentagem de
  simulações em que o piloto termina como Campeão, pelo mesmo desempate da
  classificação (calculate_standings.standings_order).
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
    from .calculate_standings import (
        calculate_driver_standings, calculate_team_standings, count_race_finishes, standings_order,
    )
    from .calculate_super_license import SUSPENDED, calculate_super_license
    from .load_calendar import load_calendar
    from .load_races import load_races
    from .load_results import load_results
    from ..errors import read_csv, require_columns, to_int_column
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from calculate_standings import (
        calculate_driver_standings, calculate_team_standings, count_race_finishes, standings_order,
    )
    from calculate_super_license import SUSPENDED, calculate_super_license
    from load_calendar import load_calendar
    from load_races import load_races
    from load_results import load_results
    from errors import read_csv, require_columns, to_int_column

N_SIMULATIONS = 10_000


def _load_points_tables(base_path, size):
    """
    Pontos por posição (índice = posição) para corrida e sprint, a partir do scores.csv.
    Cobre pelo menos até `size` e até a última posição que pontua.
    """
    scores_file = os.path.join(base_path, "scores.csv")
    df_scores = read_csv(scores_file)
    require_columns(df_scores, ["position", "points", "is_sprint"], scores_file)
    df_scores["position"] = to_int_column(df_scores, "position", scores_file)
    df_scores["points"] = to_int_column(df_scores, "points", scores_file)

    size = max([size, *df_scores["position"]])
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


def _simulate_pending_sessions(histories, presence, suspended, pending, tables, rng, n_simulations):
    """
    Simula as Sessões pendentes e devolve, por simulação (linhas) e piloto (colunas),
    os pontos, as vitórias em Corridas e os pódios conquistados, além da lista
    (índice da Sessão em `pending`, posições) de cada Corrida pendente, com posição
    infinita para quem não correu.

    `histories[is_sprint][j]` são as posições que o piloto j sorteia nesse tipo de Sessão,
    `presence[j]` é a probabilidade de ele participar de cada Sessão pendente e `suspended[j]`
    indica se ele fica fora da primeira Corrida pendente (Suspensão).
    """
    n_drivers = len(presence)
    sim_points = np.zeros((n_simulations, n_drivers))
    sim_wins = np.zeros((n_simulations, n_drivers))
    sim_podiums = np.zeros((n_simulations, n_drivers))
    sim_races = []
    suspension_pending = suspended.any()

    for index, is_sprint in enumerate(pending):
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
            sim_races.append((index, np.where(racing, ranks, np.inf)))
        sim_podiums += racing & (ranks <= 3)

    return sim_points, sim_wins, sim_podiums, sim_races


def _final_race_finishes(season, ids, by, owner):
    """
    Posições em Corridas de cada competidor (pilotos ou equipes, alinhados a `ids`) ao fim de
    cada simulação: as das Corridas disputadas, contadas como na classificação, e as das
    Corridas pendentes simuladas, que vêm depois delas na ordem do Calendário.
    `owner[j]` é o competidor que recebe os resultados simulados do piloto j.
    """
    n_simulations = len(season["sim_points"])
    worst = len(season["standings"])  # pior posição possível numa Corrida simulada
    tally = count_race_finishes(season["race_results"], ids, by, worst_position=worst).repeat(n_simulations)
    for index, positions in season["sim_races"]:
        tally.add_race(positions, owner, season["n_played"] + index)
    return tally


def _championship_probability(points, wins, podiums, finishes, ids):
    """
    Porcentagem de simulações em que cada coluna é campeã, pelo mesmo desempate da
    classificação (`finishes` é o RaceFinishes de `_final_race_finishes`).
    """
    order = standings_order(points, wins, podiums, finishes.finishes, finishes.first_best, ids)
    counts = np.bincount(order[:, 0], minlength=points.shape[1])
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
    """Preposição + nome do rival: "de Matheus", "da Ferrari", "com a Ferrari"; sem preposição, "Matheus" ou "a Ferrari"."""
    if not is_team:
        return f"{preposition} {name}" if preposition else name
    return {None: f"a {name}", "de": f"da {name}", "com": f"com a {name}", "sobre": f"sobre a {name}"}[preposition]


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


def _pending_sessions(n_pending):
    """As Sessões pendentes com artigo: ("as 5 Sessões pendentes", "nas 5 Sessões pendentes") ou "a única"."""
    if n_pending == 1:
        return "a única Sessão pendente", "na única Sessão pendente"
    return f"as {n_pending} Sessões pendentes", f"nas {n_pending} Sessões pendentes"


def _eliminated_reason(i, names, points, max_points, n_pending, is_team, team_drivers):
    """Motivo de quem está Eliminado com Sessões pendentes: nem os Pontos máximos alcançam o líder."""
    leader = f"abaixo dos {_format_number(points[0])} {_ref('de', names[0], is_team)}"
    reach = f"chega a no máximo {_count(max_points[i], 'ponto', 'pontos')}, {leader}."
    sessions, in_sessions = _pending_sessions(n_pending)
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


def _exact_tie_reason(i, names, n_pending, is_team, team_drivers):
    """Motivo de quem tem Pontos máximos iguais aos pontos do líder: só alcança vencendo tudo e indo ao desempate."""
    sessions, in_sessions = _pending_sessions(n_pending)
    if is_team and team_drivers[i] >= 2:
        needs = f"fazendo 1º e 2º {in_sessions}"
    else:
        needs = f"vencendo {sessions}"
    leader = names[0] if not is_team else f"a {names[0]}"
    return f"Só alcança {leader} {needs}, e ainda dependeria do desempate."


def _in_pending_sessions(n_pending):
    """Em quantas Sessões pendentes: "em 5 Sessões pendentes" ou "na única Sessão pendente"."""
    return _pending_sessions(n_pending)[1] if n_pending == 1 else f"em {n_pending} Sessões pendentes"


def _zero_chance_reason(i, names, points, n_pending, n_simulations, is_team):
    """Motivo de quem está Na disputa com Chance de título exibida como 0,0: a distância para o líder."""
    champion = "campeã" if is_team else "campeão"
    gap = _count(points[0] - points[i], "ponto", "pontos")
    return (
        f"Ainda está na disputa pela matemática, mas quase nunca é {champion} nas "
        f"{_format_number(n_simulations)} simulações: precisaria tirar {gap} {_ref('de', names[0], is_team)} "
        f"{_in_pending_sessions(n_pending)}."
    )


def _full_chance_reason(names, points, n_pending, n_simulations, is_team):
    """Motivo do líder Na disputa com Chance de título exibida como 100,0: o que o 2º precisaria tirar."""
    if is_team:
        not_yet, champion, runner_up = "Campeã de Construtores", "campeã", f"a {names[1]}"
    else:
        not_yet, champion, runner_up = "Campeão", "campeão", names[1]
    gap = _count(points[0] - points[1], "ponto", "pontos")
    return (
        f"Ainda não é {not_yet} pela matemática, mas é {champion} em quase todas as "
        f"{_format_number(n_simulations)} simulações: {runner_up} precisaria tirar {gap} "
        f"{_in_pending_sessions(n_pending)}."
    )


def _floor_zero_reason(i, names, points, max_points, n_pending, is_team, floor):
    """
    Motivo de quem está Na disputa com Chance de título exibida como 0,0 quando o líder, repetindo
    o pior resultado de 2026, ainda fica à frente dos seus Pontos máximos.
    """
    gain, worst = floor
    lead = points[0] - points[i]
    loss = max_points[i] - points[i] - gain  # o que o rival ganha a mais que o líder, no máximo
    in_sessions = _pending_sessions(n_pending)[1]
    if loss > 0:
        keeps = f"perde no máximo {_count(loss, 'ponto', 'pontos')}"
        than_lead = f", menos que os {_format_number(lead)} de vantagem"
    else:
        keeps, than_lead = f"mantém toda a vantagem de {_count(lead, 'ponto', 'pontos')}", ""
    if is_team:
        return (
            f"Ainda está na disputa pela matemática, mas, repetindo o pior resultado de cada piloto {worst}, "
            f"{_ref(None, names[0], is_team)} {keeps} {in_sessions}{than_lead}."
        )
    return f"Ainda está na disputa pela matemática, mas {names[0]} {worst}; repetindo isso {in_sessions}, {keeps}{than_lead}."


def _floor_full_reason(names, points, max_points, n_pending, is_team, floor):
    """
    Motivo do líder Na disputa com Chance de título exibida como 100,0 quando, repetindo o pior
    resultado de 2026, ainda fica à frente dos Pontos máximos de todo rival Na disputa (o texto cita o 2º).
    """
    gain, worst = floor
    lead = _count(points[0] - points[1], "ponto", "pontos")
    loss = max_points[1] - points[1] - gain  # o que o 2º ganha a mais que o líder, no máximo
    in_sessions = _pending_sessions(n_pending)[1]
    takes = f"tira no máximo {_format_number(loss)} dos {lead} de vantagem" if loss > 0 else f"não diminui a vantagem de {lead}"
    if is_team:
        return (
            f"Ainda não é Campeã de Construtores pela matemática, mas, repetindo o pior resultado de cada piloto "
            f"{worst}, {_ref(None, names[1], is_team)} {takes} {in_sessions}."
        )
    return f"Ainda não é Campeão pela matemática, mas {worst}; repetindo isso {in_sessions}, {names[1]} {takes}."


def _floor_holds(i, points, max_points, statuses, leader_floor):
    """
    Se o argumento do pior resultado vale para a linha i: o líder, somando o ganho mínimo, fica acima
    dos Pontos máximos do rival i; para o próprio líder, acima dos de todo rival Na disputa.
    """
    if leader_floor is None:
        return False
    rivals = [j for j in range(1, len(statuses)) if statuses[j] == "Na disputa"] if i == 0 else [i]
    return all(points[0] + leader_floor[0] > max_points[j] for j in rivals)


def _contention_main_reason(
    i, names, points, max_points, expected_points, probability, n_pending, n_simulations, is_team, team_drivers,
    floor,
):
    """
    Frase principal do Motivo de quem está Na disputa, do caso mais específico para o texto intermediário.
    `floor` é o argumento do pior resultado do líder, só quando ele vale para esta linha (senão, None).
    """
    if points[i] < points[0] == max_points[i]:
        return _exact_tie_reason(i, names, n_pending, is_team, team_drivers)
    if i > 0 and probability[i] == 0 and points[i] < points[0]:
        if floor:
            return _floor_zero_reason(i, names, points, max_points, n_pending, is_team, floor)
        return _zero_chance_reason(i, names, points, n_pending, n_simulations, is_team)
    if i == 0 and probability[0] == 100 and points[0] > points[1]:
        if floor:
            return _floor_full_reason(names, points, max_points, n_pending, is_team, floor)
        return _full_chance_reason(names, points, n_pending, n_simulations, is_team)
    return _contention_reason(i, names, points, expected_points, n_pending, is_team)


def _probability_reasons(
    rows, expected_points, n_pending, is_team, n_simulations, team_drivers=None, leader_floor=None
):
    """
    Motivo da Chance de título de cada linha (pilotos ou equipes).

    `rows` tem as colunas name, points, max_points, status, wins, podiums, probability
    (a Chance de título como exibida) e extra, na ordem da classificação atual: a 1ª linha
    é o líder, o rival de referência de todos; o próprio líder se compara com o 2º.
    `extra` são as frases extras (Suspensão, presença), que só entram depois da frase
    principal de quem está Na disputa. `expected_points` segue a mesma ordem,
    `team_drivers[i]` é a quantidade de pilotos atuais da equipe i (só para equipes),
    `n_simulations` é a quantidade de simulações e `leader_floor` é o argumento do pior
    resultado do líder, (ganho mínimo nas Sessões pendentes, trecho da frase com o pior
    resultado), ou None quando o líder não tem 100% de presença.
    """
    names = rows["name"].tolist()
    points = rows["points"].to_numpy()
    max_points = rows["max_points"].to_numpy()
    wins = rows["wins"].to_numpy()
    podiums = rows["podiums"].to_numpy()
    probability = rows["probability"].to_numpy()
    statuses = rows["status"].tolist()

    reasons = []
    for i, status in enumerate(statuses):
        if not n_pending:
            reasons.append(_final_reason(i, names, points, wins, podiums, is_team))
        elif status == "Eliminado":
            reasons.append(_eliminated_reason(i, names, points, max_points, n_pending, is_team, team_drivers))
        elif status == "Campeao":
            reasons.append(_champion_reason(i, names, points, max_points, is_team))
        else:
            floor = leader_floor if _floor_holds(i, points, max_points, statuses, leader_floor) else None
            reasons.append(_contention_main_reason(
                i, names, points, max_points, expected_points, probability, n_pending, n_simulations,
                is_team, team_drivers, floor,
            ))

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


SESSION_TYPES = {False: "Corridas", True: "Sprints"}


def _worst_results(season, j):
    """
    Pior resultado do piloto j em 2026 nos tipos de Sessão que a simulação usa para as Sessões pendentes.

    Cada tipo de Sessão pendente usa as posições do piloto no mesmo tipo ou, sem nenhuma, as do
    outro tipo (como a simulação). Devolve o ganho mínimo, a soma dos pontos dessa pior posição
    em cada Sessão pendente, e {tipo usado: pior posição}, com Corridas antes de Sprints.
    """
    positions, tables = season["positions"], season["tables"]
    gain, worst = 0, {}
    for is_sprint in season["pending"]:
        source = is_sprint if positions[is_sprint][j].size else not is_sprint
        worst[source] = int(positions[source][j].max())
        table = tables[is_sprint]
        gain += table[worst[source]] if worst[source] < len(table) else 0
    return gain, dict(sorted(worst.items()))


def _has_full_presence(season, j):
    """Se o piloto j disputou todas as Corridas da temporada (ou todas as Sessões, se só correu Sprints)."""
    played, total, _ = season["presence_counts"][j]
    return played == total


def _driver_floor(season):
    """
    Argumento do pior resultado do líder de pilotos: (ganho mínimo, "nunca terminou abaixo do 6º em
    Corridas de 2026"; "venceu todas as Corridas de 2026" quando o pior resultado é a vitória),
    ou None se ele não tem 100% de presença.
    """
    if not len(season["standings"]) or not _has_full_presence(season, 0):
        return None
    gain, worst = _worst_results(season, 0)
    won = [SESSION_TYPES[source] for source, position in worst.items() if position == 1]
    below = [f"do {position}º em {SESSION_TYPES[source]}" for source, position in worst.items() if position > 1]
    parts = ([f"venceu todas as {' e '.join(won)}"] if won else []) + (
        [f"nunca terminou abaixo {' nem '.join(below)}"] if below else []
    )
    return gain, f"{' e '.join(parts)} de 2026"


def _team_floor(season, team_id):
    """
    Argumento do pior resultado da equipe líder: (soma do ganho mínimo de cada piloto atual,
    "em Corridas de 2026 (Matheus 6º, Erick 9º)"), ou None se ela não tem piloto atual ou se
    algum deles não tem 100% de presença. Os pilotos seguem a ordem da classificação.
    """
    standings = season["standings"]
    drivers = np.flatnonzero((standings["team_id"] == team_id).to_numpy())
    if not drivers.size or not all(_has_full_presence(season, j) for j in drivers):
        return None
    names = standings["driver_name"].to_numpy()[drivers]
    gains, worsts = zip(*(_worst_results(season, j) for j in drivers))

    if len(worsts[0]) == 1 and all(worst.keys() == worsts[0].keys() for worst in worsts):
        (source,) = worsts[0]
        listed = ", ".join(f"{name} {worst[source]}º" for name, worst in zip(names, worsts))
        return sum(gains), f"em {SESSION_TYPES[source]} de 2026 ({listed})"
    listed = ", ".join(
        f"{name} " + " e ".join(f"{position}º em {SESSION_TYPES[source]}" for source, position in worst.items())
        for name, worst in zip(names, worsts)
    )
    return sum(gains), f"em 2026 ({listed})"


def _displayed_probability(status, probability):
    """Chance de título como exibida: 0 para Eliminado, 100 para Campeao e arredondada a 1 casa."""
    status = np.asarray(status)
    probability = np.where(status == "Eliminado", 0.0, np.where(status == "Campeao", 100.0, probability))
    return np.round(probability, 1)


def _finish(df, probability, expected_points, sort_key):
    """Aplica 0/100 pelo status, arredonda e ordena pela Chance de título."""
    df["championship_probability"] = _displayed_probability(df["status"], probability)
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
    pendentes (`pending`), as tabelas de pontos (`tables`), por piloto (na ordem da classificação)
    as posições que ele fez em cada tipo de Sessão em 2026 (`positions[is_sprint][j]`), as contagens
    que formam a presença (`presence_counts[j]` = (disputadas, da temporada, "Corridas" ou "Sessões"))
    e a Suspensão pendente (`suspended`), e, por simulação e piloto, `sim_points`, `sim_wins` e
    `sim_podiums`. Para o desempate, traz também os resultados das Corridas disputadas com a ordem
    cronológica da Sessão (`race_results`), a quantidade de Sessões disputadas (`n_played`, a ordem
    da 1ª Sessão pendente) e as posições de cada Corrida pendente simulada (`sim_races`).
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

    # Suspensão a cumprir: o mesmo cálculo da rota da Superlicença
    super_license = calculate_super_license(
        base_path_sl=base_path_sl, base_path_2026=base_path, base_path_2025=base_path_2025,
    )
    suspended_ids = super_license.loc[super_license["status"] == SUSPENDED, "driver_id"]
    suspended = standings["driver_id"].isin(suspended_ids).to_numpy()

    sim_points, sim_wins, sim_podiums, sim_races = _simulate_pending_sessions(
        histories, presence, suspended, pending, tables, rng, n_simulations
    )

    # Corridas disputadas com a ordem cronológica da Sessão (load_races já vem em ordem), para o desempate
    session_order = df_races[["race_id"]].assign(session_order=range(len(df_races)))
    race_results = results.loc[~results["is_sprint"]].merge(session_order, on="race_id")
    return {
        "standings": standings,
        "pending": pending,
        "tables": tables,
        "positions": positions,
        "presence_counts": presence_counts,
        "suspended": suspended,
        "sim_points": sim_points,
        "sim_wins": sim_wins,
        "sim_podiums": sim_podiums,
        "race_results": race_results,
        "n_played": len(df_races),
        "sim_races": sim_races,
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
    driver_ids = standings["driver_id"].to_numpy()
    finishes = _final_race_finishes(season, driver_ids.tolist(), "driver_id", owner=np.arange(len(standings)))
    probability = _championship_probability(final_points, final_wins, final_podiums, finishes, driver_ids)
    df["probability_reason"] = _probability_reasons(
        df.assign(name=df["driver_name"], wins=standings["wins"], podiums=standings["podiums"],
                  probability=_displayed_probability(df["status"], probability),
                  extra=_driver_extras(season["suspended"], season["presence_counts"])),
        np.round(expected_points, 1), len(pending), is_team=False, n_simulations=len(final_points),
        leader_floor=_driver_floor(season),
    )
    df = _finish(df, probability, expected_points, sort_key="position")

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
    team_ids = team_standings["team_id"].to_numpy()
    row_of = {team_id: i for i, team_id in enumerate(team_ids.tolist())}
    finishes = _final_race_finishes(
        season, list(row_of), "team_id", owner=np.array([row_of[team_id] for team_id in current_team.tolist()])
    )
    probability = _championship_probability(final_points, final_wins, final_podiums, finishes, team_ids)
    df["probability_reason"] = _probability_reasons(
        df.assign(name=df["team_name"], wins=team_standings["wins"], podiums=team_standings["podiums"],
                  probability=_displayed_probability(df["status"], probability),
                  extra=_team_extras(df["team_id"], season["standings"], season["suspended"])),
        np.round(expected_points, 1), len(pending), is_team=True, team_drivers=team_drivers,
        n_simulations=len(final_points),
        leader_floor=_team_floor(season, df["team_id"].iloc[0]) if len(df) else None,
    )
    df = _finish(df, probability, expected_points, sort_key="position")

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
