"""Inventário consultivo de rótulos de lajes/vigas por recorte de torre.

O rótulo TEXT/MTEXT é evidência direta; contorno ou vínculo geométrico não é
inferido daqui. O tracer SA exige validação própria antes de ser reutilizado,
pois seu fallback pode fabricar caixas provisórias sem origem no DXF.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_SLAB = re.compile(r"^L[A-Z]*[-_]?\d+[A-Z0-9_]*$", re.IGNORECASE)
_BEAM = re.compile(r"^(?:V|VF|CONT)[A-Z]*[-_]?\d+[A-Z0-9_.-]*$", re.IGNORECASE)


def inventory_labels(dxf_path: Path, *, source_id: str) -> dict[str, Any]:
    import ezdxf

    document = ezdxf.readfile(str(dxf_path))
    polygons = []
    for entity in document.modelspace():
        if entity.dxftype() == 'LWPOLYLINE' and entity.closed:
            points = [(float(x), float(y)) for x, y in entity.get_points('xy')]
        elif entity.dxftype() == 'POLYLINE' and entity.is_closed:
            points = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
        else:
            continue
        if len(points) >= 3 and entity.dxf.handle:
            polygons.append({'points': points, 'handle': entity.dxf.handle})

    def contains(points, point):
        x, y = point
        inside = False
        for a, b in zip(points, points[1:] + points[:1]):
            if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0]) * (y-a[1]) / (b[1]-a[1]) + a[0]:
                inside = not inside
        return inside
    labels: list[dict[str, Any]] = []
    for entity in document.modelspace():
        kind = entity.dxftype()
        if kind not in {"TEXT", "MTEXT"}:
            continue
        try:
            raw = entity.dxf.text if kind == "TEXT" else entity.plain_mtext()
            name = str(raw).strip().upper()
            item_class = "slab" if _SLAB.fullmatch(name) else "beam" if _BEAM.fullmatch(name) else None
            if item_class is None:
                continue
            insertion = entity.dxf.insert
            labels.append({
                "item_class": item_class,
                "name": name,
                "raw_text": str(raw),
                "position": [float(insertion.x), float(insertion.y)],
                "handle": str(entity.dxf.handle or ""),
            })
        except (AttributeError, TypeError, ValueError):
            continue

    counts: dict[tuple[str, str], int] = {}
    for label in labels:
        key = (label["item_class"], label["name"])
        counts[key] = counts.get(key, 0) + 1

    items: list[dict[str, Any]] = []
    for index, label in enumerate(labels):
        duplicate = counts[(label["item_class"], label["name"])] > 1
        containing = [poly for poly in polygons if contains(poly['points'], label['position'])]
        # Múltiplos contornos aninhados são comuns: sem um vínculo explícito,
        # não escolher o menor por aparência.
        geometry = (
            {'type': 'Polygon', 'coordinates': [containing[0]['points']]}
            if len(containing) == 1 else None
        )
        handle_list = ([label['handle']] if label['handle'] else []) + (
            [containing[0]['handle']] if geometry else [])
        items.append({
            "item_id": f"{source_id}:{label['item_class']}:{label['handle'] or index}",
            "item_class": label["item_class"],
            "display_name": label["name"],
            "raw_text": label["raw_text"],
            "label_position": label["position"],
            "source_entity_handles": handle_list,
            "geometry": geometry,
            "coordinate_system": "dxf:modelspace",
            "status": "ambiguous_name" if duplicate else "linked" if geometry else "label_only",
            "warnings": ["nome_duplicado_na_torre"] if duplicate else [] if geometry else
                        ["multiplos_contornos_candidatos" if containing else "geometria_nao_vinculada"],
        })

    return {
        "source_id": source_id,
        "status": "complete" if items and all(item['status'] == 'linked' for item in items) else "partial",
        "items": items,
        "counts": {
            "slabs": sum(item["item_class"] == "slab" for item in items),
            "beams": sum(item["item_class"] == "beam" for item in items),
            "ambiguous": sum(item["status"] == "ambiguous_name" for item in items),
        },
        "warnings": [] if items and all(item['status'] == 'linked' for item in items)
                    else ["geometria_parcial_ou_ambigua"],
    }
