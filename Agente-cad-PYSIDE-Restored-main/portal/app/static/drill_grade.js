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
    { nome: 'Pré-interpretação', ids: ['cortes', 'convencao_pilares', 'convencao_niveis_lajes'] },
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
    qaRuns: {},
    qaControlFeedback: {}
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
    try {
      var u = new URL(window.location.href);
      if (pav) u.searchParams.set('pavimento', pav);
      else u.searchParams.delete('pavimento');
      var q = u.searchParams.toString();
      window.history.replaceState(null, '', u.pathname + (q ? ('?' + q) : '') + u.hash);
    } catch (e) { /* */ }
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
    return ['pilares', 'lajes', 'fundo', 'laterais_para', 'laterais_passa'];
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
    if (c === 'lajes') return 'LAJ';
    if (c === 'fundo') return 'FV';
    if (c === 'laterais_para' || c === 'laterais_passa') return 'LV';
    return null;
  }

  function listPavimentos() {
    var set = {};
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

  /** Ordem fixa do hub: Torres → Detalhes → Bruto → Convenções → outros */
  function rankEstrutural(d) {
    var iid = (d.item && d.item.item_id) || '';
    if (d.tipo === 'recorte' && iid.indexOf('torre') === 0) {
      var n = parseInt(iid.replace(/\D/g, ''), 10) || 99;
      return [0, n];
    }
    if (d.tipo === 'recorte' && iid === 'detalhes') return [1, 0];
    if (d.tipo === 'bruto') return [2, 0];
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
        else if (iid === 'convencao_pilares') { short = 'Conv. Pilares'; sub = 'conv.'; ico = '⬜'; kind = 'conv'; }
        else if (iid === 'convencao_niveis') { short = 'Conv. Níveis'; sub = 'conv.'; ico = '📏'; kind = 'conv'; }
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

  /** Preferência ao abrir pav: Torre 1 → qualquer torre → Bruto */
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
    return docs.filter(function (d) { return d.tipo === 'bruto'; })[0] || docs[0] || null;
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
      ];
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
        items: g.ids.map(function (id) {
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
    var parts = [];
    function link(label, level) {
      parts.push('<button type="button" class="drill-crumb-link" data-drill="jump" data-level="' +
        level + '">' + esc(label) + '</button>');
    }
    function strong(label) { parts.push('<b>' + esc(label) + '</b>'); }
    function sep() { parts.push('<span class="drill-sep">›</span>'); }

    link(OBRA_NOME, 'pavs');
    if (state.level === 'pavs') return parts.join(' ');
    sep();
    if (state.level === 'hub') { strong(state.pav); return parts.join(' '); }
    link(state.pav, 'hub');
    if (!state.etapa) return parts.join(' ');
    sep();
    var et = ETAPAS.filter(function (e) { return e.id === state.etapa; })[0];
    if (state.level === 'etapa') { strong((et && (et.nome + ' · ' + et.short)) || state.etapa); return parts.join(' '); }
    link((et && et.short) || state.etapa, 'etapa');
    if (state.classe) {
      sep();
      strong(tituloClasse(state.classe));
    }
    return parts.join(' ');
  }

  function backLabel() {
    if (state.rightTorre) return '← fechar Torre limpa (dir.)';
    if (state.level === 'hub') return '← pavimentos';
    if (state.level === 'etapa') return '← hub do pavimento';
    if (state.level === 'itens' && state.vigaKey) return '← lista de vigas';
    if (state.level === 'itens') return '← classes da etapa';
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
    // Entrada única do detalhamento consolidado das etapas SA, N3 e N5.
    var etapas = ETAPAS.filter(function (e) { return e.id === 'sa'; }).map(function (e) {
      var hubLabel = e.hubLabel || (e.nome + ' · ' + e.short);
      return '<button type="button" class="drill-etapa-row" data-drill="etapa" data-id="' + e.id +
        '" title="Abrir ' + esc(hubLabel) + '">' +
        '<span class="lab"><span class="k">' + esc(hubLabel) + '</span></span>' +
        '<span class="seta">▸</span></button>';
    }).join('');
    return (
      '<div class="drill-sec">Estrutural · ' + esc(state.pav) + ' <em>só seleciona</em></div>' + tiles +
      '<div class="drill-sec">Etapas <em>abre classes</em></div>' +
      '<div class="drill-etapa-list">' + etapas + '</div>'
    );
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

  function renderEtapa() {
    var et = ETAPAS.filter(function (e) { return e.id === state.etapa; })[0];
    var groups = groupsForEtapa(state.etapa, state.classesCache || []);
    var html = '<div class="drill-sec">Motores · SA / N3 / N5 <em>' + esc(state.pav) +
      '</em></div>' + renderUnifiedProcBox();
    groups.forEach(function (g) {
      html += '<div class="drill-cls-grp">' + esc(g.nome) + '</div><div class="drill-cls-list">';
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

  function renderUnifiedProcBox() {
    var statuses = ETAPAS.map(function (et) {
      var statusEl = et.procStatusId ? document.getElementById(et.procStatusId) : null;
      var value = statusEl ? statusEl.textContent : '—';
      return '<div class="drill-engine-status"><b>' + esc(et.short) + '</b><span>' + esc(value) + '</span></div>';
    }).join('');
    return '<div class="drill-proc drill-proc-unified"><div class="ph">Status conjunto · ' + esc(state.pav) +
      '</div><div class="drill-engine-statuses">' + statuses + '</div>' +
      '<button type="button" class="run" data-drill="proc-global" data-id="sa">Rodar interpretação · todas as classes</button>' +
      '<button type="button" class="run" data-drill="proc-global" data-id="n3">Rodar desenho · todas as classes</button>' +
      '<button type="button" class="run" data-drill="proc-global" data-id="n5">Rodar unificação · todas as classes</button>' +
      '<button type="button" class="run run-all" data-drill="proc-global" data-id="all">Processar todos os motores · todas as classes</button>' +
      '<div class="hint">SA interpreta e já materializa o N3 da mesma rodada; o botão N3 revalida o SA da classe antes de redesenhar; N5 unifica somente classes validadas.</div></div>';
  }

  function renderItens() {
    var viga = isVigaClass(state.classe);
    var combinada = lateralCombinada(state.classe);
    var nomeClasse = tituloClasse(state.classe);
    var html = '<div class="drill-structural-home-wrap">' +
      '<button type="button" class="drill-structural-home" data-drill="structural-home" ' +
      'title="Voltar ao estrutural limpo deste pavimento">' +
      '<span class="ico" aria-hidden="true">←</span><span>Estrutural limpo</span></button></div>' +
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
        html += '<button type="button" class="drill-pi' + on + (it.validado ? ' human-ok' : '') + '" data-drill="item" data-id="' +
          esc(it.item_id) + '">' + esc(it.titulo || it.item_id) + renderQaBadges(it.qa_reviews || {}) + '</button>';
      });
      html += '</div>';
      if (!state.itens.length) html += '<div class="drill-empty">Nenhum item nesta classe.</div>';
    }

    if (!combinada) {
      html +=
        '<button type="button" class="drill-criar' + (state.rightTorre ? ' on' : '') +
        '" data-drill="criar-item"><span class="plus">+</span> Criar novo item</button>' +
        '<div class="drill-hint">Abre a Torre limpa à direita · coluna fica nesta classe</div>';
    }
    html += renderClassFooter();
    return html;
  }

  function renderClassActions(nomeClasse) {
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
      '<button type="button" data-drill="proc-class" data-id="sa">Rodar motor interpretativo<br><b>' + esc(nomeClasse) + ' · SA</b></button>' +
      '<div class="drill-qa-class" aria-label="Revisão agentiva C1 C2 C3">' +
        ['L1', 'L2', 'L3'].map(function (layer) {
          var run = qaRunFor(layer);
          var active = qaIsActive(run);
          return '<button type="button" data-drill="proc-qa-class" data-id="' + layer + '"' +
            (qaEnabled && !active ? '' : ' disabled' + (!qaEnabled ? ' title="Motor agentivo ainda não disponível para esta classe"' : ' aria-disabled="true"')) +
            (active ? ' class="is-processing"' : '') +
            '><span>C' + layer.substring(1) + '</span><small>' + (active ? 'processando…' : 'QA') + '</small></button>';
        }).join('') + '</div>' + qaStatusHtml +
      '<button type="button" data-drill="proc-class" data-id="n3">Rodar motor de desenho<br><b>' + esc(nomeClasse) + ' · N3</b></button>' +
      '<button type="button" data-drill="proc-class" data-id="n5">Rodar motor de unificação<br><b>' + esc(nomeClasse) + ' · N5</b></button>' +
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
    var html = '<button type="button" class="drill-unified" data-drill="unificados">Visualizar unificados</button>' +
      '<div class="drill-cls-grp">Outras classes</div><div class="drill-other-classes">';
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
    else if (state.level === 'itens') body = renderItens();

    root.innerHTML =
      '<div class="drill-crumb">' + crumbHtml() + '</div>' +
      (back ? '<button type="button" class="drill-back" data-drill="back">' + esc(back) + '</button>' : '') +
      '<div class="drill-scroll">' + body + '</div>';

    root.querySelectorAll('[data-drill]').forEach(function (el) {
      el.addEventListener('click', function () {
        handle(el.getAttribute('data-drill'), el.getAttribute('data-id'), el.getAttribute('data-level'));
      });
    });
  }

  function handle(act, id, level) {
    if (act === 'structural-home') {
      // Um destaque ativo reabre sua classe SA pelo hook openSaClasse.
      // O botão "Nenhuma" já limpa o destaque e chama goHub sem remontar
      // o viewer; use esse caminho para evitar uma reabertura assíncrona.
      var clearHighlights = document.getElementById('destaque-nenhuma');
      window._criarItemClassePref = null;
      window._criarItemVigaPref = null;
      if (clearHighlights && typeof clearHighlights.click === 'function') {
        clearHighlights.click();
        return;
      }
      state.level = 'hub'; state.etapa = null; state.classe = null;
      state.itens = []; state.vigaKey = null; state.itemId = null; state.rightTorre = false;
      var structuralDoc = pickDefaultDoc(state.pav);
      state.selDoc = structuralDoc ? structuralDoc.id : null;
      render();
      if (structuralDoc) openDoc(structuralDoc);
      else if (window.mostrarDetalhe) window.mostrarDetalhe('triagem');
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
        state.level = 'etapa'; state.classe = null; state.itens = [];
        state.itemId = null; state.vigaKey = null; render(); return;
      }
      if (state.level === 'etapa') {
        state.level = 'hub'; state.etapa = null; state.classe = null; render(); return;
      }
      if (state.level === 'hub') {
        goPavsList();
        return;
      }
      return;
    }
    if (act === 'pav') {
      state.pav = id; state.level = 'hub';
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
      state.selDoc = (state.selDoc === id) ? null : id;
      state.rightTorre = false;
      if (state.selDoc) {
        var d = recortesDoPav(state.pav).filter(function (x) { return x.id === state.selDoc; })[0];
        if (d) openDoc(d);
      }
      render();
      return;
    }
    if (act === 'etapa') {
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
      enqueueMotor(id, null, true);
      return;
    }
    if (act === 'unificados') {
      if (window.mostrarDetalhe) window.mostrarDetalhe('n5');
      return;
    }
  }

  function enqueueMotor(stage, classe, global) {
    var endpoint = stage === 'all' ? 'motores' : stage;
    var body = { pav: state.pav, secao: classe ? [secaoMotor(classe)] : [] };
    if (stage === 'n5') {
      var n5 = classeN5(classe);
      if (!n5 && !global) return;
      body = { classe: n5 || 'ALL', pavimento: state.pav };
    }
    fetch('/obras/' + OBRA_ID + '/' + endpoint, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    }).then(function (response) {
      return response.json().then(function (data) {
        if (!response.ok) throw new Error(data.detail || ('HTTP ' + response.status));
        return data;
      });
    }).then(function (data) {
      if (data.job_id && window._todosJobs) {
        window._todosJobs.push({ id: data.job_id, status: 'na_fila', meta: data.meta || {
          etapa: stage, pav: state.pav, secao: body.secao
        }, enfileirado_em: new Date().toISOString() });
      }
      render();
    }).catch(function (error) {
      window.alert('Não foi possível executar: ' + error.message);
    });
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
        det.innerHTML = '<div class="recorte-viewer" id="recorte-viewer-bruto-drill"></div>';
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
      if (window.mostrarDetalhe) window.mostrarDetalhe('triagem');
    }
  }

  function openItem(itemId) {
    var et = ETAPAS.filter(function (e) { return e.id === state.etapa; })[0];
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
        state.classesCache.push({ classe: 'laterais_para', titulo: 'Segmentos Lateral A.B. · Para',
          total: Number((by.lateral_a_para || {}).total || 0) + Number((by.lateral_b_para || {}).total || 0) });
        state.classesCache.push({ classe: 'laterais_passa', titulo: 'Segmentos Lateral A.B. · Passa',
          total: Number((by.lateral_a_passa || {}).total || 0) + Number((by.lateral_b_passa || {}).total || 0) });
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
    state.etapa = 'sa';
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
    state: state,
    render: render,
    // Fonte canônica da navegação por pavimento. O painel de status deve
    // consumir esta mesma lista para nunca exibir pavimentos divergentes.
    listPavimentos: listPavimentos,
    pickDefaultDoc: pickDefaultDoc,
    recortesDoPav: recortesDoPav,
    openSaClasse: openSaClasse,
    goPavsList: goPavsList,
    goHub: goHub,
    refreshItems: function () {
      if (state.level !== 'itens') return;
      loadItens(function () { render(); });
    }
  };

  var _origMontar = window.montarListaTriagem;
  window.montarListaTriagem = function () {
    // não pinta a árvore gorda na sidebar; só sincroniza dados + drill
    try {
      ensureDocsDetalhe();
      if (_origMontar && root.getAttribute('data-legacy-tree') === '1') _origMontar();
    } catch (e) { /* */ }
    onDataReady();
  };

  // re-paint quando recortes chegam
  var tries = 0;
  var boot = setInterval(function () {
    tries += 1;
    onDataReady();
    if ((window._recortesBrutosCache && window._recortesBrutosCache.length) || tries > 8) {
      clearInterval(boot);
    }
  }, 350);
  resumeSavedQaRuns();
})();
