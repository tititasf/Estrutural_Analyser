#!/usr/bin/env python3
"""Diagnóstico detalhado da V316 (cell 5,41) — rastreia o fragmento isolado Hachura @ off~2862."""
import sys, json
from collections import defaultdict as _dd
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json'
CELL_W, CELL_H, MARGIN, COLS = 2900, 1800, 80, 12

with open(PARAMS_FILE, encoding='utf-8') as f:
    raw = json.load(f)

for p in raw:
    p['_obra'] = p.get('obra') or 'desconhecida'

_groups = _dd(list)
for p in raw:
    ins = p.get('insert') or {}
    key = (p.get('_obra',''), p['viga'], round(ins.get('x',0)/5), round(ins.get('y',0)/5))
    _groups[key].append(p)

deduped = []
for key, vs in _groups.items():
    best = max(vs, key=lambda v: (
        len(v.get('hatches_data') or []) +
        len(v.get('sarr22_lines') or []) +
        len((v.get('grade_entities') or {}).get('grade_lines', []))
    ))
    deduped.append(best)

# Find V316 at index 497 (cell 5,41)
p = deduped[41*12+5]
assert p.get('viga') == 'V316', "Expected V316 at idx 497, got %s" % p.get('viga')

fa = p.get('face_a') or {}
fx_min = fa.get('face_x_min') or 0
fx_max = fa.get('face_x_max') or 0
fw = fx_max - fx_min
mx = max(fw*0.3, 300)

xs_fa = []
for hl in (fa.get('face_hlines') or []):
    xs_fa.extend([hl['x1'], hl['x2']])
for vl in (fa.get('face_vlines') or []):
    xs_fa.append(vl['x'])
bx_min = min(xs_fa) if xs_fa else 0
target_x = 5 * CELL_W  # 14500
ox = target_x + MARGIN - bx_min

print("V316 cell (5,41)")
print("  face_a: fw=%.0f  fx_range=[%.1f, %.1f]" % (fw, fx_min, fx_max))
print("  x_margin=%.0f  allowed=[%.0f, %.0f]" % (mx, fx_min-mx, fx_max+mx))
print("  bx_min=%.1f  ox=%.1f  target_x=%d" % (bx_min, ox, target_x))
print("  face_a off range: [%.0f, %.0f]" % (bx_min+ox-target_x, max(xs_fa)+ox-target_x) if xs_fa else "  face_a: EMPTY")

# Check ALL hatches (both raw and filtered)
print()
print("--- hatches_data analysis ---")
hatches_raw = p.get('hatches_data') or []
print("Total hatches_data: %d" % len(hatches_raw))
for i, h in enumerate(hatches_raw):
    bps = h.get('boundary_polys', [])
    all_pts = [pt for bp in bps for pt in bp]
    if not all_pts: continue
    cx_orig = sum(pt[0] for pt in all_pts)/len(all_pts)
    in_x = R._x_in_face_range(cx_orig, fa)
    in_y = R._y_in_face_range(cx_orig, fa)
    cx_trans = cx_orig + ox
    off = cx_trans - target_x

    # Vertex positions
    bp0 = bps[0] if bps else []
    trans_xs = sorted([round(pt[0]+ox) for pt in bp0])
    vert_ok = all(v >= target_x-50 and v <= target_x+CELL_W+50 for v in trans_xs) if trans_xs else True
    ctr_ok = (target_x-150) <= cx_trans <= (target_x+CELL_W+150)
    passes_filter = in_x  # _y range is very wide

    if off > 2700 or not passes_filter:
        print("  [%d] orig_cx=%.1f  off=%.0f  in_x=%s  layer=%s" % (i, cx_orig, off, in_x, h.get('layer','?')))
        if off > 2700:
            print("       trans_xs=%s  vert_ok=%s  ctr_ok=%s" % (trans_xs[:4], vert_ok, ctr_ok))
        if not passes_filter:
            print("       FILTERED OUT (orig_cx outside [%.0f, %.0f])" % (fx_min-mx, fx_max+mx))

print()
print("--- Filtered hatches summary ---")
filtered = R._filter_hatches(hatches_raw, fa)
print("After filter: %d" % len(filtered))
offs = []
for h in filtered:
    bps = h.get('boundary_polys', [])
    all_pts = [pt for bp in bps for pt in bp]
    if not all_pts: continue
    cx = sum(pt[0] for pt in all_pts)/len(all_pts)
    off = cx+ox-target_x
    bp0 = bps[0] if bps else []
    trans_xs = sorted([round(pt[0]+ox) for pt in bp0])
    vert_ok = all(v >= target_x-50 and v <= target_x+CELL_W+50 for v in trans_xs) if trans_xs else True
    offs.append((off, h.get('layer','?'), vert_ok))

offs.sort()
print("Offsets + vert_ok:")
for off, lyr, vok in offs:
    marker = " *** OUTSIDE ***" if (off < -10 or off > CELL_W+10) else ""
    vmarker = " [SUPPRESSED]" if not vok else " [RENDERED]"
    print("  off=%.0f  %s%s%s" % (off, lyr, vmarker, marker))

# Also check sarr22_lines, all_sarr22_polys, sarr22_polys
print()
print("--- sarr22 ---")
sarr22 = p.get('sarr22_lines') or []
print("sarr22_lines: %d" % len(sarr22))
sarr22p = p.get('all_sarr22_polys') or []
sarr22p_filt = R._filter_polys(sarr22p, fa)
print("all_sarr22_polys: %d raw, %d filtered" % (len(sarr22p), len(sarr22p_filt)))
for sp in sarr22p_filt:
    verts = sp.get('vertices') or []
    if not verts: continue
    off_xs = [round(v[0]+ox-target_x) for v in verts]
    print("  sarr22_poly off_x=[%d,%d]" % (min(off_xs), max(off_xs)))

# Check all other poly keys
print()
print("--- Other polys ---")
for key in ['all_concreto_polys','all_madeira_polys','all_sarr35_polys','panel_polys']:
    raw_p = p.get(key) or []
    filt_p = R._filter_polys(raw_p, fa)
    if filt_p:
        offs_p = []
        for pp in filt_p:
            verts = pp.get('vertices') or []
            if verts:
                cx = sum(v[0] for v in verts)/len(verts)
                offs_p.append(round(cx+ox-target_x))
        print("  %s: %d filt, off=[%d,%d]" % (key, len(filt_p), min(offs_p), max(offs_p)))
