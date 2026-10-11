"""Retângulos que são células do corredor de uma viga em planta, não corte.

No encontro de duas vigas o desenhista às vezes fecha retângulos sobre a
própria planta (o miolo do V302×V316 no 13_PAV).  Unidos, eles formam um T
igual ao símbolo de corte.  A diferença é medida no desenho: um lado de uma
célula de corredor é um trecho de parede de viga, então a linha dele continua
além do retângulo; o símbolo de corte é desenhado solto sobre a laje.  Uma
peça é célula quando os dois lados opostos (paralelos ao eixo do corredor)
seguem colineares para fora dela.
"""
from __future__ import annotations

# Colinearidade (unidades do DXF): mesma folga de coordenada das peças.
COLLINEAR_TOL = 0.05
# A parede precisa seguir pelo menos isto além da peça para não ser ruído.
MIN_CONTINUATION = 5.0


def plan_segments(dxf_data):
    """Segmentos ortogonais de linhas e polilinhas da planta: (eixo, c, a, b)."""
    result = []
    items = list(dxf_data.get('lines') or []) + list(dxf_data.get('polylines') or [])
    for item in items:
        pts = item.get('points') or []
        if not pts and item.get('start') is not None and item.get('end') is not None:
            pts = [item['start'], item['end']]
        for p, q in zip(pts, pts[1:]):
            try:
                (x0, y0), (x1, y1) = (float(p[0]), float(p[1])), (float(q[0]), float(q[1]))
            except (TypeError, ValueError, IndexError):
                continue
            if abs(y0 - y1) <= COLLINEAR_TOL and abs(x0 - x1) > COLLINEAR_TOL:
                result.append(('h', (y0 + y1) / 2, min(x0, x1), max(x0, x1)))
            elif abs(x0 - x1) <= COLLINEAR_TOL and abs(y0 - y1) > COLLINEAR_TOL:
                result.append(('v', (x0 + x1) / 2, min(y0, y1), max(y0, y1)))
    return result


def _continues(segments, axis, coord, lo, hi):
    """A linha (axis, coord) toca [lo, hi] e segue além dele?

    A parede pode atravessar o lado ou parar exatamente nele (desenhada em
    trechos que terminam no encontro); nos dois casos ela continua para fora.
    """
    for seg_axis, c, a, b in segments:
        if seg_axis != axis or abs(c - coord) > COLLINEAR_TOL:
            continue
        touches = a <= hi + COLLINEAR_TOL and b >= lo - COLLINEAR_TOL
        if touches and (a < lo - MIN_CONTINUATION or b > hi + MIN_CONTINUATION):
            return True
    return False


def is_corridor_cell(piece_points, segments):
    """Retângulo ortogonal cujos dois lados opostos são trechos de parede."""
    try:
        xs = [float(p[0]) for p in piece_points]
        ys = [float(p[1]) for p in piece_points]
    except (TypeError, ValueError, IndexError):
        return False
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    walls_h = _continues(segments, 'h', y0, x0, x1) and _continues(segments, 'h', y1, x0, x1)
    walls_v = _continues(segments, 'v', x0, y0, y1) and _continues(segments, 'v', x1, y0, y1)
    return walls_h or walls_v


def corridor_cell_pieces(piece_keys, segments):
    return [is_corridor_cell(key, segments) for key in piece_keys]
