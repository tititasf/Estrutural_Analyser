import os

path_base = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\base.html'
with open(path_base, 'r', encoding='utf-8') as f:
    content_base = f.read()

# Fix the duplicate nav-status-btn class
content_base = content_base.replace('<span class="nav-status-btn nav-texto">', '<span class="nav-texto">')

with open(path_base, 'w', encoding='utf-8') as f:
    f.write(content_base)
