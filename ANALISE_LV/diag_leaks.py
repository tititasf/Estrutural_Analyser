#!/usr/bin/env python3
"""Diagnóstico: identifica vigas com bbox corrompido ou elementos fora da célula."""
import json, sys, io
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R
from combinar_vigas_dxf import compute_content_bbox

with open('D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json', encoding='utf-8') as f:
    params = json.load(f)

CELL_W, CELL_H, MARGIN = 2900, 1800, 80
TOL = 150

def _in_cell(tx, ty, cx0, cy0):
    return (cx0 - TOL) <= tx <= (cx0 + CELL_W + TOL) and (cy0 - TOL) <= ty <= (cy0 + CELL_H + TOL)

leaks = []
for p in params:
    fa = p.get('face_a') or {}
    fa_xmin = fa.get('face_x_min')

    bbox = compute_content_bbox(p)
    if not bbox:
        continue
    bx_min, bx_max, by_min, by_max = bbox
    content_w = bx_max - bx_min
    content_h = by_max - by_min

    ox = MARGIN - bx_min
    oy = MARGIN - by_min

    issues = []

    if content_w > CELL_W * 1.5:
        issues.append(f'BBOX_W_HUGE={content_w:.0f}u (bx_min={bx_min:.0f} bx_max={bx_max:.0f})')
    if content_h > CELL_H * 1.5:
        issues.append(f'BBOX_H_HUGE={content_h:.0f}u (by_min={by_min:.0f} by_max={by_max:.0f})')

    # Check which polys are removed by _filter_polys but are in bbox
    for key in ('all_concreto_polys', 'all_sarr35_polys', 'all_madeira_polys', 'all_sarr22_polys', 'panel_polys'):
        raw = p.get(key) or []
        if not raw:
            continue
        filtered = R._filter_polys(raw, fa)
        if len(raw) != len(filtered):
            removed = [x for x in raw if x not in filtered]
            for rem in removed:
                verts = rem.get('vertices', [])
                if not verts:
                    continue
                cx = sum(v[0] for v in verts)/len(verts)
                cy = sum(v[1] for v in verts)/len(verts)
                # Impact on bbox: does this poly contribute extreme x/y?
                vx = [v[0] for v in verts]
                vy = [v[1] for v in verts]
                if min(vx) <= bx_min + 1 or min(vy) <= by_min + 1:
                    issues.append(f'{key}: OUTSIDE poly drives bbox min ({min(vx):.0f},{min(vy):.0f}) centroid=({cx:.0f},{cy:.0f})')

    # Check sarr22_lines raw — do any drive bx_min/by_min?
    sarr22_raw = p.get('sarr22_lines') or []
    for sl in sarr22_raw:
        if abs(sl['x1'] - bx_min) < 2 or abs(sl['x2'] - bx_min) < 2:
            issues.append(f'sarr22_line sets bx_min={bx_min:.0f} (line x=[{sl["x1"]:.0f},{sl["x2"]:.0f}])')
            break

    # Check all_sarr35_lines raw
    sarr35_raw = p.get('all_sarr35_lines') or []
    for sl in sarr35_raw:
        if abs(sl['x1'] - bx_min) < 2 or abs(sl['x2'] - bx_min) < 2:
            fa_xmin_val = fa.get('face_x_min')
            if fa_xmin_val and (fa_xmin_val - bx_min) > 2000:
                issues.append(f'sarr35_line sets bx_min={bx_min:.0f} far from fa_xmin={fa_xmin_val:.0f} (line x=[{sl["x1"]:.0f},{sl["x2"]:.0f}])')
            break

    if issues:
        obra = p.get('obra', '')
        viga = p.get('viga', '')
        leaks.append((obra, viga, issues))

print(f'Vigas com problemas: {len(leaks)}')
for obra, viga, issues in leaks[:40]:
    print(f'  {obra}/{viga}:')
    for i in issues:
        print(f'    {i}')
