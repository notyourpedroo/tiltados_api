"""
Fixtures compartilhadas pelos testes da API.

Cada teste roda sobre uma cópia de files/ num diretório temporário, então os
testes podem alterar ou quebrar CSVs à vontade sem tocar nos dados reais.
"""

import os
import re
import shutil

import pytest
from fastapi.testclient import TestClient

import main

REPO_FILES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files")

SESSION_HEADER = "Pos.,Piloto,Equipe,Grid,Paradas,Melhor tempo,Tempo,Pts.,tipo de piloto\n"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Cópia de files/ num diretório temporário; a API passa a ler dela."""
    shutil.copytree(REPO_FILES, tmp_path / "files")
    monkeypatch.setattr(main, "BASE_DIR", str(tmp_path))
    return tmp_path / "files"


@pytest.fixture
def client(data_dir):
    return TestClient(main.app)


def replace_in_file(path, old, new):
    """Substitui a primeira ocorrência de `old` preservando BOM e fim de linha do arquivo."""
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    assert old in text, f"trecho {old!r} não encontrado em {path}"
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace(old, new, 1))


def write_calendar(data_dir, rows):
    """
    Reescreve o Calendário de 2026 com as Sessões (local, tipo, data) dadas.
    As Sessões fora do Cadastro da cópia são cadastradas antes.
    """
    for local, session_type, _ in rows:
        register_session(data_dir, local, session_type)
    lines = [f"{local},{session_type},{date}\n" for local, session_type, date in rows]
    with open(data_dir / "2026" / "calendar.csv", "w", encoding="utf-8") as f:
        f.write("local,tipo,data\n" + "".join(lines))


def reset_2026_season(data_dir):
    """Apaga as sessões e punições de 2026, para o teste montar a temporada do zero."""
    for file_name in os.listdir(data_dir / "2026"):
        if file_name not in ("scores.csv", "calendar.csv"):
            os.remove(data_dir / "2026" / file_name)
    with open(data_dir / "super_license" / "punishments.csv", "w", encoding="utf-8") as f:
        f.write("season_year,driver_id,race_id,deduction_points,penalty_reason\n")


def register(data_dir, file_name, names):
    """Acrescenta ao Cadastro (drivers.csv ou teams.csv) os nomes que ainda não estão nele, com o próximo ID livre."""
    path = data_dir / file_name
    with open(path, encoding="utf-8") as f:
        rows = [line.rstrip("\n").split(",", 1) for line in f.readlines()[1:] if line.strip()]
    registered = {name for _, name in rows}
    next_id = max(int(row_id) for row_id, _ in rows) + 1
    with open(path, "a", encoding="utf-8") as f:
        for name in dict.fromkeys(names):
            if name not in registered:
                f.write(f"{next_id},{name}\n")
                next_id += 1


def register_session(data_dir, local, session_type):
    """
    Acrescenta ao Cadastro de Sessões (sessions.csv) a Sessão (local, tipo), se ainda não estiver nele,
    com o próximo race_id livre. O nome do GP e a cidade são os da outra Sessão do mesmo local, se houver.
    """
    path = data_dir / "sessions.csv"
    with open(path, encoding="utf-8") as f:
        rows = [line.rstrip("\n").split(",") for line in f.readlines()[1:] if line.strip()]
    if any(row[1] == local and row[2] == session_type for row in rows):
        return
    same_local = next((row for row in rows if row[1] == local), None)
    race_name, location = (same_local[3], same_local[4]) if same_local else (f"GP de {local}", local)
    next_id = max(int(row[0]) for row in rows) + 1
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{next_id},{local},{session_type},{race_name},{location}\n")


def write_session(data_dir, file_name, rows):
    """
    Cria um CSV de sessão de 2026 com o cabeçalho do export e as linhas dadas.
    Pilotos, equipes e a Sessão (local e tipo do nome do arquivo) fora do Cadastro da cópia são cadastrados antes.
    """
    local, session_type = re.match(r"(\w+)_(race|sprint)_\d{8}\.csv$", file_name).groups()
    register_session(data_dir, local, session_type)
    register(data_dir, "drivers.csv", [driver for _, driver, _, _ in rows])
    register(data_dir, "teams.csv", [team for _, _, team, _ in rows])
    lines = [
        f"{pos},{driver},{team},{grid},2,1:30.000,40:00.000,0,Pessoa\n"
        for pos, driver, team, grid in rows
    ]
    with open(data_dir / "2026" / file_name, "w", encoding="utf-8") as f:
        f.write(SESSION_HEADER + "".join(lines))
