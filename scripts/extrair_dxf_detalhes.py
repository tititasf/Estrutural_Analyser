"""
Extração detalhada de um DXF por tipo — layers com cores, blocos definidos,
amostras de geometria por layer, textos reais, dimensões reais.
Para guiar o atlas com desenho técnico idêntico ao real.
"""
import sys, json, math
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
import ezdxf
from ezdxf.math import Vec2

BASE = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
REV  = "Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"

# Um arquivo representativo de cada tipo
FILES = {
    "PL": BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-PL-R01_R2018_ASCII_ODA.dxf",
    "LV": BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-LV-R00_R2018_ASCII_ODA.dxf",
    "LJ": BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-LJ-R00_R2018_ASCII_ODA.dxf",
    "FV": BASE / "Obra_TREINO_11" / REV / "NOVA-SCHWARTZ-GWT-TIP-FV-R00_R2018_ASCII_ODA.dxf",
}

ACI_TO_RGB = {
    1:  (255,   0,   0),   # red
    2:  (255, 255,   0),   # yellow
    3:  (  0, 255,   0),   # green
    4:  (  0, 255, 255),   # cyan
    5:  (  0,   0, 255),   # blue
    6:  (255,   0, 255),   # magenta
    7:  (255, 255, 255),   # white
    8:  (128, 128, 128),   # gray
    9:  (192, 192, 192),   # light gray
    10: (255,   0,   0),
    11: (255, 127, 127),
    12: (204,   0,   0),
    13: (204, 102, 102),
    14: (153,   0,   0),
    15: (153,  76,  76),
    16: (127,   0,   0),
    17: (127,  63,  63),
    18: (76,    0,   0),
    19: (76,   38,  38),
    20: (255,  63,   0),
    21: (255, 159, 127),
    22: (204,  50,   0),
    23: (204, 127, 102),
    24: (153,  38,   0),
    25: (153,  95,  76),
    30: (255, 127,   0),
    40: (255, 191,   0),
    50: (255, 255,   0),
    60: (127, 255,   0),
    70: (  0, 255,   0),
    80: (  0, 255, 127),
    90: (  0, 255, 255),
    100:(  0, 127, 255),
    110:(  0,   0, 255),
    120:(127,   0, 255),
    130:(255,   0, 255),
    140:(255,   0, 127),
    150:(255,   0,  63),
    160:(51,   51,  51),
    161:(80,   80,  80),
    250:(51,   51,  51),
    251:(91,   91,  91),
    252:(132, 132, 132),
    253:(173, 173, 173),
    254:(214, 214, 214),
    255:(255, 255, 255),
}

def aci_rgb(color_idx):
    return ACI_TO_RGB.get(color_idx, (200, 200, 200))

def analyze_blocks(doc):
    """Analisa blocos definidos no documento."""
    block_info = {}
    for block in doc.blocks:
        name = block.name
        if name.startswith('*'):
            continue
        entities = []
        for e in block:
            etype = e.dxftype()
            layer = getattr(e.dxf, 'layer', '0')
            entities.append({'type': etype, 'layer': layer})
        if entities:
            counts = defaultdict(int)
            for en in entities:
                counts[en['type']] += 1
            block_info[name] = {
                'total_entities': len(entities),
                'entity_types': dict(counts),
            }
    return block_info

def get_pts_from_entity(e):
    """Retorna lista de (x,y) de uma entidade."""
    etype = e.dxftype()
    pts = []
    try:
        if etype == 'LWPOLYLINE':
            for x, y in e.get_points('xy'):
                pts.append((x, y))
        elif etype == 'LINE':
            pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
        elif etype in ('TEXT', 'MTEXT', 'INSERT', 'CIRCLE', 'ARC'):
            ins = e.dxf.insert if hasattr(e.dxf, 'insert') else (
                  e.dxf.center if hasattr(e.dxf, 'center') else None)
            if ins:
                pts = [(ins.x, ins.y)]
    except:
        pass
    return pts

def analyze_layers_geometry(msp, layers_info):
    """Por layer: amostra de geometrias, tipos de entidades, textos."""
    layer_data = defaultdict(lambda: {
        'entity_types': defaultdict(int),
        'texts': [],
        'poly_samples': [],
        'line_lengths': [],
        'inserts': [],
        'hatches': [],
        'dim_values': [],
    })

    for e in msp:
        etype = e.dxftype()
        layer = getattr(e.dxf, 'layer', '0') if hasattr(e, 'dxf') else '0'
        ld = layer_data[layer]
        ld['entity_types'][etype] += 1

        if etype in ('TEXT', 'MTEXT'):
            try:
                if etype == 'TEXT':
                    txt = e.dxf.text
                    h = round(getattr(e.dxf, 'height', 0), 2)
                else:
                    txt = e.plain_mtext() if hasattr(e, 'plain_mtext') else e.text
                    h = round(getattr(e.dxf, 'char_height', 0), 2)
                if len(ld['texts']) < 20:
                    ld['texts'].append({'text': txt[:60], 'height': h})
            except:
                pass

        elif etype == 'LWPOLYLINE':
            try:
                pts = list(e.get_points('xyb'))
                closed = e.is_closed
                has_arc = any(abs(p[2]) > 0.001 for p in pts)
                npts = len(pts)
                if len(ld['poly_samples']) < 10:
                    sample_pts = [(round(p[0],1), round(p[1],1)) for p in pts[:6]]
                    ld['poly_samples'].append({
                        'npts': npts, 'closed': closed, 'has_arc': has_arc,
                        'pts': sample_pts,
                    })
            except:
                pass

        elif etype == 'LINE':
            try:
                x1, y1 = e.dxf.start.x, e.dxf.start.y
                x2, y2 = e.dxf.end.x, e.dxf.end.y
                length = round(math.hypot(x2-x1, y2-y1), 1)
                if len(ld['line_lengths']) < 50:
                    ld['line_lengths'].append(length)
            except:
                pass

        elif etype == 'INSERT':
            try:
                bname = e.dxf.name
                x, y = e.dxf.insert.x, e.dxf.insert.y
                sx = round(getattr(e.dxf, 'xscale', 1.0), 3)
                sy = round(getattr(e.dxf, 'yscale', 1.0), 3)
                rot = round(getattr(e.dxf, 'rotation', 0), 1)
                if len(ld['inserts']) < 20:
                    ld['inserts'].append({
                        'block': bname,
                        'pos': (round(x,1), round(y,1)),
                        'scale': (sx, sy),
                        'rot': rot,
                    })
            except:
                pass

        elif etype == 'HATCH':
            try:
                pattern = e.dxf.pattern_name
                solid = bool(e.dxf.solid_fill)
                if len(ld['hatches']) < 10:
                    ld['hatches'].append({'pattern': pattern, 'solid': solid})
            except:
                pass

        elif etype == 'DIMENSION':
            try:
                val = round(e.get_measurement(), 1)
                if len(ld['dim_values']) < 20:
                    ld['dim_values'].append(val)
            except:
                pass

    # Converte defaultdict para dict normal
    result = {}
    for layer, data in layer_data.items():
        result[layer] = {
            'entity_types': dict(data['entity_types']),
            'texts': data['texts'],
            'poly_samples': data['poly_samples'],
            'line_lengths_sample': sorted(data['line_lengths'])[:20],
            'line_lengths_stats': {
                'count': len(data['line_lengths']),
                'min': round(min(data['line_lengths']), 1) if data['line_lengths'] else 0,
                'max': round(max(data['line_lengths']), 1) if data['line_lengths'] else 0,
                'avg': round(sum(data['line_lengths'])/max(1,len(data['line_lengths'])), 1),
            },
            'inserts': data['inserts'],
            'hatches': data['hatches'],
            'dim_values': sorted(data['dim_values'])[:15],
        }
    return result


def analyze_file(tipo, path):
    print(f"\n{'='*70}")
    print(f"TIPO: {tipo} | {path.name}")

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    # Layer colors
    layers_info = {}
    for layer in doc.layers:
        name = layer.dxf.name
        color = layer.dxf.color
        rgb = aci_rgb(abs(color)) if color != 0 else (255,255,255)
        linetype = getattr(layer.dxf, 'linetype', 'Continuous')
        layers_info[name] = {
            'aci': color,
            'rgb': rgb,
            'linetype': linetype,
        }

    print(f"\n[LAYERS COM CORES]")
    for lname, ldata in sorted(layers_info.items()):
        if lname in ('Defpoints',):
            continue
        rgb = ldata['rgb']
        print(f"  {lname:30} ACI={ldata['aci']:4d}  RGB=({rgb[0]:3d},{rgb[1]:3d},{rgb[2]:3d})  LT={ldata['linetype']}")

    # Blocos definidos
    block_info = analyze_blocks(doc)
    print(f"\n[BLOCOS DEFINIDOS] ({len(block_info)} blocos)")
    for bname, bdata in sorted(block_info.items(), key=lambda x: -x[1]['total_entities'])[:20]:
        print(f"  {bname:40} {bdata['total_entities']:5d} entidades  {bdata['entity_types']}")

    # Geometria por layer
    layer_geom = analyze_layers_geometry(msp, layers_info)

    print(f"\n[GEOMETRIA POR LAYER]")
    for lname, ldata in sorted(layer_geom.items(), key=lambda x: -sum(x[1]['entity_types'].values()))[:25]:
        total = sum(ldata['entity_types'].values())
        print(f"\n  --- Layer: {lname} ({total} entidades) ---")
        print(f"      Tipos: {ldata['entity_types']}")
        if ldata['texts']:
            print(f"      Textos ({len(ldata['texts'])}): {[t['text'] for t in ldata['texts'][:5]]}")
        if ldata['poly_samples']:
            for p in ldata['poly_samples'][:3]:
                print(f"      Poly: {p['npts']}pts  closed={p['closed']}  arc={p['has_arc']}  pts={p['pts'][:3]}")
        if ldata['line_lengths_stats']['count'] > 0:
            s = ldata['line_lengths_stats']
            print(f"      Lines: n={s['count']}  min={s['min']}  max={s['max']}  avg={s['avg']}")
        if ldata['inserts']:
            for ins in ldata['inserts'][:3]:
                print(f"      Insert: {ins['block']:30} pos={ins['pos']}  scale={ins['scale']}  rot={ins['rot']}")
        if ldata['hatches']:
            print(f"      Hatches: {ldata['hatches'][:5]}")
        if ldata['dim_values']:
            print(f"      Dims (cm): {ldata['dim_values'][:10]}")

    return {
        'layers': layers_info,
        'blocks': block_info,
        'layer_geometry': layer_geom,
    }


def main():
    all_data = {}
    for tipo, path in FILES.items():
        if not path.exists():
            print(f"SKIP {tipo}: {path.name} não encontrado")
            continue
        data = analyze_file(tipo, path)
        all_data[tipo] = data

    out_path = Path("D:/Agente-cad-PYSIDE/docs/fichas/dxf_detalhes_por_tipo.json")
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n\nDetalhes salvos em: {out_path}")

if __name__ == '__main__':
    main()
