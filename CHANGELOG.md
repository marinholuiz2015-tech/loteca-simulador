# CHANGELOG — loteca-simulador

## v11.12.2 — 21/11/2026 (Fase 0 do Estudo Base Único)
- Blend de odds **pausado por flag**: `ODDS_BLEND_ATIVO` (variável de ambiente, padrão desligado). Com a flag desligada, as probabilidades são 100% do motor (Elo + bucket bayesiano) e a fonte aparece como `modelo_puro_blend_pausado`.
- `/health` passa a mostrar `blend_odds_ativo`; a versão vem da constante `VERSAO_APP`.
- `/api/grade-automatica` informa `blend_ativo` e o peso efetivo do modelo (1,0 com o blend pausado).
- Nenhuma mudança na fórmula do motor.

## v11.12.1 — estado do main em 20/11/2026 (commit 380b367)
- app.py com 1.691 linhas; motor Elo iterativo (K=30, mando 75) + bucket empírico (α=30); fallback Dixon-Coles só sem banco.
- Blend de odds com peso fixo de 0,65 ativo sempre que havia odds (nunca calibrado).
