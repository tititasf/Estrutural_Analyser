import os
import re

path = 'D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/src/ui/widgets/detail_card.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Substituir textos
content = content.replace('QPushButton("▶ Vincular")', 'QPushButton("Vincular")')
content = content.replace('QPushButton("Vinc.")', 'QPushButton("Vincular")')
content = content.replace('btn_links.setText("▶")', 'btn_links.setText("Vínculos")')

# Remover amarras de FixedSize e FixedWidth
content = re.sub(r'btn_links?\.setFixedSize\(\d+,\s*\d+\)', 'btn_link.setFixedHeight(22)', content)
content = re.sub(r'btn_links?\.setFixedWidth\(\d+\)', '', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Botões libertados das amarras de largura!')
