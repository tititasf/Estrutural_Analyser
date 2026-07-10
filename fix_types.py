import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace TIPOS_ORDEM
old_tipos = "var TIPOS_ORDEM = ['Bruto', 'Detalhe', 'PDF', 'Outro'];"
new_tipos = "var TIPOS_ORDEM = ['brutos', 'N1', 'N2', 'N3', 'N4', 'N5', 'detalhes', 'pdfs', 'outros'];"
content = content.replace(old_tipos, new_tipos)

old_labels = "var TIPOS_LABEL = { Bruto: 'Brutos', Detalhe: 'Detalhes', PDF: 'PDFs', Outro: 'Outros' };"
new_labels = "var TIPOS_LABEL = { brutos: 'Brutos', N1: 'N1 - Estrutural Recortado', N2: 'N2', N3: 'N3 - Vigas Recortadas', N4: 'N4', N5: 'N5 - Pilares Recortados', detalhes: 'Detalhes', pdfs: 'PDFs', outros: 'Outros' };"
content = content.replace(old_labels, new_labels)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Replaced TIPOS_ORDEM and TIPOS_LABEL')
