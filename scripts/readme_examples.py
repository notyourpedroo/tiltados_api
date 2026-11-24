"""
Exemplos de resposta do README com valores reais: acha cada bloco JSON pela rota e o reescreve com a resposta atual.

Cada rota de EXAMPLE_ROUTES tem, no README, uma linha "`GET <rota>`" seguida de um bloco ```json com os N
primeiros itens da resposta. O bloco é achado pela rota, não pelo número da seção. Os exemplos hipotéticos e os
das outras rotas ficam de fora.

Uso, na raiz do projeto (depois de adicionar uma Corrida):

    python -X utf8 -m scripts.readme_examples
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

EXAMPLE_ROUTES = (
    "/load/2026/standings/drivers",
    "/load/2026/standings/teams",
    "/load/2026/prediction/drivers",
    "/load/2026/prediction/teams",
)


def find_example(readme, route):
    """
    Acha o bloco de exemplo da rota: o primeiro ```json depois da linha "`GET <rota>`", antes do próximo título.
    Devolve (início, fim, itens): o trecho readme[início:fim] é o JSON do bloco, e itens é a lista lida dele.
    Levanta ValueError se a rota ou o bloco não estiverem no README.
    """
    route_line = re.search(rf"^`GET {re.escape(route)}`$", readme, re.MULTILINE)
    if route_line is None:
        raise ValueError(f"README.md: linha '`GET {route}`' não encontrada.")
    next_title = re.compile(r"^#", re.MULTILINE).search(readme, route_line.end())
    section_end = next_title.start() if next_title else len(readme)
    block = re.compile(r"^```json\n(.*?)\n```$", re.MULTILINE | re.DOTALL).search(readme, route_line.end(), section_end)
    if block is None:
        raise ValueError(f"README.md: bloco ```json do exemplo de '{route}' não encontrado.")
    return block.start(1), block.end(1), json.loads(block.group(1))


def render(items):
    """O JSON de um bloco de exemplo, no formato do README."""
    return json.dumps(items, indent=2, ensure_ascii=False)


def rewrite_examples(readme, get_json):
    """
    Devolve o README com o bloco de cada rota de EXAMPLE_ROUTES trocado pelos N primeiros itens da resposta,
    N sendo quantos itens o bloco já mostra. get_json(rota) devolve a resposta da rota. O resto fica intacto.
    """
    for route in EXAMPLE_ROUTES:
        start, end, items = find_example(readme, route)
        readme = readme[:start] + render(get_json(route)[:len(items)]) + readme[end:]
    return readme


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    import main

    client = TestClient(main.app)

    def get_json(route):
        response = client.get(route)
        response.raise_for_status()
        return response.json()

    text = README.read_text(encoding="utf-8")
    updated = rewrite_examples(text, get_json)
    if updated == text:
        print("README.md já está em dia com a API.")
    else:
        with open(README, "w", encoding="utf-8", newline="") as f:
            f.write(updated)
        print("README.md atualizado: " + ", ".join(EXAMPLE_ROUTES))
