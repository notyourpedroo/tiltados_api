# Temporadas por Sessão com o mesmo código e um Cadastro global; 2025 fica consolidada

De 2026 em diante, toda temporada usa o formato por Sessão (um CSV por Corrida ou Sprint, mais o Calendário) e é servida pelo mesmo código, que recebe a pasta da temporada como parâmetro. Uma temporada existe quando a sua pasta de dados (`files/{ano}/`) tem Calendário, sem lista fixa no código. Pilotos, equipes e Sessões vêm de um Cadastro global (`files/drivers.csv`, `files/teams.csv`, `files/sessions.csv`), com IDs que valem para todas as temporadas. 2025 continua no formato consolidado (CSVs já com IDs), com os seus próprios módulos, e não usa o Cadastro: os dados dela foram publicados assim e migrá-los não traria nada à liga.

## Considered Options

- **Copiar `scripts/2026` para cada ano novo.** Descartada: duplica cerca de 1.700 linhas por temporada, e cada correção (desempate, Superlicença, Chance de título) teria de ser feita em dois lugares dali em diante, com o risco de as temporadas divergirem sem ninguém notar.
- **Um Cadastro por temporada.** Descartada: o mesmo ID mudaria de sentido entre os anos, como já aconteceu com as Sprints inéditas de 2026, que ganharam os IDs 31 a 34 pela ordem cronológica e em 2027 seriam reaproveitados por outras Sessões. Com um Cadastro só, o mesmo piloto e a mesma Sessão têm o mesmo ID em qualquer temporada, e dá para comparar carreiras e Etapas entre anos.

## Consequences

- Abrir um ano novo é uma tarefa de dados: criar `files/{ano}/` com o Calendário e a pontuação, cadastrar o que faltar e subir a `API_VERSION` (que muda o número de temporadas). Nenhuma rota é escrita.
- A pasta de código ainda se chama `scripts/2026`, embora sirva 2026 e as seguintes. O nome ficou para não misturar a mudança de comportamento com uma renomeação.
- Dois formatos convivem para sempre: uma regra nova de 2026+ não vale para 2025 (a classificação de 2025 fica como foi publicada).
