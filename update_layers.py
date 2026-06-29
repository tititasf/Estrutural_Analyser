import re

path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\gerar_lj_dxf_stog.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace hardcoded layer names with the new ones
# 1. Painéis -> PAINEIS for lines
text = text.replace("'Pain\\u00e9is'", "'PAINEIS'")
text = text.replace("'Painéis'", "'PAINEIS'")
text = text.replace('"Pain\\u00e9is"', "'PAINEIS'")
text = text.replace('"Painéis"', "'PAINEIS'")

# 2. Layer 3 -> SCO-___-___-___-CTA for paired lines, hatch, structural outlines
# We need to be careful with '3', it might match other things. Let's do regex for layer='3'
text = re.sub(r"layer\s*=\s*['\"]3['\"]", "layer='SCO-___-___-___-CTA'", text)
text = re.sub(r"layer:\s*['\"]3['\"]", "layer: 'SCO-___-___-___-CTA'", text)
text = re.sub(r"layer\s*=\s*['\"]4['\"]", "layer='NOMENCLATURA'", text)

# 3. For dimensions, they should be COTA instead of PAINEIS
# We can find `add_dim_on_paineis` and `add_dim_vertical_on_paineis`
text = re.sub(r"def add_dim_on_paineis\(msp, (.*?)angle=0\):(.*?)dxfattribs=\{'layer': 'PAINEIS'\}(.*?)layer='PAINEIS'", 
              r"def add_dim_on_paineis(msp, \1angle=0):\2dxfattribs={'layer': 'COTA'}\3layer='COTA'", text, flags=re.DOTALL)

text = re.sub(r"def add_dim_vertical_on_paineis\(msp, (.*?)angle=90\):(.*?)dxfattribs=\{'layer': 'PAINEIS'\}(.*?)layer='PAINEIS'", 
              r"def add_dim_vertical_on_paineis(msp, \1angle=90):\2dxfattribs={'layer': 'COTA'}\3layer='COTA'", text, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Layers updated successfully.")
