"""Inventário de pilares por recorte de torre, sem persistência SA."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Mapping

from src.core.analysis_helpers import detect_pilares_from_polylines

from .pillar_convention import geometry_signature


_PILLAR_NAME = re.compile(r"^P\d+[A-Z0-9_.-]*$", re.IGNORECASE)
_DIMENSION = re.compile(r"^\d+(?:[.,]\d+)?\s*[xX]\s*\d+(?:[.,]\d+)?$")


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _load_geometry(path: Path) -> tuple[list[dict], list[dict], list[dict]]:
    import ezdxf

    document = ezdxf.readfile(str(path))
    polylines: list[dict] = []
    texts: list[dict] = []
    lines: list[dict] = []
    for entity in document.modelspace():
        entity_type = entity.dxftype()
        try:
            if entity_type == "LWPOLYLINE":
                points = [(float(point[0]), float(point[1])) for point in entity.get_points("xy")]
                if entity.closed and points and points[0] != points[-1]:
                    points.append(points[0])
                polylines.append({"points": points, "handle": str(entity.dxf.handle or "")})
            elif entity_type == "POLYLINE":
                points = [(float(vertex.dxf.location.x), float(vertex.dxf.location.y)) for vertex in entity.vertices]
                if entity.is_closed and points and points[0] != points[-1]:
                    points.append(points[0])
                polylines.append({"points": points, "handle": str(entity.dxf.handle or "")})
            elif entity_type in {"TEXT", "MTEXT"}:
                value = entity.dxf.text if entity_type == "TEXT" else entity.plain_mtext()
                insertion = entity.dxf.insert
                texts.append({
                    "text": str(value).strip(),
                    "pos": (float(insertion.x), float(insertion.y)),
                    "handle": str(entity.dxf.handle or ""),
                })
            elif entity_type == "LINE":
                start, end = entity.dxf.start, entity.dxf.end
                lines.append({
                    "start": (float(start.x), float(start.y)),
                    "end": (float(end.x), float(end.y)),
                    "handle": str(entity.dxf.handle or ""),
                })
        except (AttributeError, TypeError, ValueError):
            continue
    return polylines, texts, lines


def _bbox(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _lines_inside(lines: list[dict], bounds: tuple[float, float, float, float]) -> list[dict]:
    x0, y0, x1, y1 = bounds
    margin = 2.0
    result = []
    for line in lines:
        center = (
            (line["start"][0] + line["end"][0]) / 2.0,
            (line["start"][1] + line["end"][1]) / 2.0,
        )
        if x0 - margin <= center[0] <= x1 + margin and y0 - margin <= center[1] <= y1 + margin:
            result.append(line)
    return result


def inventory_pillars(
    dxf_path: Path,
    *,
    source_id: str,
    convention: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Inventaria geometrias e rótulos; não grava no DB nem cria N1."""
    polylines, all_texts, lines = _load_geometry(dxf_path)
    relevant_texts = [
        text for text in all_texts
        if _PILLAR_NAME.fullmatch(text["text"]) or _DIMENSION.fullmatch(text["text"])
    ]
    detected = detect_pilares_from_polylines(
        polylines, relevant_texts, scope=source_id
    )
    signature_index = dict((convention or {}).get("signature_index") or {})
    used_label_handles: set[str] = set()
    items: list[dict[str, Any]] = []

    name_counts: dict[str, int] = {}
    for pillar in detected:
        name = str(pillar.get("name") or "").strip()
        name_counts[name] = name_counts.get(name, 0) + 1

    for pillar in detected:
        points = [(float(point[0]), float(point[1])) for point in pillar.get("points") or ()]
        bounds = _bbox(points)
        nearby_lines = _lines_inside(lines, bounds)
        signature = geometry_signature(nearby_lines)["signature"]
        labels = list(signature_index.get(signature) or ())
        classification = labels[0] if len(set(labels)) == 1 else None
        center = tuple(pillar.get("pos") or (0.0, 0.0))
        matching_labels = sorted(
            (
                text for text in relevant_texts
                if text["text"].strip().upper() == str(pillar.get("name") or "").strip().upper()
            ),
            key=lambda text: _distance(center, text["pos"]),
        )
        if matching_labels and matching_labels[0]["handle"]:
            used_label_handles.add(matching_labels[0]["handle"])
        warnings: list[str] = []
        if name_counts.get(str(pillar.get("name") or ""), 0) > 1:
            warnings.append("nome_duplicado_na_torre")
        if len(set(labels)) > 1:
            warnings.append("assinatura_com_multiplas_classes")
        items.append({
            "item_id": str(pillar["id"]),
            "display_name": pillar.get("name"),
            "status": "ambiguous" if warnings else "linked",
            "geometry": {"type": "Polygon", "coordinates": [points]},
            "coordinate_system": "dxf:modelspace",
            "source_entity_handles": [
                polyline["handle"] for polyline in polylines
                if polyline.get("points") == pillar.get("points") and polyline.get("handle")
            ],
            "dimension_raw": pillar.get("dim") or None,
            "hatch_signature": signature,
            "classification_raw": classification,
            "classification_alternatives": labels,
            "warnings": warnings,
        })

    for text in relevant_texts:
        if not _PILLAR_NAME.fullmatch(text["text"]) or text["handle"] in used_label_handles:
            continue
        items.append({
            "item_id": f"pending:{source_id}:{text['handle'] or text['text']}",
            "display_name": text["text"],
            "status": "geometry_missing",
            "geometry": None,
            "coordinate_system": "dxf:modelspace",
            "source_entity_handles": [text["handle"]] if text["handle"] else [],
            "dimension_raw": None,
            "hatch_signature": None,
            "classification_raw": None,
            "classification_alternatives": [],
            "warnings": ["rotulo_sem_geometria_associada"],
        })

    return {
        "status": "complete" if items and all(item["status"] == "linked" for item in items) else "partial",
        "source_id": source_id,
        "items": items,
        "counts": {
            "total": len(items),
            "linked": sum(item["status"] == "linked" for item in items),
            "pending": sum(item["status"] != "linked" for item in items),
        },
    }
