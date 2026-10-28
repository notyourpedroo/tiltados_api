#!/usr/bin/env python3
"""
Carregar o Cadastro de pilotos, equipes e Sessões das temporadas por Sessão.

O Cadastro fica na raiz da pasta de dados (files/drivers.csv, files/teams.csv e
files/sessions.csv) e vale para todas as temporadas por Sessão: é dele que saem
o ID e o nome de cada piloto, equipe e Sessão. Um nome num CSV de Sessão, ou um
local e tipo no nome do arquivo, que não está no Cadastro é erro, em vez de
ganhar um ID novo.
"""

import os
import sys

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from ..errors import DataError, display_path, read_csv, require_columns, to_int_column
except (ImportError, ValueError):
    scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from errors import DataError, display_path, read_csv, require_columns, to_int_column


DRIVERS_FILE = "drivers.csv"
TEAMS_FILE = "teams.csv"
SESSIONS_FILE = "sessions.csv"

# Valores da coluna 'tipo' do Cadastro de Sessões (e do Calendário) -> is_sprint
SESSION_TYPES = {"race": False, "sprint": True}


def _describe_columns(columns, values):
    """Trecho da mensagem de erro para uma coluna ou um par de colunas e seus valores."""
    if len(columns) == 1:
        return f"coluna '{columns[0]}' com valor '{values[0]}'"
    names = " e ".join(f"'{c}'" for c in columns)
    shown = " e ".join(f"'{v}'" for v in values)
    return f"colunas {names} com valor {shown}"


def read_registry(path, id_column, name_columns, unique_columns=None):
    """
    Lê um CSV do Cadastro e valida o ID e as colunas de nome.

    Retorna o DataFrame com `id_column` como int e as colunas de `name_columns`
    sem espaços nas pontas. `unique_columns` diz o que não pode se repetir: cada
    item é uma coluna ou uma tupla de colunas que, juntas, identificam a linha.
    Padrão: o ID e cada coluna de nome.

    Raises:
        DataError: Se o arquivo não existir ou não puder ser lido, faltar coluna,
                   o ID não for inteiro, um nome estiver vazio ou um ID ou nome
                   se repetir (sempre com a linha a corrigir).
    """
    df = read_csv(path)
    require_columns(df, [id_column, *name_columns], path)
    df[id_column] = to_int_column(df, id_column, path)

    for column in name_columns:
        empty = df[column].isna() | (df[column].astype(str).str.strip() == "")
        if empty.any():
            pos = int(empty.to_numpy().argmax())
            raise DataError(f"{display_path(path)}, linha {pos + 2}: coluna '{column}' vazia.")
        df[column] = df[column].astype(str).str.strip()

    if unique_columns is None:
        unique_columns = [id_column, *name_columns]
    for unique in unique_columns:
        columns = list(unique) if isinstance(unique, tuple) else [unique]
        first_line = {}
        for pos, values in enumerate(zip(*(df[c] for c in columns))):
            if values in first_line:
                raise DataError(
                    f"{display_path(path)}, linha {pos + 2}: {_describe_columns(columns, values)} "
                    f"(esperado um valor único no Cadastro, já usado na linha {first_line[values]})."
                )
            first_line[values] = pos + 2

    return df


def load_registered_drivers(registry_path="./files"):
    """
    Retorna os pilotos do Cadastro (files/drivers.csv).

    Colunas do DataFrame retornado:
    - driver_id: ID do piloto, o mesmo em todas as temporadas
    - driver_name: Nome do piloto, como aparece na coluna 'Piloto' dos CSVs de Sessão

    Raises:
        DataError: Nos casos de `read_registry`.
    """
    path = os.path.join(registry_path, DRIVERS_FILE)
    return read_registry(path, "driver_id", ["driver_name"])[["driver_id", "driver_name"]]


def load_registered_teams(registry_path="./files"):
    """
    Retorna as equipes do Cadastro (files/teams.csv).

    Colunas do DataFrame retornado:
    - team_id: ID da equipe, o mesmo em todas as temporadas
    - team_name: Nome da equipe, como aparece na coluna 'Equipe' dos CSVs de Sessão

    Raises:
        DataError: Nos casos de `read_registry`.
    """
    path = os.path.join(registry_path, TEAMS_FILE)
    return read_registry(path, "team_id", ["team_name"])[["team_id", "team_name"]]


def load_registered_sessions(registry_path="./files"):
    """
    Retorna as Sessões do Cadastro (files/sessions.csv).

    Colunas do DataFrame retornado:
    - race_id: ID da Sessão, o mesmo em todas as temporadas
    - local: Local da Etapa, como no nome dos arquivos de Sessão e no Calendário (ex: 'china')
    - is_sprint: Indica se a Sessão é uma Sprint (coluna 'tipo': 'race' ou 'sprint')
    - race_name: Nome do GP, sem o sufixo da Sprint (ex: 'GP da China')
    - race_location: Cidade da Etapa

    Raises:
        DataError: Nos casos de `read_registry`, se o tipo não for 'race' ou 'sprint'
                   ou se o mesmo local e tipo se repetirem (com a linha a corrigir).
    """
    path = os.path.join(registry_path, SESSIONS_FILE)
    df = read_registry(
        path, "race_id", ["local", "tipo", "race_name", "race_location"],
        unique_columns=["race_id", ("local", "tipo")],
    )
    for pos, value in enumerate(df["tipo"]):
        if value not in SESSION_TYPES:
            raise DataError(
                f"{display_path(path)}, linha {pos + 2}: coluna 'tipo' com valor '{value}' "
                "(esperado 'race' ou 'sprint')."
            )
    df["is_sprint"] = df["tipo"].map(SESSION_TYPES).astype(bool)
    return df[["race_id", "local", "is_sprint", "race_name", "race_location"]]


def require_registered(df_session, column, registered_names, expected, file_path):
    """
    Garante que todo valor da coluna do CSV de Sessão está no Cadastro.

    `expected` completa a mensagem (ex.: "um piloto do Cadastro").

    Raises:
        DataError: Na primeira linha cujo valor não está em `registered_names`.
    """
    for pos, value in enumerate(df_session[column]):
        if str(value).strip() not in registered_names:
            raise DataError(
                f"{display_path(file_path)}, linha {pos + 2}: coluna '{column}' com valor "
                f"'{value}' (esperado {expected})."
            )


if __name__ == "__main__":
    print("\nCadastro de pilotos:")
    print(load_registered_drivers().to_string(index=False))
    print("\nCadastro de equipes:")
    print(load_registered_teams().to_string(index=False))
    print("\nCadastro de Sessões:")
    print(load_registered_sessions().to_string(index=False))
