"""
Cartola FC (API oficial, publica) — escalacao provavel e peso dos desfalques dos times brasileiros da grade.

Para cada time brasileiro do concurso aberto:
  provaveis     - jogadores com status "Provavel" no Cartola
  desfalques    - contundidos e suspensos que jogam (5+ jogos), com a media de pontos de cada um
  duvidas       - jogadores em duvida
  forca_pct     - soma das medias dos 11 melhores provaveis / soma das medias dos 11 melhores do elenco
                  (contando contundidos, suspensos e duvidas). 100% = time completo; 80% = perdeu muita forca.
Saida: coleta/dados/cartola_aberto.csv (acrescenta um retrato por coleta; nunca apaga).
Uso: python coleta/sentinela/cartola.py
"""
import csv
import datetime as dt
import json
import os
import sys

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
DADOS = os.path.join(REPO, "coleta", "dados")
API = "https://api.cartola.globo.com"
HEAD = {"User-Agent": "Mozilla/5.0 (pesquisa pessoal; coleta leve)"}
STATUS = {2: "dúvida", 3: "suspenso", 5: "contundido", 6: "nulo", 7: "provável"}
CAMPOS = ["concurso", "jogo", "lado", "time_grade", "clube_cartola", "rodada_cartola", "provaveis", "forca_pct",
          "desfalques", "duvidas", "coletado_em_utc"]


def forca(atl):
    top = lambda L: sum(sorted((a["media_num"] for a in L), reverse=True)[:11])  # noqa: E731
    elenco = [a for a in atl if a["status_id"] in (2, 3, 5, 7) and a["jogos_num"] >= 3]
    prov = [a for a in atl if a["status_id"] == 7]
    if not prov:
        return None  # o Cartola ainda nao marcou provaveis para este time
    base = top(elenco)
    return round(100 * top(prov) / base, 1) if base > 0 else None


def main():
    sys.path.insert(0, AQUI)
    sys.path.insert(0, os.path.join(REPO, "motor"))
    import noticias as N
    import camada1
    m = requests.get(f"{API}/atletas/mercado", headers=HEAD, timeout=40).json()
    rodada = (requests.get(f"{API}/mercado/status", headers=HEAD, timeout=30).json() or {}).get("rodada_atual")
    clubes = {int(k): v for k, v in m["clubes"].items()}
    por_clube = {}
    for a in m["atletas"]:
        por_clube.setdefault(a["clube_id"], []).append(a)
    c = max(camada1.arena().keys())
    grade, _ = camada1.grade_caixa(c)
    if not grade:
        grade, _, _ = camada1.grade_guia(c)
    if not grade:
        grade, _ = camada1.grade_arena(camada1.arena(c))
    agora = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    linhas = []
    for j in sorted(grade):
        for lado, nome in zip(("mandante", "visitante"), grade[j]):
            if not N.brasileiro(nome):
                continue
            busca = N.sem_acento(N.nome_busca(nome))
            uf = N.limpa(nome)[-2:].lower()
            busca = busca.replace("athletico", "atletico")  # o Cartola usa "atletico-pr" para o Athletico
            melhor = None
            for cid, cl in clubes.items():
                slug = cl.get("slug", "").replace("-", " ")
                if slug in (f"{busca} {uf}", busca) or N.sem_acento(cl.get("apelido", "")) == busca:
                    melhor = cid
                    break
            if melhor is None:  # nome da grade maior que o slug (ex.: "vasco da gama" x "vasco")
                for cid, cl in clubes.items():
                    slug = cl.get("slug", "").replace("-", " ")
                    if len(slug) >= 5 and busca.startswith(slug + " ") and slug not in N.GENERICAS:
                        melhor = cid
                        break
            if not melhor:
                continue
            atl = por_clube.get(melhor, [])
            fora = sorted([a for a in atl if a["status_id"] in (3, 5) and a["jogos_num"] >= 5], key=lambda a: -a["media_num"])
            duv = sorted([a for a in atl if a["status_id"] == 2], key=lambda a: -a["media_num"])
            linhas.append({
                "concurso": c, "jogo": j, "lado": lado, "time_grade": nome, "clube_cartola": clubes[melhor].get("slug"),
                "rodada_cartola": rodada, "provaveis": sum(a["status_id"] == 7 for a in atl), "forca_pct": forca(atl),
                "desfalques": json.dumps([{"nome": a["apelido"], "status": STATUS[a["status_id"]], "media": a["media_num"],
                                           "jogos": a["jogos_num"]} for a in fora], ensure_ascii=False),
                "duvidas": json.dumps([{"nome": a["apelido"], "media": a["media_num"]} for a in duv], ensure_ascii=False),
                "coletado_em_utc": agora})
            print(f"Jogo {j} {lado}: {nome} -> {clubes[melhor].get('slug')} | força "
                  f"{str(linhas[-1]['forca_pct']) + '%' if linhas[-1]['forca_pct'] is not None else 'sem provaveis ainda'} | "
                  f"fora: {', '.join(a['apelido'] + ' (' + STATUS[a['status_id']] + ')' for a in fora[:5]) or '-'}")
    if not linhas:
        print("Cartola: nenhum time brasileiro na grade")
        return 0
    arq = os.path.join(DADOS, "cartola_aberto.csv")
    novo = not os.path.exists(arq)
    with open(arq, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if novo:
            w.writeheader()
        w.writerows(linhas)
    print(f"Cartola: {len(linhas)} times gravados (rodada {rodada})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
