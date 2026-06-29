import re

with open(r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\_ROBOS_ABAS\Robo_Lajes\laje_src\ui\widgets\laje_tab.py', 'r', encoding='utf-8') as f:
    text = f.read()

match = re.search(r'(campos_group = QGroupBox.*?(?=def init_canvas))', text, re.DOTALL)
if match:
    print(match.group(1)[:2000])
