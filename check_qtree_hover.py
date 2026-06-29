import re
with open(r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\main.py', 'r', encoding='utf-8') as f:
    text = f.read()
matches = re.findall(r'QTreeWidget::item:hover[^}]+}', text)
for m in matches:
    print(m)
