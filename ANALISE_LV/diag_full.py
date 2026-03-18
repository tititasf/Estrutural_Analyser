#!/usr/bin/env python3
"""Diagnóstico completo: simula translate_viga e detecta TUDO que sai da célula."""
import json, sys
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R
from combinar_vigas_dxf import compute_content_bbox, _line_in_face

with open('D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json', encoding='utf-8') as f:
    params = json.load(f)

CELL_W, CELL_H, MARGIN = 2900, 1800, 80

# Estatísticas por tipo de elemento
leak_counts = {}
leak_examples = {}

for p in params:
    fa = p.get('face_a') or {}
    bbox = compute_content_bbox(p)
    if not bbox:
        continue
    bx_min, bx_max, by_min, by_max = bbox
    cx0, cy0 = 0, 0  # target simples
    ox = MARGIN - bx_min
    oy = MARGIN - by_min

    cell = (cx0, cy0, CELL_W, CELL_H)
    TOL_LINE = 100
    TOL_PT   = 150
    TOL_POLY = 200

    def _pt_ok(tx, ty, tol=TOL_PT):
        return (cx0-tol) <= tx <= (cx0+CELL_W+tol) and (cy0-tol) <= ty <= (cy0+CELL_H+tol)

    def _line_ok(tx1, ty1, tx2, ty2, tol=TOL_LINE):
        return _pt_ok(tx1, ty1, tol) or _pt_ok(tx2, ty2, tol)

    def _poly_ok(verts, tol=TOL_POLY):
        if not verts: return True
        tv = [(v[0]+ox, v[1]+oy) for v in verts]
        cx = sum(v[0] for v in tv)/len(tv)
        cy = sum(v[1] for v in tv)/len(tv)
        return _pt_ok(cx, cy, tol)

    def _pt_out(tx, ty, tol=TOL_PT):
        """Checar se ponto está fora dos bounds STRICT (sem tolerância)."""
        return not ((cx0-5) <= tx <= (cx0+CELL_W+5) and (cy0-5) <= ty <= (cy0+CELL_H+5))

    def _line_out(tx1, ty1, tx2, ty2):
        """Linha passa pelo filtro mas algum endpoint fica fora do cell real?"""
        # Passou o filtro _line_ok — verificar se algum endpoint está fora do cell real
        return _pt_out(tx1, ty1) or _pt_out(tx2, ty2)

    obra = p.get('obra',''); viga = p.get('viga','')
    key = f"{obra}/{viga}"

    def report(etype, coords_str):
        leak_counts[etype] = leak_counts.get(etype, 0) + 1
        if etype not in leak_examples:
            leak_examples[etype] = []
        if len(leak_examples[etype]) < 5:
            leak_examples[etype].append(f"{key}: {coords_str}")

    # --- Face hlines/vlines (seções 1-3) ---
    for face in (fa, p.get('face_b') or {}):
        for hl in face.get('face_hlines', []):
            tx1, ty = hl['x1']+ox, hl['y']+oy; tx2 = hl['x2']+ox
            if _line_ok(tx1, ty, tx2, ty) and _line_out(tx1, ty, tx2, ty):
                report('face_hline_partial', f"x=[{tx1:.0f},{tx2:.0f}] y={ty:.0f}")
        for vl in face.get('face_vlines', []):
            tx, ty1 = vl['x']+ox, vl['y1']+oy; ty2 = vl['y2']+oy
            if _line_ok(tx, ty1, tx, ty2) and _line_out(tx, ty1, tx, ty2):
                report('face_vline_partial', f"x={tx:.0f} y=[{ty1:.0f},{ty2:.0f}]")

    # --- Polys (3b, 4, 5, 6) ---
    for etype, raw in [
        ('panel_poly', R._filter_polys(p.get('panel_polys') or [], fa)),
        ('concreto_poly', R._filter_polys(p.get('all_concreto_polys') or [], fa)),
        ('sarr35_poly', R._filter_polys(p.get('all_sarr35_polys') or [], fa)),
        ('madeira_poly', R._filter_polys(p.get('all_madeira_polys') or [], fa)),
        ('sarr22_poly', R._filter_polys(p.get('all_sarr22_polys') or [], fa)),
    ]:
        for poly in raw:
            verts = poly.get('vertices', [])
            if not verts: continue
            if _poly_ok(verts):
                tv = [(v[0]+ox, v[1]+oy) for v in verts]
                for vx, vy in tv:
                    if _pt_out(vx, vy, tol=5):
                        report(f'{etype}_vertex_out', f"vertex=({vx:.0f},{vy:.0f})")
                        break

    # --- sarr35_lines (5b) ---
    raw_sarr35 = p.get('all_sarr35_lines') or []
    for sl in raw_sarr35:
        if not _line_in_face(sl, fa): continue
        tx1,ty1 = sl['x1']+ox, sl['y1']+oy; tx2,ty2 = sl['x2']+ox, sl['y2']+oy
        if _line_ok(tx1,ty1,tx2,ty2) and _line_out(tx1,ty1,tx2,ty2):
            report('sarr35_line_partial', f"x=[{tx1:.0f},{tx2:.0f}]")

    # --- sarr22_lines (13b) ---
    for sl in (p.get('sarr22_lines') or []):
        cx_l = (sl['x1']+sl['x2'])/2; cy_l = (sl['y1']+sl['y2'])/2
        if not (R._x_in_face_range(cx_l, fa) and R._y_in_face_range(cy_l, fa)): continue
        tx1,ty1 = sl['x1']+ox, sl['y1']+oy; tx2,ty2 = sl['x2']+ox, sl['y2']+oy
        if _line_ok(tx1,ty1,tx2,ty2) and _line_out(tx1,ty1,tx2,ty2):
            report('sarr22_line_partial', f"x=[{tx1:.0f},{tx2:.0f}]")

    # --- hatches (11) ---
    for h in R._filter_hatches(p.get('hatches_data') or [], fa):
        for boundary in h.get('boundary_polys', []):
            if not boundary: continue
            tx_pts = [(pt[0]+ox, pt[1]+oy) for pt in boundary]
            ctr_x = sum(pt[0] for pt in tx_pts)/len(tx_pts)
            ctr_y = sum(pt[1] for pt in tx_pts)/len(tx_pts)
            if not _pt_ok(ctr_x, ctr_y, TOL_PT): continue
            for vx, vy in tx_pts:
                if _pt_out(vx, vy, tol=5):
                    report('hatch_vertex_out', f"vertex=({vx:.0f},{vy:.0f}) ctr=({ctr_x:.0f},{ctr_y:.0f})")
                    break

    # --- cotas (12) ---
    for dim in (p.get('cota_dims') or []):
        tx = (dim.get('text_x') or dim.get('x_mid') or dim.get('x1') or 0) + ox
        ty = (dim.get('text_y') or dim.get('y_mid') or dim.get('y1') or 0) + oy
        if not _pt_ok(tx, ty, TOL_PT): continue
        # check all geometry points
        for key2 in ('x1','x2','x3'):
            if key2 in dim:
                txx = dim[key2]+ox
                tyy = dim.get(key2.replace('x','y'), dim.get('y1',0))+oy
                if _pt_out(txx, tyy, tol=5):
                    report('cota_geo_out', f"pt=({txx:.0f},{tyy:.0f})")
                    break

    # --- grade_lines (14) ---
    grade = p.get('grade_entities') or {}
    for gl in grade.get('grade_lines', []):
        tx1,ty1 = gl['x1']+ox, gl['y1']+oy; tx2,ty2 = gl['x2']+ox, gl['y2']+oy
        if _line_ok(tx1,ty1,tx2,ty2) and _line_out(tx1,ty1,tx2,ty2):
            report('grade_line_partial', f"x=[{tx1:.0f},{tx2:.0f}]")

# --- Resultado ---
print("=== Elementos que PASSAM o filtro mas têm pontos fora da célula ===")
print(f"(célula: x=[0,{CELL_W}] y=[0,{CELL_H}])\n")
total = sum(leak_counts.values())
for etype, count in sorted(leak_counts.items(), key=lambda x: -x[1]):
    print(f"  {etype}: {count} ocorrências")
    for ex in leak_examples[etype][:3]:
        print(f"    ex: {ex}")
print(f"\nTotal: {total} elementos com vértice fora do cell real")
