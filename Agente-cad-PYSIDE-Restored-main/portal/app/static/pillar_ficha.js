(function () {
  'use strict';

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function number(value) { var n = Number(value); return Number.isFinite(n) ? n : 0; }
  function field(label, value, change, title) {
    var wrap = el('label', 'plf-field');
    wrap.title = title || label;
    wrap.appendChild(el('span', '', label));
    var input = el('input'); input.type = 'number'; input.step = '0.1'; input.min = '0'; input.value = number(value);
    input.addEventListener('input', function () { change(number(input.value)); });
    wrap.appendChild(input); return wrap;
  }
  function button(text, title, action, cls) {
    var b = el('button', cls || '', text); b.type = 'button'; b.title = title || text; b.addEventListener('click', action); return b;
  }
  function nextId(face, panels) {
    var max = panels.reduce(function (n, p) { var m = String(p.id || '').match(/(\d+)$/); return Math.max(n, m ? Number(m[1]) : 0); }, 0);
    return face + '-painel-' + (max + 1);
  }

  function App(root, options) {
    this.root = root; this.options = options; this.data = null; this.tab = 'abcd-para'; this.timer = null;
    this.load();
  }
  App.prototype.url = function () {
    return '/obras/' + this.options.obraId + '/n1/' + this.options.classe + '/' + encodeURIComponent(this.options.itemId) +
      '/pilar-n3-ficha' + (this.options.pavimento ? '?pavimento=' + encodeURIComponent(this.options.pavimento) : '');
  };
  App.prototype.load = function () {
    var self = this; self.root.innerHTML = '<p class="muted">Carregando ficha N3 do pilar…</p>';
    fetch(self.url()).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (body) { self.data = body.ficha; self.render(); })
      .catch(function (err) { self.root.innerHTML = '<p class="plf-error">Não foi possível carregar a ficha N3: ' + err.message + '</p>'; });
  };
  App.prototype.changed = function () {
    var self = this, status = self.root.querySelector('.plf-status');
    if (status) status.textContent = 'Alterado · salvando…';
    clearTimeout(self.timer); self.timer = setTimeout(function () { self.save(); }, 650);
  };
  App.prototype.save = function () {
    var self = this, status = self.root.querySelector('.plf-status');
    fetch(self.url(), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ficha:self.data})})
      .then(function (r) { return r.json().then(function (body) { if (!r.ok) throw new Error(body.detail || 'HTTP ' + r.status); return body; }); })
      .then(function (body) { self.data = body.ficha; if (status) status.textContent = 'Salvo · revisão ' + body.revision; })
      .catch(function (err) { if (status) { status.textContent = 'Erro ao salvar: ' + err.message; status.classList.add('error'); } });
  };
  App.prototype.render = function () {
    var self = this; self.root.innerHTML = ''; self.root.className = 'pillar-ficha-app';
    var shell = el('section', 'plf-shell');
    var header = el('div', 'plf-header');
    var title = el('div'); title.appendChild(el('strong', '', 'Ficha N3 · ' + self.data.pillar));
    title.appendChild(el('span', 'plf-special', self.data.special ? 'Pilar especial · faces A–H habilitadas' : 'Pilar normal · faces A–D'));
    header.appendChild(title); header.appendChild(el('span', 'plf-status', self.data.source.human_override ? 'Override humano carregado' : 'Preenchido pelo SA/N1'));
    shell.appendChild(header);
    var help = el('details', 'plf-help');
    help.appendChild(el('summary', '', 'Como o SA/N1 preenche esta ficha e quando editar'));
    var guide = el('div', 'plf-help-grid');
    [
      ['Dimensões e níveis', 'Vêm do contorno e dos níveis do SA. Corrija somente quando a leitura estrutural estiver errada.'],
      ['Painéis', 'A1 nasce com 2 cm. Largura, altura e distância controlam a célula e o N3 na mesma escala métrica.'],
      ['Distância do painel', 'Na primeira coluna mede da parede esquerda; nas demais, do painel imediatamente anterior.'],
      ['Abertura esquerda/direita', 'A distância é medida da parede do mesmo lado. Com distância 0, a abertura permanece dentro do painel.'],
      ['Vazio e hatch', 'Vazio de laje/viga fica vermelho; hatch é exclusivo da célula e aparece imediatamente na ficha.'],
      ['Grades e sarrafos', 'Grades usam Grade 1/Distância 1/Grade 2/Distância 2/Grade 3. Sarrafos horizontais exigem distâncias esquerda e direita.'],
      ['Pilar especial', 'As faces E–H aparecem quando o contorno N1 não é retangular ou quando a Fase 4 já possui essas faces.']
    ].forEach(function(row){var item=el('div');item.appendChild(el('b','',row[0]));item.appendChild(el('span','',row[1]));guide.appendChild(item);});
    help.appendChild(guide); shell.appendChild(help);
    var tabs = el('div', 'plf-tabs');
    [['cima','N3 Cima'],['abcd-para','ABCD Para'],['abcd-passa','ABCD Passa'],['grades-para','Grades Para'],['grades-passa','Grades Passa']].forEach(function (spec) {
      tabs.appendChild(button(spec[1], '', function () { self.tab = spec[0]; self.render(); }, self.tab === spec[0] ? 'active' : ''));
    });
    shell.appendChild(tabs);
    if (self.tab === 'cima') shell.appendChild(self.renderCima());
    else if (self.tab.indexOf('abcd') === 0) shell.appendChild(self.renderFaces());
    else shell.appendChild(self.renderGrades());
    self.root.appendChild(shell);
  };
  App.prototype.renderCima = function () {
    var self = this, d = self.data.dimensions, box = el('div', 'plf-cima'), topView = self.data.top_view || {};
    box.appendChild(el('h4', '', 'Visão de cima · dimensões canônicas do SA/N1'));
    var fields = el('div', 'plf-cima-fields');
    [['length','Comprimento'],['width','Largura'],['height','Pé-direito'],['nivel_chegada','Nível chegada'],['nivel_saida','Nível saída']].forEach(function (spec) {
      fields.appendChild(field(spec[1], d[spec[0]], function (v) { d[spec[0]] = v; self.changed(); }));
    });
    box.appendChild(fields);
    var meta = el('div', 'plf-cima-meta');
    meta.appendChild(el('span','', 'Classificação: ' + (topView.classification || (self.data.special ? 'Especial' : 'Retangular'))));
    meta.appendChild(el('span','', 'Orientação: ' + (topView.orientation || 'derivada do contorno N1'))); box.appendChild(meta);
    var points = (topView.points || []).filter(function(p){return Array.isArray(p) && p.length >= 2;});
    if (points.length >= 3) {
      var xs=points.map(function(p){return number(p[0]);}), ys=points.map(function(p){return number(p[1]);}), minX=Math.min.apply(null,xs), maxX=Math.max.apply(null,xs), minY=Math.min.apply(null,ys), maxY=Math.max.apply(null,ys);
      var svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('class','plf-cima-svg');svg.setAttribute('viewBox',(minX-5)+' '+(minY-5)+' '+Math.max(10,maxX-minX+10)+' '+Math.max(10,maxY-minY+10));
      var poly=document.createElementNS('http://www.w3.org/2000/svg','polygon');poly.setAttribute('points',points.map(function(p){return number(p[0])+','+number(p[1]);}).join(' '));svg.appendChild(poly);box.appendChild(svg);
    } else {
      var shape = el('div', 'plf-cima-shape', d.length + ' × ' + d.width + ' cm'); shape.style.aspectRatio = Math.max(1, d.length) + ' / ' + Math.max(1, d.width); box.appendChild(shape);
    }
    var faceFields=el('div','plf-cima-face-fields');
    Object.keys(self.data.faces).forEach(function(face){var panels=self.data.faces[face].panels||[], width=Math.max.apply(null,panels.map(function(p){return number(p.distance)+number(p.width);}).concat([0]));var item=el('div');item.appendChild(el('b','', 'Face '+face));item.appendChild(el('span','', width+' cm · '+panels.length+' célula(s)'));faceFields.appendChild(item);});box.appendChild(faceFields);
    return box;
  };
  App.prototype.renderFaces = function () {
    var self = this, board = el('div', 'plf-ledger');
    var intro = el('div', 'plf-ledger-title'); intro.appendChild(el('b', '', self.tab === 'abcd-para' ? 'ABCD · PARA' : 'ABCD · PASSA'));
    intro.appendChild(el('span', '', 'Scroll aplica zoom; clique apenas foca a face. Medidas em cm, mesma escala X/Y.'));
    board.appendChild(intro);
    var grid = el('div', 'plf-face-grid');
    Object.keys(self.data.faces).forEach(function (face) { grid.appendChild(self.renderFace(face, self.data.faces[face])); });
    board.appendChild(grid); return board;
  };
  App.prototype.renderFace = function (face, data) {
    var self = this, card = el('article', 'plf-face');
    var head = el('div', 'plf-face-head'); head.appendChild(el('b', '', 'FACE ' + face));
    var tools = el('div', 'plf-face-tools');
    tools.appendChild(button('+H','Adicionar linha de altura nesta face',function(){self.addRow(face);},'plf-mini'));
    tools.appendChild(button('−H','Remover última linha desta face',function(){self.removeRow(face);},'plf-mini'));
    tools.appendChild(button('+L','Adicionar coluna de largura nesta face',function(){self.addColumn(face);},'plf-mini'));
    tools.appendChild(button('−L','Remover última coluna desta face',function(){self.removeColumn(face);},'plf-mini'));
    head.appendChild(tools); card.appendChild(head);
    var viewport = el('div', 'plf-viewport'); viewport.tabIndex = 0;
    var canvas = el('div', 'plf-canvas'); viewport.appendChild(canvas); card.appendChild(viewport);
    this.layoutFace(canvas, face, data);
    var scale = 1;
    viewport.addEventListener('wheel', function(e){ e.preventDefault(); scale=Math.max(1,Math.min(5,scale*(e.deltaY<0?1.12:1/1.12))); canvas.style.transform='scale('+scale+')'; }, {passive:false});
    viewport.addEventListener('click', function(){ viewport.focus(); });
    card.appendChild(this.renderOpenings(face, data)); return card;
  };
  App.prototype.layoutFace = function (canvas, face, data) {
    var self = this, panels = data.panels, rows = {}, columns = {};
    panels.forEach(function(p){ rows[p.row]=Math.max(rows[p.row]||0,number(p.height)); columns[p.column]=Math.max(columns[p.column]||0,number(p.distance)+number(p.width)); });
    var rowIds=Object.keys(rows).map(Number).sort(function(a,b){return a-b;}), colIds=Object.keys(columns).map(Number).sort(function(a,b){return a-b;});
    var totalW=colIds.reduce(function(s,c){return s+columns[c];},0)||1, totalH=rowIds.reduce(function(s,r){return s+rows[r];},0)||1;
    canvas.style.aspectRatio=totalW+' / '+totalH; canvas.dataset.totalWidth=totalW; canvas.dataset.totalHeight=totalH;
    var xOffsets={}, yOffsets={}, x=0, y=0; colIds.forEach(function(c){xOffsets[c]=x;x+=columns[c];}); rowIds.slice().reverse().forEach(function(r){yOffsets[r]=y;y+=rows[r];});
    panels.forEach(function(p){
      var popDirection = p.row <= Math.ceil(rowIds.length / 2) ? ' pop-up' : ' pop-down';
      var cell=el('div','plf-cell kind-'+p.kind+' hatch-'+p.hatch+popDirection); cell.style.left=((xOffsets[p.column]+number(p.distance))/totalW*100)+'%';
      cell.style.width=(number(p.width)/totalW*100)+'%'; cell.style.bottom=(yOffsets[p.row]/totalH*100)+'%'; cell.style.height=(number(p.height)/totalH*100)+'%';
      cell.appendChild(el('span','plf-cell-name',p.id)); cell.appendChild(el('span','plf-cell-dim',number(p.width)+' × '+number(p.height)));
      var pop=el('div','plf-cell-pop');
      var kinds=el('div','plf-kind-picker'); [['panel','Painel'],['slab_void','Vazio laje'],['beam_void','Vazio viga']].forEach(function(k){pop.appendChild(button(k[1],'',function(e){p.kind=k[0];self.changed();self.render();},p.kind===k[0]?'active':''));});
      pop.appendChild(kinds);
      pop.appendChild(field(p.column===1?'Dist. parede esq.':'Dist. painel anterior',p.distance,function(v){p.distance=v;self.changed();self.render();}));
      pop.appendChild(field('Largura',p.width,function(v){p.width=v;self.changed();self.render();})); pop.appendChild(field('Altura',p.height,function(v){p.height=v;self.changed();self.render();}));
      var hatch=el('div','plf-hatch'); hatch.appendChild(el('span','','Hatch'));
      [['none','○'],['checker','▦'],['striped','▨']].forEach(function(h){hatch.appendChild(button(h[1],h[0],function(){p.hatch=h[0];self.changed();self.render();},p.hatch===h[0]?'active':''));}); pop.appendChild(hatch);
      pop.appendChild(button('Excluir painel','Excluir somente esta célula',function(){data.panels=data.panels.filter(function(v){return v!==p;});self.changed();self.render();},'plf-delete'));
      cell.appendChild(pop); canvas.appendChild(cell);
    });
    ['left','right'].forEach(function(side){(data.openings[side]||[]).forEach(function(o,i){ if(!o.width||!o.depth)return; var overlay=el('div','plf-opening '+side,(side==='left'?'E':'D')+(i+1)); var ox=side==='left'?o.distance:Math.max(0,totalW-o.distance-o.width); var oy=o.level||Math.max(0,totalH-o.top_distance-o.depth); overlay.style.left=(ox/totalW*100)+'%';overlay.style.width=(o.width/totalW*100)+'%';overlay.style.bottom=(oy/totalH*100)+'%';overlay.style.height=(o.depth/totalH*100)+'%';canvas.appendChild(overlay);});});
  };
  App.prototype.addRow = function(face){var d=this.data.faces[face], rows=d.panels.map(function(p){return p.row;}), cols=d.panels.map(function(p){return p.column;}), row=Math.max.apply(null,rows.concat([0]))+1, self=this; Array.from(new Set(cols)).forEach(function(c){var ref=d.panels.find(function(p){return p.column===c;});d.panels.push({id:nextId(face,d.panels),row:row,column:c,distance:0,width:ref?ref.width:30,height:40,kind:'panel',hatch:'none'});});self.changed();self.render();};
  App.prototype.removeRow = function(face){var d=this.data.faces[face], max=Math.max.apply(null,d.panels.map(function(p){return p.row;}).concat([1]));if(max>1)d.panels=d.panels.filter(function(p){return p.row!==max;});this.changed();this.render();};
  App.prototype.addColumn = function(face){var d=this.data.faces[face], cols=d.panels.map(function(p){return p.column;}), rows=d.panels.map(function(p){return p.row;}), col=Math.max.apply(null,cols.concat([0]))+1; Array.from(new Set(rows)).forEach(function(r){var ref=d.panels.find(function(p){return p.row===r;});d.panels.push({id:nextId(face,d.panels),row:r,column:col,distance:0,width:ref?ref.width:30,height:ref?ref.height:40,kind:'panel',hatch:'none'});});this.changed();this.render();};
  App.prototype.removeColumn = function(face){var d=this.data.faces[face],max=Math.max.apply(null,d.panels.map(function(p){return p.column;}).concat([1]));if(max>1)d.panels=d.panels.filter(function(p){return p.column!==max;});this.changed();this.render();};
  App.prototype.renderOpenings = function(face,data){var self=this, groups=el('div','plf-opening-groups');['left','right'].forEach(function(side){var group=el('section','plf-opening-group '+side), h=el('div','plf-opening-head');h.appendChild(el('b','',side==='left'?'Aberturas esquerda':'Aberturas direita'));h.appendChild(button('+ abertura','Máximo 4 por lado',function(){if(data.openings[side].length<4){data.openings[side].push({distance:0,width:0,depth:0,level:0,top_distance:0});self.changed();self.render();}},'plf-add'));group.appendChild(h);data.openings[side].forEach(function(o,i){var row=el('div','plf-opening-row');row.appendChild(el('strong','',(side==='left'?'E':'D')+(i+1)));row.appendChild(field(side==='left'?'Dist. esquerda':'Dist. direita',o.distance,function(v){o.distance=v;self.changed();self.render();}));row.appendChild(field('Largura',o.width,function(v){o.width=v;self.changed();self.render();}));row.appendChild(field('Profundidade',o.depth,function(v){o.depth=v;self.changed();self.render();}));row.appendChild(field('Nível',o.level,function(v){o.level=v;self.changed();self.render();}));row.appendChild(field('Dist. topo',o.top_distance,function(v){o.top_distance=v;self.changed();self.render();}));row.appendChild(button('×','Excluir abertura',function(){data.openings[side].splice(i,1);self.changed();self.render();},'plf-delete'));group.appendChild(row);});groups.appendChild(group);});return groups;};
  App.prototype.renderGrades = function(){var self=this,g=self.data.grades,wrap=el('div','plf-grades');var top=el('div','plf-grade-top');[['grade_1','Grade 1'],['distance_1','Distância 1'],['grade_2','Grade 2'],['distance_2','Distância 2'],['grade_3','Grade 3']].forEach(function(s){top.appendChild(field(s[1],g[s[0]],function(v){g[s[0]]=v;self.changed();}));});wrap.appendChild(top);wrap.appendChild(el('h4','','Detalhamento das grades · cada coluna alterna sarrafo e distância'));var table=el('table','plf-slat-table'),thead=el('thead'),hr=el('tr');hr.appendChild(el('th','', ''));g.vertical_slats.forEach(function(s,i){hr.appendChild(el('th','', 'Sarrafo V'+(i+1)));hr.appendChild(el('th','', 'Dist. '+(i+1)));});thead.appendChild(hr);table.appendChild(thead);var body=el('tbody');['width','height'].forEach(function(key){var tr=el('tr');tr.appendChild(el('th','',key==='width'?'Largura':'Altura'));g.vertical_slats.forEach(function(s){var td=el('td');td.appendChild(field('',s[key],function(v){s[key]=v;self.changed();}));tr.appendChild(td);var dist=el('td');if(key==='width')dist.appendChild(field('',s.distance,function(v){s.distance=v;self.changed();}));else dist.textContent='—';tr.appendChild(dist);});body.appendChild(tr);});table.appendChild(body);wrap.appendChild(table);wrap.appendChild(button('+ sarrafo vertical','',function(){g.vertical_slats.push({width:5,height:5,distance:0});self.changed();self.render();},'plf-add'));var hh=el('div','plf-horizontal-head');hh.appendChild(el('h4','','Sarrafos horizontais'));hh.appendChild(button('+ sarrafo','',function(){g.horizontal_slats.push({left_distance:0,right_distance:0,width:5,height:5});self.changed();self.render();},'plf-add'));wrap.appendChild(hh);g.horizontal_slats.forEach(function(s,i){var row=el('div','plf-horizontal-row');row.appendChild(el('strong','', 'Sarrafo H'+(i+1)));[['left_distance','Dist. esquerda'],['right_distance','Dist. direita'],['width','Largura'],['height','Altura']].forEach(function(k){row.appendChild(field(k[1],s[k[0]],function(v){s[k[0]]=v;self.changed();}));});row.appendChild(button('×','Excluir',function(){g.horizontal_slats.splice(i,1);self.changed();self.render();},'plf-delete'));wrap.appendChild(row);});return wrap;};

  window.PillarFicha = { mount:function(root,options){ if(root) return new App(root,options); } };
})();
