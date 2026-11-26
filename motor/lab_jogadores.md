# Camada humana pelo jogador x forca (Elo) e odds

Jogos do Brasileirao com as duas escalacoes: 3453 ([('Brasileirao B', 1522), ('Brasileirao A', 1499), ('Brasileirao C', 432)])

## Regua: forca pelo Elo (Serie A, B e C)

| fator (mandante - visitante) | jogos testados | peso | ganho por 1000 jogos | forca | veredito |
|---|---|---|---|---|---|
| fora_costume | 2911 | -0.011 | -0.66 | -0.7 | nao |
| valor_xi | 2911 | +0.031 | -1.95 | -1.7 | nao |
| desc_jog | 2911 | -0.040 | +2.07 | +1.3 | promissor |
| cansados | 2911 | +0.011 | -0.57 | -0.5 | nao |
| forma | 2911 | +0.084 | -0.30 | -1.1 | nao |
| novatos | 2911 | -0.035 | +0.93 | +1.2 | promissor |
| tecnico_novo | 2911 | +0.006 | -0.35 | -0.6 | nao |
| todos juntos | 2911 | +0.004 +0.026 -0.035 +0.004 +0.031 -0.028 +0.010 | -1.96 | -0.7 | nao |

### Efeito direto (vitoria do time menos o esperado pela regua, em pontos percentuais)

| situacao | jogos | vitoria vs esperado |
|---|---|---|
| mandante com 4+ titulares de costume fora | 1656 | -1.2 (z -0.9) |
| visitante com 4+ titulares de costume fora | 1690 | -0.7 (z -0.7) |
| mandante com 6+ titulares de costume fora (time reserva) | 596 | -2.0 (z -1.0) |
| visitante com 6+ titulares de costume fora (time reserva) | 617 | -2.4 (z -1.4) |
| mandante poupado/desfalcado (11 valem 30% menos que o costume) | 231 | -3.9 (z -1.2) |
| visitante poupado/desfalcado (11 valem 30% menos que o costume) | 251 | -3.5 (z -1.3) |
| mandante com 3+ titulares cansados (<=3 dias) | 288 | +4.7 (z +1.6) |
| visitante com 3+ titulares cansados (<=3 dias) | 288 | +0.5 (z +0.2) |
| mandante em boa fase (notas recentes +0,3 acima) | 22 | poucos jogos |
| mandante em ma fase (notas recentes -0,3 abaixo) | 152 | -2.5 (z -0.6) |
| visitante em ma fase (notas recentes -0,3 abaixo) | 123 | -1.7 (z -0.5) |
| mandante com 3+ recem-chegados no time | 867 | -2.6 (z -1.5) |
| mandante com tecnico novo (ate 3 jogos) | 737 | +0.1 (z +0.1) |
| visitante com tecnico novo (ate 3 jogos) | 711 | -0.2 (z -0.1) |

## Regua: odd de FECHAMENTO - Brasileirao A (1490 jogos; essa odd ja conhece a escalacao)

| fator (mandante - visitante) | jogos testados | peso | ganho por 1000 jogos | forca | veredito |
|---|---|---|---|---|---|
| fora_costume | 986 | -0.036 | +0.90 | +0.9 | nao |
| valor_xi | 986 | +0.033 | -0.84 | -1.9 | nao |
| desc_jog | 986 | -0.029 | +0.96 | +0.5 | nao |
| cansados | 986 | +0.020 | +0.65 | +1.1 | promissor |
| forma | 986 | +0.119 | -0.43 | -0.6 | nao |
| novatos | 986 | -0.008 | -0.14 | -0.3 | nao |
| tecnico_novo | 986 | -0.086 | -0.00 | -0.0 | nao |
| todos juntos | 986 | -0.040 +0.025 -0.013 +0.015 +0.004 +0.030 -0.081 | -0.61 | -0.3 | nao |
