"""Rotas do viewer nativo N1 (SA) — 2026-07-06 (ver plano witty-hopping-sunbeam).

O portal NUNCA reusa o HTML do headless como tela final — só LÊ os artefatos
reais já gerados (`estado_<pav>.json` + fichas HTML) via `ficha_reader`, e
monta a experiência nativa (lista + foto + campos) pedida pelo dono, na mesma
fronteira read-only do resto do portal.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import access, auth, ficha_reader, pipeline_runner
from ..dbdep import get_db_conn
from ...db import repository as repo

router = APIRouter(prefix="/obras", tags=["n1"])


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


def _pavimento_da_obra(obra_dir: Path, pavimento: Optional[str]) -> Optional[str]:
    """Resolve o pavimento: usa o pedido se existir, senao o unico/primeiro real."""
    disponiveis = ficha_reader.descobrir_pavimentos(obra_dir)
    if not disponiveis:
        return None
    if pavimento and pavimento in disponiveis:
        return pavimento
    return disponiveis[0]


@router.get("/{obra_id}/n1/classes")
def listar_classes_n1(obra_id: str, request: Request, pavimento: Optional[str] = None,
                       membro: dict = Depends(auth.exige_login),
                       conn: sqlite3.Connection = Depends(get_db_conn)):
    """Pavimentos disponiveis + classes com contagem (pra montar as sub-abas)."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    disponiveis = ficha_reader.descobrir_pavimentos(obra_dir)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav) if pav else None
    classes = []
    for classe in ficha_reader.CLASSES_N1:
        itens = ficha_reader.listar_itens_n1(estado, classe) if estado else []
        classes.append({
            "classe": classe, "titulo": ficha_reader.TITULOS_CLASSE[classe],
            "total": len(itens),
        })
    return {
        "obra_id": obra_id, "pavimentos": disponiveis, "pavimento_atual": pav,
        "classes": classes,
    }


@router.get("/{obra_id}/n1/{classe}")
def listar_itens_n1_endpoint(obra_id: str, classe: str, request: Request,
                              pavimento: Optional[str] = None,
                              membro: dict = Depends(auth.exige_login),
                              conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        return {"obra_id": obra_id, "classe": classe, "pavimento": None, "itens": []}
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    itens = ficha_reader.listar_itens_n1(estado, classe) if estado else []
    return {
        "obra_id": obra_id, "classe": classe, "pavimento": pav,
        "itens": [{"item_id": i["item_id"], "titulo": i["titulo"], "validado": request.app.state.validacoes.get(obra_id, {}).get(classe, {}).get(i["item_id"], {}).get("n1_ok", False)} for i in itens],
    }


@router.get("/{obra_id}/n1/{classe}/{item_id}")
def obter_item_n1_endpoint(obra_id: str, classe: str, item_id: str, request: Request,
                            pavimento: Optional[str] = None,
                            membro: dict = Depends(auth.exige_login),
                            conn: sqlite3.Connection = Depends(get_db_conn)):
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pav = _pavimento_da_obra(obra_dir, pavimento)
    if pav is None:
        raise HTTPException(status_code=404, detail="obra ainda sem SA rodado (nenhum estado_<pav>.json)")
    estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
    item = ficha_reader.obter_item_n1(estado, classe, item_id) if estado else None
    if item is None:
        raise HTTPException(status_code=404, detail="item nao encontrado nesta classe/pavimento")
    dir_fichas = pipeline_runner.encontrar_dir_fichas(obra_dir)
    fotos = ficha_reader.extrair_fotos_ficha(dir_fichas, classe, item)
    return {
        "obra_id": obra_id, "classe": classe, "pavimento": pav, "item_id": item_id,
        "titulo": item["titulo"], "campos": item["campos"], "atencao": item["atencao"],
        "foto_n1": fotos["n1"], "foto_n3": fotos["n3"],
    }


@router.get("/{obra_id}/stats-globais")
def stats_globais(obra_id: str, request: Request,
                  membro: dict = Depends(auth.exige_login),
                  conn: sqlite3.Connection = Depends(get_db_conn)):
    """Estatisticas globais de N1 e N3 em toda a obra."""
    obra = _obra_do_membro(conn, obra_id, membro)
    obra_dir = _obra_dir(request, obra)
    pavimentos = ficha_reader.descobrir_pavimentos(obra_dir)
    
    n1_total = 0
    n1_val = 0
    n3_total = 0
    n3_val = 0
    
    validacoes = request.app.state.validacoes.get(obra_id, {})
    
    for pav in pavimentos:
        estado = ficha_reader.ler_estado_pavimento(obra_dir, pav)
        if not estado: continue
        
        for classe in ficha_reader.CLASSES_N1:
            # Pilares N3 (Para/Passa) sao so' reprojecao N3 dos mesmos pilares
            # de "pilares"/"pilares_especiais" — contar aqui duplicaria os
            # pilares no total de N1.
            if classe in ficha_reader._PILARES_N3_VARIANTE:
                continue
            itens_n1 = ficha_reader.listar_itens_n1(estado, classe)
            n1_total += len(itens_n1)
            for it in itens_n1:
                item_id = it["item_id"]
                val = validacoes.get(classe, {}).get(item_id, {})
                if val.get("n1_ok"):
                    n1_val += 1
                    
        # [FIX] `ficha_reader.CLASSES_N3`/`listar_itens_n3` nao existem — N3 e'
        # "robo gerado a partir do N1" (mesmo conjunto de classes/itens do N1,
        # so' que com validacao propria `n3_ok`), nao uma fonte de dados
        # separada. Reaproveita CLASSES_N1/listar_itens_n1, igual o resto do
        # app ja' faz (mesmo endpoint /n1/classes serve as duas abas).
        for classe in ficha_reader.CLASSES_N1:
            # Pilares tem N3 proprio (2 variantes Para/Passa, ficha diferente
            # da N1) — a reprojecao generica ("mesmos itens do N1") nao vale
            # pra eles, senao conta cada pilar 2x (pilares/especiais) + 2x
            # (variantes) no total de N3.
            if classe in ("pilares", "pilares_especiais"):
                continue
            itens_n3 = ficha_reader.listar_itens_n1(estado, classe)
            n3_total += len(itens_n3)
            for it in itens_n3:
                item_id = it["item_id"]
                val = validacoes.get(classe, {}).get(item_id, {})
                if val.get("n3_ok"):
                    n3_val += 1
                    
    return {
        "n1": {"total": n1_total, "validados": n1_val},
        "n3": {"total": n3_total, "validados": n3_val}
    }
