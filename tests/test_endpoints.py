"""Respostas básicas e consistência dos endpoints com os dados reais."""

import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

import main

ROOT = Path(__file__).resolve().parents[1]
# Temporadas dos dados reais, lidas das pastas: 2025 (consolidada) e toda files/{ano}/ com Calendário.
# Abrir 2027 não pede mudança aqui.
SESSION_SEASONS = tuple(sorted(
    d.name for d in (ROOT / "files").iterdir() if re.fullmatch(r"\d{4}", d.name) and (d / "calendar.csv").exists()
))
SEASONS = ("2025",) + SESSION_SEASONS
# Temporadas com alguma Sessão disputada; as outras respondem lista vazia até a primeira Sessão
PLAYED_SEASONS = ("2025",) + tuple(
    season for season in SESSION_SEASONS
    if any(re.fullmatch(r"\w+_(race|sprint)_\d{8}\.csv", f.name) for f in (ROOT / "files" / season).iterdir())
)
API_ROUTES = [r.path for r in main.app.routes if isinstance(r, APIRoute) and "GET" in r.methods]
# Rotas que só existem nas temporadas por Sessão: em 2025 respondem 404 (tests/test_seasons.py)
SESSION_ONLY_ROUTES = {
    "/load/{season}/punishments",
    "/load/{season}/super-license",
    "/load/{season}/prediction/drivers",
    "/load/{season}/prediction/teams",
}


def expand(path, seasons=SEASONS):
    """
    Troca {season} por cada temporada: '/load/{season}/drivers' -> '/load/2025/drivers', '/load/2026/drivers'.
    As rotas que só existem nas temporadas por Sessão ficam só com elas: '/load/2026/punishments'.
    """
    if "{season}" not in path:
        return [path]
    if path in SESSION_ONLY_ROUTES:
        seasons = [season for season in seasons if season in SESSION_SEASONS]
    return [path.replace("{season}", season) for season in seasons]


# Toda rota da API entra nos testes de resposta automaticamente
ENDPOINTS = [path for route in API_ROUTES for path in expand(route, PLAYED_SEASONS) if path != "/"]


def test_root_retorna_versao_da_api(client):
    body = client.get("/").json()
    assert body["version"] == main.API_VERSION
    assert body["seasons"] == [int(season) for season in SEASONS]


@pytest.mark.parametrize("path", ENDPOINTS)
def test_endpoint_responde_lista_nao_vazia(client, path):
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list) and response.json()


@pytest.mark.parametrize("season", ["1999", "2024", "abc"])
def test_temporada_inexistente_retorna_404(client, season):
    response = client.get(f"/load/{season}/drivers")
    assert response.status_code == 404
    assert response.json()["detail"] == (
        f"Temporada {season} não encontrada. Temporadas disponíveis: {', '.join(SEASONS)}."
    )


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


def test_lista_de_rotas_testadas_vem_do_app():
    assert "/load/2025/standings/drivers" in ENDPOINTS
    assert "/load/2026/prediction/teams" in ENDPOINTS


def test_toda_rota_esta_na_tabela_do_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for route in API_ROUTES:
        assert f"| GET | `{route}` |" in readme, route


def test_readme_mostra_a_versao_atual_da_api():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f'"version": "{main.API_VERSION}"' in readme


def test_health_check_do_deploy_consulta_todas_as_rotas():
    script = (ROOT / "deploy" / "publicar.sh").read_text(encoding="utf-8")
    block = script.split("HEALTH_URLS=(", 1)[1].split(")", 1)[0]
    urls = [line.strip().removeprefix("http://127.0.0.1:8000") for line in block.splitlines() if line.strip()]

    assert sorted(urls) == sorted(path for route in API_ROUTES for path in expand(route))
