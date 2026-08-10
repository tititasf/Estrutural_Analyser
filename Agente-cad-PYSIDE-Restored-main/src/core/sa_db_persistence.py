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
    if not isinstance(result_links, dict):
        result_links = {}
        result["links"] = result_links
    for field, slots in (old.get("na_link_classes") or {}).items():
        field_links = result_links.get(field)
        if not isinstance(field_links, dict):
            field_links = {}
            result_links[field] = field_links
        old_field_links = (old.get("links") or {}).get(field) or {}
        if not isinstance(old_field_links, dict):
            old_field_links = {}
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


def _cut_signature(link: dict) -> tuple | None:
    """Assinatura geométrica estável para atualizar ficha sem trocar o corte humano."""
    points = link.get("points") or []
    try:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
    except (TypeError, ValueError, IndexError):
        return None
    if not xs or not ys:
        return None
    return (
        round((min(xs) + max(xs)) / 2.0, 1),
        round((min(ys) + max(ys)) / 2.0, 1),
        round(max(xs) - min(xs), 1),
        round(max(ys) - min(ys), 1),
    )


def _refresh_inferred_laj_cut_fichas(old: dict, fresh: dict) -> None:
    """Atualiza somente campos derivados de cortes inferidos já preservados.

    O selo protege a geometria e a decisão humana, não uma fórmula obsoleta.
    Nunca toca em corte humano nem cria/remapeia geometria.
    """
    old_cuts = ((old.get("links") or {}).get("laje_visao_corte") or {}).get("cut_view_geom") or []
    fresh_cuts = ((fresh.get("links") or {}).get("laje_visao_corte") or {}).get("cut_view_geom") or []
    fresh_by_signature = {
        signature: cut
        for cut in fresh_cuts
        if isinstance(cut, dict) and (signature := _cut_signature(cut)) is not None
    }
    for old_cut in old_cuts:
        if not isinstance(old_cut, dict) or not old_cut.get("is_inferred"):
            continue
        fresh_cut = fresh_by_signature.get(_cut_signature(old_cut))
        if not isinstance(fresh_cut, dict):
            continue
        for key in ("ficha", "ficha_links", "cotas_debug"):
            if key in fresh_cut:
                old_cut[key] = copy.deepcopy(fresh_cut[key])


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
    """Fontes de topologia (FV/LV) travadas contra recomputação automática.

    Selo `qa_agente` sozinho NUNCA trava (decisão do dono, 2026-07-18): o
    agente QA ainda é `diagnostic_only` para FV/LV
    (`docs/CONVENCAO-SELOS-VALIDACAO.md`), e travar a topologia por um selo
    que não comparou segmentos vizinhos entre si já protegeu geometria com
    bug (achado real: V301 sobreposto, selado `qa_agente` em 2026-07-17
    permaneceu sobreposto mesmo após o motor ser corrigido). Origem humana
    (`humano_app`/`humano_portal`, dado legado migrado incluso) trava; campo
    sem nenhum rastro de origem em ``validated_fields`` (link marcado
    ``validated`` direto, fluxo anterior a 2026-07-13) também trava, para não
    mudar o comportamento de quem nunca passou pelo agente.
    """
    from src.core.validation_model import (
        ORIGEM_QA_AGENTE,
        migrar_validated_fields_legado,
        origens_do_campo,
    )

    validated_fields = migrar_validated_fields_legado(old.get("validated_fields"))

    def _locks(field_id: str) -> bool:
        """Trava, a menos que a origem seja explicitamente só ``qa_agente``.

        Sem rastro de origem (campo nunca passou por ``validated_fields``,
        ex.: link marcado ``validated`` diretamente por um fluxo legado/de
        teste) mantém o comportamento conservador anterior — trava.
        """
        origins = origens_do_campo(validated_fields, field_id)
        if not origins:
            return True
        return bool(origins - {ORIGEM_QA_AGENTE})

    sources: dict[str, set[str]] = {}
    candidates = {field_id for field_id in validated_fields if _locks(field_id)}
    candidates.update(
        field
        for field, slots in (old.get("validated_link_classes") or {}).items()
        if slots and _locks(field)
    )
    for source_key, slots in (old.get("links") or {}).items():
        topology = _topology_class(str(source_key))
        if not topology or not isinstance(slots, dict):
            continue
        if not _locks(str(source_key)):
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
        if kind == "LAJ":
            _refresh_inferred_laj_cut_fichas(preserved, new)
        return preserved

    result = copy.deepcopy(new)
    result["id"] = old.get("id", result.get("id"))
    result["project_id"] = old.get("project_id", result.get("project_id"))

    # FV tem topologia de segmentos: uma área antiga isolada só pode voltar se
    # representar um lock humano completo. Caso contrário ela é estado stale e
    # deve deixar a nova análise reconstruir todas as áreas, preservando apenas
    # os campos auxiliares (dimensão/apoios) que forem realmente validados.
    preservation_old = old
    if kind == "BEAM":
        try:
            from src.core.preficha_segments import fundo_topology_is_locked
            stale_fv_topology = not fundo_topology_is_locked(old)
        except Exception:
            stale_fv_topology = False
        if stale_fv_topology:
            preservation_old = copy.deepcopy(old)
            fv_area_keys = {
                str(field)
                for field in preservation_old.get("validated_fields") or []
                if _FV_SOURCE_RE.match(str(field))
            }
            preservation_old["validated_fields"] = [
                field for field in preservation_old.get("validated_fields") or []
                if str(field) not in fv_area_keys
            ]
            for validation_map in (
                "validated_link_classes",
                "na_link_classes",
                "na_reasons",
            ):
                preserved_map = preservation_old.get(validation_map) or {}
                if isinstance(preserved_map, dict):
                    preservation_old[validation_map] = {
                        field: value
                        for field, value in preserved_map.items()
                        if not _FV_SOURCE_RE.match(str(field))
                    }
            links = preservation_old.get("links") or {}
            for source_key in list(links):
                if _FV_SOURCE_RE.match(str(source_key)):
                    links.pop(source_key, None)
            preservation_old["preficha_fundo_locked"] = False
            preservation_old.pop("preficha_fundo_locked_source_keys", None)

    # A análise automática não cria autoridade humana. Metadados de validação
    # e N/A vêm exatamente do registro anterior, sem união ou reordenação.
    for key in (*_VALIDATION_LISTS, *_VALIDATION_MAPS):
        result[key] = copy.deepcopy(
            preservation_old.get(key) or ([] if key in _VALIDATION_LISTS else {})
        )

    for field in preservation_old.get("validated_fields") or []:
        _copy_field(preservation_old, result, str(field))
    _copy_validated_slots(preservation_old, result)
    _apply_na(preservation_old, result)
    _preserve_geometry_root(preservation_old, result, kind)
    if kind == "BEAM":
        _lock_beam_topologies(preservation_old, result)
    return result


def _laj_candidate_quality(item: dict) -> tuple[int, int, int, float, int]:
    """Ordena candidatas LAJ de mesmo rótulo sem usar posição/ID do projeto.

    Um rótulo textual pode ser visto por mais de uma região durante o traçado.
    A identidade persistida continua sendo o rótulo da laje; portanto só uma
    candidata pode ocupar esse slot. Uma geometria fechada, não degenerada e
    com pelo menos quatro vértices distintos é mais confiável que um fragmento
    aberto/triangular. Selo humano ainda vence qualquer métrica automática.

    O último componente torna o desempate determinístico para a mesma entrada,
    sem depender de coordenadas, obra, pavimento ou número de item.
    """
    raw_points = item.get("points") or []
    points: list[tuple[float, float]] = []
    for point in raw_points:
        try:
            points.append((float(point[0]), float(point[1])))
        except (IndexError, TypeError, ValueError):
            continue
    unique = {(round(x, 6), round(y, 6)) for x, y in points}
    closed = len(points) >= 4 and points[0] == points[-1]
    has_polygon = closed and len(unique) >= 4
    try:
        confidence = float(
            (item.get("extra_data") or item.get("trace_diagnostics") or {}).get(
                "confidence_score", item.get("confidence_score", 0.0)
            )
        )
    except (TypeError, ValueError):
        confidence = 0.0
    return (
        1 if has_human_validation(item) else 0,
        1 if has_polygon else 0,
        1 if closed else 0,
        confidence,
        len(unique),
    )


def _canonical_laj_by_name(items: list[dict] | None) -> tuple[dict[str, dict], int]:
    """Retorna a única candidata LAJ por rótulo e quantifica duplicatas.

    Entradas sem nome não têm identidade e seguem fora deste índice. Duplicata
    humana não é apagada aqui: o chamador a preserva e a limpeza posterior só
    remove as sobras sem qualquer validação humana.
    """
    grouped: dict[str, list[dict]] = {}
    for item in items or []:
        name = str(item.get("name") or "").strip()
        if name:
            grouped.setdefault(name, []).append(item)
    canonical: dict[str, dict] = {}
    duplicates = 0
    for name, group in grouped.items():
        canonical[name] = max(group, key=_laj_candidate_quality)
        duplicates += max(0, len(group) - 1)
    return canonical, duplicates


def merge_analysis_collection(
    old_items: list[dict] | None,
    new_items: list[dict] | None,
    kind: str,
    project_id: str,
) -> tuple[list[dict], dict]:
    """Mescla por nome e mantém órfãos somente quando têm validação real."""
    if kind == "LAJ":
        old_by_name, old_duplicates = _canonical_laj_by_name(old_items)
        new_by_name, new_duplicates = _canonical_laj_by_name(new_items)
        candidates = list(new_by_name.values()) + [
            item for item in new_items or [] if not str(item.get("name") or "").strip()
        ]
    else:
        old_by_name = {
            str(item.get("name")): item
            for item in old_items or []
            if item.get("name")
        }
        candidates = list(new_items or [])
        old_duplicates = 0
        new_duplicates = 0
    merged: list[dict] = []
    matched: set[str] = set()
    occupied_ids = {
        str(item.get("id")) for item in old_items or [] if item.get("id")
    }
    preserved_items = 0

    for item in candidates:
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
        "duplicatas_laj_descartadas_da_analise": new_duplicates,
        "duplicatas_laj_preexistentes": old_duplicates,
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


def _persisted_laj_row_has_human_validation(row: sqlite3.Row | tuple) -> bool:
    """Equivalente DB de :func:`has_human_validation` para limpeza segura."""
    is_validated, fields_json, links_json = row
    if is_validated:
        return True
    try:
        if json.loads(fields_json or "[]"):
            return True
    except (TypeError, json.JSONDecodeError):
        # Dado ilegível é evidência insuficiente para apagar automaticamente.
        return True
    try:
        if any(json.loads(links_json or "{}").values()):
            return True
    except (AttributeError, TypeError, json.JSONDecodeError):
        return True
    return False


def _remove_unvalidated_laj_identity_duplicates(
    conn: sqlite3.Connection,
    project_id: str,
    slabs: list[dict],
) -> dict[str, int]:
    """Remove somente sobras não humanas do mesmo `(project_id, name)` LAJ.

    A rotina é restrita às identidades recebidas no microciclo. Portanto um
    upsert parcial nunca toca outra laje do pavimento. Qualquer duplicata com
    selo/campo/vínculo humano permanece e é relatada como pendência, em vez de
    a automação decidir qual ground truth descartar.
    """
    canonical_items, _ = _canonical_laj_by_name(slabs)
    canonical = {
        name: str(item.get("id") or "")
        for name, item in canonical_items.items()
        if str(item.get("id") or "")
    }
    removed = 0
    protected = 0
    for name, canonical_id in canonical.items():
        rows = conn.execute(
            """
            SELECT id,is_validated,validated_fields_json,validated_link_classes_json
            FROM slabs WHERE project_id=? AND name=? ORDER BY id
            """,
            (project_id, name),
        ).fetchall()
        if len(rows) < 2:
            continue
        for row_id, is_validated, fields_json, links_json in rows:
            if str(row_id) == canonical_id:
                continue
            if _persisted_laj_row_has_human_validation(
                (is_validated, fields_json, links_json)
            ):
                protected += 1
                continue
            conn.execute("DELETE FROM slabs WHERE id=?", (row_id,))
            removed += 1
    return {"removidas": removed, "protegidas_humanas": protected}


def persist_analysis_snapshot(
    *,
    db_path: str,
    project_id: str,
    collections: dict[str, list[dict]],
    run_id: str,
    html_dir: str,
    source_dxf: str,
    merge_stats: dict,
    delete_missing: bool = True,
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

        # Em microciclo `delete_missing=False`, o DELETE global não ocorre.
        # Ainda assim, LAJ precisa manter a invariável de uma identidade por
        # rótulo dentro do projeto. A limpeza é estritamente local aos nomes
        # recebidos e nunca apaga uma validação humana.
        laj_identity_cleanup = _remove_unvalidated_laj_identity_duplicates(
            conn, project_id, collections["slabs"]
        )

        if delete_missing:
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
        after = {
            table: int(conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id=?",
                (project_id,),
            ).fetchone()[0])
            for table in ("pillars", "slabs", "beams")
        }
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
            "laj_identity_cleanup": laj_identity_cleanup,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
