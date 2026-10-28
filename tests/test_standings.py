"""Desempate da classificação de pilotos e de construtores (temporadas por Sessão)."""

from conftest import reset_2026_season, write_session

DRIVERS = "/load/2026/standings/drivers"
TEAMS = "/load/2026/standings/teams"

# Equipes de 2025, com IDs fixos: Ferrari (2) < McLaren (4).
# Nos cenários, quem vence o desempate tem o ID maior, para a ordem do ID não decidir por acaso.
FERRARI = "Scuderia Ferrari HP"
MCLAREN = "McLaren F1 Team"
ALPINE = "BWT Alpine F1 Team"
SAUBER = "Stake F1 Team Kick Sauber"


def order(client, path, key):
    return [(row[key], row["points"]) for row in client.get(path).json()]


def test_piloto_com_mais_segundos_lugares_em_corridas_fica_a_frente(client, data_dir):
    # Mike (ID 9): um 2º numa Corrida = 18 pontos, 1 pódio.
    # Gabriel (ID 2): um 3º numa Corrida (15) + um 6º numa Sprint (3) = 18 pontos, 1 pódio.
    # Empatam em pontos, vitórias (0) e pódios (1); Mike tem um 2º em Corridas, Gabriel nenhum.
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_race_20260302.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Mike", SAUBER, 2),
        (3, "Gabriel", FERRARI, 3),
        (4, "Yohan", MCLAREN, 4),
    ])
    write_session(data_dir, "china_sprint_20260309.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Yohan", MCLAREN, 2),
        (3, "Douglas", SAUBER, 3),
        (4, "José", SAUBER, 4),
        (5, "Paulo", FERRARI, 5),
        (6, "Gabriel", FERRARI, 6),
    ])

    assert order(client, DRIVERS, "driver_name") == [
        ("Matheus", 33), ("Yohan", 19), ("Mike", 18), ("Gabriel", 18),
        ("Douglas", 6), ("José", 5), ("Paulo", 4),
    ]


def test_com_os_segundos_lugares_empatados_decide_quem_tem_mais_terceiros(client, data_dir):
    # Mike (ID 9): 2º na Austrália (18) + 6º na Sprint da China (3) + 3º no Japão (15) = 36, 2 pódios.
    # Gabriel (ID 2): 4º na Austrália (12) + 3º na Sprint da China (6) + 2º no Japão (18) = 36, 2 pódios.
    # Um 2º em Corridas para cada; Mike tem um 3º em Corridas, Gabriel nenhum (o dele foi numa Sprint).
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_race_20260302.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Mike", SAUBER, 2),
        (3, "Yohan", MCLAREN, 3),
        (4, "Gabriel", FERRARI, 4),
    ])
    write_session(data_dir, "china_sprint_20260309.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Yohan", MCLAREN, 2),
        (3, "Gabriel", FERRARI, 3),
        (4, "Douglas", SAUBER, 4),
        (5, "José", SAUBER, 5),
        (6, "Mike", SAUBER, 6),
    ])
    write_session(data_dir, "japao_race_20260323.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Gabriel", FERRARI, 2),
        (3, "Mike", SAUBER, 3),
        (4, "Yohan", MCLAREN, 4),
    ])

    assert order(client, DRIVERS, "driver_name") == [
        ("Matheus", 58), ("Mike", 36), ("Gabriel", 36), ("Yohan", 34), ("Douglas", 5), ("José", 4),
    ]


def test_com_a_contagem_empatada_fica_a_frente_quem_conseguiu_primeiro_o_melhor_resultado(client, data_dir):
    # Mike (ID 9) e Gabriel (ID 2) fazem um 2º e um 4º em Corridas: 30 pontos e 1 pódio cada.
    # Mike fez o 2º na Austrália (02/03), Gabriel só no Japão (23/03).
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_race_20260302.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Mike", SAUBER, 2),
        (3, "Yohan", MCLAREN, 3),
        (4, "Gabriel", FERRARI, 4),
    ])
    write_session(data_dir, "japao_race_20260323.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Gabriel", FERRARI, 2),
        (3, "Yohan", MCLAREN, 3),
        (4, "Mike", SAUBER, 4),
    ])

    assert order(client, DRIVERS, "driver_name") == [
        ("Matheus", 50), ("Yohan", 30), ("Mike", 30), ("Gabriel", 30),
    ]


def test_sem_corridas_disputadas_o_empate_fica_na_ordem_do_id(client, data_dir):
    # Gabriel (ID 2) e Mike (ID 9) só disputam Sprints: 4º + 5º = 9 pontos cada, sem pódio.
    reset_2026_season(data_dir)
    write_session(data_dir, "china_sprint_20260309.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Yohan", MCLAREN, 2),
        (3, "Douglas", SAUBER, 3),
        (4, "Mike", SAUBER, 4),
        (5, "Gabriel", FERRARI, 5),
    ])
    write_session(data_dir, "miami_sprint_20260427.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Yohan", MCLAREN, 2),
        (3, "Douglas", SAUBER, 3),
        (4, "Gabriel", FERRARI, 4),
        (5, "Mike", SAUBER, 5),
    ])

    assert order(client, DRIVERS, "driver_name") == [
        ("Matheus", 16), ("Yohan", 14), ("Douglas", 12), ("Gabriel", 9), ("Mike", 9),
    ]


def test_equipe_com_mais_segundos_lugares_em_corridas_fica_a_frente(client, data_dir):
    # McLaren (ID 4): Yohan 2º (18) e Adriano 5º (10) na Austrália, Adriano 2º no Japão (18) = 46, 2 pódios.
    # Ferrari (ID 2): Bryan 3º (15) e Paulo 4º (12) na Austrália, Paulo 3º no Japão (15),
    # Bryan 5º na Sprint da China (4) = 46, 2 pódios.
    # A McLaren soma dois 2ºs em Corridas, um de cada piloto; a Ferrari, nenhum.
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_race_20260302.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Yohan", MCLAREN, 2),
        (3, "Bryan", FERRARI, 3),
        (4, "Paulo", FERRARI, 4),
        (5, "Adriano", MCLAREN, 5),
        (6, "Douglas", SAUBER, 6),
    ])
    write_session(data_dir, "china_sprint_20260309.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Douglas", SAUBER, 2),
        (3, "José", SAUBER, 3),
        (4, "Mike", SAUBER, 4),
        (5, "Bryan", FERRARI, 5),
    ])
    write_session(data_dir, "japao_race_20260323.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Adriano", MCLAREN, 2),
        (3, "Paulo", FERRARI, 3),
        (4, "Douglas", SAUBER, 4),
    ])

    assert order(client, TEAMS, "team_name") == [
        (ALPINE, 58), (MCLAREN, 46), (FERRARI, 46), (SAUBER, 38),
    ]


def test_equipes_com_os_segundos_lugares_empatados_decide_quem_tem_mais_terceiros(client, data_dir):
    # McLaren (ID 4): Yohan 2º na Austrália (18), Adriano 6º na Sprint da China (3) e 3º no Japão (15) = 36.
    # Ferrari (ID 2): Bryan 4º na Austrália (12) e 2º no Japão (18), Paulo 3º na Sprint da China (6) = 36.
    # 2 pódios e um 2º em Corridas para cada; só a McLaren tem um 3º em Corridas.
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_race_20260302.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Yohan", MCLAREN, 2),
        (3, "Douglas", SAUBER, 3),
        (4, "Bryan", FERRARI, 4),
    ])
    write_session(data_dir, "china_sprint_20260309.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Douglas", SAUBER, 2),
        (3, "Paulo", FERRARI, 3),
        (4, "José", SAUBER, 4),
        (5, "Mike", SAUBER, 5),
        (6, "Adriano", MCLAREN, 6),
    ])
    write_session(data_dir, "japao_race_20260323.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Bryan", FERRARI, 2),
        (3, "Adriano", MCLAREN, 3),
        (4, "Douglas", SAUBER, 4),
    ])

    assert order(client, TEAMS, "team_name") == [
        (ALPINE, 58), (SAUBER, 43), (MCLAREN, 36), (FERRARI, 36),
    ]


def test_equipe_que_conseguiu_primeiro_o_melhor_resultado_com_qualquer_piloto_fica_a_frente(client, data_dir):
    # McLaren (ID 4) e Ferrari (ID 2) fazem um 2º e um 4º em Corridas: 30 pontos e 1 pódio cada.
    # A McLaren fez o 2º com Yohan na Austrália (02/03); a Ferrari, com Paulo no Japão (23/03).
    reset_2026_season(data_dir)
    write_session(data_dir, "australia_race_20260302.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Yohan", MCLAREN, 2),
        (3, "Douglas", SAUBER, 3),
        (4, "Bryan", FERRARI, 4),
    ])
    write_session(data_dir, "japao_race_20260323.csv", [
        (1, "Matheus", ALPINE, 1),
        (2, "Paulo", FERRARI, 2),
        (3, "Douglas", SAUBER, 3),
        (4, "Adriano", MCLAREN, 4),
    ])

    assert order(client, TEAMS, "team_name") == [
        (ALPINE, 50), (SAUBER, 30), (MCLAREN, 30), (FERRARI, 30),
    ]


def test_classificacao_de_2025_continua_como_foi_publicada(client):
    # José e Mike empatam em tudo (30 pontos, sem vitórias nem pódios); 2025 mantém a ordem publicada.
    standings = client.get("/load/2025/standings/drivers").json()
    assert [(d["position"], d["driver_name"], d["points"]) for d in standings[-2:]] == [
        (9, "José", 30), (10, "Mike", 30),
    ]
