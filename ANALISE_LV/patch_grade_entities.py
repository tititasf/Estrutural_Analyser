#!/usr/bin/env python3
"""
patch_grade_entities.py — Extrai entidades de grade (Forcador, GARFOS, Escoras, etc.)
do DXF fonte para as vigas que têm esses layers, e patcha viga_params_v3.json.
"""
import sys, io, json, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path
from collections import defaultdict

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json'
OBRAS_BASE  = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')

GRADE_LAYERS = {
    'Demarcação 1', 'Demarcação 2',
    'Forcador', 'GARFOS', 'Escoras',
    'BARRA DE ANCORAGEM', 'Perfil Metálico',
    'PONTALETE', 'MEIO_PONT',
}

def arc_to_lines(e, n=12):
    """Converte ARC em n segmentos de linha."""
    cx, cy = e.dxf.center.x, e.dxf.center.y
    r = e.dxf.radius
    a0 = math.radians(e.dxf.start_angle)
    a1 = math.radians(e.dxf.end_angle)
    if a1 <= a0: a1 += 2*math.pi
    angles = [a0 + (a1-a0)*i/n for i in range(n+1)]
    pts = [(cx + r*math.cos(a), cy + r*math.sin(a)) for a in angles]
    return [{'x1': pts[i][0], 'y1': pts[i][1], 'x2': pts[i+1][0], 'y2': pts[i+1][1]} for i in range(len(pts)-1)]

def extract_grade(dxf_path, zone, fa):
    """Extrai entidades de grade do DXF dentro da zona + filtro x."""
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()

    y_top = zone['y_top']
    y_bot = zone['y_bot']
    x_right_raw = zone.get('x_right')
    x_left_raw  = zone.get('x_left')

    # Deriva limites x a partir de face_a quando zone não tem ambos
    fa_xs = [h['x1'] for h in fa.get('face_hlines', [])] + \
            [h['x2'] for h in fa.get('face_hlines', [])] + \
            [v['x']  for v in fa.get('face_vlines', [])]
    fa_xmin = min(fa_xs) if fa_xs else None
    fa_xmax = max(fa_xs) if fa_xs else None

    if x_left_raw is not None and x_right_raw is not None and \
       abs(x_left_raw) < 1e8 and abs(x_right_raw) < 1e8:
        # Ambos definidos — usa min/max para suportar coordenadas negativas
        filter_xmin = min(x_left_raw, x_right_raw)
        filter_xmax = max(x_left_raw, x_right_raw)
        span = abs(filter_xmax - filter_xmin)
        margin = max(span * 0.15, 200)
        filter_xmin -= margin
        filter_xmax += margin
    elif x_right_raw is not None and abs(x_right_raw) < 1e8:
        xr = x_right_raw
        # x_right pode ser negativo; cobre 2000 u à esquerda e 200 u à direita
        filter_xmin = min(xr - 2000, xr + 2000)
        filter_xmax = max(xr - 2000, xr + 2000)
        # Usa face_a se disponível para refinar
        if fa_xmin is not None:
            span = abs(fa_xmax - fa_xmin)
            margin = max(span * 0.5, 300)
            filter_xmin = min(fa_xmin - margin, filter_xmin)
            filter_xmax = max(fa_xmax + margin, filter_xmax)
    elif fa_xmin is not None:
        span = abs(fa_xmax - fa_xmin)
        margin = max(span * 0.5, 300)
        filter_xmin = fa_xmin - margin
        filter_xmax = fa_xmax + margin
    else:
        filter_xmin = -1e9
        filter_xmax = 1e9

    lines = []
    polys = []
    hatches = []
    texts = []

    for e in msp:
        if e.dxf.layer not in GRADE_LAYERS:
            continue
        layer = e.dxf.layer
        try:
            if e.dxftype() == 'LINE':
                cx = (e.dxf.start.x + e.dxf.end.x) / 2
                cy = (e.dxf.start.y + e.dxf.end.y) / 2
                if not (y_bot <= cy <= y_top and filter_xmin <= cx <= filter_xmax): continue
                lines.append({'layer': layer, 'x1': round(e.dxf.start.x,1), 'y1': round(e.dxf.start.y,1),
                               'x2': round(e.dxf.end.x,1), 'y2': round(e.dxf.end.y,1)})

            elif e.dxftype() == 'ARC':
                cx, cy = e.dxf.center.x, e.dxf.center.y
                if not (y_bot <= cy <= y_top and filter_xmin <= cx <= filter_xmax): continue
                for seg in arc_to_lines(e):
                    seg['layer'] = layer
                    lines.append(seg)

            elif e.dxftype() == 'LWPOLYLINE':
                pts = list(e.get_points('xy'))
                if not pts: continue
                cx = sum(p[0] for p in pts)/len(pts)
                cy = sum(p[1] for p in pts)/len(pts)
                if not (y_bot <= cy <= y_top and filter_xmin <= cx <= filter_xmax): continue
                polys.append({'layer': layer, 'closed': e.is_closed,
                              'vertices': [(round(p[0],1), round(p[1],1)) for p in pts]})

            elif e.dxftype() == 'HATCH':
                paths = list(e.paths)
                all_pts = []
                for path in paths:
                    if hasattr(path, 'vertices'): all_pts.extend(path.vertices)
                if not all_pts: continue
                cx = sum(p[0] for p in all_pts)/len(all_pts)
                cy = sum(p[1] for p in all_pts)/len(all_pts)
                if not (y_bot <= cy <= y_top and filter_xmin <= cx <= filter_xmax): continue
                hatches.append({'layer': layer, 'pattern': e.dxf.pattern_name,
                                'solid': bool(e.dxf.solid_fill),
                                'boundary_polys': [[(round(p[0],1), round(p[1],1)) for p in all_pts]]})

            elif e.dxftype() in ('TEXT', 'MTEXT'):
                if not hasattr(e.dxf, 'insert'): continue
                cx, cy = e.dxf.insert.x, e.dxf.insert.y
                if not (y_bot <= cy <= y_top and filter_xmin <= cx <= filter_xmax): continue
                t = e.dxf.text if e.dxftype() == 'TEXT' else e.text
                texts.append({'layer': layer, 'x': round(cx,1), 'y': round(cy,1), 'text': str(t)})
        except Exception as ex:
            pass

    return {'grade_lines': lines, 'grade_polys': polys, 'grade_hatches': hatches, 'grade_texts': texts}


def find_dxf(obra, dxf_source):
    """Localiza o arquivo DXF na estrutura de pastas."""
    for sub in ['Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
                'Fase-1_Ingestao']:
        p = OBRAS_BASE / obra / sub / dxf_source
        if p.exists(): return p
    # busca ampla
    for p in (OBRAS_BASE / obra).rglob('*.dxf'):
        if p.name == dxf_source: return p
    return None


def main():
    with open(PARAMS_FILE, encoding='utf-8') as f:
        params = json.load(f)

    patched = 0
    for p in params:
        lu = p.get('layers_used', {})
        grade_count = sum(lu.get(l, 0) for l in GRADE_LAYERS)
        if grade_count == 0:
            continue

        dxf_name = p.get('dxf_source', '')
        obra = p.get('obra', '')
        dxf_path = find_dxf(obra, dxf_name)
        if not dxf_path:
            print(f'  DXF nao encontrado: {obra}/{dxf_name}')
            continue

        fa = p.get('face_a', {})
        zone = p.get('zone', {})
        grade = extract_grade(dxf_path, zone, fa)
        total = sum(len(v) for v in grade.values())
        p['grade_entities'] = grade
        print(f'  {obra}/{p["viga"]:20s} → {total} entidades grade ({len(grade["grade_lines"])} lines, {len(grade["grade_polys"])} polys, {len(grade["grade_hatches"])} hatches, {len(grade["grade_texts"])} texts)')
        patched += 1

    with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(params, f, ensure_ascii=False, separators=(',', ':'))
    print(f'\nPatchado: {patched} vigas. Salvo: {PARAMS_FILE}')

if __name__ == '__main__':
    main()
