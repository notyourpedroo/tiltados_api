#!/usr/bin/env python3
"""
Retornar o DataFrame dos pilotos de 2025.

Este módulo lê o arquivo CSV dos pilotos (drivers.csv) e retorna um DataFrame com os dados brutos.
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


def load_drivers(base_path="./files/2025"):
    """
    Lê o arquivo drivers.csv do ano 2025 e retorna um DataFrame.

    O arquivo contém pilotos virtuais com os seguintes campos:
    - driver_id: ID único do piloto
    - team_id: ID da equipe ao qual o piloto pertence
    - driver_name: Nome do piloto

    Args:
        base_path (str): Caminho para a diretória dos dados de 2025.
                         Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com os dados dos pilotos de 2025.

    Raises:
        DataError: Se o arquivo não existir, faltar coluna obrigatória ou houver ID inválido.
    """
    drivers_file = f"{base_path}/drivers.csv"

    df_drivers = read_csv(drivers_file)
    require_columns(df_drivers, ["driver_id", "team_id", "driver_name"], drivers_file)
    df_drivers["driver_id"] = to_int_column(df_drivers, "driver_id", drivers_file)
    df_drivers["team_id"] = to_int_column(df_drivers, "team_id", drivers_file)

    return df_drivers


# Alias para retrocompatibilidade
load_2025_drivers = load_drivers


if __name__ == "__main__":
    drivers_df = load_drivers()

    if drivers_df is not None:
        print("\nDataFrame de pilotos de 2025:")
        print(drivers_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados.")
