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
    lateral_b_passa: 1
  };

  var SA_GROUPS = [
    { nome: 'Pré-interpretação', ids: ['cortes', 'convencao_pilares', 'convencao_niveis_lajes'] },
    { nome: 'Pilares', ids: ['pilares', 'pilares_especiais'] },
    { nome: 'Lajes', ids: ['lajes'] },
    { nome: 'Vigas', ids: ['fundo', 'lateral_a_para', 'lateral_a_passa', 'lateral_b_para', 'lateral_b_passa'] }
  ];

  var N3_GROUPS = [
    { nome: 'Pilares', ids: ['pilares_n3_para', 'pilares_n3_passa'] },
    { nome: 'Lajes', ids: ['lajes'] },
    { nome: 'Vigas', ids: ['fundo', 'lateral_a_para', 'lateral_a_passa', 'lateral_b_para', 'lateral_b_passa'] }
  ];

  var ETAPAS = [
    { id: 'sa', short: 'SA', nome: 'Interpretação', stage: 'n1', btn: 'btn-rodar-sa',
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
    selDoc: null
  };

  // Só aplica ?pavimento= da URL no boot. Sem isso, "← pavimentos" voltava
  // pro hub na hora: selecionarTriagemGeral → montarListaTriagem → onDataReady
  // relia a query e reabria o pav (achado 2026-07-31).
  var _urlPavBootDone = false;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
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
      var tit = (state.classesCache || []).filter(function (c) { return c.classe === state.classe; })[0];
      strong((tit && tit.titulo) || state.classe);
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
    // Lista vertical original: 1 linha = 1 botão (Interpretação · SA ›)
    var etapas = ETAPAS.map(function (e) {
      return '<button type="button" class="drill-etapa-row" data-drill="etapa" data-id="' + e.id +
        '" title="Abrir ' + esc(e.nome) + ' · ' + e.short + '">' +
        '<span class="lab"><span class="k">' + esc(e.nome) + ' · ' + esc(e.short) + '</span></span>' +
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
    return (
      '<div class="drill-proc">' +
        '<div class="ph">Status · ' + esc(state.pav) + '</div>' +
        '<div class="pr"><span>Progresso:</span><strong>' + esc(statusTxt) + '</strong></div>' +
        '<div class="bar"><i style="width:' + esc(barW) + '"></i></div>' +
        '<button type="button" class="run" data-drill="proc" data-id="' + et.id + '">' + esc(et.procLabel) + '</button>' +
        '<div class="hint">' + (et.id === 'n5'
          ? 'Roda as unificações do pavimento. Cada classe abaixo também é acessível.'
          : 'Roda a análise desta etapa para o pavimento selecionado.') + '</div>' +
      '</div>'
    );
  }

  function renderEtapa() {
    var et = ETAPAS.filter(function (e) { return e.id === state.etapa; })[0];
    var groups = groupsForEtapa(state.etapa, state.classesCache || []);
    var html = '<div class="drill-sec">' + esc(et.nome) + ' · ' + et.short +
      ' <em>' + esc(state.pav) + '</em></div>' + renderProcBox(et);
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

  function renderItens() {
    var viga = isVigaClass(state.classe);
    var tit = (state.classesCache || []).filter(function (c) { return c.classe === state.classe; })[0];
    var nomeClasse = (tit && tit.titulo) || state.classe;
    var html = '<div class="drill-sec">' + esc(nomeClasse) + ' <em>' +
      (viga ? 'vigas' : 'itens') + '</em></div>';

    if (viga) {
      var groups = groupVigaItens(state.itens);
      html += '<div class="drill-itens">';
      groups.forEach(function (g) {
        var on = state.vigaKey === g.key ? ' on' : '';
        html += '<button type="button" class="drill-pi' + on + '" data-drill="viga" data-id="' +
          esc(g.key) + '">' + esc(g.key) + '<span class="subn">' + g.segs.length + ' seg</span></button>';
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
        html += '<button type="button" class="drill-pi' + on + '" data-drill="item" data-id="' +
          esc(it.item_id) + '">' + esc(it.titulo || it.item_id) + '</button>';
      });
      html += '</div>';
      if (!state.itens.length) html += '<div class="drill-empty">Nenhum item nesta classe.</div>';
    }

    html +=
      '<button type="button" class="drill-criar' + (state.rightTorre ? ' on' : '') +
      '" data-drill="criar-item"><span class="plus">+</span> Criar novo item</button>' +
      '<div class="drill-hint">Abre a Torre limpa à direita · coluna fica nesta classe</div>';
    return html;
  }

  function render() {
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
      else { state.vigaKey = id; state.itemId = null; }
      state.rightTorre = false;
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
      state.rightTorre = true; state.itemId = null;
      openTorreCriar();
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
    }
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
    var itens = state.itens;
    var indice = 0;
    for (var i = 0; i < itens.length; i++) {
      if (itens[i].item_id === itemId) { indice = i; break; }
    }
    if (window.setPainel3Estado) {
      window.setPainel3Estado({ stage: stage, classe: state.classe, itens: itens, indice: indice });
    }
    if (stage === 'n1' && window.carregarDetalheItemN1) {
      window.carregarDetalheItemN1(itemId);
      if (window.mostrarDetalhe) window.mostrarDetalhe('n1');
    } else if (stage === 'n3' && window.carregarDetalheItemN3) {
      window.carregarDetalheItemN3(itemId);
      if (window.mostrarDetalhe) window.mostrarDetalhe('n3');
    }
  }

  function openTorreCriar() {
    // Abre a Torre limpa do pav no painel direito (não iframe) com classe pré-selecionada
    // e painel "Criar item" abaixo da validação.
    ensureDocsDetalhe();
    if (window.mostrarDetalhe) window.mostrarDetalhe('triagem');
    window._criarItemClassePref = state.classe || null;
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
        if (done) done();
      })
      .catch(function () { state.classesCache = []; if (done) done(); });
  }

  function loadItens(done) {
    var q = state.pav ? ('?pavimento=' + encodeURIComponent(state.pav)) : '';
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
    pickDefaultDoc: pickDefaultDoc,
    recortesDoPav: recortesDoPav,
    openSaClasse: openSaClasse,
    goPavsList: goPavsList,
    goHub: goHub
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
})();
