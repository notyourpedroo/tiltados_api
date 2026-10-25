# Tiltados F1

Liga de F1 entre amigos. A API consolida os resultados de cada temporada e calcula classificações, Superlicença e chances de título.

## Calendário

**Etapa**:
Um fim de semana de GP (ex.: GP de São Paulo), com uma Corrida e, opcionalmente, uma Sprint.
_Avoid_: GP (quando se quer dizer o fim de semana), rodada

**Sessão**:
Uma Corrida ou uma Sprint de uma Etapa. É a unidade que gera pontos.
_Avoid_: race (para falar das duas), prova

**Corrida**:
A Sessão principal de uma Etapa, a que conta como vitória em GP.
_Avoid_: GP, race principal

**Sprint**:
A Sessão curta de uma Etapa, com pontuação menor.

**Calendário**:
A lista de todas as Sessões previstas da temporada, disputadas ou não.

**Sessão disputada**:
Uma Sessão do Calendário que já tem resultado registrado.

**Sessão pendente**:
Uma Sessão do Calendário ainda sem resultado registrado, mesmo que a data já tenha passado.
_Avoid_: sessão futura

## Campeonato

**Campeão**:
O piloto em 1º na classificação de pilotos depois da última Sessão do Calendário, com desempate por pontos, depois vitórias em Corridas, depois pódios. Passa a ser chamado Campeão assim que nenhum rival alcança mais os seus pontos.
_Avoid_: vencedor da temporada

**Campeão de Construtores**:
A equipe em 1º na classificação de construtores depois da última Sessão do Calendário, com o mesmo desempate do Campeão. Passa a ser chamada assim que nenhuma rival alcança mais os seus pontos.

**Pontos máximos**:
Os pontos atuais de um piloto ou equipe somados a tudo que ainda dá para ganhar nas Sessões pendentes.
_Avoid_: teto, pontuação possível

**Eliminado**:
Piloto ou equipe cujos Pontos máximos são menores que os pontos atuais do líder; não pode mais ser campeão.

**Chance de título**:
A estimativa, em porcentagem, de um piloto ou equipe terminar como campeão, obtida simulando as Sessões pendentes.
_Avoid_: odds, prediction, probabilidade de campeão

## Superlicença

**Superlicença**:
O saldo disciplinar de cada piloto na temporada: começa com 12 pontos e perde pontos a cada punição.
_Avoid_: carteira, licença

**Suspensão**:
A próxima Corrida que um piloto perde por ter a Superlicença zerada; cumprida, ele volta sem nova Suspensão até sofrer outra punição.
_Avoid_: ban, gancho
