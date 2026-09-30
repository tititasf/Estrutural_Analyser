(function () {
  'use strict';

  function esc(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function shown(value) {
    return value === null || value === undefined || value === '' ? '—' : esc(value);
  }

  function api(url, options) {
    return fetch(url, options).then(function (response) {
      return response.json().then(function (body) {
        if (!response.ok) throw new Error(body.detail || ('HTTP ' + response.status));
        return body;
      });
    });
  }

  function cleanSvg(raw) {
    if (!raw) return '';
    var doc = new DOMParser().parseFromString(raw, 'image/svg+xml');
    if (doc.querySelector('parsererror')) return '';
    doc.querySelectorAll('script,foreignObject').forEach(function (node) { node.remove(); });
    doc.querySelectorAll('*').forEach(function (node) {
      Array.prototype.slice.call(node.attributes || []).forEach(function (attr) {
        if (/^on/i.test(attr.name)) node.removeAttribute(attr.name);
        if ((attr.name === 'href' || attr.name === 'xlink:href') && /^javascript:/i.test(attr.value)) node.removeAttribute(attr.name);
      });
    });
    var svg = doc.documentElement;
    svg.removeAttribute('width'); svg.removeAttribute('height');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.classList.add('fv-web-svg');
    return new XMLSerializer().serializeToString(svg);
  }

  function initPanZoom(canvas) {
    var svg = canvas.querySelector('svg');
    if (!svg || !svg.viewBox || !svg.viewBox.baseVal || !svg.viewBox.baseVal.width) return;
    var base = svg.viewBox.baseVal;
    var home = {x: base.x, y: base.y, w: base.width, h: base.height};
    var view = {x: home.x, y: home.y, w: home.w, h: home.h};
    var dragging = false, last = null;
    function apply() { svg.setAttribute('viewBox', [view.x, view.y, view.w, view.h].join(' ')); }
    function reset() { view = {x: home.x, y: home.y, w: home.w, h: home.h}; apply(); }
    function point(event) {
      var rect = svg.getBoundingClientRect();
      return {x: view.x + (event.clientX - rect.left) / rect.width * view.w,
              y: view.y + (event.clientY - rect.top) / rect.height * view.h};
    }
    canvas.addEventListener('wheel', function (event) {
      event.preventDefault();
      var anchor = point(event), factor = event.deltaY < 0 ? .88 : 1.14;
      var width = Math.max(home.w * .01, Math.min(home.w * 8, view.w * factor));
      var height = width * home.h / home.w;
      var rx = (anchor.x - view.x) / view.w, ry = (anchor.y - view.y) / view.h;
      view.x = anchor.x - rx * width; view.y = anchor.y - ry * height;
      view.w = width; view.h = height; apply();
    }, {passive: false});
    canvas.addEventListener('mousedown', function (event) {
      if (event.button !== 0 && event.button !== 1) return;
      event.preventDefault(); dragging = true; last = {x: event.clientX, y: event.clientY};
      canvas.classList.add('dragging');
    });
    window.addEventListener('mousemove', function (event) {
      if (!dragging || !last) return;
      var rect = svg.getBoundingClientRect();
      view.x -= (event.clientX - last.x) / rect.width * view.w;
      view.y -= (event.clientY - last.y) / rect.height * view.h;
      last = {x: event.clientX, y: event.clientY}; apply();
    });
    window.addEventListener('mouseup', function () { dragging = false; last = null; canvas.classList.remove('dragging'); });
    canvas.addEventListener('dblclick', reset);
    var resetButton = canvas.querySelector('[data-lv-reset]');
    if (resetButton) resetButton.addEventListener('click', reset);
  }

  var _torreSvgCache = {};

  /** Busca (e reaproveita) o SVG completo da torre limpa — mesmo artefato do
   * destaque do estrutural limpo. Cacheado por URL: os segmentos de uma
   * mesma viga compartilham a mesma torre, então isso evita refetch a cada
   * clique de aba. */
  function fetchTorreSvg(url) {
    if (_torreSvgCache[url]) return _torreSvgCache[url];
    var promise = fetch(url, {credentials: 'same-origin'}).then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.text();
    }).catch(function (error) { delete _torreSvgCache[url]; throw error; });
    _torreSvgCache[url] = promise;
    return promise;
  }

  /** Recorta (viewBox) a torre limpa em volta do(s) segmento(s) e desenha o
   * destaque + a tag — mesmo padrão visual do destaque agregado do
   * estrutural limpo, só que já enquadrado na viga/segmento certo. */
  var LV_SEGMENT_COLORS = ['#ff5fb2', '#ff9a1f'];  // rosa / laranja (dono 2026-09-28)

  /** "V301 SEG 1" -> ["V301", "SEG 1"], igual ao rótulo do estrutural limpo. */
  function torreLabelLines(label) {
    var s = String(label || '').trim();
    var m = s.match(/^(.*?)\s+(SEG\s*\d+(?:\.\d+)?(?:-[AB])?)\s*$/i);
    return m ? [m[1].trim(), m[2].replace(/\s+/g, ' ').toUpperCase()] : [s];
  }

  /** `viewbox`/`highlights` chegam no espaço px do transform (`framePx`); o
   * SVG da foto tem viewBox próprio (matplotlib emite em pt). Converte
   * px -> unidades do SVG para o destaque cair exatamente onde cai no overlay
   * do estrutural limpo — mesma geometria, mesmo lugar, mesmo rótulo. */
  function composeTorreCard(rawSvgText, viewbox, highlights, framePx) {
    if (!rawSvgText) return '';
    var doc = new DOMParser().parseFromString(rawSvgText, 'image/svg+xml');
    if (doc.querySelector('parsererror')) return '';
    var svg = doc.documentElement;
    svg.querySelectorAll('script,foreignObject').forEach(function (node) { node.remove(); });
    var own = String(svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    var ox = 0, oy = 0, sx = 1, sy = 1;
    if (own.length === 4 && own.every(isFinite) && framePx && framePx[0] > 0 && framePx[1] > 0) {
      ox = own[0]; oy = own[1];
      sx = own[2] / framePx[0]; sy = own[3] / framePx[1];
    }
    function toSvg(p) { return [ox + p[0] * sx, oy + p[1] * sy]; }
    var SVGNS = 'http://www.w3.org/2000/svg';
    var group = doc.createElementNS(SVGNS, 'g');
    group.setAttribute('class', 'lv-torre-highlights');
    var vbW = viewbox && viewbox.length === 4 ? viewbox[2] * sx : 0;
    var fontSize = vbW > 0 ? Math.max(vbW / 42, 1) : 3.25;
    var tagItems = [];
    (highlights || []).forEach(function (item, index) {
      var pts = (item.points || []).map(toSvg);
      if (!pts.length) return;
      // Segmentos alternam rosa / laranja (dono 2026-09-28; antes vermelho /
      // ciano), mesma paleta do destaque de laterais no estrutural limpo.
      var cor = LV_SEGMENT_COLORS[index % LV_SEGMENT_COLORS.length];
      var poly = doc.createElementNS(SVGNS, 'polygon');
      poly.setAttribute('points', pts.map(function (p) { return p[0] + ',' + p[1]; }).join(' '));
      poly.setAttribute('fill', cor);
      poly.setAttribute('fill-opacity', '0.15');
      poly.setAttribute('stroke', cor);
      poly.setAttribute('stroke-width', '6');
      poly.setAttribute('vector-effect', 'non-scaling-stroke');
      group.appendChild(poly);
      // Tag fora das linhas destacadas, com linha-guia na cor do segmento
      // (TagLeader, mesmo algoritmo do estrutural limpo — dono 2026-09-27).
      if (window.TagLeader) {
        tagItems.push({pts: pts, color: cor, lines: torreLabelLines(item.label)});
        return;
      }
      var cx = 0, cy = 0, minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      pts.forEach(function (p) {
        cx += p[0]; cy += p[1];
        minX = Math.min(minX, p[0]); maxX = Math.max(maxX, p[0]);
        minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]);
      });
      cx /= pts.length; cy /= pts.length;
      var text = doc.createElementNS(SVGNS, 'text');
      text.setAttribute('x', cx); text.setAttribute('y', cy);
      text.setAttribute('fill', cor);
      text.setAttribute('font-size', String(fontSize));
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('dominant-baseline', 'middle');
      text.setAttribute('paint-order', 'stroke');
      text.setAttribute('stroke', '#000');
      text.setAttribute('stroke-width', String(fontSize * 0.22));
      if ((maxY - minY) > (maxX - minX) * 1.1) {
        text.setAttribute('transform', 'rotate(-90 ' + cx + ' ' + cy + ')');
      }
      var lines = torreLabelLines(item.label);
      lines.forEach(function (line, index) {
        var span = doc.createElementNS(SVGNS, 'tspan');
        span.setAttribute('x', cx);
        span.setAttribute('dy', index === 0
          ? (lines.length > 1 ? (-0.55 * (lines.length - 1)) + 'em' : '0')
          : '1.15em');
        span.textContent = line;
        text.appendChild(span);
      });
      group.appendChild(text);
    });
    if (tagItems.length) window.TagLeader.place(doc, group, tagItems, {fontSize: fontSize});
    svg.appendChild(group);
    if (viewbox && viewbox.length === 4) {
      var tl = toSvg([viewbox[0], viewbox[1]]);
      svg.setAttribute('viewBox', [tl[0], tl[1], viewbox[2] * sx, viewbox[3] * sy].join(' '));
    }
    svg.removeAttribute('width'); svg.removeAttribute('height');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.classList.add('fv-web-svg');
    return new XMLSerializer().serializeToString(svg);
  }

  function cutTable(cuts, selectedCut) {
    if (!cuts.length) return '<div class="lv-empty-state">Nenhuma visão de corte identificada para esta viga.</div>';
    return '<div class="fv-web-table-scroll lv-cut-scroll"><table class="fv-web-table"><thead><tr>' +
      '<th>Corte</th><th>Laje própria</th><th>Laje vizinha</th><th>Altura da viga</th><th>Confiança</th><th>Status</th>' +
      '</tr></thead><tbody>' + cuts.map(function (cut, index) {
        if (selectedCut !== 'todos' && selectedCut !== index) return '';
        return '<tr class="lv-cut-row ' + (selectedCut === index ? 'selected' : '') + '" data-lv-cut="' + index + '">' +
          '<td>VC' + (index + 1) + '</td><td>' + shown(cut.own_slab) + '</td><td>' + shown(cut.neighbor_slab) + '</td>' +
          '<td>' + shown(cut.beam_height_cm) + '</td><td>' + shown(cut.confidence_percent) + '%</td><td>' + shown(cut.status) + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }

  function openingEditor(segment, side) {
    var rows = (segment.pillar_openings || []).map(function (opening) {
      return '<div class="lv-opening-row" data-lv-opening><input value="' + esc(opening.pillar) + '" placeholder="Pilar" aria-label="Pilar">' +
        '<input type="number" min="0" step="0.1" value="' + esc(opening.position_cm) + '" placeholder="posição" aria-label="Posição em cm">' +
        '<input type="number" min="0.001" step="0.1" value="' + esc(opening.width_cm) + '" placeholder="largura" aria-label="Largura em cm">' +
        '<input type="number" min="0.001" step="0.1" value="' + esc(opening.height_cm) + '" placeholder="altura" aria-label="Altura em cm">' +
        '<button type="button" data-lv-remove-opening aria-label="Remover abertura">×</button></div>';
    }).join('');
    return '<div class="lv-segment-detail"><section class="fv-web-mini"><h5>Aberturas para pilar <small>medidas em cm</small></h5>' +
      '<div data-lv-openings>' + (rows || '<p class="fv-web-empty">Nenhuma abertura cadastrada.</p>') + '</div>' +
      '<div class="fv-segment-detail-actions"><button type="button" data-lv-add-opening>+ Adicionar Abertura para Pilar</button>' +
      '<button type="button" class="success" data-lv-save-openings>Salvar aberturas</button></div></section>' +
      '<section class="fv-web-mini"><h5>Dados do segmento</h5><div class="fv-web-mini-grid">' +
        '<div><span>Lado</span><b>' + esc(side) + '</b></div><div><span>Nível</span><b>' + shown(segment.level) + '</b></div>' +
        '<div><span>Comprimento</span><b>' + shown(segment.length_cm) + ' cm</b></div><div><span>Altura da viga</span><b>' + shown(segment.beam_height_cm) + ' cm</b></div>' +
      '</div></section></div>';
  }

  function segmentRows(segments, selectedIndex, expandedIndex, currentSide, data, state) {
    if (!segments.length) return '<tr><td colspan="10"><div class="lv-empty-state">Nenhum segmento identificado neste lado.</div></td></tr>';
    return segments.map(function (segment) {
      var selected = segment.index === selectedIndex, expanded = segment.index === expandedIndex;
      var slabs = (segment.slabs || []).map(function (slab) {
        return '<div>' + esc(slab.name) + ' · nível ' + shown(slab.level) + '</div>';
      }).join('') || 'Nenhuma identificada';
      var openings = (segment.beam_openings || []).map(function (opening) {
        var missing = !opening.dimension || opening.level === null || opening.level === undefined;
        var warning = missing ? ' <span class="lv-level-warning" title="Dimensão ou nível da viga incidente não confirmado pelo SA" aria-label="Dado de abertura incompleto">⚠</span>' : '';
        var location = opening.location ? ' · ' + esc(opening.location) : '';
        var measures = opening.width_cm !== undefined ? '<small>Esq. ' + shown(opening.distance_left_cm) + ' · largura ' + shown(opening.width_cm) + ' · dir. ' + shown(opening.distance_right_cm) + ' cm</small>' : '';
        return '<div>' + esc(opening.name) + ' · ' + shown(opening.dimension) + location + ' · nível ' + shown(opening.level) + warning + measures + '</div>';
      }).join('') || (segment.beam_openings_status === 'verified' ? 'Não' :
        'SA sem dados <span class="lv-level-warning" title="A rodada SA publicada não forneceu vínculos de abertura deste segmento" aria-label="Aberturas não verificadas">⚠</span>');
      var pillars = (segment.pillar_passages || []).map(function (pillar) {
        return '<div>' + esc(pillar.name) + ' · face ' + esc(pillar.face) + '<small>Esq. ' + shown(pillar.distance_left_cm) + ' · comp. ' + shown(pillar.length_cm) + ' · dir. ' + shown(pillar.distance_right_cm) + ' cm</small></div>';
      }).join('') || 'Não';
      var levelWarning = segment.level_source === 'sa_nearest_same_side_slab' || segment.level_source === 'unresolved';
      var levelTitle = segment.level_source === 'sa_nearest_same_side_slab'
        ? 'Cota inferida da laje mais próxima do mesmo lado (' + shown(segment.level_distance_cm) + ' cm); confira no SA.'
        : 'Cota ainda não resolvida pelo SA.';
      var levelCell = shown(segment.level) + (levelWarning ? ' <span class="lv-level-warning" title="' + esc(levelTitle) + '" aria-label="' + esc(levelTitle) + '">⚠</span>' : '');
      return '<tr class="fv-web-seg-row ' + (selected ? 'selected ' : '') + (expanded ? 'expanded' : '') + '" tabindex="0" data-lv-segment="' + segment.index + '">' +
        '<td class="fv-web-chev">›</td><td>S' + shown(segment.index) + '</td><td>' + shown(segment.length_cm) + '</td>' +
        '<td>' + shown(segment.width_cm) + '</td><td>' + shown(segment.beam_height_cm) + '</td><td>' + levelCell + '</td>' +
        '<td class="lv-list-cell">' + slabs + '</td><td class="lv-list-cell">' + openings + '</td><td class="lv-list-cell">' + pillars + '</td>' +
        '<td><span class="fv-validation-seal ' + (segment.human_validated ? 'valid' : 'pending') + '">' +
          (segment.human_validated ? '✓ Validado' : 'Pendente') + '</span></td></tr>' +
        (expanded ? '<tr class="fv-web-seg-detail"><td colspan="10">' + openingEditor(segment, currentSide) +
          (state.layer === 'n3_panels' ? n3Editor(data, Object.assign({}, state, {segment:segment.index})) : '') +
          '</td></tr>' : '');
    }).join('');
  }

  /** Slots sintéticos da aba "Todos" — não pertencem a nenhum segmento/corte
   * específico, então vivem à parte, um por lado (segmentos) e um global
   * (cortes), preenchidos sob demanda como qualquer camada preguiçosa. */
  function sideTodosStore(data, side) {
    var sideData = data.sides[side];
    if (!sideData._todos) {
      sideData._todos = {
        sa: {available: true, lazy: true, svg: null},
        c1: {available: false, svg: null},
        c2: {available: false, svg: null},
        c3: {available: false, svg: null},
        n3_panels: {available: true, lazy: true, svg: null}
      };
    }
    return sideData._todos;
  }

  function cutTodosStore(data, layer) {
    if (!data._cutTodos) data._cutTodos = {};
    if (!data._cutTodos[layer]) data._cutTodos[layer] = {available: layer === 'n3_cut' || (data.cut_views || []).length > 0, lazy: true, svg: null};
    return data._cutTodos[layer];
  }

  function cutLayers(data, state) {
    var cut = (data.cut_views || [])[state.cut];
    var layers = cut && cut.layers || {};
    return {
      sa_cut: state.cut === 'todos' ? cutTodosStore(data, 'sa_cut') : layers.sa,
      c1: layers.c1, c2: layers.c2, c3: layers.c3,
      n3_cut: state.cut === 'todos' ? cutTodosStore(data, 'n3_cut') : layers.n3_cut
    };
  }

  function layerInfo(data, state) {
    if (state.section === 'cut') return cutLayers(data, state)[state.layer] || null;
    if (state.segment === 'todos') {
      return sideTodosStore(data, state.side)[state.layer] || null;
    }
    var segment = (data.sides[state.side].segments || []).filter(function (item) { return item.index === state.segment; })[0] || null;
    var map = {
      sa: segment && segment.layers.sa,
      c1: segment && segment.layers.c1,
      c2: segment && segment.layers.c2,
      c3: segment && segment.layers.c3,
      n3_panels: segment && segment.layers.n3_panels
    };
    return map[state.layer] || null;
  }

  /** Subabas da camada ativa: segmentos (SA/C1/C2/C3/N3 Painéis) ou cortes
   * (N3 Visão Corte) — cada família tem sua própria contagem e sua própria
   * aba "Todos" (visão consolidada do lado / de todos os cortes). */
  function segTabsHtml(state, segments, cuts) {
    if (state.section === 'cut') {
      return '<button type="button" class="' + (state.cut === 'todos' ? 'active' : '') + '" data-lv-cut-tab="todos">Todos</button>' +
        cuts.map(function (_cut, index) {
          return '<button type="button" class="' + (state.cut === index ? 'active' : '') + '" data-lv-cut-tab="' + index + '">VC' + (index + 1) + '</button>';
        }).join('');
    }
    return '<button type="button" class="' + (state.segment === 'todos' ? 'active' : '') + '" data-lv-segment-tab="todos">Todos</button>' +
      segments.map(function (item) {
        return '<button type="button" class="' + (state.segment === item.index ? 'active' : '') + '" data-lv-segment-tab="' + item.index + '">S' + item.index + '</button>';
      }).join('');
  }

  function layerButton(name, label, info, active) {
    var available = !!(info && info.available);
    return '<button type="button" class="fv-web-layer ' + name + (active ? ' active' : '') + '" data-lv-layer="' + name + '" ' +
      (!available ? 'disabled title="Camada ainda não materializada"' : '') + '><i>' + (name.indexOf('n3') === 0 ? '■' : '●') + '</i>' +
      esc(label) + '<small>' + (info && info.loading ? 'carregando' : (info && info.lazy ? 'sob demanda' : (available ? 'disponível' : 'ausente'))) + '</small></button>';
  }

  function n3View(state) { return state.layer === 'n3_cut' ? 'corte' : 'paineis-' + state.side.toLowerCase(); }

  function n3Editor(data, state) {
    if (state.layer !== 'n3_cut' && state.layer !== 'n3_panels') return '';
    var ficha = data.n3_ficha;
    if (!ficha) return '<section class="lv-n3-editor"><h3>Ficha N3</h3><p>Os contratos N3 desta viga ainda não foram materializados pelo SA.</p></section>';
    var draft = state.n3Draft || ficha;
    var view = n3View(state), sides = state.layer === 'n3_cut' ? ['A','B'] : [state.side];
    var rows = sides.map(function(side){
      var values = draft.sides[side], source = ficha.sides[side];
      var section = state.layer === 'n3_cut' ?
        '<div class="lv-n3-numbers">' + [
          ['total_width','Largura da seção'],['total_height','Altura da face'],['h_section','Altura estrutural']
        ].map(function(spec){return '<label>'+spec[1]+' (cm)<input type="number" min="'+(spec[0]==='h_section'?'0':'0.001')+'" step="0.1" data-lv-n3-side="'+side+'" data-lv-n3-field="'+spec[0]+'" value="'+esc(values[spec[0]])+'"></label>';}).join('')+'</div>' : '';
      var panels = state.layer === 'n3_panels' ? values.panels.map(function(panel,index){
        var original = source.panels[index];
        if (state.segment && state.segment !== 'todos' && Number(original.segment_index) !== Number(state.segment)) return '';
        return '<div class="lv-n3-panel-row"><strong>Painel '+(index+1)+' · S'+shown(original.segment_index)+'</strong>'+
          [['width','Largura'],['height1','Altura 1'],['height2','Altura 2']].map(function(spec){
            return '<label>'+spec[1]+' (cm)<input type="number" min="'+(spec[0]==='width'?'0.001':'0')+'" step="0.1" data-lv-n3-side="'+side+'" data-lv-n3-panel="'+index+'" data-lv-n3-field="'+spec[0]+'" value="'+esc(panel[spec[0]])+'"></label>';
          }).join('')+'</div>';
      }).join('') : '';
      return '<div class="lv-n3-side"><h4>Lado '+side+'</h4>'+section+panels+'</div>';
    }).join('');
    return '<section class="lv-n3-editor"><div><h3>Ficha N3 · '+(state.layer==='n3_cut'?'Visão Corte':'Painéis do Lado '+state.side)+'</h3>'+
      '<p>Edite as medidas e salve antes de regenerar. Cada vista gera um DXF independente.</p></div>'+
      (ficha.stale?'<p class="lv-n3-warning">O SA mudou estes contratos. Confira as medidas e salve para vincular a edição à nova rodada.</p>':'')+
      rows+'<div class="lv-n3-actions"><button type="button" class="success" data-lv-n3-save>Salvar edições manuais</button>'+
      '<button type="button" class="primary" data-lv-n3-regen>Solicitar regeneração N3 '+(view==='corte'?'Visão Corte':'Painéis '+state.side)+'</button></div>'+
      '<div class="lv-n3-status" data-lv-n3-status></div><div class="lv-n3-monitor" data-lv-n3-monitor hidden></div></section>';
  }

  function paintN3(root, data, state) {
    var save=root.querySelector('[data-lv-n3-save]'), regen=root.querySelector('[data-lv-n3-regen]');
    if(!save || !regen)return;
    var view=n3View(state),job=state.regenJobs[view],checking=!!state.regenCheckingViews[view];
    var active=job&&['queued','running','paused'].indexOf(job.estado)>=0;
    save.disabled=(!state.n3Dirty&&!data.n3_ficha.stale)||state.n3Saving;
    save.textContent=state.n3Saving?'Salvando…':'Salvar edições manuais';
    regen.disabled=!!state.n3Saving||checking||!!active||!!data.n3_ficha.stale;
    regen.textContent=active?(job.estado==='queued'?'Regeneração na fila':'Regeneração em andamento'):
      'Solicitar regeneração N3 '+(state.layer==='n3_cut'?'Visão Corte':'Painéis '+state.side);
    var status=root.querySelector('[data-lv-n3-status]');if(status)status.textContent=state.n3Message||(state.n3Dirty?'Alterações não salvas':'');
    var monitor=root.querySelector('[data-lv-n3-monitor]');if(!monitor)return;
    var progress=job&&job.progresso||{},pct=progress.percentual_estimado;
    monitor.innerHTML=checking&&!job?'Consultando a fila…':job?
      '<strong>'+esc(({queued:'Na fila',running:'Regenerando N3',done:'Concluída',error:'Falhou',paused:'Pausada'})[job.estado]||job.estado)+'</strong> '+
      esc(progress.rotulo||'')+(typeof pct==='number'?' · '+pct+'%<i><em style="width:'+Math.max(0,Math.min(100,pct))+'%"></em></i>':'')+
      (job.erro_msg?'<small>'+esc(job.erro_msg)+'</small>':''):
      (state.regenErrors[view]?'<small>'+esc(state.regenErrors[view])+'</small>':'');
    monitor.hidden=!monitor.innerHTML;
  }

  function n3Url(data, options, view, status) {
    return '/obras/'+encodeURIComponent(options.obraId)+'/lv/'+encodeURIComponent(options.behavior)+'/'+encodeURIComponent(data.beam.name)+'/regenerar-n3/'+view+(status?'/status':'')+query(options);
  }

  function saveN3(root,data,options,state) {
    if(!state.n3Dirty&&!data.n3_ficha.stale)return Promise.resolve();
    state.n3Saving=true;state.n3Message='Salvando ficha N3…';paintN3(root,data,state);
    return api('/obras/'+encodeURIComponent(options.obraId)+'/lv/'+encodeURIComponent(options.behavior)+'/'+encodeURIComponent(data.beam.name)+'/n3-ficha'+query(options),{
      method:'PUT',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({source_hash:data.n3_ficha.source_hash,revision:data.n3_ficha.revision,sides:state.n3Draft.sides})
    }).then(function(result){data.n3_ficha=result.ficha;state.n3Draft=JSON.parse(JSON.stringify(result.ficha));state.n3Dirty=false;state.n3Saving=false;state.n3Message='Salvo · revisão '+result.ficha.revision;paintN3(root,data,state);}).catch(function(error){state.n3Saving=false;state.n3Message='Erro ao salvar: '+error.message;paintN3(root,data,state);throw error;});
  }

  function pollN3(root,data,options,state,jobId,view) {
    if(state.regenTimers[view])clearTimeout(state.regenTimers[view]);
    api('/jobs/'+encodeURIComponent(jobId)).then(function(job){
      state.regenCheckingViews[view]=false;state.regenErrors[view]='';state.regenJobs[view]=job;paintN3(root,data,state);
      if(['queued','running','paused'].indexOf(job.estado)>=0)state.regenTimers[view]=setTimeout(function(){pollN3(root,data,options,state,jobId,view);},2500);
      else if(job.estado==='done'&&state.regenRefreshOnDone[view]===jobId&&n3View(state)===view&&root.querySelector('.lv-web-ficha')){
        state.regenRefreshOnDone[view]=null;
        load(root,Object.assign({},options,{beam:data.beam.name,initialSide:state.side,initialSegment:state.segment,initialLayer:state.layer}));
      }
    }).catch(function(error){state.regenCheckingViews[view]=false;state.regenErrors[view]=error.message;paintN3(root,data,state);if(state.regenJobs[view]&&['queued','running','paused'].indexOf(state.regenJobs[view].estado)>=0)state.regenTimers[view]=setTimeout(function(){pollN3(root,data,options,state,jobId,view);},4000);});
  }

  function discoverN3(root,data,options,state) {
    var view=n3View(state);if(!data.n3_ficha||state.discoveredN3[view])return;
    state.discoveredN3[view]=true;state.regenCheckingViews[view]=true;paintN3(root,data,state);
    api(n3Url(data,options,view,true)).then(function(result){state.regenCheckingViews[view]=false;if(result.job_id)pollN3(root,data,options,state,result.job_id,view);else paintN3(root,data,state);}).catch(function(error){state.regenCheckingViews[view]=false;state.regenErrors[view]=error.message;paintN3(root,data,state);});
  }

  function requestN3(root,data,options,state) {
    var view=n3View(state);
    if(state.regenCheckingViews[view]||state.n3Saving)return;
    var chooser=window.escolherModoDesenho?window.escolherModoDesenho({currentMode:options.visualMode||'NOVA',description:'Escolha o estilo para regenerar somente esta vista N3 da lateral.'}):Promise.resolve('NOVA');
    chooser.then(function(mode){if(!mode)return null;return saveN3(root,data,options,state).then(function(){state.regenCheckingViews[view]=true;state.regenErrors[view]='';paintN3(root,data,state);return api(n3Url(data,options,view),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({visual_mode:mode})}).then(function(result){options.visualMode=mode;if(window.atualizarModoDesenhoUrl)window.atualizarModoDesenhoUrl(mode);return result;});});}).then(function(result){if(!result)return;state.regenRefreshOnDone[view]=result.job_id;pollN3(root,data,options,state,result.job_id,view);}).catch(function(error){state.regenCheckingViews[view]=false;state.regenErrors[view]=error.message;paintN3(root,data,state);});
  }

  function ensureActiveLayer(root, data, options, state) {
    var info = layerInfo(data, state);
    if (!info || !info.lazy || info.loading) return;
    info.loading = true;
    var params = query(options);
    // segment_index<=0 e cut_index<0 são os sentinelas da aba "Todos" no backend.
    var segmentIndex = state.segment === 'todos' ? 0 : (state.segment || 1);
    var cutIndex = state.cut === 'todos' ? -1 : (state.cut || 0);
    params += (params ? '&' : '?') + 'visual_mode=' + encodeURIComponent(options.visualMode||'NOVA') +
      '&side=' + encodeURIComponent(state.side) +
      '&segment_index=' + encodeURIComponent(segmentIndex) + '&cut_index=' + encodeURIComponent(cutIndex);
    api('/obras/' + encodeURIComponent(options.obraId) + '/lv/' + encodeURIComponent(options.behavior) + '/' +
      encodeURIComponent(data.beam.name) + '/camada/' + encodeURIComponent(state.layer) + params)
      .then(function (payload) {
        info.loading = false; info.lazy = false; info.available = !!payload.available;
        if (payload.mode === 'torre_context' && payload.available) {
          fetchTorreSvg(payload.svg_url).then(function (rawSvg) {
            info.svg = composeTorreCard(rawSvg, payload.viewbox, payload.highlights, payload.frame_px) || null;
            info.available = !!info.svg;
            if (layerInfo(data, state) === info) render(root, data, options, state);
          }).catch(function () {
            info.svg = null; info.available = false;
            if (layerInfo(data, state) === info) render(root, data, options, state);
          });
          return;
        }
        info.svg = payload.svg || null;
        if (layerInfo(data, state) === info) render(root, data, options, state);
      }).catch(function (error) {
        info.loading = false; info.lazy = false; info.available = false; info.error = error.message;
        if (layerInfo(data, state) === info) render(root, data, options, state);
      });
  }

  function render(root, data, options, state) {
    var sideData = data.sides[state.side], segments = sideData.segments || [];
    if (state.segment !== 'todos' && !segments.some(function (item) { return item.index === state.segment; })) {
      state.segment = segments.length ? segments[0].index : null;
    }
    var segment = state.segment === 'todos' ? null : segments.filter(function (item) { return item.index === state.segment; })[0] || null;
    var cuts = data.cut_views || [];
    if (!cuts.length && data.n3_ficha) state.cut = 'todos';
    if (state.cut !== 'todos' && state.cut >= cuts.length) state.cut = 0;
    var todosLado = sideTodosStore(data, state.side);
    var layerMap = state.segment === 'todos' ? todosLado : {
      sa: segment && segment.layers.sa, c1: segment && segment.layers.c1,
      c2: segment && segment.layers.c2, c3: segment && segment.layers.c3,
      n3_panels: segment && segment.layers.n3_panels
    };
    if (state.section === 'cut') layerMap = cutLayers(data, state);
    if (data.n3_ficha && layerMap.n3_cut && !layerMap.n3_cut.available) {
      layerMap.n3_cut.available = true;
      layerMap.n3_cut.lazy = true;
    }
    if (data.n3_ficha && layerMap.n3_panels && !layerMap.n3_panels.available) {
      layerMap.n3_panels.available = true;
      layerMap.n3_panels.lazy = true;
    }
    if (!layerMap[state.layer] || !layerMap[state.layer].available) {
      state.layer = (state.section === 'cut' ? ['sa_cut', 'n3_cut'] : ['sa', 'n3_panels']).filter(function (name) { return layerMap[name] && layerMap[name].available; })[0] || (state.section === 'cut' ? 'sa_cut' : 'sa');
    }
    var total = (data.sides.A.segments || []).length + (data.sides.B.segments || []).length;
    var visibleSegments = state.segment === 'todos' ? segments : segments.filter(function (item) {
      return item.index === state.segment;
    });
    var behaviorLabel = esc(data.beam.behavior_label).replace(/\b(passam|param)\b/i, '<strong>$1</strong>');
    var interpretation = state.section === 'cut'
      ? '<section class="fv-web-table-card lv-cut-card lv-interpretation-card" aria-label="Interpretação das visões de corte">' +
          cutTable(cuts, state.cut) + '</section>'
      : '<section class="fv-web-table-card lv-interpretation-card" aria-label="Interpretação dos segmentos · Lado ' + state.side + '">' +
          '<div class="fv-web-table-scroll"><table class="fv-web-table"><thead><tr><th></th><th>Seg.</th><th>Comprimento</th><th>Largura</th>' +
          '<th>Altura da viga</th><th>Nível da lateral</th><th>Lajes</th><th>Possui aberturas?</th><th>Passa por pilares?</th><th>Selo validação</th></tr></thead><tbody>' +
          segmentRows(visibleSegments, state.segment, state.expanded, state.side, data, state) + '</tbody></table></div></section>';
    root.innerHTML = '<article class="fv-web-ficha lv-web-ficha">' +
      '<header class="fv-web-head"><div><p class="fv-web-kicker">Lateral de viga · ficha HI-FI</p><div class="lv-name-line"><h2>' + esc(data.beam.name) + '</h2>' +
        '<span class="lv-behavior-tag"><b>Comportamento:</b> ' + behaviorLabel + '</span></div>' +
        '<span>' + total + ' segmento(s) · A: ' + data.sides.A.segments.length + ' · B: ' + data.sides.B.segments.length + '</span>' +
        '</div>' +
        '<div class="fv-web-nav"><button type="button" data-lv-beam="' + esc(data.beam.previous || '') + '" ' + (!data.beam.previous ? 'disabled' : '') + '>←</button>' +
        '<b>' + data.beam.position + '/' + data.beam.total_beams + '</b><button type="button" data-lv-beam="' + esc(data.beam.next || '') + '" ' + (!data.beam.next ? 'disabled' : '') + '>→</button></div></header>' +
      '<section class="fv-web-viewer-card">' +
      '<nav class="lv-side-tabs fv-web-layerbar" role="tablist" aria-label="Lados da lateral de viga">' + ['A','B'].map(function (side) {
        return '<button type="button" role="tab" aria-selected="' + (state.section !== 'cut' && state.side === side) + '" class="fv-web-layer lv-side-tab ' + (state.section !== 'cut' && state.side === side ? 'active' : '') + '" data-lv-side="' + side + '">' +
          '<i aria-hidden="true">■</i><span>Lado ' + side + '</span><small>' + data.sides[side].segments.length + ' segmento(s)</small></button>';
      }).join('') + '<button type="button" role="tab" aria-selected="' + (state.section === 'cut') + '" class="fv-web-layer lv-side-tab ' + (state.section === 'cut' ? 'active' : '') + '" data-lv-view="cut"><i aria-hidden="true">■</i><span>Visão Corte</span><small>' + cuts.length + ' corte(s)</small></button></nav>' +
      '<div class="fv-web-layerbar" role="toolbar" aria-label="Camadas da lateral de viga">' +
        layerButton(state.section === 'cut' ? 'sa_cut' : 'sa',state.section === 'cut' ? 'SA Visão Corte' : 'SA',state.section === 'cut' ? layerMap.sa_cut : layerMap.sa,state.layer === (state.section === 'cut' ? 'sa_cut' : 'sa')) + layerButton('c1','C1',layerMap.c1,state.layer === 'c1') +
        layerButton('c2','C2',layerMap.c2,state.layer === 'c2') + layerButton('c3','C3',layerMap.c3,state.layer === 'c3') +
        (state.section === 'cut' ? layerButton('n3_cut','N3 Visão Corte',layerMap.n3_cut,state.layer === 'n3_cut') :
        layerButton('n3_panels','N3 Painéis Segmentos',layerMap.n3_panels,state.layer === 'n3_panels')) + '</div>' +
        '<div class="fv-web-segtabs" role="tablist">' + segTabsHtml(state, segments, cuts) + '</div>' +
        interpretation + (state.layer === 'n3_cut' ? n3Editor(data,state) : '') +
        (state.section === 'cut' ? '' : '<div class="fv-web-layer-actions">' +
          '<button type="button" class="success" data-lv-validate ' + (!segment || segment.human_validated ? 'disabled' : '') + '>' + (segment && segment.human_validated ? '✓ Segmento validado' : 'Validar Segmento') + '</button>' +
          (segment && segment.human_validated ? '<button type="button" class="danger" data-lv-unvalidate>Desvalidar Segmento</button>' : '') +
          '<button type="button" disabled title="Edição geométrica será conectada ao motor lateral">Editar Segmento</button>' +
          '<button type="button" disabled title="Exclusão será conectada ao motor lateral">Excluir Segmento</button></div>') +
        '<div class="fv-web-canvas"><div class="fv-web-canvas-inner">' + (layerInfo(data, state) && layerInfo(data, state).svg ? cleanSvg(layerInfo(data, state).svg) :
          '<div class="lv-canvas-empty">' + (layerInfo(data, state) && (layerInfo(data, state).lazy || layerInfo(data, state).loading) ? 'Carregando desenho desta camada…' : 'Camada sem desenho materializado.') + '</div>') + '</div>' +
          '<div class="fv-web-canvas-actions"><span>' + esc(({sa:'SA',sa_cut:'SA Visão Corte',c1:'C1',c2:'C2',c3:'C3',n3_cut:'N3 Visão Corte',n3_panels:'N3 Painéis Segmentos'})[state.layer]) +
            ' · ' + esc(state.section === 'cut'
              ? (state.cut === 'todos' ? 'Todos os cortes' : 'VC' + (Number(state.cut) + 1))
              : ('Lado ' + state.side + (state.segment === 'todos' ? ' · Todos' : (segment ? ' · S' + segment.index : '')))) +
            '</span><div class="fv-web-canvas-buttons"><button type="button" data-lv-reset>Resetar zoom</button></div></div></div>' +
        '<p class="fv-web-view-help">Scroll para zoom · arraste para mover · duplo-clique reseta</p></section>' +
      '<section class="fv-qa-below" aria-label="Camadas agenticas da lateral de viga"><div><strong>Camadas agenticas · Lateral de viga</strong>' +
        '<span>O fluxo usa a mesma sequência SA → C1 → C2 → C3. As filas ficam habilitadas quando o motor LV materializar os respectivos artefatos.</span></div>' +
        '<div class="fv-qa-version-grid">' + ['SA','C1','C2','C3'].map(function (label) {
          return '<article class="fv-qa-version"><button type="button" disabled>' + (label === 'SA' ? 'Interpretação Motor SA' : 'Solicitar revisão · ' + label) + '</button>' +
            '<label>Anotações humanas · ' + label + '<textarea disabled placeholder="Integração com a fila LV em preparação"></textarea></label></article>';
        }).join('') + '</div><div class="fv-qa-status">Estrutura visual preparada; nenhuma revisão é enfileirada por esta ficha nesta etapa.</div></section>' +
      '<details class="fv-web-advanced"><summary>Diagnóstico e proveniência</summary><div><p><b>Contrato:</b> ' + esc(data.schema) + '</p>' +
        '<p><b>Classe ativa:</b> ' + esc(sideData.class) + '</p><p>A troca de lado recompõe segmentos, subabas e camadas do viewer.</p></div></details></article>';

    bind(root, data, options, state);
    initPanZoom(root.querySelector('.fv-web-canvas'));
    if(state.layer==='n3_cut'||state.layer==='n3_panels'){paintN3(root,data,state);discoverN3(root,data,options,state);}
    ensureActiveLayer(root, data, options, state);
  }

  function bind(root, data, options, state) {
    root.querySelectorAll('[data-lv-n3-field]').forEach(function(input){input.addEventListener('input',function(){
      var side=input.dataset.lvN3Side,field=input.dataset.lvN3Field,panel=input.dataset.lvN3Panel;
      var destination=panel===undefined?state.n3Draft.sides[side]:state.n3Draft.sides[side].panels[Number(panel)];
      destination[field]=input.value;
      state.n3Dirty=true;state.n3Message='Alterações não salvas';paintN3(root,data,state);
    });});
    var saveN3Button=root.querySelector('[data-lv-n3-save]');
    if(saveN3Button)saveN3Button.addEventListener('click',function(){saveN3(root,data,options,state).catch(function(){});});
    var regenN3Button=root.querySelector('[data-lv-n3-regen]');
    if(regenN3Button)regenN3Button.addEventListener('click',function(){requestN3(root,data,options,state);});
    root.querySelectorAll('[data-lv-side]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.section = 'side'; state.layer = state.sideLayer || 'sa'; state.side = button.dataset.lvSide; state.expanded = null; state.segment = null;
        if (window.PortalDeepLink) window.PortalDeepLink.updateView({vista:state.layer,lado:state.side});
        render(root, data, options, state);
      });
    });
    root.querySelector('[data-lv-view="cut"]').addEventListener('click', function () {
      if (state.section !== 'cut') state.sideLayer = state.layer;
      state.section = 'cut'; state.layer = state.cutLayer || 'sa_cut'; render(root, data, options, state);
      if (window.PortalDeepLink) window.PortalDeepLink.updateView({vista:state.layer});
    });
    root.querySelectorAll('[data-lv-cut]').forEach(function (row) {
      row.addEventListener('click', function () { state.cut = Number(row.dataset.lvCut); render(root, data, options, state); });
    });
    root.querySelectorAll('[data-lv-segment]').forEach(function (row) {
      function select() {
        var index = Number(row.dataset.lvSegment);
        if (state.layer !== 'n3_cut') state.segment = index;
        state.expanded = state.expanded === index ? null : index;
        render(root, data, options, state);
      }
      row.addEventListener('click', select); row.addEventListener('keydown', function (event) { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); } });
    });
    root.querySelectorAll('[data-lv-segment-tab]').forEach(function (button) {
      button.addEventListener('click', function () {
        var raw = button.dataset.lvSegmentTab;
        state.segment = raw === 'todos' ? 'todos' : Number(raw);
        render(root, data, options, state);
      });
    });
    root.querySelectorAll('[data-lv-cut-tab]').forEach(function (button) {
      button.addEventListener('click', function () {
        var raw = button.dataset.lvCutTab;
        state.cut = raw === 'todos' ? 'todos' : Number(raw);
        render(root, data, options, state);
      });
    });
    root.querySelectorAll('[data-lv-layer]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.layer = button.dataset.lvLayer;
        if (state.section === 'cut') state.cutLayer = state.layer; else state.sideLayer = state.layer;
        if (state.layer === 'n3_panels' && state.segment !== 'todos') state.expanded = state.segment;
        render(root, data, options, state);
      });
    });
    root.querySelectorAll('[data-lv-beam]').forEach(function (button) {
      button.addEventListener('click', function () { if (button.dataset.lvBeam) load(root, Object.assign({}, options, {beam: button.dataset.lvBeam, initialSegment: null})); });
    });
    var add = root.querySelector('[data-lv-add-opening]');
    if (add) add.addEventListener('click', function () {
      var list = root.querySelector('[data-lv-openings]');
      var empty = list.querySelector('.fv-web-empty'); if (empty) empty.remove();
      list.insertAdjacentHTML('beforeend', '<div class="lv-opening-row" data-lv-opening><input placeholder="Pilar" aria-label="Pilar"><input type="number" min="0" step="0.1" placeholder="posição" aria-label="Posição em cm"><input type="number" min="0.001" step="0.1" placeholder="largura" aria-label="Largura em cm"><input type="number" min="0.001" step="0.1" placeholder="altura" aria-label="Altura em cm"><button type="button" data-lv-remove-opening aria-label="Remover abertura">×</button></div>');
      bindOpeningRemovers(root);
    });
    bindOpeningRemovers(root);
    var save = root.querySelector('[data-lv-save-openings]');
    if (save) save.addEventListener('click', function () {
      var openings = Array.prototype.map.call(root.querySelectorAll('[data-lv-opening]'), function (row) {
        var inputs = row.querySelectorAll('input');
        return {pillar: inputs[0].value, position_cm: inputs[1].value, width_cm: inputs[2].value, height_cm: inputs[3].value};
      });
      save.disabled = true;
      api('/obras/' + encodeURIComponent(options.obraId) + '/lv/' + encodeURIComponent(options.behavior) + '/' + encodeURIComponent(data.beam.name) +
        '/segmentos/' + state.side + '/' + state.segment + '/aberturas-pilar' + query(options), {
          method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify({pillar_openings: openings})
        }).then(function () { return load(root, Object.assign({}, options, {beam:data.beam.name, initialSide:state.side, initialSegment:state.segment})); })
        .catch(function (error) { save.disabled = false; window.alert('Falha ao salvar aberturas: ' + error.message); });
    });
    var validate = root.querySelector('[data-lv-validate]');
    if (validate) validate.addEventListener('click', function () { setValidation(root, data, options, state, true, validate); });
    var unvalidate = root.querySelector('[data-lv-unvalidate]');
    if (unvalidate) unvalidate.addEventListener('click', function () {
      if (window.confirm('Desvalidar o segmento S' + state.segment + ' do Lado ' + state.side + '?')) setValidation(root, data, options, state, false, unvalidate);
    });
  }

  function bindOpeningRemovers(root) {
    root.querySelectorAll('[data-lv-remove-opening]').forEach(function (button) {
      if (button.dataset.bound) return; button.dataset.bound = '1';
      button.addEventListener('click', function () { button.closest('[data-lv-opening]').remove(); });
    });
  }

  function setValidation(root, data, options, state, validado, button) {
    var segment = data.sides[state.side].segments.filter(function (item) { return item.index === state.segment; })[0];
    if (!segment) return; button.disabled = true;
    api('/obras/' + encodeURIComponent(options.obraId) + '/n1/' + encodeURIComponent(data.sides[state.side].class) + '/' + encodeURIComponent(segment.id) +
      '/campo/_item_/validar' + query(options), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({validado:validado})})
      .then(function () { if (window.DrillGrade && window.DrillGrade.refreshItems) window.DrillGrade.refreshItems(); return load(root, Object.assign({}, options, {beam:data.beam.name, initialSide:state.side, initialSegment:state.segment})); })
      .catch(function (error) { button.disabled = false; window.alert('Falha ao atualizar validação: ' + error.message); });
  }

  function query(options) {
    return options.pavimento ? '?pavimento=' + encodeURIComponent(options.pavimento) : '';
  }

  function load(root, options) {
    root.innerHTML = '<div class="fv-web-loading"><i></i><span>Montando ficha lateral de ' + esc(options.beam) + '…</span></div>';
    var metadataQuery = query(options);
    metadataQuery += (metadataQuery ? '&' : '?') + 'include_svgs=false';
    return api('/obras/' + encodeURIComponent(options.obraId) + '/lv/' + encodeURIComponent(options.behavior) + '/' + encodeURIComponent(options.beam) + metadataQuery)
      .then(function (data) {
        var side = String(options.initialSide || 'A').toUpperCase(); if (!data.sides[side]) side = 'A';
        var requested = Number(String(options.initialSegment || '').replace(/\D/g, ''));
        var state = {side:side, section:['sa_cut','n3_cut'].indexOf(options.initialLayer) >= 0 ? 'cut' : 'side', segment:requested || null, expanded:null, cut:0,
          layer:options.initialLayer||'sa',n3Draft:data.n3_ficha?JSON.parse(JSON.stringify(data.n3_ficha)):null,
          n3Dirty:false,n3Saving:false,n3Message:'',regenJobs:{},regenCheckingViews:{},
          regenErrors:{},regenTimers:{},regenRefreshOnDone:{},discoveredN3:{}};
        render(root, data, options, state);
      }).catch(function (error) {
        root.innerHTML = '<div class="fv-web-error"><strong>Não foi possível montar a ficha lateral.</strong><span>' + esc(error.message) + '</span><button type="button">Tentar novamente</button></div>';
        root.querySelector('button').addEventListener('click', function () { load(root, options); });
      });
  }

  window.LvFicha = {mount: load, cleanSvg: cleanSvg};
})();
