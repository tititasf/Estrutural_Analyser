from pathlib import Path
import difflib
root=Path(r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main')
back=Path(r'D:\Agente-cad-PYSIDE\geometry-review')
def edit(file, fn):
 p=root/file; old=p.read_text(encoding='utf-8'); new=fn(old)
 if old==new: raise RuntimeError('no changes '+file)
 b=back/file; b.parent.mkdir(parents=True,exist_ok=True)
 if not b.exists(): b.write_text(old,encoding='utf-8')
 p.write_text(new,encoding='utf-8',newline='\n')
def rep(s,a,b):
 if s.count(a)!=1: raise RuntimeError('anchor '+a[:100]+' count '+str(s.count(a)))
 return s.replace(a,b)




def template(s):
 s=s.replace('✏️ Criar item no estrutural · desenhe geometria SA','✏️ Criar ou editar item no estrutural')
 lines=s.splitlines(True)
 s=''.join(l for l in lines if 'Invalidar e Regenerar Geometria</button>' not in l)
 s=rep(s,"          '<span id=\"criar-item-seg-wrap\"", "          '<select id=\"criar-item-existente\" aria-label=\"Itens já populados\"><option value=\"\">Itens já populados</option></select>' +\n          '<select id=\"editar-item-segmento\" aria-label=\"Segmento existente\" hidden></select>' +\n          '<span id=\"criar-item-seg-wrap\"")
 s=rep(s,"          '<button type=\"button\" class=\"btn-sec btn\" id=\"btn-criar-item-limpar\">Limpar</button>' +", "          '<button type=\"button\" class=\"btn-sec btn\" id=\"btn-item-redesenhar\" disabled>Redesenhar item</button>' +\n          '<button type=\"button\" class=\"btn-sec btn\" id=\"btn-item-excluir\" disabled>Excluir Item</button>' +\n          '<button type=\"button\" class=\"btn-sec btn\" id=\"btn-segmento-excluir\" hidden disabled>Excluir Segmento</button>' +\n          '<button type=\"button\" class=\"btn-sec btn\" id=\"btn-item-cancelar\" hidden>Cancelar edição</button>' +\n          '<button type=\"button\" class=\"btn-sec btn\" id=\"btn-criar-item-limpar\">Limpar</button>' +")
 s=rep(s,'    window._onPolylineFechada = function (entry) {','    window._onPolylineFechada = function (entry) {\n      if (window.ItemGeometry && window.ItemGeometry.isEditing()) {\n        window._polyGeoms = [entry];\n        return;\n      }')
 s=s.replace('  window.mostrarDetalhe = mostrarDetalhe;','  window.fecharPolylineAtual = fecharPolylineAtual;\n  window.mostrarDetalhe = mostrarDetalhe;')
 s=rep(s,'data-abcd-edit>Editar Campos da Interpretação SA</button>', 'data-abcd-edit>Editar Campos da Interpretação SA</button><button type="button" class="btn btn-sec" data-pillar-interpret>Solicitar interpretação SA deste item</button>')
 s=rep(s,"}).join('') + '</div><div id=\"pillar-n1-subviewer\"></div>';", "}).join('') + '<button type=\"button\" class=\"btn btn-sec\" data-pillar-geometry>Editar geometria N1</button></div><div id=\"pillar-n1-subviewer\"></div>';")
 s += '\n<script src="/static/item_geometry.js?v={{ request.app.state.static_versao | default(\'0\') }}"></script>\n'
 return s
edit('portal/app/templates/obra_detalhe.html',template)
def fv(s):
 s=rep(s,'Renomear fundo de viga</button></div>', 'Renomear fundo de viga</button><button type="button" class="danger" data-fv-delete-beam>Excluir viga</button></div>')
 start=s.index("      '<section class=\"fv-web-table-card\"><div")
 end=s.index("      '<section class=\"fv-web-viewer-card\">",start)
 table=s[start:end]
 title_end=table.index("<div class=\"fv-web-table-scroll\">")
 table="        '<section class=\"fv-web-table-card fv-interpretation-card\">"+table[title_end:]
 s=s[:start]+s[end:]
 anchor="        '<div class=\"fv-web-segtabs\" role=\"tablist\" data-fv-segtabs></div>' +\n"
 s=rep(s,anchor,anchor+table)
 s=rep(s,"      state.segment = String(segment);", "      state.segment = String(segment);\n      root.querySelectorAll('[data-fv-segment], [data-fv-detail]').forEach(function (row) {\n        var key = row.getAttribute('data-fv-segment') || row.getAttribute('data-fv-detail');\n        if (row.hasAttribute('data-fv-segment')) row.hidden = state.segment !== 'todos' && key !== state.segment;\n        else if (state.segment !== 'todos' && key !== state.segment) row.hidden = true;\n      });")
 s=rep(s,"    root.querySelector('[data-fv-rename]').addEventListener('click', renameBeam);", "    root.querySelector('[data-fv-rename]').addEventListener('click', renameBeam);\n    root.querySelector('[data-fv-delete-beam]').addEventListener('click', function () {\n      window.ItemGeometry.delete({classe:'fundo',itemId:data.beam.name,beam:data.beam.name,pavimento:options.pavimento}, true);\n    });")
 # Keep the ficha's existing drawing UI, use the shared persistence API.
 s=rep(s,"api('/obras/' + encodeURIComponent(options.obraId) + '/fv/' + encodeURIComponent(data.beam.name) +\n          '/segmentos/' + encodeURIComponent(state.segment) + querySuffix(), {method: 'DELETE'})", "window.ItemGeometry.remove({classe:'fundo',itemId:segment.id,pavimento:options.pavimento}, false)")
 s=rep(s,"api('/obras/' + encodeURIComponent(options.obraId) + '/fv/' + encodeURIComponent(data.beam.name) +\n          '/segmentos/' + encodeURIComponent(state.segment) + querySuffix(), {\n            method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({points: points})\n          })", "window.ItemGeometry.save({classe:'fundo',itemId:selectedSaSegment().id,pavimento:options.pavimento}, points)")
 return s
edit('portal/app/static/fv_ficha.js',fv)
def lv(s):
 s=rep(s,"        '</div>' +\n        '<div class=\"fv-web-nav\">", "        '<button type=\"button\" class=\"danger\" data-lv-delete-beam>Excluir viga</button></div>' +\n        '<div class=\"fv-web-nav\">")
 s=rep(s,'<button type="button" disabled title="Edição geométrica será conectada ao motor lateral">Editar Segmento</button>', '<button type="button" data-lv-edit '+"' + (!segment ? 'disabled' : '') + '"+'>Editar Segmento</button>')
 s=rep(s,'<button type="button" disabled title="Exclusão será conectada ao motor lateral">Excluir Segmento</button>', '<button type="button" class="danger" data-lv-delete '+"' + (!segment ? 'disabled' : '') + '"+'>Excluir Segmento</button>')
 s=rep(s,'  function bind(root, data, options, state) {','  function bind(root, data, options, state) {\n    function target() {\n      var side = data.sides[state.side];\n      var seg = side.segments.find(function (s) { return String(s.index) === String(state.segment); });\n      return {classe:side.class, itemId:seg && seg.id, beam:data.beam.name, segmento:seg && seg.index, pavimento:options.pavimento};\n    }\n    root.querySelector("[data-lv-delete-beam]").addEventListener("click", function () {\n      var t=target(); t.itemId=data.beam.name; window.ItemGeometry.delete(t, true);\n    });\n    var edit=root.querySelector("[data-lv-edit]"), del=root.querySelector("[data-lv-delete]");\n    if(edit) edit.addEventListener("click", function () { window.ItemGeometry.open(target()); });\n    if(del) del.addEventListener("click", function () { window.ItemGeometry.delete(target(), false); });')
 return s
edit('portal/app/static/lv_ficha.js',lv)
edit('portal/app/static/laje_ficha.js',lambda s:rep(s,"if(editMain)editMain.addEventListener('click',startEdit);", "if(editMain)editMain.addEventListener('click',function(){window.ItemGeometry.open({classe:'lajes',itemId:data.item.id,pavimento:options.pavimento});});"))
def headless(s):
 anchor='        window.process_pillars_action(skip_pre_validation=True)'
 s=rep(s,anchor,'        from portal.app.item_geometry import apply_window as apply_manual_geometry\n        apply_manual_geometry(window, _dados_obras_root() / obra, pavimento)\n'+anchor+'\n        apply_manual_geometry(window, _dados_obras_root() / obra, pavimento)')
 s=rep(s,"        report_stage('merge granular e saneamento N1')", "        apply_manual_geometry(window, _dados_obras_root() / obra, pavimento)\n        report_stage('merge granular e saneamento N1')")
 return s
edit('scripts/arete/headless_sa_analise.py',headless)
print('Patched shared UI, reader and pipeline integration; baselines in',back)
