from pathlib import Path
import re

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete"
    r"\html_fichas\Obra_TREINO_1\13_PAV_20260730_210556_pilares_abcd"
    r"\propostas\P1_qa_proposta.svg"
)
t = p.read_text(encoding="utf-8")
print("len", len(t))
print("labels_top", "pil_agentic_labels_top" in t)
# find a text group sample
m = re.search(r'(<g id="text_\d+"[\s\S]{0,800}?</g>)', t)
if m:
    print("--- sample text group ---")
    print(m.group(1)[:800])
# find PAS string context
i = t.find("PAS")
print("--- PAS context ---")
print(t[max(0, i - 200) : i + 400] if i >= 0 else "no PAS")
# fill colors for tags
fills = re.findall(r'fill:\s*#([0-9a-fA-F]{6})', t)
from collections import Counter
print("top fills", Counter(fills).most_common(15))
print("font-size", sorted(set(re.findall(r"font-size:\s*([^;]+)", t)))[:20])
# check if text uses use/href glyphs
print("use xlink", t.count("xlink:href"), "tspan", t.count("<tspan"), "<text", t.count("<text"))
