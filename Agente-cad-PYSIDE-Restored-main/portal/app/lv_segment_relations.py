"""Posições físicas de pilares na lateral publicada, em ordem de leitura.

Não usa bbox como contato nem altera a segmentação/curadoria do SA.
"""
from __future__ import annotations

import math
from shapely.geometry import LineString
from src.core.pillar_special_faces import physical_ring, special_l_face_segments

ALLOWED_FACES = frozenset("ABEFGH")


def _faces(pillar: dict) -> dict:
    ring = physical_ring(pillar.get("points"))
    special = special_l_face_segments(ring)
    if special:
        return special
    if len(ring) != 4:
        # Faces especiais explicitamente materializadas, quando disponíveis.
        return {fid: value for fid, value in (pillar.get("face_segments") or {}).items()
                if isinstance(value, dict) and value.get("p0") and value.get("p1")}
    edges = [{"p0": p, "p1": ring[(i + 1) % 4]} for i, p in enumerate(ring)]
    vertical = [e for e in edges if abs(e["p1"][1] - e["p0"][1]) > abs(e["p1"][0] - e["p0"][0])]
    horizontal = [e for e in edges if e not in vertical]
    if len(vertical) != 2 or len(horizontal) != 2:
        # Retângulo rotacionado: as faces longas são A/B.
        edges.sort(key=lambda e: math.dist(e["p0"], e["p1"]), reverse=True)
        return dict(zip("ABCD", edges))
    vertical.sort(key=lambda e: sum(p[0] for p in (e["p0"], e["p1"])))
    horizontal.sort(key=lambda e: sum(p[1] for p in (e["p0"], e["p1"])))
    width = math.dist(horizontal[0]["p0"], horizontal[0]["p1"])
    height = math.dist(vertical[0]["p0"], vertical[0]["p1"])
    is_vertical = height >= width
    if abs(height - width) < 0.05:
        is_vertical = "HORIZONTAL" not in str(pillar.get("orientation") or "").upper()
    return dict(zip("ABCD", vertical + horizontal[::-1] if is_vertical else horizontal + vertical))


def pillar_passages(points: list, pillars: list[dict], behavior: str) -> list[dict]:
    if behavior != "passa" or len(points) < 2:
        return []
    line = LineString(points)
    length = line.length
    if length <= 0.5:
        return []
    start, end = points[0], points[-1]
    ux, uy = (end[0] - start[0]) / length, (end[1] - start[1]) / length
    result = []
    for pillar in pillars:
        if pillar.get("ignore_in_beams") or str(pillar.get("classification") or "").upper() == "NASCE":
            continue
        for face, edge in _faces(pillar).items():
            if face not in ALLOWED_FACES:
                continue
            a, b = edge["p0"], edge["p1"]
            edge_len = math.dist(a, b)
            if edge_len <= 0.5:
                continue
            if abs(ux * (b[1] - a[1]) - uy * (b[0] - a[0])) / edge_len > 0.01:
                continue
            # Somente a parede colinear; proximidade/perpendicular não é passagem.
            offsets = [abs(ux * (p[1] - start[1]) - uy * (p[0] - start[0])) for p in (a, b)]
            if max(offsets) > 0.6:
                continue
            positions = sorted(ux * (p[0] - start[0]) + uy * (p[1] - start[1]) for p in (a, b))
            lo, hi = max(0.0, positions[0]), min(length, positions[1])
            if hi - lo <= 0.5:
                continue
            result.append({"name": pillar.get("name") or pillar.get("key"), "face": face,
                           "distance_left_cm": round(lo, 2), "length_cm": round(hi - lo, 2),
                           "distance_right_cm": round(length - hi, 2)})
    return sorted(result, key=lambda value: (value["distance_left_cm"], value["name"], value["face"]))
