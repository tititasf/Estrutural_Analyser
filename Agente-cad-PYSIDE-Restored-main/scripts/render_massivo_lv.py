#!/usr/bin/env python3
"""
render_massivo_lv.py — Renderização massiva de vigas STOG individuais
======================================================================
Usa filter_func do ezdxf Frontend para renderizar só entities da zona.
Rápido: ~2-5s por viga (vs 90s antes).

Uso:
  python scripts/render_massivo_lv.py
  python scripts/render_massivo_lv.py --obras Obra_TREINO_21 --max-per-dxf 5
"""
import sys, io, json, os, argparse, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from collections import defaultdict

import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

BASE_DIR = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')


def get_dxf_path(obra, dxf_filename):
    ref_dir = BASE_DIR / obra / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'
    return ref_dir / dxf_filename


def get_entity_ys(entity):
    """Get all Y values of an entity."""
    etype = entity.dxftype()
    ys = []
    try:
        if etype == 'LINE':
            ys = [entity.dxf.start.y, entity.dxf.end.y]
        elif etype == 'LWPOLYLINE':
            ys = [p[1] for p in entity.get_points(format='xy')]
        elif etype in ('TEXT', 'MTEXT', 'INSERT'):
            ys = [entity.dxf.insert.y]
        elif etype == 'DIMENSION':
            if hasattr(entity.dxf, 'defpoint'):
                ys.append(entity.dxf.defpoint.y)
            if hasattr(entity.dxf, 'defpoint2'):
                ys.append(entity.dxf.defpoint2.y)
        elif etype == 'HATCH':
            for p in entity.paths:
                if hasattr(p, 'vertices'):
                    ys.extend([v[1] for v in p.vertices])
        elif etype in ('CIRCLE', 'ARC'):
            ys = [entity.dxf.center.y]
        elif etype == 'SPLINE':
            ys = [pt[1] for pt in entity.control_points]
        elif etype == 'SOLID':
            for attr in ['vtx0', 'vtx1', 'vtx2', 'vtx3']:
                if hasattr(entity.dxf, attr):
                    ys.append(getattr(entity.dxf, attr).y)
        elif etype == 'LEADER':
            ys = [v[1] for v in entity.vertices]
    except Exception:
        pass
    return ys


def get_entity_xs(entity):
    """Get all X values of an entity."""
    etype = entity.dxftype()
    xs = []
    try:
        if etype == 'LINE':
            xs = [entity.dxf.start.x, entity.dxf.end.x]
        elif etype == 'LWPOLYLINE':
            xs = [p[0] for p in entity.get_points(format='xy')]
        elif etype in ('TEXT', 'MTEXT', 'INSERT'):
            xs = [entity.dxf.insert.x]
        elif etype == 'DIMENSION':
            if hasattr(entity.dxf, 'defpoint'):
                xs.append(entity.dxf.defpoint.x)
            if hasattr(entity.dxf, 'defpoint2'):
                xs.append(entity.dxf.defpoint2.x)
            if hasattr(entity.dxf, 'defpoint3'):
                xs.append(entity.dxf.defpoint3.x)
        elif etype == 'HATCH':
            for p in entity.paths:
                if hasattr(p, 'vertices'):
                    xs.extend([v[0] for v in p.vertices])
        elif etype in ('CIRCLE', 'ARC'):
            r = entity.dxf.radius
            xs = [entity.dxf.center.x - r, entity.dxf.center.x + r]
        elif etype == 'SPLINE':
            xs = [pt[0] for pt in entity.control_points]
        elif etype == 'SOLID':
            for attr in ['vtx0', 'vtx1', 'vtx2', 'vtx3']:
                if hasattr(entity.dxf, attr):
                    xs.append(getattr(entity.dxf, attr).x)
        elif etype == 'LEADER':
            xs = [v[0] for v in entity.vertices]
    except Exception:
        pass
    return xs


def entity_in_yrange(entity, y_bottom, y_top):
    """Check if entity has any Y value within range."""
    for y in get_entity_ys(entity):
        if y_bottom <= y <= y_top:
            return True
    return False


def find_all_vigas(doc):
    """Find all INSERT titulo blocks and return list with positions."""
    msp = doc.modelspace()
    vigas = []
    for e in msp:
        if e.dxftype() != 'INSERT' or not hasattr(e, 'attribs'):
            continue
        titulo = secao = None
        for att in e.attribs:
            tag = att.dxf.tag.upper()
            if tag in ('TITULO', 'TITULO1'):
                titulo = att.dxf.text.strip()
            if tag == 'SECAO':
                secao = att.dxf.text.strip()
        if titulo:
            vigas.append({
                'nome': titulo,
                'secao': secao or '',
                'x': e.dxf.insert.x,
                'y': e.dxf.insert.y,
            })
    vigas.sort(key=lambda v: -v['y'])
    return vigas


def compute_viga_bounds(vigas, target_name):
    """Compute Y and X bounds for a specific viga within the full viga list."""
    target = None
    for v in vigas:
        if v['nome'] == target_name:
            target = v
            break
    if not target:
        return None

    # Y zones: group vigas within 150 Y units
    zones = []
    current_zone = [vigas[0]]
    for i in range(1, len(vigas)):
        if current_zone[-1]['y'] - vigas[i]['y'] < 150:
            current_zone.append(vigas[i])
        else:
            zones.append(current_zone)
            current_zone = [vigas[i]]
    zones.append(current_zone)

    # Find target's zone
    target_zone = None
    target_zone_idx = None
    for zi, zone in enumerate(zones):
        for v in zone:
            if v['nome'] == target_name:
                target_zone = zone
                target_zone_idx = zi
                break
        if target_zone:
            break

    if not target_zone:
        return None

    # Y bounds: from zone top to next zone top
    y_top = max(v['y'] for v in target_zone) + 80
    if target_zone_idx < len(zones) - 1:
        y_bottom = max(v['y'] for v in zones[target_zone_idx + 1])
    else:
        y_bottom = min(v['y'] for v in target_zone) - 1000

    # X bounds: if multiple vigas in zone, compute per-viga X range
    # using midpoints between adjacent vigas as boundaries
    zone_sorted_x = sorted(target_zone, key=lambda v: v['x'])
    target_idx = None
    for i, v in enumerate(zone_sorted_x):
        if v['nome'] == target_name:
            target_idx = i
            break

    if target_idx is None:
        return None

    if len(zone_sorted_x) == 1:
        # Only viga in zone, use full X range
        x_left = None  # Will be computed from entities
        x_right = None
    else:
        # Compute X boundaries as midpoints
        if target_idx > 0:
            x_left = (zone_sorted_x[target_idx]['x'] + zone_sorted_x[target_idx - 1]['x']) / 2
        else:
            x_left = None

        if target_idx < len(zone_sorted_x) - 1:
            x_right = (zone_sorted_x[target_idx]['x'] + zone_sorted_x[target_idx + 1]['x']) / 2
        else:
            x_right = None

    return {
        'y_top': y_top,
        'y_bottom': y_bottom,
        'x_left': x_left,
        'x_right': x_right,
        'x_insert': target['x'],
        'y_insert': target['y'],
        'secao': target['secao'],
        'zone_size': len(target_zone),
    }


def render_viga(doc, bounds, output_path, title='', dpi=150):
    """Render a single viga using filter_func for fast rendering."""
    msp = doc.modelspace()
    y_top = bounds['y_top']
    y_bottom = bounds['y_bottom']

    # First pass: collect handles of entities in Y range
    zone_handles = set()
    x_min = float('inf')
    x_max = float('-inf')

    for entity in msp:
        if entity_in_yrange(entity, y_bottom, y_top):
            # Check X bounds if we have them
            xs = get_entity_xs(entity)
            if xs:
                e_xmin = min(xs)
                e_xmax = max(xs)

                # Apply X filter if bounds are defined
                if bounds['x_left'] is not None and e_xmax < bounds['x_left']:
                    continue
                if bounds['x_right'] is not None and e_xmin > bounds['x_right']:
                    continue

                x_min = min(x_min, e_xmin)
                x_max = max(x_max, e_xmax)

            zone_handles.add(entity.dxf.handle)

    if not zone_handles or x_min >= x_max:
        return False, 0

    # Compute figure dimensions
    w = x_max - x_min
    h = y_top - y_bottom
    if w <= 0 or h <= 0:
        return False, 0

    aspect = w / h
    fig_w = min(30, max(10, aspect * 6))
    fig_h = fig_w / aspect
    fig_h = min(16, max(3, fig_h))

    fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), facecolor='white')
    ax.set_facecolor('white')

    ctx = RenderContext(doc)
    be = MatplotlibBackend(ax)

    def zone_filter(entity):
        return entity.dxf.handle in zone_handles

    Frontend(ctx, be).draw_layout(msp, finalize=True, filter_func=zone_filter)

    margin_x = w * 0.02
    margin_y = h * 0.02
    ax.set_xlim(x_min - margin_x, x_max + margin_x)
    ax.set_ylim(y_bottom - margin_y, y_top + margin_y)
    ax.set_aspect('equal', adjustable='box')

    if title:
        ax.set_title(title, fontsize=8, pad=3, color='#333')
    ax.axis('off')
    plt.tight_layout(pad=0.3)
    plt.savefig(str(output_path), dpi=dpi, bbox_inches='tight',
                facecolor='white', pad_inches=0.1)
    plt.close(fig)
    return True, len(zone_handles)


def main():
    parser = argparse.ArgumentParser(description='Render massivo vigas STOG')
    parser.add_argument('--catalog', default='D:/Agente-cad-PYSIDE/ANALISE_LV/catalog.json')
    parser.add_argument('--output', default='D:/Agente-cad-PYSIDE/ANALISE_LV/vigas_png')
    parser.add_argument('--dpi', type=int, default=150)
    parser.add_argument('--max-per-dxf', type=int, default=15)
    parser.add_argument('--obras', nargs='*', help='Filter by obra names')
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.catalog, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    print(f'=== RENDER MASSIVO LV STOG ===')
    print(f'Catalogo: {len(catalog)} vigas | DPI: {args.dpi}')

    by_dxf = defaultdict(list)
    for entry in catalog:
        key = (entry['obra'], entry.get('dxf_source', ''))
        by_dxf[key].append(entry)

    total_ok = 0
    total_fail = 0

    for (obra, dxf_name), entries in sorted(by_dxf.items()):
        if args.obras and obra not in args.obras:
            continue

        dxf_path = get_dxf_path(obra, dxf_name)
        if not dxf_path.exists():
            print(f'\n  SKIP: {dxf_path}')
            continue

        print(f'\n{"="*60}')
        print(f'{obra} / {dxf_name[:55]}')

        t0 = time.time()
        doc = ezdxf.readfile(str(dxf_path))
        all_vigas = find_all_vigas(doc)
        print(f'  {len(all_vigas)} vigas found, loaded in {time.time()-t0:.1f}s')

        to_render = entries[:args.max_per_dxf]

        for vi, entry in enumerate(to_render):
            viga_name = entry['viga']
            bounds = compute_viga_bounds(all_vigas, viga_name)
            if not bounds:
                print(f'  {vi+1:2d}. {viga_name:20s} NO BOUNDS — skip')
                total_fail += 1
                continue

            safe_obra = re.sub(r'[^\w\-]', '_', obra)
            safe_pav = re.sub(r'[^\w\-]', '_', entry.get('pavimento', '')[:25])
            safe_name = re.sub(r'[^\w\-]', '_', viga_name)
            png_name = f'{safe_obra}__{safe_pav}__{safe_name}.png'
            png_path = output_dir / png_name

            title = f'{obra} | {entry.get("pavimento","")} | {viga_name} {bounds["secao"]}'

            t1 = time.time()
            ok, n_ents = render_viga(doc, bounds, png_path, title=title, dpi=args.dpi)
            dt = time.time() - t1

            if ok:
                total_ok += 1
                entry['png'] = png_name
                z = bounds['zone_size']
                print(f'  {vi+1:2d}. {viga_name:20s} {n_ents:4d} ents  zone={z}  {dt:5.1f}s  OK')
            else:
                total_fail += 1
                print(f'  {vi+1:2d}. {viga_name:20s} FAIL')

    # Save updated catalog
    out_path = Path(args.catalog).parent / 'catalog_rendered.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f'\n{"="*60}')
    print(f'RESULTADO: {total_ok} OK / {total_fail} FAIL')
    print(f'Catalogo: {out_path}')


if __name__ == '__main__':
    main()
