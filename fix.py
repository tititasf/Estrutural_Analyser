import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
path = r'D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\portal\app\templates\obra_detalhe.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

sidebar_code = """
{% block sidebar_obras_extra %}
<div class="sidebar-obras-arvore" style="margin-top: 15px;">
  <!-- Obras Section -->
  <h3 style="color: #9ca3af; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.05em; padding: 0 10px;">Obras</h3>
  <ul class="nav-lista" style="padding: 0 10px; margin-bottom: 15px;">
    {% for o in obras_do_membro %}
      <li>
        <a href="/app/obras/{{ o.id }}" 
           class="obras-strip-item {% if o.id == obra.id %}ativo{% endif %}" 
           style="background-color: {% if o.id == obra.id %}#1d4ed8{% else %}rgba(29, 78, 216, 0.15){% endif %}; color: {% if o.id == obra.id %}#fff{% else %}#1d4ed8{% endif %}; margin-bottom: 4px; border-radius: 6px; padding: 6px 10px; display: block; text-decoration: none; font-size: 0.85rem;">
          {{ o.nome }}
        </a>
      </li>
    {% endfor %}
  </ul>

  <!-- Pavimentos Section -->
  <h3 style="color: #9ca3af; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.05em; padding: 0 10px;">Pavimentos</h3>
  {% set pavimentos = {} %}
  
  {% for d in documentos %}
      {% set pav = d.pavimento or 'Geral' %}
      {% if pav not in pavimentos %}
          {% set _ = pavimentos.update({pav: {}}) %}
      {% endif %}
      
      {% set cls = d.classe or 'Sem Classe' %}
      {% if cls not in pavimentos[pav] %}
          {% set _ = pavimentos[pav].update({cls: []}) %}
      {% endif %}
      
      {% set _ = pavimentos[pav][cls].append(d) %}
  {% endfor %}

  {% for pav, classes in pavimentos.items() %}
      {% if 'brutos' not in classes %}
          {% set _ = classes.update({'brutos': []}) %}
      {% endif %}
      
      <details class="pavimento-details" style="margin-bottom: 5px; background: rgba(255,255,255,0.05); border-radius: 4px; margin: 0 10px 5px 10px;">
          <summary style="cursor: pointer; padding: 6px 10px; color: white; display: flex; justify-content: space-between; align-items: center;" 
                   onclick="const br = this.parentElement.querySelector('a[data-cls=\'brutos\']'); if(br) br.click();">
              <span style="font-size: 0.85rem; font-weight: 500;">{{ pav }}</span>
              <span style="font-size: 0.7rem; opacity: 0.7;">▼</span>
          </summary>
          <ul class="nav-lista classe-lista" style="padding: 5px 10px; padding-top: 0; margin: 0;">
              {% for cls, docs in classes.items() %}
              <li>
                  <a href="#" class="classe-link" data-pav="{{ pav }}" data-cls="{{ cls }}" 
                     style="display: flex; justify-content: space-between; font-size: 0.8rem; padding: 4px 6px; border-radius: 4px; color: #d1d5db; text-decoration: none; margin-bottom: 2px; background: {% if cls == 'brutos' %}rgba(0,0,0,0.3){% else %}rgba(0,0,0,0.15){% endif %};">
                      {{ cls }}
                      <span class="badge" style="background: rgba(255,255,255,0.1); padding: 1px 5px; border-radius: 10px; font-size: 0.7rem; min-width: 15px; text-align: center;">{{ docs|length }}</span>
                  </a>
              </li>
              {% endfor %}
          </ul>
      </details>
  {% else %}
      <p class="muted" style="padding: 0 10px; font-size: 0.85rem;">Nenhum arquivo nesta obra.</p>
  {% endfor %}
</div>
{% endblock %}
"""

insert_pos = content.find('{% block conteudo %}')
if insert_pos == -1:
    print("Could not find block conteudo")
    sys.exit(1)

new_content = content[:insert_pos] + sidebar_code + '\n' + content[insert_pos:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print('Done injecting sidebar')
