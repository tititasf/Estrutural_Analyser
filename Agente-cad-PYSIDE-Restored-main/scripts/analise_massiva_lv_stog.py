#!/usr/bin/env python3
"""
analise_massiva_lv_stog.py — Análise massiva de vigas laterais STOG
====================================================================
Extrai, renderiza e cataloga vigas individuais de DXFs STOG LV.

Fases:
  1. Inventariar: Encontrar INSERT titulo/titulo1 em cada DXF
  2. BBox: Calcular bounding box de cada viga (entities no range Y)
  3. Render: Renderizar cada viga individual como PNG
  4. Catalog: Salvar JSON com metadados (features detectadas)

Uso:
  python scripts/analise_massiva_lv_stog.py --output D:/Agente-cad-PYSIDE/ANALISE_LV
"""
import sys, io, json, re, os, time, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from collections import defaultdict, Counter
import ezdxf

# ── Configuração das 5 obras ─────────────────────────────────────────────
OBRAS_CONFIG = {
    'Obra_TREINO_3': {
        'empresa': 'NOVA/CAPREM',
        'projeto': 'RES.DIAMOND',
        'max_pavs': 3,
        'max_vigas_per_pav': 12,
    },
    'Obra_TREINO_9': {
        'empresa': 'RB2',
        'projeto': 'CITTA DI LUCCA',
        'max_pavs': 3,
        'max_vigas_per_pav': 12,
    },
    'Obra_TREINO_10': {
        'empresa': 'ROCONTEC',
        'projeto': 'HOSPITAL',
        'max_pavs': 3,
        'max_vigas_per_pav': 12,
    },
    'Obra_TREINO_21': {
        'empresa': 'STOG',
        'projeto': 'NIK SUNSET',
        'max_pavs': 3,
        'max_vigas_per_pav': 12,
    },
    'Obra_TREINO_22': {
        'empresa': 'ALIMONTI',
        'projeto': 'PARAISO',
        'max_pavs': 3,
        'max_vigas_per_pav': 12,
    },
}

BASE_DIR = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')


def find_viga_inserts(msp):
    """Encontra INSERTs com atributo TITULO/TITULO1 → retorna lista de vigas."""
    vigas = []
    for entity in msp:
        if entity.dxftype() != 'INSERT':
            continue
        if not hasattr(entity, 'attribs'):
            continue
        titulo = None
        secao = None
        for att in entity.attribs:
            tag = att.dxf.tag.upper()
            if tag in ('TITULO', 'TITULO1'):
                titulo = att.dxf.text.strip()
            if tag == 'SECAO':
                secao = att.dxf.text.strip()
        if titulo:
            ins_pt = entity.dxf.insert
            vigas.append({
                'nome': titulo,
                'secao': secao or '',
                'insert_x': round(ins_pt.x, 1),
                'insert_y': round(ins_pt.y, 1),
            })
    return vigas


def compute_viga_bbox(msp, insert_y, all_inserts_y, margin=20):
    """Calcula o bounding box de uma viga baseado no Y do INSERT.

    Vigas em DXFs STOG são organizadas em LINHAS horizontais.
    Cada INSERT Y define o centro/topo de uma linha de viga.
    O bbox vai do Y da viga até o Y da próxima viga acima/abaixo.
    """
    sorted_ys = sorted(set(all_inserts_y), reverse=True)
    idx = None
    for i, y in enumerate(sorted_ys):
        if abs(y - insert_y) < 5:
            idx = i
            break
    if idx is None:
        return None

    # Y range: do INSERT atual até o próximo INSERT (ou margem se último)
    y_top = insert_y + margin
    if idx < len(sorted_ys) - 1:
        y_bottom = sorted_ys[idx + 1] + margin  # próximo insert abaixo
    else:
        y_bottom = insert_y - 300  # margem generosa para o último

    # X range: buscar entities no range Y para determinar X
    x_min = float('inf')
    x_max = float('-inf')
    count = 0
    for entity in msp:
        try:
            if hasattr(entity.dxf, 'insert'):
                ey = entity.dxf.insert.y
                ex = entity.dxf.insert.x
            elif hasattr(entity.dxf, 'start'):
                ey = entity.dxf.start.y
                ex = entity.dxf.start.x
            elif hasattr(entity, 'vertices') and callable(entity.vertices):
                verts = list(entity.vertices())
                if not verts:
                    continue
                ey = verts[0][1]
                ex = verts[0][0]
            else:
                continue

            if y_bottom - margin <= ey <= y_top + margin:
                x_min = min(x_min, ex)
                x_max = max(x_max, ex)
                count += 1
        except Exception:
            continue

    if count < 5 or x_min >= x_max:
        return None

    return {
        'xmin': x_min - 30,
        'xmax': x_max + 50,
        'ymin': y_bottom,
        'ymax': y_top,
        'entity_count': count,
    }


def detect_features(msp, bbox):
    """Detecta features visuais dentro do bbox de uma viga.

    Features detectadas:
    - n_hatches: quantidade de HATCH entities (indica lajes, concreto, aberturas)
    - n_dimensions: quantidade de DIMENSION (cotas)
    - n_lines: quantidade de LINE
    - n_lwpolylines: quantidade de LWPOLYLINE
    - n_mtext: quantidade de MTEXT
    - n_inserts: quantidade de INSERT (sub-blocos)
    - layers_used: set de layers presentes
    - has_dashed: se tem DASHED linetype (indica aberturas/pilares)
    - estimated_panels: estimativa de painéis
    """
    features = {
        'n_hatches': 0,
        'n_dimensions': 0,
        'n_lines': 0,
        'n_lwpolylines': 0,
        'n_mtext': 0,
        'n_text': 0,
        'n_inserts': 0,
        'layers': set(),
        'has_dashed': False,
        'hatch_patterns': set(),
        'hatch_layers': set(),
    }

    for entity in msp:
        try:
            # Check if entity is within bbox
            ey = None
            if hasattr(entity.dxf, 'insert'):
                ey = entity.dxf.insert.y
                ex = entity.dxf.insert.x
            elif hasattr(entity.dxf, 'start'):
                ey = entity.dxf.start.y
                ex = entity.dxf.start.x
            elif entity.dxftype() == 'LWPOLYLINE':
                try:
                    pts = list(entity.get_points(format='xy'))
                    if pts:
                        ey = pts[0][1]
                        ex = pts[0][0]
                except Exception:
                    continue
            elif entity.dxftype() == 'HATCH':
                # Hatch bbox is complex, use association
                try:
                    paths = entity.paths
                    if paths:
                        p = paths[0]
                        if hasattr(p, 'vertices') and p.vertices:
                            ey = p.vertices[0][1]
                            ex = p.vertices[0][0]
                except Exception:
                    continue

            if ey is None:
                continue
            if not (bbox['ymin'] <= ey <= bbox['ymax']):
                continue
            if not (bbox['xmin'] <= ex <= bbox['xmax']):
                continue

            etype = entity.dxftype()
            layer = entity.dxf.layer if hasattr(entity.dxf, 'layer') else '0'
            features['layers'].add(layer)

            if etype == 'HATCH':
                features['n_hatches'] += 1
                try:
                    features['hatch_patterns'].add(entity.dxf.pattern_name)
                except Exception:
                    pass
                features['hatch_layers'].add(layer)
            elif etype == 'DIMENSION':
                features['n_dimensions'] += 1
            elif etype == 'LINE':
                features['n_lines'] += 1
                if hasattr(entity.dxf, 'linetype') and 'DASH' in str(entity.dxf.linetype).upper():
                    features['has_dashed'] = True
            elif etype == 'LWPOLYLINE':
                features['n_lwpolylines'] += 1
                if hasattr(entity.dxf, 'linetype') and 'DASH' in str(entity.dxf.linetype).upper():
                    features['has_dashed'] = True
            elif etype == 'MTEXT':
                features['n_mtext'] += 1
            elif etype == 'TEXT':
                features['n_text'] += 1
            elif etype == 'INSERT':
                features['n_inserts'] += 1
        except Exception:
            continue

    # Convert sets to lists for JSON
    features['layers'] = sorted(features['layers'])
    features['hatch_patterns'] = sorted(features['hatch_patterns'])
    features['hatch_layers'] = sorted(features['hatch_layers'])

    # Classify viga type based on features
    features['classification'] = classify_viga(features)

    return features


def classify_viga(features):
    """Classifica o tipo de viga baseado nas features detectadas."""
    tags = []

    n_h = features['n_hatches']
    layers = features['layers']
    hatch_layers = features['hatch_layers']

    # Laje detection
    laje_layers = [l for l in hatch_layers if 'LAJ' in l.upper() or 'SCO' in l.upper() or 'COTA' in l.upper()]
    reaprov_layers = [l for l in hatch_layers if 'REAPROV' in l.upper()]

    if n_h == 0:
        tags.append('SEM_HATCH')
    elif n_h <= 3:
        tags.append('HATCH_SIMPLES')
    elif n_h <= 8:
        tags.append('HATCH_MEDIO')
    else:
        tags.append('HATCH_COMPLEXO')

    if laje_layers or reaprov_layers:
        tags.append('TEM_LAJE')

    if features['has_dashed']:
        tags.append('TEM_ABERTURA_OU_PILAR')

    # Panel estimate from n_lines
    if features['n_lines'] > 100:
        tags.append('VIGA_LONGA')
    elif features['n_lines'] > 50:
        tags.append('VIGA_MEDIA')
    else:
        tags.append('VIGA_CURTA')

    # Section detail
    if any('Madeira' in l for l in layers) or any('barrote' in l for l in layers):
        tags.append('TEM_SECAO')

    # SARR
    if any('SARR' in l for l in layers):
        tags.append('TEM_SARR')

    return tags


def render_viga_png(doc, bbox, output_path, title='', dpi=150):
    """Renderiza uma viga individual como PNG."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        # Calcular aspect ratio
        w = bbox['xmax'] - bbox['xmin']
        h = bbox['ymax'] - bbox['ymin']
        if w <= 0 or h <= 0:
            return False

        aspect = w / h
        fig_w = min(20, max(8, aspect * 4))
        fig_h = fig_w / aspect
        fig_h = min(12, max(3, fig_h))

        fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h), facecolor='#0a0a14')
        ax.set_facecolor('#0a0a14')

        ctx = RenderContext(doc)
        be = MatplotlibBackend(ax)
        Frontend(ctx, be).draw_layout(doc.modelspace(), finalize=True)

        ax.set_xlim(bbox['xmin'], bbox['xmax'])
        ax.set_ylim(bbox['ymin'], bbox['ymax'])
        ax.set_aspect('equal', adjustable='datalim')

        if title:
            ax.set_title(title, color='white', fontsize=8, pad=2)

        ax.axis('off')
        plt.tight_layout(pad=0.5)
        plt.savefig(str(output_path), dpi=dpi, bbox_inches='tight',
                    facecolor='#0a0a14', pad_inches=0.1)
        plt.close(fig)
        return True
    except Exception as ex:
        print(f'    RENDER FAIL: {ex}')
        return False


def process_obra(obra_name, config, output_dir, skip_render=False):
    """Processa uma obra completa: encontra vigas, renderiza, cataloga."""
    ref_dir = BASE_DIR / obra_name / 'Fase-1_Ingestao' / 'Projetos_Finalizados_para_Engenharia_Reversa'
    if not ref_dir.exists():
        print(f'  SKIP: {ref_dir} not found')
        return []

    # Find DXF files
    lv_dxfs = sorted(f for f in ref_dir.glob('*LV*') if f.suffix.lower() == '.dxf')
    if not lv_dxfs:
        print(f'  SKIP: no LV DXFs')
        return []

    # Group by pavimento (pick max_pavs most diverse)
    pav_map = defaultdict(list)
    for f in lv_dxfs:
        parts = f.name.split(' - ')
        pav = parts[2].strip() if len(parts) >= 4 else f.stem
        pav_map[pav].append(f)

    # Select pavimentos: prefer those with most vigas
    max_pavs = config['max_pavs']
    max_per_pav = config['max_vigas_per_pav']

    obra_catalog = []
    pav_count = 0

    for pav_name, pav_files in sorted(pav_map.items()):
        if pav_count >= max_pavs:
            break

        # Use the DXF with most entities (likely most complete)
        best_file = None
        best_count = 0
        for f in pav_files:
            try:
                doc = ezdxf.readfile(str(f))
                msp = doc.modelspace()
                vigas = find_viga_inserts(msp)
                if len(vigas) > best_count:
                    best_count = len(vigas)
                    best_file = f
            except Exception:
                continue

        if not best_file or best_count == 0:
            continue

        pav_count += 1
        print(f'  PAV {pav_count}: {pav_name} ({best_count} vigas) [{best_file.name[:60]}]')

        # Load the best DXF for this pavimento
        doc = ezdxf.readfile(str(best_file))
        msp = doc.modelspace()
        vigas = find_viga_inserts(msp)

        # Get all Y positions for bbox calculation
        all_ys = [v['insert_y'] for v in vigas]

        # Select diverse vigas (spread across different Y positions)
        # Sort by Y desc (top to bottom) and pick evenly
        vigas_sorted = sorted(vigas, key=lambda v: -v['insert_y'])
        # Remove duplicates by name
        seen_names = set()
        vigas_unique = []
        for v in vigas_sorted:
            if v['nome'] not in seen_names:
                seen_names.add(v['nome'])
                vigas_unique.append(v)

        # Select max_per_pav vigas, evenly distributed
        step = max(1, len(vigas_unique) // max_per_pav)
        selected = vigas_unique[::step][:max_per_pav]

        print(f'    Selected {len(selected)}/{len(vigas_unique)} unique vigas')

        for vi, viga in enumerate(selected):
            bbox = compute_viga_bbox(msp, viga['insert_y'], all_ys)
            if not bbox:
                print(f'    SKIP {viga["nome"]}: no bbox')
                continue

            # Detect features
            features = detect_features(msp, bbox)

            # Render PNG
            safe_name = re.sub(r'[^\w\-]', '_', viga['nome'])
            safe_pav = re.sub(r'[^\w\-]', '_', pav_name)[:20]
            png_name = f'{obra_name}__{safe_pav}__{safe_name}.png'
            png_path = output_dir / png_name

            rendered = False
            if not skip_render:
                title = f'{obra_name} | {pav_name} | {viga["nome"]} {viga["secao"]}'
                rendered = render_viga_png(doc, bbox, png_path, title=title, dpi=120)

            catalog_entry = {
                'obra': obra_name,
                'projeto': config['projeto'],
                'pavimento': pav_name,
                'viga': viga['nome'],
                'secao': viga['secao'],
                'insert_x': viga['insert_x'],
                'insert_y': viga['insert_y'],
                'bbox': bbox,
                'features': features,
                'png': png_name if rendered else None,
                'dxf_source': best_file.name,
            }
            obra_catalog.append(catalog_entry)

            tags = ','.join(features['classification'][:3])
            print(f'    {vi+1:2d}. {viga["nome"]:20s} {viga["secao"]:12s} '
                  f'H={features["n_hatches"]:2d} D={features["n_dimensions"]:2d} '
                  f'L={features["n_lines"]:3d} [{tags}]'
                  f'{" PNG" if rendered else " NO-PNG"}')

    return obra_catalog


def main():
    parser = argparse.ArgumentParser(description='Análise massiva LV STOG')
    parser.add_argument('--output', default='D:/Agente-cad-PYSIDE/ANALISE_LV',
                        help='Diretório de saída')
    parser.add_argument('--max-per-pav', type=int, default=12,
                        help='Max vigas por pavimento')
    parser.add_argument('--skip-render', action='store_true',
                        help='Pular renderização PNG (só catalogar)')
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    png_dir = output_dir / 'vigas_png'
    png_dir.mkdir(exist_ok=True)

    print(f'=== ANÁLISE MASSIVA LV STOG ===')
    print(f'Output: {output_dir}')
    print(f'Obras: {len(OBRAS_CONFIG)}')
    print()

    full_catalog = []

    for obra_name, config in OBRAS_CONFIG.items():
        if args.max_per_pav:
            config['max_vigas_per_pav'] = args.max_per_pav

        print(f'\n{"="*60}')
        print(f'OBRA: {obra_name} ({config["projeto"]})')
        print(f'{"="*60}')

        obra_results = process_obra(obra_name, config, png_dir, skip_render=args.skip_render)
        full_catalog.extend(obra_results)

        print(f'  TOTAL: {len(obra_results)} vigas catalogadas')

    # Save catalog
    catalog_path = output_dir / 'catalog.json'
    # Convert sets to lists for serialization
    for entry in full_catalog:
        for k, v in entry.get('features', {}).items():
            if isinstance(v, set):
                entry['features'][k] = sorted(v)

    with open(catalog_path, 'w', encoding='utf-8') as f:
        json.dump(full_catalog, f, indent=2, ensure_ascii=False)

    # Summary
    print(f'\n\n{"="*60}')
    print(f'RESUMO FINAL')
    print(f'{"="*60}')
    print(f'Total vigas catalogadas: {len(full_catalog)}')

    # Stats by classification
    all_tags = Counter()
    for entry in full_catalog:
        for tag in entry.get('features', {}).get('classification', []):
            all_tags[tag] += 1

    print(f'\nClassificação:')
    for tag, count in all_tags.most_common():
        print(f'  {tag:30s} {count:4d}')

    # Stats by obra
    print(f'\nPor obra:')
    obra_counts = Counter(e['obra'] for e in full_catalog)
    for obra, count in obra_counts.most_common():
        print(f'  {obra:25s} {count:4d} vigas')

    # Stats by hatch count
    print(f'\nDistribuição de hatches:')
    hatch_dist = Counter()
    for e in full_catalog:
        nh = e.get('features', {}).get('n_hatches', 0)
        if nh == 0:
            hatch_dist['0 (sem hatch)'] += 1
        elif nh <= 3:
            hatch_dist['1-3 (simples)'] += 1
        elif nh <= 8:
            hatch_dist['4-8 (médio)'] += 1
        else:
            hatch_dist['9+ (complexo)'] += 1
    for k, v in sorted(hatch_dist.items()):
        print(f'  {k:20s} {v:4d}')

    rendered_count = sum(1 for e in full_catalog if e.get('png'))
    print(f'\nPNGs renderizados: {rendered_count}/{len(full_catalog)}')
    print(f'Catálogo: {catalog_path}')
    print(f'PNGs: {png_dir}')


if __name__ == '__main__':
    main()
