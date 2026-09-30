from pathlib import Path
import re
from html import unescape

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
    r"\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8")

# Isolate first local section
starts = [m.start() for m in re.finditer(r'N1 / SA — V301 · segmento', t)]
print("local sections", len(starts))
chunk = t[starts[0] : starts[1] if len(starts) > 1 else starts[0] + 8000]
# labels of interest
for lab in [
    "Segmento",
    "Comprimento declarado",
    "Largura declarada",
    "Orientação",
    "Nível",
    "nivel",
    "apoios",
    "local_ini",
    "chanfro",
    "abertura",
    "BBox",
    "Centro",
]:
    i = chunk.lower().find(lab.lower())
    if i >= 0:
        print("---", lab, "---")
        print(unescape(chunk[i : i + 280]).replace("\n", " ")[:280])
        print()

# SA svg: look for text S1
sa = t.find('aria-label="N1 / SA contextual"')
print("sa contextual svg idx", sa)
print(t[sa : sa + 200])
# search S1 text in first 50k of contextual svg
ctx_svg_start = t.find("<svg", sa if sa > 0 else 0)
# actually contextual is inside fv-layer-sa
i = t.find('class="fv-layer fv-layer-sa"')
print("sa layer", i)
svg_i = t.find("<svg", i)
print(t[svg_i : svg_i + 250])
# find S1 in sa layer
sa_end = t.find('class="fv-layer fv-layer-c1"', i)
sa_block = t[i:sa_end]
print("S1 count in SA layer", sa_block.count(">S1<"), "S16", sa_block.count(">S16<"))
print("text S1 sample")
k = sa_block.find(">S1<")
print(sa_block[k - 80 : k + 40] if k >= 0 else "no >S1<")
k = sa_block.find("S1")
print("first S1", sa_block[k - 60 : k + 40] if k >= 0 else None)

# n3 svg viewBox already known
print("n3 files exist for which beams?")
n3dir = p.parent / "n3"
print(sorted(x.name for x in n3dir.glob("*.svg")))
