#!/usr/bin/env python3
"""
Identifica o LAYER e TIPO das entidades isoladas (ponto direito do gap).
"""
import sys, math, ezdxf
from collections import defaultdict
sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DXF_PATH = 'D:/Agente-cad-PYSIDE/ANALISE_LV/combined/combined_v31.dxf'
CELL_W, CELL_H = 2900, 1800
SKIP_LAYERS = {'CELL_BORDER', 'LABEL_ID', 'Texto Seção', 'NOMENCLATURA'}
CONTENT_LAYERS = {'Painéis', 'Hachura', 'CONCRETO', 'Madeira',
                  'SARR_2.2x7', 'SARR_3.5x7', 'SARR_2.2x10', 'SARR_EDITAR',
                  'REAPROVEITAMENTO', 'COTA', 'Forcador', 'Perfil Metálico',
                  'BARRA DE ANCORAGEM', 'Demarcação 2', 'GARFOS'}

doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()

# Coletar CELL_BORDERs
borders = []
for e in msp:
    if getattr(e.dxf, 'layer', '') != 'CELL_BORDER': continue
    if e.dxftype() != 'LWPOLYLINE': continue
    pts = [(p[0], p[1]) for p in e.get_points()]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    borders.append((min(xs), max(xs), min(ys), max(ys)))

def find_border(x, y, tol=60):
    for i, (bx0, bx1, by0, by1) in enumerate(borders):
        if (bx0-tol) <= x <= (bx1+tol) and (by0-tol) <= y <= (by1+tol):
            return i
    return -1

# Coletar centroide + layer de cada entidade por célula
cell_entities = defaultdict(list)  # border_idx -> [(cx, cy, layer, dxftype)]

for entity in msp:
    layer = getattr(entity.dxf, 'layer', '0')
    if layer not in CONTENT_LAYERS: continue
    t = entity.dxftype()
    pts = []
    try:
        if t == 'LINE':
            pts = [entity.dxf.start[:2], entity.dxf.end[:2]]
        elif t == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in entity.get_points()]
        elif t == 'HATCH':
            for path in entity.paths:
                if hasattr(path, 'vertices'):
                    pts += [(v[0], v[1]) for v in path.vertices]
    except Exception:
        continue
    if not pts: continue
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    idx = find_border(cx, cy)
    if idx >= 0:
        cell_entities[idx].append((cx, cy, layer, t))

# Encontrar células dispersas e mostrar layer do ponto isolado
print("Células dispersas — layer do ponto isolado à direita:\n")
results = []
for idx, ents in cell_entities.items():
    if len(ents) < 2: continue
    bx0, bx1, by0, by1 = borders[idx]
    xs = [(e[0], e[2], e[3]) for e in ents]
    xs_sorted = sorted(xs, key=lambda x: x[0])
    x_vals = [x[0] for x in xs_sorted]
    gaps = [(x_vals[i+1] - x_vals[i], i) for i in range(len(x_vals)-1)]
    if not gaps: continue
    max_gap, gap_i = max(gaps)
    if max_gap < 500: continue
    right_ents = xs_sorted[gap_i+1:]
    left_count = gap_i + 1
    right_layers = [(e[1], e[2]) for e in right_ents]  # (layer, dxftype)
    cell_x = round(bx0 / CELL_W)
    cell_y = round(-by1 / CELL_H)
    right_x = right_ents[0][0]
    results.append((max_gap, cell_x, cell_y, left_count, len(right_ents), right_x, right_layers))

results.sort(key=lambda x: -x[0])
print(f"Total células dispersas: {len(results)}\n")
for gap, cx, cy, lp, rp, rx, rlayers in results[:20]:
    layers_str = ', '.join(f'{l}({t})' for l, t in rlayers[:3])
    print(f"  col={cx} row={cy} gap={gap:.0f}u | {lp} pts ← | → {rp} pts @ x={rx:.0f} | layers: {layers_str}")
