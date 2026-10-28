"""Chance de título de 2026: situação matemática e simulação das Sessões pendentes."""

import csv
import re

from conftest import reset_2026_season, write_calendar, write_session

DRIVERS = "/load/2026/prediction/drivers"
TEAMS = "/load/2026/prediction/teams"
TEAM = "Red Bull"
# Locais do Cadastro de Sessões usados nas temporadas sintéticas
PLAYED = ["australia", "china", "japao", "bahrein", "arabia_saudita", "miami"]
PENDING = ["mexico", "brasil", "las_vegas", "catar", "abu_dhabi"]
# Equipes de 2025, com IDs fixos: Ferrari (2) < McLaren (4)
FERRARI = "Scuderia Ferrari HP"
MCLAREN = "McLaren F1 Team"
SAUBER = "Stake F1 Team Kick Sauber"

DRIVER_FIELDS = {
    "position", "driver_id", "driver_name", "team_id", "team_name", "points",
    "max_points", "status", "championship_probability", "expected_points", "probability_reason",
}


def by_name(rows, key="driver_name"):
    return {row[key]: row for row in rows}


def calendar_rows(data_dir):
    with open(data_dir / "2026" / "calendar.csv", encoding="utf-8") as f:
        return [(r["local"], r["tipo"], r["data"]) for r in csv.DictReader(f)]


def season(data_dir, races, pending, teams=None):
    """
    Temporada sintética: `races` é uma lista de ordens de chegada; `pending` Corridas sem resultado.
    Um `None` na ordem de chegada deixa a posição vazia (ninguém terminou nela).
    `teams` diz a equipe de cada piloto por Corrida (dict piloto -> equipe ou lista de equipes).
    """
    reset_2026_season(data_dir)
    teams = teams or {}

    def team_of(driver, race_index):
        team = teams.get(driver, TEAM)
        return team[race_index] if isinstance(team, list) else team

    played = []
    for i, finishing_order in enumerate(races, start=1):
        local = PLAYED[i - 1]
        write_session(data_dir, f"{local}_race_2026030{i}.csv",
                      [(pos, driver, team_of(driver, i - 1), pos)
                       for pos, driver in enumerate(finishing_order, start=1) if driver])
        played.append((local, "race", f"2026-03-0{i}"))
    write_calendar(data_dir, played + [(PENDING[i], "race", f"2026-12-0{i + 1}") for i in range(pending)])


def test_pilotos_trazem_situacao_e_chance_de_titulo(client):
    response = client.get(DRIVERS)
    assert response.status_code == 200, response.text
    rows = by_name(response.json())

    assert all(set(row) == DRIVER_FIELDS for row in rows.values())
    # Após o GP dos Estados Unidos: Matheus 403 x Yohan 314, com 5 Corridas (125 pts) em jogo
    assert rows["Matheus"]["points"] == 403
    assert rows["Matheus"]["max_points"] == 528
    assert rows["Yohan"]["max_points"] == 439
    assert {name for name, row in rows.items() if row["status"] == "Na disputa"} == {"Matheus", "Yohan"}
    for name, row in rows.items():
        if name not in ("Matheus", "Yohan"):
            assert row["status"] == "Eliminado"
            assert row["championship_probability"] == 0


def test_motivo_do_piloto_eliminado(client):
    # Douglas 223 + 5 x 25 = 348, abaixo dos 403 do líder Matheus
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Douglas"]["probability_reason"] == (
        "Mesmo vencendo as 5 Sessões pendentes, chega a no máximo 348 pontos, abaixo dos 403 de Matheus."
    )


def test_motivo_pelo_pior_resultado_apos_o_gp_dos_estados_unidos(client):
    # Matheus (403, sem faltar) nunca terminou abaixo do 6º em Corridas; correu Sprints, mas só há Corridas
    # pendentes. Nas 5 Corridas, Yohan (314) tira no máximo 25 - 8 = 17 por Corrida, 85, menos que os 89
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Matheus"]["probability_reason"] == (
        "Ainda não é Campeão pela matemática, mas nunca terminou abaixo do 6º em Corridas de 2026; "
        "repetindo isso nas 5 Sessões pendentes, Yohan tira no máximo 85 dos 89 pontos de vantagem."
    )
    assert rows["Yohan"]["probability_reason"] == (
        "Ainda está na disputa pela matemática, mas Matheus nunca terminou abaixo do 6º em Corridas de 2026; "
        "repetindo isso nas 5 Sessões pendentes, perde no máximo 85 pontos, menos que os 89 de vantagem."
    )


def test_todo_piloto_e_toda_equipe_tem_motivo(client):
    for route in (DRIVERS, TEAMS):
        rows = client.get(route).json()
        assert rows and all(row["probability_reason"].strip() for row in rows)


AVERAGES = r"nas simulações termina em média com \d+(,\d)? pontos?, contra \d+(,\d)? (de|da) [A-Za-z ]+\.$"


def test_motivo_na_disputa_traz_distancia_sessoes_pendentes_e_pontos_medios(client, data_dir):
    # Bia 18 + 25 = 43 lidera; Ana 25 + 15 = 40; Caio 15 + 18 = 33
    season(data_dir, [["Ana", "Bia", "Caio"], ["Bia", "Caio", "Ana"]], pending=3)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Bia"]["probability_reason"].startswith(
        "Lidera com 3 pontos de vantagem sobre Ana e 3 Sessões pendentes; ")
    assert rows["Ana"]["probability_reason"].startswith("Está a 3 pontos de Bia com 3 Sessões pendentes; ")
    assert rows["Caio"]["probability_reason"].startswith("Está a 10 pontos de Bia com 3 Sessões pendentes; ")
    for row in rows.values():
        assert re.search("; " + AVERAGES, row["probability_reason"]), row["probability_reason"]


def test_motivo_na_disputa_no_singular(client, data_dir):
    # Bia 18 + 18 = 36 lidera; Ana 25 + 10 = 35
    season(data_dir, [["Ana", "Bia", "Dani"], ["Caio", "Bia", "Dani", "Edu", "Ana"]], pending=1)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Bia"]["probability_reason"].startswith(
        "Lidera com 1 ponto de vantagem sobre Ana e 1 Sessão pendente; ")
    assert rows["Ana"]["probability_reason"].startswith("Está a 1 ponto de Bia com 1 Sessão pendente; ")


def test_motivo_da_equipe_na_disputa(client, data_dir):
    # Ferrari 25 + 15 + 18 + 15 = 73 lidera; Williams 18 + 12 + 25 + 12 = 67
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams", "Dani": "Williams"}
    season(data_dir, [["Ana", "Caio", "Bia", "Dani"], ["Caio", "Ana", "Bia", "Dani"]], pending=3, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Ferrari"]["probability_reason"].startswith(
        "Lidera com 6 pontos de vantagem sobre a Williams e 3 Sessões pendentes; ")
    assert rows["Williams"]["probability_reason"].startswith("Está a 6 pontos da Ferrari com 3 Sessões pendentes; ")
    for row in rows.values():
        assert re.search("; " + AVERAGES, row["probability_reason"]), row["probability_reason"]


def test_chances_de_titulo_somam_100(client, data_dir):
    season(data_dir, [["Ana", "Bia", "Caio"], ["Bia", "Caio", "Ana"], ["Caio", "Ana", "Bia"]], pending=3)
    rows = client.get(DRIVERS).json()

    assert all(row["status"] == "Na disputa" for row in rows)
    assert all(0 < row["championship_probability"] < 100 for row in rows)
    assert abs(sum(row["championship_probability"] for row in rows) - 100) <= 0.2
    probabilities = [row["championship_probability"] for row in rows]
    assert probabilities == sorted(probabilities, reverse=True)
    assert [row["position"] for row in rows] == [1, 2, 3]


def test_sem_sessoes_pendentes_o_lider_e_campeao(client, data_dir):
    played = [row for row in calendar_rows(data_dir) if row[0] not in
              ("mexico", "brasil", "las_vegas", "catar", "abu_dhabi")]
    write_calendar(data_dir, played)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Matheus"]["status"] == "Campeao"
    assert rows["Matheus"]["championship_probability"] == 100
    for row in rows.values():
        assert row["max_points"] == row["points"] == row["expected_points"]
        if row["driver_name"] != "Matheus":
            assert row["status"] == "Eliminado"
    # Matheus 403, Yohan 314, Douglas 223
    assert rows["Matheus"]["probability_reason"] == "Terminou a temporada em 1º, com 403 pontos."
    assert rows["Yohan"]["probability_reason"] == "Terminou em 2º, 89 pontos atrás de Matheus."
    assert rows["Douglas"]["probability_reason"] == "Terminou em 3º, 180 pontos atrás de Matheus."


def test_motivo_de_posicao_final_decidida_no_desempate_por_vitorias(client, data_dir):
    # Caio 18 + 25 = 43; Ana 25 + 8 = 33 com 1 vitória; Bia 15 + 18 = 33 sem vitória
    season(data_dir, [["Ana", "Caio", "Bia", "Dani", "Edu", "Fabi"],
                      ["Caio", "Bia", "Dani", "Edu", "Fabi", "Ana"]], pending=0)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Caio"]["probability_reason"] == "Terminou a temporada em 1º, com 43 pontos."
    assert rows["Ana"]["probability_reason"] == (
        "Terminou em 2º, 10 pontos atrás de Caio. Empatou em pontos com Bia e venceu no desempate por vitórias."
    )
    assert rows["Bia"]["probability_reason"] == (
        "Terminou em 3º, 10 pontos atrás de Caio. Empatou em pontos com Ana e perdeu no desempate por vitórias."
    )


def test_motivo_do_campeao_decidido_no_desempate_por_podios(client, data_dir):
    # Ana 25 + 18 + 0 = 43 com 1 vitória e 2 pódios; Bia 10 + 25 + 8 = 43 com 1 vitória e 1 pódio
    season(data_dir, [["Ana", "Caio", "Dani", "Edu", "Bia", "Fabi"],
                      ["Bia", "Ana", "Caio", "Dani", "Edu", "Fabi"],
                      ["Gil", "Hugo", "Ivo", "Jo", "Ka", "Bia", "Ana"]], pending=0)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["probability_reason"] == (
        "Terminou a temporada em 1º, com 43 pontos. Empatou em pontos com Bia e venceu no desempate por pódios."
    )
    assert rows["Bia"]["probability_reason"] == (
        "Terminou em 2º, com 43 pontos. Empatou em pontos com Ana e perdeu no desempate por pódios."
    )


def test_motivo_de_posicao_final_decidida_pelos_segundos_lugares_em_corridas(client, data_dir):
    # Corrida: Caio 1º (25), Ana 2º (18), Bia 3º (15); Sprint da China: Bia 6ª (3). Ana e Bia somam 18,
    # sem vitórias e com 1 pódio cada; Ana tem um 2º em Corridas e Bia nenhum
    season(data_dir, [["Caio", "Ana", "Bia"]], pending=0)
    write_session(data_dir, "china_sprint_20260302.csv", [(6, "Bia", TEAM, 6)])
    write_calendar(data_dir, calendar_rows(data_dir) + [("china", "sprint", "2026-03-02")])
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["probability_reason"] == (
        "Terminou em 2º, 7 pontos atrás de Caio. Empatou em pontos, vitórias e pódios com Bia"
        " e venceu no desempate por ter mais 2ºs lugares em Corridas."
    )
    assert rows["Bia"]["probability_reason"] == (
        "Terminou em 3º, 7 pontos atrás de Caio. Empatou em pontos, vitórias e pódios com Ana"
        " e perdeu no desempate por ter menos 2ºs lugares em Corridas."
    )


def test_motivo_de_posicao_final_decidida_por_quem_fez_antes_o_melhor_resultado(client, data_dir):
    # Caio vence as 2 Corridas (50). Ana 2º e 3º, Bia 3º e 2º: 33 cada, com 2 pódios, um 2º e um 3º;
    # Ana fez o seu 2º na 1ª Corrida, Bia só na 2ª
    season(data_dir, [["Caio", "Ana", "Bia"], ["Caio", "Bia", "Ana"]], pending=0)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["probability_reason"] == (
        "Terminou em 2º, 17 pontos atrás de Caio. Empatou em pontos, vitórias, pódios e posições em Corridas"
        " com Bia e venceu no desempate por ter feito o seu melhor resultado em Corridas antes."
    )
    assert rows["Bia"]["probability_reason"] == (
        "Terminou em 3º, 17 pontos atrás de Caio. Empatou em pontos, vitórias, pódios e posições em Corridas"
        " com Ana e perdeu no desempate por ter feito o seu melhor resultado em Corridas depois."
    )


def test_empate_exato_nos_pontos_maximos_mantem_na_disputa(client, data_dir):
    # Ana 25 + 18 = 43; Bia 18 + 0 = 18, que com mais uma Corrida chega a 43
    season(data_dir, [["Ana", "Bia", "Caio"], ["Caio", "Ana", "Dani", "Edu", "Fabi", "Gil", "Bia"]], pending=1)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Bia"]["max_points"] == rows["Ana"]["points"] == 43
    assert rows["Bia"]["status"] == "Na disputa"
    assert rows["Bia"]["probability_reason"] == (
        "Só alcança Ana vencendo a única Sessão pendente, e ainda dependeria do desempate."
    )


def test_motivo_do_empate_exato_nos_pontos_maximos_com_varias_sessoes_pendentes(client, data_dir):
    # Ana venceu as 2 Corridas: 50; Bia chegou em 7º nas duas: 0, que com 2 Corridas chega a 50
    season(data_dir, [["Ana", "Caio", "Dani", "Edu", "Fabi", "Gil", "Bia"]] * 2, pending=2)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Bia"]["probability_reason"] == (
        "Só alcança Ana vencendo as 2 Sessões pendentes, e ainda dependeria do desempate."
    )


# 3 Corridas sem ninguém em 1º: Ana sempre em 2º (54) e Bia sempre em 3º (45, no máximo 95 com 2 Corridas).
# Ana termina à frente da Bia em toda simulação, mas repetindo o 2º chega só a 54 + 36 = 90, abaixo dos 95:
# o argumento do pior resultado não vale e o Motivo fica no texto genérico
RUNNER_UP_LEADER = [[None, "Ana", "Bia"]] * 3


def test_motivo_de_quem_esta_na_disputa_com_chance_de_titulo_zero(client, data_dir):
    season(data_dir, RUNNER_UP_LEADER, pending=2)
    bia = by_name(client.get(DRIVERS).json())["Bia"]

    assert bia["status"] == "Na disputa"
    assert bia["championship_probability"] == 0
    assert bia["probability_reason"] == (
        "Ainda está na disputa pela matemática, mas quase nunca é campeão nas 10.000 simulações: "
        "precisaria tirar 9 pontos de Ana em 2 Sessões pendentes."
    )


def test_motivo_do_lider_na_disputa_com_chance_de_titulo_100(client, data_dir):
    season(data_dir, RUNNER_UP_LEADER, pending=2)
    ana = by_name(client.get(DRIVERS).json())["Ana"]

    assert ana["status"] == "Na disputa"
    assert ana["championship_probability"] == 100
    assert ana["probability_reason"] == (
        "Ainda não é Campeão pela matemática, mas é campeão em quase todas as 10.000 simulações: "
        "Bia precisaria tirar 9 pontos em 2 Sessões pendentes."
    )


def test_motivo_pelo_pior_resultado_do_lider_que_sempre_venceu_na_unica_sessao_pendente(client, data_dir):
    # 3 Corridas: Ana 75 (vence sempre), Bia 54, que com mais uma Corrida chega a 79. Repetindo a vitória,
    # Ana chega a 100: a Bia ganha no máximo 25, o mesmo que a Ana, e a vantagem de 21 fica inteira
    season(data_dir, [["Ana", "Bia", "Caio"]] * 3, pending=1)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["probability_reason"] == (
        "Ainda não é Campeão pela matemática, mas venceu todas as Corridas de 2026; "
        "repetindo isso na única Sessão pendente, Bia não diminui a vantagem de 21 pontos."
    )
    assert rows["Bia"]["probability_reason"] == (
        "Ainda está na disputa pela matemática, mas Ana venceu todas as Corridas de 2026; "
        "repetindo isso na única Sessão pendente, mantém toda a vantagem de 21 pontos."
    )


def test_lider_com_presenca_abaixo_de_100_fica_no_motivo_generico(client, data_dir):
    # Ana venceu as 3 Corridas que disputou (75) e faltou à 4ª, em que Bia (2º sempre, 72) e Caio (3º sempre, 60)
    # correram sem ninguém em 1º. Com 1 Corrida pendente, Caio chega no máximo a 85; Ana, repetindo a vitória,
    # chegaria a 100, mas sem 100% de presença o argumento do pior resultado não entra.
    # Bia termina à frente do Caio em toda simulação, então o Caio tem 0%
    season(data_dir, [["Ana", "Bia", "Caio"]] * 3 + [[None, "Bia", "Caio"]], pending=1)
    caio = by_name(client.get(DRIVERS).json())["Caio"]

    assert caio["status"] == "Na disputa"
    assert caio["championship_probability"] == 0
    assert caio["probability_reason"] == (
        "Ainda está na disputa pela matemática, mas quase nunca é campeão nas 10.000 simulações: "
        "precisaria tirar 15 pontos de Ana na única Sessão pendente."
    )


# Ana sempre no pódio (1º, 3º, 1º) e Bia sempre em 4º, sem mais ninguém pontuando: Ana 65 x Bia 36.
# Com 2 Corridas pendentes, Bia chega no máximo a 36 + 50 = 86; Ana, repetindo o 3º (15 pontos), chega a 95.
# Ana perde no máximo 50 - 30 = 20 pontos para a Bia, menos que os 29 de vantagem
PODIUM_LEADER = [["Ana", None, None, "Bia"], [None, None, "Ana", "Bia"], ["Ana", None, None, "Bia"]]


def test_motivo_de_chance_de_titulo_zero_pelo_pior_resultado_do_lider(client, data_dir):
    season(data_dir, PODIUM_LEADER, pending=2)
    bia = by_name(client.get(DRIVERS).json())["Bia"]

    assert bia["status"] == "Na disputa"
    assert bia["championship_probability"] == 0
    assert bia["probability_reason"] == (
        "Ainda está na disputa pela matemática, mas Ana nunca terminou abaixo do 3º em Corridas de 2026; "
        "repetindo isso nas 2 Sessões pendentes, perde no máximo 20 pontos, menos que os 29 de vantagem."
    )


def test_motivo_de_chance_de_titulo_100_pelo_pior_resultado_do_lider(client, data_dir):
    season(data_dir, PODIUM_LEADER, pending=2)
    ana = by_name(client.get(DRIVERS).json())["Ana"]

    assert ana["status"] == "Na disputa"
    assert ana["championship_probability"] == 100
    assert ana["probability_reason"] == (
        "Ainda não é Campeão pela matemática, mas nunca terminou abaixo do 3º em Corridas de 2026; "
        "repetindo isso nas 2 Sessões pendentes, Bia tira no máximo 20 dos 29 pontos de vantagem."
    )


def test_motivo_pelo_pior_resultado_cita_corridas_e_sprints(client, data_dir):
    # Corridas: Ana 1º e 3º (25 + 15), Bia 4º nas duas (24). Sprints: Ana 1º e 2º (8 + 7), Bia 3º nas duas (12).
    # Ana 55 x Bia 36. Pendentes: 1 Sprint e 1 Corrida, Bia chega no máximo a 36 + 8 + 25 = 69.
    # Repetindo o 3º na Corrida (15) e o 2º na Sprint (7), Ana chega a 77: perde no máximo 33 - 22 = 11 pontos
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_sprint_20260301.csv", [(1, "Ana", TEAM, 1), (3, "Bia", TEAM, 3)])
    write_session(data_dir, "australia_race_20260301.csv", [(1, "Ana", TEAM, 1), (4, "Bia", TEAM, 4)])
    write_session(data_dir, "china_sprint_20260302.csv", [(2, "Ana", TEAM, 2), (3, "Bia", TEAM, 3)])
    write_session(data_dir, "china_race_20260302.csv", [(3, "Ana", TEAM, 3), (4, "Bia", TEAM, 4)])
    write_calendar(data_dir, [("australia", "sprint", "2026-03-01"), ("australia", "race", "2026-03-01"),
                              ("china", "sprint", "2026-03-02"), ("china", "race", "2026-03-02"),
                              ("mexico", "sprint", "2026-12-01"), ("mexico", "race", "2026-12-01")])
    bia = by_name(client.get(DRIVERS).json())["Bia"]

    assert bia["status"] == "Na disputa"
    assert bia["championship_probability"] == 0
    assert bia["probability_reason"] == (
        "Ainda está na disputa pela matemática, mas Ana nunca terminou abaixo do 3º em Corridas nem do 2º em "
        "Sprints de 2026; repetindo isso nas 2 Sessões pendentes, perde no máximo 11 pontos, menos que os 19 "
        "de vantagem."
    )


def test_motivo_pelo_pior_resultado_de_lider_sem_sprint_cita_so_corridas(client, data_dir):
    # Ana nunca correu Sprint: na Sprint pendente ela sorteia das Corridas, em que nunca ficou abaixo do 3º
    # (6 pontos numa Sprint). Ana 65 x Bia 36 + 5 (4º na única Sprint disputada) = 41.
    # Pendentes: 1 Sprint e 1 Corrida, Bia chega no máximo a 41 + 33 = 74; Ana, a 65 + 15 + 6 = 86.
    # Ana perde no máximo 33 - 21 = 12 pontos, menos que os 24 de vantagem
    season(data_dir, PODIUM_LEADER, pending=0)
    write_session(data_dir, "miami_sprint_20260304.csv", [(4, "Bia", TEAM, 4)])
    write_calendar(data_dir, calendar_rows(data_dir) + [
        ("miami", "sprint", "2026-03-04"), ("mexico", "sprint", "2026-12-01"), ("mexico", "race", "2026-12-01")])
    bia = by_name(client.get(DRIVERS).json())["Bia"]

    assert bia["status"] == "Na disputa"
    assert bia["championship_probability"] == 0
    assert bia["probability_reason"] == (
        "Ainda está na disputa pela matemática, mas Ana nunca terminou abaixo do 3º em Corridas de 2026; "
        "repetindo isso nas 2 Sessões pendentes, perde no máximo 12 pontos, menos que os 24 de vantagem."
    )


def test_vantagem_maior_que_os_pontos_maximos_garante_o_titulo(client, data_dir):
    # 4 Corridas: Ana 100, Bia 72; com uma Corrida pendente, Bia chega no máximo a 97
    season(data_dir, [["Ana", "Bia", "Caio"]] * 4, pending=1)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["status"] == "Campeao"
    assert rows["Ana"]["championship_probability"] == 100
    assert rows["Bia"]["status"] == "Eliminado"
    assert rows["Bia"]["max_points"] == 97


def test_motivo_do_campeao_antecipado(client, data_dir):
    # 4 Corridas: Ana 100, Bia 72 (no máximo 97), Caio 60 (no máximo 85)
    season(data_dir, [["Ana", "Bia", "Caio"]] * 4, pending=1)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["probability_reason"] == (
        "Nenhum rival alcança mais os seus 100 pontos: o mais próximo, Bia, chega a no máximo 97."
    )
    assert rows["Bia"]["probability_reason"] == (
        "Mesmo vencendo a única Sessão pendente, chega a no máximo 97 pontos, abaixo dos 100 de Ana."
    )


def test_mesmos_dados_dao_a_mesma_resposta(client, data_dir):
    season(data_dir, [["Ana", "Bia", "Caio"], ["Bia", "Caio", "Ana"]], pending=3)
    first = client.get(DRIVERS).json()
    write_calendar(data_dir, calendar_rows(data_dir))  # mesmo conteúdo: invalida o cache e recalcula
    assert all(row["probability_reason"] for row in first)
    assert client.get(DRIVERS).json() == first  # inclusive o Motivo


def test_resultado_novo_atualiza_a_chance_de_titulo(client, data_dir):
    before = by_name(client.get(DRIVERS).json())
    write_session(data_dir, "mexico_race_20261026.csv", [
        (1, "Yohan", "Red Bull", 1),
        (2, "Erick", "Red Bull", 2),
        (7, "Matheus", "Visa Cash App Racing Bulls", 7),
    ])
    after = by_name(client.get(DRIVERS).json())

    assert after["Yohan"]["points"] == before["Yohan"]["points"] + 25
    assert after["Matheus"]["points"] == before["Matheus"]["points"]
    assert after["Matheus"]["max_points"] == before["Matheus"]["max_points"] - 25


TEAM_FIELDS = {
    "position", "team_id", "team_name", "points", "max_points", "status",
    "championship_probability", "expected_points", "probability_reason",
}


def test_equipes_trazem_situacao_e_chance_de_titulo(client):
    response = client.get(TEAMS)
    assert response.status_code == 200, response.text
    rows = by_name(response.json(), key="team_name")

    assert all(set(row) == TEAM_FIELDS for row in rows.values())
    # Racing Bulls 588 x Red Bull 476, com 5 x (25 + 18) = 215 pts em jogo
    assert rows["Visa Cash App Racing Bulls"]["max_points"] == 588 + 215
    assert rows["Red Bull"]["max_points"] == 476 + 215
    assert {name for name, row in rows.items() if row["status"] == "Na disputa"} == {
        "Visa Cash App Racing Bulls", "Red Bull"}
    for name in ("Scuderia Ferrari HP", "Mercedes-AMG Petronas"):
        assert rows[name]["status"] == "Eliminado"
        assert rows[name]["championship_probability"] == 0
    assert abs(sum(row["championship_probability"] for row in rows.values()) - 100) <= 0.2


def test_motivo_da_equipe_eliminada(client, data_dir):
    # 6 Corridas: Ferrari 6 x (25 + 18) = 258; Williams 6 x (15 + 12) = 162, que chega no máximo a 162 + 2 x 43 = 248
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams", "Dani": "Williams"}
    season(data_dir, [["Ana", "Bia", "Caio", "Dani"]] * 6, pending=2, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Williams"]["probability_reason"] == (
        "Mesmo fazendo 1º e 2º nas 2 Sessões pendentes, chega a no máximo 248 pontos, abaixo dos 258 da Ferrari."
    )


def test_motivo_da_equipe_eliminada_com_uma_unica_sessao_pendente(client, data_dir):
    # 3 Corridas: Ferrari 3 x 43 = 129; Williams 3 x 27 = 81, que chega no máximo a 81 + 43 = 124
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams", "Dani": "Williams"}
    season(data_dir, [["Ana", "Bia", "Caio", "Dani"]] * 3, pending=1, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Williams"]["probability_reason"] == (
        "Mesmo fazendo 1º e 2º na única Sessão pendente, chega a no máximo 124 pontos, abaixo dos 129 da Ferrari."
    )


def test_motivo_da_equipe_campea_antecipada(client, data_dir):
    # Mesmo cenário: Ferrari 129; a Williams chega no máximo a 124
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams", "Dani": "Williams"}
    season(data_dir, [["Ana", "Bia", "Caio", "Dani"]] * 3, pending=1, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Ferrari"]["probability_reason"] == (
        "Nenhuma equipe alcança mais os seus 129 pontos: a mais próxima, Williams, chega a no máximo 124."
    )


def test_motivo_da_equipe_eliminada_com_um_unico_piloto(client, data_dir):
    # 2 Corridas: Ferrari 2 x 43 = 86; Williams só tem o Caio: 2 x 15 = 30, no máximo 30 + 2 x 25 = 80
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams"}
    season(data_dir, [["Ana", "Bia", "Caio"]] * 2, pending=2, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Williams"]["probability_reason"] == (
        "Com um único piloto, mesmo vencendo as 2 Sessões pendentes, chega a no máximo 80 pontos, "
        "abaixo dos 86 da Ferrari."
    )


def test_motivo_das_equipes_na_disputa_com_chances_de_titulo_0_e_100(client, data_dir):
    # 3 Corridas sem ninguém em 1º e 2º: Ana e Bia (Ferrari) sempre em 3º e 4º, 3 x 27 = 81;
    # Caio e Dani (Williams) sempre em 5º e 6º, 3 x 18 = 54, no máximo 54 + 2 x 43 = 140.
    # A Ferrari termina à frente em toda simulação, mas repetindo 3º e 4º chega só a 81 + 54 = 135:
    # o argumento do pior resultado não vale e o Motivo fica no texto genérico
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams", "Dani": "Williams"}
    season(data_dir, [[None, None, "Ana", "Bia", "Caio", "Dani"]] * 3, pending=2, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Ferrari"]["status"] == rows["Williams"]["status"] == "Na disputa"
    assert rows["Ferrari"]["championship_probability"] == 100
    assert rows["Williams"]["championship_probability"] == 0
    assert rows["Ferrari"]["probability_reason"] == (
        "Ainda não é Campeã de Construtores pela matemática, mas é campeã em quase todas as 10.000 simulações: "
        "a Williams precisaria tirar 27 pontos em 2 Sessões pendentes."
    )
    assert rows["Williams"]["probability_reason"] == (
        "Ainda está na disputa pela matemática, mas quase nunca é campeã nas 10.000 simulações: "
        "precisaria tirar 27 pontos da Ferrari em 2 Sessões pendentes."
    )


def test_motivo_das_equipes_pelo_pior_resultado_da_lider(client, data_dir):
    # Ferrari: Ana 1º, 2º, 1º e Bia 2º, 1º, 3º = 43 + 43 + 40 = 126; Williams: Caio 4º e Dani 5º, 3 x 22 = 66,
    # no máximo 66 + 2 x 43 = 152. Repetindo o pior de cada piloto (Ana 2º = 18, Bia 3º = 15), a Ferrari
    # ganha pelo menos 2 x 33 = 66 e chega a 192: perde no máximo 86 - 66 = 20 pontos, menos que os 60 de vantagem
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams", "Dani": "Williams"}
    season(data_dir, [["Ana", "Bia", None, "Caio", "Dani"], ["Bia", "Ana", None, "Caio", "Dani"],
                      ["Ana", None, "Bia", "Caio", "Dani"]], pending=2, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Ferrari"]["status"] == rows["Williams"]["status"] == "Na disputa"
    assert rows["Ferrari"]["championship_probability"] == 100
    assert rows["Williams"]["championship_probability"] == 0
    assert rows["Ferrari"]["probability_reason"] == (
        "Ainda não é Campeã de Construtores pela matemática, mas, repetindo o pior resultado de cada piloto "
        "em Corridas de 2026 (Ana 2º, Bia 3º), a Williams tira no máximo 20 dos 60 pontos de vantagem "
        "nas 2 Sessões pendentes."
    )
    assert rows["Williams"]["probability_reason"] == (
        "Ainda está na disputa pela matemática, mas, repetindo o pior resultado de cada piloto em Corridas "
        "de 2026 (Ana 2º, Bia 3º), a Ferrari perde no máximo 20 pontos nas 2 Sessões pendentes, menos que "
        "os 60 de vantagem."
    )


FILLER_TEAMS = {"Edu": "Mclaren", "Fabi": "Haas", "Gil": "Alpine", "Hugo": "Audi", "Ivo": "Sauber"}


def test_motivo_da_equipe_com_empate_exato_nos_pontos_maximos(client, data_dir):
    # Ferrari 25 + 18 = 43; Williams com Caio e Dani em 7º e 8º: 0, que com 1º e 2º chega a 43
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams", "Dani": "Williams", **FILLER_TEAMS}
    season(data_dir, [["Ana", "Bia", "Edu", "Fabi", "Gil", "Hugo", "Caio", "Dani"]], pending=1, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Williams"]["max_points"] == rows["Ferrari"]["points"] == 43
    assert rows["Williams"]["probability_reason"] == (
        "Só alcança a Ferrari fazendo 1º e 2º na única Sessão pendente, "
        "e ainda dependeria do desempate."
    )


def test_motivo_da_equipe_com_um_unico_piloto_e_empate_exato_nos_pontos_maximos(client, data_dir):
    # Ferrari: Ana 1º (25) e Bia 7º (0) = 25; Williams só tem o Caio, em 8º: 0, que vencendo chega a 25
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams", **FILLER_TEAMS}
    season(data_dir, [["Ana", "Edu", "Fabi", "Gil", "Hugo", "Ivo", "Bia", "Caio"]], pending=1, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Williams"]["max_points"] == rows["Ferrari"]["points"] == 25
    assert rows["Williams"]["probability_reason"] == (
        "Só alcança a Ferrari vencendo a única Sessão pendente, e ainda dependeria do desempate."
    )


def test_equipe_com_um_unico_piloto_soma_so_o_1o_lugar(client, data_dir):
    teams = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams"}
    season(data_dir, [["Ana", "Bia", "Caio"]], pending=2, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Ferrari"]["max_points"] == 25 + 18 + 2 * (25 + 18)
    assert rows["Williams"]["max_points"] == 15 + 2 * 25


def test_pontos_simulados_vao_para_a_equipe_atual_do_piloto(client, data_dir):
    # Caio correu pela Williams e trocou para a Ferrari na última Corrida disputada
    teams = {"Ana": "Mclaren", "Bia": "Williams", "Caio": ["Williams", "Ferrari"]}
    season(data_dir, [["Ana", "Bia", "Caio"], ["Ana", "Bia", "Caio"]], pending=1, teams=teams)
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Williams"]["points"] == 18 + 15 + 18
    assert rows["Ferrari"]["points"] == 15
    # A Williams só tem a Bia daqui para frente: no máximo +25; a Ferrari soma o que o Caio fizer
    assert rows["Williams"]["max_points"] == 51 + 25
    assert rows["Ferrari"]["expected_points"] > rows["Ferrari"]["points"]


def test_construtores_sem_sessoes_pendentes(client, data_dir):
    played = [row for row in calendar_rows(data_dir) if row[0] not in
              ("mexico", "brasil", "las_vegas", "catar", "abu_dhabi")]
    write_calendar(data_dir, played)
    rows = client.get(TEAMS).json()

    assert rows[0]["team_name"] == "Visa Cash App Racing Bulls"
    assert rows[0]["status"] == "Campeao" and rows[0]["championship_probability"] == 100
    assert all(row["status"] == "Eliminado" for row in rows[1:])
    assert all(row["max_points"] == row["points"] == row["expected_points"] for row in rows)
    # Racing Bulls 588 x Red Bull 476
    assert rows[0]["probability_reason"] == "Terminou a temporada em 1º, com 588 pontos."
    assert rows[1]["team_name"] == "Red Bull"
    assert rows[1]["probability_reason"] == "Terminou em 2º, 112 pontos atrás da Visa Cash App Racing Bulls."


def test_construtores_mesmos_dados_dao_a_mesma_resposta(client, data_dir):
    teams = {"Ana": "Ferrari", "Bia": "Williams", "Caio": "Mclaren"}
    season(data_dir, [["Ana", "Bia", "Caio"], ["Bia", "Caio", "Ana"]], pending=3, teams=teams)
    first = client.get(TEAMS).json()
    write_calendar(data_dir, calendar_rows(data_dir))
    assert all(row["probability_reason"] for row in first)
    assert client.get(TEAMS).json() == first  # inclusive o Motivo


def test_piloto_que_falta_a_corridas_corre_menos_na_simulacao(client, data_dir):
    # Ana venceu as 2 Corridas que disputou, mas faltou a outras 2: presença de 50%
    season(data_dir, [["Ana", "Bia", "Caio"], ["Ana", "Bia", "Caio"], ["Bia", "Caio"], ["Bia", "Caio"]], pending=1)
    ana = by_name(client.get(DRIVERS).json())["Ana"]

    # Correndo sempre, Ana ganharia pelo menos ~23 pontos em média; com 50% de presença, no máximo 12,5
    assert ana["expected_points"] - ana["points"] <= 13


def test_piloto_que_nunca_faltou_corre_todas_as_corridas_pendentes(client, data_dir):
    # Ana venceu todas as Corridas: com 100% de presença, vence as 2 pendentes em toda simulação
    season(data_dir, [["Ana", "Bia", "Caio"]] * 3, pending=2)
    ana = by_name(client.get(DRIVERS).json())["Ana"]

    assert ana["expected_points"] == ana["points"] + 50


def test_piloto_sem_corrida_sorteia_das_sprints(client, data_dir):
    season(data_dir, [["Ana", "Bia", "Caio"]], pending=1)
    write_session(data_dir, "china_sprint_20260302.csv", [(1, "Zeca", TEAM, 1), (2, "Ana", TEAM, 2)])
    write_calendar(data_dir, calendar_rows(data_dir) + [("china", "sprint", "2026-03-02")])
    zeca = by_name(client.get(DRIVERS).json())["Zeca"]

    assert zeca["points"] == 8
    assert zeca["expected_points"] > zeca["points"]


def test_sprint_pendente_usa_posicoes_e_pontos_de_sprint(client, data_dir):
    # Ana vence as Sprints e chega em último nas Corridas; Bia, o contrário
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_sprint_20260301.csv", [(1, "Ana", TEAM, 1), (2, "Bia", TEAM, 2)])
    write_session(data_dir, "australia_race_20260301.csv", [(1, "Bia", TEAM, 1), (2, "Ana", TEAM, 2)])
    write_calendar(data_dir, [("australia", "sprint", "2026-03-01"), ("australia", "race", "2026-03-01"),
                              ("china", "sprint", "2026-03-08")])
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["max_points"] == rows["Ana"]["points"] + 8
    assert rows["Ana"]["expected_points"] - rows["Ana"]["points"] == 8
    assert rows["Bia"]["expected_points"] - rows["Bia"]["points"] == 7


def punish(client, data_dir, punishments):
    """Registra punições de Superlicença: lista de (piloto, nome da corrida, pontos deduzidos)."""
    drivers = {d["driver_name"]: d["driver_id"] for d in client.get("/load/2026/drivers").json()}
    races = {r["race_name"]: r["race_id"] for r in client.get("/load/2026/races").json()}
    lines = [f"2026,{drivers[driver]},{races[race]},{points},Teste\n" for driver, race, points in punishments]
    with open(data_dir / "super_license" / "punishments.csv", "a", encoding="utf-8") as f:
        f.write("".join(lines))


def test_suspensao_tira_o_piloto_da_unica_corrida_pendente(client, data_dir):
    season(data_dir, [["Ana", "Bia"], ["Ana", "Bia"]], pending=1)
    punish(client, data_dir, [("Ana", "GP da China", 12)])
    ana = by_name(client.get(DRIVERS).json())["Ana"]

    assert ana["expected_points"] == ana["points"] == 50
    # A Suspensão só afeta a simulação: Pontos máximos e status seguem a matemática
    assert ana["max_points"] == 75
    assert ana["status"] == "Na disputa"


def test_suspensao_vale_so_para_a_primeira_corrida_pendente(client, data_dir):
    # Ana sempre vence quando corre: fora da 1ª das 3 Corridas pendentes, soma 2 x 25
    season(data_dir, [["Ana", "Bia"], ["Ana", "Bia"]], pending=3)
    punish(client, data_dir, [("Ana", "GP da China", 12)])
    ana = by_name(client.get(DRIVERS).json())["Ana"]

    assert ana["expected_points"] == ana["points"] + 50
    assert ana["max_points"] == ana["points"] + 75


def test_suspensao_cumprida_nao_tira_o_piloto_de_corridas(client, data_dir):
    # Superlicença zerada na 1ª Corrida; a 2ª Corrida disputada já cumpriu a Suspensão
    season(data_dir, [["Ana", "Bia"]] * 3, pending=1)
    punish(client, data_dir, [("Ana", "GP da Austrália", 12)])
    ana = by_name(client.get(DRIVERS).json())["Ana"]

    assert ana["expected_points"] - ana["points"] == 25


def test_nova_punicao_depois_da_suspensao_gera_nova_suspensao(client, data_dir):
    season(data_dir, [["Ana", "Bia"]] * 3, pending=1)
    punish(client, data_dir, [("Ana", "GP da Austrália", 12), ("Ana", "GP do Japão", 1)])
    ana = by_name(client.get(DRIVERS).json())["Ana"]

    assert ana["expected_points"] == ana["points"]


SUSPENSION = " Fica fora da próxima Corrida por Suspensão."


def test_motivo_do_piloto_suspenso_na_disputa(client, data_dir):
    # Ana 50 x Bia 36 (no máximo 36 + 75 = 111): as duas Na disputa; a Ana zerou a Superlicença na última Corrida
    season(data_dir, [["Ana", "Bia"], ["Ana", "Bia"]], pending=3)
    punish(client, data_dir, [("Ana", "GP da China", 12)])
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["status"] == rows["Bia"]["status"] == "Na disputa"
    assert rows["Ana"]["probability_reason"].endswith(SUSPENSION)
    assert "Suspensão" not in rows["Bia"]["probability_reason"]


FERRARI_X_WILLIAMS = {"Ana": "Ferrari", "Bia": "Ferrari", "Caio": "Williams", "Dani": "Williams"}
# Ferrari 25 + 15 + 18 + 15 = 73 x Williams 18 + 12 + 25 + 12 = 67, com 3 Corridas pendentes
FERRARI_X_WILLIAMS_RACES = [["Ana", "Caio", "Bia", "Dani"], ["Caio", "Ana", "Bia", "Dani"]]


def test_motivo_da_equipe_cita_o_piloto_suspenso(client, data_dir):
    season(data_dir, FERRARI_X_WILLIAMS_RACES, pending=3, teams=FERRARI_X_WILLIAMS)
    punish(client, data_dir, [("Ana", "GP da China", 12)])
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Ferrari"]["status"] == rows["Williams"]["status"] == "Na disputa"
    assert rows["Ferrari"]["probability_reason"].endswith(" Ana fica fora da próxima Corrida por Suspensão.")
    assert "Suspensão" not in rows["Williams"]["probability_reason"]


def test_motivo_da_equipe_com_dois_pilotos_suspensos(client, data_dir):
    # Ana (43 pontos) vem antes de Bia (30) na classificação
    season(data_dir, FERRARI_X_WILLIAMS_RACES, pending=3, teams=FERRARI_X_WILLIAMS)
    punish(client, data_dir, [("Bia", "GP da China", 12), ("Ana", "GP da China", 12)])
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Ferrari"]["probability_reason"].endswith(" Ana e Bia ficam fora da próxima Corrida por Suspensão.")


def test_motivo_do_piloto_com_presenca_abaixo_de_100(client, data_dir):
    # Ana 2 x 25 = 50 faltou a 2 das 4 Corridas e chega no máximo a 50 + 75 = 125, acima dos 86 da Bia
    season(data_dir, [["Ana", "Bia", "Caio"], ["Ana", "Bia", "Caio"], ["Bia", "Caio"], ["Bia", "Caio"]], pending=3)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["status"] == "Na disputa"
    assert rows["Ana"]["probability_reason"].endswith(
        " Disputou 2 das 4 Corridas, então nas simulações corre só parte das Sessões pendentes.")
    assert "Disputou" not in rows["Bia"]["probability_reason"]
    assert "Disputou" not in rows["Caio"]["probability_reason"]


def test_motivo_traz_suspensao_antes_da_presenca(client, data_dir):
    # Ana faltou às 2 primeiras Corridas e zerou a Superlicença na última: 50 pontos, no máximo 125
    season(data_dir, [["Bia", "Caio"], ["Bia", "Caio"], ["Ana", "Bia", "Caio"], ["Ana", "Bia", "Caio"]], pending=3)
    punish(client, data_dir, [("Ana", "GP do Barém", 12)])
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["status"] == "Na disputa"
    assert rows["Ana"]["probability_reason"].endswith(
        " Fica fora da próxima Corrida por Suspensão."
        " Disputou 2 das 4 Corridas, então nas simulações corre só parte das Sessões pendentes.")


def test_motivo_do_piloto_que_so_correu_sprints_conta_sessoes(client, data_dir):
    # Zeca só correu a Sprint: 1 das 2 Sessões disputadas; 8 pontos, no máximo 33, acima dos 32 da Ana
    season(data_dir, [["Ana", "Bia", "Caio"]], pending=1)
    write_session(data_dir, "china_sprint_20260302.csv", [(1, "Zeca", TEAM, 1), (2, "Ana", TEAM, 2)])
    write_calendar(data_dir, calendar_rows(data_dir) + [("china", "sprint", "2026-03-02")])
    zeca = by_name(client.get(DRIVERS).json())["Zeca"]

    assert zeca["status"] == "Na disputa"
    assert zeca["probability_reason"].endswith(
        " Disputou 1 das 2 Sessões, então nas simulações corre só parte das Sessões pendentes.")


def test_campeao_e_eliminado_nao_recebem_frases_extras(client, data_dir):
    # 4 Corridas: Ana 100 (Campeão) e Bia 72 (no máximo 97) zeraram a Superlicença na última;
    # Caio faltou à última: 3 x 15 = 45, no máximo 70
    season(data_dir, [["Ana", "Bia", "Caio"]] * 3 + [["Ana", "Bia"]], pending=1)
    punish(client, data_dir, [("Ana", "GP do Barém", 12), ("Bia", "GP do Barém", 12)])
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Ana"]["probability_reason"] == (
        "Nenhum rival alcança mais os seus 100 pontos: o mais próximo, Bia, chega a no máximo 97."
    )
    assert rows["Bia"]["probability_reason"] == (
        "Mesmo vencendo a única Sessão pendente, chega a no máximo 97 pontos, abaixo dos 100 de Ana."
    )
    assert rows["Caio"]["probability_reason"] == (
        "Mesmo vencendo a única Sessão pendente, chega a no máximo 70 pontos, abaixo dos 100 de Ana."
    )


def test_titulo_empatado_ate_os_podios_vai_para_quem_tem_mais_segundos_lugares_em_corridas(client, data_dir):
    # Austrália (Corrida): Mike 2º (18), Gabriel 3º (15), sem ninguém em 1º. Sprint da China: Gabriel 1º (8),
    # Mike 2º (7). Nas 2 Sprints pendentes cada um repete a sua única posição em Sprints: Gabriel +8, Mike +7.
    # Fim: Mike 18 + 7 + 14 = 39 e Gabriel 15 + 8 + 16 = 39, sem vitórias e com 4 pódios cada, em toda
    # simulação. Mike tem um 2º em Corridas e Gabriel nenhum; pela ordem do ID, seria o Gabriel (2 < 9).
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_race_20260302.csv", [(2, "Mike", SAUBER, 2), (3, "Gabriel", FERRARI, 3)])
    write_session(data_dir, "china_sprint_20260309.csv", [(1, "Gabriel", FERRARI, 1), (2, "Mike", SAUBER, 2)])
    write_calendar(data_dir, [("australia", "race", "2026-03-02"), ("china", "sprint", "2026-03-09"),
                              ("miami", "sprint", "2026-04-27"), ("canada", "sprint", "2026-05-18")])
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Mike"]["expected_points"] == rows["Gabriel"]["expected_points"] == 39
    assert rows["Mike"]["championship_probability"] == 100
    assert rows["Gabriel"]["championship_probability"] == 0


def test_titulo_empatado_na_contagem_vai_para_quem_conseguiu_primeiro_o_melhor_resultado(client, data_dir):
    # Austrália: Mike 2º (18), Gabriel 3º (15). Japão: Gabriel 2º, Mike 3º. Os dois somam 33, com 2 pódios,
    # um 2º e um 3º em Corridas. Os dois zeram a Superlicença no Japão e ficam fora da única Corrida pendente,
    # então terminam assim em toda simulação. Mike fez o 2º primeiro; pela ordem do ID, seria o Gabriel.
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_race_20260302.csv", [(2, "Mike", SAUBER, 2), (3, "Gabriel", FERRARI, 3)])
    write_session(data_dir, "japao_race_20260323.csv", [(2, "Gabriel", FERRARI, 2), (3, "Mike", SAUBER, 3)])
    write_calendar(data_dir, [("australia", "race", "2026-03-02"), ("japao", "race", "2026-03-23"),
                              ("mexico", "race", "2026-10-26")])
    punish(client, data_dir, [("Mike", "GP do Japão", 12), ("Gabriel", "GP do Japão", 12)])
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Mike"]["expected_points"] == rows["Gabriel"]["expected_points"] == 33
    assert rows["Mike"]["championship_probability"] == 100
    assert rows["Gabriel"]["championship_probability"] == 0


def test_corrida_simulada_entra_na_contagem_de_posicoes_do_desempate(client, data_dir):
    # 12 Sprints só com Mike e Gabriel, alternando 1º (8) e 2º (7): 90 pontos e 12 pódios cada.
    # Austrália: José, Bryan, Paulo, Matheus, Pedro e Yohan do 1º ao 6º, Gabriel 7º, Mike 8º; Japão: o mesmo,
    # com Mike 7º e Gabriel 8º. Nas Corridas disputadas, os dois têm um 7º e um 8º, e Gabriel fez o 7º antes.
    # Gabriel zera a Superlicença no Japão e fica fora da única Corrida pendente; nela, os 6 sorteiam a sua
    # única posição (1º ao 6º) e Mike, 7º ou 8º, termina em 7º sem pontos. Fim: 90 a 90 (José, o 1º dos
    # outros, chega a 75), e Mike vence só pelo 7º da Corrida simulada (dois 7ºs contra um). Sem ele, seria o
    # Gabriel, por ter feito o 7º antes e pela ordem do ID (2 < 9).
    reset_2026_season(data_dir)
    sprint_locals = ["china", "bahrein", "arabia_saudita", "miami", "emilia_romanha", "canada",
                     "monaco", "espanha", "silverstone", "austria", "spa", "hungria"]
    for day, local in enumerate(sprint_locals, start=1):
        first, second = ("Mike", "Gabriel") if day % 2 else ("Gabriel", "Mike")
        write_session(data_dir, f"{local}_sprint_202601{day:02d}.csv",
                      [(1, first, TEAM, 1), (2, second, TEAM, 2)])
    others = ["José", "Bryan", "Paulo", "Matheus", "Pedro", "Yohan"]
    for file_name, last_two in (("australia_race_20260302.csv", ["Gabriel", "Mike"]),
                                ("japao_race_20260323.csv", ["Mike", "Gabriel"])):
        write_session(data_dir, file_name,
                      [(pos, driver, TEAM, pos) for pos, driver in enumerate(others + last_two, start=1)])
    write_calendar(data_dir, [(local, "sprint", f"2026-01-{day:02d}") for day, local in enumerate(sprint_locals, 1)]
                   + [("australia", "race", "2026-03-02"), ("japao", "race", "2026-03-23"),
                      ("mexico", "race", "2026-10-26")])
    punish(client, data_dir, [("Gabriel", "GP do Japão", 12)])
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Mike"]["expected_points"] == rows["Gabriel"]["expected_points"] == 90
    assert rows["José"]["expected_points"] == 75
    assert rows["Mike"]["championship_probability"] == 100
    assert rows["Gabriel"]["championship_probability"] == 0


# Sprint da China disputada e Sprint de Miami pendente: Douglas (Sauber) 1º, Yohan (McLaren) 2º, Bryan
# (Ferrari) 3º, Paulo (Ferrari) 4º e Adriano (McLaren) 5º. Na Sprint pendente cada um repete a sua única
# posição em Sprints: McLaren 7 + 4 = 11 e Ferrari 6 + 5 = 11, com 1 pódio cada, em toda simulação.
CONSTRUCTORS_SPRINT = [(1, "Douglas", SAUBER, 1), (2, "Yohan", MCLAREN, 2), (3, "Bryan", FERRARI, 3),
                       (4, "Paulo", FERRARI, 4), (5, "Adriano", MCLAREN, 5)]


def constructors_season(data_dir, australia, japao):
    """Duas Corridas disputadas (ordens de chegada sem ninguém em 1º), a Sprint da China e a de Miami pendente."""
    reset_2026_season(data_dir)
    for file_name, finishing_order in (("australia_race_20260302.csv", australia),
                                       ("japao_race_20260323.csv", japao)):
        write_session(data_dir, file_name, [(pos, driver, team, pos)
                                            for pos, (driver, team) in enumerate(finishing_order, start=2)])
    write_session(data_dir, "china_sprint_20260309.csv", CONSTRUCTORS_SPRINT)
    write_calendar(data_dir, [("australia", "race", "2026-03-02"), ("china", "sprint", "2026-03-09"),
                              ("japao", "race", "2026-03-23"), ("miami", "sprint", "2026-04-27")])


def test_titulo_de_construtores_empatado_ate_os_podios_vai_para_quem_tem_mais_segundos_lugares(client, data_dir):
    # Austrália: Yohan 2º, Bryan 3º, Paulo 4º, Adriano 5º, Douglas 6º: McLaren 18 + 10 = 28, Ferrari 15 + 12 = 27.
    # Japão: Yohan 2º, Bryan 3º, Paulo 4º, Douglas 5º, Adriano 6º: McLaren 18 + 8 = 26, Ferrari 27.
    # Com as duas Sprints (11 cada), McLaren 54 + 22 = 76 e Ferrari 54 + 22 = 76, sem vitórias e com 4 pódios
    # cada. A McLaren tem dois 2ºs em Corridas e a Ferrari nenhum; pela ordem do ID, seria a Ferrari (2 < 4).
    constructors_season(
        data_dir,
        australia=[("Yohan", MCLAREN), ("Bryan", FERRARI), ("Paulo", FERRARI), ("Adriano", MCLAREN),
                   ("Douglas", SAUBER)],
        japao=[("Yohan", MCLAREN), ("Bryan", FERRARI), ("Paulo", FERRARI), ("Douglas", SAUBER),
               ("Adriano", MCLAREN)],
    )
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows[MCLAREN]["expected_points"] == rows[FERRARI]["expected_points"] == 76
    assert rows[MCLAREN]["championship_probability"] == 100
    assert rows[FERRARI]["championship_probability"] == 0


def test_titulo_de_construtores_empatado_na_contagem_vai_para_quem_conseguiu_primeiro_o_melhor_resultado(
    client, data_dir
):
    # Austrália: Yohan (McLaren) 2º, Paulo (Ferrari) 3º, Bryan (Ferrari) 4º, Adriano (McLaren) 5º, Douglas 6º.
    # Japão: Bryan 2º, Adriano 3º, Yohan 4º, Paulo 5º, Douglas 6º. Cada equipe soma 28 + 27 = 55, com 2 pódios
    # e um 2º, um 3º, um 4º e um 5º em Corridas. Com as duas Sprints (11 cada), 77 a 77, com 4 pódios cada.
    # A McLaren fez o 2º primeiro (Yohan, na Austrália); pela ordem do ID, seria a Ferrari.
    constructors_season(
        data_dir,
        australia=[("Yohan", MCLAREN), ("Paulo", FERRARI), ("Bryan", FERRARI), ("Adriano", MCLAREN),
                   ("Douglas", SAUBER)],
        japao=[("Bryan", FERRARI), ("Adriano", MCLAREN), ("Yohan", MCLAREN), ("Paulo", FERRARI),
               ("Douglas", SAUBER)],
    )
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows[MCLAREN]["expected_points"] == rows[FERRARI]["expected_points"] == 77
    assert rows[MCLAREN]["championship_probability"] == 100
    assert rows[FERRARI]["championship_probability"] == 0


def test_equipe_campea_ou_eliminada_nao_cita_piloto_suspenso(client, data_dir):
    # 3 Corridas: Ferrari 3 x 43 = 129 (Campeã); Williams 3 x 27 = 81, no máximo 124
    season(data_dir, [["Ana", "Bia", "Caio", "Dani"]] * 3, pending=1, teams=FERRARI_X_WILLIAMS)
    punish(client, data_dir, [("Ana", "GP do Japão", 12), ("Caio", "GP do Japão", 12)])
    rows = by_name(client.get(TEAMS).json(), key="team_name")

    assert rows["Ferrari"]["probability_reason"] == (
        "Nenhuma equipe alcança mais os seus 129 pontos: a mais próxima, Williams, chega a no máximo 124."
    )
    assert rows["Williams"]["probability_reason"] == (
        "Mesmo fazendo 1º e 2º na única Sessão pendente, chega a no máximo 124 pontos, abaixo dos 129 da Ferrari."
    )
