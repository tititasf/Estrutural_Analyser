"""Levantamento pré-SA de cotas por torre, sem criar resultados estruturais.

Um texto de cota é ligado a uma laje apenas se sua posição separa nitidamente
esse rótulo dos demais. Pilares, vigas e segmentos recebem alternativas
espaciais, nunca nível preenchido por proximidade. O bruto correspondente
fornece unidade/referência de pavimento sem depender de recorte aprovado.
"""
from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path
from statistics import median

from .level_convention import extract_level_convention
from .levels import item_levels


_LEVEL_TEXT = re.compile(r"^(?:N\s*[:=]\s*)?([+-]?\d+[.,]\d{1,2})$", re.I)
_FLOOR_NUM = re.compile(r"^(\d+)_PAV$", re.I)
_FLOOR_LABEL = re.compile(r"^\s*(\d+)\s*[º°oa]?\s*PAV\.\s*$", re.I)


def _texts(path: Path) -> list[dict]:
    import ezdxf

    result = []
    for entity in ezdxf.readfile(str(path)).modelspace():
        kind = entity.dxftype()
        if kind not in {"TEXT", "MTEXT"}:
            continue
        try:
            raw = entity.dxf.text if kind == "TEXT" else entity.plain_mtext()
            pos = entity.dxf.insert
            result.append({"raw": str(raw).strip(), "position": [float(pos.x), float(pos.y)],
                           "handle": str(entity.dxf.handle or ""), "layer": str(entity.dxf.layer)})
        except (AttributeError, TypeError, ValueError):
            continue
    return result


def _floor_reference(path: Path | None, floor: str, source_id: str | None,
                     anchors: list[float] | None = None) -> dict:
    result = {"status": "missing", "source_id": source_id, "unit": None,
              "base": None, "top": None, "height": None, "datum_id": None,
              "evidence_handles": [], "warnings": []}
    if path is None:
        return result
    extracted = extract_level_convention(path)
    result["unit"] = extracted.get("unit")
    match = _FLOOR_NUM.fullmatch(floor)
    if not match:
        result["status"] = "unsupported_floor_name"
        return result
    number = int(match.group(1))
    by_floor: dict[int, list[dict]] = defaultdict(list)
    for row in extracted.get("direct_floor_levels", []):
        label = _FLOOR_LABEL.fullmatch(row["floor_label"])
        if label and row["status"] == "direct" and row.get("selected"):
            by_floor[int(label.group(1))].append(row["selected"])
    tops = by_floor.get(number, [])
    bases = by_floor.get(number - 1, [])
    pairs = [(base, top) for base in bases for top in tops
             if 0 < top["value"] - base["value"] <= 6]
    distinct = {(base["value"], top["value"]) for base, top in pairs}
    selected_pair = None
    if len(distinct) == 1:
        selected_pair = pairs[0]
    elif pairs and anchors:
        # Cotas absolutas podem ser zero ou negativas. A coluna que coincide
        # com marcas da própria torre decide entre tabela de alturas e cotas.
        ranked = sorted(((min(abs(top["value"] - value) for value in anchors), base, top)
                         for base, top in pairs), key=lambda row: row[0])
        best = ranked[0][0]
        winners = [pair for distance, *pair in ranked if abs(distance - best) < 1e-6]
        if best <= 6 and len({(b["value"], t["value"]) for b, t in winners}) == 1:
            selected_pair = tuple(winners[0])
    if selected_pair:
        base, top = selected_pair
        result["base"], result["top"] = base["value"], top["value"]
        result["evidence_handles"] = [row["text_handle"] for row in selected_pair
                                      if row.get("text_handle")]
    elif pairs:
        result["warnings"].append("ambiguous_floor_elevation_pair")
    base, top = result["base"], result["top"]
    if result["unit"] == "m" and base is not None and top is not None and 0 < top - base <= 6:
        result["height"] = round(top - base, 4)
        result["datum_id"] = f"source-local:{source_id}"
        result["status"] = "direct_local_reference"
    else:
        result["status"] = "partial"
        if result["unit"] is None:
            result["warnings"].append("level_unit_unproven")
        if base is None or top is None:
            result["warnings"].append("adjacent_floor_levels_unproven")
    return result


def _label_spacing(slabs: list[dict]) -> float | None:
    if len(slabs) < 2:
        return None
    distances = []
    for item in slabs:
        pos = item["label_position"]
        distances.append(min(math.dist(pos, other["label_position"])
                             for other in slabs if other is not item))
    return median(distances)


def _beam_segments(path: Path, beams: list[dict]) -> dict[str, list[dict]]:
    """Segmentos candidatos do tracer existente; não são vínculo validado."""
    if not beams:
        return {}
    from src.core.beam_tracer import BeamTracer
    from src.core.dxf_loader import DXFLoader
    from src.core.spatial_index import SpatialIndex

    data = DXFLoader.load_dxf(str(path))
    if not data:
        return {}
    index = SpatialIndex()
    polylines = data.get("polylines", [])
    lines = data.get("lines", [])
    texts = data.get("texts", [])
    for entity in polylines + lines:
        points = entity.get("points") or ([entity["start"], entity["end"]]
                                           if "start" in entity and "end" in entity else [])
        if points:
            index.insert(entity, (min(p[0] for p in points), min(p[1] for p in points),
                                  max(p[0] for p in points), max(p[1] for p in points)))
    for entity in texts:
        point = entity.get("pos")
        if point:
            index.insert(entity, (point[0]-5, point[1]-5, point[0]+5, point[1]+5))
    geometry = [entity if "points" in entity else
                {"points": [entity["start"], entity["end"]]}
                for entity in lines + polylines if "points" in entity or
                ("start" in entity and "end" in entity)]
    traced = BeamTracer(index).detect_beams(texts, geometry, visual_obstacles=[])
    by_name: dict[str, list[dict]] = defaultdict(list)
    for beam in traced:
        by_name[str(beam.get("name") or "").upper()].append(beam)
    result = {}
    for item in beams:
        candidates = by_name.get(item["display_name"], [])
        if len(candidates) != 1:
            result[item["item_id"]] = []
            continue
        beam = candidates[0]
        intervals = (beam.get("geometry") or {}).get("classified", {}).get("merged_bottom_groups_coords") or []
        result[item["item_id"]] = [
            {"segment_id": f"{item['item_id']}:bottom:{i}", "beam_item_id": item["item_id"],
             "part": "bottom", "axis_interval": [float(interval[0]), float(interval[1])],
             "orientation": "horizontal" if beam.get("fv_is_h", beam.get("is_h")) else "vertical",
             "transverse_coordinate": float(beam["pos"][1] if beam.get("fv_is_h", beam.get("is_h"))
                                             else beam["pos"][0]),
             "status": "candidate_unverified", "level": None, "unit": None,
             "source_method": "BeamTracer.merged_bottom_groups_coords",
             "warnings": ["segment_topology_requires_sa_validation"]}
            for i, interval in enumerate(intervals, 1)
            if len(interval) == 2 and float(interval[0]) < float(interval[1])
        ]
    return result


def survey_levels(tower_path: Path, *, source_id: str, floor: str,
                  pillars: list[dict], labels: list[dict],
                  raw_reference: dict | None = None, obra_dir: Path | None = None) -> tuple[list[dict], dict]:
    """Lista todas as classes e cruza evidências sem promover hipóteses ao SA."""
    reference_path = (Path(obra_dir) / raw_reference["relative_path"]
                      if raw_reference and obra_dir else None)
    texts = _texts(tower_path)
    slabs = [item for item in labels if item["item_class"] == "slab"]
    spacing = _label_spacing(slabs)
    anchors = [float(match.group(1).replace(",", "."))
               for text in texts if (match := _LEVEL_TEXT.fullmatch(text["raw"]))
               and spacing is not None
               and any(math.dist(text["position"], slab["label_position"]) <= spacing * 0.45
                       for slab in slabs)]
    try:
        reference = _floor_reference(reference_path, floor,
                                     raw_reference["source_id"] if raw_reference else None, anchors)
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        reference = {"status": "unreadable", "source_id": raw_reference["source_id"] if raw_reference else None,
                     "unit": None, "base": None, "top": None, "height": None,
                     "datum_id": None, "evidence_handles": [],
                     "warnings": [f"raw_level_reference_unreadable:{type(exc).__name__}"]}
    if raw_reference and raw_reference.get("validated") is False and reference["status"] == "direct_local_reference":
        reference["status"] = "provisional_unvalidated_crop"
        reference["warnings"].append("level_crop_not_validated")
    annotations = []
    for text in texts:
        match = _LEVEL_TEXT.fullmatch(text["raw"])
        if match:
            value = float(match.group(1).replace(",", "."))
            if reference["top"] is None or abs(value - reference["top"]) <= 6:
                annotations.append({**text, "value": value, "source_id": source_id})
    # Sem referência de pavimento, o agrupamento modal separa cotas recorrentes
    # de dimensões isoladas. Uma marca isolada não sustenta preenchimento.
    if reference["top"] is None and annotations:
        groups = {tuple(sorted(other["handle"] for other in annotations
                               if abs(other["value"] - mark["value"]) <= 5))
                  for mark in annotations}
        peak = max(map(len, groups))
        winners = [group for group in groups if len(group) == peak]
        annotations = [mark for mark in annotations if mark["handle"] in winners[0]] \
            if peak >= 2 and len(winners) == 1 else []
    beams = [item for item in labels if item["item_class"] == "beam"]
    assigned: dict[str, list[dict]] = defaultdict(list)
    unlinked = []
    for mark in annotations:
        nearby = sorted(((math.dist(mark["position"], item["label_position"]), item)
                         for item in slabs), key=lambda pair: (pair[0], pair[1]["item_id"]))
        if not nearby or spacing is None or nearby[0][0] > spacing * 0.45 or (
                len(nearby) > 1 and nearby[1][0] < nearby[0][0] * 1.7):
            unlinked.append(mark)
            continue
        assigned[nearby[0][1]["item_id"]].append(mark)

    facts = item_levels(pillars, labels)
    fact_by_id = {fact["fact_id"]: fact for fact in facts}
    for slab in slabs:
        marks = assigned.get(slab["item_id"], [])
        if not marks:
            continue
        fact = fact_by_id[f"{slab['item_id']}:slab_level"]
        values = {mark["value"] for mark in marks}
        fact["evidence_ids"] = [f"{source_id}:text:{mark['handle']}" for mark in marks]
        fact["raw_values"] = sorted(values)
        if len(values) == 1 and reference["status"] == "direct_local_reference":
            fact.update(value=next(iter(values)), unit="m", datum_id=reference["datum_id"],
                        status="observed_text", method="near_unique_slab_label",
                        warnings=["spatial_label_link_requires_review"])
        elif len(values) > 1:
            fact.update(status="conflict", warnings=["divergent_level_marks_near_item"])
        else:
            fact.update(status="raw_unreferenced", warnings=["unit_or_datum_unproven"])

    # Cruzamento consultivo: cotas de lajes próximas ajudam a revisar pilares
    # e vigas, mas proximidade não prova apoio, face nem nível de segmento.
    observed = [(item, fact_by_id[f"{item['item_id']}:slab_level"])
                for item in slabs if fact_by_id[f"{item['item_id']}:slab_level"]["status"] == "observed_text"]
    for item in pillars + beams:
        pos = item.get("label_position")
        if pos is None:
            polygons = (item.get("geometry") or {}).get("coordinates") or []
            points = polygons[0] if polygons else []
            points = [point for point in points if len(point) >= 2]
            if points:
                pos = [sum(point[0] for point in points)/len(points),
                       sum(point[1] for point in points)/len(points)]
        if not pos or spacing is None:
            continue
        alternatives = [
            {"slab_item_id": slab["item_id"], "slab_display_name": slab["display_name"], "value": fact["value"],
             "unit": fact["unit"], "datum_id": fact["datum_id"]}
            for slab, fact in observed
            if math.dist(pos, slab["label_position"]) <= spacing * 0.8
        ]
        for fact in facts:
            if fact["item_id"] == item["item_id"]:
                fact["adjacent_slab_candidates"] = alternatives

    segment_warning = None
    try:
        segments = _beam_segments(tower_path, beams)
    except (OSError, ValueError, TypeError, RuntimeError, IndexError, KeyError) as exc:
        segments = {}
        segment_warning = f"beam_segment_survey_unavailable:{type(exc).__name__}"
    if spacing is not None:
        for group in segments.values():
            for segment in group:
                horizontal = segment["orientation"] == "horizontal"
                axis = 0 if horizontal else 1
                transverse = 1 - axis
                low, high = segment["axis_interval"]
                segment["adjacent_slab_candidates"] = [
                    {"slab_item_id": slab["item_id"], "slab_display_name": slab["display_name"], "value": fact["value"],
                     "unit": fact["unit"], "datum_id": fact["datum_id"]}
                    for slab, fact in observed
                    if low - spacing * 0.2 <= slab["label_position"][axis] <= high + spacing * 0.2
                    and abs(slab["label_position"][transverse] -
                            segment["transverse_coordinate"]) <= spacing * 0.8
                ]
    inventory = {
        "status": "partial", "reference": reference,
        "items": [{"item_id": item["item_id"], "item_class":
                   "pillar" if item in pillars else item["item_class"],
                   "display_name": item["display_name"],
                   "level_fact_ids": [fact["fact_id"] for fact in facts if fact["item_id"] == item["item_id"]],
                   "segment_ids": [segment["segment_id"] for segment in segments.get(item["item_id"], [])]}
                  for item in pillars + labels],
        "beam_segments": [segment for group in segments.values() for segment in group],
        "warnings": [segment_warning] if segment_warning else [],
        "segment_coverage": {"beam_labels": len(beams),
                             "beams_with_candidates": sum(bool(group) for group in segments.values()),
                             "candidate_segments": sum(len(group) for group in segments.values()),
                             "verified_segments": 0},
        "level_annotations": annotations, "unlinked_annotations": unlinked,
        "coverage": {"pillars": len(pillars), "slabs": len(slabs), "beams": len(beams),
                     "slab_levels_observed": sum(f["status"] == "observed_text" for f in facts),
                     "conflicts": sum(f["status"] == "conflict" for f in facts)},
    }
    return facts, inventory
