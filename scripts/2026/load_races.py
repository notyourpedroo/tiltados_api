#!/usr/bin/env python3
"""
Retornar o DataFrame das corridas de 2026.

Este módulo extrai as corridas e sprints de 2026 e mapeia os IDs canônicos
por pista/sessão para manter consistência direta com 2025.
"""

import os
import sys
import pandas as pd

# Suporta tanto importação relativa de pacote quanto execução direta de script
try:
    from .common import list_sessions
except (ImportError, ValueError):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    from common import list_sessions


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

        # 2. Identificar as sessões de 2026, já em ordem cronológica
        sessions = list_sessions(base_path)
        if not sessions:
            print("Nenhuma corrida encontrada nos arquivos de 2026.")
            return None

        # 3. Atribuir IDs canônicos
        parsed_races = []
        for session in sessions:
            key = (session["race_name"].lower(), session["is_sprint"])
            if key not in canonical_map:
                max_canonical_id += 1
                canonical_map[key] = max_canonical_id

            parsed_races.append({
                "race_id": canonical_map[key],
                "race_name": session["race_name"],
                "race_date": session["race_date"],
                "race_location": session["race_location"],
                "is_sprint": session["is_sprint"]
            })

        df_races = pd.DataFrame(parsed_races)
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
