"""
resultados_painel.py — resultados e rateio oficiais dos concursos recentes para a conferencia do painel.

Junta tres fontes, da mais nova para a mais antiga:
  1. data/cef_cache.json (ultimo concurso apurado, atualizado a cada 30 min pelo fetch_loteca.yml);
  2. coleta/dados/rateio_caixa.csv (rateio oficial de cada concurso);
  3. data/historico_cef.json (placares de todos os concursos).

Grava docs/dados/resultados.json com os ultimos N concursos:
  {"gerado_utc": ..., "concursos": {"1283": {"res": "1X2...", "jogos": [...], "premio14": ..., "premio13": ...,
   "ganhadores14": ..., "ganhadores13": ..., "acumulou": bool, "acumulado_proximo": ..., "data": ...}}}
Uso: python scripts/resultados_painel.py
"""
import ast
import csv
import json
import os
from datetime import datetime, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = 60


def ler_json(caminho):
    try:
        with open(os.path.join(RAIZ, caminho), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def lista(v):
    """a cache guarda algumas listas como texto (repr do Python)."""
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip().startswith("["):
        try:
            return ast.literal_eval(v)
        except Exception:
            return []
    return []


def resultado(j):
    a, b = j.get("nuGolEquipeUm"), j.get("nuGolEquipeDois")
    if a is None or b is None:
        return None
    return "1" if a > b else ("X" if a == b else "2")


def jogos_de(js):
    js = sorted(js, key=lambda j: j.get("nuSequencial", 0))
    if len(js) != 14:
        return None
    out = []
    for j in js:
        out.append({"m": j.get("nomeEquipeUm", ""), "v": j.get("nomeEquipeDois", ""),
                    "placar": [j.get("nuGolEquipeUm"), j.get("nuGolEquipeDois")], "res": resultado(j)})
    if any(x["res"] is None for x in out):
        return None
    return out


def main():
    conc = {}
    hist = (ler_json("data/historico_cef.json") or {}).get("concursos", {})
    for k in sorted(hist, key=int)[-N:]:
        jg = jogos_de(hist[k].get("jogos") or [])
        if jg:
            conc[int(k)] = {"jogos": jg, "data": hist[k].get("dataApuracao", "")}
    arq = os.path.join(RAIZ, "coleta", "dados", "rateio_caixa.csv")
    if os.path.exists(arq):
        with open(arq, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                c = int(r["concurso"])
                if c in conc:
                    conc[c].update(premio14=float(r["premio_14"]), premio13=float(r["premio_13"]),
                                   ganhadores14=int(float(r["ganhadores_14"])), ganhadores13=int(float(r["ganhadores_13"])),
                                   acumulado_proximo=float(r.get("acumulado_proximo") or 0))
    u = (ler_json("data/cef_cache.json") or {}).get("dados_ultimo") or {}
    if u.get("numero"):
        c = int(u["numero"])
        jg = jogos_de(lista(u.get("listaResultadoEquipeEsportiva")))
        if jg:
            item = conc.setdefault(c, {})
            item.update(jogos=jg, data=u.get("dataApuracao", ""))
            fx = {r.get("faixa"): r for r in lista(u.get("listaRateioPremio"))}
            if 1 in fx and 2 in fx:
                item.update(premio14=float(fx[1]["valorPremio"]), premio13=float(fx[2]["valorPremio"]),
                            ganhadores14=int(fx[1]["numeroDeGanhadores"]), ganhadores13=int(fx[2]["numeroDeGanhadores"]),
                            acumulado_proximo=float(u.get("valorAcumuladoProximoConcurso") or 0))
    out = {}
    for c in sorted(conc)[-N:]:
        x = conc[c]
        if not x.get("jogos"):
            continue
        x["res"] = "".join(j["res"] for j in x["jogos"])
        x["rateio"] = "premio14" in x
        x["acumulou"] = bool(x["rateio"] and x.get("ganhadores14", 0) == 0)
        out[str(c)] = x
    destino = os.path.join(RAIZ, "docs", "dados", "resultados.json")
    with open(destino, "w", encoding="utf-8") as f:
        json.dump({"gerado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "concursos": out},
                  f, ensure_ascii=False, separators=(",", ":"))
    print(f"resultados.json: {len(out)} concursos (ultimo {max(out, key=int) if out else '-'})")


if __name__ == "__main__":
    main()
