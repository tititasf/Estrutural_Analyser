import sys
import re

file_path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/gerar_fv_dxf_stog.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = r"(if seg_idx < len\(gaps\):\s+gap_w = gaps\[seg_idx\]\[0\]\s+dim_panel\(msp, seg_x_end, seg_x_end \+ gap_w, y0\)\s+x_cursor \+= gap_w)"
match = re.search(target, content)

if match:
    replacement = "x_cursor = seg_x_end\n    " + match.group(1)
    content = content[:match.start()] + replacement + content[match.end():]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed x_cursor bug via regex")
else:
    print("Regex not found")
