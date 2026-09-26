# -*- coding: utf-8 -*-
"""
kb_query.py — busca na base de conhecimento (global + obra), híbrida texto + significado.

Junta duas buscas por Reciprocal Rank Fusion:
  texto   FTS5/BM25 — acerta termo exato (grade_1, V301, G9, recuo de 11)
  vetor   similaridade de embedding — acerta por significado ("quem decide se passa")
e pondera pelo status da fonte (canônico sobe, histórico desce). Legado nem é indexado.

O resultado aponta a FONTE (caminho + seção): abrir a fonte antes de decidir. RAG nunca
é prova única (docs/CONHECIMENTO/MAPA-DO-CONHECIMENTO.md §8).

Uso:
    python scripts/kb/kb_query.py "quem decide Para ou Passa"
    python scripts/kb/kb_query.py "hachura de apoio" --classe LAJ -k 5
    python scripts/kb/kb_query.py "nível do segmento" --obra Obra_TREINO_1   # global + obra
    python scripts/kb/kb_query.py "selo laranja" --json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_comum import GLOBAL_DB, OBRAS_DIR, PESO_STATUS, criar_embedder  # noqa: E402

RRF_K = 60
# Peso de cada lista na fusão. Varredura 1.0–0.4 em kb_eval (2026-09-25, embedder local):
# diferença dentro do ruído (±1 pergunta); 1.0 maximiza hit@5. Rever ao trocar de embedder.
PESO_LISTA = {"texto": 1.0, "vetor": 1.0}
CANDIDATOS = 60
PESO_TIPO = {"decisao": 1.25, "glossario": 1.15, "regra_semantica": 1.1, "doc": 1.0, "codigo": 0.9}
STOP = set("""a o os as de da do das dos e é em no na nos nas um uma uns umas que se por para
pra com sem ao aos à às ou como qual quais quem onde quando porque isso isto essa esse este
esta ser ter faz fazer são está estão foi mais menos já não sim the of to and is""".split())

_EMB_CACHE: dict[str, object] = {}


def _tokens(pergunta: str) -> list[str]:
    palavras = re.findall(r"[\wÀ-ÿ.\-]+", pergunta.lower())
    return [p.strip(".-") for p in palavras if len(p.strip(".-")) >= 2 and p not in STOP]


def _filtros(classe: str | None, tipos: list[str] | None, sem_historico: bool) -> tuple[str, list]:
    sql, args = [], []
    if classe:
        sql.append("c.classes LIKE ?")
        args.append(f"%,{classe.upper()},%")
    if tipos:
        sql.append(f"c.tipo IN ({','.join('?' * len(tipos))})")
        args += tipos
    if sem_historico:
        sql.append("c.status != 'historico'")
    return (" AND " + " AND ".join(sql)) if sql else "", args


def busca_texto(con, pergunta, filtro_sql, filtro_args) -> list[str]:
    toks = _tokens(pergunta)
    if not toks:
        return []
    # Prefixo cobre flexão em português (decide/decidem, alterar/alterados): palavra com
    # 5+ letras vira radical* (corta até 2 letras do fim). Termo técnico curto fica exato.
    def _termo(t: str) -> str:
        t = t.replace('"', "")
        return f'"{t[:max(5, len(t) - 2)]}"*' if len(t) >= 5 and t.isalpha() else f'"{t}"'
    fts = " OR ".join(_termo(t) for t in toks)
    q = ("SELECT c.id FROM chunks_fts f JOIN chunks c ON c.rowid = f.rowid "
         f"WHERE chunks_fts MATCH ? {filtro_sql} ORDER BY bm25(chunks_fts, 3.0, 2.0, 1.0) LIMIT ?")
    try:
        return [r[0] for r in con.execute(q, [fts, *filtro_args, CANDIDATOS])]
    except sqlite3.OperationalError:
        return []


def busca_vetor(con, pergunta, filtro_sql, filtro_args) -> list[str]:
    meta = dict(con.execute("SELECT k, v FROM meta").fetchall())
    nome = meta.get("embedder", "")
    tipo = "nim" if nome.startswith("nim:") else "local"
    if tipo not in _EMB_CACHE:
        try:
            _EMB_CACHE[tipo] = criar_embedder(tipo)
        except Exception as exc:  # sem chave NIM, sem modelo local...
            print(f"[aviso] busca por significado indisponível ({exc}); só texto", file=sys.stderr)
            _EMB_CACHE[tipo] = None
    emb = _EMB_CACHE[tipo]
    if emb is None:
        return []
    rows = con.execute(
        f"SELECT c.id, v.vec FROM chunks c JOIN vetores v ON v.sha = c.sha AND v.embedder = ? "
        f"WHERE 1=1 {filtro_sql}", [nome, *filtro_args]).fetchall()
    if not rows:
        return []
    ids = [r[0] for r in rows]
    mat = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float32).reshape(len(rows), -1)
    q = emb.codificar([pergunta], consulta=True)[0]
    ordem = np.argsort(-(mat @ q))[:CANDIDATOS]
    return [ids[i] for i in ordem]


def buscar(pergunta: str, k: int = 8, classe: str | None = None, tipos: list[str] | None = None,
           obra: str | None = None, sem_historico: bool = False, modo: str = "hibrido",
           por_fonte: int = 2, db_global: Path | None = None) -> list[dict]:
    dbs = [db_global or GLOBAL_DB]
    if obra:
        dbs.append(OBRAS_DIR / f"{obra}.sqlite")
    fsql, fargs = _filtros(classe, tipos, sem_historico)
    placar: dict[tuple[str, str], float] = {}
    linhas: dict[tuple[str, str], dict] = {}
    for db in dbs:
        if not db.exists():
            print(f"[aviso] índice ausente: {db} (rodar kb_build.py)", file=sys.stderr)
            continue
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        listas = []
        if modo in ("hibrido", "texto"):
            listas.append(("texto", busca_texto(con, pergunta, fsql, fargs)))
        if modo in ("hibrido", "vetor"):
            listas.append(("vetor", busca_vetor(con, pergunta, fsql, fargs)))
        for nome, lista in listas:
            peso = PESO_LISTA[nome] if modo == "hibrido" else 1.0
            for pos, cid in enumerate(lista):
                placar[(str(db), cid)] = placar.get((str(db), cid), 0.0) + peso / (RRF_K + pos + 1)
        ids = [cid for (d, cid) in placar if d == str(db)]
        for cid in ids:
            r = con.execute("SELECT id, escopo, tipo, path, titulo, secao, status, tier, classes, data, texto "
                            "FROM chunks WHERE id = ?", (cid,)).fetchone()
            if r:
                linhas[(str(db), cid)] = dict(zip(
                    ("id", "escopo", "tipo", "path", "titulo", "secao", "status", "tier", "classes",
                     "data", "texto"), r))
        con.close()
    resultado = []
    for chave, base in placar.items():
        r = linhas.get(chave)
        if not r:
            continue
        r["score"] = base * PESO_STATUS.get(r["status"], 1.0) * PESO_TIPO.get(r["tipo"], 1.0)
        resultado.append(r)
    resultado.sort(key=lambda r: -r["score"])
    final, conta = [], {}
    for r in resultado:  # no máximo `por_fonte` trechos por arquivo: diversidade de fontes
        # decisão e termo de glossário são itens independentes (uma linha cada), mesmo
        # morando no mesmo arquivo — o limite vale por item, não por arquivo
        chave = r["id"] if r["tipo"] in ("decisao", "glossario", "regra_semantica") else r["path"]
        if conta.get(chave, 0) >= por_fonte:
            continue
        conta[chave] = conta.get(chave, 0) + 1
        final.append(r)
        if len(final) >= k:
            break
    return final


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pergunta")
    ap.add_argument("-k", type=int, default=8)
    ap.add_argument("--classe", choices=["PIL", "LV", "FV", "LAJ"])
    ap.add_argument("--tipo", action="append", choices=list(PESO_TIPO),
                    help="restringe o tipo (repetível): decisao, glossario, regra_semantica, doc, codigo")
    ap.add_argument("--obra", help="inclui KB-GLOBAL/obras/<obra>.sqlite")
    ap.add_argument("--sem-historico", action="store_true")
    ap.add_argument("--modo", default="hibrido", choices=["hibrido", "texto", "vetor"])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", type=Path, help="índice global alternativo (comparação)")
    args = ap.parse_args()
    res = buscar(args.pergunta, args.k, args.classe, args.tipo, args.obra, args.sem_historico, args.modo,
                 db_global=args.db)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    if not res:
        print("Nada encontrado.")
        return 1
    for i, r in enumerate(res, 1):
        marca = f" {r['tier']}" if r["tier"] else ""
        onde = f"{r['path']}" + (f"  §  {r['secao']}" if r["secao"] else "")
        trecho = re.sub(r"\s+", " ", r["texto"])[:260]
        print(f"{i}. [{r['tipo']} · {r['status']}{marca} · {r['escopo']}] {onde}\n   {trecho}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
