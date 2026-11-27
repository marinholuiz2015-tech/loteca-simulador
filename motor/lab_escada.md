# Escada: sinais fracos somados x odds (jogos da Loteca, teste no tempo)

Jogos da Loteca com odd e resultado: 5166 em 381 concursos. Cobertura dos novos: chuva 1357, motivacao 2178, copa 1856.

## Cada sinal novo sozinho

| sinal | jogos | forca | acerto odd | acerto modelo | veredito |
|---|---|---|---|---|---|
| Empate da Loteca (constante) | 3484 | +0.3 | 53.6% | 53.5% | nao |
| Chuva prevista (4 mm+) | 976 | +0.7 | 54.9% | 55.0% | nao |
| Motivacao: sem nada em jogo | 1464 | +0.2 | 54.0% | 53.9% | nao |
| Motivacao: luta contra a queda | 1464 | -0.3 | 54.0% | 54.1% | nao |
| Dois sem nada em jogo | 1464 | -0.8 | 54.0% | 54.0% | nao |
| Copa em ate 4 dias (poupar) | 1283 | -1.3 | 54.9% | 54.9% | nao |

## Modelos combinados

| modelo | jogos | forca | acerto odd | acerto modelo | veredito |
|---|---|---|---|---|---|
| A) todos os KPIs juntos | 3484 | -2.3 | 53.6% | 53.2% | nao |
| B) selecao no tempo (so KPIs com forca > 1 no passado) | 3484 | -1.6 | 53.6% | 53.6% | nao |
| C) so os sinais novos | 3484 | -0.1 | 53.6% | 53.6% | nao |
| D) promissores pre-escolhidos (teto otimista) | 3484 | +1.3 | 53.6% | 53.5% | promissor |

### O que a selecao no tempo escolheu em cada bloco

- a partir do concurso 1025: Massa x mercado (manada), Especialista (Lotequeiros), Motivacao: luta contra a queda, Dois sem nada em jogo
- a partir do concurso 1045: Especialista (Lotequeiros), Motivacao: sem nada em jogo, Motivacao: luta contra a queda, Dois sem nada em jogo
- a partir do concurso 1065: Especialista (Lotequeiros), Motivacao: sem nada em jogo, Motivacao: luta contra a queda, Dois sem nada em jogo
- a partir do concurso 1085: Viagem do visitante, Motivacao: sem nada em jogo, Motivacao: luta contra a queda, Dois sem nada em jogo
- a partir do concurso 1105: Dois sem nada em jogo
- a partir do concurso 1125: nenhum (fica so a odd)
- a partir do concurso 1145: Viagem do visitante, Chuva forte, Chuva prevista (4 mm+)
- a partir do concurso 1165: Viagem do visitante
- a partir do concurso 1186: Chuva forte
- a partir do concurso 1206: Viagem do visitante
- a partir do concurso 1227: Viagem do visitante
- a partir do concurso 1247: nenhum (fica so a odd)
- a partir do concurso 1270: Viagem do visitante
