"""Chance de título de 2026: situação matemática e simulação das Sessões pendentes."""

import csv

from conftest import reset_2026_season, write_calendar, write_session

DRIVERS = "/load/2026/prediction/drivers"
TEAM = "Red Bull"

DRIVER_FIELDS = {
    "position", "driver_id", "driver_name", "team_id", "team_name", "points",
    "max_points", "status", "championship_probability", "expected_points",
}


def by_name(rows, key="driver_name"):
    return {row[key]: row for row in rows}


def calendar_rows(data_dir):
    with open(data_dir / "2026" / "calendar.csv", encoding="utf-8") as f:
        return [(r["local"], r["tipo"], r["data"]) for r in csv.DictReader(f)]


def season(data_dir, races, pending):
    """Temporada sintética: `races` é uma lista de ordens de chegada; `pending` Corridas sem resultado."""
    reset_2026_season(data_dir)
    played = []
    for i, finishing_order in enumerate(races, start=1):
        local = f"etapa{'abcdefghij'[i - 1]}"
        write_session(data_dir, f"{local}_race_2026030{i}.csv",
                      [(pos, driver, TEAM, pos) for pos, driver in enumerate(finishing_order, start=1)])
        played.append((local, "race", f"2026-03-0{i}"))
    write_calendar(data_dir, played + [(f"futura{'abcdefghij'[i]}", "race", f"2026-12-0{i + 1}") for i in range(pending)])


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


def test_mesmos_dados_dao_a_mesma_resposta(client, data_dir):
    season(data_dir, [["Ana", "Bia", "Caio"], ["Bia", "Caio", "Ana"]], pending=3)
    first = client.get(DRIVERS).json()
    write_calendar(data_dir, calendar_rows(data_dir))  # mesmo conteúdo: invalida o cache e recalcula
    assert client.get(DRIVERS).json() == first


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
