# Fluxo de trabalho

Toda mudança chega à `main` por **issue → branch → PR → revisão → merge**. A `main` é protegida (vale também para a conta do dono, que os agentes usam): push direto é recusado, e o merge exige PR com o check **`Testar e empacotar`** verde num branch atualizado com a `main`.

**O merge é a publicação.** O push na `main` dispara o job `Publicar no servidor` (`.github/workflows/deploy.yml`), que põe a API em produção em 1 a 2 minutos.

## Papéis

- **Implementador**: o subagente (ou a sessão) que pega a issue e vai até o PR aberto. Pronto quando devolve a URL do PR; o merge não é dele.
- **Sessão principal**: revisa e faz o merge. Quando ela mesma implementou, faz os dois papéis.

## Implementador

1. **Issue:** pegue uma issue `ready-for-agent` sem bloqueador aberto (`issue_dependencies_summary.blocked_by == 0`; consultas em `docs/agents/issue-tracker.md`). Um bloqueador só fecha com o merge do PR dele, então todo trabalho parte do `origin/main`.
2. **Branch:** `git fetch origin` e `git switch -c tipo/descricao-curta origin/main` (ex.: `feat/punicoes-por-temporada`).
   Num worktree de subagente, o worktree nasce no commit em que a sessão estava, não no `origin/main`: o primeiro passo é `git fetch origin && git reset --hard origin/main`, e antes do push `git branch -m tipo/descricao-curta`.
3. **Commits:** cada um com sentido próprio, porque entram na `main` um a um (merge por rebase), e no padrão que o hook `.githooks/commit-msg` confere (Conventional Commits, em português sem acentos, sem co-autoria do Claude). O hook vale em todo worktree do clone que rodou `git config core.hooksPath .githooks`.
   A mensagem vai num arquivo novo com o número da issue no nome (ex.: `commit-msg-38a.txt`, no scratchpad) e entra com `git commit -F <arquivo>`: o scratchpad é compartilhado entre tarefas, e mensagem inline quebra nas aspas do shell.
4. **Verificação local:** `ruff check .` e `pytest`, os dois passos do CI, verdes.
   O worktree de subagente não tem venv: rode a partir dele com o venv do checkout principal, `E:\Dev\Code\tiltados_api\.venv\Scripts\ruff check .` e `E:\Dev\Code\tiltados_api\.venv\Scripts\python -m pytest -q`.
   Scripts Python ad hoc (conferir dados, imprimir respostas) rodam com `python -X utf8`, para que os acentos dos nomes (`José`) saiam certos no console do Windows.
5. **PR:** `git push -u origin <branch>` e `gh pr create --base main --body-file <arquivo>`, com o título no padrão dos commits e, no corpo, resumo, evidência antes/depois, risco do merge e `Closes #<issue>`. Corpos e comentários no GitHub vão sempre por `--body-file` e em português com acentos; o "sem acentos" vale só para as mensagens de commit.
6. **Entrega:** devolva a URL do PR.

## Revisão (sessão principal)

Esta é a revisão do repositório: ela substitui o passo `code-review` dos skills (como o `implement-spec`). Confira os quatro itens e registre o resultado num comentário no PR (`gh pr comment <pr> --body-file <arquivo>`), um item por linha, com ✅ ou o achado:

- **CI:** `gh pr checks <pr> --required` com `Testar e empacotar` em `pass`.
- **Spec:** cada critério de aceite da issue atendido, e o diff (`gh pr diff <pr>`) dentro do escopo dela.
- **Padrões:** `CODING_STANDARDS.md` inteiro, os termos do `GLOSSARY.md` e as ADRs de `docs/adr/` que tocam a área.
- **Tela:** a API não tem tela; o que o site enxerga é cobrado em "Contrato com o site" do `CODING_STANDARDS.md`.

## Merge

O merge publica em produção, e a sessão principal o conduz até o fim sem pedir o OK do usuário: com a revisão registrada e os quatro itens em ✅, ela mergeia e confere o `Publicar no servidor` verde (autorização do dono em 2026-11-07).

- **Tudo conferido:** `gh pr merge <pr> --rebase --delete-branch`. Cada commit do branch entra na `main` como está, então cada um precisa estar no padrão e fazer sentido sozinho; correções da revisão entram como commits próprios (`fix(...)`, `docs(...)`), não como "ajustes da revisão". Depois, no checkout principal: `git switch main && git pull --ff-only`, e confira `git worktree list` e `git branch`: o worktree do subagente costuma já ter sido removido; o que sobrar sai com `git worktree remove --force <worktree>` e `git branch -D <branch>` (o rebase dá SHAs novos aos commits, então `-d` não reconhece o branch como mergeado).
- **Branch desatualizado** (outro PR entrou antes): `gh pr update-branch <pr> --rebase`, esperar o CI de novo e só então mergear. Sem `--rebase`, o GitHub põe um merge commit no branch, e ele iria para a `main`.
- **Item falhou:** um comentário no PR por achado, e o PR volta ao implementador, que corrige no mesmo branch.
- **Dúvida que só o usuário resolve:** o PR espera, e a sessão pergunta ao usuário.

## Spec com tickets

Cada ticket (sub-issue da spec) é uma issue comum deste fluxo: um branch e um PR por ticket, a partir do `origin/main`, sem branch de integração nem PR da spec. Os PRs fecham os tickets; a spec mãe fecha à mão (`gh issue close <spec> --comment ...`) depois do merge do último ticket e do `Publicar no servidor` verde, com um comentário que liga os PRs e o deploy.

Antes de marcar a spec e os tickets como `ready-for-agent`, quem os escreve confere cada número derivado (contagem, soma, total) contra a tabela ou o dado de onde ele vem: na spec #40, "225 linhas" contradizia a própria tabela, que somava 215.
