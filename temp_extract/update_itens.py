path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\routers\recortes_routes.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('"itens": [{"item_id": i["item_id"], "titulo": i["titulo"]} for i in itens]', '"itens": [{"item_id": i["item_id"], "titulo": i["titulo"], "validado": i.get("validado", False)} for i in itens]')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
