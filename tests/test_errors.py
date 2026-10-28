"""Problemas nos CSVs devem voltar ao cliente com o arquivo e a linha a corrigir."""

import os

import pytest

from conftest import replace_in_file

JAPAO = "2026/japao_race_20260323.csv"
MIAMI = "2026/miami_race_20260427.csv"
PUNISHMENTS = "super_license/punishments.csv"
CALENDAR = "2026/calendar.csv"
PREDICTION = "/load/2026/prediction/drivers"
DRIVERS_REGISTRY = "drivers.csv"
TEAMS_REGISTRY = "teams.csv"
SESSIONS_REGISTRY = "sessions.csv"


def _replace(relative_path, old, new):
    return lambda data_dir: replace_in_file(data_dir / relative_path, old, new)


def _remove(relative_path):
    return lambda data_dir: os.remove(data_dir / relative_path)


def _rename(relative_path, new_relative_path):
    return lambda data_dir: os.rename(data_dir / relative_path, data_dir / new_relative_path)


# (descrição, alteração nos dados, endpoint, trechos esperados na mensagem)
SCENARIOS = [
    (
        "posicao nao numerica em 2025",
        _replace("2025/results.csv", "\n1,1,1,7,6,", "\n1,1,1,7,X,"),
        "/load/2025/standings/drivers",
        ["2025/results.csv, linha 2", "'driver_final_position'", "'X'"],
    ),
    (
        "coluna obrigatoria ausente",
        _replace(JAPAO, ",Grid,", ",Largada,"),
        "/load/2026/results",
        [JAPAO, "'Grid'"],
    ),
    (
        "grid nao numerico",
        _replace(JAPAO, "Racing Bulls,1,2,", "Racing Bulls,X,2,"),
        "/load/2026/results",
        [f"{JAPAO}, linha 2", "'Grid'", "'X'"],
    ),
    (
        "equipe vazia",
        _replace(JAPAO, "2,Paulo,Scuderia Ferrari HP,", "2,Paulo,,"),
        "/load/2026/standings/teams",
        [f"{JAPAO}, linha 3", "'Equipe' vazia"],
    ),
    (
        "placeholder Pessoa no lugar do piloto",
        _replace(MIAMI, "4,Gabriel,Visa", "4,Pessoa,Visa"),
        "/load/2026/drivers",
        [f"{MIAMI}, linha 5", "'Pessoa'"],
    ),
    (
        "piloto fora do Cadastro",
        _replace(JAPAO, "3,Yohan,", "3,Mateus,"),
        "/load/2026/drivers",
        [f"{JAPAO}, linha 4: coluna 'Piloto' com valor 'Mateus' (esperado um piloto do Cadastro)."],
    ),
    (
        "equipe fora do Cadastro",
        _replace(JAPAO, "3,Yohan,Red Bull,", "3,Yohan,Redbull,"),
        "/load/2026/teams",
        [f"{JAPAO}, linha 4: coluna 'Equipe' com valor 'Redbull' (esperado uma equipe do Cadastro)."],
    ),
    (
        "ID repetido no Cadastro de pilotos",
        _replace(DRIVERS_REGISTRY, "11,Erick", "10,Erick"),
        "/load/2026/drivers",
        ["drivers.csv, linha 12: coluna 'driver_id' com valor '10' "
         "(esperado um valor único no Cadastro, já usado na linha 11)."],
    ),
    (
        "nome repetido no Cadastro de equipes",
        _replace(TEAMS_REGISTRY, "5,Stake F1 Team Kick Sauber", "5,Red Bull"),
        "/load/2026/teams",
        ["teams.csv, linha 6: coluna 'team_name' com valor 'Red Bull' "
         "(esperado um valor único no Cadastro, já usado na linha 2)."],
    ),
    (
        "coluna ausente no Cadastro",
        _replace(DRIVERS_REGISTRY, "driver_id,driver_name", "driver_id,nome"),
        "/load/2026/standings/drivers",
        [DRIVERS_REGISTRY, "'driver_name'"],
    ),
    (
        "ID nao inteiro no Cadastro",
        _replace(TEAMS_REGISTRY, "6,Mercedes", "seis,Mercedes"),
        "/load/2026/standings/teams",
        [f"{TEAMS_REGISTRY}, linha 7", "'team_id'", "'seis'"],
    ),
    (
        "nome vazio no Cadastro",
        _replace(DRIVERS_REGISTRY, "11,Erick", "11,"),
        "/load/2026/drivers",
        [f"{DRIVERS_REGISTRY}, linha 12: coluna 'driver_name' vazia."],
    ),
    (
        "Sessao fora do Cadastro no nome do arquivo",
        _rename(JAPAO, "2026/japao_sprint_20260323.csv"),
        "/load/2026/races",
        ["2026/japao_sprint_20260323.csv: local 'japao' com tipo 'sprint' no nome do arquivo "
         "(esperado uma Sessão do Cadastro)."],
    ),
    (
        "race_id repetido no Cadastro de Sessoes",
        _replace(SESSIONS_REGISTRY, "31,canada,sprint", "30,canada,sprint"),
        "/load/2026/races",
        ["sessions.csv, linha 32: coluna 'race_id' com valor '30' "
         "(esperado um valor único no Cadastro, já usado na linha 31)."],
    ),
    (
        "local e tipo repetidos no Cadastro de Sessoes",
        _replace(SESSIONS_REGISTRY, "33,holanda,sprint", "33,canada,sprint"),
        "/load/2026/races",
        ["sessions.csv, linha 34: colunas 'local' e 'tipo' com valor 'canada' e 'sprint' "
         "(esperado um valor único no Cadastro, já usado na linha 32)."],
    ),
    (
        "coluna ausente no Cadastro de Sessoes",
        _replace(SESSIONS_REGISTRY, "race_id,local,tipo,race_name,", "race_id,local,tipo,nome,"),
        "/load/2026/races",
        [SESSIONS_REGISTRY, "'race_name'"],
    ),
    (
        "race_id nao inteiro no Cadastro de Sessoes",
        _replace(SESSIONS_REGISTRY, "34,singapura,sprint", "trinta,singapura,sprint"),
        "/load/2026/results",
        [f"{SESSIONS_REGISTRY}, linha 35", "'race_id'", "'trinta'"],
    ),
    (
        "tipo invalido no Cadastro de Sessoes",
        _replace(SESSIONS_REGISTRY, "31,canada,sprint", "31,canada,corrida"),
        "/load/2026/standings/drivers",
        [f"{SESSIONS_REGISTRY}, linha 32: coluna 'tipo' com valor 'corrida' (esperado 'race' ou 'sprint')."],
    ),
    (
        "scores.csv ausente",
        _remove("2026/scores.csv"),
        "/load/2026/standings/drivers",
        ["2026/scores.csv não encontrado"],
    ),
    (
        "driver_id nao numerico nas punicoes",
        _replace(PUNISHMENTS, "2026,8,34,", "2026,oito,34,"),
        "/load/2026/super-license",
        [f"{PUNISHMENTS}, linha 5", "'driver_id'", "'oito'"],
    ),
    (
        "punicao para corrida inexistente",
        _replace(PUNISHMENTS, "2026,8,34,", "2026,8,99,"),
        "/load/2026/punishments",
        [f"{PUNISHMENTS}, linha 5", "race_id 99"],
    ),
    (
        "calendario ausente",
        _remove(CALENDAR),
        PREDICTION,
        [f"{CALENDAR} não encontrado"],
    ),
    (
        "coluna ausente no calendario",
        _replace(CALENDAR, "local,tipo,data", "local,tipo,dia"),
        PREDICTION,
        [CALENDAR, "'data'"],
    ),
    (
        "tipo invalido no calendario",
        _replace(CALENDAR, "mexico,race,", "mexico,corrida,"),
        PREDICTION,
        [f"{CALENDAR}, linha 25", "'tipo'", "'corrida'"],
    ),
    (
        "Sessao fora do Cadastro no calendario",
        _replace(CALENDAR, "mexico,race,", "mexcio,race,"),
        PREDICTION,
        [f"{CALENDAR}, linha 25: local 'mexcio' com tipo 'race' (esperado uma Sessão do Cadastro)."],
    ),
    (
        "data invalida no calendario",
        _replace(CALENDAR, "mexico,race,2026-11-01", "mexico,race,01/11/2026"),
        PREDICTION,
        [f"{CALENDAR}, linha 25", "'data'", "'01/11/2026'"],
    ),
    (
        "sessao repetida no calendario",
        _replace(CALENDAR, "brasil,race,2026-11-08", "mexico,race,2026-11-08"),
        PREDICTION,
        [f"{CALENDAR}, linha 26", "'mexico'", "repetida"],
    ),
    (
        "resultado sem sessao no calendario",
        _replace(CALENDAR, "japao,race,2026-03-23\n", ""),
        PREDICTION,
        [JAPAO, CALENDAR, "japao,race,2026-03-23"],
    ),
]


@pytest.mark.parametrize("mutate, path, expected", [s[1:] for s in SCENARIOS], ids=[s[0] for s in SCENARIOS])
def test_erro_nos_dados_retorna_causa(client, data_dir, mutate, path, expected):
    mutate(data_dir)
    response = client.get(path)

    assert response.status_code == 500
    detail = response.json()["detail"]
    for fragment in expected:
        assert fragment in detail
    assert str(data_dir.parent) not in detail  # não expõe o caminho absoluto do servidor


def test_api_volta_ao_normal_quando_o_csv_e_corrigido(client, data_dir):
    miami = data_dir / MIAMI
    replace_in_file(miami, "4,Gabriel,Visa", "4,Pessoa,Visa")
    assert client.get("/load/2026/drivers").status_code == 500

    replace_in_file(miami, "4,Pessoa,Visa", "4,Gabriel,Visa")
    assert client.get("/load/2026/drivers").status_code == 200


def test_placeholder_nao_afeta_endpoints_que_nao_dependem_de_pilotos(client, data_dir):
    replace_in_file(data_dir / MIAMI, "4,Gabriel,Visa", "4,Pessoa,Visa")
    assert client.get("/load/2026/teams").status_code == 200
    assert client.get("/load/2026/races").status_code == 200


def test_erro_no_calendario_nao_afeta_endpoints_que_nao_dependem_dele(client, data_dir):
    # Sem remover o Calendário: uma pasta sem Calendário deixa de ser temporada (404, em test_seasons.py)
    replace_in_file(data_dir / CALENDAR, "mexico,race,", "mexico,corrida,")
    assert client.get(PREDICTION).status_code == 500
    assert client.get("/load/2026/standings/drivers").status_code == 200
    assert client.get("/load/2025/standings/drivers").status_code == 200


def test_chance_de_titulo_volta_ao_normal_quando_o_calendario_e_corrigido(client, data_dir):
    replace_in_file(data_dir / CALENDAR, "mexico,race,", "mexico,corrida,")
    assert client.get(PREDICTION).status_code == 500

    replace_in_file(data_dir / CALENDAR, "mexico,corrida,", "mexico,race,")
    assert client.get(PREDICTION).status_code == 200


def test_erro_no_cadastro_nao_afeta_endpoints_que_nao_dependem_dele(client, data_dir):
    replace_in_file(data_dir / DRIVERS_REGISTRY, "11,Erick", "10,Erick")
    assert client.get("/load/2026/drivers").status_code == 500
    assert client.get("/load/2026/races").status_code == 200
    assert client.get("/load/2026/teams").status_code == 200
    assert client.get("/load/2025/drivers").status_code == 200
    assert client.get("/load/2025/standings/drivers").status_code == 200


def test_erro_no_cadastro_de_sessoes_nao_afeta_endpoints_que_nao_dependem_dele(client, data_dir):
    replace_in_file(data_dir / SESSIONS_REGISTRY, "31,canada,sprint", "30,canada,sprint")
    assert client.get("/load/2026/races").status_code == 500
    assert client.get("/load/2026/drivers").status_code == 200
    assert client.get("/load/2026/teams").status_code == 200
    assert client.get("/load/2025/races").status_code == 200
    assert client.get("/load/2025/standings/drivers").status_code == 200


def test_api_volta_ao_normal_quando_o_cadastro_e_corrigido(client, data_dir):
    replace_in_file(data_dir / JAPAO, "3,Yohan,", "3,Mateus,")
    assert client.get("/load/2026/standings/drivers").status_code == 500

    replace_in_file(data_dir / DRIVERS_REGISTRY, "11,Erick", "11,Erick\n12,Mateus")
    assert client.get("/load/2026/standings/drivers").status_code == 200
