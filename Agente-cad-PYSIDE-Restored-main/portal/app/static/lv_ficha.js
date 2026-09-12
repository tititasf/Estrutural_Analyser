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

  function cutTable(cuts, selectedCut) {
    if (!cuts.length) return '<div class="lv-empty-state">Nenhuma visão de corte identificada para esta viga.</div>';
    return '<div class="fv-web-table-scroll lv-cut-scroll"><table class="fv-web-table"><thead><tr>' +
      '<th>Corte</th><th>Laje própria</th><th>Laje vizinha</th><th>Altura da viga</th><th>Confiança</th><th>Status</th>' +
      '</tr></thead><tbody>' + cuts.map(function (cut, index) {
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

  function segmentRows(segments, selectedIndex, expandedIndex, currentSide) {
    if (!segments.length) return '<tr><td colspan="8"><div class="lv-empty-state">Nenhum segmento identificado neste lado.</div></td></tr>';
    return segments.map(function (segment) {
      var selected = segment.index === selectedIndex, expanded = segment.index === expandedIndex;
      return '<tr class="fv-web-seg-row ' + (selected ? 'selected ' : '') + (expanded ? 'expanded' : '') + '" tabindex="0" data-lv-segment="' + segment.index + '">' +
        '<td class="fv-web-chev">›</td><td>S' + shown(segment.index) + '</td><td>' + shown(segment.length_cm) + '</td>' +
        '<td>' + shown(segment.width_cm) + '</td><td>' + shown(segment.beam_height_cm) + '</td><td>' + shown(segment.level) + '</td>' +
        '<td>' + shown(segment.status) + '</td><td><span class="fv-validation-seal ' + (segment.human_validated ? 'valid' : 'pending') + '">' +
          (segment.human_validated ? '✓ Validado' : 'Pendente') + '</span></td></tr>' +
        (expanded ? '<tr class="fv-web-seg-detail"><td colspan="8">' + openingEditor(segment, currentSide) + '</td></tr>' : '');
    }).join('');
  }

  function layerInfo(data, state) {
    var segment = (data.sides[state.side].segments || []).filter(function (item) { return item.index === state.segment; })[0] || null;
    var cut = data.cut_views[state.cut] || null;
    var map = {
      sa: segment && segment.layers.sa,
      c1: segment && segment.layers.c1,
      c2: segment && segment.layers.c2,
      c3: segment && segment.layers.c3,
      n3_cut: cut && cut.layers.n3_cut,
      n3_panels: segment && segment.layers.n3_panels
    };
    return map[state.layer] || null;
  }

  function layerButton(name, label, info, active) {
    var available = !!(info && info.available);
    return '<button type="button" class="fv-web-layer ' + name + (active ? ' active' : '') + '" data-lv-layer="' + name + '" ' +
      (!available ? 'disabled title="Camada ainda não materializada"' : '') + '><i>' + (name.indexOf('n3') === 0 ? '■' : '●') + '</i>' +
      esc(label) + '<small>' + (info && info.loading ? 'carregando' : (info && info.lazy ? 'sob demanda' : (available ? 'disponível' : 'ausente'))) + '</small></button>';
  }

  function ensureActiveLayer(root, data, options, state) {
    var info = layerInfo(data, state);
    if (!info || !info.lazy || info.loading) return;
    info.loading = true;
    var params = query(options);
    params += (params ? '&' : '?') + 'side=' + encodeURIComponent(state.side) +
      '&segment_index=' + encodeURIComponent(state.segment || 1) + '&cut_index=' + encodeURIComponent(state.cut || 0);
    api('/obras/' + encodeURIComponent(options.obraId) + '/lv/' + encodeURIComponent(options.behavior) + '/' +
      encodeURIComponent(data.beam.name) + '/camada/' + encodeURIComponent(state.layer) + params)
      .then(function (payload) {
        info.loading = false; info.lazy = false; info.available = !!payload.available; info.svg = payload.svg || null;
        if (layerInfo(data, state) === info) render(root, data, options, state);
      }).catch(function (error) {
        info.loading = false; info.lazy = false; info.available = false; info.error = error.message;
        if (layerInfo(data, state) === info) render(root, data, options, state);
      });
  }

  function render(root, data, options, state) {
    var sideData = data.sides[state.side], segments = sideData.segments || [];
    if (!segments.some(function (item) { return item.index === state.segment; })) state.segment = segments.length ? segments[0].index : null;
    var segment = segments.filter(function (item) { return item.index === state.segment; })[0] || null;
    var cuts = data.cut_views || [];
    if (state.cut >= cuts.length) state.cut = 0;
    var layerMap = {
      sa: segment && segment.layers.sa, c1: segment && segment.layers.c1,
      c2: segment && segment.layers.c2, c3: segment && segment.layers.c3,
      n3_cut: cuts[state.cut] && cuts[state.cut].layers.n3_cut,
      n3_panels: segment && segment.layers.n3_panels
    };
    if (!layerMap[state.layer] || !layerMap[state.layer].available) {
      state.layer = ['sa', 'n3_cut', 'n3_panels'].filter(function (name) { return layerMap[name] && layerMap[name].available; })[0] || 'sa';
    }
    var total = (data.sides.A.segments || []).length + (data.sides.B.segments || []).length;
    root.innerHTML = '<article class="fv-web-ficha lv-web-ficha">' +
      '<header class="fv-web-head"><div><p class="fv-web-kicker">Lateral de viga · ficha HI-FI</p><h2>' + esc(data.beam.name) + '</h2>' +
        '<span>' + total + ' segmento(s) · A: ' + data.sides.A.segments.length + ' · B: ' + data.sides.B.segments.length + '</span>' +
        '<div class="lv-behavior-tag"><b>Comportamento:</b> ' + esc(data.beam.behavior_label) + '</div></div>' +
        '<div class="fv-web-nav"><button type="button" data-lv-beam="' + esc(data.beam.previous || '') + '" ' + (!data.beam.previous ? 'disabled' : '') + '>←</button>' +
        '<b>' + data.beam.position + '/' + data.beam.total_beams + '</b><button type="button" data-lv-beam="' + esc(data.beam.next || '') + '" ' + (!data.beam.next ? 'disabled' : '') + '>→</button></div></header>' +
      '<nav class="lv-side-tabs" role="tablist" aria-label="Lados da lateral de viga">' + ['A','B'].map(function (side) {
        return '<button type="button" role="tab" aria-selected="' + (state.side === side) + '" class="lv-side-tab ' + (state.side === side ? 'active' : '') + '" data-lv-side="' + side + '">' +
          '<strong>Lado ' + side + '</strong><span>' + data.sides[side].segments.length + ' segmento(s)</span></button>';
      }).join('') + '</nav>' +
      '<section class="fv-web-table-card lv-cut-card"><div class="fv-web-section-title"><div><h3>Interpretação das visões de corte</h3>' +
        '<p>Referências transversais associadas à viga; a seleção altera a camada N3 Visão Corte.</p></div><span>' + cuts.length + ' visão(ões)</span></div>' + cutTable(cuts, state.cut) + '</section>' +
      '<section class="fv-web-table-card"><div class="fv-web-section-title"><div><h3>Interpretação dos segmentos · Lado ' + state.side + '</h3>' +
        '<p>Selecione uma linha para abrir os detalhes e enquadrar o segmento.</p></div><span>medidas em cm</span></div>' +
        '<div class="fv-web-table-scroll"><table class="fv-web-table"><thead><tr><th></th><th>Seg.</th><th>Comprimento</th><th>Largura</th>' +
        '<th>Altura da viga</th><th>Nível</th><th>Status</th><th>Selo validação</th></tr></thead><tbody>' +
        segmentRows(segments, state.segment, state.expanded, state.side) + '</tbody></table></div></section>' +
      '<section class="fv-web-viewer-card"><div class="fv-web-layerbar" role="toolbar" aria-label="Camadas da lateral de viga">' +
        layerButton('sa','SA',layerMap.sa,state.layer === 'sa') + layerButton('c1','C1',layerMap.c1,state.layer === 'c1') +
        layerButton('c2','C2',layerMap.c2,state.layer === 'c2') + layerButton('c3','C3',layerMap.c3,state.layer === 'c3') +
        layerButton('n3_cut','N3 Visão Corte',layerMap.n3_cut,state.layer === 'n3_cut') +
        layerButton('n3_panels','N3 Painéis Segmentos',layerMap.n3_panels,state.layer === 'n3_panels') + '</div>' +
        '<div class="fv-web-segtabs" role="tablist">' + segments.map(function (item) {
          return '<button type="button" class="' + (state.segment === item.index ? 'active' : '') + '" data-lv-segment-tab="' + item.index + '">S' + item.index + '</button>';
        }).join('') + '</div><div class="fv-web-layer-actions">' +
          '<button type="button" class="success" data-lv-validate ' + (!segment || segment.human_validated ? 'disabled' : '') + '>' + (segment && segment.human_validated ? '✓ Segmento validado' : 'Validar Segmento') + '</button>' +
          (segment && segment.human_validated ? '<button type="button" class="danger" data-lv-unvalidate>Desvalidar Segmento</button>' : '') +
          '<button type="button" disabled title="Edição geométrica será conectada ao motor lateral">Editar Segmento</button>' +
          '<button type="button" disabled title="Exclusão será conectada ao motor lateral">Excluir Segmento</button></div>' +
        '<div class="fv-web-canvas"><div class="fv-web-canvas-inner">' + (layerInfo(data, state) && layerInfo(data, state).svg ? cleanSvg(layerInfo(data, state).svg) :
          '<div class="lv-canvas-empty">' + (layerInfo(data, state) && (layerInfo(data, state).lazy || layerInfo(data, state).loading) ? 'Carregando desenho desta camada…' : 'Camada sem desenho materializado.') + '</div>') + '</div>' +
          '<div class="fv-web-canvas-actions"><span>' + esc(({sa:'SA',c1:'C1',c2:'C2',c3:'C3',n3_cut:'N3 Visão Corte',n3_panels:'N3 Painéis Segmentos'})[state.layer]) +
            ' · Lado ' + state.side + (segment ? ' · S' + segment.index : '') + '</span><div class="fv-web-canvas-buttons"><button type="button" data-lv-reset>Resetar zoom</button></div></div></div>' +
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
    ensureActiveLayer(root, data, options, state);
  }

  function bind(root, data, options, state) {
    root.querySelectorAll('[data-lv-side]').forEach(function (button) {
      button.addEventListener('click', function () {
        state.side = button.dataset.lvSide; state.expanded = null; state.segment = null; state.layer = 'sa'; render(root, data, options, state);
      });
    });
    root.querySelectorAll('[data-lv-cut]').forEach(function (row) {
      row.addEventListener('click', function () { state.cut = Number(row.dataset.lvCut); state.layer = 'n3_cut'; render(root, data, options, state); });
    });
    root.querySelectorAll('[data-lv-segment]').forEach(function (row) {
      function select() {
        var index = Number(row.dataset.lvSegment); state.segment = index; state.expanded = state.expanded === index ? null : index; state.layer = 'sa'; render(root, data, options, state);
      }
      row.addEventListener('click', select); row.addEventListener('keydown', function (event) { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); } });
    });
    root.querySelectorAll('[data-lv-segment-tab]').forEach(function (button) {
      button.addEventListener('click', function () { state.segment = Number(button.dataset.lvSegmentTab); state.layer = 'sa'; render(root, data, options, state); });
    });
    root.querySelectorAll('[data-lv-layer]').forEach(function (button) {
      button.addEventListener('click', function () { state.layer = button.dataset.lvLayer; render(root, data, options, state); });
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
        var state = {side:side, segment:requested || null, expanded:null, cut:0, layer:'sa'};
        render(root, data, options, state);
      }).catch(function (error) {
        root.innerHTML = '<div class="fv-web-error"><strong>Não foi possível montar a ficha lateral.</strong><span>' + esc(error.message) + '</span><button type="button">Tentar novamente</button></div>';
        root.querySelector('button').addEventListener('click', function () { load(root, options); });
      });
  }

  window.LvFicha = {mount: load, cleanSvg: cleanSvg};
})();
