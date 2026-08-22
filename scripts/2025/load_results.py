#!/usr/bin/env python3
"""
Retornar o DataFrame dos resultados de 2025.

Este módulo lê o arquivo CSV dos resultados (results.csv) e retorna um DataFrame simples com os dados brutos.
"""

import os
import pandas as pd


def load_results(base_path="./files/2025"):
    """
    Lê o arquivo results.csv do ano 2025 e retorna um DataFrame.

    O arquivo contém resultados de corrida virtuais com os seguintes campos:
    - race_id: ID da corrida
    - driver_id: ID do piloto que participou
    - team_id: ID da equipe do piloto
    - driver_start_position: Posição de partida do piloto na grid
    - driver_final_position: Posição final do piloto no resultado
    - grid_result: Resultado da classificação de grid (-1 para DNF, 0-2 para podiums)
    - driver_fastest_lap: Tempo da volta mais rápida (formato MM:SS.mmm ou '9:99.999' se DNF)

    Args:
        base_path (str): Caminho para a diretória dos dados de 2025.
                         Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com os resultados das corridas de 2025.
                      Retorna None se houver erro ao ler o arquivo.

    Raises:
        FileNotFoundError: Se a diretória base não existir.
        pd.errors.EmptyDataError: Se o arquivo estiver vazio.
    """
    results_file = f"{base_path}/results.csv"

    if not os.path.exists(results_file):
        raise FileNotFoundError(
            f"Arquivo de resultados não encontrado em: {results_file}"
        )

    try:
        df_results = pd.read_csv(results_file)

        df_results["race_id"] = df_results["race_id"].astype(int)
        df_results["driver_id"] = df_results["driver_id"].astype(int)
        df_results["team_id"] = df_results["team_id"].astype(int)

        df_results["driver_start_position"] = df_results["driver_start_position"].astype(int)
        df_results["driver_final_position"] = df_results["driver_final_position"].astype(int)
        df_results["grid_result"] = df_results["grid_result"].astype(int)

        return df_results

    except Exception as e:
        print(f"Erro ao ler {results_file}: {e}")
        return None


# Alias para retrocompatibilidade
load_2025_results = load_results


if __name__ == "__main__":
    results_df = load_results()

    if results_df is not None:
        print("\nDataFrame de resultados de 2025:")
        print(results_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados.")
