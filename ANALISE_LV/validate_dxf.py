#!/usr/bin/env python3
"""
Valida o DXF gerado lendo as entidades reais e verificando se ficam dentro de alguma célula.
Não simula — lê o arquivo de saída e mede o que está fora dos bounds.
"""
import sys, math, ezdxf
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')

DXF_PATH = 'D:/Agente-cad-PYSIDE/ANALISE_LV/combined/combined_v31.dxf'
CELL_W, CELL_H = 2900, 1800
COLS = 12
SKIP_LAYERS = {'CELL_BORDER', 'LABEL_ID'}
TOL = 60  # tolerância: ponto pode estar até 60u além da borda da célula

doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()

def in_any_cell(x, y):
    """Ponto (x,y) está dentro de alguma célula do grid?
    Célula row r: y ∈ [-r*CELL_H, -(r-1)*CELL_H] → row = ceil(-y/CELL_H)
    """
    col = int(x // CELL_W)
    if col < 0: return False
    if y > CELL_H: return False   # acima do row 0 com margem
    if y >= 0:
        row = 0
    else:
        row = math.ceil((-y) / CELL_H)
    cx0 = col * CELL_W
    cy0 = -row * CELL_H   # bottom of cell (mais negativo)
    cx1 = cx0 + CELL_W
    cy1 = cy0 + CELL_H    # top of cell (menos negativo)
    return (cx0 - TOL <= x <= cx1 + TOL) and (cy0 - TOL <= y <= cy1 + TOL)

leaks_by_layer = {}
total_entities = 0
leaks_count = 0

for entity in msp:
    layer = getattr(entity.dxf, 'layer', '0')
    if layer in SKIP_LAYERS:
        continue
    total_entities += 1
    pts = []
    t = entity.dxftype()
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
                elif hasattr(path, 'edges'):
                    for edge in path.edges:
                        if hasattr(edge, 'start'):
                            pts.append((edge.start[0], edge.start[1]))
                        if hasattr(edge, 'end'):
                            pts.append((edge.end[0], edge.end[1]))
    except Exception:
        continue

    for x, y in pts:
        if not in_any_cell(x, y):
            leaks_by_layer[layer] = leaks_by_layer.get(layer, 0) + 1
            leaks_count += 1
            break  # conta 1 por entidade

print(f"DXF: {DXF_PATH}")
print(f"Entidades verificadas: {total_entities}")
print(f"Com pelo menos 1 ponto fora da célula: {leaks_count}")
print()
if leaks_count == 0:
    print("PASS: zero entidades fora dos bounds!")
else:
    print("Entidades fora por layer:")
    for layer, count in sorted(leaks_by_layer.items(), key=lambda x: -x[1]):
        print(f"  {layer}: {count}")
