"""Exemplos de resposta do README com valores reais conferidos contra a API (scripts/readme_examples.py)."""

from pathlib import Path

import pytest

from scripts.readme_examples import EXAMPLE_ROUTES, find_example, render, rewrite_examples

README = Path(__file__).resolve().parents[1] / "README.md"
UPDATE_COMMAND = "python -X utf8 -m scripts.readme_examples"


@pytest.mark.parametrize("route", EXAMPLE_ROUTES)
def test_exemplo_do_readme_bate_com_a_resposta_da_rota(client, route):
    _, _, items = find_example(README.read_text(encoding="utf-8"), route)
    assert items, f"o exemplo de {route} no README está vazio"
    assert items == client.get(route).json()[:len(items)], (
        f"o exemplo de {route} no README difere da API; atualize com: {UPDATE_COMMAND}"
    )


def test_script_reescreve_os_exemplos_sem_mudar_o_readme_em_dia(client):
    readme = README.read_text(encoding="utf-8")
    assert rewrite_examples(readme, lambda route: client.get(route).json()) == readme


@pytest.mark.parametrize("route", EXAMPLE_ROUTES)
def test_script_corrige_o_exemplo_desatualizado_e_deixa_o_resto_intacto(client, route):
    readme = README.read_text(encoding="utf-8")
    start, end, items = find_example(readme, route)
    items[0]["points"] += 1
    outdated = readme[:start] + render(items) + readme[end:]
    assert rewrite_examples(outdated, lambda route: client.get(route).json()) == readme


def test_readme_diz_como_atualizar_os_exemplos():
    assert UPDATE_COMMAND in README.read_text(encoding="utf-8")
