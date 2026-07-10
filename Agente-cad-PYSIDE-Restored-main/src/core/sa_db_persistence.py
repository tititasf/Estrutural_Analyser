"""Persistência transacional da reanálise do Structural Analyzer.

O headless produz um candidato novo. Este módulo combina esse candidato com o
ground truth humano já salvo e grava PIL/LAJ/FV/LV em uma única transação.
"""

from __future__ import annotations

import copy
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_VALIDATION_LISTS = ("validated_fields", "na_fields")
_VALIDATION_MAPS = (
    "validated_link_classes",
    "na_link_classes",
    "na_reasons",
)
_FV_SOURCE_RE = re.compile(r"^viga_fundo_seg_(\d+)_area_segs$")
_LV_SOURCE_RE = re.compile(
    r"^viga_([ab])_seg_(\d+)_(comprimento_total|comp_total_passa)$"
)


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        try:
            import numpy as np

            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.bool_):
                return bool(obj)
        except ImportError:
            pass
        return super().default(obj)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, cls=_NumpyEncoder)


def _contains_validated_link(item: dict) -> bool:
    for slots in (item.get("links") or {}).values():
        if not isinstance(slots, dict):
            continue
        for links in slots.values():
            if not isinstance(links, list):
                continue
            if any(isinstance(link, dict) and link.get("validated") for link in links):
                return True
    return False


def has_human_validation(item: dict | None) -> bool:
    """Selo real: item, campo, slot ou vínculo. Pré-ficha não conta."""
    if not isinstance(item, dict):
        return False
    return bool(
        item.get("is_validated")
        or item.get("validated_fields")
        or any(item.get("validated_link_classes", {}).values())
        or _contains_validated_link(item)
    )


def _copy_field(old: dict, result: dict, field: str) -> None:
    """Preserva valor e vínculos de um campo integralmente validado."""
    if field in old:
        result[field] = copy.deepcopy(old[field])
    else:
        result.pop(field, None)

    old_fields = old.get("fields") or {}
    result_fields = result.setdefault("fields", {})
    if field in old_fields:
        result_fields[field] = copy.deepcopy(old_fields[field])
    else:
        result_fields.pop(field, None)

    old_links = old.get("links") or {}
    result_links = result.setdefault("links", {})
    if field in old_links:
        result_links[field] = copy.deepcopy(old_links[field])
    else:
        result_links.pop(field, None)


def _copy_validated_slots(old: dict, result: dict) -> None:
    old_links = old.get("links") or {}
    result_links = result.setdefault("links", {})
    for field, slots in (old.get("validated_link_classes") or {}).items():
        old_field_links = old_links.get(field) or {}
        if not isinstance(old_field_links, dict):
            continue
        new_field_links = result_links.setdefault(field, {})
        for slot in slots or []:
            if slot in old_field_links:
                new_field_links[slot] = copy.deepcopy(old_field_links[slot])
            else:
                new_field_links.pop(slot, None)


def _apply_na(old: dict, result: dict) -> None:
    for field in old.get("na_fields") or []:
        result.pop(field, None)
        (result.get("fields") or {}).pop(field, None)
        (result.get("links") or {}).pop(field, None)

    result_links = result.setdefault("links", {})
    for field, slots in (old.get("na_link_classes") or {}).items():
        field_links = result_links.setdefault(field, {})
        old_field_links = (old.get("links") or {}).get(field) or {}
        for slot in slots or []:
            if slot in old_field_links:
                field_links[slot] = copy.deepcopy(old_field_links[slot])
            else:
                field_links.pop(slot, None)


def _preserve_geometry_root(old: dict, result: dict, kind: str) -> None:
    validated_fields = set(old.get("validated_fields") or [])
    validated_slots = old.get("validated_link_classes") or {}
    if kind == "PIL":
        geometry_field = "pilar_segs"
        root_keys = ("points", "area", "area_val", "bbox", "pos")
    elif kind == "LAJ":
        geometry_field = "laje_outline_segs"
        root_keys = ("points", "area", "area_val", "bbox", "pos")
    else:
        return

    geometry_validated = (
        geometry_field in validated_fields
        or bool(validated_slots.get(geometry_field))
    )
    if not geometry_validated:
        return
    for key in root_keys:
        if key in old:
            result[key] = copy.deepcopy(old[key])
        else:
            result.pop(key, None)


def _topology_class(source_key: str) -> tuple[str, int] | None:
    match = _FV_SOURCE_RE.match(source_key)
    if match:
        return "FV", int(match.group(1))
    match = _LV_SOURCE_RE.match(source_key)
    if not match:
        return None
    side, index, suffix = match.groups()
    behavior = "PARA" if suffix == "comprimento_total" else "PASSA"
    return f"LV_{side.upper()}_{behavior}", int(index)


def _validated_topology_sources(old: dict) -> dict[str, set[str]]:
    sources: dict[str, set[str]] = {}
    candidates = set(old.get("validated_fields") or [])
    candidates.update(
        field
        for field, slots in (old.get("validated_link_classes") or {}).items()
        if slots
    )
    for source_key, slots in (old.get("links") or {}).items():
        topology = _topology_class(str(source_key))
        if not topology or not isinstance(slots, dict):
            continue
        if any(
            isinstance(link, dict) and link.get("validated")
            for links in slots.values()
            if isinstance(links, list)
            for link in links
        ):
            candidates.add(str(source_key))

    for source_key in candidates:
        topology = _topology_class(str(source_key))
        if topology:
            sources.setdefault(topology[0], set()).add(str(source_key))
    return sources


def _lock_beam_topologies(old: dict, result: dict) -> None:
    locked = _validated_topology_sources(old)
    if not locked:
        return

    old_links = old.get("links") or {}
    result_links = result.setdefault("links", {})
    for class_name, allowed in locked.items():
        for source_key in list(result_links):
            topology = _topology_class(str(source_key))
            if topology and topology[0] == class_name and source_key not in allowed:
                result_links.pop(source_key, None)
        for source_key in allowed:
            if source_key in old_links:
                result_links[source_key] = copy.deepcopy(old_links[source_key])

        if class_name == "FV":
            allowed_indexes = {
                int(_FV_SOURCE_RE.match(key).group(1))
                for key in allowed
                if _FV_SOURCE_RE.match(key)
            }
            for container in (result, result.get("fields") or {}):
                for key in list(container):
                    match = re.match(r"^viga_fundo_seg_(\d+)_", str(key))
                    if match and int(match.group(1)) not in allowed_indexes:
                        container.pop(key, None)
            result["preficha_fundo_locked"] = True
            result["preficha_fundo_locked_version"] = 2
            result["preficha_fundo_locked_source_keys"] = sorted(allowed)

    result["validated_segment_topologies_v1"] = {
        class_name: sorted(keys) for class_name, keys in locked.items()
    }


def merge_analysis_item(old: dict | None, new: dict, kind: str) -> dict:
    """Combina candidato novo com ground truth granular salvo."""
    if not old:
        return copy.deepcopy(new)
    if old.get("is_validated"):
        preserved = copy.deepcopy(old)
        preserved["id_item"] = new.get("id_item", preserved.get("id_item"))
        preserved["project_id"] = new.get(
            "project_id", preserved.get("project_id")
        )
        return preserved

    result = copy.deepcopy(new)
    result["id"] = old.get("id", result.get("id"))
    result["project_id"] = old.get("project_id", result.get("project_id"))

    # A análise automática não cria autoridade humana. Metadados de validação
    # e N/A vêm exatamente do registro anterior, sem união ou reordenação.
    for key in (*_VALIDATION_LISTS, *_VALIDATION_MAPS):
        result[key] = copy.deepcopy(old.get(key) or ([] if key in _VALIDATION_LISTS else {}))

    for field in old.get("validated_fields") or []:
        _copy_field(old, result, str(field))
    _copy_validated_slots(old, result)
    _apply_na(old, result)
    _preserve_geometry_root(old, result, kind)
    if kind == "BEAM":
        _lock_beam_topologies(old, result)
    return result


def merge_analysis_collection(
    old_items: list[dict] | None,
    new_items: list[dict] | None,
    kind: str,
    project_id: str,
) -> tuple[list[dict], dict]:
    """Mescla por nome e mantém órfãos somente quando têm validação real."""
    old_by_name = {
        str(item.get("name")): item
        for item in old_items or []
        if item.get("name")
    }
    merged: list[dict] = []
    matched: set[str] = set()
    occupied_ids = {
        str(item.get("id")) for item in old_items or [] if item.get("id")
    }
    preserved_items = 0

    for item in new_items or []:
        name = str(item.get("name") or "")
        old = old_by_name.get(name)
        candidate = merge_analysis_item(old, item, kind)
        if old:
            matched.add(name)
            if has_human_validation(old):
                preserved_items += 1
        else:
            candidate_id = str(candidate.get("id") or "")
            if not candidate_id or candidate_id in occupied_ids:
                candidate["id"] = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"cad-analyzer:{project_id}:{kind}:{name}",
                    )
                )
        candidate["project_id"] = project_id
        merged.append(candidate)

    preserved_orphans = 0
    for name, old in old_by_name.items():
        if name in matched or not has_human_validation(old):
            continue
        merged.append(copy.deepcopy(old))
        preserved_orphans += 1

    merged.sort(
        key=lambda item: [
            int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", str(item.get("name") or ""))
        ]
    )
    for index, item in enumerate(merged, start=1):
        item["id_item"] = f"{index:02}"
        item["project_id"] = project_id

    return merged, {
        "old": len(old_items or []),
        "new": len(new_items or []),
        "persisted": len(merged),
        "items_com_ground_truth_preservado": preserved_items,
        "orfaos_validados_preservados": preserved_orphans,
    }


def merge_analysis_snapshot(
    *,
    old_pillars: list[dict],
    old_slabs: list[dict],
    old_beams: list[dict],
    new_pillars: list[dict],
    new_slabs: list[dict],
    new_beams: list[dict],
    project_id: str,
) -> tuple[dict[str, list[dict]], dict]:
    collections = {}
    stats = {}
    for label, kind, old, new in (
        ("pillars", "PIL", old_pillars, new_pillars),
        ("slabs", "LAJ", old_slabs, new_slabs),
        ("beams", "BEAM", old_beams, new_beams),
    ):
        collections[label], stats[label] = merge_analysis_collection(
            old, new, kind, project_id
        )
    return collections, stats


def fv_area_errors(beams: list[dict]) -> list[str]:
    """Lista contornos FV automáticos que não representam área fechada."""
    errors: list[str] = []
    for beam in beams or []:
        validated_sources = _validated_topology_sources(beam).get("FV", set())
        if beam.get("is_validated"):
            validated_sources.update(
                key for key in (beam.get("links") or {}) if _FV_SOURCE_RE.match(str(key))
            )
        for source_key, slots in (beam.get("links") or {}).items():
            if not _FV_SOURCE_RE.match(str(source_key)) or source_key in validated_sources:
                continue
            contours = slots.get("contour") if isinstance(slots, dict) else None
            if not contours:
                continue
            for occurrence, link in enumerate(contours, start=1):
                points = (link or {}).get("points") if isinstance(link, dict) else []
                clean = []
                for point in points or []:
                    try:
                        clean.append((float(point[0]), float(point[1])))
                    except (TypeError, ValueError, IndexError):
                        continue
                area = 0.0
                if len(clean) >= 3:
                    area = abs(sum(
                        x1 * y2 - x2 * y1
                        for (x1, y1), (x2, y2) in zip(
                            clean, clean[1:] + clean[:1]
                        )
                    )) / 2.0
                closed = len(clean) >= 4 and clean[0] == clean[-1]
                if not closed or area <= 0.05:
                    errors.append(
                        f"{beam.get('name')}:{source_key}:{occurrence}:"
                        f"closed={closed}:area={area:.6f}"
                    )
    return errors


def _pillar_params(item: dict, project_id: str) -> tuple:
    from src.core.database import DatabaseManager

    extra = {
        key: value
        for key, value in item.items()
        if key not in DatabaseManager._PILLAR_FIXED_KEYS
    }
    return (
        item["id"], project_id, item.get("name"), item.get("type"),
        float(item.get("area_val", item.get("area", 0.0)) or 0.0),
        _json(item.get("points", [])), _json(item.get("sides_data", {})),
        _json(item.get("links", {})), _json(item.get("confidence_map", {})),
        _json(item.get("validated_fields", [])),
        _json(item.get("validated_link_classes", {})),
        _json(item.get("na_fields", [])),
        _json(item.get("na_link_classes", {})),
        _json(item.get("na_reasons", {})), _json(item.get("issues", [])),
        item.get("id_item"), 1 if item.get("is_validated") else 0,
        item.get("pkl_path"), _json(extra) if extra else None,
    )


def _slab_params(item: dict, project_id: str) -> tuple:
    from src.core.database import DatabaseManager

    extra = {
        key: value
        for key, value in item.items()
        if key not in DatabaseManager._SLAB_FIXED_KEYS
    }
    return (
        item["id"], project_id, item.get("name"), item.get("type", "Laje"),
        float(item.get("area", 0.0) or 0.0), _json(item.get("points", [])),
        _json(item.get("links", {})), _json(item.get("validated_fields", [])),
        _json(item.get("validated_link_classes", {})),
        _json(item.get("na_fields", [])),
        _json(item.get("na_link_classes", {})),
        _json(item.get("na_reasons", {})), _json(item.get("issues", [])),
        item.get("id_item"), 1 if item.get("is_validated") else 0,
        item.get("pkl_path"), _json(extra) if extra else None,
    )


def _beam_params(item: dict, project_id: str) -> tuple:
    return (
        item["id"], project_id, item.get("name"), _json(item),
        _json(item.get("validated_fields", [])),
        _json(item.get("validated_link_classes", {})),
        _json(item.get("na_fields", [])),
        _json(item.get("na_link_classes", {})),
        _json(item.get("na_reasons", {})), item.get("id_item"),
        1 if item.get("is_validated") else 0, item.get("pkl_path"),
    )


def _delete_missing(
    conn: sqlite3.Connection,
    table: str,
    project_id: str,
    items: list[dict],
) -> None:
    ids = [str(item["id"]) for item in items]
    if not ids:
        conn.execute(f"DELETE FROM {table} WHERE project_id=?", (project_id,))
        return
    marks = ",".join("?" for _ in ids)
    conn.execute(
        f"DELETE FROM {table} WHERE project_id=? AND id NOT IN ({marks})",
        [project_id, *ids],
    )


def persist_analysis_snapshot(
    *,
    db_path: str,
    project_id: str,
    collections: dict[str, list[dict]],
    run_id: str,
    html_dir: str,
    source_dxf: str,
    merge_stats: dict,
) -> dict:
    """Grava as três coleções em uma única transação ``BEGIN IMMEDIATE``."""
    db = Path(db_path)
    if not db.is_file():
        raise FileNotFoundError(f"DB não encontrado: {db}")

    conn = sqlite3.connect(str(db), timeout=60)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        before = {
            table: int(conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id=?",
                (project_id,),
            ).fetchone()[0])
            for table in ("pillars", "slabs", "beams")
        }

        for item in collections["pillars"]:
            conn.execute(
                """
                INSERT INTO pillars (
                    id,project_id,name,type,area,points_json,sides_data_json,
                    links_json,conf_map_json,validated_fields_json,
                    validated_link_classes_json,na_fields_json,
                    na_link_classes_json,na_reasons_json,issues_json,id_item,
                    is_validated,pkl_path,extra_data_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,name=excluded.name,
                    type=excluded.type,area=excluded.area,
                    points_json=excluded.points_json,
                    sides_data_json=excluded.sides_data_json,
                    links_json=excluded.links_json,
                    conf_map_json=excluded.conf_map_json,
                    validated_fields_json=excluded.validated_fields_json,
                    validated_link_classes_json=excluded.validated_link_classes_json,
                    na_fields_json=excluded.na_fields_json,
                    na_link_classes_json=excluded.na_link_classes_json,
                    na_reasons_json=excluded.na_reasons_json,
                    issues_json=excluded.issues_json,id_item=excluded.id_item,
                    is_validated=excluded.is_validated,pkl_path=excluded.pkl_path,
                    extra_data_json=excluded.extra_data_json
                """,
                _pillar_params(item, project_id),
            )

        for item in collections["slabs"]:
            conn.execute(
                """
                INSERT INTO slabs (
                    id,project_id,name,type,area,points_json,links_json,
                    validated_fields_json,validated_link_classes_json,
                    na_fields_json,na_link_classes_json,na_reasons_json,
                    issues_json,id_item,is_validated,pkl_path,extra_data_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,name=excluded.name,
                    type=excluded.type,area=excluded.area,
                    points_json=excluded.points_json,
                    links_json=excluded.links_json,
                    validated_fields_json=excluded.validated_fields_json,
                    validated_link_classes_json=excluded.validated_link_classes_json,
                    na_fields_json=excluded.na_fields_json,
                    na_link_classes_json=excluded.na_link_classes_json,
                    na_reasons_json=excluded.na_reasons_json,
                    issues_json=excluded.issues_json,id_item=excluded.id_item,
                    is_validated=excluded.is_validated,pkl_path=excluded.pkl_path,
                    extra_data_json=excluded.extra_data_json
                """,
                _slab_params(item, project_id),
            )

        for item in collections["beams"]:
            conn.execute(
                """
                INSERT INTO beams (
                    id,project_id,name,data_json,validated_fields_json,
                    validated_link_classes_json,na_fields_json,
                    na_link_classes_json,na_reasons_json,id_item,is_validated,
                    pkl_path
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,name=excluded.name,
                    data_json=excluded.data_json,
                    validated_fields_json=excluded.validated_fields_json,
                    validated_link_classes_json=excluded.validated_link_classes_json,
                    na_fields_json=excluded.na_fields_json,
                    na_link_classes_json=excluded.na_link_classes_json,
                    na_reasons_json=excluded.na_reasons_json,
                    id_item=excluded.id_item,
                    is_validated=excluded.is_validated,pkl_path=excluded.pkl_path
                """,
                _beam_params(item, project_id),
            )

        for table in ("pillars", "slabs", "beams"):
            _delete_missing(conn, table, project_id, collections[table])

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sa_persistence_runs (
                run_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                html_dir TEXT,
                source_dxf TEXT,
                before_json TEXT NOT NULL,
                after_json TEXT NOT NULL,
                merge_stats_json TEXT NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        after = {table: len(collections[table]) for table in collections}
        conn.execute(
            """
            INSERT INTO sa_persistence_runs (
                run_id,project_id,created_at,html_dir,source_dxf,before_json,
                after_json,merge_stats_json,status
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id, project_id, datetime.now(timezone.utc).isoformat(),
                html_dir, source_dxf, _json(before), _json(after),
                _json(merge_stats), "COMMITTED",
            ),
        )
        conn.commit()
        return {
            "status": "COMMITTED",
            "run_id": run_id,
            "project_id": project_id,
            "before": before,
            "after": after,
            "merge_stats": merge_stats,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
