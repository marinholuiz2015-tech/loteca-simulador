# Estrutura da aposta por concurso — orçamento de ~R$ 200

301 concursos (975–1284), cartelas montadas só com informação anterior. Os triplos vão para os jogos mais incertos e os duplos para favorito + empate (posição ótima para a chance de 14). Dinheiro com a regra atual da Caixa, líquido de IR.

Jogos incertos (favorito < 45%) por concurso: mediana 5, de 0 a 11.

| Estrutura | Gasto | Recebido líquido | Retorno líquido | 14 | 13 | Retorno esperado pelo modelo (bruto, regra da época) | Escolhas |
|---|---|---|---|---|---|---|---|
| 6 duplos | R$ 38.528 | R$ 14.923 | 39% | 1 | 10 | 16% | R$ 128: 301 |
| 3 duplos + 2 triplos | R$ 43.344 | R$ 13.136 | 30% | 1 | 10 | 20% | R$ 144: 301 |
| 4 triplos | R$ 48.762 | R$ 1.923 | 4% | 0 | 8 | 25% | R$ 162: 301 |
| 5 duplos + 1 triplo (hoje) | R$ 57.792 | R$ 15.131 | 26% | 1 | 12 | 17% | R$ 192: 301 |
| 2 duplos + 3 triplos | R$ 65.016 | R$ 13.739 | 21% | 1 | 12 | 22% | R$ 216: 301 |
| **Adaptativa** (maior retorno esperado no concurso) | R$ 50.880 | R$ 2.440 | 5% | 0 | 10 | 26% | R$ 128: 15, R$ 144: 10, R$ 162: 216, R$ 192: 18, R$ 216: 42 |
| **Por incerteza** (≥ 6 jogos incertos → 2 duplos + 3 triplos; ≤ 3 → 6 duplos; senão hoje) | R$ 54.416 | R$ 1.933 | 4% | 0 | 10 | 18% | R$ 128: 88, R$ 192: 119, R$ 216: 94 |

## Leitura
- **Os triplos já são computados pela incerteza:** em todas as estruturas, o motor põe os triplos nos jogos mais incertos e os duplos em favorito + empate, na posição ótima para a chance de 14.
- **Calibração por estrutura** (esperado × feito): 6 duplos 1,2 × 1 catorze e 7,3 × 10 treze; hoje (5d+1t) 1,8 × 1 e 9,9 × 12; 2d+3t 2,4 × 1 e 12,6 × 12; 4 triplos 2,1 × 0 e 11,5 × 8 (abaixo do esperado, ainda dentro da sorte).
- **Pelo modelo, mais triplos rendem mais por real** (a massa joga menos as combinações das zebras, o prêmio é dividido com menos gente): 4 triplos 25%, 2d+3t 22%, 3d+2t 20%, hoje 17%, 6 duplos 16%. O retorno realizado não confirma nem desmente: com R$ 200 sai no máximo um 14 em 300 concursos, e um único prêmio decide a tabela.
- **Desdobre espalhado de R$ 200** (mesmos concursos, 256 com dados): 14 esperado 1,93 × 2 feitos; 13 ou 14 esperado 13,9 (5,4% por concurso) × 11 treze + 2 catorze. Por concurso, tem mais chance de 14 (0,75%) e de 13 que qualquer volante único de ~R$ 200 (hoje: 0,60% e 3,9%). **Para R$ 200, o espalhado continua sendo o melhor jogo** — a decisão de quantos triplos usar passa a ser na base do desdobre.
