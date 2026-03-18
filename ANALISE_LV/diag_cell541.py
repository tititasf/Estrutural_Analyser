#!/usr/bin/env python3
"""Diagnóstico completo da célula (5,41) e adjacentes para achar o fragmento isolado."""
import sys, json, ezdxf
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json'
DXF_PATH    = 'D:/Agente-cad-PYSIDE/ANALISE_LV/combined/combined_v31.dxf'
CELL_W, CELL_H, MARGIN, COLS = 2900, 1800, 80, 12
CONTENT_LAYERS = {'Paineis', 'Painéis', 'Hachura', 'CONCRETO', 'Madeira', 'SARR_2.2x7',
                  'SARR_3.5x7', 'SARR_2.2x10', 'SARR_EDITAR', 'REAPROVEITAMENTO', 'COTA', 'Forcador'}

def dedup_params(params):
    _groups = {}; order = []
    for p in params:
        obra = p.get('obra',''); viga = p.get('viga','')
        ix = round((p.get('insert_x') or 0) / 5)
        iy = round((p.get('insert_y') or 0) / 5)
        key = (obra, viga, ix, iy)
        if key not in _groups: _groups[key] = []; order.append(key)
        _groups[key].append(p)
    result = []
    for key in order:
        best = max(_groups[key], key=lambda e: sum(len(e.get(k) or []) for k in
            ['face_a','face_b','all_concreto_polys','hatches_data','sarr22_lines']))
        result.append(best)
    return result

with open(PARAMS_FILE, encoding='utf-8') as f:
    raw = json.load(f)
params = dedup_params(raw)

# --- Part 1: Params analysis for cell (5,41) ---
print("=== PARAMS analysis cell (5,41) ===")
r, c = 0, 0
for p in params:
    if (c, r) == (5, 41):
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

        print("viga=%s  fw=%.0f  bx_min=%.1f  ox=%.1f" % (viga,fw,bx_min,ox))
        print("face_a x_range=[%.1f, %.1f]" % (fa.get('face_x_min',0), fa.get('face_x_max',0)))

        # All hatch offsets
        hatches = R._filter_hatches(p.get('hatches_data') or [], fa)
        print("Hatches: %d" % len(hatches))
        for h in hatches:
            bps = h.get('boundary_polys', [])
            all_pts = [pt for bp in bps for pt in bp]
            if not all_pts: continue
            cx = sum(pt[0] for pt in all_pts)/len(all_pts)
            off = cx + ox - target_x
            bp0 = bps[0] if bps else []
            vert_xs = sorted([round(pt[0]+ox) for pt in bp0])
            lyr = h.get('layer','?')
            # Check if passed vertex check (tol=50)
            cell_x = target_x
            vert_ok = all(v >= cell_x-50 and v <= cell_x+CELL_W+50 for v in vert_xs)
            print("  %s off=%.0f  vert=[%d,%d]  vert_ok=%s" % (
                lyr, off, min(vert_xs) if vert_xs else 0, max(vert_xs) if vert_xs else 0, vert_ok))

        # section_geometry
        sg = p.get('section_geometry') or {}
        sc = sg.get('seccao_concreto')
        if sc and sc.get('vertices'):
            verts = sc['vertices']
            cx = sum(v[0] for v in verts)/len(verts)
            off = cx+ox-target_x
            xs_v = [round(v[0]+ox-target_x) for v in verts]
            print("SG/seccao_concreto off=%.0f x=[%d,%d]" % (off,min(xs_v),max(xs_v)))

        # concreto polys
        cp = R._filter_polys(p.get('all_concreto_polys') or [], fa)
        for i,poly in enumerate(cp[:5]):
            verts = poly.get('vertices') or []
            if not verts: continue
            cx = sum(v[0] for v in verts)/len(verts)
            xs_v = [round(v[0]+ox-target_x) for v in verts]
            print("CONCRETO[%d] off=%.0f x=[%d,%d]" % (i,cx+ox-target_x,min(xs_v),max(xs_v)))

        print("insert_x=%s  insert_y=%s" % (p.get('insert_x'), p.get('insert_y')))
    c += 1
    if c >= COLS: c = 0; r += 1

# --- Part 2: DXF scan for cell (5,41) actual content ---
print()
print("=== DXF scan cell (5,41) ===")
# Cell (5,41): x=[14500,17400], y=[-73800,-72000]
C5_X0 = 5*CELL_W   # 14500
C5_X1 = C5_X0 + CELL_W  # 17400
C5_Y0 = -41*CELL_H  # -73800
C5_Y1 = C5_Y0 + CELL_H  # -72000
print("Expected bounds: x=[%d,%d]  y=[%d,%d]" % (C5_X0,C5_X1,C5_Y0,C5_Y1))

doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()
entities_in_cell = []
for entity in msp:
    layer = getattr(entity.dxf, 'layer', '0')
    if layer not in CONTENT_LAYERS: continue
    t = entity.dxftype()
    pts = []
    try:
        if t == 'LINE': pts = [entity.dxf.start[:2], entity.dxf.end[:2]]
        elif t == 'LWPOLYLINE': pts = [(p[0], p[1]) for p in entity.get_points()]
        elif t == 'HATCH':
            for path in entity.paths:
                if hasattr(path, 'vertices'):
                    pts += [(v[0], v[1]) for v in path.vertices[:4]]
    except: continue
    if not pts: continue
    cx = sum(p[0] for p in pts)/len(pts)
    cy = sum(p[1] for p in pts)/len(pts)
    # in cell with tol=60
    if (C5_X0-60) <= cx <= (C5_X1+60) and (C5_Y0-60) <= cy <= (C5_Y1+60):
        off_x = round(cx - C5_X0)
        entities_in_cell.append((off_x, cy, layer, t))

entities_in_cell.sort()
print("Entities in cell (5,41): %d total" % len(entities_in_cell))
# Show off_x distribution
off_xs = [e[0] for e in entities_in_cell]
if off_xs:
    print("off_x range: [%d, %d]" % (min(off_xs), max(off_xs)))
    # Find gaps
    from collections import Counter
    sorted_xs = sorted(set(off_xs))
    if len(sorted_xs) > 1:
        gaps = [(sorted_xs[i+1]-sorted_xs[i], sorted_xs[i], sorted_xs[i+1])
                for i in range(len(sorted_xs)-1)]
        max_gap, g0, g1 = max(gaps)
        print("Max gap: %d (between x=%d and x=%d)" % (max_gap, g0, g1))
        left_ents = [(off,cy,lyr,t) for off,cy,lyr,t in entities_in_cell if off <= g0]
        right_ents = [(off,cy,lyr,t) for off,cy,lyr,t in entities_in_cell if off >= g1]
        print("Left cluster (%d ents) max_off=%d" % (len(left_ents), max(e[0] for e in left_ents) if left_ents else 0))
        print("Right cluster (%d ents): %s" % (len(right_ents), [(e[0],e[2]) for e in right_ents[:5]]))
