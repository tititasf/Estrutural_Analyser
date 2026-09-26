# -*- coding: utf-8 -*-
"""
kb_build.py — constrói o índice da base de conhecimento (global ou de uma obra).

Global (padrão): indexa as fontes com status entrada/canonico/ativo/historico do
inventário (kb_inventario.py), o glossário e as decisões do dono linha a linha, o mapa
de código e as regras T1+ da tabela semantic_rag_kb (somente leitura no DB real).
Legado e candidato_obsoleto ficam fora.

Por obra: indexa uma pasta de textos da obra num arquivo separado, com o mesmo
esquema (docs/CONHECIMENTO/CONTRATO-KB-MULTIOBRA.md).

Vetores são cacheados por hash de conteúdo + embedder: reconstruir só recalcula o que
mudou. O índice é derivado — apagar KB-GLOBAL/ e rodar de novo reproduz tudo.

Uso:
    python scripts/kb/kb_build.py                         # global, embedder NIM (padrão medido)
    python scripts/kb/kb_build.py --embedder local        # global offline (modelo local, sem rede)
    python scripts/kb/kb_build.py --obra Obra_TREINO_1 --fontes <pasta>   # KB da obra
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kb_comum import (ESQUEMA_VERSAO, GLOBAL_DB, OBRAS_DIR, STATUS_INDEXADOS, WORKSPACE,  # noqa: E402
                      conectar, criar_embedder, detectar_classes, fatiar_markdown, sha256,
                      texto_para_vetor)

POR_LINHA = {"GLOSSARIO.md": "glossario", "DECISOES-DO-DONO.md": "decisao", "MAPA-CODIGO.md": "codigo"}
RE_OBRA = re.compile(r"^[\w .\-\[\]]+$")


def _chunk(escopo, tipo, path, titulo, secao, status, tier, data, ordem, texto) -> dict:
    return {
        "id": hashlib.sha1(f"{escopo}|{path}|{secao}|{ordem}".encode()).hexdigest(),
        "escopo": escopo, "tipo": tipo, "path": path, "titulo": titulo, "secao": secao,
        # o título do doc conta como a seção: "Semântica — Laje NOVA" já marca LAJ
        "status": status, "tier": tier, "classes": detectar_classes(path, f"{titulo} {secao}", texto),
        "data": data, "ordem": ordem, "texto": texto.strip(),
    }


def _linhas_de_tabela(txt: str) -> list[tuple[str, str, str]]:
    """(seção, cabeçalho, linha) para cada linha de dados de tabela markdown."""
    saida, secao, cab = [], "", ""
    linhas = txt.splitlines()
    for i, ln in enumerate(linhas):
        m = re.match(r"^#{1,4}\s+(.*)$", ln)
        if m:
            secao, cab = m.group(1).strip(), ""
            continue
        if ln.startswith("|"):
            prox = linhas[i + 1] if i + 1 < len(linhas) else ""
            if not cab and set(prox.replace("|", "").strip()) <= set("-: ") and prox.startswith("|"):
                cab = ln
            elif not set(ln.replace("|", "").strip()) <= set("-: "):
                saida.append((secao, cab, ln))
        else:
            cab = ""  # linha fora de tabela encerra a tabela; a próxima tem cabeçalho próprio
    return saida


def chunks_globais() -> tuple[list[dict], int]:
    from kb_inventario import classificar, coletar
    fontes = coletar()
    classificar(fontes)
    chunks: list[dict] = []
    usadas = 0
    for f in fontes:
        if f["status"] not in STATUS_INDEXADOS or not f["nome"].lower().endswith(".md"):
            continue
        usadas += 1
        tipo_linha = POR_LINHA.get(f["nome"]) if "CONHECIMENTO" in f["path"] else None
        if tipo_linha:
            tier = "T1" if tipo_linha == "decisao" else None
            for i, (secao, cab, ln) in enumerate(_linhas_de_tabela(f["_texto"])):
                texto = f"{cab}\n{ln}" if cab else ln
                chunks.append(_chunk("global", tipo_linha, f["path"], f["titulo"], secao,
                                     f["status"], tier, f["data"], i, texto))
            continue
        for i, (secao, texto) in enumerate(fatiar_markdown(f["_texto"])):
            chunks.append(_chunk("global", "doc", f["path"], f["titulo"], secao,
                                 f["status"], None, f["data"], i, texto))
    chunks += regras_semanticas_t1()
    return chunks, usadas


def regras_semanticas_t1() -> list[dict]:
    """Regras validadas (T1/T2) da semantic_rag_kb — leitura somente, DB real."""
    db = WORKSPACE / "project_data.vision"
    if not db.exists():
        return []
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(semantic_rag_kb)")}
        if "tier" not in cols:
            return []
        rows = con.execute(
            "SELECT id, classe, regra_semantica, obra_contexto, field_id, familia, created_at, tier "
            "FROM semantic_rag_kb WHERE tier IN ('T1','T2')").fetchall()
    finally:
        con.close()
    out = []
    for rid, classe, regra, obra, field_id, familia, criado, tier in rows:
        secao = " / ".join(x for x in (classe, familia, field_id) if x)
        texto = f"Regra semântica {classe or ''} {field_id or ''}: {regra}\nObra de origem: {obra or '—'}"
        out.append(_chunk("global", "regra_semantica", f"project_data.vision#semantic_rag_kb/{rid}",
                          f"Regra {classe} {field_id or ''}".strip(), secao, "canonico", tier,
                          (criado or "")[:10], 0, texto))
    return out


def chunks_obra(obra: str, fontes: Path) -> list[dict]:
    escopo = f"obra:{obra}"
    chunks = []
    for p in sorted(fontes.rglob("*")):
        if p.suffix.lower() not in (".md", ".txt") or not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(WORKSPACE).as_posix() if WORKSPACE in p.parents else p.as_posix()
        titulo = next((ln[2:].strip() for ln in txt.splitlines() if ln.startswith("# ")), p.stem)
        data = datetime.fromtimestamp(p.stat().st_mtime).date().isoformat()
        for i, (secao, texto) in enumerate(fatiar_markdown(txt)):
            chunks.append(_chunk(escopo, "doc", rel, titulo, secao, "ativo", None, data, i, texto))
    return chunks


def gravar(db: Path, chunks: list[dict], embedder_nome: str, escopo: str, extra_meta: dict) -> None:
    con = conectar(db)
    emb = criar_embedder(embedder_nome)
    antigo = dict(con.execute("SELECT k, v FROM meta").fetchall())
    if antigo.get("embedder") and antigo["embedder"] != emb.nome:
        print(f"  embedder mudou ({antigo['embedder']} -> {emb.nome}): vetores novos serão calculados")
    for c in chunks:
        c["sha"] = sha256(texto_para_vetor(c["titulo"], c["secao"], c["texto"]))
    tem = {r[0] for r in con.execute("SELECT sha FROM vetores WHERE embedder=?", (emb.nome,))}
    faltam = [c for c in {c["sha"]: c for c in chunks}.values() if c["sha"] not in tem]
    t0 = time.time()
    if faltam:
        print(f"  embedding de {len(faltam)} trechos novos/alterados ({emb.nome})...", flush=True)
        for i in range(0, len(faltam), 256):
            lote = faltam[i:i + 256]
            vecs = emb.codificar([texto_para_vetor(c["titulo"], c["secao"], c["texto"]) for c in lote])
            con.executemany("INSERT OR REPLACE INTO vetores (sha, embedder, vec) VALUES (?,?,?)",
                            [(c["sha"], emb.nome, v.astype(np.float32).tobytes()) for c, v in zip(lote, vecs)])
            con.commit()
            print(f"    {min(i + 256, len(faltam))}/{len(faltam)}", flush=True)
    with con:
        con.execute("DELETE FROM chunks")
        con.executemany(
            "INSERT INTO chunks (id, escopo, tipo, path, titulo, secao, status, tier, classes, data, ordem, texto, sha) "
            "VALUES (:id,:escopo,:tipo,:path,:titulo,:secao,:status,:tier,:classes,:data,:ordem,:texto,:sha)",
            chunks)
        con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        usados = {c["sha"] for c in chunks}
        orfaos = [r[0] for r in con.execute("SELECT sha FROM vetores WHERE embedder=?", (emb.nome,))
                  if r[0] not in usados]
        con.executemany("DELETE FROM vetores WHERE sha=? AND embedder=?", [(s, emb.nome) for s in orfaos])
        meta = {"esquema": ESQUEMA_VERSAO, "escopo": escopo, "embedder": emb.nome, "dim": str(emb.dim),
                "gerado_em": datetime.now().isoformat(timespec="seconds"), "n_chunks": str(len(chunks)),
                **{k: str(v) for k, v in extra_meta.items()}}
        con.executemany("INSERT OR REPLACE INTO meta (k, v) VALUES (?,?)", meta.items())
    con.execute("VACUUM")
    con.close()
    print(f"  {len(chunks)} trechos gravados em {db} ({time.time() - t0:.0f}s de embedding)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--embedder", default="nim", choices=["local", "nim"],
                    help="nim (padrão, medido melhor em 2026-09-26) | local (offline, sem rede)")
    ap.add_argument("--obra", help="constrói a KB desta obra em KB-GLOBAL/obras/<obra>.sqlite")
    ap.add_argument("--fontes", type=Path, help="pasta de textos da obra (com --obra)")
    ap.add_argument("--db", type=Path, help="caminho do índice (padrão: global ou obras/<obra>)")
    args = ap.parse_args()

    if args.obra:
        if not RE_OBRA.match(args.obra) or not args.fontes or not args.fontes.is_dir():
            ap.error("--obra exige nome simples e --fontes <pasta existente>")
        chunks = chunks_obra(args.obra, args.fontes)
        db = args.db or OBRAS_DIR / f"{args.obra}.sqlite"
        gravar(db, chunks, args.embedder, f"obra:{args.obra}", {"fontes": args.fontes.as_posix()})
    else:
        chunks, usadas = chunks_globais()
        por_tipo = {}
        for c in chunks:
            por_tipo[c["tipo"]] = por_tipo.get(c["tipo"], 0) + 1
        print(f"  {usadas} fontes -> {len(chunks)} trechos {por_tipo}")
        gravar(args.db or GLOBAL_DB, chunks, args.embedder, "global",
               {"n_fontes": usadas, "por_tipo": json.dumps(por_tipo)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
