"""Confronto: jogos prontos do Arena do AZ e da Vovoteca x nosso palpite nos mesmos concursos
(mesma quantidade de secos, duplos e triplos). Uso: python motor/confronto_sites.py > motor/confronto_sites.md"""
import csv,json,math,sys,collections,numpy as np
sys.path.insert(0,'motor'); import camada2 as c2
from calibracao import sem_margem, ajusta_gama
# resultados oficiais
H=json.load(open('data/historico_cef.json'))['concursos']
res={}
for k,c in H.items():
    js=sorted(c['jogos'],key=lambda j:j['nuSequencial'])
    if len(js)==14 and all(j['nuGolEquipeUm'] is not None for j in js):
        res[int(k)]=[0 if j['nuGolEquipeUm']>j['nuGolEquipeDois'] else (1 if j['nuGolEquipeUm']==j['nuGolEquipeDois'] else 2) for j in js]
rat=c2.rateio(); odds=c2.odds_por_concurso()
def carregar(arq,col='marcas'):
    d=collections.defaultdict(dict)
    for r in csv.DictReader(open(arq)): d[int(r['concurso'])][int(r['jogo'])]=sorted("1X2".index(x) for x in r[col])
    return {c:[v[j] for j in range(1,15)] for c,v in d.items() if len(v)==14}
def avalia(cart,r,R):
    ok=[r[i] in cart[i] for i in range(14)]; er=ok.count(False); tam=[len(x) for x in cart]
    pr=0;n14=er==0
    if R:
        if er==0: c13=sum(t-1 for t in tam); pr+=R['pool_14']/(R['ganhadores_14']+1)
        elif er==1: c13=tam[ok.index(False)]
        else: c13=0
        if c13: pr+=c13*R['pool_13']/(R['ganhadores_13']+c13)
    secos=[ok[i] for i in range(14) if tam[i]==1]; duplos=[ok[i] for i in range(14) if tam[i]==2]
    return 14-er, er<=1, n14, pr, secos, duplos
def confronto(nome,outro):
    cs=[c for c in outro if c in res and len(odds.get(c,{}))==14]
    T=collections.defaultdict(lambda:[0,0,0,0.0,0.0,[],[]])
    for c in cs:
        A=outro[c]; d=sum(len(x)==2 for x in A); t=sum(len(x)==3 for x in A)
        P=[c2.prob_mercado(odds[c][j]) for j in range(1,15)]
        N=c2.cartela(P,d,t)
        R=rat.get(c); custo=2**d*3**t*2
        for quem,cart in ((nome,A),('Nosso (mesma estrutura)',N)):
            pts,s13,s14,pr,se,du=avalia(cart,res[c],R)
            x=T[quem]; x[0]+=pts; x[1]+=s13; x[2]+=s14; x[3]+=pr; x[4]+=custo if R else 0; x[5]+=se; x[6]+=du
    n=len(cs)
    print(f"\n=== {nome} x nosso sistema: {n} concursos (mesmos jogos, mesma quantidade de secos/duplos/triplos) ===")
    print(f"{'':26s} {'pontos/conc.':>12s} {'13 ou 14':>9s} {'fez 14':>7s} {'secos certos':>13s} {'duplos certos':>14s} {'retorno':>8s}")
    for quem,x in T.items():
        print(f"{quem:26s} {x[0]/n:12.2f} {x[1]:9d} {x[2]:7d} {100*np.mean(x[5]):12.1f}% {100*np.mean(x[6]) if x[6] else float('nan'):13.1f}% {100*x[3]/x[4] if x[4] else 0:7.1f}%")
    return cs
aaz=carregar('coleta/dados/arena_palpites.csv')
confronto('Arena do AZ',aaz)

cs=[c for c in aaz if c in res and len(odds.get(c,{}))==14]
dif=[];sec=[]
for c in cs:
    A=aaz[c]; d=sum(len(x)==2 for x in A); t=sum(len(x)==3 for x in A)
    N=c2.cartela([c2.prob_mercado(odds[c][j]) for j in range(1,15)],d,t)
    dif.append(avalia(N,res[c],None)[0]-avalia(A,res[c],None)[0])
dif=np.array(dif); print(f"\ndiferenca de pontos por concurso (nosso - Arena): {dif.mean():+.2f} | erro {dif.std()/math.sqrt(len(dif)):.2f} | z {dif.mean()/(dif.std()/math.sqrt(len(dif))):+.1f} | nosso melhor em {np.mean(dif>0)*100:.0f}% dos concursos, empate {np.mean(dif==0)*100:.0f}%, Arena melhor {np.mean(dif<0)*100:.0f}%")

vov=carregar('coleta/dados/vovo_matriz.csv','seco')
cs=confronto('Vovoteca (matriz, 14 secos)',vov)
dif=[]
for c in cs:
    N=c2.cartela([c2.prob_mercado(odds[c][j]) for j in range(1,15)],0,0)
    dif.append(avalia(N,res[c],None)[0]-avalia(vov[c],res[c],None)[0])
dif=np.array(dif); se=dif.std()/math.sqrt(len(dif))
print(f"\ndiferenca (nosso - Vovoteca): {dif.mean():+.2f} | erro {se:.2f} | z {dif.mean()/se:+.1f} | nosso melhor {np.mean(dif>0)*100:.0f}%, empate {np.mean(dif==0)*100:.0f}%, Vovo melhor {np.mean(dif<0)*100:.0f}%")
# concordancia e quem acerta quando discordam
a=b=n=0
for c in cs:
    P=[c2.prob_mercado(odds[c][j]) for j in range(1,15)]
    for j in range(14):
        nos=int(np.argmax(P[j])); v=vov[c][j][0]
        if nos!=v: n+=1; a+=res[c][j]==nos; b+=res[c][j]==v
print(f"jogos em que discordam: {n} | nosso acerta {a} ({100*a/n:.0f}%) | Vovo acerta {b} ({100*b/n:.0f}%)")
