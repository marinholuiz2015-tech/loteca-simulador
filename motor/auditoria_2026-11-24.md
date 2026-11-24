# Auditoria do projeto — 24/11/2026

## O que está certo (verificado)
- **Odds da Arena bem calibradas**: em todas as faixas, o favorito acerta o que a odd promete (40–50%: 45,1% × 44,7%; 60–70%: 66,5% × 64,4%; 80–90%: 87,0% × 84,0%). Margens entre 4% e 12%, nenhum resultado diferente do oficial da Caixa e nenhum jogo trocado.
- **Modelo de ganhadores calibrado**: 13 e 14 feitos batem com os esperados em todos os níveis de concurso.
- **Confronto com os sites é justo** (mesmos jogos, mesma estrutura) e favorável: +0,70 ponto por concurso sobre a Arena (z 7,9), +0,84 sobre a matriz da Vovoteca (z 5,3).

## Onde a construção está errada ou frágil (por prioridade)
1. **Dois motores convivendo na produção.** `app.py` (2.215 linhas) ainda carrega o motor antigo (lambdas fixos por liga, rotas `/`, `/api/analisar`, `/api/backtest-*`) junto com o painel novo, que lê os arquivos do `motor/`. Na raiz há scripts das fases antigas (`backtesting.py`, `calibrar_e_gerar.py`, `coletar2.py`, `elo_dinamico.py`, `setup_ia.py`, `loteca_historico.db`). Risco de consultar o motor errado e de confusão em toda manutenção. **Ação:** mover o legado para `legado/` e deixar o `app.py` só com o painel e as APIs que ele usa.
2. **Odds de uma fonte só, lida por OCR de imagem.** 76 concursos com jogo faltando (162 jogos), inclusive recentes (1228–1231, 1239, 1258, 1266, 1283); 4 odds lidas como 1,00 (1087-2, 1123-11, 1196-8, 1283-1); concurso 942 duplicado. Se a Arena atrasar ou mudar a imagem, o motor fica cego. **Ação:** segunda fonte de odds na quinta (The Odds API — a chave já está no Render, mas o motor não usa) e conferência cruzada OCR × API.
3. **Jogo sem odd vira TRIPLO automático** (`camada1`: frequência histórica, classe triplo). Gasta um triplo — o recurso mais caro da cartela — no jogo sobre o qual menos se sabe. **Ação:** usar os pilares sem odds (50,4% × 44,9% do chute) e a segunda fonte de odds.
4. **Estrutura da aposta fixa por orçamento** (`camada3.ESCADA`: R$ 2.592 = sempre 4 duplos + 4 triplos etc.). O pedido era que o estudo definisse a estrutura por concurso; hoje só a posição dos duplos e triplos muda. **Ação:** escolher, em cada concurso, a estrutura de maior retorno líquido esperado (nível do concurso + rateio + IR).
5. **Prova prospectiva ainda não começou.** Existe o registro (`registro_previsoes.csv`), mas não há placar semanal contra Arena, Vovoteca e massa. **Ação:** aba "Confronto" a partir do 1285.
6. **Previsão do tempo gravada por dia, não no horário do jogo** — e a chuva é o único sinal novo achado no laboratório. **Ação:** gravar a previsão hora a hora na quinta.
7. **Massa de uma fonte só** (enquete Vovoteca, 297 concursos) — gargalo de todo o estudo de rateio. **Ação:** procurar outras enquetes e guardar as parciais de quinta e sexta.
