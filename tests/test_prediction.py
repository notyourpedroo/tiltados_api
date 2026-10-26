"""Chance de título de 2026: situação matemática e simulação das Sessões pendentes."""

import csv
import re

from conftest import reset_2026_season, write_calendar, write_session

DRIVERS = "/load/2026/prediction/drivers"
TEAMS = "/load/2026/prediction/teams"
TEAM = "Red Bull"
# Locais do LOCATION_MAP usados nas temporadas sintéticas
PLAYED = ["australia", "china", "japao", "bahrein", "arabia_saudita", "miami"]
PENDING = ["mexico", "brasil", "las_vegas", "catar", "abu_dhabi"]

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
                      [(pos, driver, team_of(driver, i - 1), pos) for pos, driver in enumerate(finishing_order, start=1)])
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


def test_empate_exato_nos_pontos_maximos_mantem_na_disputa(client, data_dir):
    # Ana 25 + 18 = 43; Bia 18 + 0 = 18, que com mais uma Corrida chega a 43
    season(data_dir, [["Ana", "Bia", "Caio"], ["Caio", "Ana", "Dani", "Edu", "Fabi", "Gil", "Bia"]], pending=1)
    rows = by_name(client.get(DRIVERS).json())

    assert rows["Bia"]["max_points"] == rows["Ana"]["points"] == 43
    assert rows["Bia"]["status"] == "Na disputa"


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
