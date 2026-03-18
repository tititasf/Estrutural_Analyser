#!/usr/bin/env python3
"""Diagnóstico 2: bbox vs face_a offsets reais, e elementos sem clipping."""
import json, sys
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R
from combinar_vigas_dxf import compute_content_bbox

with open('D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json', encoding='utf-8') as f:
    params = json.load(f)

CELL_W, CELL_H, MARGIN, TOL = 2900, 1800, 80, 150

real_problems = []
for p in params:
    fa = p.get('face_a') or {}
    fa_xmin = fa.get('face_x_min')
    fa_ymin = fa.get('y_min')
    fa_ymax = fa.get('y_max')

    bbox = compute_content_bbox(p)
    if not bbox:
        continue
    bx_min, bx_max, by_min, by_max = bbox

    ox = MARGIN - bx_min
    oy = MARGIN - by_min
    cx0, cy0 = 0, 0  # target_x/y = 0 for simplicity

    def in_cell(tx, ty):
        return (cx0 - TOL) <= tx <= (cx0 + CELL_W + TOL) and (cy0 - TOL) <= ty <= (cy0 + CELL_H + TOL)

    # Check if face_a itself renders within the cell after offset
    issues = []
    if fa_xmin is not None:
        fa_xmin_t = fa_xmin + ox
        fa_xmax_t = fa.get('face_x_max', fa_xmin) + ox
        if fa_xmin_t < -TOL or fa_xmax_t > CELL_W + TOL:
            issues.append(f'face_a X OUTSIDE cell: x=[{fa_xmin_t:.0f},{fa_xmax_t:.0f}]')

    # Check aberturas (NO clipping in translate_viga)
    for ab in (p.get('aberturas') or []):
        if ab.get('vertices'):
            verts = ab['vertices']
            cx = sum(v[0]+ox for v in verts)/len(verts)
            cy = sum(v[1]+oy for v in verts)/len(verts)
            if not in_cell(cx, cy):
                issues.append(f'abertura OUTSIDE cell: centroid=({cx:.0f},{cy:.0f})')
        else:
            xmn, xmx = ab.get('x_min',0)+ox, ab.get('x_max',0)+ox
            ymn, ymx = ab.get('y_min',0)+oy, ab.get('y_max',0)+oy
            if not in_cell((xmn+xmx)/2, (ymn+ymx)/2):
                issues.append(f'abertura(bbox) OUTSIDE cell: x=[{xmn:.0f},{xmx:.0f}] y=[{ymn:.0f},{ymx:.0f}]')

    # Check titulo_insert text (NO clipping)
    sg = p.get('section_geometry') or {}
    ti = sg.get('titulo_insert')
    if ti:
        tx, ty = ti['x']+ox, ti['y']+oy+5
        if not in_cell(tx, ty):
            issues.append(f'titulo_insert OUTSIDE cell: ({tx:.0f},{ty:.0f})')

    # Check panel_labels (NO clipping)
    for pl in (p.get('panel_labels') or []):
        tx, ty = pl['x']+ox, pl['y']+oy
        if not in_cell(tx, ty):
            issues.append(f'panel_label OUTSIDE cell: ({tx:.0f},{ty:.0f})')

    # Check panel_texts_positioned (NO clipping)
    for pt in (p.get('panel_texts_positioned') or []):
        tx, ty = pt['x']+ox, pt['y']+oy
        if not in_cell(tx, ty):
            issues.append(f'panel_text OUTSIDE cell: ({tx:.0f},{ty:.0f})')

    if issues:
        obra = p.get('obra','')
        viga = p.get('viga','')
        real_problems.append((obra, viga, issues))

print(f'Vigas com problemas REAIS (elementos fora da célula): {len(real_problems)}')
for obra, viga, issues in real_problems[:30]:
    print(f'  {obra}/{viga}:')
    for i in issues[:3]:
        print(f'    {i}')
if len(real_problems) > 30:
    print(f'  ... e mais {len(real_problems)-30}')
