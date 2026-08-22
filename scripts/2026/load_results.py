#!/usr/bin/env python3
"""
Retornar o DataFrame dos resultados de 2026.

Este módulo processa os arquivos de resultados de corridas e sprints de 2026,
vinculando race_id, driver_id e team_id com os dados padronizados da liga.
"""

import glob
import io
import os
import re
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


# Mapeamento de locais e nomes canônicos de GP
LOCATION_MAP = {
    "australia": ("GP da Austrália", "Melbourne"),
    "china": ("GP da China", "Xangai"),
    "japao": ("GP do Japão", "Suzuka"),
    "miami": ("GP de Miami", "Miami Gardens"),
    "canada": ("GP do Canadá", "Montreal"),
    "monaco": ("GP de Mônaco", "Monte Carlo"),
    "espanha": ("GP da Espanha", "Montmeló"),
    "silverstone": ("GP da Grã-Bretanha", "Silverstone"),
    "austria": ("GP da Áustria", "Spielberg"),
    "belgica": ("GP da Bélgica", "Spa-Francorchamps"),
    "hungria": ("GP da Hungria", "Mogyoród"),
    "holanda": ("GP dos Países Baixos", "Zandvoort"),
    "italia": ("GP da Itália", "Monza"),
    "azerbaijao": ("GP do Azerbaijão", "Bacu"),
    "singapura": ("GP de Singapura", "Marina Bay"),
    "estados_unidos": ("GP dos Estados Unidos", "Austin"),
    "mexico": ("GP da Cidade do México", "Cidade do México"),
    "brasil": ("GP de São Paulo", "São Paulo"),
    "las_vegas": ("GP de Las Vegas", "Las Vegas"),
    "catar": ("GP do Catar", "Lusail"),
    "abu_dhabi": ("GP de Abu Dhabi", "Abu Dhabi"),
}


def load_results(base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Lê os arquivos CSV de 2026 e retorna o DataFrame com os resultados consolidados.

    Gera um DataFrame com as seguintes colunas (mesmo schema de 2025):
    - race_id: ID canônico da corrida/sprint
    - driver_id: ID único do piloto
    - team_id: ID único da equipe
    - driver_start_position: Posição de largada no grid
    - driver_final_position: Posição de chegada na sessão
    - grid_result: Diferença de posições (chegada - largada)
    - driver_fastest_lap: Volta mais rápida na sessão

    Args:
        base_path (str): Caminho para a pasta dos dados de 2026.
                         Padrão: './files/2026'
        base_path_2025 (str): Caminho para a pasta dos dados de 2025 (para mapeamento histórico).
                              Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com os resultados das sessões de 2026.
                      Retorna None se houver erro ao carregar os dados.

    Raises:
        FileNotFoundError: Se o diretório base de 2026 não existir.
    """
    if not os.path.exists(base_path):
        raise FileNotFoundError(
            f"Diretório de 2026 não encontrado em: {base_path}"
        )

    try:
        # 1. Carregar mapeamento de IDs de pilotos
        driver_id_map = {}
        drivers_2025_file = os.path.join(base_path_2025, "drivers.csv")
        if os.path.exists(drivers_2025_file):
            df_2025_drivers = pd.read_csv(drivers_2025_file)
            driver_id_map = dict(zip(df_2025_drivers["driver_name"], df_2025_drivers["driver_id"]))

        max_driver_id = max(driver_id_map.values()) if driver_id_map else 0

        # 2. Carregar mapeamento de IDs de equipes
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

        # 3. Carregar mapeamento canônico de corridas
        canonical_race_map = {}
        max_canonical_race_id = 0
        races_2025_file = os.path.join(base_path_2025, "races.csv")
        if os.path.exists(races_2025_file):
            df_2025_races = pd.read_csv(races_2025_file)
            for _, row in df_2025_races.iterrows():
                rid = int(row["race_id"])
                rname = str(row["race_name"]).strip().lower()
                sprint = bool(row["is_sprint"])
                canonical_race_map[(rname, sprint)] = rid
                if rid > max_canonical_race_id:
                    max_canonical_race_id = rid

        # 4. Ler e identificar arquivos de 2026
        csv_files = glob.glob(os.path.join(base_path, "*.csv"))
        file_sessions = []
        teams_found = set()
        drivers_found = set()

        for file_path in csv_files:
            file_name = os.path.basename(file_path)
            if file_name.startswith("scores"):
                continue

            match = re.match(r"([a-zA-Z_]+)_(race|sprint)_(\d{8})\.csv", file_name, re.IGNORECASE)
            if not match:
                continue

            loc_raw, session_type, date_raw = match.groups()
            is_sprint = (session_type.lower() == "sprint")
            formatted_date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:]}"

            loc_key = loc_raw.lower()
            base_gp_name, _ = LOCATION_MAP.get(
                loc_key, (f"GP de {loc_raw.capitalize()}", loc_raw.capitalize())
            )
            race_name = f"{base_gp_name} (SPRINT)" if is_sprint else base_gp_name

            file_sessions.append({
                "file_path": file_path,
                "race_name": race_name,
                "race_date": formatted_date,
                "is_sprint": is_sprint
            })

            # Extração de equipes e pilotos com pandas para evitar capturar cabeçalhos
            lines = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip() or line.startswith(",,,,") or line.startswith("Tempo,"):
                        break
                    lines.append(line)
            if lines:
                df_temp = pd.read_csv(io.StringIO("".join(lines)))
                if "Piloto" in df_temp.columns:
                    for d in df_temp["Piloto"].dropna():
                        d_str = str(d).strip()
                        if d_str and d_str.lower() != "pessoa":
                            drivers_found.add(d_str)
                if "Equipe" in df_temp.columns:
                    for t in df_temp["Equipe"].dropna():
                        t_str = str(t).strip()
                        if t_str:
                            teams_found.add(t_str)

        # 5. Atribuir team_ids e driver_ids de forma ordenada e determinística
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

        for driver_name in sorted(list(drivers_found)):
            if driver_name not in driver_id_map:
                max_driver_id += 1
                driver_id_map[driver_name] = max_driver_id

        # Ordenar sessões cronologicamente
        file_sessions.sort(key=lambda x: (x["race_date"], not x["is_sprint"]))

        # Mapear race_id canônico para cada sessão
        for session in file_sessions:
            key = (session["race_name"].lower(), session["is_sprint"])
            if key in canonical_race_map:
                session["race_id"] = canonical_race_map[key]
            else:
                max_canonical_race_id += 1
                canonical_race_map[key] = max_canonical_race_id
                session["race_id"] = max_canonical_race_id

        # 6. Extrair resultados de cada arquivo
        all_results = []
        for session in file_sessions:
            race_id = session["race_id"]
            file_path = session["file_path"]

            lines = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip() or line.startswith(",,,,") or line.startswith("Tempo,"):
                        break
                    lines.append(line)

            if not lines:
                continue

            df_session = pd.read_csv(io.StringIO("".join(lines)))

            for _, row in df_session.iterrows():
                driver_name = str(row.get("Piloto", "")).strip()
                team_name = str(row.get("Equipe", "")).strip()

                # Resolver placeholder 'Pessoa' quando presente
                if driver_name.lower() == "pessoa":
                    if "racing bulls" in team_name.lower() or "visa" in team_name.lower():
                        driver_name = "Gabriel"

                driver_id = driver_id_map.get(driver_name)

                # Resolver team_id
                norm_team = _normalize_team_name(team_name)
                team_id = team_id_map.get(team_name, norm_team_to_id.get(norm_team))

                start_pos = int(row["Grid"])
                final_pos = int(row["Pos."])
                grid_result = final_pos - start_pos
                fastest_lap = str(row.get("Melhor tempo", "")).strip()

                all_results.append({
                    "race_id": race_id,
                    "driver_id": driver_id,
                    "team_id": team_id,
                    "driver_start_position": start_pos,
                    "driver_final_position": final_pos,
                    "grid_result": grid_result,
                    "driver_fastest_lap": fastest_lap
                })

        df_results = pd.DataFrame(all_results)
        df_results["race_id"] = df_results["race_id"].astype(int)
        df_results["driver_id"] = df_results["driver_id"].astype(int)
        df_results["team_id"] = df_results["team_id"].astype(int)
        df_results["driver_start_position"] = df_results["driver_start_position"].astype(int)
        df_results["driver_final_position"] = df_results["driver_final_position"].astype(int)
        df_results["grid_result"] = df_results["grid_result"].astype(int)

        return df_results

    except Exception as e:
        print(f"Erro ao extrair resultados de 2026 em {base_path}: {e}")
        return None


# Alias para retrocompatibilidade
load_2026_results = load_results


if __name__ == "__main__":
    results_df = load_results()

    if results_df is not None:
        print(f"\nDataFrame de resultados de 2026 (Total de linhas: {len(results_df)}):")
        print(results_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de resultados de 2026.")
