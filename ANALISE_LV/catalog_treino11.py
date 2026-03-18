#!/usr/bin/env python3
"""
catalog_treino11.py -- Gera catalog entries para Obra_TREINO_11 GWT-1PV (LV).

Este DXF usa TEXT na layer NOMENCLATURA em vez de INSERT com atributos.
Formato: "V401\\P(14x158)" onde \\P eh quebra de linha, (14x158) eh secao.

Uso:
  python catalog_treino11.py
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path

DXF_PATH = Path(r'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_11/Fase-1_Ingestao/'
                r'Projetos_Finalizados_para_Engenharia_Reversa/'
                r'NOVA-SCHWARTZ-GWT-1PV-LV-R00_R2018_ASCII_ODA.dxf')
OUTPUT_PATH = Path(r'D:/Agente-cad-PYSIDE/ANALISE_LV/params/catalog_treino11_1pv.json')

OBRA = 'Obra_TREINO_11'
PROJETO = 'NOVA-SCHWARTZ-GWT'
PAVIMENTO = 'GWT-1PV'


def find_viga_texts(msp):
    """Encontra TEXTs na layer NOMENCLATURA com pattern V\\d+.
    Formato: 'V401\\P(14x158)' -> titulo='V401', secao='(14x158)'.
    Exclui face labels como V401.A, V402.B.
    """
    vigas = []
    for e in msp:
        if e.dxftype() not in ('TEXT', 'MTEXT'):
            continue
        layer = e.dxf.layer
        if layer != 'NOMENCLATURA':
            continue

        if e.dxftype() == 'TEXT':
            text = e.dxf.text.strip()
            x, y = e.dxf.insert.x, e.dxf.insert.y
        else:
            text = e.text.strip() if hasattr(e, 'text') else ''
            x, y = e.dxf.insert.x, e.dxf.insert.y

        if not re.match(r'^V\d+', text):
            continue

        # Parse: 'V401\P(14x158)'
        parts = text.split('\\P')
        titulo = parts[0].strip()
        secao = parts[1].strip() if len(parts) > 1 else ''

        # Skip face labels like V401.A, V402.B
        if re.search(r'\.[AB]$', titulo):
            continue

        vigas.append({
            'nome': titulo,
            'secao': secao,
            'insert_x': round(x, 1),
            'insert_y': round(y, 1),
        })

    # Remove duplicates (keep first occurrence, sorted by Y desc)
    vigas.sort(key=lambda v: (-v['insert_y'], v['insert_x']))
    seen = set()
    unique = []
    for v in vigas:
        if v['nome'] not in seen:
            seen.add(v['nome'])
            unique.append(v)
    return unique


def compute_zone(all_vigas, target_name):
    """Calcula zone similar ao extrair_parametros_viga_v3.py."""
    if not all_vigas:
        return None

    # Group vigas into rows by Y proximity
    sorted_vigas = sorted(all_vigas, key=lambda v: -v['insert_y'])
    zones = []
    current = [sorted_vigas[0]]
    for i in range(1, len(sorted_vigas)):
        if current[-1]['insert_y'] - sorted_vigas[i]['insert_y'] < 150:
            current.append(sorted_vigas[i])
        else:
            zones.append(current)
            current = [sorted_vigas[i]]
    zones.append(current)

    for zi, zone in enumerate(zones):
        for v in zone:
            if v['nome'] == target_name:
                y_top = max(z['insert_y'] for z in zone) + 80
                if zi < len(zones) - 1:
                    y_bot = max(z['insert_y'] for z in zones[zi + 1])
                else:
                    y_bot = min(z['insert_y'] for z in zone) - 1000

                zone_by_x = sorted(zone, key=lambda z: z['insert_x'])
                idx = next(i for i, z in enumerate(zone_by_x) if z['nome'] == target_name)
                x_left = (zone_by_x[idx]['insert_x'] + zone_by_x[idx - 1]['insert_x']) / 2 if idx > 0 else None
                x_right = (zone_by_x[idx]['insert_x'] + zone_by_x[idx + 1]['insert_x']) / 2 if idx < len(zone_by_x) - 1 else None

                return {
                    'y_top': round(y_top, 1),
                    'y_bot': round(y_bot, 1),
                    'x_left': round(x_left, 1) if x_left is not None else None,
                    'x_right': round(x_right, 1) if x_right is not None else None,
                }
    return None


def compute_bbox(msp, insert_y, all_inserts_y, margin=20):
    """Calcula bounding box de entities no range Y da viga."""
    sorted_ys = sorted(set(all_inserts_y), reverse=True)
    idx = None
    for i, y in enumerate(sorted_ys):
        if abs(y - insert_y) < 5:
            idx = i
            break
    if idx is None:
        return None

    y_top = insert_y + margin
    if idx < len(sorted_ys) - 1:
        y_bottom = sorted_ys[idx + 1] + margin
    else:
        y_bottom = insert_y - 300

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
        'xmin': round(x_min - 30, 1),
        'xmax': round(x_max + 50, 1),
        'ymin': round(y_bottom, 1),
        'ymax': round(y_top, 1),
        'entity_count': count,
    }


def main():
    print(f'=== CATALOG TREINO_11 / {PAVIMENTO} ===')
    print(f'DXF: {DXF_PATH}')

    if not DXF_PATH.exists():
        print(f'ERRO: DXF nao encontrado: {DXF_PATH}')
        sys.exit(1)

    doc = ezdxf.readfile(str(DXF_PATH))
    msp = doc.modelspace()

    vigas = find_viga_texts(msp)
    print(f'Vigas encontradas: {len(vigas)}')

    all_ys = [v['insert_y'] for v in vigas]

    catalog = []
    for v in vigas:
        bbox = compute_bbox(msp, v['insert_y'], all_ys)
        zone = compute_zone(vigas, v['nome'])

        entry = {
            'obra': OBRA,
            'projeto': PROJETO,
            'pavimento': PAVIMENTO,
            'viga': v['nome'],
            'secao': v['secao'],
            'insert_x': v['insert_x'],
            'insert_y': v['insert_y'],
            'dxf_source': DXF_PATH.name,
            'bbox': bbox,
            'zone': zone,
        }
        catalog.append(entry)
        bstatus = f"entities={bbox['entity_count']}" if bbox else 'NO-BBOX'
        print(f'  {v["nome"]:25s} {v["secao"]:15s} ({v["insert_x"]:8.0f},{v["insert_y"]:8.0f}) {bstatus}')

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f'\nSalvo: {OUTPUT_PATH}')
    print(f'Total vigas: {len(catalog)}')


if __name__ == '__main__':
    main()
