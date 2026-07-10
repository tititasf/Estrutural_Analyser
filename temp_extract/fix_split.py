path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('is_virtual_recorte: true,', 'original_item_id: it.item_id,\n                       is_virtual_recorte: true,')
content = content.replace("encodeURIComponent(d.id.split('_')[0])", "encodeURIComponent(d.original_item_id)")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
