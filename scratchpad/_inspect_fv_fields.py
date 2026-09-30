from pathlib import Path
import re
from html import unescape
from collections import Counter

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
    r"\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = unescape(p.read_text(encoding="utf-8"))

# all unique field-like keys around viga_fundo / nivel / dim / altura
keys = set(re.findall(r'"([a-z0-9_]*nivel[a-z0-9_]*)"', t, re.I))
keys |= set(re.findall(r'"([a-z0-9_]*altura[a-z0-9_]*)"', t, re.I))
keys |= set(re.findall(r'"([a-z0-9_]*dim[a-z0-9_]*)"', t, re.I))
keys |= set(re.findall(r'"([a-z0-9_]*corte[a-z0-9_]*)"', t, re.I))
keys |= set(re.findall(r'"([a-z0-9_]*laje[a-z0-9_]*)"', t, re.I))
print("keys:")
for k in sorted(keys):
    print(" ", k)

print("\n--- dimensao ---")
for m in re.finditer(r'"dimensao"\s*:\s*"([^"]+)"', t):
    print(m.group(0)[:80])
    break
print("dimensao count", len(re.findall(r'"dimensao"', t)))

print("\n--- sample campos SA keys from first identity ---")
i = t.find("campos SA do segmento")
print(t[i:i+1800][:1800])
