import json
from pathlib import Path
import shutil
import sys

if len(sys.argv) == 1:
    helper = Path('portal/app/static/drawing_mode.js').read_text(encoding='utf-8')
    payload = {'helper':helper[helper.index('  function applyBadge('):helper.index('  window.DrawingMode')]}
    Path('scripts/n3_mode_tabs.json').write_text(json.dumps(payload),encoding='utf-8')
    sys.exit()
root = Path('/opt/cad-analyzer')
backup = Path('/root/backup_n3_mode_tabs_20260930')
payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
staged = {}
path = root / 'portal/app/static/drawing_mode.js'
value = path.read_text(encoding='utf-8')
start,end = value.index('  function applyBadge('),value.index('  window.DrawingMode')
assert 'return badge;' in value[start:end]
staged[path] = value[:start] + payload['helper'] + value[end:]

def patch(filename,old,new):
    path = root / ('portal/app/static/' + filename)
    value = staged.get(path,path.read_text(encoding='utf-8'))
    assert value.count(old)==1, filename
    staged[path]=value.replace(old,new,1)

old = "    if(window.aplicarTagModoDesenho)window.aplicarTagModoDesenho(viewport,this.visualMode,{onChange:function(mode){this.visualMode=mode;this.load();}.bind(this)});\n    card.appendChild(viewport);"
patch('pillar_ficha.js',old, '\n'.join(reversed(old.split('\n'))))
old = "      var missingSwitch = button('Ver modo ' + (this.visualMode === 'INI' ? 'Nova' : 'Ini'),'',function(){this.visualMode=this.visualMode==='INI'?'NOVA':'INI';if(window.atualizarModoDesenhoUrl)window.atualizarModoDesenhoUrl(this.visualMode);this.load();}.bind(this),'');\n      card.appendChild(missingSwitch);"
new = "      var missingViewport = el('div', 'plf-missing-mode-anchor');\n      card.appendChild(missingViewport);\n      if(window.aplicarTagModoDesenho)window.aplicarTagModoDesenho(missingViewport,this.visualMode,{onChange:function(mode){this.visualMode=mode;this.load();}.bind(this)});"
patch('pillar_ficha.js',old,new)
patch('fv_ficha.js',"      state.pz = initPanZoom(canvas);\n      if (name === 'n3'", "      state.pz = initPanZoom(canvas);\n      var modeTabs = canvas.previousElementSibling;\n      if (name !== 'n3' && modeTabs && modeTabs.classList.contains('drawing-mode-tabs')) modeTabs.remove();\n      if (name === 'n3'")
patch('portal.css','button.drawing-mode-badge { cursor:pointer; pointer-events:auto; }', 'button.drawing-mode-badge { cursor:pointer; pointer-events:auto; }\n.drawing-mode-tabs { margin:10px 0; grid-template-columns:repeat(2,minmax(0,1fr)); max-width:600px; }')
for path,value in staged.items():
    target=backup/path.relative_to(root)
    target.parent.mkdir(parents=True,exist_ok=True)
    assert not target.exists()
    shutil.copy2(path,target)
    path.write_text(value,encoding='utf-8')
    print(path)
