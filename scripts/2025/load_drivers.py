#!/usr/bin/env python3
"""
Retornar o DataFrame dos pilotos de 2025.

Este módulo lê o arquivo CSV dos pilotos (drivers.csv) e retorna um DataFrame com os dados brutos.
"""

import os
import pandas as pd


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
                      Retorna None se houver erro ao ler o arquivo.

    Raises:
        FileNotFoundError: Se a diretória base não existir.
        pd.errors.EmptyDataError: Se o arquivo estiver vazio.
    """
    drivers_file = f"{base_path}/drivers.csv"

    if not os.path.exists(drivers_file):
        raise FileNotFoundError(
            f"Arquivo de pilotos não encontrado em: {drivers_file}"
        )

    try:
        df_drivers = pd.read_csv(drivers_file)
        df_drivers["driver_id"] = df_drivers["driver_id"].astype(int)
        df_drivers["team_id"] = df_drivers["team_id"].astype(int)

        return df_drivers

    except Exception as e:
        print(f"Erro ao ler {drivers_file}: {e}")
        return None


# Alias para retrocompatibilidade
load_2025_drivers = load_drivers


if __name__ == "__main__":
    drivers_df = load_drivers()

    if drivers_df is not None:
        print("\nDataFrame de pilotos de 2025:")
        print(drivers_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados.")
