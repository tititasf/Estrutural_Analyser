#!/usr/bin/env python3
"""
obra_rag_pipeline.py - Snapshot RAG local por obra.

Gera `DADOS-OBRAS/{obra}/obra_rag/` com contexto local da obra para consulta
e auditoria. Nao escreve no RAG global, nao indexa FAISS/Chroma e nao promove
T0 para T1.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sqlite3
from pathlib import Path
from typing import Any

try:
    from .rag_tier import get_tier, load_tombstones
except ImportError:
    from rag_tier import get_tier, load_tombstones

DEFAULT_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
SNAPSHOT_DIR_NAME = "obra_rag"


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _fetch_dicts(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _json_loads(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except Exception:
        return None


def _compact_campos(raw: Any) -> dict[str, Any]:
    data = _json_loads(raw)
    if not isinstance(data, dict):
        return {"keys": [], "preview": None}
    preview: dict[str, Any] = {}
    for key in (
        "name",
        "number",
        "comprimento",
        "largura",
        "altura",
        "total_width",
        "total_height",
        "espessura",
        "area_cm2",
        "modo_distribuicao",
        "_confianca",
    ):
        if key in data:
            preview[key] = data.get(key)
    return {"keys": sorted(data.keys()), "preview": preview}


def _compact_rule(raw: str) -> dict[str, Any]:
    payload = _json_loads(raw)
    if not isinstance(payload, dict):
        return {"text": str(raw or "")[:500]}
    return {
        "source_doc": payload.get("source_doc"),
        "section": payload.get("section"),
        "tags": payload.get("tags"),
        "sprint_validated": payload.get("sprint_validated"),
        "text": str(payload.get("text") or "")[:700],
    }


def build_snapshot(
    obra_name: str,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    obras_root: str | Path = DEFAULT_OBRAS_ROOT,
) -> dict[str, Any]:
    db_path = Path(db_path)
    obras_root = Path(obras_root)
    obra_dir = obras_root / obra_name
    tombstones = load_tombstones()

    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": _now(),
        "obra_name": obra_name,
        "scope": "obra_local",
        "promotion_policy": "never_auto_global",
        "paths": {
            "db_path": str(db_path),
            "obra_dir": str(obra_dir),
            "snapshot_dir": str(obra_dir / SNAPSHOT_DIR_NAME),
        },
        "warnings": [],
        "counts": {},
        "tiers": {},
        "projects": [],
        "documents": [],
        "reverse_fichas": [],
        "reverse_recortes": [],
        "obra_recortes": [],
        "semantic_rules": [],
    }

    if not obra_dir.exists():
        snapshot["warnings"].append(f"obra_dir_missing:{obra_dir}")
    if not db_path.exists():
        snapshot["warnings"].append(f"db_missing:{db_path}")
        return snapshot

    tier_counts: dict[str, int] = {}
    with sqlite3.connect(db_path) as conn:
        if _table_exists(conn, "projects"):
            projects = _fetch_dicts(
                conn,
                """
                SELECT id, name, dxf_path, work_name, pavement_name, sync_status, file_version
                FROM projects
                WHERE work_name=?
                ORDER BY name
                """,
                (obra_name,),
            )
            snapshot["projects"] = projects

        if _table_exists(conn, "project_documents"):
            snapshot["documents"] = _fetch_dicts(
                conn,
                """
                SELECT id, project_id, work_name, name, file_path, extension, phase,
                       category, file_version, entity_count, dxf_version
                FROM project_documents
                WHERE work_name=? OR project_id IN (SELECT id FROM projects WHERE work_name=?)
                ORDER BY phase, category, name
                """,
                (obra_name, obra_name),
            )

        if _table_exists(conn, "reverse_eng_fichas"):
            rows = _fetch_dicts(
                conn,
                """
                SELECT id, projeto_id, obra_name, pavimento, classe, elemento_id,
                       campos_json, recorte_path, confianca, status, aprovado_at,
                       rag_indexed, created_at, updated_at
                FROM reverse_eng_fichas
                WHERE obra_name=?
                ORDER BY pavimento, classe, elemento_id, id
                """,
                (obra_name,),
            )
            for row in rows:
                tier = get_tier(row, tombstones=tombstones)
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
                snapshot["reverse_fichas"].append(
                    {
                        "id": row.get("id"),
                        "pavimento": row.get("pavimento"),
                        "classe": row.get("classe"),
                        "elemento_id": row.get("elemento_id"),
                        "status": row.get("status"),
                        "tier": tier,
                        "confianca": row.get("confianca"),
                        "rag_indexed": row.get("rag_indexed"),
                        "aprovado_at": row.get("aprovado_at"),
                        "recorte_path": row.get("recorte_path"),
                        "campos": _compact_campos(row.get("campos_json")),
                    }
                )

        if _table_exists(conn, "reverse_eng_recortes"):
            recortes = _fetch_dicts(
                conn,
                """
                SELECT id, ficha_id, obra_name, elemento_id, recorte_path, entity_count,
                       projeto_id, classe, status, confidence, created_at
                FROM reverse_eng_recortes
                WHERE obra_name=?
                ORDER BY classe, elemento_id, id
                """,
                (obra_name,),
            )
            snapshot["reverse_recortes"] = recortes

        if _table_exists(conn, "obra_recortes"):
            snapshot["obra_recortes"] = _fetch_dicts(
                conn,
                """
                SELECT id, obra_name, pavimento_name, dxf_bruto_path, recorte_type,
                       recorte_index, output_path, entity_count, score, status,
                       n_torres, approved_at, updated_at
                FROM obra_recortes
                WHERE obra_name=?
                ORDER BY pavimento_name, recorte_type, recorte_index
                """,
                (obra_name,),
            )

        if _table_exists(conn, "semantic_rag_kb"):
            rules = _fetch_dicts(
                conn,
                """
                SELECT id, classe, regra_semantica, obra_contexto, confianca, created_at
                FROM semantic_rag_kb
                ORDER BY classe, id
                """,
                (),
            )
            snapshot["semantic_rules"] = [
                {
                    "id": row.get("id"),
                    "classe": row.get("classe"),
                    "obra_contexto": row.get("obra_contexto"),
                    "confianca": row.get("confianca"),
                    "rule": _compact_rule(row.get("regra_semantica") or ""),
                }
                for row in rules
            ]

    snapshot["counts"] = {
        "projects": len(snapshot["projects"]),
        "documents": len(snapshot["documents"]),
        "reverse_fichas": len(snapshot["reverse_fichas"]),
        "reverse_recortes": len(snapshot["reverse_recortes"]),
        "obra_recortes": len(snapshot["obra_recortes"]),
        "semantic_rules": len(snapshot["semantic_rules"]),
    }
    snapshot["tiers"] = dict(sorted(tier_counts.items()))
    if tier_counts.get("T0", 0):
        snapshot["warnings"].append("contains_local_T0_context_not_global_truth")
    return snapshot


def write_snapshot(snapshot: dict[str, Any], *, obras_root: str | Path = DEFAULT_OBRAS_ROOT) -> Path:
    obra_name = snapshot["obra_name"]
    out_dir = Path(obras_root) / obra_name / SNAPSHOT_DIR_NAME
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "manifest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, sort_keys=True)
    return out_path


def run_pipeline(
    obra_name: str,
    *,
    force: bool = False,
    progress_cb=None,
    db_path: str | Path = DEFAULT_DB_PATH,
    obras_root: str | Path = DEFAULT_OBRAS_ROOT,
) -> dict[str, Any]:
    """Compatibilidade com a UI antiga: materializa snapshot local por obra."""
    start = _dt.datetime.now(_dt.timezone.utc)

    def progress(pct: int, msg: str) -> None:
        if progress_cb:
            progress_cb(pct, msg)

    progress(5, "Preparando snapshot RAG local")
    snapshot = build_snapshot(obra_name, db_path=db_path, obras_root=obras_root)
    progress(75, "Gravando manifest local")
    out_path = write_snapshot(snapshot, obras_root=obras_root)
    duration = (_dt.datetime.now(_dt.timezone.utc) - start).total_seconds()
    progress(100, "Snapshot RAG local pronto")

    counts = snapshot.get("counts", {})
    return {
        "status": "ok" if not any(str(w).startswith("db_missing") for w in snapshot.get("warnings", [])) else "warning",
        "scope": snapshot.get("scope"),
        "promotion_policy": snapshot.get("promotion_policy"),
        "snapshot_path": str(out_path),
        "doc_chunks": counts.get("documents", 0),
        "dxf_indexed": counts.get("reverse_fichas", 0),
        "triagem_rows": counts.get("obra_recortes", 0),
        "duration_s": duration,
        "errors": [],
        "warnings": snapshot.get("warnings", []),
        "counts": counts,
        "tiers": snapshot.get("tiers", {}),
        "force": force,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera snapshot RAG local por obra")
    parser.add_argument("--obra", required=True, help="Nome da obra em DADOS-OBRAS")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path do project_data.vision")
    parser.add_argument("--obras-root", default=str(DEFAULT_OBRAS_ROOT), help="Path de DADOS-OBRAS")
    parser.add_argument("--apply", action="store_true", help="Grava DADOS-OBRAS/{obra}/obra_rag/manifest.json")
    parser.add_argument("--dry-run", action="store_true", help="Apenas imprime resumo (padrao)")
    args = parser.parse_args()

    snapshot = build_snapshot(args.obra, db_path=args.db, obras_root=args.obras_root)
    print(f"[obra_rag] obra={args.obra} counts={snapshot['counts']} tiers={snapshot['tiers']}")
    if snapshot["warnings"]:
        print(f"[obra_rag] warnings={snapshot['warnings']}")
    if not args.apply:
        print("[dry-run] Nenhuma escrita realizada. Use --apply para materializar o snapshot local.")
        return

    out_path = write_snapshot(snapshot, obras_root=args.obras_root)
    print(f"[OK] snapshot={out_path}")


if __name__ == "__main__":
    main()
