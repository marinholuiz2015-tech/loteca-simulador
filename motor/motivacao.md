# Motivação pela tabela (reta final: 10 rodadas ou menos)

Jogos testados: 11478 (Brasileirão Série A e ligas europeias, odd de fechamento — média das casas).

| Situação | Jogos | Aconteceu | A odd dava | Peso (0 = a odd já sabe) |
|---|---|---|---|---|
| mandante sem nada em jogo (vitoria do mandante) | 1065 | 37.8% | 38.2% | -0.016 |
| visitante sem nada em jogo (vitoria do visitante) | 1073 | 21.5% | 25.1% | -0.222 |
| os dois sem nada em jogo (empate) | 1413 | 23.8% | 23.6% | +0.007 |
| mandante na luta contra o rebaixamento (vitoria do mandante) | 1231 | 38.1% | 36.2% | +0.085 |
| visitante na luta contra o rebaixamento (vitoria do visitante) | 1189 | 22.5% | 22.6% | +0.007 |

**Teste no tempo — todas as situacoes juntas:** 4762 jogos, ganho médio -0.0005 log-loss por jogo, força -0.7 → não passa no critério (precisa > 2)
Pesos aprendidos só com o passado, por ano: 2019: [-0.067, -0.182, 0.234, 0.091, -0.038], 2020: [-0.01, -0.147, 0.121, 0.17, -0.03], 2021: [0.141, -0.12, 0.116, 0.185, -0.033], 2022: [0.021, -0.105, 0.027, 0.216, -0.024], 2023: [0.019, -0.143, 0.017, 0.185, -0.076], 2024: [0.024, -0.183, -0.007, 0.104, -0.027], 2025: [-0.005, -0.218, 0.008, 0.063, 0.036], 2026: [-0.018, -0.221, 0.007, 0.075, 0.004]

**Teste no tempo — so visitante sem nada em jogo:** 903 jogos, ganho médio +0.0038 log-loss por jogo, força +1.8 → não passa no critério (precisa > 2)
Pesos aprendidos só com o passado, por ano: 2019: [-0.182], 2020: [-0.147], 2021: [-0.12], 2022: [-0.105], 2023: [-0.143], 2024: [-0.183], 2025: [-0.218], 2026: [-0.221]

Uso no motor: alerta no concurso aberto sempre; entra na probabilidade só com força > 2 (hoje: desligado).
