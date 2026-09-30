"""Rotas de comentarios T0 (equipe:*) — server-side, substituem localStorage (HANDOFF §1.1/§4).

Todo comentario grava marcado_por = 'equipe:<login>' (proveniencia real T0, §3). O
portal so grava no namespace 'equipe' (o repository forca isso); a curadoria/decisao
continua exclusiva do dono, pela cabine PySide6 — nunca por este processo.
"""

from __future__ import annotations

import base64
import binascii
import json
import sqlite3
from typing import Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from .. import access, auth
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(prefix="/obras", tags=["comentarios"])
ui_router = APIRouter(prefix="/apontamentos-ui", tags=["apontamentos-ui"])


class ComentarioIn(BaseModel):
    texto: str
    tipo: str = "observacao"  # 'erro' | 'observacao'
    classe: Optional[str] = None
    pavimento: Optional[str] = None
    item_id: Optional[str] = None


class ApontamentoUIIn(BaseModel):
    obra_id: Optional[str] = Field(default=None, max_length=200)
    texto: str = Field(min_length=1, max_length=4000)
    pagina_url: str = Field(min_length=1, max_length=4000)
    pagina_titulo: Optional[str] = Field(default=None, max_length=500)
    seletor_elemento: Optional[str] = Field(default=None, max_length=2000)
    elemento_tag: Optional[str] = Field(default=None, max_length=100)
    elemento_role: Optional[str] = Field(default=None, max_length=200)
    elemento_texto: Optional[str] = Field(default=None, max_length=2000)
    elemento: dict = Field(default_factory=dict)
    clique_x: float
    clique_y: float
    pagina_x: float
    pagina_y: float
    viewport_largura: int = Field(gt=0, le=20000)
    viewport_altura: int = Field(gt=0, le=20000)
    captura_data_url: Optional[str] = None


class ApontamentoUIPontoIn(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)
    pagina_url: str = Field(min_length=1, max_length=4000)
    pagina_titulo: Optional[str] = Field(default=None, max_length=500)
    seletor_elemento: Optional[str] = Field(default=None, max_length=2000)
    elemento_tag: Optional[str] = Field(default=None, max_length=100)
    elemento_role: Optional[str] = Field(default=None, max_length=200)
    elemento_texto: Optional[str] = Field(default=None, max_length=2000)
    elemento: dict = Field(default_factory=dict)
    clique_x: float
    clique_y: float
    pagina_x: float
    pagina_y: float
    viewport_largura: int = Field(gt=0, le=20000)
    viewport_altura: int = Field(gt=0, le=20000)
    captura_data_url: Optional[str] = None


class ApontamentoUIPaginaIn(BaseModel):
    pagina_url: str = Field(min_length=1, max_length=4000)
    pagina_titulo: Optional[str] = Field(default=None, max_length=500)
    pontos: list[ApontamentoUIPontoIn] = Field(min_length=1, max_length=20)


class ApontamentoUISessaoIn(BaseModel):
    obra_id: Optional[str] = Field(default=None, max_length=200)
    titulo: Optional[str] = Field(default=None, max_length=500)
    paginas: list[ApontamentoUIPaginaIn] = Field(min_length=1, max_length=10)


_CAPTURA_MAX_BYTES = 2_500_000
_CAPTURA_PREFIXOS = {
    "data:image/png;base64,": "image/png",
    "data:image/jpeg;base64,": "image/jpeg",
    "data:image/webp;base64,": "image/webp",
}


def _decodificar_captura(data_url: Optional[str]) -> tuple[Optional[str], Optional[bytes]]:
    if not data_url:
        return None, None
    prefixo = next((p for p in _CAPTURA_PREFIXOS if data_url.startswith(p)), None)
    if prefixo is None:
        raise HTTPException(status_code=422, detail="captura deve ser PNG, JPEG ou WebP")
    encoded = data_url[len(prefixo):]
    # Base64 cresce ~4/3. Recusar cedo evita alocar payloads arbitrariamente grandes.
    if len(encoded) > ((_CAPTURA_MAX_BYTES + 2) // 3) * 4 + 8:
        raise HTTPException(status_code=413, detail="captura excede 2,5 MB")
    try:
        blob = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="captura base64 invalida") from exc
    if len(blob) > _CAPTURA_MAX_BYTES:
        raise HTTPException(status_code=413, detail="captura excede 2,5 MB")
    mime = _CAPTURA_PREFIXOS[prefixo]
    assinaturas_validas = {
        "image/png": blob.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": blob.startswith(b"\xff\xd8\xff"),
        "image/webp": blob.startswith(b"RIFF") and blob[8:12] == b"WEBP",
    }
    if not assinaturas_validas[mime]:
        raise HTTPException(status_code=422, detail="conteudo da captura nao corresponde ao formato")
    return mime, blob


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


def _validar_url_pagina(value: str) -> None:
    pagina = urlsplit(value)
    if pagina.scheme not in {"http", "https"} or not pagina.netloc:
        raise HTTPException(status_code=422, detail="URL da pagina invalida")


def _normalizar_ponto(body: ApontamentoUIIn | ApontamentoUIPontoIn) -> tuple[dict, int]:
    texto = body.texto.strip()
    if not texto:
        raise HTTPException(status_code=422, detail="escreva o comentario do apontamento")
    _validar_url_pagina(body.pagina_url)
    elemento_json = json.dumps(body.elemento, ensure_ascii=False, sort_keys=True)
    if len(elemento_json) > 20_000:
        raise HTTPException(status_code=422, detail="contexto do elemento excede 20 KB")
    captura_mime, captura_blob = _decodificar_captura(body.captura_data_url)
    return ({
        "texto": texto, "pagina_url": body.pagina_url,
        "pagina_titulo": body.pagina_titulo,
        "seletor_elemento": body.seletor_elemento,
        "elemento_tag": body.elemento_tag, "elemento_role": body.elemento_role,
        "elemento_texto": body.elemento_texto, "elemento_json": elemento_json,
        "clique_x": body.clique_x, "clique_y": body.clique_y,
        "pagina_x": body.pagina_x, "pagina_y": body.pagina_y,
        "viewport_largura": body.viewport_largura,
        "viewport_altura": body.viewport_altura,
        "captura_mime": captura_mime, "captura_blob": captura_blob,
    }, len(captura_blob or b""))


@router.post("/{obra_id}/comentarios")
def criar_comentario(obra_id: str, body: ComentarioIn, request: Request,
                     membro: dict = Depends(auth.exige_login),
                     conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    if body.tipo not in ("erro", "observacao"):
        raise HTTPException(status_code=422, detail="tipo deve ser 'erro' ou 'observacao'")
    coment_id = repo.inserir_comentario(
        conn, obra_id=obra["id"], membro_id=membro["id"], texto=body.texto,
        tipo=body.tipo, classe=body.classe, pavimento=body.pavimento, item_id=body.item_id,
    )
    return {"comentario_id": coment_id, "marcado_por": f"equipe:{membro['login']}",
            "tipo": body.tipo}


@router.get("/{obra_id}/comentarios")
def listar_comentarios(obra_id: str, request: Request,
                       membro: dict = Depends(auth.exige_login),
                       conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    coments = repo.listar_comentarios_por_obra(conn, obra["id"])
    return {"obra_id": obra_id, "total": len(coments), "comentarios": coments}


@ui_router.post("")
def criar_apontamento_ui(
    body: ApontamentoUIIn, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra_id = None
    if body.obra_id:
        obra_id = _obra_do_membro(conn, body.obra_id, membro)["id"]
    point, _ = _normalizar_ponto(body)
    apontamento_id = repo.inserir_apontamento_ui(
        conn, obra_id=obra_id, membro_id=membro["id"], **point,
    )
    return {"status": "ok", "apontamento_id": apontamento_id}


@ui_router.post("/sessoes")
def criar_sessao_apontamento_ui(
    body: ApontamentoUISessaoIn,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    obra_id = _obra_do_membro(conn, body.obra_id, membro)["id"] if body.obra_id else None
    paginas = []
    total_bytes = 0
    total_points = 0
    for page in body.paginas:
        _validar_url_pagina(page.pagina_url)
        points = []
        for point_body in page.pontos:
            point, capture_bytes = _normalizar_ponto(point_body)
            # A página pai é canônica; evita pontos agrupados sob URL divergente.
            point["pagina_url"] = page.pagina_url
            point["pagina_titulo"] = page.pagina_titulo
            points.append(point)
            total_bytes += capture_bytes
            total_points += 1
        paginas.append({
            "pagina_url": page.pagina_url,
            "pagina_titulo": page.pagina_titulo,
            "pontos": points,
        })
    if total_points > 40:
        raise HTTPException(status_code=422, detail="sessao excede 40 pontos")
    if total_bytes > 25_000_000:
        raise HTTPException(status_code=413, detail="capturas da sessao excedem 25 MB")
    sessao_id = repo.inserir_sessao_apontamento_ui(
        conn, obra_id=obra_id, membro_id=membro["id"],
        titulo=(body.titulo or "").strip() or None, paginas=paginas,
    )
    return {"status": "ok", "sessao_id": sessao_id, "paginas": len(paginas), "pontos": total_points}


@ui_router.get("/sessoes")
def listar_sessoes_apontamento_ui(
    meus: bool = Query(default=False), membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    sessions = repo.listar_sessoes_apontamento_ui(conn, membro=membro, somente_meus=meus)
    for session in sessions:
        for page in session["paginas"]:
            for point in page["pontos"]:
                point["tem_captura"] = bool(point.pop("captura_mime", None))
                try:
                    point["elemento"] = json.loads(point.pop("elemento_json") or "{}")
                except (TypeError, json.JSONDecodeError):
                    point["elemento"] = {}
    # Registros v1 continuam aparecendo como sessões unitárias.
    for legacy in repo.listar_apontamentos_ui(conn, membro=membro, somente_meus=meus):
        if legacy.get("sessao_id"):
            continue
        legacy["tem_captura"] = bool(legacy.pop("captura_mime", None))
        try:
            legacy["elemento"] = json.loads(legacy.pop("elemento_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            legacy["elemento"] = {}
        sessions.append({
            "id": legacy["id"], "obra_id": legacy.get("obra_id"),
            "membro_id": legacy["membro_id"], "titulo": legacy["texto"],
            "created_at": legacy["created_at"], "autor_login": legacy["autor_login"],
            "autor_nome": legacy["autor_nome"], "obra_nome": legacy.get("obra_nome"),
            "paginas": [{
                "id": "legacy-" + legacy["id"], "ordem": 1,
                "pagina_url": legacy["pagina_url"], "pagina_titulo": legacy.get("pagina_titulo"),
                "pontos": [legacy],
            }],
        })
    sessions.sort(key=lambda row: (row.get("created_at") or "", row["id"]), reverse=True)
    return {"total": len(sessions), "sessoes": sessions}


@ui_router.get("")
def listar_apontamentos_ui(
    request: Request, meus: bool = Query(default=False),
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    rows = repo.listar_apontamentos_ui(conn, membro=membro, somente_meus=meus)
    for row in rows:
        row["tem_captura"] = bool(row.pop("captura_mime", None))
        try:
            row["elemento"] = json.loads(row.pop("elemento_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            row["elemento"] = {}
    return {"total": len(rows), "apontamentos": rows}


@ui_router.get("/{apontamento_id}/captura")
def captura_apontamento_ui(
    apontamento_id: str, request: Request,
    membro: dict = Depends(auth.exige_login),
    conn: sqlite3.Connection = Depends(get_db_conn),
):
    row = repo.obter_apontamento_ui(conn, apontamento_id)
    if row is None or not repo.pode_ver_apontamento_ui(conn, row, membro):
        raise HTTPException(status_code=404, detail="apontamento nao encontrado")
    if not row.get("captura_blob") or not row.get("captura_mime"):
        raise HTTPException(status_code=404, detail="apontamento sem captura")
    return Response(
        content=row["captura_blob"], media_type=row["captura_mime"],
        headers={"Cache-Control": "private, max-age=300"},
    )
