"""Âncora N2 canônica — recorte validado no Diagnostic Reverse Hub.

O hub grava em ``reverse_eng_recortes.status='aprovado'`` (revisão humana do
crop). Isso é a base de verdade do recorte N2. A ficha em
``reverse_eng_fichas`` pode ficar desatualizada (``recorte_path`` antigo /
``status=draft``); consumidores (CE, gerador N4, G2-V) devem preferir a âncora
do recorte aprovado, não o arquivo mais recente no disco.

Prioridade de path:
1. reverse_eng_recortes com status autoritativo (aprovado > manual_sel >
   manual > auto_aprovado > motor), filtrado por obra/classe/item/pavimento
2. reverse_eng_fichas.recorte_path (pavimento exato)
3. None (caller faz fallback de disco se quiser)
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

_STATUS_RANK = {
    "aprovado": 0,
    "approved": 0,
    "manual_sel": 1,
    "manual": 2,
    "auto_aprovado": 3,
    "motor": 4,
}

_CLS_MAP = {"PL": "PIL", "PIL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ", "LAJ": "LAJ"}


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _norm_class(classe: str) -> str:
    return _CLS_MAP.get(_norm(classe).upper(), _norm(classe).upper())


def _norm_item(item_id: str) -> str:
    item = _norm(item_id).upper()
    item = re.sub(r"_(PARA|PASSA)$", "", item, flags=re.IGNORECASE)
    return item


def pav_key_to_db_pav(pav_key: str) -> str:
    """Normaliza chave de pavimento da UI/CAD para forma de pasta/DB (ex. 14_PAV)."""
    s = unicodedata.normalize("NFKD", _norm(pav_key))
    s = "".join(c for c in s if not unicodedata.combining(c)).upper().strip()
    if "TERREO" in s or "TRREO" in s or re.search(r"[-_ ]TER[-_ ]", s):
        return "TERREO"
    if "COB" in s:
        return "COBERTURA"
    matches = re.findall(r"(\d+)\s*PAV", s)
    if matches:
        return f"{matches[-1]}_PAV"
    matches = re.findall(r"[-_ ](\d{1,2})P(?:V)?(?:[-_ ]|$)", s)
    if matches:
        return f"{matches[-1]}_PAV"
    if "TIPO" in s or re.search(r"[-_ ]TIP[-_ ]", s):
        return "TIPO"
    return _norm(pav_key)


def folder_name_to_db_pav(folder_name: str) -> str:
    n = unicodedata.normalize("NFKD", folder_name or "")
    n = "".join(c for c in n if not unicodedata.combining(c)).upper()
    if "TERREO" in n or "TRREO" in n:
        return "TERREO"
    if "COB" in n:
        return "COBERTURA"
    nums = re.findall(r"(\d+)\s*(?:PAV|°)", n)
    if nums:
        return f"{nums[-1]}_PAV"
    return (folder_name or "").upper()


def _path_matches_pav(recorte_path: str, db_pav: str) -> bool:
    if not db_pav:
        return True
    p = Path(recorte_path)
    parent = p.parent.name if p.parent else ""
    return folder_name_to_db_pav(parent) == db_pav


def resolve_n2_anchor(
    obra: str,
    classe: str,
    item_id: str,
    pavimento: str = "",
    *,
    db_path: Path | str = DB_PATH,
    require_exists: bool = True,
) -> dict | None:
    """Resolve a âncora N2 (recorte canônico) para um item.

    Returns:
        dict com keys: recorte_path, status, confidence, source
        (``reverse_eng_recortes`` | ``reverse_eng_fichas``), elemento_id,
        classe, pavimento_db — ou None se não achar.
    """
    obra_n = _norm(obra)
    classe_n = _norm_class(classe)
    item_n = _norm_item(item_id)
    db_pav = pav_key_to_db_pav(pavimento) if pavimento else ""
    if not obra_n or not classe_n or not item_n:
        return None

    db_path = Path(db_path)
    if not db_path.exists():
        return None

    best: tuple | None = None  # (rank, -confidence, path, status, conf, source)
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT elemento_id, status, confidence, recorte_path
            FROM reverse_eng_recortes
            WHERE (obra_name=? OR obra_name='')
              AND UPPER(COALESCE(classe,''))=?
              AND UPPER(COALESCE(elemento_id,''))=?
            ORDER BY CASE WHEN obra_name=? THEN 0 ELSE 1 END, id DESC
            """,
            (obra_n, classe_n, item_n, obra_n),
        ).fetchall()
        for elem_id, status, conf, recorte_path in rows:
            if not recorte_path:
                continue
            if db_pav and not _path_matches_pav(recorte_path, db_pav):
                continue
            if require_exists and not Path(recorte_path).exists():
                continue
            rank = _STATUS_RANK.get((status or "").lower(), 9)
            conf_f = float(conf or 0.0)
            cand = (rank, -conf_f, recorte_path, status or "", conf_f, "reverse_eng_recortes")
            if best is None or cand[:2] < best[:2]:
                best = cand

        if best is None:
            # Fallback: path gravado na ficha (pode estar stale, mas é âncora fraca)
            if db_pav:
                frow = conn.execute(
                    """
                    SELECT recorte_path, status, confianca
                    FROM reverse_eng_fichas
                    WHERE obra_name=? AND UPPER(classe)=? AND UPPER(elemento_id)=?
                      AND pavimento=?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (obra_n, classe_n, item_n, db_pav),
                ).fetchone()
            else:
                frow = conn.execute(
                    """
                    SELECT recorte_path, status, confianca
                    FROM reverse_eng_fichas
                    WHERE obra_name=? AND UPPER(classe)=? AND UPPER(elemento_id)=?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (obra_n, classe_n, item_n),
                ).fetchone()
            if frow and frow[0]:
                path = frow[0]
                if (not require_exists) or Path(path).exists():
                    best = (
                        8,
                        0.0,
                        path,
                        frow[1] or "draft",
                        float(frow[2] or 0.0),
                        "reverse_eng_fichas",
                    )

    if best is None:
        return None
    _rank, _nc, path, status, conf, source = best
    return {
        "recorte_path": str(Path(path)),
        "status": status,
        "confidence": conf,
        "source": source,
        "elemento_id": item_n,
        "classe": classe_n,
        "pavimento_db": db_pav,
        "is_human_approved": (status or "").lower() in ("aprovado", "approved", "manual_sel"),
    }


def list_n2_anchors(
    obra: str,
    classe: str,
    pavimento: str,
    *,
    db_path: Path | str = DB_PATH,
    require_exists: bool = True,
) -> list[dict]:
    """Lista âncoras N2 (um path por elemento) para obra/classe/pavimento."""
    obra_n = _norm(obra)
    classe_n = _norm_class(classe)
    db_pav = pav_key_to_db_pav(pavimento)
    db_path = Path(db_path)
    out: dict[str, dict] = {}
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT elemento_id, status, confidence, recorte_path
            FROM reverse_eng_recortes
            WHERE (obra_name=? OR obra_name='')
              AND UPPER(COALESCE(classe,''))=?
            ORDER BY id DESC
            """,
            (obra_n, classe_n),
        ).fetchall()
    for elem_id, status, conf, recorte_path in rows:
        eid = _norm_item(elem_id)
        if not eid or not recorte_path:
            continue
        if db_pav and not _path_matches_pav(recorte_path, db_pav):
            continue
        if require_exists and not Path(recorte_path).exists():
            continue
        rank = _STATUS_RANK.get((status or "").lower(), 9)
        prev = out.get(eid)
        prev_rank = _STATUS_RANK.get((prev or {}).get("status", "").lower(), 99) if prev else 99
        if prev is None or rank < prev_rank:
            out[eid] = {
                "recorte_path": str(Path(recorte_path)),
                "status": status or "",
                "confidence": float(conf or 0.0),
                "source": "reverse_eng_recortes",
                "elemento_id": eid,
                "classe": classe_n,
                "pavimento_db": db_pav,
                "is_human_approved": (status or "").lower()
                in ("aprovado", "approved", "manual_sel"),
            }
    return [out[k] for k in sorted(out)]


def rebind_fichas_to_n2_anchors(
    obra: str,
    classe: str,
    pavimento: str,
    *,
    db_path: Path | str = DB_PATH,
    reextract: bool = True,
    only_if_path_differs: bool = True,
) -> dict:
    """Alinha ``reverse_eng_fichas.recorte_path`` (e opcionalmente campos) à âncora.

    Não marca a ficha como ``approved`` de campos F5 — só reaponta o crop
    validado no Reverse Hub e reextrai geometria se ``reextract=True``.
    """
    obra_n = _norm(obra)
    classe_n = _norm_class(classe)
    db_pav = pav_key_to_db_pav(pavimento)
    anchors = list_n2_anchors(obra_n, classe_n, db_pav, db_path=db_path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    updated = []
    skipped = []
    errors = []

    extract_fn = None
    if reextract and classe_n == "LAJ":
        try:
            import sys

            scripts = Path(__file__).resolve().parents[2] / "scripts"
            if str(scripts) not in sys.path:
                sys.path.insert(0, str(scripts))
            from motor_reverso_laj import extrair_ficha_laje

            extract_fn = extrair_ficha_laje
        except Exception as exc:
            errors.append(f"import motor_reverso_laj: {exc}")
            reextract = False

    db_path = Path(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        for anc in anchors:
            eid = anc["elemento_id"]
            path = anc["recorte_path"]
            row = conn.execute(
                """
                SELECT id, recorte_path, campos_json, status
                FROM reverse_eng_fichas
                WHERE obra_name=? AND pavimento=? AND UPPER(classe)=?
                  AND UPPER(elemento_id)=?
                LIMIT 1
                """,
                (obra_n, db_pav, classe_n, eid),
            ).fetchone()
            if not row:
                skipped.append({"item": eid, "reason": "sem_ficha"})
                continue
            ficha_id, old_path, campos_raw, st = row
            if only_if_path_differs and Path(old_path or "").resolve() == Path(path).resolve():
                skipped.append({"item": eid, "reason": "path_igual"})
                continue

            campos: dict
            try:
                campos = json.loads(campos_raw or "{}")
                if not isinstance(campos, dict):
                    campos = {}
            except Exception:
                campos = {}

            if reextract and extract_fn is not None:
                try:
                    fresh = extract_fn(path, eid, obra_n)
                    if isinstance(fresh, dict) and fresh:
                        meta = dict(campos.get("_er_meta") or {})
                        meta.update(
                            {
                                "n2_anchor_path": path,
                                "n2_anchor_status": anc["status"],
                                "n2_anchor_rebound_at": now,
                                "n2_anchor_previous_path": old_path,
                            }
                        )
                        fresh["_er_meta"] = meta
                        # preserve sa meta if any
                        if "_sa_meta" in campos and "_sa_meta" not in fresh:
                            fresh["_sa_meta"] = campos["_sa_meta"]
                        campos = fresh
                except Exception as exc:
                    errors.append(f"{eid}: reextract {exc}")
                    meta = dict(campos.get("_er_meta") or {})
                    meta.update(
                        {
                            "n2_anchor_path": path,
                            "n2_anchor_status": anc["status"],
                            "n2_anchor_rebound_at": now,
                            "n2_anchor_previous_path": old_path,
                            "n2_anchor_reextract_error": str(exc),
                        }
                    )
                    campos["_er_meta"] = meta
            else:
                meta = dict(campos.get("_er_meta") or {})
                meta.update(
                    {
                        "n2_anchor_path": path,
                        "n2_anchor_status": anc["status"],
                        "n2_anchor_rebound_at": now,
                        "n2_anchor_previous_path": old_path,
                    }
                )
                campos["_er_meta"] = meta

            conn.execute(
                """
                UPDATE reverse_eng_fichas
                SET recorte_path=?, campos_json=?, updated_at=?
                WHERE id=?
                """,
                (path, json.dumps(campos, ensure_ascii=False), now, ficha_id),
            )
            updated.append(
                {
                    "item": eid,
                    "old": Path(old_path or "").name,
                    "new": Path(path).name,
                    "status_recorte": anc["status"],
                    "ficha_status": st,
                }
            )
        conn.commit()

    return {
        "obra": obra_n,
        "classe": classe_n,
        "pavimento": db_pav,
        "anchors": len(anchors),
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }
