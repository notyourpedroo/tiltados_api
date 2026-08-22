# Tiltados API

API REST desenvolvida em FastAPI para consolidar e servir os dados das temporadas de 2025 e 2026 da liga Tiltados F1.

## Requisitos

- Python 3.10 ou superior
- Pip (gerenciador de pacotes do Python)

## Instalacao

1. Clone ou acesse a pasta raiz do repositorio:

```bash
cd tiltados_api
```

2. Crie e ative um ambiente virtual:

Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Instale as dependencias necessarias:

```bash
pip install -r requirements.txt
```

## Execucao

Para iniciar o servidor de desenvolvimento:

```bash
uvicorn main:app --reload
```

A API estara disponivel em:
- Endereco base: `http://localhost:8000`
- Documentacao interativa (Swagger UI): `http://localhost:8000/docs`
- Documentacao alternativa (ReDoc): `http://localhost:8000/redoc`

## Endpoints Disponiveis

O parametro `{season}` aceita os valores `2025` ou `2026`.

| Metodo | Endpoint | Descricao |
|---|---|---|
| GET | `/` | Informacoes basicas e versao da API |
| GET | `/load/{season}/drivers` | Lista de pilotos da temporada |
| GET | `/load/{season}/teams` | Lista de equipes da temporada |
| GET | `/load/{season}/races` | Lista de corridas e sprints da temporada |
| GET | `/load/{season}/results` | Resultados detalhados de todas as corridas |
| GET | `/load/{season}/standings/drivers` | Tabela de classificacao do campeonato de pilotos |
| GET | `/load/{season}/standings/teams` | Tabela de classificacao do campeonato de construtores |
| GET | `/load/2026/punishments` | Relatorio de punicoes da Superlicenca (2026) |
| GET | `/load/2026/super-license` | Status e saldo de pontos da Superlicenca (2026) |

## Exemplos de Uso e Respostas

### 1. Informacoes da API
`GET /`

```json
{
  "name": "Tiltados API",
  "version": "v2.26.0822",
  "seasons": [
    2025,
    2026
  ],
  "docs": "/docs"
}
```

### 2. Pilotos da Temporada
`GET /load/2026/drivers`

```json
[
  {
    "driver_id": 2,
    "team_id": 7,
    "driver_name": "Gabriel"
  },
  {
    "driver_id": 3,
    "team_id": 2,
    "driver_name": "Bryan"
  },
  {
    "driver_id": 4,
    "team_id": 2,
    "driver_name": "Paulo"
  }
]
```

### 3. Classificacao de Pilotos
`GET /load/2026/standings/drivers`

```json
[
  {
    "position": 1,
    "driver_id": 5,
    "driver_name": "Matheus",
    "team_id": 7,
    "team_name": "Visa Cash App Racing Bulls",
    "points": 212,
    "wins": 6,
    "sprint_wins": 2,
    "podiums": 11,
    "races": 12
  },
  {
    "position": 2,
    "driver_id": 7,
    "driver_name": "Yohan",
    "team_id": 1,
    "team_name": "Red Bull",
    "points": 134,
    "wins": 1,
    "sprint_wins": 1,
    "podiums": 7,
    "races": 12
  }
]
```

### 4. Classificacao de Construtores
`GET /load/2026/standings/teams`

```json
[
  {
    "position": 1,
    "team_id": 7,
    "team_name": "Visa Cash App Racing Bulls",
    "points": 309,
    "wins": 6,
    "podiums": 14
  },
  {
    "position": 2,
    "team_id": 1,
    "team_name": "Red Bull",
    "points": 192,
    "wins": 1,
    "podiums": 7
  }
]
```

### 5. Status da Superlicenca (2026)
`GET /load/2026/super-license`

```json
[
  {
    "driver_id": 2,
    "driver_name": "Gabriel",
    "team_id": 7,
    "team_name": "Visa Cash App Racing Bulls",
    "initial_points": 12,
    "deducted_points": 4,
    "remaining_points": 8,
    "punishments_count": 2,
    "status": "Atencao"
  },
  {
    "driver_id": 5,
    "driver_name": "Matheus",
    "team_id": 7,
    "team_name": "Visa Cash App Racing Bulls",
    "initial_points": 12,
    "deducted_points": 2,
    "remaining_points": 10,
    "punishments_count": 1,
    "status": "Regular"
  }
]
```

## Estrutura do Projeto

```text
tiltados_api/
|-- files/
|   |-- 2025/               # CSVs consolidados da temporada 2025
|   |-- 2026/               # CSVs de cada sessao da temporada 2026
|   `-- super_license/      # Arquivo de punicoes da superlicenca
|-- scripts/
|   |-- 2025/               # Modulos de extracao e calculo de 2025
|   `-- 2026/               # Modulos de extracao e calculo de 2026
|-- main.py                 # Aplicacao FastAPI e definicao de rotas
|-- requirements.txt        # Dependencias do projeto
`-- README.md               # Documentacao do projeto
```
