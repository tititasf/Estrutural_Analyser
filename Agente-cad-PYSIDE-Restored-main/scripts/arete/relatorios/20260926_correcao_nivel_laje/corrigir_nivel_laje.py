# -*- coding: utf-8 -*-
"""Correção pontual do bug de unidade cm×m no nível de laje (13_PAV, 2026-09-26).

Só troca um valor errado quando ele aparece LIGADO ao nome da laje afetada (mesmo
objeto JSON ou mesma string). Valores calculados que não carregam o nome da laje
ficam para o recálculo do pipeline. Sem --aplicar: só lista (dry-run).
Com --aplicar: backup das linhas tocadas em backup_linhas.json, uma transação.
"""
import argparse, json, re, sqlite3, sys
from pathlib import Path

DB = "D:/Agente-cad-PYSIDE/project_data.vision"
PROJ = "dd238e47-1dc6-4f63-a760-4e7ce19a7386"          # 13_PAV ativo (Obra_TREINO_1)
CORRECAO = {"L317": ("855.12", "852.15"), "L318": ("822.19", "851.89"),
            "L324": ("859.12", "852.19"), "L325": ("859.12", "852.19")}
ALVOS = [("slabs", "links_json", "id"), ("slabs", "extra_data_json", "id"),
         ("slab_elements", "campos_json", "rowid"), ("fase3_fichas", "dados_json", "rowid"),
         ("beams", "links_json", "id"), ("pillars", "extra_data_json", "id"), ("pillars", "links_json", "id")]
RE_NOME = {n: re.compile(rf"\b{n}\b") for n in CORRECAO}
AQUI = Path(__file__).resolve().parent


def menciona(obj, nome):
    return any(isinstance(v, str) and RE_NOME[nome].search(v) for v in obj.values())


def corrigir(obj, trocas, trilha=""):
    """Percorre o JSON; troca o valor errado só em objeto que cita a laje."""
    if isinstance(obj, list):
        return [corrigir(x, trocas, f"{trilha}[{i}]") for i, x in enumerate(obj)]
    if not isinstance(obj, dict):
        return obj
    nomes = [n for n in CORRECAO if menciona(obj, n)]
    novo = {}
    for k, v in obj.items():
        if isinstance(v, str):
            for n, (errado, certo) in CORRECAO.items():
                if errado in v and (n in nomes or RE_NOME[n].search(v)):
                    v2 = v.replace(errado, certo)
                    if v2 != v:
                        trocas.append((f"{trilha}.{k}", n, v[:90], v2[:90])); v = v2
        elif isinstance(v, dict) and nomes and isinstance(v.get("nivel"), str):
            # "Laje adjacente": {"text": "L324", "ficha": {"nivel": "859.12"}}
            for n in nomes:
                errado, certo = CORRECAO[n]
                if v["nivel"] == errado:
                    trocas.append((f"{trilha}.{k}.nivel", n, errado, certo)); v = {**v, "nivel": certo}
        novo[k] = corrigir(v, trocas, f"{trilha}.{k}")
    return novo


def _troca_valor(obj, errado, certo, trocas, nome, trilha):
    if isinstance(obj, dict):
        return {k: _troca_valor(v, errado, certo, trocas, nome, f"{trilha}.{k}") for k, v in obj.items()}
    if isinstance(obj, list):
        return [_troca_valor(v, errado, certo, trocas, nome, f"{trilha}[{i}]") for i, v in enumerate(obj)]
    if isinstance(obj, str) and errado in obj:
        trocas.append((trilha, nome, obj[:90], obj.replace(errado, certo)[:90])); return obj.replace(errado, certo)
    if isinstance(obj, float) and abs(obj - float(errado)) < 1e-6:
        trocas.append((trilha, nome, obj, float(certo))); return float(certo)
    return obj


def propria_laje(dado, nome, col, trocas):
    """Na linha da própria laje, o rótulo e a inferência citam a laje de ORIGEM, não ela."""
    errado, certo = CORRECAO[nome]
    if col == "links_json" and isinstance(dado.get("laje_nivel"), dict):
        dado["laje_nivel"] = _troca_valor(dado["laje_nivel"], errado, certo, trocas, nome, ".laje_nivel")
    if col == "extra_data_json" and isinstance(dado.get("level_inference"), dict):
        li = _troca_valor(dado["level_inference"], errado, certo, trocas, nome, ".level_inference")
        sys.path.insert(0, str(AQUI.parents[3]))
        from src.core.slab_level_inference import gate_cut_delta_level
        delta = next((s.get("delta") for s in li.get("sources") or [] if s.get("delta") is not None), None)
        rotulo = {"L324": 852.19}.get(nome)   # cota escrita na planta (rótulo layer 3 da L324)
        veredito = gate_cut_delta_level(float(certo), delta if delta is not None else 0.0,
                                        reference_level_m=852.12, own_label_level_m=rotulo)
        li["gates"] = veredito["gates"]
        li["correcao"] = {"data": "2026-09-26", "motivo": "bug de unidade: delta do corte em cm somado ao nível em m",
                          "valor_anterior": errado, "valor_corrigido": certo,
                          "fonte": "docs/CONHECIMENTO/DECISOES-DO-DONO.md (Pendente: nível de laje)"}
        dado["level_inference"] = li
    return dado


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--aplicar", action="store_true"); a = ap.parse_args()
    con = sqlite3.connect(DB if a.aplicar else f"file:{DB}?mode=ro", uri=not a.aplicar, timeout=60)
    mudancas, backup = [], []
    for tab, col, chave in ALVOS:
        cols = [r[1] for r in con.execute(f'pragma table_info("{tab}")')]
        col_proj = "project_id" if "project_id" in cols else ("obra_id" if "obra_id" in cols else None)
        filtro = f'where "{col_proj}"=?' if col_proj else ""
        args = [PROJ] if filtro else []
        if tab == "slabs":
            nome_por_id = dict(con.execute("select id, name from slabs where project_id=?", [PROJ]).fetchall())
        for rid, txt in con.execute(f'select {chave}, "{col}" from "{tab}" {filtro}', args).fetchall():
            if not txt or not any(e in txt for e, _ in CORRECAO.values()):
                continue
            try:
                dado = json.loads(txt)
            except ValueError:
                continue
            trocas = []
            novo = corrigir(dado, trocas)
            if tab == "slabs" and nome_por_id.get(rid) in CORRECAO:
                novo = propria_laje(novo, nome_por_id[rid], col, trocas)
            if trocas:
                mudancas.append((tab, col, chave, rid, novo, trocas)); backup.append({"tabela": tab, "coluna": col, "chave": chave, "id": rid, "valor": txt})
    for tab, col, chave, rid, _, trocas in mudancas:
        print(f"{tab}.{col} [{rid}]: {len(trocas)} troca(s)")
        for caminho, n, antes, depois in trocas[:4]:
            print(f"    {n} {caminho[-60:]}: {antes!r} -> {depois!r}")
    print(f"TOTAL: {sum(len(m[5]) for m in mudancas)} trocas em {len(mudancas)} linhas")
    if a.aplicar and mudancas:
        (AQUI / "backup_linhas.json").write_text(json.dumps(backup, ensure_ascii=False, indent=1), encoding="utf-8")
        with con:
            for tab, col, chave, rid, novo, _ in mudancas:
                con.execute(f'update "{tab}" set "{col}"=? where {chave}=?', (json.dumps(novo, ensure_ascii=False), rid))
        print("APLICADO; backup em", AQUI / "backup_linhas.json")


if __name__ == "__main__":
    main()
