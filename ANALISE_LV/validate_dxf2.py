#!/usr/bin/env python3
"""Mostra exemplos reais de entidades fora dos bounds por layer."""
import sys, math, ezdxf
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')

DXF_PATH = 'D:/Agente-cad-PYSIDE/ANALISE_LV/combined/combined_v29.dxf'
CELL_W, CELL_H = 2900, 1800
COLS = 12
SKIP_LAYERS = {'CELL_BORDER', 'LABEL_ID'}
TOL = 60

doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()

def _row_for_y(y):
    """Linha do grid para coordenada y. Célula r: y ∈ [-r*CELL_H, -(r-1)*CELL_H].
    Fórmula correta: ceil(-y/CELL_H) para y<0."""
    if y > CELL_H: return -1
    if y >= 0: return 0
    return math.ceil((-y) / CELL_H)

def nearest_cell(x, y):
    col = int(x // CELL_W) if x >= 0 else -1
    row = _row_for_y(y)
    return col, row

def in_any_cell(x, y):
    col = int(x // CELL_W) if x >= 0 else -1
    row = _row_for_y(y)
    if col < 0 or row < 0: return False
    cx0 = col * CELL_W; cy0 = -row * CELL_H
    return (cx0-TOL<=x<=cx0+CELL_W+TOL) and (cy0-TOL<=y<=cy0+CELL_H+TOL)

# Coletar exemplos por layer
examples = {}  # layer -> [(x,y,tipo,distancia_ao_grid)]

def dist_to_grid(x, y):
    """Distância mínima ao grid de células mais próximo."""
    # X: distância à célula mais próxima
    col = max(0, int(x // CELL_W)) if x >= 0 else 0
    cx0 = col * CELL_W
    dx = max(0, cx0 - x, x - (cx0 + CELL_W))
    # Y: distância à célula mais próxima
    row = max(0, _row_for_y(y)) if y <= 0 else 0
    cy0 = -row * CELL_H
    dy = max(0, cy0 - y, y - (cy0 + CELL_H))  # cy0 is bottom, cy0+CELL_H is top
    # Nota: y vai para baixo (negativo), então cy0 é o bottom mais alto (menos negativo)
    # ponto abaixo do bottom: y < cy0 → dy = cy0 - y
    # ponto acima do top: y > cy0+CELL_H → dy = y - (cy0+CELL_H)
    return max(dx, dy)

for entity in msp:
    layer = getattr(entity.dxf, 'layer', '0')
    if layer in SKIP_LAYERS: continue
    t = entity.dxftype()
    pts = []
    try:
        if t == 'LINE':
            pts = [entity.dxf.start[:2], entity.dxf.end[:2]]
        elif t == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in entity.get_points()]
        elif t == 'TEXT':
            pts = [entity.dxf.insert[:2]]
        elif t == 'HATCH':
            for path in entity.paths:
                if hasattr(path, 'vertices'):
                    pts += [(v[0], v[1]) for v in path.vertices]
    except Exception:
        continue

    for x, y in pts:
        if not in_any_cell(x, y):
            d = dist_to_grid(x, y)
            examples.setdefault(layer, []).append((x, y, t, d))
            break

print(f"Entidades fora por layer — exemplos com distância ao grid mais próximo:\n")
for layer, cases in sorted(examples.items(), key=lambda kv: -len(kv[1])):
    cases_sorted = sorted(cases, key=lambda c: -c[3])[:5]  # top 5 por distância
    print(f"  {layer}: {len(cases)} total | exemplos mais distantes:")
    for x, y, t2, d in cases_sorted:
        print(f"    ({x:.0f}, {y:.0f}) tipo={t2} dist={d:.0f}u")
