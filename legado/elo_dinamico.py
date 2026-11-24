"""
elo_dinamico.py
================
Elo dinâmico calculado a partir do histórico real de 17.602 jogos
(carregado uma vez no boot do app.py, tabela elo_times no Postgres).

Este arquivo é isolado de propósito: não depende de nada do app.py
além da função get_conn, que é passada como parâmetro -- assim dá
pra colocar esse arquivo no repositório sem editar o app.py em si,
só adicionando 3 linhas nele (import, uma chamada, e a troca de
duas linhas dentro de poisson_probs). Nada precisa ser apagado.
"""
import logging

log = logging.getLogger("loteca")

# Fallback: usado só se o banco estiver fora do ar no boot, ou se
# por algum motivo um time não tiver rating dinâmico calculado.
ELO_FALLBACK = {
    "Argentina":2140,"França":2100,"Inglaterra":2080,"Espanha":2070,
    "Alemanha":2060,"Portugal":2040,"Holanda":2030,"Brasil":2050,
    "Bélgica":1990,"Uruguai":1960,"Itália":2010,"México":1880,
    "Estados Unidos":1880,"Marrocos":1900,"Japão":1870,"Coreia do Sul":1850,
    "Equador":1830,"Suíça":1870,"Canadá":1840,"Austrália":1820,
    "Turquia":1840,"Escócia":1820,"Arábia Saudita":1780,"Paraguai":1780,
    "Catar":1650,"Curaçao":1540,"Cabo Verde":1660,"África do Sul":1700,
    "Rep. Tcheca":1820,"Haiti":1490,"Egito":1770,"Costa do Marfim":1820,
    "Senegal":1850,"Congo-Kinshasa":1650,"Argélia":1700,"Noruega":1830,
    "Iraque":1580,"Croácia":1890,
    "Palmeiras":1820,"Flamengo":1810,"Botafogo":1780,"Fluminense":1750,
    "Atletico MG":1760,"São Paulo":1740,"Corinthians":1720,"Grêmio":1700,
    "Internacional":1710,"Cruzeiro":1690,"Vasco da Gama":1660,"Santos":1650,
    "Fortaleza":1670,"Bahia":1640,"Mirassol":1610,"Juventude":1590,
    "Vitória":1580,"Sport":1560,"Bragantino":1620,"Athletico PR":1660,
    "Chapecoense":1480,"Londrina":1470,"Remo":1460,"CRB":1450,
    "Manchester City":1810,"Arsenal":1750,"Liverpool":1790,"Chelsea":1730,
    "Manchester United":1700,"Tottenham":1690,"Aston Villa":1720,
    "Crystal Palace":1680,"Everton":1620,"Newcastle":1700,
}

ELO_DINAMICO = {}  # populado por carregar_elo_dinamico()

def carregar_elo_dinamico(get_conn):
    """Chama isso uma vez no boot do app.py, passando a função get_conn
    que já existe lá. Não roda a cada requisição -- só no startup."""
    global ELO_DINAMICO
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT time, rating FROM elo_times")
        ELO_DINAMICO = {row[0]: float(row[1]) for row in cur.fetchall()}
        conn.close()
        log.info("Elo dinâmico carregado: %d times", len(ELO_DINAMICO))
    except Exception as e:
        log.warning("Elo dinâmico indisponível, usando fallback estático: %s", e)
        ELO_DINAMICO = {}

def elo_do_time(nome):
    """Busca rating: dinâmico (histórico real) > fallback estático > 1500 genérico."""
    if nome in ELO_DINAMICO:
        return ELO_DINAMICO[nome]
    if nome in ELO_FALLBACK:
        return ELO_FALLBACK[nome]
    return 1500
