
(function(){
function _notesEl(){ return document.getElementById('fv-notes-store'); }
function _readStore(){
  var el=_notesEl();
  if(!el) return {version:1, updated_at:'', notes:{}};
  try { return JSON.parse(el.textContent||'{}') || {version:1,notes:{}}; }
  catch(e){ return {version:1, updated_at:'', notes:{}}; }
}
function _writeStore(obj){
  var el=_notesEl();
  if(!el){
    el=document.createElement('script');
    el.type='application/json'; el.id='fv-notes-store';
    document.body.appendChild(el);
  }
  obj.version=1;
  obj.updated_at=new Date().toISOString();
  el.textContent=JSON.stringify(obj, null, 2);
  return obj;
}
function collectNotes(){
  var notes={};
  document.querySelectorAll('textarea[data-atkey], [data-atkey][contenteditable]').forEach(function(el){
    var key=el.dataset.atkey; if(!key) return;
    var val=(el.value!=null?el.value:(el.innerText||'')).trim();
    if(val) notes[key]=val;
  });
  // radio groups (ex.: veredito agêntico validou/invalidou) — seleção única
  document.querySelectorAll('input[type="radio"][data-atkey]').forEach(function(el){
    var key=el.dataset.atkey; if(!key) return;
    if(el.checked) notes[key]=el.value;
  });
  document.querySelectorAll('input[type="checkbox"][data-atkey]').forEach(function(el){
    var key=el.dataset.atkey; if(!key) return;
    notes[key]=el.checked?'1':'0';
  });
  try{
    notes[_pointsKey()] = JSON.stringify((window._fvPagePoints||[]).filter(function(p){ return !p._removed; }));
  }catch(e){}
  // error marker checkbox if present
  var chk=document.getElementById('erro_check');
  var nota=document.getElementById('erro_nota');
  if(chk){
    var ek=chk.getAttribute('data-atkey')||('erro_'+ (document.title||'page'));
    notes[ek+'_flag']=chk.checked?'1':'0';
  }
  if(nota && nota.dataset && nota.dataset.atkey){
    var nv=(nota.value||'').trim(); if(nv) notes[nota.dataset.atkey]=nv;
  } else if(nota){
    var nv2=(nota.value||'').trim(); if(nv2) notes['erro_nota']=nv2;
  }
  return notes;
}
function applyNotes(notes){
  if(!notes) return;
  document.querySelectorAll('textarea[data-atkey]').forEach(function(ta){
    var key=ta.dataset.atkey;
    if(notes.hasOwnProperty(key)) ta.value=notes[key];
  });
  document.querySelectorAll('input[type="radio"][data-atkey]').forEach(function(el){
    var key=el.dataset.atkey;
    if(!notes.hasOwnProperty(key)) return;
    el.checked = String(notes[key])===String(el.value);
  });
  document.querySelectorAll('input[type="checkbox"][data-atkey]').forEach(function(el){
    var key=el.dataset.atkey;
    if(!notes.hasOwnProperty(key)) return;
    var v=notes[key];
    el.checked = (v==='1'||v===true||v==='true'||v===1);
  });
  var chk=document.getElementById('erro_check');
  if(chk){
    var fk=Object.keys(notes).filter(function(k){return k.indexOf('_flag')>0 || k.indexOf('erro')===0;})[0];
    // prefer explicit flag keys
    Object.keys(notes).forEach(function(k){
      if(k.slice(-5)==='_flag' && (notes[k]==='1'||notes[k]===true||notes[k]==='true')) chk.checked=true;
    });
  }
  var nota=document.getElementById('erro_nota');
  if(nota){
    if(nota.dataset && nota.dataset.atkey && notes[nota.dataset.atkey]!=null) nota.value=notes[nota.dataset.atkey];
    else if(notes['erro_nota']!=null) nota.value=notes['erro_nota'];
  }
  refreshAgentVerdictUI();
  if(typeof refreshTabSeals==='function') refreshTabSeals();
  if(typeof loadFvPointsFromNotes==='function') loadFvPointsFromNotes(notes);
}
/** Placeholder + hint + borda conforme veredito agêntico. */
function refreshAgentVerdictUI(root){
  root=root||document;
  root.querySelectorAll('.fv-agent-box').forEach(function(box){
    var checked=box.querySelector('input[type="radio"][data-atkey][data-role="agent-verdict"]:checked');
    var ta=box.querySelector('textarea[data-atrole="agent"]');
    var hint=box.querySelector('.fv-agent-verdict-hint');
    var v=checked?checked.value:'';
    box.classList.toggle('has-validou', v==='validou');
    box.classList.toggle('has-invalidou', v==='invalidou');
    box.classList.toggle('has-verdict', !!v);
    if(ta){
      if(v==='validou'){
        ta.placeholder='VALIDOU: descreva a compreensão do contextual e o porquê validou (segmentos, continuidade, quebras).';
      } else if(v==='invalidou'){
        ta.placeholder='INVALIDOU: descreva os erros (S# falhos, over/under-segmentation, dono provável, ajuste sugerido).';
      } else {
        ta.placeholder=ta.getAttribute('data-placeholder-default')||'Selecione validou/invalidou e escreva o comentário…';
      }
      var txt=(ta.value||'').trim();
      var needText=!!v;
      var incomplete=needText && txt.length<12;
      ta.classList.toggle('fv-need-text', incomplete);
      box.classList.toggle('fv-incomplete', incomplete||!v);
    }
    if(hint){
      if(!v) hint.textContent='Seleção única obrigatória: Agente validou OU Agente invalidou. Em ambos os casos o comentário é obrigatório.';
      else if(v==='validou') hint.textContent='✓ Validou — obrigatório: compreensão do que o N1 mostra + por que está correto.';
      else hint.textContent='✗ Invalidou — obrigatório: comentários com falhas, segmentos e hipótese de causa.';
    }
  });
}
function onAgentVerdictChange(el){
  refreshAgentVerdictUI(el&&el.closest?el.closest('.fv-agent-box')||document:document);
  saveAtenTA(el);
  if(typeof refreshTabSeals==='function') refreshTabSeals();
}
window.refreshAgentVerdictUI=refreshAgentVerdictUI;
window.onAgentVerdictChange=onAgentVerdictChange;

/** Selos dinâmicos nas abas SA/C1/C2/C3: humano (H) + agente (A). */

function _sealHtmlHuman(verdict){
  if(verdict==='validou') return '<span class="fv-seal fv-seal-h-ok" title="Humano validou este destaque">H✓</span>';
  if(verdict==='invalidou') return '<span class="fv-seal fv-seal-h-bad" title="Humano invalidou este destaque">H✗</span>';
  return '<span class="fv-seal fv-seal-empty" title="Humano ainda não julgou">H·</span>';
}
/** Agente N julga a ENTRADA (SA p/ N=1, C1 p/ N=2). C3 não tem veredito agêntico. */
function _sealHtmlAgentN(n, verdict){
  if(verdict==='validou') return '<span class="fv-seal fv-seal-a-ok" title="Agente '+n+' julgou a entrada e marcou CERTO">A'+n+' Certo</span>';
  if(verdict==='invalidou') return '<span class="fv-seal fv-seal-a-bad" title="Agente '+n+' invalidou a entrada e gerou a camada '+n+'">A'+n+' X</span>';
  return '<span class="fv-seal fv-seal-empty" title="Agente '+n+' ainda não julgou">A'+n+' ·</span>';
}
function _humanVerdictForTab(tab){
  var el=document.querySelector('input[data-role="human-hl-verdict"][data-hl-target="'+tab+'"]:checked');
  return el?el.value:'';
}
function _agentVerdictForLayer(layer){
  var box=document.querySelector('.fv-agent-box[data-layer="'+layer+'"]');
  if(box){
    if(box.getAttribute('data-no-agent-verdict')==='1') return '';
    var el=box.querySelector('input[data-role="agent-verdict"]:checked');
    if(el) return el.value;
  }
  var el2=document.querySelector('input[data-role="agent-verdict"][data-atkey*="_c'+layer+'_"]:checked');
  return el2?el2.value:'';
}
function refreshTabSeals(root){
  root=root||document;
  root.querySelectorAll('.fv-layer-toggle .fv-hl-btn[data-hl]').forEach(function(btn){
    var tab=btn.getAttribute('data-hl');
    if(!tab||['sa','c1','c2','c3'].indexOf(tab)<0) return;
    var seals=btn.querySelector('.fv-tab-seals');
    if(!seals){
      seals=document.createElement('span');
      seals.className='fv-tab-seals';
      seals.setAttribute('data-seals', tab);
      btn.appendChild(seals);
    }
    var h=_humanVerdictForTab(tab);
    var html=_sealHtmlHuman(h);
    // A1 no tab C1 (julgou SA); A2 no tab C2 (julgou C1); C3 só H
    if(tab==='c1') html+=_sealHtmlAgentN(1, _agentVerdictForLayer(1));
    else if(tab==='c2') html+=_sealHtmlAgentN(2, _agentVerdictForLayer(2));
    seals.innerHTML=html;
  });
}
function onHumanHlVerdictChange(el){
  var card=el&&el.closest?el.closest('.fv-human-hl-card,.fv-human-hl-row'):null;
  if(card){
    var v=el.value||'';
    card.classList.toggle('has-validou', v==='validou');
    card.classList.toggle('has-invalidou', v==='invalidou');
  }
  if(typeof saveAtenTA==='function') saveAtenTA(el);
  refreshTabSeals();
}
function refreshHumanHlUI(){
  document.querySelectorAll('.fv-human-hl-card,.fv-human-hl-row').forEach(function(card){
    var c=card.querySelector('input[type="radio"][data-role="human-hl-verdict"]:checked');
    var v=c?c.value:'';
    card.classList.toggle('has-validou', v==='validou');
    card.classList.toggle('has-invalidou', v==='invalidou');
  });
  refreshTabSeals();
}
window.refreshTabSeals=refreshTabSeals;
window.onHumanHlVerdictChange=onHumanHlVerdictChange;
window.refreshHumanHlUI=refreshHumanHlUI;


function _packKey(){ return 'fv_notes_pack_'+_pageStem(); }
/** API local (fv_notes_server.py) — grava .notes.json em disco mesmo vindo de file:// */
function _notesApiBase(){
  if(window.FV_NOTES_API) return String(window.FV_NOTES_API).replace(/\/$/,'');
  // default server
  return 'http://127.0.0.1:8765';
}
function _fieldValue(el){
  if(!el) return '';
  if(el.type==='checkbox') return el.checked?'1':'0';
  return (el.value!=null?el.value:(el.innerText||''));
}
/** Persist one field + full pack snapshot. Called on every input/change. */
function saveAtenTA(el){
  if(!el) { persistAllNotes(true); return; }
  var key=el.dataset&&el.dataset.atkey;
  if(!key && el.id==='erro_check') key='erro_check_flag';
  if(!key && el.id==='erro_nota') key='erro_nota';
  if(!key) { persistAllNotes(true); return; }
  var val=_fieldValue(el);
  try{
    if(el.type==='checkbox'){
      localStorage.setItem(key, val);
    } else {
      var t=String(val);
      if(t.length) localStorage.setItem(key, t); else localStorage.removeItem(key);
    }
  }catch(e){}
  persistAllNotes(true);
  try{ if(el.tagName==='TEXTAREA'){ el.setAttribute('data-saved','1'); } }catch(e){}
}
/** Snapshot all fields → localStorage + #fv-notes-store + POST API (disco) */
function persistAllNotes(quiet){
  var notes={};
  document.querySelectorAll('textarea[data-atkey]').forEach(function(ta){
    var k=ta.dataset.atkey; if(!k) return;
    notes[k]=ta.value||'';
    try{
      if(notes[k]) localStorage.setItem(k, notes[k]); else localStorage.removeItem(k);
    }catch(e){}
  });
  // merge collectNotes extras (flags + radios)
  var extra=collectNotes();
  Object.keys(extra).forEach(function(k){
    if(notes[k]==null||notes[k]==='') notes[k]=extra[k];
    // radios always win when present in extra
    if(k.indexOf('aten_fv_ctx_agent_verdict_')===0) notes[k]=extra[k];
  });
  try{
    notes[_pointsKey()] = JSON.stringify((window._fvPagePoints||[]).filter(function(p){ return !p._removed; }));
  }catch(e){}
  // also persist radio keys to localStorage
  document.querySelectorAll('input[type="radio"][data-atkey]:checked').forEach(function(el){
    try{ localStorage.setItem(el.dataset.atkey, el.value); }catch(e){}
  });
  var payload={version:1, updated_at:new Date().toISOString(), page:_pageStem(), notes:notes};
  try{ localStorage.setItem(_packKey(), JSON.stringify(payload)); }catch(e){}
  _writeStore(payload);
  // grava em disco via servidor local (funciona com file:// graças ao CORS)
  _pushNotesToServer(payload, quiet);
  refreshAgentVerdictUI();
  if(!quiet) _setSaveHint('✓ Snapshot salvo.');
  return payload;
}
var _pushTimer=null;
var _lastPushOk=null;
function _pushNotesToServer(payload, quiet){
  if(_pushTimer) clearTimeout(_pushTimer);
  _pushTimer=setTimeout(function(){
    var url=_notesApiBase()+'/api/notes/'+encodeURIComponent(_pageStem());
    try{
      fetch(url,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(payload),
        mode:'cors',
        cache:'no-store'
      }).then(function(r){
        if(!r.ok) throw new Error('HTTP '+r.status);
        _lastPushOk=true;
        _setSaveHint('✓ Salvo em disco (servidor local → '+_pageStem()+'.notes.json)');
      }).catch(function(){
        _lastPushOk=false;
        if(!quiet) _setSaveHint('⚠ Só browser (localStorage). Suba o servidor: python scripts/arete/tmp/fv_notes_server.py');
        else _setSaveHint('✓ localStorage OK · servidor offline (notas não no disco)');
      });
    }catch(e){
      _lastPushOk=false;
    }
  }, 200);
}
function loadAllAtenTA(){
  var store=_readStore();
  var embedded=(store && store.notes) ? store.notes : {};
  var live={};
  try{
    var raw=localStorage.getItem(_packKey());
    if(raw){ var pack=JSON.parse(raw); if(pack&&pack.notes) live=pack.notes; }
  }catch(e){}
  var merged=Object.assign({}, embedded, live);
  document.querySelectorAll('textarea[data-atkey]').forEach(function(ta){
    var key=ta.dataset.atkey;
    var fromLS=null;
    try{ fromLS=localStorage.getItem(key); }catch(e){}
    if(fromLS!==null) merged[key]=fromLS;
  });
  document.querySelectorAll('textarea[data-atrole="human"][data-atlegacy]').forEach(function(ta){
    var leg=ta.dataset.atlegacy;
    if((merged[ta.dataset.atkey]||'')!=='') return;
    try{
      var lv=localStorage.getItem(leg);
      if(lv) merged[ta.dataset.atkey]=lv;
    }catch(e){}
    if(!(merged[ta.dataset.atkey]||'') && embedded[leg]) merged[ta.dataset.atkey]=embedded[leg];
  });
  applyNotes(merged);
  if(typeof loadFvPointsFromNotes==='function') loadFvPointsFromNotes(merged);
  _writeStore({version:1, updated_at:new Date().toISOString(), page:_pageStem(), notes:merged});

  // 1) API disco (preferido)
  var apiUrl=_notesApiBase()+'/api/notes/'+encodeURIComponent(_pageStem());
  var loadedFromDisk=false;
  try{
    fetch(apiUrl,{cache:'no-store', mode:'cors'}).then(function(r){
      if(!r.ok) throw new Error('no api');
      return r.json();
    }).then(function(j){
      var n=(j&&j.notes)||j;
      if(typeof n!=='object') return;
      // disco vence se tiver conteúdo; senão mantém LS
      var cur=collectNotes();
      var hasDisk=Object.keys(n).some(function(k){ return (n[k]||'').toString().trim(); });
      if(hasDisk){
        // merge: disk base, then non-empty live typing
        var m2=Object.assign({}, n);
        Object.keys(cur).forEach(function(k){ if((cur[k]||'').trim()) m2[k]=cur[k]; });
        applyNotes(m2);
        try{ localStorage.setItem(_packKey(), JSON.stringify({version:1,page:_pageStem(),notes:m2,updated_at:new Date().toISOString()})); }catch(e){}
        _writeStore({version:1, page:_pageStem(), notes:m2, updated_at:new Date().toISOString()});
        loadedFromDisk=true;
        _setSaveHint('✓ Notas carregadas do disco (servidor local). Autosave ativo.');
      } else {
        _setSaveHint('✓ Autosave ativo (servidor local online).');
      }
    }).catch(function(){
      // 2) relative .notes.json (http serve only)
      var side=_pageStem()+'.notes.json';
      fetch(side,{cache:'no-store'}).then(function(r){
        if(!r.ok) return null; return r.json();
      }).then(function(j){
        if(!j) {
          _setSaveHint('⚠ Abrindo em file:// sem servidor: use python scripts/arete/tmp/fv_notes_server.py');
          return;
        }
        var n=j.notes||j;
        if(typeof n==='object'){
          var cur=collectNotes();
          var m2=Object.assign({}, n);
          Object.keys(cur).forEach(function(k){ if((cur[k]||'').trim()) m2[k]=cur[k]; });
          applyNotes(m2);
          persistAllNotes(true);
        }
      }).catch(function(){
        _setSaveHint('⚠ Sem servidor de notas. Rode: python scripts/arete/tmp/fv_notes_server.py');
      });
    });
  }catch(e){}
}
var _autosaveTimer=null;
function scheduleAutosave(el){
  if(_autosaveTimer) clearTimeout(_autosaveTimer);
  _autosaveTimer=setTimeout(function(){ saveAtenTA(el||null); }, 150);
}
function bindAutosaveFields(){
  var nodes=[].slice.call(document.querySelectorAll(
    'textarea[data-atkey], input[data-atkey], #erro_nota, #erro_check'
  ));
  nodes.forEach(function(el){
    if(el.dataset.fvAuto==='1') return;
    el.dataset.fvAuto='1';
    el.addEventListener('input', function(){
      if(el.matches && el.matches('textarea[data-atrole="agent"]')) refreshAgentVerdictUI();
      scheduleAutosave(el);
    });
    el.addEventListener('change', function(){
      if(el.type==='radio' && el.dataset.role==='agent-verdict') onAgentVerdictChange(el);
      else saveAtenTA(el);
    });
    el.addEventListener('blur', function(){ saveAtenTA(el); });
    el.addEventListener('keyup', function(){
      if(el.matches && el.matches('textarea[data-atrole="agent"]')) refreshAgentVerdictUI();
      scheduleAutosave(el);
    });
  });
  window.addEventListener('beforeunload', function(){ persistAllNotes(true); });
  window.addEventListener('pagehide', function(){ persistAllNotes(true); });
  document.addEventListener('visibilitychange', function(){
    if(document.visibilityState==='hidden') persistAllNotes(true);
  });
  refreshAgentVerdictUI();
  if(typeof refreshHumanHlUI==='function') refreshHumanHlUI();
  if(typeof refreshTabSeals==='function') refreshTabSeals();
}
function _setSaveHint(msg){
  var h=document.getElementById('fv-notes-hint');
  if(h) h.textContent=msg||'';
}
function _download(filename, text, mime){
  var blob=new Blob([text],{type:mime||'text/plain;charset=utf-8'});
  var a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=filename;
  document.body.appendChild(a); a.click();
  setTimeout(function(){ URL.revokeObjectURL(a.href); a.remove(); }, 800);
}
function _pageStem(){
  return (location.pathname.split('/').pop()||'ficha.html').replace(/\.html?$/i,'')||'ficha';
}
/** Bake current notes into DOM + download HTML and .notes.json for agent access. */
function saveNotesToHtmlFile(){
  var notes=collectNotes();
  var payload={version:1, updated_at:new Date().toISOString(), page:_pageStem(), notes:notes};
  _writeStore(payload);
  // bake textarea contents into attributes so static HTML keeps values
  document.querySelectorAll('textarea[data-atkey]').forEach(function(ta){
    ta.textContent=ta.value||'';
    ta.defaultValue=ta.value||'';
  });
  var stem=_pageStem();
  _download(stem+'.notes.json', JSON.stringify(payload,null,2), 'application/json');
  // full HTML snapshot (no literal backslash-n — breaks script if expanded)
  var html='<!DOCTYPE html>'+document.documentElement.outerHTML;
  _download(stem+'.html', html, 'text/html;charset=utf-8');
  _setSaveHint('Baixados: '+stem+'.notes.json e '+stem+'.html — mova/substitua na pasta fundos_viga/ para o agente ler.');
  try{ localStorage.setItem('fv_notes_last_save_'+stem, payload.updated_at); }catch(e){}
  return payload;
}
function exportAnotacoes(){
  // compat: same as save, plus fill hidden pre
  var payload=saveNotesToHtmlFile();
  var el=document.getElementById('_aten_export');
  if(el) el.textContent=JSON.stringify(payload,null,2);
}
window.saveAtenTA=saveAtenTA;
window.loadAllAtenTA=loadAllAtenTA;
window.collectNotes=collectNotes;
window.persistAllNotes=persistAllNotes;
window.saveNotesToHtmlFile=saveNotesToHtmlFile;
window.exportAnotacoes=exportAnotacoes;
window.bindAutosaveFields=bindAutosaveFields;

function _activeSvg(outer){
  // prefer visible layer svg; fallback first svg
  var vis=outer.querySelector('.fv-layer:not(.fv-layer-hidden) svg, .fv-layer[data-visible="1"] svg');
  if(vis) return vis;
  var all=outer.querySelectorAll('svg');
  for(var i=0;i<all.length;i++){
    var el=all[i];
    var layer=el.closest('.fv-layer');
    if(layer && layer.classList.contains('fv-layer-hidden')) continue;
    if(el.offsetParent!==null || !layer) return el;
  }
  return outer.querySelector('svg');
}
function _allSyncSvgs(outer){
  // SA + agent HI-FI (fv-sync-vb). N3 tem viewBox próprio — nunca sincronizar.
  var list=[].slice.call(outer.querySelectorAll('.fv-layer-sa svg, svg.fv-sync-vb, .fv-layer-agent svg.fv-sync-vb'));
  return list.filter(function(s,i,a){
    if(s.closest && s.closest('.fv-layer-n3')) return false;
    if(s.classList.contains('fv-n3-svg')) return false;
    if(s.closest && s.closest('.fv-layer-agent') && !s.classList.contains('fv-sync-vb')) return false;
    return a.indexOf(s)===i;
  });
}
function _prepAgentSvg(s){
  if(!s) return;
  if(s.closest && s.closest('.fv-layer-n3')){ _prepN3Svg(s); return; }
  if(!s.getAttribute('viewBox')) s.setAttribute('viewBox','0 0 1152 288');
  var vb=s.getAttribute('viewBox')||'';
  // HI-FI matplotlib (0 0 W H) = mesmo espaco do SA -> sync pan/zoom
  var isHifi = s.classList.contains('fv-sync-vb') || /^0 +0 +/.test(vb);
  if(!s.dataset.homeVb) s.dataset.homeVb=vb;
  s.setAttribute('preserveAspectRatio','xMidYMid meet');
  s.classList.add('img-fv-hifi','fv-agent-svg');
  if(isHifi){ s.classList.add('fv-sync-vb'); s.dataset.hifiAgent='1'; }
  else { s.classList.remove('fv-sync-vb'); s.dataset.hifiAgent='0'; }
  s.removeAttribute('width'); s.removeAttribute('height');
  s.style.width='100%'; s.style.height='100%';
  s.style.maxWidth='100%'; s.style.maxHeight='100%';
  s.style.display='block'; s.style.background='#0a0a0a';
}
function _prepN3Svg(s){
  if(!s) return;
  s.classList.remove('fv-sync-vb');
  s.classList.add('img-fv-hifi','fv-n3-svg');
  s.setAttribute('preserveAspectRatio','xMidYMid meet');
  s.querySelectorAll('[clip-path]').forEach(function(el){ el.removeAttribute('clip-path'); });
  if(!s.getAttribute('viewBox')) s.setAttribute('viewBox','0 0 1200 200');
  if(!s.dataset.homeVb) s.dataset.homeVb=s.getAttribute('viewBox')||'';
  s.removeAttribute('width'); s.removeAttribute('height');
  s.style.width='100%'; s.style.height='100%';
  s.style.maxWidth='100%'; s.style.maxHeight='100%';
  s.style.display='block'; s.style.background='#0a0a0a';
}
function _readVb(svg){
  if(!svg) return {x:0,y:0,w:100,h:100};
  var raw=svg.dataset.homeVb||svg.getAttribute('viewBox')||'0 0 100 100';
  var p=String(raw).replace(/,/g,' ').trim().split(/ +/).map(parseFloat);
  if(p.length<4||p.some(function(n){return !isFinite(n);})) return {x:0,y:0,w:100,h:100};
  return {x:p[0],y:p[1],w:p[2],h:p[3]};
}
function _zoomState(home, z0){
  z0=(typeof z0==='number')?z0:0.5;
  return {
    x:home.x+home.w*(1-z0)/2,
    y:home.y+home.h*(1-z0)/2,
    w:home.w*z0,
    h:home.h*z0
  };
}
function initPanZoom(cid){
  var outer=document.getElementById(cid);
  if(!outer||outer.dataset.pzInit==='1') return;
  outer.dataset.pzInit='1';
  var svg=_activeSvg(outer);
  if(!svg) return;
  function prep(s){
    if(!s.getAttribute('viewBox')) s.setAttribute('viewBox','0 0 1152 288');
    s.setAttribute('preserveAspectRatio','xMidYMid meet');
    s.classList.add('fv-sync-vb');
    s.style.width='100%'; s.style.height='100%';
    s.style.display='block'; s.style.background='#0a0a0a';
  }
  prep(svg);
  _allSyncSvgs(outer).forEach(prep);
  outer.querySelectorAll('.fv-layer-agent svg').forEach(_prepAgentSvg);

  var home=_readVb(svg);
  if(!svg.dataset.homeVb) svg.dataset.homeVb=home.x+' '+home.y+' '+home.w+' '+home.h;
  // Zoom inicial 2× mais próximo (metade do viewBox, centrado no home)
  var state=_zoomState(home, 0.5);
  outer.dataset.pzLayer='sa';
  var drag=false,lx=0,ly=0;
  outer._dragMoved=0;

  function applyAgentRelative(){
    var zx=state.w/home.w, zy=state.h/home.h;
    var rx=(state.x-home.x)/home.w;
    var ry=(state.y-home.y)/home.h;
    outer.querySelectorAll('.fv-layer-agent svg').forEach(function(ag){
      if(ag.dataset.hifiAgent==='1'||ag.classList.contains('fv-sync-vb')) return;
      _prepAgentSvg(ag);
      var _vbRaw=(ag.dataset.homeVb||ag.getAttribute('viewBox')||'0 0 100 100');
      var parts=_vbRaw.replace(/,/g,' ').trim().split(/ +/).map(parseFloat);
      if(parts.length<4||parts.some(function(n){return !isFinite(n);})) return;
      var hx=parts[0], hy=parts[1], hw=parts[2], hh=parts[3];
      var aw=hw*zx, ah=hh*zy;
      var ax=hx+rx*hw, ay=hy+ry*hh;
      ag.setAttribute('viewBox', ax+' '+ay+' '+aw+' '+ah);
    });
  }
  function apply(){
    var vb=state.x+' '+state.y+' '+state.w+' '+state.h;
    if(outer.dataset.pzLayer==='n3'){
      var n3=outer.querySelector('.fv-layer-n3 svg');
      if(n3) n3.setAttribute('viewBox', vb);
      if(typeof renderFvDots==='function') renderFvDots(outer);
      return;
    }
    _allSyncSvgs(outer).forEach(function(s){ s.setAttribute('viewBox', vb); });
    applyAgentRelative();
    if(typeof renderFvDots==='function') renderFvDots(outer);
  }
  function reset(){ state={x:home.x,y:home.y,w:home.w,h:home.h}; apply(); }
  outer._pzReset=reset;
  outer._pzApply=apply;
  outer._prepAgentSvg=_prepAgentSvg;
  outer._pzSwitchLayer=function(mode){
    var next=(mode==='n3')?'n3':'sa';
    outer.dataset.pzLayer=next;
    if(next==='n3'){
      var n3=outer.querySelector('.fv-layer-n3 svg');
      if(!n3) return;
      _prepN3Svg(n3);
      home=_readVb(n3);
      outer.style.height='320px';
      // N3 é faixa de painéis: mostrar todos lado a lado
      state={x:home.x,y:home.y,w:home.w,h:home.h};
      apply();
      return;
    }
    outer.style.height='560px';
    var sa=outer.querySelector('.fv-layer-sa svg')||svg;
    home=_readVb(sa);
    state=_zoomState(home, 0.5);
    apply();
  };
  outer._pzFocusBox=function(box){
    if(!box||!isFinite(box.w)||box.w<=0) return;
    var pad=Math.max(box.w, box.h)*0.12;
    var x=box.x-pad, y=box.y-pad, w=box.w+2*pad, h=box.h+2*pad;
    if(outer.dataset.pzLayer==='n3'){
      state={x:x,y:y,w:Math.max(w,1),h:Math.max(h,1)};
    } else {
      var side=Math.max(w,h);
      x=x-(side-w)/2; y=y-(side-h)/2;
      state={x:x,y:y,w:side,h:side};
    }
    apply();
  };

  function clientToSvg(cx,cy){
    var act=_activeSvg(outer)||svg;
    var pt=act.createSVGPoint(); pt.x=cx; pt.y=cy;
    var ctm=act.getScreenCTM();
    if(!ctm) return {x:state.x+state.w/2,y:state.y+state.h/2};
    var p=pt.matrixTransform(ctm.inverse());
    return {x:p.x,y:p.y};
  }

  outer.addEventListener('wheel',function(e){
    e.preventDefault();
    var factor=e.deltaY<0?0.88:1.14;
    var nextW=state.w*factor, nextH=state.h*factor;
    var minW=home.w*0.03, maxW=home.w*4.5;
    if(nextW<minW){factor=minW/state.w; nextW=minW; nextH=state.h*factor;}
    if(nextW>maxW){factor=maxW/state.w; nextW=maxW; nextH=state.h*factor;}
    var p=clientToSvg(e.clientX,e.clientY);
    state.x=p.x-(p.x-state.x)*(nextW/state.w);
    state.y=p.y-(p.y-state.y)*(nextH/state.h);
    state.w=nextW; state.h=nextH; apply();
  },{passive:false});

  outer.addEventListener('mousedown',function(e){
    if(e.button!==0) return;
    if(e.target&&e.target.closest&&e.target.closest('button,textarea,a,input,.fv-layer-toggle,.fv-seg-subtabs')) return;
    drag=true; lx=e.clientX; ly=e.clientY; outer._dragMoved=0;
    outer.style.cursor='grabbing'; e.preventDefault();
  });
  window.addEventListener('mousemove',function(e){
    if(!drag) return;
    var act=_activeSvg(outer)||svg;
    var ctm=act.getScreenCTM(); if(!ctm) return;
    var inv=ctm.inverse();
    var p0=act.createSVGPoint(); p0.x=lx; p0.y=ly;
    var p1=act.createSVGPoint(); p1.x=e.clientX; p1.y=e.clientY;
    var a=p0.matrixTransform(inv), b=p1.matrixTransform(inv);
    state.x-=(b.x-a.x); state.y-=(b.y-a.y);
    outer._dragMoved+=(Math.abs(e.clientX-lx)+Math.abs(e.clientY-ly));
    lx=e.clientX; ly=e.clientY; apply();
  });
  window.addEventListener('mouseup',function(){
    if(!drag) return; drag=false; outer.style.cursor='grab';
  });
  outer.addEventListener('dblclick',function(e){
    if(e.target&&e.target.closest&&e.target.closest('button,textarea')) return;
    reset();
  });
  outer.addEventListener('click',function(e){
    if(typeof onFvPointClick==='function') onFvPointClick(outer, e);
  });
  apply();
}
function resetZoom(cid){
  var outer=document.getElementById(cid);
  if(outer&&typeof outer._pzReset==='function'){ outer._pzReset(); }
}
function _syncSaGhostChrome(root, mode){
  root=root||document;
  var outer=(root.querySelector&&root.querySelector('#fvctx-main [data-panzoom]'))
    ||(root.querySelector&&root.querySelector('[data-panzoom]'));
  if(!outer) return;
  var btn=outer.querySelector('.fv-sa-ghost-btn');
  if(!btn) return;
  btn.style.display=(mode==='sa'||!mode)?'':'none';
}
function _normCssColor(v){
  v=(v||'').toString().trim().toLowerCase();
  if(!v || v==='none' || v==='transparent') return '';
  var m=v.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  if(m){
    return '#'+[m[1],m[2],m[3]].map(function(x){
      var h=Number(x).toString(16);
      return h.length<2?'0'+h:h;
    }).join('');
  }
  if(v.charAt(0)==='#' && v.length===4)
    return '#'+v.charAt(1)+v.charAt(1)+v.charAt(2)+v.charAt(2)+v.charAt(3)+v.charAt(3);
  if(v.charAt(0)==='#' && v.length>=7) return v.slice(0,7);
  return v;
}
function _markSaHl(svg){
  if(!svg || svg.getAttribute('data-fv-hl-marked')==='1') return;
  svg.setAttribute('data-fv-hl-marked','1');
  var FACE={'#e53935':1,'#ec407a':1};
  var EDGE={'#ff1744':1,'#f8bbd0':1};
  var TAG={'#b71c1c':1,'#ad1457':1};
  [].slice.call(svg.querySelectorAll('path,polygon,rect')).forEach(function(p){
    if(p.getAttribute('data-fv-hl')) return;
    var st=((p.getAttribute('style')||'')+' '+(p.getAttribute('fill')||'')+' '+(p.getAttribute('stroke')||'')).toLowerCase();
    var fill='', stroke='', sw=0, op=1, hasOp=false;
    var mf=st.match(/fill:\s*([^;]+)/);
    var ms=st.match(/stroke:\s*([^;]+)/);
    var mw=st.match(/stroke-width:\s*([^;]+)/);
    var mo=st.match(/(?:^|;|\s)opacity:\s*([^;]+)/);
    if(mf) fill=_normCssColor(mf[1]);
    if(ms) stroke=_normCssColor(ms[1]);
    if(mw) sw=parseFloat(mw[1])||0;
    if(mo){ op=parseFloat(mo[1]); hasOp=true; }
    if(!fill){
      try{
        var cs=window.getComputedStyle(p);
        fill=_normCssColor(cs.fill);
        if(!stroke) stroke=_normCssColor(cs.stroke);
        if(!sw) sw=parseFloat(String(cs.strokeWidth))||0;
        if(!hasOp) op=parseFloat(cs.opacity);
      }catch(e){}
    }
    if(TAG[fill]){ p.setAttribute('data-fv-hl','tag'); return; }
    if(FACE[fill] && (op<0.9 || st.indexOf('opacity: 0.38')>=0)){
      p.setAttribute('data-fv-hl','face'); return;
    }
    var fillNone=!fill || /fill:\s*none/.test(st);
    if(fillNone && EDGE[stroke] && sw>=0.35 && sw<=0.62){
      p.setAttribute('data-fv-hl','edge');
    }
  });
}
function _applySaGhostVisual(layer, on){
  var svg=layer && layer.querySelector('svg');
  if(!svg) return;
  _markSaHl(svg);
  [].slice.call(svg.querySelectorAll('[data-fv-hl="face"]')).forEach(function(p){
    if(on){
      if(p.getAttribute('data-fv-prev-style')==null)
        p.setAttribute('data-fv-prev-style', p.getAttribute('style')||'');
      p.style.setProperty('fill','none','important');
      p.style.setProperty('fill-opacity','0','important');
      p.style.setProperty('opacity','0','important');
    } else {
      var prev=p.getAttribute('data-fv-prev-style');
      if(prev!=null) p.setAttribute('style', prev);
    }
  });
  [].slice.call(svg.querySelectorAll('[data-fv-hl="edge"]')).forEach(function(p){
    if(on){
      if(p.getAttribute('data-fv-prev-style')==null)
        p.setAttribute('data-fv-prev-style', p.getAttribute('style')||'');
      p.style.setProperty('stroke-opacity','0.38','important');
      p.style.setProperty('opacity','0.45','important');
    } else {
      var prev=p.getAttribute('data-fv-prev-style');
      if(prev!=null) p.setAttribute('style', prev);
    }
  });
}
function toggleSaGhost(btn){
  btn=btn||document.querySelector('.fv-sa-ghost-btn');
  var outer=btn&&btn.closest('[data-panzoom]');
  var layer=outer&&outer.querySelector('.fv-layer-sa');
  if(!layer) return;
  var on=layer.classList.toggle('fv-sa-ghost');
  _applySaGhostVisual(layer, on);
  if(btn){
    btn.setAttribute('data-sa-ghost', on?'1':'0');
    btn.classList.toggle('active', on);
  }
  try{ localStorage.setItem('fv_sa_ghost_'+_pageStem(), on?'1':'0'); }catch(e){}
}
var pointColors=['#f87171','#60a5fa','#4ade80','#fbbf24','#c084fc','#f472b6','#2dd4bf','#fb923c'];
window._fvPagePoints=window._fvPagePoints||[];
function _pointsKey(){ return 'aten_fv_points_'+_pageStem(); }
function _cssEsc(s){
  if(window.CSS && CSS.escape) return CSS.escape(String(s));
  return String(s);
}
function _fvPtSide(outer){
  if(!outer) return 'sa';
  if(outer.querySelector && outer.querySelector('[data-ctx-layers]')){
    var root=outer.closest('#fvctx-main')||document;
    var b=root.querySelector('.fv-hl-btn.active');
    return (b && b.getAttribute('data-hl')) || 'sa';
  }
  var id=outer.id||'local';
  var m=id.match(/_s([^_]+)$/i);
  if(m) return 'S'+m[1];
  return id.replace(/^fvlocal_[^_]+_/,'')||'local';
}
function _isBgPatch(el){
  var st=((el.getAttribute('style')||'')+' '+(el.getAttribute('fill')||'')).toLowerCase();
  if(st.indexOf('#0a0a0a')>=0 && st.indexOf('stroke')<0) return true;
  if(st.indexOf('#212830')>=0 && st.indexOf('stroke')<0) return true;
  return false;
}
function _ensurePtEls(svg){
  if(!svg || svg.getAttribute('data-pt-els')==='1') return;
  svg.setAttribute('data-pt-els','1');
  var i=0;
  var nodes=[].slice.call(svg.querySelectorAll('path,line,polygon,polyline,circle,ellipse,text,rect'));
  nodes.forEach(function(el){
    if(el.closest && el.closest('defs')) return;
    if(el.classList.contains('fv-pt-hit')) return;
    if(_isBgPatch(el)) return;
    i+=1;
    if(!el.id){
      var svgId=svg.getAttribute('id')||'svg';
      el.setAttribute('id', svgId+'-pt-'+i);
    }
    el.classList.add('fv-pt-el');
    var tag=el.tagName.toLowerCase();
    if(!el.getAttribute('data-type')){
      var hl=el.getAttribute('data-fv-hl')||'';
      var typ=tag==='text'?'TEXT':(hl==='face'?'HL-FACE':(hl==='edge'?'HL-EDGE':(hl==='tag'?'TAG':tag.toUpperCase())));
      el.setAttribute('data-type', typ);
    }
    if(!el.getAttribute('data-layer')){
      el.setAttribute('data-layer', el.getAttribute('data-fv-hl')||el.getAttribute('data-n3-seg')||'CAD');
    }
    if(tag==='text' && !el.getAttribute('data-text')){
      el.setAttribute('data-text', (el.textContent||'').trim().slice(0,80));
    }
    var st=(el.getAttribute('style')||'').toLowerCase();
    if((tag==='path'||tag==='line'||tag==='polyline') && /fill:\s*none/.test(st)){
      try{
        var hit=el.cloneNode(true);
        hit.removeAttribute('id');
        hit.classList.remove('fv-pt-el');
        hit.classList.add('fv-pt-hit');
        hit.style.stroke='transparent';
        hit.style.fill='none';
        hit.style.strokeWidth='12';
        hit.style.pointerEvents='stroke';
        hit.setAttribute('data-pt-for', el.id);
        if(el.parentNode) el.parentNode.insertBefore(hit, el);
      }catch(err){}
    }
  });
}
function _visibleSvg(outer){
  if(!outer) return null;
  var layer=outer.querySelector('.fv-layer:not(.fv-layer-hidden)');
  if(layer){
    var s=layer.querySelector('svg');
    if(s) return s;
  }
  return outer.querySelector('svg');
}
function markPicked(target){
  if(!target||target.classList.contains('fv-pt-picked')||target.classList.contains('dxf-picked')) return;
  target.classList.add('fv-pt-picked');
  target.classList.add('dxf-picked');
  if(target.parentNode) target.parentNode.prepend(target);
}
function unmarkPicked(outer, elementId){
  if(!elementId||!outer) return;
  outer.querySelectorAll('svg').forEach(function(svg){
    var el=null;
    try{ el=svg.querySelector('#'+_cssEsc(elementId)); }catch(e){}
    if(el){
      el.classList.remove('fv-pt-picked');
      el.classList.remove('dxf-picked');
    }
  });
}
function renderFvDots(outer){
  if(!outer) return;
  outer.querySelectorAll('.click-dot,.click-label').forEach(function(el){ el.remove(); });
  var side=_fvPtSide(outer);
  var wRect=outer.getBoundingClientRect();
  var vi=-1;
  (window._fvPagePoints||[]).forEach(function(p){
    if(p._removed) return;
    vi+=1;
    if(p.viewer && outer.id && p.viewer!==outer.id) return;
    if(p.side && p.side!==side) return;
    var c=pointColors[vi%pointColors.length];
    var x=p.x, y=p.y;
    var el=null;
    if(p.element && p.element.id){
      try{ el=outer.querySelector('#'+_cssEsc(p.element.id)); }catch(e){}
    }
    if(el) markPicked(el);
    if(el && wRect.width>0 && wRect.height>0){
      var r=el.getBoundingClientRect();
      x=(r.left+r.width/2-wRect.left)/wRect.width;
      y=(r.top+r.height/2-wRect.top)/wRect.height;
    }
    if(x<-0.05||x>1.05||y<-0.05||y>1.05) return;
    var dot=document.createElement('div');
    dot.className='click-dot';
    dot.style.left=(x*100)+'%'; dot.style.top=(y*100)+'%'; dot.style.background=c;
    outer.appendChild(dot);
    var lb=document.createElement('div');
    lb.className='click-label';
    lb.style.left=(x*100)+'%'; lb.style.top=(y*100)+'%'; lb.style.color=c;
    lb.textContent=String(vi+1);
    outer.appendChild(lb);
  });
}
function pointRefText(p, i){
  var parts=[_pageStem(), 'P'+(i+1)+' '+(p.side||'')];
  if(p.element){
    var el=p.element;
    var s=(el.type||'?')+'·'+(el.layer||'CAD');
    if(el.pattern) s+=' pattern='+el.pattern;
    if(el.handle) s+=' handle='+el.handle;
    if(el.text) s+=' texto="'+el.text+'"';
    if(el.length_cm) s+=' '+el.length_cm+'cm';
    parts.push(s);
  }
  if(p.note) parts.push('nota: "'+p.note+'"');
  return parts.join(' | ');
}
function _copyText(text, btn, idle){
  var done=function(){ if(!btn) return; btn.textContent='✓'; setTimeout(function(){ btn.textContent=idle; }, 1200); };
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done).catch(done);
  } else {
    var ta=document.createElement('textarea');
    ta.value=text; ta.style.position='fixed'; ta.style.opacity='0';
    document.body.appendChild(ta); ta.select();
    try{ document.execCommand('copy'); }catch(e){}
    document.body.removeChild(ta); done();
  }
}
function renderFvPointsList(){
  var list=document.querySelector('.fv-points-list');
  if(!list) return;
  list.innerHTML='';
  var copyAllBtn=document.querySelector('.copy-all-points');
  var active=(window._fvPagePoints||[]).filter(function(p){ return !p._removed; });
  if(copyAllBtn) copyAllBtn.hidden=!active.length;
  var vi=-1;
  (window._fvPagePoints||[]).forEach(function(p, i){
    if(p._removed){
      var row=document.createElement('div');
      row.className='point-row point-row-removed';
      var lbl=document.createElement('span');
      lbl.style.cssText='flex:1;color:#94a3b8;font-style:italic;font-size:11px;';
      lbl.textContent='ponto removido';
      var undo=document.createElement('button');
      undo.type='button'; undo.textContent='↺ desfazer';
      undo.addEventListener('click', function(){
        delete p._removed;
        document.querySelectorAll('[data-panzoom]').forEach(function(w){
          if(p.element&&p.element.id){
            var el=null;
            try{ el=w.querySelector('#'+_cssEsc(p.element.id)); }catch(e){}
            if(el) markPicked(el);
          }
          renderFvDots(w);
        });
        renderFvPointsList(); saveFvPoints();
      });
      row.appendChild(lbl); row.appendChild(undo);
      list.appendChild(row);
      return;
    }
    vi+=1;
    var c=pointColors[vi%pointColors.length];
    var row=document.createElement('div');
    row.className='point-row';
    var lbl=document.createElement('span');
    lbl.style.cssText='min-width:70px;color:'+c+';font-family:monospace;';
    lbl.textContent='P'+(vi+1)+' '+String(p.side||'').toUpperCase();
    var inp=document.createElement('input');
    inp.type='text'; inp.placeholder='nota sobre este ponto'; inp.value=p.note||'';
    inp.addEventListener('input', function(){ p.note=inp.value; saveFvPoints(); });
    var cp=document.createElement('button');
    cp.type='button'; cp.textContent='📋'; cp.title='copiar referência deste ponto';
    (function(pt, idx){
      cp.addEventListener('click', function(){ _copyText(pointRefText(pt, idx), cp, '📋'); });
    })(p, vi);
    var rm=document.createElement('button');
    rm.type='button'; rm.textContent='×';
    rm.addEventListener('click', function(){
      document.querySelectorAll('[data-panzoom]').forEach(function(w){
        unmarkPicked(w, p.element && p.element.id);
        renderFvDots(w);
      });
      p._removed=true; renderFvPointsList(); saveFvPoints();
    });
    row.appendChild(lbl);
    if(p.element){
      var tag=document.createElement('span');
      tag.className='elem-tag';
      tag.title='handle='+(p.element.handle||'')+(p.element.pattern?' pattern='+p.element.pattern:'')+(p.element.text?' texto="'+p.element.text+'"':'')+(p.element.length_cm?' '+p.element.length_cm+'cm':'');
      tag.textContent=(p.element.type||'?')+'·'+(p.element.layer||'CAD');
      row.appendChild(tag);
    }
    row.appendChild(inp); row.appendChild(cp); row.appendChild(rm);
    list.appendChild(row);
  });
}
function saveFvPoints(){
  var json=JSON.stringify((window._fvPagePoints||[]).filter(function(p){ return !p._removed; }));
  try{ localStorage.setItem(_pointsKey(), json); }catch(e){}
  if(typeof persistAllNotes==='function') persistAllNotes(true);
}
function loadFvPointsFromNotes(notes){
  var raw=notes && notes[_pointsKey()];
  if(raw==null || raw===''){
    try{ raw=localStorage.getItem(_pointsKey()); }catch(e){}
  }
  if(raw==null || raw===''){
    if(!Array.isArray(window._fvPagePoints)) window._fvPagePoints=[];
  } else {
    try{ window._fvPagePoints = JSON.parse(raw); }
    catch(e){ window._fvPagePoints=[]; }
    if(!Array.isArray(window._fvPagePoints)) window._fvPagePoints=[];
  }
  document.querySelectorAll('[data-panzoom]').forEach(function(w){ renderFvDots(w); });
  renderFvPointsList();
}
function toggleFvPointMode(btn){
  btn=btn||document.querySelector('.fv-pt-btn');
  var outer=btn && btn.closest('[data-panzoom]');
  if(!outer) return;
  var on=btn.classList.toggle('active');
  btn.setAttribute('data-pt', on?'1':'0');
  outer.classList.toggle('fv-pt-mode', on);
  if(on){
    var svg=_visibleSvg(outer);
    if(svg) _ensurePtEls(svg);
  }
}
function onFvPointClick(outer, e){
  if(!outer || !outer.classList.contains('fv-pt-mode')) return;
  if(e.target && e.target.closest && e.target.closest('button,textarea,a,input')) return;
  if((outer._dragMoved||0)>4) return;
  var target=e.target.closest && e.target.closest('.fv-pt-el, .dxf-el');
  if(!target){
    var hit=e.target.closest && e.target.closest('.fv-pt-hit');
    if(hit && hit.getAttribute('data-pt-for')){
      try{ target=outer.querySelector('#'+_cssEsc(hit.getAttribute('data-pt-for'))); }catch(err){ target=null; }
    }
  }
  if(!target) return;
  if(target.classList.contains('fv-pt-picked')||target.classList.contains('dxf-picked')) return;
  var rect=outer.getBoundingClientRect();
  var tr=target.getBoundingClientRect();
  var x=(tr.left+tr.width/2-rect.left)/rect.width;
  var y=(tr.top+tr.height/2-rect.top)/rect.height;
  markPicked(target);
  window._fvPagePoints=window._fvPagePoints||[];
  window._fvPagePoints.push({
    viewer: outer.id||'',
    side: _fvPtSide(outer),
    x:x, y:y, note:'',
    element:{
      id: target.id||'',
      layer: target.getAttribute('data-layer')||'',
      type: target.getAttribute('data-type')||target.tagName,
      handle: target.getAttribute('data-handle')||'',
      text: target.getAttribute('data-text')||((target.tagName.toLowerCase()==='text'?(target.textContent||'').trim():'')),
      length_cm: target.getAttribute('data-length-cm')||'',
      pattern: target.getAttribute('data-pattern')||''
    }
  });
  renderFvDots(outer);
  renderFvPointsList();
  saveFvPoints();
  var tab=document.querySelector('.fv-human-tab-btn[data-htab="points"]');
  if(tab && !tab.classList.contains('active') && typeof setHumanTab==='function') setHumanTab('points');
}
function setHumanTab(name, root){
  root=root||document.querySelector('.fv-human-box')||document;
  name=name||'layers';
  root.querySelectorAll('.fv-human-tab-btn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-htab')===String(name));
  });
  var box=root.classList && root.classList.contains('fv-human-box') ? root : (root.querySelector && root.querySelector('.fv-human-box')) || document;
  box.querySelectorAll('.fv-human-tab-panel').forEach(function(p){
    p.classList.toggle('active', p.getAttribute('data-htab-panel')===String(name));
  });
}
function bindHumanTabs(){
  document.querySelectorAll('.fv-human-tabs').forEach(function(bar){
    if(bar.dataset.bound==='1') return;
    bar.dataset.bound='1';
    bar.querySelectorAll('.fv-human-tab-btn').forEach(function(btn){
      btn.addEventListener('click', function(e){
        e.preventDefault();
        setHumanTab(btn.getAttribute('data-htab'), bar.closest('.fv-human-box')||document);
      });
    });
  });
  var copyAll=document.querySelector('.copy-all-points');
  if(copyAll && copyAll.dataset.bound!=='1'){
    copyAll.dataset.bound='1';
    copyAll.addEventListener('click', function(){
      var text=(window._fvPagePoints||[]).filter(function(p){ return !p._removed; }).map(function(p,i){ return pointRefText(p,i); }).join('\n');
      _copyText(text, copyAll, '📋 copiar todos os pontos');
    });
  }
}
window.toggleFvPointMode=toggleFvPointMode;
window.renderFvDots=renderFvDots;
window.renderFvPointsList=renderFvPointsList;
window.onFvPointClick=onFvPointClick;
window.setHumanTab=setHumanTab;
window.bindHumanTabs=bindHumanTabs;
window.loadFvPointsFromNotes=loadFvPointsFromNotes;
/** Toggle SA / C1 / C2 / C3 / N3 layers inside contextual viewer.
    Uma camada visível por vez (sem modo "ambos"). */
var CTX_LAYER_MODES=['sa','c1','c2','c3','n3'];
function _syncSegSubtabs(root, mode){
  var bar=root.querySelector('.fv-seg-subtabs');
  if(!bar) return;
  var show=(mode==='sa'||mode==='n3');
  bar.style.display=show?'flex':'none';
  if(!show) return;
  var cur=bar.querySelector('.fv-seg-btn.active');
  var seg=(cur && cur.getAttribute('data-seg'))||'todos';
  setCtxSegFocus(seg, root);
}
function _saTagLabel(t){
  var s=(t.textContent||'').trim();
  var m=s.match(/^S(\d+[A-Z]?)$/i);
  return m?m[1]:'';
}
function _dimSaSegs(svg, keep){
  if(!svg) return;
  var texts=[].slice.call(svg.querySelectorAll('text'));
  var tags=texts.map(function(t){ return {_el:t, lab:_saTagLabel(t)}; }).filter(function(x){ return x.lab; });
  tags.forEach(function(x){
    var g=x._el.closest('g')||x._el;
    g.style.opacity=(keep==='todos'||String(keep)===String(x.lab))?'1':'0.16';
  });
  var fillRe=/#e53935|#ec407a|#ff1744|#f8bbd0|#b71c1c|#ad1457|#ff8a80|#f48fb1/i;
  var paths=[].slice.call(svg.querySelectorAll('path,polygon'));
  paths.forEach(function(p){
    var hl=p.getAttribute('data-fv-hl')||'';
    if(hl==='tag') return;
    var st=(p.getAttribute('style')||'')+' '+(p.getAttribute('fill')||'')+' '+(p.getAttribute('stroke')||'');
    if(hl!=='face' && hl!=='edge' && !fillRe.test(st)) return;
    if(keep==='todos'){ p.style.opacity='1'; return; }
    try{
      var b=p.getBBox();
      var cx=b.x+b.width/2, cy=b.y+b.height/2;
      var best=null, bestD=1e15;
      tags.forEach(function(x){
        var tb=x._el.getBBox();
        var dx=tb.x+tb.width/2-cx, dy=tb.y+tb.height/2-cy;
        var d=dx*dx+dy*dy;
        if(d<bestD){ bestD=d; best=x.lab; }
      });
      p.style.opacity=(best && String(best)===String(keep))?'1':'0.12';
    }catch(e){}
  });
}
function _focusSA(root, outer, seg){
  var svg=(outer&&outer.querySelector('.fv-layer-sa svg'))||null;
  if(!svg) return;
  _dimSaSegs(svg, seg);
  if(seg==='todos'){
    if(outer&&outer._pzSwitchLayer) outer._pzSwitchLayer('sa');
    return;
  }
  var texts=[].slice.call(svg.querySelectorAll('text'));
  var tag=null;
  texts.forEach(function(t){ if(_saTagLabel(t)===String(seg)) tag=t; });
  if(!tag) return;
  var box=null;
  try{
    var tb=tag.getBBox();
    var cx=tb.x+tb.width/2, cy=tb.y+tb.height/2;
    var fillRe=/#e53935|#ec407a|#ff1744|#f8bbd0/i;
    var best=null, bestD=1e15;
    [].slice.call(svg.querySelectorAll('path,polygon')).forEach(function(p){
      var hl=p.getAttribute('data-fv-hl')||'';
      var st=(p.getAttribute('style')||'')+' '+(p.getAttribute('fill')||'');
      if(hl!=='face' && hl!=='edge' && !fillRe.test(st)) return;
      var b=p.getBBox();
      var dx=b.x+b.width/2-cx, dy=b.y+b.height/2-cy;
      var d=dx*dx+dy*dy;
      if(d<bestD){ bestD=d; best=b; }
    });
    box=best||tb;
  }catch(e){ return; }
  if(outer&&outer._pzFocusBox) outer._pzFocusBox(box);
}
function _dimN3Segs(svg, keep){
  if(!svg) return;
  svg.querySelectorAll('.fv-n3-seg').forEach(function(g){
    var lab=g.getAttribute('data-n3-seg')||g.getAttribute('data-seg')||'';
    var on=(keep==='todos'||String(keep)===String(lab));
    g.style.opacity=on?'1':'0.18';
  });
}
function _focusN3(root, outer, seg){
  var svg=(outer&&outer.querySelector('.fv-layer-n3 svg'))||null;
  if(!svg) return;
  _dimN3Segs(svg, seg);
  if(outer&&outer._pzSwitchLayer) outer._pzSwitchLayer('n3');
  if(seg==='todos') return;
  var g=svg.querySelector('.fv-n3-seg[data-n3-seg="'+String(seg)+'"]')
    || svg.querySelector('.fv-n3-seg[data-seg="'+String(seg)+'"]');
  if(g){
    try{
      var b=g.getBBox();
      var pad=Math.max(10, Math.max(b.width,b.height)*0.08);
      if(outer&&outer._pzFocusBox){
        outer._pzFocusBox({x:b.x-pad,y:b.y-pad,w:b.width+2*pad,h:b.height+2*pad});
      }
      return;
    }catch(e){}
  }
  var texts=[].slice.call(svg.querySelectorAll('text.fv-n3-tag,text'));
  var tag=null;
  var want='S'+String(seg);
  texts.forEach(function(t){
    var s=(t.textContent||'').trim();
    if(s===want || s===String(seg) || _saTagLabel(t)===String(seg)) tag=t;
  });
  if(!tag) return;
  try{
    var tb=tag.getBBox();
    var pad=Math.max(12, tb.width);
    if(outer&&outer._pzFocusBox){
      outer._pzFocusBox({x:tb.x-pad,y:tb.y-pad,w:tb.width+2*pad,h:tb.height+80});
    }
  }catch(e){}
}
function _syncSegAccordion(seg, root){
  var list=(root&&root.querySelector('#fv-seg-list'))||document.getElementById('fv-seg-list');
  if(!list) return;
  var target=null;
  var solo=String(seg)!=='todos';
  list.dataset.syncing='1';
  list.classList.toggle('fv-seg-solo', solo);
  list.querySelectorAll('.fv-seg-item').forEach(function(item){
    var match=solo && item.getAttribute('data-seg')===String(seg);
    item.classList.toggle('open', !!match);
    item.setAttribute('aria-expanded', match?'true':'false');
    if(item.tagName==='DETAILS') item.open=!!match;
    if(solo && !match) item.setAttribute('hidden','hidden');
    else item.removeAttribute('hidden');
    if(match) target=item;
  });
  list.querySelectorAll('.fv-seg-detail').forEach(function(detail){
    var match=solo && detail.getAttribute('data-seg')===String(seg);
    if(match) detail.removeAttribute('hidden');
    else detail.setAttribute('hidden','hidden');
  });
  list.dataset.syncing='';
  if(target && target.scrollIntoView && !solo){
    try{ target.scrollIntoView({block:'nearest', behavior:'smooth'}); }catch(e){}
  }
}
function setCtxSegFocus(seg, root){
  root=root||document.getElementById('fvctx-main')||document;
  seg=seg||'todos';
  var bar=root.querySelector('.fv-seg-subtabs');
  if(bar){
    bar.querySelectorAll('.fv-seg-btn').forEach(function(b){
      b.classList.toggle('active', b.getAttribute('data-seg')===String(seg));
    });
  }
  _syncSegAccordion(seg, root);
  var modeBtn=root.querySelector('.fv-hl-btn.active');
  var mode=(modeBtn && modeBtn.getAttribute('data-hl'))||'sa';
  var outer=root.querySelector('[data-panzoom]');
  if(mode==='n3') _focusN3(root, outer, seg);
  else _focusSA(root, outer, seg);
}
function bindCtxSegSubtabs(){
  document.querySelectorAll('.fv-seg-subtabs').forEach(function(bar){
    if(bar.dataset.bound==='1') return;
    bar.dataset.bound='1';
    bar.addEventListener('click', function(e){
      var btn=e.target.closest('.fv-seg-btn');
      if(!btn) return;
      e.preventDefault(); e.stopPropagation();
      var root=bar.closest('#fvctx-main')||bar.parentElement;
      setCtxSegFocus(btn.getAttribute('data-seg')||'todos', root);
    });
  });
  document.querySelectorAll('#fv-seg-list').forEach(function(list){
    if(list.dataset.accBound==='1') return;
    list.dataset.accBound='1';
    list.addEventListener('toggle', function(e){
      var item=e.target;
      if(list.dataset.syncing==='1') return;
      if(!item || !item.classList || !item.classList.contains('fv-seg-item') || !item.open) return;
      var root=list.closest('#fvctx-main')||document;
      setCtxSegFocus(item.getAttribute('data-seg')||'todos', root);
    }, true);
    list.addEventListener('click', function(e){
      if(list.dataset.syncing==='1') return;
      if(e.target.closest && e.target.closest('.fv-seg-detail')) return;
      var item=e.target.closest && e.target.closest('.fv-seg-item');
      if(!item || item.tagName==='DETAILS') return;
      e.preventDefault();
      var root=list.closest('#fvctx-main')||document;
      var seg=item.getAttribute('data-seg')||'todos';
      setCtxSegFocus(item.classList.contains('open')?'todos':seg, root);
    });
    list.addEventListener('keydown', function(e){
      if(e.key!=='Enter' && e.key!==' ') return;
      var item=e.target.closest && e.target.closest('.fv-seg-item');
      if(!item || item.tagName==='DETAILS') return;
      e.preventDefault();
      var root=list.closest('#fvctx-main')||document;
      var seg=item.getAttribute('data-seg')||'todos';
      setCtxSegFocus(item.classList.contains('open')?'todos':seg, root);
    });
  });
}
function _mountN3Layer(n3, done){
  function finish(){
    var s=n3.querySelector('svg');
    if(s) _prepN3Svg(s);
    if(typeof done==='function') done();
  }
  if(!n3){ if(typeof done==='function') done(); return; }
  if(n3.querySelector('svg')){ finish(); return; }
  var src=n3.getAttribute('data-n3-src')||n3.dataset.n3Src;
  if(!src){ finish(); return; }
  if(n3.dataset.loaded==='1'){ finish(); return; }
  n3.dataset.loaded='1';
  fetch(src,{cache:'no-store'}).then(function(r){
    if(!r.ok) throw new Error('n3 '+r.status);
    return r.text();
  }).then(function(txt){
    var i=(txt||'').indexOf('<svg');
    if(i<0) throw new Error('n3 empty');
    n3.innerHTML=txt.slice(i);
    finish();
  }).catch(function(){
    n3.dataset.loaded='0';
    n3.innerHTML='<div class="fv-agent-status">N3 indisponível ainda.<br>'
      +'<span style="font-size:11px;opacity:.75">'+ (src||'') +'</span></div>';
    if(typeof done==='function') done();
  });
}
function setCtxHighlightMode(mode, root){
  root=root||document.getElementById('fvctx-main')||document;
  var wrap=root.querySelector('[data-ctx-layers]')||root;
  var btns=root.querySelectorAll('.fv-hl-btn');
  mode=mode||'sa';
  if(CTX_LAYER_MODES.indexOf(mode)<0) mode='sa';
  var any=false;
  CTX_LAYER_MODES.forEach(function(m){
    var el=wrap.querySelector('.fv-layer-'+m);
    if(!el) return;
    any=true;
    el.style.opacity='1';
    if(m===mode){ el.classList.remove('fv-layer-hidden'); el.setAttribute('data-visible','1'); el.style.display=''; }
    else { el.classList.add('fv-layer-hidden'); el.setAttribute('data-visible','0'); el.style.display='none'; }
  });
  if(!any) return;
  btns.forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-hl')===mode);
  });
  try{ localStorage.setItem('fv_ctx_hl_mode_'+_pageStem(), mode); }catch(e){}
  _syncSaGhostChrome(root, mode);
  var outer=root.querySelector('[data-panzoom]')||wrap.closest('[data-panzoom]');
  function afterLayer(){
    if(outer && outer._pzSwitchLayer) outer._pzSwitchLayer(mode);
    _syncSegSubtabs(root, mode);
    if(outer && outer.classList.contains('fv-pt-mode')){
      var svg=_visibleSvg(outer);
      if(svg) _ensurePtEls(svg);
    }
    if(outer && typeof renderFvDots==='function') renderFvDots(outer);
  }
  if(mode==='n3'){
    _mountN3Layer(wrap.querySelector('.fv-layer-n3'), afterLayer);
  } else {
    afterLayer();
  }
}
/** Mini-abas Camada 1/2/3 da anotação agêntica (uma caixa visível por vez) */
function setAgentTab(n, root){
  root=root||document;
  var bar=root.querySelector('.fv-agent-tabs');
  if(!bar) return;
  var wrap=bar.parentElement;
  wrap.querySelectorAll('.fv-agent-tab-btn').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-atab')===String(n));
  });
  wrap.querySelectorAll('.fv-agent-tab-panel').forEach(function(p){
    p.classList.toggle('active', p.getAttribute('data-atab-panel')===String(n));
  });
}
function bindAgentTabs(){
  document.querySelectorAll('.fv-agent-tabs').forEach(function(bar){
    if(bar.dataset.bound==='1') return;
    bar.dataset.bound='1';
    bar.querySelectorAll('.fv-agent-tab-btn').forEach(function(btn){
      btn.addEventListener('click', function(e){
        e.preventDefault();
        setAgentTab(btn.getAttribute('data-atab'), bar.closest('.fv-agent-tab-wrap')||document);
      });
    });
  });
}
window.setAgentTab=setAgentTab;
window.bindAgentTabs=bindAgentTabs;

function bindCtxHighlightToggles(){
  document.querySelectorAll('.fv-layer-toggle').forEach(function(bar){
    if(bar.dataset.bound==='1') return;
    bar.dataset.bound='1';
    bar.querySelectorAll('.fv-hl-btn').forEach(function(btn){
      btn.addEventListener('click', function(e){
        e.preventDefault(); e.stopPropagation();
        var mode=btn.getAttribute('data-hl')||'sa';
        var root=bar.closest('#fvctx-main')||bar.parentElement;
        setCtxHighlightMode(mode, root);
      });
    });
  });
  document.querySelectorAll('.fv-layer-sa svg').forEach(_markSaHl);
  // restore
  try{
    var m=localStorage.getItem('fv_ctx_hl_mode_'+_pageStem());
    if(m) setCtxHighlightMode(m);
  }catch(e){}
  try{
    if(localStorage.getItem('fv_sa_ghost_'+_pageStem())==='1'){
      var gb=document.querySelector('.fv-sa-ghost-btn');
      var layer=document.querySelector('.fv-layer-sa');
      if(gb&&layer&&!layer.classList.contains('fv-sa-ghost')) toggleSaGhost(gb);
    }
  }catch(e){}
  // carrega SVG de proposta (coords CAD independentes do SA) — uma por camada
  document.querySelectorAll('.fv-layer-c1[data-proposal-src],.fv-layer-c2[data-proposal-src],.fv-layer-c3[data-proposal-src]').forEach(function(layer){
    function mount(svgText){
      if(!svgText||svgText.indexOf('<svg')<0) throw new Error('empty svg');
      var i=svgText.indexOf('<svg');
      layer.innerHTML=svgText.slice(i);
      var s=layer.querySelector('svg');
      if(s){
        if(typeof _prepAgentSvg==='function') _prepAgentSvg(s);
        else {
          s.classList.add('img-fv-hifi','fv-agent-svg');
          s.classList.remove('fv-sync-vb');
          if(!s.dataset.homeVb) s.dataset.homeVb=s.getAttribute('viewBox')||'';
          s.removeAttribute('width'); s.removeAttribute('height');
          s.style.width='100%'; s.style.height='100%'; s.style.display='block';
        }
      }
      var outer=layer.closest('[data-panzoom]');
      if(outer&&outer._pzApply) outer._pzApply();
    }
    var existing=layer.querySelector('svg');
    if(existing){
      if(typeof _prepAgentSvg==='function') _prepAgentSvg(existing);
      var outer0=layer.closest('[data-panzoom]');
      if(outer0&&outer0._pzApply) outer0._pzApply();
      return;
    }
    var src=layer.getAttribute('data-proposal-src');
    if(!src) return;
    fetch(src,{cache:'no-store'}).then(function(r){
      if(!r.ok) throw new Error('HTTP '+r.status);
      return r.text();
    }).then(mount).catch(function(err){
      console.warn('[fv] proposta', src, err);
      if(!layer.querySelector('svg') && !layer.querySelector('.fv-agent-status')){
        layer.innerHTML='<div class="fv-agent-status">Sem artefato ainda.<br><span style="font-size:11px;opacity:.75">'+src+'</span></div>';
      }
    });
  });
  document.querySelectorAll('.fv-layer-n3').forEach(function(layer){
    var existing=layer.querySelector('svg');
    if(existing){ _prepN3Svg(existing); return; }
    if(layer.getAttribute('data-n3-src')||layer.dataset.n3Src){
      _mountN3Layer(layer);
    }
  });
}
window._prepAgentSvg=_prepAgentSvg;
window._prepN3Svg=_prepN3Svg;
window.resetZoom=resetZoom;
window.toggleSaGhost=toggleSaGhost;
window.initPanZoom=initPanZoom;
window.setCtxHighlightMode=setCtxHighlightMode;
window.setCtxSegFocus=setCtxSegFocus;
window.bindCtxHighlightToggles=bindCtxHighlightToggles;
window.bindCtxSegSubtabs=bindCtxSegSubtabs;

document.addEventListener('DOMContentLoaded',function(){
  loadAllAtenTA();
  bindAutosaveFields();
  bindCtxSegSubtabs();
  document.querySelectorAll('[data-panzoom]').forEach(function(el){
    if(el.id) initPanZoom(el.id);
  });
  bindCtxHighlightToggles(); if(typeof refreshTabSeals==='function') refreshTabSeals();
  bindAgentTabs();
  bindHumanTabs();
  if(typeof loadFvPointsFromNotes==='function') loadFvPointsFromNotes(_readStore().notes||{});
});
// if script injects after DOMContentLoaded
if(document.readyState!=='loading'){
  try{
    loadAllAtenTA(); bindAutosaveFields(); bindCtxSegSubtabs();
    document.querySelectorAll('[data-panzoom]').forEach(function(el){
      if(el.id && el.dataset.pzInit!=='1') initPanZoom(el.id);
    });
    bindCtxHighlightToggles(); bindAgentTabs(); bindHumanTabs();
  }catch(e){}
}
})();
