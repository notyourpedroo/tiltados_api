#!/usr/bin/env python3
"""
Calcular o status da Superlicença de uma temporada por Sessão.

Este módulo calcula o saldo de pontos da Superlicença para cada piloto da temporada:
- Todos os pilotos iniciam cada temporada com 12 pontos.
- Cada infração da temporada registrada em punishments.csv deduz pontos da Superlicença;
  as punições de outras temporadas não contam.
- Gera o saldo restante e o status disciplinar do piloto.
- Decide quem tem Suspensão a cumprir: é o mesmo cálculo que a Chance de título usa.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .load_drivers import load_drivers
    from .load_teams import load_teams
    from .load_punishments import load_punishments
    from .load_races import load_races
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from load_drivers import load_drivers
    from load_teams import load_teams
    from load_punishments import load_punishments
    from load_races import load_races

INITIAL_SUPER_LICENSE_POINTS = 12

SUSPENDED = "Suspenso"
SUSPENSION_SERVED = "Suspensao cumprida"


def _get_license_status(remaining_points, suspension_pending):
    """Retorna o status disciplinar do piloto com base nos pontos restantes e na Suspensão a cumprir."""
    if remaining_points <= 0:
        return SUSPENDED if suspension_pending else SUSPENSION_SERVED
    if remaining_points <= 4:
        return "Alerta Critico"
    if remaining_points <= 8:
        return "Atencao"
    return "Regular"


def _pending_suspensions(driver_ids, df_races, df_punishments, initial_points):
    """
    Indica, para cada piloto, se ele tem Suspensão a cumprir na próxima Corrida.

    A Suspensão vem da última punição que deixou a Superlicença zerada (ou abaixo de zero)
    e está cumprida se houve alguma Corrida disputada depois da Sessão dessa punição.
    """
    session_order = {race_id: i for i, race_id in enumerate(df_races["race_id"])}
    race_orders = [i for i, is_sprint in enumerate(df_races["is_sprint"]) if not is_sprint]

    punishments = df_punishments.assign(order=df_punishments["race_id"].map(session_order))
    punishments = punishments.sort_values("order", kind="stable")

    pending = []
    for driver_id in driver_ids:
        driver_punishments = punishments[punishments["driver_id"] == driver_id]
        remaining = initial_points
        zeroed_at = None
        for deduction, order in zip(driver_punishments["deduction_points"], driver_punishments["order"]):
            remaining -= deduction
            if remaining <= 0:
                zeroed_at = order
        pending.append(zeroed_at is not None and not any(order > zeroed_at for order in race_orders))
    return pending


def calculate_super_license(
    initial_points=INITIAL_SUPER_LICENSE_POINTS,
    base_path_sl="./files/super_license",
    base_path="./files/2026",
    season_year=2026,
):
    """
    Calcula a tabela de pontos da Superlicença de uma temporada por Sessão.

    Colunas do DataFrame retornado:
    - driver_id: ID único do piloto
    - driver_name: Nome do piloto
    - team_id: ID da equipe
    - team_name: Nome da equipe
    - initial_points: Pontuação inicial de superlicença (padrão: 12)
    - deducted_points: Total de pontos deduzidos por penalidades
    - remaining_points: Pontos restantes na superlicença
    - punishments_count: Quantidade de punições recebidas
    - status: Status disciplinar (Regular, Atencao, Alerta Critico, Suspenso, Suspensao cumprida).
      `Suspenso` é a Suspensão a cumprir; `Suspensao cumprida`, o saldo zerado depois de uma
      Corrida disputada após a punição que zerou a Superlicença.

    Args:
        initial_points (int): Pontos concedidos a cada piloto no início da temporada.
        base_path_sl (str): Caminho para a pasta de punições da superlicença.
        base_path (str): Caminho para a pasta da temporada (ex.: './files/2027').
                         Padrão: './files/2026'
        season_year (int): Ano da temporada; só as punições com esse season_year contam.

    Returns:
        pd.DataFrame: Tabela de controle da Superlicença.

    Raises:
        DataError: Se os dados da temporada ou o arquivo de punições forem inválidos, ou se
                   uma punição da temporada apontar para piloto ou Sessão não disputada nela.
    """
    df_drivers = load_drivers(base_path=base_path)
    df_teams = load_teams(base_path=base_path)
    df_races = load_races(base_path=base_path)
    df_punishments = load_punishments(
        base_path=base_path_sl, season_year=season_year, enriched=True, season_path=base_path,
    )

    # 1. Totalizar deduções por piloto
    if not df_punishments.empty:
        deductions = df_punishments.groupby("driver_id").agg(
            deducted_points=("deduction_points", "sum"),
            punishments_count=("deduction_points", "count")
        ).reset_index()
    else:
        deductions = pd.DataFrame(columns=["driver_id", "deducted_points", "punishments_count"])

    # 2. Cruzar com a lista completa de pilotos da temporada
    df_sl = df_drivers.merge(deductions, on="driver_id", how="left")
    df_sl["deducted_points"] = df_sl["deducted_points"].fillna(0).astype(int)
    df_sl["punishments_count"] = df_sl["punishments_count"].fillna(0).astype(int)
    df_sl["initial_points"] = int(initial_points)
    df_sl["remaining_points"] = df_sl["initial_points"] - df_sl["deducted_points"]

    # 3. Vincular dados de equipe
    df_sl = df_sl.merge(df_teams[["team_id", "team_name"]], on="team_id", how="left")

    # 4. Determinar status disciplinar, separando a Suspensão a cumprir da cumprida
    suspension_pending = _pending_suspensions(df_sl["driver_id"], df_races, df_punishments, int(initial_points))
    df_sl["status"] = [
        _get_license_status(remaining, pending)
        for remaining, pending in zip(df_sl["remaining_points"], suspension_pending)
    ]

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


# Alias para retrocompatibilidade
calculate_2026_super_license = calculate_super_license


if __name__ == "__main__":
    sl_df = calculate_super_license()

    if sl_df is not None:
        print("\n=== CONTROLE DA SUPERLICENCA - TEMPORADA 2026 ===")
        print(sl_df.to_string(index=False))
    else:
        print("⚠️ Erro ao calcular os dados da Superlicença.")
