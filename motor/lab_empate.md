# Laboratório do empate — etapas 1 e 2

Jogos da Loteca com odds e resultado: **4217** (concursos 895–1281). Todas as medidas são **além do que a odd já diz** (a odd entra como ponto de partida).

## EMPATE

### Etapa 1 — regressão logística (uma informação por vez, erro agrupado por concurso)

Efeito = mudança no log-odds para 1 desvio-padrão da informação. |z| ≥ 2 = efeito real.

| Informação | Jogos | Efeito | z |
|---|---|---|---|
| chuva_mm | 3403 | +0.102 | +2.95 ** |
| nivel | 3430 | -0.068 | -1.75 |
| jogos14_fav_menos_az | 3613 | -0.065 | -1.61 |
| massa_marca_x | 3216 | +0.057 | +1.41 |
| equil | 4217 | -0.050 | -1.31 |
| lotequeiros_seco_x | 4200 | +0.040 | +1.17 |
| massa_x_menos_odd | 3216 | +0.046 | +1.12 |
| altitude_m | 3400 | +0.025 | +0.65 |
| massa_fav_menos_odd | 3216 | +0.024 | +0.61 |
| lotequeiros_duplo_tem_x | 4200 | -0.012 | -0.32 |
| h2h_n | 3312 | +0.012 | +0.31 |
| arena_n_marcas | 4058 | -0.011 | -0.30 |
| arena_marca_x | 4058 | +0.009 | +0.27 |
| desfalques_valor_fav_menos_az | 3619 | +0.009 | +0.22 |
| vovo_matriz_x | 1122 | -0.014 | -0.21 |
| posicao | 4217 | +0.006 | +0.18 |
| serie_b_c | 4217 | -0.004 | -0.11 |
| descanso_fav_menos_az | 3613 | +0.004 | +0.11 |
| forma5_fav_menos_az | 3613 | -0.002 | -0.05 |

### Etapa 2 — LightGBM (todas as informações juntas, procura combinações), teste no tempo

Jogos testados (blocos de 20 concursos, só com o passado): 2572. Ganho de log-loss sobre a odd: -0.00714 → **força -2.61** (sem ganho comprovado).

Importância SHAP (quanto cada informação mexe na previsão, modelo com todos os dados — só explica, não prova):

- nivel: 0.0656
- equil: 0.0573
- massa_fav_menos_odd: 0.0463
- chuva_mm: 0.0443
- massa_x_menos_odd: 0.0349
- jogos14_fav_menos_az: 0.0339
- descanso_fav_menos_az: 0.0324
- altitude_m: 0.0278

## DUPLO favorito + empate

### Etapa 1 — regressão logística (uma informação por vez, erro agrupado por concurso)

Efeito = mudança no log-odds para 1 desvio-padrão da informação. |z| ≥ 2 = efeito real.

| Informação | Jogos | Efeito | z |
|---|---|---|---|
| h2h_n | 3312 | +0.093 | +2.17 ** |
| lotequeiros_duplo_tem_x | 4200 | -0.065 | -1.89 |
| lotequeiros_seco_x | 4200 | +0.068 | +1.79 |
| nivel | 3430 | -0.082 | -1.76 |
| vovo_matriz_x | 1122 | -0.126 | -1.51 |
| massa_marca_x | 3216 | +0.062 | +1.42 |
| equil | 4217 | -0.053 | -1.13 |
| posicao | 4217 | +0.043 | +1.05 |
| forma5_fav_menos_az | 3613 | -0.039 | -0.86 |
| arena_n_marcas | 4058 | -0.032 | -0.79 |
| massa_x_menos_odd | 3216 | +0.036 | +0.79 |
| jogos14_fav_menos_az | 3613 | -0.032 | -0.74 |
| desfalques_valor_fav_menos_az | 3619 | +0.034 | +0.61 |
| descanso_fav_menos_az | 3613 | +0.021 | +0.52 |
| altitude_m | 3400 | +0.018 | +0.40 |
| arena_marca_x | 4058 | -0.011 | -0.26 |
| massa_fav_menos_odd | 3216 | -0.011 | -0.24 |
| chuva_mm | 3403 | +0.003 | +0.08 |
| serie_b_c | 4217 | +0.003 | +0.07 |

### Etapa 2 — LightGBM (todas as informações juntas, procura combinações), teste no tempo

Jogos testados (blocos de 20 concursos, só com o passado): 2572. Ganho de log-loss sobre a odd: -0.00733 → **força -2.66** (sem ganho comprovado).

Importância SHAP (quanto cada informação mexe na previsão, modelo com todos os dados — só explica, não prova):

- vovo_matriz_x: 0.0673
- nivel: 0.0646
- equil: 0.0546
- descanso_fav_menos_az: 0.0521
- massa_fav_menos_odd: 0.0442
- altitude_m: 0.0396
- h2h_n: 0.0356
- massa_x_menos_odd: 0.0340

