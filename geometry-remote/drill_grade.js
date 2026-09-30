/**
 * Drill grade — painel esquerdo em 1 coluna (aprovado no mock 2026-07).
 * Conteúdo central intacto: usa window.selecionarPavimento, carregarDetalhe*,
 * mostrarDetalhe, renderizarDetalheRecorte, botões de processar legados.
 */
(function () {
  'use strict';

  var root = document.getElementById('drill-root');
  if (!root) return;

  var OBRA_ID = root.getAttribute('data-obra');
  var OBRA_COMPORTAMENTO = root.getAttribute('data-comportamento') || 'misto';
  function classePermitida(c) {
    return OBRA_COMPORTAMENTO === 'misto' || !/_(para|passa)$/.test(c) || c.endsWith('_' + OBRA_COMPORTAMENTO);
  }
  var OBRA_NOME = root.getAttribute('data-obra-nome') || 'Obra';

  var VIGA_CLASSES = {
    fundo: 1,
    lateral_a_para: 1,
    lateral_b_para: 1,
    lateral_a_passa: 1,
    lateral_b_passa: 1,
    laterais_para: 1,
    laterais_passa: 1
  };

  var LATERAIS_COMBINADAS = {
    laterais_para: {
      titulo: 'Segmentos Lateral A.B. · Para',
      a: 'lateral_a_para',
      b: 'lateral_b_para'
    },
    laterais_passa: {
      titulo: 'Segmentos Lateral A.B. · Passa',
      a: 'lateral_a_passa',
      b: 'lateral_b_passa'
    }
  };

  var SA_GROUPS = [
    { nome: 'Estrutura', ids: ['pilares', 'lajes', 'fundo', 'laterais_para', 'laterais_passa'] },
  ];

  var N3_GROUPS = [
    { nome: 'Pilares', ids: ['pilares_n3_para', 'pilares_n3_passa'] },
    { nome: 'Lajes', ids: ['lajes'] },
    { nome: 'Vigas', ids: ['fundo', 'lateral_a_para', 'lateral_a_passa', 'lateral_b_para', 'lateral_b_passa'] }
  ];

  var ETAPAS = [
    { id: 'sa', short: 'SA', nome: 'Interpretação', hubLabel: 'Detalhamento Etapas', stage: 'n1', btn: 'btn-rodar-sa',
      procLabel: 'Processar Interpretação · SA (Pavimento) →',
      procStatusId: 'progresso-recortes-pavimento', procBarId: 'progresso-recortes-barra' },
    { id: 'n3', short: 'N3', nome: 'Desenho', stage: 'n3', btn: 'btn-rodar-n3',
      procLabel: 'Processar Desenho · N3 (Pavimento) →',
      procStatusId: 'progresso-n1-pavimento', procBarId: 'progresso-n1-barra' },
    { id: 'n5', short: 'N5', nome: 'Unificação', stage: 'n5', btn: null,
      procLabel: 'Processar todas as unificações (Pavimento) →',
      procStatusId: 'progresso-n3-txt', procBarId: 'progresso-n3-bar' }
  ];

  var state = {
    level: 'pavs',
    pav: null,
    etapa: null,
    classe: null,
    classesCache: null,
    itens: [],
    vigaKey: null,
    itemId: null,
    rightTorre: false,
    createClasse: null,
    selDoc: null,
    analysisDoc: null,
    qaRuns: {},
    qaControlFeedback: {}
  };
  var preprocState = null;
  var preprocPolling = false;
  var preprocSubmitting = false;
  var submittingMotors = {};

  function motorRequestKey(stage, classe, pav) {
    return [pav || '', classe || 'ALL', stage].join(':');
  }

  function localMotorRequest(classe, pav) {
    return Object.keys(submittingMotors).map(function (key) { return submittingMotors[key]; }).filter(function (request) {
      return request.pav === pav && (!request.classe || request.classe === classe);
    })[0] || null;
  }

  function refreshPreprocessamento() {
    if (!state.pav || state.level !== 'hub' || preprocPolling || preprocSubmitting) return;
    var pav = state.pav;
    preprocPolling = true;
    fetch('/obras/' + encodeURIComponent(OBRA_ID) + '/preprocessamento?pavimento=' + encodeURIComponent(pav))
      .then(function (response) { if (!response.ok) throw new Error('HTTP ' + response.status); return response.json(); })
      .then(function (data) {
        if (state.pav !== pav || preprocSubmitting) return;
        var next = JSON.stringify(data);
        if (next !== JSON.stringify(preprocState)) { preprocState = data; render(); }
      })
      .catch(function () { /* Mantém último estado; novo polling tentará novamente. */ })
      .finally(function () { preprocPolling = false; });
  }

  function enqueuePreprocessamento() {
    if (!state.pav || preprocSubmitting) return;
    var requestPav = state.pav;
    var docs = recortesDoPav(state.pav).filter(function (doc) { return doc.tipo === 'recorte'; });
    var torres = docs.filter(function (doc) { return doc.kind === 'torre'; });
    if (!torres.length) { window.alert('Crie e valide uma torre antes de pré-processar.'); return; }
    var pendentes = docs.filter(function (doc) {
      return !doc.validado && !(doc.item && doc.item.item_id === 'convencao_niveis');
    });
    var message = 'Pré-processar ' + state.pav + ' com ' + torres.length + ' torre(s) e ' + docs.length +
      ' recorte(s)? A coleta usa os brutos e as torres e executa a interpretação contextual necessária para obter os níveis antes do SA de produção.';
    if (pendentes.length) message += '\nHá ' + pendentes.length + ' recorte(s) pendente(s); o servidor recusará até validar.';
    if (!window.confirm(message)) return;
    preprocSubmitting = true;
    preprocState = {status: 'na_fila', job_id: null, result: null, error: null, enabled: true};
    render();
    fetch('/obras/' + encodeURIComponent(OBRA_ID) + '/preprocessamento/jobs', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({pavimento: requestPav})
    }).then(function (response) { return response.json().then(function (data) {
      if (!response.ok) throw new Error(data.detail || ('HTTP ' + response.status));
      return data;
    }); }).then(function (data) {
      if (!window._todosJobs) window._todosJobs = [];
      if (!window._todosJobs.some(function (job) { return job.id === data.job_id; })) {
        window._todosJobs.push({id: data.job_id, status: 'na_fila',
          meta: {etapa: 'preprocessamento', pav: requestPav}, enfileirado_em: new Date().toISOString()});
      }
      if (state.pav === requestPav) preprocState.job_id = data.job_id;
    }).catch(function (error) {
      if (state.pav === requestPav) preprocState = {
        status: 'falhou', result: null, enabled: true, error: error.message
      };
      window.alert('Não foi possível enfileirar: ' + error.message);
    }).finally(function () {
      preprocSubmitting = false;
      render();
      refreshPreprocessamento();
    });
  }

  function showLevelInventory() {
    if (!state.pav) return;
    state.level = 'hub';
    state.etapa = null; state.classe = null; state.itens = [];
    state.itemId = null; state.vigaKey = null; state.rightTorre = false;
    state.selDoc = 'preproc:niveis';
    render();
    ensureDocsDetalhe();
    if (window.mostrarDetalhe) window.mostrarDetalhe('triagem');
    var det = document.getElementById('docs-detalhe');
    if (!det) return;
    var pav = state.pav;
    var crop = recortesDoPav(pav).filter(function (doc) {
      return doc.tipo === 'recorte' && doc.item && doc.item.item_id === 'convencao_niveis';
    })[0];
    if (crop && window.renderizarDetalheRecorte) {
      window.renderizarDetalheRecorte({
        titulo: crop.item.titulo || crop.nome,
        categoria: 'Detalhes e Convenções', pavimento: pav,
        brutoId: crop.bruto_id, itemId: crop.item.item_id
      });
      mountRecorteTabs(crop.id);
    } else det.innerHTML = '';
    var section = document.createElement('section');
    section.innerHTML = '<div class="preproc-level-page" aria-label="Convenção de Níveis">' +
      '<header><div><small>Pré-processamento · ' + esc(pavimentoTitulo(pav)) + '</small>' +
      '<h2>Convenção de Níveis</h2></div>' +
      '<button type="button" class="preproc-level-back">← Recortes</button></header>' +
      '<div class="preproc-level-body" role="status">Carregando listagem…</div></div>';
    det.appendChild(section);
    section.querySelector('.preproc-level-back').onclick = function () {
      var previous = pickDefaultDoc(state.pav);
      if (previous) selectRecorteDoc(previous.id);
      else { state.selDoc = null; render(); det.innerHTML = ''; }
    };
    var body = section.querySelector('.preproc-level-body');
    function cell(value) { return '<td>' + esc(String(value == null ? '—' : value)) + '</td>'; }
    function candidateText(candidates) {
      return (candidates || []).map(function (c) { return c.value + ' ' + (c.unit || '') + ' (' + (c.slab_display_name || c.slab_item_id) + ')'; }).join('; ');
    }
    fetch('/obras/' + encodeURIComponent(OBRA_ID) + '/preprocessamento/niveis?pavimento=' + encodeURIComponent(pav))
      .then(function (response) { return response.json().then(function (data) {
        if (!response.ok) throw new Error(data.detail || ('HTTP ' + response.status));
        return data;
      }); }).then(function (data) {
        if (!body.isConnected || state.selDoc !== 'preproc:niveis' || state.pav !== pav) return;
        if (data.status === 'not_started') {
          body.innerHTML = '<p class="preproc-level-empty">Execute Pré-processar pavimento para montar a listagem. O recorte de níveis não é obrigatório.</p>';
          return;
        }
        var html = data.status === 'stale' ? '<p class="preproc-level-warning">Fontes alteradas; execute o pré-processamento novamente.</p>' : '';
        (data.towers || []).forEach(function (tower, index) {
          var ref = tower.reference || {}, coverage = tower.coverage || {}, seg = tower.segment_coverage || {};
          html += '<h3>Torre ' + (index + 1) + '</h3>' +
            '<p>Referência do pavimento: ' + (ref.status === 'direct_local_reference' ?
              esc(ref.base + ' → ' + ref.top + ' ' + ref.unit + ' · altura ' + ref.height + ' m (referência local)') :
              'indeterminada') + '. ' + esc(String(coverage.slab_levels_observed || 0)) +
            ' cota(s) de laje observada(s); ' + esc(String(seg.candidate_segments || 0)) +
            ' segmento(s) candidato(s) de viga.' + (tower.sa_evidence ?
              ' Coleta contextual: ' + esc(String(tower.sa_evidence.items_with_levels)) + ' itens com níveis e ' +
              esc(String(tower.sa_evidence.segments)) + ' segmentos; ' + esc(String(seg.estimated_segments || 0)) + ' estimados.' : '') + '</p>' +
            '<div class="preproc-level-tower" data-tower="' + index + '">' +
            '<div class="preproc-level-tabs" role="tablist" aria-label="Classes da Torre ' + (index + 1) + '">';
          var classes = [{key:'pillar', label:'Pilares'}, {key:'beam', label:'Vigas'}, {key:'slab', label:'Lajes'}];
          var groups = {};
          // Uma linha por nome/classe na torre; identidades e evidências continuam nos detalhes.
          (tower.items || []).forEach(function (item) {
            var key = item.item_class + ':' + (item.display_name || item.item_id);
            if (!groups[key]) groups[key] = {item_class:item.item_class, display_name:item.display_name,
              item_id:item.item_id, source_item_ids:[], levels:[], segments:[]};
            if (groups[key].source_item_ids.indexOf(item.item_id) < 0) groups[key].source_item_ids.push(item.item_id);
            ['levels','segments'].forEach(function (field) {
              (item[field] || []).forEach(function (part) {
                if (!groups[key][field].some(function (p) { return JSON.stringify(p) === JSON.stringify(part); }))
                  groups[key][field].push(part);
              });
            });
          });
          var items = Object.keys(groups).map(function (key) { return groups[key]; }).sort(function (a,b) {
            return String(a.display_name).localeCompare(String(b.display_name), 'pt-BR', {numeric:true});
          });
          classes.forEach(function (cls, ci) {
            var count = items.filter(function (item) { return item.item_class === cls.key; }).length;
            html += '<button type="button" role="tab" id="level-tab-' + index + '-' + ci + '" aria-controls="level-panel-' + index + '-' + ci +
              '" aria-selected="' + (ci === 0) + '" tabindex="' + (ci === 0 ? '0' : '-1') + '" data-class="' + cls.key + '">' +
              esc(cls.label) + '<span>' + count + '</span></button>';
          });
          html += '</div><p class="preproc-level-legend"><span class="level-good">● Nível observado</span> ' +
            '<span class="level-doubt">● Revisar / duvidoso</span> <span class="level-pending">● Pendente</span> ' +
            '<span class="level-conflict">● Conflito</span></p>';
          var partNames = {base:'Base', top:'Topo', slab_level:'Nível da laje', beam_top:'Topo da viga', beam_bottom:'Fundo físico',
            fundo:'Referência FV', lateral_a_para:'Lateral A Para', lateral_b_para:'Lateral B Para',
            lateral_a_passa:'Lateral A Passa', lateral_b_passa:'Lateral B Passa'};
          var statusNames = {unknown:'Pendente', observed_text:'Observado no desenho', conflict:'Conflito', raw_unreferenced:'Texto sem referência',
            candidate:'Candidato não validado', sa_evidence:'Evidência coletada', inferred:'Inferido · revisar',
            estimated:'Estimado · revisar', floor_reference:'Referência do pavimento', human_review:'Revisão humana',
            not_applicable:'Não se aplica neste pavimento'};
          function levelValue(fact) {
            return fact.value != null ? fact.value + ' ' + (fact.unit || '') :
              fact.status === 'not_applicable' ? 'Não se aplica' :
              (fact.raw_values || []).length ? 'Texto: ' + fact.raw_values.join(', ') : 'Não determinado';
          }
          function factTone(fact) {
            if (fact.status === 'conflict') return 'conflict';
            if (fact.status === 'not_applicable') return 'good';
            if (fact.value == null) return (fact.adjacent_slab_candidates || []).length || (fact.raw_values || []).length ? 'doubt' : 'pending';
            return (fact.warnings || []).length ? 'doubt' : 'good';
          }
          function confidence(fact) {
            var pct = fact.confidence_pct;
            if (pct == null) pct = fact.conf_pct;
            if (typeof pct !== 'number' || !isFinite(pct) || pct < 0 || pct > 100) return 'Não calculada';
            return pct.toLocaleString('pt-BR', {maximumFractionDigits:1}) + '%';
          }
          classes.forEach(function (cls, ci) {
            var parts = cls.key === 'pillar' ? ['base','top'] : cls.key === 'beam' ?
              ['fundo','beam_bottom','lateral_a_para','lateral_b_para','lateral_a_passa','lateral_b_passa'] : ['slab_level'];
            var listed = items.filter(function (item) { return item.item_class === cls.key; });
            html += '<div role="tabpanel" class="preproc-level-panel" id="level-panel-' + index + '-' + ci +
              '" aria-labelledby="level-tab-' + index + '-' + ci + '" data-class="' + cls.key + '"' + (ci ? ' hidden' : '') + '>' +
              '<div class="preproc-level-table-wrap"><table><thead><tr><th>Item</th><th>Nível obtido</th><th>Confiança</th>';
            parts.forEach(function (part) { html += '<th>' + esc(partNames[part]) + '</th>'; });
            html += '<th>Segmentos / cruzamentos / evidências</th></tr></thead><tbody>';
            listed.forEach(function (item) {
              var facts = item.levels, values = [], tones = facts.map(factTone);
              facts.forEach(function (f) { if (f.value != null && values.indexOf(levelValue(f)) < 0) values.push(levelValue(f)); });
              var tone = tones.indexOf('conflict') >= 0 ? 'conflict' : tones.indexOf('doubt') >= 0 ? 'doubt' :
                facts.length && tones.every(function (t) { return t === 'good'; }) ? 'good' : 'pending';
              var confs = [];
              facts.forEach(function (f) { var v = confidence(f); if (confs.indexOf(v) < 0) confs.push(v); });
              html += '<tr class="level-row-' + tone + '" data-item-id="' + esc(item.item_id) + '"><th scope="row">' + esc(item.display_name) + '</th>' +
                '<td><span class="level-badge level-' + tone + '">' + esc(values.length === 1 ? values[0] : values.length ? 'Por parte: ' + values.join(' / ') : 'Não determinado') +
                '</span>' + (facts.length && facts.every(function (f) { return f.status === 'not_applicable'; }) ? ' Não se aplica' : '') + '</td>' + cell(confs.join(' / ') || 'Não calculada');
              parts.forEach(function (part) {
                var matches = facts.filter(function (f) { return f.field === part; });
                matches = matches.filter(function (f, i) { return !matches.slice(0,i).some(function (other) {
                  return levelValue(other) === levelValue(f) && other.status === f.status && confidence(other) === confidence(f);
                }); });
                html += '<td>' + (matches.map(function (f) { return '<div class="level-part"><strong>' + esc(levelValue(f)) + '</strong><small class="level-' + factTone(f) + '">' +
                  esc(statusNames[f.status] || f.status || 'Pendente') + ' · confiança: ' + esc(confidence(f)) + '</small></div>'; }).join('') || 'Não determinado') + '</td>';
              });
              html += '<td><details><summary>' + item.source_item_ids.length + ' registros · ' + item.segments.length + ' segmentos</summary>' +
                '<small>' + esc('Identidades de origem: ' + item.source_item_ids.join(', ')) + '</small>';
              facts.forEach(function (f) {
                html += '<div class="level-evidence"><strong>' + esc(partNames[f.field] || f.field) + '</strong>' +
                  '<p>' + esc(candidateText(f.adjacent_slab_candidates) || 'Sem lajes próximas com cota observada') + '</p>' +
                  '<small>' + esc('Registro: ' + f.item_id + ' · nível: ' + levelValue(f) + ' · estado: ' + (statusNames[f.status] || f.status) +
                  ' · método: ' + (f.method || 'não informado') + ' · datum: ' + (f.datum_id || 'não definido') +
                  ' · textos: ' + (f.raw_values || []).join(', ') + ' · evidências: ' + (f.evidence_ids || []).join(', ') +
                  ' · alertas: ' + (f.warnings || []).join(', ')) + '</small></div>';
              });
              item.segments.forEach(function (s) {
                html += '<div class="level-evidence"><strong>' + esc(partNames[s.family] || 'Fundo') + ' · segmento ' + esc(s.segment_label || s.segment_id) +
                  '</strong><p>' + esc(s.family ? ('Referência: ' + s.level + ' m · ' + (statusNames[s.status] || s.status) +
                    (s.bottom_level == null ? '' : ' · fundo físico: ' + s.bottom_level + ' m') + ' · lajes: ' + (s.level_slabs || []).join(', ')) :
                    ('Candidato não validado · ' + (candidateText(s.adjacent_slab_candidates) || 'Sem cota associada'))) + '</p>' +
                  '<small>' + esc('Orientação: ' + (s.orientation || '—') + ' · intervalo: ' + (s.axis_interval || []).join(' → ') +
                  ' · coordenada transversal: ' + (s.transverse_coordinate == null ? '—' : s.transverse_coordinate)) + '</small></div>';
              });
              html += '</details></td></tr>';
            });
            html += '</tbody></table></div>' + (!listed.length ? '<p>Nenhum item nesta classe.</p>' : '') + '</div>';
          });
          html += '<p class="preproc-level-note">Cada segmento mantém seu nível e sua origem. A referência FV é o nível superior; o fundo físico desconta a altura da seção. Referências de pavimento, inferências e estimativas exigem revisão. A confiança percentual só é exibida quando calculada na origem.</p></div>';
        });
        body.innerHTML = html || 'Nenhum item disponível.';
        body.querySelectorAll('.preproc-level-tower').forEach(function (towerEl) {
          function activate(button) {
            towerEl.querySelectorAll('[role="tab"]').forEach(function (tab) {
              var active = tab === button; tab.setAttribute('aria-selected', String(active)); tab.tabIndex = active ? 0 : -1;
            });
            towerEl.querySelectorAll('[role="tabpanel"]').forEach(function (panel) { panel.hidden = panel.dataset.class !== button.dataset.class; });
          }
          var tabs = Array.from(towerEl.querySelectorAll('[role="tab"]'));
          tabs.forEach(function (button, i) {
            button.onclick = function () { activate(button); };
            button.onkeydown = function (event) {
              var next = event.key === 'ArrowRight' ? (i+1)%tabs.length : event.key === 'ArrowLeft' ? (i+tabs.length-1)%tabs.length :
                event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length-1 : -1;
              if (next >= 0) { event.preventDefault(); activate(tabs[next]); tabs[next].focus(); }
            };
          });
        });
      }).catch(function (error) { if (body.isConnected) body.textContent = 'Não foi possível carregar os níveis: ' + error.message; });
  }

  // Deep-link canônico da página de obra. A URL passa a descrever toda a
  // navegação visível, não somente o pavimento. Isso torna refresh, favoritos
  // e apontamentos reproduzíveis até a classe/item/aba interna exatos.
  var DETAIL_URL_KEYS = ['vista', 'subvista', 'lado', 'segmento', 'corte'];
  var _urlIntent = readUrlIntent();
  var _urlRestoreStarted = false;
  var _urlRestoreDone = false;

  function readUrlIntent() {
    try {
      var q = new URLSearchParams(window.location.search);
      return {
        pav: q.get('pavimento'), etapa: q.get('etapa'), classe: q.get('classe'),
        item: q.get('item'), viga: q.get('viga'), doc: q.get('documento'),
        torre: q.get('torre'),
        vista: q.get('vista'), subvista: q.get('subvista'), lado: q.get('lado'),
        segmento: q.get('segmento'), corte: q.get('corte')
      };
    } catch (e) { return {}; }
  }

  function replaceUrlParams(patch, clearDetail) {
    try {
      var u = new URL(window.location.href);
      if (clearDetail) DETAIL_URL_KEYS.forEach(function (key) { u.searchParams.delete(key); });
      Object.keys(patch || {}).forEach(function (key) {
        var value = patch[key];
        if (value === null || value === undefined || value === '') u.searchParams.delete(key);
        else u.searchParams.set(key, String(value));
      });
      window.history.replaceState(null, '', u.pathname + (u.search ? u.search : '') + u.hash);
    } catch (e) { /* URL antiga ou browser sem History API */ }
  }

  function syncNavigationUrl() {
    if (!_urlRestoreDone) return;
    var current = readUrlIntent();
    var nextItem = state.itemId || null;
    var contextChanged = current.pav !== (state.pav || null) ||
      current.etapa !== (state.etapa || null) || current.classe !== (state.classe || null) ||
      current.item !== nextItem;
    replaceUrlParams({
      pavimento: state.pav,
      etapa: state.etapa,
      classe: state.classe,
      item: nextItem,
      viga: state.vigaKey,
      documento: state.selDoc,
      torre: state.analysisDoc
    }, contextChanged);
  }

  function viewParam(name, fallback) {
    var value = readUrlIntent()[name];
    return value === null || value === undefined || value === '' ? fallback : value;
  }

  window.PortalDeepLink = {
    get: viewParam,
    updateView: function (patch) { replaceUrlParams(patch || {}, false); },
    sync: syncNavigationUrl
  };

  var QA_STORAGE_KEY = 'cad.qa.runs.' + OBRA_ID;
  var qaPollTimers = {};
  var qaRoundLoading = {};

  try {
    state.qaRuns = JSON.parse(window.localStorage.getItem(QA_STORAGE_KEY) || '{}') || {};
  } catch (e) {
    state.qaRuns = {};
  }

  // Só aplica ?pavimento= da URL no boot. Sem isso, "← pavimentos" voltava
  // pro hub na hora: selecionarTriagemGeral → montarListaTriagem → onDataReady
  // relia a query e reabria o pav (achado 2026-07-31).
  var _urlPavBootDone = false;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function qaClassId(classe) {
    return classe === 'pilares' ? 'PIL' : (classe === 'fundo' ? 'FV' : null);
  }

  function qaRunKey(pavimento, qaClass, layer) {
    return [pavimento || '', qaClass || '', layer || ''].join('|');
  }

  function saveQaRuns() {
    try { window.localStorage.setItem(QA_STORAGE_KEY, JSON.stringify(state.qaRuns)); } catch (e) { /* */ }
  }

  function qaIsActive(run) {
    return !!run && ['queued', 'running', 'na_fila', 'executando'].indexOf(run.status) >= 0;
  }

  function qaRunFor(layer) {
    var qaClass = qaClassId(state.classe);
    return qaClass ? state.qaRuns[qaRunKey(state.pav, qaClass, layer)] : null;
  }

  function qaControlKey(run) {
    return run && (run.jobId || run.roundId) || '';
  }

  function controlQaJob(jobId, action) {
    if (!jobId || ['pausar', 'continuar', 'cancelar'].indexOf(action) < 0) return;
    if (action === 'cancelar' && !window.confirm('Cancelar esta revisão agentiva? Os resultados já salvos serão preservados.')) return;

    var run = null;
    Object.keys(state.qaRuns).some(function (key) {
      if (String(state.qaRuns[key].jobId || '') !== String(jobId)) return false;
      run = state.qaRuns[key];
      return true;
    });
    var feedbackKey = qaControlKey(run) || String(jobId);
    state.qaControlFeedback[feedbackKey] = action === 'continuar'
      ? 'Devolvendo à fila…'
      : (action === 'pausar' ? 'Solicitando pausa…' : 'Cancelando…');
    render();

    fetch('/jobs/' + encodeURIComponent(jobId) + '/' + action, {method: 'POST'})
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) throw new Error(data.detail || 'Não foi possível controlar a revisão.');
          return data;
        });
      })
      .then(function (data) {
        if (run) run.status = action === 'pausar' ? 'paused' : (action === 'continuar' ? 'queued' : 'cancelled');
        state.qaControlFeedback[feedbackKey] = data.mensagem || 'Estado atualizado.';
        saveQaRuns();
        return fetch('/obras/' + encodeURIComponent(OBRA_ID) + '/jobs?t=' + Date.now());
      })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data.jobs) window._todosJobs = data.jobs;
        render();
        if (run && run.roundId && action !== 'cancelar') pollQaRound(run.roundId);
        window.setTimeout(function () {
          delete state.qaControlFeedback[feedbackKey];
          render();
        }, 4000);
      })
      .catch(function (error) {
        state.qaControlFeedback[feedbackKey] = error.message;
        render();
      });
  }

  function qaProgressFromDetail(detail) {
    var items = detail.items || [];
    var done = items.filter(function (item) { return item.status !== 'queued'; }).length;
    var failed = items.filter(function (item) { return item.status === 'failed'; }).length;
    var total = items.length;
    return {
      roundId: detail.id,
      jobId: detail.job_id,
      pavimento: detail.pavimento,
      qaClass: detail.classe,
      layer: detail.layer,
      status: detail.job_status === 'cancelado' && qaIsActive({status: detail.status})
        ? 'paused' : detail.status,
      total: total,
      done: done,
      failed: failed,
      percent: total ? Math.round((done / total) * 100) : 0,
      updatedAt: new Date().toISOString()
    };
  }

  function pollQaRound(roundId) {
    if (!roundId || qaRoundLoading[roundId]) return;
    qaRoundLoading[roundId] = true;
    fetch('/qa-rounds/' + encodeURIComponent(roundId))
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok) throw new Error(data.detail || ('HTTP ' + response.status));
          return data;
        });
      })
      .then(function (detail) {
        var run = qaProgressFromDetail(detail);
        state.qaRuns[qaRunKey(run.pavimento, run.qaClass, run.layer)] = run;
        saveQaRuns();
        render();
        if (qaIsActive(run)) {
          clearTimeout(qaPollTimers[roundId]);
          qaPollTimers[roundId] = setTimeout(function () { pollQaRound(roundId); }, 2500);
        } else {
          delete qaPollTimers[roundId];
          if (state.level === 'itens' && qaClassId(state.classe) === run.qaClass && state.pav === run.pavimento) {
            loadItens(function () { render(); });
          }
        }
      })
      .catch(function (error) {
        console.warn('[drill] acompanhamento QA', error);
        clearTimeout(qaPollTimers[roundId]);
        qaPollTimers[roundId] = setTimeout(function () { pollQaRound(roundId); }, 5000);
      })
      .finally(function () { delete qaRoundLoading[roundId]; });
  }

  function recoverQaRunsFromJobs() {
    var jobs = window._todosJobs || [];
    jobs.forEach(function (job) {
      var meta = job.meta || {};
      if (meta.etapa !== 'qa_agentico' || !meta.round_id) return;
      // O feed também contém histórico: só uma execução ativa pode adotar ou
      // substituir o progresso visível da classe.
      if (job.status === 'na_fila' || job.status === 'executando') pollQaRound(meta.round_id);
    });
  }

  function resumeSavedQaRuns() {
    Object.keys(state.qaRuns).forEach(function (key) {
      var run = state.qaRuns[key];
      if (qaIsActive(run) && run.roundId) pollQaRound(run.roundId);
    });
  }

  function setPavimentoUrl(pav) {
    replaceUrlParams({pavimento: pav}, true);
  }

  function setObraModo(modo) {
    // modo: 'pavs' | 'pavimento' — ficha/docs da obra só no modo pavs
    try {
      if (typeof window.setObraModo === 'function') window.setObraModo(modo);
      else {
        document.body.classList.toggle('obra-mode-pavs', modo === 'pavs');
        document.body.classList.toggle('obra-mode-pavimento', modo === 'pavimento');
      }
    } catch (e) { /* */ }
  }

  function goPavsList() {
    state.level = 'pavs';
    state.pav = null;
    state.etapa = null;
    state.classe = null;
    state.itens = [];
    state.vigaKey = null;
    state.itemId = null;
    state.rightTorre = false;
    state.selDoc = null;
    state.classesCache = null;
    _urlPavBootDone = true; // impede reabrir via ?pavimento=
    setPavimentoUrl(null);
    setObraModo('pavs');
    try {
      if (window.selecionarTriagemGeral) window.selecionarTriagemGeral();
      else if (window.mostrarDetalhe) window.mostrarDetalhe('triagem');
    } catch (e) {
      console.warn('[drill] selecionarTriagemGeral', e);
    }
    render();
  }

  /** Volta ao hub do pavimento atual (limpa classe/etapa SA) — filtro «Nenhuma». */
  function goHub() {
    if (!state.pav) {
      goPavsList();
      return;
    }
    state.level = 'hub';
    state.etapa = null;
    state.classe = null;
    state.itens = [];
    state.vigaKey = null;
    state.itemId = null;
    state.rightTorre = false;
    setObraModo('pavimento');
    render();
  }

  function isVigaClass(c) { return !!VIGA_CLASSES[c]; }

  function lateralCombinada(c) { return LATERAIS_COMBINADAS[c] || null; }

  function tituloClasse(c) {
    var combinada = lateralCombinada(c);
    if (combinada) return combinada.titulo;
    var encontrada = (state.classesCache || []).filter(function (item) { return item.classe === c; })[0];
    return (encontrada && encontrada.titulo) || c;
  }

  function classesPrincipais() {
    return ['pilares', 'lajes', 'fundo', 'laterais_para', 'laterais_passa'].filter(classePermitida);
  }

  function secaoMotor(c) {
    if (c === 'pilares') return 'pilares';
    if (c === 'lajes') return 'lajes';
    if (c === 'fundo') return 'fundos_viga';
    if (c === 'laterais_para' || c === 'laterais_passa') return 'laterais_viga';
    return c;
  }

  function classeN5(c) {
    if (c === 'pilares') return 'PL';
    if (c === 'lajes') return 'LJ';
    if (c === 'fundo') return 'FV';
    if (c === 'laterais_para' || c === 'laterais_passa') return 'LV';
    return null;
  }

  function classeAtualInfo() {
    return (state.classesCache || []).filter(function (item) {
      return item.classe === state.classe;
    })[0] || {};
  }

  function statusMarker(status, label) {
    var symbol = status === 'done' ? '✓' : (status === 'active' ? '…' : (status === 'error' ? '!' : '⏳'));
    return '<span class="drill-stage-mark ' + status + '" title="' + esc(label) +
      '" aria-label="' + esc(label) + '">' + symbol + '</span>';
  }

  function jobMatchesClass(job, stages) {
    var meta = job.meta || {};
    var pav = meta.pav || meta.pavimento;
    if (pav && pav !== state.pav) return false;
    if (stages.indexOf(meta.etapa) < 0) return false;
    if (meta.classe_ui) return meta.classe_ui === state.classe;
    if (meta.classe) return String(meta.classe).toUpperCase() === String(classeN5(state.classe) || '').toUpperCase();
    var section = meta.secao;
    if (!section || (Array.isArray(section) && !section.length)) return true;
    if (!Array.isArray(section)) section = [section];
    return section.indexOf(secaoMotor(state.classe)) >= 0;
  }

  function activeClassMotorJob(stage) {
    return (window._todosJobs || []).filter(function (job) {
      return (job.status === 'na_fila' || job.status === 'executando') &&
        jobMatchesClass(job, stage ? [stage, 'motores'] : ['sa', 'n3', 'n5', 'motores']);
    })[0] || null;
  }

  function motorProgress(job, localRequest) {
    if (!job && !localRequest) return '';
    var prog = job && job.progresso || {};
    var elapsed = localRequest ? Math.max(0, Math.round((Date.now() - localRequest.startedAt) / 1000)) : 0;
    var raw = localRequest ? Math.min(95, Math.max(2, Math.round(elapsed / 120 * 100))) : prog.percentual_estimado;
    var pct = Math.max(0, Math.min(95, Number(raw) || 0));
    var queued = job && job.status === 'na_fila';
    var finalizing = !queued && pct >= 95;
    var label = queued ? 'Na fila' : finalizing ? 'Finalizando · aguardando resposta do motor' :
      (localRequest ? 'Processando no motor' : (prog.rotulo || 'Processando'));
    var rank = job && job.fila;
    var queueTime = rank && Number(rank.posicao) > 0
      ? 'posição ' + rank.posicao + ' de ' + rank.total_ativos +
        ' · ' + rank.a_frente + (rank.a_frente === 1 ? ' pedido à frente' : ' pedidos à frente')
      : 'aguardando posição na fila';
    var time = queued ? queueTime : finalizing ?
      'tempo acima da estimativa histórica' :
      ('decorrido ' + formatMinutos(localRequest ? elapsed : prog.decorrido_s) + ' · restante ' +
        (localRequest || prog.restante_estimado_s == null ? 'calculando…' : '~' + formatMinutos(prog.restante_estimado_s)));
    return '<div class="drill-inline-job" role="status" aria-live="polite"><div><b>' + esc(label) +
      '</b><span>' + esc(String(pct)) + '% estimado · ' + esc(time) + '</span></div>' +
      '<div class="bar" role="progressbar" aria-label="Progresso estimado do motor" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' +
      esc(String(pct)) + '"><i style="width:' + esc(String(pct)) + '%"></i></div></div>';
  }

  function engineStatus(stage) {
    var info = classeAtualInfo();
    if (activeClassMotorJob(stage) || localMotorRequest(state.classe, state.pav)) {
      return {status:'active', label:'Processamento em andamento'};
    }
    if (stage === 'n5' && info.n5_concluido) return {status:'done', label:'N5 concluído neste pavimento'};
    var job = (window._todosJobs || []).filter(function (candidate) {
      return jobMatchesClass(candidate, [stage]);
    })[0];
    if (job) {
      if (job.status === 'na_fila' || job.status === 'executando') return {status:'active', label:'Processamento em andamento'};
      if (job.status === 'erro' || job.status === 'falhou' || job.status === 'cancelado') return {status:'error', label:'Último processamento não foi concluído'};
      if (job.status === 'concluido') return {status:'done', label:'Processamento concluído'};
    }
    if ((stage === 'sa' || stage === 'n3') && Number(info.total || 0) > 0) {
      return {status:'done', label:'Dados processados disponíveis'};
    }
    return {status:'pending', label:'Processamento pendente'};
  }

  function qaStatusMarker(layer) {
    var run = qaRunFor(layer);
    if (!run) return statusMarker('pending', 'Revisão pendente');
    if (qaIsActive(run)) return statusMarker('active', 'Revisão em andamento');
    if (run.status === 'completed') return statusMarker('done', 'Revisão concluída');
    return statusMarker('error', 'Revisão não concluída');
  }

  function engineStatusMarker(stage) {
    var result = engineStatus(stage);
    return statusMarker(result.status, result.label);
  }

  function listPavimentos() {
    var set = {};
    var cadastrados = (window.ORDEM_PAVIMENTOS || []).map(function (item) {
      return String(item.pavimento || '').trim();
    }).filter(Boolean);
    cadastrados.forEach(function (p) { set[p] = 1; });
    (window.documentosTriagem || []).forEach(function (d) {
      var p = (window.pavimentoDe && window.pavimentoDe(d)) ||
        d.pavimento_confirmado || d.pavimento_sugerido;
      if (p) set[String(p).trim()] = 1;
    });
    (window._recortesBrutosCache || []).forEach(function (b) {
      var p = (b.pavimento || '').trim();
      if (p) set[p] = 1;
    });
    var nomes = Object.keys(set);
    if (!nomes.length) return [];
    nomes.sort(function (a, b) {
      var ia = cadastrados.indexOf(a), ib = cadastrados.indexOf(b);
      if (ia !== -1 || ib !== -1) {
        if (ia === -1) return 1;
        if (ib === -1) return -1;
        return ia - ib;
      }
      function rank(x) {
        var u = x.toUpperCase();
        if (u === 'FUNDACAO' || u.indexOf('FUND') === 0) return [0, 0];
        if (u === 'TERREO' || u === 'TÉRREO') return [1, 0];
        var m = u.match(/(\d+)/);
        if (m) return [2, parseInt(m[1], 10)];
        if (u === 'TIPO') return [3, 0];
        if (u.indexOf('ATIC') === 0) return [4, 0];
        if (u.indexOf('COBERT') === 0) return [5, 0];
        return [6, 0];
      }
      var ra = rank(a), rb = rank(b);
      return ra[0] - rb[0] || ra[1] - rb[1] || a.localeCompare(b);
    });
    return nomes;
  }

  function stemBrutoCanonico(stem) {
    var s = String(stem || '');
    var suf = /_R2018_ASCII_ODA$/i;
    return suf.test(s) ? s.replace(suf, '') : s;
  }

  /** 1 bruto canônico por pav: evita 2 tiles "Bruto" (DWG/DXF + ODA). */
  function brutosDoPavDedup(pav) {
    var brutos = window._recortesBrutosCache || [];
    var porBase = {};
    brutos.forEach(function (b) {
      if ((b.pavimento || 'Indeterminado').trim() !== pav) return;
      var base = (b.bruto_base || stemBrutoCanonico(b.bruto_id || '')).toLowerCase();
      var cur = porBase[base];
      if (!cur) { porBase[base] = b; return; }
      var score = function (x) {
        var id = String(x.bruto_id || '');
        var oda = /_R2018_ASCII_ODA$/i.test(id) ? 1 : 0;
        var nItens = ((window._recortesItensPorBruto || {})[x.bruto_id] || []).length;
        return oda * 1000 + nItens;
      };
      if (score(b) > score(cur)) porBase[base] = b;
    });
    return Object.keys(porBase).map(function (k) { return porBase[k]; });
  }

  /** Ordem fixa do viewer único: Bruto → Torres → Detalhes → Convenções → outros. */
  function rankEstrutural(d) {
    if (d.tipo === 'bruto') return [0, 0];
    var iid = (d.item && d.item.item_id) || '';
    if (d.tipo === 'recorte' && iid.indexOf('torre') === 0) {
      var n = parseInt(iid.replace(/\D/g, ''), 10) || 99;
      return [1, n];
    }
    if (d.tipo === 'recorte' && iid === 'detalhes') return [2, 0];
    if (d.tipo === 'recorte' && iid.indexOf('convencao') === 0) return [3, iid.indexOf('pilares') >= 0 ? 0 : 1];
    return [4, 0];
  }

  function itemValidado(brutoId, itemId) {
    if (window.statusValidacaoRecorte) return !!window.statusValidacaoRecorte(brutoId, itemId);
    var it = ((window._recortesItensPorBruto || {})[brutoId] || []).find(function (x) {
      return x.item_id === itemId;
    });
    return !!(it && it.validado);
  }

  function recortesDoPav(pav) {
    var out = [];
    var porBruto = window._recortesItensPorBruto || {};
    brutosDoPavDedup(pav).forEach(function (b) {
      // Preferir itens do ODA; se vazio, tenta o stem canônico (pasta legada)
      var itens = porBruto[b.bruto_id] || [];
      if (!itens.length) {
        var base = stemBrutoCanonico(b.bruto_id);
        Object.keys(porBruto).forEach(function (k) {
          if (stemBrutoCanonico(k) === base && (porBruto[k] || []).length) {
            itens = porBruto[k];
          }
        });
      }
      itens.forEach(function (it) {
        var iid = it.item_id || '';
        var short = it.titulo || iid;
        var sub = 'recorte';
        var ico = '🏙';
        var kind = 'outro';
        if (iid.indexOf('torre') === 0) { sub = 'recorte'; ico = '🏙'; kind = 'torre'; }
        else if (iid === 'detalhes') { short = 'Detalhes'; sub = 'detalhe'; ico = '🗒'; kind = 'detalhes'; }
        else if (iid === 'convencao_pilares' || iid.indexOf('convencao_pilares_') === 0) { short = 'Conv. Pilares'; sub = 'conv.'; ico = '⬜'; kind = 'conv'; }
        else if (iid === 'convencao_niveis' || iid.indexOf('convencao_niveis_') === 0) { short = 'Conv. Níveis'; sub = 'conv.'; ico = '📏'; kind = 'conv'; }
        else { sub = 'outro'; ico = '📎'; }
        if (short.length > 14) short = short.slice(0, 12) + '…';
        out.push({
          tipo: 'recorte',
          kind: kind,
          id: 'rec:' + b.bruto_id + ':' + iid,
          short: short,
          sub: sub,
          ico: ico,
          nome: it.titulo || iid,
          bruto_id: b.bruto_id,
          item: it,
          validado: itemValidado(b.bruto_id, iid)
        });
      });
      out.push({
        tipo: 'bruto',
        kind: 'bruto',
        id: 'bruto:' + b.bruto_id,
        short: 'Bruto',
        sub: 'DXF',
        ico: '📄',
        nome: b.nome,
        bruto_id: b.bruto_id,
        item: null,
        validado: false
      });
    });
    out.sort(function (a, b) {
      var ra = rankEstrutural(a), rb = rankEstrutural(b);
      return ra[0] - rb[0] || ra[1] - rb[1] || String(a.short).localeCompare(String(b.short));
    });
    return out;
  }

  /** Aba padrão do viewer consolidado: Torre 1 (recorte limpo) se existir; senão Bruto. */
  function pickDefaultDoc(pav) {
    var docs = recortesDoPav(pav);
    var t1 = docs.filter(function (d) {
      return d.tipo === 'recorte' && d.item && d.item.item_id === 'torre_1';
    })[0];
    if (t1) return t1;
    var tAny = docs.filter(function (d) {
      return d.tipo === 'recorte' && d.item && String(d.item.item_id).indexOf('torre') === 0;
    })[0];
    if (tAny) return tAny;
    var bruto = docs.filter(function (d) { return d.tipo === 'bruto'; })[0];
    if (bruto) return bruto;
    return docs[0] || null;
  }

  function pavimentoTitulo(pav) {
    var value = String(pav || '').trim();
    var match = value.match(/^(\d+)_PAV$/i);
    return match ? (match[1] + ' Pavimento') : value.replace(/_/g, ' ');
  }

  function recorteTabsHtml(activeId) {
    var docs = recortesDoPav(state.pav);
    if (!docs.length) return '';
    return '<div class="recorte-tabs-shell">' +
      '<div class="recorte-tabs-heading"><span>Recortes do estrutural</span><b>' +
        esc(pavimentoTitulo(state.pav)) + '</b></div>' +
      '<div class="recorte-tabs" role="tablist" aria-label="Recortes do estrutural de ' +
        esc(state.pav) + '">' + docs.map(function (doc) {
          var active = doc.id === activeId;
          var ok = doc.validado ? '<span class="recorte-tab-status" title="Recorte validado">✓</span>' : '';
          return '<button type="button" class="recorte-tab' + (active ? ' on' : '') +
            '" role="tab" aria-selected="' + (active ? 'true' : 'false') +
            '" data-recorte-tab="' + esc(doc.id) + '" title="' + esc(doc.nome) + '">' +
            '<span aria-hidden="true">' + doc.ico + '</span><span>' + esc(doc.short) + '</span>' + ok +
            '</button>';
        }).join('') + '</div></div>';
  }

  function mountRecorteTabs(activeId) {
    var det = document.getElementById('docs-detalhe');
    if (!det) return;
    var old = det.querySelector('.recorte-tabs-shell');
    if (old) old.remove();
    var slot = document.createElement('div');
    slot.innerHTML = recorteTabsHtml(activeId || state.selDoc);
    if (!slot.firstElementChild) return;
    det.insertBefore(slot.firstElementChild, det.firstChild);
    det.querySelectorAll('[data-recorte-tab]').forEach(function (tab) {
      tab.addEventListener('click', function () {
        var id = tab.getAttribute('data-recorte-tab');
        selectRecorteDoc(id);
      });
    });
  }

  function selectRecorteDoc(id) {
    var doc = recortesDoPav(state.pav).filter(function (candidate) { return candidate.id === id; })[0];
    if (!doc) return;
    // Recorte e etapa são contextos irmãos. Limpar a etapa evita URLs híbridas
    // (ex.: documento=bruto&etapa=sa) e mantém menu, aba e conteúdo sincronizados.
    state.level = 'hub';
    state.etapa = null;
    state.classe = null;
    state.itens = [];
    state.vigaKey = null;
    state.itemId = null;
    state.rightTorre = false;
    state.selDoc = id;
    render();
    openDoc(doc);
  }

  function groupsForEtapa(etapaId, classes) {
    var byId = {};
    (classes || []).forEach(function (c) { byId[c.classe] = c; });
    if (etapaId === 'n5') {
      return [
        { nome: 'Pilares unificados', items: [
          byId.pilares_n3_para || { classe: 'pilares_n3_para', titulo: 'Pilares · Para', total: 0 },
          byId.pilares_n3_passa || { classe: 'pilares_n3_passa', titulo: 'Pilares · Passa', total: 0 }
        ]},
        { nome: 'Vigas A', items: [
          byId.lateral_a_para || { classe: 'lateral_a_para', titulo: 'Viga A · Para', total: 0 },
          byId.lateral_a_passa || { classe: 'lateral_a_passa', titulo: 'Viga A · Passa', total: 0 }
        ]},
        { nome: 'Vigas B', items: [
          byId.lateral_b_para || { classe: 'lateral_b_para', titulo: 'Viga B · Para', total: 0 },
          byId.lateral_b_passa || { classe: 'lateral_b_passa', titulo: 'Viga B · Passa', total: 0 }
        ]},
        { nome: 'Laje & fundo', items: [
          byId.lajes || { classe: 'lajes', titulo: 'Laje unificada', total: 0 },
          byId.fundo || { classe: 'fundo', titulo: 'Fundo de viga unificado', total: 0 }
        ]}
      ].map(function (g) { g.items = g.items.filter(function (c) { return classePermitida(c.classe); }); return g; });
    }
    var schema = etapaId === 'n3' ? N3_GROUPS : SA_GROUPS;
    // N3 também lista laterais/fundos/lajes do SA + pilares n3
    if (etapaId === 'n3') {
      schema = [
        { nome: 'Pilares', ids: ['pilares_n3_para', 'pilares_n3_passa'] },
        { nome: 'Lajes', ids: ['lajes'] },
        { nome: 'Vigas', ids: ['fundo', 'lateral_a_para', 'lateral_a_passa', 'lateral_b_para', 'lateral_b_passa'] }
      ];
    }
    return schema.map(function (g) {
      return {
        nome: g.nome,
        items: g.ids.filter(classePermitida).map(function (id) {
          return byId[id] || { classe: id, titulo: id, total: 0 };
        })
      };
    });
  }

  function groupVigaItens(itens) {
    var map = {};
    var order = [];
    itens.forEach(function (it) {
      var t = it.titulo || it.item_id || '';
      var m = t.match(/^(.+?)\s*\(segmento\s*([^)]+)\)/i);
      var viga = m ? m[1].trim() : t;
      var seg = m ? String(m[2]).trim() : '1';
      if (!map[viga]) { map[viga] = []; order.push(viga); }
      map[viga].push({ seg: seg, item: it });
    });
    return order.map(function (v) { return { key: v, segs: map[v] }; });
  }

  function ensureDocsDetalhe() {
    var painel = document.getElementById('docs-detalhe-painel');
    if (painel && !document.getElementById('docs-detalhe')) {
      painel.innerHTML = '<div class="n1-detalhe" id="docs-detalhe"></div>';
    }
  }

  function crumbHtml() {
    // O cabeçalho lateral identifica somente a obra. Pavimento, etapa e
    // classe já possuem títulos próprios logo abaixo e não devem competir
    // visualmente com o nome principal.
    return '<strong>' + esc(OBRA_NOME) + '</strong>';
  }

  function backLabel() {
    if (state.rightTorre) return '← fechar Torre limpa (dir.)';
    if (state.level === 'hub') return '← pavimentos';
    if (state.level === 'etapa') return torresDoPav().length > 1 ? '← torres do pavimento' : '';
    if (state.level === 'itens' && state.vigaKey) return '← lista de vigas';
    if (state.level === 'itens' && state.classe === 'cortes') return '← pré-processamento';
    // [2026-09-28] Dentro de uma classe não há "← estrutura da torre": a aba
    // Estrutura logo acima já leva de volta (pedido do dono).
    return '';
  }

  function renderPavs() {
    var pavs = listPavimentos();
    if (!pavs.length) {
      return '<div class="drill-empty">Nenhum pavimento detectado ainda.<br>Envie documentos ou rode a triagem.</div>';
    }
    return (
      '<div class="drill-sec">' + esc(OBRA_NOME) + ' <em>lista</em></div>' +
      '<div class="drill-pav-list">' +
      pavs.map(function (p) {
        var on = p === state.pav ? ' on' : '';
        return '<button type="button" class="drill-pav' + on + '" data-drill="pav" data-id="' + esc(p) + '">' +
          '<span class="lab">' + esc(p) + '</span><span class="seta">▸</span></button>';
      }).join('') +
      '</div>'
    );
  }

  function renderHub() {
    var docs = recortesDoPav(state.pav);
    var tiles;
    if (!docs.length) {
      tiles = '<div class="drill-empty">Sem recortes estruturais neste pavimento.</div>';
    } else {
      tiles = '<div class="drill-tiles">' + docs.map(function (d) {
        var on = state.selDoc === d.id ? ' on' : '';
        var ok = d.validado ? ' ok' : '';
        var badge = d.validado
          ? '<span class="drill-tile-ok" title="Recorte validado">✓</span>'
          : '';
        return '<button type="button" class="drill-tile' + on + ok + '" data-drill="doc" data-id="' + esc(d.id) +
          '" title="' + esc(d.nome) + (d.validado ? ' · validado' : '') + '">' +
          '<span class="ico">' + d.ico + '</span>' +
          '<span class="k">' + esc(d.short) + '</span>' +
          '<span class="s">' + esc(d.sub) + (d.validado ? ' · ok' : '') + '</span>' +
          badge +
          '</button>';
      }).join('') + '</div>';
    }
    // Cada torre é uma unidade analisável. Detalhes e convenções continuam no
    // viewer de recortes, mas nunca entram como análise SA.
    var torres = docs.filter(function (doc) { return doc.kind === 'torre'; });
    var classesById = {};
    (state.classesCache || []).forEach(function (item) { classesById[item.classe] = item; });
    function totalPre(classe) {
      return Number((classesById[classe] || {}).total || 0);
    }
    function docConvencao(itemId) {
      return docs.filter(function (doc) {
        return doc.tipo === 'recorte' && doc.item && (doc.item.item_id === itemId || doc.item.item_id.indexOf(itemId + '_') === 0);
      })[0];
    }
    function preRow(label, count, action, id, available) {
      return '<button type="button" class="drill-pre-row" data-drill="' + action + '" data-id="' +
        esc(id || '') + '"' + (available ? '' : ' disabled aria-disabled="true"') + '>' +
        '<span class="nm">' + esc(label) + '</span><span class="meta">' + esc(String(count)) +
        '</span><span class="seta">▸</span></button>';
    }
    var convPilares = docConvencao('convencao_pilares');
    var convNiveis = docConvencao('convencao_niveis');
    var preProcessamento =
      preRow('Visão de Cortes', totalPre('cortes'), 'preproc-cortes', 'cortes', true) +
      preRow('Convenção de Pilares', convPilares ? 1 : 0, 'preproc-doc', convPilares && convPilares.id, !!convPilares) +
      preRow('Convenção de Níveis', preprocState && preprocState.result ?
        (preprocState.result.level_observed || 0) : '—', 'preproc-levels', 'niveis', true);
    var preJob = (window._todosJobs || []).filter(function (job) {
      return job.meta && job.meta.etapa === 'preprocessamento' && job.meta.pav === state.pav;
    }).sort(function (a, b) {
      return String(b.enfileirado_em || '').localeCompare(String(a.enfileirado_em || ''));
    })[0];
    var preStatus = preprocSubmitting ? 'na_fila' : preJob ? preJob.status : preprocState && preprocState.status;
    var preBusy = preStatus === 'na_fila' || preStatus === 'executando';
    var preLabel = preStatus === 'na_fila' ? 'Aguardando na fila…' :
      preStatus === 'executando' ? 'Pré-processando…' : 'Pré-processar pavimento';
    var preProgress = preprocState && preprocState.progress;
    var preEnabled = preprocState && preprocState.enabled !== false;
    var preResult = preprocState && preprocState.result;
    var preFeedback = !preEnabled ? 'Recurso ainda não habilitado.' :
      preResult && preResult.status === 'stale' ? 'Fontes alteradas · execute novamente o pré-processamento.' :
      preStatus === 'concluido' ? 'Pacotes concluídos · ' + String((preResult && preResult.level_observed) || 0) +
        ' cotas de laje observadas' + (preResult && preResult.collected_segments ? ' · ' + preResult.items_with_levels +
          ' itens com níveis · ' + preResult.collected_segments + ' segmentos coletados' : '') + '; confira a Convenção de Níveis.' :
      (preStatus === 'falhou' || preStatus === 'erro' || preStatus === 'cancelado') ?
        'Processamento não concluído: ' + String((preJob && preJob.erro_msg) || (preprocState && preprocState.error) || preStatus) :
      preBusy ? (preStatus === 'na_fila' ? 'Na fila' : preProgress ?
        preProgress.stage === 'collecting_sa_level_evidence' ? 'Coletando níveis com interpretação contextual do estrutural…' :
        preProgress.completed + '/' + preProgress.total + ' torres processadas' : 'Preparando fontes…') :
      'Inventário, convenções e coleta contextual de níveis.';
    var preAction = '<div class="drill-pre-action">' +
      '<button type="button" class="drill-pre-run" data-drill="preproc-run"' +
      (preBusy || !preEnabled ? ' disabled aria-disabled="true"' : '') + '><span>' + esc(preLabel) + '</span>' +
      '<small>Inventário e convenções</small>' + statusMarker(preBusy ? 'active' : preStatus === 'concluido' ? 'done' :
        ['falhou', 'erro', 'cancelado'].indexOf(preStatus) >= 0 ? 'error' : 'pending', preFeedback) + '</button>' +
      (preBusy ? motorProgress(preJob || {status: preStatus}) :
        '<div class="drill-inline-job drill-pre-feedback" role="status" aria-live="polite">' + esc(preFeedback) + '</div>') +
      '</div>';
    var etapas = torres.map(function (doc) {
      var on = state.analysisDoc === doc.id ? ' on' : '';
      return '<button type="button" class="drill-etapa-row' + on + '" data-drill="etapa" data-id="sa"' +
        ' data-level="' + esc(doc.id) + '" title="Abrir detalhamento de ' + esc(doc.nome) + '">' +
        '<span class="lab"><span class="k">' + esc(doc.nome) + '</span>' +
        '<small>SA · N3 · N5 desta torre</small></span>' +
        '<span class="seta">▸</span></button>';
    }).join('');
    if (!etapas) etapas = '<div class="drill-empty">Crie um recorte de torre para iniciar o detalhamento.</div>';
    // Abas do hub (dono 2026-09-28): uma seção por vez no painel esquerdo.
    var tab = state.hubTab || 'recortes';
    if (tab === 'pre') {
      return '<div class="drill-sec drill-sec-recortes drill-sec-preprocessamento"><strong>Pré-processamento</strong>' +
        '<span>' + esc(pavimentoTitulo(state.pav)) + '</span></div>' +
        preAction + '<div class="drill-pre-list">' + preProcessamento + '</div>';
    }
    if (tab === 'etapas') {
      // Mais de uma torre: escolher qual antes de Motores/Estrutura.
      return '<div class="drill-sec drill-sec-recortes drill-sec-etapas"><strong>Escolha a torre</strong>' +
        '<span>' + esc(pavimentoTitulo(state.pav)) + '</span></div>' +
        '<div class="drill-etapa-list">' + etapas + '</div>';
    }
    return '<div class="drill-sec drill-sec-recortes"><strong>Recortes do Estrutural</strong>' +
      '<span>' + esc(pavimentoTitulo(state.pav)) + '</span></div>' + tiles;
  }

  function activeTab() {
    if (state.level === 'pavs') return 'pavs';
    if (state.level === 'itens' && state.classe === 'cortes') return 'pre';
    if (state.level === 'itens') return 'estrutura';
    if (state.level === 'etapa' || state.hubTab === 'etapas') return state.etapaTab || 'estrutura';
    return state.hubTab || 'recortes';
  }

  function torresDoPav() {
    return recortesDoPav(state.pav).filter(function (doc) { return doc.kind === 'torre'; });
  }

  function renderTabs() {
    var cur = activeTab();
    var tabs = [['pavs', 'Pavimentos'], ['recortes', 'Recortes'], ['pre', 'Pré-proc.'],
      ['motores', 'Motores'], ['estrutura', 'Estrutura']];
    return '<div class="drill-tabs" role="tablist">' + tabs.map(function (t) {
      var off = t[0] !== 'pavs' && !state.pav;
      return '<button type="button" role="tab" class="drill-tab' + (cur === t[0] ? ' on' : '') + '"' +
        ' aria-selected="' + (cur === t[0]) + '" data-drill="tab" data-id="' + t[0] + '"' +
        (off ? ' disabled aria-disabled="true"' : '') + '>' + esc(t[1]) + '</button>';
    }).join('') + '</div>';
  }

  function renderProcBox(et) {
    var statusEl = et.procStatusId ? document.getElementById(et.procStatusId) : null;
    var barEl = et.procBarId ? document.getElementById(et.procBarId) : null;
    var statusTxt = statusEl ? statusEl.textContent : '—';
    var barW = barEl ? (barEl.style.width || '0%') : '0%';
    var jobs = window._todosJobs || [];
    var jobAtivo = jobs.filter(function (job) {
      if (job.status !== 'na_fila' && job.status !== 'executando') return false;
      var meta = job.meta || {};
      return (meta.etapa || 'sa') === et.id && (!meta.pav || meta.pav === state.pav);
    })[0];
    var liveHtml = '';
    var disabled = '';
    var buttonLabel = et.procLabel;
    if (jobAtivo) {
      var prog = jobAtivo.progresso || {};
      var pct = prog.percentual_estimado;
      disabled = ' disabled aria-disabled="true"';
      buttonLabel = jobAtivo.status === 'na_fila' ? 'Aguardando na fila…' : 'Processamento em andamento…';
      statusTxt = jobAtivo.status === 'na_fila' ? 'Na fila' : String(pct == null ? 2 : pct) + '% estimado';
      barW = String(pct == null ? 0 : pct) + '%';
      var decorrido = formatMinutos(prog.decorrido_s);
      var restante = prog.restante_estimado_s == null ? 'calculando…' : ('~' + formatMinutos(prog.restante_estimado_s));
      liveHtml = '<div class="job-live" role="status" aria-live="polite">' +
        '<strong>' + esc(prog.rotulo || buttonLabel) + '</strong>' +
        '<span>Decorrido: ' + esc(decorrido) + ' · restante: ' + esc(restante) + '</span>' +
        '<small>Job deste pavimento · atualização automática</small>' +
      '</div>';
    }
    return (
      '<div class="drill-proc">' +
        '<div class="ph">Status · ' + esc(state.pav) + '</div>' +
        '<div class="pr"><span>' + (jobAtivo ? 'Progresso do job:' : 'Progresso:') + '</span><strong>' + esc(statusTxt) + '</strong></div>' +
        '<div class="bar"><i style="width:' + esc(barW) + '"></i></div>' +
        liveHtml +
        '<button type="button" class="run" data-drill="proc" data-id="' + et.id + '"' + disabled + '>' + esc(buttonLabel) + '</button>' +
        '<div class="hint">' + (et.id === 'n5'
          ? 'Roda as unificações do pavimento. Cada classe abaixo também é acessível.'
          : 'Roda a análise desta etapa para o pavimento selecionado.') + '</div>' +
      '</div>'
    );
  }

  function formatMinutos(segundos) {
    segundos = Math.max(0, Number(segundos) || 0);
    if (segundos < 60) return '<1 min';
    return Math.ceil(segundos / 60) + ' min';
  }

  function nomeTorreAnalise(doc) {
    var itemId = doc && doc.item && String(doc.item.item_id || '');
    var match = itemId.match(/^torre[_-]?(\d+)$/i);
    if (match) return 'Torre ' + match[1];
    var nome = String((doc && doc.nome) || 'Torre').trim();
    // O pavimento já aparece como subtítulo; evita "Torre 1 - 14_PAV" duplicado.
    return nome.replace(/\s*[-–—]\s*\d+_PAV\s*$/i, '') || 'Torre';
  }

  function renderEtapa() {
    var et = ETAPAS.filter(function (e) { return e.id === state.etapa; })[0];
    var groups = groupsForEtapa(state.etapa, state.classesCache || []);
    var torre = recortesDoPav(state.pav).filter(function (doc) { return doc.id === state.analysisDoc; })[0];
    var torreNome = nomeTorreAnalise(torre);
    // Abas Motores / Estrutura (dono 2026-09-28): uma parte por vez.
    if (state.etapaTab === 'motores') {
      return '<div class="drill-sec drill-sec-recortes drill-sec-motores"><strong>Motores da ' +
        esc(torreNome) + '</strong><span>SA → N3 → N5</span></div>' + renderUnifiedProcBox();
    }
    var html = '<div class="drill-tower-title"><strong>Estrutura da ' +
      esc(torreNome) + '</strong><span>' + esc(pavimentoTitulo(state.pav)) + '</span></div>';
    groups.forEach(function (g) {
      html += '<div class="drill-cls-grp drill-cls-title">' + esc(g.nome) + '</div><div class="drill-cls-list">';
      g.items.forEach(function (c) {
        var on = c.classe === state.classe ? ' on' : '';
        html += '<button type="button" class="drill-cls-row' + on + '" data-drill="classe" data-id="' +
          esc(c.classe) + '"><span class="nm">' + esc(c.titulo) + '</span><span class="meta">' +
          (c.total != null ? c.total : '—') + '</span><span class="seta">▸</span></button>';
      });
      html += '</div>';
    });
    return html;
  }

  function renderCortesPreprocessamento() {
    var html = '<div class="drill-tower-title"><strong>Visão de Cortes</strong><span>' +
      esc(pavimentoTitulo(state.pav)) + '</span></div>' +
      '<div class="drill-sec">Cortes <em>itens</em></div><div class="drill-itens drill-pre-itens">';
    (state.itens || []).forEach(function (item) {
      var on = state.itemId === item.item_id ? ' on' : '';
      html += '<button type="button" class="drill-pi' + on + '" data-drill="item" data-id="' +
        esc(item.item_id) + '">' + esc(item.titulo || item.item_id) + '</button>';
    });
    html += '</div>';
    if (!state.itens.length) html += '<div class="drill-empty">Nenhuma visão de corte neste pavimento.</div>';
    return html;
  }

  function renderUnifiedProcBox() {
    var statusValues = {};
    ETAPAS.forEach(function (et) {
      var statusEl = et.procStatusId ? document.getElementById(et.procStatusId) : null;
      statusValues[et.id] = { label: et.short, value: statusEl ? statusEl.textContent : '—' };
    });
    var allJobs = window._todosJobs || [];
    var jobs = allJobs.filter(function (job) {
      if (job.status !== 'na_fila' && job.status !== 'executando') return false;
      var meta = job.meta || {};
      var section = meta.secao;
      return (!meta.pav || meta.pav === state.pav) && !meta.classe_ui &&
        (!section || (Array.isArray(section) && !section.length));
    });
    function activeJob(stage) {
      var expected = stage === 'all' ? 'motores' : stage;
      return jobs.filter(function (job) { return String((job.meta || {}).etapa || 'sa') === expected; })[0];
    }
    var allJob = activeJob('all');
    var globalRequest = localMotorRequest(null, state.pav);
    var ultimoFalho = allJobs.filter(function (job) {
      var meta = job.meta || {};
      return job.status === 'falhou' && (!meta.pav || meta.pav === state.pav) &&
        ['sa', 'n3', 'n5', 'motores'].indexOf(String(meta.etapa || 'sa')) >= 0;
    })[0];
    function resumoFalha(job) {
      if (!job) return '';
      var raw = String(job.erro_msg || job.erro || 'O motor encerrou com falha.');
      var linhas = raw.split(/\r?\n/).map(function (line) { return line.trim(); }).filter(Boolean);
      var texto = linhas.length ? linhas[linhas.length - 1] : raw;
      if (texto.length > 180) texto = texto.slice(0, 177) + '…';
      return '<div class="drill-job-failed" role="alert"><b>Último processamento falhou</b><span>' +
        esc(texto) + '</span></div>';
    }
    function progress(job) {
      return motorProgress(job, null);
    }
    function engineButton(stage, label, extraClass) {
      var ownJob = activeJob(stage);
      var disabled = allJob || ownJob || globalRequest;
      return '<button type="button" class="run' + (extraClass ? ' ' + extraClass : '') +
        '" data-drill="proc-global" data-id="' + stage + '"' +
        (disabled ? ' disabled aria-disabled="true"' : '') + '>' + esc(label) + '</button>';
    }
    function engineStep(stage, label) {
      var status = statusValues[stage] || { label: stage.toUpperCase(), value: '—' };
      return '<div class="drill-engine-step">' + engineButton(stage, label) +
        '<div class="drill-engine-status"><b>' + esc(status.label) + '</b><span>' +
        esc(status.value) + '</span></div>' +
        (progress(activeJob(stage)) || motorProgress(null, globalRequest && globalRequest.stage === stage ? globalRequest : null)) + '</div>';
    }
    return '<div class="drill-proc drill-proc-unified">' +
      engineStep('sa', 'Rodar interpretação · todas as classes') +
      engineStep('n3', 'Rodar desenho · todas as classes') +
      engineStep('n5', 'Rodar unificação · todas as classes') +
      '<div class="drill-engine-all">' +
      engineButton('all', 'Rodar os 3 em sequência · SA → N3 → N5', 'run-all') +
      (progress(activeJob('all')) || motorProgress(null, globalRequest && globalRequest.stage === 'all' ? globalRequest : null)) +
      '</div>' + resumoFalha(ultimoFalho) + '</div>';
  }

  function renderItens() {
    var viga = isVigaClass(state.classe);
    var combinada = lateralCombinada(state.classe);
    var nomeClasse = tituloClasse(state.classe);
    var html = '<div class="drill-structural-home-wrap">' +
      '<button type="button" class="drill-structural-home" data-drill="structural-home" ' +
      'title="Voltar ao estrutural limpo deste pavimento">' +
      '<span class="ico" aria-hidden="true">←</span><span>Estrutural limpo</span></button></div>' +
      '<div class="drill-cls-title drill-motores-granulares">Motores granulares</div>' +
      renderClassActions(nomeClasse) +
      '<div class="drill-sec">' + esc(nomeClasse) + ' <em>' +
      (viga ? 'vigas' : 'itens') + '</em></div>';

    if (combinada) {
      html += renderLateraisCombinadas(combinada);
    } else if (viga) {
      var groups = groupVigaItens(state.itens);
      html += '<div class="drill-itens">';
      groups.forEach(function (g) {
        var on = state.vigaKey === g.key ? ' on' : '';
        var humanOk = g.segs.length && g.segs.every(function (s) { return !!s.item.validado; });
        html += '<button type="button" class="drill-pi' + on + (humanOk ? ' human-ok' : '') + '" data-drill="viga" data-id="' +
          esc(g.key) + '">' + esc(g.key) + '<span class="subn">' + g.segs.length + ' seg</span>' +
          renderQaBadges((g.segs[0] && g.segs[0].item.qa_reviews) || {}) + '</button>';
      });
      html += '</div>';
      if (!groups.length) html += '<div class="drill-empty">Nenhuma viga nesta classe.</div>';
      if (state.vigaKey) {
        var gSel = groups.filter(function (g) { return g.key === state.vigaKey; })[0];
        if (gSel) {
          html += '<div class="drill-seg-wrap"><div class="sh"><span><b>' + esc(gSel.key) +
            '</b> · segmentos</span><em style="font-style:normal">' + gSel.segs.length +
            '</em></div><div class="drill-segs">';
          gSel.segs.forEach(function (s) {
            var on = state.itemId === s.item.item_id ? ' on' : '';
            html += '<button type="button" class="drill-sg' + on + '" data-drill="item" data-id="' +
              esc(s.item.item_id) + '">S' + esc(s.seg) + '</button>';
          });
          html += '</div></div>';
        }
      }
    } else {
      html += '<div class="drill-itens">';
      state.itens.forEach(function (it) {
        var on = state.itemId === it.item_id ? ' on' : '';
        var convention = String(it.classification || '').toUpperCase();
        var conventionClass = /^pilares/.test(state.classe) ? ' pillar-convention-' + (convention === 'NASCE' ? 'nasce' : convention === 'MORRE' ? 'morre' : /^(SEGUE|CONTINUA|PASSA)$/.test(convention) ? 'segue' : 'unknown') : '';
        html += '<button type="button" class="drill-pi' + on + conventionClass + (it.validado ? ' human-ok' : '') + '" title="' + esc(convention) + '" data-drill="item" data-id="' +
          esc(it.item_id) + '">' + esc(it.titulo || it.item_id) + renderQaBadges(it.qa_reviews || {}) + '</button>';
      });
      html += '</div>';
      if (!state.itens.length) html += '<div class="drill-empty">Nenhum item nesta classe.</div>';
    }

    if (!combinada) {
      html +=
        '<button type="button" class="drill-criar' + (state.rightTorre ? ' on' : '') +
        '" data-drill="criar-item"><span class="plus">+</span> Criar novo item</button>';
    }
    html += renderClassFooter();
    return html;
  }

  function renderClassActions(nomeClasse) {
    var activeMotor = activeClassMotorJob(null);
    var submittingMotor = localMotorRequest(state.classe, state.pav);
    function classMotorButton(stage, label) {
      var ownJob = activeClassMotorJob(stage);
      var ownRequest = submittingMotor && (submittingMotor.stage === stage || submittingMotor.stage === 'all') ? submittingMotor : null;
      var locked = !!(activeMotor || submittingMotor);
      return '<div class="drill-class-engine">' +
        '<button type="button" data-drill="proc-class" data-id="' + stage + '"' +
          (locked ? ' disabled aria-disabled="true"' : '') + '>' + label + '<br><b>' +
          esc(nomeClasse) + ' · ' + stage.toUpperCase() + '</b>' + engineStatusMarker(stage) + '</button>' +
        motorProgress(ownJob, ownRequest) + '</div>';
    }
    var qaEnabled = state.classe === 'pilares' || state.classe === 'fundo';
    var activeRuns = ['L1', 'L2', 'L3'].map(qaRunFor).filter(qaIsActive);
    var pausedRuns = ['L1', 'L2', 'L3'].map(qaRunFor).filter(function (run) { return run && run.status === 'paused'; });
    var visibleRun = activeRuns[0] || pausedRuns[0] || ['L3', 'L2', 'L1'].map(qaRunFor).filter(function (run) { return !!run; })[0];
    var qaStatusHtml = '';
    if (visibleRun) {
      var label = 'C' + visibleRun.layer.substring(1);
      var terminal = !qaIsActive(visibleRun);
      var statusLabel;
      if (!terminal) {
        var current = Math.min((visibleRun.done || 0) + 1, visibleRun.total || 1);
        statusLabel = visibleRun.status === 'queued'
          ? 'na fila · 0/' + visibleRun.total
          : 'processando item ' + current + '/' + visibleRun.total;
      } else if (visibleRun.status === 'paused') {
        statusLabel = 'pausada pelo operador · ' + visibleRun.done + '/' + visibleRun.total;
      } else if (visibleRun.status === 'completed') {
        statusLabel = 'concluída · ' + visibleRun.done + '/' + visibleRun.total;
      } else if (visibleRun.status === 'cancelled' || visibleRun.status === 'canceled') {
        statusLabel = 'cancelada pelo operador · ' + visibleRun.done + '/' + visibleRun.total;
      } else if (visibleRun.status === 'partial_failed') {
        statusLabel = 'concluída com ' + visibleRun.failed + ' falha(s)';
      } else {
        statusLabel = 'falhou · ' + (visibleRun.failed || visibleRun.total) + ' item(ns)';
      }
      var statusClass = !terminal ? 'active' : (visibleRun.status === 'completed' ? 'done' :
        (visibleRun.status === 'partial_failed' || visibleRun.status === 'paused' ? 'warn' : 'error'));
      var controllable = qaIsActive(visibleRun) || visibleRun.status === 'paused';
      var feedback = state.qaControlFeedback[qaControlKey(visibleRun)] || '';
      qaStatusHtml = '<div class="drill-qa-progress ' + statusClass + '" role="status" aria-live="polite">' +
        '<div><strong>Revisão agentiva ' + label + '</strong><span>' + esc(statusLabel) + '</span></div>' +
        '<div class="drill-qa-progress-bar"><i style="width:' + esc(visibleRun.percent || 0) + '%"></i></div>' +
        '<small>' + esc(visibleRun.percent || 0) + '% concluído' + (visibleRun.failed ? ' · ' + visibleRun.failed + ' falha(s)' : '') + '</small>' +
        (controllable && visibleRun.jobId ? '<div class="drill-qa-controls" aria-label="Ações da revisão agentiva">' +
          '<button type="button" data-drill="qa-job-control" data-id="' + esc(visibleRun.jobId) + '" data-level="pausar"' +
            (qaIsActive(visibleRun) ? '' : ' disabled') + '>Pausar</button>' +
          '<button type="button" data-drill="qa-job-control" data-id="' + esc(visibleRun.jobId) + '" data-level="continuar"' +
            (visibleRun.status === 'paused' ? '' : ' disabled') + '>Continuar</button>' +
          '<button type="button" class="danger" data-drill="qa-job-control" data-id="' + esc(visibleRun.jobId) + '" data-level="cancelar">Cancelar</button>' +
        '</div>' : '') +
        (feedback ? '<div class="drill-qa-control-feedback">' + esc(feedback) + '</div>' : '') +
        '</div>';
    }
    return '<div class="drill-class-actions" aria-label="Motores desta classe">' +
      classMotorButton('sa', 'Rodar motor interpretativo') +
      '<div class="drill-qa-class" aria-label="Revisão agentiva C1 C2 C3">' +
        ['L1', 'L2', 'L3'].map(function (layer) {
          var run = qaRunFor(layer);
          var active = qaIsActive(run);
          return '<button type="button" data-drill="proc-qa-class" data-id="' + layer + '"' +
            (qaEnabled && !active ? '' : ' disabled' + (!qaEnabled ? ' title="Motor agentivo ainda não disponível para esta classe"' : ' aria-disabled="true"')) +
            (active ? ' class="is-processing"' : '') +
            '><span>C' + layer.substring(1) + '</span><small>' + (active ? 'processando…' : 'QA') + '</small>' + qaStatusMarker(layer) + '</button>';
        }).join('') + '</div>' + qaStatusHtml +
      classMotorButton('n3', 'Rodar motor de desenho') +
      classMotorButton('n5', 'Rodar motor de unificação') +
      '<button type="button" class="drill-unified" data-drill="unificados">Visualizar unificados</button>' +
      '</div>';
  }

  function renderQaBadges(reviews) {
    return ['L1', 'L2', 'L3'].map(function (layer) {
      var review = reviews[layer];
      if (!review || !review.verdict) return '';
      var ok = review.verdict === 'validou';
      var target = ({L1: 'SA', L2: 'C1', L3: 'C2'})[layer];
      var confidence = review.confidence_percent == null ? '' : ' ' + review.confidence_percent + '%';
      return '<span class="drill-qa-tag ' + (ok ? 'ok' : 'bad') + '">' + target +
        (ok ? ' ✓' : ' ✕') + confidence + '</span>';
    }).join('');
  }

  function renderClassFooter() {
    var html = '<div class="drill-cls-grp">Outras classes</div><div class="drill-other-classes">';
    classesPrincipais().forEach(function (id) {
      if (id === state.classe) return;
      html += '<button type="button" data-drill="classe" data-id="' + esc(id) + '">' + esc(tituloClasse(id)) + '</button>';
    });
    return html + '</div>';
  }

  function renderBotaoCriarLateral(lado, classeReal, vigaNome) {
    var criando = state.rightTorre && state.createClasse === classeReal ? ' on' : '';
    return '<button type="button" class="drill-criar drill-criar-side' + criando +
      '" data-drill="criar-item-lateral" data-id="' + esc(classeReal) +
      '" data-level="' + esc(vigaNome || '') + '">' +
      '<span class="plus">+</span> Criar segmento ' + lado + '</button>';
  }

  function renderSegmentosLadoSelecionado(lado, classeReal, grupo, vigaNome) {
    var segs = grupo ? grupo.segs : [];
    var html = '<section class="drill-seg-wrap drill-seg-side" aria-label="' +
      esc(vigaNome) + ' · segmentos do lado ' + lado + '"><div class="sh"><span><b>' +
      esc(vigaNome) + '</b> · lado ' + lado + '</span><em style="font-style:normal">' +
      segs.length + '</em></div><div class="drill-segs">';
    segs.forEach(function (s) {
      var chaveItem = s.item._drillKey || s.item.item_id;
      var on = state.itemId === chaveItem ? ' on' : '';
      html += '<button type="button" class="drill-sg' + on + '" data-drill="item" data-id="' +
        esc(chaveItem) + '">S' + esc(s.seg) + ' <span class="drill-seg-side-letter">' + lado +
        '</span></button>';
    });
    if (!segs.length) html += '<span class="drill-empty-side">Nenhum segmento ' + lado + '</span>';
    html += '</div>' + renderBotaoCriarLateral(lado, classeReal, vigaNome) + '</section>';
    return html;
  }

  function renderLateraisCombinadas(combinada) {
    var itensA = state.itens.filter(function (it) { return it._drillClasse === combinada.a; });
    var itensB = state.itens.filter(function (it) { return it._drillClasse === combinada.b; });
    var gruposA = groupVigaItens(itensA);
    var gruposB = groupVigaItens(itensB);
    var mapaA = {}, mapaB = {}, nomes = {};
    gruposA.forEach(function (g) { mapaA[g.key] = g; nomes[g.key] = 1; });
    gruposB.forEach(function (g) { mapaB[g.key] = g; nomes[g.key] = 1; });
    var lista = Object.keys(nomes).sort(function (a, b) {
      return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
    });
    var html = '<div class="drill-combined-total"><span>Vigas</span><strong>A · ' + itensA.length +
      ' seg</strong><strong>B · ' + itensB.length + ' seg</strong></div><div class="drill-itens drill-vigas-combined">';
    lista.forEach(function (nome) {
      var na = mapaA[nome] ? mapaA[nome].segs.length : 0;
      var nb = mapaB[nome] ? mapaB[nome].segs.length : 0;
      var on = state.vigaKey === nome ? ' on' : '';
      html += '<button type="button" class="drill-pi drill-viga-combined' + on +
        '" data-drill="viga" data-id="' + esc(nome) + '"><span class="drill-viga-name">' +
        esc(nome) + '</span><span class="subn drill-viga-sidecount">A · ' + na +
        ' seg</span><span class="subn drill-viga-sidecount">B · ' + nb + ' seg</span></button>';
    });
    html += '</div>';
    if (!lista.length) html += '<div class="drill-empty">Nenhuma viga nesta classe.</div>';
    if (state.vigaKey) {
      html += '<div class="drill-selected-sides">' +
        renderSegmentosLadoSelecionado('A', combinada.a, mapaA[state.vigaKey], state.vigaKey) +
        renderSegmentosLadoSelecionado('B', combinada.b, mapaB[state.vigaKey], state.vigaKey) +
        '</div>';
    } else {
      html += '<div class="drill-create-pair">' +
        renderBotaoCriarLateral('A', combinada.a, '') +
        renderBotaoCriarLateral('B', combinada.b, '') + '</div>' +
        '<div class="drill-hint">Selecione uma viga para preencher o nome e ver A/B.</div>';
    }
    return html;
  }

  function render() {
    recoverQaRunsFromJobs();
    var back = backLabel();
    var body = '';
    if (state.level === 'pavs') body = renderPavs();
    else if (state.level === 'hub') body = renderHub();
    else if (state.level === 'etapa') body = renderEtapa();
    else if (state.level === 'itens' && state.classe === 'cortes') body = renderCortesPreprocessamento();
    else if (state.level === 'itens') body = renderItens();

    root.innerHTML =
      '<div class="drill-crumb drill-obra-title">' + crumbHtml() + '</div>' +
      renderTabs() +
      (back && state.level !== 'hub' ?'<button type="button" class="drill-back" data-drill="back">' + esc(back) + '</button>' : '') +
      '<div class="drill-scroll">' + body + '</div>';

    root.querySelectorAll('[data-drill]').forEach(function (el) {
      el.addEventListener('click', function () {
        handle(el.getAttribute('data-drill'), el.getAttribute('data-id'), el.getAttribute('data-level'));
      });
    });
    syncNavigationUrl();
  }

  function handle(act, id, level) {
    if (act === 'structural-home') {
      // Sempre navega de volta pela via canônica (openDoc troca o painel
      // visível para 'triagem', remonta as abas de recorte e reabre a Torre 1
      // com a barra de destaques zerada por padrão). Um clique em
      // #destaque-nenhuma NÃO basta sozinho: quando o usuário estava dentro
      // de uma ficha de item (painel 'n1'/'n3'), esse botão só reseta o drill
      // à esquerda e nunca troca o painel visível nem reabre a Torre 1 — daí
      // sobrar a aba errada (ou nenhuma aba) selecionada ao clicar aqui.
      // Dono 2026-09-28: so' o painel direito volta ao estrutural limpo; o
      // painel esquerdo (aba, classe, lista) fica exatamente onde estava.
      window._criarItemClassePref = null;
      window._criarItemVigaPref = null;
      var structuralDoc = pickDefaultDoc(state.pav);
      if (structuralDoc) openDoc(structuralDoc);
      else if (window.mostrarDetalhe) window.mostrarDetalhe('triagem');
      return;
    }
    if (act === 'tab') {
      if (id === 'pavs') { goPavsList(); return; }
      if (!state.pav) return;
      if (id === 'motores' || id === 'estrutura') {
        state.etapaTab = id;
        var torres = torresDoPav();
        var torre = torres.filter(function (d) { return d.id === state.analysisDoc; })[0] ||
          (torres.length === 1 ? torres[0] : null);
        if (torre) {
          if (state.level === 'etapa' && state.analysisDoc === torre.id) { render(); return; }
          handle('etapa', 'sa', torre.id);
          return;
        }
        id = 'etapas';
      }
      state.hubTab = id;
      state.level = 'hub'; state.etapa = null; state.classe = null;
      state.itens = []; state.vigaKey = null; state.itemId = null; state.rightTorre = false;
      render();
      return;
    }
    if (act === 'jump') {
      if (level === 'pavs') {
        goPavsList();
        return;
      } else if (level === 'hub') {
        state.level = 'hub'; state.etapa = null; state.classe = null;
        state.itens = []; state.vigaKey = null; state.itemId = null; state.rightTorre = false;
      } else if (level === 'etapa') {
        state.level = 'etapa'; state.classe = null; state.itens = [];
        state.vigaKey = null; state.itemId = null; state.rightTorre = false;
      }
      render();
      return;
    }
    if (act === 'back') {
      if (state.rightTorre) { state.rightTorre = false; render(); return; }
      if (state.level === 'itens' && state.vigaKey) {
        state.vigaKey = null; state.itemId = null; render(); return;
      }
      if (state.level === 'itens') {
        if (state.classe === 'cortes') state.hubTab = 'pre';
        state.level = state.classe === 'cortes' ? 'hub' : 'etapa';
        state.etapa = state.classe === 'cortes' ? null : state.etapa;
        state.classe = null; state.itens = [];
        state.itemId = null; state.vigaKey = null; render(); return;
      }
      if (state.level === 'etapa') {
        state.hubTab = 'etapas';
        state.level = 'hub'; state.etapa = null; state.classe = null; render(); return;
      }
      if (state.level === 'hub') {
        goPavsList();
        return;
      }
      return;
    }
    if (act === 'pav') {
      state.pav = id; state.level = 'hub'; state.hubTab = 'recortes';
      preprocState = null;
      state.etapa = null; state.classe = null; state.itens = [];
      state.vigaKey = null; state.itemId = null; state.rightTorre = false;
      state.classesCache = null;
      _urlPavBootDone = true;
      setPavimentoUrl(id);
      setObraModo('pavimento');
      try {
        if (window.selecionarPavimento) window.selecionarPavimento(id);
        if (window.atualizarProgressoRecortesPavimento) window.atualizarProgressoRecortesPavimento(id);
      } catch (e) {
        console.warn('[drill] selecionarPavimento', e);
      }
      // auto: Torre 1 se existir; senão Bruto
      var def = pickDefaultDoc(id);
      state.selDoc = def ? def.id : null;
      render();
      if (def) openDoc(def);
      return;
    }
    if (act === 'doc') {
      selectRecorteDoc(id);
      return;
    }
    if (act === 'preproc-doc') {
      if (id) selectRecorteDoc(id);
      return;
    }
    if (act === 'preproc-levels') {
      showLevelInventory();
      return;
    }
    if (act === 'preproc-run') {
      enqueuePreprocessamento();
      return;
    }
    if (act === 'preproc-cortes') {
      state.etapa = 'preprocessamento'; state.classe = 'cortes'; state.level = 'itens';
      state.vigaKey = null; state.itemId = null; state.rightTorre = false;
      loadItens(function () { render(); });
      return;
    }
    if (act === 'etapa') {
      state.analysisDoc = level || state.analysisDoc;
      state.etapa = id; state.level = 'etapa';
      state.classe = null; state.itens = []; state.vigaKey = null;
      state.itemId = null; state.rightTorre = false; state.selDoc = null;
      if (id === 'n5' && window.mostrarDetalhe) window.mostrarDetalhe('n5');
      if (window.atualizarProgressoRecortesPavimento && state.pav) {
        window.atualizarProgressoRecortesPavimento(state.pav);
      }
      loadClasses(function () { render(); });
      return;
    }
    if (act === 'classe') {
      state.classe = id; state.level = 'itens';
      state.vigaKey = null; state.itemId = null; state.rightTorre = false;
      loadItens(function () { render(); });
      return;
    }
    if (act === 'viga') {
      if (state.vigaKey === id) { state.vigaKey = null; state.itemId = null; }
      else {
        state.vigaKey = id; state.itemId = null;
        // Fundo e laterais são fichas por viga. Ao selecionar a viga, abrimos
        // a ficha inteira pelo primeiro segmento; nas laterais a troca A/B
        // acontece dentro da própria ficha.
        if (state.classe === 'fundo') {
          var grupoFundo = groupVigaItens(state.itens).filter(function (group) {
            return group.key === id;
          })[0];
          if (grupoFundo && grupoFundo.segs.length) {
            state.itemId = grupoFundo.segs[0].item.item_id;
          }
        } else if (lateralCombinada(state.classe)) {
          var grupoLateral = groupVigaItens(state.itens).filter(function (group) {
            return group.key === id;
          })[0];
          if (grupoLateral && grupoLateral.segs.length) {
            var primeiroLateral = grupoLateral.segs[0].item;
            state.itemId = primeiroLateral._drillKey || primeiroLateral.item_id;
          }
        }
      }
      state.rightTorre = false;
      if (state.itemId) openItem(state.itemId);
      render();
      return;
    }
    if (act === 'item') {
      state.itemId = id; state.rightTorre = false;
      openItem(id);
      render();
      return;
    }
    if (act === 'criar-item') {
      state.rightTorre = true; state.createClasse = state.classe; state.itemId = null;
      openTorreCriar(state.classe);
      render();
      return;
    }
    if (act === 'criar-item-lateral') {
      state.rightTorre = true; state.createClasse = id; state.itemId = null;
      openTorreCriar(id, level || '');
      render();
      return;
    }
    if (act === 'proc') {
      var et = ETAPAS.filter(function (e) { return e.id === id; })[0];
      if (!et) return;
      if (et.id === 'n5') {
        var btnN5 = document.querySelector('.painel2-acao-btn[data-acao="n5"]:not([data-escopo="global"])');
        if (btnN5) btnN5.click();
        else if (window.mostrarDetalhe) window.mostrarDetalhe('n5');
        return;
      }
      var btn = et.btn ? document.getElementById(et.btn) : null;
      if (btn) btn.click();
      return;
    }
    if (act === 'proc-class') {
      enqueueMotor(id, state.classe, false);
      return;
    }
    if (act === 'proc-qa-class') {
      enqueueQaClass(id);
      return;
    }
    if (act === 'qa-job-control') {
      controlQaJob(id, level);
      return;
    }
    if (act === 'proc-global') {
      var confirmLabel = id === 'all'
        ? 'Rodar SA, N3 e N5 em sequência para ' + state.pav + '? Os quatro botões ficarão bloqueados enquanto esta fila estiver ativa.'
        : 'Enfileirar o motor ' + String(id).toUpperCase() + ' para todas as classes de ' + state.pav + '?';
      if (!window.confirm(confirmLabel)) return;
      enqueueMotor(id, null, true);
      return;
    }
    if (act === 'unificados') {
      replaceUrlParams({vista:'unificados'}, false);
      if (window.mostrarDetalhe) window.mostrarDetalhe('n5-pavimento');
      return;
    }
  }

  function enqueueMotor(stage, classe, global) {
    if (!global && (activeClassMotorJob(null) || localMotorRequest(classe, state.pav))) return;
    var targetInfo = classeAtualInfo();
    var endpoint = stage === 'all' ? 'motores' : stage;
    var body = { pav: state.pav, secao: classe ? [secaoMotor(classe)] : [],
      classe_ui: classe || null };
    if (stage === 'n5') {
      var n5 = classeN5(classe);
      if (!n5 && !global) return;
      body = { classe: n5 || 'ALL', pavimento: state.pav };
    }
    function dispatch(visualMode) {
      var requestPav = state.pav;
      var requestKey = motorRequestKey(stage, classe, requestPav);
      if (submittingMotors[requestKey]) return;
      submittingMotors[requestKey] = {stage: stage, classe: classe, pav: requestPav, startedAt: Date.now()};
      var progressTimer = window.setInterval(function () {
        if (state.pav === requestPav && state.level === 'itens') render();
      }, 1000);
      render();
      if (visualMode) body.visual_mode = visualMode;
      fetch('/obras/' + OBRA_ID + '/' + endpoint, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
      }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) throw new Error(data.detail || ('HTTP ' + response.status));
        return data;
      });
    }).then(function (data) {
      if (stage === 'n5' && !global) targetInfo.n5_concluido = true;
      if (data.job_id && window._todosJobs) {
        window._todosJobs.push({ id: data.job_id, status: 'na_fila', meta: data.meta || {
          etapa: stage, pav: requestPav, secao: body.secao, classe_ui: classe || null
        }, enfileirado_em: new Date().toISOString() });
      }
    }).catch(function (error) {
      window.alert('Não foi possível executar: ' + error.message);
    }).finally(function () {
      delete submittingMotors[requestKey];
      window.clearInterval(progressTimer);
      render();
    });
    }
    var modeAware = stage === 'n3' || stage === 'n5' || stage === 'all';
    var isLateralOnly = !global && classeN5(classe) === 'LV';
    if (modeAware && !isLateralOnly && window.escolherModoDesenho) {
      var available = stage === 'n5' && !global
        ? fetch('/obras/' + OBRA_ID + '/n5/modos?classe=' + classeN5(classe) + '&pavimento=' + encodeURIComponent(state.pav))
            .then(function (response) { if (!response.ok) throw new Error('Não foi possível consultar os modos N3.'); return response.json(); })
            .then(function (data) { return ['NOVA','INI'].filter(function (mode) { return data.modes[mode].n3; }); })
        : Promise.resolve(null);
      available.then(function (modes) {
        return window.escolherModoDesenho({
          currentMode: new URLSearchParams(window.location.search).get('modo_desenho') || 'NOVA',
          availableModes: modes,
          description: stage === 'n5' ? 'Escolha o estilo do N3 já produzido para unificar. Modos sem N3 completo ficam indisponíveis.' : 'Escolha o estilo que será gravado nesta geração ' + stage.toUpperCase() + '.'
        });
      }).then(function (mode) { if (mode) dispatch(mode); }).catch(function (error) { window.alert(error.message); });
      return;
    }
    dispatch(null);
  }

  function enqueueQaClass(layer) {
    var qaClass = qaClassId(state.classe);
    if (!qaClass) return;
    var items = [];
    state.itens.forEach(function (item) {
      var value = qaClass === 'FV' ? item.beam_name : item.item_id;
      value = String(value || '').toUpperCase();
      if (value && items.indexOf(value) < 0) items.push(value);
    });
    if (!items.length) { window.alert('Nenhum item disponível para revisão.'); return; }
    fetch('/obras/' + OBRA_ID + '/qa-agentico', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({items: items, classe: qaClass, pavimento: state.pav, layer: layer})
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) throw new Error(data.detail || ('HTTP ' + response.status));
        return data;
      });
    }).then(function (data) {
      var run = {
        roundId: data.round_id,
        jobId: data.job_id,
        pavimento: data.pavimento || state.pav,
        qaClass: data.classe || qaClass,
        layer: data.layer || layer,
        status: data.status || 'queued',
        total: items.length,
        done: 0,
        failed: 0,
        percent: 0,
        updatedAt: new Date().toISOString()
      };
      state.qaRuns[qaRunKey(run.pavimento, run.qaClass, run.layer)] = run;
      saveQaRuns();
      if (data.job_id && window._todosJobs) {
        window._todosJobs.push({id: data.job_id, status: 'na_fila', meta: {
          etapa: 'qa_agentico', round_id: data.round_id
        }, enfileirado_em: new Date().toISOString()});
      }
      render();
      pollQaRound(data.round_id);
    }).catch(function (error) {
      window.alert('Não foi possível enfileirar a revisão: ' + error.message);
    });
  }

  function openDoc(d) {
    ensureDocsDetalhe();
    if (window.mostrarDetalhe) window.mostrarDetalhe('triagem');
    if (d.tipo === 'bruto' && d.bruto_id) {
      var det = document.getElementById('docs-detalhe');
      if (det && window.renderizarFotoRecorte) {
        det.innerHTML = recorteTabsHtml(d.id) + '<div class="recorte-viewer" id="recorte-viewer-bruto-drill"></div>';
        mountRecorteTabs(d.id);
        window.renderizarFotoRecorte(
          document.getElementById('recorte-viewer-bruto-drill'),
          '/obras/' + OBRA_ID + '/recortes/brutos/' + encodeURIComponent(d.bruto_id) + '/foto',
          'Planta Completa'
        );
      }
      return;
    }
    if (d.tipo === 'recorte' && d.item && window.renderizarDetalheRecorte) {
      window.renderizarDetalheRecorte({
        titulo: d.item.titulo || d.nome,
        categoria: d.sub === 'recorte' ? 'Torres Limpas' : (d.sub === 'detalhe' ? 'Detalhes e Convenções' : 'Recorte'),
        pavimento: state.pav,
        brutoId: d.bruto_id,
        itemId: d.item.item_id
      });
      mountRecorteTabs(d.id);
      if (window.mostrarDetalhe) window.mostrarDetalhe('triagem');
    }
  }

  // Fim de job (SA/N3/N5): o recarregamento do pavimento desenha o Bruto no
  // painel direito. Reabre o que o usuario estava vendo (dono 2026-09-28):
  // documento escolhido, a torre da etapa ou a Torre limpa; ficha de item
  // recarrega com os dados novos; outras paginas (N5 etc.) ficam intactas.
  function reabrirConteudo(secao) {
    if (!state.pav) return;
    var ficha = secao === 'detalhe-n1' || secao === 'detalhe-n3';
    if (secao && secao !== 'detalhe-triagem' && !ficha) return;
    // O estrutural por baixo da ficha tambem volta (senao o "voltar" mostra o Bruto).
    var docs = recortesDoPav(state.pav);
    var doc = docs.filter(function (d) { return d.id === state.selDoc; })[0] ||
      docs.filter(function (d) { return d.id === state.analysisDoc; })[0] ||
      pickDefaultDoc(state.pav);
    if (doc) openDoc(doc);
    if (ficha && state.level === 'itens' && state.itemId) {
      var itemId = state.itemId;
      if (window.mostrarDetalhe) window.mostrarDetalhe(secao.replace('detalhe-', ''));
      loadItens(function () { state.itemId = itemId; render(); openItem(itemId); });
    }
  }

  function openItem(itemId) {
    var et = state.classe === 'cortes'
      ? { id: 'sa', stage: 'n1' }
      : ETAPAS.filter(function (e) { return e.id === state.etapa; })[0];
    if (!et) return;
    if (et.id === 'n5') {
      if (window.mostrarDetalhe) window.mostrarDetalhe('n5');
      return;
    }
    var stage = et.stage;
    var itemEscolhido = state.itens.filter(function (it) {
      return (it._drillKey || it.item_id) === itemId;
    })[0];
    if (!itemEscolhido) return;
    var classeReal = itemEscolhido._drillClasse || state.classe;
    var idReal = itemEscolhido.item_id;
    var itens = lateralCombinada(state.classe)
      ? state.itens.filter(function (it) { return it._drillClasse === classeReal; })
      : state.itens;
    var indice = 0;
    for (var i = 0; i < itens.length; i++) {
      if (itens[i].item_id === idReal) { indice = i; break; }
    }
    if (window.setPainel3Estado) {
      window.setPainel3Estado({ stage: stage, classe: classeReal, itens: itens, indice: indice });
    }
    if (stage === 'n1' && window.carregarDetalheItemN1) {
      window.carregarDetalheItemN1(idReal);
      if (window.mostrarDetalhe) window.mostrarDetalhe('n1');
    } else if (stage === 'n3' && window.carregarDetalheItemN3) {
      window.carregarDetalheItemN3(idReal);
      if (window.mostrarDetalhe) window.mostrarDetalhe('n3');
    }
  }

  function openTorreCriar(classePref, vigaPref) {
    // Abre a Torre limpa do pav no painel direito (não iframe) com classe pré-selecionada
    // e painel "Criar item" abaixo da validação.
    ensureDocsDetalhe();
    if (window.mostrarDetalhe) window.mostrarDetalhe('triagem');
    window._criarItemClassePref = classePref || state.classe || null;
    window._criarItemVigaPref = vigaPref || null;
    var docs = recortesDoPav(state.pav);
    var t1 = docs.filter(function (d) {
      return d.tipo === 'recorte' && d.item && d.item.item_id === 'torre_1';
    })[0];
    var tAny = docs.filter(function (d) {
      return d.tipo === 'recorte' && d.item && String(d.item.item_id).indexOf('torre') === 0;
    })[0];
    var alvo = t1 || tAny;
    if (alvo) {
      state.selDoc = alvo.id;
      openDoc(alvo);
      return;
    }
    // Sem torre: fallback viewer da obra
    var url = '/app/obras/' + encodeURIComponent(OBRA_ID) + '/viewer/' + encodeURIComponent(state.pav || '');
    var det = document.getElementById('docs-detalhe');
    if (!det) return;
    det.innerHTML =
      '<div class="drill-torre-criar">' +
        '<h3 style="margin:0 0 8px">Estrutural limpo · ' + esc(state.pav) + '</h3>' +
        '<p class="muted">Nenhuma torre limpa neste pavimento ainda. Rode Triagem + Recortes ou abra o viewer.</p>' +
        '<p><a class="btn" href="' + esc(url) + '" target="_blank" rel="noopener">Abrir viewer →</a></p>' +
      '</div>';
  }

  function loadClasses(done) {
    var q = state.pav ? ('?pavimento=' + encodeURIComponent(state.pav)) : '';
    fetch('/obras/' + OBRA_ID + '/n1/classes' + q)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.classesCache = data.classes || [];
        var by = {};
        state.classesCache.forEach(function (c) { by[c.classe] = c; });
        if (classePermitida('laterais_para')) state.classesCache.push({ classe: 'laterais_para', titulo: 'Segmentos Lateral A.B. · Para',
          total: Number((by.lateral_a_para || {}).total || 0) + Number((by.lateral_b_para || {}).total || 0),
          n5_concluido: Boolean((by.lateral_a_para || {}).n5_concluido || (by.lateral_b_para || {}).n5_concluido) });
        if (classePermitida('laterais_passa')) state.classesCache.push({ classe: 'laterais_passa', titulo: 'Segmentos Lateral A.B. · Passa',
          total: Number((by.lateral_a_passa || {}).total || 0) + Number((by.lateral_b_passa || {}).total || 0),
          n5_concluido: Boolean((by.lateral_a_passa || {}).n5_concluido || (by.lateral_b_passa || {}).n5_concluido) });
        if (done) done();
      })
      .catch(function () { state.classesCache = []; if (done) done(); });
  }

  function loadItens(done) {
    var q = state.pav ? ('?pavimento=' + encodeURIComponent(state.pav)) : '';
    var combinada = lateralCombinada(state.classe);
    if (combinada) {
      function buscar(classe, lado) {
        return fetch('/obras/' + OBRA_ID + '/n1/' + encodeURIComponent(classe) + q)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            return (data.itens || []).map(function (it) {
              var item = Object.assign({}, it);
              item._drillClasse = classe;
              item._drillLado = lado;
              item._drillKey = lado + '::' + item.item_id;
              return item;
            });
          });
      }
      Promise.all([buscar(combinada.a, 'A'), buscar(combinada.b, 'B')])
        .then(function (listas) {
          state.itens = listas[0].concat(listas[1]);
          if (done) done();
        })
        .catch(function () { state.itens = []; if (done) done(); });
      return;
    }
    fetch('/obras/' + OBRA_ID + '/n1/' + encodeURIComponent(state.classe) + q)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        state.itens = data.itens || [];
        if (done) done();
      })
      .catch(function () { state.itens = []; if (done) done(); });
  }

  /**
   * Abre Interpretação · SA na classe pedida e mostra a lista de itens no drill.
   * Usado pelos filtros de destaque do estrutural (seleção única).
   */
  function openSaClasse(classeId, pavimento) {
    if (!classeId) return;
    if (pavimento) state.pav = pavimento;
    if (!state.pav) {
      try {
        var p = new URLSearchParams(window.location.search).get('pavimento');
        if (p) state.pav = p;
      } catch (e) { /* */ }
    }
    if (!state.pav) return;
    _urlPavBootDone = true;
    state.etapa = classeId === 'cortes' ? 'preprocessamento' : 'sa';
    state.level = 'itens';
    state.classe = classeId;
    state.vigaKey = null;
    state.itemId = null;
    state.rightTorre = false;
    // mantém selDoc/torre se já aberta no centro
    function go() {
      loadItens(function () {
        render(); // lista de itens da classe no painel esquerdo (drill)
        if (window.setPainel3Estado) {
          try {
            window.setPainel3Estado({
              stage: 'n1',
              classe: state.classe,
              itens: state.itens || [],
              indice: 0
            });
          } catch (e2) { /* */ }
        }
        // NÃO troca o conteúdo central (mantém torre + destaques)
      });
    }
    if (!state.classesCache || !state.classesCache.length) {
      loadClasses(function () { go(); });
    } else {
      go();
    }
  }

  function onDataReady() {
    ensureDocsDetalhe();
    if (!_urlRestoreStarted) {
      _urlRestoreStarted = true;
      var intent = _urlIntent || {};
      if (intent.pav) {
        state.pav = intent.pav;
        state.level = intent.etapa ? (intent.classe ? 'itens' : 'etapa') : 'hub';
        state.etapa = intent.etapa || null;
        state.classe = intent.classe || null;
        state.vigaKey = intent.viga || null;
        state.itemId = intent.item || null;
        state.selDoc = intent.doc || null;
        state.analysisDoc = intent.torre || null;
        _urlPavBootDone = true;
        setObraModo('pavimento');
        try {
          if (window.selecionarPavimento) window.selecionarPavimento(intent.pav);
        } catch (e) { console.warn('[drill] restaurar pavimento', e); }

        function finishRestore() {
          if (state.level === 'itens' && state.vigaKey && !state.itemId) {
            var group = groupVigaItens(state.itens).filter(function (candidate) {
              return candidate.key === state.vigaKey;
            })[0];
            if (group && group.segs.length) {
              state.itemId = group.segs[0].item._drillKey || group.segs[0].item.item_id;
            }
          }
          _urlRestoreDone = true;
          render();
          if (intent.vista === 'unificados') {
            if (window.mostrarDetalhe) window.mostrarDetalhe('n5-pavimento');
            return;
          }
          if (intent.vista === 'gestao-finalizados') {
            if (window.mostrarDetalhe) window.mostrarDetalhe('n5');
            return;
          }
          if (state.level === 'itens' && state.itemId) openItem(state.itemId);
          else if (state.selDoc === 'preproc:niveis') showLevelInventory();
          else if (state.selDoc) {
            var selectedDoc = recortesDoPav(state.pav).filter(function (doc) {
              return doc.id === state.selDoc;
            })[0];
            if (selectedDoc) openDoc(selectedDoc);
          } else if (state.level === 'hub') {
            var defaultDoc = pickDefaultDoc(state.pav);
            if (defaultDoc) {
              state.selDoc = defaultDoc.id;
              syncNavigationUrl();
              openDoc(defaultDoc);
            }
          }
        }

        if (state.etapa) {
          loadClasses(function () {
            if (state.classe) {
              loadItens(function () {
                var found = state.itens.some(function (item) {
                  return (item._drillKey || item.item_id) === state.itemId;
                });
                if (!found) state.itemId = null;
                finishRestore();
              });
            } else finishRestore();
          });
        } else finishRestore();
        return;
      }
      _urlRestoreDone = true;
    }
    // Boot único a partir da URL — nunca reabre pav depois de "← pavimentos"
    if (!_urlPavBootDone && !state.pav && state.level === 'pavs') {
      _urlPavBootDone = true;
      var p = new URLSearchParams(window.location.search).get('pavimento');
      if (p) {
        state.pav = p;
        state.level = 'hub';
        setObraModo('pavimento');
        try {
          if (window.selecionarPavimento) window.selecionarPavimento(p);
        } catch (e) {
          console.warn('[drill] boot selecionarPavimento', e);
        }
      } else {
        setObraModo('pavs');
      }
    } else if (!_urlPavBootDone) {
      _urlPavBootDone = true;
      if (!state.pav) setObraModo('pavs');
      else setObraModo('pavimento');
    }
    // Se entrou no hub sem seleção, aplica default Torre 1 / Bruto
    if (state.level === 'hub' && state.pav && !state.selDoc) {
      var def = pickDefaultDoc(state.pav);
      if (def) {
        state.selDoc = def.id;
        render();
        openDoc(def);
        return;
      }
    }
    render();
  }

  window.DrillGrade = {
    refresh: onDataReady,
    reabrirConteudo: reabrirConteudo,
    state: state,
    render: render,
    // Fonte canônica da navegação por pavimento. O painel de status deve
    // consumir esta mesma lista para nunca exibir pavimentos divergentes.
    listPavimentos: listPavimentos,
    pickDefaultDoc: pickDefaultDoc,
    recortesDoPav: recortesDoPav,
    refreshRecorteTabs: function () { mountRecorteTabs(state.selDoc); },
    openRecorteById: selectRecorteDoc,
    // Pavimento aberto (URL ou clique): mesmo viewer COM abas de recortes,
    // no recorte já escolhido ou no padrão (Torre 1, senão Bruto). Devolve
    // false se os recortes ainda não carregaram (chamador usa o fallback).
    openRecorteDoPav: function (pav) {
      var docs = recortesDoPav(pav);
      var doc = docs.filter(function (d) { return d.id === state.selDoc; })[0] ||
        pickDefaultDoc(pav);
      if (!doc) return false;
      state.selDoc = doc.id;
      openDoc(doc);
      return true;
    },
    startRecorteReplace: function (brutoId, itemId) {
      var brutoDoc = recortesDoPav(state.pav).filter(function (doc) {
        return doc.tipo === 'bruto' && doc.bruto_id === brutoId;
      })[0];
      if (!brutoDoc) return;
      window._recorteReplaceIntent = { brutoId: brutoId, itemId: itemId };
      selectRecorteDoc(brutoDoc.id);
    },
    openSaClasse: openSaClasse,
    goPavsList: goPavsList,
    goHub: goHub,
    refreshItems: function () {
      if (state.level !== 'itens') return;
      loadItens(function () { render(); });
    }
  };

  // As fichas são módulos independentes. Este listener mantém a URL precisa
  // sem acoplá-las ao drill e sem alterar o módulo de laterais em trabalho por
  // outra sessão.
  document.addEventListener('click', function (event) {
    var target = event.target && event.target.closest ? event.target.closest('button') : null;
    if (!target || !window.PortalDeepLink) return;
    var patch = {};
    if (target.hasAttribute('data-pillar-tab')) patch.vista = target.getAttribute('data-pillar-tab');
    if (target.hasAttribute('data-pillar-n1-subtab')) patch.subvista = target.getAttribute('data-pillar-n1-subtab');
    if (target.hasAttribute('data-lj-layer')) patch.vista = target.getAttribute('data-lj-layer');
    if (target.hasAttribute('data-fv-layer')) patch.vista = target.getAttribute('data-fv-layer');
    if (target.hasAttribute('data-fv-focus')) patch.segmento = target.getAttribute('data-fv-focus');
    if (target.hasAttribute('data-lv-side')) patch.lado = target.getAttribute('data-lv-side');
    if (target.hasAttribute('data-lv-layer')) patch.vista = target.getAttribute('data-lv-layer');
    if (target.hasAttribute('data-lv-segment-tab')) patch.segmento = target.getAttribute('data-lv-segment-tab');
    if (target.hasAttribute('data-lv-cut')) patch.corte = target.getAttribute('data-lv-cut');
    if (target.hasAttribute('data-lj-nav')) {
      state.itemId = target.getAttribute('data-lj-nav');
      syncNavigationUrl();
    }
    if (target.hasAttribute('data-fv-nav')) {
      state.vigaKey = target.getAttribute('data-fv-target') || null;
      replaceUrlParams({viga: state.vigaKey, item: null}, true);
    }
    if (target.hasAttribute('data-lv-beam')) {
      state.vigaKey = target.getAttribute('data-lv-beam');
      replaceUrlParams({viga: state.vigaKey, item: null}, true);
    }
    if (Object.keys(patch).length) replaceUrlParams(patch, false);
  });

  var _origMontar = window.montarListaTriagem;
  window.montarListaTriagem = function () {
    // não pinta a árvore gorda na sidebar; só sincroniza dados + drill
    try {
      ensureDocsDetalhe();
      if (_origMontar && root.getAttribute('data-legacy-tree') === '1') _origMontar();
    } catch (e) { /* */ }
    onDataReady();
  };

  // A lista cadastrada já veio no HTML; não espere a primeira rodada do timer.
  onDataReady();

  // re-paint quando recortes chegam
  var tries = 0;
  var boot = setInterval(function () {
    tries += 1;
    onDataReady();
    if ((window._recortesBrutosCache && window._recortesBrutosCache.length) || tries > 8) {
      clearInterval(boot);
    }
  }, 350);
  setInterval(refreshPreprocessamento, 4000);
  setTimeout(refreshPreprocessamento, 900);
  resumeSavedQaRuns();
})();
