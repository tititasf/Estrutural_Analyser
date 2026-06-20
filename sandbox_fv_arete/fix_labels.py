import sys
import re

file_path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/gerar_fv_dxf_stog.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """        # Textos de inicio e fim de segmento (Labels ESQ / DIR)
        seg_label_left = label_left if seg_idx == 0 else gaps[seg_idx - 1][1]
        seg_label_right = label_right if seg_idx == len(segments) - 1 else gaps[seg_idx][1]
        add_text(msp, seg_x0 - 5.0, y0 - 5.0, seg_label_left, 8, '5', halign=2, rotation=90)
        add_text(msp, seg_x_end + 12.0, y0 - 5.0, seg_label_right, 8, '5', halign=2, rotation=90)"""

replacement = """        # Textos de inicio e fim de segmento (Labels ESQ / DIR)
        if seg_idx == 0 and label_left:
            add_text(msp, seg_x0, y0 - 30.0, label_left, 8, '5', halign=0, rotation=0)
        
        if seg_idx == len(segments) - 1 and label_right:
            add_text(msp, seg_x_end, y0 - 30.0, label_right, 8, '5', halign=2, rotation=0)
            
        if seg_idx < len(gaps):
            gap_label = gaps[seg_idx][1]
            if gap_label and gap_label != 'Pilar Cruzado':
                gap_center = seg_x_end + gaps[seg_idx][0] / 2
                add_text(msp, gap_center, y0 - 30.0, gap_label, 8, '5', halign=1, rotation=0)"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed labels")
else:
    print("Target not found")
