from pathlib import Path

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
    r"\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8")
a = t.find("<!--FVCTX_START-->")
b = t.find("<!--FVCTX_END-->")
block = t[a:b]
print("ctx len", len(block))
# print structure tags only
import re
for m in re.finditer(
    r'<(div class="(?:sec|sec-title|sec-body|fv-ctx-notes|fv-human-box|fv-agent-box|fv-layer-toggle|fv-layer)[^"]*"|div id="fvctx_)',
    block,
):
    print(m.group(0)[:120])

print("--- first 1500 after body ---")
i = block.find('class="sec-body"')
print(block[i : i + 1200])
print("--- TOGGLE ---")
i = block.find("fv-layer-toggle")
print(block[i : i + 900])
