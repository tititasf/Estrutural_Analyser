"""
Extrai geometria completa de UN pilar individual do DXF real.
Identifica agrupamentos de painéis, sarrafos, pontaletes por pilar.
"""
import sys, json, math
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
import ezdxf

BASE = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
REV  = "Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"

# Usar um arquivo mais simples — ALIMONTI TIPO (12 pavimentos típicos — estrutura mais clara)
FILE_PL = BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- PL - R00.dxf"
FILE_LV = BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- LV - R00.dxf"
FILE_LJ = BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- LJ - R00.dxf"
FILE_FV = BASE / "Obra_TREINO_1" / REV / "ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- FV - R00.dxf"

def bbox_pts(pts):
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))

def get_entity_info(e):
    etype = e.dxftype()
    layer = getattr(e.dxf, 'layer', '0') if hasattr(e, 'dxf') else '0'
    data = {'type': etype, 'layer': layer}

    if etype == 'LWPOLYLINE':
        try:
            pts = [(round(x,1), round(y,1)) for x,y in e.get_points('xy')]
            bulges = [round(b,4) for _,_,b in e.get_points('xyb') if abs(b)>0.001]
            data['pts'] = pts
            data['closed'] = e.is_closed
            data['has_arc'] = len(bulges) > 0
            data['bulges'] = bulges
            if pts:
                bb = bbox_pts(pts)
                data['bbox'] = bb
                data['width'] = round(bb[2]-bb[0], 1)
                data['height'] = round(bb[3]-bb[1], 1)
        except Exception as ex:
            data['err'] = str(ex)

    elif etype == 'LINE':
        try:
            x1, y1 = e.dxf.start.x, e.dxf.start.y
            x2, y2 = e.dxf.end.x, e.dxf.end.y
            data['start'] = (round(x1,1), round(y1,1))
            data['end'] = (round(x2,1), round(y2,1))
            data['length'] = round(math.hypot(x2-x1, y2-y1), 1)
        except:
            pass

    elif etype in ('TEXT', 'MTEXT'):
        try:
            if etype == 'TEXT':
                data['text'] = e.dxf.text
                data['pos'] = (round(e.dxf.insert.x,1), round(e.dxf.insert.y,1))
                data['height'] = round(e.dxf.height, 2)
            else:
                data['text'] = (e.plain_mtext() if hasattr(e, 'plain_mtext') else e.text)[:100]
                data['pos'] = (round(e.dxf.insert.x,1), round(e.dxf.insert.y,1))
        except:
            pass

    elif etype == 'INSERT':
        try:
            data['block'] = e.dxf.name
            data['pos'] = (round(e.dxf.insert.x,1), round(e.dxf.insert.y,1))
            data['scale'] = (round(getattr(e.dxf,'xscale',1),3), round(getattr(e.dxf,'yscale',1),3))
            data['rot'] = round(getattr(e.dxf,'rotation',0), 1)
        except:
            pass

    elif etype == 'DIMENSION':
        try:
            data['value'] = round(e.get_measurement(), 1)
            if hasattr(e.dxf, 'defpoint'):
                data['defpoint'] = (round(e.dxf.defpoint.x,1), round(e.dxf.defpoint.y,1))
        except:
            pass

    elif etype == 'HATCH':
        try:
            data['pattern'] = e.dxf.pattern_name
            data['solid'] = bool(e.dxf.solid_fill)
        except:
            pass

    elif etype == 'ARC':
        try:
            data['center'] = (round(e.dxf.center.x,1), round(e.dxf.center.y,1))
            data['radius'] = round(e.dxf.radius, 1)
            data['start_angle'] = round(e.dxf.start_angle, 1)
            data['end_angle'] = round(e.dxf.end_angle, 1)
        except:
            pass

    elif etype == 'CIRCLE':
        try:
            data['center'] = (round(e.dxf.center.x,1), round(e.dxf.center.y,1))
            data['radius'] = round(e.dxf.radius, 1)
        except:
            pass

    return data


def analyze_file_full(path, tipo):
    print(f"\n{'='*70}")
    print(f"[{tipo}] {path.name}")
    if not path.exists():
        print(f"  ARQUIVO NÃO ENCONTRADO!")
        return

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    # Coleta TUDO por layer
    by_layer = defaultdict(list)
    all_pts = []

    count = 0
    for e in msp:
        info = get_entity_info(e)
        layer = info['layer']
        by_layer[layer].append(info)

        # Coletar pts para bbox global
        pts = info.get('pts', [])
        if pts and len(all_pts) < 10000:
            all_pts.extend(pts[:4])
        pos = info.get('pos')
        if pos:
            all_pts.append(pos)
        s = info.get('start')
        if s and len(all_pts) < 10000:
            all_pts.append(s)
        count += 1

    # Bbox global
    if all_pts:
        bb = bbox_pts(all_pts)
        print(f"\n  Bounding Box Global: x=[{bb[0]:.0f}, {bb[2]:.0f}] y=[{bb[1]:.0f}, {bb[3]:.0f}]")
        print(f"  Dimensão total: {(bb[2]-bb[0]):.0f} x {(bb[3]-bb[1]):.0f} mm")
        print(f"  Total entidades: {count}")

    # Análise por layer com estatísticas de posição
    print(f"\n  LAYERS PRESENTES ({len(by_layer)}):")
    for layer in sorted(by_layer.keys(), key=lambda l: -len(by_layer[l]))[:30]:
        entities = by_layer[layer]
        types = defaultdict(int)
        for e in entities:
            types[e['type']] += 1

        # Stats de posição para entender o layout
        pts_layer = []
        for e in entities:
            for p in e.get('pts', [])[:2]:
                pts_layer.append(p)
            if e.get('pos'):
                pts_layer.append(e['pos'])
            if e.get('start'):
                pts_layer.append(e['start'])

        pos_info = ""
        if pts_layer:
            bb = bbox_pts(pts_layer)
            pos_info = f"  bbox=[{bb[0]:.0f},{bb[1]:.0f}..{bb[2]:.0f},{bb[3]:.0f}] ({bb[2]-bb[0]:.0f}x{bb[3]-bb[1]:.0f})"

        print(f"    {layer:30} {len(entities):4d} ent | {dict(types)}{pos_info}")

    # Análise detalhada dos layers mais importantes
    LAYERS_DETAIL = {
        'PL': ['Painéis', 'Pain\u00e9is', 'SARRAFO', 'SARR_2.2x7', 'Madeira', 'COTA', 'CONCRETO',
               'BARRA ANCORAGEM', 'CHAPA', 'Perfil Met\u00e1lico', 'NOMENCLATURA',
               'Texto Se\u00e7\u00e3o', 'TEXTO_GERAL', 'texto', 'Sarrafo de Press\u00e3o',
               'SARRAFO DE PRESSAO', 'Laje_Perimetro', 'Folhas', 'Hachura'],
        'LV': ['Painéis', 'Pain\u00e9is', 'SARRAFO', 'SARR_2.2x7', 'Madeira', 'COTA',
               'BARRA DE ANCORAGEM', 'GARFOS', 'Escoras', 'Forcador', 'TENSOR',
               'presilha', 'fundo', 'HACHURA MADEIRAS', 'barrote', '5', '0'],
        'LJ': ['Painéis', 'Pain\u00e9is', 'SARRAFO DE PRESSAO', 'Pilares', 'VIGAS', 'COTA',
               'Hachura', 'REAPROVEITAMENTO', '0', 'SARR_2.2x7', 'FOLHA'],
        'FV': ['Painéis', 'Pain\u00e9is', 'SARRAFO', 'SARR_2.2x7', 'Madeira', 'COTA',
               'BARRA DE ANCORAGEM', 'CONCRETO', 'REAPROVEITAMENTO', '0', 'Hachura'],
    }

    target_layers = LAYERS_DETAIL.get(tipo, [])

    print(f"\n  DETALHE DAS LAYERS PRINCIPAIS:")
    for layer in target_layers:
        entities = by_layer.get(layer, [])
        if not entities:
            # Tentar com encoding issues
            alt = [k for k in by_layer.keys() if layer.lower() in k.lower()]
            if alt:
                layer = alt[0]
                entities = by_layer[layer]
        if not entities:
            continue

        print(f"\n    === {layer} ({len(entities)} entidades) ===")

        polys = [e for e in entities if e['type'] == 'LWPOLYLINE']
        lines = [e for e in entities if e['type'] == 'LINE']
        texts = [e for e in entities if e['type'] in ('TEXT','MTEXT')]
        inserts = [e for e in entities if e['type'] == 'INSERT']
        hatches = [e for e in entities if e['type'] == 'HATCH']
        dims = [e for e in entities if e['type'] == 'DIMENSION']

        if polys:
            widths = [p['width'] for p in polys if 'width' in p]
            heights = [p['height'] for p in polys if 'height' in p]
            print(f"      LWPOLYLINE ({len(polys)}):")
            if widths:
                print(f"        larguras: min={min(widths):.1f} max={max(widths):.1f} avg={sum(widths)/len(widths):.1f} mm")
            if heights:
                print(f"        alturas:  min={min(heights):.1f} max={max(heights):.1f} avg={sum(heights)/len(heights):.1f} mm")
            # Mostrar 5 exemplos
            for p in polys[:5]:
                bb = p.get('bbox')
                arc = 'ARC' if p.get('has_arc') else ''
                closed = 'closed' if p.get('closed') else 'open'
                print(f"        [{closed}] {p['pts'][:4]} W={p.get('width',0):.0f} H={p.get('height',0):.0f} {arc}")

        if lines:
            lengths = [l['length'] for l in lines if 'length' in l]
            if lengths:
                print(f"      LINE ({len(lines)}): lengths min={min(lengths):.0f} max={max(lengths):.0f} avg={sum(lengths)/len(lengths):.0f} mm")
            for ln in lines[:3]:
                print(f"        {ln.get('start','?')} -> {ln.get('end','?')} L={ln.get('length',0):.0f}")

        if texts:
            print(f"      TEXT/MTEXT ({len(texts)}):")
            for t in texts[:8]:
                print(f"        '{t.get('text','')[:50]}' pos={t.get('pos','?')}")

        if inserts:
            print(f"      INSERT ({len(inserts)}):")
            for ins in inserts[:5]:
                print(f"        block={ins.get('block','?'):25} pos={ins.get('pos','?')} scale={ins.get('scale','?')} rot={ins.get('rot','?')}")

        if hatches:
            patterns = defaultdict(int)
            for h in hatches:
                patterns[h.get('pattern','?')] += 1
            print(f"      HATCH ({len(hatches)}): {dict(patterns)}")

        if dims:
            vals = sorted([d.get('value',0) for d in dims if d.get('value')])[:15]
            print(f"      DIMENSION ({len(dims)}): valores={vals}")

    # Blocos definidos
    print(f"\n  BLOCOS DEFINIDOS:")
    for block in doc.blocks:
        name = block.name
        if name.startswith('*'):
            continue
        ents = list(block)
        types = defaultdict(int)
        for e in ents:
            types[e.dxftype()] += 1
        print(f"    {name:40} {len(ents):5d}  {dict(types)}")
        # Mostrar geometria do bloco
        for e in ents[:5]:
            info = get_entity_info(e)
            if info['type'] == 'LWPOLYLINE':
                print(f"      POLY pts={info.get('pts',[])[:4]} closed={info.get('closed')}")
            elif info['type'] == 'LINE':
                print(f"      LINE {info.get('start')} -> {info.get('end')} L={info.get('length',0):.1f}")
            elif info['type'] == 'ARC':
                print(f"      ARC center={info.get('center')} R={info.get('radius')} {info.get('start_angle')}°-{info.get('end_angle')}°")


def main():
    analyze_file_full(FILE_PL, 'PL')
    analyze_file_full(FILE_LV, 'LV')
    analyze_file_full(FILE_LJ, 'LJ')
    analyze_file_full(FILE_FV, 'FV')

if __name__ == '__main__':
    main()
