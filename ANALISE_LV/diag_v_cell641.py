#!/usr/bin/env python3
"""Diagnóstico da viga em cell (6,41) — verifica se produz hachura em off<0 (bleeding into cell5)."""
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

# Check cell (6,41) = index 41*12+6 = 498
# Also check surrounding cells: (6,40)=490, (6,42)=510, (7,41)=499
for test_col, test_row in [(6,41), (6,40), (7,41), (5,42), (6,39)]:
    idx = test_row * 12 + test_col
    if idx >= len(deduped): continue
    p = deduped[idx]
    viga = p.get('viga','?')
    fa = p.get('face_a') or {}
    fx_min = fa.get('face_x_min') or 0; fx_max = fa.get('face_x_max') or 0
    fw = fx_max - fx_min
    mx = max(fw*0.3, 300)
    xs_fa = []
    for hl in (fa.get('face_hlines') or []):
        xs_fa.extend([hl['x1'], hl['x2']])
    for vl in (fa.get('face_vlines') or []):
        xs_fa.append(vl['x'])
    bx_min = min(xs_fa) if xs_fa else 0
    target_x = test_col * CELL_W
    ox = target_x + MARGIN - bx_min

    # Check hatches for any off < -10 (bleeding left) or off > CELL_W+10 (bleeding right)
    hatches = R._filter_hatches(p.get('hatches_data') or [], fa)
    bleeds = []
    for h in hatches:
        bps = h.get('boundary_polys', [])
        all_pts = [pt for bp in bps for pt in bp]
        if not all_pts: continue
        cx = sum(pt[0] for pt in all_pts)/len(all_pts)
        off = cx+ox-target_x
        bp0 = bps[0] if bps else []
        trans_xs = sorted([round(pt[0]+ox) for pt in bp0])
        vert_ok = all(v >= target_x-50 and v <= target_x+CELL_W+50 for v in trans_xs) if trans_xs else True
        ctr_ok = (target_x-150) <= (cx+ox) <= (target_x+CELL_W+150)
        if off < -10:
            bleeds.append((off, h.get('layer','?'), trans_xs, vert_ok, ctr_ok))

    if bleeds:
        print("Cell (%d,%d) viga=%s  fw=%.0f  bx_min=%.1f  ox=%.1f" % (
            test_col, test_row, viga, fw, bx_min, ox))
        print("  BLEEDING HATCHES (off < -10):")
        for off, lyr, vxs, vok, cok in bleeds:
            status = "RENDERED" if (vok and cok) else "suppressed(vert=%s,ctr=%s)"%(vok,cok)
            print("  off=%.0f  %s  vxs=%s  %s" % (off, lyr, vxs[:4], status))
            # The entity appears in cell (test_col-1, test_row) at offset CELL_W+off
            prev_off = CELL_W + off
            print("  -> appears in cell (%d,%d) at offset %.0f" % (test_col-1, test_row, prev_off))
    else:
        # Still show summary
        if hatches:
            all_offs = sorted([sum(pt[0] for pt in [pt for bp in h.get('boundary_polys',[]) for pt in bp])/
                               max(1,len([pt for bp in h.get('boundary_polys',[]) for pt in bp]))+ox-target_x
                               for h in hatches if [pt for bp in h.get('boundary_polys',[]) for pt in bp]])
            if all_offs:
                print("Cell (%d,%d) viga=%s  off=[%.0f,%.0f]  no bleeds" % (
                    test_col, test_row, viga, min(all_offs), max(all_offs)))
