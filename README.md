# Tiltados API

API REST desenvolvida em FastAPI para consolidar e servir os dados das temporadas de 2025 e 2026 da liga Tiltados F1.

## Requisitos

- Python 3.11 ou superior
- Pip (gerenciador de pacotes do Python)

## Instalação

1. Clone ou acesse a pasta raiz do repositório:

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

3. Instale as dependências necessárias:

```bash
pip install -r requirements.txt
```

4. Ative o hook que confere as mensagens de commit (Conventional Commits, em português sem acentos):

```bash
git config core.hooksPath .githooks
```

## Execução

Para iniciar o servidor de desenvolvimento:

```bash
uvicorn main:app --reload
```

A API estará disponível em:
- Endereço base: `http://localhost:8000`
- Documentação interativa (Swagger UI): `http://localhost:8000/docs`
- Documentação alternativa (ReDoc): `http://localhost:8000/redoc`

## Produção

Em produção a API fica atrás do nginx, com HTTPS, no prefixo `/api`:

- Endereço base: `https://<ip-do-servidor>/api`
- Documentação: `https://<ip-do-servidor>/api/docs`

As rotas são as mesmas do desenvolvimento, por exemplo `https://<ip-do-servidor>/api/load/2026/teams`.
O uvicorn escuta só em `127.0.0.1:8000` (veja `deploy/setup-servidor.sh`), então a porta 8000
não é acessível de fora. O nginx limita cada IP a 10 requisições por segundo, com rajadas de até 60;
acima disso responde `429`.

A configuração do nginx não fica neste repositório. No servidor, o trecho que publica a API fica no
`server` da porta 443 (`/etc/nginx/sites-available/tiltados-app`):

```nginx
location /api/ {
    limit_req zone=tiltados_api burst=60 nodelay;
    access_log /var/log/nginx/tiltados-api.access.log;

    proxy_pass http://127.0.0.1:8000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location = /api {
    return 301 /api/;
}
```

E a zona de limite, em `/etc/nginx/conf.d/tiltados-api.conf`:

```nginx
limit_req_zone $binary_remote_addr zone=tiltados_api:10m rate=10r/s;
limit_req_status 429;
```

## Testes

Instale as dependências de desenvolvimento e rode o lint e o `pytest` na raiz do projeto (o CI roda os dois, nessa ordem):

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

Os testes rodam sobre uma cópia de `files/` em uma pasta temporária, então podem alterar ou quebrar CSVs sem tocar nos dados reais. Eles cobrem os endpoints, a consistência dos dados (IDs, pontos, superlicença), as regras de 2026 (IDs reaproveitados de 2025, equipe atual do piloto, recarga do cache) e as mensagens de erro para CSVs inválidos.

Toda rota da API entra sozinha nos testes de resposta. Uma rota nova também precisa aparecer na tabela de "Endpoints Disponíveis" e na lista `HEALTH_URLS` de `deploy/publicar.sh`, senão os testes falham.

Um dos testes exige que todo local de arquivo em `files/2026/` esteja no `LOCATION_MAP`. Ao adicionar um GP novo, inclua o local no mapeamento.

## Atualização Automática dos Dados

Os dados são lidos dos CSVs em `files/` e guardados em cache. O cache é invalidado sozinho sempre que um CSV é adicionado, editado ou removido, então **não é preciso reiniciar o servidor** para ver os dados novos.

Isso vale para qualquer arquivo em `files/` (2025, 2026 e `super_license`). Mudanças no código Python (`main.py` ou `scripts/`) ainda exigem reiniciar o servidor, ou usar `--reload`.

Se algum CSV estiver com problema (arquivo ausente, coluna faltando, valor inválido), os endpoints que dependem dele retornam HTTP 500 com a causa em `detail`, indicando o arquivo e a linha a corrigir. Por exemplo:

```json
{"detail": "2026/japao_race_20260323.csv, linha 2: coluna 'Grid' com valor 'X' (esperado um número inteiro)."}
```

## Adicionando uma Nova Corrida (2026)

1. Salve o CSV da sessão em `files/2026/` seguindo o padrão de nome:

   ```
   {local}_{race|sprint}_{YYYYMMDD}.csv
   ```

   Exemplos: `singapura_race_20261005.csv`, `silverstone_sprint_20260728.csv`.

   - `{local}` deve estar em minúsculas e sem acentos. Se não estiver no mapeamento `LOCATION_MAP` (em `scripts/2026/common.py`), o nome do GP é derivado do arquivo (ex.: `GP de Imola`) e a corrida recebe um `race_id` novo em vez de reaproveitar o de 2025. Para ter o nome oficial, adicione a entrada no mapeamento, com o nome do GP igual ao de `files/2025/races.csv`.
   - `race` ou `sprint` define o tipo da sessão.
   - `YYYYMMDD` é a data da sessão.

2. O CSV deve ter o cabeçalho e as colunas do exportado do site de resultados:

   ```
   Pos.,Piloto,Equipe,Grid,Paradas,Melhor tempo,Tempo,Pts.,tipo de piloto
   ```

   A leitura para na primeira linha em branco, na que começa com `,,,,` ou na que começa com `Tempo,`. Tudo que vier depois disso é ignorado.

3. Pronto. Corridas, resultados, pilotos e equipes de 2026 são derivados da pasta `files/2026/`. Se o export vier com o nome `Pessoa` (placeholder do site) ou vazio no lugar do piloto, troque pelo nome real antes de salvar. Caso contrário, os endpoints de 2026 que dependem de pilotos retornam erro indicando o arquivo e a linha a corrigir.

   A sessão precisa estar no Calendário (`files/2026/calendar.csv`, colunas `local,tipo,data`), com o mesmo `{local}` e o mesmo tipo do nome do arquivo. No Calendário, todo `local` precisa estar no `LOCATION_MAP`, para um nome digitado errado não virar uma Sessão pendente para sempre. A ligação é só por local e tipo: a data do arquivo de resultado prevalece sobre a data prevista do Calendário. Uma sessão fora do Calendário faz as rotas `/load/2026/prediction/drivers` e `/load/2026/prediction/teams` retornarem erro indicando o arquivo e a linha a adicionar.

   Se a corrida tiver punição de Superlicença, registre também em `files/super_license/punishments.csv` (colunas `season_year,driver_id,race_id,deduction_points,penalty_reason`).

4. Faça o commit e o push na `main`. O GitHub Actions roda os testes e publica a corrida nova no servidor em cerca de 1 a 2 minutos. Os CSVs de produção vêm sempre do Git: não edite arquivos direto no servidor, porque cada publicação substitui a pasta `files/`.

A pontuação de cada posição vem de `files/2026/scores.csv` (colunas `position`, `points`, `is_sprint`).

## Endpoints Disponíveis

O parâmetro `{season}` aceita os valores `2025` ou `2026`.

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/` | Informações básicas e versão da API |
| GET | `/load/{season}/drivers` | Lista de pilotos da temporada |
| GET | `/load/{season}/teams` | Lista de equipes da temporada |
| GET | `/load/{season}/races` | Lista de corridas e sprints da temporada |
| GET | `/load/{season}/results` | Resultados detalhados de todas as corridas |
| GET | `/load/{season}/standings/drivers` | Tabela de classificação do campeonato de pilotos |
| GET | `/load/{season}/standings/teams` | Tabela de classificação do campeonato de construtores |
| GET | `/load/2026/punishments` | Relatório de punições da Superlicença (2026) |
| GET | `/load/2026/super-license` | Status e saldo de pontos da Superlicença (2026) |
| GET | `/load/2026/prediction/drivers` | Situação no título e Chance de título dos pilotos (2026) |
| GET | `/load/2026/prediction/teams` | Situação no título e Chance de título dos construtores (2026) |

## Regras de Negócio

**Classificação (pilotos e construtores)**
- Pontos vêm de `scores.csv`, cruzando a posição final com o tipo da sessão (corrida ou sprint).
- Desempate: pontos, depois vitórias em GP, depois pódios.
- `races` conta sessões disputadas, ou seja, corridas e sprints somadas. `wins` conta apenas corridas (GP); `sprint_wins` conta apenas sprints.

**Superlicença (2026)**
- Cada piloto começa com 12 pontos.
- Cada punição em `files/super_license/punishments.csv` deduz pontos (`deduction_points`).
- Status conforme os pontos restantes:

| Pontos restantes | Status |
|---|---|
| 9 a 12 | `Regular` |
| 5 a 8 | `Atencao` |
| 1 a 4 | `Alerta Critico` |
| 0 ou menos | `Suspenso (Ban)` |

**Chance de título (2026)**
- O que falta disputar vem do Calendário (`files/2026/calendar.csv`): uma Sessão sem CSV de resultado é pendente, mesmo que a data já tenha passado.
- Pontos máximos (`max_points`): pontos atuais + os pontos do 1º lugar em cada Sessão pendente. Para equipes, do 1º e do 2º lugar (só do 1º se a equipe tiver um único piloto).
- Status no título:

| Situação | Status |
|---|---|
| Pontos atuais maiores que os Pontos máximos de todos os rivais | `Campeao` |
| Pontos máximos menores que os pontos atuais do líder | `Eliminado` |
| Todo o resto, inclusive empate exato nos Pontos máximos | `Na disputa` |

- Sem Sessões pendentes, o 1º da classificação é `Campeao` e os demais, `Eliminado`.
- A Chance de título (`championship_probability`, em %) vem de 10.000 simulações das Sessões pendentes. Em cada Corrida pendente, cada piloto sorteia uma das posições que já fez em Corridas de 2026, e a ordem de chegada é a ordenação desses sorteios (posições iguais são desempatadas por sorteio). Numa Sprint pendente, o sorteio é entre as posições em Sprints. Quem não tem nenhuma Sessão do tipo sorteia das posições do outro tipo. O campeão de cada simulação sai por pontos, depois vitórias em GP, depois pódios, depois sorteio.
- Entra na simulação todo piloto com alguma sessão disputada em 2026. Ele participa de cada Sessão pendente com a sua taxa de presença: Corridas que disputou / Corridas disputadas na temporada (quem só correu Sprints usa a razão sobre todas as sessões).
- Punições futuras não são sorteadas. Um piloto com a Superlicença zerada fica fora da primeira Corrida pendente (Suspensão), a menos que já tenha havido uma Corrida disputada depois da punição que zerou a Superlicença. Depois de cumprida, só uma nova punição gera outra Suspensão. A Suspensão não muda os Pontos máximos nem o status.
- No campeonato de construtores, os pontos simulados de cada piloto vão para a equipe atual dele (a da sessão mais recente).
- `Eliminado` sempre tem 0% e `Campeao` sempre 100%. `expected_points` é a média dos pontos finais nas simulações.
- A semente da simulação vem dos dados: enquanto os CSVs não mudam, a resposta é sempre a mesma.
- `probability_reason` traz o Motivo da Chance de título: uma frase em PT-BR montada por templates a partir dos mesmos dados, então os mesmos CSVs dão sempre o mesmo Motivo. O rival de referência é o líder da classificação; o próprio líder se compara com o 2º. O template segue esta ordem:
  - Sem Sessões pendentes: a posição final e a distância para o campeão. Se a posição foi decidida no desempate, diz com quem empatou em pontos e se ganhou ou perdeu por vitórias ou por pódios.
  - `Eliminado`: os Pontos máximos (vencendo todas as Sessões pendentes; para equipes, fazendo 1º e 2º, ou só vencendo, com um único piloto) abaixo dos pontos do líder.
  - `Campeao` antes da última Sessão: nenhum rival alcança mais os seus pontos, com os Pontos máximos do mais próximo.
  - `Na disputa`, do caso mais específico para o mais geral:
    - Pontos máximos exatamente iguais aos pontos do líder: só alcança o líder vencendo todas as Sessões pendentes (para equipes, fazendo 1º e 2º, ou só vencendo, com um único piloto) e ainda dependeria do desempate (vitórias, depois pódios).
    - Chance de título exibida como 0,0 (quem não lidera): quase nunca é campeão nas simulações, com os pontos que precisaria tirar do líder nas Sessões pendentes.
    - Chance de título exibida como 100,0 (o líder, ainda sem ser `Campeao`): é campeão em quase todas as simulações, com os pontos que o 2º precisaria tirar nas Sessões pendentes.
    - Os demais: a distância para o líder (ou, para o líder, a vantagem sobre o 2º), as Sessões pendentes e os pontos médios nas simulações, os seus e os do rival.
  - Só para quem está `Na disputa`, depois da frase principal, entram as frases dos fatores que mexem na porcentagem sem aparecer no JSON: primeiro a Suspensão ("Fica fora da próxima Corrida por Suspensão."; na equipe, citando os pilotos atuais suspensos: "Ana fica fora da próxima Corrida por Suspensão.") e depois, só para pilotos, a presença abaixo de 100% ("Disputou 12 das 18 Corridas, então nas simulações corre só parte das Sessões pendentes.", com "Sessões" no lugar de "Corridas" para quem só correu Sprints). `Campeao` e `Eliminado` não recebem essas frases, porque elas não mudam a situação.
  - Os números do texto seguem o padrão brasileiro ("10.000", "509,5", "6º"); os campos numéricos do JSON não mudam.

## Exemplos de Uso e Respostas

Os valores abaixo são do estado atual dos dados (temporada 2026, até o GP de Singapura).

### 1. Informações da API
`GET /`

```json
{
  "name": "Tiltados API",
  "version": "v2.26.1026",
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

### 3. Classificação de Pilotos
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

### 4. Classificação de Construtores
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

### 5. Status da Superlicença (2026)
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

### 6. Punições da Superlicença (2026)
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

Cada punição precisa apontar para um `driver_id` e um `race_id` existentes em 2026; caso contrário, o endpoint retorna erro indicando a linha do `punishments.csv`.

### 7. Chance de Título dos Pilotos (2026)
`GET /load/2026/prediction/drivers`

Valores após o GP dos Estados Unidos, com 5 Corridas pendentes (os 3 primeiros da lista):

```json
[
  {
    "position": 1,
    "driver_id": 5,
    "driver_name": "Matheus",
    "team_id": 7,
    "team_name": "Visa Cash App Racing Bulls",
    "points": 403,
    "max_points": 528,
    "status": "Na disputa",
    "championship_probability": 100.0,
    "expected_points": 509.5,
    "probability_reason": "Ainda não é Campeão pela matemática, mas é campeão em quase todas as 10.000 simulações: Yohan precisaria tirar 89 pontos em 5 Sessões pendentes."
  },
  {
    "position": 2,
    "driver_id": 7,
    "driver_name": "Yohan",
    "team_id": 1,
    "team_name": "Red Bull",
    "points": 314,
    "max_points": 439,
    "status": "Na disputa",
    "championship_probability": 0.0,
    "expected_points": 394.3,
    "probability_reason": "Ainda está na disputa pela matemática, mas quase nunca é campeão nas 10.000 simulações: precisaria tirar 89 pontos de Matheus em 5 Sessões pendentes."
  },
  {
    "position": 3,
    "driver_id": 8,
    "driver_name": "Douglas",
    "team_id": 6,
    "team_name": "Mercedes-AMG Petronas",
    "points": 223,
    "max_points": 348,
    "status": "Eliminado",
    "championship_probability": 0.0,
    "expected_points": 279.4,
    "probability_reason": "Mesmo vencendo as 5 Sessões pendentes, chega a no máximo 348 pontos, abaixo dos 403 de Matheus."
  }
]
```

Yohan ainda está `Na disputa` pela matemática, mas aparece com 0% porque, nas Corridas de 2026, Matheus nunca terminou abaixo do 6º lugar. Pontuando em todas as 5 Corridas, Matheus perde no máximo 17 pontos por Corrida para Yohan (25 contra 8), ou 85 no total, menos que os 89 de vantagem. Yohan só seria campeão com Matheus fora dos pontos em alguma Corrida, o que praticamente não acontece nos sorteios.

### 8. Chance de Título dos Construtores (2026)
`GET /load/2026/prediction/teams`

Valores após o GP dos Estados Unidos (os 2 primeiros da lista):

```json
[
  {
    "position": 1,
    "team_id": 7,
    "team_name": "Visa Cash App Racing Bulls",
    "points": 588,
    "max_points": 803,
    "status": "Na disputa",
    "championship_probability": 100.0,
    "expected_points": 740.8,
    "probability_reason": "Ainda não é Campeã de Construtores pela matemática, mas é campeã em quase todas as 10.000 simulações: a Red Bull precisaria tirar 112 pontos em 5 Sessões pendentes."
  },
  {
    "position": 2,
    "team_id": 1,
    "team_name": "Red Bull",
    "points": 476,
    "max_points": 691,
    "status": "Na disputa",
    "championship_probability": 0.0,
    "expected_points": 595.8,
    "probability_reason": "Ainda está na disputa pela matemática, mas quase nunca é campeã nas 10.000 simulações: precisaria tirar 112 pontos da Visa Cash App Racing Bulls em 5 Sessões pendentes."
  }
]
```

## Estrutura do Projeto

```text
tiltados_api/
|-- .github/workflows/      # CI/CD: testes e deploy automático (deploy.yml)
|-- deploy/                 # Scripts do servidor (preparação única e publicação)
|-- files/
|   |-- 2025/               # CSVs consolidados da temporada 2025
|   |-- 2026/               # CSVs de cada sessão da temporada 2026 (+ scores.csv e calendar.csv)
|   `-- super_license/      # Arquivo de punições da superlicença
|-- scripts/
|   |-- 2025/               # Módulos de extração e cálculo de 2025
|   |-- 2026/               # Módulos de extração e cálculo de 2026
|   |   `-- common.py       # LOCATION_MAP, padrão de nome e leitura dos CSVs de sessão
|   `-- errors.py           # DataError e validação dos CSVs (arquivo, coluna, valor)
|-- tests/                  # Testes automatizados (pytest)
|-- main.py                 # Aplicação FastAPI, cache e definição de rotas
|-- pytest.ini              # Configuração do pytest
|-- requirements.txt        # Dependências do projeto
|-- requirements-dev.txt    # Dependências de desenvolvimento (testes)
`-- README.md               # Documentação do projeto
```
