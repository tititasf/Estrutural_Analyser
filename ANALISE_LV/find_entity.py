#!/usr/bin/env python3
"""Find the specific entity at x~17362, y~-72273 in the DXF."""
import sys, ezdxf
sys.path.insert(0, 'D:/Agente-cad-PYSIDE/ANALISE_LV')

DXF_PATH = 'D:/Agente-cad-PYSIDE/ANALISE_LV/combined/combined_v31.dxf'
CELL_W, CELL_H = 2900, 1800
CONTENT_LAYERS = {'Paineis', 'Paineis', 'Painéis', 'Hachura', 'CONCRETO', 'Madeira',
                  'SARR_2.2x7', 'SARR_3.5x7', 'SARR_2.2x10', 'SARR_EDITAR',
                  'REAPROVEITAMENTO', 'COTA', 'Forcador'}

doc = ezdxf.readfile(DXF_PATH)
msp = doc.modelspace()

# Scan for entities near x=17362, y=-72273
TARGET_X = 17362
TARGET_Y = -72273
TOL = 200

print("Searching for entity at x~%d, y~%d" % (TARGET_X, TARGET_Y))
for entity in msp:
    layer = getattr(entity.dxf, 'layer', '0')
    if layer not in CONTENT_LAYERS: continue
    t = entity.dxftype()
    pts = []
    try:
        if t == 'LINE': pts = [entity.dxf.start[:2], entity.dxf.end[:2]]
        elif t == 'LWPOLYLINE': pts = [(p[0], p[1]) for p in entity.get_points()]
        elif t == 'HATCH':
            for path in entity.paths:
                if hasattr(path, 'vertices'):
                    pts += [(v[0], v[1]) for v in path.vertices]
    except: continue
    if not pts: continue
    cx = sum(p[0] for p in pts)/len(pts)
    cy = sum(p[1] for p in pts)/len(pts)
    if abs(cx - TARGET_X) < TOL and abs(cy - TARGET_Y) < TOL:
        print("\nFound: %s layer=%s" % (t, layer))
        print("  centroid: cx=%.1f  cy=%.1f" % (cx, cy))
        # Show all vertices
        xs = [round(p[0]) for p in pts]
        ys = [round(p[1]) for p in pts]
        print("  x range: [%d, %d]  y range: [%d, %d]" % (min(xs),max(xs),min(ys),max(ys)))
        print("  all vertices (x,y): %s" % [(round(p[0]),round(p[1])) for p in pts[:8]])
        # Which cell does it belong to?
        c5 = round(cx / CELL_W); r5 = round(-cy / CELL_H)
        c5_floor = int(cx // CELL_W); r5_floor = int(-cy // CELL_H)
        print("  cell approx: (%d,%d)  floor: (%d,%d)" % (c5,r5,c5_floor,r5_floor))
        # Cell (5,41) range: x=[14500,17400], y=[-73800,-72000]
        # Cell (6,41) range: x=[17400,20300], y=[-73800,-72000]
        in_c5 = (14500-60) <= cx <= (17400+60) and (-73800-60) <= cy <= (-72000+60)
        in_c6 = (17400-60) <= cx <= (20300+60) and (-73800-60) <= cy <= (-72000+60)
        print("  in cell (5,41): %s  in cell (6,41): %s" % (in_c5, in_c6))
