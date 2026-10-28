## Fluxo de trabalho

Toda mudança chega à `main` protegida por issue → branch → PR → revisão → merge, e o merge publica em produção. Ao pegar uma issue, abrir um PR ou revisar e mergear um PR, siga `docs/agents/workflow.md`.

## Agent skills

### Issue tracker

Issues e specs ficam no GitHub Issues do repo, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Labels padrão: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` e `docs/adr/` na raiz. See `docs/agents/domain.md`.

### Coding standards

Regras que a revisão cobra (domínio, erros de dados, módulos, testes, README, versão). See `CODING_STANDARDS.md`.
