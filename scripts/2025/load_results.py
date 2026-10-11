#!/usr/bin/env python3
"""
Retornar o DataFrame dos resultados de 2025.

Este módulo lê o arquivo CSV dos resultados (results.csv) e retorna um DataFrame simples com os dados brutos.
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

    Raises:
        DataError: Se o arquivo não existir, faltar coluna obrigatória ou houver ID inválido.
    """
    results_file = f"{base_path}/results.csv"

    df_results = read_csv(results_file)
    require_columns(df_results, [
        "race_id", "driver_id", "team_id", "driver_start_position",
        "driver_final_position", "grid_result", "driver_fastest_lap"
    ], results_file)
    df_results["race_id"] = to_int_column(df_results, "race_id", results_file)
    df_results["driver_id"] = to_int_column(df_results, "driver_id", results_file)
    df_results["team_id"] = to_int_column(df_results, "team_id", results_file)
    df_results["driver_start_position"] = to_int_column(df_results, "driver_start_position", results_file)
    df_results["driver_final_position"] = to_int_column(df_results, "driver_final_position", results_file)
    df_results["grid_result"] = to_int_column(df_results, "grid_result", results_file)

    return df_results


# Alias para retrocompatibilidade
load_2025_results = load_results


if __name__ == "__main__":
    results_df = load_results()

    if results_df is not None:
        print("\nDataFrame de resultados de 2025:")
        print(results_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados.")
