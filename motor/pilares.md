# Pilares sem odds — teste no tempo

Base FotMob: 18849 jogos (Brasileirão A/B/C, Copa do Brasil, Libertadores, Sul-Americana, Paulista, 5 ligas grandes da Europa e Championship). Jogos com histórico suficiente: 17292; testados mês a mês, sempre ajustando só com o passado: 12462.

| Método | Acerto do favorito | Log-loss (menor = melhor) | Ganho | Força |
|---|---|---|---|---|
| Só a frequência (chute) | 44.9% | 1.0701 |  |  |
| **Todos os pilares sem odds** | 50.4% | 1.0077 | +0.0623 | +19.9 |
| Só Elo (força própria) | 49.4% | 1.0180 | +0.0521 | +17.7 |

## Cada pilar

| Pilar | Acerto sozinho | Somado ao Elo: força (precisa > 2) |
|---|---|---|
| Qualidade das chances (xG) | 48.7% | +6.4 |
| xG em casa / fora | 48.2% | +6.6 |
| Eficiência (gols − xG) | 44.8% | +4.0 |
| Domínio (toques na área) | 48.6% | +7.6 |
| Forma (geral e mando) | 46.9% | +0.9 |
| Calendário (descanso, copa) | 44.9% | +0.3 |
| Distância da viagem | 44.9% | +2.6 |
| Gramado sintético | 44.8% | -1.7 |
| Árbitro | 44.9% | +0.3 |

## Contra as odds de fechamento (8635 jogos que casaram com o football-data)

| Método | Acerto | Log-loss |
|---|---|---|
| Odds | 53.1% | 0.9785 |
| Pilares sem odds | 51.2% | 1.0004 |
| Odds + 15% pilares | 53.0% | 0.9794 (força -3.1 sobre as odds) |
| Odds + 30% pilares | 52.8% | 0.9812 (força -4.4 sobre as odds) |
| Odds + 50% pilares | 52.3% | 0.9848 (força -6.2 sobre as odds) |

Quando o mercado tem favorito forte (>55%) e os pilares discordam (<42%): 92 jogos; favorito venceu 60.9% (odd dava 61.0%); empate 26.1% (odd dava 21.9%).

## Peso de cada variável (vitória do mandante − vitória do visitante, escala padronizada)

- elo: +0.507
- dom: +0.288
- xgm_saldo: +0.141
- viagem: +0.102
- descanso: -0.065
- forma_mando: +0.064
- xg_pro: +0.055
- copa: -0.054
- xg_saldo: +0.044
- arb_verm: +0.040
- forma5: -0.025
- efic: -0.024
- xg_contra: +0.016
- arb_casa: +0.013
- j14: +0.013
- sintetico: +0.006
