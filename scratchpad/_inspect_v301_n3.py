from pathlib import Path

p = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
    r"\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga\V301.html"
)
t = p.read_text(encoding="utf-8")
needle = 'class="fv-layer fv-layer-n3'
i = t.find(needle)
print("layer div idx", i)
print(repr(t[i : i + 420]))
print("---")
print("DOCTYPE nearby?", "<!DOCTYPE" in t[i : i + 200])
print("n3 layer count", t.count("fv-layer fv-layer-n3"))
print("data-n3-src", t.count("data-n3-src"))
print("N1 / SA local", t.count("N1 / SA local"))
print("segmento titles", t.count("N1 / SA — V301 · segmento"))

# first identity table snippet around comprimento
j = t.find("Comprimento declarado")
print("comp idx", j)
print(t[j : j + 180])
j = t.find("Largura declarada")
print("larg", t[j : j + 160])
j = t.find("apoios locais do segmento")
print("apoios", t[j : j + 400][:400])
