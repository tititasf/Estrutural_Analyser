#!/usr/bin/env python3
"""
patch_extra_layers.py -- Captura TODOS os layers nao tratados pelo extrator principal
e adiciona ao viga_params_v3.json como campo 'extra_entities'.

Estrategia: BLACKLIST (exclui apenas layers ja totalmente capturados).
Isso garante que layers como '0', 'TENSOR', 'barrote', 'presilha', 'cotas',
'SCO-___-LAJ', 'detalhes' e outros sejam capturados.

Otimizacao: agrupa vigas por DXF, abre cada DXF uma unica vez.
"""
import sys, io, json, gc
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import ezdxf
from pathlib import Path
from collections import defaultdict

PARAMS_FILE = Path('D:/Agente-cad-PYSIDE/ANALISE_LV/params/viga_params_v3.json')
OBRAS_BASE  = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS')

# Layers JA completamente capturados pelo extrator principal.
ALREADY_CAPTURED = {
    'Painéis',           # face_hlines/vlines/panel_polys
    'CONCRETO',          # concreto_polys
    'Madeira',           # madeira_polys
    'COTA',              # cota_dims
    'COTA_H',            # cota_dims
    'Hachura',           # hatches_data (HATCH entities)
    'HACHURA MADEIRAS',  # hatches_data
    # Metadata puro (sem geometria estrutural)
    'CELL_BORDER',
    'LABEL_ID',
    'CARIMBO',
    'FOLHA MB',
    'Folhas',
    'Romaneio',
    'fundo',
}


def should_skip(layer):
    """True se este layer ja e tratado pelo extrator principal."""
    if layer in ALREADY_CAPTURED:
        return True
    # SARR_* e Sarr* capturados via sarr22/sarr35 extractors
    if 'sarr' in layer.lower():
        return True
    return False


def find_dxf(obra, dxf_name):
    for sub in ['Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa',
                'Fase-1_Ingestao']:
        p = OBRAS_BASE / obra / sub / dxf_name
        if p.exists():
            return p
    for p in (OBRAS_BASE / obra).rglob('*.dxf'):
        if p.name == dxf_name:
            return p
    return None


def _get_xfilter(zone, fa):
    """Retorna (y_bot, y_top, filter_xmin, filter_xmax) para filtrar entidades."""
    y_top = zone.get('y_top', float('inf'))
    y_bot = zone.get('y_bot', float('-inf'))

    fa_xs = ([h['x1'] for h in fa.get('face_hlines', [])] +
             [h['x2'] for h in fa.get('face_hlines', [])] +
             [v['x']  for v in fa.get('face_vlines', [])])
    if fa_xs:
        fa_xmin = min(fa_xs)
        fa_xmax = max(fa_xs)
        span = fa_xmax - fa_xmin
        margin = max(span * 0.5, 500)
        filter_xmin = fa_xmin - margin
        filter_xmax = fa_xmax + margin
    else:
        x_left  = zone.get('x_left')
        x_right = zone.get('x_right')
        if x_left is not None and x_right is not None:
            filter_xmin = min(x_left, x_right) - 200
            filter_xmax = max(x_left, x_right) + 200
        else:
            filter_xmin = float('-inf')
            filter_xmax = float('inf')

    return y_bot, y_top, filter_xmin, filter_xmax


def extract_from_msp(msp, y_bot, y_top, filter_xmin, filter_xmax):
    """Extrai LINE e LWPOLYLINE de layers nao capturados, dentro da zona."""
    lines = []
    polys = []
    layers_found = set()

    for e in msp:
        layer = e.dxf.layer if hasattr(e.dxf, 'layer') else '0'
        if should_skip(layer):
            continue
        try:
            etype = e.dxftype()
            if etype == 'LINE':
                cx = (e.dxf.start.x + e.dxf.end.x) / 2
                cy = (e.dxf.start.y + e.dxf.end.y) / 2
                if not (y_bot <= cy <= y_top and filter_xmin <= cx <= filter_xmax):
                    continue
                lines.append({
                    'layer': layer,
                    'x1': round(e.dxf.start.x, 1), 'y1': round(e.dxf.start.y, 1),
                    'x2': round(e.dxf.end.x,   1), 'y2': round(e.dxf.end.y,   1),
                })
                layers_found.add(layer)
            elif etype == 'LWPOLYLINE':
                pts = list(e.get_points('xy'))
                if not pts:
                    continue
                cx = sum(p[0] for p in pts) / len(pts)
                cy = sum(p[1] for p in pts) / len(pts)
                if not (y_bot <= cy <= y_top and filter_xmin <= cx <= filter_xmax):
                    continue
                polys.append({
                    'layer': layer,
                    'closed': e.is_closed,
                    'vertices': [(round(p[0], 1), round(p[1], 1)) for p in pts],
                })
                layers_found.add(layer)
        except Exception:
            pass

    return lines, polys, layers_found


def main():
    with open(PARAMS_FILE, encoding='utf-8') as f:
        params = json.load(f)

    # Agrupar vigas por (obra, dxf_name) para abrir cada DXF uma unica vez
    dxf_groups = defaultdict(list)  # (obra, dxf_name) -> [idx, ...]
    for idx, p in enumerate(params):
        lu = p.get('layers_used') or {}
        if isinstance(lu, dict):
            has_uncaptured = any(not should_skip(l) for l in lu)
        else:
            has_uncaptured = False
        if has_uncaptured:
            obra     = p.get('obra', '')
            dxf_name = p.get('dxf_source', '')
            dxf_groups[(obra, dxf_name)].append(idx)

    patched = 0
    skipped = len(params) - sum(len(v) for v in dxf_groups.values())
    layer_stats = {}

    print(f'Vigas a processar: {sum(len(v) for v in dxf_groups.values())} em {len(dxf_groups)} DXFs')

    for (obra, dxf_name), idxs in sorted(dxf_groups.items()):
        dxf_path = find_dxf(obra, dxf_name)
        if not dxf_path:
            print(f'  [NAO ENCONTRADO] {obra}/{dxf_name}')
            continue

        # Abrir DXF uma unica vez para este grupo
        try:
            doc = ezdxf.readfile(str(dxf_path))
            msp = doc.modelspace()
        except MemoryError:
            print(f'  [SKIP MemoryError] {dxf_path.name} ({len(idxs)} vigas)')
            continue
        except Exception as ex:
            print(f'  [SKIP Erro] {dxf_path.name}: {ex}')
            continue

        # Processar cada viga deste DXF
        for idx in idxs:
            p    = params[idx]
            name = p.get('viga', '') or p.get('nome', '')
            fa   = p.get('face_a', {})
            zone = p.get('zone', {})

            y_bot, y_top, fx_min, fx_max = _get_xfilter(zone, fa)
            lines, polys, layers_found = extract_from_msp(msp, y_bot, y_top, fx_min, fx_max)

            for l in layers_found:
                layer_stats[l] = layer_stats.get(l, 0) + 1

            if lines or polys:
                p['extra_entities'] = {'extra_lines': lines, 'extra_polys': polys}
                print(f'  {name:25s}: {len(lines)} lines  {len(polys)} polys  '
                      f'layers={sorted(layers_found)}  ({obra})')
                patched += 1
            else:
                p.pop('extra_entities', None)

        # Liberar memoria do DXF antes de abrir o proximo
        del doc, msp
        gc.collect()

    with open(PARAMS_FILE, 'w', encoding='utf-8') as f:
        json.dump(params, f, ensure_ascii=False, separators=(',', ':'))

    print(f'\nPatchado: {patched} vigas ({skipped} sem layers nao capturados). Salvo: {PARAMS_FILE}')
    print(f'\nLayers capturados (top 25):')
    for l, cnt in sorted(layer_stats.items(), key=lambda x: -x[1])[:25]:
        print(f'  {l!r:35s}: {cnt} vigas')


if __name__ == '__main__':
    main()
