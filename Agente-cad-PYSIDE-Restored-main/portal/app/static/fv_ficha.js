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

  function cleanSvg(raw) {
    if (!raw) return '';
    var doc = new DOMParser().parseFromString(raw, 'image/svg+xml');
    if (doc.querySelector('parsererror')) return '';
    doc.querySelectorAll('script,foreignObject').forEach(function (node) { node.remove(); });
    doc.querySelectorAll('*').forEach(function (node) {
      Array.prototype.slice.call(node.attributes || []).forEach(function (attr) {
        if (/^on/i.test(attr.name)) node.removeAttribute(attr.name);
        if ((attr.name === 'href' || attr.name === 'xlink:href') && /^javascript:/i.test(attr.value)) {
          node.removeAttribute(attr.name);
        }
      });
    });
    var svg = doc.documentElement;
    svg.removeAttribute('width');
    svg.removeAttribute('height');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.classList.add('fv-web-svg');
    return new XMLSerializer().serializeToString(svg);
  }

  function layerLabel(name) {
    return ({sa: 'SA', c1: 'C1', c2: 'C2', c3: 'C3', n3: 'N3'})[name] || name.toUpperCase();
  }

  function layerIcon(name) {
    return ({sa: '●', c1: '●', c2: '●', c3: '●', n3: '■'})[name] || '●';
  }

  function reviewBadge(layer, review) {
    if (!review || !review.verdict) return '';
    var approved = review.verdict === 'validou';
    var confidence = review.confidence_percent === null || review.confidence_percent === undefined
      ? '' : ' · ' + shown(review.confidence_percent) + '%';
    var target = ({L1: 'SA', L2: 'C1', L3: 'C2'})[layer] || layer;
    return '<span class="fv-qa-badge ' + (approved ? 'approved' : 'rejected') + '">' +
      target + ' ' + (approved ? 'aprovado' : 'reprovado') + confidence + '</span>';
  }

  function qaStatusHtml(reviews) {
    var layers = ['L1', 'L2', 'L3'];
    var badges = layers.map(function (layer) { return reviewBadge(layer, reviews[layer]); }).join('');
    return badges || '<span class="fv-qa-empty">Nenhuma revisão solicitada nesta abertura.</span>';
  }

  function featureEditor(kind, title, values) {
    values = Array.isArray(values) ? values : [];
    var rows = values.map(function (value, index) {
      if (kind === 'chamfer') return '<div class="fv-n3-feature-row" data-fv-chamfer><select><option value="te" ' +
        (value.position === 'te' ? 'selected' : '') + '>Topo esquerdo</option><option value="fe" ' +
        (value.position === 'fe' ? 'selected' : '') + '>Fundo esquerdo</option><option value="td" ' +
        (value.position === 'td' ? 'selected' : '') + '>Topo direito</option><option value="fd" ' +
        (value.position === 'fd' ? 'selected' : '') + '>Fundo direito</option></select><input type="number" min="0.001" step="0.1" value="' +
        esc(value.size_cm) + '" aria-label="Tamanho do chanfro"><button type="button" data-fv-remove-feature>×</button></div>';
      return '<div class="fv-n3-feature-row openings" data-fv-opening><input type="number" min="0" step="0.1" value="' +
        esc(value.position_cm) + '" placeholder="posição" aria-label="Posição da abertura"><input type="number" min="0.001" step="0.1" value="' +
        esc(value.width_cm) + '" placeholder="largura" aria-label="Largura da abertura"><input type="number" min="0.001" step="0.1" value="' +
        esc(value.height_cm) + '" placeholder="altura" aria-label="Altura da abertura"><button type="button" data-fv-remove-feature>×</button></div>';
    }).join('');
    return '<section class="fv-web-mini"><h5>' + esc(title) + '</h5><div data-fv-feature-list="' + kind + '">' +
      (rows || '<p class="fv-web-empty">Nenhum</p>') + '</div><button type="button" class="fv-mini-add" data-fv-add-' + kind +
      '>+ Adicionar ' + (kind === 'chamfer' ? 'chanfro' : 'abertura') + '</button></section>';
  }

  function panelTable(panels) {
    if (!panels || !panels.length) {
      return '<section class="fv-web-mini"><h5>Painéis N3</h5><p class="fv-web-empty">Não materializados</p></section>';
    }
    return '<section class="fv-web-mini"><h5>Painéis N3 <small>máx. 244 × 122</small></h5>' +
      '<table><thead><tr><th>#</th><th>Comprimento</th><th>Largura</th></tr></thead><tbody>' +
      panels.map(function (panel) {
        return '<tr data-fv-panel><td>' + shown(panel.index) + '</td><td><input type="number" min="0.001" step="0.1" value="' +
          esc(panel.length_cm) + '" aria-label="Comprimento do painel"></td><td><input type="number" min="0.001" step="0.1" value="' +
          esc(panel.width_cm) + '" aria-label="Largura do painel"></td></tr>';
      }).join('') + '</tbody></table></section>';
  }

  function segmentRows(segments) {
    return (segments || []).map(function (segment) {
      var detailId = 'fv-web-detail-' + segment.index;
      var n3 = segment.n3 || {};
      var mismatch = segment.enrichment_status === 'mismatch';
      return '<tr class="fv-web-seg-row" data-fv-segment="' + esc(segment.index) + '" tabindex="0" ' +
        'aria-expanded="false" aria-controls="' + detailId + '">' +
        '<td class="fv-web-chev" aria-hidden="true">›</td><td><b>S' + shown(segment.index) + '</b></td>' +
        '<td>' + shown(segment.length_cm) + '</td><td>' + shown(segment.width_cm) + '</td>' +
        '<td>' + shown(segment.beam_height_cm) + '</td><td>' + shown(segment.level) + '</td>' +
        '<td>' + shown(segment.support_start) + '</td><td>' + shown(segment.support_end) + '</td>' +
        '<td><span class="fv-web-count' + (n3.available ? '' : ' empty') + (mismatch ? ' mismatch' : '') + '" ' +
          (mismatch ? 'title="A ficha HI-FI pertence a outra segmentação; prevalece o SA atual"' : '') + '>' +
          (mismatch ? 'revisar' : (n3.available ? shown((n3.panels || []).length) : '—')) + '</span></td>' +
        '<td><span class="fv-validation-seal ' + (segment.human_validated ? 'valid' : 'pending') + '">' +
          (segment.human_validated ? '✓ Validado' : 'Pendente') + '</span></td></tr>' +
        '<tr class="fv-web-seg-detail" id="' + detailId + '" data-fv-detail="' + esc(segment.index) + '" hidden>' +
        '<td colspan="10"><div class="fv-web-detail-grid">' + panelTable(n3.panels) +
          featureEditor('chamfer', 'Chanfros', n3.chamfers) + featureEditor('opening', 'Aberturas', n3.openings) +
        '</div><div class="fv-segment-detail-actions"><button type="button" data-fv-save-n3>Salvar dados N3</button>' +
          '<button type="button" data-fv-regenerate-n3>Regenerar N3 deste segmento</button>' +
          (segment.human_validated
            ? '<button type="button" class="success" disabled>✓ Segmento validado</button>' +
              '<button type="button" class="danger" data-fv-detail-unvalidate>Desvalidar segmento</button>'
            : '<button type="button" class="success" data-fv-detail-validate>Validar segmento</button>') +
          '</div></td></tr>';
    }).join('');
  }

  function frame(data) {
    var beam = data.beam;
    var layers = (data.context && data.context.layers) || {};
    var enrichment = (data.source && data.source.segment_enrichment) || {};
    var mismatchCount = Number(enrichment.mismatch || 0);
    var layerOrder = ['sa', 'c1', 'c2', 'c3', 'n3'];
    return '<article class="fv-web-ficha" aria-label="Ficha de fundo de viga ' + esc(beam.name) + '">' +
      '<header class="fv-web-head"><div>' +
        '<p class="fv-web-kicker">Fundo de viga · ficha HI-FI</p><h2>' + esc(beam.name) + '</h2>' +
        '<span>' + beam.segment_count + ' segmento(s)</span><button type="button" class="fv-rename" data-fv-rename>Renomear fundo de viga</button><button type="button" class="danger" data-fv-delete-beam>Excluir viga</button></div>' +
        '<div class="fv-web-nav"><button type="button" data-fv-nav="previous" data-fv-target="' + esc(beam.previous || '') + '" ' + (!beam.previous ? 'disabled' : '') +
          ' aria-label="Viga anterior">←</button><b>' + beam.position + '/' + beam.total_beams + '</b>' +
          '<button type="button" data-fv-nav="next" data-fv-target="' + esc(beam.next || '') + '" ' + (!beam.next ? 'disabled' : '') +
          ' aria-label="Próxima viga">→</button></div></header>' +
      (mismatchCount ? '<aside class="fv-web-integrity" role="status"><strong>SA atual preservado</strong><span>' +
        mismatchCount + ' segmento(s) diferem da ficha HI-FI de referência. Medidas e painéis antigos não foram aplicados; ' +
        'as camadas de desenho permanecem disponíveis somente para comparação.</span></aside>' : '') +
      '<section class="fv-web-viewer-card"><div class="fv-web-layerbar" role="toolbar" aria-label="Camadas do fundo de viga">' +
        layerOrder.map(function (name) {
          var available = name === 'n3' || (layers[name] && layers[name].available);
          var referenceOnly = available && name !== 'sa' && mismatchCount > 0;
          return '<button type="button" class="fv-web-layer ' + name + (name === 'sa' ? ' active' : '') + '" data-fv-layer="' + name + '" ' +
            (!available ? 'disabled title="Camada não materializada"' : (referenceOnly ? 'title="Referência visual de outra segmentação"' : '')) +
            '><i>' + layerIcon(name) + '</i>' + layerLabel(name) +
            '<small>' + (available ? (referenceOnly ? 'referência' : 'disponível') : 'ausente') + '</small></button>';
        }).join('') + '</div>' +
        '<div class="fv-web-segtabs" role="tablist" data-fv-segtabs></div>' +
        '<section class="fv-web-table-card lv-interpretation-card fv-interpretation-card"><div class="fv-web-table-scroll"><table class="fv-web-table">' +
        '<thead><tr><th></th><th>Seg.</th><th>Comprimento</th><th>Largura</th><th>Altura da viga</th>' +
        '<th>Nível</th><th>Ponto inicial</th><th>Ponto final</th><th>Painéis N3</th>' +
        '<th>Selo validação<br><button type="button" data-fv-table-validate-all>Validar todos</button></th></tr></thead>' +
        '<tbody>' + segmentRows(data.segments) + '</tbody></table></div></section>' +
        '<div class="fv-web-layer-actions" data-fv-layer-actions></div>' +
        '<div class="fv-web-canvas" tabindex="0"><div class="fv-web-canvas-inner"></div>' +
          '<div class="fv-web-canvas-actions"><span data-fv-view-label>SA · Todos</span>' +
          '<div class="fv-web-canvas-buttons"><button type="button" data-fv-toggle-highlight>Ocultar destaque · Todos</button>' +
          '<button type="button" data-fv-reset>Resetar zoom</button></div></div></div>' +
        '<p class="fv-web-view-help">Scroll para zoom · arraste para mover · na edição, botão do meio arrasta · duplo-clique reseta</p>' +
      '</section>' +
      '<section class="fv-qa-below" aria-label="QA agentivo e humano do fundo de viga">' +
        '<div><strong>QA agentivo e Humano</strong><span>Cada revisão recebe as notas e apontamentos humanos salvos.</span></div>' +
        '<div class="fv-qa-version-grid">' + ['sa', 'c1', 'c2', 'c3'].map(function (name, index) {
          var qaLayer = index ? 'L' + index : '';
          return '<article class="fv-qa-version"><button type="button" ' + (qaLayer ? 'data-fv-qa-layer="' + qaLayer + '"' : 'disabled') + '>' +
            (name === 'sa' ? 'Interpretação Motor SA' : 'Solicitar revisão · Camada ' + index) + '</button>' +
            '<label>Anotações humanas · ' + name.toUpperCase() + '<textarea data-fv-note="' + name + '" placeholder="Opinião humana sobre esta versão">' +
            esc((data.human_notes || {})[name] || '') + '</textarea></label></article>';
        }).join('') + '</div><button type="button" data-fv-save-notes>Salvar anotações humanas</button>' +
        '<div class="fv-qa-status" data-fv-qa-status>' + qaStatusHtml(data.qa_reviews || {}) + '</div>' +
        '<section class="fv-annotations"><h4>Apontamentos humanos</h4><div data-fv-annotation-editor hidden>' +
          '<span data-fv-point-label>Selecione um elemento no viewer</span><input type="text" data-fv-point-text placeholder="Escreva o que deseja registrar sobre este ponto">' +
          '<button type="button" data-fv-save-point>Salvar apontamento</button><button type="button" data-fv-cancel-point>Cancelar</button></div>' +
          '<div data-fv-annotations>' + (data.annotations || []).map(function (point) {
            return '<div class="fv-annotation" data-fv-annotation="' + esc(point.id) + '"><b>' + esc(point.layer.toUpperCase()) +
              ' · ' + esc(point.segment === 'todos' ? 'Todos' : 'S' + point.segment) + '</b><span>' + esc(point.element) + '</span><p>' +
              esc(point.text) + '</p><button type="button" data-fv-delete-point>Excluir</button></div>';
          }).join('') + '</div></section>' +
      '</section>' +
      '<details class="fv-web-advanced"><summary>Diagnóstico e proveniência</summary><div>' +
        '<p><b>Contrato:</b> ' + esc(data.schema) + '</p><p><b>Artefato:</b> ' + shown(data.source.artifact) + '</p>' +
        '<p><b>Enriquecimento:</b> ' + shown((data.source.segment_enrichment || {}).matched) + ' compatível(is), ' +
          shown((data.source.segment_enrichment || {}).mismatch) + ' divergente(s), ' +
          shown((data.source.segment_enrichment || {}).absent) + ' sem referência</p>' +
        '<p>O estado SA determina os segmentos. A ficha HI-FI fornece somente o enriquecimento visual e N3 materializado.</p>' +
      '</div></details></article>';
  }

  function initPanZoom(canvas) {
    var svg = canvas.querySelector('svg');
    if (!svg || !svg.viewBox || !svg.viewBox.baseVal) return null;
    var base = svg.viewBox.baseVal;
    var home = {x: base.x, y: base.y, w: base.width, h: base.height};
    var view = {x: home.x, y: home.y, w: home.w, h: home.h};
    var dragging = false;
    var last = null;

    function apply() { svg.setAttribute('viewBox', [view.x, view.y, view.w, view.h].join(' ')); }
    function reset() { view = {x: home.x, y: home.y, w: home.w, h: home.h}; apply(); }
    function point(event) {
      var rect = svg.getBoundingClientRect();
      return {x: view.x + (event.clientX - rect.left) / rect.width * view.w,
              y: view.y + (event.clientY - rect.top) / rect.height * view.h};
    }
    canvas.addEventListener('wheel', function (event) {
      event.preventDefault();
      var anchor = point(event);
      var factor = event.deltaY < 0 ? 0.88 : 1.14;
      var nextW = Math.max(home.w * 0.006, Math.min(home.w * 8, view.w * factor));
      var nextH = nextW * home.h / home.w;
      var rx = (anchor.x - view.x) / view.w;
      var ry = (anchor.y - view.y) / view.h;
      view.x = anchor.x - rx * nextW; view.y = anchor.y - ry * nextH;
      view.w = nextW; view.h = nextH; apply();
    }, {passive: false});
    // Use mouse events here rather than relying only on pointer events. Chromium
    // starts its native middle-button auto-scroll from `mousedown`; cancelling
    // only `pointerdown` still lets the document steal the wheel-button gesture.
    canvas.addEventListener('mousedown', function (event) {
      var editing = canvas.classList.contains('fv-editing');
      var middleButton = event.button === 1;
      if (!middleButton && (editing || event.button !== 0)) return;
      // No editor o botão esquerdo continua reservado para marcar vértices. O
      // botão do meio navega pelo mesmo viewBox e também cancela o auto-scroll
      // nativo do navegador, que concorria com o pan.
      event.preventDefault();
      event.stopPropagation();
      dragging = true; last = {x: event.clientX, y: event.clientY};
      canvas.classList.add('dragging');
    });
    window.addEventListener('mousemove', function (event) {
      if (!dragging) return;
      event.preventDefault();
      var rect = svg.getBoundingClientRect();
      view.x -= (event.clientX - last.x) / rect.width * view.w;
      view.y -= (event.clientY - last.y) / rect.height * view.h;
      last = {x: event.clientX, y: event.clientY}; apply();
    });
    function stop() { dragging = false; canvas.classList.remove('dragging'); }
    window.addEventListener('mouseup', stop);
    canvas.addEventListener('auxclick', function (event) {
      if (event.button === 1) {
        event.preventDefault();
        event.stopPropagation();
      }
    });
    canvas.addEventListener('dblclick', reset);
    return {reset: reset, svg: svg, view: view, home: home, apply: apply,
      isDragging: function () { return dragging; }};
  }

  function focusSegment(pz, layer, segment) {
    if (!pz || segment === 'todos') { if (pz) pz.reset(); return; }
    var svg = pz.svg;
    var target = null;
    if (layer === 'n3') {
      target = svg.querySelector('.fv-n3-seg[data-n3-seg="' + segment + '"]') ||
        svg.querySelector('.fv-n3-seg[data-seg="' + segment + '"]');
    } else {
      Array.prototype.slice.call(svg.querySelectorAll('text')).some(function (text) {
        if ((text.textContent || '').trim().toUpperCase() === ('S' + segment).toUpperCase()) {
          target = text.closest('g') || text; return true;
        }
        return false;
      });
    }
    if (!target || typeof target.getBBox !== 'function') return;
    try {
      var box = target.getBBox();
      var pad = Math.max(12, Math.max(box.width, box.height) * 1.4);
      var width = Math.max(box.width + pad * 2, pz.home.w * 0.12);
      var height = width * pz.home.h / pz.home.w;
      pz.view.x = box.x + box.width / 2 - width / 2;
      pz.view.y = box.y + box.height / 2 - height / 2;
      pz.view.w = width; pz.view.h = height; pz.apply();
    } catch (ignore) {}
  }

  function bind(root, options, data) {
    var state = {layer: String(options.initialLayer || 'sa'), segment: String(options.initialSegment || 'todos'), pz: null,
      editing: null, pointing: null, hiddenHighlights: []};
    var layers = data.context.layers || {};
    var canvas = root.querySelector('.fv-web-canvas');
    var inner = root.querySelector('.fv-web-canvas-inner');
    var label = root.querySelector('[data-fv-view-label]');
    var qaStatus = root.querySelector('[data-fv-qa-status]');

    function querySuffix() {
      return options.pavimento ? '?pavimento=' + encodeURIComponent(options.pavimento) : '';
    }

    function api(url, requestOptions) {
      return fetch(url, requestOptions || {}).then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) throw new Error(body.detail || ('HTTP ' + response.status));
          return body;
        });
      });
    }

    function segmentsForLayer(name) {
      var source = (layers[name] && layers[name].segments) || [];
      return source.map(function (segment) { return String(segment.index || segment.label); }).filter(Boolean);
    }

    function renderSegmentTabs() {
      var host = root.querySelector('[data-fv-segtabs]');
      var available = segmentsForLayer(state.layer);
      if (state.segment !== 'todos' && available.indexOf(state.segment) < 0) state.segment = 'todos';
      host.innerHTML = '<button type="button" data-fv-focus="todos">Todos</button>' + available.map(function (index) {
        return '<button type="button" data-fv-focus="' + esc(index) + '">S' + esc(index) + '</button>';
      }).join('');
      host.querySelectorAll('[data-fv-focus]').forEach(function (button) {
        button.classList.toggle('active', button.getAttribute('data-fv-focus') === state.segment);
      });
    }

    function selectedSaSegment() {
      return (data.segments || []).filter(function (segment) {
        return String(segment.index) === state.segment;
      })[0] || null;
    }

    function renderLayerActions() {
      var host = root.querySelector('[data-fv-layer-actions]');
      if (state.editing) {
        host.innerHTML = '<button type="button" class="primary" data-fv-save-edit>Concluir e Salvar</button>' +
          '<button type="button" class="fv-ortho' + (state.editing.ortho ? ' active' : '') +
            '" data-fv-edit-ortho aria-pressed="' + (state.editing.ortho ? 'true' : 'false') +
            '">Ortho <kbd>F8</kbd></button>' +
          '<span class="fv-osnap-state ' + (state.editing.osnapReady ? 'ready' : '') + '">OSNAP · ' +
            (state.editing.osnapReady ? state.editing.snapCount + ' alvos' : 'indexando…') + '</span>' +
          '<button type="button" data-fv-cancel-edit>Cancelar edição</button>';
        return;
      }
      if (['c1', 'c2', 'c3'].indexOf(state.layer) >= 0) {
        host.innerHTML = '<button type="button" class="primary" data-fv-adopt>Adotar Camada Agentica como SA</button>' +
          '<button type="button" class="danger" data-fv-delete-layer>Excluir Camada Agentica</button>' +
          '<button type="button" data-fv-point>Fazer apontamento</button>';
        return;
      }
      if (state.layer !== 'sa') { host.innerHTML = ''; return; }
      var selected = selectedSaSegment();
      host.innerHTML =
        '<button type="button" class="success" data-fv-validate-all>' +
          (data.human_validated ? '✓ Todos os segmentos validados' : 'Validar Todos Segmentos') + '</button>' +
        '<button type="button" class="success" data-fv-validate-one ' + (!selected || selected.human_validated ? 'disabled' : '') + '>' +
          (selected && selected.human_validated ? '✓ Segmento validado' : 'Validar Segmento') + '</button>' +
        (selected && selected.human_validated
          ? '<button type="button" class="danger" data-fv-unvalidate-one>Desvalidar Segmento</button>' : '') +
        '<button type="button" data-fv-edit ' + (!selected ? 'disabled' : '') + '>Editar Segmento</button>' +
        '<button type="button" class="danger" data-fv-delete ' + (!selected ? 'disabled' : '') + '>Excluir Segmento</button>' +
        '<button type="button" data-fv-point>Fazer apontamento</button>';
    }

    function notesPayload() {
      var notes = {};
      root.querySelectorAll('[data-fv-note]').forEach(function (field) {
        notes[field.getAttribute('data-fv-note')] = field.value;
      });
      return notes;
    }

    function saveNotes(showFeedback) {
      return api('/obras/' + encodeURIComponent(options.obraId) + '/fv/' + encodeURIComponent(data.beam.name) +
        '/notas' + querySuffix(), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({notes:notesPayload()})})
        .then(function () { if (showFeedback) qaStatus.textContent = 'Anotações humanas salvas.'; });
    }

    function requestQa(button, layer) {
      button.disabled = true;
      qaStatus.className = 'fv-qa-status';
      qaStatus.textContent = 'Salvando notas e enfileirando revisão ' + layer + '…';
      saveNotes(false).then(function () { return fetch('/obras/' + encodeURIComponent(options.obraId) + '/qa-agentico', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({items: [data.beam.name], classe: 'FV', pavimento: options.pavimento, layer: layer})
      }); }).then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) throw new Error(body.detail || ('HTTP ' + response.status));
          return body;
        });
      }).then(function (body) {
        function poll() {
          fetch('/qa-rounds/' + encodeURIComponent(body.round_id)).then(function (response) {
            return response.json().then(function (detail) {
              if (!response.ok) throw new Error(detail.detail || ('HTTP ' + response.status));
              return detail;
            });
          }).then(function (detail) {
            if (['queued', 'running', 'na_fila'].indexOf(detail.status) >= 0) {
              qaStatus.textContent = 'QA ' + detail.status + ' · ' + layer + '…';
              window.setTimeout(poll, 2500); return;
            }
            button.disabled = false;
            var result = (detail.items || [])[0] || {};
            if (result.status !== 'completed') {
              var attempts = result.attempts || [];
              var lastAttempt = attempts.length ? attempts[attempts.length - 1] : {};
              qaStatus.className = 'fv-qa-status error';
              qaStatus.textContent = 'Falha técnica no QA' +
                (lastAttempt.failure_category ? ' · ' + lastAttempt.failure_category : '') +
                (lastAttempt.error ? ': ' + lastAttempt.error : '.');
              return;
            }
            qaStatus.innerHTML = reviewBadge(layer, result) +
              '<p>' + esc(result.note || 'Sem observação.') + '</p>';
            if (result.status === 'completed') {
              if (window.DrillGrade && typeof window.DrillGrade.refreshItems === 'function') {
                window.DrillGrade.refreshItems();
              }
              window.setTimeout(function () { load(root, options); }, 900);
            }
          }).catch(function (error) {
            button.disabled = false; qaStatus.className = 'fv-qa-status error';
            qaStatus.textContent = 'Falha ao acompanhar a revisão: ' + error.message;
          });
        }
        poll();
      }).catch(function (error) {
        button.disabled = false; qaStatus.className = 'fv-qa-status error';
        qaStatus.textContent = 'Falha ao enfileirar: ' + error.message;
      });
    }

    function detailPayload(detail) {
      return {
        panels: Array.prototype.slice.call(detail.querySelectorAll('[data-fv-panel]')).map(function (row) {
          var fields = row.querySelectorAll('input'); return {length_cm: fields[0].value, width_cm: fields[1].value};
        }),
        chamfers: Array.prototype.slice.call(detail.querySelectorAll('[data-fv-chamfer]')).map(function (row) {
          return {position: row.querySelector('select').value, size_cm: row.querySelector('input').value};
        }),
        openings: Array.prototype.slice.call(detail.querySelectorAll('[data-fv-opening]')).map(function (row) {
          var fields = row.querySelectorAll('input'); return {position_cm: fields[0].value, width_cm: fields[1].value, height_cm: fields[2].value};
        })
      };
    }

    function saveN3(detail, button) {
      var index = detail.getAttribute('data-fv-detail'); button.disabled = true;
      return api('/obras/' + encodeURIComponent(options.obraId) + '/fv/' + encodeURIComponent(data.beam.name) +
        '/segmentos/' + index + '/n3' + querySuffix(), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(detailPayload(detail))})
        .then(function () { qaStatus.textContent = 'Dados N3 do segmento S' + index + ' salvos.'; button.disabled = false; })
        .catch(function (error) { button.disabled = false; qaStatus.className='fv-qa-status error'; qaStatus.textContent=error.message; throw error; });
    }

    function regenerateN3(detail, button) {
      var index = detail.getAttribute('data-fv-detail'); button.disabled = true; button.textContent = 'Salvando e enfileirando…';
      var chooser = window.escolherModoDesenho ? window.escolherModoDesenho({currentMode:data.visual_mode,description:'Escolha o estilo para regenerar este fundo de viga e manter no N5.'}) : Promise.resolve('NOVA');
      chooser.then(function (visualMode) {
        if (!visualMode) { button.disabled=false; button.textContent='Regenerar N3 deste segmento'; return null; }
        options.visualMode = visualMode;
        return saveN3(detail, button).then(function () {
        return api('/obras/' + encodeURIComponent(options.obraId) + '/fv/' + encodeURIComponent(data.beam.name) +
          '/segmentos/' + index + '/regenerar-n3' + querySuffix(), {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({visual_mode:visualMode})});
        });
      }).then(function (job) {
        if (!job) return;
        qaStatus.textContent = 'Regeneração N3 de S' + index + ' enfileirada · aguardando processamento…';
        function pollJob() {
          fetch('/jobs/' + encodeURIComponent(job.job_id)).then(function(response){return response.json();}).then(function(status){
            var current = status.status || status.estado;
            if (['na_fila','queued','rodando','running'].indexOf(current) >= 0) {
              qaStatus.textContent = 'Regenerando N3 de S' + index + ' · ' + current + '…'; window.setTimeout(pollJob,2500); return;
            }
            button.textContent = 'Regenerar N3 deste segmento'; button.disabled = false;
            if (['concluido','completed','sucesso'].indexOf(current) >= 0) load(root,Object.assign({},options,{initialSegment:index}));
            else { qaStatus.className='fv-qa-status error'; qaStatus.textContent='Regeneração não concluída: '+(status.erro_msg||current||'falha'); }
          }).catch(function(error){button.disabled=false;qaStatus.className='fv-qa-status error';qaStatus.textContent='Falha ao acompanhar N3: '+error.message;});
        }
        pollJob();
      }).catch(function (error) {
        button.disabled = false; button.textContent = 'Regenerar N3 deste segmento';
        qaStatus.className='fv-qa-status error'; qaStatus.textContent='Falha ao regenerar N3: '+error.message;
      });
    }

    function renameBeam() {
      var name = window.prompt('Novo nome do fundo de viga:', data.beam.name);
      if (!name || name.trim().toUpperCase() === data.beam.name.toUpperCase()) return;
      name = name.trim().toUpperCase();
      if (!window.confirm('Renomear ' + data.beam.name + ' para ' + name + ' e atualizar todos os seus segmentos?')) return;
      api('/obras/' + encodeURIComponent(options.obraId) + '/fv/' + encodeURIComponent(data.beam.name) + '/renomear' + querySuffix(), {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({new_name:name, confirmado:true})
      }).then(function (result) {
        if (window.DrillGrade && window.DrillGrade.refreshItems) window.DrillGrade.refreshItems();
        load(root, Object.assign({}, options, {beam:result.new_name, initialSegment:'todos'}));
      }).catch(function (error) { qaStatus.className='fv-qa-status error'; qaStatus.textContent='Falha ao renomear: '+error.message; });
    }

    function startPointing() {
      if (state.layer === 'n3') { qaStatus.textContent = 'Apontamentos estão disponíveis em SA, C1, C2 e C3.'; return; }
      state.pointing = {selected:null}; canvas.classList.add('fv-pointing');
      var editor = root.querySelector('[data-fv-annotation-editor]'); editor.hidden = false;
      root.querySelector('[data-fv-point-label]').textContent = 'Clique no elemento desejado no viewer.';
      root.querySelector('[data-fv-point-text]').focus();
    }

    function choosePoint(event) {
      if (!state.pointing || !state.pz) return false;
      var position = svgPoint(state.pz.svg, event); if (!position) return true;
      var target = event.target; var labelText = target.getAttribute && (target.getAttribute('data-fv-hl') || target.getAttribute('class'));
      state.pointing.selected = {x:position.x, y:position.y, element:(labelText || target.tagName || 'elemento SVG').toString()};
      root.querySelector('[data-fv-point-label]').textContent = state.layer.toUpperCase() + ' · ' +
        (state.segment === 'todos' ? 'Todos' : 'S' + state.segment) + ' · ' + state.pointing.selected.element;
      event.preventDefault(); event.stopPropagation(); return true;
    }

    function validateHuman(button) {
      var targets = (data.segments || []).map(function (segment) { return segment.id; }).filter(Boolean);
      if (!targets.length) return;
      button.disabled = true;
      Promise.all(targets.map(function (itemId) {
        var query = options.pavimento ? '?pavimento=' + encodeURIComponent(options.pavimento) : '';
        return fetch('/obras/' + encodeURIComponent(options.obraId) + '/n1/fundo/' + encodeURIComponent(itemId) +
          '/campo/_item_/validar' + query, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({validado:true})})
          .then(function (response) { if (!response.ok) throw new Error('HTTP ' + response.status); });
      })).then(function () {
        if (window.DrillGrade && window.DrillGrade.refreshItems) window.DrillGrade.refreshItems();
        load(root, options);
      }).catch(function (error) {
        button.disabled = false; qaStatus.className = 'fv-qa-status error';
        qaStatus.textContent = 'Falha na validação humana: ' + error.message;
      });
    }

    function setOneValidation(button, validado) {
      var segment = selectedSaSegment();
      if (!segment || !segment.id) return;
      if (!validado && !window.confirm('Desvalidar o segmento S' + segment.index + '? Ele voltará ao estado pendente.')) return;
      button.disabled = true;
      api('/obras/' + encodeURIComponent(options.obraId) + '/n1/fundo/' + encodeURIComponent(segment.id) +
          '/campo/_item_/validar' + querySuffix(), {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({validado: validado})
          }).then(function () {
        if (window.DrillGrade && window.DrillGrade.refreshItems) window.DrillGrade.refreshItems();
        load(root, Object.assign({}, options, {initialSegment: state.segment}));
      }).catch(function (error) {
        button.disabled = false; qaStatus.className = 'fv-qa-status error';
        qaStatus.textContent = 'Falha ao ' + (validado ? 'validar' : 'desvalidar') + ' segmento: ' + error.message;
      });
    }

    function validateOne(button) { setOneValidation(button, true); }
    function unvalidateOne(button) { setOneValidation(button, false); }

    function adoptLayer(button) {
      var labelName = layerLabel(state.layer);
      if (!window.confirm('Adotar ' + labelName + ' como novo SA? Isso substituirá os segmentos atuais e apagará C1, C2 e C3 desta viga.')) return;
      button.disabled = true; button.textContent = 'Adotando ' + labelName + '…';
      api('/obras/' + encodeURIComponent(options.obraId) + '/fv/' + encodeURIComponent(data.beam.name) +
          '/adotar-camada' + querySuffix(), {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({layer: state.layer, confirmado: true})
          }).then(function () {
        if (window.DrillGrade && window.DrillGrade.refreshItems) window.DrillGrade.refreshItems();
        load(root, Object.assign({}, options, {initialSegment: 'todos'}));
      }).catch(function (error) {
        button.disabled = false; button.textContent = 'Adotar Camada Agentica como SA';
        qaStatus.className = 'fv-qa-status error'; qaStatus.textContent = 'Falha ao adotar camada: ' + error.message;
      });
    }

    function deleteSegment(button) {
      var segment = selectedSaSegment();
      if (!segment) return;
      window.ItemGeometry.delete({classe:'fundo',itemId:segment.id,beam:data.beam.name,
        segmento:segment.index,pavimento:options.pavimento}, false);
    }
    function deleteLayer(button) {
      var layer = state.layer;
      if (['c1', 'c2', 'c3'].indexOf(layer) < 0) return;
      if (!window.confirm('Excluir a camada agentica ' + layer.toUpperCase() + ' de ' + data.beam.name + '? O SA não será alterado.')) return;
      button.disabled = true; button.textContent = 'Excluindo…';
      api('/obras/' + encodeURIComponent(options.obraId) + '/fv/' + encodeURIComponent(data.beam.name) +
          '/excluir-camada' + querySuffix(), {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({layer: layer, confirmado: true})
          }).then(function () {
        load(root, Object.assign({}, options, {initialSegment: 'todos'}));
      }).catch(function (error) {
        button.disabled = false; button.textContent = 'Excluir Camada Agentica';
        qaStatus.className = 'fv-qa-status error'; qaStatus.textContent = 'Falha ao excluir camada: ' + error.message;
      });
    }

    function svgPoint(svg, event) {
      var point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
      var matrix = svg.getScreenCTM();
      return matrix ? point.matrixTransform(matrix.inverse()) : null;
    }

    function editOrtho(point) {
      if (!state.editing || !state.editing.ortho || !state.editing.points.length) return point;
      var last = state.editing.points[state.editing.points.length - 1];
      return Math.abs(point.x - last.x) >= Math.abs(point.y - last.y)
        ? {x: point.x, y: last.y} : {x: last.x, y: point.y};
    }

    function editPoint(event) {
      var raw = svgPoint(state.pz.svg, event); if (!raw) return null;
      var hit = null;
      if (state.editing.osnapReady && typeof window.nearestSnapClient === 'function') {
        hit = window.nearestSnapClient(state.pz.svg, event.clientX, event.clientY, raw);
      }
      // Mesma prioridade do editor estrutural: OSNAP vence o travamento Ortho.
      return hit ? {x: hit.x, y: hit.y, snapped: true} : editOrtho(raw);
    }

    function drawDraft() {
      if (!state.editing || !state.pz) return;
      var svg = state.pz.svg;
      var old = svg.querySelector('[data-fv-edit-draft]'); if (old) old.remove();
      if (!state.editing.points.length && !state.editing.hover) return;
      var draftPoints = state.editing.points.slice();
      if (state.editing.hover) draftPoints.push(state.editing.hover);
      var group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      group.setAttribute('data-fv-edit-draft', '1');
      var node = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      node.setAttribute('points', draftPoints.map(function (p) { return p.x + ',' + p.y; }).join(' '));
      node.setAttribute('fill', state.editing.points.length > 2 ? 'rgba(23,92,211,.28)' : 'none');
      node.setAttribute('stroke', '#4ea1ff'); node.setAttribute('stroke-width', '3');
      node.setAttribute('vector-effect', 'non-scaling-stroke'); group.appendChild(node);
      state.editing.points.forEach(function (point) {
        var marker = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        marker.setAttribute('cx', point.x); marker.setAttribute('cy', point.y);
        marker.setAttribute('r', typeof window.screenPxToSvgUnits === 'function'
          ? window.screenPxToSvgUnits(svg, 2.2) : '2');
        marker.setAttribute('fill', '#4ea1ff'); group.appendChild(marker);
      });
      if (state.editing.hover && state.editing.hover.snapped) {
        var snapMarker = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        snapMarker.setAttribute('cx', state.editing.hover.x); snapMarker.setAttribute('cy', state.editing.hover.y);
        snapMarker.setAttribute('r', typeof window.screenPxToSvgUnits === 'function'
          ? window.screenPxToSvgUnits(svg, 3.45) : '3');
        snapMarker.setAttribute('fill', '#22c55e'); group.appendChild(snapMarker);
      }
      svg.appendChild(group);
    }

    function finishEdit() {
      if (!state.editing || state.editing.points.length < 3) {
        qaStatus.textContent = 'Marque ao menos 3 pontos antes de concluir.'; return;
      }
      var transform = state.editing.transform;
      var bbox = transform.bbox_dxf;
      var points = state.editing.points.map(function (point) {
        return [bbox[0] + point.x / transform.largura_px * (bbox[2] - bbox[0]),
                bbox[3] - point.y / transform.altura_px * (bbox[3] - bbox[1])];
      });
      window.ItemGeometry.save({classe:'fundo',itemId:selectedSaSegment().id,pavimento:options.pavimento}, points).then(function () {
        if (window.DrillGrade && window.DrillGrade.refreshItems) window.DrillGrade.refreshItems();
        load(root, Object.assign({}, options, {initialSegment: state.segment}));
      }).catch(function (error) {
        qaStatus.className = 'fv-qa-status error'; qaStatus.textContent = 'Falha ao editar segmento: ' + error.message;
      });
    }

    function startEdit(button) {
      if (!selectedSaSegment()) return;
      button.disabled = true; button.textContent = 'Carregando estrutural…';
      api('/obras/' + encodeURIComponent(options.obraId) + '/viewer/' + encodeURIComponent(options.pavimento))
        .then(function (viewer) {
          return fetch(viewer.svg_url).then(function (response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.text().then(function (svgText) { return {viewer: viewer, svgText: svgText}; });
          });
        }).then(function (payload) {
          inner.innerHTML = cleanSvg(payload.svgText);
          state.pz = initPanZoom(canvas);
          state.editing = {points: [], hover: null, ortho: false, osnapReady: false,
            snapCount: 0, transform: payload.viewer.transform};
          canvas.classList.add('fv-editing'); canvas.focus();
          label.textContent = 'Editando ' + data.beam.name + ' · S' + state.segment;
          qaStatus.className = 'fv-qa-status';
          qaStatus.textContent = 'Clique os vértices no estrutural. Botão do meio arrasta o viewer · OSNAP automático · Ortho (F8) · Enter salva · Esc cancela · botão direito desfaz.';
          renderLayerActions();
          if (typeof window.rebuildSnapIndex === 'function') {
            window.rebuildSnapIndex(state.pz.svg, {async: true, onDone: function (count) {
              if (!state.editing) return;
              state.editing.osnapReady = true; state.editing.snapCount = count || 0;
              renderLayerActions();
            }});
          } else {
            state.editing.osnapReady = true; renderLayerActions();
          }
        }).catch(function (error) {
          button.disabled = false; button.textContent = 'Editar Segmento';
          qaStatus.className = 'fv-qa-status error'; qaStatus.textContent = 'Falha ao abrir editor: ' + error.message;
        });
    }

    function showLayer(name) {
      if (!layers[name] || (!layers[name].available && name !== 'n3')) return;
      restoreHighlights();
      state.layer = name;
      inner.innerHTML = cleanSvg(layers[name].svg) || (name === 'n3'
        ? '<div class="lv-canvas-empty"><strong>Modo ' + (data.visual_mode === 'INI' ? 'Ini' : 'Nova') + ' ainda não gerado.</strong><br>Solicite a regeneração deste fundo nesse modo para visualizar ou baixar.</div>'
        : '');
      root.querySelectorAll('[data-fv-layer]').forEach(function (button) {
        button.classList.toggle('active', button.getAttribute('data-fv-layer') === name);
      });
      state.editing = null; canvas.classList.remove('fv-editing');
      renderSegmentTabs(); renderLayerActions();
      state.pz = initPanZoom(canvas);
      if (name === 'n3' && window.aplicarTagModoDesenho) window.aplicarTagModoDesenho(canvas, data.visual_mode,{onChange:function(mode){load(root,Object.assign({},options,{initialLayer:'n3',visualMode:mode}));}});
      renderAnnotationMarkers();
      label.textContent = layerLabel(name) + ' · ' + (state.segment === 'todos' ? 'Todos' : 'S' + state.segment);
      window.requestAnimationFrame(function () { focusSegment(state.pz, name, state.segment); });
    }

    function renderAnnotationMarkers() {
      if (!state.pz || !state.pz.svg) return;
      var svg = state.pz.svg;
      var old = svg.querySelector('[data-fv-annotation-markers]'); if (old) old.remove();
      var points = (data.annotations || []).filter(function (point) {
        return point.layer === state.layer && (state.segment === 'todos' || point.segment === 'todos' || String(point.segment) === String(state.segment));
      });
      if (!points.length) return;
      var ns='http://www.w3.org/2000/svg', group=document.createElementNS(ns,'g');
      group.setAttribute('data-fv-annotation-markers',''); group.setAttribute('pointer-events','none');
      points.forEach(function(point,index){
        var circle=document.createElementNS(ns,'circle'); circle.setAttribute('cx',point.x); circle.setAttribute('cy',point.y);
        circle.setAttribute('r','7'); circle.setAttribute('fill','#ef4444'); circle.setAttribute('stroke','#fff'); circle.setAttribute('stroke-width','2');
        var textNode=document.createElementNS(ns,'text'); textNode.setAttribute('x',Number(point.x)+10); textNode.setAttribute('y',Number(point.y)-10);
        textNode.setAttribute('fill','#fff'); textNode.setAttribute('stroke','#991b1b'); textNode.setAttribute('paint-order','stroke');
        textNode.setAttribute('stroke-width','3'); textNode.setAttribute('font-size','12'); textNode.setAttribute('font-weight','700');
        textNode.textContent='A'+(index+1); group.appendChild(circle); group.appendChild(textNode);
      });
      svg.appendChild(group);
    }

    function restoreHighlights() {
      state.hiddenHighlights.forEach(function (node) {
        node.style.visibility = node.getAttribute('data-fv-old-visibility') || '';
        node.removeAttribute('data-fv-old-visibility');
      });
      state.hiddenHighlights = [];
      var button = root.querySelector('[data-fv-toggle-highlight]');
      if (button) {
        button.classList.remove('active');
        button.textContent = 'Ocultar destaque · ' + (state.segment === 'todos' ? 'Todos' : 'S' + state.segment);
      }
    }

    function proposalNodes(svg, segment) {
      var polygons = Array.prototype.slice.call(svg.querySelectorAll('#qa-proposta polygon[data-prop-label]'));
      if (segment !== 'todos') polygons = polygons.filter(function (node) {
        return (node.getAttribute('data-prop-label') || '').toUpperCase() === ('P' + segment).toUpperCase();
      });
      var nodes = [];
      polygons.forEach(function (polygon) {
        nodes.push(polygon);
        var sibling = polygon.nextElementSibling;
        while (sibling && sibling.tagName.toLowerCase() !== 'polygon') {
          // Preserva o grupo que contém a tag textual; remove só contorno, guia e ponto.
          if (['line', 'circle'].indexOf(sibling.tagName.toLowerCase()) >= 0) nodes.push(sibling);
          sibling = sibling.nextElementSibling;
        }
      });
      return nodes;
    }

    function highlightNodes() {
      if (!state.pz) return [];
      var svg = state.pz.svg;
      var nodes = [];
      var selector = state.segment === 'todos'
        ? '.fv-web-sa-segment polygon'
        : '.fv-web-sa-segment[data-fv-seg="' + state.segment + '"] polygon';
      nodes = Array.prototype.slice.call(svg.querySelectorAll(selector));
      if (!nodes.length) nodes = proposalNodes(svg, state.segment);
      if (!nodes.length) {
        // O renderer HI-FI marca face/aresta/tag, mas fichas históricas não
        // trazem o índice no atributo. A ordem de emissão é a ordem S1..Sn;
        // numeramos cada família no DOM e preservamos integralmente as tags.
        ['face', 'edge'].forEach(function (kind) {
          Array.prototype.slice.call(svg.querySelectorAll('[data-fv-hl="' + kind + '"]'))
            .forEach(function (node, index) {
              if (!node.getAttribute('data-fv-seg')) node.setAttribute('data-fv-seg', String(index + 1));
              if (state.segment === 'todos' || node.getAttribute('data-fv-seg') === state.segment) nodes.push(node);
            });
        });
      }
      if (!nodes.length && state.layer !== 'n3') {
        // Compatibilidade com propostas HI-FI antigas (Matplotlib): cada tag S#
        // vem depois dos grupos do conector. Não escondemos o próprio grupo de texto.
        Array.prototype.slice.call(svg.querySelectorAll('text')).forEach(function (text) {
          var value = (text.textContent || '').trim().toUpperCase();
          if (!/^S\d+$/.test(value)) return;
          if (state.segment !== 'todos' && value !== ('S' + state.segment).toUpperCase()) return;
          var tagGroup = text.closest('g');
          var cursor = tagGroup && tagGroup.previousElementSibling;
          for (var i = 0; cursor && i < 2; i += 1, cursor = cursor.previousElementSibling) {
            if (cursor.querySelector && cursor.querySelector('path,use,line,circle,polygon,polyline')) nodes.push(cursor);
          }
        });
      }
      return nodes.filter(function (node, index) { return nodes.indexOf(node) === index; });
    }

    function toggleHighlights(button) {
      if (state.hiddenHighlights.length) { restoreHighlights(); return; }
      var nodes = highlightNodes();
      if (!nodes.length) {
        qaStatus.className = 'fv-qa-status';
        qaStatus.textContent = 'Esta camada não possui contorno de destaque separável; o desenho foi preservado.';
        return;
      }
      nodes.forEach(function (node) {
        node.setAttribute('data-fv-old-visibility', node.style.visibility || '');
        node.style.visibility = 'hidden';
      });
      state.hiddenHighlights = nodes;
      button.classList.add('active');
      button.textContent = 'Mostrar destaque · ' + (state.segment === 'todos' ? 'Todos' : 'S' + state.segment);
    }

    function selectSegment(segment, expand) {
      restoreHighlights();
      state.segment = String(segment);
      root.querySelectorAll('[data-fv-segment], [data-fv-detail]').forEach(function (row) {
        var key = row.getAttribute('data-fv-segment') || row.getAttribute('data-fv-detail');
        if (row.hasAttribute('data-fv-segment')) row.hidden = state.segment !== 'todos' && key !== state.segment;
        else if (state.segment !== 'todos' && key !== state.segment) row.hidden = true;
      });
      root.querySelectorAll('[data-fv-focus]').forEach(function (button) {
        button.classList.toggle('active', button.getAttribute('data-fv-focus') === state.segment);
      });
      root.querySelectorAll('.fv-web-seg-row').forEach(function (row) {
        row.classList.toggle('selected', row.getAttribute('data-fv-segment') === state.segment);
      });
      if (expand && state.segment !== 'todos') {
        var row = root.querySelector('[data-fv-segment="' + state.segment + '"]');
        var detail = root.querySelector('[data-fv-detail="' + state.segment + '"]');
        if (row && detail) {
          var opening = detail.hidden;
          detail.hidden = !opening;
          row.setAttribute('aria-expanded', opening ? 'true' : 'false');
          row.classList.toggle('expanded', opening);
        }
      }
      label.textContent = layerLabel(state.layer) + ' · ' + (state.segment === 'todos' ? 'Todos' : 'S' + state.segment);
      focusSegment(state.pz, state.layer, state.segment);
      renderAnnotationMarkers();
      renderLayerActions();
    }

    root.querySelectorAll('[data-fv-layer]').forEach(function (button) {
      button.addEventListener('click', function () { showLayer(button.getAttribute('data-fv-layer')); });
    });
    root.querySelector('[data-fv-segtabs]').addEventListener('click', function (event) {
      var button = event.target.closest('[data-fv-focus]');
      if (button) selectSegment(button.getAttribute('data-fv-focus'), false);
    });
    root.querySelector('[data-fv-layer-actions]').addEventListener('click', function (event) {
      var button = event.target.closest('button'); if (!button) return;
      if (button.matches('[data-fv-adopt]')) adoptLayer(button);
      else if (button.matches('[data-fv-delete-layer]')) deleteLayer(button);
      else if (button.matches('[data-fv-validate-all]')) validateHuman(button);
      else if (button.matches('[data-fv-validate-one]')) validateOne(button);
      else if (button.matches('[data-fv-unvalidate-one]')) unvalidateOne(button);
      else if (button.matches('[data-fv-edit]')) startEdit(button);
      else if (button.matches('[data-fv-delete]')) deleteSegment(button);
      else if (button.matches('[data-fv-point]')) startPointing();
      else if (button.matches('[data-fv-save-edit]')) finishEdit();
      else if (button.matches('[data-fv-edit-ortho]')) {
        state.editing.ortho = !state.editing.ortho; renderLayerActions(); drawDraft(); canvas.focus();
      }
      else if (button.matches('[data-fv-cancel-edit]')) showLayer('sa');
    });
    canvas.addEventListener('click', function (event) {
      if (choosePoint(event)) return;
      if (!state.editing || !state.pz) return;
      if (event.target.closest && event.target.closest('button')) return;
      var point = editPoint(event); if (!point) return;
      var last = state.editing.points[state.editing.points.length - 1];
      if (!last || Math.abs(last.x - point.x) > 0.0001 || Math.abs(last.y - point.y) > 0.0001) {
        state.editing.points.push({x: point.x, y: point.y});
      }
      state.editing.hover = null; drawDraft();
    });
    canvas.addEventListener('pointermove', function (event) {
      if (!state.editing || !state.pz) return;
      if (state.pz.isDragging && state.pz.isDragging()) return;
      state.editing.hover = editPoint(event); drawDraft();
    });
    canvas.addEventListener('pointerleave', function () {
      if (!state.editing) return; state.editing.hover = null; drawDraft();
    });
    canvas.addEventListener('keydown', function (event) {
      if (!state.editing) return;
      if (event.key === 'F8') {
        event.preventDefault(); state.editing.ortho = !state.editing.ortho;
        renderLayerActions(); drawDraft(); return;
      }
      if (event.key === 'Enter') { event.preventDefault(); finishEdit(); }
      if (event.key === 'Escape') { event.preventDefault(); showLayer('sa'); }
    });
    canvas.addEventListener('contextmenu', function (event) {
      if (!state.editing) return;
      event.preventDefault(); state.editing.points.pop(); state.editing.hover = null; drawDraft();
    });
    root.querySelectorAll('.fv-web-seg-row').forEach(function (row) {
      function activate() { selectSegment(row.getAttribute('data-fv-segment'), true); }
      row.addEventListener('click', activate);
      row.addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); }
      });
    });
    root.querySelector('.fv-web-table-card').addEventListener('click', function (event) {
      var button = event.target.closest('button'); if (!button) return;
      if (button.matches('[data-fv-table-validate-all]')) { validateHuman(button); return; }
      var detail = button.closest('[data-fv-detail]'); if (!detail) return;
      if (button.matches('[data-fv-add-chamfer]')) {
        var list = detail.querySelector('[data-fv-feature-list="chamfer"]');
        list.querySelectorAll('.fv-web-empty').forEach(function(n){n.remove();});
        list.insertAdjacentHTML('beforeend','<div class="fv-n3-feature-row" data-fv-chamfer><select><option value="te">Topo esquerdo</option><option value="fe">Fundo esquerdo</option><option value="td">Topo direito</option><option value="fd">Fundo direito</option></select><input type="number" min="0.001" step="0.1" placeholder="tamanho"><button type="button" data-fv-remove-feature>×</button></div>');
      } else if (button.matches('[data-fv-add-opening]')) {
        var openings = detail.querySelector('[data-fv-feature-list="opening"]');
        openings.querySelectorAll('.fv-web-empty').forEach(function(n){n.remove();});
        openings.insertAdjacentHTML('beforeend','<div class="fv-n3-feature-row openings" data-fv-opening><input type="number" min="0" step="0.1" placeholder="posição"><input type="number" min="0.001" step="0.1" placeholder="largura"><input type="number" min="0.001" step="0.1" placeholder="altura"><button type="button" data-fv-remove-feature>×</button></div>');
      } else if (button.matches('[data-fv-remove-feature]')) button.parentElement.remove();
      else if (button.matches('[data-fv-save-n3]')) saveN3(detail, button);
      else if (button.matches('[data-fv-regenerate-n3]')) regenerateN3(detail, button);
      else if (button.matches('[data-fv-detail-validate]')) {
        state.segment = detail.getAttribute('data-fv-detail'); validateOne(button);
      } else if (button.matches('[data-fv-detail-unvalidate]')) {
        state.segment = detail.getAttribute('data-fv-detail'); unvalidateOne(button);
      }
    });
    root.querySelector('[data-fv-reset]').addEventListener('click', function () { if (state.pz) state.pz.reset(); });
    root.querySelector('[data-fv-toggle-highlight]').addEventListener('click', function () {
      toggleHighlights(this);
    });
    root.querySelectorAll('[data-fv-nav]').forEach(function (button) {
      button.addEventListener('click', function () {
        var target = data.beam[button.getAttribute('data-fv-nav')];
        if (target) load(root, Object.assign({}, options, {beam: target, initialSegment: 'todos'}));
      });
    });
    root.querySelectorAll('[data-fv-qa-layer]').forEach(function (button) {
      button.addEventListener('click', function () { requestQa(button, button.getAttribute('data-fv-qa-layer')); });
    });
    root.querySelector('[data-fv-save-notes]').addEventListener('click', function () { saveNotes(true); });
    root.querySelector('[data-fv-rename]').addEventListener('click', renameBeam);
    root.querySelector('[data-fv-delete-beam]').addEventListener('click', function () {
      window.ItemGeometry.delete({classe:'fundo',itemId:data.beam.name,beam:data.beam.name,pavimento:options.pavimento}, true);
    });
    root.querySelector('[data-fv-cancel-point]').addEventListener('click', function () {
      state.pointing=null; canvas.classList.remove('fv-pointing'); root.querySelector('[data-fv-annotation-editor]').hidden=true;
    });
    root.querySelector('[data-fv-save-point]').addEventListener('click', function () {
      var text = root.querySelector('[data-fv-point-text]').value.trim();
      if (!state.pointing || !state.pointing.selected || !text) { qaStatus.textContent='Selecione um elemento e escreva a observação.'; return; }
      var selected = state.pointing.selected;
      api('/obras/'+encodeURIComponent(options.obraId)+'/fv/'+encodeURIComponent(data.beam.name)+'/apontamentos'+querySuffix(), {
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({layer:state.layer,segment:state.segment,x:selected.x,y:selected.y,element:selected.element,text:text})
      }).then(function(){load(root,Object.assign({},options,{initialSegment:state.segment}));})
        .catch(function(error){qaStatus.className='fv-qa-status error';qaStatus.textContent=error.message;});
    });
    root.querySelector('[data-fv-annotations]').addEventListener('click', function(event){
      var button=event.target.closest('[data-fv-delete-point]'); if(!button)return;
      var id=button.closest('[data-fv-annotation]').getAttribute('data-fv-annotation');
      api('/obras/'+encodeURIComponent(options.obraId)+'/fv/'+encodeURIComponent(data.beam.name)+'/apontamentos/'+encodeURIComponent(id)+querySuffix(),{method:'DELETE'})
        .then(function(){load(root,Object.assign({},options,{initialSegment:state.segment}));});
    });
    var requestedLayer = state.layer;
    showLayer(layers[requestedLayer] && (layers[requestedLayer].available || requestedLayer === 'n3')
      ? requestedLayer
      : (layers.sa && layers.sa.available ? 'sa' : Object.keys(layers).filter(function (key) { return layers[key].available; })[0]));
    if (state.segment !== 'todos') selectSegment(state.segment, true);
  }

  function load(root, options) {
    root.innerHTML = '<div class="fv-web-loading"><i></i><span>Montando ficha HI-FI de ' + esc(options.beam) + '…</span></div>';
    var query = options.pavimento ? '?pavimento=' + encodeURIComponent(options.pavimento) : '';
    if (options.visualMode) query += (query ? '&' : '?') + 'visual_mode=' + encodeURIComponent(options.visualMode);
    fetch('/obras/' + encodeURIComponent(options.obraId) + '/fv/' + encodeURIComponent(options.beam) + query)
      .then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) throw new Error(body.detail || ('HTTP ' + response.status));
          return body;
        });
      })
      .then(function (data) { root.innerHTML = frame(data); bind(root, options, data); })
      .catch(function (error) {
        root.innerHTML = '<div class="fv-web-error"><strong>Não foi possível abrir a ficha de fundo.</strong><span>' + esc(error.message) + '</span>' +
          '<button type="button">Tentar novamente</button></div>';
        root.querySelector('button').addEventListener('click', function () { load(root, options); });
      });
  }

  window.FvFicha = {mount: load, cleanSvg: cleanSvg};
})();
