#!/usr/bin/env python3
"""Consulta RAG particionada e retrocompatível para o QA Global.

Tier pode viver em coluna nativa ou embutido no JSON de ``regra_semantica``
(legado). Filtro por tier falha fechado quando exigido e não há como tipar.
"""

from __future__ import annotations

import json
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


def parse_tier_from_rule(regra_semantica: object) -> str | None:
    """Extrai tier do JSON da regra quando a coluna tier não existe."""
    if regra_semantica is None:
        return None
    if isinstance(regra_semantica, dict):
        tier = regra_semantica.get("tier") or regra_semantica.get("tier_candidate")
        return str(tier).upper() if tier else None
    text = str(regra_semantica).strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        tier = data.get("tier") or data.get("tier_candidate")
        return str(tier).upper() if tier else None
    return None


def parse_field_from_rule(regra_semantica: object) -> str | None:
    if isinstance(regra_semantica, dict):
        field = regra_semantica.get("field_id") or regra_semantica.get("campo")
        return str(field) if field else None
    text = str(regra_semantica or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None
    if isinstance(data, dict):
        field = data.get("field_id") or data.get("campo")
        return str(field) if field else None
    return None


def load_partitioned_rag(
    con: sqlite3.Connection, classes: Iterable[str], *,
    family: str | None = None, field: str | None = None,
    tiers: Iterable[str] | None = None, obra: str | None = None,
    pav: str | None = None, limit: int = 50,
    require_tier: bool = False,
) -> dict[str, list[dict]]:
    classes = [str(classe).upper() for classe in classes]
    result = {classe: [] for classe in classes}
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "semantic_rag_kb" not in tables:
        if require_tier and tiers:
            raise RuntimeError(
                "RAG required com filtro de tier, mas a tabela semantic_rag_kb não existe"
            )
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
    order_col = "created_at" if "created_at" in columns else "id"
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
        tier_column = aliases["tier"]
        if requested["tier"] and tier_column:
            placeholders = ",".join("?" for _ in requested["tier"])
            where.append(f"upper({tier_column}) IN ({placeholders})")
            params.extend(requested["tier"])
            applied.append("tier")
        # Busca folgada; filtros JSON de tier/field aplicam-se depois
        fetch_limit = max(1, int(limit) * 4 if (requested["tier"] and not tier_column) else int(limit))
        params.append(fetch_limit)
        rows = con.execute(
            f"SELECT {', '.join(selected_columns)} FROM semantic_rag_kb "
            f"WHERE {' AND '.join(where)} ORDER BY {order_col} DESC, id DESC LIMIT ?",
            params,
        ).fetchall()
        entries: list[dict] = []
        for row in rows:
            regra = row["regra_semantica"] if "regra_semantica" in row.keys() else None
            tier_value = None
            if tier_column and tier_column in row.keys() and row[tier_column]:
                tier_value = str(row[tier_column]).upper()
            else:
                tier_value = parse_tier_from_rule(regra)
            field_value = None
            if aliases["field"] and aliases["field"] in row.keys() and row[aliases["field"]]:
                field_value = row[aliases["field"]]
            else:
                field_value = parse_field_from_rule(regra)

            if requested["field"] and not aliases["field"]:
                if field_value and str(field_value).lower() != str(requested["field"]).lower():
                    continue
                if not field_value:
                    continue
                if "field" not in applied:
                    applied.append("field_json")

            if requested["tier"]:
                if tier_value not in set(requested["tier"]):
                    if not tier_value and require_tier:
                        continue
                    if tier_value:
                        continue
                    if require_tier:
                        continue
                    # sem tier parseável e require_tier=False: descarta para não confirmar com T3 ambíguo
                    continue
                if "tier" not in applied and "tier_json" not in applied:
                    applied.append("tier_json" if not tier_column else "tier")

            entry = {
                "kind": "rag_semantic_context",
                "rag_id": row["id"],
                "classe": row["classe"],
                "regra_semantica": regra,
                "obra_contexto": row["obra_contexto"] if "obra_contexto" in row.keys() else None,
                "confianca_declarada": row["confianca"] if "confianca" in row.keys() else None,
                "created_at": row["created_at"] if "created_at" in row.keys() else None,
                "tier": tier_value,
                "field": field_value,
                "partition": {
                    "requested": requested,
                    "applied": list(dict.fromkeys(applied)),
                    "unavailable": [
                        kind for kind in unavailable
                        if kind not in ("tier", "field") or (
                            kind == "tier" and not tier_value and not tier_column
                        )
                    ],
                    "exact": not unavailable or (tier_value is not None if requested["tier"] else True),
                },
                "authority": "consultative_only; requires local CAD/ficha evidence and human-approved tier before confirmation",
            }
            for kind in ("family", "pav"):
                column = aliases[kind]
                if column and column in row.keys():
                    entry[kind] = row[column]
            entries.append(entry)
            if len(entries) >= max(1, int(limit)):
                break

        if require_tier and requested["tier"] and not entries:
            raise RuntimeError(
                f"RAG required com tier={requested['tier']} para {classe}, "
                "mas nenhuma entrada tipável (coluna ou JSON) correspondeu"
            )
        result[classe] = entries
    return result
