#!/usr/bin/env python3
"""Adaptadores mínimos de leitura N1 por classe para provas ultragranares."""

from __future__ import annotations

import copy
import fnmatch
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable

@dataclass(frozen=True)
class ClassSource:
    table: str
    payload_column: str
    source_columns: dict[str, str]
    allowed_paths: dict[str, tuple[str, ...]] | None = None


CLASS_SOURCES: dict[str, ClassSource] = {
    "PIL": ClassSource(
        table="pillars", payload_column="links_json",
        source_columns={
            "payload": "links_json", "geometry": "points_json",
            "sides": "sides_data_json", "extra": "extra_data_json",
            "confidence": "conf_map_json",
        },
    ),
    "LAJ": ClassSource(
        table="slabs", payload_column="links_json",
        source_columns={
            "payload": "links_json", "geometry": "points_json",
            "extra": "extra_data_json",
        },
    ),
    "FV": ClassSource(
        table="beams", payload_column="data_json",
        source_columns={
            "payload": "data_json", "links": "links_json",
            "sides": "sides_data_json",
        },
        allowed_paths={
            "payload": (
                "fields.nome", "fields.numero", "fields.dimensao",
                "fields.viga_fundo_*", "viga_fundo_*", "links.viga_segs.*",
                "links.apoios.*", "links.name.*", "links.cortes*",
                "links.aberturas*", "holes*", "preficha_segmentos*",
            ),
            "links": ("viga_fundo_*", "viga_segs.*", "apoios.*", "name.*", "cortes*", "aberturas*"),
            "sides": ("*",),
        },
    ),
    "LV": ClassSource(
        table="beams", payload_column="data_json",
        source_columns={
            "payload": "data_json", "links": "links_json",
            "sides": "sides_data_json",
        },
        allowed_paths={
            "payload": (
                "fields.nome", "fields.numero", "fields.dimensao",
                "fields.viga_a_*", "fields.viga_b_*",
                "links.viga_a_*", "links.viga_b_*",
                "lv_generation_contracts.*", "lv_interpreter_contract_version",
            ),
            "links": ("viga_a_*", "viga_b_*", "apoios.*", "name.*"),
            "sides": ("*",),
        },
    ),
}


def _assert_semantic_path(spec: ClassSource, classe: str, source: str, path: str) -> None:
    """Impede que FV e LV leiam famílias da outra classe no mesmo data_json."""
    if spec.allowed_paths is None:
        return
    patterns = spec.allowed_paths.get(source, ())
    if not path or not any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns):
        raise ValueError(
            f"path fora da família semântica de {classe}: source={source!r} path={path!r}"
        )


def json_value(raw: Any) -> Any:
    if raw in (None, ""):
        return None
    if isinstance(raw, (dict, list, int, float, bool)):
        return copy.deepcopy(raw)
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw


def table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in con.execute(f"PRAGMA table_info({table})")}


def raw_snapshot_hash(values: dict[str, Any]) -> str:
    """Hash determinístico da linha sem desserializar JSONs potencialmente grandes."""
    digest = hashlib.sha256()
    for column in sorted(values):
        name = column.encode("utf-8")
        value = values[column]
        if value is None:
            raw = b"<NULL>"
        elif isinstance(value, bytes):
            raw = value
        else:
            raw = str(value).encode("utf-8")
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


def _sqlite_json_path(path: str) -> str:
    result = "$"
    for token in (part for part in path.split(".") if part != ""):
        if token.isdigit():
            result += f"[{token}]"
        else:
            escaped = token.replace('"', '\\"')
            result += f'."{escaped}"'
    return result


def load_requested_fields(
    con: sqlite3.Connection, *, project_id: str, classe: str, item: str,
    fields: list[dict[str, Any]],
) -> dict[str, Any]:
    """Lê somente os JSON paths declarados; wildcard/raiz usam fallback da coluna."""
    classe = classe.upper()
    if classe not in CLASS_SOURCES:
        raise ValueError(f"classe não suportada: {classe}")
    spec = CLASS_SOURCES[classe]
    available = table_columns(con, spec.table)
    selections = ["id AS __id", "project_id AS __project_id", "name AS __name"]
    params: list[Any] = []
    descriptors: list[dict[str, Any]] = []
    selected_columns = {"id", "project_id", "name"}

    for index, field in enumerate(fields):
        field_id = str(field["id"])
        source = str(field.get("source") or "payload")
        path = str(field.get("path") or "")
        alias = f"__field_{index}"
        if source == "column":
            column, _, remaining = path.partition(".")
            if column not in available:
                raise ValueError(f"coluna indisponível em {spec.table}: {column}")
            if spec.allowed_paths is not None and column in spec.source_columns.values():
                semantic_sources = [
                    semantic_source for semantic_source, source_column in spec.source_columns.items()
                    if source_column == column
                ]
                if not semantic_sources or not any(
                    remaining and any(
                        fnmatch.fnmatchcase(remaining, pattern)
                        for pattern in spec.allowed_paths.get(semantic_source, ())
                    )
                    for semantic_source in semantic_sources
                ):
                    raise ValueError(
                        f"path de coluna fora da família semântica de {classe}: {path!r}"
                    )
            selections.append(f'"{column}" AS {alias}')
            selected_columns.add(column)
            descriptors.append({
                "id": field_id, "alias": alias, "preselected": not remaining,
                "remaining_path": remaining,
            })
            continue

        column = spec.source_columns.get(source)
        if not column or column not in available:
            raise ValueError(f"fonte indisponível para {classe}: {source}")
        _assert_semantic_path(spec, classe, source, path)
        selected_columns.add(column)
        exact_path = bool(path) and "*" not in path
        if exact_path:
            selections.append(f'json_extract("{column}", ?) AS {alias}')
            params.append(_sqlite_json_path(path))
        else:
            selections.append(f'"{column}" AS {alias}')
        descriptors.append({
            "id": field_id, "alias": alias, "preselected": exact_path,
            "remaining_path": "" if exact_path else path,
        })

    row = con.execute(
        f"SELECT {', '.join(selections)} FROM {spec.table} WHERE project_id=? AND name=?",
        (*params, project_id, item),
    ).fetchone()
    if row is None:
        raise ValueError(f"item ausente: {classe}:{item}")
    values = dict(zip(["__id", "__project_id", "__name", *[d["alias"] for d in descriptors]], row))
    raw_fields = {
        descriptor["id"]: {
            "value": values[descriptor["alias"]],
            "preselected": descriptor["preselected"],
            "remaining_path": descriptor["remaining_path"],
        }
        for descriptor in descriptors
    }
    snapshot_values = {
        "id": values["__id"], "project_id": values["__project_id"],
        "name": values["__name"],
        **{f"field:{field_id}": data["value"] for field_id, data in raw_fields.items()},
    }
    return {
        "classe": classe,
        "item": item,
        "table": spec.table,
        "selected_columns": sorted(selected_columns),
        "raw_fields": raw_fields,
        "snapshot_hash": raw_snapshot_hash(snapshot_values),
    }


def resolve_project_scope(
    con: sqlite3.Connection, *, project_id: str | None,
    obra: str | None = None, pav: str | None = None,
) -> str:
    if project_id:
        row = con.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise ValueError(f"project_id inexistente: {project_id}")
        return str(row[0])
    if not obra or not pav:
        raise ValueError("informe project_id ou obra+pav")
    rows = con.execute(
        "SELECT id FROM projects WHERE work_name=? AND pavement_name=? ORDER BY updated_at DESC",
        (obra, pav),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError(f"escopo ambíguo: obra={obra!r} pav={pav!r} resolveu {len(rows)} projetos")
    return str(rows[0][0])


def load_item_sources(
    con: sqlite3.Connection, *, project_id: str, classe: str, item: str,
    requested_sources: Iterable[str], requested_columns: Iterable[str] = (),
    decode_sources: bool = True,
) -> dict[str, Any]:
    classe = classe.upper()
    if classe not in CLASS_SOURCES:
        raise ValueError(f"classe não suportada: {classe}")
    spec = CLASS_SOURCES[classe]
    available = table_columns(con, spec.table)
    columns = {"id", "project_id", "name"}
    for source in requested_sources:
        column = spec.source_columns.get(source)
        if column and column in available:
            columns.add(column)
    columns.update(column for column in requested_columns if column in available)
    ordered = sorted(columns)
    row = con.execute(
        f"SELECT {', '.join(ordered)} FROM {spec.table} WHERE project_id=? AND name=?",
        (project_id, item),
    ).fetchone()
    if row is None:
        raise ValueError(f"item ausente: {classe}:{item}")
    values = dict(zip(ordered, row))
    sources: dict[str, Any] = {}
    for source, column in spec.source_columns.items():
        if column in values:
            sources[source] = json_value(values[column]) if decode_sources else values[column]
    sources["column"] = {
        column: json_value(value) if decode_sources else value
        for column, value in values.items()
        if column not in spec.source_columns.values()
    }
    return {
        "classe": classe,
        "item": item,
        "table": spec.table,
        "selected_columns": ordered,
        "sources": sources,
        "snapshot_hash": raw_snapshot_hash(values),
        "sources_decoded": decode_sources,
    }
