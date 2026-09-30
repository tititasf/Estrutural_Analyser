"""Rotas do viewer de Recortes (bruto×limpo) — 2026-07-06.

Só leitura: usa `recortes_reader` (acha o recorte mais recente por item, real
em disco) + `dxf_preview` (rasteriza DXF→PNG, com cache) pra montar bruto
(mesma região recortada, vista no DXF de entrada original) e limpo (o próprio
recorte gerado pelo RecorteMotor).
"""

from __future__ import annotations

import logging
import json
import math
import re
import shutil
import sqlite3
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response

from .. import access, auth, dxf_preview, ficha_reader, pipeline_runner, recortes_reader, torre_crop
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
        stem = Path(bruto["nome"]).stem.lower()
        base = recortes_reader.stem_bruto_canonico(stem).lower()
        # ODA stem não está em portal_documentos (só o DWG original) — cai no base
        doc = por_stem.get(stem) or por_stem.get(base)
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
        return Response(
            content=svg,
            media_type="image/svg+xml",
            headers={"Cache-Control": "private, max-age=3600"},
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # [2026-07-30] Removida a escrita de C:/Users/Thierry/Desktop/err_foto.txt
        # (caminho de Desktop fixo num processo de servidor). Vai para o log.
        logging.getLogger("portal.recortes_routes").exception(
            "foto_bruto_completo falhou: obra=%s bruto=%s", obra_id, bruto_id
        )
        raise HTTPException(status_code=500, detail=f"falha ao renderizar: {exc}") from exc
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
    """Foto INTEIRA da torre limpa / detalhes (SVG, PREVIEW_ALVO_PX)."""
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
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, max-age=3600"},
    )


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
    substituir_item_id: str | None = None
    confirmar_limpeza_dependencias: bool = False


def _recorte_tem_dependencias_estruturais(item_id: str | None) -> bool:
    """Somente recortes de torre alimentam os motores SA/N3/N5.

    Detalhes, convencoes e demais recortes auxiliares podem ser refeitos sem
    consultar ou invalidar qualquer analise estrutural da torre.
    """
    if not item_id:
        return False
    return re.fullmatch(r"torre_\d+", item_id) is not None


def _projetos_sa_que_usam_recorte(settings, recorte_path: Path) -> list[dict]:
    """Descobre dados derivados cuja fonte e exatamente este recorte.

    O modelo SA atual ainda identifica o projeto por obra+pavimento. Enquanto
    nao houver uma dimensao de torre no contrato inteiro, nunca apagamos esses
    dados automaticamente: sobrescrever o DXF e manter SA/N3 antigo seria
    incoerente; limpar por pavimento poderia atingir outra torre.
    """
    db_path = Path(settings.sa_db_path)
    if not db_path.is_file():
        return []
    alvo = str(recorte_path.resolve())
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, name, dxf_path FROM projects WHERE dxf_path = ?",
            (alvo,),
        ).fetchall()
        resultado = []
        for row in rows:
            project_id = str(row["id"])
            counts = {}
            for table in ("pillars", "beams", "slabs"):
                try:
                    counts[table] = int(conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",
                        (project_id,),
                    ).fetchone()[0])
                except sqlite3.OperationalError:
                    counts[table] = 0
            if sum(counts.values()) > 0:
                resultado.append({"project_id": project_id, "pavimento": row["name"], **counts})
        return resultado
    finally:
        conn.close()


def _limpar_projetos_sa(settings, dependencias: list[dict]) -> int:
    project_ids = [str(item["project_id"]) for item in dependencias]
    if not project_ids:
        return 0
    conn = sqlite3.connect(str(settings.sa_db_path))
    try:
        conn.execute("BEGIN IMMEDIATE")
        placeholders = ",".join("?" for _ in project_ids)
        tabelas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name <> 'projects'"
        ).fetchall()
        for (tabela,) in tabelas:
            colunas = {row[1] for row in conn.execute(f'PRAGMA table_info("{tabela}")')}
            if "project_id" in colunas:
                nome_seguro = tabela.replace('"', '""')
                conn.execute(f'DELETE FROM "{nome_seguro}" WHERE project_id IN ({placeholders})', project_ids)
        conn.execute(f"DELETE FROM projects WHERE id IN ({placeholders})", project_ids)
        conn.commit()
        return len(project_ids)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _artefatos_sa_que_usam_recorte(obra_dir: Path, recorte_path: Path) -> list[Path]:
    """Localiza snapshots/runs cuja origem e exatamente ``recorte_path``.

    O estado canônico ainda e publicado por pavimento. Por isso ele somente
    pode ser invalidado quando a rodada mais recente daquele pavimento aponta
    para este recorte. Rodadas de outras torres nunca entram no resultado.
    """
    obra_dir = Path(obra_dir).resolve()
    alvo = Path(recorte_path).resolve()
    production_root = obra_dir / "Fase-6_Execucao_CAD" / "production_sa"
    manifests: list[tuple[Path, str, Path]] = []
    if production_root.is_dir():
        for manifest in production_root.glob("*/*/production_manifest.json"):
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                source = Path(str(payload.get("source_dxf") or "")).resolve()
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            manifests.append((manifest.parent, manifest.parent.parent.name, source))

    encontrados: list[Path] = []
    por_pavimento: dict[str, list[tuple[Path, Path]]] = {}
    for run, pavimento, source in manifests:
        por_pavimento.setdefault(pavimento, []).append((run, source))
        if source == alvo:
            encontrados.append(run)

    for pavimento, runs in por_pavimento.items():
        latest_run, latest_source = max(runs, key=lambda item: item[0].name)
        if latest_source != alvo:
            continue
        canonical = obra_dir / f"estado_{pavimento}.json"
        if canonical.is_file():
            encontrados.append(canonical)
        # O snapshot isolado que originou a rodada traz o PID no nome da run.
        pid = latest_run.name.rsplit("_", 1)[-1]
        if pid.isdigit():
            snapshot = obra_dir / f"estado_{pavimento}_pid{pid}.json"
            if snapshot.is_file():
                encontrados.append(snapshot)

    # Mantém ordem estável e elimina duplicatas sem ampliar o escopo.
    return list(dict.fromkeys(encontrados))


def _arquivar_artefatos_sa(
    obra_dir: Path, recorte_path: Path, artefatos: list[Path],
) -> list[str]:
    """Retira artefatos antigos da área ativa, mantendo cópia recuperável."""
    if not artefatos:
        return []
    obra_dir = Path(obra_dir).resolve()
    recorte_path = Path(recorte_path).resolve()
    carimbo = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    destino = recorte_path.parent / ".historico_recortes" / "analises" / carimbo
    movidos: list[str] = []
    for artefato in artefatos:
        origem = Path(artefato).resolve()
        try:
            relativo = origem.relative_to(obra_dir)
        except ValueError as exc:
            raise RuntimeError(f"artefato SA fora da obra: {origem}") from exc
        if not origem.exists():
            continue
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(origem), str(alvo))
        movidos.append(str(alvo))
    return movidos

@router.post("/{obra_id}/recortes/brutos/{bruto_id}/manual_crop")
def manual_crop_endpoint(obra_id: str, bruto_id: str, payload: ManualCropPayload, request: Request,
                         membro: dict = Depends(auth.exige_login),
                         conn: sqlite3.Connection = Depends(get_db_conn)):
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
        if not payload.bboxes:
            raise HTTPException(status_code=422, detail="Desenhe pelo menos um recorte")

        # [2026-07-30] A transform vem do RENDER, não é mais recalculada aqui.
        # Antes esta rota reproduzia a fórmula de renderizar_dxf_completo_cacheado
        # (margem 0.03 + proporção do desenho). Dava o mesmo resultado — conferido,
        # erro zero — mas só enquanto as duas contas ficassem idênticas. Mudar
        # alvo_px/margem/proporção de um lado deslocaria todo recorte manual sem
        # erro nenhum. Agora existe uma fonte só.
        transform = dxf_preview.transform_preview_completo(
            bruto_path, cache_dir=obra_dir / ".previews"
        )
        if transform is None:
            raise HTTPException(status_code=500, detail="Nao foi possivel ler os limites do DXF")

        dxf_bboxes = []
        for b in payload.bboxes:
            valores = (b.x_pct, b.y_pct, b.w_pct, b.h_pct)
            if not all(math.isfinite(v) for v in valores):
                raise HTTPException(status_code=422, detail="Coordenadas do recorte invalidas")
            if b.w_pct <= 0 or b.h_pct <= 0:
                raise HTTPException(status_code=422, detail="O recorte precisa ter largura e altura")
            tolerancia = 1e-6
            if (b.x_pct < -tolerancia or b.y_pct < -tolerancia
                    or b.x_pct + b.w_pct > 1 + tolerancia
                    or b.y_pct + b.h_pct > 1 + tolerancia):
                raise HTTPException(status_code=422, detail="O recorte precisa ficar dentro da imagem")
            x_pct = max(0.0, min(1.0, b.x_pct))
            y_pct = max(0.0, min(1.0, b.y_pct))
            x2_pct = max(0.0, min(1.0, b.x_pct + b.w_pct))
            y2_pct = max(0.0, min(1.0, b.y_pct + b.h_pct))
            # Percentuais da imagem exibida -> pixel -> coordenada DXF.
            px_esq = x_pct * transform.largura_px
            px_dir = x2_pct * transform.largura_px
            py_topo = y_pct * transform.altura_px
            py_base = y2_pct * transform.altura_px
            cx0, cy1 = transform.px_para_dxf(px_esq, py_topo)
            cx1, cy0 = transform.px_para_dxf(px_dir, py_base)
            dxf_bboxes.append([cx0, cy0, cx1, cy1])

        out_dir = torre_crop._dir_recortes_bruto(obra_dir, bruto_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        nome_alvo = re.sub(r'[^a-zA-Z0-9_]', '_', payload.classe_alvo)
        if not nome_alvo.strip("_"):
            raise HTTPException(status_code=422, detail="Escolha um nome valido para o recorte")
        substituir_item_id = None
        if payload.substituir_item_id:
            substituir_item_id = re.sub(r'[^a-zA-Z0-9_]', '_', payload.substituir_item_id)
            if substituir_item_id != payload.substituir_item_id or substituir_item_id != nome_alvo:
                raise HTTPException(
                    status_code=422,
                    detail="O recorte de destino precisa coincidir com o item substituido",
                )
        out_path = out_dir / f"{nome_alvo}.dxf"
        dependencias = []
        artefatos_sa: list[Path] = []
        substitui_torre = _recorte_tem_dependencias_estruturais(substituir_item_id)
        if substituir_item_id:
            if not out_path.is_file():
                raise HTTPException(status_code=404, detail="Recorte a substituir nao encontrado")
            if substitui_torre:
                dependencias = _projetos_sa_que_usam_recorte(
                    request.app.state.settings, out_path,
                )
                artefatos_sa = _artefatos_sa_que_usam_recorte(obra_dir, out_path)
                if (dependencias or artefatos_sa) and not payload.confirmar_limpeza_dependencias:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Esta torre possui dados SA/N3/N5 persistidos. "
                            "Confirme a substituicao para apagar somente os dados vinculados a ela."
                        ),
                    )
        elif out_path.exists():
            raise HTTPException(
                status_code=409,
                detail="Este recorte ja existe. Selecione 'Substituir recorte existente'.",
            )
        tmp_path = out_dir / f".{nome_alvo}.{uuid.uuid4().hex}.tmp.dxf"

        from scripts.obra_crop_engine import crop_dxf, crop_dxf_multi
        inicio_crop = time.perf_counter()
        backup_path = None
        projetos_sa_removidos = 0
        artefatos_sa_arquivados: list[str] = []
        try:
            if len(dxf_bboxes) == 1:
                crop = crop_dxf(
                    bruto_path, tmp_path, dxf_bboxes[0], padding_pct=0.0,
                    selection_mode="contained",
                )
            else:
                crop = crop_dxf_multi(
                    bruto_path, tmp_path, dxf_bboxes, padding_pct=0.0,
                    selection_mode="contained",
                )

            if crop.get("error"):
                raise HTTPException(status_code=422, detail=crop["error"])
            if substituir_item_id:
                historico_dir = out_dir / ".historico_recortes"
                historico_dir.mkdir(parents=True, exist_ok=True)
                backup_path = historico_dir / (
                    f"{nome_alvo}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.dxf"
                )
                shutil.copy2(out_path, backup_path)
            tmp_path.replace(out_path)
            if dependencias:
                try:
                    projetos_sa_removidos = _limpar_projetos_sa(
                        request.app.state.settings, dependencias,
                    )
                except Exception:
                    if backup_path:
                        shutil.copy2(backup_path, out_path)
                    raise
            if artefatos_sa:
                try:
                    artefatos_sa_arquivados = _arquivar_artefatos_sa(
                        obra_dir, out_path, artefatos_sa,
                    )
                except Exception:
                    if backup_path:
                        shutil.copy2(backup_path, out_path)
                    raise
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        duracao_ms = round((time.perf_counter() - inicio_crop) * 1000)

        data = torre_crop._ler_validacao(out_dir)
        # Todo recorte novo/refeito volta a pendente: a geometria mudou e
        # precisa de nova aprovacao humana antes de alimentar as etapas.
        data[nome_alvo] = False
        torre_crop._salvar_validacao(out_dir, data)

        return {
            "status": "ok",
            "torre": nome_alvo,
            "bboxes_dxf": dxf_bboxes,
            "entities_copied": crop.get("entities_copied", 0),
            "entities_skipped_outside": crop.get("entities_skipped_outside", 0),
            "duration_ms": duracao_ms,
            "substituido": bool(substituir_item_id),
            "backup_path": str(backup_path) if substituir_item_id and backup_path else None,
            "projetos_sa_removidos": projetos_sa_removidos,
            "artefatos_sa_arquivados": len(artefatos_sa_arquivados),
        }
    except HTTPException:
        raise  # 404/500 já tratados acima não viram 500 genérico com stack
    except Exception as exc:  # noqa: BLE001 - falha de crop vira erro de request
        # [2026-07-30] Removida a escrita de C:/Users/Thierry/Desktop/err_crop.txt:
        # caminho de Desktop fixo, gravado a cada exceção, quebra em qualquer
        # máquina que não seja a do dono — e o portal é servidor. Vai para o log.
        logging.getLogger("portal.recortes_routes").exception(
            "manual_crop falhou: obra=%s bruto=%s", obra_id, bruto_id
        )
        raise HTTPException(status_code=500, detail=f"falha ao recortar: {exc}") from exc

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

def _publicar_pavimento_e_recorte_ao_validar(
    request: Request, obra: dict, obra_dir: Path, conn: sqlite3.Connection,
    bruto_id: str, item_id: str,
) -> dict:
    """[2026-07-13, pedido do dono] Ao validar um recorte (Torre 1/Detalhes)
    na Triagem — bem antes do SA rodar — minta na hora o código de
    pavimento (que antes só existia quando a obra INTEIRA chegava em
    'pronta', via auto_publish_poller) e o código PRÓPRIO deste recorte.
    Falha aqui NUNCA derruba a validação em si — é só um bônus de
    referência, não o dado principal."""
    resultado: dict = {
        "code_publico_pavimento": None, "code_publico_recorte": None,
        "referencia_pavimento": None, "referencia_recorte": None,
    }
    try:
        docs = repo.listar_documentos_por_obra(conn, obra["id"])
        bruto_doc = next(
            (d for d in docs if Path(d["arquivo_nome"]).stem.lower() == bruto_id.lower()), None,
        )
        pavimento = bruto_doc.get("pavimento_confirmado") or bruto_doc.get("pavimento_sugerido") if bruto_doc else None
        if not pavimento:
            return resultado  # sem pavimento classificado ainda, nada a mintar

        settings = request.app.state.settings
        titulo = torre_crop._TITULOS_RECORTE.get(item_id, item_id)
        pav_label = ficha_reader.pavimento_label(pavimento)
        nome_obra = obra.get("nome", "")

        import sys
        _repo_root = Path(__file__).resolve().parents[3]
        if str(_repo_root) not in sys.path:
            sys.path.insert(0, str(_repo_root))
        _consulta_dir = _repo_root / "consulta-publica-api"
        if str(_consulta_dir) not in sys.path:
            sys.path.insert(0, str(_consulta_dir))
        from publisher.publish import publicar_pavimento_minimo, publicar_recorte

        mint_pav = publicar_pavimento_minimo(
            obra["id"], obra_dir, pavimento, nome_obra,
            db_path=settings.public_consulta_db_path,
        )
        resultado["code_publico_pavimento"] = mint_pav["code_pavimento"]
        resultado["referencia_pavimento"] = f"{nome_obra} › {pav_label}"
        resultado["code_publico_recorte"] = publicar_recorte(
            obra["id"], obra_dir, pavimento, item_id, bruto_id, titulo, nome_obra,
            db_path=settings.public_consulta_db_path,
        )
        resultado["referencia_recorte"] = f"{nome_obra} › {pav_label} › {titulo}"
    except Exception:
        logging.getLogger("portal.recortes_routes").exception(
            "falha ao mintar codigo publico ao validar recorte (obra=%s, bruto=%s, item=%s)",
            obra.get("id"), bruto_id, item_id,
        )
    return resultado


@router.post("/{obra_id}/recortes/brutos/{bruto_id}/{item_id}/validar")
def validar_recorte_endpoint(obra_id: str, bruto_id: str, item_id: str, payload: ValidacaoPayload,
                             request: Request,
                             membro: dict = Depends(auth.exige_login),
                             conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    torre_crop.set_recorte_validado(obra_dir, bruto_id, item_id, payload.validado)
    resposta = {"status": "ok", "validado": payload.validado}
    if payload.validado:
        resposta.update(_publicar_pavimento_e_recorte_ao_validar(
            request, obra, obra_dir, conn, bruto_id, item_id,
        ))
    return resposta
