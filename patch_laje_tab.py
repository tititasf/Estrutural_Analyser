import re
import sys

path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\_ROBOS_ABAS\Robo_Lajes\laje_src\ui\widgets\laje_tab.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

old_def = 'def automate_ai_for_all_lajes(self):'
new_def = 'def automate_ai_for_all_lajes(self, progress_callback=None):'
text = text.replace(old_def, new_def)

lines = text.split('\n')
for i, line in enumerate(lines):
    if 'print(f"[AI AUTOMATION] [{idx+1}/{total}] Processando {laje.nome}...")' in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines.insert(i+1, indent + 'if progress_callback:')
        lines.insert(i+2, indent + '    pct = int(((idx+1) / total) * 100)')
        lines.insert(i+3, indent + '    progress_callback(pct, f"IA processando {laje.nome} ({idx+1}/{total})...")')
        break

with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
