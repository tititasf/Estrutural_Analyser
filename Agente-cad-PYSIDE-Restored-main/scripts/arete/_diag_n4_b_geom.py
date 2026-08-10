# -*- coding: utf-8 -*-
import ezdxf
from pathlib import Path

n4 = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1"
    r"\Fase-6_Execucao_CAD\n4\LV_preview_V301_VIEW_B.dxf"
)
doc = ezdxf.readfile(str(n4))
msp = doc.modelspace()

labs = []
for e in msp.query("TEXT"):
    t = (e.dxf.text or "").strip()
    if t:
        labs.append((round(e.dxf.insert.x, 1), round(e.dxf.insert.y, 1), t))
labs.sort()
print("LABELS", labs)

lx = None
for x, y, t in labs:
    if t == "V301.B":
        lx = x
        print("V301.B at", x, y)
        break

vs = []
hs = []
for e in msp:
    if e.dxftype() != "LINE":
        continue
    if e.dxf.layer not in ("Painéis", "Paineis"):
        continue
    s, e2 = e.dxf.start, e.dxf.end
    if abs(s.x - e2.x) < 0.4:
        h = abs(e2.y - s.y)
        if h > 15 and lx - 80 < s.x < lx + 500:
            vs.append(
                (
                    round(float(s.x), 1),
                    round(min(s.y, e2.y), 1),
                    round(max(s.y, e2.y), 1),
                    round(h, 1),
                )
            )
    if abs(s.y - e2.y) < 0.4:
        w = abs(e2.x - s.x)
        if w > 30 and lx - 80 < 0.5 * (s.x + e2.x) < lx + 500:
            hs.append(
                (
                    round(float(s.y), 1),
                    round(min(s.x, e2.x), 1),
                    round(max(s.x, e2.x), 1),
                    round(w, 1),
                )
            )
print("V lines")
for v in sorted(set(vs)):
    print(" ", v)
print("H long")
for h in sorted(set(hs)):
    print(" ", h)

print("DIMENSION near V301.B")
for e in msp.query("DIMENSION"):
    try:
        m = float(e.dxf.actual_measurement)
        dp = e.dxf.defpoint
        if lx - 100 < dp.x < lx + 500:
            print(
                " DIM",
                round(m, 2),
                "at",
                round(dp.x, 1),
                round(dp.y, 1),
                "txt",
                e.dxf.get("text"),
            )
    except Exception:
        pass

print("numeric TEXT near")
for e in msp.query("TEXT"):
    t = (e.dxf.text or "").strip().replace(",", ".")
    try:
        v = float(t)
    except Exception:
        continue
    if lx - 100 < e.dxf.insert.x < lx + 500:
        print(
            " TXT",
            v,
            "at",
            round(e.dxf.insert.x, 1),
            round(e.dxf.insert.y, 1),
        )
