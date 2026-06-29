import re

path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\gerar_lj_dxf_stog.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

# Replace hardcoded '3' with 'SCO-___-___-___-CTA'
# Be careful not to replace it in the dictionary definition: "'3':                      3,"
# We can use regex to match 'layer': '3' or layer='3' or '3' as argument to add_pline_rect and _add_clipped_axis_lines.

text = text.replace("'layer': '3'", "'layer': 'SCO-___-___-___-CTA'")
text = text.replace("layer='3'", "layer='SCO-___-___-___-CTA'")
text = text.replace("abs_x, '3'", "abs_x, 'SCO-___-___-___-CTA'")
text = text.replace("abs_y, '3'", "abs_y, 'SCO-___-___-___-CTA'")
text = text.replace("h_s, '3'", "h_s, 'SCO-___-___-___-CTA'")

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Layer 3 replaced successfully.")
