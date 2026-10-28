"""Regras de montagem dos dados de 2026: IDs entre temporadas, equipe atual e recarga do cache."""

import csv
import os

from conftest import replace_in_file, reset_2026_season, write_session


def races_by_name(client, season):
    return {r["race_name"]: r for r in client.get(f"/load/{season}/races").json()}


def test_todas_as_sessoes_e_o_calendario_de_2026_estao_no_cadastro(client, data_dir):
    # Uma Sessão (local e tipo) fora do Cadastro, no nome de um arquivo ou no Calendário, vira erro
    session_files = [
        f for f in os.listdir(data_dir / "2026") if f.endswith(".csv") and f not in ("scores.csv", "calendar.csv")
    ]
    races = client.get("/load/2026/races")

    assert races.status_code == 200
    assert len(races.json()) == len(session_files) == 23
    assert client.get("/load/2026/prediction/drivers").status_code == 200


def test_sessoes_de_2025_tem_o_mesmo_race_id_no_cadastro(client, data_dir):
    # Uma Sessão de 2026 para cada linha do Cadastro faz /load/2026/races mostrar o race_id de cada uma.
    reset_2026_season(data_dir)
    with open(data_dir / "sessions.csv", encoding="utf-8") as f:
        registered = [(row["local"], row["tipo"]) for row in csv.DictReader(f)]
    for i, (local, session_type) in enumerate(registered):
        write_session(data_dir, f"{local}_{session_type}_2026{1 + i // 28:02d}{1 + i % 28:02d}.csv",
                      [(1, "Bryan", "Scuderia Ferrari HP", 1)])

    def ids(season):
        return {name: (r["race_id"], r["race_location"], r["is_sprint"])
                for name, r in races_by_name(client, season).items()}

    ids_2025, ids_2026 = ids("2025"), ids("2026")
    assert len(ids_2025) == 30 and len(ids_2026) == 34
    for name, race in ids_2025.items():
        assert ids_2026.get(name) == race, name


def test_sprints_ineditas_de_2026_tem_os_ids_31_a_34(client):
    races = races_by_name(client, "2026")

    assert races["GP do Canadá (SPRINT)"]["race_id"] == 31
    assert races["GP da Grã-Bretanha (SPRINT)"]["race_id"] == 32
    assert races["GP dos Países Baixos (SPRINT)"]["race_id"] == 33
    assert races["GP de Singapura (SPRINT)"]["race_id"] == 34


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


def test_sessao_salva_antes_das_outras_nao_muda_o_race_id_de_ninguem(client, data_dir):
    before = {r["race_name"]: r["race_id"] for r in client.get("/load/2026/races").json()}

    # Uma Sprint na Austrália, antes de todas as Sessões de 2026, cadastrada com o ID 35
    replace_in_file(data_dir / "sessions.csv", "34,singapura,sprint,GP de Singapura,Marina Bay\n",
                    "34,singapura,sprint,GP de Singapura,Marina Bay\n35,australia,sprint,GP da Austrália,Melbourne\n")
    write_session(data_dir, "australia_sprint_20260301.csv", [(1, "Bryan", "Scuderia Ferrari HP", 1)])

    after = {r["race_name"]: r["race_id"] for r in client.get("/load/2026/races").json()}
    assert after == {**before, "GP da Austrália (SPRINT)": 35}
    assert before["GP do Canadá (SPRINT)"] == 31  # sem o Cadastro, viraria 32


def test_sessao_nova_entra_com_o_id_e_o_nome_do_cadastro(client, data_dir):
    with open(data_dir / "sessions.csv", "a", encoding="utf-8") as f:
        f.write("40,portugal,sprint,GP de Portugal,Portimão\n")

    write_session(data_dir, "portugal_sprint_20261020.csv", [(1, "Bryan", "Scuderia Ferrari HP", 1)])

    assert races_by_name(client, "2026")["GP de Portugal (SPRINT)"] == {
        "race_id": 40,
        "race_name": "GP de Portugal (SPRINT)",
        "race_date": "2026-10-20",
        "race_location": "Portimão",
        "is_sprint": True,
    }


def test_estreantes_entram_com_o_id_do_cadastro(client, data_dir):
    replace_in_file(data_dir / "drivers.csv", "11,Erick\n", "11,Erick\n20,Zeca\n")
    replace_in_file(data_dir / "teams.csv", "7,Visa Cash App Racing Bulls\n",
                    "7,Visa Cash App Racing Bulls\n15,Williams Racing\n")

    write_session(data_dir, "imola_sprint_20261020.csv", [
        (1, "Zeca", "Williams Racing", 1),
        (2, "Bryan", "Scuderia Ferrari HP", 2),
    ])

    zeca = next(d for d in client.get("/load/2026/drivers").json() if d["driver_name"] == "Zeca")
    williams = next(t for t in client.get("/load/2026/teams").json() if t["team_name"] == "Williams Racing")

    assert zeca == {"driver_id": 20, "team_id": 15, "driver_name": "Zeca"}
    assert williams == {"team_id": 15, "team_name": "Williams Racing"}


def test_pilotos_e_equipes_de_2025_tem_o_mesmo_id_no_cadastro(client, data_dir):
    # Uma Sessão com todo o grid de 2025 faz /load/2026/* mostrar o ID de cada um no Cadastro.
    # Desde 2026 os CSVs trazem a Red Bull como "Red Bull"; em 2025 era "Oracle Red Bull Racing".
    renamed = {"Oracle Red Bull Racing": "Red Bull"}
    drivers_2025 = client.get("/load/2025/drivers").json()
    teams_2025 = {t["team_id"]: t["team_name"] for t in client.get("/load/2025/teams").json()}

    write_session(data_dir, "mexico_race_20261026.csv", [
        (pos, driver["driver_name"], renamed.get(teams_2025[driver["team_id"]], teams_2025[driver["team_id"]]), pos)
        for pos, driver in enumerate(drivers_2025, start=1)
    ])
    drivers_2026 = {d["driver_name"]: d["driver_id"] for d in client.get("/load/2026/drivers").json()}
    teams_2026 = {t["team_name"]: t["team_id"] for t in client.get("/load/2026/teams").json()}

    assert len(drivers_2025) == 10 and len(teams_2025) == 5
    for driver in drivers_2025:
        assert drivers_2026[driver["driver_name"]] == driver["driver_id"], driver["driver_name"]
    for team_id, team_name in teams_2025.items():
        assert teams_2026[renamed.get(team_name, team_name)] == team_id, team_name


def test_dados_recarregam_quando_o_csv_muda(client, data_dir):
    def gabriel_points():
        standings = client.get("/load/2026/standings/drivers").json()
        return next(d["points"] for d in standings if d["driver_name"] == "Gabriel")

    before = gabriel_points()
    # Gabriel (5º no Japão, 10 pts) passa a ser 6º (8 pts), sem reiniciar a API
    replace_in_file(data_dir / "2026" / "japao_race_20260323.csv",
                    "5,Gabriel,Visa Cash App Racing Bulls,5,", "6,Gabriel,Visa Cash App Racing Bulls,5,")

    assert gabriel_points() == before - 2
