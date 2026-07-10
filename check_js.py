import re
with open(r'D:\Agente-cad-PYSIDE\temp.js', 'r', encoding='utf-8') as f:
    js = f.read()
js = re.sub(r'\{\{.*?\}\}', '""', js)
js = re.sub(r'\{%.*?%\}', '', js)
with open(r'D:\Agente-cad-PYSIDE\temp2.js', 'w', encoding='utf-8') as f:
    f.write(js)
