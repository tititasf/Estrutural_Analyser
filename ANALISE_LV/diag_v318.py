#!/usr/bin/env python3
"""Diagnóstico V318 (cell 6,41) — rastreia origem da hachura x~17362 no DXF."""
import sys, json
from collections import defaultdict as _dd
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json'
CELL_W, CELL_H, MARGIN, COLS = 2900, 1800, 80, 12

with open(PARAMS_FILE, encoding='utf-8') as f:
    raw = json.load(f)
for p in raw: p['_obra'] = p.get('obra') or 'desconhecida'

_groups = _dd(list)
for p in raw:
    ins = p.get('insert') or {}
    key = (p.get('_obra',''), p['viga'], round(ins.get('x',0)/5), round(ins.get('y',0)/5))
    _groups[key].append(p)
deduped = []
for key, vs in _groups.items():
    best = max(vs, key=lambda v: (
        len(v.get('hatches_data') or []) + len(v.get('sarr22_lines') or []) +
        len((v.get('grade_entities') or {}).get('grade_lines', []))))
    deduped.append(best)

p = deduped[41*12+6]  # cell (6,41)
assert p.get('viga') == 'V318', "Expected V318, got %s" % p.get('viga')
fa = p.get('face_a') or {}

# Compute bx_min using FULL compute_content_bbox logic
import sys; sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
# Inline compute_content_bbox
xs, ys = [], []
for hl in (fa.get('face_hlines') or []):
    xs.extend([hl['x1'], hl['x2']]); ys.extend([hl['y'], hl['y']])
for vl in (fa.get('face_vlines') or []):
    xs.extend([vl['x'], vl['x']]); ys.extend([vl['y1'], vl['y2']])
fb = p.get('face_b') or {}
for hl in (fb.get('face_hlines') or []):
    ys.extend([hl['y'], hl['y']])
for vl in (fb.get('face_vlines') or []):
    ys.extend([vl['y1'], vl['y2']])
# Polys
for pk in ['all_concreto_polys','all_sarr35_polys','all_madeira_polys','all_sarr22_polys','panel_polys']:
    for poly in R._filter_polys(p.get(pk) or [], fa):
        for v in (poly.get('vertices') or []):
            if len(v) >= 2: xs.append(v[0]); ys.append(v[1])
# sarr22_lines
for sl in (p.get('sarr22_lines') or []):
    cx = (sl['x1']+sl['x2'])/2; cy = (sl['y1']+sl['y2'])/2
    if R._x_in_face_range(cx, fa) and R._y_in_face_range(cy, fa):
        xs.extend([sl['x1'], sl['x2']]); ys.extend([sl['y1'], sl['y2']])
# sarr35_lines
def _line_in_face(l, face, margin=8):
    xmin = face.get('face_x_min'); xmax = face.get('face_x_max')
    ymin = face.get('y_min');      ymax = face.get('y_max')
    if not all([xmin is not None, xmax is not None, ymin is not None, ymax is not None]):
        return True
    mx2 = (l['x1'] + l['x2']) / 2; my2 = (l['y1'] + l['y2']) / 2
    return (xmin-margin <= mx2 <= xmax+margin and ymin-margin <= my2 <= ymax+margin)
for sl in (p.get('all_sarr35_lines') or []):
    if _line_in_face(sl, fa):
        xs.extend([sl['x1'], sl['x2']]); ys.extend([sl['y1'], sl['y2']])

bx_min_full = min(xs) if xs else 0
by_max_full = max(ys) if ys else 0
target_x = 6 * CELL_W  # 17400
target_y = -41 * CELL_H  # -73800
CONTENT_TOP_Y = target_y + CELL_H - 70  # -72070
ox = target_x + MARGIN - bx_min_full
oy = CONTENT_TOP_Y - by_max_full

print("V318 cell (6,41)")
print("  bx_min_full=%.2f  by_max_full=%.2f" % (bx_min_full, by_max_full))
print("  ox=%.2f  oy=%.2f" % (ox, oy))
print("  face_a: fx_range=[%.1f, %.1f]" % (fa.get('face_x_min',0), fa.get('face_x_max',0)))

# Now check which hatch produces the entity at translated_x~17362
print()
print("--- All hatches (raw, not filtered) ---")
hatches_raw = p.get('hatches_data') or []
for i, h in enumerate(hatches_raw):
    bps = h.get('boundary_polys', [])
    all_pts = [pt for bp in bps for pt in bp]
    if not all_pts: continue
    cx_orig = sum(pt[0] for pt in all_pts)/len(all_pts)
    cy_orig = sum(pt[1] for pt in all_pts)/len(all_pts)
    cx_t = cx_orig + ox
    cy_t = cy_orig + oy
    off_x = cx_t - target_x
    # Vertices
    bp0 = bps[0] if bps else []
    vert_xs = sorted([round(pt[0]+ox) for pt in bp0])
    vert_ys = sorted([round(pt[1]+oy) for pt in bp0])
    if abs(cx_t - 17362) < 200 or off_x < 0:  # Show relevant ones
        in_x = R._x_in_face_range(cx_orig, fa)
        print("  [%d] %s off_x=%.0f  cx_trans=%.1f  cy_trans=%.1f  in_x=%s" % (
            i, h.get('layer','?'), off_x, cx_t, cy_t, in_x))
        print("     vert_xs=%s  vert_ys=%s" % (vert_xs[:4], vert_ys[:4]))

print()
print("--- Check: which hatch has vertices at ~[17351,17373] ---")
for i, h in enumerate(hatches_raw):
    bps = h.get('boundary_polys', [])
    for bp_idx, bp in enumerate(bps):
        trans_xs = sorted([round(pt[0]+ox) for pt in bp])
        if trans_xs and min(trans_xs) <= 17380 and min(trans_xs) >= 17320:
            print("  Found: hatch[%d] boundary[%d]: trans_xs=%s" % (i, bp_idx, trans_xs))
            trans_ys = sorted([round(pt[1]+oy) for pt in bp])
            print("    trans_ys=%s  layer=%s" % (trans_ys, h.get('layer','?')))
            orig_xs = sorted([round(pt[0]) for pt in bp])
            print("    orig_xs=%s" % orig_xs)
            in_x = R._x_in_face_range(sum(pt[0] for pt in bp)/len(bp), fa)
            print("    _filter_hatches passes: in_x=%s" % in_x)
