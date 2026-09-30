# -*- coding: utf-8 -*-
"""Inspect actual generated N4 combined DXF for Face B Painéis verts."""
import ezdxf
from pathlib import Path

p = Path(r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n4\LV_preview_V301_A.dxf")
doc = ezdxf.readfile(str(p))
msp = doc.modelspace()

# Collect labels to locate units
texts = []
for e in msp:
    if e.dxftype() == "TEXT":
        t = str(e.dxf.get("text", "") or "")
        if "V301" in t or "CONT" in t or "UNIT" in t:
            texts.append((round(e.dxf.insert.x, 1), round(e.dxf.insert.y, 1), t, e.dxf.layer))
print("LABELS")
for row in sorted(texts):
    print(" ", row)

print("\nPainéis V grouped by x clusters (x, y1, y2, len)")
verts = []
for e in msp:
    if e.dxftype() != "LINE":
        continue
    layer = str(e.dxf.layer or "")
    if layer != "Painéis":
        continue
    a, b = e.dxf.start, e.dxf.end
    if abs(a.x - b.x) > 0.4:
        continue
    y1, y2 = sorted((a.y, b.y))
    if y2 - y1 < 5:
        continue
    verts.append((round(a.x, 1), round(y1, 1), round(y2, 1), round(y2 - y1, 1)))

# print by increasing x, but only show those whose fractional relative to nearest 244-like
for v in sorted(verts):
    print(" ", v)
