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

## Odds da Arena do AZ (bet365), lidas das imagens — 21/11/2026
Pasta `ocr/`: `ocr_arena.py` (leitura célula a célula), `rodar_arena.py`
(processa as imagens em paralelo, retomável), `avaliar_arena.py` (casa com a
grade da Caixa em `data/historico_cef.json` e mede). Base final:
`dados/arena_odds.csv` (5.162 jogos, concursos 895–1283).
- Cobertura: 97% dos jogos desses concursos têm odds (inclui estaduais e divisões menores).
- Favorito do mercado acerta **52,0%** vs. 45,6% de "sempre coluna 1" (lift 1,141x); Brier 0,5883 vs. 0,6442 (−8,7%).
- Contra o Lotequeiros nos mesmos 3.944 jogos: mercado 51,5% × 47,9% (McNemar z = 4,8). Quando discordam: mercado 44,0% × 31,6%.
- Conferência: 180 odds checadas a olho sem erro; cada jogo só entra se as odds passam na checagem de coerência e os times batem com a grade da Caixa.

## Enquete final da Vovoteca (efeito manada) — 21/11/2026
`vovoteca_enquete.py` (`historico` ou `semanal`) lê a enquete **final** (publicada
depois do fechamento de sábado, formato tabela com decimais) e grava
`dados/vovoteca_massa.csv`. Cada linha só entra se os três percentuais somam
100 ± 0,6 e o nome lido na imagem bate com a grade da Caixa; o resto vai para
`dados/vovoteca_massa_revisar.csv`. Base: 729 jogos aceitos de 854 (61 concursos,
945–1284). Conferência visual: 1284 idêntico; desvios de até 0,5 ponto em alguns números.

`avaliar_massa.py` cruza massa × odds bet365 × resultado (683 jogos, 58 concursos):
- Favorito acerta: mercado **57,8%** × massa 54,6%. Brier: mercado 0,5519 × massa 0,5804.
- Favoritos diferentes (123 jogos): mercado 49% × massa 31% (McNemar z = 2,2).
- A massa **supervaloriza o favorito**: quando dá 72% ao mandante e o mercado 52%, o real é 55%.
- E **subvaloriza o visitante**: quando dá 14% ao visitante e o mercado 33%, o real é 31% — onde
  o resultado acontece na frequência do mercado mas com poucos apostadores (rateio melhor).

A coleta semanal (`.github/workflows/coleta_semanal.yml`) agora instala o tesseract e roda também
`ocr/arena_semanal.py` (odds da Arena) e `vovoteca_enquete.py semanal` + `avaliar_massa.py`.

## Massa ampliada com as enquetes parciais — 21/11/2026
`vovoteca_enquete.py parciais` lê a última parcial (arte colorida de quinta/sexta) dos concursos
sem enquete final. A cor de cada célula indica a faixa do número (vermelho = zebra 0–12%,
amarelo = surpresa 13–25%, ciano = normal 26–50%, verde = favorito, verde escuro = super
favorito), o que elimina leituras impossíveis ("4%" com ícone lido como 14). Conferência à mão
em 10 parciais: 137 jogos aceitos, nenhum errado. Base: 3.889 jogos, 297 concursos (61 finais + 236 parciais).

`vovoteca_enquete.py aberto` (coleta semanal) guarda a parcial do concurso **ainda aberto** em
`dados/vovoteca_massa_aberto.csv` — é a massa disponível na hora de apostar; nunca é sobrescrita.

`pesquisa/teste_massa.py` (195 concursos, validação deixando um concurso de fora):
- Ganhadores de 13: erro (log10) odds 0,450 × massa 0,397 × **odds+massa 0,351 (−22%)**; de 14: 0,379 × 0,393 × 0,366 (−3%).
- Desdobre com o mesmo custo (170 concursos): cortar pelo retorno (ganhadores previstos pela massa)
  troca chance por combinações menos jogadas e pagou 10–18% mais que cortar pela chance; inconclusivo
  (2 a 6 casos de 14 por coluna).
