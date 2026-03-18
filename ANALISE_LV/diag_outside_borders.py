#!/usr/bin/env python3
"""
Diagnóstico preciso: encontra entidades que estão fora dos retângulos CELL_BORDER.
Lê as bordas reais do DXF e verifica cada entidade contra elas.
"""
import sys, math, ezdxf
sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DXF_PATH = 'D:/Agente-cad-PYSIDE/ANALISE_LV/combined/combined_v31.dxf'
SKIP_LAYERS = {'CELL_BORDER', 'LABEL_ID'}
TOL = 60  # ponto pode estar até 60u fora de alguma border

doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()

# 1. Coletar todas as CELL_BORDERs (retângulos cx0,cy0,cx1,cy1)
borders = []
for e in msp:
    if getattr(e.dxf, 'layer', '') != 'CELL_BORDER':
        continue
    if e.dxftype() != 'LWPOLYLINE':
        continue
    pts = [(p[0], p[1]) for p in e.get_points()]
    if len(pts) < 4:
        continue
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    borders.append((min(xs), max(xs), min(ys), max(ys)))

print(f"Total CELL_BORDERs encontrados: {len(borders)}")

def in_any_border(x, y):
    for bx0, bx1, by0, by1 in borders:
        if (bx0-TOL) <= x <= (bx1+TOL) and (by0-TOL) <= y <= (by1+TOL):
            return True
    return False

# 2. Verificar cada entidade
leaks_by_layer = {}
leaks_count = 0
total = 0

for entity in msp:
    layer = getattr(entity.dxf, 'layer', '0')
    if layer in SKIP_LAYERS:
        continue
    total += 1
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
                elif hasattr(path, 'edges'):
                    for edge in path.edges:
                        if hasattr(edge, 'start'): pts.append((edge.start[0], edge.start[1]))
                        if hasattr(edge, 'end'):   pts.append((edge.end[0], edge.end[1]))
    except Exception:
        continue

    for x, y in pts:
        if not in_any_border(x, y):
            leaks_by_layer[layer] = leaks_by_layer.get(layer, 0) + 1
            leaks_count += 1
            break

print(f"Entidades verificadas: {total}")
print(f"Fora de qualquer CELL_BORDER: {leaks_count}")
print()
if leaks_count == 0:
    print("PASS: todas as entidades estão dentro de algum CELL_BORDER!")
else:
    print("Fora por layer:")
    for layer, count in sorted(leaks_by_layer.items(), key=lambda x: -x[1]):
        print(f"  {layer}: {count}")
