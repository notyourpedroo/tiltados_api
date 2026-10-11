#!/usr/bin/env python3
"""
Retornar o DataFrame das punições da Superlicença de 2026.

Este módulo lê o arquivo de punições (punishments.csv) da Superlicença e
filtra/estrutura as penalidades aplicadas na temporada de 2026.
"""

import os
import sys

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from ..errors import DataError, display_path, read_csv, require_columns, to_int_column
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from errors import DataError, display_path, read_csv, require_columns, to_int_column


def load_punishments(
    base_path="./files/super_license",
    season_year=2026,
    enriched=False,
    base_path_2026="./files/2026",
    base_path_2025="./files/2025"
):
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
        enriched (bool): Se True, inclui driver_name, team_id, team_name, race_name e race_date,
                         e valida que cada punição aponta para um piloto e uma corrida de 2026.
        base_path_2026 (str): Caminho para os dados de 2026 (usado só com enriched=True).
        base_path_2025 (str): Caminho para os dados de 2025 (usado só com enriched=True).

    Returns:
        pd.DataFrame: DataFrame com as punições da temporada.

    Raises:
        DataError: Se o arquivo de punições não existir, faltar coluna obrigatória,
                   houver valor numérico inválido ou (com enriched=True) uma punição
                   apontar para piloto ou corrida inexistente.
    """
    punishments_file = os.path.join(base_path, "punishments.csv")

    df_punishments = read_csv(punishments_file)
    require_columns(df_punishments, [
        "season_year", "driver_id", "race_id", "deduction_points", "penalty_reason"
    ], punishments_file)

    for column in ("season_year", "driver_id", "race_id", "deduction_points"):
        df_punishments[column] = to_int_column(df_punishments, column, punishments_file)
    df_punishments["penalty_reason"] = df_punishments["penalty_reason"].astype(str)

    # Filtrar pelo ano especificado
    df_filtered = df_punishments[df_punishments["season_year"] == int(season_year)].copy()

    if enriched:
        # Suporta tanto importação relativa de pacote quanto execução direta
        try:
            from .load_drivers import load_drivers
            from .load_races import load_races
            from .load_teams import load_teams
        except (ImportError, ValueError):
            from load_drivers import load_drivers
            from load_races import load_races
            from load_teams import load_teams

        df_drivers = load_drivers(base_path=base_path_2026, base_path_2025=base_path_2025)
        df_teams = load_teams(base_path=base_path_2026, base_path_2025=base_path_2025)
        df_races = load_races(base_path=base_path_2026, base_path_2025=base_path_2025)

        # Toda punição precisa apontar para um piloto e uma corrida que existem na temporada
        for column, valid_ids, label in (
            ("driver_id", df_drivers["driver_id"], "nenhum piloto"),
            ("race_id", df_races["race_id"], "nenhuma corrida"),
        ):
            unknown = ~df_filtered[column].isin(valid_ids)
            if unknown.any():
                pos = int(unknown.to_numpy().argmax())
                raise DataError(
                    f"{display_path(punishments_file)}, linha {df_filtered.index[pos] + 2}: "
                    f"{column} {df_filtered[column].iloc[pos]} não corresponde a {label} de {season_year}."
                )

        df_filtered = df_filtered.merge(
            df_drivers[["driver_id", "driver_name", "team_id"]], on="driver_id", how="left"
        )
        df_filtered = df_filtered.merge(
            df_teams[["team_id", "team_name"]], on="team_id", how="left"
        )
        df_filtered = df_filtered.merge(
            df_races[["race_id", "race_name", "race_date"]], on="race_id", how="left"
        )

    return df_filtered.reset_index(drop=True)


# Alias para retrocompatibilidade
load_2026_punishments = load_punishments


if __name__ == "__main__":
    punishments_df = load_punishments(enriched=True)

    if punishments_df is not None:
        print("\n=== PUNIÇÕES DA SUPERLICENÇA - TEMPORADA 2026 ===")
        print(punishments_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de punições de 2026.")
