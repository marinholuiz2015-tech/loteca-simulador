# Desgaste e calendario x forca e odds

Jogos de liga analisados: 16847 ([('Championship', 2807), ('Brasileirao A', 1987), ('Brasileirao B', 1971), ('LaLiga', 1934), ('Serie A Italia', 1931), ('Premier League', 1920), ('Ligue 1', 1668), ('Bundesliga', 1539), ('Brasileirao C', 1090)])


## Regua: forca pelo Elo - Brasil (Serie A, B e C)

| fator (mandante - visitante) | jogos testados | ganho por 1000 jogos | forca | veredito |
|---|---|---|---|---|
| descanso | 3885 | -0.23 | -1.9 | nao |
| jogos_14d | 3885 | -0.25 | -1.3 | nao |
| viagem | 3885 | -0.18 | -1.4 | nao |
| poupa | 3885 | +0.16 | +0.4 | nao |
| veio_copa | 3885 | -0.15 | -1.1 | nao |
| todos juntos | 3885 | -0.71 | -1.3 | nao |

### Efeito direto (resultado real menos o esperado pela regua, em pontos percentuais)

| situacao | jogos | vitoria do time vs esperado |
|---|---|---|
| visitante com <=3 dias de descanso e mandante com 6+ | 105 | +3.6 (z +0.8) |
| mandante com <=3 dias de descanso e visitante com 6+ | 99 | +2.5 (z +0.5) |
| mandante vai jogar copa em ate 4 dias (pode poupar) | 360 | -1.1 (z -0.4) |
| visitante vai jogar copa em ate 4 dias (pode poupar) | 368 | -2.5 (z -1.1) |
| mandante veio de jogo de copa | 377 | +0.2 (z +0.1) |
| visitante veio de jogo de copa | 416 | -0.6 (z -0.3) |
| visitante viajou mais de 2.000 km | 847 | +1.1 (z +0.8) |
| mandante com 4+ jogos em 14 dias | 179 | +5.9 (z +1.6) |
| visitante com 4+ jogos em 14 dias | 161 | +0.2 (z +0.1) |

## Regua: forca pelo Elo - Serie B e C (sem odds no mercado de dados)

| fator (mandante - visitante) | jogos testados | ganho por 1000 jogos | forca | veredito |
|---|---|---|---|---|
| descanso | 2386 | -0.76 | -1.2 | nao |
| jogos_14d | 2386 | -0.31 | -0.4 | nao |
| viagem | 2386 | -0.02 | -0.0 | nao |
| poupa | 2386 | -0.55 | -0.9 | nao |
| veio_copa | 2386 | +0.29 | +0.5 | nao |
| todos juntos | 2386 | -1.52 | -1.4 | nao |

## Regua: forca pelo Elo - Europa

| fator (mandante - visitante) | jogos testados | ganho por 1000 jogos | forca | veredito |
|---|---|---|---|---|
| descanso | 9588 | +0.05 | +0.8 | nao |
| jogos_14d | 9588 | +0.04 | +0.2 | nao |
| viagem | 9588 | -0.07 | -0.9 | nao |
| poupa | - | - | - | sem dado (fator sempre zero nesta base) |
| veio_copa | - | - | - | sem dado (fator sempre zero nesta base) |
| todos juntos | 9588 | -0.10 | -0.4 | nao |

## Regua: odd de ABERTURA - Europa (11358 jogos casados)

| fator (mandante - visitante) | jogos testados | ganho por 1000 jogos | forca | veredito |
|---|---|---|---|---|
| descanso | 9227 | +0.02 | +0.2 | nao |
| jogos_14d | 9227 | +0.06 | +0.4 | nao |
| viagem | 9227 | -0.13 | -1.3 | nao |
| poupa | - | - | - | sem dado (fator sempre zero nesta base) |
| veio_copa | - | - | - | sem dado (fator sempre zero nesta base) |
| todos juntos | 9227 | -0.15 | -0.6 | nao |

## Regua: odd de FECHAMENTO - Europa (11359 jogos casados)

| fator (mandante - visitante) | jogos testados | ganho por 1000 jogos | forca | veredito |
|---|---|---|---|---|
| descanso | 9227 | +0.00 | +0.0 | nao |
| jogos_14d | 9227 | +0.06 | +0.4 | nao |
| viagem | 9227 | -0.12 | -1.0 | nao |
| poupa | - | - | - | sem dado (fator sempre zero nesta base) |
| veio_copa | - | - | - | sem dado (fator sempre zero nesta base) |
| todos juntos | 9227 | -0.15 | -0.6 | nao |

## Regua: odd de FECHAMENTO - Brasileirao A (1978 jogos casados)

| fator (mandante - visitante) | jogos testados | ganho por 1000 jogos | forca | veredito |
|---|---|---|---|---|
| descanso | 1490 | +0.11 | +0.1 | nao |
| jogos_14d | 1490 | +0.24 | +0.3 | nao |
| viagem | 1490 | -1.22 | -0.9 | nao |
| poupa | 1490 | +0.17 | +0.5 | nao |
| veio_copa | 1490 | -0.17 | -0.2 | nao |
| todos juntos | 1490 | -1.03 | -0.6 | nao |

### Efeito direto (resultado real menos o esperado pela regua, em pontos percentuais)

| situacao | jogos | vitoria do time vs esperado |
|---|---|---|
| visitante com <=3 dias de descanso e mandante com 6+ | 111 | -1.2 (z -0.3) |
| mandante com <=3 dias de descanso e visitante com 6+ | 105 | +5.7 (z +1.2) |
| mandante vai jogar copa em ate 4 dias (pode poupar) | 418 | +1.8 (z +0.8) |
| visitante vai jogar copa em ate 4 dias (pode poupar) | 437 | -4.0 (z -1.9) |
| mandante veio de jogo de copa | 439 | +1.7 (z +0.7) |
| visitante veio de jogo de copa | 469 | -0.5 (z -0.2) |
| visitante viajou mais de 2.000 km | 331 | -1.3 (z -0.5) |
| mandante com 4+ jogos em 14 dias | 237 | +4.7 (z +1.5) |
| visitante com 4+ jogos em 14 dias | 218 | -2.2 (z -0.7) |
