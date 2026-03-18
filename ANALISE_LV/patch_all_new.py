#!/usr/bin/env python3
"""
patch_all_new.py -- Applies zone_boundaries, labels, and synth_sarr patches
to a new batch of extracted viga params.

Reuses logic from patch_zone_boundaries.py, patch_labels.py, patch_synth_sarr.py
but operates on a specified input file instead of v3.

Usage:
  python patch_all_new.py --input params/viga_params_new_batch.json
"""
import sys, io, json, re, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path
from collections import defaultdict

OBRAS_BASE = Path(r'D:/Agente-cad-PYSIDE/DADOS-OBRAS')


def find_dxf(obra, dxf_name):
    for sub in ['Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
                'Fase-1_Ingestao']:
        p = OBRAS_BASE / obra / sub / dxf_name
        if p.exists():
            return p
    return None


# ============================================================
# PATCH A: Zone boundaries
# ============================================================
def patch_zone_boundaries(params):
    fixed_xl = fixed_xr = fixed_yb = 0
    for v in params:
        zone = v.get('zone')
        if not zone:
            continue
        fa = v.get('face_a') or {}

        if zone.get('x_left') is None:
            fa_xmin = fa.get('face_x_min')
            if fa_xmin is not None:
                zone['x_left'] = fa_xmin
                fixed_xl += 1
            elif zone.get('x_right') is not None and fa.get('total_width'):
                zone['x_left'] = zone['x_right'] - fa['total_width'] - 50
                fixed_xl += 1

        if zone.get('x_right') is None:
            fa_xmax = fa.get('face_x_max')
            if fa_xmax is not None:
                zone['x_right'] = fa_xmax
                fixed_xr += 1
            elif zone.get('x_left') is not None and fa.get('total_width'):
                zone['x_right'] = zone['x_left'] + fa['total_width'] + 50
                fixed_xr += 1

        if zone.get('y_bot') is None:
            fa_ymin = fa.get('y_min')
            if fa_ymin is not None:
                zone['y_bot'] = fa_ymin - 50
                fixed_yb += 1

    print(f'PATCH-A: zone_boundaries — x_left={fixed_xl}, x_right={fixed_xr}, y_bot={fixed_yb}')
    return params


# ============================================================
# PATCH B: Labels (face_labels, column_labels, continuacoes)
# ============================================================
RE_FACE_LABEL = re.compile(r'V\d+\.?[AB]', re.IGNORECASE)
RE_COL_LABEL  = re.compile(r'^C\d{1,3}$')
RE_CONT       = re.compile(r'CONT\.?', re.IGNORECASE)


def extract_texts_from_msp(msp):
    texts = []
    for e in msp:
        if e.dxftype() == 'TEXT':
            try:
                texts.append({
                    'text': e.dxf.text.strip(),
                    'x': round(e.dxf.insert.x, 1),
                    'y': round(e.dxf.insert.y, 1),
                    'layer': e.dxf.layer
                })
            except Exception:
                pass
        elif e.dxftype() == 'MTEXT':
            try:
                t = e.text.strip() if hasattr(e, 'text') else e.dxf.text.strip()
                ins = e.dxf.insert
                texts.append({
                    'text': t,
                    'x': round(ins.x, 1),
                    'y': round(ins.y, 1),
                    'layer': e.dxf.layer
                })
            except Exception:
                pass
    return texts


def labels_for_viga(all_texts, zone, existing_continuacoes):
    y_top = zone.get('y_top')
    y_bot = zone.get('y_bot')
    x_left = zone.get('x_left')
    x_right = zone.get('x_right')
    if y_top is None or y_bot is None:
        return [], [], []

    y_lo = y_bot - 200
    y_hi = y_top + 200
    x_lo = (x_left - 300) if x_left is not None else -1e9
    x_hi = (x_right + 300) if x_right is not None else 1e9

    face_labels = []
    col_labels = []
    cont_labels = []
    existing_cont_texts = set()
    for c in (existing_continuacoes or []):
        existing_cont_texts.add((round(c.get('x', 0), 0), round(c.get('y', 0), 0)))

    for t in all_texts:
        tx, ty = t['x'], t['y']
        if ty < y_lo or ty > y_hi or tx < x_lo or tx > x_hi:
            continue
        text = t['text']
        if RE_FACE_LABEL.search(text):
            face_labels.append({'text': text, 'x': tx, 'y': ty})
        elif RE_COL_LABEL.match(text):
            col_labels.append({'text': text, 'x': tx, 'y': ty})
        elif RE_CONT.search(text):
            key = (round(tx, 0), round(ty, 0))
            if key not in existing_cont_texts:
                cont_labels.append({'text': text, 'x': tx, 'y': ty})

    return face_labels, col_labels, cont_labels


def patch_labels(params):
    grupos = defaultdict(list)
    for v in params:
        key = (v.get('obra', ''), v.get('dxf_source', ''))
        grupos[key].append(v)

    total_face = total_col = total_cont = 0

    for (obra, dxf_src), vigas in grupos.items():
        dxf_path = find_dxf(obra, dxf_src)
        if not dxf_path:
            continue
        doc = ezdxf.readfile(str(dxf_path))
        all_texts = extract_texts_from_msp(doc.modelspace())

        for v in vigas:
            zone = v.get('zone', {})
            existing_cont = v.get('continuacoes', [])
            face_labels, col_labels, cont_labels = labels_for_viga(
                all_texts, zone, existing_cont)
            if face_labels:
                v['face_labels'] = face_labels
                total_face += len(face_labels)
            if col_labels:
                v['column_labels'] = col_labels
                total_col += len(col_labels)
            if cont_labels:
                v['continuacoes'] = (v.get('continuacoes') or []) + cont_labels
                total_cont += len(cont_labels)

    print(f'PATCH-B: labels — face={total_face}, column={total_col}, cont={total_cont}')
    return params


# ============================================================
# PATCH C: Synthetic sarrafos
# ============================================================
def parse_n_from_label(text):
    text = text.strip()
    m = re.match(r'^(\d+)\s*(1/2|½|pont|sarr)', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.match(r'^(\d+)', text)
    if m:
        n = int(m.group(1))
        if 2 <= n <= 30:
            return n
    return None


def assign_label_to_panel(lx, panel_positions):
    if not panel_positions:
        return None
    best_i, best_dist = 0, float('inf')
    for i, pp in enumerate(panel_positions):
        cx = (pp['x_start'] + pp['x_end']) / 2
        d = abs(lx - cx)
        if d < best_dist:
            best_dist = d
            best_i = i
    return best_i


def face_panel_y_range(face_data):
    y_min = face_data.get('y_min')
    y_max_full = face_data.get('y_max')
    hlines = face_data.get('face_hlines') or []
    face_w = face_data.get('total_width') or 0
    INSET_TOP = 3.0

    if y_min is None:
        return None, None
    if not hlines:
        return y_min, y_min + min(150, (y_max_full or y_min + 150) - y_min)

    threshold = max(face_w * 0.25, 50) if face_w > 0 else 50
    wide_hlines = [h for h in hlines if h.get('len', 0) >= threshold]

    if len(wide_hlines) >= 2:
        ys = sorted(set(h['y'] for h in wide_hlines))
        panel_y_min = min(ys)
        upper_ys = [y for y in ys if y > panel_y_min + 5]
        panel_y_max = (min(upper_ys) - INSET_TOP) if upper_ys else (panel_y_min + 70)
    elif wide_hlines:
        panel_y_min = min(h['y'] for h in wide_hlines)
        panel_y_max = panel_y_min + 70
    else:
        panel_y_min = y_min
        panel_y_max = y_min + 70

    if panel_y_max <= panel_y_min:
        panel_y_max = panel_y_min + 56
    return panel_y_min, panel_y_max


def generate_sarr_lines(x_start, x_end, y_min, y_max, n):
    if n <= 0 or y_max <= y_min or x_end <= x_start:
        return []
    span = y_max - y_min
    lines = []
    for i in range(1, n + 1):
        y = y_min + (span * i / (n + 1))
        lines.append({
            'x1': x_start + 1, 'y1': y,
            'x2': x_end - 1, 'y2': y,
            'layer': 'SARR_2.2x7',
        })
    return lines


def patch_synth_sarr(params):
    total_synth = total_vigas = 0

    for v in params:
        panel_labels = v.get('panel_labels') or []
        if not panel_labels:
            continue

        fa = v.get('face_a') or {}
        fb = v.get('face_b') or {}

        fa_y_min, fa_y_max = face_panel_y_range(fa)
        fb_y_min, fb_y_max = face_panel_y_range(fb) if fb.get('panel_count', 0) > 0 else (None, None)

        fa_panels = fa.get('panel_positions') or []
        fb_panels = (fb.get('panel_positions') or []) if fb.get('panel_count', 0) > 0 else []

        existing_sarr = v.get('sarr22_lines') or []

        def is_horiz_in_face(l, y_min, y_max):
            if y_min is None or y_max is None:
                return False
            dy = abs(l.get('y2', 0) - l.get('y1', 0))
            y = l.get('y1', 0)
            return dy < 2 and y_min <= y <= y_max

        horiz_in_fa = sum(1 for l in existing_sarr if is_horiz_in_face(l, fa_y_min, fa_y_max))
        horiz_in_fb = sum(1 for l in existing_sarr if is_horiz_in_face(l, fb_y_min, fb_y_max))

        synth_lines = []

        for pl in panel_labels:
            text = pl.get('text', '')
            lx = pl.get('x', 0)
            ly = pl.get('y', 0)
            n = parse_n_from_label(text)
            if n is None or n < 2:
                continue

            face_matched = panel_idx = None

            if fa_y_min is not None and fa_y_max is not None and fa_panels:
                y_center_a = (fa_y_min + fa_y_max) / 2
                if abs(ly - y_center_a) < (fa_y_max - fa_y_min) * 2:
                    if horiz_in_fa < n - 1:
                        face_matched = 'a'
                        panel_idx = assign_label_to_panel(lx, fa_panels)

            if face_matched is None and fb_y_min is not None and fb_y_max is not None and fb_panels:
                y_center_b = (fb_y_min + fb_y_max) / 2
                if abs(ly - y_center_b) < (fb_y_max - fb_y_min) * 2:
                    if horiz_in_fb < n - 1:
                        face_matched = 'b'
                        panel_idx = assign_label_to_panel(lx, fb_panels)

            if face_matched is None:
                if fa_y_min is not None and fa_y_max is not None and fa_panels and horiz_in_fa < n - 1:
                    face_matched = 'a'
                    panel_idx = assign_label_to_panel(lx, fa_panels)

            if face_matched is None or panel_idx is None:
                continue

            if face_matched == 'a':
                panels, y_min, y_max = fa_panels, fa_y_min, fa_y_max
            else:
                panels, y_min, y_max = fb_panels, fb_y_min, fb_y_max

            pp = panels[panel_idx]
            new_lines = generate_sarr_lines(pp['x_start'], pp['x_end'], y_min, y_max, n)
            if not new_lines:
                continue

            existing_in_panel = [
                l for l in existing_sarr + synth_lines
                if abs(l.get('y1', 0) - new_lines[0]['y1']) < 5 and
                   l.get('x1', 0) >= pp['x_start'] - 5 and l.get('x2', 0) <= pp['x_end'] + 5
            ]
            if existing_in_panel:
                continue

            synth_lines.extend(new_lines)

        if synth_lines:
            v['sarr22_lines'] = existing_sarr + synth_lines
            total_synth += len(synth_lines)
            total_vigas += 1

    print(f'PATCH-C: synth_sarr — {total_synth} lines in {total_vigas} vigas')
    return params


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Input params JSON')
    parser.add_argument('--output', help='Output params JSON (default: overwrites input)')
    args = parser.parse_args()

    input_path = Path(args.input)
    params = json.loads(input_path.read_text(encoding='utf-8'))
    print(f'Loaded: {input_path} ({len(params)} vigas)')

    params = patch_zone_boundaries(params)
    params = patch_labels(params)
    params = patch_synth_sarr(params)

    out_path = Path(args.output) if args.output else input_path
    out_path.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nSaved: {out_path}')


if __name__ == '__main__':
    main()
