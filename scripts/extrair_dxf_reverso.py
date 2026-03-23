"""
Engenharia Reversa DXF — extrator completo de geometria real dos robôs.
Analisa PL, LV, LJ, FV de 3 pavimentos de 5 obras diferentes.
Extrai: layers, entity types, blocks, texts, dimensions, hatches, polylines.
"""
import sys, os, json, math
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

try:
    import ezdxf
    from ezdxf.math import Vec2, Vec3
    HAS_EZDXF = True
except ImportError:
    print("ERRO: ezdxf nao instalado. Execute: pip install ezdxf")
    sys.exit(1)

# ── Amostras selecionadas (3 pavimentos de 5 obras) ──────────────────────────

BASE = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
REV = "Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"

SAMPLES = {
    "PL": [
        # Obra_TREINO_1 (ALIMONTI)
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- PL - R00.dxf",
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - 1° PAV.- PL - R00.dxf",
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TÉRREO - PL - R00.dxf",
        # Obra_TREINO_11 (GWT-SCHWARTZ)
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-PL-R01_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TER-PL-R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-1PV-PL-R00_R2018_ASCII_ODA.dxf",
        # Obra_TREINO_13 (LEAF)
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO - PL - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TER - PL - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - 1PV - PL - R00_R2018_ASCII_ODA.dxf",
        # Obra_TREINO_5 (D'URSO EMBRAMACO)
        BASE / "Obra_TREINO_5" / REV / "NOVA-D´URSO-EMBRAMACO-TER-PL-R01_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_5" / REV / "NOVA-D´URSO-EMBRAMACO-1PV-PL-R02_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_5" / REV / "NOVA-D´URSO-EMBRAMACO-2PV-PL-R00_R2018_ASCII_ODA.dxf",
        # Obra_TREINO_10 (ROCONTEC)
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO -  1°SS - TRECHO 1- PL- R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO - 4° PAV.- PL- R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO - 7° PAV.- PL- R00_R2018_ASCII_ODA.dxf",
    ],
    "LV": [
        # Obra_TREINO_1
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- LV - R00.dxf",
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - 1° PAV.- LV - R00.dxf",
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TÉRREO - LV - R00.dxf",
        # Obra_TREINO_11
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-LV-R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TER-LV-R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-1PV-LV-R00_R2018_ASCII_ODA.dxf",
        # Obra_TREINO_13
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO  - LV - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TER  - LV - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - 1PV  - LV - R00_R2018_ASCII_ODA.dxf",
        # Obra_TREINO_5
        BASE / "Obra_TREINO_5" / REV / "NOVA-D´URSO-EMBRAMACO-TER-LV-R02_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_5" / REV / "NOVA-D´URSO-EMBRAMACO-1PV-LV-R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_5" / REV / "NOVA-D´URSO-EMBRAMACO-2PV-LV-R00_R2018_ASCII_ODA.dxf",
        # Obra_TREINO_10
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO -  1°SS - TRECHO I- LV - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO - 4° PAV.- LV - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO - 3° PAV.- LV - R00_R2018_ASCII_ODA.dxf",
    ],
    "LJ": [
        # Obra_TREINO_1
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- LJ - R00.dxf",
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - 1° PAV.- LJ - R01.dxf",
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TÉRREO - LJ - R00.dxf",
        # Obra_TREINO_11
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-LJ-R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TER-LJ-R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-1PV-LJ-R00_R2018_ASCII_ODA.dxf",
        # Obra_TREINO_13
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO - LJ - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TER - LJ - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - 1PV - LJ - R00_R2018_ASCII_ODA.dxf",
        # Obra_TREINO_10
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO -  1°SS - TRECHO 1- LJ- R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO - 2°SS - TRECHO 3- LJ - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO - 1°SS - TRECHO 3- LJ - R00_R2018_ASCII_ODA.dxf",
        # Obra_TREINO_5 (sem LJ, usar Obra_TREINO_3 ou 6 se existir)
    ],
    "FV": [
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- FV - R00.dxf",
        BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - 1° PAV.- FV - R00.dxf",
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-FV-R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TER-FV-R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TIPO - FV - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_13" / REV / "SKR - LEAF - TER - FV - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_5" / REV / "NOVA-D´URSO-EMBRAMACO-TER-FV-R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO - 1°SS - TRECHO 1 - FV - R00_R2018_ASCII_ODA.dxf",
        BASE / "Obra_TREINO_10" / REV / "ROCONTEC - HOSPITAL ASSUNÇÃO - 4° PAV.- FV - R00_R2018_ASCII_ODA.dxf",
    ],
}


# ── Extrator ─────────────────────────────────────────────────────────────────

def bbox(pts):
    """Bounding box de lista de pontos (x,y)."""
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return {
        'xmin': round(min(xs), 1), 'xmax': round(max(xs), 1),
        'ymin': round(min(ys), 1), 'ymax': round(max(ys), 1),
        'width': round(max(xs)-min(xs), 1), 'height': round(max(ys)-min(ys), 1),
    }

def get_lwpoly_points(e):
    pts = []
    try:
        for x, y in e.get_points('xy'):
            pts.append((round(x,1), round(y,1)))
    except:
        pass
    return pts

def get_lwpoly_bulges(e):
    bulges = []
    try:
        pts = list(e.get_points('xyb'))
        for _, _, b in pts:
            if abs(b) > 0.001:
                bulges.append(round(b,4))
    except:
        pass
    return bulges

def analyze_dxf(path: Path) -> dict:
    """Analisa um DXF e extrai toda informação relevante."""
    result = {
        'file': path.name,
        'obra': path.parts[-4] if len(path.parts) >= 4 else '?',
        'exists': path.exists(),
        'layers': {},
        'blocks': [],
        'entity_counts': defaultdict(int),
        'texts': [],
        'dimensions': [],
        'hatches': [],
        'polylines': [],
        'inserts': [],
        'lines': [],
        'circles': [],
        'arcs': [],
        'bounding_box': None,
    }

    if not path.exists():
        result['error'] = 'file not found'
        return result

    try:
        doc = ezdxf.readfile(str(path))
    except Exception as ex:
        result['error'] = str(ex)
        return result

    msp = doc.modelspace()

    # Layers
    for layer in doc.layers:
        result['layers'][layer.dxf.name] = {
            'color': layer.dxf.color,
            'linetype': getattr(layer.dxf, 'linetype', 'Continuous'),
        }

    # Blocos definidos no documento
    for block in doc.blocks:
        if not block.name.startswith('*'):
            result['blocks'].append(block.name)

    # Todos os pontos para bounding box geral
    all_pts = []

    # Iterar entidades
    for e in msp:
        etype = e.dxftype()
        layer = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'
        result['entity_counts'][etype] += 1

        if etype == 'LWPOLYLINE':
            pts = get_lwpoly_points(e)
            bulges = get_lwpoly_bulges(e)
            closed = bool(e.is_closed)
            if len(all_pts) < 50000:
                all_pts.extend(pts[:20])
            bb = bbox(pts)
            poly_info = {
                'layer': layer,
                'pts_count': len(pts),
                'closed': closed,
                'has_arcs': len(bulges) > 0,
                'bulges': bulges[:4],
                'bbox': bb,
            }
            # Amostra dos primeiros pontos
            if pts:
                poly_info['sample_pts'] = pts[:4]
            result['polylines'].append(poly_info)

        elif etype == 'LINE':
            try:
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                length = round(math.hypot(x2-x1, y2-y1), 1)
                # Apenas acumular pontos para bbox (sem guardar cada linha — pode ser milhares)
                if len(all_pts) < 50000:
                    all_pts.append((x1,y1))
                # Guardar apenas amostra das primeiras 100 lines por layer
                if len(result['lines']) < 100:
                    result['lines'].append({
                        'layer': layer,
                        'start': (round(x1,1), round(y1,1)),
                        'end': (round(x2,1), round(y2,1)),
                        'length': length,
                    })
            except:
                pass

        elif etype in ('TEXT', 'MTEXT'):
            try:
                if etype == 'TEXT':
                    txt = e.dxf.text
                    x, y = e.dxf.insert.x, e.dxf.insert.y
                    h = round(getattr(e.dxf, 'height', 0), 1)
                else:
                    txt = e.plain_mtext() if hasattr(e, 'plain_mtext') else e.text
                    x, y = e.dxf.insert.x, e.dxf.insert.y
                    h = round(getattr(e.dxf, 'char_height', 0), 1)
                result['texts'].append({
                    'type': etype,
                    'layer': layer,
                    'text': txt[:80],
                    'pos': (round(x,1), round(y,1)),
                    'height': h,
                })
                all_pts.append((x,y))
            except:
                pass

        elif etype in ('DIMENSION', 'ALIGNED_DIMENSION', 'LINEAR_DIMENSION',
                       'ROTATED_DIMENSION', 'RADIAL_DIMENSION', 'DIAMETRIC_DIMENSION'):
            try:
                dimval = None
                try:
                    dimval = round(e.get_measurement(), 1)
                except:
                    pass
                result['dimensions'].append({
                    'type': etype,
                    'layer': layer,
                    'value': dimval,
                    'dimtype': getattr(e.dxf, 'dimtype', None),
                })
            except:
                pass

        elif etype == 'HATCH':
            try:
                pattern_name = e.dxf.pattern_name
                solid = bool(e.dxf.solid_fill)
                assoc_count = 0
                try:
                    for path_ in e.paths:
                        assoc_count += 1
                except:
                    pass
                result['hatches'].append({
                    'layer': layer,
                    'pattern': pattern_name,
                    'solid': solid,
                    'paths': assoc_count,
                })
            except:
                pass

        elif etype == 'INSERT':
            try:
                bname = e.dxf.name
                x, y = e.dxf.insert.x, e.dxf.insert.y
                sx = round(getattr(e.dxf, 'xscale', 1.0), 3)
                sy = round(getattr(e.dxf, 'yscale', 1.0), 3)
                rot = round(getattr(e.dxf, 'rotation', 0), 1)
                result['inserts'].append({
                    'block': bname,
                    'layer': layer,
                    'pos': (round(x,1), round(y,1)),
                    'scale': (sx, sy),
                    'rotation': rot,
                })
                all_pts.append((x,y))
            except:
                pass

        elif etype == 'CIRCLE':
            try:
                x, y = e.dxf.center.x, e.dxf.center.y
                r = round(e.dxf.radius, 1)
                result['circles'].append({'layer': layer, 'center': (round(x,1), round(y,1)), 'radius': r})
                all_pts.append((x,y))
            except:
                pass

        elif etype == 'ARC':
            try:
                x, y = e.dxf.center.x, e.dxf.center.y
                r = round(e.dxf.radius, 1)
                result['arcs'].append({'layer': layer, 'center': (round(x,1), round(y,1)), 'radius': r})
            except:
                pass

    result['entity_counts'] = dict(result['entity_counts'])

    if all_pts:
        result['bounding_box'] = bbox(all_pts)

    return result


# ── Sumarização ───────────────────────────────────────────────────────────────

def summarize(analyses: list, tipo: str) -> dict:
    """Gera sumário estatístico de múltiplas análises."""
    layers_all = defaultdict(int)
    blocks_all = defaultdict(int)
    entity_counts_all = defaultdict(int)
    patterns_all = defaultdict(int)
    insert_blocks_all = defaultdict(int)
    text_samples = []
    dim_samples = []
    poly_stats = {'counts': [], 'has_arcs_count': 0, 'closed_count': 0}
    bbox_list = []

    for a in analyses:
        if 'error' in a:
            continue
        for layer in a['layers']:
            layers_all[layer] += 1
        for block in a['blocks']:
            blocks_all[block] += 1
        for etype, cnt in a['entity_counts'].items():
            entity_counts_all[etype] += cnt
        for h in a['hatches']:
            patterns_all[h['pattern']] += 1
        for ins in a['inserts']:
            insert_blocks_all[ins['block']] += 1
        for t in a['texts'][:5]:
            text_samples.append({'file': a['file'][:40], 'layer': t['layer'], 'text': t['text'], 'height': t['height']})
        for d in a['dimensions'][:3]:
            dim_samples.append({'file': a['file'][:40], 'value': d['value'], 'type': d['type']})
        for p in a['polylines']:
            poly_stats['counts'].append(p['pts_count'])
            if p['has_arcs']:
                poly_stats['has_arcs_count'] += 1
            if p['closed']:
                poly_stats['closed_count'] += 1
        if a.get('bounding_box'):
            bbox_list.append(a['bounding_box'])

    return {
        'tipo': tipo,
        'arquivos_analisados': sum(1 for a in analyses if 'error' not in a),
        'arquivos_nao_encontrados': sum(1 for a in analyses if a.get('error') == 'file not found'),
        'layers_presentes': dict(sorted(layers_all.items(), key=lambda x: -x[1])),
        'blocks_definidos': dict(sorted(blocks_all.items(), key=lambda x: -x[1])),
        'entity_totals': dict(sorted(entity_counts_all.items(), key=lambda x: -x[1])),
        'hatch_patterns': dict(sorted(patterns_all.items(), key=lambda x: -x[1])),
        'insert_blocks': dict(sorted(insert_blocks_all.items(), key=lambda x: -x[1])),
        'text_samples': text_samples[:20],
        'dim_samples': dim_samples[:10],
        'polyline_stats': {
            'total': len(poly_stats['counts']),
            'avg_pts': round(sum(poly_stats['counts'])/max(1,len(poly_stats['counts'])),1),
            'min_pts': min(poly_stats['counts'], default=0),
            'max_pts': max(poly_stats['counts'], default=0),
            'has_arcs': poly_stats['has_arcs_count'],
            'closed': poly_stats['closed_count'],
        },
        'bboxes': bbox_list,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    out = {}
    details = {}

    for tipo, paths in SAMPLES.items():
        print(f"\n{'='*60}")
        print(f"Analisando tipo: {tipo} ({len(paths)} arquivos)")
        analyses = []
        for p in paths:
            print(f"  {'OK' if p.exists() else 'NOT FOUND':10} {p.name[:60]}")
            a = analyze_dxf(p)
            analyses.append(a)

        sumario = summarize(analyses, tipo)
        out[tipo] = sumario
        details[tipo] = analyses

        print(f"\n  Layers encontrados ({len(sumario['layers_presentes'])}):")
        for l, cnt in list(sumario['layers_presentes'].items())[:20]:
            print(f"    [{cnt:2d}x] {l}")

        print(f"\n  Entidades totais:")
        for et, cnt in list(sumario['entity_totals'].items())[:10]:
            print(f"    {et:20} {cnt:5d}")

        print(f"\n  Blocos (INSERT):")
        for b, cnt in list(sumario['insert_blocks'].items())[:10]:
            print(f"    [{cnt:3d}x] {b}")

        print(f"\n  Hatch patterns: {sumario['hatch_patterns']}")

        print(f"\n  LWPOLYLINE stats: {sumario['polyline_stats']}")

    # Salvar JSON completo
    out_path = Path("D:/Agente-cad-PYSIDE/docs/fichas/dxf_reverso_analise.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'sumarios': out, 'detalhes': details}, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n\nJSON completo salvo em: {out_path}")

    return out

if __name__ == '__main__':
    result = main()
