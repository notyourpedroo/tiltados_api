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
4. **Verificação local:** `ruff check .` e `pytest`, os dois passos do CI, verdes.
5. **PR:** `git push -u origin <branch>` e `gh pr create --base main`, com o título no padrão dos commits e, no corpo, resumo, evidência antes/depois, risco do merge e `Closes #<issue>`.
6. **Entrega:** devolva a URL do PR.

## Revisão (sessão principal)

Confira os quatro itens e registre o resultado num comentário no PR (`gh pr comment <pr> --body-file <arquivo>`), um item por linha, com ✅ ou o achado:

- **CI:** `gh pr checks <pr> --required` com `Testar e empacotar` em `pass`.
- **Spec:** cada critério de aceite da issue atendido, e o diff (`gh pr diff <pr>`) dentro do escopo dela.
- **Padrões:** `CODING_STANDARDS.md` inteiro, os termos do `GLOSSARY.md` e as ADRs de `docs/adr/` que tocam a área.
- **Tela:** a API não tem tela; o que o site enxerga é cobrado em "Contrato com o site" do `CODING_STANDARDS.md`.

## Merge

- **Tudo conferido:** `gh pr merge <pr> --rebase --delete-branch`. Cada commit do branch entra na `main` como está, então cada um precisa estar no padrão e fazer sentido sozinho; correções da revisão entram como commits próprios (`fix(...)`, `docs(...)`), não como "ajustes da revisão". Depois, no checkout principal: `git switch main && git pull --ff-only`, `git worktree remove` do worktree, se houver, e `git branch -D <branch>` (o rebase dá SHAs novos aos commits, então `-d` não reconhece o branch como mergeado).
- **Branch desatualizado** (outro PR entrou antes): `gh pr update-branch <pr> --rebase`, esperar o CI de novo e só então mergear. Sem `--rebase`, o GitHub põe um merge commit no branch, e ele iria para a `main`.
- **Item falhou:** um comentário no PR por achado, e o PR volta ao implementador, que corrige no mesmo branch.
- **Dúvida que só o usuário resolve:** o PR espera, e a sessão pergunta ao usuário.

## PRs do Dependabot

O merge de um PR do Dependabot põe o `dependabot[bot]` como autor do commit e na lista de Contributors. As versões que ele propõe entram por um PR próprio (`chore(deps): atualiza <pacote> de X para Y`), depois de conferido o CI do PR dele; o Dependabot fecha o PR dele sozinho quando vê a versão nova na `main`.
