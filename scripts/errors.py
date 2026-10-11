#!/usr/bin/env python3
"""
Erros de dados e helpers de leitura usados pelos loaders de 2025 e 2026.

Todo problema nos arquivos de files/ (arquivo ausente, coluna faltando, valor
inválido) vira um DataError com uma mensagem que indica o arquivo e, quando
possível, a linha a corrigir. A API devolve essa mensagem ao cliente.
"""

import os
import pandas as pd


class DataError(Exception):
    """Problema nos arquivos de dados em files/."""


def display_path(path):
    """Caminho do arquivo relativo à pasta files/, para não expor o caminho absoluto do servidor."""
    parts = os.path.normpath(path).split(os.sep)
    if "files" in parts:
        idx = len(parts) - 1 - parts[::-1].index("files")
        relative = parts[idx + 1:]
        if relative:
            return "/".join(relative)
    return os.path.basename(path)


def require_dir(path):
    """Garante que a pasta de dados existe."""
    if not os.path.isdir(path):
        raise DataError(f"Pasta {display_path(path)} não encontrada.")


def read_csv(path):
    """Lê um CSV de files/, convertendo arquivo ausente ou ilegível em DataError."""
    if not os.path.exists(path):
        raise DataError(f"Arquivo {display_path(path)} não encontrado.")
    try:
        return pd.read_csv(path)
    except Exception as e:
        raise DataError(f"Não foi possível ler {display_path(path)}: {e}") from e


def require_columns(df, columns, path):
    """Garante que o DataFrame lido de `path` tem as colunas obrigatórias."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        names = ", ".join(f"'{c}'" for c in missing)
        raise DataError(f"{display_path(path)}: coluna(s) obrigatória(s) não encontrada(s): {names}.")


def to_int_column(df, column, path):
    """
    Converte a coluna para int. Um valor vazio ou não inteiro vira DataError
    indicando a linha do arquivo (considerando o cabeçalho na linha 1).
    """
    converted = pd.to_numeric(df[column], errors="coerce")
    invalid = converted.isna() | (converted % 1 != 0)
    if invalid.any():
        pos = int(invalid.to_numpy().argmax())
        raise DataError(
            f"{display_path(path)}, linha {pos + 2}: coluna '{column}' com valor "
            f"'{df[column].iloc[pos]}' (esperado um número inteiro)."
        )
    return converted.astype(int)
