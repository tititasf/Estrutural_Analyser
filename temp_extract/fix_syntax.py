path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# The incorrect snippet is:
# '<label>Classe estrutural<select id="docs-det-classe">' + '
#             '<option value=""' + (classeAtual ? '' : ' selected') + '>'
# It should be:
# '<label>Classe estrutural<select id="docs-det-classe">' +
#             '<option value=""' + (classeAtual ? '' : ' selected') + '>'

content = content.replace('<select id="docs-det-classe">\' + \'\n', '<select id="docs-det-classe">\' +\n')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
