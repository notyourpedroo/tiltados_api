#!/usr/bin/env python3
"""
Retornar o DataFrame das equipes de 2025.

Este módulo lê o arquivo CSV das equipes (teams.csv) e retorna um DataFrame simples com os dados brutos.
"""

import os
import sys

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from ..errors import read_csv, require_columns, to_int_column
except (ImportError, ValueError):
    scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from errors import read_csv, require_columns, to_int_column


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

    Raises:
        DataError: Se o arquivo não existir, faltar coluna obrigatória ou houver ID inválido.
    """
    teams_file = f"{base_path}/teams.csv"

    df_teams = read_csv(teams_file)
    require_columns(df_teams, ["team_id", "team_name"], teams_file)
    df_teams["team_id"] = to_int_column(df_teams, "team_id", teams_file)

    return df_teams


# Alias para retrocompatibilidade
load_2025_teams = load_teams


if __name__ == "__main__":
    teams_df = load_teams()

    if teams_df is not None:
        print("\nDataFrame de equipes de 2025:")
        print(teams_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados.")
