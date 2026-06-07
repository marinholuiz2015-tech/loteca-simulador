import requests, sqlite3, time
from datetime import datetime

DB = 'loteca_historico.db'
URL = 'https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca'

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute('SELECT MAX(numero) FROM concursos')
ultimo = c.fetchone()[0] or 0
print('Ultimo no banco:', ultimo)
print('Coletando a partir de:', ultimo + 1)

falhas = 0
numero = ultimo + 1
coletados = 0

while falhas < 5:
    try:
        r = requests.get(URL + '/' + str(numero), timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200:
            print('Nao encontrado #' + str(numero))
            falhas += 1
            numero += 1
            continue
        d = r.json()
        falhas = 0
        t1 = d.get('listaResultadosEquipeUm', d.get('listaTimeCoracao', []))
        t2 = d.get('listaResultadosEquipeDois', [])
        res = d.get('listaDezenas', d.get('dezenas', []))
        agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('INSERT OR REPLACE INTO concursos(numero,data_apuracao,data_proximo,acumulado,arrecadacao,coletado_em) VALUES(?,?,?,?,?,?)',
            (numero, d.get('dataApuracao',''), d.get('dataProximoConcurso',''),
             1 if d.get('acumulado') else 0, 0.0, agora))
        c.execute('DELETE FROM jogos WHERE concurso=?', (numero,))
        for i in range(max(len(t1), len(res), 1)):
            c.execute('INSERT INTO jogos(concurso,sequencial,mandante,visitante,resultado) VALUES(?,?,?,?,?)',
                (numero, i+1,
                 t1[i] if i < len(t1) else 'Time A',
                 t2[i] if i < len(t2) else 'Time B',
                 res[i] if i < len(res) else '?'))
        conn.commit()
        print('OK #' + str(numero) + ' - ' + d.get('dataApuracao', '?') + ' - ' + str(len(t1)) + ' jogos')
        coletados += 1
        numero += 1
        time.sleep(0.4)
    except Exception as e:
        print('ERRO #' + str(numero) + ': ' + str(e))
        falhas += 1
        numero += 1

c.execute('SELECT COUNT(*) FROM concursos')
tc = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM jogos')
tj = c.fetchone()[0]
c.execute('SELECT MIN(numero), MAX(numero) FROM concursos')
mn, mx = c.fetchone()
conn.close()
print('Finalizado! Novos: ' + str(coletados))
print('Total banco: ' + str(tc) + ' concursos, ' + str(tj) + ' jogos')
print('Periodo: #' + str(mn) + ' ate #' + str(mx))
