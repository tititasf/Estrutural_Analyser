path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Always show 'Bruto' class even if empty
old_if_length = '''            // não aparecem mais — só entram na lista quando têm algo pra mostrar.
            if (!itens.length) return;
            var cabTipo = document.createElement('li');'''
new_if_length = '''            // não aparecem mais — só entram na lista quando têm algo pra mostrar.
            if (!itens.length && tipo !== 'Bruto') return;
            var cabTipo = document.createElement('li');'''
content = content.replace(old_if_length, new_if_length)

# 2. Change Pavimento input to a combobox logic in renderizarDetalhe
old_pav_html = '''            '</select></label>' +
            '<label>Pavimento<input type="text" id="docs-det-pavimento" value="' + pavAtual.replace(/"/g, '&quot;') +
              '" placeholder="ex.: 13_PAV"></label>' +
            '<label>Classe estrutural<select id="docs-det-classe">' +'''

new_pav_html = '''            '</select></label>' +
            '<label>Pavimento' +
            (function() {
                var grupos = agrupar(documentos);
                var pavReais = ordenarPavimentos(Object.keys(grupos).filter(function (p) { return p !== 'Indeterminado' && p !== 'Docs Geral da Obra'; }));
                var predefinidos = ["Fundacao", "3 Subsolo", "2 Subsolo", "1 Subsolo", "Terreo"];
                for(var i=1; i<=20; i++) predefinidos.push(i + " Pavimento");
                predefinidos.push("Cobertura", "Deck");
                
                var opcoesPav = [];
                pavReais.forEach(function(p) { opcoesPav.push(p); });
                predefinidos.forEach(function(p) { if(opcoesPav.indexOf(p) === -1) opcoesPav.push(p); });
                
                var selectHtml = \'<select id="docs-det-pavimento" class="form-control" style="width:100%; margin-top:4px;">\';
                if (opcoesPav.indexOf(pavAtual) === -1 && pavAtual) {
                    selectHtml += \'<option value="\' + pavAtual.replace(/"/g, \'&quot;\') + \'" selected>\' + pavAtual + \'</option>\';
                }
                if (!pavAtual) {
                    selectHtml += \'<option value="" selected>-- Selecione --</option>\';
                }
                opcoesPav.forEach(function(p) {
                    selectHtml += \'<option value="\' + p + \'"\' + (p === pavAtual ? \' selected\' : \'\') + \'>\' + p + \'</option>\';
                });
                selectHtml += \'<option value="__NOVO__" style="font-weight:bold; color:#3b82f6;">+ Criar Novo Pavimento...</option>\';
                selectHtml += \'<option value="__TIPO__" style="font-weight:bold; color:#8b5cf6;">+ Criar Pavimento Tipo (Intervalo)...</option>\';
                selectHtml += \'</select>\';
                return selectHtml;
            })() +
            '</label>' +
            '<label>Classe estrutural<select id="docs-det-classe">' +'''
content = content.replace(old_pav_html, new_pav_html)

# 3. Add the event listener for the new select
old_save_event = '''      document.getElementById('docs-det-salvar').addEventListener('click', function () {'''
new_save_event = '''      var selectPav = document.getElementById('docs-det-pavimento');
      if (selectPav) {
          selectPav.addEventListener('change', function(e) {
              if (e.target.value === '__NOVO__') {
                  var p = prompt("Digite o nome do novo pavimento (ex: Mezanino):");
                  if (p && p.trim()) {
                      p = p.trim();
                      var opt = new Option(p, p, true, true);
                      e.target.add(opt, e.target.options[e.target.options.length - 2]);
                      e.target.value = p;
                  } else {
                      e.target.value = pavAtual || '';
                  }
              } else if (e.target.value === '__TIPO__') {
                  var inicio = prompt("Do pavimento (ex: 3):");
                  if (inicio) {
                      var fim = prompt("Ao pavimento (ex: 15):");
                      if (fim) {
                          var p = "Tipo (" + inicio.trim() + " ao " + fim.trim() + " Pavimento)";
                          var opt = new Option(p, p, true, true);
                          e.target.add(opt, e.target.options[e.target.options.length - 2]);
                          e.target.value = p;
                      } else { e.target.value = pavAtual || ''; }
                  } else { e.target.value = pavAtual || ''; }
              }
          });
      }

      document.getElementById('docs-det-salvar').addEventListener('click', function () {'''
content = content.replace(old_save_event, new_save_event)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
