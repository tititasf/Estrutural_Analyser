"""Fallbacks de convenção com evidência local, sem significado fixo por símbolo."""
from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

from shapely.geometry import LineString, Polygon


def convention_for_source(source_path):
    """Usa somente o recorte único de convenção vizinho da torre selecionada."""
    if not source_path:
        return {}
    paths = list(Path(source_path).parent.glob('convencao_pilares*.dxf'))
    if len(paths) != 1:
        return {}
    from portal.app.preprocessamento.adapters.pillar_convention import extract_pillar_convention
    try:
        extracted = extract_pillar_convention(paths[0])
    except (OSError, ValueError):
        return {}
    if extracted.get('conflicts'):
        return {}
    return {e['label']: {'label': e['label'], 'sig': e['signature']}
            for e in extracted.get('entries', []) if e.get('line_count', 0) >= 4}


def recognize(points, data, convention):
    """Retorna (termo, evidência); ambiguidades nunca escolhem o primeiro termo.

    1. Traços inteiros no interior do polígono real.
    2. Família de traços recortados, paralelos e regularmente espaçados.
    3. Símbolo vazio com contorno fechado confirmado no DXF.
    """
    unknown = 'INDETERMINADO'
    labels = defaultdict(set)
    for key, entry in (convention or {}).items():
        if isinstance(entry, dict) and entry.get('sig'):
            labels[entry['sig']].add(entry.get('label') or key)
    def result(sig, path, count):
        values = labels.get(sig, set())
        if len(values) == 1:
            return next(iter(values)), {'path': path, 'signature': sig, 'strokes': count}
        return unknown, {'path': path, 'reason': 'missing_or_conflicting_legend', 'signature': sig}
    try:
        poly = Polygon(points)
        if not poly.is_valid or poly.area <= 0:
            return unknown, {'reason': 'invalid_polygon'}
    except (ValueError, TypeError):
        return unknown, {'reason': 'invalid_polygon'}
    short = min(poly.minimum_rotated_rectangle.length / 4, math.sqrt(poly.area))
    tolerance = max(1e-5, short * 1e-5)
    full, clipped, partial = [], [], []
    for line in data.get('lines', []):
        try:
            stroke = LineString([line['start'][:2], line['end'][:2]])
            if stroke.length <= tolerance:
                continue
            interior = stroke.intersection(poly.buffer(-tolerance))
            if interior.length <= tolerance:
                continue
            angle = math.degrees(math.atan2(line['end'][1]-line['start'][1],
                                           line['end'][0]-line['start'][0])) % 180
            if min(angle, abs(angle-90), 180-angle) <= 8:
                continue
            record = (stroke, angle, line.get('layer', ''), interior)
            if poly.buffer(tolerance).covers(stroke):
                full.append(record)
            if interior.length / stroke.length >= .8:
                clipped.append(record)
            elif not poly.buffer(tolerance).covers(stroke):
                partial.append(record)
        except (KeyError, TypeError, ValueError):
            continue
    def signature(records):
        if len(records) < 2:
            return None
        angles = [r[1] for r in records]
        # Two intersecting, nonparallel complete strokes form the cross.
        if len(records) == 2:
            difference = abs(angles[0]-angles[1])
            if min(difference, 180-difference) > 12 and records[0][0].crosses(records[1][0]):
                return 'CROSS'
        spread = max(angles)-min(angles)
        if spread < 8:
            return 'DIAG'
        return None
    sig = signature(full)
    if sig:
        return result(sig, 'polygon_complete_strokes', len(full))
    # A dominant fill must be a regular family, not a lone leader/cota.
    families = defaultdict(list)
    for record in clipped:
        families[record[2]].append(record)
    candidates = []
    for records in families.values():
        if len(records) < 3 or signature(records) != 'DIAG':
            continue
        angle = math.radians(records[0][1])
        offsets = sorted(set(round(-math.sin(angle)*r[0].centroid.x +
                                   math.cos(angle)*r[0].centroid.y, 4) for r in records))
        gaps = [b-a for a,b in zip(offsets, offsets[1:])]
        if len(gaps) < 2 or min(gaps) <= tolerance or max(gaps)/min(gaps) > 1.25:
            continue
        total = sum(r[3].length for r in clipped)
        if sum(r[3].length for r in records) >= .9 * total:
            candidates.append(records)
    if len(candidates) == 1:
        return result('DIAG', 'regular_clipped_fill', len(candidates[0]))
    # Absence alone is insufficient: the source must contain this closed outline.
    if not full and not clipped:
        outlines = []
        for outline in data.get('polylines', []):
            pts = outline.get('points') or []
            if len(pts) < 4 or not (outline.get('closed') or pts[0][:2] == pts[-1][:2]):
                continue
            try:
                other = Polygon(pts)
                if other.is_valid:
                    outlines.append(other)
            except (TypeError, ValueError):
                continue
        exact = [o for o in outlines if poly.boundary.hausdorff_distance(o.boundary) <= tolerance]
        # Long strokes crossing the target may belong to a neighboring symbol.
        # Without that source outline, absence of local fill remains ambiguous.
        unexplained = [r for r in partial if not any(
            o.boundary.hausdorff_distance(poly.boundary) > tolerance
            and o.buffer(tolerance).covers(r[0]) for o in outlines)]
        def dimension_tick(record):
            stroke = record[0]
            center = stroke.interpolate(.5, normalized=True)
            if poly.boundary.distance(center) > tolerance:
                return False
            # Slash centered on an outline, crossing a long dimension line.
            # Fill/cross symbols have their centers inside their own contours.
            directions = set()
            for source in data.get('lines', []):
                try:
                    axis = LineString([source['start'][:2], source['end'][:2]])
                    dx = source['end'][0]-source['start'][0]
                    dy = source['end'][1]-source['start'][1]
                    if min(abs(dx), abs(dy)) <= tolerance and axis.length >= 1.5*stroke.length \
                            and axis.distance(center) <= tolerance:
                        directions.add('horizontal' if abs(dx) > abs(dy) else 'vertical')
                except (KeyError, TypeError, ValueError):
                    continue
            return len(directions) == 2
        unexplained = [r for r in unexplained if not dimension_tick(r)]
        if exact and not unexplained:
            return result('EMPTY', 'confirmed_empty_outline', 0)
    return unknown, {'reason': 'insufficient_or_mixed_evidence', 'complete_strokes': len(full)}
