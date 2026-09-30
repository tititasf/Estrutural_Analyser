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
  function svgEl(tag, attrs, text) {
    var node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.keys(attrs || {}).forEach(function(key){node.setAttribute(key, attrs[key]);});
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function field(label, value, change, title) {
    var wrap = el('label', 'plf-field');
    wrap.title = title || label;
    wrap.appendChild(el('span', '', label));
    var input = el('input'); input.type = 'number'; input.step = '0.1'; input.min = '0'; input.value = value==null?'':number(value);
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
    this.visualMode = options.visualMode || null; this.availableVisualModes = [];
    this.dirty = false; this.saving = false; this.regenJob = null; this.regenChecking = false; this.regenDiscovered = false; this.regenError = ''; this.regenTimer = null; this.regenRefreshOnDone = null;
    this.load();
  }
  App.prototype.url = function () {
    return '/obras/' + this.options.obraId + '/n1/' + this.options.classe + '/' + encodeURIComponent(this.options.itemId) +
      '/pilar-n3-ficha?' + (this.options.pavimento ? 'pavimento=' + encodeURIComponent(this.options.pavimento) + '&' : '') +
      'vista=' + encodeURIComponent(this.tab) + (this.visualMode ? '&visual_mode=' + encodeURIComponent(this.visualMode) : '');
  };
  App.prototype.load = function () {
    var self = this; self.root.innerHTML = '<p class="muted">Carregando ficha N3 do pilar…</p>';
    fetch(self.url(), {cache:'no-store'}).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (body) { self.data = body.ficha; self.cimaContract = body.cima_contract || body.ficha; self.views = body.visualizacoes_n3 || {}; self.visualMode=body.visual_mode||self.visualMode||'NOVA'; self.availableVisualModes=body.available_visual_modes||[]; self.dirty = false; self.saving = false; self.render(); if(self.tab==='cima')self.discoverRegen(); })
      .catch(function (err) { self.root.innerHTML = '<p class="plf-error">Não foi possível carregar a ficha N3: ' + err.message + '</p>'; });
  };
  App.prototype.changed = function () {
    var self = this, status = self.root.querySelector('.plf-status');
    if (self.tab.indexOf('abcd') === 0) self.refreshFaces();
    if (self.tab === 'cima') {
      self.dirty = true;
      if (status) { status.textContent = 'Alterações não salvas'; status.classList.remove('error'); }
      self.paintCimaActions();
      return;
    }
    if (status) status.textContent = 'Alterado · salvando…';
    clearTimeout(self.timer); self.timer = setTimeout(function () { self.save(); }, 650);
  };
  App.prototype.save = function () {
    var self = this, status = self.root.querySelector('.plf-status');
    self.data.cima_contract = self.cimaContract;
    self.saving = true; self.paintCimaActions();
    return fetch(self.url(), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ficha:self.data})})
      .then(function (r) { return r.json().then(function (body) { if (!r.ok) throw new Error(body.detail || 'HTTP ' + r.status); return body; }); })
      .then(function (body) { if(self.tab.indexOf('abcd')!==0) self.data = body.ficha; else {self.data.revision=body.revision;self.data.source=body.ficha.source;} self.cimaContract = body.ficha.cima_contract || self.cimaContract; self.dirty = false; self.saving = false; if (status) { status.textContent = 'Salvo · revisão ' + body.revision; status.classList.remove('error'); } self.paintCimaActions(); return body; })
      .catch(function (err) { self.saving = false; if (status) { status.textContent = 'Erro ao salvar: ' + err.message; status.classList.add('error'); } self.paintCimaActions(); throw err; });
  };
  App.prototype.regenUrl = function (suffix) {
    var query = this.options.pavimento ? '?pavimento=' + encodeURIComponent(this.options.pavimento) : '';
    return '/obras/' + this.options.obraId + '/n1/' + this.options.classe + '/' + encodeURIComponent(this.options.itemId) + '/pilar-n3-cima/regenerar' + (suffix || '') + query;
  };
  App.prototype.regenActive = function () { var job=this.regenJob; return !!job && ['queued','running','paused'].indexOf(job.estado)>=0; };
  App.prototype.paintCimaActions = function () {
    var save=this.root.querySelector('[data-plf-cima-save]'), regen=this.root.querySelector('[data-plf-cima-regen]'), monitor=this.root.querySelector('[data-plf-cima-monitor]');
    if(save){save.disabled=!this.dirty||this.saving;save.textContent=this.saving?'Salvando…':'Salvar edições manuais';}
    if(regen){regen.disabled=this.saving||this.regenChecking||this.regenActive();regen.textContent=this.regenActive()?(this.regenJob.estado==='queued'?'Regeneração na fila':'Regeneração em andamento'):'Solicitar regeneração N3 Cima';}
    if(!monitor)return;
    var job=this.regenJob, labels={queued:'Na fila',running:'Regenerando N3 Cima',paused:'Pausada',done:'Concluída',error:'Falhou',cancelled:'Cancelada'};
    if(this.regenChecking&&!job)monitor.innerHTML='<b>Consultando regeneração…</b><span>Verificando a fila</span>';
    else if(!job&&this.regenError)monitor.innerHTML='<b class="error">Falha ao consultar</b><span>'+this.regenError+'</span>';
    else if(job){var progress=job.progresso||{},pct=progress.percentual_estimado,detail=progress.rotulo||labels[job.estado]||job.estado;monitor.innerHTML='<b>'+labels[job.estado]+'</b><span>'+detail+(typeof pct==='number'?' · '+pct+'%':'')+'</span>'+(typeof pct==='number'?'<i><em style="width:'+Math.max(0,Math.min(100,pct))+'%"></em></i>':'')+(job.erro_msg?'<small>'+job.erro_msg+'</small>':'');}
    else monitor.innerHTML='';
    monitor.hidden=!monitor.innerHTML;
  };
  App.prototype.pollRegen = function (jobId) {
    var self=this;if(!jobId)return;if(self.regenTimer){clearTimeout(self.regenTimer);self.regenTimer=null;}self.regenChecking=true;self.paintCimaActions();
    fetch('/jobs/'+encodeURIComponent(jobId),{cache:'no-store'}).then(function(r){return r.json().then(function(body){if(!r.ok)throw new Error(body.detail||'HTTP '+r.status);return body;});}).then(function(job){self.regenChecking=false;self.regenError='';self.regenJob=job;self.paintCimaActions();if(self.regenActive())self.regenTimer=setTimeout(function(){self.pollRegen(jobId);},2500);else if(job.estado==='done'&&self.regenRefreshOnDone===jobId){self.regenRefreshOnDone=null;self.load();}}).catch(function(err){self.regenChecking=false;self.regenError=err.message;self.paintCimaActions();if(self.regenActive())self.regenTimer=setTimeout(function(){self.pollRegen(jobId);},4000);});
  };
  App.prototype.discoverRegen = function () {
    var self=this;if(self.regenDiscovered||self.regenChecking)return;self.regenChecking=true;self.paintCimaActions();
    fetch(self.regenUrl('/status'),{cache:'no-store'}).then(function(r){return r.json().then(function(body){if(!r.ok)throw new Error(body.detail||'HTTP '+r.status);return body;});}).then(function(result){self.regenDiscovered=true;self.regenChecking=false;if(result.job_id)self.pollRegen(result.job_id);else self.paintCimaActions();}).catch(function(err){self.regenDiscovered=true;self.regenChecking=false;self.regenError=err.message;self.paintCimaActions();});
  };
  App.prototype.requestCimaRegen = function (requestedMode) {
    var self=this;if(self.regenActive()||self.regenChecking)return;
    var chooser=requestedMode?Promise.resolve(requestedMode):(window.escolherModoDesenho?window.escolherModoDesenho({currentMode:self.visualMode,description:'Escolha o estilo para regenerar o N3 Cima deste pilar.'}):Promise.resolve('NOVA'));
    chooser.then(function(mode){if(!mode)return null;var ready=self.dirty?self.save():Promise.resolve();return ready.then(function(){self.regenChecking=true;self.regenError='';self.paintCimaActions();return fetch(self.regenUrl(),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({visual_mode:mode})});});}).then(function(r){if(!r)return null;return r.json().then(function(body){if(!r.ok)throw new Error(body.detail||'HTTP '+r.status);return body;});}).then(function(body){if(!body)return;self.regenRefreshOnDone=body.job_id;self.pollRegen(body.job_id);}).catch(function(err){self.regenChecking=false;self.regenError=err.message;self.paintCimaActions();});
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
      ['Lajes e vigas', 'Lajes e aberturas de viga são editadas nas listas da face. Clique em cada desenho para destacar seus campos. Hatch é exclusivo dos painéis.'],
      ['Grades e sarrafos', 'Grades usam Grade 1/Distância 1/Grade 2/Distância 2/Grade 3. Sarrafos horizontais exigem distâncias esquerda e direita.'],
      ['Pilar especial', 'As faces E–H aparecem quando o contorno N1 não é retangular ou quando a Fase 4 já possui essas faces.']
    ].forEach(function(row){var item=el('div');item.appendChild(el('b','',row[0]));item.appendChild(el('span','',row[1]));guide.appendChild(item);});
    help.appendChild(guide); shell.appendChild(help);
    if (!self.options.hideTabs) {
      var tabs = el('div', 'plf-tabs');
      [['cima','N3 Cima'],['abcd-para','ABCD Para'],['abcd-passa','ABCD Passa'],['grades-para','Grades Para'],['grades-passa','Grades Passa']].forEach(function (spec) {
        tabs.appendChild(button(spec[1], '', function () {
          if (self.tab === spec[0]) return;
          if (self.dirty && !confirm('Descartar as alterações não salvas da ficha Cima?')) return;
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
      card.appendChild(el('p', 'muted', 'Modo ' + (this.visualMode === 'INI' ? 'Ini' : 'Nova') + ' ainda não gerado para ' + (labels[this.tab] || 'esta vista') + '.'));
      card.appendChild(el('p', 'muted', this.tab === 'cima' ? 'Use o botão abaixo para regenerar exatamente este desenho neste modo.' : 'Rode o motor N3 de pilares escolhendo este modo para materializar esta vista.'));
      if (this.tab === 'cima') card.appendChild(button('Regenerar N3 Cima em ' + (this.visualMode === 'INI' ? 'Ini' : 'Nova'),'',this.requestCimaRegen.bind(this,this.visualMode),'primary'));
      var missingSwitch = button('Ver modo ' + (this.visualMode === 'INI' ? 'Nova' : 'Ini'),'',function(){this.visualMode=this.visualMode==='INI'?'NOVA':'INI';if(window.atualizarModoDesenhoUrl)window.atualizarModoDesenhoUrl(this.visualMode);this.load();}.bind(this),'');
      card.appendChild(missingSwitch);
      return card;
    }
    var viewport = el('div', 'zoom-pan-viewport');
    viewport.innerHTML = svg;
    if(window.aplicarTagModoDesenho)window.aplicarTagModoDesenho(viewport,this.visualMode,{onChange:function(mode){this.visualMode=mode;this.load();}.bind(this)});
    card.appendChild(viewport);
    card.appendChild(el('p', 'zoom-pan-dica', 'Scroll zoom · arraste pan · duplo-clique reseta (viewBox)'));
    return card;
  };
  App.prototype.renderCima = function () {
    var self = this, box = el('div', 'plf-cima'), fields = (this.cimaContract || {}).fields || {};
    function save() { self.data.cima_contract = self.cimaContract; self.changed(); }
    function numericGroup(title, values, max, key, afterChange) {
      var group = el('section', 'plf-cima-group plf-cima-group-' + max); group.appendChild(el('span', 'plf-cima-label', title));
      var numbers = el('span', 'plf-cima-values');
      for (var index = 0; index < max; index += 1) {
        var input = el('input', 'plf-cima-input'); input.type = 'number'; input.step = '0.1'; input.placeholder = '—';
        input.value = values[index] === undefined || values[index] === null || values[index] === 0 ? '' : values[index];
        input.setAttribute('aria-label', title + ' ' + (index + 1));
        (function (position, control) { control.addEventListener('input', function () { values[position] = control.value === '' ? null : number(control.value); if(afterChange)afterChange(); save(); }); })(index, input);
        numbers.appendChild(input);
      }
      group.appendChild(numbers); group.appendChild(el('span', 'plf-cima-unit', 'cm')); return group;
    }
    function single(title, key, target) {
      target = target || fields; var values = [target[key]]; var group = numericGroup(title, values, 1, key);
      group.querySelector('input').addEventListener('input', function () { target[key] = values[0]; }); return group;
    }
    function classificationPicker(value, special) {
      var group=el('section','plf-cima-group plf-cima-classification');
      group.appendChild(el('span','plf-cima-label','Classificação do pilar'));
      var select=el('select','plf-cima-select');
      [
        ['retangular','Retangular (comum)',special],
        ['especial_l','Especial em L',!special],
        ['especial_u','Especial em U — motor em preparação',true],
        ['especial_t','Especial em T — motor em preparação',true],
        ['circular','Circular — motor em preparação',true],
        ['outro','Outro especial — motor em preparação',true]
      ].forEach(function(spec){var option=el('option','',spec[1]);option.value=spec[0];option.disabled=spec[2];if(spec[0]===value)option.selected=true;select.appendChild(option);});
      select.addEventListener('change',function(){fields.classificacao_pilar=select.value;save();});
      group.appendChild(select); return group;
    }
    function screwBox(target, isSpecial) {
      if(target.parafuso_inicio===undefined||target.parafuso_inicio===null)target.parafuso_inicio=isSpecial?0:-1;
      if(target.parafuso_final===undefined||target.parafuso_final===null)target.parafuso_final=1;
      var screw=el('div','plf-cima-screw-box');
      screw.appendChild(single('Início dos parafusos','parafuso_inicio',target));
      screw.appendChild(numericGroup('Distâncias entre parafusos',target.parafusos||(target.parafusos=[]),7));
      screw.appendChild(single('Final do parafuso','parafuso_final',target));
      return screw;
    }
    box.appendChild(el('h4', '', 'CIMA — medidas da planta'));
    box.appendChild(el('p', 'plf-cima-intro', 'Edite somente os números. As medidas estão em centímetros.'));
    function gradeSide(sideName, widths, gaps, quads, meta) {
      while(widths.length < 3) widths.push(null);
      while(gaps.length < 2) gaps.push(null);
      while(quads.length < 3) quads.push([]);
      var side = el('section','plf-cima-side');
      side.appendChild(el('h5','',sideName));
      if(meta)side.appendChild(screwBox(meta,true));
      var rows=el('div','plf-cima-grade-list');
      for(var gi=0;gi<3;gi+=1){
        var row=el('div','plf-cima-grade-row');
        var totalValue=[widths[gi]];
        var total=numericGroup('Tamanho total da grade '+(gi+1),totalValue,1,'grade-total',(function(index,values){return function(){widths[index]=values[0];};})(gi,totalValue));
        row.appendChild(total);
        row.appendChild(numericGroup('Quadradinhos da grade '+(gi+1),quads[gi],5));
        if(gi<2){
          var gapValue=[gaps[gi]];
          var gap=numericGroup('Distância '+(gi+1)+' entre grades',gapValue,1,'grade-gap',(function(index,values){return function(){gaps[index]=values[0];};})(gi,gapValue));
          gap.classList.add('plf-cima-gap'); row.appendChild(gap);
        }
        rows.appendChild(row);
      }
      side.appendChild(rows); return side;
    }
    var especial = fields.especial;
    if (especial && (especial.haste_ext || especial.haste || especial.ramo_ext || especial.ramo)) {
      fields.classificacao_pilar=fields.classificacao_pilar||'especial_l';
      var shape=fields.shape||(fields.shape={});
      var specialCore=el('div','plf-cima-contract plf-cima-special-core');
      specialCore.appendChild(classificationPicker(fields.classificacao_pilar,true));
      specialCore.appendChild(single('Comprimento 1 interno · parte vertical do L','comprimento_1_interno',shape));
      specialCore.appendChild(single('Comprimento 1 externo · parte vertical do L','comprimento_1_externo',shape));
      specialCore.appendChild(single('Comprimento 2 interno · parte horizontal do L','comprimento_2_interno',shape));
      specialCore.appendChild(single('Comprimento 2 externo · parte horizontal do L','comprimento_2_externo',shape));
      specialCore.appendChild(single('Largura 1 · parte vertical do L','largura_1',shape));
      specialCore.appendChild(single('Largura 2 · parte horizontal do L','largura_2',shape));
      box.appendChild(specialCore);
      var faceSpecs = especial.haste_ext
        ? [['haste_ext','A'],['haste_int','B'],['ramo_ext','E'],['ramo_int','F']]
        : [['haste','A'],['ramo','E']];
      var sideGrid=el('div','plf-cima-side-grid plf-cima-special-sides');
      faceSpecs.forEach(function (entry) {
        var arm = especial[entry[0]] || (especial[entry[0]] = {});
        arm.side_id=arm.side_id||entry[1];
        sideGrid.appendChild(gradeSide('Lado '+arm.side_id,arm.grade_widths||(arm.grade_widths=[]),arm.gaps||(arm.gaps=[]),arm.quadradinhos||(arm.quadradinhos=[]),arm));
      });
      box.appendChild(sideGrid);
    } else {
      fields.classificacao_pilar=fields.classificacao_pilar||'retangular';
      var form = el('div', 'plf-cima-contract plf-cima-core');
      form.appendChild(classificationPicker(fields.classificacao_pilar,false));
      form.appendChild(single('Comprimento interno', 'comprimento_interno'));
      form.appendChild(single('Largura interna', 'largura_interna'));
      form.appendChild(single('Comprimento externo', 'comprimento_externo'));
      box.appendChild(form);
      box.appendChild(screwBox(fields,false));
      var gradeValues=fields.grades||(fields.grades={});
      var sharedWidths=[gradeValues.grade_1,gradeValues.grade_2,gradeValues.grade_3];
      var sharedGaps=[gradeValues.distancia_1,gradeValues.distancia_2];
      function syncRegular(){gradeValues.grade_1=sharedWidths[0];gradeValues.grade_2=sharedWidths[1];gradeValues.grade_3=sharedWidths[2];gradeValues.distancia_1=sharedGaps[0];gradeValues.distancia_2=sharedGaps[1];}
      var sideTabs=el('div','plf-cima-side-tabs');
      sideTabs.setAttribute('role','tablist');
      sideTabs.setAttribute('aria-label','Lado da grade da vista de cima');
      var regularGrid=el('div','plf-cima-side-grid plf-cima-regular-sides');
      var sideButtons={};
      var sideCards={};
      function selectSide(face) {
        self.cimaSide=face;
        ['A','B'].forEach(function(id){
          var active=id===face;
          sideButtons[id].classList.toggle('active',active);
          sideButtons[id].setAttribute('aria-selected',active?'true':'false');
          sideButtons[id].tabIndex=active?0:-1;
          sideCards[id].hidden=!active;
        });
      }
      [['A','quadradinhos_a'],['B','quadradinhos_b']].forEach(function(spec){
        var face=spec[0];
        var values=fields[spec[1]]||(fields[spec[1]]=spec[0]==='A'?(fields.quadradinhos||[]):[]);
        var card=gradeSide('Lado '+spec[0],sharedWidths,sharedGaps,values,null);
        var tab=button('Lado '+face,'Editar as grades do lado '+face,function(){selectSide(face);},'plf-cima-side-tab');
        tab.id=self.root.id+'-cima-tab-'+face;
        tab.setAttribute('role','tab');
        tab.setAttribute('aria-controls',self.root.id+'-cima-side-'+face);
        tab.addEventListener('keydown',function(event){
          if(event.key!=='ArrowLeft'&&event.key!=='ArrowRight')return;
          event.preventDefault();
          var other=face==='A'?'B':'A';
          selectSide(other);
          sideButtons[other].focus();
        });
        card.id=self.root.id+'-cima-side-'+face;
        card.setAttribute('role','tabpanel');
        card.setAttribute('aria-labelledby',tab.id);
        sideButtons[face]=tab;
        sideCards[face]=card;
        sideTabs.appendChild(tab);
        card.addEventListener('input',syncRegular); regularGrid.appendChild(card);
      });
      box.appendChild(sideTabs);
      box.appendChild(regularGrid);
      selectSide(self.cimaSide==='B'?'B':'A');
    }
    var actions=el('div','plf-cima-actions');
    actions.appendChild(button('Salvar edições manuais','Persiste os valores editados desta ficha',function(){self.save().catch(function(){});},'success'));
    actions.lastChild.setAttribute('data-plf-cima-save','');
    actions.appendChild(button('Solicitar regeneração N3 Cima','Regenera somente este pilar',function(){self.requestCimaRegen();},'primary'));
    actions.lastChild.setAttribute('data-plf-cima-regen','');
    var monitor=el('div','plf-cima-monitor');monitor.setAttribute('data-plf-cima-monitor','');monitor.hidden=true;actions.appendChild(monitor);box.appendChild(actions);
    setTimeout(function(){self.paintCimaActions();},0);
    return box;
  };
  App.prototype.renderFaces = function () {
    var self = this, board = el('div', 'plf-ledger');
    var intro = el('div', 'plf-ledger-title'); intro.appendChild(el('b', '', self.tab === 'abcd-para' ? 'ABCD · PARA' : 'ABCD · PASSA'));
    intro.appendChild(el('span', '', 'Scroll para zoom · arraste para navegar · clique em painel, abertura ou laje para editar abaixo. Medidas em cm.'));
    intro.appendChild(button('Enquadrar', 'Mostrar todas as faces', function(){self.faceCamera=null;self.refreshFaces();}, 'plf-fit'));
    board.appendChild(intro);
    var viewport = el('div', 'plf-shared-viewport');
    var svg = svgEl('svg', {'class':'plf-shared-svg', 'aria-label':'Desenho das faces do pilar', preserveAspectRatio:'xMidYMid meet'});
    viewport.appendChild(svg); board.appendChild(viewport);
    self.paintFaces(svg); self.initFacePanZoom(svg);
    var controls=el('div','plf-controls-scroll');
    self.renderFaceControls(controls, self.activeFace);
    board.appendChild(controls); return board;
  };
  App.prototype.renderFaceControls = function (controls, preferredFace) {
    var self=this, faces=Object.keys(self.data.faces);
    if (!faces.length) { controls.replaceChildren(); return; }
    self.activeFace=faces.indexOf(preferredFace)>=0?preferredFace:faces[0];
    var tabs=el('div','plf-face-tabs'); tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Face para editar');
    faces.forEach(function(face){
      var tab=button('Face '+face,'Editar painéis, aberturas e lajes da face '+face,function(){self.selectElement(null,face);},'plf-face-tab'+(face===self.activeFace?' active':''));
      tab.setAttribute('role','tab');tab.setAttribute('aria-selected',face===self.activeFace?'true':'false');
      tab.setAttribute('aria-controls','plf-face-content');tabs.appendChild(tab);
    });
    var content=el('div','plf-face-grid plf-face-controls');content.id='plf-face-content';content.setAttribute('role','tabpanel');
    content.setAttribute('aria-label','Campos da face '+self.activeFace);
    content.appendChild(self.renderFace(self.activeFace,self.data.faces[self.activeFace]));
    controls.replaceChildren(tabs,content);
  };
  App.prototype.renderFace = function (face, data) {
    var self = this, card = el('article', 'plf-face'); card.dataset.face=face;
    card.classList.toggle('is-selected',!!self.selectedPanel && self.selectedPanel.face===face);
    var head = el('div', 'plf-face-head'); head.appendChild(el('b', '', 'FACE ' + face));
    var openingCount = (data.openings.left || []).length + (data.openings.right || []).length;
    head.appendChild(el('span', 'plf-face-meta', data.panels.length + ' painel(is) · ' + openingCount + ' abertura(s) · ' + (data.slabs||[]).length + ' laje(s)'));
    var tools = el('div', 'plf-face-tools');
    tools.appendChild(button('+H','Adicionar linha de altura nesta face',function(){self.addRow(face);},'plf-mini'));
    tools.appendChild(button('−H','Remover última linha desta face',function(){self.removeRow(face);},'plf-mini'));
    tools.appendChild(button('+L','Adicionar coluna de largura nesta face',function(){self.addColumn(face);},'plf-mini'));
    tools.appendChild(button('−L','Remover última coluna desta face',function(){self.removeColumn(face);},'plf-mini'));
    head.appendChild(tools); card.appendChild(head);
    card.appendChild(this.renderPanelEditor(face, data));
    card.appendChild(this.renderOpenings(face, data));
    card.appendChild(this.renderSlabs(face, data)); return card;
  };
  App.prototype.refreshFaces = function () {
    var svg=this.root.querySelector('.plf-shared-svg'); if(svg)this.paintFaces(svg);
    var note=this.root.querySelector('.plf-panel-editor-n3'), selection=this.selectedPanel;
    if(note&&selection&&selection.type==='panel'){var face=this.data.faces[selection.face], panel=face.panels.find(function(p){return p.id===selection.id;});if(panel)note.textContent='Largura N3 exibida: '+number(panel.width)+' + '+number(face.n3_width_extra)+' = '+(number(panel.width)+number(face.n3_width_extra))+' cm';}
  };
  App.prototype.isSelected = function(type,face,detail){
    var chosen=this.selectedPanel;
    return !!chosen && chosen.type===type && chosen.face===face &&
      (type==='panel'?chosen.id===detail.id:type==='slab'?chosen.index===detail.index:chosen.side===detail.side&&chosen.index===detail.index);
  };
  App.prototype.pillarTopLevel = function(){
    var level=this.data&&this.data.source&&this.data.source.pillar_top_level;
    return level===undefined||level===null?null:number(level);
  };
  App.prototype.orderedOpenings = function(data){
    var items=[];
    ['left','right'].forEach(function(side){(data.openings[side]||[]).forEach(function(opening,index){items.push({side:side,index:index,opening:opening});});});
    return items.sort(function(a,b){return number(b.opening.level)-number(a.opening.level)||
      (a.side===b.side?a.index-b.index:a.side==='left'?-1:1);});
  };
  App.prototype.renderLevelFields = function(row,entry,levelKey,onChanged){
    var self=this,top=self.pillarTopLevel(),notice=el('span','plf-level-warning','Nível do elemento acima do topo do pilar: conferir interpretação SA.');
    var provenance=el('span','plf-level-source','');
    var gapNotice=el('span','plf-level-warning','');
    function updateGap(){
      var bottom=self.data&&self.data.source&&self.data.source.pillar_bottom_level;
      var gap=bottom==null||entry[levelKey]==null?null:Math.round(((number(entry[levelKey])-number(bottom))*100-number(entry.level))*100)/100;
      gapNotice.hidden=levelKey!=='element_level'||gap===null||Math.abs(gap)<=1;
      if(!gapNotice.hidden)gapNotice.textContent='Cota SA e posição do recorte N3 divergem em '+Math.abs(gap).toLocaleString('pt-BR')+' cm. Conferir interpretação da viga antes de regenerar.';
    }
    function update(changed){
      if(levelKey==='element_level'){entry.level_source='manual';provenance.hidden=true;}
      if(top!==null){
        if(changed==='level')entry.top_distance=Math.round((top-number(entry[levelKey]))*10000)/100;
        else entry[levelKey]=Math.round((top-number(entry.top_distance)/100)*10000)/10000;
        var other=row.querySelector('[data-level-key="'+(changed==='level'?'top_distance':levelKey)+'"] input');
        if(other)other.value=entry[changed==='level'?'top_distance':levelKey];
      }
      row.classList.toggle('plf-level-error',number(entry.top_distance)<-0.001);
      notice.hidden=number(entry.top_distance)>=-0.001;
      updateGap();
      if(onChanged)onChanged();
      self.changed();
    }
    var level=field('Nível do elemento',entry[levelKey],function(v){entry[levelKey]=v;update('level');});
    level.dataset.levelKey=levelKey;level.querySelector('input').step='0.01';row.appendChild(level);
    var distance=field('Dist. topo (cm)',entry.top_distance,function(v){entry.top_distance=v;update('top_distance');});
    distance.dataset.levelKey='top_distance';row.appendChild(distance);
    notice.hidden=number(entry.top_distance)>=-0.001;
    row.classList.toggle('plf-level-error',!notice.hidden);
    provenance.hidden=levelKey!=='element_level'||entry.level_source==='sa'||entry.level_source==='manual';
    if(!provenance.hidden)provenance.textContent={
      abcd_sa:'Nível confirmado pelo segmento da viga no SA/N1.',
      abcd_manual:'Nível corrigido manualmente na tabela ABCD.',
      abcd_inferred:'Nível inferido na tabela ABCD; conferir a viga no desenho.',
      sa_related:'Nível recuperado de outro vínculo SA da mesma viga.'
    }[entry.level_source]||'SA sem cota inequívoca para esta viga; nível não estimado pelo desenho.';
    updateGap();
    return [notice,provenance,gapNotice];
  };
  App.prototype.selectElement = function(selection,face){
    this.selectedPanel=selection;
    this.root.querySelectorAll('.plf-svg-cell,.plf-svg-opening,.plf-svg-slab').forEach(function(item){
      var chosen=selection && item.parentNode.dataset.face===selection.face &&
        item.dataset.selectType===selection.type &&
        (selection.type==='panel'?item.dataset.panelId===selection.id:
         selection.type==='slab'?Number(item.dataset.index)===selection.index:
         item.dataset.side===selection.side&&Number(item.dataset.index)===selection.index);
      item.classList.toggle('selected',!!chosen);item.setAttribute('aria-pressed',!!chosen);
    });
    var controls=this.root.querySelector('.plf-controls-scroll');
    if(controls)this.renderFaceControls(controls,face||selection&&selection.face||this.activeFace);
    if(selection){var box=controls&&controls.querySelector('.plf-selection-box');if(box)box.scrollIntoView({block:'nearest',behavior:'smooth'});}
  };
  App.prototype.selectPanel = function(face,id){
    this.selectElement(id?{type:'panel',face:face,id:id}:null,face);
  };
  App.prototype.paintFaces = function (svg) {
    var self=this, faces=Object.keys(self.data.faces), layouts=faces.map(function(face){
      var group=svgEl('g',{'data-face':face}); self.layoutFace(group,face,self.data.faces[face]); return group;
    });
    var maxW=Math.max.apply(null,layouts.map(function(g){return number(g.dataset.totalWidth);}).concat([1]));
    var maxH=Math.max.apply(null,layouts.map(function(g){return number(g.dataset.totalHeight)+number(g.dataset.topVoid);}).concat([1]));
    var gap=Math.max(22,maxW*.35), slot=maxW+gap, labelSize=Math.max(7,maxH*.024), top=labelSize*4;
    svg.replaceChildren();
    var defs=svgEl('defs');
    ['checker','striped'].forEach(function(kind){
      var pattern=svgEl('pattern',{id:'plf-'+kind,patternUnits:'userSpaceOnUse',width:6,height:6});
      pattern.appendChild(svgEl('rect',{width:6,height:6,fill:'#2856dc'}));
      pattern.appendChild(svgEl('path',{d:kind==='checker'?'M0 0h3v3H0z M3 3h3v3H3z':'M-1 1L1 -1M0 6L6 0M5 7L7 5',fill:kind==='checker'?'#ffffff66':'none',stroke:kind==='striped'?'#ffffff88':'none','stroke-width':1}));
      defs.appendChild(pattern);
    });
    svg.appendChild(defs);
    layouts.forEach(function(group,index){
      var center=slot*(index+.5), width=number(group.dataset.totalWidth), height=number(group.dataset.totalHeight);
      var tag=svgEl('g',{'class':'plf-face-tag'});
      tag.appendChild(svgEl('rect',{x:center-labelSize*1.2,y:labelSize, width:labelSize*2.4,height:labelSize*1.8,rx:labelSize*.4}));
      tag.appendChild(svgEl('text',{x:center,y:labelSize*1.95,'font-size':labelSize,'text-anchor':'middle','dominant-baseline':'middle'},faces[index]));
      svg.appendChild(tag);
      // As quatro faces compartilham a linha de fundo, mesmo com alturas diferentes.
      group.setAttribute('transform','translate('+(center-width/2)+' '+(top+maxH-height)+')'); svg.appendChild(group);
    });
    self.faceHome={x:0,y:0,w:Math.max(1,slot*faces.length),h:top+maxH+gap/2};
    if(!self.faceCamera || self.faceCameraTab!==self.tab){self.faceCamera=Object.assign({},self.faceHome);self.faceCameraTab=self.tab;}
    self.applyFaceCamera(svg);
  };
  App.prototype.applyFaceCamera = function(svg){var v=this.faceCamera;svg.setAttribute('viewBox',[v.x,v.y,v.w,v.h].join(' '));};
  App.prototype.initFacePanZoom = function(svg){
    // Same viewBox/clientToSvg contract as FV initPanZoom; one camera for all faces.
    var self=this, drag=null, moved=false;
    function point(e){var p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());}
    svg.addEventListener('wheel',function(e){
      e.preventDefault(); var p=point(e),v=self.faceCamera,scale=self.faceHome.w/v.w;
      var next=Math.max(FACE_ZOOM_MIN,Math.min(FACE_ZOOM_MAX,scale*(e.deltaY<0?1.12:1/1.12))),ratio=scale/next;
      self.faceCamera={x:p.x-(p.x-v.x)*ratio,y:p.y-(p.y-v.y)*ratio,w:v.w*ratio,h:v.h*ratio};self.applyFaceCamera(svg);
    },{passive:false});
    svg.addEventListener('pointerdown',function(e){if(e.button!==0)return;moved=false;drag={id:e.pointerId,x:e.clientX,y:e.clientY,start:point(e)};});
    svg.addEventListener('pointermove',function(e){
      if(!drag||drag.id!==e.pointerId)return;
      if(!moved&&Math.hypot(e.clientX-drag.x,e.clientY-drag.y)<4)return;
      moved=true;svg.setPointerCapture(e.pointerId);svg.classList.add('is-dragging');
      var p=point(e),v=self.faceCamera;v.x-=p.x-drag.start.x;v.y-=p.y-drag.start.y;self.applyFaceCamera(svg);
    });
    function end(e){if(!drag||drag.id!==e.pointerId)return;drag=null;svg.classList.remove('is-dragging');if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);}
    svg.addEventListener('pointerup',end);svg.addEventListener('pointercancel',end);svg.addEventListener('lostpointercapture',end);
    svg.addEventListener('pointerleave',function(e){if(!moved)end(e);});
    svg.addEventListener('click',function(e){if(moved){e.preventDefault();e.stopPropagation();moved=false;}},true);
    svg.addEventListener('dblclick',function(e){e.preventDefault();self.faceCamera=Object.assign({},self.faceHome);self.applyFaceCamera(svg);});
  };
  App.prototype.renderPanelEditor = function (face, data) {
    var self = this, selected = self.selectedPanel && self.selectedPanel.type==='panel' && self.selectedPanel.face === face ? data.panels.find(function(p){return p.id === self.selectedPanel.id;}) : null;
    var editor = el('section', 'plf-panel-editor');
    if (!selected) { editor.appendChild(el('span', 'plf-panel-editor-empty', 'Clique em um painel acima para editar suas medidas.')); return editor; }
    editor.classList.add('plf-selection-box');
    var head = el('div', 'plf-panel-editor-head'); head.appendChild(el('b', '', 'Editando ' + selected.id));
    head.appendChild(button('Limpar seleção', 'Voltar a escolher outro painel', function(){self.selectPanel(face,null);}, 'plf-mini'));
    editor.appendChild(head);
    var body = el('div', 'plf-panel-editor-body');
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
    var topVoid=Math.max(0,number(data.top_void_cm));
    canvas.dataset.totalWidth=totalW; canvas.dataset.totalHeight=totalH; canvas.dataset.topVoid=topVoid;
    function shape(cls,left,bottom,width,height,label){
      var group=svgEl('g',{'class':cls}), top=totalH-bottom-height;
      group.appendChild(svgEl('rect',{x:left,y:top,width:Math.max(0,width),height:Math.max(0,height)}));
      if(label)group.appendChild(svgEl('text',{x:left+width/2,y:top+height/2,'text-anchor':'middle','dominant-baseline':'middle','font-size':Math.min(4.2,Math.max(1.2,width/6),Math.max(1.2,height*.6))},label));
      canvas.appendChild(group);return group;
    }
    var xOffsets={}, yOffsets={}, x=0, y=0; colIds.forEach(function(c){xOffsets[c]=x;x+=columns[c]+colExtra[c];}); rowIds.forEach(function(r){yOffsets[r]=y;y+=rows[r];});
    if(topVoid>0){
      var voidBand=svgEl('g',{'class':'plf-svg-top-void'});
      voidBand.appendChild(svgEl('rect',{x:0,y:-topVoid,width:totalW,height:topVoid}));
      voidBand.appendChild(svgEl('text',{x:totalW/2,y:-topVoid/2,'text-anchor':'middle','dominant-baseline':'middle','font-size':Math.min(5,Math.max(2,totalW/5))},'VAZIO '+topVoid+' cm'));
      if(data.top_void_evidence)voidBand.appendChild(svgEl('title',{},data.top_void_evidence));
      canvas.appendChild(voidBand);
    }
    function visualWidth(p){return number(p.width)+(p.column===lastCol?colExtra[p.column]:0);}
    function visualLeft(p){return xOffsets[p.column]+number(p.distance);}
    panels.forEach(function(p){
      var isSelected = self.isSelected('panel',face,{id:p.id});
      var panelHeight=number(p.height); if(panelHeight<=0)return;
      var cell=shape('plf-svg-cell kind-'+p.kind+' hatch-'+p.hatch+(isSelected?' selected':''),visualLeft(p),yOffsets[p.row],visualWidth(p),panelHeight,visualWidth(p)+' × '+panelHeight);
      cell.dataset.panelId=p.id;
      cell.dataset.selectType='panel';
      var dim=cell.querySelector('text');
      if(panelHeight>20){dim.setAttribute('font-size',6.5);if(visualWidth(p)<35)dim.setAttribute('transform','rotate(-90 '+dim.getAttribute('x')+' '+dim.getAttribute('y')+')');}
      if(panelHeight>8)cell.appendChild(svgEl('text',{x:visualLeft(p)+1.5,y:totalH-yOffsets[p.row]-panelHeight+5,'font-size':Math.min(4.5,visualWidth(p)/5)},p.id));
      cell.setAttribute('tabindex','0'); cell.setAttribute('role','button'); cell.setAttribute('aria-label','Editar painel '+p.id);cell.setAttribute('aria-pressed',!!isSelected);
      var choose = function(){self.selectPanel(face,p.id);}; cell.addEventListener('click',choose); cell.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});
    });
    (data.slabs||[]).forEach(function(slab,i){
      var w=number(slab.width),h=number(slab.height);if(w<=0||h<=0)return;
      var left=number(slab.left_distance);
      if(left===0 && number(slab.right_distance)>0)left=totalW-number(slab.right_distance)-w;
      var selected=self.isSelected('slab',face,{index:i});
      var band=shape('plf-svg-slab'+(selected?' selected':''),left,totalH+topVoid-number(slab.top_distance)-h,w,h,'LAJE '+(i+1));
      band.dataset.selectType='slab';band.dataset.index=i;
      band.setAttribute('tabindex','0');band.setAttribute('role','button');band.setAttribute('aria-label','Editar laje '+(i+1)+' da face '+face);band.setAttribute('aria-pressed',selected);
      var choose=function(){self.selectElement({type:'slab',face:face,index:i});};
      band.addEventListener('click',choose);band.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});
      band.appendChild(svgEl('title',{},'Laje '+(i+1)+' · '+w+' × '+h+' cm'));
    });
    // No contrato N3, y_rel mede a partir do topo da cinta h1. Esta é a
    // mesma origem que o gerador usa no DXF para as vigas e aberturas.
    var openingBase=rows[rowIds[0]]||0;
    self.orderedOpenings(data).forEach(function(item){
      var side=item.side,i=item.index,o=item.opening;
      if(!o.width||!o.depth)return;
      var centralSlot=o.n3_slot&&o.n3_slot.length===2&&o.n3_slot[0]===o.n3_slot[1];
      var ox=centralSlot?(totalW-number(o.width))/2:
        side==='left'?number(o.distance):totalW-number(o.distance)-number(o.width);
      var hasLevel=o.level!==undefined&&o.level!==null&&o.level!=='';
      var hasAbsoluteLevel=o.element_level!==undefined&&o.element_level!==null&&Number.isFinite(Number(o.top_distance));
      var oy=hasAbsoluteLevel?totalH+topVoid-number(o.top_distance)-number(o.depth):
        hasLevel?openingBase+number(o.level):Math.max(0,totalH-number(o.top_distance)-number(o.depth));
      var selected=self.isSelected('opening',face,{side:side,index:i});
      var opening=shape('plf-svg-opening'+(o.n3_kind==='passing_beam'?' passing-beam':'')+(selected?' selected':''),ox,oy,number(o.width),number(o.depth),(side==='left'?'E':'D')+(i+1));
      opening.dataset.selectType='opening';opening.dataset.side=side;opening.dataset.index=i;
      opening.setAttribute('tabindex','0');opening.setAttribute('role','button');
      opening.setAttribute('aria-label','Editar abertura '+(side==='left'?'esquerda':'direita')+' '+(i+1)+' da face '+face);
      opening.setAttribute('aria-pressed',selected);
      var choose=function(){self.selectElement({type:'opening',face:face,side:side,index:i});};
      opening.addEventListener('click',choose);opening.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});
    });
  };
  App.prototype.addRow = function(face){var d=this.data.faces[face], rows=d.panels.map(function(p){return p.row;}), cols=d.panels.map(function(p){return p.column;}), row=Math.max.apply(null,rows.concat([0]))+1, self=this; Array.from(new Set(cols)).forEach(function(c){var ref=d.panels.find(function(p){return p.column===c;});d.panels.push({id:nextId(face,d.panels),row:row,column:c,distance:0,width:ref?ref.width:30,height:40,kind:'panel',hatch:'none'});});self.changed();self.render();};
  App.prototype.removeRow = function(face){var d=this.data.faces[face], max=Math.max.apply(null,d.panels.map(function(p){return p.row;}).concat([1]));if(max>1)d.panels=d.panels.filter(function(p){return p.row!==max;});this.changed();this.render();};
  App.prototype.addColumn = function(face){var d=this.data.faces[face], cols=d.panels.map(function(p){return p.column;}), rows=d.panels.map(function(p){return p.row;}), col=Math.max.apply(null,cols.concat([0]))+1; Array.from(new Set(rows)).forEach(function(r){var ref=d.panels.find(function(p){return p.row===r;});d.panels.push({id:nextId(face,d.panels),row:r,column:col,distance:0,width:ref?ref.width:30,height:ref?ref.height:40,kind:'panel',hatch:'none'});});this.changed();this.render();};
  App.prototype.removeColumn = function(face){var d=this.data.faces[face],max=Math.max.apply(null,d.panels.map(function(p){return p.column;}).concat([1]));if(max>1)d.panels=d.panels.filter(function(p){return p.column!==max;});this.changed();this.render();};
  App.prototype.renderOpenings = function(face,data){
    var self=this,group=el('section','plf-opening-list'),head=el('div','plf-opening-head');
    head.appendChild(el('b','','Aberturas de viga'));
    ['left','right'].forEach(function(side){
      head.appendChild(button(side==='left'?'+ abertura esquerda':'+ abertura direita','Máximo 4 por lado',function(){
        if(data.openings[side].length<4){
          data.openings[side].push({distance:0,width:0,depth:0,level:0,
            element_level:self.pillarTopLevel(),top_distance:0});
          self.changed();self.render();
        }
      },'plf-add'));
    });
    group.appendChild(head);
    self.orderedOpenings(data).forEach(function(item){
      var side=item.side,i=item.index,opening=item.opening;
      var selected=self.isSelected('opening',face,{side:side,index:i});
      var row=el('div','plf-opening-row'+(selected?' plf-selection-box':''));
      row.appendChild(el('strong','',(side==='left'?'E':'D')+(i+1)+' · '+(side==='left'?'Esquerda':'Direita')));
      row.appendChild(field(side==='left'?'Dist. esquerda':'Dist. direita',opening.distance,function(v){opening.distance=v;self.changed();}));
      row.appendChild(field('Largura',opening.width,function(v){opening.width=v;self.changed();}));
      row.appendChild(field('Profundidade',opening.depth,function(v){opening.depth=v;self.changed();}));
      var levelNotes=self.renderLevelFields(row,opening,'element_level');
      row.appendChild(button('×','Excluir abertura',function(){
        data.openings[side].splice(i,1);
        if(self.selectedPanel&&self.selectedPanel.type==='opening'&&self.selectedPanel.face===face&&self.selectedPanel.side===side)self.selectedPanel=null;
        self.changed();self.render();
      },'plf-delete'));
      levelNotes.forEach(function(note){row.appendChild(note);});
      group.appendChild(row);
    });
    return group;
  };
  App.prototype.renderSlabs = function(face,data){
    var self=this,group=el('section','plf-slab-group'),head=el('div','plf-opening-head');
    if(!Array.isArray(data.slabs))data.slabs=[];
    var widths={};data.panels.forEach(function(panel){
      widths[panel.column]=Math.max(widths[panel.column]||0,number(panel.distance)+number(panel.width));
    });
    var span=Object.keys(widths).reduce(function(total,key){return total+widths[key];},number(data.n3_width_extra));
    head.appendChild(el('b','','Lajes'));
    head.appendChild(button('+ laje','Adicionar laje nesta face',function(){
      data.slabs.push({left_distance:0,right_distance:0,level:self.pillarTopLevel(),top_distance:0,width:0,height:0});
      self.changed();self.render();
    },'plf-add'));
    group.appendChild(head);
    data.slabs.forEach(function(slab,i){
      var row=el('div','plf-slab-row'+(self.isSelected('slab',face,{index:i})?' plf-selection-box':''));row.appendChild(el('strong','','L'+(i+1)));
      [['left_distance','Dist. esquerda'],['right_distance','Dist. direita']].forEach(function(item){
        var control=field(item[1],slab[item[0]],function(v){
          slab[item[0]]=v;
          if(item[0]==='right_distance')slab.left_distance=Math.max(0,span-v-number(slab.width));
          if(item[0]==='left_distance'||item[0]==='width')slab.right_distance=Math.max(0,span-number(slab.left_distance)-number(slab.width));
          ['left_distance','right_distance'].forEach(function(key){
            if(key!==item[0]){var input=row.querySelector('[data-slab-key="'+key+'"] input');if(input)input.value=slab[key];}
          });
          self.changed();
        });
        control.dataset.slabKey=item[0];row.appendChild(control);
      });
      var levelNotes=self.renderLevelFields(row,slab,'level');
      [['width','Largura'],['height','Altura']].forEach(function(item){
        var control=field(item[1],slab[item[0]],function(v){
          slab[item[0]]=v;
          if(item[0]==='width'){
            slab.right_distance=Math.max(0,span-number(slab.left_distance)-v);
            var input=row.querySelector('[data-slab-key="right_distance"] input');if(input)input.value=slab.right_distance;
          }
          self.changed();
        });
        control.dataset.slabKey=item[0];row.appendChild(control);
      });
      row.appendChild(button('×','Excluir laje '+(i+1),function(){data.slabs.splice(i,1);if(self.selectedPanel&&self.selectedPanel.type==='slab'&&self.selectedPanel.face===face)self.selectedPanel=null;self.changed();self.render();},'plf-delete'));
      levelNotes.forEach(function(note){row.appendChild(note);});
      group.appendChild(row);
    });
    return group;
  };
  App.prototype.renderGrades = function(){var self=this,g=self.data.grades,wrap=el('div','plf-grades');var top=el('div','plf-grade-top');[['grade_1','Grade 1'],['distance_1','Distância 1'],['grade_2','Grade 2'],['distance_2','Distância 2'],['grade_3','Grade 3']].forEach(function(s){top.appendChild(field(s[1],g[s[0]],function(v){g[s[0]]=v;self.changed();}));});wrap.appendChild(top);wrap.appendChild(el('h4','','Detalhamento das grades · cada coluna alterna sarrafo e distância'));var table=el('table','plf-slat-table'),thead=el('thead'),hr=el('tr');hr.appendChild(el('th','', ''));g.vertical_slats.forEach(function(s,i){hr.appendChild(el('th','', 'Sarrafo V'+(i+1)));hr.appendChild(el('th','', 'Dist. '+(i+1)));});thead.appendChild(hr);table.appendChild(thead);var body=el('tbody');['width','height'].forEach(function(key){var tr=el('tr');tr.appendChild(el('th','',key==='width'?'Largura':'Altura'));g.vertical_slats.forEach(function(s){var td=el('td');td.appendChild(field('',s[key],function(v){s[key]=v;self.changed();}));tr.appendChild(td);var dist=el('td');if(key==='width')dist.appendChild(field('',s.distance,function(v){s.distance=v;self.changed();}));else dist.textContent='—';tr.appendChild(dist);});body.appendChild(tr);});table.appendChild(body);wrap.appendChild(table);wrap.appendChild(button('+ sarrafo vertical','',function(){g.vertical_slats.push({width:5,height:5,distance:0});self.changed();self.render();},'plf-add'));var hh=el('div','plf-horizontal-head');hh.appendChild(el('h4','','Sarrafos horizontais'));hh.appendChild(button('+ sarrafo','',function(){g.horizontal_slats.push({left_distance:0,right_distance:0,width:5,height:5});self.changed();self.render();},'plf-add'));wrap.appendChild(hh);g.horizontal_slats.forEach(function(s,i){var row=el('div','plf-horizontal-row');row.appendChild(el('strong','', 'Sarrafo H'+(i+1)));[['left_distance','Dist. esquerda'],['right_distance','Dist. direita'],['width','Largura'],['height','Altura']].forEach(function(k){row.appendChild(field(k[1],s[k[0]],function(v){s[k[0]]=v;self.changed();}));});row.appendChild(button('×','Excluir',function(){g.horizontal_slats.splice(i,1);self.changed();self.render();},'plf-delete'));wrap.appendChild(row);});return wrap;};

  window.PillarFicha = { mount:function(root,options){ if(root) return new App(root,options); } };
})();
