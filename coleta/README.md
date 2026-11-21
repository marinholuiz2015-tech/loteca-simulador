# coleta/ — fontes externas da Loteca

Pasta separada do app (o Render não usa nada daqui). Tudo roda no GitHub
Actions pelo workflow `.github/workflows/coleta_semanal.yml`:
quinta 19:23, sábado 10:17 e segunda 21:41 (horário de Brasília), ou na mão
pela aba **Actions → Coleta semanal de fontes → Run workflow**.

| Script | Fonte | Saída em `dados/` |
|---|---|---|
| `guia_loteria.py` | Guia da Loteria — probabilidades de mercado (fair odds), odds e palpite. A página é reescrita a cada concurso, por isso o retrato é semanal | `guia_loteria.csv` (um bloco de 14 linhas por retrato) |
| `coletar_lotequeiros.py semanal` | Blog Lotequeiros — seco e duplo por jogo (desde o concurso ~750, 2017) | `lotequeiros_palpites.csv` |
| `resultados_caixa.py` | API oficial da Caixa | `resultados_caixa.csv` |
| `avaliar_lotequeiros.py` | Cruza palpites × resultados | `lotequeiros_x_caixa.csv`, `resumo_lotequeiros.txt` |

`coletar_lotequeiros.py baixar` refaz o histórico inteiro (7.100 posts,
~2 min); o bruto (`lotequeiros_bruto.jsonl`, 24 MB) fica fora do git.

## Resultado em 21/11/2026 (6.350 jogos, concursos 750–1281)
- Seco: **49,2%** vs. 45,9% de "sempre coluna 1" → lift 1,072x (McNemar z = 4,2)
- Duplo: **76,0%** (79% de 2024 em diante)
- Seco "2": 45,2% (marcar 1 nesses jogos daria 26,7%) · Seco "X": 32,6% (marcar 1 daria 40,5%)
