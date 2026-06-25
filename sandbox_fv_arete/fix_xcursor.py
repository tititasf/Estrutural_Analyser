import sys

file_path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/gerar_fv_dxf_stog.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """    if seg_idx < len(gaps):
        gap_w = gaps[seg_idx][0]
        dim_panel(msp, seg_x_end, seg_x_end + gap_w, y0)
        x_cursor += gap_w"""

replacement = """    x_cursor = seg_x_end
    if seg_idx < len(gaps):
        gap_w = gaps[seg_idx][0]
        dim_panel(msp, seg_x_end, seg_x_end + gap_w, y0)
        x_cursor += gap_w"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed x_cursor bug in gerar_fv_dxf_stog.py")
else:
    print("Target not found")
