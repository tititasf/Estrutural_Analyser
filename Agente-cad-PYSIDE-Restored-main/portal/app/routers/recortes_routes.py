"""Rotas do viewer de Recortes (bruto×limpo) — 2026-07-06.

Só leitura: usa `recortes_reader` (acha o recorte mais recente por item, real
em disco) + `dxf_preview` (rasteriza DXF→PNG, com cache) pra montar bruto
(mesma região recortada, vista no DXF de entrada original) e limpo (o próprio
recorte gerado pelo RecorteMotor).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response

from .. import access, auth, dxf_preview, pipeline_runner, recortes_reader, torre_crop
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(prefix="/obras", tags=["recortes"])

_EXT_DWG = ".dwg"


def _obra_do_membro(conn: sqlite3.Connection, obra_id: str, membro: dict) -> dict:
    obra = repo.obter_obra(conn, obra_id)
    if obra is None:
        raise HTTPException(status_code=404, detail="obra nao encontrada")
    if not access.pode_ver_obra(obra, membro):
        raise HTTPException(status_code=403, detail="obra de outro membro")
    return obra


def _obra_dir(request: Request, obra: dict) -> Path:
    settings = request.app.state.settings
    lp = obra.get("local_path")
    return Path(lp) if lp else settings.dados_obras_dir / obra.get("nome", "obra")


def _entrada_dxf(obra_dir: Path, obra: dict) -> Path | None:
    nome = obra.get("arquivo_nome")
    if not nome:
        return None
    entrada = obra_dir / "entrada" / nome
    if entrada.suffix.lower() == _EXT_DWG:
        entrada = entrada.with_suffix(".dxf")
    return entrada if entrada.is_file() else None


@router.get("/{obra_id}/recortes/classes")
def listar_classes_recorte_endpoint(obra_id: str, request: Request,
                                     membro: dict = Depends(auth.exige_login),
                                     conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    return {"obra_id": obra_id, "classes": recortes_reader.listar_classes_recorte(obra_dir)}


@router.get("/{obra_id}/recortes/brutos")
def listar_brutos_recorte_endpoint(obra_id: str, request: Request,
                                    membro: dict = Depends(auth.exige_login),
                                    conn: sqlite3.Connection = Depends(get_db_conn)):
    """[2026-07-07] Navegação por bruto/pavimento (espelha diagnostic_hub.py real),
    não mais por classe estrutural — ver nota em recortes_reader.listar_brutos_recorte.

    [2026-07-07 v2] Achado com o dono: a lista aqui era um glob cru do disco
    (ordem alfabética, sem organização), diferente da Triagem (que já agrupa
    por Pavimento→Tipo via portal_documentos). Enriquece cada bruto com a
    MESMA classificação real (pavimento_confirmado/sugerido,
    tipo_documento_confirmado/sugerido) pra a UI desenhar os mesmos grupos —
    sem duplicar a lógica de agrupamento, só os dados pra ela."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    brutos = recortes_reader.listar_brutos_recorte(obra_dir)
    from pathlib import Path
    por_stem = {Path(d["arquivo_nome"]).stem.lower(): d for d in repo.listar_documentos_por_obra(conn, obra_id)}
    for bruto in brutos:
        doc = por_stem.get(Path(bruto["nome"]).stem.lower())
        bruto["pavimento"] = (doc.get("pavimento_confirmado") or doc.get("pavimento_sugerido")) if doc else None
        bruto["tipo_documento"] = (
            (doc.get("tipo_documento_confirmado") or doc.get("tipo_documento_sugerido")) if doc else None
        )
    return {"obra_id": obra_id, "brutos": brutos}


@router.get("/{obra_id}/recortes")
def listar_todos_recortes_endpoint(obra_id: str, request: Request,
                                    membro: dict = Depends(auth.exige_login),
                                    conn: sqlite3.Connection = Depends(get_db_conn)):
    """Lista achatada com todos os recortes de qualquer classe (cada item traz
    sua `classe` pra UI desenhar cabeçalhos de grupo, sem abas separadas)."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    itens = recortes_reader.listar_todos_recortes(obra_dir)
    return {"obra_id": obra_id,
            "itens": [{"item_id": i["item_id"], "titulo": i["titulo"], "classe": i["classe"]} for i in itens]}


# ── Torre/Detalhes (2026-07-07) — o que a aba Recortes REALMENTE mostra ──────
# Motor `torre_crop.py` (DBSCAN via scripts/obra_crop_engine): planta inteira
# em torre(s) limpa(s) + detalhes/convenções unificados, não por-elemento.
# Prefixo /brutos/ evita colisão de rota com /{classe}/{item_id}/foto acima
# (mesmo shape de path, {classe} vs {bruto_id} são indistinguíveis pro FastAPI).

@router.get("/{obra_id}/recortes/brutos/{bruto_id}/foto")
def foto_bruto_completo_endpoint(obra_id: str, bruto_id: str, request: Request,
                                  membro: dict = Depends(auth.exige_login),
                                  conn: sqlite3.Connection = Depends(get_db_conn)):
    """A planta INTEIRA do bruto (DXF de entrada), alta resolução — sem
    recorte nenhum, pra comparar com as torres/detalhes já limpos."""
    import traceback
    try:
        obra = _obra_do_membro(conn, obra_id, membro)
        obra_dir = _obra_dir(request, obra)
        entrada = _entrada_dxf(obra_dir, obra)
        if entrada is None or entrada.stem != bruto_id:
            # fallback: procura por stem direto na pasta entrada/ (dwg+dxf dedup)
            candidato = obra_dir / "entrada" / f"{bruto_id}.dxf"
            entrada = candidato if candidato.is_file() else entrada
        if entrada is None:
            raise HTTPException(status_code=404, detail="DXF de entrada nao encontrado")
        cache_dir = obra_dir / ".previews"
        try:
            svg = dxf_preview.renderizar_dxf_completo_cacheado(entrada, cache_dir)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"falha ao renderizar: {exc}") from exc
        return Response(content=svg, media_type="image/svg+xml")


    except Exception as e:
        err_msg = str(e) + "\n" + traceback.format_exc()
        with open("C:/Users/Thierry/Desktop/err_foto.txt", "w", encoding="utf-8") as f:
            f.write(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)
@router.get("/{obra_id}/recortes/brutos/{bruto_id}/itens")
def listar_itens_torre_endpoint(obra_id: str, bruto_id: str, request: Request,
                                 membro: dict = Depends(auth.exige_login),
                                 conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    itens = torre_crop.listar_recortes_bruto(obra_dir, bruto_id)
    # [FIX] `repo.obter_documentos_da_obra` nao existe (a funcao real e'
    # `listar_documentos_por_obra`); alem disso `bruto_id` e' o STEM do
    # arquivo (ex.: "TMC-...-R01_R2018_ASCII_ODA"), nunca o id (UUID) de
    # portal_documentos — o match tem que ser por nome de arquivo, igual
    # `listar_brutos_recorte_endpoint` acima ja' faz.
    docs = repo.listar_documentos_por_obra(conn, obra_id)
    bruto_doc = next(
        (d for d in docs if Path(d["arquivo_nome"]).stem.lower() == bruto_id.lower()), None,
    )
    pav = "Desconhecido"
    if bruto_doc:
        pav = bruto_doc.get("pavimento_confirmado") or bruto_doc.get("pavimento_sugerido") or "Desconhecido"

    return {"obra_id": obra_id, "bruto_id": bruto_id,
            "itens": [{"item_id": i["item_id"], "titulo": f"{i['titulo']} - {pav}", "validado": i.get("validado", False)} for i in itens]}


@router.get("/{obra_id}/recortes/brutos/{bruto_id}/{item_id}/arquivo")
def arquivo_recorte_endpoint(obra_id: str, bruto_id: str, item_id: str, request: Request,
                             membro: dict = Depends(auth.exige_login),
                             conn: sqlite3.Connection = Depends(get_db_conn)):
    """[novo, Masterplan OBRAS DRIVE Fase 1] Serve o .dxf REAL do recorte (nao
    o SVG renderizado dos endpoints de "foto" acima) — usado pela app desktop
    pra baixar sob demanda (1 arquivo por vez) o mesmo torre_1.dxf que
    alimenta o Diagnostic Hub localmente, sem precisar espelhar a obra
    inteira."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    item = torre_crop.obter_recorte_bruto(obra_dir, bruto_id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="recorte nao encontrado")
    caminho = Path(item["path"])
    if not caminho.is_file():
        raise HTTPException(status_code=404, detail="arquivo do recorte nao encontrado em disco")
    return FileResponse(caminho, filename=caminho.name, media_type="application/octet-stream")


@router.get("/{obra_id}/recortes/brutos/{bruto_id}/{item_id}/foto")
def foto_torre_endpoint(obra_id: str, bruto_id: str, item_id: str, request: Request,
                         membro: dict = Depends(auth.exige_login),
                         conn: sqlite3.Connection = Depends(get_db_conn)):
    """Foto INTEIRA em alta resolução (2400px no lado maior) — torre limpa ou
    detalhes/convenções, sempre o desenho completo, nunca um crop por elemento."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    item = torre_crop.obter_recorte_bruto(obra_dir, bruto_id, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="recorte de torre nao encontrado")
    cache_dir = obra_dir / ".previews"
    try:
        svg = dxf_preview.renderizar_dxf_completo_cacheado(Path(item["path"]), cache_dir)
    except Exception as exc:  # noqa: BLE001 - DXF pode ter geometria que o renderer nao suporta
        raise HTTPException(status_code=502, detail=f"falha ao renderizar: {exc}") from exc
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/{obra_id}/recortes/{classe}")
def listar_itens_recorte_endpoint(obra_id: str, classe: str, request: Request,
                                   membro: dict = Depends(auth.exige_login),
                                   conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    itens = recortes_reader.listar_itens_recorte(obra_dir, classe)
    return {"obra_id": obra_id, "classe": classe,
            "itens": [{"item_id": i["item_id"], "titulo": i["titulo"], "validado": i.get("validado", False)} for i in itens]}


@router.get("/{obra_id}/recortes/{classe}/{item_id}/detalhes")
def detalhes_recorte_endpoint(obra_id: str, classe: str, item_id: str, request: Request,
                               membro: dict = Depends(auth.exige_login),
                               conn: sqlite3.Connection = Depends(get_db_conn)):
    """Metadados reais do recorte (entidades, camadas, tipos, dimensões) —
    o texto do painel "Detalhes e Convenções", ao lado da foto com zoom fechado."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    item = recortes_reader.obter_item_recorte(obra_dir, classe, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="recorte nao encontrado")
    try:
        detalhes = recortes_reader.obter_detalhes_recorte(Path(item["recorte_path"]))
    except Exception as exc:  # noqa: BLE001 - DXF pode estar corrompido/formato inesperado
        raise HTTPException(status_code=502, detail=f"falha ao ler detalhes: {exc}") from exc
    return {"obra_id": obra_id, "classe": classe, "item_id": item_id, **detalhes}


@router.get("/{obra_id}/recortes/{classe}/{item_id}/foto")
def foto_recorte_endpoint(obra_id: str, classe: str, item_id: str, tipo: str, request: Request,
                           membro: dict = Depends(auth.exige_login),
                           conn: sqlite3.Connection = Depends(get_db_conn)):
    """`tipo=limpo` -> o recorte em si (com contexto ao redor). `tipo=bruto` ->
    a MESMA região no DXF de entrada original (comparação real, não
    side-by-side arbitrário). `tipo=detalhes` -> o MESMO recorte, mas
    enquadrado bem fechado na própria geometria (zoom sem folga de contexto)
    pra ler cota/hachura/texto com nitidez — não é um artefato separado, é
    o único DXF real que o RecorteMotor produz, só que exibido diferente."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    item = recortes_reader.obter_item_recorte(obra_dir, classe, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="recorte nao encontrado")

    recorte_path = Path(item["recorte_path"])
    cache_dir = obra_dir / ".previews"

    if tipo == "limpo":
        alvo, bbox, margem = recorte_path, None, 0.08
    elif tipo == "detalhes":
        alvo = recorte_path
        bbox = dxf_preview.obter_bbox_dxf(recorte_path)
        margem = 0.0
    elif tipo == "bruto":
        entrada = _entrada_dxf(obra_dir, obra)
        if entrada is None:
            raise HTTPException(status_code=404, detail="DXF de entrada nao encontrado")
        alvo = entrada
        bbox = dxf_preview.obter_bbox_dxf(recorte_path)
        margem = 0.08
    else:
        raise HTTPException(status_code=422, detail="tipo deve ser 'bruto', 'limpo' ou 'detalhes'")

    try:
        svg = dxf_preview.renderizar_dxf_svg_cacheado(alvo, cache_dir, bbox=bbox, margem_pct=margem)
    except Exception as exc:  # noqa: BLE001 - DXF pode ter geometria que o renderer nao suporta
        raise HTTPException(status_code=502, detail=f"falha ao renderizar: {exc}") from exc
    return Response(content=svg, media_type="image/svg+xml")


from pydantic import BaseModel
class ValidacaoPayload(BaseModel):
    validado: bool

class BboxPct(BaseModel):
    x_pct: float
    y_pct: float
    w_pct: float
    h_pct: float

class ManualCropPayload(BaseModel):
    bboxes: list[BboxPct]
    classe_alvo: str

@router.post("/{obra_id}/recortes/brutos/{bruto_id}/manual_crop")
def manual_crop_endpoint(obra_id: str, bruto_id: str, payload: ManualCropPayload, request: Request,
                         membro: dict = Depends(auth.exige_login),
                         conn: sqlite3.Connection = Depends(get_db_conn)):
    import traceback
    try:
        obra = _obra_do_membro(conn, obra_id, membro)
        obra_dir = _obra_dir(request, obra)

        brutos = recortes_reader.listar_brutos_recorte(obra_dir)
        bruto = next((b for b in brutos if b["bruto_id"] == bruto_id), None)
        if not bruto:
            raise HTTPException(status_code=404, detail="Bruto nao encontrado")

        bruto_path = obra_dir / "entrada" / bruto["nome"]
        if not bruto_path.is_file():
            raise HTTPException(status_code=404, detail="DXF nao encontrado")

        bbox_dxf = dxf_preview.obter_bbox_dxf(bruto_path)
        if not bbox_dxf:
            raise HTTPException(status_code=500, detail="Nao foi possivel ler os limites do DXF")

        x0, y0, x1, y1 = bbox_dxf
        margem_pct = 0.03
        margem_x = max((x1 - x0) * margem_pct, 0.5)
        margem_y = max((y1 - y0) * margem_pct, 0.5)

        rx0, ry0 = x0 - margem_x, y0 - margem_y
        rx1, ry1 = x1 + margem_x, y1 + margem_y

        rw = rx1 - rx0
        rh = ry1 - ry0

        dxf_bboxes = []
        for b in payload.bboxes:
            cx0 = rx0 + b.x_pct * rw
            cx1 = cx0 + b.w_pct * rw
            cy1 = ry1 - b.y_pct * rh
            cy0 = cy1 - b.h_pct * rh
            dxf_bboxes.append([cx0, cy0, cx1, cy1])

        out_dir = torre_crop._dir_recortes_bruto(obra_dir, bruto_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        import re
        nome_alvo = re.sub(r'[^a-zA-Z0-9_]', '_', payload.classe_alvo)
        out_path = out_dir / f"{nome_alvo}.dxf"

        from scripts.obra_crop_engine import crop_dxf, crop_dxf_multi
        if len(dxf_bboxes) == 1:
            crop = crop_dxf(bruto_path, out_path, dxf_bboxes[0], padding_pct=0.0)
        else:
            crop = crop_dxf_multi(bruto_path, out_path, dxf_bboxes, padding_pct=0.0)

        if crop.get("error"):
            raise HTTPException(status_code=500, detail=crop["error"])

        data = torre_crop._ler_validacao(out_dir)
        data[nome_alvo] = True
        torre_crop._salvar_validacao(out_dir, data)

        return {"status": "ok", "torre": nome_alvo}
    except Exception as e:
        err_msg = str(e) + "\n" + traceback.format_exc()
        with open("C:/Users/Thierry/Desktop/err_crop.txt", "w", encoding="utf-8") as f:
            f.write(err_msg)
        raise HTTPException(status_code=500, detail=err_msg)

@router.post("/{obra_id}/recortes/brutos/{bruto_id}/reprocessar")
def reprocessar_bruto_endpoint(obra_id: str, bruto_id: str, request: Request,
                               membro: dict = Depends(auth.exige_login),
                               conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    
    brutos = recortes_reader.listar_brutos_recorte(obra_dir)
    bruto = next((b for b in brutos if b["bruto_id"] == bruto_id), None)
    if not bruto:
        raise HTTPException(status_code=404, detail="Bruto nao encontrado")
    
    bruto_path = obra_dir / "entrada" / bruto["nome"]
    if not bruto_path.is_file():
        raise HTTPException(status_code=404, detail="DXF nao encontrado")
        
    resultado = torre_crop.gerar_recortes_bruto(obra_dir, bruto_path, bruto_id, force=True)
    if resultado.get("error"):
        raise HTTPException(status_code=500, detail=resultado["error"])
        
    return {"status": "ok", "resultado": resultado}

@router.delete("/{obra_id}/recortes/brutos/{bruto_id}/{item_id}")
def excluir_recorte_endpoint(obra_id: str, bruto_id: str, item_id: str, request: Request,
                             membro: dict = Depends(auth.exige_login),
                             conn: sqlite3.Connection = Depends(get_db_conn)):
    # [FIX] importava `src.core.torre_crop` (modulo que nao existe — sempre
    # 500ava) em vez do `torre_crop` real deste pacote (ja importado no topo
    # do arquivo, mesmo usado por gerar/listar/validar recorte acima).
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    removido = torre_crop.excluir_recorte(obra_dir, bruto_id, item_id)
    if not removido:
        raise HTTPException(status_code=404, detail="recorte nao encontrado")
    return {"status": "ok", "removido": True}

@router.post("/{obra_id}/recortes/brutos/{bruto_id}/{item_id}/validar")
def validar_recorte_endpoint(obra_id: str, bruto_id: str, item_id: str, payload: ValidacaoPayload,
                             request: Request,
                             membro: dict = Depends(auth.exige_login),
                             conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    torre_crop.set_recorte_validado(obra_dir, bruto_id, item_id, payload.validado)
    return {"status": "ok", "validado": payload.validado}
