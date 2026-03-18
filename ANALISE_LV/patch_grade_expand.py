#!/usr/bin/env python3
"""
patch_grade_expand.py -- Coleta grade_entities (Forcador, GARFOS, Escoras, etc.)
para vigas que nao possuem.

A grade fica tipicamente ~1760u a esquerda do insert_x.
Coleta entidades em:
  x range: [insert_x - 2500, insert_x - 200]
  y range: [zone.y_bot, zone.y_top]
Layers alvo: 'Forcador', 'GARFOS', 'Escoras', 'Demarcacao 1', 'Torre'

Formato de saida (compativel com combinar_vigas_dxf.py):
  grade_entities = {
    'grade_lines':   [{'x1','y1','x2','y2','layer'}, ...],
    'grade_polys':   [{'vertices': [(x,y),...], 'layer', 'closed'}, ...],
    'grade_texts':   [{'text','x','y','layer'}, ...],
    'grade_hatches': [{'layer','pattern','solid','boundary_polys': [[(x,y),...]]}, ...],
  }

Uso:
  python patch_grade_expand.py
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path

import ezdxf

PARAMS_FILE = Path(r'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json')
OBRAS_BASE  = Path(r'D:/Agente-cad-PYSIDE/DADOS-OBRAS')

# Layers to capture for grade
GRADE_LAYERS = {'Forcador', 'GARFOS', 'Escoras', 'Demarcação 1', 'Demarcacao 1', 'Torre',
                'Forcadores', 'Garfos', 'garfos', 'forcador', 'escoras', 'torre',
                'ESCORAS', 'FORCADOR', 'FORCADORES', 'TORRE'}


def find_dxf(obra, dxf_name):
    for sub in ['Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
                'Fase-1_Ingestao']:
        p = OBRAS_BASE / obra / sub / dxf_name
        if p.exists():
            return p
    return None


def is_grade_layer(layer_name):
    """Check if layer is a grade-related layer (case-insensitive)."""
    ln = layer_name.strip()
    if ln in GRADE_LAYERS:
        return True
    lu = ln.upper()
    for kw in ('FORCADOR', 'GARFOS', 'ESCORA', 'TORRE', 'DEMARCA'):
        if kw in lu:
            return True
    return False


def collect_grade_entities(msp, insert_x, y_bot, y_top, x_left_limit=None):
    """Collect grade entities from DXF modelspace in the grade region."""
    # Grade region: to the left of insert
    x_min = (insert_x - 2500) if x_left_limit is None else min(insert_x - 2500, x_left_limit - 200)
    x_max = insert_x - 200
    y_min = y_bot - 50 if y_bot else -1e9
    y_max = y_top + 50 if y_top else 1e9

    grade_lines = []
    grade_polys = []
    grade_texts = []
    grade_hatches = []

    for e in msp:
        layer = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'
        if not is_grade_layer(layer):
            continue

        dtype = e.dxftype()

        if dtype == 'LINE':
            try:
                s = e.dxf.start
                en = e.dxf.end
                # Check if line is in the grade region
                lx_min = min(s.x, en.x)
                lx_max = max(s.x, en.x)
                ly_min = min(s.y, en.y)
                ly_max = max(s.y, en.y)
                if lx_max < x_min or lx_min > x_max:
                    continue
                if ly_max < y_min or ly_min > y_max:
                    continue
                grade_lines.append({
                    'x1': round(s.x, 1), 'y1': round(s.y, 1),
                    'x2': round(en.x, 1), 'y2': round(en.y, 1),
                    'layer': layer,
                })
            except Exception:
                pass

        elif dtype == 'LWPOLYLINE':
            try:
                pts = list(e.get_points(format='xy'))
                if not pts:
                    continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if max(xs) < x_min or min(xs) > x_max:
                    continue
                if max(ys) < y_min or min(ys) > y_max:
                    continue
                grade_polys.append({
                    'vertices': [(round(p[0], 1), round(p[1], 1)) for p in pts],
                    'layer': layer,
                    'closed': e.closed,
                })
            except Exception:
                pass

        elif dtype in ('TEXT', 'MTEXT'):
            try:
                if dtype == 'TEXT':
                    t = e.dxf.text.strip()
                    tx = e.dxf.insert.x
                    ty = e.dxf.insert.y
                else:
                    t = e.text.strip() if hasattr(e, 'text') else e.dxf.text.strip()
                    tx = e.dxf.insert.x
                    ty = e.dxf.insert.y
                if tx < x_min or tx > x_max or ty < y_min or ty > y_max:
                    continue
                grade_texts.append({
                    'text': t, 'x': round(tx, 1), 'y': round(ty, 1),
                    'layer': layer,
                })
            except Exception:
                pass

        elif dtype == 'HATCH':
            try:
                boundary_polys = []
                for bp in e.paths:
                    if hasattr(bp, 'vertices'):
                        pts = [(round(v.x, 1) if hasattr(v, 'x') else round(v[0], 1),
                                round(v.y, 1) if hasattr(v, 'y') else round(v[1], 1))
                               for v in bp.vertices]
                        if pts:
                            xs = [p[0] for p in pts]
                            ys = [p[1] for p in pts]
                            if max(xs) >= x_min and min(xs) <= x_max and max(ys) >= y_min and min(ys) <= y_max:
                                boundary_polys.append(pts)
                if boundary_polys:
                    pattern = e.dxf.pattern_name if hasattr(e.dxf, 'pattern_name') else 'SOLID'
                    is_solid = (pattern == 'SOLID') or e.dxf.solid_fill if hasattr(e.dxf, 'solid_fill') else False
                    grade_hatches.append({
                        'layer': layer,
                        'pattern': pattern,
                        'solid': bool(is_solid),
                        'boundary_polys': boundary_polys,
                    })
            except Exception:
                pass

    return {
        'grade_lines': grade_lines,
        'grade_polys': grade_polys,
        'grade_texts': grade_texts,
        'grade_hatches': grade_hatches,
    }


def has_grade(v):
    """Check if viga already has non-empty grade_entities."""
    ge = v.get('grade_entities')
    if not ge:
        return False
    return bool(ge.get('grade_lines') or ge.get('grade_polys') or ge.get('grade_hatches'))


def main():
    params = json.loads(PARAMS_FILE.read_text(encoding='utf-8'))

    # Vigas without grade entities
    vigas_sem_grade = [v for v in params if not has_grade(v)]
    print(f"Vigas sem grade_entities: {len(vigas_sem_grade)}")

    # Group by (obra, dxf_source)
    from collections import defaultdict
    grupos = defaultdict(list)
    for v in vigas_sem_grade:
        key = (v['obra'], v.get('dxf_source', ''))
        grupos[key].append(v)

    patched = 0

    for (obra, dxf_src), vigas in grupos.items():
        dxf_path = find_dxf(obra, dxf_src)
        if not dxf_path:
            print(f"  [SKIP] DXF nao encontrado: {obra}/{dxf_src}")
            continue

        print(f"\n  DXF: {dxf_src[:60]}")
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()

        for v in vigas:
            zone = v.get('zone', {})
            ins = v.get('insert', {})
            insert_x = ins.get('x')
            y_top = zone.get('y_top')
            y_bot = zone.get('y_bot')

            if insert_x is None or y_top is None or y_bot is None:
                continue

            grade = collect_grade_entities(msp, insert_x, y_bot, y_top)

            n_ents = len(grade['grade_lines']) + len(grade['grade_polys']) + len(grade['grade_hatches'])
            if n_ents > 0:
                v['grade_entities'] = grade
                patched += 1
                print(f"    {v['viga']}: grade OK -- {len(grade['grade_lines'])} lines, "
                      f"{len(grade['grade_polys'])} polys, {len(grade['grade_texts'])} texts, "
                      f"{len(grade['grade_hatches'])} hatches")

    PARAMS_FILE.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding='utf-8')

    # Count final state
    with_grade = sum(1 for p in params if has_grade(p))
    print(f"\nPATCH-D: patch_grade_expand")
    print(f"  Vigas com grade: {with_grade}/{len(params)}")
    print(f"  Novas: {patched}")
    print(f"  Salvo: {PARAMS_FILE}")


if __name__ == '__main__':
    main()
