#!/usr/bin/env python3
"""
Retornar o DataFrame das corridas de 2026.

Este módulo extrai as corridas e sprints de 2026 a partir dos arquivos de
resultados, com o race_id, o nome do GP e a cidade vindos do Cadastro de
Sessões (files/sessions.csv), o mesmo em todas as temporadas por Sessão.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .common import list_sessions
    from .load_registry import load_registered_sessions
    from ..errors import DataError, display_path, require_dir
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from common import list_sessions
    from load_registry import load_registered_sessions
    from errors import DataError, display_path, require_dir


def load_races(base_path="./files/2026", base_path_2025="./files/2025", registry_path=None):
    """
    Lê os arquivos de resultados de 2026 e gera o DataFrame de corridas,
    com o race_id, o nome e a cidade de cada Sessão vindos do Cadastro.

    Gera um DataFrame, em ordem cronológica, com as seguintes colunas:
    - race_id: ID da Sessão no Cadastro (o mesmo em todas as temporadas)
    - race_name: Nome do GP no Cadastro; na Sprint, com o sufixo (ex: 'GP da China (SPRINT)')
    - race_date: Data da corrida (formato YYYY-MM-DD), a do nome do arquivo
    - race_location: Cidade da Etapa no Cadastro
    - is_sprint: Indica se é uma corrida sprint (True/False)

    Args:
        base_path (str): Caminho para a pasta dos dados de 2026.
                         Padrão: './files/2026'
        base_path_2025 (str): Não é mais usado (os IDs vêm do Cadastro). Fica na
                              assinatura porque os chamadores passam os mesmos
                              caminhos a todos os loaders de 2026.
        registry_path (str): Pasta do Cadastro. Padrão: a pasta acima de `base_path`.

    Returns:
        pd.DataFrame: DataFrame com as corridas de 2026.

    Raises:
        DataError: Se a pasta de 2026 não existir, não houver sessões, o Cadastro de
                   Sessões for inválido ou o local e o tipo no nome de um arquivo de
                   sessão não estiverem no Cadastro.
    """
    require_dir(base_path)
    if registry_path is None:
        registry_path = os.path.dirname(os.path.normpath(base_path))

    df_registered = load_registered_sessions(registry_path)
    registered = {
        (local, bool(sprint)): (int(rid), name, location)
        for rid, local, sprint, name, location in zip(
            df_registered["race_id"], df_registered["local"], df_registered["is_sprint"],
            df_registered["race_name"], df_registered["race_location"],
        )
    }

    # Sessões de 2026, já em ordem cronológica
    sessions = list_sessions(base_path)
    if not sessions:
        raise DataError(
            f"Nenhuma sessão encontrada em {display_path(base_path)} "
            "(nome esperado: {local}_{race|sprint}_{YYYYMMDD}.csv)."
        )

    parsed_races = []
    for session in sessions:
        key = (session["local"], session["is_sprint"])
        if key not in registered:
            raise DataError(
                f"{display_path(session['file_path'])}: local '{session['local']}' com tipo "
                f"'{'sprint' if session['is_sprint'] else 'race'}' no nome do arquivo "
                "(esperado uma Sessão do Cadastro)."
            )
        race_id, gp_name, location = registered[key]

        parsed_races.append({
            "race_id": race_id,
            "race_name": f"{gp_name} (SPRINT)" if session["is_sprint"] else gp_name,
            "race_date": session["race_date"],
            "race_location": location,
            "is_sprint": session["is_sprint"],
        })

    df_races = pd.DataFrame(parsed_races)
    df_races["race_id"] = df_races["race_id"].astype(int)
    df_races["is_sprint"] = df_races["is_sprint"].astype(bool)

    return df_races


# Alias para retrocompatibilidade
load_2026_races = load_races


if __name__ == "__main__":
    races_df = load_races()

    if races_df is not None:
        print("\nDataFrame de corridas de 2026 (IDs do Cadastro):")
        print(races_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de corridas de 2026.")
