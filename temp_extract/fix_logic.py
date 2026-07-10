import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# I will replace the previously inserted `fetch_logic` with a fixed one.
# First, let's find the current logic.
current_logic_regex = r"function montarLista\(\) \{.*?\n      function _buildListaHtml\(\) \{"
new_logic = """function montarLista() {
      if (typeof OBRA_ID === 'undefined') return;
      
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
           documentos = documentos.filter(function(d) { return !d.is_virtual_recorte; });
           var vistos = {};
           
           recortesBrutos.forEach(function(rb) {
               // Fix: some brutos might not have a linked document if names mismatched, but they might have the floor in the name?
               // Regardless, we use rb.bruto.pavimento. 
               var pav = rb.bruto.pavimento || 'Indeterminado';
               
               rb.itens.forEach(function(it) {
                   if (vistos[it.item_id]) return;
                   vistos[it.item_id] = true;
                   
                   var tipo = 'Recortes Torres Limpas';
                   if (it.titulo.toLowerCase().indexOf('detalhe') >= 0 || it.titulo.toLowerCase().indexOf('convencao') >= 0 || it.titulo.toLowerCase().indexOf('convenção') >= 0) {
                       tipo = 'Recortes Detalhes e Convencoes';
                   }
                   
                   // Inherit floor name in the title
                   var suffix = (pav !== 'Indeterminado' ? ' - ' + pav : '');
                   var novoTitulo = it.titulo.indexOf(suffix) === -1 ? it.titulo + suffix : it.titulo;
                   
                   documentos.push({
                       id: it.item_id,
                       arquivo_nome: novoTitulo,
                       nome_exibicao: novoTitulo,
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
    
    function _buildListaHtml() {"""

content = re.sub(current_logic_regex, new_logic.replace('\\', '\\\\'), content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
