#!/usr/bin/env python3
"""
Encontra células onde conteúdo está distribuído em MÚLTIPLOS clusters separados
(indicando que elementos de uma viga estão dispersos pela célula).
"""
import sys, math, ezdxf
from collections import defaultdict
sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DXF_PATH = 'D:/Agente-cad-PYSIDE/ANALISE_LV/combined/combined_v31.dxf'
CELL_W, CELL_H = 2900, 1800
SKIP_LAYERS = {'CELL_BORDER', 'LABEL_ID', 'Texto Seção', 'NOMENCLATURA'}
# Conteúdo real: Painéis, Hachura, CONCRETO, Madeira, SARR_*
CONTENT_LAYERS = {'Painéis', 'Hachura', 'CONCRETO', 'Madeira',
                  'SARR_2.2x7', 'SARR_3.5x7', 'SARR_2.2x10', 'SARR_EDITAR',
                  'REAPROVEITAMENTO', 'COTA'}

doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()

# Coletar CELL_BORDERs com índice (col, row)
borders = []  # [(cx0,cy0,cx1,cy1)]
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

# Coletar pontos de conteúdo por célula
cell_points = defaultdict(list)   # border_idx -> [(x,y,layer)]

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
                    pts += [(v[0], v[1]) for v in path.vertices[:2]]  # sample
    except Exception:
        continue
    if not pts: continue
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    idx = find_border(cx, cy)
    if idx >= 0:
        cell_points[idx].append((cx, cy, layer))

# Encontrar células com conteúdo muito disperso (separação grande)
print("Células com conteúdo disperso (separação X > 500u entre grupos):\n")
dispersas = []
for idx, pts in cell_points.items():
    if len(pts) < 2: continue
    bx0, bx1, by0, by1 = borders[idx]
    xs = [p[0] for p in pts]
    xs_sorted = sorted(xs)
    # Encontrar maior gap em X
    gaps = [(xs_sorted[i+1] - xs_sorted[i], xs_sorted[i], xs_sorted[i+1])
            for i in range(len(xs_sorted)-1)]
    if not gaps: continue
    max_gap, gap_left, gap_right = max(gaps)
    if max_gap > 500:
        cell_x = round(bx0 / CELL_W)
        cell_y = round(-by1 / CELL_H)
        # quantos pontos de cada lado do gap
        left_pts = sum(1 for x in xs if x <= gap_left)
        right_pts = sum(1 for x in xs if x >= gap_right)
        dispersas.append((max_gap, cell_x, cell_y, bx0, left_pts, right_pts, gap_left, gap_right))

dispersas.sort(key=lambda x: -x[0])
print(f"Total células dispersas: {len(dispersas)}")
print()
for gap, cx, cy, bx0, lp, rp, gl, gr in dispersas[:20]:
    print(f"  Célula col={cx} row={cy} (bx0={bx0:.0f}): gap={gap:.0f}u entre x=[{gl:.0f},{gr:.0f}]  ({lp} pts ← | → {rp} pts)")
