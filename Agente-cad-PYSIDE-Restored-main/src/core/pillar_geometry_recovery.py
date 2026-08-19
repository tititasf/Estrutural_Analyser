"""Recuperacao conservadora de contornos de pilares truncados no DXF."""
from __future__ import annotations

from typing import Any

from src.core.pillar_geometry_fix import _bbox


def repair_truncated_named_pillars_from_dxf(
    pillar_report: dict[str, dict], *, polylines: list[dict], texts: list[dict]
) -> list[dict[str, Any]]:
    """Troca apenas um trecho curto por um retangulo completo homonimo do DXF.

    A regra nao busca por raio, nem recorre a GOLDEN: a alternativa precisa ter
    o mesmo nome e conter exatamente os quatro cantos do seu bounding box.
    """
    try:
        from src.core.analysis_helpers import detect_pilares_from_polylines

        detected = detect_pilares_from_polylines(polylines or [], texts or [])
    except Exception:
        return []

    def dims(points: list) -> tuple[float, float, tuple[float, float, float, float]] | None:
        bb = _bbox(points)
        if not bb:
            return None
        width, height = abs(bb[2] - bb[0]), abs(bb[3] - bb[1])
        if width <= 0 or height <= 0:
            return None
        return min(width, height), max(width, height), bb

    def is_complete_rectangle(points: list) -> bool:
        bb = _bbox(points)
        if not bb:
            return False
        vertices = {(round(float(x), 2), round(float(y), 2)) for x, y in points}
        x0, y0, x1, y1 = (round(value, 2) for value in bb)
        return vertices == {(x0, y0), (x0, y1), (x1, y0), (x1, y1)}

    candidates_by_name: dict[str, list[dict]] = {}
    for candidate in detected:
        name = str(candidate.get("name") or (candidate.get("fields") or {}).get("nome") or "").strip().upper()
        if name:
            candidates_by_name.setdefault(name, []).append(candidate)

    repaired: list[dict[str, Any]] = []
    for key, pillar in pillar_report.items():
        name = str(pillar.get("name") or key or "").strip().upper()
        current = dims(pillar.get("points") or [])
        if not name or not current:
            continue
        short, long, old_bbox = current
        if short < 8.0 or short > 40.0 or long >= 45.0:
            continue
        choices = []
        for candidate in candidates_by_name.get(name, []):
            points = candidate.get("points") or []
            candidate_dims = dims(points)
            if not candidate_dims or not is_complete_rectangle(points):
                continue
            candidate_short, candidate_long, candidate_bbox = candidate_dims
            if abs(candidate_short - short) > max(2.0, short * 0.12):
                continue
            if candidate_long < max(45.0, long * 1.8):
                continue
            choices.append((candidate_long, points, candidate_short, candidate_bbox))
        if not choices:
            continue
        new_long, points, new_short, new_bbox = min(choices, key=lambda choice: choice[0])
        pillar["points"] = [[float(x), float(y)] for x, y in points]
        pillar["bbox"] = new_bbox
        pillar["_geometry_repaired"] = {
            "from": {"short": round(short, 2), "long": round(long, 2), "bbox": old_bbox},
            "to": {"short": round(new_short, 2), "long": round(new_long, 2), "bbox": new_bbox},
            "source": "DXF: retangulo homonimo completo (contorno truncado por pilar nasce)",
        }
        repaired.append({"item": name, **pillar["_geometry_repaired"]})
    return repaired
