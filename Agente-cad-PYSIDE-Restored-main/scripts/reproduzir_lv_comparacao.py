#!/usr/bin/env python3
"""
reproduzir_lv_comparacao.py — Reprodução + Comparação de vigas STOG v3
====================================================================
Usa parâmetros extraídos de viga_params.json para gerar DXFs via
gerar_lv_dxf_stog.py e criar comparações lado a lado com PNGs STOG originais.

v3: Fix compound sections, add reaproveitamento hatching, better panel logic.

Uso:
  python scripts/reproduzir_lv_comparacao.py --max 20
  python scripts/reproduzir_lv_comparacao.py --vigas V101A-V115A,V1
"""
import sys, io, json, re, os, argparse, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

# Import generator functions
sys.path.insert(0, str(Path(__file__).parent))
from gerar_lv_dxf_stog import (
    setup_doc, draw_viga_lateral, draw_lv_face, draw_section_detail,
    LAYERS, GAP_ROW_LV, NOM_ABOVE, DIM_TOTAL_BELOW, DIM_H_RIGHT,
    SECT_W, SECT_GAP
)

PARAMS_FILE = Path('D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json')
STOG_PNG_DIR = Path('D:/Agente-cad-PYSIDE/ANALISE_LV/vigas_png')
OUTPUT_DIR = Path('D:/Agente-cad-PYSIDE/ANALISE_LV/comparacao')


def parse_secao(secao_str):
    """Parse section string, handling compound formats like (19x55/120).
    For compound BxH1/H2, use max(H1, H2) as the total height.
    """
    b = h = 0
    m = re.search(r'\((\d+)[xX](\d+)(?:/(\d+))?', secao_str)
    if m:
        b = int(m.group(1))
        h2 = int(m.group(2))
        h3 = int(m.group(3)) if m.group(3) else 0
        h = max(h2, h3) if h3 > 0 else h2
    return b, h


def filter_real_panel_widths(dims):
    """Filter DIMENSION values to keep only plausible individual panel widths.
    STOG panels: 40-300cm (common: 88.5, 99, 100, 122, 130, 131, 155, 156, 160, 220, 224, 244).
    Exclude totals (>300) and tiny measurements (<40).
    """
    if not dims:
        return []
    panels = [round(d, 1) for d in dims if 40 <= d <= 300]
    if not panels:
        mx = max(dims) if dims else 0
        panels = [round(d, 1) for d in dims if 40 <= d < mx * 0.9]
    return sorted(panels)


def smart_panel_selection(panel_widths, total_width):
    """Select best subset of panels that sum close to total_width.
    Handles over-extraction (duplicates, mixed faces, compound vigas)."""
    if not panel_widths:
        return panel_widths
    if total_width <= 0:
        return panel_widths[:6]  # cap at 6 if no total

    # Remove values >= total_width (those are totals, not panels)
    candidates = [w for w in panel_widths if w < total_width * 0.95]
    if not candidates:
        return panel_widths[:4]

    # If sum is already close to total, return as-is
    s = sum(candidates)
    if 0.85 <= s / total_width <= 1.15:
        return candidates

    # Sum too large — greedily select subset summing to total_width
    # Try from largest panels first
    candidates_desc = sorted(candidates, reverse=True)
    selected = []
    remaining = total_width
    for w in candidates_desc:
        if w <= remaining + 5:  # 5cm tolerance
            selected.append(w)
            remaining -= w
        if remaining < 20:
            break

    if selected and abs(sum(selected) - total_width) / total_width < 0.20:
        return sorted(selected)

    # Fallback: take unique values up to total_width
    unique = sorted(set(candidates))
    sel2 = []
    rem2 = total_width
    for w in sorted(unique, reverse=True):
        if w <= rem2 + 5:
            sel2.append(w)
            rem2 -= w
        if rem2 < 20:
            break
    if sel2:
        return sorted(sel2)

    return candidates[:6]


def split_panels_for_faces(all_widths, fa_specific, fb_specific, fa_total=0, fb_total=0):
    """Smart split: use face-specific when available, otherwise divide all_widths.
    Uses total_width to validate and cap panel selection.
    """
    fa = filter_real_panel_widths(fa_specific)
    fb = filter_real_panel_widths(fb_specific)
    all_filtered = filter_real_panel_widths(all_widths)

    # Apply total_width validation to each face
    if fa and fa_total > 0:
        fa = smart_panel_selection(fa, fa_total)
    if fb and fb_total > 0:
        fb = smart_panel_selection(fb, fb_total)

    if fa and fb:
        return fa, fb

    if not all_filtered:
        return fa or [244], fb or [244]

    # If only one face has data, use for both (with total validation)
    if fa and not fb:
        fb_panels = smart_panel_selection(fa, fb_total) if fb_total > 0 else fa
        return fa, fb_panels
    if fb and not fa:
        fa_panels = smart_panel_selection(fb, fa_total) if fa_total > 0 else fb
        return fa_panels, fb

    # Neither face specific — use all_filtered with total validation
    fa_result = smart_panel_selection(all_filtered, fa_total) if fa_total > 0 else all_filtered
    fb_result = smart_panel_selection(all_filtered, fb_total) if fb_total > 0 else all_filtered
    return fa_result, fb_result


def params_to_panels(panel_widths, h, add_reaprov_hatch=False):
    """Convert extracted panel widths to generator panel format."""
    if not panel_widths:
        return []
    return [{'width': w, 'height1': 0, 'height2': 0, 'grade_h1': 0, 'grade_h2': 0}
            for w in panel_widths]


def add_reaprov_hatching(msp, x0, y0, panels, h, panel_reaprov=None):
    """Add reaproveitamento hatching as explicit diagonal LINE entities.
    ANSI31 hatch pattern renders too faintly in matplotlib backend.
    Drawing actual diagonal lines at 45° matches STOG visual style.
    Spacing 8cm between lines — visible stripes at render scale.

    panel_reaprov: list of bools per panel (from v3 extraction).
    If None or all True, hatches all panels (legacy behavior).
    """
    spacing = 8.0
    attribs = {'layer': 'Reaproveitamento', 'color': 30}

    x_cur = x0
    for idx, p in enumerate(panels):
        pw = p['width']

        # Skip panels not marked for reaproveitamento (v3 per-panel flags)
        if panel_reaprov and idx < len(panel_reaprov):
            if not panel_reaprov[idx]:
                x_cur += pw
                continue

        # Draw 45deg diagonal lines sweeping across the panel
        total_span = pw + h
        n_lines = int(total_span / spacing) + 1
        for i in range(n_lines):
            d = i * spacing
            x_start = x_cur + d
            y_start = y0
            x_end = x_start - h
            y_end = y0 + h

            if x_end < x_cur:
                dy = x_cur - x_end
                x_end = x_cur
                y_end = y0 + h - dy
            if x_start > x_cur + pw:
                dy = x_start - (x_cur + pw)
                x_start = x_cur + pw
                y_start = y0 + dy

            if x_start >= x_cur and x_end >= x_cur and y_start <= y_end:
                msp.add_line((x_start, y_start), (x_end, y_end), dxfattribs=attribs)

        x_cur += pw


def generate_viga_dxf(params):
    """Generate a single-viga DXF from extracted params."""
    doc = setup_doc()
    msp = doc.modelspace()

    # Ensure Reaproveitamento layer exists with visible color
    if 'Reaproveitamento' not in doc.layers:
        doc.layers.add('Reaproveitamento', color=30)  # dark orange/brown — visible hatching

    viga_name = params['viga']

    # Parse section — handles compound formats like (19x108/138)
    b_alma_raw = params.get('b_alma', 0)
    h_total_raw = params.get('h_total', 0)
    if b_alma_raw <= 0 or h_total_raw <= 0:
        b_parsed, h_parsed = parse_secao(params.get('secao', ''))
        b_alma_raw = b_parsed or 19
        h_total_raw = h_parsed or 60

    b_alma = b_alma_raw
    h_total = h_total_raw
    h_section = h_total // 2 if h_total else 30

    fa = params.get('face_a', {})
    fb = params.get('face_b', {})

    # === FACE HEIGHTS — prefer extracted v3 heights, fallback to STOG formula ===
    h_formula_A = h_section + 4 if h_section > 0 else 34
    h_formula_B = max(h_section - 10, 10) if h_section > 0 else 20
    fa_height = fa.get('height', 0)
    fb_height = fb.get('height', 0)
    # Use extracted height if plausible (within ±40% of formula and >10cm)
    h_A = round(fa_height) if (fa_height > 10 and
                                0.60 * h_formula_A <= fa_height <= 1.40 * h_formula_A) else h_formula_A
    h_B = round(fb_height) if (fb_height > 10 and
                                0.60 * h_formula_B <= fb_height <= 1.40 * h_formula_B) else h_formula_B

    # === PANEL WIDTHS — Smart split between faces ===
    all_dims = params.get('all_cota_h_dims', [])
    fa_total = fa.get('total_width', 0)
    fb_total = fb.get('total_width', 0)
    fa_widths, fb_widths = split_panels_for_faces(
        all_dims,
        fa.get('panel_widths', []),
        fb.get('panel_widths', []),
        fa_total=fa_total,
        fb_total=fb_total,
    )

    # Synthesize from total_width if still empty
    if not fa_widths and fa_total > 30:
        fa_widths = synthesize_panels(fa_total)
    if not fb_widths and fb_total > 30:
        fb_widths = synthesize_panels(fb_total)

    # Last resort
    if not fa_widths:
        fa_widths = [244]
    if not fb_widths:
        fb_widths = [244]

    # Laje detection
    laje_pos = params.get('laje', {}).get('position', 'none')
    laje_sup = 7.0 if laje_pos in ('superior', 'central') else 0
    laje_inf = 7.0 if laje_pos in ('inferior', 'central') else 0

    panels_A = params_to_panels(fa_widths, h_A)
    panels_B = params_to_panels(fb_widths, h_B)

    # Draw the viga
    x_max, y_min = draw_viga_lateral(
        msp,
        x_origin=0.0,
        y_top=0.0,
        viga_nome=viga_name,
        h_A=h_A,
        h_B=h_B,
        b=b_alma,
        h_section=h_section,
        b_alma=b_alma,
        panels_A=panels_A,
        panels_B=panels_B,
        laje_sup=laje_sup,
        laje_inf=laje_inf,
    )

    # === ADD REAPROVEITAMENTO HATCHING ===
    # Use per-panel reaprov flags from v3 extraction when available
    has_reaprov = params.get('hatches', {}).get('reaproveitamento', 0) > 0
    has_ansi31 = params.get('hatches', {}).get('ansi31', 0) > 0
    reaprov_str = params.get('reaprov', '')
    fa_reaprov = fa.get('panel_reaprov', [])
    fb_reaprov = fb.get('panel_reaprov', [])

    # Determine if any reaprov exists
    has_any_reaprov = (has_reaprov or has_ansi31 or reaprov_str
                       or any(fa_reaprov) or any(fb_reaprov))

    if has_any_reaprov:
        # Compute face positions (same logic as draw_viga_lateral)
        sect_total = max(SECT_W + SECT_GAP, int(b_alma) + 178)
        x_A = sect_total
        comp_A = sum(p['width'] for p in panels_A)
        comp_B = sum(p['width'] for p in panels_B)
        comprimento = max(comp_A, comp_B, 1.0)
        x_B = x_A + comprimento + 50  # GAP_AB = 50
        y0_A = -h_A
        y0_B = -h_B

        # Use per-panel flags if available, otherwise hatch all panels
        add_reaprov_hatching(msp, x_A, y0_A, panels_A, h_A,
                             panel_reaprov=fa_reaprov if fa_reaprov else None)
        add_reaprov_hatching(msp, x_B, y0_B, panels_B, h_B,
                             panel_reaprov=fb_reaprov if fb_reaprov else None)

    return doc, {
        'x_max': x_max,
        'y_min': y_min,
        'h_A': h_A,
        'h_B': h_B,
        'fa_widths': fa_widths,
        'fb_widths': fb_widths,
        'laje_sup': laje_sup,
        'laje_inf': laje_inf,
    }


def synthesize_panels(total_width):
    """Synthesize panel widths from total width using STOG standard modules."""
    if total_width <= 0:
        return []
    widths = []
    remaining = total_width
    while remaining > 0:
        if remaining >= 244:
            widths.append(244)
            remaining -= 244
        elif remaining >= 122:
            widths.append(122)
            remaining -= 122
        elif remaining > 30:
            widths.append(round(remaining))
            remaining = 0
        else:
            if widths:
                widths[-1] += remaining
            else:
                widths.append(round(remaining))
            remaining = 0
    return widths


def render_generated_png(doc, gen_info, output_path, title='', dpi=150):
    """Render generated DXF to PNG."""
    msp = doc.modelspace()

    x_max = gen_info['x_max']
    y_min = gen_info['y_min']

    w = x_max + 50
    h = abs(y_min) + 50
    if w <= 0 or h <= 0:
        return False

    aspect = w / h
    fig_w = min(30, max(10, aspect * 6))
    fig_h = fig_w / aspect
    fig_h = min(16, max(3, fig_h))

    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), facecolor='white')
    ax.set_facecolor('white')

    ctx = RenderContext(doc)
    be = MatplotlibBackend(ax)
    Frontend(ctx, be).draw_layout(msp, finalize=True)

    margin_x = w * 0.02
    margin_y = h * 0.02
    ax.set_xlim(-50 - margin_x, x_max + margin_x)
    ax.set_ylim(y_min - margin_y, 50 + margin_y)
    ax.set_aspect('equal', adjustable='box')

    if title:
        ax.set_title(title, fontsize=8, pad=3, color='#333')
    ax.axis('off')
    plt.tight_layout(pad=0.3)
    plt.savefig(str(output_path), dpi=dpi, bbox_inches='tight',
                facecolor='white', pad_inches=0.1)
    plt.close(fig)
    return True


def create_comparison(stog_png_path, gen_png_path, output_path, title=''):
    """Create side-by-side comparison image with matched scaling."""
    fig = plt.figure(figsize=(28, 10), facecolor='white')
    gs = GridSpec(1, 2, figure=fig, wspace=0.05)

    # Left: STOG Original
    ax1 = fig.add_subplot(gs[0, 0])
    if stog_png_path.exists():
        img = plt.imread(str(stog_png_path))
        ax1.imshow(img)
    ax1.set_title('STOG ORIGINAL', fontsize=12, fontweight='bold', color='#2d5f2d')
    ax1.axis('off')

    # Right: Generated
    ax2 = fig.add_subplot(gs[0, 1])
    if gen_png_path.exists():
        img = plt.imread(str(gen_png_path))
        ax2.imshow(img)
    ax2.set_title('GERADO (nosso sistema)', fontsize=12, fontweight='bold', color='#2d2d5f')
    ax2.axis('off')

    fig.suptitle(title, fontsize=14, fontweight='bold', y=0.98)
    plt.savefig(str(output_path), dpi=120, bbox_inches='tight',
                facecolor='white', pad_inches=0.2)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description='Reproduzir vigas STOG e comparar v3')
    parser.add_argument('--params', default=str(PARAMS_FILE))
    parser.add_argument('--stog-png', default=str(STOG_PNG_DIR))
    parser.add_argument('--output', default=str(OUTPUT_DIR))
    parser.add_argument('--max', type=int, default=999)
    parser.add_argument('--vigas', help='Comma-separated viga names')
    parser.add_argument('--dpi', type=int, default=150)
    args = parser.parse_args()

    output_dir = Path(args.output)
    gen_dir = output_dir / 'gerados'
    comp_dir = output_dir / 'comparacao'
    gen_dir.mkdir(parents=True, exist_ok=True)
    comp_dir.mkdir(parents=True, exist_ok=True)

    with open(args.params, 'r', encoding='utf-8') as f:
        all_params = json.load(f)

    # Filter
    if args.vigas:
        names = set(args.vigas.split(','))
        targets = [p for p in all_params if p['viga'] in names]
    else:
        targets = select_diverse(all_params, args.max)

    print(f'=== REPRODUCAO + COMPARACAO v3 === {len(targets)} vigas')
    print(f'Output: {output_dir}')

    total_ok = total_fail = 0

    for i, params in enumerate(targets):
        viga_name = params['viga']
        obra = params['obra']
        dxf_src = params.get('dxf_source', '')[:30]
        safe_name = re.sub(r'[^\w\-]', '_', f"{obra}__{dxf_src}__{viga_name}")

        print(f'\n[{i+1}/{len(targets)}] {obra} / {viga_name} sec={params["secao"]}')

        t0 = time.time()
        try:
            doc, gen_info = generate_viga_dxf(params)
        except Exception as ex:
            import traceback
            print(f'  GENERATE FAIL: {ex}')
            traceback.print_exc()
            total_fail += 1
            continue

        # Save DXF
        dxf_path = gen_dir / f'{safe_name}.dxf'
        doc.saveas(str(dxf_path))

        # Render generated PNG
        gen_png = gen_dir / f'{safe_name}.png'
        title = f'{obra} | {viga_name} | {params["secao"]}'
        ok = render_generated_png(doc, gen_info, gen_png, title=title, dpi=args.dpi)
        if not ok:
            print(f'  RENDER FAIL')
            total_fail += 1
            continue

        dt = time.time() - t0

        # Find STOG original PNG
        png_name = params.get('png', '')
        stog_png = Path(args.stog_png) / png_name if png_name else Path(args.stog_png)
        if not png_name or not stog_png.exists() or stog_png.is_dir():
            # Try glob for matching PNG by viga name
            safe_viga = re.sub(r'[^\w]', '*', viga_name)
            matches = list(Path(args.stog_png).glob(f'*{safe_viga}*'))
            stog_png = matches[0] if matches else Path('')

        # Create comparison
        comp_png = comp_dir / f'{safe_name}_COMP.png'
        has_stog = stog_png.exists() and stog_png.is_file()
        if has_stog:
            create_comparison(stog_png, gen_png, comp_png, title=title)

        n_fa = len(gen_info['fa_widths'])
        n_fb = len(gen_info['fb_widths'])
        reaprov = 'Y' if params.get('hatches', {}).get('ansi31', 0) > 0 else 'N'
        print(f'  FA: {n_fa}p h={gen_info["h_A"]:.0f} w={sum(gen_info["fa_widths"]):.0f} | '
              f'FB: {n_fb}p h={gen_info["h_B"]:.0f} w={sum(gen_info["fb_widths"]):.0f} | '
              f'laje={"sup" if gen_info["laje_sup"] else ""}{"inf" if gen_info["laje_inf"] else ""}{"none" if not gen_info["laje_sup"] and not gen_info["laje_inf"] else ""} | '
              f'reaprov={reaprov} | {dt:.1f}s {"COMP" if has_stog else "NO-STOG"}')
        total_ok += 1

    print(f'\n{"=" * 60}')
    print(f'RESULTADO: {total_ok} OK / {total_fail} FAIL')
    print(f'DXFs:       {gen_dir}')
    print(f'Comparacoes: {comp_dir}')


def _viga_uid(p):
    """Unique ID for a viga: obra + dxf_source + viga name."""
    return f"{p.get('obra', '')}::{p.get('dxf_source', '')}::{p['viga']}"


def select_diverse(params_list, max_count):
    """Select maximally diverse vigas across multiple dimensions."""
    from collections import defaultdict

    # Score diversity axes for each viga
    buckets = defaultdict(list)
    for p in params_list:
        laje = p.get('laje', {}).get('position', 'none')
        h = p.get('h_total', 60)
        has_reaprov = p.get('hatches', {}).get('ansi31', 0) > 0
        obra = p.get('obra', '')
        n_panels = len(p.get('face_a', {}).get('panel_widths', [])) + \
                   len(p.get('face_b', {}).get('panel_widths', []))

        h_cat = 'short' if h < 50 else ('med' if h < 80 else 'tall')
        panel_cat = 'few' if n_panels <= 4 else ('med' if n_panels <= 8 else 'many')
        key = (obra, laje, h_cat, has_reaprov, panel_cat)
        buckets[key].append(p)

    # Round-robin from buckets to maximize diversity
    diverse = []
    seen_vigas = set()
    keys = sorted(buckets.keys())

    while len(diverse) < max_count and keys:
        next_keys = []
        for k in keys:
            if len(diverse) >= max_count:
                break
            remaining = [p for p in buckets[k] if _viga_uid(p) not in seen_vigas]
            if remaining:
                p = remaining[0]
                diverse.append(p)
                seen_vigas.add(_viga_uid(p))
                if len(remaining) > 1:
                    next_keys.append(k)
        keys = next_keys

    # Fill remaining slots
    if len(diverse) < max_count:
        for p in params_list:
            if _viga_uid(p) not in seen_vigas:
                diverse.append(p)
                seen_vigas.add(_viga_uid(p))
            if len(diverse) >= max_count:
                break

    return diverse[:max_count]


if __name__ == '__main__':
    main()
