#!/usr/bin/env python3
"""
Retornar o DataFrame dos pilotos de 2026.

Este módulo extrai os pilotos participantes a partir dos arquivos de resultados
de 2026, associando os IDs das equipes e mantendo a consistência de IDs entre temporadas.
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


def _is_placeholder_driver(value):
    """Indica se o nome do piloto está vazio ou é o placeholder 'Pessoa' do export."""
    if pd.isna(value):
        return True
    name = str(value).strip()
    return not name or name.lower() == "pessoa"


def load_drivers(base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Lê os arquivos de resultados de 2026 e extrai os pilotos participantes.

    Gera um DataFrame com as seguintes colunas:
    - driver_id: ID único do piloto (mantém consistência com histórico de 2025)
    - team_id: ID da equipe correspondente (mantém consistência com histórico de 2025)
    - driver_name: Nome do piloto

    Args:
        base_path (str): Caminho para a pasta dos dados de 2026.
                         Padrão: './files/2026'
        base_path_2025 (str): Caminho para a pasta dos dados de 2025.
                              Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com os pilotos de 2026 (driver_id, team_id, driver_name).
                      Retorna None se houver erro ao ler os dados.

    Raises:
        FileNotFoundError: Se o diretório base de 2026 não existir.
    """
    if not os.path.exists(base_path):
        raise FileNotFoundError(
            f"Diretório de 2026 não encontrado em: {base_path}"
        )

    try:
        # 1. Carregar mapeamento de IDs de pilotos existentes (2025)
        driver_id_map = {}
        drivers_2025_file = os.path.join(base_path_2025, "drivers.csv")
        if os.path.exists(drivers_2025_file):
            df_2025_drivers = pd.read_csv(drivers_2025_file)
            driver_id_map = dict(zip(df_2025_drivers["driver_name"], df_2025_drivers["driver_id"]))

        max_driver_id = max(driver_id_map.values()) if driver_id_map else 0

        # 2. Carregar mapeamento de IDs de equipes existentes (2025)
        team_id_map = {}
        norm_team_to_id = {}
        teams_2025_file = os.path.join(base_path_2025, "teams.csv")
        if os.path.exists(teams_2025_file):
            df_2025_teams = pd.read_csv(teams_2025_file)
            for _, row in df_2025_teams.iterrows():
                tid = int(row["team_id"])
                tname = str(row["team_name"]).strip()
                team_id_map[tname] = tid
                norm_team_to_id[_normalize_team_name(tname)] = tid

        max_team_id = max(team_id_map.values()) if team_id_map else 0

        # 3. Extrair equipes e pilotos de 2026 a partir dos CSVs
        csv_files = glob.glob(os.path.join(base_path, "*.csv"))
        driver_team_map = {}
        teams_found = set()

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
            if "Piloto" in df_temp.columns and "Equipe" in df_temp.columns:
                for i, row in df_temp.iterrows():
                    if _is_placeholder_driver(row.get("Piloto")):
                        raise ValueError(
                            f"Piloto não identificado em {os.path.basename(file_path)}, "
                            f"linha {i + 2}: '{row.get('Piloto')}'. Corrija o nome do piloto no CSV."
                        )

                    driver_name = str(row.get("Piloto", "")).strip()
                    team_name = str(row.get("Equipe", "")).strip()

                    if team_name:
                        teams_found.add(team_name)
                        driver_team_map[driver_name] = team_name

        if not driver_team_map:
            print("Nenhum piloto encontrado nos arquivos de 2026.")
            return None

        # 4. Resolver team_id para cada equipe encontrada
        for team_name in sorted(list(teams_found)):
            norm = _normalize_team_name(team_name)
            if team_name in team_id_map:
                continue
            elif norm in norm_team_to_id:
                team_id_map[team_name] = norm_team_to_id[norm]
            else:
                max_team_id += 1
                team_id_map[team_name] = max_team_id
                norm_team_to_id[norm] = max_team_id

        # 5. Construir o DataFrame de pilotos
        rows = []
        for driver_name in sorted(driver_team_map.keys()):
            if driver_name not in driver_id_map:
                max_driver_id += 1
                driver_id_map[driver_name] = max_driver_id

            team_name = driver_team_map[driver_name]
            tid = team_id_map.get(team_name)
            if tid is None:
                norm = _normalize_team_name(team_name)
                tid = norm_team_to_id.get(norm)

            rows.append({
                "driver_id": int(driver_id_map[driver_name]),
                "team_id": int(tid),
                "driver_name": driver_name
            })

        df_drivers = pd.DataFrame(rows)
        df_drivers = df_drivers.sort_values("driver_id").reset_index(drop=True)
        df_drivers["driver_id"] = df_drivers["driver_id"].astype(int)
        df_drivers["team_id"] = df_drivers["team_id"].astype(int)

        return df_drivers

    except ValueError:
        raise
    except Exception as e:
        print(f"Erro ao extrair pilotos de 2026 em {base_path}: {e}")
        return None


# Alias para retrocompatibilidade
load_2026_drivers = load_drivers


if __name__ == "__main__":
    drivers_df = load_drivers()

    if drivers_df is not None:
        print("\nDataFrame bruto de pilotos de 2026:")
        print(drivers_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de pilotos de 2026.")
