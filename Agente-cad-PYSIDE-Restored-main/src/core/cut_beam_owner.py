"""Viga dona de um corte desenhado em planta, pela geometria do fundo.

O símbolo de corte (T) é desenhado sobre a viga cortada.  O rótulo de viga
mais próximo erra quando o rótulo de uma viga perpendicular fica mais perto
que o da viga cortada (V314 em vez de V302).  O fundo interpretado pelo SA
(``viga_fundo_seg_*_area_segs``) cobre a viga real, então a dona é a viga cujo
fundo cobre a maior parte do símbolo.  Sem fundo sob o símbolo, ou com dois
fundos de vigas diferentes cobrindo quase o mesmo, não há resposta: o
chamador mantém o critério do rótulo (restrito aos empatados, se houver).
"""
from __future__ import annotations

# Área mínima (unidades do DXF²) para contar como sobreposição; abaixo disso é
# só contato de borda entre o símbolo e o fundo vizinho.
MIN_OVERLAP_AREA = 1.0
# A maior sobreposição precisa vencer a segunda viga por esta razão.
DOMINANCE_RATIO = 1.5


def _polygon(points):
    from shapely.geometry import Polygon
    try:
        poly = Polygon([tuple(map(float, p[:2])) for p in points]).buffer(0)
    except (TypeError, ValueError, IndexError):
        return None
    return poly if poly.is_valid and not poly.is_empty and poly.area > 0 else None


def fundo_polygons(beams):
    """[(nome da viga, polígono do fundo)] de todos os segmentos de fundo."""
    result = []
    for beam in beams or []:
        if not isinstance(beam, dict) or not beam.get('name'):
            continue
        for key, slots in (beam.get('links') or {}).items():
            if not (isinstance(key, str) and key.startswith('viga_fundo_seg_')
                    and key.endswith('_area_segs') and isinstance(slots, dict)):
                continue
            for contour in slots.get('contour') or []:
                points = contour.get('points') if isinstance(contour, dict) else contour
                poly = _polygon(points or []) if points and len(points) >= 3 else None
                if poly is not None:
                    result.append((str(beam['name']), poly))
    return result


def owner_candidates(cut_points, fundos):
    """{viga: área do símbolo coberta pelo fundo dela}, só sobreposições reais."""
    cut = _polygon(cut_points or []) if cut_points and len(cut_points) >= 3 else None
    if cut is None:
        return {}
    areas = {}
    for name, poly in fundos:
        if poly.intersects(cut):
            area = poly.intersection(cut).area
            if area > MIN_OVERLAP_AREA:
                areas[name] = areas.get(name, 0.0) + area
    return areas


def owner_by_fundo(cut_points, fundos):
    """(viga dona ou None, vigas empatadas).  Empate = mais de uma candidata."""
    areas = owner_candidates(cut_points, fundos)
    ranked = sorted(areas.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return None, []
    if len(ranked) == 1 or ranked[0][1] >= DOMINANCE_RATIO * ranked[1][1]:
        return ranked[0][0], []
    return None, [name for name, _ in ranked]
