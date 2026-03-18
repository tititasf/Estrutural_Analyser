#!/usr/bin/env python3
"""Debug: analyze boundary alignment between _compute_section_boundary and face_a.y_min."""
import sys, io, json, os

# Prevent double-wrapping of stdout
if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

os.chdir('D:/Agente-cad-PYSIDE/ANALISE_LV')
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')

# Patch stdout before importing R to prevent its wrapper from failing
_orig_stdout = sys.stdout
import reconstruir_lv_dxf as R
sys.stdout = _orig_stdout

# Re-implement _compute_section_boundary locally to avoid double-import issue
SECTION_DETECT_THRESHOLD = 200
SECTION_GAP_TARGET = 30
PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json'

def _line_in_face(l, face, margin=8):
    xmin = face.get('face_x_min'); xmax = face.get('face_x_max')
    ymin = face.get('y_min');      ymax = face.get('y_max')
    if not all([xmin is not None, xmax is not None, ymin is not None, ymax is not None]):
        return True
    mx = (l['x1'] + l['x2']) / 2
    my = (l['y1'] + l['y2']) / 2
    return (xmin - margin <= mx <= xmax + margin and
            ymin - margin <= my <= ymax + margin)


def _compute_section_boundary(vdata):
    fa = vdata.get('face_a') or {}
    fa_ymin = fa.get('y_min')
    fa_ymax = fa.get('y_max')
    if fa_ymin is None or fa_ymax is None:
        return None

    all_ys = []

    for hl in (fa.get('face_hlines') or []):
        all_ys.append(hl['y'])
    for vl in (fa.get('face_vlines') or []):
        all_ys.extend([vl['y1'], vl['y2']])

    fb = vdata.get('face_b') or {}
    for hl in (fb.get('face_hlines') or []):
        all_ys.append(hl['y'])
    for vl in (fb.get('face_vlines') or []):
        all_ys.extend([vl['y1'], vl['y2']])

    for sl in (vdata.get('sarr22_lines') or []):
        cx = (sl['x1'] + sl['x2']) / 2
        cy = (sl['y1'] + sl['y2']) / 2
        if R._x_in_face_range(cx, fa) and R._y_in_face_range(cy, fa):
            all_ys.extend([sl['y1'], sl['y2']])

    for sl in (vdata.get('all_sarr35_lines') or []):
        if _line_in_face(sl, fa):
            all_ys.extend([sl['y1'], sl['y2']])

    for polys_key in ('all_concreto_polys', 'all_sarr35_polys', 'all_madeira_polys',
                      'all_sarr22_polys', 'panel_polys'):
        for poly in R._filter_polys(vdata.get(polys_key) or [], fa):
            for v in (poly.get('vertices') or []):
                if len(v) >= 2:
                    all_ys.append(v[1])

    for h in R._filter_hatches(vdata.get('hatches_data') or [], fa):
        for boundary in h.get('boundary_polys', []):
            for pt in (boundary or []):
                if len(pt) >= 2:
                    all_ys.append(pt[1])

    for dim in (vdata.get('cota_dims') or []):
        for yk in ('y1', 'y2', 'y3', 'text_y'):
            yv = dim.get(yk)
            if yv is not None:
                all_ys.append(yv)

    if len(all_ys) < 4:
        return None

    sorted_ys = sorted(set(round(y, 1) for y in all_ys))
    max_gap = 0
    gap_idx = -1
    for i in range(1, len(sorted_ys)):
        gap = sorted_ys[i] - sorted_ys[i - 1]
        if gap > max_gap:
            max_gap = gap
            gap_idx = i

    if max_gap < SECTION_DETECT_THRESHOLD:
        return None

    section_y_max = sorted_ys[gap_idx - 1]
    face_y_min = sorted_ys[gap_idx]

    return (face_y_min, section_y_max, max_gap)


def main():
    with open(PARAMS_FILE, encoding='utf-8') as f:
        params = json.load(f)

    no_compaction = 0
    compacted = 0
    boundary_misaligned = 0
    boundary_aligned = 0
    no_face_below = 0  # vigas without section elements, but gap detected
    details = []

    for p in params:
        fa = p.get('face_a') or {}
        sec_info = _compute_section_boundary(p)
        if sec_info is None:
            no_compaction += 1
        else:
            face_y_min_boundary, section_y_max, gap = sec_info
            fa_ymin = fa.get('y_min')
            compacted += 1
            if fa_ymin is not None:
                diff = face_y_min_boundary - fa_ymin
                if abs(diff) > 10:
                    boundary_misaligned += 1
                    details.append((p.get('_obra', p.get('obra', '')), p['viga'],
                                    fa_ymin, face_y_min_boundary, diff, gap,
                                    section_y_max))
                else:
                    boundary_aligned += 1

    print(f'Total vigas: {len(params)}')
    print(f'No compaction detected: {no_compaction}')
    print(f'Compaction detected: {compacted}')
    print(f'  Boundary aligned with face_a.y_min (diff<=10): {boundary_aligned}')
    print(f'  Boundary MISALIGNED (diff>10): {boundary_misaligned}')
    print()

    # Categorize misalignment direction
    above_face = sum(1 for d in details if d[4] > 0)
    below_face = sum(1 for d in details if d[4] < 0)
    print(f'Misaligned breakdown:')
    print(f'  boundary ABOVE face_a.y_min (diff>0): {above_face}')
    print(f'  boundary BELOW face_a.y_min (diff<0): {below_face}')
    print()

    print('Top 30 misaligned (sorted by abs(diff)):')
    for obra, viga, fa_ymin, boundary, diff, gap, sec_ymax in sorted(details, key=lambda x: -abs(x[4]))[:30]:
        print(f'  {obra:20s} {viga:20s}  fa.ymin={fa_ymin:8.1f}  boundary={boundary:8.1f}'
              f'  diff={diff:+7.1f}  gap={gap:6.1f}  sec_ymax={sec_ymax:8.1f}')


if __name__ == '__main__':
    main()
