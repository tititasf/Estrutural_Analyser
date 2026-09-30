(function () {
  'use strict';

  function esc(v) { return String(v == null ? '' : v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function shown(v) { return v === null || v === undefined || v === '' ? '—' : esc(v); }
  function query(o) {
    var params=[];
    if(o.pavimento)params.push('pavimento='+encodeURIComponent(o.pavimento));
    if(o.visualMode)params.push('visual_mode='+encodeURIComponent(o.visualMode));
    return params.length?'?'+params.join('&'):'';
  }
  function api(url, options) {
    options=options||{};
    // Fichas e camadas apontam para artefatos mutáveis por microciclo. Sem
    // isto o Chromium pode reaproveitar o JSON/SVG anterior mesmo depois de o
    // job publicar um DXF novo no servidor.
    if (!options.method || options.method==='GET') options.cache='no-store';
    return fetch(url, options).then(function (r) { return r.json().then(function (b) { if (!r.ok) throw new Error(b.detail || ('HTTP ' + r.status)); return b; }); });
  }
  function json(method, body) { return {method:method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}; }

  function cleanSvg(raw) {
    if (!raw) return '';
    var doc = new DOMParser().parseFromString(raw, 'image/svg+xml');
    if (doc.querySelector('parsererror')) return '';
    doc.querySelectorAll('script,foreignObject').forEach(function(n){n.remove();});
    doc.querySelectorAll('*').forEach(function(n){ Array.prototype.slice.call(n.attributes || []).forEach(function(a){
      if (/^on/i.test(a.name)) n.removeAttribute(a.name);
      if ((a.name === 'href' || a.name === 'xlink:href') && /^javascript:/i.test(a.value)) n.removeAttribute(a.name);
    }); });
    var svg = doc.documentElement; svg.removeAttribute('width'); svg.removeAttribute('height');
    svg.setAttribute('preserveAspectRatio','xMidYMid meet'); svg.classList.add('fv-web-svg');
    return new XMLSerializer().serializeToString(svg);
  }

  function initPanZoom(canvas) {
    var svg = canvas && canvas.querySelector('svg'); if (!svg || !svg.viewBox || !svg.viewBox.baseVal.width) return;
    var b=svg.viewBox.baseVal, home={x:b.x,y:b.y,w:b.width,h:b.height}, v={x:b.x,y:b.y,w:b.width,h:b.height}, drag=false,last;
    function apply(){svg.setAttribute('viewBox',[v.x,v.y,v.w,v.h].join(' '));}
    function reset(){v={x:home.x,y:home.y,w:home.w,h:home.h};apply();}
    canvas.addEventListener('wheel',function(e){e.preventDefault();var r=svg.getBoundingClientRect(),px=v.x+(e.clientX-r.left)/r.width*v.w,py=v.y+(e.clientY-r.top)/r.height*v.h,f=e.deltaY<0?.88:1.14,nw=Math.max(home.w*.01,Math.min(home.w*8,v.w*f)),nh=nw*home.h/home.w,rx=(px-v.x)/v.w,ry=(py-v.y)/v.h;v={x:px-rx*nw,y:py-ry*nh,w:nw,h:nh};apply();},{passive:false});
    canvas.addEventListener('mousedown',function(e){if(e.button>1)return;e.preventDefault();drag=true;last={x:e.clientX,y:e.clientY};canvas.classList.add('dragging');});
    window.addEventListener('mousemove',function(e){if(!drag)return;var r=svg.getBoundingClientRect();v.x-=(e.clientX-last.x)/r.width*v.w;v.y-=(e.clientY-last.y)/r.height*v.h;last={x:e.clientX,y:e.clientY};apply();});
    window.addEventListener('mouseup',function(){drag=false;canvas.classList.remove('dragging');}); canvas.addEventListener('dblclick',reset);
    var btn=canvas.querySelector('[data-lj-reset]');if(btn)btn.addEventListener('click',reset);
  }

  function layerButton(key, info, active) {
    var labels={sa:'SA',c1:'Camada 1',c2:'Camada 2',c3:'Camada 3',n3:'N3'};
    return '<button type="button" class="fv-web-layer '+key+(active?' active':'')+'" data-lj-layer="'+key+'" '+(!info.available?'disabled title="Camada ainda não materializada"':'')+'><i>'+(key==='n3'?'■':'●')+'</i>'+labels[key]+'<small>'+(info.loading?'carregando':(info.lazy?'sob demanda':(info.available?'disponível':'ausente')))+'</small></button>';
  }

  function saFields(item, editing) {
    if (editing) return '<div class="lj-fields-grid"><label>Nome<input name="name" value="'+esc(item.name)+'"></label><label>Nível<input name="nivel" inputmode="decimal" value="'+esc(item.nivel)+'"></label><label>Altura (cm)<input name="height" inputmode="decimal" value="'+esc(item.height)+'"></label></div>';
    return '<div class="lj-fields-grid"><div><span>Nome</span><b>'+shown(item.name)+'</b></div><div><span>Nível</span><b>'+shown(item.nivel)+'</b></div><div><span>Altura</span><b>'+shown(item.height)+' cm</b></div></div>';
  }

  function derivePanels(rows,total) {
    total=Number(total);
    if (!(total>0)) return [];
    var positions=(rows||[]).map(function(row){return {value:Number(row.value),is_union:!!row.is_union};})
      .filter(function(row){return row.value>0&&row.value<total;}).sort(function(a,b){return a.value-b.value;})
      .filter(function(row,index,all){return !index||Math.abs(row.value-all[index-1].value)>.0001;});
    var previous=0;
    var panels=positions.map(function(row,index){var width=Math.round((row.value-previous)*1000)/1000;previous=row.value;return {index:index+1,value:width,is_remainder:false,is_union:row.is_union};});
    panels.push({index:panels.length+1,value:Math.round((total-previous)*1000)/1000,is_remainder:true,is_union:false});
    return panels;
  }

  function editablePanelRow(axis,panel) {
    return '<div class="lj-n3-panel-row" data-lj-panel-row data-axis="'+axis+'"><span data-lj-panel-label>Painel '+panel.index+'</span><label class="lj-n3-panel-value"><input type="number" min="0.001" step="0.1" value="'+esc(panel.value)+'" aria-label="Largura do painel '+panel.index+' em cm"><small>cm</small></label><label class="lj-n3-union"><input type="checkbox" '+(panel.is_union?'checked':'')+'> União</label><button type="button" data-lj-remove aria-label="Remover painel '+panel.index+'">×</button></div>';
  }

  function panelEditor(axis,rows,total,editing) {
    var title=axis==='vertical'?'Painéis verticais':'Painéis horizontais';
    var remainder=axis==='vertical'?'Sobra vertical':'Sobra horizontal';
    var panels=derivePanels(rows,total);
    var body=panels.map(function(panel){
      if (panel.is_remainder) return '<div class="lj-n3-panel-row remainder" data-lj-remainder-row><span>'+remainder+'</span><b><output data-lj-remainder>'+shown(panel.value)+'</output> cm</b><em>Automática</em></div>';
      if (editing) return editablePanelRow(axis,panel);
      return '<div class="lj-n3-panel-row"><span>Painel '+panel.index+'</span><b>'+shown(panel.value)+' cm</b><em>'+(panel.is_union?'União':'Divisão')+'</em></div>';
    }).join('');
    return '<section><h4>'+title+'</h4><div class="lj-n3-panel-list" data-lj-panel-list="'+axis+'" data-total="'+esc(total)+'">'+body+'</div>'+(editing?'<button type="button" data-lj-add="'+axis+'">+ Adicionar painel</button>':'')+'</section>';
  }

  function n3Fields(data, editing) {
    return '<div class="lj-n3-summary"><div><span>Comprimento</span><b>'+shown(data.n3.comprimento)+' cm</b></div><div><span>Largura</span><b>'+shown(data.n3.largura)+' cm</b></div><div><span>Modo</span><b>'+shown(data.n3.modo_selecionado)+'</b></div><div><span>Fonte</span><b>'+(data.n3.has_override?'Correção humana':'Contrato do motor')+'</b></div></div>'+
      '<p class="lj-n3-help">Cada campo é a largura real cotada no N3. A sobra final é calculada automaticamente a partir da dimensão total da laje.</p>'+
      '<div class="lj-n3-columns">'+panelEditor('vertical',data.n3.linhas_verticais,data.n3.comprimento,editing)+panelEditor('horizontal',data.n3.linhas_horizontais,data.n3.largura,editing)+'</div>';
  }

  function refreshPanelEditors(root) {
    var save=root.querySelector('[data-lj-save]');
    if(!save)return;
    var valid=true;
    root.querySelectorAll('[data-lj-panel-list]').forEach(function(list){
      var sum=0;
      list.querySelectorAll('[data-lj-panel-row]').forEach(function(row,index){var label=row.querySelector('[data-lj-panel-label]');if(label)label.textContent='Painel '+(index+1);var input=row.querySelector('input[type=number]');var value=Number(input&&input.value);if(value>0)sum+=value;else valid=false;});
      var remainder=Math.round((Number(list.dataset.total)-sum)*1000)/1000;
      var output=list.querySelector('[data-lj-remainder]');if(output)output.textContent=shown(remainder);
      list.classList.toggle('invalid',!(remainder>0));
      if (!(remainder>0)) valid=false;
    });
    save.disabled=!valid;
  }

  function noteCards(notes) {
    var labels={sa:'SA',c1:'Camada 1',c2:'Camada 2',c3:'Camada 3',n3:'N3'};
    return Object.keys(labels).map(function(k){return '<label>'+labels[k]+'<textarea data-lj-note="'+k+'" placeholder="Opinião humana sobre esta camada">'+esc(notes[k]||'')+'</textarea></label>';}).join('');
  }

  function regenActive(job) { return !!job && (job.estado === 'queued' || job.estado === 'running' || job.estado === 'paused'); }
  function regenTime(value) { if (!value) return ''; var d=new Date(value); return isNaN(d.getTime())?'':d.toLocaleString('pt-BR'); }
  function regenMonitorMarkup(state) {
    var job=state.regenJob;
    if (!job && !state.regenChecking && !state.regenError) return '';
    if (state.regenChecking && !job) return '<div class="lj-regen-head"><b>Consultando regeneração N3…</b><span>Verificando a fila</span></div>';
    if (!job) return '<div class="lj-regen-head error"><b>Não foi possível consultar o job</b><span>'+esc(state.regenError)+'</span></div>';
    var labels={queued:'Na fila',running:'Regenerando N3',paused:'Pausada',done:'Concluída',error:'Falhou',cancelled:'Cancelada'};
    var progress=job.progresso||{}, pct=progress.percentual_estimado, active=regenActive(job);
    var when=job.finalizado_em||job.iniciado_em||job.criado_em;
    var detail=progress.rotulo||labels[job.estado]||job.estado;
    var error=job.erro_msg?'<p class="lj-regen-error">'+esc(job.erro_msg)+'</p>':'';
    var bar=(typeof pct==='number')?'<div class="lj-regen-progress"><i style="width:'+Math.max(0,Math.min(100,pct))+'%"></i></div>':'';
    return '<div class="lj-regen-head '+esc(job.estado)+'"><b>'+(active?'<i class="lj-regen-spinner"></i>':'')+esc(labels[job.estado]||'Status')+'</b><span>'+esc(detail)+(typeof pct==='number'?' · '+pct+'%':'')+'</span></div>'+bar+
      '<div class="lj-regen-meta"><span>Job '+esc(String(job.job_id||'').slice(0,8))+'</span>'+(when?'<span>'+esc(regenTime(when))+'</span>':'')+'</div>'+error;
  }

  function paintRegen(root,state) {
    var button=root.querySelector('[data-lj-regenerate]'), monitor=root.querySelector('[data-lj-regen-monitor]');
    if (button) {
      var active=regenActive(state.regenJob);
      button.disabled=!!state.regenChecking||active;
      button.textContent=active?(state.regenJob.estado==='queued'?'Regeneração N3 na fila':'Regeneração N3 em andamento'):'Solicitar regeneração N3';
    }
    if (monitor) {
      monitor.innerHTML=regenMonitorMarkup(state);
      monitor.hidden=!monitor.innerHTML;
      monitor.className='lj-regen-monitor'+(state.regenJob?' '+state.regenJob.estado:'');
    }
  }

  function pollRegenJob(root,data,options,state,jobId) {
    if (root._ljState !== state || !jobId) return;
    if (state.regenTimer) { clearTimeout(state.regenTimer); state.regenTimer=null; }
    state.regenChecking=true; paintRegen(root,state);
    api('/jobs/'+encodeURIComponent(jobId)).then(function(job){
      if (root._ljState !== state) return;
      state.regenChecking=false; state.regenError=''; state.regenJob=job; paintRegen(root,state);
      if (regenActive(job)) {
        state.regenTimer=setTimeout(function(){pollRegenJob(root,data,options,state,jobId);},2500);
      } else if (job.estado==='done' && state.regenRefreshOnDone===jobId && !state.editing) {
        state.regenRefreshOnDone=null;
        load(root,Object.assign({},options,{item:data.item.id,initialLayer:state.layer,cacheBust:Date.now()}));
      }
    }).catch(function(e){
      if (root._ljState !== state) return;
      state.regenChecking=false; state.regenError=e.message; paintRegen(root,state);
      if (regenActive(state.regenJob)) state.regenTimer=setTimeout(function(){pollRegenJob(root,data,options,state,jobId);},4000);
    });
  }

  function ensureRegenMonitor(root,data,options,state) {
    if (state.regenDiscovered || state.regenChecking) return;
    state.regenChecking=true; paintRegen(root,state);
    api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+'/regenerar-n3/status'+query(options)).then(function(result){
      if (root._ljState !== state) return;
      state.regenDiscovered=true; state.regenChecking=false;
      if (result.job_id) pollRegenJob(root,data,options,state,result.job_id); else paintRegen(root,state);
    }).catch(function(e){
      if (root._ljState !== state) return;
      state.regenDiscovered=true; state.regenChecking=false; state.regenError=e.message; paintRegen(root,state);
    });
  }

  function render(root, data, options, state) {
    var info=data.layers[state.layer];
    root.innerHTML='<article class="fv-web-ficha lj-web-ficha"><header class="fv-web-head"><div><p class="fv-web-kicker">Laje · ficha HI-FI</p><h2>'+esc(data.item.name)+'</h2><span>Dados SA e desenho N3 editável</span></div><div class="fv-web-nav"><button data-lj-nav="'+esc(data.item.previous||'')+'" '+(!data.item.previous?'disabled':'')+'>←</button><b>'+data.item.position+'/'+data.item.total+'</b><button data-lj-nav="'+esc(data.item.next||'')+'" '+(!data.item.next?'disabled':'')+'>→</button></div></header>'+
      '<section class="lj-fields-card"><div class="fv-web-section-title"><div><h3>'+(state.layer==='n3'?'Campos do desenho N3':'Campos da laje')+'</h3><p>'+(state.layer==='n3'?'Verticais e horizontais usadas para desenhar esta camada.':'Informações interpretadas pelo SA para este item.')+'</p></div></div><div data-lj-fields>'+(state.layer==='n3'?n3Fields(data,state.editing):saFields(data.item,state.editing))+'</div><div class="fv-web-layer-actions">'+
      (state.editing?'<button class="success" data-lj-save>Salvar alterações</button><button data-lj-cancel>Cancelar</button>':'<button data-lj-edit>Editar campos</button>')+(state.layer==='n3'&&!state.editing?'<button class="primary" data-lj-regenerate>Solicitar regeneração N3</button>':'')+'</div>'+(state.layer==='n3'?'<div class="lj-regen-monitor" data-lj-regen-monitor hidden></div>':'')+'</section>'+ 
      '<section class="fv-web-viewer-card"><div class="fv-web-layerbar">'+['sa','c1','c2','c3','n3'].map(function(k){return layerButton(k,data.layers[k],state.layer===k);}).join('')+'</div><div class="fv-web-layer-actions"><button class="success" data-lj-validate>'+(data.human_validated?'✓ Laje validada':'Validar laje')+'</button>'+(data.human_validated?'<button class="danger" data-lj-unvalidate>Desvalidar laje</button>':'')+'<button data-lj-edit-main>Editar</button><button class="danger" data-lj-delete>Excluir</button></div>'+
      '<div class="fv-web-canvas"><div class="fv-web-canvas-inner">'+(info.svg?cleanSvg(info.svg):'<div class="lv-canvas-empty">'+(info.loading?'Carregando desenho…':(state.layer==='n3'?'<strong>Modo '+(data.visual_mode==='INI'?'Ini':'Nova')+' ainda não gerado.</strong><br>Solicite a regeneração N3 neste modo para visualizar ou baixar.':'Camada sem desenho materializado.'))+'</div>')+'</div><div class="fv-web-canvas-actions"><span>'+esc(({sa:'SA',c1:'Camada 1',c2:'Camada 2',c3:'Camada 3',n3:'N3'})[state.layer])+' · '+esc(data.item.name)+'</span><div class="fv-web-canvas-buttons"><button data-lj-reset>Resetar zoom</button></div></div></div><p class="fv-web-view-help">Scroll para zoom · arraste para mover · duplo-clique reseta</p></section>'+
      '<section class="fv-qa-below"><div><strong>Opiniões humanas por camada</strong><span>Notas persistidas separadamente para SA, Camadas 1–3 e N3.</span></div><div class="lj-notes-grid">'+noteCards(data.notes||{})+'</div><button type="button" data-lj-save-notes>Salvar opiniões</button><div class="fv-qa-status" data-lj-status>Pronto.</div></section></article>';
    bind(root,data,options,state); initPanZoom(root.querySelector('.fv-web-canvas')); ensureLayer(root,data,options,state); if(state.layer==='n3'){if(window.aplicarTagModoDesenho)window.aplicarTagModoDesenho(root.querySelector('.fv-web-canvas'),data.visual_mode,{onChange:function(mode){load(root,Object.assign({},options,{initialLayer:'n3',visualMode:mode}));}});ensureRegenMonitor(root,data,options,state);}
  }

  function ensureLayer(root,data,options,state){var info=data.layers[state.layer];if(!info||!info.lazy||info.loading)return;info.loading=true;var q=query(options);q+=(q?'&':'?')+'_fresh='+encodeURIComponent(state.cacheBust);api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+'/camada/'+state.layer+q).then(function(p){info.loading=false;info.lazy=false;info.available=!!p.available;info.svg=p.svg||null;render(root,data,options,state);}).catch(function(e){info.loading=false;info.lazy=false;info.available=false;info.error=e.message;render(root,data,options,state);});}

  function collectLines(root,axis){var accumulated=0;return Array.prototype.map.call(root.querySelectorAll('[data-lj-panel-row][data-axis="'+axis+'"]'),function(row){var inputs=row.querySelectorAll('input');accumulated+=Number(inputs[0].value);return {value:Math.round(accumulated*1000)/1000,is_union:inputs[1].checked};});}
  function bind(root,data,options,state){
    root.querySelectorAll('[data-lj-layer]').forEach(function(b){b.addEventListener('click',function(){state.layer=b.dataset.ljLayer;state.editing=false;render(root,data,options,state);});});
    root.querySelectorAll('[data-lj-nav]').forEach(function(b){b.addEventListener('click',function(){if(b.dataset.ljNav)load(root,Object.assign({},options,{item:b.dataset.ljNav}));});});
    var edit=root.querySelector('[data-lj-edit]'),editMain=root.querySelector('[data-lj-edit-main]');function startEdit(){state.editing=true;render(root,data,options,state);}if(edit)edit.addEventListener('click',startEdit);if(editMain)editMain.addEventListener('click',startEdit);
    var cancel=root.querySelector('[data-lj-cancel]');if(cancel)cancel.addEventListener('click',function(){state.editing=false;render(root,data,options,state);});
    root.querySelectorAll('[data-lj-add]').forEach(function(b){b.addEventListener('click',function(){var box=root.querySelector('[data-lj-panel-list="'+b.dataset.ljAdd+'"]');var remainder=box.querySelector('[data-lj-remainder-row]');remainder.insertAdjacentHTML('beforebegin',editablePanelRow(b.dataset.ljAdd,{index:box.querySelectorAll('[data-lj-panel-row]').length+1,value:'',is_union:false}));bindRemovers(root);bindPanelInputs(root);refreshPanelEditors(root);});});bindRemovers(root);bindPanelInputs(root);refreshPanelEditors(root);
    var save=root.querySelector('[data-lj-save]');if(save)save.addEventListener('click',function(){save.disabled=true;var url='/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+(state.layer==='n3'?'/n3':'/campos')+query(options);var body;if(state.layer==='n3')body={linhas_verticais:collectLines(root,'vertical'),linhas_horizontais:collectLines(root,'horizontal')};else{var f=root.querySelector('[data-lj-fields]');body={name:f.querySelector('[name=name]').value,nivel:f.querySelector('[name=nivel]').value,height:f.querySelector('[name=height]').value};}api(url,json('PUT',body)).then(function(p){load(root,Object.assign({},options,{item:p.item||data.item.id,initialLayer:state.layer}));}).catch(function(e){save.disabled=false;alert('Falha ao salvar: '+e.message);});});
    function validation(value,button){button.disabled=true;api('/obras/'+encodeURIComponent(options.obraId)+'/n1/lajes/'+encodeURIComponent(data.item.id)+'/campo/_item_/validar'+query(options),json('POST',{validado:value})).then(function(){return load(root,Object.assign({},options,{item:data.item.id,initialLayer:state.layer}));}).catch(function(e){button.disabled=false;alert('Falha na validação: '+e.message);});}
    var val=root.querySelector('[data-lj-validate]');if(val)val.addEventListener('click',function(){validation(true,val);});var unval=root.querySelector('[data-lj-unvalidate]');if(unval)unval.addEventListener('click',function(){if(confirm('Desvalidar '+data.item.name+'?'))validation(false,unval);});
    var del=root.querySelector('[data-lj-delete]');if(del)del.addEventListener('click',function(){if(!confirm('Excluir a laje '+data.item.name+'? Um backup recuperável será criado.'))return;del.disabled=true;api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+query(options),json('DELETE',{confirmado:true})).then(function(){if(window.DrillGrade&&window.DrillGrade.refreshItems)window.DrillGrade.refreshItems();var next=data.item.next||data.item.previous;if(next)load(root,Object.assign({},options,{item:next}));else root.innerHTML='<div class="fv-web-error">Laje excluída. Não há outro item nesta lista.</div>';}).catch(function(e){del.disabled=false;alert('Falha ao excluir: '+e.message);});});
    var regen=root.querySelector('[data-lj-regenerate]');if(regen)regen.addEventListener('click',function(){if(regenActive(state.regenJob)||state.regenChecking)return;var chooser=window.escolherModoDesenho?window.escolherModoDesenho({currentMode:data.visual_mode,description:'A laje mantém a mesma geometria nos dois modos; a escolha ficará registrada para o N3 e o N5.'}):Promise.resolve('NOVA');chooser.then(function(mode){if(!mode)return;options.visualMode=mode;state.regenChecking=true;state.regenError='';paintRegen(root,state);return api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+'/regenerar-n3'+query(options),json('POST',{visual_mode:mode})).then(function(p){state.regenRefreshOnDone=p.job_id;pollRegenJob(root,data,options,state,p.job_id);});}).catch(function(e){state.regenChecking=false;state.regenError=e.message;paintRegen(root,state);});});
    var notes=root.querySelector('[data-lj-save-notes]');if(notes)notes.addEventListener('click',function(){var values={};root.querySelectorAll('[data-lj-note]').forEach(function(t){values[t.dataset.ljNote]=t.value;});notes.disabled=true;api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+'/notas'+query(options),json('PUT',{notes:values})).then(function(p){data.notes=p.notes;notes.disabled=false;root.querySelector('[data-lj-status]').textContent='Opiniões salvas.';}).catch(function(e){notes.disabled=false;root.querySelector('[data-lj-status]').textContent='Falha: '+e.message;});});
  }
  function bindPanelInputs(root){root.querySelectorAll('[data-lj-panel-row] input[type=number]').forEach(function(input){if(input.dataset.bound)return;input.dataset.bound='1';input.addEventListener('input',function(){refreshPanelEditors(root);});});}
  function bindRemovers(root){root.querySelectorAll('[data-lj-remove]').forEach(function(b){if(b.dataset.bound)return;b.dataset.bound='1';b.addEventListener('click',function(){b.closest('[data-lj-panel-row]').remove();refreshPanelEditors(root);});});}
  function load(root,options){if(root._ljState&&root._ljState.regenTimer)clearTimeout(root._ljState.regenTimer);root.innerHTML='<div class="fv-web-loading"><i></i><span>Montando ficha da laje '+esc(options.item)+'…</span></div>';var fresh=options.cacheBust||Date.now(),q=query(options);q+=(q?'&':'?')+'include_svgs=false&_fresh='+encodeURIComponent(fresh);return api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(options.item)+q).then(function(data){var state={layer:options.initialLayer||'sa',editing:false,regenJob:null,regenChecking:false,regenDiscovered:false,regenError:'',regenTimer:null,regenRefreshOnDone:null,cacheBust:fresh};root._ljState=state;render(root,data,options,state);}).catch(function(e){root._ljState=null;root.innerHTML='<div class="fv-web-error"><strong>Não foi possível montar a ficha da laje.</strong><span>'+esc(e.message)+'</span><button>Tentar novamente</button></div>';root.querySelector('button').addEventListener('click',function(){load(root,options);});});}
  window.LajeFicha={mount:load,cleanSvg:cleanSvg};
})();
