# -*- coding: utf-8 -*-
"""Find ANY vertical edge (LINE or LWPOLYLINE) through the laje at 244."""
import ezdxf
from pathlib import Path

p = Path(r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n4\LV_preview_V301_A.dxf")
doc = ezdxf.readfile(str(p))
msp = doc.modelspace()

# Second CONT.B ~ x0=9872.4, 244 at 10116.4
# y_top body ~ -150, laje to -136, 7 to -129
x244 = 10116.4
y_body_top = -150.0
y_7_bot = -136.0


def add_vert(kind, layer, x, y1, y2):
    y1, y2 = sorted((y1, y2))
    if y2 - y1 < 1.0:
        return
    through = y1 < y_7_bot - 0.3 and y2 > y_body_top + 0.3
    in_laje = not (y2 <= y_body_top + 0.4 or y1 >= y_7_bot - 0.4)
    if abs(x - x244) < 1.5 or through or in_laje:
        print(
            f"{kind:12} {layer:12} x={x:8.1f} y={y1:8.1f}->{y2:8.1f}"
            f" through={through} in_laje={in_laje}"
        )


print("=== near 3B 244 / laje band ===")
for e in msp:
    layer = str(e.dxf.get("layer", "") or "")
    if e.dxftype() == "LINE":
        a, b = e.dxf.start, e.dxf.end
        if abs(a.x - b.x) > 0.4:
            continue
        if abs(a.x - x244) > 80:
            continue
        add_vert("LINE", layer, round(a.x, 1), a.y, b.y)
    elif e.dxftype() == "LWPOLYLINE":
        pts = list(e.get_points("xy"))
        if len(pts) < 2:
            continue
        closed = bool(e.closed)
        seq = pts + ([pts[0]] if closed and pts[0] != pts[-1] else [])
        for (x1, y1), (x2, y2) in zip(seq, seq[1:]):
            if abs(x1 - x2) > 0.4:
                continue
            if abs(x1 - x244) > 80:
                continue
            add_vert("LWPOLY", layer, round(x1, 1), y1, y2)
