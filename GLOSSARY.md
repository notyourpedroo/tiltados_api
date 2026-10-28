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
O piloto em 1º na classificação de pilotos depois da última Sessão do Calendário, com desempate por pontos, depois vitórias em Corridas, depois pódios (Corridas e Sprints), depois mais 2ºs lugares em Corridas, mais 3ºs, e assim por diante, e por fim quem conseguiu primeiro o seu melhor resultado em Corridas. Passa a ser chamado Campeão assim que nenhum rival alcança mais os seus pontos.
_Avoid_: vencedor da temporada

**Campeão de Construtores**:
A equipe em 1º na classificação de construtores depois da última Sessão do Calendário, com o mesmo desempate do Campeão. Passa a ser chamada assim que nenhuma rival alcança mais os seus pontos. Numa frase sobre a equipe, concorda com ela: "Campeã de Construtores", "campeã".

**Pontos máximos**:
Os pontos atuais de um piloto ou equipe somados a tudo que ainda dá para ganhar nas Sessões pendentes.
_Avoid_: teto, pontuação possível

**Eliminado**:
Piloto ou equipe cujos Pontos máximos são menores que os pontos atuais do líder; não pode mais ser campeão.

**Chance de título**:
A estimativa, em porcentagem, de um piloto ou equipe terminar como campeão, obtida simulando as Sessões pendentes.
_Avoid_: odds, probabilidade de campeão

**Motivo da Chance de título**:
A frase que explica por que um piloto ou equipe tem a sua Chance de título: pela matemática, quando já é Campeão ou Eliminado, ou pela simulação, quando ainda está na disputa. No dia a dia, só "Motivo".
_Avoid_: justificativa, explicação

**Ganho mínimo**:
Os pontos que o líder ainda soma nas Sessões pendentes repetindo, em cada uma, o pior resultado que já fez na temporada naquele tipo de Sessão. Para uma equipe, a soma do Ganho mínimo dos seus pilotos atuais.

**Argumento do pior resultado**:
O Motivo de quem está na disputa com Chance de título de 0% ou 100%: mesmo com o rival somando tudo o que ainda pode, o líder fica à frente só com o seu Ganho mínimo. Só vale quando o líder (ou todos os pilotos da equipe líder) disputou todas as Corridas.

## Superlicença

**Superlicença**:
O saldo disciplinar de cada piloto na temporada: começa com 12 pontos e perde pontos a cada punição.
_Avoid_: carteira, licença

**Suspensão**:
A próxima Corrida que um piloto perde por ter a Superlicença zerada; cumprida, ele volta sem nova Suspensão até sofrer outra punição.
_Avoid_: ban, gancho

**Suspensão a cumprir**:
A Suspensão de um piloto cuja Superlicença zerou e que ainda não teve uma Corrida disputada depois da Sessão da punição que a zerou. Uma Sprint não cumpre a Suspensão. É a mesma na Superlicença e na Chance de título.

**Suspensão cumprida**:
A Suspensão de um piloto que já teve uma Corrida disputada depois da Sessão da punição que zerou a Superlicença. O saldo continua zerado, então a próxima punição gera uma nova Suspensão a cumprir.
