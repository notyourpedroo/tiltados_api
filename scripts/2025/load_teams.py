#!/usr/bin/env python3
"""
Retornar o DataFrame das equipes de 2025.

Este módulo lê o arquivo CSV das equipes (teams.csv) e retorna um DataFrame simples com os dados brutos.
"""

import os
import pandas as pd


def load_teams(base_path="./files/2025"):
    """
    Lê o arquivo teams.csv do ano 2025 e retorna um DataFrame.

    O arquivo contém equipes virtuais com os seguintes campos:
    - team_id: ID único da equipe
    - team_name: Nome da equipe

    Args:
        base_path (str): Caminho para a diretória dos dados de 2025.
                         Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com os dados das equipes de 2025.
                      Retorna None se houver erro ao ler o arquivo.

    Raises:
        FileNotFoundError: Se a diretória base não existir.
        pd.errors.EmptyDataError: Se o arquivo estiver vazio.
    """
    teams_file = f"{base_path}/teams.csv"

    if not os.path.exists(teams_file):
        raise FileNotFoundError(
            f"Arquivo de equipes não encontrado em: {teams_file}"
        )

    try:
        df_teams = pd.read_csv(teams_file)
        df_teams["team_id"] = df_teams["team_id"].astype(int)

        return df_teams

    except Exception as e:
        print(f"Erro ao ler {teams_file}: {e}")
        return None


# Alias para retrocompatibilidade
load_2025_teams = load_teams


if __name__ == "__main__":
    teams_df = load_teams()

    if teams_df is not None:
        print("\nDataFrame de equipes de 2025:")
        print(teams_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados.")
