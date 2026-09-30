# -*- coding: utf-8 -*-
"""2ª passada da correção de nível (2026-09-26): cadeia derivada nos pilares e espelhos.

Pilares vizinhos de L317/L324/L325 copiaram o nível errado da laje e derivaram dele o
topo (nivel_saida_abs = nível da laje) e a base (nivel_chegada_abs = topo − altura).
Correção determinística: o valor errado vira o certo; a base anda o mesmo deslocamento.
Só em pilares cujo JSON cita a laje afetada. Espelhos (slab_elements/fase3) da própria
laje: rótulo e inferência seguem a linha corrigida em `slabs`.
"""
import argparse, json, re, sqlite3
from pathlib import Path

DB = "D:/Agente-cad-PYSIDE/project_data.vision"
PROJ = "dd238e47-1dc6-4f63-a760-4e7ce19a7386"
CORR = {"L317": (855.12, 852.15), "L324": (859.12, 852.19), "L325": (859.12, 852.19), "L318": (822.19, 851.89)}  # L318: só o registro da inferência (nível validado = 852.19)
AQUI = Path(__file__).resolve().parent


def fmt(x):
    return f"{x:.2f}"


def trocar(obj, errado, certo, trocas, trilha=""):
    desl = round(errado - certo, 2)
    if isinstance(obj, dict):
        out = {}
        saida_errada = isinstance(obj.get("nivel_saida_abs"), (int, float)) and abs(obj["nivel_saida_abs"] - errado) < 1e-6
        for k, v in obj.items():
            if k == "nivel_chegada_abs" and saida_errada and isinstance(v, (int, float)):
                novo = round(v - desl, 2); trocas.append((f"{trilha}.{k}", v, novo)); out[k] = novo; continue
            out[k] = trocar(v, errado, certo, trocas, f"{trilha}.{k}")
        return out
    if isinstance(obj, list):
        return [trocar(v, errado, certo, trocas, f"{trilha}[{i}]") for i, v in enumerate(obj)]
    if isinstance(obj, float) and abs(obj - errado) < 1e-6:
        trocas.append((trilha, obj, certo)); return certo
    if isinstance(obj, str) and fmt(errado) in obj:
        novo = obj.replace(fmt(errado), fmt(certo)); trocas.append((trilha, obj[:70], novo[:70])); return novo
    return obj


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--aplicar", action="store_true"); a = ap.parse_args()
    con = sqlite3.connect(DB if a.aplicar else f"file:{DB}?mode=ro", uri=not a.aplicar, timeout=60)
    plano, backup = [], []
    # pilares que citam uma laje afetada (a laje L318 ficou 852.19 validado; pilares com 822.19 não existem)
    for rid, nome, col, txt in [(r[0], r[1], c, r[i + 2]) for r in con.execute(
            "select id, name, extra_data_json, links_json from pillars where project_id=?", [PROJ])
            for i, c in enumerate(("extra_data_json", "links_json"))]:
        if not txt:
            continue
        lajes = [l for l in ("L317", "L324", "L325") if re.search(rf"\b{l}\b", txt)]
        errados = {CORR[l] for l in lajes if fmt(CORR[l][0]) in txt}
        if not errados:
            continue
        dado, trocas = json.loads(txt), []
        for errado, certo in errados:
            dado = trocar(dado, errado, certo, trocas)
        if trocas:
            plano.append(("pillars", col, "id", rid, dado, trocas, nome)); backup.append({"tabela": "pillars", "coluna": col, "id": rid, "valor": txt})
    # espelhos da própria laje (fase3/slab_elements): mesma correção da linha em `slabs`
    for tab, col, chave, filtro in (("slab_elements", "campos_json", "rowid", "project_id"), ("fase3_fichas", "dados_json", "rowid", "obra_id")):
        for rid, txt in con.execute(f'select {chave}, "{col}" from "{tab}" where "{filtro}"=?', [PROJ]).fetchall():
            if not txt:
                continue
            d = json.loads(txt)
            nome = (d.get("fields") or {}).get("nome") or d.get("name") or d.get("nome")
            if nome not in CORR or fmt(CORR[nome][0]) not in txt:
                continue
            trocas = []
            d = trocar(d, *CORR[nome], trocas)
            if trocas:
                plano.append((tab, col, chave, rid, d, trocas, nome)); backup.append({"tabela": tab, "coluna": col, "id": rid, "valor": txt})
    for tab, col, _, rid, _, trocas, nome in plano:
        print(f"{tab}.{col} [{nome} {str(rid)[-6:]}]: {len(trocas)} troca(s): " +
              "; ".join(f"{t[0].split('.')[-1]} {t[1]}→{t[2]}" for t in trocas[:3]))
    print(f"TOTAL: {sum(len(p[5]) for p in plano)} trocas em {len(plano)} linhas")
    if a.aplicar and plano:
        (AQUI / "backup_cadeia.json").write_text(json.dumps(backup, ensure_ascii=False, indent=1), encoding="utf-8")
        with con:
            for tab, col, chave, rid, d, _, _ in plano:
                con.execute(f'update "{tab}" set "{col}"=? where {chave}=?', (json.dumps(d, ensure_ascii=False), rid))
        print("APLICADO; backup em", AQUI / "backup_cadeia.json")


if __name__ == "__main__":
    main()
