/* Aba Base Global (dono): grafo da base de conhecimento em perspectivas.
 * Dados: /app/base-global/grafo.json (scripts/kb/kb_grafo.py). Só leitura. */
(function () {
  "use strict";

  var COR_TIPO = {
    classe: "#111827", fonte: "#2563eb", decisao: "#d97706", termo: "#059669",
    regra: "#7c3aed", codigo: "#6b7280"
  };
  var NOME_TIPO = {
    classe: "Classe", fonte: "Documento", decisao: "Decisão do dono", termo: "Termo do glossário",
    regra: "Regra semântica", codigo: "Módulo de código"
  };
  var ORDEM_STATUS = ["entrada", "canonico", "ativo", "historico", "fora_inventario", "legado"];
  var NOME_STATUS = {
    entrada: "entrada", canonico: "canônico", ativo: "ativo", historico: "histórico",
    fora_inventario: "fora do inventário", legado: "legado"
  };
  var NOME_LACUNA = {
    referencia_quebrada: "Referência quebrada (cita um .md que não existe)",
    decisao_sem_fonte: "Decisão sem fonte achável",
    termo_sem_fonte: "Termo sem fonte achável",
    fonte_orfa: "Documento vivo solto (não cita nem é citado)",
    codigo_sem_docstring: "Módulo citado sem docstring",
    regras_nao_validadas: "Regras semânticas ainda T0"
  };
  var VIVOS = { entrada: 1, canonico: 1, ativo: 1 };

  function vivo(n) { return !!VIVOS[n.status]; }

  var PERSPECTIVAS = [
    { id: "geral", nome: "Mapa geral",
      ajuda: "Documentos vivos, decisões, glossário e as 4 classes. Sem código nem legado.",
      inclui: function (n) { return n.tipo === "classe" || n.tipo === "decisao" || n.tipo === "termo" || (n.tipo === "fonte" && vivo(n)); },
      layout: "cose" },
    { id: "classes", nome: "Por classe (PIL · LV · FV · LAJ)",
      ajuda: "Tudo o que fala de cada classe, agrupado em volta dela. Classe com pouca coisa ao redor = área pouco documentada.",
      inclui: function (n) { return n.tipo === "classe" || (n.classes && n.classes.length && n.tipo !== "codigo" && (n.tipo !== "fonte" || vivo(n))); },
      layout: "cose", soClasse: true },
    { id: "status", nome: "Por status (vivo × legado)",
      ajuda: "Todos os documentos em anéis: canônico no centro, legado na borda. Mostra o peso do que é histórico.",
      inclui: function (n) { return n.tipo === "fonte"; },
      layout: "status" },
    { id: "decisoes", nome: "Decisões do dono",
      ajuda: "Cada decisão ligada ao documento-fonte; seta vermelha = revogação.",
      inclui: function (n, viz) { return n.tipo === "decisao" || (n.tipo === "fonte" && viz.decisao[n.id]); },
      layout: "cose" },
    { id: "glossario", nome: "Glossário",
      ajuda: "Termos e onde a definição completa mora.",
      inclui: function (n, viz) { return n.tipo === "termo" || (n.tipo === "fonte" && viz.termo[n.id]); },
      layout: "cose" },
    { id: "codigo", nome: "Código × documentos",
      ajuda: "Módulos citados pelos documentos vivos. Cinza claro com borda vermelha = sem docstring.",
      inclui: function (n, viz) { return n.tipo === "codigo" || (n.tipo === "fonte" && vivo(n) && viz.codigo[n.id]); },
      layout: "cose" },
    { id: "regras", nome: "Regras semânticas",
      ajuda: "Regras da semantic_rag_kb por classe. Lilás cheio = validada (T1/T2); vazado = T0.",
      inclui: function (n) { return n.tipo === "regra" || n.tipo === "classe"; },
      layout: "cose" },
    { id: "lacunas", nome: "Lacunas — o que falta",
      ajuda: "Só o que tem problema. A lista e a cobertura por classe aparecem no painel da direita.",
      inclui: function (n) { return (n.lacunas && n.lacunas.length) || n.tipo === "classe"; },
      layout: "lacunas", painelLacunas: true }
  ];

  var dados, cy, porId = {}, perspAtual = null, focoVizinhanca = null;

  function el(tag, attrs, filhos) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "texto") e.textContent = attrs[k];
      else if (k === "onclick") e.addEventListener("click", attrs[k]);
      else e.setAttribute(k, attrs[k]);
    });
    (filhos || []).forEach(function (f) { if (f) e.appendChild(typeof f === "string" ? document.createTextNode(f) : f); });
    return e;
  }

  function corta(s, n) { s = s || ""; return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  function vizinhosPorTipo() {
    var viz = { decisao: {}, termo: {}, codigo: {} };
    dados.arestas.forEach(function (a) {
      var s = porId[a.s], t = porId[a.t];
      if (!s || !t) return;
      [[s, t], [t, s]].forEach(function (p) {
        if (viz[p[0].tipo]) viz[p[0].tipo][p[1].id] = true;
      });
    });
    return viz;
  }

  function montar() {
    dados.nos.forEach(function (n) { porId[n.id] = n; });
    var elementos = dados.nos.map(function (n) {
      var tam = n.tipo === "classe" ? 70 : 12 + Math.min(34, Math.sqrt(n.grau || 0) * 5);
      var cls = [n.tipo, "st-" + n.status];
      if (n.lacunas && n.lacunas.length) cls.push("com-lacuna");
      if (n.tipo === "regra" && (n.tier === "T1" || n.tier === "T2")) cls.push("validada");
      if (n.tipo === "codigo" && n.docstring === false) cls.push("sem-doc");
      return { group: "nodes", data: { id: n.id, rotulo: corta(n.label, 34), tam: tam }, classes: cls.join(" ") };
    });
    dados.arestas.forEach(function (a, i) {
      if (porId[a.s] && porId[a.t]) elementos.push({ group: "edges", data: { id: "e" + i, source: a.s, target: a.t }, classes: a.tipo });
    });
    cy = cytoscape({
      container: document.getElementById("bg-grafo"),
      elements: elementos,
      wheelSensitivity: 0.25,
      minZoom: 0.05, maxZoom: 4,
      style: [
        { selector: "node", style: {
          "width": "data(tam)", "height": "data(tam)", "background-color": "#9ca3af",
          "label": "data(rotulo)", "font-size": 9, "min-zoomed-font-size": 7, "color": "#111827",
          "text-valign": "bottom", "text-margin-y": 2, "text-outline-color": "#fff", "text-outline-width": 2,
          "border-width": 1, "border-color": "#fff" } },
        { selector: "node.classe", style: { "background-color": COR_TIPO.classe, "font-size": 18, "font-weight": 700, "color": "#fff", "text-valign": "center", "text-outline-width": 0, "shape": "round-rectangle" } },
        { selector: "node.fonte", style: { "background-color": COR_TIPO.fonte } },
        { selector: "node.decisao", style: { "background-color": COR_TIPO.decisao, "shape": "diamond" } },
        { selector: "node.termo", style: { "background-color": COR_TIPO.termo, "shape": "round-tag" } },
        { selector: "node.regra", style: { "background-color": "#fff", "border-color": COR_TIPO.regra, "border-width": 2, "shape": "hexagon" } },
        { selector: "node.regra.validada", style: { "background-color": COR_TIPO.regra } },
        { selector: "node.codigo", style: { "background-color": COR_TIPO.codigo, "shape": "rectangle" } },
        { selector: "node.codigo.sem-doc", style: { "background-color": "#e5e7eb" } },
        { selector: "node.st-canonico", style: { "border-width": 3, "border-color": "#0f172a" } },
        { selector: "node.st-historico", style: { "opacity": 0.6 } },
        { selector: "node.st-legado", style: { "opacity": 0.35, "border-style": "dashed", "border-color": "#6b7280", "border-width": 2 } },
        { selector: "node.st-fora_inventario", style: { "background-color": "#bfdbfe" } },
        { selector: "node.com-lacuna", style: { "border-color": "#dc2626", "border-width": 3 } },
        { selector: "edge", style: { "width": 0.8, "line-color": "#cbd5e1", "curve-style": "haystack", "opacity": 0.7 } },
        { selector: "edge.classe", style: { "line-color": "#e5e7eb", "line-style": "dashed", "opacity": 0.5 } },
        { selector: "edge.revoga", style: { "line-color": "#dc2626", "width": 2.5, "curve-style": "bezier", "target-arrow-shape": "triangle", "target-arrow-color": "#dc2626", "opacity": 1 } },
        { selector: ".oculto", style: { "display": "none" } },
        { selector: ".sem-rotulo", style: { "label": "" } },
        { selector: "node:selected", style: { "border-color": "#f59e0b", "border-width": 5, "opacity": 1 } },
        { selector: ".esmaecido", style: { "opacity": 0.12 } },
        { selector: "edge.realce", style: { "line-color": "#f59e0b", "width": 2, "opacity": 1 } }
      ]
    });
    cy.on("tap", "node", function (ev) { mostrarDetalhe(ev.target.id()); realcar(ev.target); });
    cy.on("dbltap", "node", function (ev) { abrirVizinhanca(ev.target.id()); });
    cy.on("tap", function (ev) { if (ev.target === cy) limparRealce(); });
  }

  function realcar(no) {
    limparRealce();
    var viz = no.closedNeighborhood();
    cy.elements().not(".oculto").not(viz).addClass("esmaecido");
    viz.edges().addClass("realce");
  }
  function limparRealce() { cy.elements().removeClass("esmaecido realce"); }

  function filtrosAtivos() {
    var tipos = {}, status = {};
    document.querySelectorAll("#bg-filtros-tipo input").forEach(function (i) { tipos[i.value] = i.checked; });
    document.querySelectorAll("#bg-filtros-status input").forEach(function (i) { status[i.value] = i.checked; });
    return { tipos: tipos, status: status };
  }

  function aplicar(relayout) {
    var f = filtrosAtivos(), viz = aplicar.viz || (aplicar.viz = vizinhosPorTipo());
    var visiveis = {};
    if (focoVizinhanca) {
      cy.getElementById(focoVizinhanca).closedNeighborhood().nodes().forEach(function (n) { visiveis[n.id()] = true; });
    } else {
      dados.nos.forEach(function (n) { if (perspAtual.inclui(n, viz)) visiveis[n.id] = true; });
    }
    cy.batch(function () {
      cy.nodes().forEach(function (no) {
        var n = porId[no.id()];
        var ok = visiveis[n.id] && f.tipos[n.tipo] !== false && (n.tipo === "classe" || f.status[n.status] !== false);
        no.toggleClass("oculto", !ok);
      });
      cy.edges().forEach(function (e) {
        e.toggleClass("oculto", e.source().hasClass("oculto") || e.target().hasClass("oculto"));
      });
      cy.elements().toggleClass("sem-rotulo", !document.getElementById("bg-rotulos").checked);
    });
    limparRealce();
    var nNos = cy.nodes().not(".oculto").length, nAr = cy.edges().not(".oculto").length;
    document.getElementById("bg-contagem").textContent =
      (focoVizinhanca ? "Vizinhança de " + porId[focoVizinhanca].label + " · " : perspAtual.nome + " · ") +
      nNos + " nós · " + nAr + " ligações";
    if (relayout !== false) organizar();
  }

  function organizar() {
    var vis = cy.elements().not(".oculto");
    var opts;
    if (!focoVizinhanca && perspAtual.layout === "status") {
      opts = { name: "concentric", animate: false, minNodeSpacing: 4,
        concentric: function (no) { var i = ORDEM_STATUS.indexOf(porId[no.id()].status); return 10 - (i < 0 ? 9 : i); },
        levelWidth: function () { return 1; } };
    } else if (!focoVizinhanca && perspAtual.layout === "lacunas") {
      opts = { name: "grid", animate: false, avoidOverlapPadding: 6,
        sort: function (a, b) {
          var la = (porId[a.id()].lacunas || ["~"])[0], lb = (porId[b.id()].lacunas || ["~"])[0];
          return la < lb ? -1 : la > lb ? 1 : 0;
        } };
    } else if (focoVizinhanca) {
      opts = { name: "concentric", animate: false, minNodeSpacing: 20,
        concentric: function (no) { return no.id() === focoVizinhanca ? 2 : 1; }, levelWidth: function () { return 1; } };
    } else {
      opts = { name: "cose", animate: false, randomize: true, nodeRepulsion: function () { return 9000; },
        idealEdgeLength: function (e) { return e.hasClass("classe") ? 160 : 60; },
        edgeElasticity: function (e) { return e.hasClass("classe") ? 30 : 100; },
        gravity: 0.6, numIter: 1200, nodeDimensionsIncludeLabels: false };
    }
    var carregando = document.getElementById("bg-carregando");
    carregando.hidden = false;
    setTimeout(function () {
      vis.layout(opts).run();
      cy.fit(cy.elements().not(".oculto"), 30);
      carregando.hidden = true;
    }, 20);
  }

  function escolherPerspectiva(id) {
    perspAtual = PERSPECTIVAS.filter(function (p) { return p.id === id; })[0];
    focoVizinhanca = null;
    document.querySelectorAll("#bg-persp button").forEach(function (b) { b.classList.toggle("ativo", b.dataset.id === id); });
    document.getElementById("bg-persp-ajuda").textContent = perspAtual.ajuda;
    aplicar();
    if (perspAtual.painelLacunas) painelLacunas(); else painelVazio();
  }

  function abrirVizinhanca(id) {
    focoVizinhanca = id;
    document.querySelectorAll("#bg-persp button").forEach(function (b) { b.classList.remove("ativo"); });
    document.getElementById("bg-persp-ajuda").textContent = "Vizinhança: o nó e tudo ligado diretamente a ele. Escolha uma perspectiva para voltar.";
    aplicar();
    mostrarDetalhe(id);
    cy.getElementById(id).select();
  }

  function painelVazio() {
    var c = document.getElementById("bg-detalhe-corpo");
    c.innerHTML = "";
    c.appendChild(el("p", { "class": "bg-ajuda", texto: "Clique num nó para ver o que é, de onde vem e com quem se liga. Duplo clique abre a vizinhança dele." }));
    c.appendChild(tabelaCobertura());
  }

  function tabelaCobertura() {
    var cols = [["fontes_vivas", "docs"], ["fontes_canonicas", "canôn."], ["decisoes", "decis."],
      ["termos", "termos"], ["regras_validadas", "T1+"], ["regras_t0", "T0"]];
    var t = el("table", { "class": "bg-cob" });
    t.appendChild(el("tr", {}, [el("th", { texto: "" })].concat(cols.map(function (c) { return el("th", { texto: c[1] }); }))));
    Object.keys(dados.cobertura).forEach(function (cls) {
      var linha = dados.cobertura[cls];
      t.appendChild(el("tr", {}, [el("td", { texto: cls })].concat(cols.map(function (c) {
        var v = linha[c[0]];
        return el("td", { texto: String(v), "class": v === 0 && c[0] !== "regras_t0" ? "zero" : "" });
      }))));
    });
    return el("div", {}, [el("div", { "class": "bg-rotulo", texto: "Cobertura por classe" }), el("div", { "class": "bg-cob-rolagem" }, [t]),
      el("p", { "class": "bg-ajuda", texto: "docs = documentos vivos · canôn. = canônicos · decis. = decisões do dono · T1+ = regras validadas · T0 = regras não validadas. Vermelho = zero." })]);
  }

  function painelLacunas() {
    var c = document.getElementById("bg-detalhe-corpo");
    c.innerHTML = "";
    c.appendChild(tabelaCobertura());
    var grupos = {};
    dados.lacunas.forEach(function (l) { (grupos[l.tipo] = grupos[l.tipo] || []).push(l); });
    Object.keys(grupos).sort(function (a, b) { return grupos[a].length - grupos[b].length; }).forEach(function (tipo) {
      c.appendChild(el("div", { "class": "bg-rotulo", texto: (NOME_LACUNA[tipo] || tipo) + " — " + grupos[tipo].length }));
      var ul = el("ul");
      grupos[tipo].slice(0, 200).forEach(function (l) {
        var n = porId[l.no];
        ul.appendChild(el("li", { title: l.detalhe, onclick: function () { irPara(l.no); } },
          [corta(n ? n.label : l.no, 60) + (l.detalhe && tipo !== "fonte_orfa" && tipo !== "codigo_sem_docstring" ? " → " + corta(l.detalhe, 50) : "")]));
      });
      c.appendChild(ul);
    });
  }

  function irPara(id) {
    var no = cy.getElementById(id);
    if (!no.length) return;
    if (no.hasClass("oculto")) { abrirVizinhanca(id); return; }
    cy.nodes().unselect(); no.select();
    cy.animate({ center: { eles: no }, zoom: Math.max(cy.zoom(), 1.2) }, { duration: 250 });
    realcar(no);
    mostrarDetalhe(id);
  }

  function mostrarDetalhe(id) {
    var n = porId[id], c = document.getElementById("bg-detalhe-corpo");
    if (!n) return;
    c.innerHTML = "";
    c.appendChild(el("h2", { texto: n.label }));
    var tags = el("div");
    tags.appendChild(el("span", { "class": "bg-tag", texto: NOME_TIPO[n.tipo] || n.tipo }));
    if (n.tipo !== "classe") tags.appendChild(el("span", { "class": "bg-tag", texto: NOME_STATUS[n.status] || n.status }));
    (n.classes || []).forEach(function (k) { tags.appendChild(el("span", { "class": "bg-tag", texto: k })); });
    (n.lacunas || []).forEach(function (l) { tags.appendChild(el("span", { "class": "bg-tag lacuna", texto: NOME_LACUNA[l] || l })); });
    c.appendChild(tags);
    var campos = [["titulo", n.tipo === "fonte" ? "Título" : "Texto"], ["path", "Caminho"], ["data", "Data"],
      ["escopo", "Escopo"], ["estado", "Estado"], ["secao", "Seção"], ["tier", "Tier"], ["campo", "Campo"],
      ["linhas", "Linhas"], ["citado_por", "Citado por"], ["motivo", "Status porque"], ["grau", "Ligações"]];
    var dl = el("dl");
    campos.forEach(function (p) {
      var v = n[p[0]];
      if (v === undefined || v === null || v === "" || (p[0] === "titulo" && v === n.label)) return;
      dl.appendChild(el("dt", { texto: p[1] })); dl.appendChild(el("dd", { texto: String(v) }));
    });
    c.appendChild(dl);
    var saida = [], entrada = [];
    dados.arestas.forEach(function (a) {
      if (a.tipo === "classe") return;
      if (a.s === id && porId[a.t]) saida.push([a.t, a.tipo]);
      if (a.t === id && porId[a.s]) entrada.push([a.s, a.tipo]);
    });
    [["Cita / aponta para", saida], ["É citado por", entrada]].forEach(function (g) {
      if (!g[1].length) return;
      c.appendChild(el("div", { "class": "bg-rotulo", texto: g[0] + " (" + g[1].length + ")" }));
      var ul = el("ul");
      g[1].sort(function (a, b) { return porId[a[0]].tipo.localeCompare(porId[b[0]].tipo); }).slice(0, 150).forEach(function (p) {
        var m = porId[p[0]];
        ul.appendChild(el("li", { onclick: function () { irPara(m.id); } },
          [el("span", { "class": "bg-bola", style: "background:" + (COR_TIPO[m.tipo] || "#999") + ";width:8px;height:8px;margin-right:4px" }),
           corta(m.label, 60) + (p[1] === "revoga" ? " (revoga)" : "")]));
      });
      c.appendChild(ul);
    });
    c.appendChild(el("button", { type: "button", "class": "btn-sec btn", texto: "Ver só a vizinhança",
      onclick: function () { abrirVizinhanca(id); } }));
  }

  function montarControles() {
    var persp = document.getElementById("bg-persp");
    PERSPECTIVAS.forEach(function (p) {
      var b = el("button", { type: "button", "data-id": p.id, texto: p.nome, onclick: function () { escolherPerspectiva(p.id); } });
      b.dataset.id = p.id;
      persp.appendChild(b);
    });
    var ft = document.getElementById("bg-filtros-tipo"), fs = document.getElementById("bg-filtros-status");
    Object.keys(NOME_TIPO).forEach(function (t) {
      if (t === "classe") return;
      var i = el("input", { type: "checkbox", value: t }); i.checked = true;
      i.addEventListener("change", function () { aplicar(); });
      ft.appendChild(el("label", { "class": "bg-chk" }, [i, NOME_TIPO[t]]));
    });
    ORDEM_STATUS.forEach(function (s) {
      var i = el("input", { type: "checkbox", value: s }); i.checked = true;
      i.addEventListener("change", function () { aplicar(); });
      fs.appendChild(el("label", { "class": "bg-chk" }, [i, NOME_STATUS[s]]));
    });
    document.getElementById("bg-rotulos").addEventListener("change", function () { aplicar(false); });
    document.getElementById("bg-ajustar").addEventListener("click", function () { cy.fit(cy.elements().not(".oculto"), 30); });
    document.getElementById("bg-relayout").addEventListener("click", organizar);
    var leg = document.getElementById("bg-legenda");
    Object.keys(NOME_TIPO).forEach(function (t) {
      leg.appendChild(el("div", {}, [el("span", { "class": "bg-bola", style: "background:" + COR_TIPO[t] }), NOME_TIPO[t]]));
    });
    leg.appendChild(el("div", {}, [el("span", { "class": "bg-bola", style: "background:#fff;border:3px solid #0f172a" }), "canônico (borda escura)"]));
    leg.appendChild(el("div", {}, [el("span", { "class": "bg-bola", style: "background:#fff;border:3px solid #dc2626" }), "tem lacuna (borda vermelha)"]));
    leg.appendChild(el("div", {}, [el("span", { "class": "bg-bola", style: "background:#9ca3af;opacity:.35" }), "legado / histórico (apagado)"]));

    var busca = document.getElementById("bg-busca"), res = document.getElementById("bg-resultados");
    busca.addEventListener("input", function () {
      var q = busca.value.trim().toLowerCase();
      res.innerHTML = "";
      if (q.length < 2) return;
      dados.nos.filter(function (n) {
        return (n.label || "").toLowerCase().indexOf(q) >= 0 || (n.titulo || "").toLowerCase().indexOf(q) >= 0 ||
          (n.path || "").toLowerCase().indexOf(q) >= 0;
      }).slice(0, 40).forEach(function (n) {
        res.appendChild(el("li", { onclick: function () { irPara(n.id); } },
          [el("span", { "class": "bg-bola", style: "background:" + (COR_TIPO[n.tipo] || "#999") + ";width:8px;height:8px;margin-right:4px" }), corta(n.label, 44)]));
      });
    });
  }

  fetch("/app/base-global/grafo.json", { credentials: "same-origin" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (g) {
      dados = g;
      document.getElementById("bg-gerado").textContent = "gerado em " + g.gerado_em.replace("T", " ") +
        " · " + g.nos.length + " nós · " + g.arestas.length + " ligações · " + g.lacunas.length + " lacunas.";
      montar();
      montarControles();
      escolherPerspectiva("geral");
    })
    .catch(function (e) {
      document.getElementById("bg-carregando").textContent = "Falha ao carregar o grafo: " + e.message;
    });
})();
