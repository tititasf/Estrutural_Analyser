import re
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

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
                
                var selectHtml = '<select id="docs-det-pavimento" class="form-control" style="width:100%; margin-top:4px;">';
                if (opcoesPav.indexOf(pavAtual) === -1 && pavAtual && pavAtual !== 'Indeterminado') {
                    selectHtml += '<option value="' + pavAtual.replace(/"/g, '&quot;') + '" selected>' + pavAtual + '</option>';
                }
                if (!pavAtual || pavAtual === 'Indeterminado') {
                    selectHtml += '<option value="" selected>-- Selecione --</option>';
                }
                opcoesPav.forEach(function(p) {
                    selectHtml += '<option value="' + p + '"' + (p === pavAtual ? ' selected' : '') + '>' + p + '</option>';
                });
                selectHtml += '<option value="__NOVO__" style="font-weight:bold; color:#3b82f6;">+ Criar Novo Pavimento...</option>';
                selectHtml += '<option value="__TIPO__" style="font-weight:bold; color:#8b5cf6;">+ Criar Pavimento Tipo (Intervalo)...</option>';
                selectHtml += '</select>';
                return selectHtml;
            })() +
            '</label>' +
            '<label>Classe estrutural<select id="docs-det-classe">' +'''

content = re.sub(r'\'</select></label>\'\s*\+\s*\'<label>Pavimento<input type="text" id="docs-det-pavimento" value="\' \+ pavAtual\.replace\(/"/g, \'&quot;\'\) \+\s*\'" placeholder="ex\.: 13_PAV"></label>\'\s*\+\s*\'<label>Classe estrutural<select id="docs-det-classe">\' \+', new_pav_html.replace('\\', '\\\\') + " '", content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
