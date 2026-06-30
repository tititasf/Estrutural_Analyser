import re

fname = 'src/ui/modules/diagnostic_hub.py'
with open(fname, 'r', encoding='utf-8') as f:
    content = f.read()

def replace_transparent_bg(m):
    block = m.group(0)
    hover_match = re.search(r'QPushButton:hover\s*\{\{?\s*background:\s*(rgba\([^)]+\));', block)
    if hover_match:
        hover_color = hover_match.group(1)
        # make normal color slightly transparent compared to hover, or just solid
        normal_color = hover_color.replace('230', '180').replace('160', '180')
        block = re.sub(r'background:\s*transparent;', f'background: {normal_color};', block)
        block = re.sub(r'background:\s*\{Colors\.BG_DEEP\};', f'background: {normal_color};', block)
        block = re.sub(r'border:\s*1px\s*solid\s*rgba\([^)]+\);', 'border: none;', block)
        block = re.sub(r'color:\s*\{Colors\.TEXT_SECONDARY\};', 'color: white;', block)
    return block

content = re.sub(r'\.setStyleSheet\(f\"\"\"(.*?)\"\"\"\)', replace_transparent_bg, content, flags=re.DOTALL)

def fix_class_btns(m):
    block = m.group(0)
    block = block.replace('background: transparent;', 'background: {cls_color};')
    block = re.sub(r'QPushButton:hover:!checked[^}]+}', 'QPushButton:hover:!checked {{ background: rgba(255, 255, 255, 30); }}', block)
    return block

content = re.sub(r'btn\.setStyleSheet\(f\"\"\"(.*?QPushButton:checked.*?)\"\"\"\)', fix_class_btns, content, flags=re.DOTALL)

# For 'Abrir' and 'Atualizar' that don't have rgba hover but use Colors.BG_DEEP and Colors.ACCENT_TEAL
content = re.sub(
    r'btn_abrir_dxf\.setStyleSheet\(f\"\"\"(.*?)background:\s*\{Colors\.BG_DEEP\};(.*?)QPushButton:hover',
    r'btn_abrir_dxf.setStyleSheet(f"""\1background: {Colors.BG_CARD};\2QPushButton:hover',
    content, flags=re.DOTALL
)
content = re.sub(
    r'btn_refresh\.setStyleSheet\(f\"\"\"(.*?)background:\s*\{Colors\.BG_DEEP\};(.*?)QPushButton:hover',
    r'btn_refresh.setStyleSheet(f"""\1background: {Colors.BG_CARD};\2QPushButton:hover',
    content, flags=re.DOTALL
)

# For 'Modo 1' and 'Modo 3' which are transparent
content = re.sub(
    r'btn\.setStyleSheet\(f\"\"\"(.*?)background:\s*transparent;(.*?)QPushButton:hover',
    r'btn.setStyleSheet(f"""\1background: {Colors.BG_CARD};\2QPushButton:hover',
    content, flags=re.DOTALL
)

with open(fname, 'w', encoding='utf-8') as f:
    f.write(content)
