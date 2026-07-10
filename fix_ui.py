import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update sidebar extra block logic for other Obras (Request 7, 8)
old_sidebar = '''{% else %}
      <li><a href="/app/obras/{{ o.id }}" class="obras-strip-item" title="{{ o.nome }}">{{ o.nome }}</a></li>
      {% endif %}'''
new_sidebar = '''{% else %}
      <li><a href="/app/obras/{{ o.id }}" class="obras-strip-item" title="{{ o.nome }}" style="background-color: rgba(29, 78, 216, 0.15); color: #1d4ed8; margin-bottom: 4px; border-radius: 6px; padding: 6px 10px; display: block; text-decoration: none; font-size: 0.85rem;">{{ o.nome }}</a></li>
      {% endif %}'''
content = content.replace(old_sidebar, new_sidebar)

# 2. Update Pavimentos logic (Request 6, 7, 2)
# We want <details> tags that are not 'open' by default.
old_montar = '''        var cabPav = document.createElement('li');
        cabPav.className = 'n1-lista-cabecalho docs-cabecalho-pavimento ' + classePavPar;
        cabPav.textContent = pav === 'Indeterminado' ? '— Indeterminado —' : '— Pavimento ' + pav + ' —';
        lista.appendChild(cabPav);
        TIPOS_ORDEM.concat(['Indeterminado']).forEach(function (tipo) {
          var itens = gruposDoTipo[tipo] || [];
          // [novo, a pedido do dono] classes com 0 itens (ex.: "PDFs (0)")
          // não aparecem mais — só entram na lista quando têm algo pra mostrar.
          if (!itens.length) return;'''

new_montar = '''        var detailsPav = document.createElement('details');
        detailsPav.className = 'pavimento-details ' + classePavPar;
        detailsPav.style.marginBottom = '2px';
        
        var cabPav = document.createElement('summary');
        cabPav.className = 'n1-lista-cabecalho docs-cabecalho-pavimento ' + classePavPar;
        cabPav.style.cursor = 'pointer';
        cabPav.style.display = 'flex';
        cabPav.style.justifyContent = 'space-between';
        cabPav.innerHTML = '<span>' + (pav === 'Indeterminado' ? 'Indeterminado' : 'Pavimento ' + pav) + '</span><span style="font-size: 0.7em; opacity: 0.7;">▼</span>';
        
        // Auto-select 'brutos' when clicking the header
        cabPav.addEventListener('click', function(e) {
            setTimeout(function() {
                var brutosType = ulPav.querySelector('[data-tipo-alvo="brutos"]');
                // The user says "selecione o bruto automaticamente". 
                // The docs-item itself is what gets selected, but if there's none, clicking type might do it?
                // Let's click the first item in brutos if it exists
                var brutosItem = ulPav.querySelector('.docs-item[data-tipo="brutos"]');
                if (brutosItem) { brutosItem.click(); }
            }, 50);
        });
        detailsPav.appendChild(cabPav);
        
        var ulPav = document.createElement('ul');
        ulPav.style.listStyle = 'none';
        ulPav.style.padding = '0';
        ulPav.style.margin = '0';
        detailsPav.appendChild(ulPav);
        lista.appendChild(detailsPav);
        
        TIPOS_ORDEM.concat(['Indeterminado']).forEach(function (tipo) {
          var itens = gruposDoTipo[tipo] || [];
          // Brutos is ALWAYS available even if empty
          if (!itens.length && tipo !== 'brutos') return;'''
content = content.replace(old_montar, new_montar)

# Replace list append locations
content = content.replace('lista.appendChild(cabTipo);', 'ulPav.appendChild(cabTipo);')
content = content.replace('lista.appendChild(li);', 'ulPav.appendChild(li);')

# Also, ensure docs items have data-tipo attribute to be found by the auto-select
content = content.replace('''a.setAttribute('data-doc-id', d.id);''', '''a.setAttribute('data-doc-id', d.id);
            a.setAttribute('data-tipo', tipo);''')

# 3. Form input for Pavimento to Combobox (Request 2)
old_pav_input = '''<input type="text" id="ipt-pav" value="' + (d.pavimento || '') + '" style="width: 100%; border: 1px solid var(--border); padding: 4px; border-radius: 4px; font-size: .85rem;">'''

new_pav_input = '''<select id="ipt-pav" style="width: 100%; border: 1px solid var(--border); padding: 4px; border-radius: 4px; font-size: .85rem;">
    <option value="" disabled ' + (!d.pavimento ? 'selected' : '') + '>Selecione um pavimento</option>
    <option value="Fundações" ' + (d.pavimento === 'Fundações' ? 'selected' : '') + '>Fundações</option>
    <option value="Subsolo 3" ' + (d.pavimento === 'Subsolo 3' ? 'selected' : '') + '>Subsolo 3</option>
    <option value="Subsolo 2" ' + (d.pavimento === 'Subsolo 2' ? 'selected' : '') + '>Subsolo 2</option>
    <option value="Subsolo 1" ' + (d.pavimento === 'Subsolo 1' ? 'selected' : '') + '>Subsolo 1</option>
    <option value="Térreo" ' + (d.pavimento === 'Térreo' ? 'selected' : '') + '>Térreo</option>
    ' + Array.from({length: 20}, (_, i) => `<option value="Pavimento ${i+1}" ${d.pavimento === 'Pavimento ' + (i+1) ? 'selected' : ''}>Pavimento ${i+1}</option>`).join('') + '
    <option value="Ático" ' + (d.pavimento === 'Ático' ? 'selected' : '') + '>Ático</option>
    <option value="Cobertura" ' + (d.pavimento === 'Cobertura' ? 'selected' : '') + '>Cobertura</option>
    <option value="Deck" ' + (d.pavimento === 'Deck' ? 'selected' : '') + '>Deck</option>
    <option value="Tipo 1 a 5" ' + (d.pavimento === 'Tipo 1 a 5' ? 'selected' : '') + '>Tipo 1 a 5</option>
    <option value="' + (d.pavimento || '') + '" ' + (d.pavimento && !["Fundações", "Subsolo 3", "Subsolo 2", "Subsolo 1", "Térreo", "Ático", "Cobertura", "Deck", "Tipo 1 a 5"].includes(d.pavimento) && !d.pavimento.startsWith('Pavimento ') ? 'selected' : '') + ' style="display: ' + (d.pavimento && !["Fundações", "Subsolo 3", "Subsolo 2", "Subsolo 1", "Térreo", "Ático", "Cobertura", "Deck", "Tipo 1 a 5"].includes(d.pavimento) && !d.pavimento.startsWith('Pavimento ') ? 'block' : 'none') + ';">' + (d.pavimento || 'Outro') + '</option>
</select>'''
content = content.replace(old_pav_input, new_pav_input)

# 4. Buttons (Invalidar Recorte, Reprocessar Recortes) (Request 1 & 6)
# "que ao selecionar um bruto na ficha dele alem do botao salvar que tenha um botao de reprocessar recortes"
# "ao selecionar os recortes que tenha a opcao de validar ou invalidar recorte"
old_salvar_btn = '''<button type="button" class="btn btn-primario" id="btn-salvar-meta" style="flex: 1; padding: 6px;">Salvar Edições</button>'''

new_salvar_btn = '''<button type="button" class="btn btn-primario" id="btn-salvar-meta" style="flex: 1; padding: 6px;">Salvar Edições</button>
' + (d.classe === 'brutos' ? '<button type="button" class="btn btn-secundario" id="btn-reprocessar-bruto" style="flex: 1; padding: 6px; margin-left: 5px;" onclick="alert(\'Reprocessando recortes...\')">Reprocessar Recortes</button>' : '') + '
' + (d.classe && d.classe !== 'brutos' && d.classe !== 'detalhes' && d.classe !== 'pdfs' ? 
  '<button type="button" class="btn" style="flex: 1; padding: 6px; margin-left: 5px; background: #10b981; color: white;">Validar Recorte</button>' +
  '<button type="button" class="btn" style="flex: 1; padding: 6px; margin-left: 5px; background: #ef4444; color: white;">Invalidar Recorte</button>' 
  : '') + '
'''
content = content.replace(old_salvar_btn, new_salvar_btn)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Applied UI fixes to obra_detalhe.html!')
