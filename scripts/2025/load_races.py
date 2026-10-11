#!/usr/bin/env python3
"""
Retornar o DataFrame das corridas de 2025.

Este módulo lê o arquivo CSV das corridas (races.csv) e retorna um DataFrame simples com os dados brutos.
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


def load_races(base_path="./files/2025"):
    """
    Lê o arquivo races.csv do ano 2025 e retorna um DataFrame.

    O arquivo contém corridas virtuais com os seguintes campos:
    - race_id: ID único da corrida
    - race_name: Nome da corrida
    - race_date: Data da corrida (formato YYYY-MM-DD)
    - race_location: Local da corrida
    - is_sprint: Indica se a corrida é um sprint (TRUE/FALSE)

    Args:
        base_path (str): Caminho para a diretória dos dados de 2025.
                         Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com os dados das corridas de 2025.

    Raises:
        DataError: Se o arquivo não existir, faltar coluna obrigatória ou houver ID inválido.
    """
    races_file = f"{base_path}/races.csv"

    df_races = read_csv(races_file)
    require_columns(df_races, ["race_id", "race_name", "race_date", "race_location", "is_sprint"], races_file)
    df_races["race_id"] = to_int_column(df_races, "race_id", races_file)

    return df_races


# Alias para retrocompatibilidade
load_2025_races = load_races


if __name__ == "__main__":
    races_df = load_races()

    if races_df is not None:
        print("\nDataFrame de corridas de 2025:")
        print(races_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados.")
