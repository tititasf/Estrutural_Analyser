#!/usr/bin/env python3
"""
analisar_dxf_detalhado.py — Análise profunda entity-by-entity de um DXF
=========================================================================
Extrai tudo de um DXF: layers, tipos, blocos, dimensões, cotas, textos.
Usado para entender o que o AutoCAD gera via SCR e comparar com ezdxf.

Uso:
  python scripts/analisar_dxf_detalhado.py --dxf GROUND_TRUTH/CIMA/P01_CIMA.dxf
  python scripts/analisar_dxf_detalhado.py --dxf GROUND_TRUTH/CIMA/P01_CIMA.dxf --verbose
  python scripts/analisar_dxf_detalhado.py --dir GROUND_TRUTH/CIMA --output analise_cima.json
"""
import sys, io, json, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
from collections import Counter, defaultdict

try:
    import ezdxf
    from ezdxf.math import BoundingBox
except ImportError:
    print("pip install ezdxf")
    sys.exit(1)


def analisar_dxf(dxf_path, verbose=False):
    """Análise completa de um DXF."""
    path = Path(dxf_path)
    if not path.exists():
        return {'error': f'Arquivo não encontrado: {dxf_path}'}

    try:
        doc = ezdxf.readfile(str(path))
    except Exception as e:
        return {'error': str(e)}

    msp = doc.modelspace()
    entities = list(msp)

    # Contagens básicas
    layer_counts = Counter(e.dxf.layer for e in entities)
    type_counts = Counter(e.dxftype() for e in entities)

    # Blocos (INSERT)
    insert_counts = Counter()
    insert_layers = defaultdict(Counter)
    for e in entities:
        if e.dxftype() == 'INSERT':
            name = e.dxf.name
            layer = e.dxf.layer
            insert_counts[name] += 1
            insert_layers[layer][name] += 1

    # Dimensões
    dim_styles = Counter()
    for e in entities:
        if e.dxftype() == 'DIMENSION':
            ds = e.dxf.get('dimstyle', 'Standard')
            dim_styles[ds] += 1

    # Textos (TEXT + MTEXT)
    texts = []
    for e in entities:
        if e.dxftype() == 'TEXT':
            txt = e.dxf.get('text', '')
            if txt and verbose:
                texts.append({'text': txt, 'layer': e.dxf.layer,
                               'height': e.dxf.get('height', 0)})
        elif e.dxftype() == 'MTEXT':
            txt = e.text if hasattr(e, 'text') else ''
            if txt and verbose:
                texts.append({'text': txt[:50], 'layer': e.dxf.layer})

    # Hatch
    hatch_layers = Counter(e.dxf.layer for e in entities if e.dxftype() == 'HATCH')

    # Polylines
    pline_layers = Counter(e.dxf.layer for e in entities if e.dxftype() in ('LWPOLYLINE', 'POLYLINE'))
    line_layers = Counter(e.dxf.layer for e in entities if e.dxftype() == 'LINE')

    # Bounding box aproximada
    try:
        bbox = BoundingBox()
        for e in entities:
            if hasattr(e, 'dxf') and hasattr(e.dxf, 'start'):
                bbox.extend([e.dxf.start])
            if hasattr(e, 'dxf') and hasattr(e.dxf, 'end'):
                bbox.extend([e.dxf.end])
        bbox_info = {
            'min': list(bbox.extmin)[:2] if bbox.has_data else [0, 0],
            'max': list(bbox.extmax)[:2] if bbox.has_data else [0, 0],
        }
    except:
        bbox_info = {'min': [0, 0], 'max': [0, 0]}

    result = {
        'file': path.name,
        'size_bytes': path.stat().st_size,
        'total_entities': len(entities),
        'layers': dict(layer_counts),
        'types': dict(type_counts),
        'inserts': dict(insert_counts),
        'insert_by_layer': {k: dict(v) for k, v in insert_layers.items()},
        'dim_styles': dict(dim_styles),
        'hatch_layers': dict(hatch_layers),
        'pline_by_layer': dict(pline_layers),
        'line_by_layer': dict(line_layers),
        'bbox': bbox_info,
    }

    if verbose and texts:
        result['texts'] = texts[:20]

    return result


def comparar_dois_dxf(path_a, path_b, label_a='AutoCAD', label_b='ezdxf'):
    """Compara dois DXFs lado a lado."""
    da = analisar_dxf(path_a)
    db = analisar_dxf(path_b)

    if 'error' in da:
        print(f"ERRO {label_a}: {da['error']}")
        return None
    if 'error' in db:
        print(f"ERRO {label_b}: {db['error']}")
        return None

    # Layers diff
    all_layers = sorted(set(list(da['layers'].keys()) + list(db['layers'].keys())))

    rows = []
    for layer in all_layers:
        ra = da['layers'].get(layer, 0)
        rb = db['layers'].get(layer, 0)
        if ra > 0:
            ratio = rb / ra
        elif rb > 0:
            ratio = float('inf')
        else:
            continue
        rows.append({'layer': layer, label_a: ra, label_b: rb, 'ratio': round(ratio, 3)})

    # Types diff
    all_types = sorted(set(list(da['types'].keys()) + list(db['types'].keys())))
    type_rows = []
    for t in all_types:
        ra = da['types'].get(t, 0)
        rb = db['types'].get(t, 0)
        type_rows.append({'type': t, label_a: ra, label_b: rb})

    # Inserts diff
    all_inserts = sorted(set(list(da['inserts'].keys()) + list(db['inserts'].keys())))
    insert_rows = []
    for ins in all_inserts:
        ra = da['inserts'].get(ins, 0)
        rb = db['inserts'].get(ins, 0)
        insert_rows.append({'block': ins, label_a: ra, label_b: rb})

    return {
        'file_a': path_a,
        'file_b': path_b,
        'total': {label_a: da['total_entities'], label_b: db['total_entities']},
        'layers': rows,
        'types': type_rows,
        'inserts': insert_rows,
    }


def print_comparacao(comp, label_a='AutoCAD', label_b='ezdxf'):
    """Imprime comparação formatada."""
    if comp is None:
        return

    ta = comp['total'][label_a]
    tb = comp['total'][label_b]
    ratio = tb / ta if ta > 0 else 0
    print(f"\n{'='*60}")
    print(f"TOTAL: {label_a}={ta}  {label_b}={tb}  ratio={ratio:.2f}")
    print(f"{'='*60}")

    print(f"\n{'Layer':<30} {label_a:>8} {label_b:>8} {'Ratio':>7} Status")
    print('-' * 60)
    for r in comp['layers']:
        layer = r['layer']
        ra = r[label_a]
        rb = r[label_b]
        ratio = r['ratio']
        if ratio == float('inf'):
            status = 'NEW'
        elif ratio > 0.9:
            status = 'OK'
        elif ratio > 0.5:
            status = 'PARTIAL'
        elif ratio == 0:
            status = 'MISS'
        else:
            status = 'LOW'
        print(f"  {layer:<28} {ra:>8} {rb:>8} {ratio:>7.2f} {status}")

    print(f"\n{'Type':<20} {label_a:>8} {label_b:>8}")
    print('-' * 40)
    for r in comp['types']:
        print(f"  {r['type']:<18} {r[label_a]:>8} {r[label_b]:>8}")

    if comp['inserts']:
        print(f"\n{'Block':<25} {label_a:>8} {label_b:>8}")
        print('-' * 45)
        for r in comp['inserts']:
            print(f"  {r['block']:<23} {r[label_a]:>8} {r[label_b]:>8}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dxf', help='Arquivo DXF para analisar')
    parser.add_argument('--compare', nargs=2, metavar=('DXF_A', 'DXF_B'),
                        help='Comparar dois DXFs')
    parser.add_argument('--dir', help='Analisar todos os DXF de um diretório')
    parser.add_argument('--output', help='Salvar resultado em JSON')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    if args.compare:
        comp = comparar_dois_dxf(args.compare[0], args.compare[1])
        print_comparacao(comp)
        if args.output and comp:
            Path(args.output).write_text(json.dumps(comp, indent=2, ensure_ascii=False))
        return

    if args.dxf:
        result = analisar_dxf(args.dxf, verbose=args.verbose)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return

    if args.dir:
        d = Path(args.dir)
        dxfs = sorted(d.glob('*.dxf'))
        print(f"Analisando {len(dxfs)} DXFs em {d.name}...")
        results = {}
        for dxf in dxfs:
            r = analisar_dxf(dxf, verbose=args.verbose)
            results[dxf.name] = r
            total = r.get('total_entities', 0)
            layers = len(r.get('layers', {}))
            print(f"  {dxf.name}: {total} entities, {layers} layers")

        if args.output:
            Path(args.output).write_text(json.dumps(results, indent=2, ensure_ascii=False))
            print(f"Salvo em: {args.output}")
        return

    parser.print_help()


if __name__ == '__main__':
    main()
