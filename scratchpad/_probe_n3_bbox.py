from pathlib import Path
import re

raw = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/n3/V301_n3.svg"
).read_text(encoding="utf-8")

# path d coordinates, skip full-canvas fills
content_xs, content_ys = [], []
n_skip = 0
for m in re.finditer(r'<path d="([^"]+)"([^>]*)>', raw):
    d, rest = m.group(1), m.group(2)
    vals = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", d)]
    xs = vals[0::2]
    ys = vals[1::2]
    if not xs:
        continue
    spanx, spany = max(xs) - min(xs), max(ys) - min(ys)
    style = rest
    if spanx > 1000 and spany > 100:
        n_skip += 1
        continue
    content_xs.extend(xs)
    content_ys.extend(ys)
print("skipped bg", n_skip)
print("content x", min(content_xs), max(content_xs), "span", max(content_xs)-min(content_xs))
print("content y", min(content_ys), max(content_ys), "span", max(content_ys)-min(content_ys))
print("n content pts", len(content_xs))
print("viewBox", re.search(r'viewBox="([^"]+)"', raw).group(1))

# clipPath
for m in re.finditer(r"<clipPath[\s\S]{0,400}</clipPath>", raw):
    print("clipPath", m.group(0)[:300])

# fills
fills = re.findall(r"fill: (#[0-9a-fA-F]{3,8})", raw)
from collections import Counter
print("fills", Counter(fills).most_common(8))
strokes = re.findall(r"stroke: (#[0-9a-fA-F]{3,8})", raw)
print("strokes", Counter(strokes).most_common(8))
print("stroke-widths", Counter(re.findall(r"stroke-width: ([0-9.]+)", raw)).most_common(8))
