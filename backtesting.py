import sqlite3, math, os

DB_PATH = "loteca_historico.db"

def poisson_prob(lam, k):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam**k) * math.exp(-lam) / math.factorial(k)

def calcular_probs():
    lc = max(0.3, min(1.55*(1.55/max(0.5,(1.10+1.10)/2))*1.15, 5.0))
    lf = max(0.3, min(1.10*(1.10/max(0.5,(1.55+1.55)/2))*0.90, 5.0))
    p1=px=p2=0.0
    for i in range(8):
        for j in range(8):
            p=poisson_prob(lc,i)*poisson_prob(lf,j)
            if i>j: p1+=p
            elif i==j: px+=p
            else: p2+=p
    t=p1+px+p2
    return p1/t, px/t, p2/t

def previsto(p1,px,p2):
    if p1>=px and p1>=p2: return "1"
    elif px>=p1 and px>=p2: return "X"
    return "2"

def rodar():
    if not os.path.exists(DB_PATH):
        print(f"ERRO: banco nao encontrado em {os.getcwd()}")
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT numero FROM concursos ORDER BY numero")
    concursos = [r[0] for r in c.fetchall()]
    print(f"\n{'='*50}")
    print(f"  BACKTESTING — {len(concursos)} concursos")
    print(f"{'='*50}\n")
    total=a14=a13=a12=a11=a10=total_acertos=total_jogos=0
    for num in concursos:
        c.execute("SELECT resultado FROM jogos WHERE concurso=? ORDER BY sequencial",(num,))
        jogos=[r[0] for r in c.fetchall() if r[0]]
        if len(jogos)<14: continue
        total+=1
        pontos=0
        p1,px,p2=calcular_probs()
        prev=previsto(p1,px,p2)
        for res in jogos:
            total_jogos+=1
            if prev==res:
                pontos+=1
                total_acertos+=1
        if pontos==14: a14+=1
        elif pontos==13: a13+=1
        elif pontos==12: a12+=1
        elif pontos==11: a11+=1
        elif pontos==10: a10+=1
    if total==0:
        print("Nenhum concurso completo encontrado.")
        return
    anos=total/52
    assertividade=total_acertos/total_jogos*100 if total_jogos>0 else 0
    print(f"  Concursos: {total} ({anos:.1f} anos)")
    print(f"  Assertividade real: {assertividade:.1f}%")
    print(f"")
    print(f"  14 pontos: {a14}x ({a14/total*100:.2f}%) = {a14/anos:.1f}x/ano")
    print(f"  13 pontos: {a13}x ({a13/total*100:.2f}%) = {a13/anos:.1f}x/ano")
    print(f"  12 pontos: {a12}x ({a12/total*100:.2f}%) = {a12/anos:.1f}x/ano")
    print(f"  11 pontos: {a11}x ({a11/total*100:.2f}%) = {a11/anos:.1f}x/ano")
    print(f"{'='*50}\n")
    conn.close()

rodar()