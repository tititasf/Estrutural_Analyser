#!/usr/bin/env python3
"""
Scan COMPLETO: encontra todas as hatches que têm centroide fora dos limites da célula.
Para cada uma, verifica se passou pelo vertex check (HATCH_TOL=50) e seria renderizada.
"""
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

print("Total vigas: %d" % len(deduped))

# Find ALL hatches with centroid outside cell boundary (no tolerance)
bleeding_rendered = []   # centroid outside, passes vertex check → appears in DXF!
bleeding_suppressed = [] # centroid outside, fails vertex check → doesn't appear

r, c = 0, 0
for p in deduped:
    viga = p.get('viga','?')
    fa = p.get('face_a') or {}
    xs_fa = []
    for hl in (fa.get('face_hlines') or []):
        xs_fa.extend([hl['x1'], hl['x2']])
    for vl in (fa.get('face_vlines') or []):
        xs_fa.append(vl['x'])
    bx_min = min(xs_fa) if xs_fa else 0
    target_x = c * CELL_W
    target_y = -r * CELL_H
    ox = target_x + MARGIN - bx_min

    hatches = R._filter_hatches(p.get('hatches_data') or [], fa)
    for h in hatches:
        bps = h.get('boundary_polys', [])
        all_pts = [pt for bp in bps for pt in bp]
        if not all_pts: continue
        cx = sum(pt[0] for pt in all_pts)/len(all_pts)
        cy = sum(pt[1] for pt in all_pts)/len(all_pts)
        cx_t = cx + ox
        cy_t = cy  # hatches don't transform y... wait, yes they do via oy
        # Actually: tx_pts = [(p[0]+ox, p[1]+oy) for p in boundary]
        # For oy, we need the actual oy. But oy requires by_max.
        # For x-direction analysis only: use cx+ox
        off_x = cx_t - target_x
        # Check if outside cell in X
        if off_x < 0 or off_x > CELL_W:
            # Check vertex OK
            bp0 = bps[0] if bps else []
            trans_xs = sorted([round(pt[0]+ox) for pt in bp0])
            vert_ok = all(v >= target_x-50 and v <= target_x+CELL_W+50 for v in trans_xs) if trans_xs else True
            ctr_ok_150 = (target_x-150) <= cx_t <= (target_x+CELL_W+150)
            ctr_ok_20 = (target_x-20) <= cx_t <= (target_x+CELL_W+20)
            layer = h.get('layer','?')
            entry = (c, r, viga, off_x, layer, trans_xs, vert_ok, ctr_ok_150, ctr_ok_20)
            if vert_ok and ctr_ok_150:
                bleeding_rendered.append(entry)
            else:
                bleeding_suppressed.append(entry)

    c += 1
    if c >= COLS: c = 0; r += 1

print()
print("=== HATCHES BLEEDING (centroid outside cell x-boundary) ===")
print("Rendered in DXF (vert_ok=True & ctr_ok_150=True): %d" % len(bleeding_rendered))
print("Suppressed:                                          %d" % len(bleeding_suppressed))

print()
print("RENDERED bleeding hatches (these appear as isolated fragments!):")
for c,r,viga,off_x,layer,vxs,vok,cok150,cok20 in bleeding_rendered:
    prev_cell = "col%d" % (c-1 if off_x < 0 else c+1)
    print("  Cell(%d,%d) %s  off=%.0f  %s  vxs=[%d,%d]  ctr_ok_20=%s  -> bleeds into %s" % (
        c,r,viga,off_x,layer,
        min(vxs) if vxs else 0, max(vxs) if vxs else 0,
        cok20, prev_cell))

if bleeding_suppressed:
    print()
    print("Suppressed bleeding hatches (not in DXF, good): %d total" % len(bleeding_suppressed))
    for c,r,viga,off_x,layer,vxs,vok,cok150,cok20 in bleeding_suppressed[:5]:
        print("  Cell(%d,%d) %s  off=%.0f  %s  vert_ok=%s  ctr_ok_150=%s" % (
            c,r,viga,off_x,layer,vok,cok150))

print()
print("Summary: fix needed for %d rendered bleeding hatches" % len(bleeding_rendered))
print("Proposed fix: change centroid tol from 150 to 20")
print("After fix: all %d would be suppressed" % sum(1 for *_,cok20 in bleeding_rendered if not cok20))
