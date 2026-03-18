#!/usr/bin/env python3
"""
patch_sarr35_lines.py — Extrai SARR_3.5x7 LINE entities da fonte e adiciona ao params JSON.

O extrator atual captura SARR_3.5x7 LINEs em sarr_lines mas os EXCLUI de sarr22_lines
(filtro '3.5' not in layer). Essas linhas são os "sarrafos verdes" que ficam dentro dos
painéis e estão completamente ausentes do combined DXF.

Esse patch:
1. Lê viga_params_v6.json
2. Para cada obra com DXF acessível, abre o DXF e extrai SARR_3.5x7 LINEs
3. Atribui as linhas a cada viga pela bounding box da face_a (com margem)
4. Adiciona campo 'all_sarr35_lines' a cada viga
5. Salva viga_params_v6.json atualizado
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path
from collections import defaultdict

PARAMS_FILE = 'D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v6.json'

# Mapping obra → base directory for DXF files
OBRA_DIRS = {
    'Obra_TREINO_1':  'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
    'Obra_TREINO_3':  'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_3/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
    'Obra_TREINO_5':  'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_5/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
    'Obra_TREINO_9':  'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_9/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
    'Obra_TREINO_10': 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_10/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
    'Obra_TREINO_11': 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_11/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
    'Obra_TREINO_21': 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_21/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
    'Obra_TREINO_22': 'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_22/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
}

MARGIN = 30  # units of margin around face_a bounds for line attribution


def load_sarr35_lines_from_dxf(dxf_path):
    """Load all SARR_3.5x7 LINE entities from a DXF file."""
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        print(f'  ERROR reading {dxf_path.name}: {e}')
        return []

    lines = []
    for e in doc.modelspace():
        if e.dxftype() != 'LINE':
            continue
        if e.dxf.layer != 'SARR_3.5x7':
            continue
        try:
            x1, y1 = e.dxf.start.x, e.dxf.start.y
            x2, y2 = e.dxf.end.x, e.dxf.end.y
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)
            lines.append({
                'layer': 'SARR_3.5x7',
                'x1': round(min(x1, x2), 1),
                'x2': round(max(x1, x2), 1),
                'y1': round(min(y1, y2), 1),
                'y2': round(max(y1, y2), 1),
                'is_h': dx > dy,
                'src': 'LINE',
            })
        except Exception:
            pass
    return lines


def get_viga_bounds(viga):
    """Get the face_a bounding box for a viga, with margin."""
    fa = viga.get('face_a') or {}
    xmin = fa.get('face_x_min')
    xmax = fa.get('face_x_max')
    ymin = fa.get('y_min')
    ymax = fa.get('y_max')

    if xmin is None or xmax is None or ymin is None or ymax is None:
        # Try insert-based fallback: use insert + reasonable zone size
        ins = viga.get('insert') or {}
        ix, iy = ins.get('x', 0), ins.get('y', 0)
        return (ix - 1500, ix + 3000, iy - 3000, iy + 500)

    return (xmin - MARGIN, xmax + MARGIN, ymin - MARGIN, ymax + MARGIN)


def lines_in_bounds(lines, bounds):
    """Filter lines whose midpoint falls within bounds."""
    x0, x1, y0, y1 = bounds
    result = []
    for l in lines:
        mid_x = (l['x1'] + l['x2']) / 2
        mid_y = (l['y1'] + l['y2']) / 2
        if x0 <= mid_x <= x1 and y0 <= mid_y <= y1:
            result.append(l)
    return result


def main():
    with open(PARAMS_FILE, encoding='utf-8') as f:
        data = json.load(f)

    # Group vigas by (obra, dxf_source)
    dxf_groups = defaultdict(list)
    for i, v in enumerate(data):
        key = (v.get('obra', ''), v.get('dxf_source', ''))
        dxf_groups[key].append(i)

    total_patched = 0
    total_lines_added = 0

    for (obra, dxf_src), indices in sorted(dxf_groups.items()):
        base_dir = OBRA_DIRS.get(obra)
        if not base_dir:
            print(f'SKIP {obra}: no directory mapping')
            continue

        dxf_path = Path(base_dir) / dxf_src
        if not dxf_path.exists():
            print(f'MISSING {dxf_path.name} — skip')
            continue

        print(f'Processing {obra}/{dxf_src} ({len(indices)} vigas)...')
        all_sarr35 = load_sarr35_lines_from_dxf(dxf_path)
        print(f'  Found {len(all_sarr35)} SARR_3.5x7 LINEs in source')

        obra_lines_added = 0
        for idx in indices:
            v = data[idx]
            bounds = get_viga_bounds(v)
            matched = lines_in_bounds(all_sarr35, bounds)
            v['all_sarr35_lines'] = matched
            obra_lines_added += len(matched)

        total_patched += len(indices)
        total_lines_added += obra_lines_added
        print(f'  Assigned {obra_lines_added} lines across {len(indices)} vigas')

    # Ensure all vigas have the field (empty list if not patched)
    for v in data:
        if 'all_sarr35_lines' not in v:
            v['all_sarr35_lines'] = []

    with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    print(f'\nDone: patched {total_patched} vigas, added {total_lines_added} SARR_3.5x7 lines')
    print(f'Saved: {PARAMS_FILE}')


if __name__ == '__main__':
    main()
