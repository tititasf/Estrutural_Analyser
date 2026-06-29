#!/usr/bin/env python3
"""
rag_context_service.py - Consulta RAG read-only para a UI.

Retorna contexto semantico e exemplos validados sem escrever no banco e sem
promover fichas. Por padrao, exemplos usam apenas tier T1/T2.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

try:
    from .active_learning_query import query_active_learning
    from .obra_rag_query import query_local_snapshot
    from .rag_tier import get_tier, is_indexable, load_tombstones
except ImportError:
    from active_learning_query import query_active_learning
    from obra_rag_query import query_local_snapshot
    from rag_tier import get_tier, is_indexable, load_tombstones

DEFAULT_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
FAISS_DIR = Path("D:/Agente-cad-PYSIDE/data/vectors/faiss")
DEFAULT_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

CLASS_TO_DB = {"PL": "PIL", "PIL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ", "LAJ": "LAJ"}
CLASS_TO_TIPO = {"PIL": "pilar", "LV": "viga", "FV": "viga", "LAJ": "laje"}
TIPO_TO_STORE = {"pilar": "pilares", "viga": "vigas", "laje": "lajes"}


def normalize_class(classe: str) -> str:
    return CLASS_TO_DB.get(str(classe or "").upper(), str(classe or "").upper())


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _load_rules(classe: str, *, db_path: str | Path = DEFAULT_DB_PATH, limit: int = 8) -> list[dict[str, Any]]:
    db_path = Path(db_path)
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if not _table_exists(conn, "semantic_rag_kb"):
            return []
        rows = conn.execute(
            """
            SELECT id, classe, regra_semantica, obra_contexto, confianca, created_at
            FROM semantic_rag_kb
            WHERE classe=?
            ORDER BY confianca DESC, id ASC
            LIMIT ?
            """,
            (classe, int(limit)),
        ).fetchall()
    return [dict(row) for row in rows]


def _load_validated_examples(
    classe: str,
    item_id: str,
    *,
    obra: str | None = None,
    min_tier: str = "T1",
    limit: int = 5,
) -> list[dict[str, Any]]:
    tipo = CLASS_TO_TIPO.get(classe)
    if not tipo:
        return []
    meta_path = FAISS_DIR / f"{TIPO_TO_STORE.get(tipo, tipo + 's')}_meta.json"
    if not meta_path.exists():
        return []

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(meta, list):
        return []

    tombstones = load_tombstones()
    needle = str(item_id or "").upper()
    exact: list[dict[str, Any]] = []
    same_class: list[dict[str, Any]] = []
    for row in meta:
        if not isinstance(row, dict):
            continue
        if not is_indexable(row, min_tier=min_tier, tombstones=tombstones):
            continue
        if obra and row.get("obra") != obra:
            continue
        row_id = str(row.get("id") or row.get("elemento_id") or "").upper()
        payload = {
            "id": row.get("id") or row.get("elemento_id"),
            "obra": row.get("obra"),
            "pavimento": row.get("pavimento"),
            "tipo": row.get("tipo"),
            "tier": get_tier(row, tombstones=tombstones),
            "text": row.get("text", ""),
            "dados": row.get("dados", {}),
        }
        if needle and row_id == needle:
            exact.append(payload)
        else:
            same_class.append(payload)
    return (exact + same_class)[:limit]


def get_rag_context_for_item(
    *,
    classe: str,
    item_id: str,
    obra: str | None = None,
    pavimento: str | None = None,
    db_path: str | Path = DEFAULT_DB_PATH,
    obras_root: str | Path = DEFAULT_OBRAS_ROOT,
    min_tier: str = "T1",
) -> dict[str, Any]:
    db_class = normalize_class(classe)
    rules = _load_rules(db_class, db_path=db_path)
    examples = _load_validated_examples(db_class, item_id, obra=obra, min_tier=min_tier)
    local_context = []
    if obra:
        local_query = " ".join(
            value for value in (db_class, item_id, pavimento) if value
        )
        local_context = query_local_snapshot(
            obra,
            local_query,
            obras_root=obras_root,
        )
    approved_lessons = query_active_learning(
        " ".join(value for value in (db_class, item_id, pavimento) if value),
        limit=5,
        include_candidates=False,
    )
    return {
        "classe": db_class,
        "ui_classe": classe,
        "item_id": item_id,
        "obra": obra,
        "pavimento": pavimento,
        "min_tier": min_tier,
        "rules": rules,
        "validated_examples": examples,
        "local_context": local_context,
        "approved_active_learning": approved_lessons,
        "status": "ok",
        "warnings": [] if examples else ["Sem exemplos validados T1/T2 para este contexto ainda."],
    }


def _compact_text(value: Any, limit: int) -> str:
    text = str(value or "").strip().replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: max(limit - 3, 0)] + "..."
    return text


def _first_useful_excerpt(text: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines()]
    useful = [
        line
        for line in lines
        if line and not line.startswith("---") and not line.startswith("#")
    ]
    return " ".join(useful[:2]) if useful else str(text or "").strip()


def format_rule_text(rule: dict[str, Any], *, limit: int = 220) -> str:
    raw = str(rule.get("regra_semantica") or "").strip()
    try:
        payload = json.loads(raw)
    except Exception:
        return _compact_text(raw, limit)

    if not isinstance(payload, dict):
        return _compact_text(raw, limit)

    source_doc = payload.get("source_doc") or "domain_knowledge"
    section = payload.get("section") or "regra"
    excerpt = _first_useful_excerpt(payload.get("text") or "")
    text = f"{source_doc} :: {section}"
    if excerpt:
        text = f"{text} — {excerpt}"
    return _compact_text(text, limit)


def format_context_text(context: dict[str, Any], *, max_rules: int = 5, max_examples: int = 3) -> str:
    lines = [
        f"RAG read-only | classe={context.get('classe')} item={context.get('item_id')}",
        f"obra={context.get('obra') or '-'} pavimento={context.get('pavimento') or '-'} min_tier={context.get('min_tier')}",
        "",
        "Regras semanticas:",
    ]
    rules = context.get("rules") or []
    if not rules:
        lines.append("  - Nenhuma regra em semantic_rag_kb para esta classe.")
    else:
        for rule in rules[:max_rules]:
            lines.append(f"  - {format_rule_text(rule)}")

    lines.append("")
    lines.append("Contexto local da obra (nao e verdade global):")
    local_context = context.get("local_context") or []
    if not local_context:
        lines.append("  - Snapshot local ausente ou sem correspondencias.")
    else:
        for result in local_context[:max_examples]:
            lines.append(
                f"  - LOCAL/{result.get('tier')} {result.get('kind')} "
                f"{result.get('classe') or '-'} {result.get('item_id') or result.get('title') or '-'} "
                f"| score={result.get('score')}"
            )

    lines.append("")
    lines.append("Lições MCP aprovadas T1/T2:")
    approved_lessons = context.get("approved_active_learning") or []
    if not approved_lessons:
        lines.append("  - Nenhuma proposta MCP aprovada para este contexto.")
    else:
        for result in approved_lessons[:max_examples]:
            meta = result.get("meta") or {}
            lines.append(
                f"  - {meta.get('tier')} {meta.get('tipo')} "
                f"{meta.get('classe')} {meta.get('item_id')} | "
                f"score={result.get('score', 0):.3f}"
            )

    lines.append("")
    lines.append("Exemplos validados T1/T2:")
    examples = context.get("validated_examples") or []
    if not examples:
        lines.append("  - Nenhum exemplo validado ainda. Correto: T0 nao aparece aqui.")
    else:
        for ex in examples[:max_examples]:
            text = _compact_text(ex.get("text"), 160)
            lines.append(
                f"  - {ex.get('tier')} {ex.get('tipo')} {ex.get('id')} "
                f"obra={ex.get('obra')} pav={ex.get('pavimento')} | {text}"
            )

    warnings = context.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("Avisos:")
        for warning in warnings:
            lines.append(f"  - {warning}")
    return "\n".join(lines)


if __name__ == "__main__":
    ctx = get_rag_context_for_item(classe="PL", item_id="P1", obra="Obra_TREINO_1", pavimento="1_PAV")
    print(format_context_text(ctx))
