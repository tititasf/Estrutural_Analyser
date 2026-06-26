path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/src/ui/components/project_cards.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'header.addWidget(lbl_name)' in line:
        block = """        pid = str(self.data.get('id', '???'))[:8]
        lbl_id = QLabel(pid.upper())
        lbl_id.setAlignment(Qt.AlignCenter)
        lbl_id.setFixedSize(70, 24)
        lbl_id.setStyleSheet(f\"\"\"
            background-color: {Colors.BG_HOVER}; color: rgba(136, 144, 176, 1); 
            border-radius: 4px; font-family: monospace; font-size: 11px; font-weight: bold;
        \"\"\")
        header.addWidget(lbl_id)
        
        p_name = self.data.get('project_name') or self.data.get('name') or 'Sem Nome'
        lbl_name = QLabel(str(p_name).upper())
        lbl_name.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {Colors.TEXT_BRIGHT};")
"""
        if not any("pid =" in l for l in new_lines):
            new_lines.append(block)
            new_lines.append(line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print('Restaurado com sucesso!')
