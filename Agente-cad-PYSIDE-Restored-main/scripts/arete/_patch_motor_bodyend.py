# -*- coding: utf-8 -*-
from pathlib import Path
import os

p = Path(__file__).resolve().parent.parent / "gerar_lv_dxf_stog.py"
text = p.read_text(encoding="utf-8")

old = """def _small_panel_start_x(x0, h, panels, threshold=25.0):
    x = float(x0)
    for panel in panels:
        pw = float(panel.get('width', 0) or 0)
        if not _is_degrau_panel(panel, h) and pw < threshold:
            return x
        x += pw
    return None
"""

new = """def _small_panel_start_x(x0, h, panels, threshold=25.0):
    \"\"\"Inicio da faixa de marco (estreitos finais apos bay largo).

    Nao corta no meio da face: em V301.B o 22.5 apos 244 nao e marco.
    Marco so apos bay >=55 (ex. 111|19|21.2 em V301.A).
    \"\"\"
    plist = list(panels or [])
    if not plist:
        return None
    widths = [float(p.get('width', 0) or 0) for p in plist]
    n = len(widths)
    i1 = n
    while i1 > 0:
        pw = widths[i1 - 1]
        if pw <= 0:
            i1 -= 1
            continue
        if pw < threshold and not _is_degrau_panel(plist[i1 - 1], h):
            i1 -= 1
            continue
        break
    if i1 <= 0 or i1 >= n:
        return None
    if widths[i1 - 1] < 55.0:
        return None
    return float(x0) + sum(widths[:i1])
"""

if old not in text:
    raise SystemExit("small_x block not found")
text = text.replace(old, new, 1)
print("small_x ok")

old2 = """    i0 = 0
    while i0 < n and _is_marco_strip(i0):
        i0 += 1
    i1 = n
    while i1 > i0 and _is_marco_strip(i1 - 1):
        i1 -= 1
    kept = widths[i0:i1]
    return kept if kept else widths
"""

new2 = """    i0 = 0
    while i0 < n and _is_marco_strip(i0):
        i0 += 1
    i1 = n
    while i1 > i0 and _is_marco_strip(i1 - 1):
        i1 -= 1
    # trailing marco so apos bay largo (>=55); senao 21.7|26.2 de B e corpo
    if i1 < n and i1 > i0 and float(widths[i1 - 1]) < 55.0:
        i1 = n
    kept = widths[i0:i1]
    return kept if kept else widths
"""

if old2 not in text:
    raise SystemExit("marco strip block not found")
text = text.replace(old2, new2, 1)
print("marco strip ok")

tmp = p.with_suffix(".py.tmp_patch")
tmp.write_text(text, encoding="utf-8")
os.replace(str(tmp), str(p))
print("patched", p)
