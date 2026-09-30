from pathlib import Path
import re

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas\Obra_TREINO_1"
    r"\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8", errors="replace")
print("fv-pt-btn", t.count("fv-pt-btn"))
print("Reset zoom", t.count("Reset zoom"))
print("human-tab", t.count("fv-human-tab-btn"))
print("Anotações Pontos", t.count("Anotações Pontos"))
print("SA / Camadas", t.count("SA / Camadas"))
print("toggleFvPointMode", t.count("toggleFvPointMode"))
print("fill:\\s*none in html", "fill:\\s*none" in t)
print("fill:\\s*none raw", t.count(r"fill:\s*none"))

i = t.find('<script id="fv-hifi-panzoom">')
j = t.find("</script>", i)
script = t[i:j]
print("script len", len(script))
# write script for node check
out = Path(r"D:\Agente-cad-PYSIDE\scratchpad\_fv_panzoom.js")
# strip script tags
body = script.split(">", 1)[-1]
out.write_text(body, encoding="utf-8")
print("wrote", out, "chars", len(body))

# find likely bad tokens
for needle in ["\\\\n", "join('\\n')", "join(\"\\n\")", "fill:\\s", "/fill:"]:
    print("needle", repr(needle), body.count(needle) if needle in body or True else 0, body.find(needle))
