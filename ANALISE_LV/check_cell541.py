import sys, json
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json'
CELL_W, CELL_H, MARGIN, COLS = 2900, 1800, 80, 12

with open(PARAMS_FILE, encoding='utf-8') as f:
    raw = json.load(f)

_groups = {}; order = []
for p in raw:
    obra = p.get('obra',''); viga = p.get('viga','')
    ix = round((p.get('insert_x') or 0)/5); iy = round((p.get('insert_y') or 0)/5)
    key = (obra, viga, ix, iy)
    if key not in _groups: _groups[key] = []; order.append(key)
    _groups[key].append(p)
params = [max(_groups[k], key=lambda e: sum(len(e.get(x) or []) for x in
    ['face_a','face_b','all_concreto_polys','hatches_data','sarr22_lines'])) for k in order]
print("After dedup: %d params" % len(params))

# Find cell (5,41): index 41*12+5=497
# Also find cells with hachura near offset 2862
print("\nLooking for vigas that produce a hachura at offset ~2862 in any cell:")
r, c = 0, 0
for i, p in enumerate(params):
    fa = p.get('face_a') or {}
    fx_min = fa.get('face_x_min') or 0
    fx_max = fa.get('face_x_max') or 0
    fw = fx_max - fx_min
    mx = max(fw*0.3, 300) if fw else 999
    xs_fa = []
    for hl in (fa.get('face_hlines') or []):
        xs_fa.extend([hl['x1'], hl['x2']])
    for vl in (fa.get('face_vlines') or []):
        xs_fa.append(vl['x'])
    bx_min = min(xs_fa) if xs_fa else 0
    target_x = c * CELL_W
    ox = target_x + MARGIN - bx_min if bx_min else 0

    # Check hatches
    hatches = R._filter_hatches(p.get('hatches_data') or [], fa)
    for h in hatches:
        bps = h.get('boundary_polys', [])
        all_pts = [pt for bp in bps for pt in bp]
        if not all_pts: continue
        cx = sum(pt[0] for pt in all_pts)/len(all_pts)
        off = cx + ox - target_x
        if 2800 <= off <= 2900:  # Near right edge
            # Check vertex status
            bp0 = bps[0] if bps else []
            vert_xs = sorted([round(pt[0]+ox) for pt in bp0])
            vert_ok = all(v >= target_x-50 and v <= target_x+CELL_W+50 for v in vert_xs) if vert_xs else False
            ctr_ok = (target_x-150) <= (cx+ox) <= (target_x+CELL_W+150)
            print("  Cell (%d,%d) viga=%s hatch off=%.0f layer=%s vert_ok=%s ctr_ok=%s" % (
                c,r,p.get('viga','?'),off,h.get('layer','?'),vert_ok,ctr_ok))
            if vert_ok:  # This one actually appears in DXF
                print("    *** APPEARS IN DXF: translated_cx=%.1f  vert=[%d,%d]" % (
                    cx+ox, min(vert_xs) if vert_xs else 0, max(vert_xs) if vert_xs else 0))

    c += 1
    if c >= COLS: c = 0; r += 1

# Directly check cell index 497
print("\n--- Cell index 497 (expected (5,41)) ---")
if 497 < len(params):
    p = params[497]
    print("viga=%s obra=%s" % (p.get('viga','?'), p.get('obra','?')))
