"""Resultados de 2025: só quem teve Participação na Sessão aparece no resultado dela."""

NO_LAP = "9:99.999"

# Contado à mão no CSV de 2025 (spec #40): (posição, piloto, pontos, Participações).
DRIVERS_2025 = [
    (1, "Matheus", 521, 30),
    (2, "Bryan", 407, 28),
    (3, "Pedro", 261, 22),
    (4, "Paulo", 247, 30),
    (5, "Gabriel", 227, 29),
    (6, "Adriano", 211, 12),
    (7, "Yohan", 193, 30),
    (8, "Douglas", 140, 15),
    (9, "José", 30, 13),
    (10, "Mike", 30, 6),
]

TEAMS_2025 = [
    (1, "BWT Alpine F1 Team", 782),
    (2, "Scuderia Ferrari HP", 654),
    (3, "McLaren F1 Team", 404),
    (4, "Oracle Red Bull Racing", 257),
    (5, "Stake F1 Team Kick Sauber", 170),
]


def test_races_de_2025_conta_as_participacoes_de_cada_piloto(client):
    standings = client.get("/load/2025/standings/drivers").json()

    assert [(d["position"], d["driver_name"], d["points"], d["races"]) for d in standings] == DRIVERS_2025


def test_resultados_de_2025_trazem_so_quem_correu(client):
    results = client.get("/load/2025/results").json()
    jose = next(d["driver_id"] for d in client.get("/load/2025/drivers").json() if d["driver_name"] == "José")

    # Soma das Participações da tabela acima.
    assert len(results) == 215
    # O único 9:99.999 que sobra é o abandono de José na Sessão 10: largou P7 e chegou P10.
    assert [
        (r["race_id"], r["driver_id"], r["driver_start_position"], r["driver_final_position"])
        for r in results if r["driver_fastest_lap"] == NO_LAP
    ] == [(10, jose, 7, 10)]


def test_construtores_de_2025_continuam_como_foram_publicados(client):
    standings = client.get("/load/2025/standings/teams").json()

    assert [(t["position"], t["team_name"], t["points"]) for t in standings] == TEAMS_2025
