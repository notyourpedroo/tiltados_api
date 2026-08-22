#!/usr/bin/env python3
"""
Retornar o DataFrame das corridas de 2025.

Este módulo lê o arquivo CSV das corridas (races.csv) e retorna um DataFrame simples com os dados brutos.
"""

import os
import pandas as pd


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
                      Retorna None se houver erro ao ler o arquivo.

    Raises:
        FileNotFoundError: Se a diretória base não existir.
        pd.errors.EmptyDataError: Se o arquivo estiver vazio.
    """
    races_file = f"{base_path}/races.csv"

    if not os.path.exists(races_file):
        raise FileNotFoundError(
            f"Arquivo de corridas não encontrado em: {races_file}"
        )

    try:
        df_races = pd.read_csv(races_file)
        df_races["race_id"] = df_races["race_id"].astype(int)

        return df_races

    except Exception as e:
        print(f"Erro ao ler {races_file}: {e}")
        return None


# Alias para retrocompatibilidade
load_2025_races = load_races


if __name__ == "__main__":
    races_df = load_races()

    if races_df is not None:
        print("\nDataFrame de corridas de 2025:")
        print(races_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados.")
