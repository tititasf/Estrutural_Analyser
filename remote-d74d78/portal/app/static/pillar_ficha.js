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
  function behaviorText(value) { return ({viga_para:'viga para',viga_chega:'viga chega',viga_passa:'viga passa',viga_interna:'viga interna',laje:'laje'})[value] || 'comportamento pendente ⚠'; }
  function itemText(name,dimension,behavior) { return (name||'sem nome ⚠')+' · '+(dimension||'dim. pendente ⚠')+' · '+behaviorText(behavior); }
  function svgEl(tag, attrs, text) {
    var node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.keys(attrs || {}).forEach(function(key){node.setAttribute(key, attrs[key]);});
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function field(label, value, change, title, eventName) {
    var wrap = el('label', 'plf-field');
    wrap.title = title || label;
    wrap.appendChild(el('span', '', label));
    var input = el('input'); input.type = 'number'; input.step = '0.1'; input.min = '0'; input.value = value==null?'':number(value);
    input.addEventListener(eventName||'input', function () { change(number(input.value)); });
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
      .then(function (body) { self.data = body.ficha; self.cimaContract = body.cima_contract || body.ficha.cima_contract || JSON.parse(JSON.stringify(body.ficha)); self.gradesDetail=body.grades_detail||{}; self.views = body.visualizacoes_n3 || {}; self.visualMode=body.visual_mode||self.visualMode||'NOVA'; self.availableVisualModes=body.available_visual_modes||[]; self.dirty = false; self.saving = false; self.render(); self.discoverRegen(); })
      .catch(function (err) { self.root.innerHTML = '<p class="plf-error">Não foi possível carregar a ficha N3: ' + err.message + '</p>'; });
  };
  App.prototype.changed = function () {
    var self = this, status = self.root.querySelector('.plf-status');
    if (self.tab.indexOf('abcd') === 0) self.refreshFaces();
    self.dirty = true;
    if (self.tab === 'cima') {
      if (status) { status.textContent = 'Alterações não salvas'; status.classList.remove('error'); }
      self.paintActions();
      return;
    }
    if (status) status.textContent = 'Alterado · salvando…';
    self.paintActions();
    clearTimeout(self.timer); self.timer = setTimeout(function () { self.save(); }, 650);
  };
  App.prototype.save = function () {
    var self = this, status = self.root.querySelector('.plf-status');
    self.data.cima_contract = self.cimaContract;
    self.saving = true; self.paintActions();
    return fetch(self.url(), {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ficha:self.data})})
      .then(function (r) { return r.json().then(function (body) { if (!r.ok) throw new Error(body.detail || 'HTTP ' + r.status); return body; }); })
      .then(function (body) { if(self.tab.indexOf('abcd')!==0) self.data = body.ficha; else {self.data.revision=body.revision;self.data.source=body.ficha.source;} self.cimaContract = body.ficha.cima_contract || self.cimaContract; self.dirty = false; self.saving = false; if (status) { status.textContent = 'Salvo · revisão ' + body.revision; status.classList.remove('error'); } self.paintActions(); return body; })
      .catch(function (err) { self.saving = false; if (status) { status.textContent = 'Erro ao salvar: ' + err.message; status.classList.add('error'); } self.paintActions(); throw err; });
  };
  App.prototype.regenUrl = function (suffix) {
    var query = this.options.pavimento ? '?pavimento=' + encodeURIComponent(this.options.pavimento) : '';
    return '/obras/' + this.options.obraId + '/n1/' + this.options.classe + '/' + encodeURIComponent(this.options.itemId) + '/pilar-n3-' + encodeURIComponent(this.tab) + '/regenerar' + (suffix || '') + query;
  };
  App.prototype.regenActive = function () { var job=this.regenJob; return !!job && ['queued','running','paused'].indexOf(job.estado)>=0; };
  App.prototype.viewLabel = function () { return ({cima:'Cima','abcd-para':'ABCD Para','abcd-passa':'ABCD Passa','grades-para':'Grades Para','grades-passa':'Grades Passa'})[this.tab] || this.tab; };
  App.prototype.paintActions = function () {
    var save=this.root.querySelector('[data-plf-save]'), regen=this.root.querySelector('[data-plf-regen]'), monitor=this.root.querySelector('[data-plf-monitor]');
    if(save){save.disabled=!this.dirty||this.saving;save.textContent=this.saving?'Salvando…':'Salvar edições manuais';}
    if(regen){regen.disabled=this.saving||this.regenChecking||this.regenActive();regen.textContent=this.regenActive()?(this.regenJob.estado==='queued'?'Regeneração na fila':'Regeneração em andamento'):'Solicitar regeneração N3 '+this.viewLabel();}
    if(!monitor)return;
    var job=this.regenJob, labels={queued:'Na fila',running:'Regenerando N3 '+this.viewLabel(),paused:'Pausada',done:'Concluída',error:'Falhou',cancelled:'Cancelada'};
    if(this.regenChecking&&!job)monitor.innerHTML='<b>Consultando regeneração…</b><span>Verificando a fila</span>';
    else if(!job&&this.regenError)monitor.innerHTML='<b class="error">Falha ao consultar</b><span>'+this.regenError+'</span>';
    else if(job){var progress=job.progresso||{},pct=progress.percentual_estimado,detail=progress.rotulo||labels[job.estado]||job.estado;monitor.innerHTML='<b>'+labels[job.estado]+'</b><span>'+detail+(typeof pct==='number'?' · '+pct+'%':'')+'</span>'+(typeof pct==='number'?'<i><em style="width:'+Math.max(0,Math.min(100,pct))+'%"></em></i>':'')+(job.erro_msg?'<small>'+job.erro_msg+'</small>':'');}
    else monitor.innerHTML='';
    monitor.hidden=!monitor.innerHTML;
  };
  App.prototype.pollRegen = function (jobId) {
    var self=this;if(!jobId)return;if(self.regenTimer){clearTimeout(self.regenTimer);self.regenTimer=null;}self.regenChecking=true;self.paintActions();
    fetch('/jobs/'+encodeURIComponent(jobId),{cache:'no-store'}).then(function(r){return r.json().then(function(body){if(!r.ok)throw new Error(body.detail||'HTTP '+r.status);return body;});}).then(function(job){self.regenChecking=false;self.regenError='';self.regenJob=job;self.paintActions();if(self.regenActive())self.regenTimer=setTimeout(function(){self.pollRegen(jobId);},2500);else if(job.estado==='done'&&self.regenRefreshOnDone===jobId){self.regenRefreshOnDone=null;self.load();}}).catch(function(err){self.regenChecking=false;self.regenError=err.message;self.paintActions();if(self.regenActive())self.regenTimer=setTimeout(function(){self.pollRegen(jobId);},4000);});
  };
  App.prototype.discoverRegen = function () {
    var self=this;if(self.regenDiscovered||self.regenChecking)return;self.regenChecking=true;self.paintActions();
    fetch(self.regenUrl('/status'),{cache:'no-store'}).then(function(r){return r.json().then(function(body){if(!r.ok)throw new Error(body.detail||'HTTP '+r.status);return body;});}).then(function(result){self.regenDiscovered=true;self.regenChecking=false;if(result.job_id)self.pollRegen(result.job_id);else self.paintActions();}).catch(function(err){self.regenDiscovered=true;self.regenChecking=false;self.regenError=err.message;self.paintActions();});
  };
  App.prototype.requestRegen = function (requestedMode) {
    var self=this;if(self.regenActive()||self.regenChecking)return;
    var chooser=requestedMode?Promise.resolve(requestedMode):(window.escolherModoDesenho?window.escolherModoDesenho({currentMode:self.visualMode,description:'Escolha o estilo para regenerar o N3 '+self.viewLabel()+' deste pilar.'}):Promise.resolve('NOVA'));
    chooser.then(function(mode){if(!mode)return null;clearTimeout(self.timer);var ready=self.dirty?self.save():Promise.resolve();return ready.then(function(){self.regenChecking=true;self.regenError='';self.paintActions();return fetch(self.regenUrl(),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({visual_mode:mode})});});}).then(function(r){if(!r)return null;return r.json().then(function(body){if(!r.ok)throw new Error(body.detail||'HTTP '+r.status);return body;});}).then(function(body){if(!body)return;self.regenRefreshOnDone=body.job_id;self.pollRegen(body.job_id);}).catch(function(err){self.regenChecking=false;self.regenError=err.message;self.paintActions();});
  };
  App.prototype.renderActions = function () {
    var self=this, actions=el('div','plf-cima-actions');
    actions.appendChild(button('Salvar edições manuais','Persiste os valores editados desta ficha',function(){clearTimeout(self.timer);self.save().catch(function(){});},'success'));
    actions.lastChild.setAttribute('data-plf-save','');
    actions.appendChild(button('Solicitar regeneração N3 '+this.viewLabel(),'Regenera somente esta vista deste pilar',function(){self.requestRegen();},'primary'));
    actions.lastChild.setAttribute('data-plf-regen','');
    var monitor=el('div','plf-cima-monitor');monitor.setAttribute('data-plf-monitor','');monitor.hidden=true;actions.appendChild(monitor);
    setTimeout(function(){self.paintActions();},0);
    return actions;
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
          if (self.dirty && !confirm('Descartar as alterações não salvas desta ficha?')) return;
          clearTimeout(self.timer);clearTimeout(self.regenTimer);self.regenJob=null;self.regenDiscovered=false;self.regenChecking=false;self.regenError='';
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
      card.appendChild(el('p', 'muted', 'Use o botão acima para regenerar exatamente este desenho neste modo.'));
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
    box.appendChild(self.renderActions());
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
    board.appendChild(controls); board.appendChild(self.renderActions()); return board;
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
    head.appendChild(el('span', 'plf-face-meta', data.panels.length + ' painel(is) de base · ' + openingCount + ' recorte(s) de viga · ' + (data.slabs||[]).length + ' laje(s)'));
    var tools = el('div', 'plf-face-tools');
    tools.appendChild(button('+H','Adicionar linha de altura nesta face',function(){self.addRow(face);},'plf-mini'));
    tools.appendChild(button('−H','Remover última linha desta face',function(){self.removeRow(face);},'plf-mini'));
    tools.appendChild(button('+L','Adicionar coluna de largura nesta face',function(){self.addColumn(face);},'plf-mini'));
    tools.appendChild(button('−L','Remover última coluna desta face',function(){self.removeColumn(face);},'plf-mini'));
    head.appendChild(tools); card.appendChild(head);
    card.appendChild(this.renderPanelEditor(face, data));
    var cutPieces=(this.visualFragments&&this.visualFragments[face]||[]).filter(function(entry){return entry.isCut;});
    if(cutPieces.length){
      var pieces=el('div','plf-fragments');pieces.appendChild(el('b','','Painéis após os recortes'));
      cutPieces.forEach(function(entry){
        var chosen=self.isSelected('panel',face,{id:entry.id,fragmentIndex:entry.index});
        var control=button(entry.id+'.'+(entry.index+1)+' · '+entry.description,
          'Selecionar este painel recortado',function(){
            var current=(self.visualFragments[face]||[]).find(function(part){return part.id===entry.id&&part.index===entry.index;});
            if(current)self.selectElement({type:'panel',face:face,id:current.id,fragmentIndex:current.index,fragmentSize:{width:current.width,height:current.height,label:current.description}});
          },'plf-fragment-button'+(chosen?' active':''));
        control.dataset.panelId=entry.id;control.dataset.fragmentIndex=entry.index;pieces.appendChild(control);
      });card.appendChild(pieces);
    }
    if(number(data.top_void_cm)>0){
      var info=el('div','plf-void-info'+(self.isSelected('void',face,{})?' plf-selection-box':''));
      info.setAttribute('role','button');info.setAttribute('tabindex','0');
      info.setAttribute('aria-label','Selecionar '+itemText(data.top_void_name,data.top_void_dimension,data.top_void_behavior)+' da face '+face);
      var chooseTopVoid=function(){self.selectElement({type:'void',face:face});};
      info.addEventListener('click',chooseTopVoid);
      info.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseTopVoid();}});
      info.appendChild(el('b','','Vazio superior · '+number(data.top_void_cm)+' cm'));
      info.appendChild(el('span','',itemText(data.top_void_name,data.top_void_dimension,data.top_void_behavior)));
      card.appendChild(info);
    }
    card.appendChild(this.renderOpenings(face, data));
    card.appendChild(this.renderSlabs(face, data)); return card;
  };
  App.prototype.refreshFaces = function () {
    var svg=this.root.querySelector('.plf-shared-svg'); if(svg)this.paintFaces(svg);
    var note=this.root.querySelector('.plf-panel-editor-n3'), selection=this.selectedPanel;
    this.root.querySelectorAll('.plf-fragment-button').forEach(function(control){
      var current=(this.visualFragments[this.activeFace]||[]).find(function(part){return part.id===control.dataset.panelId&&part.index===Number(control.dataset.fragmentIndex);});
      control.hidden=!current;
      if(current)control.textContent=current.id+'.'+(current.index+1)+' · '+current.description;
    },this);
    if(selection&&selection.type==='panel'){
      var entry=(this.visualFragments&&this.visualFragments[selection.face]||[]).find(function(part){return part.id===selection.id&&part.index===selection.fragmentIndex;});
      if(entry){
        selection.fragmentSize={width:entry.width,height:entry.height,label:entry.description};
        var sizeNote=this.root.querySelector('.plf-fragment-note');
        if(sizeNote)sizeNote.textContent='Painel '+selection.id+'.'+(selection.fragmentIndex+1)+' após os vazios: '+entry.description+'. Largura e altura são medidas pelo contorno total; os vazios se adaptam à edição.';
        [['width',entry.width],['height',entry.height]].forEach(function(metric){
          var input=this.root.querySelector('[data-panel-dimension="'+metric[0]+'"] input');
          if(input&&document.activeElement!==input)input.value=metric[1];
        },this);
      }
    }
    if(note&&selection&&selection.type==='panel'){var face=this.data.faces[selection.face], panel=face.panels.find(function(p){return p.id===selection.id;});if(panel)note.textContent='Largura N3 exibida: '+number(panel.width)+' + '+number(face.n3_width_extra)+' = '+(number(panel.width)+number(face.n3_width_extra))+' cm';}
  };
  App.prototype.isSelected = function(type,face,detail){
    var chosen=this.selectedPanel;
    return !!chosen && chosen.type===type && chosen.face===face &&
      (type==='panel'?chosen.id===detail.id&&(detail.fragmentIndex===undefined||chosen.fragmentIndex===detail.fragmentIndex):type==='void'?true:type==='slab'?chosen.index===detail.index:chosen.side===detail.side&&chosen.index===detail.index);
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
      var gap=entry.geometry_level_gap_cm;
      gapNotice.hidden=levelKey!=='element_level'||gap==null||!Number.isFinite(Number(gap))||Math.abs(gap)<=1;
      if(!gapNotice.hidden)gapNotice.textContent='Cota SA e posição do recorte N3 divergem em '+Math.abs(gap).toLocaleString('pt-BR')+' cm. Conferir interpretação da viga antes de regenerar.';
    }
    function update(changed){
      if(levelKey==='element_level'){entry.level_source='manual';delete entry.geometry_level_gap_cm;provenance.hidden=true;}
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
      sa_related:'Nível recuperado de outro vínculo SA da mesma viga.',
      pillar_fallback:'⚠ Cota da viga não confirmada; usado o nível de chegada do pilar para revisão.'
    }[entry.level_source]||'SA sem cota inequívoca para esta viga; nível não estimado pelo desenho.';
    updateGap();
    return [notice,provenance,gapNotice];
  };
  App.prototype.selectElement = function(selection,face){
    this.selectedPanel=selection;
    this.root.querySelectorAll('.plf-svg-cell,.plf-svg-opening,.plf-svg-slab,.plf-svg-top-void').forEach(function(item){
      var chosen=selection && item.parentNode.dataset.face===selection.face &&
        item.dataset.selectType===selection.type &&
        (selection.type==='panel'?item.dataset.panelId===selection.id&&Number(item.dataset.fragmentIndex)===selection.fragmentIndex:
         selection.type==='void'?true:
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
    var maxNotes=0;
    layouts.forEach(function(group,index){
      var center=slot*(index+.5), width=number(group.dataset.totalWidth), height=number(group.dataset.totalHeight);
      var tag=svgEl('g',{'class':'plf-face-tag'});
      tag.appendChild(svgEl('rect',{x:center-labelSize*1.2,y:labelSize, width:labelSize*2.4,height:labelSize*1.8,rx:labelSize*.4}));
      tag.appendChild(svgEl('text',{x:center,y:labelSize*1.95,'font-size':labelSize,'text-anchor':'middle','dominant-baseline':'middle'},faces[index]));
      svg.appendChild(tag);
      // As quatro faces compartilham a linha de fundo, mesmo com alturas diferentes.
      group.setAttribute('transform','translate('+(center-width/2)+' '+(top+maxH-height)+')'); svg.appendChild(group);
      var data=self.data.faces[faces[index]], notes=[];
      if(number(data.top_void_cm)>0)notes.push(itemText(data.top_void_name,data.top_void_dimension,data.top_void_behavior)+' · vazio '+number(data.top_void_cm)+'cm');
      self.orderedOpenings(data).forEach(function(item){var o=item.opening;notes.push(itemText(o.beam_name,o.beam_dimension,o.beam_behavior));});
      (data.slabs||[]).forEach(function(s){notes.push(itemText(s.slab_name,s.slab_dimension,s.slab_behavior));});
      maxNotes=Math.max(maxNotes,notes.length);
      notes.forEach(function(note,i){svg.appendChild(svgEl('text',{'class':'plf-face-annotation',x:center-slot/2+4,y:top+maxH+10+i*8,'font-size':4},note));});
    });
    self.faceHome={x:0,y:0,w:Math.max(1,slot*faces.length),h:top+maxH+Math.max(gap/2,14+maxNotes*8)};
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
    if(self.selectedPanel.fragmentSize){
      var piece=self.selectedPanel.fragmentSize;
      editor.appendChild(el('div','plf-fragment-note','Painel '+selected.id+'.'+(self.selectedPanel.fragmentIndex+1)+' após os vazios: '+piece.label+'. Largura e altura são medidas pelo contorno total; os vazios se adaptam à edição.'));
    }
    var body = el('div', 'plf-panel-editor-body');
    body.appendChild(field(selected.column===1?'Dist. parede esq.':'Dist. painel anterior',selected.distance,function(v){selected.distance=v;self.changed();}));
    var size=self.selectedPanel.fragmentSize;
    if(size){
      var widthField=field('Largura total',size.width,function(v){
        var delta=v-number(self.selectedPanel.fragmentSize.width);
        var oldFaceWidth=Math.max.apply(null,data.panels.map(function(panel){return number(panel.distance)+number(panel.width);}).concat([0]))+number(data.n3_width_extra);
        selected.width=Math.max(0,number(selected.width)+delta);
        var newFaceWidth=Math.max.apply(null,data.panels.map(function(panel){return number(panel.distance)+number(panel.width);}).concat([0]))+number(data.n3_width_extra);
        var faceDelta=newFaceWidth-oldFaceWidth;
        if(Math.abs(faceDelta)>0.001)(data.slabs||[]).forEach(function(slab){
          if(Math.abs(number(slab.left_distance)+number(slab.width)+number(slab.right_distance)-oldFaceWidth)<0.2){
            slab.width=Math.max(0,number(slab.width)+faceDelta);
          }
        });
        self.changed();
      },null,'change');
      widthField.dataset.panelDimension='width';body.appendChild(widthField);
      var heightField=field('Altura total',size.height,function(v){selected.height=Math.max(0,number(selected.height)+v-number(self.selectedPanel.fragmentSize.height));self.changed();},null,'change');
      heightField.dataset.panelDimension='height';body.appendChild(heightField);
    }else{
      body.appendChild(field(number(data.n3_width_extra)>0?'Largura interna':'Largura',selected.width,function(v){selected.width=v;self.changed();}));
      body.appendChild(field('Altura',selected.height,function(v){selected.height=v;self.changed();}));
    }
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
    function coveredByAnother(rect, ownKey, candidates){
      var eps=.001;
      var own=candidates.find(function(candidate){return candidate.key===ownKey;});
      return candidates.some(function(other){
        if(other.key===ownKey)return false;
        var cover=rect.x>=other.rect.x-eps && rect.y>=other.rect.y-eps &&
          rect.x+rect.w<=other.rect.x+other.rect.w+eps && rect.y+rect.h<=other.rect.y+other.rect.h+eps;
        if(!cover)return false;
        var equal=Math.abs(rect.x-other.rect.x)<eps && Math.abs(rect.y-other.rect.y)<eps &&
          Math.abs(rect.w-other.rect.w)<eps && Math.abs(rect.h-other.rect.h)<eps;
        return !equal || (own&&other.order<own.order);
      });
    }
    var voidCandidates=[],candidateOrder=0;
    function addCandidate(key,rect){if(rect)voidCandidates.push({key:key,order:candidateOrder++,rect:rect});return rect;}
    if(topVoid>0)addCandidate('top',{x:0,y:-topVoid,w:totalW,h:topVoid});
    /* O vazio superior é desenhado depois de conhecer as outras aberturas. */
    function drawTopVoid(){
      if(!(topVoid>0)||coveredByAnother({x:0,y:-topVoid,w:totalW,h:topVoid},'top',voidCandidates))return;
      var voidBand=svgEl('g',{'class':'plf-svg-top-void'});
      voidBand.dataset.selectType='void';voidBand.setAttribute('role','button');voidBand.setAttribute('tabindex','0');
      voidBand.setAttribute('aria-label',itemText(data.top_void_name,data.top_void_dimension,data.top_void_behavior)+' · vazio '+topVoid+' cm da face '+face);
      var chooseVoid=function(){self.selectElement({type:'void',face:face});};
      voidBand.addEventListener('click',chooseVoid);voidBand.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseVoid();}});
      voidBand.appendChild(svgEl('rect',{x:0,y:-topVoid,width:totalW,height:topVoid}));
      voidBand.appendChild(svgEl('text',{x:totalW/2,y:-topVoid/2,'text-anchor':'middle','dominant-baseline':'middle','font-size':Math.min(5,Math.max(2,totalW/5))},(data.top_void_name||'VAZIO')+' · '+topVoid+' cm'));
      if(data.top_void_evidence)voidBand.appendChild(svgEl('title',{},data.top_void_evidence));
      canvas.appendChild(voidBand);
    }
    function visualWidth(p){return number(p.width)+(p.column===lastCol?colExtra[p.column]:0);}
    function visualLeft(p){return xOffsets[p.column]+number(p.distance);}
    function clipVoid(x,y,w,h){
      var x0=Math.max(0,x),x1=Math.min(totalW,x+w);
      if(x1<=x0||h<=0)return null;
      return {x:x0,y:y,w:x1-x0,h:h};
    }
    var cuts=[];
    (data.slabs||[]).forEach(function(slab,i){
      var w=number(slab.width),left=number(slab.left_distance);
      if(left===0&&number(slab.right_distance)>0)left=totalW-number(slab.right_distance)-w;
      var cut=clipVoid(left,number(slab.top_distance)-topVoid,w,number(slab.height));
      if(cut){cuts.push(cut);addCandidate('slab-'+i,cut);}
    });
    self.orderedOpenings(data).forEach(function(item){
      var o=item.opening,side=item.side,w=number(o.width),h=number(o.depth);
      var central=o.n3_slot&&o.n3_slot.length===2&&o.n3_slot[0]===o.n3_slot[1];
      var x=central?(totalW-w)/2:side==='left'?number(o.distance):totalW-number(o.distance)-w;
      if(o.beam_behavior==='viga_passa'||o.beam_behavior==='viga_interna'||w>=totalW)x=0,w=totalW;
      var absolute=o.element_level!==undefined&&o.element_level!==null&&Number.isFinite(Number(o.top_distance));
      var y=absolute?number(o.top_distance)-topVoid:totalH-(rows[rowIds[0]]||0)-number(o.level)-h;
      var cut=clipVoid(x,y,w,h);if(cut){cuts.push(cut);addCandidate('opening-'+item.side+'-'+item.index,cut);}
    });
    drawTopVoid();
    function subtract(rect,cut){
      var x0=Math.max(rect.x,cut.x),x1=Math.min(rect.x+rect.w,cut.x+cut.w);
      var y0=Math.max(rect.y,cut.y),y1=Math.min(rect.y+rect.h,cut.y+cut.h);
      if(x1<=x0||y1<=y0)return [rect];
      return [
        {x:rect.x,y:rect.y,w:rect.w,h:y0-rect.y},
        {x:rect.x,y:y1,w:rect.w,h:rect.y+rect.h-y1},
        {x:rect.x,y:y0,w:x0-rect.x,h:y1-y0},
        {x:x1,y:y0,w:rect.x+rect.w-x1,h:y1-y0}
      ].filter(function(piece){return piece.w>0.01&&piece.h>0.01;});
    }
    function connectedComponents(pieces){
      var seen=new Set(),components=[],eps=0.001;
      function touches(a,b){
        var side=(Math.abs(a.x+a.w-b.x)<eps||Math.abs(b.x+b.w-a.x)<eps)&&Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y)>eps;
        var top=(Math.abs(a.y+a.h-b.y)<eps||Math.abs(b.y+b.h-a.y)<eps)&&Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x)>eps;
        return side||top;
      }
      pieces.forEach(function(piece,start){
        if(seen.has(start))return;
        var members=[],stack=[start];seen.add(start);
        while(stack.length){
          var index=stack.pop();members.push(pieces[index]);
          pieces.forEach(function(other,j){if(!seen.has(j)&&touches(pieces[index],other)){seen.add(j);stack.push(j);}});
        }
        components.push(members);
      });
      return components;
    }
    function shapeOf(members){
      if(members.length===1)return 'retangular';
      var minX=Math.min.apply(null,members.map(function(p){return p.x;}));
      var maxX=Math.max.apply(null,members.map(function(p){return p.x+p.w;}));
      var minY=Math.min.apply(null,members.map(function(p){return p.y;}));
      var maxY=Math.max.apply(null,members.map(function(p){return p.y+p.h;}));
      var area=members.reduce(function(total,p){return total+p.w*p.h;},0);
      if(Math.abs(area-(maxX-minX)*(maxY-minY))<0.01)return 'retangular';
      if(members.length!==2)return 'recortado';
      var a=members[0],b=members[1],eps=0.001;
      var vertical=Math.abs(a.y+a.h-b.y)<eps||Math.abs(b.y+b.h-a.y)<eps;
      var horizontal=Math.abs(a.x+a.w-b.x)<eps||Math.abs(b.x+b.w-a.x)<eps;
      if(vertical&&(Math.abs(a.x-b.x)<eps||Math.abs(a.x+a.w-b.x-b.w)<eps))return 'em L';
      if(horizontal&&(Math.abs(a.y-b.y)<eps||Math.abs(a.y+a.h-b.y-b.h)<eps))return 'em L';
      return 'recortado';
    }
    if(!self.visualFragments)self.visualFragments={};
    self.visualFragments[face]=[];
    panels.forEach(function(p){
      var isSelected = self.isSelected('panel',face,{id:p.id});
      var panelHeight=number(p.height); if(panelHeight<=0)return;
      var panelTop=totalH-yOffsets[p.row]-panelHeight;
      var fragments=[{x:visualLeft(p),y:panelTop,w:visualWidth(p),h:panelHeight}];
      cuts.forEach(function(cut){fragments=fragments.flatMap(function(piece){return subtract(piece,cut);});});
      var components=connectedComponents(fragments);
      components.forEach(function(members,fragmentIndex){
        var kind=shapeOf(members);
        var minX=Math.min.apply(null,members.map(function(piece){return piece.x;}));
        var minY=Math.min.apply(null,members.map(function(piece){return piece.y;}));
        var maxX=Math.max.apply(null,members.map(function(piece){return piece.x+piece.w;}));
        var maxY=Math.max.apply(null,members.map(function(piece){return piece.y+piece.h;}));
        var overallWidth=maxX-minX,overallHeight=maxY-minY;
        var description=(kind==='retangular'?'':kind+' · ')+overallWidth+' × '+overallHeight+' cm';
        var isCut=fragments.length>1;
        self.visualFragments[face].push({id:p.id,index:fragmentIndex,count:components.length,isCut:isCut,width:overallWidth,height:overallHeight,description:description});
        var selectedPiece=isSelected&&self.selectedPanel.fragmentIndex===fragmentIndex;
        var cell=svgEl('g',{'class':'plf-svg-cell kind-'+p.kind+' hatch-'+p.hatch+(members.length>1?' connected':'')+(selectedPiece?' selected':'')});
        members.forEach(function(piece){
          // Retângulos da mesma peça compartilham bordas. Uma pequena
          // sobreposição interna evita a fresta escura de antialias do SVG.
          var seam=.25,px=piece.x,py=piece.y,pw=piece.w,ph=piece.h;
          members.forEach(function(other){
            if(other===piece)return;
            var verticalOverlap=Math.min(piece.y+piece.h,other.y+other.h)-Math.max(piece.y,other.y)>0.001;
            var horizontalOverlap=Math.min(piece.x+piece.w,other.x+other.w)-Math.max(piece.x,other.x)>0.001;
            if(verticalOverlap&&Math.abs(piece.x+piece.w-other.x)<.001)pw+=seam;
            if(verticalOverlap&&Math.abs(other.x+other.w-piece.x)<.001){px-=seam;pw+=seam;}
            if(horizontalOverlap&&Math.abs(piece.y+piece.h-other.y)<.001)ph+=seam;
            if(horizontalOverlap&&Math.abs(other.y+other.h-piece.y)<.001){py-=seam;ph+=seam;}
          });
          cell.appendChild(svgEl('rect',{x:px,y:py,width:pw,height:ph}));
        });
        var main=members.reduce(function(best,piece){return !best||piece.w*piece.h>best.w*best.h?piece:best;},null);
        if(main.w>=7&&main.h>=8){
          var label=svgEl('text',{x:main.x+main.w/2,y:main.y+main.h/2,'text-anchor':'middle','dominant-baseline':'middle','font-size':Math.min(6.5,Math.max(1.2,main.w/5))},members.length>1?(kind==='em L'?'EM L':'RECORTE'):main.w+' × '+main.h);
          if(main.w<35&&main.h>20)label.setAttribute('transform','rotate(-90 '+label.getAttribute('x')+' '+label.getAttribute('y')+')');
          cell.appendChild(label);
        }
        canvas.appendChild(cell);
        cell.dataset.panelId=p.id;cell.dataset.fragmentIndex=fragmentIndex;
        cell.dataset.selectType='panel';
        if(panelHeight>8)cell.appendChild(svgEl('text',{x:main.x+1.5,y:main.y+5,'font-size':Math.min(4.5,main.w/5)},p.id+(isCut?'.'+(fragmentIndex+1):'')));
        cell.setAttribute('tabindex','0');cell.setAttribute('role','button');
        cell.setAttribute('aria-label','Editar painel '+p.id+(isCut?'.'+(fragmentIndex+1):'')+' · '+description);
        cell.setAttribute('aria-pressed',!!selectedPiece);
        cell.appendChild(svgEl('title',{},description));
        var choose=function(){self.selectElement({type:'panel',face:face,id:p.id,fragmentIndex:fragmentIndex,fragmentSize:{width:overallWidth,height:overallHeight,label:description}});};
        cell.addEventListener('click',choose);cell.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});
      });
    });
    (data.slabs||[]).forEach(function(slab,i){
      var w=number(slab.width),h=number(slab.height);if(w<=0||h<=0)return;
      var candidate=voidCandidates.find(function(value){return value.key==='slab-'+i;});
      if(!candidate||coveredByAnother(candidate.rect,candidate.key,voidCandidates))return;
      var left=number(slab.left_distance);
      if(left===0 && number(slab.right_distance)>0)left=totalW-number(slab.right_distance)-w;
      var selected=self.isSelected('slab',face,{index:i});
      var band=shape('plf-svg-slab'+(selected?' selected':''),left,totalH+topVoid-number(slab.top_distance)-h,w,h,slab.slab_name||'LAJE '+(i+1));
      band.dataset.selectType='slab';band.dataset.index=i;
      band.setAttribute('tabindex','0');band.setAttribute('role','button');band.setAttribute('aria-label','Editar laje '+(i+1)+' da face '+face);band.setAttribute('aria-pressed',selected);
      var choose=function(){self.selectElement({type:'slab',face:face,index:i});};
      band.addEventListener('click',choose);band.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}});
      band.appendChild(svgEl('title',{},itemText(slab.slab_name,slab.slab_dimension,slab.slab_behavior)+' · vazio '+w+' × '+h+' cm'));
    });
    // No contrato N3, y_rel mede a partir do topo da cinta h1. Esta é a
    // mesma origem que o gerador usa no DXF para as vigas e aberturas.
    var openingBase=rows[rowIds[0]]||0;
    self.orderedOpenings(data).forEach(function(item){
      var side=item.side,i=item.index,o=item.opening;
      if(!o.width||!o.depth)return;
      var candidate=voidCandidates.find(function(value){return value.key==='opening-'+side+'-'+i;});
      if(!candidate||coveredByAnother(candidate.rect,candidate.key,voidCandidates))return;
      var centralSlot=o.n3_slot&&o.n3_slot.length===2&&o.n3_slot[0]===o.n3_slot[1];
      var ox=centralSlot?(totalW-number(o.width))/2:
        side==='left'?number(o.distance):totalW-number(o.distance)-number(o.width);
      var drawWidth=number(o.width);
      if(o.beam_behavior==='viga_passa'||o.beam_behavior==='viga_interna'||drawWidth>=totalW){ox=0;drawWidth=totalW;}
      else {var clipped=clipVoid(ox,0,drawWidth,number(o.depth));if(!clipped)return;ox=clipped.x;drawWidth=clipped.w;}
      var hasLevel=o.level!==undefined&&o.level!==null&&o.level!=='';
      var hasAbsoluteLevel=o.element_level!==undefined&&o.element_level!==null&&Number.isFinite(Number(o.top_distance));
      var oy=hasAbsoluteLevel?totalH+topVoid-number(o.top_distance)-number(o.depth):
        hasLevel?openingBase+number(o.level):Math.max(0,totalH-number(o.top_distance)-number(o.depth));
      var selected=self.isSelected('opening',face,{side:side,index:i});
      var opening=shape('plf-svg-opening'+(o.n3_kind==='passing_beam'?' passing-beam':'')+(selected?' selected':''),ox,oy,drawWidth,number(o.depth),o.beam_name||(side==='left'?'E':'D')+(i+1));
      opening.appendChild(svgEl('title',{},itemText(o.beam_name,o.beam_dimension,o.beam_behavior)+' · recorte '+number(o.width)+' × '+number(o.depth)+' cm'));
      opening.dataset.selectType='opening';opening.dataset.side=side;opening.dataset.index=i;
      opening.setAttribute('tabindex','0');opening.setAttribute('role','button');
      opening.setAttribute('aria-label','Editar '+itemText(o.beam_name,o.beam_dimension,o.beam_behavior)+' da face '+face);
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
    head.appendChild(el('b','','Aberturas e vazios de viga'));
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
      row.appendChild(el('strong','',(side==='left'?'E':'D')+(i+1)+' · '+itemText(opening.beam_name,opening.beam_dimension,opening.beam_behavior)+' · '+(side==='left'?'Esquerda':'Direita')));
      row.appendChild(field(side==='left'?'Dist. esquerda':'Dist. direita',opening.distance,function(v){opening.distance=v;self.changed();}));
      row.appendChild(field('Largura',opening.width,function(v){opening.width=v;self.changed();}));
      row.appendChild(field('Profundidade',opening.depth,function(v){opening.depth=v;self.changed();}));
      var faceWidth=Math.max.apply(null,data.panels.map(function(panel){return number(panel.width);}).concat([0]))+number(data.n3_width_extra);
      if(number(opening.width)>faceWidth+0.1)row.appendChild(el('span','plf-level-warning','⚠ Largura SA/N3 '+number(opening.width)+' cm excede a face '+faceWidth+' cm. Desenho limitado ao contorno; revisar vínculo da viga.'));
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
      var row=el('div','plf-slab-row'+(self.isSelected('slab',face,{index:i})?' plf-selection-box':''));row.appendChild(el('strong','',itemText(slab.slab_name,slab.slab_dimension,slab.slab_behavior)));
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

  App.prototype.renderGrades = function(){
    var self=this,detail=(this.gradesDetail||{}).faces||{};
    var wrap=el('div','plf-grades');
    wrap.appendChild(el('h4','','GRADES — quadradinhos e alturas'));
    wrap.appendChild(el('p','plf-grade-intro','Medidas do desenho N3 em cm. Larguras seguem a malha da vista Cima; alturas seguem o modo de desenho e os recortes de cada face.'));
    var faces=Object.keys(detail);
    if(!faces.length){wrap.appendChild(el('p','plf-grade-intro','O N3 ainda não informou medidas de grades para esta face.'));wrap.appendChild(self.renderActions());return wrap;}
    var tabs=el('div','plf-grade-face-tabs');tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Face das grades');
    var panels={},buttons={};
    function choose(face){
      self.gradesFace=face;
      faces.forEach(function(id){
        var active=id===face;
        buttons[id].classList.toggle('active',active);
        buttons[id].setAttribute('aria-selected',active?'true':'false');
        panels[id].hidden=!active;
      });
    }
    faces.forEach(function(face){
      var tab=button('Face '+face,'Detalhar grades da face '+face,function(){choose(face);},'plf-grade-face-tab');
      tab.setAttribute('role','tab');buttons[face]=tab;tabs.appendChild(tab);
      var panel=el('section','plf-grade-face');panel.setAttribute('role','tabpanel');
      panel.appendChild(el('strong','','Face '+face+' · largura externa '+detail[face].width+' cm'));
      detail[face].grades.forEach(function(grade,index){
        var card=el('article','plf-grade-card');
        card.appendChild(el('h5','','Grade '+(index+1)+' · largura '+grade.width+' cm'));
        var widths=el('div','plf-grade-measures');
        widths.appendChild(el('b','','Largura dos quadradinhos'));
        var widthFields=el('div','plf-grade-field-grid');
        grade.quadradinhos.forEach(function(value,col){
          var control=field('Q'+(col+1),value,function(){});
          control.querySelector('input').readOnly=true;
          widthFields.appendChild(control);
        });
        widths.appendChild(widthFields);card.appendChild(widths);
        var heights=el('div','plf-grade-measures');
        heights.appendChild(el('b','','Altura dos quadradinhos'));
        var heightFields=el('div','plf-grade-field-grid');
        heightFields.style.gridTemplateColumns='repeat('+grade.quadradinhos.length+',minmax(0,1fr))';
        var columnHeights=grade.alturas_por_coluna||[];
        grade.alturas_quadradinhos.forEach(function(value,row){
          grade.quadradinhos.forEach(function(width,col){
            var height=columnHeights[col]&&columnHeights[col][row]!=null?columnHeights[col][row]:value;
            var control=field('Q'+(col+1)+' · faixa '+(row+1),height,function(){});
            control.querySelector('input').readOnly=true;
            control.title='Altura deste quadradinho, limitada pelos montantes da coluna';
            heightFields.appendChild(control);
          });
        });
        heights.appendChild(heightFields);card.appendChild(heights);
        var preview=el('div','plf-grade-cell-preview');
        preview.style.gridTemplateColumns='repeat('+grade.quadradinhos.length+',minmax(0,1fr))';
        grade.alturas_quadradinhos.slice().reverse().forEach(function(value,reversedRow){
          var row=grade.alturas_quadradinhos.length-1-reversedRow;
          grade.quadradinhos.forEach(function(width,col){
            var height=columnHeights[col]&&columnHeights[col][row]!=null?columnHeights[col][row]:value;
            preview.appendChild(el('span','',''+width+' × '+height));
          });
        });
        card.appendChild(preview);
        card.appendChild(el('small','plf-grade-member-height','Alturas dos montantes: '+grade.alturas_montantes.join(' · ')+' cm'));
        panel.appendChild(card);
        if(index<detail[face].distancias.length)panel.appendChild(el('p','plf-grade-gap','Distância até a próxima grade: '+detail[face].distancias[index]+' cm'));
      });
      panels[face]=panel;wrap.appendChild(panel);
    });
    wrap.insertBefore(tabs,wrap.querySelector('.plf-grade-face'));
    choose(faces.indexOf(this.gradesFace)>=0?this.gradesFace:faces[0]);
    wrap.appendChild(self.renderActions());
    return wrap;
  };

  window.PillarFicha = { mount:function(root,options){ if(root) return new App(root,options); } };
})();
