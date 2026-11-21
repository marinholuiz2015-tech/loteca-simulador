"""
Enquete final da Vovoteca (efeito manada) -> coleta/dados/vovoteca_massa.csv

A Vovoteca publica a enquete em duas versoes: parciais durante a semana
(arte colorida, percentuais inteiros) e a versao final depois do fechamento
de sabado (nome com "finalizada", "encerrada" ou "final"), que e a tabela do
site da enquete com 2 decimais e total de votos. So a versao final entra
aqui: e a contagem completa e o formato que a leitura automatica le bem.

Uso:
  python coleta/vovoteca_enquete.py historico   # todas as finais publicadas
  python coleta/vovoteca_enquete.py semanal     # so concursos ainda nao gravados
  python coleta/vovoteca_enquete.py parciais    # ultima parcial dos concursos sem enquete final
  python coleta/vovoteca_enquete.py aberto      # parcial do concurso aberto (antes do fechamento)

Colunas: concurso, jogo, mandante, visitante (grade da Caixa), massa_1,
massa_x, massa_2 (% de votos), soma_ok (soma 100 +- 0,6), times_conferem
(nome lido na imagem bate com a Caixa), arquivo, coletado_em_utc.
So entram linhas com soma_ok=1; as outras ficam em vovoteca_massa_revisar.csv.
"""
import csv
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone

import requests

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "ocr"))
from ocr_vovo import checar, ler_imagem  # noqa: E402

REPO = os.path.dirname(AQUI)
DADOS = os.path.join(AQUI, "dados")
SAIDA = os.path.join(DADOS, "vovoteca_massa.csv")
REVISAR = os.path.join(DADOS, "vovoteca_massa_revisar.csv")
TMP = os.path.join(AQUI, "ocr", "_tmp_vovo")
MEDIA = "https://vovoteca.com/wp-json/wp/v2/media?search={q}&per_page=100&page={p}&_fields=date,source_url"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36"}
RE_FINAL = re.compile(r"final|encerr|fechad", re.I)
CAMPOS = ["concurso", "jogo", "mandante", "visitante", "massa_1", "massa_x", "massa_2",
          "soma_ok", "times_conferem", "texto_mandante", "texto_visitante", "arquivo",
          "versao", "coletado_em_utc"]


def listar_imagens(paginas=9):
    """Por concurso: a enquete final mais recente e a parcial mais recente."""
    finais, parciais = {}, {}
    for q in ("enq", "enquete"):
        for p in range(1, paginas + 1):
            r = requests.get(MEDIA.format(q=q, p=p), headers=UA, timeout=60)
            if r.status_code != 200:
                break
            d = r.json()
            if not d:
                break
            for m in d:
                nome = m["source_url"].rsplit("/", 1)[-1]
                mm = re.match(r"(\d{3,4})-(enq.*)\.(png|jpe?g)$", nome, re.I)
                if not mm:
                    continue
                c = int(mm.group(1))
                alvo = finais if RE_FINAL.search(mm.group(2)) else parciais
                if c not in alvo or m["date"] > alvo[c]["date"]:
                    alvo[c] = {"date": m["date"], "url": m["source_url"]}
            time.sleep(1)
    return finais, parciais


def listar_finais(paginas=9):
    return listar_imagens(paginas)[0]


def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z]", "", s)


def confere(texto, nome):
    a, b = _norm(texto), _norm(nome)
    return bool(a and b) and (a[:3] == b[:3] or a in b or b in a)


def grade_caixa():
    with open(os.path.join(REPO, "data", "historico_cef.json"), encoding="utf-8") as f:
        return json.load(f)["concursos"]


def processa(conc, url, cef, versao="final"):
    os.makedirs(TMP, exist_ok=True)
    arq = os.path.join(TMP, url.rsplit("/", 1)[-1])
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    with open(arq, "wb") as f:
        f.write(r.content)
    grade = {j["nuSequencial"]: j for j in cef.get(str(conc), {}).get("jogos", [])}
    mandantes = [grade.get(k, {}).get("nomeEquipeUm", "") for k in range(1, 15)]
    jogos = ler_imagem(arq, mandantes=mandantes if grade else None)
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    linhas = []
    for j in jogos:
        g = grade.get(j["jogo"], {})
        mand, vis = g.get("nomeEquipeUm", ""), g.get("nomeEquipeDois", "")
        linhas.append(dict(
            concurso=conc, jogo=j["jogo"], mandante=mand, visitante=vis,
            massa_1=j["massa_1"], massa_x=j["massa_x"], massa_2=j["massa_2"],
            soma_ok=int(not checar(j)),
            # concurso ainda aberto (sem grade oficial): nao ha com o que conferir
            times_conferem=(int(confere(j.get("texto_mandante", ""), mand) or
                                confere(j.get("texto_visitante", ""), vis)) if grade else ""),
            texto_mandante=j.get("texto_mandante", ""), texto_visitante=j.get("texto_visitante", ""),
            arquivo=url.rsplit("/", 1)[-1], versao=versao, coletado_em_utc=agora))
    os.remove(arq)
    return linhas


def _ler_csv(caminho):
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _gravar(caminho, linhas):
    linhas.sort(key=lambda r: (int(r["concurso"]), int(r["jogo"])))
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(linhas)


def main(modo):
    """historico/semanal: enquetes finais (substituem parciais do mesmo concurso).
    parciais: ultima parcial dos concursos encerrados que nao tem enquete final."""
    os.makedirs(DADOS, exist_ok=True)
    ok, rev = _ler_csv(SAIDA), _ler_csv(REVISAR)
    for r in ok + rev:
        r.setdefault("versao", "final")
        if not r.get("versao"):
            r["versao"] = "final"
    com_final = {int(r["concurso"]) for r in ok + rev if r["versao"] == "final"}
    feitos = {int(r["concurso"]) for r in ok + rev}
    finais, parciais = listar_imagens(paginas=9 if modo in ("historico", "parciais") else 1)
    cef = grade_caixa()
    if modo == "aberto":
        return registrar_aberto(parciais, cef)
    if modo == "parciais":
        minimo = int(os.environ.get("CONCURSO_MINIMO", "895"))  # 895 = inicio das odds da Arena
        alvo = {c: v for c, v in parciais.items()
                if c >= minimo and c not in finais and c not in feitos and str(c) in cef}
        versao = "parcial"
    else:
        alvo = {c: v for c, v in finais.items() if c not in com_final}
        versao = "final"
    falta = sorted(alvo)
    print(f"Modo {modo}: finais {len(finais)} | parciais {len(parciais)} | ja gravados {len(feitos)} | a ler {len(falta)}")
    nucleos = int(os.environ.get("NUCLEOS", "1"))
    if nucleos > 1:
        from multiprocessing import Pool
        with Pool(nucleos, initializer=_inicia_worker, initargs=(versao,)) as pool:
            resultados = pool.imap_unordered(_worker, [(c, alvo[c]["url"]) for c in falta])
            ok, rev = _consome(resultados, ok, rev, versao)
    else:
        ok, rev = _consome(((c, _processa_seguro(c, alvo[c]["url"], cef, versao)) for c in falta),
                           ok, rev, versao)
    _gravar(SAIDA, ok)
    _gravar(REVISAR, rev)
    print(f"Total: {len(ok)} jogos aceitos | {len(rev)} para revisar -> {SAIDA}")


ABERTO = os.path.join(DADOS, "vovoteca_massa_aberto.csv")


def registrar_aberto(parciais, cef):
    """Guarda a parcial mais recente do concurso ainda aberto (o que se sabe da
    massa ANTES do fechamento). Registro prospectivo: nunca e sobrescrito; cada
    nova parcial publicada vira um novo bloco de 14 linhas."""
    if not parciais:
        print("nenhuma parcial encontrada")
        return
    c = max(parciais)
    url = parciais[c]["url"]
    ja = _ler_csv(ABERTO)
    if any(r["arquivo"] == url.rsplit("/", 1)[-1] for r in ja):
        print(f"parcial do concurso {c} ja registrada ({url.rsplit('/', 1)[-1]})")
        return
    linhas = _processa_seguro(c, url, cef, "parcial")
    if not linhas:
        return
    linhas = [l for l in linhas if l["soma_ok"]]
    with open(ABERTO, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        if not ja:
            w.writeheader()
        w.writerows(linhas)
    print(f"concurso aberto {c}: {len(linhas)}/14 jogos da parcial registrados -> {ABERTO}")


def _processa_seguro(c, url, cef, versao):
    try:
        return processa(c, url, cef, versao)
    except Exception as e:
        print(f"  concurso {c}: falhou ({e})", flush=True)
        return None


_CEF = None
_VERSAO = None


def _inicia_worker(versao):
    global _CEF, _VERSAO
    _CEF, _VERSAO = grade_caixa(), versao


def _worker(arg):
    c, url = arg
    return c, _processa_seguro(c, url, _CEF, _VERSAO)


def _consome(resultados, ok, rev, versao):
    for c, linhas in resultados:
        if linhas is None:
            continue
        if versao == "final":  # a final substitui a parcial do mesmo concurso
            ok = [r for r in ok if int(r["concurso"]) != c]
            rev = [r for r in rev if int(r["concurso"]) != c]
        boas = [l for l in linhas if l["soma_ok"] and l["times_conferem"] != 0]
        ok += boas
        rev += [l for l in linhas if l not in boas]
        print(f"  concurso {c}: {len(boas)}/14 jogos aceitos", flush=True)
        _gravar(SAIDA, ok)  # grava a cada concurso: pode ser interrompido e retomado
        _gravar(REVISAR, rev)
    return ok, rev


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "semanal")
