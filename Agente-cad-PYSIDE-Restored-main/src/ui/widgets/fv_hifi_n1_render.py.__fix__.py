"""HI-FI N1 render for Fundos de Viga (FV).

Canonical visual language approved on V301:
- thin CAD lineweights + true DXF text heights
- circles + solid hatches
- multi-segment contextual (all segs) OR local (one seg)
- red/pink alternating fill + hairline contour
- S-tags ~100 cm above centroid with leader line
- viewBox pan/zoom viewer chrome (not CSS scale)

Used by ``preficha_fundo_html`` and ``PreValidationDialog`` so headless,
app and web pages share the same output.
"""
from __future__ import annotations

import html as html_lib
import io
import re
from typing import Any, Iterable, Sequence

# ── Visual constants (locked to approved V301 look) ─────────────────────
BG = "#0a0a0a"
TAG_DY = 100.0  # drawing units ≈ cm
DEFAULT_CTX_W, DEFAULT_CTX_H = 3600, 1100
DEFAULT_LOC_W, DEFAULT_LOC_H = 2800, 900
DEFAULT_DPI = 200

OUTER_CTX = (
    "position:relative;width:100%;max-width:100%;height:560px;"
    "box-sizing:border-box;background:#0a0a0a;overflow:hidden;cursor:grab;"
    "border:1px solid #2a2a2a;border-radius:4px;touch-action:none;user-select:none;"
)
OUTER_LOC = (
    "position:relative;width:100%;max-width:100%;height:420px;"
    "box-sizing:border-box;background:#0a0a0a;overflow:hidden;cursor:grab;"
    "border:1px solid #2a2a2a;border-radius:4px;touch-action:none;user-select:none;"
)
INNER_STYLE = (
    "position:absolute;inset:0;width:100%;height:100%;"
    "box-sizing:border-box;margin:0;padding:0;"
)
SVG_STYLE = (
    "display:block;width:100%;height:100%;"
    "max-width:100%;max-height:100%;background:#0a0a0a;"
)

# ViewBox pan/zoom — CAD-like (approved on V301)
# Embedded notes store + pan/zoom. Notes are persisted in:
# 1) <script type="application/json" id="fv-notes-store"> (inside HTML)
# 2) localStorage (browser cache)
# 3) optional download of {page}.notes.json + HTML re-baked (agent-readable)
NOTES_STORE_TAG = (
    '<script type="application/json" id="fv-notes-store">'
    '{"version":1,"updated_at":"","notes":{}}'
    "</script>"
)

PANZOOM_VIEWBOX_JS = """
<script id="fv-hifi-panzoom">
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
}
window.refreshAgentVerdictUI=refreshAgentVerdictUI;
window.onAgentVerdictChange=onAgentVerdictChange;
function _packKey(){ return 'fv_notes_pack_'+_pageStem(); }
/** API local (fv_notes_server.py) — grava .notes.json em disco mesmo vindo de file:// */
function _notesApiBase(){
  if(window.FV_NOTES_API) return String(window.FV_NOTES_API).replace(/\\/$/,'');
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
  return (location.pathname.split('/').pop()||'ficha.html').replace(/\\.html?$/i,'')||'ficha';
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
  var list=[].slice.call(outer.querySelectorAll('svg.fv-sync-vb, .fv-layer svg, svg'));
  // unique
  return list.filter(function(s,i,a){ return a.indexOf(s)===i; });
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

  var base=svg.viewBox.baseVal;
  var home={x:base.x,y:base.y,w:base.width,h:base.height};
  var state={x:home.x,y:home.y,w:home.w,h:home.h};
  var drag=false,lx=0,ly=0;

  function apply(){
    var vb=state.x+' '+state.y+' '+state.w+' '+state.h;
    _allSyncSvgs(outer).forEach(function(s){ s.setAttribute('viewBox', vb); });
  }
  function reset(){ state={x:home.x,y:home.y,w:home.w,h:home.h}; apply(); }
  outer._pzReset=reset;
  outer._pzApply=apply;

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
    if(e.target&&e.target.closest&&e.target.closest('button,textarea,a,input,.fv-layer-toggle')) return;
    drag=true; lx=e.clientX; ly=e.clientY;
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
    lx=e.clientX; ly=e.clientY; apply();
  });
  window.addEventListener('mouseup',function(){
    if(!drag) return; drag=false; outer.style.cursor='grab';
  });
  outer.addEventListener('dblclick',function(e){
    if(e.target&&e.target.closest&&e.target.closest('button,textarea')) return;
    reset();
  });
  apply();
}
function resetZoom(cid){
  var outer=document.getElementById(cid);
  if(outer&&typeof outer._pzReset==='function'){ outer._pzReset(); }
}
/** Toggle SA / agent proposal layers inside contextual viewer */
function setCtxHighlightMode(mode, root){
  root=root||document.getElementById('fvctx-main')||document;
  var wrap=root.querySelector('[data-ctx-layers]')||root;
  var sa=wrap.querySelector('.fv-layer-sa');
  var ag=wrap.querySelector('.fv-layer-agent');
  var btns=root.querySelectorAll('.fv-hl-btn');
  if(!sa&&!ag) return;
  function show(el, on){
    if(!el) return;
    if(on){ el.classList.remove('fv-layer-hidden'); el.setAttribute('data-visible','1'); el.style.display=''; }
    else { el.classList.add('fv-layer-hidden'); el.setAttribute('data-visible','0'); el.style.display='none'; }
  }
  mode=mode||'sa';
  if(mode==='sa'){ show(sa,true); show(ag,false); }
  else if(mode==='agent'){ show(sa,false); show(ag,true); }
  else { show(sa,true); show(ag,true); if(sa) sa.style.opacity='0.35'; if(ag) ag.style.opacity='1'; }
  if(mode!=='both'){ if(sa) sa.style.opacity='1'; if(ag) ag.style.opacity='1'; }
  btns.forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-hl')===mode);
  });
  try{ localStorage.setItem('fv_ctx_hl_mode_'+_pageStem(), mode); }catch(e){}
}
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
  // restore
  try{
    var m=localStorage.getItem('fv_ctx_hl_mode_'+_pageStem());
    if(m) setCtxHighlightMode(m);
  }catch(e){}
  // try load agent proposal svg if empty
  document.querySelectorAll('.fv-layer-agent[data-proposal-src]').forEach(function(layer){
    if(layer.querySelector('svg')) return;
    var src=layer.getAttribute('data-proposal-src');
    if(!src) return;
    fetch(src,{cache:'no-store'}).then(function(r){ if(!r.ok) throw new Error('no'); return r.text(); }).then(function(svg){
      layer.innerHTML=svg;
      var s=layer.querySelector('svg');
      if(s){ s.classList.add('fv-sync-vb','img-fv-hifi'); s.style.width='100%'; s.style.height='100%'; }
      var outer=layer.closest('[data-panzoom]');
      if(outer&&outer._pzApply) outer._pzApply();
      var st=layer.querySelector('.fv-agent-status');
      if(st) st.remove();
    }).catch(function(){
      if(!layer.querySelector('.fv-agent-status')){
        layer.innerHTML='<div class="fv-agent-status">Sem proposta agêntica ainda.<br><span style="font-size:11px;opacity:.75">Gere com propose-draw → propostas/'+_pageStem()+'_qa_proposta.svg</span></div>';
      }
    });
  });
}
window.resetZoom=resetZoom;
window.initPanZoom=initPanZoom;
window.setCtxHighlightMode=setCtxHighlightMode;
window.bindCtxHighlightToggles=bindCtxHighlightToggles;

document.addEventListener('DOMContentLoaded',function(){
  loadAllAtenTA();
  bindAutosaveFields();
  bindCtxHighlightToggles();
  document.querySelectorAll('[data-panzoom]').forEach(function(el){
    if(el.id) initPanZoom(el.id);
  });
});
// if script injects after DOMContentLoaded
if(document.readyState!=='loading'){
  try{
    loadAllAtenTA(); bindAutosaveFields(); bindCtxHighlightToggles();
    document.querySelectorAll('[data-panzoom]').forEach(function(el){
      if(el.id && el.dataset.pzInit!=='1') initPanZoom(el.id);
    });
  }catch(e){}
}
})();
</script>
""".strip()

NOTES_SAVE_BAR = (
    '<div id="fv-notes-bar" style="position:sticky;bottom:12px;z-index:40;'
    'display:flex;flex-wrap:wrap;gap:10px;align-items:center;'
    'margin:18px 0 8px;padding:12px 14px;border-radius:12px;'
    'background:linear-gradient(135deg,#1a2740,#121820);'
    'border:1px solid #33506e;box-shadow:0 8px 24px rgba(0,0,0,.35)">'
    '<button type="button" onclick="saveNotesToHtmlFile()" '
    'style="min-height:44px;padding:10px 16px;border-radius:10px;cursor:pointer;'
    'background:#3d8bfd;color:#fff;border:none;font-weight:700;font-size:14px">'
    "💾 Salvar anotações no HTML / JSON</button>"
    '<span id="fv-notes-hint" style="color:#8b95a8;font-size:12px;flex:1">'
    "Prefira abrir via servidor local (grava .notes.json no disco a cada tecla). "
    "Comando: <code style=\"color:#9ec9ff\">python scripts/arete/tmp/fv_notes_server.py</code> "
    "→ http://127.0.0.1:8765/fundos_viga/V301.html</span>"
    "</div>"
)

HIFI_CSS = (
    "<style id=\"fv-hifi-css\">"
    "/* viewers */"
    ".img-fv-hifi,.img-fvctx-main,.img-fvlocal-main{"
    "width:100%!important;height:100%!important;"
    "max-width:100%!important;max-height:100%!important;"
    "display:block!important;background:#0a0a0a}"
    "[data-panzoom]{max-width:100%;box-sizing:border-box}"
    "/* page chrome — ficha da viga */"
    "body{font-family:\"Segoe UI\",system-ui,sans-serif!important;"
    "background:#0b0d10!important;color:#e8edf5!important;"
    "padding:18px 20px 48px!important}"
    "h2.fv-page-title{font-size:22px!important;font-weight:750!important;"
    "color:#f2f6ff!important;margin:0 0 14px!important;letter-spacing:-.02em;"
    "font-family:\"Segoe UI\",system-ui,sans-serif!important}"
    ".nav-bar{display:flex!important;align-items:center!important;gap:12px!important;"
    "flex-wrap:wrap!important;margin:0 0 18px!important;"
    "background:linear-gradient(135deg,#152033 0%,#10151f 100%)!important;"
    "padding:14px 16px!important;border-radius:14px!important;"
    "border:1px solid #2a3344!important;"
    "box-shadow:0 10px 28px rgba(0,0,0,.28)!important;"
    "position:sticky!important;top:10px!important;z-index:30!important}"
    ".nav-arrow{color:#9ec9ff!important;text-decoration:none!important;"
    "font-size:13px!important;font-weight:650!important;"
    "padding:10px 14px!important;border:1px solid #33506e!important;"
    "border-radius:10px!important;background:#121a28!important;"
    "white-space:nowrap!important;min-height:42px!important;"
    "display:inline-flex!important;align-items:center!important}"
    ".nav-arrow:hover{background:#1a2740!important;border-color:#3d8bfd!important}"
    ".nav-pos{color:#c5d0e0!important;font-size:14px!important;flex:1!important;"
    "display:flex!important;align-items:center!important;justify-content:center!important;"
    "flex-wrap:wrap!important;gap:10px!important;text-align:center!important}"
    ".nav-pos b{color:#fff!important;font-size:16px!important}"
    ".nav-pos select,.nav-bar select{"
    "appearance:none!important;-webkit-appearance:none!important;"
    "background:#0f1724 url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%235eb0ff' d='M1 1l5 5 5-5'/%3E%3C/svg%3E\") "
    "no-repeat right 12px center!important;"
    "color:#fff!important;border:1px solid #3d8bfd!important;"
    "padding:10px 36px 10px 14px!important;border-radius:10px!important;"
    "font-weight:700!important;font-size:15px!important;cursor:pointer!important;"
    "min-height:44px!important;min-width:180px!important;"
    "font-family:\"Segoe UI\",system-ui,sans-serif!important}"
    ".nav-pos select:hover,.nav-bar select:hover{box-shadow:0 0 0 3px rgba(61,139,253,.22)!important}"
    ".tag{display:inline-flex!important;align-items:center!important;"
    "background:#243044!important;color:#9ec9ff!important;"
    "font-size:12px!important;font-weight:700!important;"
    "padding:8px 12px!important;border-radius:999px!important;"
    "border:1px solid #33506e!important;margin-left:0!important}"
    ".sec{margin:14px 0!important;border:1px solid #2a3344!important;"
    "border-radius:12px!important;overflow:hidden!important;"
    "background:#121820!important;box-shadow:0 6px 18px rgba(0,0,0,.18)!important}"
    ".sec-title{background:#171e2b!important;color:#7dffa8!important;"
    "padding:14px 16px!important;font-size:15px!important;font-weight:700!important;"
    "border-radius:0!important;border-bottom:1px solid #243044!important;"
    "font-family:\"Segoe UI\",system-ui,sans-serif!important;"
    "display:flex!important;align-items:center!important;gap:8px!important}"
    ".sec-title .fv-chevron{color:#5eb0ff!important;font-size:12px!important;"
    "width:18px!important;display:inline-block!important}"
    ".sec-body{padding:14px 16px!important}"
    ".evidence-card{background:#10151f!important;border:1px solid #2a3344!important;"
    "border-radius:12px!important;padding:12px!important}"
    ".evidence-title{color:#c5d0e0!important;font-size:13px!important;"
    "font-weight:650!important;margin-bottom:8px!important}"
    ".ficha-col-title{color:#9ec9ff!important;font-size:13px!important;"
    "font-weight:700!important;margin-bottom:8px!important;padding:8px 10px!important;"
    "border-radius:8px!important}"
    "a{color:#7eb8f7}"
    "/* highlight toggle SA / agent */"
    ".fv-layer-toggle{display:flex;flex-wrap:wrap;gap:8px;align-items:center;"
    "margin:0 0 10px;padding:8px;background:#0f1520;border:1px solid #2a3344;"
    "border-radius:12px}"
    ".fv-hl-btn{min-height:40px;padding:8px 14px;border-radius:10px;cursor:pointer;"
    "font-weight:700;font-size:13px;border:1px solid #33506e;background:#121a28;"
    "color:#9ec9ff;font-family:Segoe UI,system-ui,sans-serif}"
    ".fv-hl-btn:hover{border-color:#3d8bfd}"
    ".fv-hl-btn.active[data-hl='sa']{background:#3b1515;border-color:#ff5252;color:#ffcdd2}"
    ".fv-hl-btn.active[data-hl='agent']{background:#00363a;border-color:#00e5ff;color:#b2ebf2}"
    ".fv-hl-btn.active[data-hl='both']{background:#1a2740;border-color:#69f0ae;color:#c8e6c9}"
    ".fv-hl-legend{color:#8b95a8;font-size:12px;margin-left:auto}"
    ".fv-hl-legend b.sa{color:#ff8a80}.fv-hl-legend b.ag{color:#00e5ff}"
    "[data-ctx-layers]{position:relative;width:100%;height:100%}"
    ".fv-layer{position:absolute;inset:0;width:100%;height:100%}"
    ".fv-layer-hidden{display:none!important}"
    ".fv-layer svg{width:100%!important;height:100%!important}"
    ".fv-agent-status{display:flex;align-items:center;justify-content:center;"
    "height:100%;color:#567;text-align:center;padding:24px;font-size:14px;"
    "background:#0a0a0a;border:1px dashed #2a5080;border-radius:8px}"
    "/* veredito agêntico: radio seleção única */"
    ".fv-agent-box{position:relative}"
    ".fv-agent-verdict{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 10px}"
    ".fv-verdict-opt{display:inline-flex;align-items:center;gap:8px;"
    "min-height:40px;padding:8px 14px;border-radius:999px;cursor:pointer;"
    "border:1px solid #33506e;background:#0f1724;color:#9ec9ff;"
    "font-weight:700;font-size:13px;user-select:none}"
    ".fv-verdict-opt input{position:absolute;opacity:0;pointer-events:none}"
    ".fv-verdict-opt .fv-radio-dot{width:16px;height:16px;border-radius:50%;"
    "border:2px solid #5a7a9a;box-sizing:border-box;flex:0 0 auto;"
    "background:transparent;position:relative}"
    ".fv-verdict-opt .fv-radio-dot::after{content:'';position:absolute;"
    "inset:3px;border-radius:50%;background:transparent}"
    ".fv-verdict-opt:has(input:checked) .fv-radio-dot::after{background:currentColor}"
    ".fv-verdict-opt.validou:has(input:checked){border-color:#69f0ae;color:#b9f6ca;"
    "background:#0d2818;box-shadow:0 0 0 2px rgba(105,240,174,.18)}"
    ".fv-verdict-opt.invalidou:has(input:checked){border-color:#ff8a80;color:#ffcdd2;"
    "background:#2a1212;box-shadow:0 0 0 2px rgba(255,138,128,.18)}"
    ".fv-agent-verdict-hint{color:#8b95a8;font-size:11px;margin:0 0 8px;line-height:1.35}"
    ".fv-agent-box.has-validou .fv-agent-verdict-hint{color:#81c784}"
    ".fv-agent-box.has-invalidou .fv-agent-verdict-hint{color:#ef9a9a}"
    "textarea.fv-need-text{border-color:#ff7043!important;"
    "box-shadow:0 0 0 2px rgba(255,112,67,.25)!important}"
    ".fv-agent-box.fv-incomplete{outline:1px dashed #445;outline-offset:4px}"
    "</style>"
)


def agent_verdict_key(agent_key: str) -> str:
    """aten_fv_ctx_agent_X → aten_fv_ctx_agent_verdict_X"""
    prefix = "aten_fv_ctx_agent_"
    if agent_key.startswith(prefix) and not agent_key.startswith(
        "aten_fv_ctx_agent_verdict_"
    ):
        return "aten_fv_ctx_agent_verdict_" + agent_key[len(prefix) :]
    return agent_key + "_verdict"


def agent_verdict_radios_html(agent_key: str, beam: str = "") -> str:
    """Radio exclusivos: Agente validou | Agente invalidou."""
    vk = agent_verdict_key(agent_key)
    safe_vk = html_lib.escape(vk, quote=True)
    safe_beam = html_lib.escape(beam or "beam", quote=True)
    group = f"fv_agent_verdict_{safe_beam}"
    return (
        f'<div class="fv-agent-verdict" role="radiogroup" '
        f'aria-label="Veredito agêntico {html_lib.escape(beam or "")}">'
        f'<label class="fv-verdict-opt validou">'
        f'<input type="radio" name="{group}" data-atkey="{safe_vk}" '
        f'data-role="agent-verdict" value="validou" '
        f'onchange="onAgentVerdictChange(this)">'
        f'<span class="fv-radio-dot" aria-hidden="true"></span>'
        f"<span>Agente validou</span></label>"
        f'<label class="fv-verdict-opt invalidou">'
        f'<input type="radio" name="{group}" data-atkey="{safe_vk}" '
        f'data-role="agent-verdict" value="invalidou" '
        f'onchange="onAgentVerdictChange(this)">'
        f'<span class="fv-radio-dot" aria-hidden="true"></span>'
        f"<span>Agente invalidou</span></label>"
        f"</div>"
        f'<div class="fv-agent-verdict-hint">'
        f"Seleção única obrigatória: Agente validou OU Agente invalidou. "
        f"Em ambos os casos o comentário é obrigatório."
        f"</div>"
    )


def agent_annotation_box_html(
    agent_key: str,
    beam: str,
    *,
    ta_css: str | None = None,
) -> str:
    """Caixa completa da anotação agêntica (radios + textarea)."""
    css = ta_css or (
        "width:100%;min-height:110px;background:#0d1520;color:#7ec8ff;"
        "border:1px solid #2a5080;border-radius:8px;padding:10px;"
        "font-family:Segoe UI,system-ui,monospace;font-size:13px;"
        "box-sizing:border-box;resize:vertical;line-height:1.4"
    )
    safe_key = html_lib.escape(agent_key, quote=True)
    safe_beam = html_lib.escape(beam)
    default_ph = (
        f"Selecione validou/invalidou e escreva o comentário sobre {safe_beam}…"
    )
    return (
        '<div class="fv-agent-box" style="background:#0a121c;border:1px solid #2a5080;'
        'border-radius:10px;padding:12px">'
        '<div style="color:#7ec8ff;font-size:13px;font-weight:700;'
        f'margin-bottom:6px">🤖 Anotação agêntica — QA / looping {safe_beam}</div>'
        '<div style="color:#567;font-size:11px;margin-bottom:8px">'
        "Agente QA: veredito único + comentário obrigatório "
        "(validou = compreensão/porquê; invalidou = falhas e causa)."
        "</div>"
        f"{agent_verdict_radios_html(agent_key, beam)}"
        f'<textarea data-atkey="{safe_key}" data-atrole="agent" '
        f'data-placeholder-default="{html_lib.escape(default_ph, quote=True)}" '
        f'onblur="saveAtenTA(this)" oninput="refreshAgentVerdictUI()" '
        f'placeholder="{html_lib.escape(default_ph, quote=True)}" '
        f'style="{css}"></textarea></div>'
    )


def wrap_panzoom_viewer(
    cid: str,
    svg_markup: str,
    *,
    height_css: str | None = None,
    mode: str = "local",
    agent_svg: str = "",
    proposal_src: str = "",
) -> str:
    """Wrap SVG in pan/zoom chrome. Contextual mode adds SA/agent highlight toggle."""
    if not svg_markup and mode != "contextual":
        return (
            '<div style="height:120px;display:flex;align-items:center;'
            'justify-content:center;color:#a85d55">artefato N1 ausente</div>'
        )
    outer = OUTER_CTX if mode == "contextual" else OUTER_LOC
    if height_css:
        outer = re.sub(r"height:\d+px", f"height:{height_css}", outer, count=1)
    safe_cid = html_lib.escape(cid, quote=True)
    btn = (
        f'<button type="button" onclick="resetZoom(\'{safe_cid}\')" '
        f'style="position:absolute;top:6px;right:6px;background:#2a2a2a;color:#aaa;'
        f'border:1px solid #444;padding:2px 10px;cursor:pointer;font-size:10px;'
        f'border-radius:3px;z-index:20">Reset zoom</button>'
    )
    if mode != "contextual":
        return (
            f'<div id="{safe_cid}" data-panzoom="1" style="{outer}">'
            f'<div id="{safe_cid}-inner" style="{INNER_STYLE}">{svg_markup or ""}</div>'
            f"{btn}</div>"
        )

    # Contextual: dual layers + toggle
    prop_src = proposal_src or f"propostas/{cid.replace('fvctx_', '')}_qa_proposta.svg"
    # beam slug from cid fvctx_V301
    beam_guess = cid.replace("fvctx_", "")
    prop_src = proposal_src or f"propostas/{beam_guess}_qa_proposta.svg"
    agent_inner = agent_svg or (
        f'<div class="fv-agent-status">Sem proposta agêntica ainda.<br>'
        f'<span style="font-size:11px;opacity:.75">Arquivo esperado: {html_lib.escape(prop_src)}</span></div>'
    )
    toggle = (
        '<div class="fv-layer-toggle" role="toolbar" aria-label="Alternar destaques">'
        '<button type="button" class="fv-hl-btn active" data-hl="sa">🔴 Destaque SA</button>'
        '<button type="button" class="fv-hl-btn" data-hl="agent">🔵 Destaque agêntico</button>'
        '<button type="button" class="fv-hl-btn" data-hl="both">⚖ Ambos</button>'
        '<span class="fv-hl-legend"><b class="sa">SA</b> vermelho/rosa · '
        '<b class="ag">QA</b> ciano/verde</span></div>'
    )
    layers = (
        f'<div data-ctx-layers="1" style="position:relative;width:100%;height:100%">'
        f'<div class="fv-layer fv-layer-sa" data-visible="1">{svg_markup or ""}</div>'
        f'<div class="fv-layer fv-layer-agent fv-layer-hidden" data-visible="0" '
        f'data-proposal-src="{html_lib.escape(prop_src, quote=True)}">{agent_inner}</div>'
        f"</div>"
    )
    return (
        f"{toggle}"
        f'<div id="{safe_cid}" data-panzoom="1" style="{outer}">'
        f'<div id="{safe_cid}-inner" style="{INNER_STYLE}">{layers}</div>'
        f"{btn}</div>"
    )


def _as_xy(points: Sequence[Any]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points or []:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                out.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError):
                continue
    return out


def _normalize_segments(segments: Iterable[dict]) -> list[dict]:
    """Accept [{points,label,index}, ...] → cleaned list with poly/centroid."""
    cleaned: list[dict] = []
    for i, raw in enumerate(segments or []):
        if not isinstance(raw, dict):
            continue
        pts = _as_xy(raw.get("points") or [])
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        # closed rect if only sparse points — use convex hull bbox poly
        if len(pts) >= 3:
            poly = pts if pts[0] != pts[-1] else pts[:-1]
            if len(poly) < 3:
                poly = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        else:
            poly = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        lab = str(raw.get("label") or raw.get("segment_label") or (i + 1))
        idx = int(raw.get("index") if raw.get("index") is not None else i)
        cleaned.append(
            {
                "label": lab,
                "index": idx,
                "points": pts,
                "poly": poly,
                "c": (cx, cy),
                "bbox": (xmin, ymin, xmax, ymax),
            }
        )
    return cleaned


def _seg_colors(index: int) -> tuple[str, str, str, str]:
    even = index % 2 == 0
    face = "#e53935" if even else "#ec407a"
    edge = "#ff1744" if even else "#f8bbd0"
    tag_bg = "#b71c1c" if even else "#ad1457"
    tag_edge = "#ff8a80" if even else "#f48fb1"
    return face, edge, tag_bg, tag_edge


def _rgb(ent: dict) -> tuple[float, float, float]:
    c = ent.get("color")
    if isinstance(c, (list, tuple)) and len(c) == 3:
        r, g, b = c
        if r == 0 and g == 0 and b == 0:
            return (0.92, 0.92, 0.92)
        return (r / 255.0, g / 255.0, b / 255.0)
    return (0.55, 0.65, 0.80)


def _lw(ent: dict) -> float:
    raw = float(ent.get("lineweight") or 25.0)
    return max(0.10, min(0.85, raw / 90.0))


def _text_fontsize_pt(h_dxf: float, view_h: float, fig_h_px: float, dpi: float) -> float:
    px_per_unit = fig_h_px / max(view_h, 1e-6)
    fsz = float(h_dxf) * px_per_unit * 72.0 / dpi
    return max(1.2, min(28.0, fsz))


def _view_envelope(
    segs: list[dict], mode: str
) -> tuple[float, float, float, float, float]:
    """Return vx0,vx1,vy0,vy1,view_h."""
    bbs = [s["bbox"] for s in segs]
    xmin = min(b[0] for b in bbs)
    ymin = min(b[1] for b in bbs)
    xmax = max(b[2] for b in bbs)
    ymax = max(b[3] for b in bbs)
    span_x = max(xmax - xmin, 1.0)
    span_y = max(ymax - ymin, 1.0)
    if mode == "contextual":
        # +~50% neighborhood around full beam
        pad_x = max(180.0, span_x * 0.15)
        pad_y = max(135.0, span_y * 9.0, span_x * 0.09, TAG_DY + 40.0)
    else:
        pad_x = max(100.0, span_x * 0.55)
        pad_y = max(TAG_DY + 40.0, span_y * 10.0, span_x * 0.12)
    vx0, vx1 = xmin - pad_x, xmax + pad_x
    vy0, vy1 = ymin - pad_y, ymax + pad_y
    # ensure tags fit
    for s in segs:
        cy = s["c"][1]
        vy1 = max(vy1, cy + TAG_DY + 30.0)
    return vx0, vx1, vy0, vy1, max(vy1 - vy0, 1.0)


def render_fv_hifi_n1_svg(
    dxf_data: dict | None,
    segments: Sequence[dict],
    *,
    mode: str = "local",
    width: int | None = None,
    height: int | None = None,
    dpi: int = DEFAULT_DPI,
    aria_label: str | None = None,
    alt: str | None = None,
) -> str:
    """Render HI-FI SVG markup (no XML decl). Empty string on failure.

    ``mode``:
      - ``local``: frame first/only segment neighborhood
      - ``contextual``: frame all segments, highlight every one
    """
    segs = _normalize_segments(segments)
    if not segs:
        return ""
    mode = "contextual" if mode == "contextual" else "local"
    if mode == "local":
        segs_draw = segs[:1]
        width = width or DEFAULT_LOC_W
        height = height or DEFAULT_LOC_H
        default_aria = f"N1 / SA local · Seg {segs_draw[0]['label']}"
        default_alt = "N1 / SA local"
    else:
        segs_draw = segs
        width = width or DEFAULT_CTX_W
        height = height or DEFAULT_CTX_H
        default_aria = f"N1 / SA contextual · {len(segs_draw)} segmentos"
        default_alt = "N1 / SA contextual"
    aria_label = aria_label or default_aria
    alt = alt or default_alt

    dxf = dxf_data if isinstance(dxf_data, dict) else {}
    vx0, vx1, vy0, vy1, view_h = _view_envelope(segs_draw, mode)

    try:
        import matplotlib

        matplotlib.use("Agg")
        matplotlib.rcParams["svg.fonttype"] = "none"
        matplotlib.rcParams["path.simplify"] = False
        import matplotlib.pyplot as plt
        from matplotlib.collections import LineCollection
        from matplotlib.patches import Circle, Polygon as MplPolygon
    except Exception:
        return ""

    try:
        fig, ax = plt.subplots(
            figsize=(width / dpi, height / dpi), dpi=dpi
        )
        ax.set_facecolor(BG)
        fig.patch.set_facecolor(BG)
        fig.subplots_adjust(left=0.01, right=0.99, bottom=0.02, top=0.98)
        ax.set_aspect("equal")
        ax.set_xlim(vx0, vx1)
        ax.set_ylim(vy0, vy1)
        ax.axis("off")

        def in_view_line(s, e) -> bool:
            return not (
                min(s[0], e[0]) > vx1
                or max(s[0], e[0]) < vx0
                or min(s[1], e[1]) > vy1
                or max(s[1], e[1]) < vy0
            )

        # Lines
        segs_lc: dict[tuple, list] = {}
        for line in dxf.get("lines") or []:
            s, e = line.get("start"), line.get("end")
            if not s or not e or not in_view_line(s, e):
                continue
            key = (_rgb(line), _lw(line))
            segs_lc.setdefault(key, []).append([(s[0], s[1]), (e[0], e[1])])
        for (col, lw), batches in segs_lc.items():
            ax.add_collection(
                LineCollection(
                    batches,
                    colors=[col],
                    linewidths=lw,
                    antialiaseds=True,
                    capstyle="butt",
                    joinstyle="miter",
                )
            )

        for poly in dxf.get("polylines") or []:
            pts = poly.get("points") or []
            if len(pts) < 2:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            if min(xs) > vx1 or max(xs) < vx0 or min(ys) > vy1 or max(ys) < vy0:
                continue
            ax.plot(
                xs,
                ys,
                color=_rgb(poly),
                lw=_lw(poly),
                solid_capstyle="butt",
                solid_joinstyle="miter",
                antialiased=True,
            )

        for cir in dxf.get("circles") or []:
            c = cir.get("center")
            r = float(cir.get("radius") or 0)
            if not c or r <= 0:
                continue
            if (
                c[0] + r < vx0
                or c[0] - r > vx1
                or c[1] + r < vy0
                or c[1] - r > vy1
            ):
                continue
            ax.add_patch(
                Circle(
                    (c[0], c[1]),
                    r,
                    fill=False,
                    edgecolor=_rgb(cir),
                    lw=max(0.12, _lw(cir)),
                    zorder=3,
                )
            )

        for hatch in dxf.get("hatches") or []:
            if not hatch.get("solid"):
                continue
            col = _rgb(hatch)
            for path in hatch.get("paths") or []:
                if not path or len(path) < 3:
                    continue
                xs = [p[0] for p in path]
                ys = [p[1] for p in path]
                if (
                    min(xs) > vx1
                    or max(xs) < vx0
                    or min(ys) > vy1
                    or max(ys) < vy0
                ):
                    continue
                ax.add_patch(
                    MplPolygon(
                        list(path),
                        closed=True,
                        fill=True,
                        facecolor=col,
                        edgecolor=col,
                        lw=0.15,
                        alpha=0.18,
                        zorder=1,
                    )
                )

        for txt in dxf.get("texts") or []:
            pos = txt.get("pos") or [0, 0]
            tx, ty = float(pos[0]), float(pos[1])
            if not (vx0 <= tx <= vx1 and vy0 <= ty <= vy1):
                continue
            t = str(txt.get("text") or "").strip()
            if not t or len(t) > 80 or ("\\" in t and len(t) > 20):
                continue
            h = float(txt.get("height") or 10.0)
            fsz = _text_fontsize_pt(h, view_h, height, dpi)
            rot = float(txt.get("rotation") or 0.0)
            ax.text(
                tx,
                ty,
                t,
                color=_rgb(txt),
                fontsize=fsz,
                rotation=rot,
                ha="center",
                va="center",
                clip_on=True,
                fontfamily="DejaVu Sans",
                zorder=5,
            )

        # Highlights + tags
        for s in segs_draw:
            face, edge, tag_bg, tag_edge = _seg_colors(int(s["index"]))
            ax.add_patch(
                MplPolygon(
                    s["poly"],
                    closed=True,
                    fill=True,
                    facecolor=face,
                    edgecolor="none",
                    lw=0,
                    alpha=0.38,
                    zorder=8,
                )
            )
            ax.add_patch(
                MplPolygon(
                    s["poly"],
                    closed=True,
                    fill=False,
                    edgecolor=edge,
                    lw=0.50,
                    alpha=1.0,
                    zorder=9,
                    joinstyle="miter",
                )
            )
            cx, cy = s["c"]
            ax.plot(
                [cx],
                [cy],
                marker="o",
                markersize=3.2,
                markeredgewidth=0.55,
                markerfacecolor="#ffffff",
                markeredgecolor=edge,
                zorder=10,
            )
            ax.annotate(
                f"S{s['label']}",
                xy=(cx, cy),
                xytext=(cx, cy + TAG_DY),
                color="#ffffff",
                fontsize=9.0,
                fontweight="bold",
                ha="center",
                va="bottom",
                zorder=10,
                bbox=dict(
                    boxstyle="round,pad=0.28",
                    facecolor=tag_bg,
                    edgecolor=tag_edge,
                    linewidth=1.0,
                    alpha=0.95,
                ),
                arrowprops=dict(
                    arrowstyle="-|>",
                    color=edge,
                    lw=0.7,
                    mutation_scale=9,
                    shrinkA=2,
                    shrinkB=2,
                    connectionstyle="arc3,rad=0",
                ),
            )

        buf = io.BytesIO()
        fig.savefig(buf, format="svg", facecolor=BG, dpi=dpi, pad_inches=0)
        plt.close(fig)
        svg = buf.getvalue().decode("utf-8")
    except Exception:
        try:
            plt.close("all")
        except Exception:
            pass
        return ""

    svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>\s*", "", svg)

    def _root(m: re.Match[str]) -> str:
        tag = m.group(0)
        cls = "img-fv-hifi"
        if 'class="' in tag:
            tag = re.sub(r'class="[^"]*"', f'class="{cls}"', tag, count=1)
        else:
            tag = tag[:-1] + f' class="{cls}">'
        if 'style="' in tag:
            tag = re.sub(r'style="[^"]*"', f'style="{SVG_STYLE}"', tag, count=1)
        else:
            tag = tag[:-1] + f' style="{SVG_STYLE}">'
        if "preserveAspectRatio=" not in tag:
            tag = tag[:-1] + ' preserveAspectRatio="xMidYMid meet">'
        tag = re.sub(r'\s(width|height)="[^"]*"', "", tag)
        # aria / alt for selectors & a11y
        if "aria-label=" in tag:
            tag = re.sub(
                r'aria-label="[^"]*"',
                f'aria-label="{html_lib.escape(aria_label, quote=True)}"',
                tag,
            )
        else:
            tag = (
                tag[:-1]
                + f' role="img" aria-label="{html_lib.escape(aria_label, quote=True)}">'
            )
        if 'alt="' in tag:
            tag = re.sub(
                r'alt="[^"]*"',
                f'alt="{html_lib.escape(alt, quote=True)}"',
                tag,
            )
        else:
            tag = tag[:-1] + f' alt="{html_lib.escape(alt, quote=True)}">'
        if "role=" not in tag:
            tag = tag[:-1] + ' role="img">'
        return tag

    svg = re.sub(r"<svg\b[^>]*>", _root, svg, count=1)
    return svg.strip()
