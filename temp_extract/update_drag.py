import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update moverDocumento to send empty string
old_mover = '''    function moverDocumento(docId, pavimentoAlvo, tipoAlvo) {
      var body = {};
      if (pavimentoAlvo !== 'Indeterminado') body.pavimento = pavimentoAlvo;
      if (tipoAlvo !== 'Indeterminado') body.tipo_documento = tipoAlvo;'''
new_mover = '''    function moverDocumento(docId, pavimentoAlvo, tipoAlvo) {
      var body = {
          pavimento: (pavimentoAlvo === 'Indeterminado') ? '' : pavimentoAlvo,
          tipo_documento: (tipoAlvo === 'Indeterminado') ? '' : tipoAlvo
      };'''
content = content.replace(old_mover, new_mover)

# 2. Update agrupar to treat empty string as Indeterminado explicitly
old_agrupar = '''    function agrupar(documentos) {
      var res = {};
      documentos.forEach(function (d) {
        if (d.is_virtual_recorte) return;
        var pav = d.pavimento_confirmado || d.pavimento_sugerido || 'Indeterminado';
        var tipo = d.tipo_documento_confirmado || d.tipo_documento_sugerido || 'Indeterminado';'''
new_agrupar = '''    function agrupar(documentos) {
      var res = {};
      documentos.forEach(function (d) {
        if (d.is_virtual_recorte) return;
        var pav = 'Indeterminado';
        if (d.pavimento_confirmado === "") pav = 'Indeterminado';
        else if (d.pavimento_confirmado) pav = d.pavimento_confirmado;
        else if (d.pavimento_sugerido) pav = d.pavimento_sugerido;
        
        var tipo = 'Indeterminado';
        if (d.tipo_documento_confirmado === "") tipo = 'Indeterminado';
        else if (d.tipo_documento_confirmado) tipo = d.tipo_documento_confirmado;
        else if (d.tipo_documento_sugerido) tipo = d.tipo_documento_sugerido;'''
content = content.replace(old_agrupar, new_agrupar)

# 3. Fix preview for virtual recortes
old_preview = '''      } else if (formato === 'DWG' || formato === 'DXF') {
          // fetch preview if available
          viewerContainer.innerHTML = '<img src="/obras/' + OBRA_ID + '/documentos/' + d.id + '/preview" style="max-width:100%; border-radius:8px; border:1px solid #d1d5db;" onerror="this.outerHTML=\\'<p class=\\\\\\'muted\\\\\\'>Preview indisponvel</p>\\'"/>';'''
new_preview = '''      } else if (formato === 'DWG' || formato === 'DXF') {
          // fetch preview if available
          if (d.is_virtual_recorte) {
              var src = '/obras/' + OBRA_ID + '/recortes/brutos/' + encodeURIComponent(d.bruto_id) + '/' + encodeURIComponent(d.original_item_id) + '/foto';
              viewerContainer.innerHTML = '<img src="' + src + '" style="max-width:100%; border-radius:8px; border:1px solid #d1d5db;" onerror="this.outerHTML=\\'<p class=\\\\\\'muted\\\\\\'>Preview indisponível</p>\\'"/>';
          } else {
              viewerContainer.innerHTML = '<img src="/obras/' + OBRA_ID + '/documentos/' + d.id + '/preview" style="max-width:100%; border-radius:8px; border:1px solid #d1d5db;" onerror="this.outerHTML=\\'<p class=\\\\\\'muted\\\\\\'>Preview indisponível</p>\\'"/>';
          }'''
# Due to the unicode issue with 'indisponvel', it's safer to use regex to replace it
content = re.sub(r'\} else if \(formato === \'DWG\' \|\| formato === \'DXF\'\) \{\s*// fetch preview if available\s*viewerContainer\.innerHTML = \'<img src="/obras/\' \+ OBRA_ID \+ \'/documentos/\' \+ d\.id \+ \'/preview"[^>]+/>\';', new_preview, content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
