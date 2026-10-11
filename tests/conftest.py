"""
Fixtures compartilhadas pelos testes da API.

Cada teste roda sobre uma cópia de files/ num diretório temporário, então os
testes podem alterar ou quebrar CSVs à vontade sem tocar nos dados reais.
"""

import os
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


def write_session(data_dir, file_name, rows):
    """Cria um CSV de sessão de 2026 com o cabeçalho do export e as linhas dadas."""
    lines = [
        f"{pos},{driver},{team},{grid},2,1:30.000,40:00.000,0,Pessoa\n"
        for pos, driver, team, grid in rows
    ]
    with open(data_dir / "2026" / file_name, "w", encoding="utf-8") as f:
        f.write(SESSION_HEADER + "".join(lines))
