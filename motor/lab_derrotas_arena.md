# Por que perdemos ou empatamos com a Arena em algumas semanas? (359 concursos)

Mesmos concursos, mesma estrutura de secos/duplos/triplos da Arena; só muda onde marcar.
Placar: 188 vitórias, 94 empates, 77 derrotas. Em média os dois marcam diferente em 7,8 jogos por concurso.

## 1. Onde a marcação difere, a Arena acerta exatamente o que a chance do nosso motor previa

| tipo de diferença | jogos | Arena acertou | nós acertamos | chance (motor) da marca Arena | da nossa |
|---|---|---|---|---|---|
| Arena seco x nosso duplo | 554 | 41.9% | 76.0% | 39.9% | 73.7% |
| Arena duplo x nosso seco | 548 | 80.7% | 60.6% | 79.7% | 59.3% |
| Arena duplo x nosso duplo | 534 | 63.9% | 74.5% | 67.7% | 71.4% |
| Arena triplo x nosso seco | 448 | 100.0% | 54.0% | 100.0% | 55.1% |
| Arena seco x nosso triplo | 442 | 38.0% | 100.0% | 34.4% | 100.0% |
| Arena seco x nosso seco | 222 | 27.9% | 49.1% | 26.9% | 48.9% |

Todas as diferenças juntas: Arena acertou 62,0% (o motor previa 61,6%, z +0,5). A escolha diferente dela não traz informação escondida.

## 2. Recortes procurados (nenhum vira ganho)
- Jogos sem odds: só 69 jogos; Arena 60,9% x previsto 54,7% (z +1,0) - poucos para concluir.
- Seco da Arena contra o favorito (722 jogos): acerta 32,5% x 29,0% da odd, mas no teste no tempo força 0,0.
  O excesso vem dos empates (610 jogos, 32,8% x 28,9%), que é a tendência geral da Loteca de o empate sair
  acima da odd - o nosso motor já usa isso. Seco no azarão: 112 jogos, força -1,6.
- Últimos 60 concursos: Arena 62,3% x previsto 63,2% - igual.

## 3. Prova: as derrotas são variação, não erro
Simulando os resultados com as chances do motor (400 vezes por concurso):

| | ganhar | empatar | perder |
|---|---|---|---|
| esperado se o motor estiver certo | 53% | 23% | 23% |
| o que aconteceu | 52% | 26% | 21% |

Mesmo com probabilidades perfeitas, uma cartela diferente faz mais pontos em cerca de 1 de cada 4-5 semanas.
Para perder menos semanas é preciso saber mais do que a odd sabe (informação nova), não marcar diferente.
