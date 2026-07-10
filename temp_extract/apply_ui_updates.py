import re
import os

# 1. Update obra_detalhe.html to collapse floors by default
path_detalhe = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path_detalhe, 'r', encoding='utf-8') as f:
    content_detalhe = f.read()

old_html_pav = '''        cabPav.innerHTML = '<div style="display:flex; justify-content:space-between; align-items:center; cursor:pointer;" class="pav-header-inner">' +
                           '<span style="flex:1;">' + strPav + '</span>' +
                           '<span class="pav-arrow" style="padding:0 5px;">▼</span>' +
                           '</div>';
        lista.appendChild(cabPav);

        var subLista = document.createElement('ul');
        subLista.style.listStyle = 'none';
        subLista.style.padding = '0';
        subLista.style.margin = '0';'''

new_html_pav = '''        cabPav.innerHTML = '<div style="display:flex; justify-content:space-between; align-items:center; cursor:pointer;" class="pav-header-inner">' +
                           '<span style="flex:1;">' + strPav + '</span>' +
                           '<span class="pav-arrow" style="padding:0 5px;">▶</span>' +
                           '</div>';
        lista.appendChild(cabPav);

        var subLista = document.createElement('ul');
        subLista.style.listStyle = 'none';
        subLista.style.padding = '0';
        subLista.style.margin = '0';
        subLista.style.display = 'none';'''

content_detalhe = content_detalhe.replace(old_html_pav, new_html_pav)
with open(path_detalhe, 'w', encoding='utf-8') as f:
    f.write(content_detalhe)

# 2. Update base.html to move Status Arete above Obras
path_base = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\base.html'
with open(path_base, 'r', encoding='utf-8') as f:
    content_base = f.read()

# Extract Status Arete block
status_block_match = re.search(r'\s*<li><a href="/app/status".*?</li>', content_base, re.DOTALL)
if status_block_match:
    status_block = status_block_match.group(0)
    # Add nav-status-btn class to it
    status_block_mod = status_block.replace('class="', 'class="nav-status-btn ')
    # Remove from original position
    content_base = content_base.replace(status_block, '')
    
    # Insert above Obras
    obras_block_match = re.search(r'\s*<li><a href="/app/obras".*?</li>', content_base, re.DOTALL)
    if obras_block_match:
        obras_block = obras_block_match.group(0)
        content_base = content_base.replace(obras_block, status_block_mod + obras_block)

with open(path_base, 'w', encoding='utf-8') as f:
    f.write(content_base)

# 3. Update portal.css for Obras and Status Arete styles
path_css = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\static\portal.css'
with open(path_css, 'r', encoding='utf-8') as f:
    content_css = f.read()

# Make all obras-strip-item blue boxes
old_css_obras = '''  border-radius: 6px;
  background: none;'''
new_css_obras = '''  border-radius: 6px;
  background: rgba(29, 78, 216, 0.15);'''
content_css = content_css.replace(old_css_obras, new_css_obras)

# Add nav-status-btn styles
status_styles = '''
.nav-status-btn {
  background: rgba(16, 185, 129, 0.15) !important;
  color: #10b981 !important;
  margin-bottom: 8px;
}
.nav-status-btn:hover {
  background: rgba(16, 185, 129, 0.25) !important;
}
.nav-status-btn.ativo {
  background: #10b981 !important;
  color: #fff !important;
}
'''
if '.nav-status-btn' not in content_css:
    content_css += status_styles

with open(path_css, 'w', encoding='utf-8') as f:
    f.write(content_css)

print("Updates applied successfully.")
