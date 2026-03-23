#!/usr/bin/env python3
"""
extrair_parametros_viga.py — Extração profunda de parâmetros de vigas STOG
==========================================================================
Versão 2.0 — Usa DIMENSION entities (COTA) como fonte primária de medidas,
e LINE segments no Painéis layer para estrutura de faces.

Uso:
  python scripts/extrair_parametros_viga.py --all --max 30
  python scripts/extrair_parametros_viga.py --obra Obra_TREINO_9
"""
import sys, io, json, re, os, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from collections import defaultdict

import ezdxf

BASE_DIR = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')


def find_all_inserts(msp):
    """Find all titulo INSERT blocks with attribs."""
    vigas = []
    for e in msp:
        if e.dxftype() != 'INSERT' or not hasattr(e, 'attribs'):
            continue
        titulo = secao = reaprov = None
        for att in e.attribs:
            tag = att.dxf.tag.upper()
            val = att.dxf.text.strip()
            if tag in ('TITULO', 'TITULO1'):
                titulo = val
            elif tag in ('SECAO', 'SEÇÃO'):
                secao = val
            elif 'REAPROV' in tag:
                reaprov = val
        if titulo:
            vigas.append({
                'nome': titulo,
                'secao': secao or '',
                'reaprov': reaprov or '',
                'x': e.dxf.insert.x,
                'y': e.dxf.insert.y,
            })
    vigas.sort(key=lambda v: -v['y'])
    return vigas


def compute_zone(all_vigas, target_name):
    """Compute Y/X bounds for a target viga using zone grouping."""
    if not all_vigas:
        return None

    zones = []
    current = [all_vigas[0]]
    for i in range(1, len(all_vigas)):
        if current[-1]['y'] - all_vigas[i]['y'] < 150:
            current.append(all_vigas[i])
        else:
            zones.append(current)
            current = [all_vigas[i]]
    zones.append(current)

    for zi, zone in enumerate(zones):
        for v in zone:
            if v['nome'] == target_name:
                y_top = max(z['y'] for z in zone) + 80
                y_bot = max(z['y'] for z in zones[zi + 1]) if zi < len(zones) - 1 else min(z['y'] for z in zone) - 1000

                zone_by_x = sorted(zone, key=lambda z: z['x'])
                idx = next(i for i, z in enumerate(zone_by_x) if z['nome'] == target_name)
                x_left = (zone_by_x[idx]['x'] + zone_by_x[idx - 1]['x']) / 2 if idx > 0 else None
                x_right = (zone_by_x[idx]['x'] + zone_by_x[idx + 1]['x']) / 2 if idx < len(zone_by_x) - 1 else None

                return {
                    'y_top': y_top, 'y_bot': y_bot,
                    'x_left': x_left, 'x_right': x_right,
                    'insert_x': v['x'], 'insert_y': v['y'],
                    'secao': v['secao'], 'reaprov': v['reaprov'],
                    'zone_size': len(zone),
                }
    return None


def entity_in_zone(e, zone):
    """Check if entity has any point within zone bounds."""
    etype = e.dxftype()
    ys = []
    xs = []
    try:
        if etype == 'LINE':
            ys = [e.dxf.start.y, e.dxf.end.y]
            xs = [e.dxf.start.x, e.dxf.end.x]
        elif etype == 'LWPOLYLINE':
            pts = list(e.get_points(format='xy'))
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
        elif etype in ('TEXT', 'MTEXT', 'INSERT'):
            ys = [e.dxf.insert.y]
            xs = [e.dxf.insert.x]
        elif etype == 'HATCH':
            for p in e.paths:
                if hasattr(p, 'vertices'):
                    xs.extend([v[0] for v in p.vertices])
                    ys.extend([v[1] for v in p.vertices])
        elif etype == 'DIMENSION':
            if hasattr(e.dxf, 'defpoint'):
                ys.append(e.dxf.defpoint.y)
                xs.append(e.dxf.defpoint.x)
            if hasattr(e.dxf, 'defpoint2'):
                ys.append(e.dxf.defpoint2.y)
                xs.append(e.dxf.defpoint2.x)
        elif etype in ('CIRCLE', 'ARC'):
            ys = [e.dxf.center.y]
            xs = [e.dxf.center.x]
        elif etype == 'SOLID':
            for attr in ['vtx0', 'vtx1', 'vtx2', 'vtx3']:
                if hasattr(e.dxf, attr):
                    v = getattr(e.dxf, attr)
                    xs.append(v.x)
                    ys.append(v.y)
    except Exception:
        return False, [], []

    if not ys:
        return False, [], []
    if not any(zone['y_bot'] <= y <= zone['y_top'] for y in ys):
        return False, xs, ys
    if zone['x_left'] is not None and xs and max(xs) < zone['x_left']:
        return False, xs, ys
    if zone['x_right'] is not None and xs and min(xs) > zone['x_right']:
        return False, xs, ys
    return True, xs, ys


def extract_viga_deep(doc, viga_name, zone):
    """Deep extraction of viga parameters from DXF entities in zone."""
    msp = doc.modelspace()
    insert_y = zone['insert_y']

    # Collect all zone entities with metadata
    dimensions = []
    h_lines = []  # Horizontal Painéis lines
    v_lines = []  # Vertical Painéis lines
    hatches = []
    texts = []
    sarr_lines = []
    laje_entities = []
    layers_used = defaultdict(int)
    entity_count = 0

    for e in msp:
        in_zone, xs, ys = entity_in_zone(e, zone)
        if not in_zone:
            continue

        etype = e.dxftype()
        layer = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'
        layers_used[layer] += 1
        entity_count += 1

        # DIMENSION entities — primary measurement source
        if etype == 'DIMENSION':
            dp = e.dxf.defpoint if hasattr(e.dxf, 'defpoint') else None
            dp2 = e.dxf.defpoint2 if hasattr(e.dxf, 'defpoint2') else None
            actual = e.dxf.actual_measurement if hasattr(e.dxf, 'actual_measurement') else 0
            if dp and dp2 and actual > 0:
                # Classify: horizontal (panel width) vs vertical (height)
                dx = abs(dp.x - dp2.x)
                dy = abs(dp.y - dp2.y)
                is_horizontal = dx > dy
                dimensions.append({
                    'actual': round(actual, 1),
                    'layer': layer,
                    'horizontal': is_horizontal,
                    'x_mid': round((dp.x + dp2.x) / 2, 1),
                    'y_mid': round((dp.y + dp2.y) / 2, 1),
                    'dp': (round(dp.x, 1), round(dp.y, 1)),
                    'dp2': (round(dp2.x, 1), round(dp2.y, 1)),
                })

        # LINE on Painéis layer — panel structure
        elif etype == 'LINE' and 'pain' in layer.lower():
            dx = abs(e.dxf.end.x - e.dxf.start.x)
            dy = abs(e.dxf.end.y - e.dxf.start.y)
            if dx > dy and dx > 10:  # Horizontal line
                h_lines.append({
                    'x1': round(min(e.dxf.start.x, e.dxf.end.x), 1),
                    'x2': round(max(e.dxf.start.x, e.dxf.end.x), 1),
                    'y': round((e.dxf.start.y + e.dxf.end.y) / 2, 1),
                    'len': round(dx, 1),
                })
            elif dy > dx and dy > 10:  # Vertical line
                v_lines.append({
                    'x': round((e.dxf.start.x + e.dxf.end.x) / 2, 1),
                    'y1': round(min(e.dxf.start.y, e.dxf.end.y), 1),
                    'y2': round(max(e.dxf.start.y, e.dxf.end.y), 1),
                    'len': round(dy, 1),
                })

        # HATCH entities
        elif etype == 'HATCH':
            try:
                pattern = e.dxf.pattern_name if hasattr(e.dxf, 'pattern_name') else 'SOLID'
                all_pts = []
                for p in e.paths:
                    if hasattr(p, 'vertices'):
                        all_pts.extend([(v[0], v[1]) for v in p.vertices])
                if all_pts:
                    hatches.append({
                        'pattern': pattern,
                        'layer': layer,
                        'x_min': round(min(p[0] for p in all_pts), 1),
                        'x_max': round(max(p[0] for p in all_pts), 1),
                        'y_min': round(min(p[1] for p in all_pts), 1),
                        'y_max': round(max(p[1] for p in all_pts), 1),
                    })
            except Exception:
                pass

        # TEXT entities
        elif etype in ('TEXT', 'MTEXT'):
            txt = e.dxf.text if etype == 'TEXT' else (e.text if hasattr(e, 'text') else '')
            # Strip MTEXT formatting
            if etype == 'MTEXT':
                txt = re.sub(r'\{[^}]*?;', '', txt).replace('}', '').replace('{', '')
                txt = re.sub(r'\\[A-Za-z][^;]*;', '', txt)
            texts.append({
                'text': txt.strip(),
                'layer': layer,
                'x': round(e.dxf.insert.x, 1),
                'y': round(e.dxf.insert.y, 1),
            })

        # Sarrafo lines
        elif etype == 'LINE' and 'sarr' in layer.lower():
            sarr_lines.append(layer)

        # Laje entities (SCO-___-LAJ layer)
        elif 'LAJ' in layer.upper() or 'SCO' in layer.upper():
            laje_entities.append({
                'type': etype,
                'layer': layer,
                'y_mid': round(sum(ys) / len(ys), 1) if ys else 0,
            })

    # === ANALYSIS ===

    # Parse section from INSERT attrib
    secao_str = zone.get('secao', '')
    b_alma = h_total = 0
    # Handle compound sections like (19x108/138), (19x60), (50x80)
    m = re.search(r'\((\d+)[xX](\d+)', secao_str)
    if m:
        b_alma = int(m.group(1))
        h_total = int(m.group(2))
    h_section = h_total // 2 if h_total else 0

    # Analyze face structure from horizontal Painéis lines
    # Group by Y level (within tolerance of 2 units)
    face_a_lines = []
    face_b_lines = []
    if h_lines:
        # Lines above insert_y midpoint → Face A (closer to insert)
        # Lines below → Face B
        # The insert is at top; Face A starts just below insert
        face_split_y = insert_y - (h_total + 20 if h_total else 150)

        for hl in h_lines:
            if hl['y'] > face_split_y:
                face_a_lines.append(hl)
            else:
                face_b_lines.append(hl)

    # Extract face dimensions from longest horizontal lines at each Y level
    def analyze_face(lines):
        if not lines:
            return {'height': 0, 'total_width': 0, 'y_levels': [], 'panel_count': 0, 'panel_widths': []}

        # Group by Y level (tolerance 3)
        y_groups = defaultdict(list)
        for ln in lines:
            key = round(ln['y'] / 3) * 3
            y_groups[key].append(ln)

        # Get Y extent
        all_ys = [ln['y'] for ln in lines]
        height = round(max(all_ys) - min(all_ys), 1) if all_ys else 0

        # Get total width from longest line
        total_width = max(ln['len'] for ln in lines) if lines else 0

        # Count Y levels
        y_levels = sorted(y_groups.keys(), reverse=True)

        return {
            'height': height,
            'total_width': round(total_width, 1),
            'y_levels': len(y_levels),
            'panel_count': 0,  # will be enriched from dimensions
            'panel_widths': [],
        }

    face_a = analyze_face(face_a_lines)
    face_b = analyze_face(face_b_lines)

    # Extract panel widths from DIMENSION entities
    # Horizontal dimensions on COTA layer near face A or face B
    h_dims = [d for d in dimensions if d['horizontal'] and d['layer'] in ('COTA', 'Cota') and d['actual'] > 30]

    # Separate dims into Face A and Face B by Y position
    fa_dims = []
    fb_dims = []
    for d in h_dims:
        if d['y_mid'] > (insert_y - (h_total + 20 if h_total else 150)):
            fa_dims.append(d['actual'])
        else:
            fb_dims.append(d['actual'])

    # Filter to likely panel widths (between 50 and 500, common values)
    def filter_panel_widths(dims):
        """Keep widths that look like individual panel dimensions (not totals)."""
        if not dims:
            return []
        # Sort and find the total (usually largest)
        sorted_dims = sorted(dims)
        total = max(dims) if dims else 0
        # Panel widths are the ones that sum up to approximately the total
        panels = [d for d in sorted_dims if d < total * 0.95 and d >= 50]
        if not panels:
            panels = [d for d in sorted_dims if d >= 50]
        return sorted(panels)

    face_a['panel_widths'] = filter_panel_widths(fa_dims)
    face_b['panel_widths'] = filter_panel_widths(fb_dims)
    face_a['panel_count'] = len(face_a['panel_widths'])
    face_b['panel_count'] = len(face_b['panel_widths'])

    # Hatch analysis
    reaprov_hatches = [h for h in hatches if 'reaprov' in h['layer'].lower()]
    concrete_hatches = [h for h in hatches if h['pattern'] == 'AR-CONC']
    laje_hatches = [h for h in hatches if 'LAJ' in h['layer'].upper() or 'SCO' in h['layer'].upper()]
    ansi31_hatches = [h for h in hatches if h['pattern'] == 'ANSI31']

    # Laje position
    laje_position = 'none'
    if laje_entities:
        laje_ys = [le['y_mid'] for le in laje_entities if le['y_mid'] != 0]
        if laje_ys:
            avg_laje_y = sum(laje_ys) / len(laje_ys)
            if avg_laje_y > insert_y - 50:
                laje_position = 'superior'
            elif avg_laje_y < insert_y - (h_total + 50 if h_total else 200):
                laje_position = 'inferior'
            else:
                laje_position = 'central'

    # Section dimensions from vertical DIMENSION entities on "Cota Seção"
    section_dims = [d for d in dimensions if not d['horizontal'] and 'se' in d['layer'].lower()]
    section_measurements = sorted(set(d['actual'] for d in section_dims)) if section_dims else []

    # Sarrafo layers used
    sarr_layers = sorted(set(sarr_lines))

    # Panel number texts (P1, P2, etc.)
    panel_texts = [t for t in texts if re.match(r'^P?\d+$', t['text']) and t['layer'] in ('5', 'texto', 'NOMENCLATURA')]

    # All unique COTA horizontal dimensions (for debugging/analysis)
    all_h_dim_values = sorted(set(d['actual'] for d in h_dims))

    return {
        'viga': viga_name,
        'secao': secao_str,
        'b_alma': b_alma,
        'h_total': h_total,
        'h_section': h_section,
        'insert': {'x': round(zone['insert_x'], 1), 'y': round(zone['insert_y'], 1)},
        'zone': {'y_top': round(zone['y_top'], 1), 'y_bot': round(zone['y_bot'], 1),
                 'x_left': round(zone['x_left'], 1) if zone['x_left'] else None,
                 'x_right': round(zone['x_right'], 1) if zone['x_right'] else None},
        'face_a': face_a,
        'face_b': face_b,
        'hatches': {
            'total': len(hatches),
            'reaproveitamento': len(reaprov_hatches),
            'concrete_arconc': len(concrete_hatches),
            'ansi31': len(ansi31_hatches),
            'laje': len(laje_hatches),
            'patterns': sorted(set(h['pattern'] for h in hatches)),
        },
        'laje': {
            'position': laje_position,
            'entity_count': len(laje_entities),
        },
        'section_dims': section_measurements,
        'sarr_layers': sarr_layers,
        'panel_texts': len(panel_texts),
        'all_cota_h_dims': all_h_dim_values,
        'entity_count': entity_count,
        'layers_used': dict(sorted(layers_used.items(), key=lambda x: -x[1])),
        'reaprov': zone.get('reaprov', ''),
    }


def main():
    parser = argparse.ArgumentParser(description='Extrai parametros de viga STOG v2')
    parser.add_argument('--catalog', default='D:/Agente-cad-PYSIDE/ANALISE_LV/catalog_rendered.json')
    parser.add_argument('--output', default='D:/Agente-cad-PYSIDE/ANALISE_LV/params')
    parser.add_argument('--obra', help='Specific obra')
    parser.add_argument('--all', action='store_true', help='Extract all vigas')
    parser.add_argument('--max', type=int, default=142, help='Max vigas to extract')
    parser.add_argument('--diverse', action='store_true', help='Select diverse subset')
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.catalog, 'r', encoding='utf-8') as f:
        catalog = json.load(f)

    # Select targets
    if args.obra:
        targets = [e for e in catalog if e['obra'] == args.obra][:args.max]
    elif args.all:
        targets = catalog[:args.max]
    elif args.diverse:
        # Select diverse vigas by type
        diverse = []
        seen = set()
        for e in catalog:
            key = (e['obra'], e.get('features', {}).get('type', ''))
            if key not in seen:
                diverse.append(e)
                seen.add(key)
            if len(diverse) >= args.max:
                break
        targets = diverse
    else:
        targets = catalog[:args.max]

    print(f'=== EXTRACAO PARAMETROS STOG v2 === {len(targets)} vigas')

    # Group by DXF
    by_dxf = defaultdict(list)
    for t in targets:
        by_dxf[(t['obra'], t.get('dxf_source', ''))].append(t)

    all_params = []
    total_ok = total_fail = 0

    for (obra, dxf_name), entries in sorted(by_dxf.items()):
        ref_dir = BASE_DIR / obra / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'

        # Handle encoding issues in filenames
        dxf_path = ref_dir / dxf_name
        if not dxf_path.exists():
            # Try finding by matching key parts
            found = False
            try:
                for f in os.listdir(str(ref_dir)):
                    if f.endswith('.dxf') and 'LV' in f:
                        # Match by key substring
                        key_parts = dxf_name.split(' - ')[:3]
                        if all(kp in f for kp in key_parts if len(kp) > 3):
                            dxf_path = ref_dir / f
                            found = True
                            break
            except Exception:
                pass
            if not found:
                print(f'\n  SKIP: {dxf_path}')
                total_fail += len(entries)
                continue

        try:
            doc = ezdxf.readfile(str(dxf_path))
        except Exception as ex:
            print(f'\n  LOAD ERROR: {dxf_path.name} — {ex}')
            total_fail += len(entries)
            continue

        msp = doc.modelspace()
        all_vigas = find_all_inserts(msp)
        print(f'\n{obra} / {dxf_path.name[:55]}  ({len(all_vigas)} vigas)')

        for entry in entries:
            viga_name = entry['viga']
            zone = compute_zone(all_vigas, viga_name)
            if not zone:
                print(f'  {viga_name:25s} NO ZONE')
                total_fail += 1
                continue

            params = extract_viga_deep(doc, viga_name, zone)
            params['obra'] = obra
            params['dxf_source'] = dxf_name
            params['png'] = entry.get('png', '')
            all_params.append(params)

            fa = params['face_a']
            fb = params['face_b']
            pw_a = ','.join(str(int(w)) for w in fa['panel_widths'][:5])
            pw_b = ','.join(str(int(w)) for w in fb['panel_widths'][:5])
            print(f'  {viga_name:25s} sec={params["secao"]:10s} '
                  f'FA: h={fa["height"]:5.1f} w={fa["total_width"]:6.1f} [{pw_a}] | '
                  f'FB: h={fb["height"]:5.1f} w={fb["total_width"]:6.1f} [{pw_b}] | '
                  f'H={params["hatches"]["total"]:2d} laje={params["laje"]["position"]:8s} '
                  f'ents={params["entity_count"]}')
            total_ok += 1

    # Save results
    params_path = output_dir / 'viga_params.json'
    with open(params_path, 'w', encoding='utf-8') as f:
        json.dump(all_params, f, indent=2, ensure_ascii=False)

    print(f'\n{"=" * 60}')
    print(f'RESULTADO: {total_ok} OK / {total_fail} FAIL')
    print(f'Salvo: {params_path}')

    # Summary statistics
    if all_params:
        with_panels = sum(1 for p in all_params if p['face_a']['panel_count'] > 0)
        with_laje = sum(1 for p in all_params if p['laje']['position'] != 'none')
        with_hatches = sum(1 for p in all_params if p['hatches']['total'] > 0)
        with_secao = sum(1 for p in all_params if p['h_total'] > 0)
        print(f'\nEstatisticas:')
        print(f'  Com secao:   {with_secao:3d}/{len(all_params)}')
        print(f'  Com paineis: {with_panels:3d}/{len(all_params)}')
        print(f'  Com laje:    {with_laje:3d}/{len(all_params)}')
        print(f'  Com hatch:   {with_hatches:3d}/{len(all_params)}')


if __name__ == '__main__':
    main()
