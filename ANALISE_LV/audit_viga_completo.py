"""Audit COMPLETO de uma viga — dump de TODOS os elementos por layer.
Objetivo: identificar o que precisa estar no ficha para reconstrução idêntica.
"""
import sys, os, glob, json
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts')
import ezdxf
import extrair_parametros_viga_v3 as ext

TARGET_VIGA = 'V302'

dxf_dir = 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa'
dxf_path = None
for f in os.listdir(dxf_dir):
    if f.endswith('.dxf') and 'LV' in f and '13' in f:
        dxf_path = os.path.join(dxf_dir, f)
        print(f"DXF: {f}")
        break

doc = ezdxf.readfile(dxf_path)
msp = doc.modelspace()

all_vigas = ext.find_all_inserts(msp)
zone = ext.compute_zone(all_vigas, TARGET_VIGA)
print(f"Zone: insert=({zone['insert_x']:.0f},{zone['insert_y']:.0f})  "
      f"x=[{zone.get('x_left')},{zone.get('x_right'):.0f}]  "
      f"y=[{zone['y_bot']:.0f},{zone['y_top']:.0f}]")

# Coleta entidades na zona
from collections import defaultdict
by_layer = defaultdict(list)
all_entities = []

for e in msp:
    pts = ext.get_entity_coords(e)
    if not ext.entity_in_zone(pts, zone):
        continue
    layer = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'
    etype = e.dxftype()
    info = {'type': etype, 'layer': layer}

    if etype == 'LINE':
        info['x1'] = round(e.dxf.start.x, 1)
        info['y1'] = round(e.dxf.start.y, 1)
        info['x2'] = round(e.dxf.end.x, 1)
        info['y2'] = round(e.dxf.end.y, 1)
        info['dx'] = round(abs(e.dxf.end.x - e.dxf.start.x), 1)
        info['dy'] = round(abs(e.dxf.end.y - e.dxf.start.y), 1)
        info['orient'] = 'H' if info['dx'] > info['dy'] else 'V'
        info['len'] = round(max(info['dx'], info['dy']), 1)

    elif etype == 'LWPOLYLINE':
        pts2 = list(e.get_points(format='xy'))
        xs = [p[0] for p in pts2]
        ys = [p[1] for p in pts2]
        info['n_pts'] = len(pts2)
        info['x_min'] = round(min(xs), 1)
        info['x_max'] = round(max(xs), 1)
        info['y_min'] = round(min(ys), 1)
        info['y_max'] = round(max(ys), 1)
        info['closed'] = e.is_closed

    elif etype == 'DIMENSION':
        actual = e.dxf.actual_measurement if hasattr(e.dxf, 'actual_measurement') else 0
        dp = e.dxf.defpoint if hasattr(e.dxf, 'defpoint') else None
        dp2 = e.dxf.defpoint2 if hasattr(e.dxf, 'defpoint2') else None
        info['actual'] = round(actual, 2) if actual else 0
        info['dimtype'] = getattr(e.dxf, 'dimtype', 0)
        if dp and dp2:
            info['x1'] = round(dp.x, 1); info['y1'] = round(dp.y, 1)
            info['x2'] = round(dp2.x, 1); info['y2'] = round(dp2.y, 1)
            info['orient'] = 'H' if abs(dp.x - dp2.x) > abs(dp.y - dp2.y) else 'V'
            info['x_mid'] = round((dp.x + dp2.x) / 2, 1)
            info['y_mid'] = round((dp.y + dp2.y) / 2, 1)

    elif etype == 'HATCH':
        pattern = getattr(e.dxf, 'pattern_name', 'SOLID')
        scale = getattr(e.dxf, 'pattern_scale', 1.0)
        all_pts = []
        for p in e.paths:
            if hasattr(p, 'vertices'):
                all_pts.extend([(v[0], v[1]) for v in p.vertices])
        if all_pts:
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            info['pattern'] = pattern
            info['scale'] = round(scale, 3)
            info['x_min'] = round(min(xs), 1); info['x_max'] = round(max(xs), 1)
            info['y_min'] = round(min(ys), 1); info['y_max'] = round(max(ys), 1)
            info['width'] = round(max(xs) - min(xs), 1)
            info['height'] = round(max(ys) - min(ys), 1)

    elif etype in ('TEXT', 'MTEXT'):
        import re
        txt = e.dxf.text if etype == 'TEXT' else (e.text if hasattr(e, 'text') else '')
        if etype == 'MTEXT':
            txt = re.sub(r'\{[^}]*?;', '', txt).replace('}', '').replace('{', '')
            txt = re.sub(r'\\[A-Za-z][^;]*;', '', txt)
        info['text'] = txt.strip()[:60]
        info['x'] = round(e.dxf.insert.x, 1)
        info['y'] = round(e.dxf.insert.y, 1)
        if etype == 'TEXT' and hasattr(e.dxf, 'height'):
            info['height'] = round(e.dxf.height, 2)

    elif etype == 'INSERT':
        info['block'] = e.dxf.name if hasattr(e.dxf, 'name') else ''
        info['x'] = round(e.dxf.insert.x, 1)
        info['y'] = round(e.dxf.insert.y, 1)
        attribs = {}
        if hasattr(e, 'attribs'):
            for att in e.attribs:
                attribs[att.dxf.tag] = att.dxf.text.strip()
        info['attribs'] = attribs

    elif etype in ('CIRCLE', 'ARC'):
        info['cx'] = round(e.dxf.center.x, 1)
        info['cy'] = round(e.dxf.center.y, 1)
        info['r'] = round(e.dxf.radius, 2)

    elif etype == 'SOLID':
        verts = []
        for attr in ['vtx0', 'vtx1', 'vtx2', 'vtx3']:
            if hasattr(e.dxf, attr):
                v = getattr(e.dxf, attr)
                verts.append((round(v.x, 1), round(v.y, 1)))
        info['vertices'] = verts

    by_layer[layer].append(info)
    all_entities.append(info)

# ── Print por layer ──
print(f"\n{'='*70}")
print(f"TOTAL ENTIDADES: {len(all_entities)}")
print(f"{'='*70}")

for layer in sorted(by_layer.keys()):
    ents = by_layer[layer]
    types = defaultdict(int)
    for e in ents:
        types[e['type']] += 1
    print(f"\n▸ Layer: {repr(layer)} — {len(ents)} entidades  {dict(types)}")

    # Mostrar detalhes por tipo
    for etype in sorted(set(e['type'] for e in ents)):
        sub = [e for e in ents if e['type'] == etype]

        if etype == 'LINE':
            # Agrupar por orientação
            h_lines = [e for e in sub if e.get('orient') == 'H']
            v_lines = [e for e in sub if e.get('orient') == 'V']
            if h_lines:
                h_lens = sorted(set(e['len'] for e in h_lines))
                h_ys = sorted(set(e['y1'] for e in h_lines))
                print(f"    LINE H ({len(h_lines)}): lens={h_lens[:10]}  ys={[round(y,0) for y in h_ys[:15]]}")
            if v_lines:
                v_lens = sorted(set(e['len'] for e in v_lines))
                v_xs = sorted(set(round(e['x1'],0) for e in v_lines))
                print(f"    LINE V ({len(v_lines)}): lens={v_lens[:10]}  xs={v_xs[:20]}")

        elif etype == 'DIMENSION':
            for e in sorted(sub, key=lambda x: (x.get('orient',''), x.get('actual',0))):
                orient = e.get('orient', '?')
                actual = e.get('actual', 0)
                xm = e.get('x_mid', 0)
                ym = e.get('y_mid', 0)
                print(f"    DIM {orient}: actual={actual:7.1f}  mid=({xm:.0f},{ym:.0f})")

        elif etype == 'TEXT':
            for e in sorted(sub, key=lambda x: x.get('y', 0)):
                print(f"    TEXT: {repr(e.get('text','')[:40]):<42}  pos=({e.get('x',0):.0f},{e.get('y',0):.0f})  h={e.get('height',0):.1f}")

        elif etype == 'MTEXT':
            for e in sorted(sub, key=lambda x: x.get('y', 0)):
                print(f"    MTEXT: {repr(e.get('text','')[:40]):<40}  pos=({e.get('x',0):.0f},{e.get('y',0):.0f})")

        elif etype == 'HATCH':
            for e in sub:
                print(f"    HATCH: pattern={e.get('pattern','')}  scale={e.get('scale',0)}  "
                      f"x=[{e.get('x_min',0):.0f},{e.get('x_max',0):.0f}]  "
                      f"y=[{e.get('y_min',0):.0f},{e.get('y_max',0):.0f}]  "
                      f"wh={e.get('width',0):.0f}x{e.get('height',0):.0f}")

        elif etype == 'INSERT':
            for e in sub:
                print(f"    INSERT: block={e.get('block','')}  pos=({e.get('x',0):.0f},{e.get('y',0):.0f})  attribs={e.get('attribs',{})}")

        elif etype == 'LWPOLYLINE':
            for e in sub:
                print(f"    LWPOLY: {e.get('n_pts',0)} pts  x=[{e.get('x_min',0):.0f},{e.get('x_max',0):.0f}]  "
                      f"y=[{e.get('y_min',0):.0f},{e.get('y_max',0):.0f}]  closed={e.get('closed',False)}")

print(f"\n{'='*70}")
print("RESUMO PARA FICHA COMPLETA — O QUE FALTA CAPTURAR:")
print(f"{'='*70}")

# Usar o extractor atual para ver o que é calculado
ents = ext.collect_zone_entities(msp, zone)
face_a_data, face_b_data = ext.detect_faces_by_clustering(
    ents['panel_h_lines'], ents['panel_v_lines'], zone['insert_y'],
    insert_x=zone['insert_x'], x_left=zone.get('x_left'), x_right=zone.get('x_right'),
    y_top=zone.get('y_top')
)
if face_a_data:
    lines = face_a_data['lines']
    max_line_len = face_a_data.get('max_width', 1) or 1
    len_thresh = max(20, max_line_len * 0.30)
    long_lines = [ln for ln in lines if ln['len'] >= len_thresh]
    if not long_lines:
        long_lines = lines
    face_x_min = min(ln['x1'] for ln in long_lines)
    face_x_max = max(ln['x2'] for ln in long_lines)
    print(f"\nFace A:")
    print(f"  y_min={face_a_data['y_min']:.1f}  y_max={face_a_data['y_max']:.1f}  height={face_a_data['y_max']-face_a_data['y_min']:.1f}")
    print(f"  face_x_min={face_x_min:.1f}  face_x_max={face_x_max:.1f}  total_width={face_x_max-face_x_min:.1f}")
    print(f"  *** FALTA SALVAR: face_x_min, face_x_max no JSON ***")

    # Mostrar v_lines no face
    face_vlines = [vl for vl in ents['panel_v_lines']
                   if vl['y1'] <= face_a_data['y_max'] + 5 and vl['y2'] >= face_a_data['y_min'] - 5
                   and face_x_min - 5 <= vl['x'] <= face_x_max + 5]
    vx_set = sorted(set(round(vl['x'], 1) for vl in face_vlines))
    print(f"  Panel V-dividers ({len(vx_set)}): {vx_set}")
    print(f"  *** FALTA SALVAR: panel_dividers_x no JSON ***")

    # Gaps entre divisores = panel widths absolutas
    all_dividers = [face_x_min] + vx_set + [face_x_max]
    clean_dividers = [all_dividers[0]]
    for x in all_dividers[1:]:
        if x - clean_dividers[-1] > 3:
            clean_dividers.append(x)
    panel_xs = []
    for i in range(len(clean_dividers) - 1):
        w = round(clean_dividers[i+1] - clean_dividers[i], 1)
        if 20 < w <= 300:
            panel_xs.append((round(clean_dividers[i], 1), round(clean_dividers[i+1], 1), w))
    print(f"  Panel positions (x_start, x_end, width):")
    for px in panel_xs:
        print(f"    {px}")
    print(f"  *** FALTA SALVAR: panels com x_start, x_end por painel ***")

# Aberturas — CONCRETO hatches dentro da face indicam aberturas de pilar
print(f"\nAberturas de Pilar/Viga:")
for layer in sorted(by_layer.keys()):
    if 'concreto' in layer.lower() or 'aber' in layer.lower() or 'pilar' in layer.lower():
        print(f"  Layer {repr(layer)}: {len(by_layer[layer])} entities")
        for e in by_layer[layer]:
            print(f"    {e}")
# AR-CONC hatches dentro da face
arconc = [e for e in all_entities if e.get('type') == 'HATCH' and e.get('pattern') == 'AR-CONC']
print(f"  AR-CONC hatches: {len(arconc)}")
for h in arconc:
    print(f"    x=[{h.get('x_min',0):.0f},{h.get('x_max',0):.0f}]  y=[{h.get('y_min',0):.0f},{h.get('y_max',0):.0f}]  wh={h.get('width',0):.0f}x{h.get('height',0):.0f}")
