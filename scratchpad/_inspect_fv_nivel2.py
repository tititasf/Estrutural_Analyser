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
for pat in [
    r"nivel_lado_a",
    r"nivel_viga",
    r"laje_superior",
    r"laje_nivel",
    r"visao_corte",
    r"cut_view",
    r"altura_h1",
    r"dimensao",
]:
    print(pat, t.lower().count(pat.lower()))

# ficha of first segment - altura_total vs dim
i = t.find("IDENTIDADE E DECISÃO SA")
print("\n--- first ficha snippet ---")
print(t[i:i+2500][:2500])

# extract per-segment dim and altura from local sections
print("\n--- per segment dim/altura ---")
for n in range(1, 17):
    # find section
    m = re.search(rf"N1 / SA — V301 · segmento {n}</div>", t)
    if not m:
        print(n, "NO SECTION")
        continue
    chunk = t[m.end(): m.end()+8000]
    dim = re.search(rf'"viga_fundo_seg_{n}_dim":\s*"([^"]+)"', chunk)
    alt = re.search(r'"altura_total":\s*([\d.]+)', chunk)
    larg = re.search(r"Largura declarada</td><td[^>]*>([^<]+)", chunk)
    print(f"  seg {n}: dim={dim.group(1) if dim else None}  altura_total={alt.group(1) if alt else None}  largura_decl={larg.group(1) if larg else None}")
