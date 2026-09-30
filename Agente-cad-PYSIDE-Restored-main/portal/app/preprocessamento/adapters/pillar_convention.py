"""Extração conservadora da legenda geométrica de pilares em DXF.

Não traduz CROSS/DIAG/EMPTY para NASCE/SEGUE/MORRE. O próprio desenho fornece o
rótulo; assinaturas repetidas permanecem conflitos explícitos.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any


HEADER_KEYWORDS = ("CONVEN", "LEGENDA", "CONVENTION", "PILAR", "PILLAR", "SYMBOL")
HEADER_LABEL_RADIUS = 600.0
LABEL_LINE_RADIUS = 150.0
ORTHOGONAL_TOLERANCE = 8.0


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _line_center(line: dict[str, Any]) -> tuple[float, float]:
    return (
        (line["start"][0] + line["end"][0]) / 2.0,
        (line["start"][1] + line["end"][1]) / 2.0,
    )


def _line_angle(line: dict[str, Any]) -> float:
    dx = line["end"][0] - line["start"][0]
    dy = line["end"][1] - line["start"][1]
    return math.degrees(math.atan2(dy, dx)) % 180.0


def geometry_signature(lines: list[dict[str, Any]]) -> dict[str, Any]:
    diagonals = [
        line for line in lines
        if abs(_line_angle(line)) > ORTHOGONAL_TOLERANCE
        and abs(_line_angle(line) - 90.0) > ORTHOGONAL_TOLERANCE
        and abs(_line_angle(line) - 180.0) > ORTHOGONAL_TOLERANCE
    ]
    angles = [round(_line_angle(line)) for line in diagonals]
    cross = False
    parallel = False
    if len(diagonals) >= 2:
        unique = sorted(set(angles))
        cross = any(
            abs(unique[left] + unique[right] - 180) < 20
            for left in range(len(unique))
            for right in range(left + 1, len(unique))
        )
        parallel = not cross and max(angles) - min(angles) < 20
    signature = "CROSS" if cross else "DIAG" if parallel else "EMPTY" if not diagonals else f"DIAG_{len(diagonals)}"
    return {
        "signature": signature,
        "diagonal_count": len(diagonals),
        "diagonal_angles": angles,
        "cross_pattern": cross,
        "parallel_diagonal": parallel,
    }


def _is_label(text: str) -> bool:
    value = text.strip()
    if len(value) <= 1 or value.endswith(":") or value.endswith(")"):
        return False
    if re.fullmatch(r"[\d\s.,;:\-/()]+", value):
        return False
    if re.match(r"^\d+\)", value) or len(value.split()) > 3:
        return False
    return not any(keyword in value.upper() for keyword in HEADER_KEYWORDS)


def extract_pillar_convention(dxf_path: Path) -> dict[str, Any]:
    """Extrai rótulos e assinaturas sem lhes atribuir significado universal."""
    import ezdxf

    document = ezdxf.readfile(str(dxf_path))
    texts: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    for entity in document.modelspace():
        entity_type = entity.dxftype()
        if entity_type in {"TEXT", "MTEXT"}:
            try:
                value = entity.dxf.text if entity_type == "TEXT" else entity.plain_mtext()
                insertion = entity.dxf.insert
                texts.append({
                    "text": str(value).strip(),
                    "position": (float(insertion.x), float(insertion.y)),
                    "handle": str(entity.dxf.handle or ""),
                })
            except (AttributeError, TypeError, ValueError):
                continue
        elif entity_type == "LINE":
            try:
                start, end = entity.dxf.start, entity.dxf.end
                lines.append({
                    "start": (float(start.x), float(start.y)),
                    "end": (float(end.x), float(end.y)),
                    "handle": str(entity.dxf.handle or ""),
                })
            except (AttributeError, TypeError, ValueError):
                continue

    headers = [
        text for text in texts
        if any(keyword in text["text"].upper() for keyword in HEADER_KEYWORDS)
    ]
    if not headers:
        return {
            "status": "partial",
            "headers": [],
            "entries": [],
            "signature_index": {},
            "conflicts": [],
            "warnings": ["Cabeçalho de convenção não localizado."],
        }

    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, float, float]] = set()
    for header in headers:
        for candidate in texts:
            if not _is_label(candidate["text"]):
                continue
            if _distance(candidate["position"], header["position"]) >= HEADER_LABEL_RADIUS:
                continue
            key = (candidate["text"], *candidate["position"])
            if key in seen:
                continue
            seen.add(key)
            nearby = [
                line for line in lines
                if _distance(_line_center(line), candidate["position"]) < LABEL_LINE_RADIUS
            ]
            signature = geometry_signature(nearby)
            entries.append({
                "label": candidate["text"],
                "label_normalized": candidate["text"].strip().upper(),
                "label_position": list(candidate["position"]),
                "label_handle": candidate["handle"] or None,
                "line_handles": [line["handle"] for line in nearby if line["handle"]],
                "line_count": len(nearby),
                **signature,
            })

    index: dict[str, list[str]] = {}
    for entry in entries:
        index.setdefault(entry["signature"], []).append(entry["label"])
    conflicts = [
        {"signature": signature, "labels": labels}
        for signature, labels in sorted(index.items()) if len(set(labels)) > 1
    ]
    return {
        "status": "complete" if entries and not conflicts else "partial",
        "headers": headers,
        "entries": entries,
        "signature_index": index,
        "conflicts": conflicts,
        "warnings": [] if entries else ["Cabeçalho encontrado, mas nenhum rótulo elegível foi associado."],
    }
