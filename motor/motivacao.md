# Motivação pela tabela (reta final: 10 rodadas ou menos)

Jogos testados: 11487 (Brasileirão Série A e ligas europeias, odd de fechamento — média das casas).

| Situação | Jogos | Aconteceu | A odd dava | Peso (0 = a odd já sabe) |
|---|---|---|---|---|
| mandante sem nada em jogo (vitoria do mandante) | 1029 | 37.4% | 37.9% | -0.025 |
| visitante sem nada em jogo (vitoria do visitante) | 1055 | 21.2% | 24.6% | -0.213 |
| os dois sem nada em jogo (empate) | 1318 | 24.1% | 23.6% | +0.024 |
| mandante na luta contra o rebaixamento (vitoria do mandante) | 1257 | 38.0% | 36.3% | +0.081 |
| visitante na luta contra o rebaixamento (vitoria do visitante) | 1227 | 22.7% | 22.6% | +0.020 |

**Teste no tempo — todas as situacoes juntas:** 4689 jogos, ganho médio -0.0008 log-loss por jogo, força -1.0 → não passa no critério (precisa > 2)
Pesos aprendidos só com o passado, por ano: 2019: [-0.085, -0.247, 0.244, 0.072, -0.037], 2020: [0.018, -0.142, 0.164, 0.158, -0.012], 2021: [0.164, -0.125, 0.114, 0.189, -0.007], 2022: [0.029, -0.087, 0.038, 0.231, -0.012], 2023: [0.015, -0.141, 0.029, 0.197, -0.066], 2024: [0.002, -0.183, 0.01, 0.112, -0.018], 2025: [-0.026, -0.222, 0.023, 0.068, 0.044], 2026: [-0.024, -0.213, 0.025, 0.073, 0.01]

**Teste no tempo — so visitante sem nada em jogo:** 890 jogos, ganho médio +0.0026 log-loss por jogo, força +1.2 → não passa no critério (precisa > 2)
Pesos aprendidos só com o passado, por ano: 2019: [-0.247], 2020: [-0.142], 2021: [-0.125], 2022: [-0.087], 2023: [-0.141], 2024: [-0.183], 2025: [-0.222], 2026: [-0.213]

Uso no motor: alerta no concurso aberto sempre; entra na probabilidade só com força > 2 (hoje: desligado).
