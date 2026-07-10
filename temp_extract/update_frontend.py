path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Do not populate recortes in 'Docs Geral da Obra'
old_loop = '''           recortesBrutos.forEach(function(rb) {
               var pav = rb.bruto.pavimento || 'Indeterminado';
               
               rb.itens.forEach(function(it) {'''
new_loop = '''           recortesBrutos.forEach(function(rb) {
               var pav = rb.bruto.pavimento || 'Indeterminado';
               if (pav === 'Indeterminado') return; // Do not populate recortes in Geral
               
               rb.itens.forEach(function(it) {'''
content = content.replace(old_loop, new_loop)

# 2. Map `validado` from `it.validado`
old_push = '''                       is_virtual_recorte: true,
                       is_torre_limpa: tipo === 'Recortes Torres Limpas',
                       bruto_id: rb.bruto.bruto_id'''
new_push = '''                       is_virtual_recorte: true,
                       is_torre_limpa: tipo === 'Recortes Torres Limpas',
                       validado: it.validado,
                       bruto_id: rb.bruto.bruto_id'''
content = content.replace(old_push, new_push)

# 3. Add buttons to the detail panel
old_btn = '''        '<div style="margin-top:10px;display:flex;gap:8px;align-items:center">' +
          '<button type="button" class="btn" id="docs-det-salvar">Salvar</button>' +
          '<span id="docs-det-resultado" class="meta" role="status" aria-live="polite"></span>' +
        '</div>' + 
        '<div id="item-viewer-container" style="margin-top:20px;"></div>';'''

new_btn = '''        '<div style="margin-top:10px;display:flex;gap:8px;align-items:center">' +
          '<button type="button" class="btn" id="docs-det-salvar">Salvar</button>' +
          ( (d.tipo_documento_sugerido === 'Bruto' || d.tipo_documento_confirmado === 'Bruto') ? '<button type="button" class="btn" id="btn-reprocessar-bruto" style="background:#f59e0b;color:#fff;border:none;">Reprocessar Recortes</button>' : '' ) +
          ( d.is_virtual_recorte ? '<button type="button" class="btn" id="btn-validar-recorte" style="background:' + (d.validado ? '#ef4444' : '#10b981') + ';color:#fff;border:none;">' + (d.validado ? 'Invalidar Recorte' : 'Validar Recorte') + '</button>' : '' ) +
          '<span id="docs-det-resultado" class="meta" role="status" aria-live="polite"></span>' +
        '</div>' + 
        '<div id="item-viewer-container" style="margin-top:20px;"></div>';'''
content = content.replace(old_btn, new_btn)

# 4. Add event listeners for the new buttons
old_event = '''      document.getElementById('docs-det-salvar').addEventListener('click', function () {'''
new_event = '''      var btnReprocessar = document.getElementById('btn-reprocessar-bruto');
      if (btnReprocessar) {
          btnReprocessar.addEventListener('click', function() {
              if (!confirm('Deseja reprocessar os recortes deste bruto? Recortes NÃO validados serão sobrescritos.')) return;
              btnReprocessar.disabled = true;
              btnReprocessar.textContent = 'Reprocessando...';
              fetch('/obras/' + OBRA_ID + '/recortes/brutos/' + encodeURIComponent(d.id) + '/reprocessar', {method: 'POST'})
                .then(r => r.json())
                .then(j => {
                    if (j.status === 'ok') {
                        alert('Recortes reprocessados com sucesso!');
                        montarLista();
                    } else {
                        alert('Erro ao reprocessar recortes.');
                    }
                })
                .catch(e => alert('Erro: ' + e))
                .finally(() => {
                    btnReprocessar.disabled = false;
                    btnReprocessar.textContent = 'Reprocessar Recortes';
                });
          });
      }
      
      var btnValidar = document.getElementById('btn-validar-recorte');
      if (btnValidar) {
          btnValidar.addEventListener('click', function() {
              var novoStatus = !d.validado;
              btnValidar.disabled = true;
              fetch('/obras/' + OBRA_ID + '/recortes/brutos/' + encodeURIComponent(d.bruto_id) + '/' + encodeURIComponent(d.id.split('_')[0]) + '/validar', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({validado: novoStatus})
              }).then(r => r.json()).then(j => {
                  if (j.status === 'ok') {
                      d.validado = j.validado;
                      btnValidar.style.background = d.validado ? '#ef4444' : '#10b981';
                      btnValidar.textContent = d.validado ? 'Invalidar Recorte' : 'Validar Recorte';
                  }
              }).finally(() => {
                  btnValidar.disabled = false;
              });
          });
      }

      document.getElementById('docs-det-salvar').addEventListener('click', function () {'''
content = content.replace(old_event, new_event)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
