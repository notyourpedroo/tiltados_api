"""Fixação das actions nos workflows do GitHub: oficiais pela tag de major, de terceiros pelo SHA."""

import os
import re

import pytest

WORKFLOWS_DIR = os.path.join(os.path.dirname(__file__), "..", ".github", "workflows")

USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)\s*(?:#\s*(.*))?$")
OFFICIAL_BY_MAJOR = re.compile(r"actions/[\w.-]+@v\d+")
THIRD_PARTY_BY_SHA = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}")


def pinning_error(line):
    """O motivo de a linha `uses:` estar fora da regra, ou None quando está certa."""
    match = USES.match(line)
    if not match:
        return None
    ref, comment = match.groups()
    if ref.startswith("./"):
        return None
    if ref.startswith("actions/"):
        return None if OFFICIAL_BY_MAJOR.fullmatch(ref) else f"{ref}: action oficial vai pela tag de major (@vN)"
    if not THIRD_PARTY_BY_SHA.fullmatch(ref):
        return f"{ref}: action de terceiros vai pelo SHA de 40 caracteres do commit"
    if not comment:
        return f"{ref}: falta a versão no comentário"
    return None


def workflow_lines():
    for name in sorted(os.listdir(WORKFLOWS_DIR)):
        if name.endswith((".yml", ".yaml")):
            with open(os.path.join(WORKFLOWS_DIR, name), encoding="utf-8") as f:
                for number, line in enumerate(f, start=1):
                    yield f"{name}:{number}", line.rstrip("\n")


def test_toda_action_dos_workflows_segue_a_regra_de_fixacao():
    errors = [f"{where} {error}" for where, line in workflow_lines() if (error := pinning_error(line))]

    assert errors == []


def test_os_workflows_usam_alguma_action():
    # Garante que a regex de `uses:` ainda reconhece as linhas do workflow
    assert any(USES.match(line) for _, line in workflow_lines())


@pytest.mark.parametrize("line", [
    "      - uses: actions/checkout@v7",
    "      - uses: actions/download-artifact@v8",
    "        uses: actions/setup-python@v7",
    "      - uses: ./.github/actions/local",
    "      - uses: owner/some-action@0123456789abcdef0123456789abcdef01234567 # v2.1.0",
])
def test_linhas_dentro_da_regra(line):
    assert pinning_error(line) is None


@pytest.mark.parametrize("line", [
    "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
    "      - uses: actions/checkout@v7.0.1",
    "      - uses: actions/checkout@main",
    "      - uses: owner/some-action@v2",
    "      - uses: owner/some-action@0123456789abcdef0123456789abcdef01234567",
])
def test_linhas_fora_da_regra(line):
    assert pinning_error(line) is not None
