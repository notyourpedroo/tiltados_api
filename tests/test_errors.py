"""Problemas nos CSVs devem voltar ao cliente com o arquivo e a linha a corrigir."""

import os

import pytest

from conftest import replace_in_file

JAPAO = "2026/japao_race_20260323.csv"
MIAMI = "2026/miami_race_20260427.csv"
PUNISHMENTS = "super_license/punishments.csv"


def _replace(relative_path, old, new):
    return lambda data_dir: replace_in_file(data_dir / relative_path, old, new)


def _remove(relative_path):
    return lambda data_dir: os.remove(data_dir / relative_path)


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
