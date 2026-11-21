# CHANGELOG — loteca-simulador

## v11.13.0 — 21/11/2026 (Fase 1 do Estudo Base Único: dados confiáveis)
- **Base histórica oficial nova: tabela `jogos_cef`**, carregada de `data/historico_cef.json` (coleta completa da Caixa pelo GitHub Actions: 1.283 concursos, 17.952 jogos). Proteção `UNIQUE(concurso, sequencial)`: importar duas vezes não duplica.
- **Chave de time = NOME-UF** (ou NOME-PAÍS para estrangeiros). Separa ATLETICO-MG/GO, AMERICA-MG/RN/RJ/SP, BOTAFOGO-RJ/SP/PB e outros 45 nomes homônimos. Acaba com os jogos `-INDEFINIDO`. Seleções sem código em concursos antigos recebem o código de país único (BRASIL → BRASIL-BRA).
- A grade ao vivo usa a mesma regra de chave (`mandante_chave`/`visitante_chave`), igual ao backtest.
- `/api/importar-historico-cef`: simula por padrão; `?aplicar=1` grava.
- Sincronização automática: antes de recalcular o Elo (no máximo a cada 6 h), o app grava concursos novos do arquivo. O workflow "Baixar historico completo" passa a rodar 1 vez por dia.
- Elo com ordem fixa dentro do concurso (`concurso, sequencial`), para resultado reproduzível.
- `/health` mostra a base em uso; `/api/db-info` mostra concursos distintos, primeiro e último.
- `BASE_HISTORICA=antiga` (variável no Render) volta para a tabela antiga, só para comparação.
- Teste local (SQLite, 21/11/2026): 1.283 concursos e 17.952 jogos importados; reimportação sem duplicar; backtest avaliou 1.283 concursos; 0 nomes -INDEFINIDO.
- Nenhuma mudança na fórmula do motor (K, mando, bucket e α iguais).

## v11.12.2 — 21/11/2026 (Fase 0 do Estudo Base Único)
- Blend de odds **pausado por flag**: `ODDS_BLEND_ATIVO` (variável de ambiente, padrão desligado). Com a flag desligada, as probabilidades são 100% do motor (Elo + bucket bayesiano) e a fonte aparece como `modelo_puro_blend_pausado`.
- `/health` passa a mostrar `blend_odds_ativo`; a versão vem da constante `VERSAO_APP`.
- `/api/grade-automatica` informa `blend_ativo` e o peso efetivo do modelo (1,0 com o blend pausado).
- Nenhuma mudança na fórmula do motor.

## v11.12.1 — estado do main em 20/11/2026 (commit 380b367)
- app.py com 1.691 linhas; motor Elo iterativo (K=30, mando 75) + bucket empírico (α=30); fallback Dixon-Coles só sem banco.
- Blend de odds com peso fixo de 0,65 ativo sempre que havia odds (nunca calibrado).
