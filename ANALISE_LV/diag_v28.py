#!/usr/bin/env python3
"""
Simula EXATAMENTE o translate_viga do código atual (v28) e conta elementos
que ainda renderizariam fora dos bounds reais da célula.
Usa a mesma lógica de ox/oy (top-left anchor).
"""
import json, sys
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')
import reconstruir_lv_dxf as R
from combinar_vigas_dxf import compute_content_bbox, _line_in_face, _dedup_lines

with open('D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json', encoding='utf-8') as f:
    params = json.load(f)

CELL_W, CELL_H, MARGIN = 2900, 1800, 80
LABEL_RESERVED = 70
CLIP_MARGIN = 50       # margem do _clip_line
HATCH_TOL   = 50       # tolerância vértice hatch
COTA_TOL    = 50       # tolerância pontos cota
CELL_STRICT = 5        # "verdadeiramente fora" = > 5u além da borda

# simulação do _clip_line
def clip_line(tx1, ty1, tx2, ty2, cx0, cy0, cw, ch, margin=CLIP_MARGIN):
    xmin, xmax = cx0-margin, cx0+cw+margin
    ymin, ymax = cy0-margin, cy0+ch+margin
    dx=tx2-tx1; dy=ty2-ty1
    t0,t1=0.,1.
    for p,q in [(-dx,tx1-xmin),(dx,xmax-tx1),(-dy,ty1-ymin),(dy,ymax-ty1)]:
        if abs(p)<1e-10:
            if q<0: return None
        else:
            t=q/p
            if p<0: t0=max(t0,t)
            else:   t1=min(t1,t)
    if t0>t1: return None
    return (tx1+t0*dx, ty1+t0*dy, tx1+t1*dx, ty1+t1*dy)

def in_cell_pt(tx, ty, cx0, cy0, cw, ch, tol):
    return (cx0-tol)<=tx<=(cx0+cw+tol) and (cy0-tol)<=ty<=(cy0+ch+tol)

def poly_centroid_in_cell(verts, ox, oy, cx0, cy0, cw, ch, tol=200):
    tv = [(v[0]+ox, v[1]+oy) for v in verts]
    cx = sum(v[0] for v in tv)/len(tv)
    cy = sum(v[1] for v in tv)/len(tv)
    return in_cell_pt(cx, cy, cx0, cy0, cw, ch, tol)

# contadores por tipo
leaks = {}      # tipo → lista de (obra/viga, coords)

def add_leak(t, obra, viga, msg):
    leaks.setdefault(t, []).append(f"{obra}/{viga}: {msg}")

# loop principal
col = row = 0
COLS = 12
for p in params:
    obra = p.get('obra','?'); viga = p.get('viga','?')

    bbox = compute_content_bbox(p)
    if not bbox: col+=1
    if col>=COLS: col=0; row+=1
    target_x = col*CELL_W; target_y = -row*CELL_H
    cx0,cy0,cw,ch = target_x, target_y, CELL_W, CELL_H

    if bbox:
        bx_min, _, _, by_max = bbox
        ox = target_x + MARGIN - bx_min
        oy = (target_y + CELL_H - LABEL_RESERVED) - by_max
    else:
        ins = p.get('insert') or {}
        ox = target_x + MARGIN - ins.get('x',0)
        oy = (target_y + CELL_H - LABEL_RESERVED) - ins.get('y',0)
        col+=1
        if col>=COLS: col=0; row+=1
        continue

    fa = p.get('face_a') or {}
    fb = p.get('face_b') or {}

    def pt_strict_out(tx, ty):
        """Ponto fora dos bounds REAIS da célula por mais de CELL_STRICT."""
        return not ((cx0-CELL_STRICT)<=tx<=(cx0+cw+CELL_STRICT) and
                    (cy0-CELL_STRICT)<=ty<=(cy0+ch+CELL_STRICT))

    def check_line_after_clip(tx1,ty1,tx2,ty2, etype):
        c = clip_line(tx1,ty1,tx2,ty2,cx0,cy0,cw,ch)
        if c is None: return
        # após clip, endpoints devem estar dentro
        for px,py in [c[:2], c[2:]]:
            if pt_strict_out(px, py):
                add_leak(etype, obra, viga, f"clip_endpoint=({px:.0f},{py:.0f})")

    # --- 1-3: face hlines/vlines (após _clip_line, não devem vazar)
    for face in (fa, fb):
        for hl in face.get('face_hlines',[]):
            check_line_after_clip(hl['x1']+ox, hl['y']+oy, hl['x2']+ox, hl['y']+oy, 'face_hline_post_clip')
        for vl in face.get('face_vlines',[]):
            check_line_after_clip(vl['x']+ox, vl['y1']+oy, vl['x']+ox, vl['y2']+oy, 'face_vline_post_clip')

    # --- 3b-6: polys com _poly_in_cell(tol=200) — verifica se centroide fica dentro mas vértice fica fora
    for etype, raw in [
        ('panel_poly',    R._filter_polys(p.get('panel_polys') or [], fa)),
        ('concreto_poly', R._filter_polys(p.get('all_concreto_polys') or [], fa)),
        ('sarr35_poly',   R._filter_polys(p.get('all_sarr35_polys') or [], fa)),
        ('madeira_poly',  R._filter_polys(p.get('all_madeira_polys') or [], fa)),
        ('sarr22_poly',   R._filter_polys(p.get('all_sarr22_polys') or [], fa)),
    ]:
        for poly in raw:
            verts = poly.get('vertices',[])
            if not verts: continue
            if not poly_centroid_in_cell(verts, ox, oy, cx0, cy0, cw, ch): continue
            # centroide OK → mas algum vértice vai fora?
            for vx,vy in [(v[0]+ox,v[1]+oy) for v in verts]:
                if pt_strict_out(vx, vy):
                    add_leak(f'{etype}_vtx', obra, viga, f"vtx=({vx:.0f},{vy:.0f})")
                    break

    # --- 5b: sarr35_lines (após _clip_line)
    raw35 = p.get('all_sarr35_lines') or []
    sarr35 = _dedup_lines([l for l in raw35 if _line_in_face(l,fa)] +
                          [l for l in raw35 if fb and _line_in_face(l,fb) and not _line_in_face(l,fa)])
    for sl in sarr35:
        check_line_after_clip(sl['x1']+ox,sl['y1']+oy,sl['x2']+ox,sl['y2']+oy,'sarr35_post_clip')

    # --- 11: hatches
    for h in R._filter_hatches(p.get('hatches_data') or [], fa):
        for boundary in h.get('boundary_polys',[]):
            if not boundary: continue
            tx_pts = [(pt[0]+ox,pt[1]+oy) for pt in boundary]
            ctr_x = sum(q[0] for q in tx_pts)/len(tx_pts)
            ctr_y = sum(q[1] for q in tx_pts)/len(tx_pts)
            if not in_cell_pt(ctr_x,ctr_y,cx0,cy0,cw,ch,150): continue
            # vertex check
            vertex_ok = all((cx0-HATCH_TOL)<=px<=(cx0+cw+HATCH_TOL) and
                            (cy0-HATCH_TOL)<=py<=(cy0+ch+HATCH_TOL)
                            for px,py in tx_pts)
            if not vertex_ok: continue
            # hatch passou — algum vértice ainda fora dos bounds reais?
            for px,py in tx_pts:
                if pt_strict_out(px, py):
                    add_leak('hatch_vtx_real', obra, viga, f"vtx=({px:.0f},{py:.0f})")
                    break

    # --- 12: cotas
    for dim in (p.get('cota_dims') or []):
        dt = {k:v for k,v in dim.items()}
        for k in ('x1','x2','x3','text_x','x_mid'):
            if k in dt: dt[k]+=ox
        for k in ('y1','y2','y3','text_y','y_mid'):
            if k in dt: dt[k]+=oy
        skip=False
        for xk in ('x1','x2','x3','text_x','x_mid'):
            xv=dt.get(xk)
            if xv is not None and not ((cx0-COTA_TOL)<=xv<=(cx0+cw+COTA_TOL)):
                skip=True; break
        if not skip:
            for yk in ('y1','y2','y3','text_y','y_mid'):
                yv=dt.get(yk)
                if yv is not None and not ((cy0-COTA_TOL)<=yv<=(cy0+ch+COTA_TOL)):
                    skip=True; break
        if skip: continue
        # cota passou — verifica se algum ponto está fora dos bounds reais
        for xk in ('x1','x2','x3','text_x','x_mid'):
            xv=dt.get(xk)
            if xv is not None and pt_strict_out(xv, dt.get(xk.replace('x','y'), cy0)):
                add_leak('cota_geo_real', obra, viga, f"x={xv:.0f}")
                break

    # --- 13b: sarr22_lines (após _clip_line)
    for sl in (p.get('sarr22_lines') or []):
        cx_l=(sl['x1']+sl['x2'])/2; cy_l=(sl['y1']+sl['y2'])/2
        if not (R._x_in_face_range(cx_l,fa) and R._y_in_face_range(cy_l,fa)): continue
        check_line_after_clip(sl['x1']+ox,sl['y1']+oy,sl['x2']+ox,sl['y2']+oy,'sarr22_post_clip')

    # --- 14: grade_lines (após _clip_line)
    grade = p.get('grade_entities') or {}
    for gl in grade.get('grade_lines',[]):
        check_line_after_clip(gl['x1']+ox,gl['y1']+oy,gl['x2']+ox,gl['y2']+oy,'grade_post_clip')

    # --- textos: panel_texts, panel_labels, titulo, continuacoes
    for etype, items, xk, yk in [
        ('panel_text', p.get('panel_texts_positioned') or [], 'x','y'),
        ('panel_label', p.get('panel_labels') or [], 'x','y'),
    ]:
        for it in items:
            tx_t, ty_t = it[xk]+ox, it[yk]+oy
            if not in_cell_pt(tx_t,ty_t,cx0,cy0,cw,ch,100): continue
            if pt_strict_out(tx_t, ty_t):
                add_leak(etype+'_real', obra, viga, f"({tx_t:.0f},{ty_t:.0f})")

    col+=1
    if col>=COLS: col=0; row+=1

# Resultado
print("=== DIAGNÓSTICO v28: elementos que ainda vazam da célula real ===\n")
total = sum(len(v) for v in leaks.values())
if total == 0:
    print("PERFEITO: zero elementos fora dos bounds reais!")
else:
    for etype, cases in sorted(leaks.items(), key=lambda x: -len(x[1])):
        print(f"  {etype}: {len(cases)} ocorrências")
        for ex in cases[:3]:
            print(f"    {ex}")
    print(f"\nTotal: {total} elementos ainda fora dos bounds reais")
