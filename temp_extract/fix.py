import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("var pav = rb.bruto.pavimento_sugerido || rb.bruto.pavimento_confirmado || 'Indeterminado';", "var pav = rb.bruto.pavimento || 'Indeterminado';")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
