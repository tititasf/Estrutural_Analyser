path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/main.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "if item_data.get('is_fully_validated'): status_icon =" in line:
        if "status_icon = " not in lines[i-1]:
            lines.insert(i, '            status_icon = "⏳"\n')
        break

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('status_icon corrigido com sucesso!')
