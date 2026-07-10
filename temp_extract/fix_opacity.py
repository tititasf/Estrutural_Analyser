import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix opacity logic: The active state should be opacity 1.0, the inactive state should be 0.4
old_html = '''              '<button type="button" class="btn" id="btn-validar-recorte" style="background:#10b981;color:#fff;border:none; ' + (d.validado ? 'opacity:0.5;' : '') + '">Validar</button>' +
              '<button type="button" class="btn" id="btn-invalidar-recorte" style="background:#ef4444;color:#fff;border:none; ' + (!d.validado && d.validado !== undefined ? 'opacity:0.5;' : '') + '">Invalidar</button>' +'''

new_html = '''              '<button type="button" class="btn" id="btn-validar-recorte" style="background:#10b981;color:#fff;border:none; ' + (d.validado === false ? 'opacity:0.4;' : '') + '">Validar Recorte</button>' +
              '<button type="button" class="btn" id="btn-invalidar-recorte" style="background:#ef4444;color:#fff;border:none; ' + (d.validado === true ? 'opacity:0.4;' : '') + '">Invalidar</button>' +'''
content = content.replace(old_html, new_html)

old_js = '''                  if (j.status === 'ok') {
                      d.validado = j.validado;
                      if(btnValidar) btnValidar.style.opacity = d.validado ? '0.5' : '1';
                      if(btnInvalidar) btnInvalidar.style.opacity = (!d.validado) ? '0.5' : '1';
                  }'''
new_js = '''                  if (j.status === 'ok') {
                      d.validado = j.validado;
                      if(btnValidar) btnValidar.style.opacity = (d.validado === false) ? '0.4' : '1';
                      if(btnInvalidar) btnInvalidar.style.opacity = (d.validado === true) ? '0.4' : '1';
                  }'''
content = content.replace(old_js, new_js)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
