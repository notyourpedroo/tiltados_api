# Tiltados API

API REST desenvolvida em FastAPI para consolidar e servir os dados das temporadas da liga Tiltados F1: 2025, no formato consolidado, e as temporadas por Sessão, de 2026 em diante.

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

Os testes rodam sobre uma cópia de `files/` em uma pasta temporária, então podem alterar ou quebrar CSVs sem tocar nos dados reais. Eles cobrem os endpoints, a consistência dos dados (IDs, pontos, superlicença), a descoberta das temporadas pelas pastas (uma temporada montada na cópia, com e sem Sessão disputada), as regras de 2026 (IDs do Cadastro iguais aos de 2025, equipe atual do piloto, recarga do cache) e as mensagens de erro para CSVs inválidos.

Toda rota da API entra sozinha nos testes de resposta. Uma rota nova também precisa aparecer na tabela de "Endpoints Disponíveis" e na lista `HEALTH_URLS` de `deploy/publicar.sh`, senão os testes falham.

Um dos testes exige que toda Sessão de `files/2026/` (nos nomes dos arquivos e no Calendário) esteja no Cadastro de Sessões (`files/sessions.csv`). Ao adicionar um GP novo, ou uma Sprint num GP que não tinha, cadastre a Sessão antes.

## Atualização Automática dos Dados

Os dados são lidos dos CSVs em `files/` e guardados em cache. O cache é invalidado sozinho sempre que um CSV é adicionado, editado ou removido, então **não é preciso reiniciar o servidor** para ver os dados novos.

Isso vale para qualquer arquivo em `files/` (2025, 2026, `super_license` e o Cadastro), inclusive para uma temporada nova: a pasta `files/{ano}/` com o Calendário aparece na API sem reiniciar. O cache guarda cada recurso de cada temporada separado. Mudanças no código Python (`main.py` ou `scripts/`) ainda exigem reiniciar o servidor, ou usar `--reload`.

Se algum CSV estiver com problema (arquivo ausente, coluna faltando, valor inválido), os endpoints que dependem dele retornam HTTP 500 com a causa em `detail`, indicando o arquivo e a linha a corrigir. Um erro nos CSVs de uma temporada não afeta as rotas das outras (o Cadastro é o mesmo para todas as temporadas por Sessão, então um erro nele afeta todas elas). Por exemplo:

```json
{"detail": "2026/japao_race_20260323.csv, linha 2: coluna 'Grid' com valor 'X' (esperado um número inteiro)."}
```

## Adicionando uma Nova Corrida (2026)

1. Salve o CSV da sessão em `files/2026/` seguindo o padrão de nome:

   ```
   {local}_{race|sprint}_{YYYYMMDD}.csv
   ```

   Exemplos: `singapura_race_20261005.csv`, `silverstone_sprint_20260728.csv`.

   - `{local}` deve estar em minúsculas e sem acentos, igual à coluna `local` do Cadastro de Sessões (ex.: `spa` para o GP da Bélgica).
   - `race` ou `sprint` define o tipo da sessão.
   - `YYYYMMDD` é a data da sessão. A data só define a ordem das sessões: salvar um CSV com data anterior às outras não muda o `race_id` de nenhuma.

   O `local` e o tipo do nome do arquivo precisam estar no Cadastro de Sessões (`files/sessions.csv`, colunas `race_id,local,tipo,race_name,race_location`). É de lá que saem o `race_id`, o nome do GP e a cidade que a API devolve, os mesmos em todas as temporadas a partir de 2026. A coluna `tipo` é `race` ou `sprint`, e `race_name` é o nome do GP sem sufixo: na Sprint, a API acrescenta ` (SPRINT)` (ex.: `GP da China (SPRINT)`). Para cadastrar uma Sessão nova (um GP inédito ou uma Sprint num GP que não tinha), acrescente uma linha com o próximo `race_id` livre, por exemplo:

   ```
   35,portugal,race,GP de Portugal,Portimão
   ```

   Não troque o `race_id` de uma Sessão já cadastrada, porque os resultados e as punições guardados apontam para ele. Um local e tipo fora do Cadastro faz os endpoints de 2026 que dependem das Sessões retornarem erro indicando o arquivo, por exemplo:

   ```json
   {"detail": "2026/japao_sprint_20260323.csv: local 'japao' com tipo 'sprint' no nome do arquivo (esperado uma Sessão do Cadastro)."}
   ```

   Um `race_id` repetido, o mesmo local e tipo em duas linhas, uma coluna faltando, um `race_id` que não é inteiro ou um tipo diferente de `race` e `sprint` também viram erro com o arquivo e a linha.

2. O CSV deve ter o cabeçalho e as colunas do exportado do site de resultados:

   ```
   Pos.,Piloto,Equipe,Grid,Paradas,Melhor tempo,Tempo,Pts.,tipo de piloto
   ```

   A leitura para na primeira linha em branco, na que começa com `,,,,` ou na que começa com `Tempo,`. Tudo que vier depois disso é ignorado.

3. Confira se todo piloto e toda equipe do CSV estão no Cadastro (`files/drivers.csv`, colunas `driver_id,driver_name`, e `files/teams.csv`, colunas `team_id,team_name`). O Cadastro vale para todas as temporadas a partir de 2026 e é de lá que saem o ID e o nome que a API devolve. Para cadastrar um piloto ou equipe novos, acrescente uma linha com o próximo ID livre e o nome escrito exatamente como nas colunas `Piloto` e `Equipe` do CSV (ex.: `12,Zeca`). Não troque o ID de quem já está cadastrado, porque os resultados e as punições guardados apontam para ele. Um nome fora do Cadastro faz os endpoints de 2026 que dependem dele retornarem erro indicando o arquivo e a linha, por exemplo:

   ```json
   {"detail": "2026/japao_race_20260323.csv, linha 4: coluna 'Piloto' com valor 'Mateus' (esperado um piloto do Cadastro)."}
   ```

   Um ID ou nome repetido no Cadastro, uma coluna faltando ou um ID que não é inteiro também viram erro com o arquivo e a linha. A temporada 2025 não usa o Cadastro: continua lendo `files/2025/`, com os mesmos IDs.

4. Pronto. Corridas, resultados, pilotos e equipes de 2026 são derivados da pasta `files/2026/` e do Cadastro (pilotos, equipes e Sessões). Se o export vier com o nome `Pessoa` (placeholder do site) ou vazio no lugar do piloto, troque pelo nome real antes de salvar. Caso contrário, os endpoints de 2026 que dependem de pilotos retornam erro indicando o arquivo e a linha a corrigir.

   A sessão precisa estar no Calendário (`files/2026/calendar.csv`, colunas `local,tipo,data`), com o mesmo `{local}` e o mesmo tipo do nome do arquivo. No Calendário, todo `local` e tipo precisa estar no Cadastro de Sessões, para um nome digitado errado não virar uma Sessão pendente para sempre; senão, as rotas de Chance de título retornam erro com o arquivo e a linha. A ligação é só por local e tipo: a data do arquivo de resultado prevalece sobre a data prevista do Calendário. Uma sessão fora do Calendário faz as rotas `/load/2026/prediction/drivers` e `/load/2026/prediction/teams` retornarem erro indicando o arquivo e a linha a adicionar.

   Se a corrida tiver punição de Superlicença, registre também em `files/super_license/punishments.csv` (colunas `season_year,driver_id,race_id,deduction_points,penalty_reason`).

5. Faça o commit e o push na `main`. O GitHub Actions roda os testes e publica a corrida nova no servidor em cerca de 1 a 2 minutos. Os CSVs de produção vêm sempre do Git: não edite arquivos direto no servidor, porque cada publicação substitui a pasta `files/`.

A pontuação de cada posição vem de `files/2026/scores.csv` (colunas `position`, `points`, `is_sprint`).

Os passos valem para qualquer temporada por Sessão: em 2027, os CSVs vão para `files/2027/`.

## Abrindo uma Temporada Nova

De 2026 em diante, toda temporada usa o formato por Sessão e o mesmo código (a decisão está em `docs/adr/0001-temporadas-por-sessao-com-cadastro-global.md`). Uma temporada existe quando a pasta `files/{ano}/` tem o Calendário: não há lista de temporadas no código. Para abrir 2027:

1. Crie `files/2027/` com o Calendário (`calendar.csv`, colunas `local,tipo,data`, todas as Sessões previstas) e a pontuação (`scores.csv`, colunas `score_id,position,points,is_sprint`; copie a de 2026 se a pontuação não mudar).
2. Cadastre em `files/sessions.csv` toda Sessão do Calendário que ainda não está no Cadastro (um GP inédito ou uma Sprint num GP que não tinha), com o próximo `race_id` livre. Pilotos e equipes estreantes entram em `files/drivers.csv` e `files/teams.csv` antes do primeiro resultado. Os IDs do Cadastro valem para todas as temporadas: não crie um ID novo para quem já está cadastrado.
3. Suba a `API_VERSION` em `main.py`: o primeiro número é a quantidade de temporadas, então abrir 2027 leva a versão para `v3.{YY}.{MMDD}`. Acrescente as rotas de 2027 à lista `HEALTH_URLS` de `deploy/publicar.sh`.
4. Faça o commit e o push. A temporada aparece em `seasons` na rota `/` e responde em `/load/2027/drivers`, `teams`, `races`, `results`, `standings/drivers` e `standings/teams`.

Até a primeira Sessão disputada, essas rotas respondem lista vazia (`[]`), sem erro. Depois, cada Sessão entra como em "Adicionando uma Nova Corrida", na pasta do ano. Superlicença, punições e Chance de título ainda só existem para 2026.

## Endpoints Disponíveis

O parâmetro `{season}` aceita o ano de qualquer temporada servida pela API, listadas em `seasons` na rota `/`: hoje, `2025` e `2026`. Uma temporada inexistente responde `404`, com a causa em `detail`:

```json
{"detail": "Temporada 2027 não encontrada. Temporadas disponíveis: 2025, 2026."}
```

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
- Desempate (2026): pontos; vitórias em Corridas; pódios (Corridas e Sprints); mais 2ºs lugares em Corridas, depois mais 3ºs, e assim por diante; quem conseguiu primeiro (na Sessão mais antiga) o seu melhor resultado em Corridas; e, se ainda empatar (por exemplo, nenhum dos dois disputou Corridas), a ordem do ID. Nos construtores, a contagem soma as posições dos pilotos da equipe em cada Corrida, e o melhor resultado é o de qualquer piloto da equipe.
- Desempate (2025): pontos, depois vitórias em Corridas, depois pódios, e então a ordem do ID. A classificação de 2025 fica como foi publicada.
- `races` conta sessões disputadas, ou seja, corridas e sprints somadas. `wins` conta apenas corridas (GP); `sprint_wins` conta apenas sprints.

**Superlicença (2026)**
- Cada piloto começa com 12 pontos.
- Cada punição em `files/super_license/punishments.csv` deduz pontos (`deduction_points`).
- Status conforme os pontos restantes e a Suspensão:

| Situação | Status |
|---|---|
| 9 a 12 | `Regular` |
| 5 a 8 | `Atencao` |
| 1 a 4 | `Alerta Critico` |
| 0 ou menos, com Suspensão a cumprir | `Suspenso` |
| 0 ou menos, Suspensão cumprida | `Suspensao cumprida` |

- A Suspensão vem da última punição que deixou o saldo em 0 ou menos e fica cumprida quando há uma Corrida disputada depois da Sessão dessa punição (uma Sprint não cumpre). O saldo continua zerado depois de cumprida, então uma nova punição gera outra Suspensão e o status volta a `Suspenso`.
- A Chance de título usa o mesmo cálculo: quem está `Suspenso` aqui fica fora da primeira Corrida pendente na simulação.

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
- A Chance de título (`championship_probability`, em %) vem de 10.000 simulações das Sessões pendentes. Em cada Corrida pendente, cada piloto sorteia uma das posições que já fez em Corridas de 2026, e a ordem de chegada é a ordenação desses sorteios (posições iguais são desempatadas por sorteio). Numa Sprint pendente, o sorteio é entre as posições em Sprints. Quem não tem nenhuma Sessão do tipo sorteia das posições do outro tipo. O campeão de cada simulação sai pelo mesmo desempate da classificação: pontos; vitórias em Corridas; pódios (Corridas e Sprints); mais 2ºs lugares em Corridas, depois mais 3ºs, e assim por diante; quem conseguiu primeiro o seu melhor resultado em Corridas; e, por fim, a ordem do ID. A contagem junta as posições das Corridas disputadas com as das Corridas pendentes simuladas, e as Sessões pendentes contam como posteriores às disputadas, na ordem do Calendário, para "quem conseguiu primeiro". Nos construtores, a contagem soma as posições dos pilotos da equipe em cada Corrida (nas simuladas, as dos seus pilotos atuais), e o melhor resultado é o de qualquer piloto da equipe. Assim, o campeão de cada simulação nunca sai por sorteio.
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
    - Pontos máximos exatamente iguais aos pontos do líder: só alcança o líder vencendo todas as Sessões pendentes (para equipes, fazendo 1º e 2º, ou só vencendo, com um único piloto) e ainda dependeria do desempate.
    - Chance de título exibida como 0,0 (quem não lidera) ou 100,0 (o líder, ainda sem ser `Campeao`, contra o 2º): primeiro vale o argumento do pior resultado do líder. Em cada tipo de Sessão pendente, o líder repete a pior posição que já fez em 2026 naquele tipo (quem nunca disputou o tipo usa o outro, como a simulação); a soma desses pontos nas Sessões pendentes é o seu ganho mínimo. Se os pontos do líder mais o ganho mínimo passam dos Pontos máximos do rival (para o líder, de todo rival `Na disputa`), o Motivo cita o pior resultado e quanto o rival tira no máximo da vantagem ("Matheus nunca terminou abaixo do 6º em Corridas de 2026; repetindo isso nas 5 Sessões pendentes, perde no máximo 85 pontos, menos que os 89 de vantagem."; quando o pior resultado é a vitória, "venceu todas as Corridas de 2026"). O texto cita só os tipos de Sessão que o líder disputou, entre os usados pelas Sessões pendentes. Nas equipes, o ganho mínimo da líder é a soma do ganho mínimo de cada piloto atual dela, e o texto cita o pior resultado de cada um. O argumento só entra quando o líder tem 100% de presença (nas equipes, todos os pilotos atuais da líder, que precisa ter pelo menos um).
    - Sem o argumento, o texto genérico: com 0,0, quase nunca é campeão nas simulações, com os pontos que precisaria tirar do líder nas Sessões pendentes; com 100,0, é campeão em quase todas as simulações, com os pontos que o 2º precisaria tirar.
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
  "version": "v2.26.1028",
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
    "deducted_points": 5,
    "remaining_points": 7,
    "punishments_count": 3,
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

Um piloto com o saldo em 0 ou menos aparece com `status` `Suspenso` (Suspensão a cumprir) ou `Suspensao cumprida`; nos dados atuais, nenhum piloto chegou a zerar a Superlicença.

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
    "probability_reason": "Ainda não é Campeão pela matemática, mas nunca terminou abaixo do 6º em Corridas de 2026; repetindo isso nas 5 Sessões pendentes, Yohan tira no máximo 85 dos 89 pontos de vantagem."
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
    "probability_reason": "Ainda está na disputa pela matemática, mas Matheus nunca terminou abaixo do 6º em Corridas de 2026; repetindo isso nas 5 Sessões pendentes, perde no máximo 85 pontos, menos que os 89 de vantagem."
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

O `probability_reason` já explica por que Yohan, ainda `Na disputa` pela matemática, aparece com 0%: é o argumento do pior resultado de Matheus, montado pela API a cada Sessão disputada.

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

Aqui o Motivo fica no texto genérico porque o Gabriel, piloto atual da Visa Cash App Racing Bulls, disputou 14 das 17 Corridas: sem 100% de presença de todos os pilotos da líder, o argumento do pior resultado não entra.

## Estrutura do Projeto

```text
tiltados_api/
|-- .github/workflows/      # CI/CD: testes e deploy automático (deploy.yml)
|-- deploy/                 # Scripts do servidor (preparação única e publicação)
|-- docs/adr/               # Decisões de arquitetura (ADRs)
|-- files/
|   |-- 2025/               # CSVs consolidados da temporada 2025
|   |-- 2026/               # CSVs de cada sessão da temporada 2026 (+ scores.csv e calendar.csv); 2027 em diante, igual
|   |-- super_license/      # Arquivo de punições da superlicença
|   |-- drivers.csv         # Cadastro de pilotos (2026 em diante)
|   |-- teams.csv           # Cadastro de equipes (2026 em diante)
|   `-- sessions.csv        # Cadastro de Sessões: race_id, nome do GP e cidade (2026 em diante)
|-- scripts/
|   |-- 2025/               # Módulos de extração e cálculo de 2025
|   |-- 2026/               # Módulos das temporadas por Sessão (2026 em diante)
|   |   |-- common.py       # Padrão de nome e leitura dos CSVs de sessão
|   |   `-- load_registry.py # Leitura e validação do Cadastro (pilotos, equipes e Sessões)
|   `-- errors.py           # DataError e validação dos CSVs (arquivo, coluna, valor)
|-- tests/                  # Testes automatizados (pytest)
|-- main.py                 # Aplicação FastAPI, cache e definição de rotas
|-- pytest.ini              # Configuração do pytest
|-- requirements.txt        # Dependências do projeto
|-- requirements-dev.txt    # Dependências de desenvolvimento (testes)
`-- README.md               # Documentação do projeto
```
