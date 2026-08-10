# -*- coding: utf-8 -*-
import ezdxf
from pathlib import Path

n4 = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1"
    r"\Fase-6_Execucao_CAD\n4\LV_preview_V301_VIEW_B.dxf"
)
doc = ezdxf.readfile(str(n4))
msp = doc.modelspace()

# V301.B origin ~1236
x0, x1 = 1200, 1700
print("=== DIMENSION in band ===")
for e in msp.query("DIMENSION"):
    vals = []
    try:
        vals.append(("actual", float(e.dxf.actual_measurement)))
    except Exception as ex:
        vals.append(("actual_err", str(ex)[:40]))
    try:
        vals.append(("get", float(e.get_measurement())))
    except Exception as ex:
        vals.append(("get_err", str(ex)[:40]))
    txt = e.dxf.get("text")
    try:
        defpoint = e.dxf.defpoint
        dx, dy = float(defpoint.x), float(defpoint.y)
    except Exception:
        dx, dy = None, None
    try:
        p1 = e.dxf.defpoint2
        p2 = e.dxf.defpoint3
        mids = (
            0.5 * (float(p1.x) + float(p2.x)),
            0.5 * (float(p1.y) + float(p2.y)),
        )
    except Exception:
        mids = None
    if dx is not None and x0 <= dx <= x1:
        print("def", round(dx, 1), round(dy, 1), "txt", txt, vals, "mid", mids)
    elif mids and x0 <= mids[0] <= x1:
        print("mid", mids, "txt", txt, vals)

print("=== TEXT numeric band ===")
for e in msp.query("TEXT"):
    t = (e.dxf.text or "").strip()
    x, y = float(e.dxf.insert.x), float(e.dxf.insert.y)
    if x0 <= x <= x1:
        print(repr(t), "at", round(x, 1), round(y, 1))
