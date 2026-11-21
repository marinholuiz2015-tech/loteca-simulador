"""
fetch_historico_cef.py  (Fase 1 do Estudo Base Unico, 21/11/2026)

Roda no GitHub Actions (nao no Render: a Caixa bloqueia o Render com 403).
Baixa os resultados de TODOS os concursos fechados da Loteca na API da
Caixa e grava em data/historico_cef.json, com os campos de cada jogo
exatamente como a Caixa devolve (inclui a sigla da UF de cada time).

Serve para duas coisas da Fase 1:
  1. resolver os 866 jogos ATLETICO-INDEFINIDO / AMERICA-INDEFINIDO
     (a UF separa ATLETICO-MG de ATLETICO-GO, AMERICA-MG de AMERICA-RN);
  2. trazer os concursos que faltam no banco (o app nao grava jogos novos).

Incremental: concursos ja presentes no arquivo nao sao baixados de novo.
Nunca esconde falha: concursos que falharam ficam listados em "falhas".
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

URL_CEF = "https://servicebus2.caixa.gov.br/portaldeloterias/api/loteca"
ARQUIVO = "data/historico_cef.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://loterias.caixa.gov.br/Paginas/Programacao-Loteca.aspx",
    "Origin": "https://loterias.caixa.gov.br",
}
PAUSA_SEG = 0.4
TENTATIVAS = 3
CAMPOS_CONCURSO = ["numero", "dataApuracao", "acumulado", "valorArrecadado",
                   "indicadorConcursoEspecial"]


def buscar(numero=""):
    url = f"{URL_CEF}/{numero}" if numero else URL_CEF
    ultimo = None
    for t in range(1, TENTATIVAS + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return 200, r.json()
            ultimo = r.status_code
            if r.status_code == 403:
                return 403, None
        except Exception as e:
            ultimo = f"excecao: {e}"
        time.sleep(3 * t)
    return ultimo, None


def main():
    base = {"gerado_em_utc": None, "ultimo_concurso": None,
            "concursos": {}, "falhas": {}}
    if os.path.exists(ARQUIVO):
        with open(ARQUIVO, encoding="utf-8") as f:
            base = json.load(f)
        base.setdefault("falhas", {})

    st, ult = buscar("")
    if st != 200:
        print(f"ERRO: nao consegui ler o ultimo concurso (status {st})")
        sys.exit(1)
    ultimo = int(ult["numero"])
    base["ultimo_concurso"] = ultimo

    limite = int(os.getenv("LIMITE", "0") or 0)  # 0 = sem limite
    pendentes = [n for n in range(1, ultimo + 1) if str(n) not in base["concursos"]]
    if limite:
        pendentes = pendentes[:limite]
    print(f"ultimo concurso fechado: {ultimo}; ja no arquivo: "
          f"{len(base['concursos'])}; a baixar agora: {len(pendentes)}")

    n_ok = n_403 = 0
    for i, n in enumerate(pendentes, 1):
        st, d = buscar(str(n))
        if st == 200 and d:
            jogos = d.get("listaResultadoEquipeEsportiva") or []
            base["concursos"][str(n)] = {
                **{k: d.get(k) for k in CAMPOS_CONCURSO},
                "jogos": jogos,
            }
            base["falhas"].pop(str(n), None)
            n_ok += 1
        else:
            base["falhas"][str(n)] = str(st)
            if st == 403:
                n_403 += 1
                if n_403 >= 5:
                    print("ERRO: 5 bloqueios 403 seguidos -- a Caixa bloqueou o runner. Parando.")
                    break
        if i % 100 == 0:
            print(f"  {i}/{len(pendentes)} processados")
        time.sleep(PAUSA_SEG)

    # resumo honesto do que veio, para conferencia
    n_jogos = n_com_uf = 0
    for c in base["concursos"].values():
        for j in c["jogos"]:
            n_jogos += 1
            if j.get("siglaUFEquipeUm") and j.get("siglaUFEquipeDois"):
                n_com_uf += 1
    base["gerado_em_utc"] = datetime.now(timezone.utc).isoformat()
    base["resumo"] = {
        "concursos_no_arquivo": len(base["concursos"]),
        "concursos_com_falha": len(base["falhas"]),
        "jogos_no_arquivo": n_jogos,
        "jogos_com_uf_dos_dois_times": n_com_uf,
    }
    os.makedirs("data", exist_ok=True)
    with open(ARQUIVO, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, separators=(",", ":"))
    print(f"baixados nesta rodada: {n_ok}; resumo: {base['resumo']}")
    if n_ok == 0 and pendentes:
        sys.exit(1)


if __name__ == "__main__":
    main()
