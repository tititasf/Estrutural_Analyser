(function () {
  'use strict';

  function esc(v) { return String(v == null ? '' : v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function shown(v) { return v === null || v === undefined || v === '' ? '—' : esc(v); }
  function query(o) { return o.pavimento ? '?pavimento=' + encodeURIComponent(o.pavimento) : ''; }
  function api(url, options) { return fetch(url, options).then(function (r) { return r.json().then(function (b) { if (!r.ok) throw new Error(b.detail || ('HTTP ' + r.status)); return b; }); }); }
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

  function lineRows(rows, axis, editing) {
    if (!rows.length && !editing) return '<p class="fv-web-empty">Nenhuma linha '+axis+' registrada.</p>';
    return rows.map(function(row){ return '<div class="lj-n3-line" data-lj-line="'+axis+'">'+
      (editing?'<input type="number" min="0.001" step="0.1" value="'+esc(row.value)+'" aria-label="Posição em cm"><label><input type="checkbox" '+(row.is_union?'checked':'')+'> união</label><button type="button" data-lj-remove>×</button>':'<b>'+shown(row.value)+' cm</b><span>'+(row.is_union?'União':'Divisão')+'</span>')+'</div>'; }).join('');
  }

  function n3Fields(data, editing) {
    return '<div class="lj-n3-summary"><div><span>Comprimento</span><b>'+shown(data.n3.comprimento)+' cm</b></div><div><span>Largura</span><b>'+shown(data.n3.largura)+' cm</b></div><div><span>Modo</span><b>'+shown(data.n3.modo_selecionado)+'</b></div><div><span>Fonte</span><b>'+(data.n3.has_override?'Correção humana':'Contrato do motor')+'</b></div></div>'+
      '<div class="lj-n3-columns"><section><h4>Verticais</h4><div data-lj-lines="vertical">'+lineRows(data.n3.linhas_verticais,'vertical',editing)+'</div>'+(editing?'<button type="button" data-lj-add="vertical">+ Linha vertical</button>':'')+'</section><section><h4>Horizontais</h4><div data-lj-lines="horizontal">'+lineRows(data.n3.linhas_horizontais,'horizontal',editing)+'</div>'+(editing?'<button type="button" data-lj-add="horizontal">+ Linha horizontal</button>':'')+'</section></div>';
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
        load(root,Object.assign({},options,{item:data.item.id,initialLayer:state.layer}));
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
      (state.editing?'<button class="success" data-lj-save>Salvar alterações</button><button data-lj-cancel>Cancelar</button>':'<button data-lj-edit>Editar campos</button>')+(state.layer==='n3'?'<button class="primary" data-lj-regenerate>Solicitar regeneração N3</button>':'')+'</div>'+(state.layer==='n3'?'<div class="lj-regen-monitor" data-lj-regen-monitor hidden></div>':'')+'</section>'+ 
      '<section class="fv-web-viewer-card"><div class="fv-web-layerbar">'+['sa','c1','c2','c3','n3'].map(function(k){return layerButton(k,data.layers[k],state.layer===k);}).join('')+'</div><div class="fv-web-layer-actions"><button class="success" data-lj-validate>'+(data.human_validated?'✓ Laje validada':'Validar laje')+'</button>'+(data.human_validated?'<button class="danger" data-lj-unvalidate>Desvalidar laje</button>':'')+'<button data-lj-edit-main>Editar</button><button class="danger" data-lj-delete>Excluir</button></div>'+
      '<div class="fv-web-canvas"><div class="fv-web-canvas-inner">'+(info.svg?cleanSvg(info.svg):'<div class="lv-canvas-empty">'+(info.loading?'Carregando desenho…':'Camada sem desenho materializado.')+'</div>')+'</div><div class="fv-web-canvas-actions"><span>'+esc(({sa:'SA',c1:'Camada 1',c2:'Camada 2',c3:'Camada 3',n3:'N3'})[state.layer])+' · '+esc(data.item.name)+'</span><div class="fv-web-canvas-buttons"><button data-lj-reset>Resetar zoom</button></div></div></div><p class="fv-web-view-help">Scroll para zoom · arraste para mover · duplo-clique reseta</p></section>'+
      '<section class="fv-qa-below"><div><strong>Opiniões humanas por camada</strong><span>Notas persistidas separadamente para SA, Camadas 1–3 e N3.</span></div><div class="lj-notes-grid">'+noteCards(data.notes||{})+'</div><button type="button" data-lj-save-notes>Salvar opiniões</button><div class="fv-qa-status" data-lj-status>Pronto.</div></section></article>';
    bind(root,data,options,state); initPanZoom(root.querySelector('.fv-web-canvas')); ensureLayer(root,data,options,state); if(state.layer==='n3')ensureRegenMonitor(root,data,options,state);
  }

  function ensureLayer(root,data,options,state){var info=data.layers[state.layer];if(!info||!info.lazy||info.loading)return;info.loading=true;api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+'/camada/'+state.layer+query(options)).then(function(p){info.loading=false;info.lazy=false;info.available=!!p.available;info.svg=p.svg||null;render(root,data,options,state);}).catch(function(e){info.loading=false;info.lazy=false;info.available=false;info.error=e.message;render(root,data,options,state);});}

  function collectLines(root,axis){return Array.prototype.map.call(root.querySelectorAll('[data-lj-line="'+axis+'"]'),function(row){var inputs=row.querySelectorAll('input');return {value:inputs[0].value,is_union:inputs[1].checked};});}
  function bind(root,data,options,state){
    root.querySelectorAll('[data-lj-layer]').forEach(function(b){b.addEventListener('click',function(){state.layer=b.dataset.ljLayer;state.editing=false;render(root,data,options,state);});});
    root.querySelectorAll('[data-lj-nav]').forEach(function(b){b.addEventListener('click',function(){if(b.dataset.ljNav)load(root,Object.assign({},options,{item:b.dataset.ljNav}));});});
    var edit=root.querySelector('[data-lj-edit]'),editMain=root.querySelector('[data-lj-edit-main]');function startEdit(){state.editing=true;render(root,data,options,state);}if(edit)edit.addEventListener('click',startEdit);if(editMain)editMain.addEventListener('click',startEdit);
    var cancel=root.querySelector('[data-lj-cancel]');if(cancel)cancel.addEventListener('click',function(){state.editing=false;render(root,data,options,state);});
    root.querySelectorAll('[data-lj-add]').forEach(function(b){b.addEventListener('click',function(){var box=root.querySelector('[data-lj-lines="'+b.dataset.ljAdd+'"]');var empty=box.querySelector('.fv-web-empty');if(empty)empty.remove();box.insertAdjacentHTML('beforeend','<div class="lj-n3-line" data-lj-line="'+b.dataset.ljAdd+'"><input type="number" min="0.001" step="0.1" aria-label="Posição em cm"><label><input type="checkbox"> união</label><button type="button" data-lj-remove>×</button></div>');bindRemovers(root);});});bindRemovers(root);
    var save=root.querySelector('[data-lj-save]');if(save)save.addEventListener('click',function(){save.disabled=true;var url='/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+(state.layer==='n3'?'/n3':'/campos')+query(options);var body;if(state.layer==='n3')body={linhas_verticais:collectLines(root,'vertical'),linhas_horizontais:collectLines(root,'horizontal')};else{var f=root.querySelector('[data-lj-fields]');body={name:f.querySelector('[name=name]').value,nivel:f.querySelector('[name=nivel]').value,height:f.querySelector('[name=height]').value};}api(url,json('PUT',body)).then(function(p){load(root,Object.assign({},options,{item:p.item||data.item.id,initialLayer:state.layer}));}).catch(function(e){save.disabled=false;alert('Falha ao salvar: '+e.message);});});
    function validation(value,button){button.disabled=true;api('/obras/'+encodeURIComponent(options.obraId)+'/n1/lajes/'+encodeURIComponent(data.item.id)+'/campo/_item_/validar'+query(options),json('POST',{validado:value})).then(function(){return load(root,Object.assign({},options,{item:data.item.id,initialLayer:state.layer}));}).catch(function(e){button.disabled=false;alert('Falha na validação: '+e.message);});}
    var val=root.querySelector('[data-lj-validate]');if(val)val.addEventListener('click',function(){validation(true,val);});var unval=root.querySelector('[data-lj-unvalidate]');if(unval)unval.addEventListener('click',function(){if(confirm('Desvalidar '+data.item.name+'?'))validation(false,unval);});
    var del=root.querySelector('[data-lj-delete]');if(del)del.addEventListener('click',function(){if(!confirm('Excluir a laje '+data.item.name+'? Um backup recuperável será criado.'))return;del.disabled=true;api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+query(options),json('DELETE',{confirmado:true})).then(function(){if(window.DrillGrade&&window.DrillGrade.refreshItems)window.DrillGrade.refreshItems();var next=data.item.next||data.item.previous;if(next)load(root,Object.assign({},options,{item:next}));else root.innerHTML='<div class="fv-web-error">Laje excluída. Não há outro item nesta lista.</div>';}).catch(function(e){del.disabled=false;alert('Falha ao excluir: '+e.message);});});
    var regen=root.querySelector('[data-lj-regenerate]');if(regen)regen.addEventListener('click',function(){if(regenActive(state.regenJob)||state.regenChecking)return;if(!confirm('Enfileirar a regeneração N3 de '+data.item.name+' usando as correções salvas?'))return;state.regenChecking=true;state.regenError='';paintRegen(root,state);api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+'/regenerar-n3'+query(options),{method:'POST'}).then(function(p){state.regenRefreshOnDone=p.job_id;pollRegenJob(root,data,options,state,p.job_id);}).catch(function(e){state.regenChecking=false;state.regenError=e.message;paintRegen(root,state);});});
    var notes=root.querySelector('[data-lj-save-notes]');if(notes)notes.addEventListener('click',function(){var values={};root.querySelectorAll('[data-lj-note]').forEach(function(t){values[t.dataset.ljNote]=t.value;});notes.disabled=true;api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(data.item.id)+'/notas'+query(options),json('PUT',{notes:values})).then(function(p){data.notes=p.notes;notes.disabled=false;root.querySelector('[data-lj-status]').textContent='Opiniões salvas.';}).catch(function(e){notes.disabled=false;root.querySelector('[data-lj-status]').textContent='Falha: '+e.message;});});
  }
  function bindRemovers(root){root.querySelectorAll('[data-lj-remove]').forEach(function(b){if(b.dataset.bound)return;b.dataset.bound='1';b.addEventListener('click',function(){b.closest('[data-lj-line]').remove();});});}
  function load(root,options){if(root._ljState&&root._ljState.regenTimer)clearTimeout(root._ljState.regenTimer);root.innerHTML='<div class="fv-web-loading"><i></i><span>Montando ficha da laje '+esc(options.item)+'…</span></div>';var q=query(options);q+=(q?'&':'?')+'include_svgs=false';return api('/obras/'+encodeURIComponent(options.obraId)+'/lajes/'+encodeURIComponent(options.item)+q).then(function(data){var state={layer:options.initialLayer||'sa',editing:false,regenJob:null,regenChecking:false,regenDiscovered:false,regenError:'',regenTimer:null,regenRefreshOnDone:null};root._ljState=state;render(root,data,options,state);}).catch(function(e){root._ljState=null;root.innerHTML='<div class="fv-web-error"><strong>Não foi possível montar a ficha da laje.</strong><span>'+esc(e.message)+'</span><button>Tentar novamente</button></div>';root.querySelector('button').addEventListener('click',function(){load(root,options);});});}
  window.LajeFicha={mount:load,cleanSvg:cleanSvg};
})();
