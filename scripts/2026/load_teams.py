#!/usr/bin/env python3
"""
Retornar o DataFrame das equipes de 2026.

Este módulo extrai as equipes participantes a partir dos arquivos de resultados
de 2026 e retorna um DataFrame com team_id e team_name, mantendo consistência de IDs
com as equipes de 2025.
"""

import glob
import io
import os
import pandas as pd


def _normalize_team_name(name):
    """Normaliza o nome da equipe para correspondência entre temporadas."""
    n = name.lower().strip()
    if "red bull" in n and "racing bulls" not in n:
        return "red bull"
    if "ferrari" in n:
        return "ferrari"
    if "mercedes" in n:
        return "mercedes"
    if "racing bulls" in n or "vcarb" in n:
        return "racing bulls"
    if "alpine" in n:
        return "alpine"
    if "mclaren" in n:
        return "mclaren"
    if "sauber" in n or "kick" in n:
        return "sauber"
    if "aston" in n:
        return "aston martin"
    if "williams" in n:
        return "williams"
    if "haas" in n:
        return "haas"
    return n


def load_teams(base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Lê os arquivos de resultados de 2026 e extrai as equipes participantes,
    preservando os IDs de 2025 para equipes existentes e atribuindo novos IDs para estreantes.

    Gera um DataFrame com as seguintes colunas:
    - team_id: ID único da equipe (compatível entre temporadas)
    - team_name: Nome da equipe em 2026

    Args:
        base_path (str): Caminho para a pasta dos dados de 2026.
                         Padrão: './files/2026'
        base_path_2025 (str): Caminho para a pasta dos dados de 2025.
                              Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com as equipes de 2026 (team_id, team_name).
                      Retorna None se houver erro ou nenhuma equipe encontrada.

    Raises:
        FileNotFoundError: Se o diretório base não existir.
    """
    if not os.path.exists(base_path):
        raise FileNotFoundError(
            f"Diretório de 2026 não encontrado em: {base_path}"
        )

    try:
        # 1. Carregar mapeamento de equipes de 2025 (se existir)
        team_id_map = {}
        norm_to_id = {}
        teams_2025_file = os.path.join(base_path_2025, "teams.csv")
        if os.path.exists(teams_2025_file):
            df_2025_teams = pd.read_csv(teams_2025_file)
            for _, row in df_2025_teams.iterrows():
                tid = int(row["team_id"])
                tname = str(row["team_name"]).strip()
                team_id_map[tname] = tid
                norm_to_id[_normalize_team_name(tname)] = tid

        max_team_id = max(team_id_map.values()) if team_id_map else 0

        # 2. Extrair equipes únicas presentes nos arquivos de 2026
        teams_found = set()
        csv_files = glob.glob(os.path.join(base_path, "*.csv"))

        for file_path in csv_files:
            if os.path.basename(file_path).startswith("scores"):
                continue

            lines = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip() or line.startswith(",,,,") or line.startswith("Tempo,"):
                        break
                    lines.append(line)

            if not lines:
                continue

            df_temp = pd.read_csv(io.StringIO("".join(lines)))
            if "Equipe" in df_temp.columns:
                for team in df_temp["Equipe"].dropna():
                    team_clean = str(team).strip()
                    if team_clean:
                        teams_found.add(team_clean)

        if not teams_found:
            print("Nenhuma equipe encontrada nos arquivos de 2026.")
            return None

        # 3. Mapear team_id mantendo consistência com 2025
        rows = []
        for team_name in sorted(list(teams_found)):
            norm = _normalize_team_name(team_name)
            if team_name in team_id_map:
                tid = team_id_map[team_name]
            elif norm in norm_to_id:
                tid = norm_to_id[norm]
            else:
                max_team_id += 1
                tid = max_team_id
                team_id_map[team_name] = tid
                norm_to_id[norm] = tid

            rows.append({
                "team_id": tid,
                "team_name": team_name
            })

        df_teams = pd.DataFrame(rows).sort_values("team_id").reset_index(drop=True)
        df_teams["team_id"] = df_teams["team_id"].astype(int)

        return df_teams

    except Exception as e:
        print(f"Erro ao extrair equipes de 2026 em {base_path}: {e}")
        return None


# Alias para retrocompatibilidade
load_2026_teams = load_teams


if __name__ == "__main__":
    teams_df = load_teams()

    if teams_df is not None:
        print("\nDataFrame de equipes de 2026:")
        print(teams_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de equipes de 2026.")
