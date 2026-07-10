import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\routers\obras_routes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'\"eh_obra_rapida\":\s*bool\(obra\.get\(\"arquivo_nome\"\)\),?\s*', '', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
