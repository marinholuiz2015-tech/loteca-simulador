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
- **Calendário (Brasília):** terça 09:17 = previsão **provisória**; quinta 09:47 (depois da atualização das 7h da Arena) e 19:23 = previsão **oficial**, a tempo dos especialistas e bolões; sábado 10:17 = **atualização**. Fora disso, nada é registrado.
- **Registro prospectivo** (`registro_previsoes.csv`, coluna `versao`): gravado pela coleta semanal; nunca é sobrescrito.
- **Placar ao vivo** (`placar.py` → `placar.md`): mede a última previsão **oficial** de cada concurso contra o resultado e as metas (14 = 56%, 10 = 60%, 8 = 62%, 6 = 65%, 4 = 70%), mais a chance de 14 da aposta mínima (13 secos + 1 duplo). A **atualização de sábado** é medida à parte, para saber se esperar mais informação melhora o acerto. Primeiro concurso: 1285.
- **Escada** (`escada.py`): chance de 14 da aposta mínima (R$4: 0,039%, 1 em 2.563) até R$8.192 (4,65%), acrescentando o duplo/triplo que mais compra chance por real.

Uso manual: `python motor/camada1.py 1285 --sem-registro` (gera a tabela em `motor/saida/` sem gravar no registro).

## Camada Sentinela (fatos do jogo) — automática

- `coleta/sentinela/coletar_sentinela.py aberto`: antes de cada previsão (terça, quinta, sábado), busca na FotMob cada jogo do concurso aberto e grava desfalques (quantidade, lesão/suspensão, valor de mercado), descanso (dias desde o último jogo, jogos em 14 dias), forma (pontos nos últimos 5) e clima no estádio (Open-Meteo). Arquivo `coleta/dados/sentinela_aberto.csv`, só acrescenta.
- `coleta/sentinela/coletar_sentinela.py historico`: os mesmos fatos para todos os jogos da base de odds (895 em diante); toda segunda acrescenta os jogos do concurso que acabou. `clima` completa a chuva/temperatura respeitando o limite da Open-Meteo.
- `motor/sentinela.py treinar` (toda segunda): teste no tempo do ajuste mercado + fatos. **Só liga se melhorar a perda logarítmica com folga (mais de 2 erros-padrão) e não piorar o acerto.** Resultado em `motor/sentinela_modelo.json` e `motor/sentinela_relatorio.txt`.
- `camada1.py` aplica o ajuste quando ligado e grava as duas probabilidades (`pm1/pmx/pm2` = mercado, `p1/px/p2` = final) e o estado da camada em cada jogo. O placar compara motor × só mercado ao vivo.

## KPIs (substitui o ajuste da Sentinela)

`motor/kpis.py` reúne todos os indicadores do jogo num só lugar: desempenho (forma, sequência sem perder, confronto direto), situacional (descanso, calendário, rodízio, desfalques), ambiente (altitude, viagem, clássico, chuva), massa, especialistas, notícias (crise, técnico, reservas, desfalques) e movimento da odd.

- `python motor/kpis.py medir` (toda segunda): mede cada KPI sozinho no tempo (força = ganho/erro) e todos juntos com pesos aprendidos. Escreve o placar em `motor/kpis.md` e o modelo em `motor/kpis_modelo.json`. Os KPIs juntos só entram na previsão com força acima de 2 e sem perder acerto.
- Pesos do Luiz: copiar `motor/kpis_pesos_luiz.exemplo.json` para `motor/kpis_pesos_luiz.json` e ajustar. São testados do mesmo jeito e usados se superarem o mercado e os pesos aprendidos.
- KPIs sem histórico (notícias, movimento da odd) ficam "coletando" até 20 concursos.
- A previsão (`motor/saida/concurso_N.md`) mostra a nota de cada KPI por jogo.
