#!/usr/bin/env python3
"""Debug: for each problematic cell in v36, determine the root cause."""
import sys, io, json, os, math
if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

os.chdir('D:/Agente-cad-PYSIDE/ANALISE_LV')
sys.path.insert(0, '.')
_orig = sys.stdout
import reconstruir_lv_dxf as R
sys.stdout = _orig
from collections import defaultdict

import combinar_vigas_dxf as C

with open(C.PARAMS_FILE, encoding='utf-8') as f:
    params = json.load(f)

# Reproduce deduplication from build_combined
_groups = defaultdict(list)
for p in params:
    ins = p.get('insert') or {}
    p['_obra'] = p.get('obra') or 'desconhecida'
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

_name_tally = defaultdict(list)
for p in deduped:
    _name_tally[(p.get('_obra',''), p['viga'])].append(p)
for (obra, viga), vs in _name_tally.items():
    if len(vs) > 1:
        for i, v in enumerate(vs):
            v['_viga_label'] = f'{viga}_{chr(ord("a")+i)}'
    else:
        vs[0]['_viga_label'] = vs[0]['viga']

CELL_W = 2900
CELL_H = 1800
MARGIN = 80
COLS = 12

# For each viga, compute what its problematic output dimensions would be
categories = defaultdict(list)

for idx, p in enumerate(deduped):
    col = idx % COLS
    row = idx // COLS

    fa = p.get('face_a') or {}
    fa_ymin = fa.get('y_min')
    fa_ymax = fa.get('y_max')

    bbox = C.compute_content_bbox(p)
    sec_info = C._compute_section_boundary(p)

    target_x = col * CELL_W
    target_y = -row * CELL_H
    CONTENT_TOP_Y = target_y + CELL_H - 70

    if not bbox:
        continue

    bx_min, bx_max, by_min, by_max = bbox
    ox = target_x + MARGIN - bx_min
    oy = CONTENT_TOP_Y - by_max

    content_height = by_max - by_min
    cell_avail = CELL_H - 70  # 1730
    overflow = content_height - cell_avail

    # Compute actual rendered content range including elements NOT in bbox
    all_rendered_ys = []

    # Collect ALL elements that translate_viga would render, with their translated Y
    if sec_info:
        boundary, sec_ymax, gap = sec_info
        shift = gap - C.SECTION_GAP_TARGET
    else:
        boundary = None
        shift = 0

    def _sy(y_orig):
        if boundary is None:
            return oy
        if y_orig < boundary:
            return oy + shift
        return oy

    def _ty(y_orig):
        return y_orig + _sy(y_orig)

    # face_a hlines/vlines
    for hl in (fa.get('face_hlines') or []):
        all_rendered_ys.append(_ty(hl['y']))
    for vl in (fa.get('face_vlines') or []):
        all_rendered_ys.extend([_ty(vl['y1']), _ty(vl['y2'])])

    # face_b
    fb = p.get('face_b') or {}
    for hl in (fb.get('face_hlines') or []):
        all_rendered_ys.append(_ty(hl['y']))
    for vl in (fb.get('face_vlines') or []):
        all_rendered_ys.extend([_ty(vl['y1']), _ty(vl['y2'])])

    # sarr22_lines
    for sl in (p.get('sarr22_lines') or []):
        cx = (sl['x1'] + sl['x2']) / 2
        cy = (sl['y1'] + sl['y2']) / 2
        if R._x_in_face_range(cx, fa) and R._y_in_face_range(cy, fa):
            all_rendered_ys.extend([_ty(sl['y1']), _ty(sl['y2'])])

    # sarr35_lines
    for sl in (p.get('all_sarr35_lines') or []):
        if C._line_in_face(sl, fa):
            all_rendered_ys.extend([_ty(sl['y1']), _ty(sl['y2'])])

    # Polys
    for pk in ('all_concreto_polys', 'all_sarr35_polys', 'all_madeira_polys',
               'all_sarr22_polys', 'panel_polys'):
        for poly in R._filter_polys(p.get(pk) or [], fa):
            for v in (poly.get('vertices') or []):
                if len(v) >= 2:
                    all_rendered_ys.append(_ty(v[1]))

    # Hatches
    for h in R._filter_hatches(p.get('hatches_data') or [], fa):
        for bd in h.get('boundary_polys', []):
            for pt in (bd or []):
                if len(pt) >= 2:
                    all_rendered_ys.append(_ty(pt[1]))

    # Cotas
    for dim in (p.get('cota_dims') or []):
        for yk in ('y1', 'y2', 'y3', 'text_y'):
            yv = dim.get(yk)
            if yv is not None:
                all_rendered_ys.append(_ty(yv))

    # Grade
    ge = p.get('grade_entities') or {}
    for gl in ge.get('grade_lines', []):
        all_rendered_ys.extend([_ty(gl['y1']), _ty(gl['y2'])])
    for gp in ge.get('grade_polys', []):
        for v in gp.get('vertices', []):
            if len(v) >= 2:
                all_rendered_ys.append(_ty(v[1]))
    for gh in ge.get('grade_hatches', []):
        for bd in gh.get('boundary_polys', []):
            for pt in (bd or []):
                if len(pt) >= 2:
                    all_rendered_ys.append(_ty(pt[1]))
    for gt in ge.get('grade_texts', []):
        all_rendered_ys.append(_ty(gt['y']))

    if not all_rendered_ys:
        continue

    rendered_ymin = min(all_rendered_ys)
    rendered_ymax = max(all_rendered_ys)
    rendered_height = rendered_ymax - rendered_ymin

    # Find gaps in rendered output
    unique_rys = sorted(set(round(y, 1) for y in all_rendered_ys))
    max_gap = 0
    for i in range(1, len(unique_rys)):
        g = unique_rys[i] - unique_rys[i-1]
        if g > max_gap:
            max_gap = g

    obra = p.get('_obra', '')
    label = p.get('_viga_label', p['viga'])

    if max_gap > 250:
        if sec_info:
            categories['compacted_but_still_gapped'].append(
                (col, row, obra, label, content_height, rendered_height, max_gap,
                 boundary, fa_ymin, shift))
        else:
            categories['no_compaction_gapped'].append(
                (col, row, obra, label, content_height, rendered_height, max_gap,
                 None, fa_ymin, 0))


print(f'=== DIAGNOSIS OF REMAINING PROBLEMS ===')
print()

for cat, items in sorted(categories.items()):
    print(f'--- {cat}: {len(items)} vigas ---')
    for col, row, obra, label, ch, rh, mg, bnd, fa_ym, sh in sorted(items)[:15]:
        bnd_str = f'bnd={bnd:.0f}' if bnd else 'no_compaction'
        fa_str = f'fa_ym={fa_ym:.0f}' if fa_ym else 'no_fa'
        diff_str = f'diff={bnd-fa_ym:.0f}' if bnd and fa_ym else ''
        print(f'  [{col},{row}] {obra:20s} {label:20s}  '
              f'bbox_h={ch:.0f}  rendered_h={rh:.0f}  max_gap={mg:.0f}  '
              f'{bnd_str}  {fa_str}  {diff_str}')
    if len(items) > 15:
        print(f'  ... and {len(items) - 15} more')
    print()

# Summary
total = sum(len(v) for v in categories.values())
print(f'Total vigas with rendered gap > 250: {total}')
for cat, items in sorted(categories.items()):
    print(f'  {cat}: {len(items)}')
