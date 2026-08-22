#!/usr/bin/env python3
"""
Retornar o DataFrame das punições da Superlicença de 2026.

Este módulo lê o arquivo de punições (punishments.csv) da Superlicença e
filtra/estrutura as penalidades aplicadas na temporada de 2026.
"""

import os
import sys
import pandas as pd


def load_punishments(base_path="./files/super_license", season_year=2026, enriched=False):
    """
    Lê o arquivo punishments.csv e retorna as punições registradas para a temporada de 2026.

    Campos padrão retornados:
    - season_year: Ano da temporada (2026)
    - driver_id: ID único do piloto penalizado
    - race_id: ID canônico da corrida onde ocorreu a infração
    - deduction_points: Quantidade de pontos deduzidos na Superlicença
    - penalty_reason: Descrição/motivo da penalidade

    Args:
        base_path (str): Caminho para a pasta dos dados da superlicença.
                         Padrão: './files/super_license'
        season_year (int): Ano da temporada a ser filtrada. Padrão: 2026.
        enriched (bool): Se True, inclui driver_name, team_id, race_name e race_date.

    Returns:
        pd.DataFrame: DataFrame com as punições da temporada.
                      Retorna None se houver erro ao carregar os dados.

    Raises:
        FileNotFoundError: Se o arquivo de punições não existir.
    """
    punishments_file = os.path.join(base_path, "punishments.csv")

    if not os.path.exists(punishments_file):
        raise FileNotFoundError(
            f"Arquivo de punições não encontrado em: {punishments_file}"
        )

    try:
        df_punishments = pd.read_csv(punishments_file)

        df_punishments["season_year"] = df_punishments["season_year"].astype(int)
        df_punishments["driver_id"] = df_punishments["driver_id"].astype(int)
        df_punishments["race_id"] = df_punishments["race_id"].astype(int)
        df_punishments["deduction_points"] = df_punishments["deduction_points"].astype(int)
        df_punishments["penalty_reason"] = df_punishments["penalty_reason"].astype(str)

        # Filtrar pelo ano especificado
        df_filtered = df_punishments[df_punishments["season_year"] == int(season_year)].copy()

        if enriched:
            try:
                # Suporta tanto importação relativa de pacote quanto execução direta
                try:
                    from .load_drivers import load_drivers
                    from .load_races import load_races
                except (ImportError, ValueError):
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    if current_dir not in sys.path:
                        sys.path.insert(0, current_dir)
                    from load_drivers import load_drivers
                    from load_races import load_races

                df_drivers = load_drivers()
                df_races = load_races()

                if df_drivers is not None:
                    df_filtered = df_filtered.merge(
                        df_drivers[["driver_id", "driver_name", "team_id"]],
                        on="driver_id",
                        how="left"
                    )

                if df_races is not None:
                    df_filtered = df_filtered.merge(
                        df_races[["race_id", "race_name", "race_date"]],
                        on="race_id",
                        how="left"
                    )
            except Exception as enrich_err:
                print(f"Aviso: Não foi possível enriquecer os dados: {enrich_err}")

        return df_filtered.reset_index(drop=True)

    except Exception as e:
        print(f"Erro ao ler {punishments_file}: {e}")
        return None


# Alias para retrocompatibilidade
load_2026_punishments = load_punishments


if __name__ == "__main__":
    punishments_df = load_punishments(enriched=True)

    if punishments_df is not None:
        print("\n=== PUNIÇÕES DA SUPERLICENÇA - TEMPORADA 2026 ===")
        print(punishments_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de punições de 2026.")
