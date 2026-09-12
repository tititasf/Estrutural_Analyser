(function () {
  'use strict';

  var FACE_ZOOM_MIN = 0.1;
  var FACE_ZOOM_MAX = 5;

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
    this.root = root; this.options = options; this.data = null; this.views = {}; this.tab = options.initialTab || 'abcd-para'; this.timer = null; this.selectedPanel = null;
    this.load();
  }
  App.prototype.url = function () {
    return '/obras/' + this.options.obraId + '/n1/' + this.options.classe + '/' + encodeURIComponent(this.options.itemId) +
      '/pilar-n3-ficha?' + (this.options.pavimento ? 'pavimento=' + encodeURIComponent(this.options.pavimento) + '&' : '') +
      'vista=' + encodeURIComponent(this.tab);
  };
  App.prototype.load = function () {
    var self = this; self.root.innerHTML = '<p class="muted">Carregando ficha N3 do pilar…</p>';
    fetch(self.url()).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (body) { self.data = body.ficha; self.cimaContract = body.cima_contract || body.ficha; self.views = body.visualizacoes_n3 || {}; self.render(); })
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
      .then(function (body) { self.data = body.ficha; self.cimaContract = body.ficha.cima_contract || self.cimaContract; if (status) status.textContent = 'Salvo · revisão ' + body.revision; })
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
    if (!self.options.hideTabs) {
      var tabs = el('div', 'plf-tabs');
      [['cima','N3 Cima'],['abcd-para','ABCD Para'],['abcd-passa','ABCD Passa'],['grades-para','Grades Para'],['grades-passa','Grades Passa']].forEach(function (spec) {
        tabs.appendChild(button(spec[1], '', function () {
          if (self.tab === spec[0]) return;
          self.tab = spec[0];
          self.load();
        }, self.tab === spec[0] ? 'active' : ''));
      });
      shell.appendChild(tabs);
    }
    if (self.tab === 'cima') shell.appendChild(self.renderCima());
    else if (self.tab.indexOf('abcd') === 0) shell.appendChild(self.renderFaces());
    else if (self.tab.indexOf('grades') === 0) shell.appendChild(self.renderGrades());
    shell.appendChild(self.renderDrawing());
    self.root.appendChild(shell);
    if (window.ativarZoomEmContainer) window.ativarZoomEmContainer(shell);
  };
  App.prototype.renderDrawing = function () {
    var labels = {
      'cima':'N3 Cima', 'abcd-para':'N3 ABCD Para',
      'abcd-passa':'N3 ABCD Passa', 'grades-para':'N3 Grades Para',
      'grades-passa':'N3 Grades Passa'
    };
    var card = el('section', 'n1-foto-card plf-dxf-view');
    card.appendChild(el('h4', '', labels[this.tab] || 'N3'));
    var svg = this.views[this.tab];
    if (!svg) {
      card.classList.add('n1-foto-ausente');
      card.appendChild(el('p', 'muted', 'DXF desta vista ainda não foi gerado.'));
      return card;
    }
    var viewport = el('div', 'zoom-pan-viewport');
    viewport.innerHTML = svg;
    card.appendChild(viewport);
    card.appendChild(el('p', 'zoom-pan-dica', 'Scroll zoom · arraste pan · duplo-clique reseta (viewBox)'));
    return card;
  };
  App.prototype.renderCima = function () {
    var self = this, box = el('div', 'plf-cima'), fields = (this.cimaContract || {}).fields || {};
    function save() { self.data.cima_contract = self.cimaContract; self.changed(); }
    function numericGroup(title, values, max, key) {
      var group = el('section', 'plf-cima-group plf-cima-group-' + max); group.appendChild(el('span', 'plf-cima-label', title));
      var numbers = el('span', 'plf-cima-values');
      for (var index = 0; index < max; index += 1) {
        var input = el('input', 'plf-cima-input'); input.type = 'number'; input.step = '0.1'; input.placeholder = '—';
        input.value = values[index] === undefined || values[index] === null || values[index] === 0 ? '' : values[index];
        input.setAttribute('aria-label', title + ' ' + (index + 1));
        (function (position, control) { control.addEventListener('input', function () { values[position] = control.value === '' ? null : number(control.value); save(); }); })(index, input);
        numbers.appendChild(input);
      }
      group.appendChild(numbers); group.appendChild(el('span', 'plf-cima-unit', 'cm')); return group;
    }
    function single(title, key, target) {
      target = target || fields; var values = [target[key]]; var group = numericGroup(title, values, 1, key);
      group.querySelector('input').addEventListener('input', function () { target[key] = values[0]; }); return group;
    }
    box.appendChild(el('h4', '', 'CIMA — medidas da planta'));
    box.appendChild(el('p', 'plf-cima-intro', 'Edite somente os números. As medidas estão em centímetros.'));
    var form = el('div', 'plf-cima-contract plf-cima-core');
    form.appendChild(single('Comprimento interno', 'comprimento_interno'));
    form.appendChild(single('Largura interna', 'largura_interna'));
    form.appendChild(single('Comprimento externo', 'comprimento_externo'));
    form.appendChild(numericGroup('Parafusos', fields.parafusos || (fields.parafusos = []), 7));
    box.appendChild(form);
    var grades = el('section', 'plf-cima-section'); grades.appendChild(el('h5', '', 'Grades'));
    var gradeForm = el('div', 'plf-cima-contract plf-cima-grades'); var gradeValues = fields.grades || (fields.grades = {});
    [['grade_1', 'Grade 1'], ['distancia_1', 'Distância 1'], ['grade_2', 'Grade 2'], ['distancia_2', 'Distância 2'], ['grade_3', 'Grade 3']].forEach(function (entry) { gradeForm.appendChild(single(entry[1], entry[0], gradeValues)); });
    grades.appendChild(gradeForm); box.appendChild(grades);
    var squares = el('section', 'plf-cima-section'); squares.appendChild(el('h5', '', 'Quadradinhos'));
    var squareForm = el('div', 'plf-cima-contract plf-cima-squares'); var quadradinhos = fields.quadradinhos || (fields.quadradinhos = []);
    for (var gradeIndex = 0; gradeIndex < 3; gradeIndex += 1) squareForm.appendChild(numericGroup('Grade ' + (gradeIndex + 1), quadradinhos[gradeIndex] || (quadradinhos[gradeIndex] = []), 5));
    squares.appendChild(squareForm); box.appendChild(squares);
    var especial = fields.especial;
    if (especial && (especial.haste_ext || especial.haste || especial.ramo_ext || especial.ramo)) {
      var faceSpecs = especial.haste_ext
        ? [['haste_ext', 'Haste externa'], ['haste_int', 'Haste interna'], ['ramo_ext', 'Ramo externo'], ['ramo_int', 'Ramo interno']]
        : [['haste', 'Haste (braço longo)'], ['ramo', 'Ramo (braço curto)']];
      faceSpecs.forEach(function (entry) {
        var arm = especial[entry[0]] || (especial[entry[0]] = {});
        var section = el('section', 'plf-cima-section');
        section.appendChild(el('h5', '', 'CIMA L · ' + entry[1]));
        var armForm = el('div', 'plf-cima-contract');
        armForm.appendChild(single('Comprimento interno', 'comprimento_interno', arm));
        armForm.appendChild(single('Grade externa', 'grade_externa', arm));
        armForm.appendChild(single('Largura de cada grade', 'grade_width', arm));
        armForm.appendChild(single('Início dos parafusos', 'parafuso_inicio', arm));
        armForm.appendChild(numericGroup('Parafusos ' + entry[1], arm.parafusos || (arm.parafusos = []), 7));
        section.appendChild(armForm);
        var sq = el('div', 'plf-cima-contract plf-cima-squares');
        var quads = arm.quadradinhos || (arm.quadradinhos = []);
        for (var gi = 0; gi < 3; gi += 1) sq.appendChild(numericGroup('Quadradinhos G' + (gi + 1), quads[gi] || (quads[gi] = []), 5));
        section.appendChild(sq);
        box.appendChild(section);
      });
    }
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
    var openingCount = (data.openings.left || []).length + (data.openings.right || []).length;
    head.appendChild(el('span', 'plf-face-meta', data.panels.length + ' painel(is) · ' + openingCount + ' abertura(s)'));
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
    viewport.addEventListener('wheel', function(e){ e.preventDefault(); scale=Math.max(FACE_ZOOM_MIN,Math.min(FACE_ZOOM_MAX,scale*(e.deltaY<0?1.12:1/1.12))); canvas.style.transform='scale('+scale+')'; }, {passive:false});
    viewport.addEventListener('click', function(){ viewport.focus(); });
    card.appendChild(this.renderPanelEditor(face, data));
    card.appendChild(this.renderOpenings(face, data)); return card;
  };
  App.prototype.renderPanelEditor = function (face, data) {
    var self = this, selected = self.selectedPanel && self.selectedPanel.face === face ? data.panels.find(function(p){return p.id === self.selectedPanel.id;}) : null;
    var editor = el('section', 'plf-panel-editor');
    if (!selected) { editor.appendChild(el('span', 'plf-panel-editor-empty', 'Clique em um painel acima para editar suas medidas.')); return editor; }
    var head = el('div', 'plf-panel-editor-head'); head.appendChild(el('b', '', 'Editando ' + selected.id));
    head.appendChild(button('Limpar seleção', 'Voltar a escolher outro painel', function(){self.selectedPanel=null;self.render();}, 'plf-mini'));
    editor.appendChild(head);
    var body = el('div', 'plf-panel-editor-body');
    var kinds = el('div', 'plf-kind-picker'); [['panel','Painel'],['slab_void','Vazio laje'],['beam_void','Vazio viga']].forEach(function(k){kinds.appendChild(button(k[1],'',function(){selected.kind=k[0];self.changed();self.render();},selected.kind===k[0]?'active':''));}); body.appendChild(kinds);
    body.appendChild(field(selected.column===1?'Dist. parede esq.':'Dist. painel anterior',selected.distance,function(v){selected.distance=v;self.changed();}));
    body.appendChild(field(number(data.n3_width_extra)>0?'Largura interna':'Largura',selected.width,function(v){selected.width=v;self.changed();})); body.appendChild(field('Altura',selected.height,function(v){selected.height=v;self.changed();}));
    if (number(data.n3_width_extra)>0) body.appendChild(el('div','plf-panel-editor-n3','Largura N3 exibida: '+number(selected.width)+' + '+number(data.n3_width_extra)+' = '+(number(selected.width)+number(data.n3_width_extra))+' cm'));
    var hatch=el('div','plf-hatch'); hatch.appendChild(el('span','','Hatch')); [['none','○'],['checker','▦'],['striped','▨']].forEach(function(h){hatch.appendChild(button(h[1],h[0],function(){selected.hatch=h[0];self.changed();self.render();},selected.hatch===h[0]?'active':''));}); body.appendChild(hatch);
    body.appendChild(button('Excluir painel','Excluir somente esta célula',function(){data.panels=data.panels.filter(function(v){return v!==selected;});self.selectedPanel=null;self.changed();self.render();},'plf-delete'));
    editor.appendChild(body); return editor;
  };
  App.prototype.layoutFace = function (canvas, face, data) {
    var self = this, panels = data.panels, rows = {}, columns = {};
    panels.forEach(function(p){ rows[p.row]=Math.max(rows[p.row]||0,number(p.height)); columns[p.column]=Math.max(columns[p.column]||0,number(p.distance)+number(p.width)); });
    var rowIds=Object.keys(rows).map(Number).sort(function(a,b){return a-b;}), colIds=Object.keys(columns).map(Number).sort(function(a,b){return a-b;});
    // A/B no N3 incluem as duas chapas laterais (+22 cm). Em malhas com mais
    // de uma coluna, a sobra se divide nas bordas externas, nunca em cada painel.
    var widthExtra=number(data.n3_width_extra), colExtra={}, firstCol=colIds[0], lastCol=colIds[colIds.length-1];
    colIds.forEach(function(c){colExtra[c]=0;});
    if (widthExtra>0 && colIds.length===1) colExtra[firstCol]=widthExtra;
    else if(widthExtra>0){colExtra[firstCol]=widthExtra/2;colExtra[lastCol]+=widthExtra/2;}
    var totalW=colIds.reduce(function(s,c){return s+columns[c]+colExtra[c];},0)||1, totalH=rowIds.reduce(function(s,r){return s+rows[r];},0)||1;
    canvas.style.aspectRatio=totalW+' / '+totalH; canvas.dataset.totalWidth=totalW; canvas.dataset.totalHeight=totalH;
    var xOffsets={}, yOffsets={}, x=0, y=0; colIds.forEach(function(c){xOffsets[c]=x;x+=columns[c]+colExtra[c];}); rowIds.forEach(function(r){yOffsets[r]=y;y+=rows[r];});
    // No DXF N3, a laje e' um vazio entre painéis: h3 e' particionado em
    // painel inferior, vazio (espessura + 2) e rebaixo no topo. Isto substitui
    // a antiga faixa desenhada por cima do painel.
    var slab=data.slab && number(data.slab.void)>0 ? data.slab : null, topRow=rowIds[rowIds.length-1], slabPhysicalVoid=slab?number(slab.void):0, slabVoid=0, slabRecess=0, topPanelHeight=0, slabBase=0;
    if(slab && topRow!==undefined){slabVoid=Math.min(number(slab.void),rows[topRow]);slabRecess=Math.min(number(slab.recess),Math.max(0,rows[topRow]-slabVoid));topPanelHeight=Math.max(0,rows[topRow]-slabVoid-slabRecess);slabBase=yOffsets[topRow]+topPanelHeight;}
    function visualWidth(p){return number(p.width)+(p.column===lastCol?colExtra[p.column]:0);}
    function visualLeft(p){return xOffsets[p.column]+number(p.distance);}
    panels.forEach(function(p){
      var isSelected = self.selectedPanel && self.selectedPanel.face === face && self.selectedPanel.id === p.id;
      var panelHeight=(slab && p.row===topRow)?topPanelHeight:number(p.height); if(panelHeight<=0)return;
      var cell=el('div','plf-cell kind-'+p.kind+' hatch-'+p.hatch+(isSelected?' selected':'')); cell.style.left=((xOffsets[p.column]+number(p.distance))/totalW*100)+'%';
      cell.style.width=(visualWidth(p)/totalW*100)+'%'; cell.style.bottom=(yOffsets[p.row]/totalH*100)+'%'; cell.style.height=(panelHeight/totalH*100)+'%';
      cell.appendChild(el('span','plf-cell-name',p.id)); cell.appendChild(el('span','plf-cell-dim',visualWidth(p)+' × '+panelHeight));
      cell.tabIndex=0; cell.setAttribute('role','button'); cell.setAttribute('aria-label','Editar painel '+p.id);
      var choose = function(){self.selectedPanel={face:face,id:p.id};self.render();}; cell.addEventListener('click',choose); cell.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}}); canvas.appendChild(cell);
    });
    if (slab) {
      var slabLeft=0, slabRight=totalW, leftOpenings=data.openings.left||[], rightOpenings=data.openings.right||[];
      if(leftOpenings.length) slabLeft=Math.max.apply(null,leftOpenings.map(function(o){return number(o.distance)+number(o.width);}));
      if(rightOpenings.length) slabRight=Math.min.apply(null,rightOpenings.map(function(o){return totalW-number(o.distance)-number(o.width);}));
      if(slabRight<=slabLeft){slabLeft=0;slabRight=totalW;}
      var slabBand=el('div','plf-slab-band'); slabBand.style.left=(slabLeft/totalW*100)+'%';slabBand.style.width=((slabRight-slabLeft)/totalW*100)+'%';slabBand.style.bottom=(slabBase/totalH*100)+'%';slabBand.style.height=(slabVoid/totalH*100)+'%';slabBand.title=slab.evidence||'Laje vinculada ao N3';slabBand.textContent='LAJE · '+number(slab.thickness)+' + 2 = '+slabPhysicalVoid+' cm';canvas.appendChild(slabBand);
      if(slabRecess>0){var recess=el('div','plf-rebaixo-panel','REBAIXO · '+slabRecess+' cm');recess.style.left=(slabLeft/totalW*100)+'%';recess.style.width=((slabRight-slabLeft)/totalW*100)+'%';recess.style.bottom=((slabBase+slabVoid)/totalH*100)+'%';recess.style.height=(slabRecess/totalH*100)+'%';canvas.appendChild(recess);}
    }
    // No contrato N3, y_rel mede a partir do topo da cinta h1. Esta é a
    // mesma origem que o gerador usa no DXF para as vigas e aberturas.
    var openingBase=rows[rowIds[0]]||0;
    ['left','right'].forEach(function(side){(data.openings[side]||[]).forEach(function(o,i){ if(!o.width||!o.depth)return; var overlay=el('div','plf-opening '+side+(o.n3_kind==='passing_beam'?' passing-beam':' natural-opening'),(side==='left'?'E':'D')+(i+1)); var ox=side==='left'?o.distance:Math.max(0,totalW-o.distance-o.width), hasLevel=o.level!==undefined&&o.level!==null&&o.level!==''; var oy=hasLevel?openingBase+number(o.level):Math.max(0,totalH-number(o.top_distance)-number(o.depth)), depth=number(o.depth); if(slab && leftOpenings.length && rightOpenings.length)depth=Math.max(0,Math.min(oy+depth,slabBase)-oy); if(depth<=0)return; overlay.style.left=(ox/totalW*100)+'%';overlay.style.width=(o.width/totalW*100)+'%';overlay.style.bottom=(oy/totalH*100)+'%';overlay.style.height=(depth/totalH*100)+'%';canvas.appendChild(overlay);});});
  };
  App.prototype.addRow = function(face){var d=this.data.faces[face], rows=d.panels.map(function(p){return p.row;}), cols=d.panels.map(function(p){return p.column;}), row=Math.max.apply(null,rows.concat([0]))+1, self=this; Array.from(new Set(cols)).forEach(function(c){var ref=d.panels.find(function(p){return p.column===c;});d.panels.push({id:nextId(face,d.panels),row:row,column:c,distance:0,width:ref?ref.width:30,height:40,kind:'panel',hatch:'none'});});self.changed();self.render();};
  App.prototype.removeRow = function(face){var d=this.data.faces[face], max=Math.max.apply(null,d.panels.map(function(p){return p.row;}).concat([1]));if(max>1)d.panels=d.panels.filter(function(p){return p.row!==max;});this.changed();this.render();};
  App.prototype.addColumn = function(face){var d=this.data.faces[face], cols=d.panels.map(function(p){return p.column;}), rows=d.panels.map(function(p){return p.row;}), col=Math.max.apply(null,cols.concat([0]))+1; Array.from(new Set(rows)).forEach(function(r){var ref=d.panels.find(function(p){return p.row===r;});d.panels.push({id:nextId(face,d.panels),row:r,column:col,distance:0,width:ref?ref.width:30,height:ref?ref.height:40,kind:'panel',hatch:'none'});});this.changed();this.render();};
  App.prototype.removeColumn = function(face){var d=this.data.faces[face],max=Math.max.apply(null,d.panels.map(function(p){return p.column;}).concat([1]));if(max>1)d.panels=d.panels.filter(function(p){return p.column!==max;});this.changed();this.render();};
  App.prototype.renderOpenings = function(face,data){var self=this, groups=el('div','plf-opening-groups');['left','right'].forEach(function(side){var group=el('section','plf-opening-group '+side), h=el('div','plf-opening-head');h.appendChild(el('b','',side==='left'?'Aberturas esquerda':'Aberturas direita'));h.appendChild(button('+ abertura','Máximo 4 por lado',function(){if(data.openings[side].length<4){data.openings[side].push({distance:0,width:0,depth:0,level:0,top_distance:0});self.changed();self.render();}},'plf-add'));group.appendChild(h);data.openings[side].forEach(function(o,i){var row=el('div','plf-opening-row');row.appendChild(el('strong','',(side==='left'?'E':'D')+(i+1)));row.appendChild(field(side==='left'?'Dist. esquerda':'Dist. direita',o.distance,function(v){o.distance=v;self.changed();self.render();}));row.appendChild(field('Largura',o.width,function(v){o.width=v;self.changed();self.render();}));row.appendChild(field('Profundidade',o.depth,function(v){o.depth=v;self.changed();self.render();}));row.appendChild(field('Nível acima da cinta',o.level,function(v){o.level=v;self.changed();self.render();}));row.appendChild(field('Dist. topo',o.top_distance,function(v){o.top_distance=v;self.changed();self.render();}));row.appendChild(button('×','Excluir abertura',function(){data.openings[side].splice(i,1);self.changed();self.render();},'plf-delete'));group.appendChild(row);});groups.appendChild(group);});return groups;};
  App.prototype.renderGrades = function(){var self=this,g=self.data.grades,wrap=el('div','plf-grades');var top=el('div','plf-grade-top');[['grade_1','Grade 1'],['distance_1','Distância 1'],['grade_2','Grade 2'],['distance_2','Distância 2'],['grade_3','Grade 3']].forEach(function(s){top.appendChild(field(s[1],g[s[0]],function(v){g[s[0]]=v;self.changed();}));});wrap.appendChild(top);wrap.appendChild(el('h4','','Detalhamento das grades · cada coluna alterna sarrafo e distância'));var table=el('table','plf-slat-table'),thead=el('thead'),hr=el('tr');hr.appendChild(el('th','', ''));g.vertical_slats.forEach(function(s,i){hr.appendChild(el('th','', 'Sarrafo V'+(i+1)));hr.appendChild(el('th','', 'Dist. '+(i+1)));});thead.appendChild(hr);table.appendChild(thead);var body=el('tbody');['width','height'].forEach(function(key){var tr=el('tr');tr.appendChild(el('th','',key==='width'?'Largura':'Altura'));g.vertical_slats.forEach(function(s){var td=el('td');td.appendChild(field('',s[key],function(v){s[key]=v;self.changed();}));tr.appendChild(td);var dist=el('td');if(key==='width')dist.appendChild(field('',s.distance,function(v){s.distance=v;self.changed();}));else dist.textContent='—';tr.appendChild(dist);});body.appendChild(tr);});table.appendChild(body);wrap.appendChild(table);wrap.appendChild(button('+ sarrafo vertical','',function(){g.vertical_slats.push({width:5,height:5,distance:0});self.changed();self.render();},'plf-add'));var hh=el('div','plf-horizontal-head');hh.appendChild(el('h4','','Sarrafos horizontais'));hh.appendChild(button('+ sarrafo','',function(){g.horizontal_slats.push({left_distance:0,right_distance:0,width:5,height:5});self.changed();self.render();},'plf-add'));wrap.appendChild(hh);g.horizontal_slats.forEach(function(s,i){var row=el('div','plf-horizontal-row');row.appendChild(el('strong','', 'Sarrafo H'+(i+1)));[['left_distance','Dist. esquerda'],['right_distance','Dist. direita'],['width','Largura'],['height','Altura']].forEach(function(k){row.appendChild(field(k[1],s[k[0]],function(v){s[k[0]]=v;self.changed();}));});row.appendChild(button('×','Excluir',function(){g.horizontal_slats.splice(i,1);self.changed();self.render();},'plf-delete'));wrap.appendChild(row);});return wrap;};

  window.PillarFicha = { mount:function(root,options){ if(root) return new App(root,options); } };
})();
