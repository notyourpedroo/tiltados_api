"""Superlicença de 2026: saldo, status e Suspensão a cumprir ou cumprida."""

import pytest

from conftest import reset_2026_season, write_calendar, write_session

SUPER_LICENSE = "/load/2026/super-license"
TEAM = "Red Bull"


def season(data_dir, sessions):
    """Temporada sintética com Ana e Bia: `sessions` é uma lista de (local, tipo, data), todas disputadas."""
    reset_2026_season(data_dir)
    for local, session_type, date in sessions:
        write_session(data_dir, f"{local}_{session_type}_{date.replace('-', '')}.csv",
                      [(1, "Ana", TEAM, 1), (2, "Bia", TEAM, 2)])
    write_calendar(data_dir, sessions)


def punish(client, data_dir, punishments):
    """Registra punições de Superlicença: lista de (piloto, nome da Sessão, pontos deduzidos)."""
    drivers = {d["driver_name"]: d["driver_id"] for d in client.get("/load/2026/drivers").json()}
    races = {r["race_name"]: r["race_id"] for r in client.get("/load/2026/races").json()}
    lines = [f"2026,{drivers[driver]},{races[race]},{points},Teste\n" for driver, race, points in punishments]
    with open(data_dir / "super_license" / "punishments.csv", "a", encoding="utf-8") as f:
        f.write("".join(lines))


def license_of(client, driver_name):
    response = client.get(SUPER_LICENSE)
    assert response.status_code == 200, response.text
    return {row["driver_name"]: row for row in response.json()}[driver_name]


TWO_RACES = [("australia", "race", "2026-03-01"), ("china", "race", "2026-03-08")]


def test_superlicenca_zerada_sem_corrida_depois_da_punicao_fica_suspenso(client, data_dir):
    # Ana perde os 12 pontos na última Corrida disputada: Suspensão a cumprir
    season(data_dir, TWO_RACES)
    punish(client, data_dir, [("Ana", "GP da China", 12)])
    ana = license_of(client, "Ana")

    assert ana["remaining_points"] == 0
    assert ana["status"] == "Suspenso"
    assert license_of(client, "Bia")["status"] == "Regular"


def test_suspensao_cumprida_depois_de_uma_corrida_disputada(client, data_dir):
    # Ana zera a Superlicença na 1ª Corrida e disputa a 2ª: o saldo continua zerado, mas a Suspensão foi cumprida
    season(data_dir, TWO_RACES)
    punish(client, data_dir, [("Ana", "GP da Austrália", 12)])
    ana = license_of(client, "Ana")

    assert ana["remaining_points"] == 0
    assert ana["status"] == "Suspensao cumprida"


def test_sprint_disputada_depois_da_punicao_nao_cumpre_a_suspensao(client, data_dir):
    # Ana zera a Superlicença na 1ª Corrida; depois dela só houve a Sprint da China
    season(data_dir, [("australia", "race", "2026-03-01"), ("china", "sprint", "2026-03-08")])
    punish(client, data_dir, [("Ana", "GP da Austrália", 12)])

    assert license_of(client, "Ana")["status"] == "Suspenso"


def test_nova_punicao_depois_da_suspensao_cumprida_volta_a_suspenso(client, data_dir):
    # Ana zera na Austrália, cumpre na China e perde mais 1 ponto na China: saldo -1, nova Suspensão
    season(data_dir, TWO_RACES)
    punish(client, data_dir, [("Ana", "GP da Austrália", 12), ("Ana", "GP da China", 1)])
    ana = license_of(client, "Ana")

    assert ana["remaining_points"] == -1
    assert ana["punishments_count"] == 2
    assert ana["status"] == "Suspenso"


@pytest.mark.parametrize("deducted, status", [
    (3, "Regular"),
    (4, "Atencao"),
    (7, "Atencao"),
    (8, "Alerta Critico"),
    (11, "Alerta Critico"),
])
def test_status_com_saldo_positivo_nao_muda(client, data_dir, deducted, status):
    # 12 - 3 = 9 é o menor saldo Regular; 12 - 4 = 8 e 12 - 7 = 5, Atencao; 12 - 8 = 4 e 12 - 11 = 1, Alerta Critico
    season(data_dir, TWO_RACES)
    punish(client, data_dir, [("Ana", "GP da China", deducted)])

    assert license_of(client, "Ana")["status"] == status


PENDING_RACE = ("japao", "race", "2026-03-15")


@pytest.mark.parametrize("sessions, punishments, status", [
    (TWO_RACES, [("Ana", "GP da China", 12)], "Suspenso"),
    (TWO_RACES, [("Ana", "GP da Austrália", 12)], "Suspensao cumprida"),
    ([("australia", "race", "2026-03-01"), ("china", "sprint", "2026-03-08")],
     [("Ana", "GP da Austrália", 12)], "Suspenso"),
    (TWO_RACES, [("Ana", "GP da Austrália", 12), ("Ana", "GP da China", 1)], "Suspenso"),
])
def test_superlicenca_e_chance_de_titulo_concordam_sobre_a_suspensao(client, data_dir, sessions, punishments, status):
    # Ana vence toda Sessão que disputa; resta 1 Corrida pendente, que ela vence (25 pontos) se não estiver suspensa
    season(data_dir, sessions)
    write_calendar(data_dir, sessions + [PENDING_RACE])
    punish(client, data_dir, punishments)
    ana = {row["driver_name"]: row for row in client.get("/load/2026/prediction/drivers").json()}["Ana"]

    assert license_of(client, "Ana")["status"] == status
    assert ana["status"] == "Na disputa"
    if status == "Suspenso":
        assert ana["expected_points"] == ana["points"]
        assert ana["probability_reason"].endswith(" Fica fora da próxima Corrida por Suspensão.")
    else:
        assert ana["expected_points"] == ana["points"] + 25
        assert "Suspensão" not in ana["probability_reason"]
