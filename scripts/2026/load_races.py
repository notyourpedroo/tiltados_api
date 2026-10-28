#!/usr/bin/env python3
"""
Retornar o DataFrame das Sessões de uma temporada por Sessão.

Este módulo extrai as corridas e sprints da temporada a partir dos arquivos de
resultados, com o race_id, o nome do GP e a cidade vindos do Cadastro de
Sessões (files/sessions.csv), o mesmo em todas as temporadas por Sessão.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .common import list_sessions
    from .load_registry import SESSION_TYPE_NAMES, load_registered_sessions, registry_dir
    from ..errors import DataError, display_path, require_dir
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from common import list_sessions
    from load_registry import SESSION_TYPE_NAMES, load_registered_sessions, registry_dir
    from errors import DataError, display_path, require_dir


RACE_COLUMNS = ["race_id", "race_name", "race_date", "race_location", "is_sprint"]


def load_races(base_path="./files/2026"):
    """
    Lê os arquivos de resultados de uma temporada por Sessão (2026 em diante) e gera
    o DataFrame de corridas, com o race_id, o nome e a cidade de cada Sessão vindos do Cadastro.

    Gera um DataFrame, em ordem cronológica, com as seguintes colunas (vazio se a
    temporada ainda não tem Sessão disputada):
    - race_id: ID da Sessão no Cadastro (o mesmo em todas as temporadas)
    - race_name: Nome do GP no Cadastro; na Sprint, com o sufixo (ex: 'GP da China (SPRINT)')
    - race_date: Data da corrida (formato YYYY-MM-DD), a do nome do arquivo
    - race_location: Cidade da Etapa no Cadastro
    - is_sprint: Indica se é uma corrida sprint (True/False)

    Args:
        base_path (str): Caminho para a pasta da temporada (ex.: './files/2027').
                         Padrão: './files/2026'

    Returns:
        pd.DataFrame: DataFrame com as corridas da temporada.

    Raises:
        DataError: Se a pasta da temporada não existir, o Cadastro de Sessões for
                   inválido ou o local e o tipo no nome de um arquivo de sessão não
                   estiverem no Cadastro.
    """
    require_dir(base_path)

    df_registered = load_registered_sessions(registry_dir(base_path))
    registered = {
        (local, bool(sprint)): (int(rid), name, location)
        for rid, local, sprint, name, location in zip(
            df_registered["race_id"], df_registered["local"], df_registered["is_sprint"],
            df_registered["race_name"], df_registered["race_location"],
        )
    }

    # Sessões disputadas da temporada, já em ordem cronológica (nenhuma no início da temporada)
    parsed_races = []
    for session in list_sessions(base_path):
        key = (session["local"], session["is_sprint"])
        if key not in registered:
            raise DataError(
                f"{display_path(session['file_path'])}: local '{session['local']}' com tipo "
                f"'{SESSION_TYPE_NAMES[session['is_sprint']]}' no nome do arquivo "
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

    df_races = pd.DataFrame(parsed_races, columns=RACE_COLUMNS)
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
