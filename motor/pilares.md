# Pilares sem odds — teste no tempo

Base FotMob: 21238 jogos (Brasileirão A/B/C, Copa do Brasil, Libertadores, Sul-Americana, Paulista, 5 ligas grandes da Europa e Championship). Jogos com histórico suficiente: 19659; testados mês a mês, sempre ajustando só com o passado: 12513.

| Método | Acerto do favorito | Log-loss (menor = melhor) | Ganho | Força |
|---|---|---|---|---|
| Só a frequência (chute) | 44.9% | 1.0694 |  |  |
| **Todos os pilares sem odds** | 50.6% | 1.0063 | +0.0631 | +20.5 |
| Só Elo (força própria) | 49.7% | 1.0155 | +0.0539 | +18.4 |

## Cada pilar

| Pilar | Acerto sozinho | Somado ao Elo: força (precisa > 2) |
|---|---|---|
| Qualidade das chances (xG) | 48.7% | +5.8 |
| xG em casa / fora | 48.4% | +6.2 |
| Eficiência (gols − xG) | 44.9% | +4.4 |
| Domínio (toques na área) | 49.0% | +7.0 |
| Forma (geral e mando) | 46.9% | +0.6 |
| Calendário (descanso, copa) | 44.9% | +0.5 |
| Distância da viagem | 44.9% | +2.5 |
| Gramado sintético | 44.8% | -1.7 |
| Árbitro | 44.9% | +0.4 |

## Contra as odds de fechamento (8746 jogos que casaram com o football-data)

| Método | Acerto | Log-loss |
|---|---|---|
| Odds | 53.1% | 0.9787 |
| Pilares sem odds | 51.3% | 0.9981 |
| Odds + 15% pilares | 52.9% | 0.9795 (força -2.7 sobre as odds) |
| Odds + 30% pilares | 52.8% | 0.9810 (força -4.0 sobre as odds) |
| Odds + 50% pilares | 52.5% | 0.9842 (força -5.7 sobre as odds) |

Quando o mercado tem favorito forte (>55%) e os pilares discordam (<42%): 74 jogos; favorito venceu 60.8% (odd dava 60.7%); empate 28.4% (odd dava 22.1%).

## Peso de cada variável (vitória do mandante − vitória do visitante, escala padronizada)

- elo: +0.546
- dom: +0.282
- xgm_saldo: +0.118
- viagem: +0.098
- xg_pro: +0.055
- descanso: -0.051
- forma_mando: +0.050
- copa: -0.050
- xg_saldo: +0.046
- forma5: -0.045
- arb_casa: +0.032
- efic: -0.028
- j14: +0.024
- arb_verm: +0.021
- xg_contra: +0.020
- sintetico: +0.006
