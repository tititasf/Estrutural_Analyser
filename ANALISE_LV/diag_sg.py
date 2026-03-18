#!/usr/bin/env python3
"""
Diagnóstico: verifica section_geometry e polys isolados.
Para cada célula-problema, mostra os offsets de TODOS os elementos renderizados.
"""
import sys, json
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json'
CELL_W, CELL_H, MARGIN, COLS = 2900, 1800, 80, 12

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

def poly_centroid(verts):
    cx = sum(v[0] for v in verts)/len(verts)
    cy = sum(v[1] for v in verts)/len(verts)
    return cx, cy

with open(PARAMS_FILE, encoding='utf-8') as f:
    raw = json.load(f)
params = dedup_params(raw)

# Cells from previous diagnostic with isolated CONCRETO/Paineis
TARGET_CELLS = {(8,7), (5,41), (10,37), (4,44), (5,15), (2,38), (1,31), (4,10)}

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

        print("\n" + "="*55)
        print("Cell (%d,%d) viga=%s  fw=%.0f  bx_min=%.1f  ox=%.1f" % (c,r,viga,fw,bx_min,ox))

        # face_a hlines/vlines offsets
        fa_xs = []
        for hl in (fa.get('face_hlines') or []):
            fa_xs.extend([hl['x1']+ox-target_x, hl['x2']+ox-target_x])
        for vl in (fa.get('face_vlines') or []):
            fa_xs.append(vl['x']+ox-target_x)
        if fa_xs:
            print("  face_a off range: [%.0f, %.0f]" % (min(fa_xs), max(fa_xs)))

        # All polys (filtered)
        for key, layer in [('all_concreto_polys','CONCRETO'), ('all_madeira_polys','Madeira'),
                            ('all_sarr35_polys','SARR35'), ('all_sarr22_polys','SARR22'),
                            ('panel_polys','Paineis')]:
            raw_polys = p.get(key) or []
            filt = R._filter_polys(raw_polys, fa)
            if filt:
                for i, poly in enumerate(filt[:3]):
                    verts = poly.get('vertices') or []
                    if not verts: continue
                    cx,cy = poly_centroid(verts)
                    off = cx + ox - target_x
                    xs_v = [round(v[0]+ox-target_x) for v in verts]
                    print("  %s[%d] off=%.0f  x=[%d,%d]" % (layer,i,off,min(xs_v),max(xs_v)))
                if len(filt) > 3:
                    all_offs = []
                    for poly in filt:
                        verts = poly.get('vertices') or []
                        if verts:
                            cx,cy = poly_centroid(verts)
                            all_offs.append(cx+ox-target_x)
                    print("  %s total=%d off=[%.0f,%.0f]" % (layer,len(filt),min(all_offs),max(all_offs)))

        # section_geometry polys (used when all_xxx_polys is empty)
        sg = p.get('section_geometry') or {}
        for sg_key, layer in [('seccao_concreto','CONCRETO_SG'), ('sarrafos_35x7','SARR35_SG'),
                               ('barrotes_madeira','Madeira_SG')]:
            sg_val = sg.get(sg_key)
            if sg_key == 'seccao_concreto':
                if sg_val and sg_val.get('vertices'):
                    verts = sg_val['vertices']
                    cx,cy = poly_centroid(verts)
                    off = cx+ox-target_x
                    xs_v = [round(v[0]+ox-target_x) for v in verts]
                    print("  SG/%s off=%.0f  x=[%d,%d]" % (layer,off,min(xs_v),max(xs_v)))
                    in_cell = (target_x-200) <= (cx+ox) <= (target_x+CELL_W+200)
                    print("    poly_in_cell(tol=200): %s" % in_cell)
            else:
                items = sg.get(sg_key) or []
                for i, item in enumerate(items[:3]):
                    verts = item.get('vertices') or []
                    if not verts: continue
                    cx,cy = poly_centroid(verts)
                    off = cx+ox-target_x
                    xs_v = [round(v[0]+ox-target_x) for v in verts]
                    print("  SG/%s[%d] off=%.0f  x=[%d,%d]" % (sg_key,i,off,min(xs_v),max(xs_v)))

        # sarr22_lines (filtered by x/y range)
        sarr22 = p.get('sarr22_lines') or []
        sarr22_filt = [sl for sl in sarr22 if R._x_in_face_range((sl['x1']+sl['x2'])/2, fa) and
                       R._y_in_face_range((sl['y1']+sl['y2'])/2, fa)]
        if sarr22_filt:
            s22_offs = [(sl['x1']+sl['x2'])/2 + ox - target_x for sl in sarr22_filt]
            print("  sarr22_lines: %d filtered, off=[%.0f,%.0f]" % (len(sarr22_filt),min(s22_offs),max(s22_offs)))

    c += 1
    if c >= COLS: c = 0; r += 1
