"""Temporadas por Sessão descobertas pelas pastas: uma pasta com Calendário basta para a temporada existir."""

import os
import shutil

import pytest

from conftest import open_season, replace_in_file, write_session

GENERIC_RESOURCES = ["drivers", "teams", "races", "results", "standings/drivers", "standings/teams"]

CALENDAR_2027 = [
    ("australia", "race", "2027-03-07"),
    ("china", "sprint", "2027-03-14"),
    ("china", "race", "2027-03-14"),
    ("japao", "race", "2027-03-28"),
]

RBR, FERRARI, MERCEDES, VCARB = "Red Bull", "Scuderia Ferrari HP", "Mercedes-AMG Petronas", "Visa Cash App Racing Bulls"


def open_2027_with_three_sessions(data_dir):
    """
    2027 com Austrália (Corrida), China (Sprint e Corrida) disputadas e o Japão pendente.
    Matheus troca a Visa Cash App Racing Bulls pela Mercedes na Corrida da China.
    """
    open_season(data_dir, "2027", CALENDAR_2027)
    write_session(data_dir, "australia_race_20270307.csv", [
        (1, "Yohan", RBR, 2), (2, "Matheus", VCARB, 1), (3, "Paulo", FERRARI, 3),
    ], season="2027")
    write_session(data_dir, "china_sprint_20270314.csv", [
        (1, "Matheus", VCARB, 1), (2, "Paulo", FERRARI, 2), (3, "Yohan", RBR, 3),
    ], season="2027")
    write_session(data_dir, "china_race_20270314.csv", [
        (1, "Paulo", FERRARI, 3), (2, "Yohan", RBR, 1), (3, "Matheus", MERCEDES, 2),
    ], season="2027")


def test_temporada_com_calendario_aparece_na_rota_raiz(client, data_dir):
    open_season(data_dir, "2027", CALENDAR_2027)

    assert client.get("/").json()["seasons"] == [2025, 2026, 2027]


@pytest.mark.parametrize("resource", GENERIC_RESOURCES)
def test_swagger_documenta_o_parametro_da_temporada(client, resource):
    operation = client.get("/openapi.json").json()["paths"][f"/load/{{season}}/{resource}"]["get"]
    season = next(p for p in operation["parameters"] if p["name"] == "season")

    assert season["in"] == "path" and season["required"]
    assert "As temporadas disponíveis estão em `seasons`, na rota `/`" in season["description"]


def test_pasta_sem_calendario_nao_e_temporada(client, data_dir):
    os.makedirs(data_dir / "2027")
    shutil.copy(data_dir / "2026" / "scores.csv", data_dir / "2027" / "scores.csv")

    assert client.get("/").json()["seasons"] == [2025, 2026]
    response = client.get("/load/2027/standings/drivers")
    assert response.status_code == 404
    assert response.json()["detail"] == "Temporada 2027 não encontrada. Temporadas disponíveis: 2025, 2026."


@pytest.mark.parametrize("resource", GENERIC_RESOURCES)
def test_temporada_sem_sessao_disputada_responde_lista_vazia(client, data_dir, resource):
    open_season(data_dir, "2027", CALENDAR_2027)

    response = client.get(f"/load/2027/{resource}")
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_erro_nos_dados_de_uma_temporada_nao_derruba_as_outras(client, data_dir):
    open_2027_with_three_sessions(data_dir)
    replace_in_file(data_dir / "2027" / "china_race_20270314.csv", "1,Paulo,", "1,Paolo,")

    response = client.get("/load/2027/standings/drivers")
    assert response.status_code == 500
    assert response.json()["detail"] == (
        "2027/china_race_20270314.csv, linha 2: coluna 'Piloto' com valor 'Paolo' (esperado um piloto do Cadastro)."
    )
    assert client.get("/").json()["seasons"] == [2025, 2026, 2027]
    for season in ("2025", "2026"):
        for resource in GENERIC_RESOURCES:
            assert client.get(f"/load/{season}/{resource}").status_code == 200, (season, resource)


def test_temporada_criada_com_o_servidor_no_ar_aparece_sem_reiniciar(client, data_dir):
    assert client.get("/load/2027/races").status_code == 404

    open_2027_with_three_sessions(data_dir)

    assert client.get("/").json()["seasons"] == [2025, 2026, 2027]
    assert [r["race_id"] for r in client.get("/load/2027/races").json()] == [1, 2, 3]


def test_temporada_nova_traz_pilotos_e_equipes_com_ids_do_cadastro(client, data_dir):
    open_2027_with_three_sessions(data_dir)

    assert client.get("/load/2027/drivers").json() == [
        {"driver_id": 4, "team_id": 2, "driver_name": "Paulo"},
        {"driver_id": 5, "team_id": 6, "driver_name": "Matheus"},
        {"driver_id": 7, "team_id": 1, "driver_name": "Yohan"},
    ]
    assert client.get("/load/2027/teams").json() == [
        {"team_id": 1, "team_name": RBR},
        {"team_id": 2, "team_name": FERRARI},
        {"team_id": 6, "team_name": MERCEDES},
        {"team_id": 7, "team_name": VCARB},
    ]


def test_temporada_nova_traz_as_sessoes_disputadas_com_ids_do_cadastro(client, data_dir):
    open_2027_with_three_sessions(data_dir)

    assert client.get("/load/2027/races").json() == [
        {"race_id": 1, "race_name": "GP da Austrália", "race_date": "2027-03-07",
         "race_location": "Melbourne", "is_sprint": False},
        {"race_id": 2, "race_name": "GP da China (SPRINT)", "race_date": "2027-03-14",
         "race_location": "Xangai", "is_sprint": True},
        {"race_id": 3, "race_name": "GP da China", "race_date": "2027-03-14",
         "race_location": "Xangai", "is_sprint": False},
    ]
    results = client.get("/load/2027/results").json()
    assert [(r["race_id"], r["driver_id"], r["team_id"], r["driver_final_position"], r["grid_result"])
            for r in results] == [
        (1, 7, 1, 1, -1), (1, 5, 7, 2, 1), (1, 4, 2, 3, 0),
        (2, 5, 7, 1, 0), (2, 4, 2, 2, 0), (2, 7, 1, 3, 0),
        (3, 4, 2, 1, -2), (3, 7, 1, 2, 1), (3, 5, 6, 3, 1),
    ]


def test_classificacao_da_temporada_nova(client, data_dir):
    open_2027_with_three_sessions(data_dir)

    # Yohan 25 + 6 + 18 = 49; Paulo 15 + 7 + 25 = 47; Matheus 18 + 8 + 15 = 41
    assert client.get("/load/2027/standings/drivers").json() == [
        {"position": 1, "driver_id": 7, "driver_name": "Yohan", "team_id": 1, "team_name": RBR,
         "points": 49, "wins": 1, "sprint_wins": 0, "podiums": 3, "races": 3},
        {"position": 2, "driver_id": 4, "driver_name": "Paulo", "team_id": 2, "team_name": FERRARI,
         "points": 47, "wins": 1, "sprint_wins": 0, "podiums": 3, "races": 3},
        {"position": 3, "driver_id": 5, "driver_name": "Matheus", "team_id": 6, "team_name": MERCEDES,
         "points": 41, "wins": 0, "sprint_wins": 1, "podiums": 3, "races": 3},
    ]
    # Os pontos de Matheus ficam com a equipe de cada Sessão: 18 + 8 na VCARB, 15 na Mercedes
    assert client.get("/load/2027/standings/teams").json() == [
        {"position": 1, "team_id": 1, "team_name": RBR, "points": 49, "wins": 1, "podiums": 3},
        {"position": 2, "team_id": 2, "team_name": FERRARI, "points": 47, "wins": 1, "podiums": 3},
        {"position": 3, "team_id": 7, "team_name": VCARB, "points": 26, "wins": 0, "podiums": 2},
        {"position": 4, "team_id": 6, "team_name": MERCEDES, "points": 15, "wins": 0, "podiums": 1},
    ]
