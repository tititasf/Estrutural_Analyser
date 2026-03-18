#!/usr/bin/env python3
"""
Diagnóstico final: conta células dispersas em v31 vs v32 para validar o fix.
Usa scan direto do DXF com atribuição de célula por grid (sem CELL_BORDER).
"""
import sys, ezdxf
sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CELL_W, CELL_H = 2900, 1800
COLS = 12
CONTENT_LAYERS = {'Paineis', 'Painéis', 'Hachura', 'CONCRETO', 'Madeira', 'SARR_2.2x7',
                  'SARR_3.5x7', 'SARR_2.2x10', 'SARR_EDITAR', 'REAPROVEITAMENTO',
                  'COTA', 'Forcador'}
GAP_THRESHOLD = 600

def count_dispersed(dxf_path, label):
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    from collections import defaultdict
    cell_xs = defaultdict(list)

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
                        pts += [(v[0], v[1]) for v in path.vertices[:4]]
        except: continue
        if not pts: continue
        cx = sum(p[0] for p in pts)/len(pts)
        cy = sum(p[1] for p in pts)/len(pts)

        # Direct cell assignment (no tol for proper counting)
        col = int(cx // CELL_W)
        row = int(-cy // CELL_H)
        if 0 <= col < COLS:
            off = cx - col * CELL_W
            cell_xs[(col, row)].append((round(off), layer, t))

    dispersed = []
    for (col, row), ents in cell_xs.items():
        if len(ents) < 2: continue
        off_list = sorted(set(e[0] for e in ents))
        if len(off_list) < 2: continue
        gaps = [(off_list[i+1]-off_list[i], off_list[i], off_list[i+1])
                for i in range(len(off_list)-1)]
        max_gap, g0, g1 = max(gaps)
        if max_gap >= GAP_THRESHOLD:
            right = [e for e in ents if e[0] >= g1]
            # Only flag if right cluster is tiny (1-2 pts) — genuine isolated
            if len(right) <= 2:
                dispersed.append((max_gap, col, row, g0, g1, right))

    dispersed.sort(key=lambda x: -x[0])
    print("%s: %d cells with 1-2 isolated pts (gap>=%d)" % (label, len(dispersed), GAP_THRESHOLD))
    for gap, col, row, g0, g1, right in dispersed[:10]:
        right_str = [(o, l) for o,l,t in right]
        print("  (%d,%d) gap=%d [%d→%d] right=%s" % (col, row, gap, g0, g1, right_str))
    return dispersed

print("=" * 60)
disp31 = count_dispersed('combined/combined_v31.dxf', 'v31')
print()
disp32 = count_dispersed('combined/combined_v32.dxf', 'v32')
print()
print("IMPROVEMENT: %d cells fixed (%d → %d)" % (
    len(disp31) - len(disp32), len(disp31), len(disp32)))
