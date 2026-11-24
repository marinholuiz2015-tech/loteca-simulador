# Frente 2 — ajuste da odd por campeonato × ajuste único

Gama > 1 = a odd subestima o favorito (deixa ele mais forte); < 1 = superestima. Fator de empate > 1 = a odd subestima o empate nos jogos equilibrados.

## A) Europa — bet365, 31288 jogos testados (temporada seguinte, nunca vista)

Ganho total do ajuste por liga sobre o único: **força +0.23** (ganho médio de log-loss +0.00005).

| Liga | Jogos testados | Força | Gama aprendida | Fator de empate |
|---|---|---|---|---|
| E1 | 2952 | +1.95 | 0.94 | 0.960 |
| E2 | 2935 | +0.93 | 1.1 | 0.986 |
| SP2 | 2465 | -0.45 | 1.02 | 1.066 |
| SP1 | 2029 | -0.56 | 1.04 | 1.120 |
| I1 | 2019 | -0.63 | 1.02 | 1.101 |
| I2 | 2017 | +2.06 | 1.0 | 1.157 |
| E0 | 2010 | +0.11 | 0.96 | 1.000 |
| F2 | 1859 | -2.12 | 0.96 | 1.043 |
| T1 | 1824 | -2.15 | 1.06 | 1.078 |
| F1 | 1777 | -1.04 | 0.96 | 0.999 |
| B1 | 1649 | -1.18 | 0.98 | 1.067 |
| N1 | 1647 | +0.66 | 0.94 | 0.974 |
| D2 | 1638 | -1.56 | 0.92 | 1.008 |
| P1 | 1626 | +1.07 | 1.1 | 1.096 |
| D1 | 1620 | -0.61 | 0.92 | 1.038 |
| SC0 | 1221 | +0.47 | 1.02 | 0.959 |

## B) Loteca — bet365 de quinta (Arena), 3484 jogos testados

Ganho total do ajuste por campeonato sobre o único: **força -2.84** (ganho médio de log-loss -0.00156). Ajuste único aprendido: gama 1.02, empate 1.098.

| Campeonato | Jogos (total) | Jogos testados | Força | Gama | Fator de empate |
|---|---|---|---|---|---|
| Outros (Série B/C, copas, estaduais, seleções) | 3025 | 2263 | -1.69 | 1.02 | 1.107 |
| Brasileirão A | 1558 | 903 | -2.36 | 1.02 | 1.084 |
| Inglaterra | 155 | 102 | +0.00 | 1.02 | 1.098 |
| Itália | 186 | 95 | +0.00 | 1.02 | 1.098 |
| Espanha | 163 | 93 | +0.00 | 1.02 | 1.098 |
| Outras ligas europeias | 65 | 28 | +0.00 | 1.02 | 1.098 |
