import re

path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\main.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

matches = re.findall(r'self\.list_slabs = (.*?)def ', text, re.DOTALL)
if matches:
    print(matches[0][:2000])
