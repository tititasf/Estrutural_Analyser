#!/usr/bin/env python3
"""Diagnóstico: verifica hatch offsets e vertex positions para células-problema."""
import sys, json
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json'
CELL_W, CELL_H, MARGIN, COLS = 2900, 1800, 80, 12

def dedup_params(params):
    _groups = {}; order = []
    for p in params:
        obra = p.get('obra',''); viga = p.get('viga','')
        ix = round((p.get('insert_x') or 0) / 5); iy = round((p.get('insert_y') or 0) / 5)
        key = (obra, viga, ix, iy)
        if key not in _groups: _groups[key] = []; order.append(key)
        _groups[key].append(p)
    result = []
    for key in order:
        entries = _groups[key]
        best = max(entries, key=lambda e: sum(len(e.get(k) or []) for k in
            ['face_a','face_b','all_concreto_polys','hatches_data','sarr22_lines']))
        result.append(best)
    return result

with open(PARAMS_FILE, encoding='utf-8') as f:
    raw = json.load(f)
params = dedup_params(raw)

TARGET_CELLS = {(9,19), (5,22), (4,10), (8,7), (5,41), (1,0)}

r, c = 0, 0
for p in params:
    cell = (c, r)
    if cell in TARGET_CELLS:
        viga = p.get('viga','?')
        fa = p.get('face_a') or {}
        xs_fa = []
        for hl in (fa.get('face_hlines') or []):
            xs_fa.extend([hl['x1'], hl['x2']])
        for vl in (fa.get('face_vlines') or []):
            xs_fa.append(vl['x'])
        bx_min = min(xs_fa) if xs_fa else 0
        target_x = c * CELL_W
        ox = target_x + MARGIN - bx_min

        fw = fa.get('face_x_max',0) - fa.get('face_x_min',0)
        margin_x = max(fw*0.3, 300)

        print("\n" + "="*55)
        print("Cell (%d,%d) viga=%s  fw=%.0f  margin_x=%.0f" % (c,r,viga,fw,margin_x))
        print("bx_min=%.1f  ox=%.1f  target_x=%d" % (bx_min, ox, target_x))

        hatches_raw = p.get('hatches_data') or []
        hatches = R._filter_hatches(hatches_raw, fa)
        print("Hatches: %d raw -> %d filtered" % (len(hatches_raw), len(hatches)))

        # Show any hatch with centroid offset outside [-100, CELL_W+100]
        outside = []
        for h in hatches:
            bps = h.get('boundary_polys', [])
            all_pts = [pt for bp in bps for pt in bp]
            if not all_pts: continue
            cx = sum(pt[0] for pt in all_pts)/len(all_pts)
            off = cx + ox - target_x
            if off < -10 or off > CELL_W + 10:
                bp0 = bps[0] if bps else []
                vert_xs = sorted([round(pt[0]+ox) for pt in bp0])
                # Vertex check simulation (HATCH_TOL=50)
                cell_ok = all((target_x-50) <= vx <= (target_x+CELL_W+50) for vx in vert_xs)
                # Centroid check simulation (tol=150)
                ctr_ok = (target_x-150) <= (cx+ox) <= (target_x+CELL_W+150)
                outside.append((off, h.get('layer','?'), vert_xs, cell_ok, ctr_ok))

        if outside:
            print("  OUTSIDE hatches (centroid off<-10 or >CELL_W+10):")
            for off,lyr,vxs,vchk,cchk in outside:
                print("  off=%.1f  layer=%s  vert_xs=%s  ctr_ok=%s  vert_ok=%s" % (
                    off, lyr, vxs[:4], cchk, vchk))
        else:
            print("  All hatches within cell bounds (no outside)")

        # Show full range
        all_offs = []
        for h in hatches:
            bps = h.get('boundary_polys', [])
            all_pts = [pt for bp in bps for pt in bp]
            if not all_pts: continue
            cx = sum(pt[0] for pt in all_pts)/len(all_pts)
            all_offs.append((round(cx+ox-target_x), h.get('layer','?')))
        if all_offs:
            all_offs.sort()
            print("  offset range: [%d, %d]  n=%d" % (all_offs[0][0], all_offs[-1][0], len(all_offs)))

    c += 1
    if c >= COLS: c = 0; r += 1
