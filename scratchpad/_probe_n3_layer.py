from pathlib import Path
import re

p = Path(
    r"Agente-cad-PYSIDE-Restored-main/scripts/arete/html_fichas/Obra_TREINO_1/"
    r"TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20/"
    r"fundos_viga/V301.html"
)
t = p.read_text(encoding="utf-8")
ctx = t.split("<!--FVCTX_START-->", 1)[-1].split("<!--FVCTX_END-->", 1)[0]
print("DOCTYPE svg in ctx", "<!DOCTYPE svg" in ctx)
print("data-n3-src", "data-n3-src" in ctx)
i = ctx.find("fv-layer fv-layer-n3")
print("n3 idx", i)
print("---open tag---")
print(ctx[i : i + 400])
# find the n3 div contents until next fv-layer or close of layers
start = ctx.rfind("<div", 0, i)
gt = ctx.find(">", i)
# naive: next sibling starts at next <div class=" or end
rest = ctx[gt + 1 :]
print("---inner first 300---")
print(rest[:300])
print("---has svg after n3 open---")
print("<svg" in rest[:5000])
print("inner starts with", repr(rest[:80]))
svg = Path(p.parent / "n3" / "V301_n3.svg")
print("disk svg exists", svg.exists(), "size", svg.stat().st_size if svg.exists() else 0)
raw = svg.read_text(encoding="utf-8", errors="replace")
print("disk doctype", raw.lstrip().startswith("<!DOCTYPE"))
print("disk viewBox", re.search(r'viewBox="([^"]+)"', raw).group(1) if re.search(r'viewBox="([^"]+)"', raw) else None)
print("disk paths", raw.count("<path"))
print("disk clipPath", raw.count("clipPath"), "clip-path", raw.count("clip-path"))
