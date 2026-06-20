import sys

file_path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/gerar_fv_dxf_stog.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if i == 497:
        new_lines.append('        x_cursor = seg_x_end\n')
    elif i == 498:
        new_lines.append('        if seg_idx < len(gaps):\n')
    elif i == 499:
        new_lines.append('            gap_w = gaps[seg_idx][0]\n')
    elif i == 500:
        new_lines.append('            dim_panel(msp, seg_x_end, seg_x_end + gap_w, y0)\n')
    elif i == 501:
        new_lines.append('            x_cursor += gap_w\n')
    else:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Fixed indentation")
