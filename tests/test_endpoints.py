"""Respostas básicas e consistência dos endpoints com os dados reais."""

import pytest

import main

SEASONS = ("2025", "2026")
SEASON_RESOURCES = ("drivers", "teams", "races", "results", "standings/drivers", "standings/teams")
ENDPOINTS = [f"/load/{season}/{resource}" for season in SEASONS for resource in SEASON_RESOURCES] + [
    "/load/2026/punishments",
    "/load/2026/super-license",
    "/load/2026/prediction/drivers",
]


def test_root_retorna_versao_da_api(client):
    body = client.get("/").json()
    assert body["version"] == main.API_VERSION
    assert body["seasons"] == [2025, 2026]


@pytest.mark.parametrize("path", ENDPOINTS)
def test_endpoint_responde_lista_nao_vazia(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list) and response.json()


def test_temporada_invalida_retorna_422(client):
    assert client.get("/load/2027/drivers").status_code == 422


@pytest.mark.parametrize("season", SEASONS)
def test_resultados_apontam_para_corridas_pilotos_e_equipes_existentes(client, season):
    races = {r["race_id"] for r in client.get(f"/load/{season}/races").json()}
    drivers = {d["driver_id"] for d in client.get(f"/load/{season}/drivers").json()}
    teams = {t["team_id"] for t in client.get(f"/load/{season}/teams").json()}

    for result in client.get(f"/load/{season}/results").json():
        assert result["race_id"] in races
        assert result["driver_id"] in drivers
        assert result["team_id"] in teams


@pytest.mark.parametrize("season", SEASONS)
def test_race_ids_sao_unicos_na_temporada(client, season):
    ids = [r["race_id"] for r in client.get(f"/load/{season}/races").json()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("season", SEASONS)
def test_pontos_de_pilotos_e_construtores_somam_o_mesmo(client, season):
    drivers = client.get(f"/load/{season}/standings/drivers").json()
    teams = client.get(f"/load/{season}/standings/teams").json()
    assert sum(d["points"] for d in drivers) == sum(t["points"] for t in teams)


@pytest.mark.parametrize("path", ["/load/2025/standings/drivers", "/load/2026/standings/teams"])
def test_classificacao_ordenada_por_pontos(client, path):
    standings = client.get(path).json()
    assert [s["position"] for s in standings] == list(range(1, len(standings) + 1))
    points = [s["points"] for s in standings]
    assert points == sorted(points, reverse=True)


def test_superlicenca_cobre_todos_os_pilotos_com_saldo_correto(client):
    drivers = {d["driver_id"] for d in client.get("/load/2026/drivers").json()}
    license_rows = client.get("/load/2026/super-license").json()

    assert {row["driver_id"] for row in license_rows} == drivers
    for row in license_rows:
        assert row["remaining_points"] == row["initial_points"] - row["deducted_points"]


def test_punicoes_trazem_nomes_de_piloto_equipe_e_corrida(client):
    for punishment in client.get("/load/2026/punishments").json():
        for field in ("driver_name", "team_id", "team_name", "race_name", "race_date"):
            assert punishment[field] not in (None, ""), field


def test_cors_libera_qualquer_origem_sem_credenciais(client):
    response = client.get("/load/2026/teams", headers={"Origin": "https://exemplo.com"})
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers
