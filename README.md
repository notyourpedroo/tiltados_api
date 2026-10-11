# Tiltados API

API REST desenvolvida em FastAPI para consolidar e servir os dados das temporadas de 2025 e 2026 da liga Tiltados F1.

## Requisitos

- Python 3.11 ou superior
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

## Testes

Instale as dependencias de desenvolvimento e rode o `pytest` na raiz do projeto:

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes rodam sobre uma copia de `files/` em uma pasta temporaria, entao podem alterar ou quebrar CSVs sem tocar nos dados reais. Eles cobrem os endpoints, a consistencia dos dados (IDs, pontos, superlicenca), as regras de 2026 (IDs reaproveitados de 2025, equipe atual do piloto, recarga do cache) e as mensagens de erro para CSVs invalidos.

Um dos testes exige que todo local de arquivo em `files/2026/` esteja no `LOCATION_MAP`. Ao adicionar um GP novo, inclua o local no mapeamento.

## Atualizacao Automatica dos Dados

Os dados sao lidos dos CSVs em `files/` e guardados em cache. O cache e invalidado sozinho sempre que um CSV e adicionado, editado ou removido, entao **nao e preciso reiniciar o servidor** para ver os dados novos.

Isso vale para qualquer arquivo em `files/` (2025, 2026 e `super_license`). Mudancas no codigo Python (`main.py` ou `scripts/`) ainda exigem reiniciar o servidor, ou usar `--reload`.

Se algum CSV estiver com problema (arquivo ausente, coluna faltando, valor invalido), os endpoints que dependem dele retornam HTTP 500 com a causa em `detail`, indicando o arquivo e a linha a corrigir. Por exemplo:

```json
{"detail": "2026/japao_race_20260323.csv, linha 2: coluna 'Grid' com valor 'X' (esperado um número inteiro)."}
```

## Adicionando uma Nova Corrida (2026)

1. Salve o CSV da sessao em `files/2026/` seguindo o padrao de nome:

   ```
   {local}_{race|sprint}_{YYYYMMDD}.csv
   ```

   Exemplos: `singapura_race_20261005.csv`, `silverstone_sprint_20260728.csv`.

   - `{local}` deve estar em minusculas e sem acentos. Se nao estiver no mapeamento `LOCATION_MAP` (em `scripts/2026/common.py`), o nome do GP e derivado do arquivo (ex.: `GP de Imola`) e a corrida recebe um `race_id` novo em vez de reaproveitar o de 2025. Para ter o nome oficial, adicione a entrada no mapeamento, com o nome do GP igual ao de `files/2025/races.csv`.
   - `race` ou `sprint` define o tipo da sessao.
   - `YYYYMMDD` e a data da sessao.

2. O CSV deve ter o cabecalho e as colunas do exportado do site de resultados:

   ```
   Pos.,Piloto,Equipe,Grid,Paradas,Melhor tempo,Tempo,Pts.,tipo de piloto
   ```

   A leitura para na primeira linha em branco, na que comeca com `,,,,` ou na que comeca com `Tempo,`. Tudo que vier depois disso e ignorado.

3. Pronto. Corridas, resultados, pilotos e equipes de 2026 sao derivados da pasta `files/2026/`. Se o export vier com o nome `Pessoa` (placeholder do site) ou vazio no lugar do piloto, troque pelo nome real antes de salvar. Caso contrario, os endpoints de 2026 que dependem de pilotos retornam erro indicando o arquivo e a linha a corrigir.

   Se a corrida tiver punicao de Superlicenca, registre tambem em `files/super_license/punishments.csv` (colunas `season_year,driver_id,race_id,deduction_points,penalty_reason`).

A pontuacao de cada posicao vem de `files/2026/scores.csv` (colunas `position`, `points`, `is_sprint`).

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

## Regras de Negocio

**Classificacao (pilotos e construtores)**
- Pontos vem de `scores.csv`, cruzando a posicao final com o tipo da sessao (corrida ou sprint).
- Desempate: pontos, depois vitorias em GP, depois podios.
- `races` conta sessoes disputadas, ou seja, corridas e sprints somadas. `wins` conta apenas corridas (GP); `sprint_wins` conta apenas sprints.

**Superlicenca (2026)**
- Cada piloto comeca com 12 pontos.
- Cada punicao em `files/super_license/punishments.csv` deduz pontos (`deduction_points`).
- Status conforme os pontos restantes:

| Pontos restantes | Status |
|---|---|
| 9 a 12 | `Regular` |
| 5 a 8 | `Atencao` |
| 1 a 4 | `Alerta Critico` |
| 0 ou menos | `Suspenso (Ban)` |

## Exemplos de Uso e Respostas

Os valores abaixo sao do estado atual dos dados (temporada 2026, ate o GP de Singapura).

### 1. Informacoes da API
`GET /`

```json
{
  "name": "Tiltados API",
  "version": "v2.26.1010",
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
    "points": 385,
    "wins": 10,
    "sprint_wins": 2,
    "podiums": 20,
    "races": 22
  },
  {
    "position": 2,
    "driver_id": 7,
    "driver_name": "Yohan",
    "team_id": 1,
    "team_name": "Red Bull",
    "points": 289,
    "wins": 4,
    "sprint_wins": 3,
    "podiums": 15,
    "races": 22
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
    "points": 560,
    "wins": 10,
    "podiums": 25
  },
  {
    "position": 2,
    "team_id": 1,
    "team_name": "Red Bull",
    "points": 443,
    "wins": 4,
    "podiums": 17
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
    "driver_id": 8,
    "driver_name": "Douglas",
    "team_id": 6,
    "team_name": "Mercedes-AMG Petronas",
    "initial_points": 12,
    "deducted_points": 3,
    "remaining_points": 9,
    "punishments_count": 1,
    "status": "Regular"
  }
]
```

### 6. Punicoes da Superlicenca (2026)
`GET /load/2026/punishments`

```json
[
  {
    "season_year": 2026,
    "driver_id": 5,
    "race_id": 3,
    "deduction_points": 2,
    "penalty_reason": "Causou uma colisão",
    "driver_name": "Matheus",
    "team_id": 7,
    "team_name": "Visa Cash App Racing Bulls",
    "race_name": "GP da China",
    "race_date": "2026-03-09"
  },
  {
    "season_year": 2026,
    "driver_id": 8,
    "race_id": 34,
    "deduction_points": 3,
    "penalty_reason": "Causou uma colisão",
    "driver_name": "Douglas",
    "team_id": 6,
    "team_name": "Mercedes-AMG Petronas",
    "race_name": "GP de Singapura (SPRINT)",
    "race_date": "2026-10-05"
  }
]
```

Cada punicao precisa apontar para um `driver_id` e um `race_id` existentes em 2026; caso contrario, o endpoint retorna erro indicando a linha do `punishments.csv`.

## Estrutura do Projeto

```text
tiltados_api/
|-- files/
|   |-- 2025/               # CSVs consolidados da temporada 2025
|   |-- 2026/               # CSVs de cada sessao da temporada 2026 (+ scores.csv)
|   `-- super_license/      # Arquivo de punicoes da superlicenca
|-- scripts/
|   |-- 2025/               # Modulos de extracao e calculo de 2025
|   `-- 2026/               # Modulos de extracao e calculo de 2026
|-- main.py                 # Aplicacao FastAPI, cache e definicao de rotas
|-- requirements.txt        # Dependencias do projeto
`-- README.md               # Documentacao do projeto
```
