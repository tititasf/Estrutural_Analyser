import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the Validate/Invalidate buttons
old_btn = '''          ( d.is_virtual_recorte ? '<button type="button" class="btn" id="btn-validar-recorte" style="background:' + (d.validado ? '#ef4444' : '#10b981') + ';color:#fff;border:none;">' + (d.validado ? 'Invalidar Recorte' : 'Validar Recorte') + '</button>' : '' ) +'''
new_btn = '''          ( d.is_virtual_recorte ? 
            '<div style="display:inline-flex; gap: 8px;">' +
              '<button type="button" class="btn" id="btn-validar-recorte" style="background:#10b981;color:#fff;border:none; ' + (d.validado ? 'opacity:0.5;' : '') + '">Validar</button>' +
              '<button type="button" class="btn" id="btn-invalidar-recorte" style="background:#ef4444;color:#fff;border:none; ' + (!d.validado && d.validado !== undefined ? 'opacity:0.5;' : '') + '">Invalidar</button>' +
            '</div>' : '' ) +'''
content = content.replace(old_btn, new_btn)

old_validar_logic = '''          var btnValidar = document.getElementById('btn-validar-recorte');
          if (btnValidar) {
              btnValidar.addEventListener('click', function() {
                  btnValidar.disabled = true;
                  var novoEstado = !d.validado;
                  fetch('/obras/' + OBRA_ID + '/recortes/' + encodeURIComponent(d.bruto_id) + '/' + encodeURIComponent(d.original_item_id) + '/validar', {
                      method: 'POST',
                      headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify({validado: novoEstado})
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
          }'''
new_validar_logic = '''          var btnValidar = document.getElementById('btn-validar-recorte');
          var btnInvalidar = document.getElementById('btn-invalidar-recorte');
          function setValidacao(estado) {
              if(btnValidar) btnValidar.disabled = true;
              if(btnInvalidar) btnInvalidar.disabled = true;
              fetch('/obras/' + OBRA_ID + '/recortes/' + encodeURIComponent(d.bruto_id) + '/' + encodeURIComponent(d.original_item_id) + '/validar', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({validado: estado})
              }).then(r => r.json()).then(j => {
                  if (j.status === 'ok') {
                      d.validado = j.validado;
                      if(btnValidar) btnValidar.style.opacity = d.validado ? '0.5' : '1';
                      if(btnInvalidar) btnInvalidar.style.opacity = (!d.validado) ? '0.5' : '1';
                  }
              }).finally(() => {
                  if(btnValidar) btnValidar.disabled = false;
                  if(btnInvalidar) btnInvalidar.disabled = false;
              });
          }
          if (btnValidar) {
              btnValidar.addEventListener('click', function() { setValidacao(true); });
          }
          if (btnInvalidar) {
              btnInvalidar.addEventListener('click', function() { setValidacao(false); });
          }'''
content = content.replace(old_validar_logic, new_validar_logic)

# 2. Update the Left Panel list building
old_build = '''        var cabPav = document.createElement('li');
        cabPav.className = 'n1-lista-cabecalho docs-cabecalho-pavimento ' + classePavPar;
        cabPav.textContent = pav === 'Indeterminado' ? 'Docs Geral da Obra' : 'Pavimento ' + pav;
        lista.appendChild(cabPav);
        TIPOS_ORDEM.concat(['Indeterminado']).forEach(function (tipo) {
          var itens = gruposDoTipo[tipo] || [];
          // [novo, a pedido do dono] classes com 0 itens (ex.: "PDFs (0)")
          // não aparecem mais — só entram na lista quando têm algo pra mostrar.
          if (!itens.length && tipo !== 'Bruto') return;
          var cabTipo = document.createElement('li');
          cabTipo.className = 'n1-lista-cabecalho docs-cabecalho-tipo docs-drop-alvo ' + classePavPar;
          cabTipo.textContent = (TIPOS_LABEL[tipo] || tipo) + ' (' + itens.length + ')';
          cabTipo.setAttribute('data-pavimento-alvo', pav);
          cabTipo.setAttribute('data-tipo-alvo', tipo);
          cabTipo.addEventListener('dragover', function (e) {
            e.preventDefault();
            cabTipo.classList.add('docs-drop-hover');
          });
          cabTipo.addEventListener('dragleave', function () { cabTipo.classList.remove('docs-drop-hover'); });
          cabTipo.addEventListener('drop', function (e) {
            e.preventDefault();
            cabTipo.classList.remove('docs-drop-hover');
            var docId = e.dataTransfer.getData('text/plain');
            var doc = documentos.find(function (d) { return d.id === docId; });
            if (!doc) return;
            moverDocumento(docId, pav, tipo).then(function (docAtualizado) {
              Object.assign(doc, docAtualizado);
              montarLista();
            }).catch(function () {
              alert('Não foi possível mover o documento.');
            });
          });
          lista.appendChild(cabTipo);
          itens.forEach(function (d) {
            var li = document.createElement('li');
            li.className = classePavPar;
            var a = document.createElement('button');
            a.type = 'button';
            a.className = 'n1-item-link docs-item';
            a.textContent = d.nome_exibicao || d.arquivo_nome;
            a.setAttribute('data-doc-id', d.id);
            a.setAttribute('draggable', 'true');
            a.title = 'Arraste pra outro pavimento/tipo pra corrigir a classificação';
            a.addEventListener('dragstart', function (e) {
              e.dataTransfer.setData('text/plain', d.id);
              e.dataTransfer.effectAllowed = 'move';
            });
            a.addEventListener('click', function () {
              lista.querySelectorAll('.docs-item').forEach(function (x) { x.classList.remove('ativo'); });
              a.classList.add('ativo');
              _docEstado.docId = d.id;
              renderizarDetalhe(d);
              mostrarDetalhe('triagem');
              _docSelecionadoAtual = d;
              // sincronizarRecortesComDocSelecionado();
            });
            li.appendChild(a);
            lista.appendChild(li);
          });
        });'''

new_build = '''        var cabPav = document.createElement('li');
        cabPav.className = 'n1-lista-cabecalho docs-cabecalho-pavimento ' + classePavPar;
        var strPav = pav === 'Indeterminado' ? 'Docs Geral da Obra' : 'Pavimento ' + pav;
        cabPav.innerHTML = '<div style="display:flex; justify-content:space-between; align-items:center; cursor:pointer;" class="pav-header-inner">' +
                           '<span style="flex:1;">' + strPav + '</span>' +
                           '<span class="pav-arrow" style="padding:0 5px;">▼</span>' +
                           '</div>';
        lista.appendChild(cabPav);

        var subLista = document.createElement('ul');
        subLista.style.listStyle = 'none';
        subLista.style.padding = '0';
        subLista.style.margin = '0';
        lista.appendChild(subLista);

        cabPav.addEventListener('click', function(e) {
            if (e.target.classList.contains('pav-arrow')) {
                if (subLista.style.display === 'none') {
                    subLista.style.display = 'block';
                    cabPav.querySelector('.pav-arrow').textContent = '▼';
                } else {
                    subLista.style.display = 'none';
                    cabPav.querySelector('.pav-arrow').textContent = '▶';
                }
                return;
            }
            
            // Auto-selecionar o Bruto ao clicar no nome
            var itensBrutos = gruposDoTipo['Bruto'] || [];
            if (itensBrutos.length > 0) {
                var btn = subLista.querySelector('button[data-doc-id="'+itensBrutos[0].id+'"]');
                if (btn) btn.click();
            } else {
                // Se não tem bruto, clica no primeiro doc qualquer desse pavimento
                var botoes = subLista.querySelectorAll('button[data-doc-id]');
                if (botoes.length > 0) botoes[0].click();
            }
        });

        TIPOS_ORDEM.concat(['Indeterminado']).forEach(function (tipo) {
          var itens = gruposDoTipo[tipo] || [];
          if (!itens.length && tipo !== 'Bruto') return;
          var cabTipo = document.createElement('li');
          cabTipo.className = 'n1-lista-cabecalho docs-cabecalho-tipo docs-drop-alvo ' + classePavPar;
          cabTipo.textContent = (TIPOS_LABEL[tipo] || tipo) + ' (' + itens.length + ')';
          cabTipo.setAttribute('data-pavimento-alvo', pav);
          cabTipo.setAttribute('data-tipo-alvo', tipo);
          cabTipo.addEventListener('dragover', function (e) {
            e.preventDefault();
            cabTipo.classList.add('docs-drop-hover');
          });
          cabTipo.addEventListener('dragleave', function () { cabTipo.classList.remove('docs-drop-hover'); });
          cabTipo.addEventListener('drop', function (e) {
            e.preventDefault();
            cabTipo.classList.remove('docs-drop-hover');
            var docId = e.dataTransfer.getData('text/plain');
            var doc = documentos.find(function (d) { return d.id === docId; });
            if (!doc) return;
            moverDocumento(docId, pav, tipo).then(function (docAtualizado) {
              Object.assign(doc, docAtualizado);
              montarLista();
            }).catch(function () {
              alert('Não foi possível mover o documento.');
            });
          });
          subLista.appendChild(cabTipo);
          itens.forEach(function (d) {
            var li = document.createElement('li');
            li.className = classePavPar;
            var a = document.createElement('button');
            a.type = 'button';
            a.className = 'n1-item-link docs-item';
            a.textContent = d.nome_exibicao || d.arquivo_nome;
            a.setAttribute('data-doc-id', d.id);
            a.setAttribute('draggable', 'true');
            a.title = 'Arraste pra outro pavimento/tipo pra corrigir a classificação';
            a.addEventListener('dragstart', function (e) {
              e.dataTransfer.setData('text/plain', d.id);
              e.dataTransfer.effectAllowed = 'move';
            });
            a.addEventListener('click', function () {
              lista.querySelectorAll('.docs-item').forEach(function (x) { x.classList.remove('ativo'); });
              a.classList.add('ativo');
              _docEstado.docId = d.id;
              renderizarDetalhe(d);
              mostrarDetalhe('triagem');
              _docSelecionadoAtual = d;
            });
            li.appendChild(a);
            subLista.appendChild(li);
          });
        });'''

content = content.replace(old_build, new_build)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
