import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\routers\portal_documentos_routes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'@router.post\("/[^"]+/documentos/\{doc_id\}/mover"[^\n]*\n(?:[ \t]+.*?\n)+', content)
if match:
    print(match.group(0))
else:
    print('Not found')
