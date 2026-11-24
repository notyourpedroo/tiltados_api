# Nova corrida

Roteiro para quando chega um CSV de resultado novo em `files/{ano}/`. O formato do arquivo, o Cadastro e o Calendário estão em "Adicionando uma Nova Corrida" do README. O caminho até a `main` é o de `docs/agents/workflow.md`.

## 1. Perguntar ao dono da liga, antes da issue

Só o usuário sabe duas coisas, e a resposta muda o escopo da issue:

- **Superlicença:** houve punição nesta Sessão? Para cada uma, o piloto, os pontos e o motivo, que vão para `files/super_license/punishments.csv`.
- **Placeholder:** o export trouxe `Pessoa` ou um nome vazio no lugar de um piloto? Para cada um, quem é. A troca vale para o bloco de resultados e para o de incidentes.

O passo termina com as duas respostas na conversa. "Sem punições" precisa vir do usuário: não se deduz dos incidentes do export.

## 2. Issue

Título `Adicionar o resultado do GP de <nome> de <ano>`, label `ready-for-agent`. O corpo tem:

- **Contexto:** o arquivo, a data da Corrida, as trocas de placeholder e as punições (ou "sem punições, confirmado pelo dono da liga").
- **Critérios de aceite:** CSV versionado (Sessão `<local>`/`<tipo>`); `punishments.csv` com as punições da Sessão, ou sem mudança; testes de Chance de título e exemplos do README com os dados de depois deste GP; `API_VERSION` com a data da mudança.

## 3. Dados, testes e README

1. **Dados:** o CSV, com as trocas do passo 1, e as punições, se houver.
2. **Testes:** `pytest` deixa vermelhos os testes de `tests/test_prediction.py` que têm os números dos dados reais. Os comentários de cada um mostram a conta (pontos de antes + pontos do GP), e ela é refeita para o estado novo. Um teste com o GP anterior no nome (ex.: `..._apos_o_gp_de_las_vegas`) passa a citar o GP novo. As Sessões pendentes saem sozinhas dos dados (`pending_sessions`).
3. **README:** `python -X utf8 -m scripts.readme_examples` reescreve os blocos JSON de Classificação e Chance de título. À mão ficam o texto em volta dos blocos ("até o GP de...", "Valores após o GP de...", as frases depois dos blocos 7 e 8) e a `version` do exemplo de `GET /`.
4. **Versão:** `API_VERSION` em `main.py` com a data da mudança (regra em "Versão da API" do `CODING_STANDARDS.md`).

O passo termina com `ruff check .` e `pytest` verdes.

## 4. PR

O corpo segue o do workflow.md. Na evidência entra um bloco com o estado novo do campeonato:

```text
Pilotos:      <líder> <antes> + <GP> = <agora> (<status>) | <2º> ... (máx. <Pontos máximos>)
Construtores: <líder> ... | <2ª> ...
Pendentes:    <n> Corridas (<locais>)
```

No risco do merge entra o que o site passa a mostrar, como um título decidido ou um NC que pontua (regra no `GLOSSARY.md`).
