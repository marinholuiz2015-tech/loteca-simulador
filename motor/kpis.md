# Placar de KPIs

Atualizado em 2026-11-25T00:40:02Z · teste no tempo (aprende só com concursos anteriores).

Força = ganho sobre as odds dividido pelo erro: 2 ou mais = comprovado; 0,5 a 2 = promissor; perto de 0 = neutro; negativo = atrapalha.

| Grupo | KPI | Jogos | Força | Peso aprendido | Leitura | O que mede |
|---|---|---|---|---|---|---|
| Desempenho | Forma (pontos nos ultimos 5) | 3048 | -1.7 | +0.001 | atrapalha | pontos do mandante - do visitante nos 5 ultimos jogos |
| Desempenho | Sequencia sem perder | 3048 | -0.3 | -0.048 | neutro | jogos seguidos sem perder (ate 5), mandante - visitante |
| Desempenho | Confronto direto (H2H) | 2719 | +0.6 | +0.095 | promissor | saldo de vitorias nos ultimos confrontos |
| Situacional | Descanso | 3048 | +0.5 | -0.047 | neutro | dias desde o ultimo jogo, mandante - visitante |
| Situacional | Calendario apertado | 3048 | -1.6 | +0.001 | atrapalha | jogos em 14 dias, visitante - mandante |
| Situacional | Rodizio / time reserva | 2651 | +1.0 | +0.086 | promissor | titulares trocados desde o ultimo jogo, visitante - mandante |
| Situacional | Desfalques | 3051 | -0.0 | +0.026 | neutro | lesionados e suspensos, visitante - mandante |
| Ambiente | Altitude | 2929 | +0.7 | +0.127 | promissor | estadio a 1.500 m ou mais: diferenca para a casa do visitante (km) |
| Ambiente | Viagem do visitante | 2842 | +1.3 | +0.043 | promissor | distancia da casa do visitante ate o estadio (log) |
| Ambiente | Classico / rivalidade local | 2842 | -0.1 | +0.117 | neutro | casas a menos de 60 km (favorece empate) |
| Ambiente | Chuva forte | 2920 | +0.2 | +0.218 | neutro | 10 mm ou mais no dia (favorece empate) |
| Massa | Massa x mercado (manada) | 2497 | -0.6 | -0.052 | atrapalha | quanto a enquete puxa para o mandante alem do mercado |
| Especialistas | Especialista (Lotequeiros) | 2806 | +0.2 | +0.012 | neutro | seco do Lotequeiros: 1, X ou 2 |
| Institucional | Noticias: crise | 1834 | -0.3 | -0.021 | neutro | manchetes de crise, visitante - mandante |
| Institucional | Noticias: tecnico | 1834 | -0.5 | +0.018 | neutro | manchetes de tecnico ameacado/trocado, visitante - mandante |
| Institucional | Noticias: reservas | 1834 | -1.6 | -0.022 | atrapalha | manchetes de poupar/reservas, visitante - mandante |
| Institucional | Noticias: desfalques | 1834 | -0.4 | +0.020 | neutro | manchetes de lesao/suspensao, visitante - mandante |
| Mercado | Movimento da odd | 14 | — | +0.000 | coletando (1 concursos) | odd andando a favor do mandante durante a semana |

## Todos os KPIs juntos

- Jogos de teste: 3484 · acerto: mercado 53.6% × KPIs 53.1% · força -2.5.
- Na previsão: **desligado** (liga sozinho com força acima de 2 sem perder acerto).
- Pesos do Luiz: nenhum definido (arquivo `motor/kpis_pesos_luiz.json`).
