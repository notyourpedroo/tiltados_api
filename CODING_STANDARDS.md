# Padrões de código

Regras para a revisão de mudanças. As mecânicas já são cobradas pelo `ruff`, pelos testes e pelo hook de commit; aqui fica o que pede julgamento.

## Vocabulário do domínio

- Nomes no código, nos testes, no README e nos commits usam os termos do `GLOSSARY.md` (Etapa, Sessão, Corrida, Sprint, Calendário, Chance de título...). Os sinônimos marcados com _Avoid_ ficam de fora. Identificadores em inglês traduzem o termo do glossário (Calendário → `calendar`, Cadastro → `registry`); os _Avoid_ valem para o texto em português.
- Um conceito novo do domínio entra no `GLOSSARY.md` na mesma mudança que o introduz.

## Erros de dados

- Todo problema num arquivo de `files/` vira `DataError` com o caminho relativo (`display_path`) e, quando dá, a linha, no formato dos existentes: `"<arquivo>, linha N: coluna 'X' com valor 'Y' (esperado ...)."`.
- Cada mensagem nova ganha um cenário em `tests/test_errors.py`.
- Um erro num arquivo derruba só as rotas que dependem dele; o resto da API segue respondendo.

## Módulos de `scripts/sessions`

Seguem o formato dos módulos existentes:

- docstring de módulo dizendo o que o módulo calcula ou carrega;
- docstring de cada função pública listando as colunas do DataFrame retornado e os casos de `DataError`;
- import relativo com o fallback `try/except` para execução direta;
- bloco `if __name__ == "__main__"` que imprime o resultado.

## Testes

- Testam pela API HTTP (`TestClient` sobre a fixture `data_dir`), nunca funções internas.
- O valor esperado vem de um exemplo calculado à mão ou da spec, nunca recalculado do jeito que o código calcula.
- Cenários com sorteio verificam propriedades que valem para qualquer sorteio (soma 100%, 0% para `Eliminado`) ou montam dados em que o resultado não depende de sorte.
- Todo caminho novo do código tem um teste que fica vermelho quando o caminho é desligado. O implementador confirma desligando o trecho e rodando o teste; a revisão pergunta qual teste cobre cada caminho novo, e um caminho sem resposta é um achado, mesmo que o implementador tenha avisado da lacuna.

## README

Toda rota nova ou regra de negócio nova atualiza o README na mesma mudança: a tabela de endpoints, a seção "Regras de Negócio" e um exemplo de resposta com valores reais. Quando os dados reais ainda não têm o caso novo (um status que nenhum piloto atingiu, por exemplo), o exemplo é hipotético e diz que é.

## Contrato com o site

O site (`notyourpedroo/tiltados_web`) espelha os valores de `status` e os campos das respostas nos tipos dele. Uma mudança que troca, tira ou acrescenta um valor de `status` ou um campo de resposta leva junto uma issue no `tiltados_web` descrevendo a mudança. A revisão pede o link da issue; sem ele, é um achado.

## Versão da API

`API_VERSION` (em `main.py`) segue `v{temporadas}.{YY}.{MMDD}`:

- `temporadas`: quantas temporadas a API serve (2 com 2025 e 2026);
- `YY` e `MMDD`: ano, mês e dia da mudança (25/10/2026 → `v2.26.1025`).

Mudanças no mesmo dia mantêm a versão; ela só muda num dia posterior ou quando muda o número de temporadas. Nada de incremento estilo semver. Uma mudança de comportamento num dia novo sem versão nova é um achado.
