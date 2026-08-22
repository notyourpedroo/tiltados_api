#!/usr/bin/env python3
"""
Retornar o DataFrame das corridas de 2026.

Este módulo extrai as corridas e sprints de 2026 e mapeia os IDs canônicos
por pista/sessão para manter consistência direta com 2025.
"""

import glob
import os
import re
import pandas as pd


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


def _normalize_location_key(location_raw):
    return location_raw.lower().replace("_", "").strip()


def load_races(base_path="./files/2026", base_path_2025="./files/2025"):
    """
    Lê os arquivos de resultados de 2026 e gera o DataFrame de corridas
    utilizando IDs canônicos por pista/evento baseados em 2025.

    Gera um DataFrame com as seguintes colunas:
    - race_id: ID canônico da corrida/pista (mesmo ID de 2025 para a mesma pista/sessão)
    - race_name: Nome oficial da corrida (ex: 'GP da China (SPRINT)' ou 'GP da China')
    - race_date: Data da corrida (formato YYYY-MM-DD)
    - race_location: Localidade/cidade do evento
    - is_sprint: Indica se é uma corrida sprint (True/False)

    Args:
        base_path (str): Caminho para a pasta dos dados de 2026.
                         Padrão: './files/2026'
        base_path_2025 (str): Caminho para a pasta dos dados de 2025 (para mapeamento canônico de IDs).
                              Padrão: './files/2025'

    Returns:
        pd.DataFrame: DataFrame com as corridas de 2026.
                      Retorna None se houver erro ao carregar os dados.

    Raises:
        FileNotFoundError: Se o diretório base de 2026 não existir.
    """
    if not os.path.exists(base_path):
        raise FileNotFoundError(
            f"Diretório de 2026 não encontrado em: {base_path}"
        )

    try:
        # 1. Carregar mapeamento canônico de 2025
        canonical_map = {}
        max_canonical_id = 0
        races_2025_file = os.path.join(base_path_2025, "races.csv")
        if os.path.exists(races_2025_file):
            df_2025 = pd.read_csv(races_2025_file)
            for _, row in df_2025.iterrows():
                rid = int(row["race_id"])
                rname = str(row["race_name"]).strip()
                sprint = bool(row["is_sprint"])
                canonical_map[(rname.lower(), sprint)] = rid
                if rid > max_canonical_id:
                    max_canonical_id = rid

        # 2. Identificar arquivos de 2026
        csv_files = glob.glob(os.path.join(base_path, "*.csv"))
        parsed_races = []

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
            base_gp_name, location = LOCATION_MAP.get(
                loc_key, (f"GP de {loc_raw.capitalize()}", loc_raw.capitalize())
            )
            race_name = f"{base_gp_name} (SPRINT)" if is_sprint else base_gp_name

            parsed_races.append({
                "race_name": race_name,
                "race_date": formatted_date,
                "race_location": location,
                "is_sprint": is_sprint
            })

        if not parsed_races:
            print("Nenhuma corrida encontrada nos arquivos de 2026.")
            return None

        # 3. Ordenar cronologicamente
        parsed_races.sort(key=lambda x: (x["race_date"], not x["is_sprint"]))

        # 4. Atribuir IDs canônicos
        for race_item in parsed_races:
            key = (race_item["race_name"].lower(), race_item["is_sprint"])
            if key in canonical_map:
                race_item["race_id"] = canonical_map[key]
            else:
                max_canonical_id += 1
                canonical_map[key] = max_canonical_id
                race_item["race_id"] = max_canonical_id

        df_races = pd.DataFrame(parsed_races)
        df_races = df_races[["race_id", "race_name", "race_date", "race_location", "is_sprint"]]
        df_races["race_id"] = df_races["race_id"].astype(int)
        df_races["is_sprint"] = df_races["is_sprint"].astype(bool)

        return df_races

    except Exception as e:
        print(f"Erro ao extrair corridas de 2026 em {base_path}: {e}")
        return None


# Alias para retrocompatibilidade
load_2026_races = load_races


if __name__ == "__main__":
    races_df = load_races()

    if races_df is not None:
        print("\nDataFrame de corridas de 2026 (IDs Canônicos):")
        print(races_df.to_string(index=False))
    else:
        print("⚠️ Erro ao carregar os dados de corridas de 2026.")
