"""Regras de montagem dos dados de 2026: IDs entre temporadas, equipe atual e recarga do cache."""

import importlib
import os

from conftest import replace_in_file, write_session

common = importlib.import_module("scripts.2026.common")


def races_by_name(client, season):
    return {r["race_name"]: r for r in client.get(f"/load/{season}/races").json()}


def test_todos_os_locais_de_2026_estao_no_location_map(data_dir):
    # Um local fora do mapa gera nome derivado do arquivo e race_id novo (ex.: "GP de Spa").
    for file_name in os.listdir(data_dir / "2026"):
        match = common.SESSION_FILE_PATTERN.match(file_name)
        if match:
            assert match.group(1).lower() in common.LOCATION_MAP, file_name


def test_gps_de_2026_reaproveitam_o_race_id_de_2025(client):
    races_2025 = races_by_name(client, "2025")
    races_2026 = races_by_name(client, "2026")

    for name, race in races_2026.items():
        if name in races_2025:
            assert race["race_id"] == races_2025[name]["race_id"], name

    assert races_2026["GP da Bélgica"]["race_id"] == 16
    assert races_2026["GP da Arábia Saudita"]["race_id"] == 6
    assert races_2026["GP do Barém"]["race_id"] == 5


def test_piloto_mantem_driver_id_de_2025(client):
    ids_2025 = {d["driver_name"]: d["driver_id"] for d in client.get("/load/2025/drivers").json()}
    for driver in client.get("/load/2026/drivers").json():
        if driver["driver_name"] in ids_2025:
            assert driver["driver_id"] == ids_2025[driver["driver_name"]]


def test_equipe_do_piloto_e_a_da_sessao_mais_recente(client, data_dir):
    # Mike corre pela Ferrari numa sessão posterior a todas as outras
    write_session(data_dir, "estados_unidos_race_20261019.csv", [
        (1, "Matheus", "Visa Cash App Racing Bulls", 1),
        (2, "Mike", "Scuderia Ferrari HP", 2),
    ])
    teams = {t["team_name"]: t["team_id"] for t in client.get("/load/2026/teams").json()}
    mike = next(d for d in client.get("/load/2026/drivers").json() if d["driver_name"] == "Mike")

    assert mike["team_id"] == teams["Scuderia Ferrari HP"]


def test_estreantes_recebem_ids_novos(client, data_dir):
    before_races = client.get("/load/2026/races").json()
    before_drivers = client.get("/load/2026/drivers").json()
    before_teams = client.get("/load/2026/teams").json()

    write_session(data_dir, "imola_sprint_20261020.csv", [
        (1, "Zeca", "Williams Racing", 1),
        (2, "Bryan", "Scuderia Ferrari HP", 2),
    ])

    race = races_by_name(client, "2026")["GP de Imola (SPRINT)"]
    zeca = next(d for d in client.get("/load/2026/drivers").json() if d["driver_name"] == "Zeca")
    williams = next(t for t in client.get("/load/2026/teams").json() if t["team_name"] == "Williams Racing")

    assert race["race_id"] > max(r["race_id"] for r in before_races)
    assert zeca["driver_id"] > max(d["driver_id"] for d in before_drivers)
    assert williams["team_id"] > max(t["team_id"] for t in before_teams)
    assert zeca["team_id"] == williams["team_id"]


def test_dados_recarregam_quando_o_csv_muda(client, data_dir):
    def gabriel_points():
        standings = client.get("/load/2026/standings/drivers").json()
        return next(d["points"] for d in standings if d["driver_name"] == "Gabriel")

    before = gabriel_points()
    # Gabriel (5º no Japão, 10 pts) passa a ser 6º (8 pts), sem reiniciar a API
    replace_in_file(data_dir / "2026" / "japao_race_20260323.csv",
                    "5,Gabriel,Visa Cash App Racing Bulls,5,", "6,Gabriel,Visa Cash App Racing Bulls,5,")

    assert gabriel_points() == before - 2
