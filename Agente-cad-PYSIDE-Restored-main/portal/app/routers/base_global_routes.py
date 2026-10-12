"""Aba "Base Global" — grafo da base de conhecimento da empresa, só para o dono.

Lê `docs/CONHECIMENTO/grafo.json` (gerado por `scripts/kb/kb_grafo.py` e versionado
com o código, então chega à VPS no deploy). O portal só lê; nada é escrito.

Membro comum recebe 404 — a aba não existe para ele (nem no menu, nem por URL).
"""

from __future__ import annotations

import sqlite3
import re
import json
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse

from .. import access
from ..dbdep import get_db_conn
from .paginas_routes import _membro_da_sessao, _render

router = APIRouter(tags=["base-global"], include_in_schema=False)

GRAFO_JSON = Path(__file__).resolve().parents[3] / "docs" / "CONHECIMENTO" / "grafo.json"
KB_DB = Path(__file__).resolve().parents[3] / "KB-GLOBAL" / "kb_global.sqlite"


def _dono_ou_404(request: Request, conn: sqlite3.Connection):
    membro = _membro_da_sessao(request, conn)
    if membro is None:
        return None
    if not access.eh_dono(membro):
        raise HTTPException(status_code=404)
    return membro


@router.get("/app/base-global")
def pagina_base_global(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    membro = _dono_ou_404(request, conn)
    if membro is None:
        return RedirectResponse("/login", status_code=303)
    return _render(request, "base_global.html", {
        "membro": membro, "nav_ativo": "base_global", "tem_grafo": GRAFO_JSON.exists(),
        "knowledge_works": [dict(zip(('id','nome'), row)) for row in conn.execute('SELECT id,nome FROM portal_obras ORDER BY nome')],
    })


@router.get("/app/base-global/grafo.json")
def grafo_json(request: Request, conn: sqlite3.Connection = Depends(get_db_conn)):
    if _dono_ou_404(request, conn) is None:
        raise HTTPException(status_code=401)
    if not GRAFO_JSON.exists():
        raise HTTPException(status_code=404, detail="grafo.json ainda não gerado (scripts/kb/kb_grafo.py)")
    from ..knowledge_scope import graph_nodes
    graph=json.loads(GRAFO_JSON.read_text())
    nodes,edges=graph_nodes(conn)
    graph['nos'].extend(nodes); graph['arestas'].extend(edges)
    graph['contagens']['obra']=sum(n['tipo']=='obra' for n in nodes)
    graph['contagens']['pavimento']=sum(n['tipo']=='pavimento' for n in nodes)
    return JSONResponse(graph,headers={"Cache-Control":"no-cache"})


@router.get("/app/base-global/buscar")
def buscar_conhecimento(q: str, request: Request, obra_id: str | None = None,
                        pavimento: str | None = None, conn: sqlite3.Connection = Depends(get_db_conn)):
    """FTS5 read-only on the published KB snapshot; available only to the owner."""
    if _dono_ou_404(request, conn) is None:
        raise HTTPException(status_code=401)
    db=KB_DB
    scope='global'
    if obra_id:
        if not conn.execute('SELECT 1 FROM portal_obras WHERE id=?',(obra_id,)).fetchone():
            raise HTTPException(status_code=404,detail='obra inexistente')
        from ..knowledge_scope import safe
        try:
            safe(obra_id)
            if pavimento: safe(pavimento)
        except ValueError as exc: raise HTTPException(status_code=422,detail='escopo inválido') from exc
        db=KB_DB.parent/'obras'/(obra_id+'.sqlite');scope='obra:'+obra_id
    elif pavimento:
        raise HTTPException(status_code=422,detail='pavimento exige obra')
    if not db.is_file():
        raise HTTPException(status_code=503, detail="Índice de busca indisponível")
    if len(q) > 160:
        raise HTTPException(status_code=400, detail="Consulta longa demais")
    terms = re.findall(r"[\wÀ-ÿ-]{2,}", q, flags=re.UNICODE)[:12]
    if not terms:
        return {"resultados": [], "consulta": q}
    expression = " OR ".join('"' + term.replace('"', '') + '"' for term in terms)
    try:
        with closing(sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=2)) as kb:
            rows = kb.execute(
                "SELECT c.tipo, c.path, c.titulo, c.secao, c.status, c.tier, c.texto "
                "FROM chunks_fts f JOIN chunks c ON c.rowid=f.rowid "
                "WHERE chunks_fts MATCH ? AND c.status!='historico' AND c.escopo=? "
                "AND (? IS NULL OR instr(c.path, '/pavimentos/' || ? || '/')>0) "
                "ORDER BY bm25(chunks_fts, 3.0, 2.0, 1.0) LIMIT 60",
                (expression,scope,pavimento,pavimento),
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise HTTPException(status_code=503, detail="Índice de busca indisponível") from exc
    results = []
    per_source = {}
    for tipo, path, titulo, secao, status, tier, texto in rows:
        key = (path, texto) if tipo in {"decisao", "glossario", "regra_semantica"} else path
        if per_source.get(key, 0) >= 2:
            continue
        per_source[key] = per_source.get(key, 0) + 1
        results.append({"tipo": tipo, "path": path, "titulo": titulo, "secao": secao,
                        "status": status, "tier": tier,
                        "trecho": re.sub(r"\s+", " ", texto)[:420]})
        if len(results) == 10:
            break
    return {"consulta": q, "resultados": results,"escopo":scope,"pavimento":pavimento}
