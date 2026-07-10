import re
import os

path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove Recortes from painel-2
content = re.sub(r'<div class="painel2-secao">\s*<div class="painel2-secao-titulo">\s*Recortes.*?<div id="recortes-viewer" data-obra="\{\{ obra\.id \}\}"></div>\s*</div>', '', content, flags=re.DOTALL)

# 2. Remove Recortes detail panel
content = re.sub(r'\{\# ============================== RECORTES \(detalhe\) ============================== \#\}.*?<div class="conteudo-secao" id="detalhe-recortes" hidden>\s*<div id="recortes-detalhe-painel" class="n1-detalhe"></div>\s*</div>', '', content, flags=re.DOTALL)

# 3. Update TIPOS_ORDEM
content = content.replace("var TIPOS_ORDEM = ['Bruto', 'Detalhe', 'PDF', 'Outro'];", "var TIPOS_ORDEM = ['Bruto', 'Recortes Torres Limpas', 'Recortes Detalhes e Convencoes', 'Detalhe', 'PDF', 'Outro'];")
content = content.replace("var TIPOS_LABEL = { Bruto: 'Brutos', Detalhe: 'Detalhes', PDF: 'PDFs', Outro: 'Outros' };", "var TIPOS_LABEL = { Bruto: 'Brutos', Detalhe: 'Detalhes', PDF: 'PDFs', Outro: 'Outros', 'Recortes Torres Limpas': 'Recortes Torres Limpas', 'Recortes Detalhes e Convencoes': 'Recortes Detalhes e Convencoes' };")

# 4. Change Indeterminado positioning and label
content = content.replace("var pavimentosReais = ordenarPavimentos(Object.keys(grupos).filter(function (p) { return p !== 'Indeterminado'; }));\n      var pavimentos = pavimentosReais.concat(['Indeterminado']);", "var pavimentosReais = ordenarPavimentos(Object.keys(grupos).filter(function (p) { return p !== 'Indeterminado'; }));\n      var pavimentos = ['Indeterminado'].concat(pavimentosReais);")
content = content.replace("cabPav.textContent = pav === 'Indeterminado' ? '— Indeterminado —' : '— Pavimento ' + pav + ' —';", "cabPav.textContent = pav === 'Indeterminado' ? 'Docs Geral da Obra' : 'Pavimento ' + pav;")

# 5. Add Recortes fetching and injection logic to montarLista
# Replace `montarLista()` function body
fetch_logic = """
    function montarLista() {
      if (typeof OBRA_ID === 'undefined') return;
      
      // if recortes is done (or might be done), let's fetch them first, then build list
      var btnRodar = document.getElementById('btn-rodar-triagem');
      // Just check if we can fetch recortes brutos
      fetch('/obras/' + OBRA_ID + '/recortes/brutos').then(function (r) { return r.ok ? r.json() : {brutos: []}; })
        .then(function (data) {
           var promises = [];
           var brutos = data.brutos || [];
           brutos.forEach(function(b) {
               promises.push(fetch('/obras/' + OBRA_ID + '/recortes/brutos/' + encodeURIComponent(b.bruto_id) + '/itens').then(r => r.ok ? r.json() : {itens: []}).then(function(idata) {
                   return {bruto: b, itens: idata.itens || []};
               }));
           });
           return Promise.all(promises);
        })
        .catch(function() { return []; })
        .then(function(recortesBrutos) {
           // Inject recortes into 'documentos' as virtual items so they group properly
           // First remove any previously injected virtual recortes to avoid duplication
           documentos = documentos.filter(function(d) { return !d.is_virtual_recorte; });
           
           recortesBrutos.forEach(function(rb) {
               var pav = rb.bruto.pavimento_sugerido || rb.bruto.pavimento_confirmado || 'Indeterminado';
               rb.itens.forEach(function(it) {
                   var tipo = 'Recortes Torres Limpas';
                   if (it.titulo.toLowerCase().indexOf('detalhe') >= 0 || it.titulo.toLowerCase().indexOf('convencao') >= 0 || it.titulo.toLowerCase().indexOf('convenção') >= 0) {
                       tipo = 'Recortes Detalhes e Convencoes';
                   }
                   documentos.push({
                       id: it.item_id,
                       arquivo_nome: it.titulo,
                       nome_exibicao: it.titulo,
                       status: 'classificado',
                       created_at: '',
                       pavimento_sugerido: pav,
                       tipo_documento_sugerido: tipo,
                       is_virtual_recorte: true,
                       is_torre_limpa: tipo === 'Recortes Torres Limpas',
                       bruto_id: rb.bruto.bruto_id
                   });
               });
           });
           
           _buildListaHtml();
        });
    }
    
    function _buildListaHtml() {
"""

content = content.replace("function montarLista() {", fetch_logic)
content = content.replace("    montarLista();\n  })();", "    _buildListaHtml(); // Initial build, then replaced by fetch\n    montarLista();\n  })();")


# Update the viewer appending logic in `renderizarDetalhe`
viewer_append = """
        '<div style="margin-top:10px;display:flex;gap:8px;align-items:center">' +
          '<button type="button" class="btn" id="docs-det-salvar">Salvar</button>' +
          '<span id="docs-det-resultado" class="meta" role="status" aria-live="polite"></span>' +
        '</div>' + 
        '<div id="item-viewer-container" style="margin-top:20px;"></div>';
"""
content = content.replace("""        '<div style="margin-top:10px;display:flex;gap:8px;align-items:center">' +
          '<button type="button" class="btn" id="docs-det-salvar">Salvar</button>' +
          '<span id="docs-det-resultado" class="meta" role="status" aria-live="polite"></span>' +
        '</div>';""", viewer_append)

load_viewer_js = """
      document.getElementById('docs-det-salvar').addEventListener('click', function () {
"""
load_viewer_js_replacement = """
      // Load viewer based on format
      var viewerContainer = document.getElementById('item-viewer-container');
      viewerContainer.innerHTML = '<p class="muted">Carregando visualização...</p>';
      
      if (d.is_virtual_recorte) {
          // Fetch the N1/SA photo for this recorte (usually available via N1 endpoint)
          // Wait, they are just items, we can hit the N1 item endpoint if we know the class
          // But it's easier to just fetch it directly or if it's already an image.
          // Actually, we can fetch `/obras/OBRA_ID/n1/CLASSE/ITEM_ID` but we don't have CLASSE.
          // Let's hit the same endpoint `selecionarRecorteFoto` uses if it exists.
          fetch('/obras/' + OBRA_ID + '/n1/qualquer/' + encodeURIComponent(d.id)).then(r => r.json()).then(item => {
              if (item.foto_n1 || item.foto_n3) {
                  var foto = item.foto_n1 || item.foto_n3;
                  viewerContainer.innerHTML = '<div class="n1-foto-card"><div class="zoom-pan-viewport">' + foto + '</div><p class="zoom-pan-dica">Scroll pra zoom, arraste pra navegar, duplo-clique reseta</p></div>';
                  ativarZoomEmContainer(viewerContainer);
              } else {
                  viewerContainer.innerHTML = '<p class="muted">Imagem não disponível.</p>';
              }
          }).catch(e => {
              viewerContainer.innerHTML = '<p class="muted">Erro ao carregar imagem.</p>';
          });
      } else if (formato === 'PDF') {
          viewerContainer.innerHTML = '<iframe src="/obras/' + OBRA_ID + '/documentos/' + d.id + '/download" style="width:100%; height:60vh; border:1px solid #d1d5db; border-radius:8px;"></iframe>';
      } else if (formato === 'DWG' || formato === 'DXF') {
          // fetch preview if available
          viewerContainer.innerHTML = '<img src="/obras/' + OBRA_ID + '/documentos/' + d.id + '/preview" style="max-width:100%; border-radius:8px; border:1px solid #d1d5db;" onerror="this.outerHTML=\\'<p class=\\\\\\'muted\\\\\\'>Preview indisponível</p>\\'"/>';
      } else if (['PNG', 'JPG', 'JPEG'].includes(formato)) {
          viewerContainer.innerHTML = '<div class="zoom-pan-viewport"><img src="/obras/' + OBRA_ID + '/documentos/' + d.id + '/download" style="max-width:100%; border-radius:8px; border:1px solid #d1d5db;"/></div>';
          ativarZoomEmContainer(viewerContainer);
      } else {
          viewerContainer.innerHTML = '<p class="muted">Visualização não suportada para este formato.</p>';
      }

      document.getElementById('docs-det-salvar').addEventListener('click', function () {
"""
content = content.replace(load_viewer_js, load_viewer_js_replacement)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
