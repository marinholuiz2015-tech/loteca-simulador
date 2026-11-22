# motor/ — Loteca Elite Pro

Arquitetura em camadas separadas (cada uma com o seu próprio teste):

| Camada | O que faz | Status |
|---|---|---|
| **1. Motor de previsão** (`camada1.py`) | Probabilidade 1/X/2 calibrada de cada jogo, confiança, ordem, classe seco/duplo/triplo e duplo sugerido | ✅ No ar (21/11/2026) |
| 2. Rateio | Quantos ganhadores e quanto paga cada resultado (odds + massa) | A construir |
| 3. Decisão | Jogo principal, desdobre, gavetas e quanto investir | A construir |

## Camada 1
- **Probabilidades:** odds bet365 (Arena) sem margem pelo método de potência + ajuste gama aprendido no histórico.
- **Validação no tempo** (`validar_camada1.py`, 280 concursos 998–1283, ajustes aprendidos só com o passado):

| | 14 | Top 10 | Top 8 | Top 6 | Top 4 | Brier | Calibração |
|---|---|---|---|---|---|---|---|
| Odds puras (potência) | 52,9% | 57,6% | 60,6% | 65,0% | 69,8% | 0,5805 | 1,07% |
| + ajuste de empate | 52,7% | 57,3% | 60,8% | 65,2% | 69,4% | 0,5808 | 1,63% ❌ |
| **+ gama (adotado)** | **52,9%** | **57,6%** | **60,6%** | **65,1%** | **69,8%** | **0,5805** | **0,87%** ✅ |
| + empate + gama | 52,8% | 57,3% | 60,8% | 65,4% | 69,3% | 0,5807 | 1,51% ❌ |

  O empate subestimado visto no histórico inteiro não se sustentou fora da amostra; ficou de fora.
- **Classe:** SECO se o favorito tem ≥ 60%; TRIPLO se os dois resultados mais prováveis somam < 70%; senão DUPLO (com o duplo dos dois mais prováveis). Jogos sem odds: frequência histórica, TRIPLO.
- **Grade:** API da Caixa → tabela do Guia da Loteria → imagem da Arena. As probabilidades da bolsa (Guia) ficam gravadas, ainda sem peso (precisam de semanas para validar).
- **Registro prospectivo** (`registro_previsoes.csv`): gravado só de quinta a sábado até 15h, pela coleta semanal, para cada previsão ser anterior ao fechamento. Nunca é sobrescrito.
- **Placar ao vivo** (`placar.py` → `placar.md`): última previsão antes do fechamento × resultado oficial, contra as metas (14 = 56%, 10 = 60%, 8 = 62%, 6 = 65%, 4 = 70%). Primeiro concurso: 1285.

Uso manual: `python motor/camada1.py 1285 --sem-registro` (gera a tabela em `motor/saida/` sem gravar no registro).
