#!/usr/bin/env python3
"""Consulta RAG particionada e retrocompatível para o QA Global."""

from __future__ import annotations

import sqlite3
from typing import Iterable


FIELD_ALIASES = {
    "family": ("familia", "family", "subclasse"),
    "field": ("campo", "field_id"),
    "tier": ("tier",),
    "obra": ("obra", "obra_contexto"),
    "pav": ("pavimento", "pav"),
}


def _first(columns: set[str], aliases: tuple[str, ...]) -> str | None:
    return next((name for name in aliases if name in columns), None)


def load_partitioned_rag(
    con: sqlite3.Connection, classes: Iterable[str], *,
    family: str | None = None, field: str | None = None,
    tiers: Iterable[str] | None = None, obra: str | None = None,
    pav: str | None = None, limit: int = 50,
) -> dict[str, list[dict]]:
    classes = [str(classe).upper() for classe in classes]
    result = {classe: [] for classe in classes}
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "semantic_rag_kb" not in tables:
        return result
    columns = {row[1] for row in con.execute("PRAGMA table_info(semantic_rag_kb)")}
    aliases = {kind: _first(columns, names) for kind, names in FIELD_ALIASES.items()}
    requested = {
        "family": family,
        "field": field,
        "tier": sorted({str(tier).upper() for tier in (tiers or [])}) or None,
        "obra": obra,
        "pav": pav,
    }
    con.row_factory = sqlite3.Row
    selected_columns = [
        name for name in (
            "id", "classe", "regra_semantica", "obra_contexto", "confianca", "created_at",
            aliases["family"], aliases["field"], aliases["tier"], aliases["pav"],
        )
        if name and name in columns
    ]
    selected_columns = list(dict.fromkeys(selected_columns))
    for classe in classes:
        where = ["upper(classe)=?"]
        params: list[object] = [classe]
        applied: list[str] = []
        unavailable: list[str] = []
        for kind in ("family", "field", "obra", "pav"):
            value = requested[kind]
            if value is None:
                continue
            column = aliases[kind]
            if column:
                where.append(f"lower({column})=lower(?)")
                params.append(value)
                applied.append(kind)
            else:
                unavailable.append(kind)
        if requested["tier"]:
            column = aliases["tier"]
            if column:
                placeholders = ",".join("?" for _ in requested["tier"])
                where.append(f"upper({column}) IN ({placeholders})")
                params.extend(requested["tier"])
                applied.append("tier")
            else:
                unavailable.append("tier")
        params.append(max(1, int(limit)))
        rows = con.execute(
            f"SELECT {', '.join(selected_columns)} FROM semantic_rag_kb "
            f"WHERE {' AND '.join(where)} ORDER BY created_at DESC, id DESC LIMIT ?",
            params,
        ).fetchall()
        exact = not unavailable
        entries: list[dict] = []
        for row in rows:
            entry = {
                "kind": "rag_semantic_context",
                "rag_id": row["id"],
                "classe": row["classe"],
                "regra_semantica": row["regra_semantica"],
                "obra_contexto": row["obra_contexto"] if "obra_contexto" in row.keys() else None,
                "confianca_declarada": row["confianca"] if "confianca" in row.keys() else None,
                "created_at": row["created_at"] if "created_at" in row.keys() else None,
                "partition": {
                    "requested": requested,
                    "applied": applied,
                    "unavailable": unavailable,
                    "exact": exact,
                },
                "authority": "consultative_only; requires local CAD/ficha evidence and human-approved tier before confirmation",
            }
            for kind in ("family", "field", "tier", "pav"):
                column = aliases[kind]
                if column and column in row.keys():
                    entry[kind] = row[column]
            entries.append(entry)
        result[classe] = entries
    return result
