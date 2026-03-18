#!/usr/bin/env python3
"""
Diagnóstico: por célula problemática, mostra qual viga está lá,
o bx_min calculado, e quais elementos face_a forçam bx_min tão negativo.
"""
import sys, io, json, math
# use stderr to avoid encoding issues on Windows
out = sys.stderr
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json'
CELL_W, CELL_H, MARGIN, COLS = 2900, 1800, 80, 12

# Células problemáticas (col, row) onde a maioria do conteúdo fica à DIREITA
PROBLEM_CELLS = {
    (2, 42), (10, 11), (10, 36), (6, 29), (0, 32),
    (4, 32), (10, 37), (6, 37), (8, 41), (7, 41),
}

def compute_bbox_debug(vdata):
    """Igual a compute_content_bbox mas retorna também os xs mais negativos."""
    xs, ys = [], []
    fa = vdata.get('face_a') or {}

    def _line_in_face(l, face, margin=8):
        xmin = face.get('face_x_min'); xmax = face.get('face_x_max')
        ymin = face.get('y_min');      ymax = face.get('y_max')
        if not all([xmin is not None, xmax is not None, ymin is not None, ymax is not None]):
            return True
        mx = (l['x1'] + l['x2']) / 2; my = (l['y1'] + l['y2']) / 2
        return (xmin - margin <= mx <= xmax + margin and
                ymin - margin <= my <= ymax + margin)

    # face_a hlines/vlines → xs
    fa_xs = []
    for hl in (fa.get('face_hlines') or []):
        fa_xs.extend([hl['x1'], hl['x2']]); ys.extend([hl['y'], hl['y']])
    for vl in (fa.get('face_vlines') or []):
        fa_xs.extend([vl['x'], vl['x']]); ys.extend([vl['y1'], vl['y2']])
    xs.extend(fa_xs)

    # face_b → ys only
    fb = vdata.get('face_b') or {}
    for hl in (fb.get('face_hlines') or []):
        ys.extend([hl['y'], hl['y']])
    for vl in (fb.get('face_vlines') or []):
        ys.extend([vl['y1'], vl['y2']])

    # polys
    poly_xs = []
    for poly_key in ['all_concreto_polys','all_sarr35_polys','all_madeira_polys','all_sarr22_polys','panel_polys']:
        for poly in (R._filter_polys(vdata.get(poly_key) or [], fa)):
            for v in (poly.get('vertices') or []):
                if len(v) >= 2:
                    poly_xs.append(v[0]); xs.append(v[0]); ys.append(v[1])

    # sarr22_lines
    sarr_xs = []
    for sl in (vdata.get('sarr22_lines') or []):
        cx = (sl['x1'] + sl['x2']) / 2; cy = (sl['y1'] + sl['y2']) / 2
        if R._x_in_face_range(cx, fa) and R._y_in_face_range(cy, fa):
            sarr_xs.extend([sl['x1'], sl['x2']]); xs.extend([sl['x1'], sl['x2']]); ys.extend([sl['y1'], sl['y2']])

    # sarr35_lines
    for sl in (vdata.get('all_sarr35_lines') or []):
        if _line_in_face(sl, fa):
            xs.extend([sl['x1'], sl['x2']]); ys.extend([sl['y1'], sl['y2']])

    if not xs:
        return None, fa_xs, poly_xs, sarr_xs

    bx_min = min(xs)
    return (bx_min, max(xs), min(ys), max(ys)), fa_xs, poly_xs, sarr_xs


with open(PARAMS_FILE, encoding='utf-8') as f:
    params = json.load(f)

# Montar índice célula → viga
row, col = 0, 0
for p in params:
    cell = (col, row)
    if cell in PROBLEM_CELLS:
        viga = p.get('viga', '?')
        bbox, fa_xs, poly_xs, sarr_xs = compute_bbox_debug(p)
        if bbox:
            bx_min = bbox[0]
            ox = col * CELL_W + MARGIN - bx_min
            print(f"\n{'='*60}")
            print(f"Célula ({col},{row}) — viga: {viga}")
            print(f"  bx_min={bx_min:.1f}  ox={ox:.1f}  (conteúdo principal ~x={col*CELL_W + ox:.0f})")
            if fa_xs:
                fa_xs_sorted = sorted(fa_xs)[:5]
                print(f"  face_a xs (5 menores): {[round(x,1) for x in fa_xs_sorted]}")
                print(f"  face_a xs range: [{min(fa_xs):.1f}, {max(fa_xs):.1f}]  n={len(fa_xs)}")
            else:
                print(f"  face_a xs: VAZIO")
            if poly_xs:
                neg_polys = sorted([x for x in poly_xs if x < -100])[:5]
                if neg_polys:
                    print(f"  poly xs negativos: {[round(x,1) for x in neg_polys]}")
            if sarr_xs:
                neg_sarr = sorted([x for x in sarr_xs if x < -100])[:5]
                if neg_sarr:
                    print(f"  sarr xs negativos: {[round(x,1) for x in neg_sarr]}")
            # Mostrar fa info
            fa = p.get('face_a') or {}
            print(f"  face_a keys: {list(fa.keys())[:10]}")
            print(f"  face_a face_x_min={fa.get('face_x_min')} face_x_max={fa.get('face_x_max')}")
        else:
            print(f"\nCélula ({col},{row}) — viga: {viga} — BBOX NONE")
        sys.stdout.flush()

    col += 1
    if col >= COLS:
        col = 0
        row += 1
