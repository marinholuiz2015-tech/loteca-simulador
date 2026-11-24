# Legado — código das fases anteriores (não usado)

Movido para cá na limpeza de 24/11/2026. Nada aqui é executado pelo painel nem pela coleta automática.

- `app_antigo.py` — servidor antigo (v11.12): motor Poisson/Elo com parâmetros fixos por liga e as rotas
  `/api/analisar`, `/api/backtest-*`, `/api/grade-automatica`. O painel oficial foi mantido no novo `app.py`.
- `index_antigo.html` — dashboard antigo que usava essas rotas.
- `backtesting.py`, `calibrar_e_gerar.py`, `coletar2.py`, `elo_dinamico.py`, `setup_ia.py`, `loteca_historico.db` —
  scripts e banco das fases iniciais.

O motor atual está em `motor/` e a coleta em `coleta/`.
