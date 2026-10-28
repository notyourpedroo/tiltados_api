#!/usr/bin/env python3
"""
Retornar o DataFrame das equipes de 2026.

Este módulo extrai as equipes participantes a partir dos arquivos de resultados
de 2026 e retorna um DataFrame com team_id e team_name, ambos vindos do Cadastro.
"""

import os
import sys

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .common import list_sessions, read_session_results
    from .load_registry import load_registered_teams, require_registered
    from ..errors import require_dir
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for path in (current_dir, os.path.dirname(current_dir)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from common import list_sessions, read_session_results
    from load_registry import load_registered_teams, require_registered
    from errors import require_dir


def load_teams(base_path="./files/2026", base_path_2025="./files/2025", registry_path=None):
    """
    Lê os arquivos de resultados de uma temporada por Sessão (2026 em diante) e
    extrai as equipes participantes.

    Gera um DataFrame com as seguintes colunas (vazio se a temporada ainda não tem
    Sessão disputada):
    - team_id: ID da equipe no Cadastro (o mesmo em todas as temporadas)
    - team_name: Nome da equipe no Cadastro

    Args:
        base_path (str): Caminho para a pasta da temporada (ex.: './files/2027').
                         Padrão: './files/2026'
        base_path_2025 (str): Não é mais usado (os IDs vêm do Cadastro). Fica na
                              assinatura porque os chamadores passam os mesmos
                              caminhos a todos os loaders de 2026.
        registry_path (str): Pasta do Cadastro. Padrão: a pasta acima de `base_path`.

    Returns:
        pd.DataFrame: DataFrame com as equipes da temporada (team_id, team_name).

    Raises:
        DataError: Se a pasta da temporada não existir, algum CSV de sessão for
                   inválido, alguma equipe não estiver no Cadastro ou o Cadastro
                   for inválido.
    """
    require_dir(base_path)
    if registry_path is None:
        registry_path = os.path.dirname(os.path.normpath(base_path))

    df_registered = load_registered_teams(registry_path)
    registered_names = set(df_registered["team_name"])

    # Equipes presentes nos arquivos de 2026, conferidas contra o Cadastro
    teams_found = set()
    for session in list_sessions(base_path):
        df_session = read_session_results(session["file_path"])
        if df_session is None:
            continue
        require_registered(df_session, "Equipe", registered_names, "uma equipe do Cadastro", session["file_path"])
        teams_found.update(df_session["Equipe"].astype(str).str.strip())

    df_teams = df_registered[df_registered["team_name"].isin(teams_found)]
    df_teams = df_teams.sort_values("team_id").reset_index(drop=True)
    df_teams["team_id"] = df_teams["team_id"].astype(int)

    return df_teams


# Alias para retrocompatibilidade
load_2026_teams = load_teams


if __name__ == "__main__":
    teams_df = load_teams()

    if teams_df is not None:
        print("\nDataFrame de equipes de 2026:")
        print(teams_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de equipes de 2026.")
