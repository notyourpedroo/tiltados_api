#!/usr/bin/env python3
"""
Calcular o status da Superlicença de 2026.

Este módulo calcula o saldo de pontos da Superlicença para cada piloto de 2026:
- Todos os pilotos iniciam com 12 pontos.
- Cada infração registrada em punishments.csv deduz pontos da carteira.
- Gera o saldo restante e o status disciplinar do piloto.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .load_drivers import load_drivers
    from .load_teams import load_teams
    from .load_punishments import load_punishments
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from load_drivers import load_drivers
    from load_teams import load_teams
    from load_punishments import load_punishments

INITIAL_SUPER_LICENSE_POINTS = 12


def _get_license_status(remaining_points):
    """Retorna o status disciplinar do piloto com base nos pontos restantes."""
    if remaining_points <= 0:
        return "Suspenso (Ban)"
    if remaining_points <= 4:
        return "Alerta Critico"
    if remaining_points <= 8:
        return "Atencao"
    return "Regular"


def calculate_super_license(
    initial_points=INITIAL_SUPER_LICENSE_POINTS,
    base_path_sl="./files/super_license",
    base_path_2026="./files/2026",
    base_path_2025="./files/2025"
):
    """
    Calcula a tabela de pontos da Superlicença para a temporada de 2026.

    Colunas do DataFrame retornado:
    - driver_id: ID único do piloto
    - driver_name: Nome do piloto
    - team_id: ID da equipe
    - team_name: Nome da equipe
    - initial_points: Pontuação inicial de superlicença (padrão: 12)
    - deducted_points: Total de pontos deduzidos por penalidades
    - remaining_points: Pontos restantes na superlicença
    - punishments_count: Quantidade de punições recebidas
    - status: Status disciplinar (Regular, Atencao, Alerta Critico, Suspenso)

    Args:
        initial_points (int): Pontos concedidos a cada piloto no início da temporada.
        base_path_sl (str): Caminho para a pasta de punições da superlicença.
        base_path_2026 (str): Caminho para os dados de 2026.
        base_path_2025 (str): Caminho para os dados de 2025.

    Returns:
        pd.DataFrame: Tabela de controle da Superlicença.
    """
    try:
        df_drivers = load_drivers(base_path=base_path_2026, base_path_2025=base_path_2025)
        df_teams = load_teams(base_path=base_path_2026, base_path_2025=base_path_2025)
        df_punishments = load_punishments(base_path=base_path_sl, season_year=2026)

        if df_drivers is None:
            return None

        # 1. Totalizar deduções por piloto
        if df_punishments is not None and not df_punishments.empty:
            deductions = df_punishments.groupby("driver_id").agg(
                deducted_points=("deduction_points", "sum"),
                punishments_count=("deduction_points", "count")
            ).reset_index()
        else:
            deductions = pd.DataFrame(columns=["driver_id", "deducted_points", "punishments_count"])

        # 2. Cruzar com a lista completa de pilotos de 2026
        df_sl = df_drivers.merge(deductions, on="driver_id", how="left")
        df_sl["deducted_points"] = df_sl["deducted_points"].fillna(0).astype(int)
        df_sl["punishments_count"] = df_sl["punishments_count"].fillna(0).astype(int)
        df_sl["initial_points"] = int(initial_points)
        df_sl["remaining_points"] = df_sl["initial_points"] - df_sl["deducted_points"]

        # 3. Vincular dados de equipe
        if df_teams is not None:
            df_sl = df_sl.merge(df_teams[["team_id", "team_name"]], on="team_id", how="left")
        else:
            df_sl["team_name"] = "N/A"

        # 4. Determinar status disciplinar
        df_sl["status"] = df_sl["remaining_points"].apply(_get_license_status)

        # 5. Ordenar por pilotos mais penalizados primeiro, depois por ID
        df_sl = df_sl.sort_values(
            by=["remaining_points", "deducted_points", "driver_id"],
            ascending=[True, False, True]
        ).reset_index(drop=True)

        cols = [
            "driver_id", "driver_name", "team_id", "team_name",
            "initial_points", "deducted_points", "remaining_points",
            "punishments_count", "status"
        ]
        return df_sl[cols]

    except Exception as e:
        print(f"Erro ao calcular a Superlicenca de 2026: {e}")
        return None


# Alias para retrocompatibilidade
calculate_2026_super_license = calculate_super_license


if __name__ == "__main__":
    sl_df = calculate_super_license()

    if sl_df is not None:
        print("\n=== CONTROLE DA SUPERLICENCA - TEMPORADA 2026 ===")
        print(sl_df.to_string(index=False))
    else:
        print("⚠️ Erro ao calcular os dados da Superlicença.")
