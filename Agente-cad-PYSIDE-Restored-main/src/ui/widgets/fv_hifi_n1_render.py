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
TAG_DY = 100.0  # drawing units ≈ cm — horizontal beams (tag above)
TAG_DX = 55.0  # vertical beams: tag to the LEFT of centroid
TAG_FS_H = 9.0  # horizontal tag font
TAG_FS_V = 5.5  # vertical tag font (smaller — tags used to hide the strip)
# Initial viewer zoom: half viewBox → 2× closer than full home
INITIAL_ZOOM_FACTOR = 0.5
# Canvas quadrado: o envelope de dados já é square; o figure precisa
# acompanhar senão o SVG fica 3:1 e o viewer só mostra a faixa central.
DEFAULT_CTX_W, DEFAULT_CTX_H = 1600, 1600
DEFAULT_LOC_W, DEFAULT_LOC_H = 1200, 1200
DEFAULT_DPI = 160

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
SA_GHOST_BTN_HTML = (
    '<button type="button" class="fv-sa-ghost-btn" data-sa-ghost="0" '
    'title="Destaque translúcido: contorno suave, sem fundo sólido (somente SA)" '
    'onclick="toggleSaGhost(this)">Destaque suave</button>'
)
PT_BTN_HTML = (
    '<button type="button" class="fv-pt-btn" data-pt="0" '
    'title="Ponto de atenção: clique num elemento do desenho para anotar (igual N2×N4)" '
    'onclick="toggleFvPointMode(this)">Ponto</button>'
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
  var m=v.match(/^rgba?\\(\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)/);
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
    if((tag==='path'||tag==='line'||tag==='polyline') && /fill:\\s*none/.test(st)){
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
      var text=(window._fvPagePoints||[]).filter(function(p){ return !p._removed; }).map(function(p,i){ return pointRefText(p,i); }).join('\\n');
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
  var m=s.match(/^S(\\d+[A-Z]?)$/i);
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
    ".fv-hl-btn.active[data-hl='c1']{background:#00363a;border-color:#00e5ff;color:#b2ebf2}"
    ".fv-hl-btn.active[data-hl='c2']{background:#3a1a3a;border-color:#e040fb;color:#f3c9ff}"
    ".fv-hl-btn.active[data-hl='c3']{background:#3a2b00;border-color:#ffab00;color:#ffe0b2}"
    ".fv-hl-btn.active[data-hl='n3']{background:#1a2a3a;border-color:#64b5f6;color:#bbdefb}"
    ".fv-hl-legend{color:#8b95a8;font-size:12px;margin-left:auto}"
    ".fv-hl-legend b.sa{color:#ff8a80}.fv-hl-legend b.ag{color:#00e5ff}"
    ".fv-hl-legend b.n3{color:#64b5f6}"
    "/* selos H/A nas abas SA C1 C2 C3 */"
    ".fv-tab-seals{display:inline-flex;gap:2px;margin-left:4px;align-items:center;vertical-align:middle}"
    ".fv-seal{font-size:9px;padding:0 3px;border-radius:3px;font-weight:700;line-height:1.35;letter-spacing:0}"
    ".fv-seal-h-ok{background:#1b5e20;color:#c8e6c9}"
    ".fv-seal-h-bad{background:#b71c1c;color:#ffcdd2}"
    ".fv-seal-a-ok{background:#006064;color:#b2ebf2}"
    ".fv-seal-a-bad{background:#6a1b9a;color:#e1bee7}"
    ".fv-seal-empty{opacity:.35;color:#8b95a8}"
    ".fv-hl-btn{display:inline-flex;align-items:center;gap:2px}"
    "[data-ctx-layers]{position:relative;width:100%;height:100%}"
    ".fv-layer{position:absolute;inset:0;width:100%;height:100%}"
    ".fv-layer-hidden{display:none!important}"
    ".fv-layer svg{width:100%!important;height:100%!important;"
    "max-width:100%!important;max-height:100%!important;display:block!important}"
    ".fv-layer-c1,.fv-layer-c2,.fv-layer-c3,.fv-layer-n3{z-index:2;background:#0a0a0a}"
    ".fv-layer-sa{z-index:1}"
    ".fv-layer-c1 svg.fv-agent-svg,.fv-layer-c2 svg.fv-agent-svg,"
    ".fv-layer-c3 svg.fv-agent-svg,.fv-layer-n3 svg.fv-agent-svg{background:#0a0a0a}"
    ".fv-agent-status{display:flex;align-items:center;justify-content:center;"
    "height:100%;color:#567;text-align:center;padding:24px;font-size:14px;"
    "background:#0a0a0a;border:1px dashed #2a5080;border-radius:8px}"
    "/* veredito agêntico: radio seleção única */"
    ".fv-agent-box{position:relative}"
    ".fv-agent-verdict{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 8px;align-items:center}"
    ".fv-verdict-opt{display:inline-flex;align-items:center;gap:3px;"
    "min-height:20px;padding:1px 7px;border-radius:999px;cursor:pointer;"
    "border:1px solid #33506e;background:#0f1724;color:#9ec9ff;"
    "font-weight:600;font-size:10px;user-select:none;line-height:1.15}"
    ".fv-verdict-opt input{position:absolute;opacity:0;pointer-events:none}"
    ".fv-verdict-opt .fv-radio-dot{width:9px;height:9px;border-radius:50%;"
    "border:1.5px solid #5a7a9a;box-sizing:border-box;flex:0 0 auto;"
    "background:transparent;position:relative}"
    ".fv-verdict-opt .fv-radio-dot::after{content:'';position:absolute;"
    "inset:2px;border-radius:50%;background:transparent}"
    ".fv-verdict-opt:has(input:checked) .fv-radio-dot::after{background:currentColor}"
    ".fv-verdict-opt.validou:has(input:checked){border-color:#69f0ae;color:#b9f6ca;"
    "background:#0d2818;box-shadow:none}"
    ".fv-verdict-opt.invalidou:has(input:checked){border-color:#ff8a80;color:#ffcdd2;"
    "background:#2a1212;box-shadow:none}"
    ".fv-agent-verdict-hint{color:#8b95a8;font-size:11px;margin:0 0 8px;line-height:1.35}"
    ".fv-agent-box.has-validou .fv-agent-verdict-hint{color:#81c784}"
    ".fv-agent-box.has-invalidou .fv-agent-verdict-hint{color:#ef9a9a}"
    "textarea.fv-need-text{border-color:#ff7043!important;"
    "box-shadow:0 0 0 2px rgba(255,112,67,.25)!important}"
    ".fv-agent-box.fv-incomplete{outline:1px dashed #445;outline-offset:4px}"
    "/* mini-abas Camada 1/2/3 da anotacao agentica */"
    ".fv-agent-tabs{display:flex;gap:6px;margin:0 0 8px;flex-wrap:wrap}"
    ".fv-agent-tab-btn{min-height:32px;padding:6px 12px;border-radius:8px;"
    "cursor:pointer;font-weight:700;font-size:12px;border:1px solid #33506e;"
    "background:#121a28;color:#9ec9ff;font-family:Segoe UI,system-ui,sans-serif}"
    ".fv-agent-tab-btn:hover{border-color:#3d8bfd}"
    ".fv-agent-tab-btn.active[data-atab='1']{background:#00363a;border-color:#00e5ff;color:#b2ebf2}"
    ".fv-agent-tab-btn.active[data-atab='2']{background:#3a1a3a;border-color:#e040fb;color:#f3c9ff}"
    ".fv-agent-tab-btn.active[data-atab='3']{background:#3a2b00;border-color:#ffab00;color:#ffe0b2}"
    ".fv-agent-tab-panel{display:none}"
    ".fv-agent-tab-panel.active{display:block}"
    "/* human validators DENTRO da caixa humana — compacto */"
    ".fv-human-box{position:relative}"
    ".fv-ctx-notes{margin:0 0 12px!important}"
    ".fv-human-hl-validators{margin:0 0 8px;padding:0;background:transparent;"
    "border:none;border-radius:0}"
    ".fv-human-hl-title{display:none}"
    ".fv-human-hl-help{color:#775;font-size:10px;margin:0 0 6px;line-height:1.3}"
    ".fv-human-hl-grid{display:flex;flex-direction:column;flex-wrap:nowrap;"
    "gap:4px;align-items:stretch;width:100%}"
    ".fv-human-hl-row{display:flex;flex-direction:row;flex-wrap:nowrap;"
    "align-items:center;gap:6px;width:100%}"
    ".fv-human-hl-row-label{font-size:10px;font-weight:700;min-width:5.5em;"
    "flex:0 0 auto;color:#c9a050}"
    ".fv-human-hl-row.sa .fv-human-hl-row-label{color:#ff8a80}"
    ".fv-human-hl-row.c1 .fv-human-hl-row-label{color:#4dd0e1}"
    ".fv-human-hl-row.c2 .fv-human-hl-row-label{color:#e77afc}"
    ".fv-human-hl-row.c3 .fv-human-hl-row-label{color:#ffb74d}"
    ".fv-human-hl-row .fv-agent-verdict{margin:0;gap:4px}"
    ".fv-human-hl-card{display:contents}"
    ".fv-human-hl-card-title{display:none}"
    ".fv-human-hl-card.has-validou .fv-human-hl-row-label,"
    ".fv-human-hl-row.has-validou .fv-human-hl-row-label{opacity:1}"
    "/* ficha + tabela + subabas do viewer unificado */"
    ".fv-ficha-summary{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 14px}"
    ".fv-sum-item{background:#10151f;border:1px solid #2a3344;border-radius:10px;"
    "padding:10px 14px;min-width:140px}"
    ".fv-sum-item span{display:block;color:#8b95a8;font-size:11px;margin-bottom:4px;"
    "letter-spacing:.02em}"
    ".fv-sum-item b{color:#f2f6ff;font-size:16px;font-weight:750}"
    ".fv-seg-table-wrap{margin:0 0 16px;border:1px solid #2a3344;border-radius:12px;"
    "overflow:auto;background:#0f1520}"
    ".fv-seg-table-title{padding:10px 14px;font-size:13px;font-weight:700;color:#7dffa8;"
    "background:#171e2b;border-bottom:1px solid #243044}"
    ".fv-seg-table{width:100%;border-collapse:collapse;font-size:12px}"
    ".fv-seg-table th{text-align:left;padding:8px 10px;color:#9ec9ff;background:#121820;"
    "border-bottom:1px solid #2a3344;white-space:nowrap;font-weight:700}"
    ".fv-seg-table td{padding:7px 10px;border-bottom:1px solid #1d2533;color:#d5deea;"
    "white-space:nowrap;vertical-align:middle}"
    ".fv-seg-table tr[hidden]{display:none!important}"
    ".fv-seg-table tr.fv-seg-item:hover td{background:#151c28}"
    ".fv-seg-table tr.fv-seg-item.open td{background:#152033}"
    ".fv-seg-table tr.fv-seg-detail:hover td{background:#0c1118}"
    ".fv-seg-table td.fv-muted{color:#8b95a8}"
    ".fv-seg-table th,.fv-seg-table td{text-align:left}"
    ".fv-seg-table th.fv-col-num,.fv-seg-table td.fv-col-num{"
    "font-variant-numeric:tabular-nums}"
    ".fv-seg-table th.fv-col-chev,.fv-seg-table td.fv-col-chev{"
    "width:22px;padding-left:12px;padding-right:4px}"
    ".fv-seg-item{cursor:pointer}"
    ".fv-seg-chev{display:inline-block;width:8px;height:8px;"
    "border-right:2px solid #5eb0ff;border-bottom:2px solid #5eb0ff;"
    "transform:rotate(-45deg);transition:transform .15s ease}"
    ".fv-seg-item.open .fv-seg-chev,.fv-seg-item[open] .fv-seg-chev{"
    "transform:rotate(45deg)}"
    ".fv-seg-id{display:inline-flex;min-width:28px;height:22px;align-items:center;"
    "justify-content:center;border-radius:7px;background:#1a2a3a;color:#bbdefb;"
    "font-weight:800}"
    ".fv-seg-item.open .fv-seg-id,.fv-seg-item[open] .fv-seg-id{"
    "background:#3d8bfd;color:#fff}"
    ".fv-seg-detail td{padding:0;white-space:normal;background:#0c1118;"
    "border-bottom:1px solid #243044}"
    ".fv-seg-body{padding:12px 14px 16px;display:flex;flex-direction:column;gap:12px;"
    "background:#0c1118}"
    ".fv-mini-block{background:#10151f;border:1px solid #2a3344;border-radius:10px;"
    "padding:10px}"
    ".fv-mini-title{color:#9ec9ff;font-size:12px;font-weight:700;margin:0 0 8px}"
    ".fv-panel-table{width:100%;border-collapse:collapse;font-size:12px}"
    ".fv-panel-table th{text-align:left;padding:6px 8px;color:#7dffa8;"
    "border-bottom:1px solid #2a3344}"
    ".fv-panel-table td{padding:6px 8px;border-bottom:1px solid #1d2533;color:#d5deea}"
    ".fv-mini-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));"
    "gap:8px}"
    ".fv-mini-field{background:#0f1520;border:1px solid #243044;border-radius:8px;"
    "padding:8px 10px}"
    ".fv-mini-field span{display:block;color:#8b95a8;font-size:10px;margin-bottom:3px}"
    ".fv-mini-field b{color:#f2f6ff;font-size:13px}"
    ".fv-seg-subtabs{display:flex;flex-wrap:wrap;gap:6px;align-items:center;"
    "margin:0 0 10px;padding:8px;background:#0f1520;border:1px solid #2a3344;"
    "border-radius:12px}"
    ".fv-seg-btn{min-height:32px;padding:6px 12px;border-radius:8px;cursor:pointer;"
    "font-weight:700;font-size:12px;border:1px solid #33506e;background:#121a28;"
    "color:#9ec9ff;font-family:Segoe UI,system-ui,sans-serif}"
    ".fv-seg-btn:hover{border-color:#3d8bfd}"
    ".fv-seg-btn.active{background:#1a2a3a;border-color:#64b5f6;color:#bbdefb}"
    ".fv-ctx-notes{margin:16px 0 0!important}"
    ".fv-pt-btn{position:absolute;top:6px;right:88px;background:#2a2a2a;"
    "color:#bbb;border:1px solid #444;padding:2px 10px;cursor:pointer;font-size:10px;"
    "border-radius:3px;z-index:20;font-family:Segoe UI,system-ui,sans-serif}"
    ".fv-pt-btn:hover{border-color:#4ade80;color:#bbf7d0}"
    ".fv-pt-btn.active{background:#052e1a;border-color:#4ade80;color:#bbf7d0}"
    ".fv-sa-ghost-btn{position:absolute;top:6px;right:170px;background:#2a2a2a;"
    "color:#bbb;border:1px solid #444;padding:2px 10px;cursor:pointer;font-size:10px;"
    "border-radius:3px;z-index:20;font-family:Segoe UI,system-ui,sans-serif}"
    ".fv-sa-ghost-btn:hover{border-color:#ff8a80;color:#ffe0e0}"
    ".fv-sa-ghost-btn.active{background:#3b1515;border-color:#ff8a80;color:#ffcdd2}"
    "[data-panzoom].fv-pt-mode{cursor:crosshair}"
    "[data-panzoom].fv-pt-mode .fv-pt-el{cursor:pointer}"
    "[data-panzoom].fv-pt-mode .fv-pt-el:hover line,"
    "[data-panzoom].fv-pt-mode .fv-pt-el:hover path,"
    "[data-panzoom].fv-pt-mode .fv-pt-el:hover text,"
    "[data-panzoom].fv-pt-mode .fv-pt-el:hover{filter:drop-shadow(0 0 0.6px #0ea5e9) drop-shadow(0 0 1.5px #0ea5e9)}"
    ".fv-pt-el.fv-pt-picked line,.fv-pt-el.fv-pt-picked path,.dxf-el.dxf-picked line,.dxf-el.dxf-picked path{"
    "stroke:#0ea5e9!important;stroke-width:1.6!important}"
    ".fv-pt-el.fv-pt-picked text,.dxf-el.dxf-picked text{fill:#0ea5e9!important}"
    ".fv-pt-el.fv-pt-picked,.dxf-el.dxf-picked{cursor:default}"
    ".fv-pt-el.fv-pt-picked,.fv-pt-el.fv-pt-picked *,"
    ".dxf-el.dxf-picked *{pointer-events:none!important}"
    ".click-dot{position:absolute;width:14px;height:14px;margin-left:-7px;margin-top:-7px;"
    "border-radius:50%;border:2px solid #fff;box-shadow:0 0 2px #000;pointer-events:none;z-index:18}"
    ".click-label{position:absolute;margin-left:9px;margin-top:-16px;font-size:11px;font-weight:700;"
    "color:#fff;text-shadow:0 0 3px #000,0 0 3px #000;pointer-events:none;font-family:monospace;z-index:18}"
    ".fv-points-help{color:#886;font-size:11px;margin:0 0 8px;line-height:1.35}"
    ".copy-all-points{background:#1f2937;color:#e5e7eb;border:1px solid #475569;border-radius:6px;"
    "padding:4px 10px;font-size:12px;cursor:pointer;font-family:Segoe UI,system-ui,sans-serif}"
    ".copy-all-points:hover{background:#334155}"
    ".copy-all-points[hidden]{display:none}"
    ".fv-points-list,.points-list{margin-top:8px;display:flex;flex-direction:column;gap:6px}"
    ".point-row{display:flex;gap:6px;align-items:center;font-size:12px}"
    ".point-row input{flex:1;background:#0b1220;color:#e5e7eb;border:1px solid #475569;"
    "border-radius:6px;padding:4px 6px;font:inherit}"
    ".point-row button{width:24px;background:#1f2937;color:#e5e7eb;border:1px solid #475569;"
    "border-radius:6px;cursor:pointer}"
    ".point-row .elem-tag{font-family:monospace;font-size:10px;color:#93c5fd;background:#1e293b;"
    "border-radius:4px;padding:1px 5px;white-space:nowrap}"
    ".point-row-removed{opacity:.75}"
    ".point-row-removed button{width:auto;padding:3px 8px;font-size:11px}"
    ".fv-human-tabs{display:flex;gap:6px;margin:0 0 10px;flex-wrap:wrap}"
    ".fv-human-tab-btn{min-height:32px;padding:6px 12px;border-radius:8px;cursor:pointer;"
    "font-weight:700;font-size:12px;border:1px solid #554400;background:#1a1a0a;color:#c9a050;"
    "font-family:Segoe UI,system-ui,sans-serif}"
    ".fv-human-tab-btn:hover{border-color:#f0b840}"
    ".fv-human-tab-btn.active{background:#3a2b00;border-color:#f0b840;color:#ffe0b2}"
    ".fv-human-tab-panel{display:none}"
    ".fv-human-tab-panel.active{display:block}"
    ".fv-layer-sa.fv-sa-ghost [data-fv-hl='face']{"
    "fill:none!important;fill-opacity:0!important;opacity:0!important}"
    ".fv-layer-sa.fv-sa-ghost [data-fv-hl='edge']{"
    "stroke-opacity:.38!important;opacity:.45!important}"
    ".fv-layer-sa.fv-sa-ghost path[style*='fill: #e53935'],"
    ".fv-layer-sa.fv-sa-ghost path[style*='fill: #ec407a']{"
    "fill:none!important;opacity:0!important}"
    ".fv-layer-sa.fv-sa-ghost path[style*='stroke: #ff1744'][style*='stroke-width: 0.5'],"
    ".fv-layer-sa.fv-sa-ghost path[style*='stroke: #f8bbd0'][style*='stroke-width: 0.5']{"
    "stroke-opacity:.38!important;opacity:.45!important}"
    ".fv-layer-n3 svg.fv-n3-svg{background:#0a0a0a}"
    ".fv-layer-n3 svg.fv-n3-svg:not([data-n3-composed]) path{"
    "vector-effect:non-scaling-stroke!important;stroke-width:1.4px!important}"
    ".fv-n3-tag,.fv-n3-dim{pointer-events:none}"
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


def agent_key_for_layer(base_key: str, layer: int) -> str:
    """aten_fv_ctx_agent_{base} → aten_fv_ctx_agent_c{layer}_{base}.

    ``base_key`` pode vir com ou sem o prefixo ``aten_fv_ctx_agent_``.
    Looping cego (camadas 1/2/3): cada camada é um veredito/anotação
    independente — camada N+1 julga a sugestão da camada N sem saber que
    está reavaliando (a evidência é redesenhada como se fosse o Destaque SA).
    """
    prefix = "aten_fv_ctx_agent_"
    base = base_key[len(prefix) :] if base_key.startswith(prefix) else base_key
    return f"{prefix}c{int(layer)}_{base}"


def agent_verdict_radios_html(
    agent_key: str,
    beam: str = "",
    *,
    layer: int = 1,
    label_ok: str = "Certo",
    label_bad: str = "X",
) -> str:
    """Radio Agente N: Certo | X — julga a ENTRADA (não a própria camada)."""
    vk = agent_verdict_key(agent_key)
    safe_vk = html_lib.escape(vk, quote=True)
    safe_beam = html_lib.escape(beam or "beam", quote=True)
    group = f"fv_agent_verdict_c{int(layer)}_{safe_beam}"
    lo = html_lib.escape(label_ok)
    lb = html_lib.escape(label_bad)
    return (
        f'<div class="fv-agent-verdict" role="radiogroup" '
        f'aria-label="Veredito Agente {int(layer)} {html_lib.escape(beam or "")}">'
        f'<label class="fv-verdict-opt validou">'
        f'<input type="radio" name="{group}" data-atkey="{safe_vk}" '
        f'data-role="agent-verdict" data-agent-n="{int(layer)}" value="validou" '
        f'onchange="onAgentVerdictChange(this)">'
        f'<span class="fv-radio-dot" aria-hidden="true"></span>'
        f"<span>{lo}</span></label>"
        f'<label class="fv-verdict-opt invalidou">'
        f'<input type="radio" name="{group}" data-atkey="{safe_vk}" '
        f'data-role="agent-verdict" data-agent-n="{int(layer)}" value="invalidou" '
        f'onchange="onAgentVerdictChange(this)">'
        f'<span class="fv-radio-dot" aria-hidden="true"></span>'
        f"<span>{lb}</span></label>"
        f"</div>"
        f'<div class="fv-agent-verdict-hint">'
        f"Agente {int(layer)}: Certo ou X sobre a entrada (com comentário obrigatório)."
        f"</div>"
    )


def agent_annotation_box_html(
    agent_key: str,
    beam: str,
    *,
    ta_css: str | None = None,
    layer: int = 1,
) -> str:
    """Caixa da anotação agêntica de UMA etapa.

    - Camada 1 / **Agente 1**: julga o **SA** (Certo/X) e gera C1 se X.
    - Camada 2 / **Agente 2**: julga a **C1** às cegas (Certo/X) e gera C2 se X.
    - Camada 3: **só geração** da sugestão final (sem veredito agêntico).
    """
    css = ta_css or (
        "width:100%;min-height:110px;background:#0d1520;color:#7ec8ff;"
        "border:1px solid #2a5080;border-radius:8px;padding:10px;"
        "font-family:Segoe UI,system-ui,monospace;font-size:13px;"
        "box-sizing:border-box;resize:vertical;line-height:1.4"
    )
    safe_key = html_lib.escape(agent_key, quote=True)
    safe_beam = html_lib.escape(beam)
    ly = int(layer)

    if ly >= 3:
        default_ph = (
            f"C3 (sugestão final): descreva a geometria proposta após A2 invalidar C2 — {safe_beam}"
        )
        return (
            f'<div class="fv-agent-box" data-layer="3" data-no-agent-verdict="1" '
            'style="background:#0a121c;border:1px solid #554400;'
            'border-radius:10px;padding:12px">'
            '<div style="color:#ffb74d;font-size:13px;font-weight:700;'
            f'margin-bottom:6px">🟠 C3 · sugestão final · {safe_beam}</div>'
            '<div style="color:#886;font-size:11px;margin-bottom:8px">'
            "Sem veredito agêntico. Só a geração da última proposta (depois que A2 "
            "invalidou C2). O humano valida a C3 no selo <b>H</b> da aba C3."
            "</div>"
            f'<textarea data-atkey="{safe_key}" data-atrole="agent" '
            f'data-placeholder-default="{html_lib.escape(default_ph, quote=True)}" '
            f'onblur="saveAtenTA(this)" '
            f'placeholder="{html_lib.escape(default_ph, quote=True)}" '
            f'style="{css}"></textarea></div>'
        )

    if ly == 1:
        title = f"🤖 Agente 1 — julga o SA · {safe_beam}"
        help_t = (
            "Agente 1 avalia o Destaque SA. <b>Certo</b> = SA ok. "
            "<b>X</b> = SA errado → gera proposta C1."
        )
        default_ph = "A1: por que o SA está Certo ou X (e o que C1 corrige)…"
        radio_ok, radio_bad = "A1 Certo (SA ok)", "A1 X (SA errado)"
    else:
        title = f"🤖 Agente 2 — julga a C1 (cego) · {safe_beam}"
        help_t = (
            "Agente 2 julga a sugestão C1 redesenhada como se fosse SA (looping cego). "
            "<b>Certo</b> = C1 ok. <b>X</b> = gera C2."
        )
        default_ph = "A2: por que a entrada (C1 disfarçada) está Certo ou X…"
        radio_ok, radio_bad = "A2 Certo", "A2 X"

    radios = agent_verdict_radios_html(
        agent_key, beam, layer=ly, label_ok=radio_ok, label_bad=radio_bad
    )
    return (
        f'<div class="fv-agent-box" data-layer="{ly}" '
        'style="background:#0a121c;border:1px solid #2a5080;'
        'border-radius:10px;padding:12px">'
        f'<div style="color:#7ec8ff;font-size:13px;font-weight:700;margin-bottom:6px">{title}</div>'
        f'<div style="color:#567;font-size:11px;margin-bottom:8px">{help_t}</div>'
        f"{radios}"
        f'<textarea data-atkey="{safe_key}" data-atrole="agent" '
        f'data-placeholder-default="{html_lib.escape(default_ph, quote=True)}" '
        f'onblur="saveAtenTA(this)" oninput="refreshAgentVerdictUI()" '
        f'placeholder="{html_lib.escape(default_ph, quote=True)}" '
        f'style="{css}"></textarea></div>'
    )


def agent_annotation_boxes_html(
    base_agent_key: str,
    beam: str,
    *,
    ta_css: str | None = None,
) -> str:
    """Mini-abas Agente 1 / Agente 2 / C3 final.

    - A1 julga **SA** (Certo/X) e gera desenho C1 se X.
    - A2 julga **C1** às cegas (Certo/X) e gera C2 se X.
    - C3 só **gera** a sugestão final (sem veredito agêntico).
    """
    tab_labels = {1: "🔵 Agente 1", 2: "🟣 Agente 2", 3: "🟠 C3 final"}
    tabs = "".join(
        f'<button type="button" class="fv-agent-tab-btn{" active" if layer == 1 else ""}" '
        f'data-atab="{layer}">{tab_labels[layer]}</button>'
        for layer in (1, 2, 3)
    )
    panels = "".join(
        f'<div class="fv-agent-tab-panel{" active" if layer == 1 else ""}" '
        f'data-atab-panel="{layer}">'
        + agent_annotation_box_html(
            agent_key_for_layer(base_agent_key, layer), beam, ta_css=ta_css, layer=layer
        )
        + "</div>"
        for layer in (1, 2, 3)
    )
    return (
        '<div class="fv-agent-tab-wrap">'
        f'<div class="fv-agent-tabs" role="tablist">{tabs}</div>'
        f"{panels}"
        "</div>"
    )




def human_hl_keys_from_human(human_key: str) -> tuple[str, str, str, str]:
    """aten_fv_ctx_human_BASE → (sa_key, c1_key, c2_key, c3_key) — validação
    humana do Destaque SA + de cada camada do looping cego agêntico."""
    prefix = "aten_fv_ctx_human_"
    if human_key.startswith(prefix):
        base = human_key[len(prefix) :]
    else:
        base = human_key
    return (
        f"aten_fv_hl_sa_human_{base}",
        f"aten_fv_hl_agent_c1_human_{base}",
        f"aten_fv_hl_agent_c2_human_{base}",
        f"aten_fv_hl_agent_c3_human_{base}",
    )


def human_hl_validators_html(human_key: str, beam: str = "") -> str:
    """Validadores humanos SA + Camada 1/2/3 (compacto, lado a lado)."""
    k_sa, k_c1, k_c2, k_c3 = human_hl_keys_from_human(human_key)
    safe_beam = html_lib.escape(beam or "beam", quote=True)

    def _row(kind: str, label: str, key: str, group: str) -> str:
        safe_key = html_lib.escape(key, quote=True)
        return (
            f'<div class="fv-human-hl-row {kind} fv-human-hl-card" data-hl-target="{kind}">'
            f'<span class="fv-human-hl-row-label">{label}</span>'
            f'<div class="fv-agent-verdict" role="radiogroup" '
            f'aria-label="{html_lib.escape(label)}">'
            f'<label class="fv-verdict-opt validou">'
            f'<input type="radio" name="{group}" data-atkey="{safe_key}" '
            f'data-role="human-hl-verdict" data-hl-target="{kind}" value="validou" '
            f'onchange="onHumanHlVerdictChange(this)">'
            f'<span class="fv-radio-dot" aria-hidden="true"></span>'
            f"<span>Validou</span></label>"
            f'<label class="fv-verdict-opt invalidou">'
            f'<input type="radio" name="{group}" data-atkey="{safe_key}" '
            f'data-role="human-hl-verdict" data-hl-target="{kind}" value="invalidou" '
            f'onchange="onHumanHlVerdictChange(this)">'
            f'<span class="fv-radio-dot" aria-hidden="true"></span>'
            f"<span>Invalidou</span></label>"
            f"</div></div>"
        )

    return (
        '<div class="fv-human-hl-validators" id="fv-human-hl-validators">'
        '<div class="fv-human-hl-help">'
        "Valide cada destaque (humano). Agêntico primeiro (por camada); depois alinhar motor SA."
        "</div>"
        '<div class="fv-human-hl-grid">'
        + _row("sa", "🔴 SA", k_sa, f"fv_hl_sa_human_{safe_beam}")
        + _row("c1", "🔵 Camada 1", k_c1, f"fv_hl_c1_human_{safe_beam}")
        + _row("c2", "🟣 Camada 2", k_c2, f"fv_hl_c2_human_{safe_beam}")
        + _row("c3", "🟠 Camada 3", k_c3, f"fv_hl_c3_human_{safe_beam}")
        + "</div></div>"
    )


def human_annotation_box_html(
    human_key: str,
    beam: str,
    *,
    legacy_key: str = "",
    ta_css: str | None = None,
) -> str:
    """Caixa humana = validadores SA/Agêntico (compactos) + textarea (como a agêntica)."""
    css = ta_css or (
        "width:100%;min-height:90px;background:#1a1a0a;color:#f0b840;"
        "border:1px solid #554400;border-radius:8px;padding:10px;"
        "font-family:Segoe UI,system-ui,monospace;font-size:13px;"
        "box-sizing:border-box;resize:vertical;line-height:1.4"
    )
    safe_key = html_lib.escape(human_key, quote=True)
    safe_beam = html_lib.escape(beam)
    leg = html_lib.escape(legacy_key or "", quote=True)
    leg_attr = f' data-atlegacy="{leg}"' if legacy_key else ""
    return (
        '<div class="fv-human-box" style="background:#14120a;border:1px solid #554400;'
        'border-radius:10px;padding:12px">'
        '<div style="color:#f0b840;font-size:13px;font-weight:700;'
        f'margin-bottom:8px">✏️ Anotação humana — contexto {safe_beam}</div>'
        '<div class="fv-human-tabs" role="tablist">'
        '<button type="button" class="fv-human-tab-btn active" data-htab="layers">'
        "SA / Camadas</button>"
        '<button type="button" class="fv-human-tab-btn" data-htab="points">'
        "Anotações Pontos</button>"
        "</div>"
        '<div class="fv-human-tab-panel active" data-htab-panel="layers">'
        '<div style="color:#886;font-size:11px;margin-bottom:6px">'
        "Revisor: validar destaques + dúvidas, erros e pedidos de fix."
        "</div>"
        f"{human_hl_validators_html(human_key, beam)}"
        f'<textarea data-atkey="{safe_key}" data-atrole="human"{leg_attr} '
        f'onblur="saveAtenTA(this)" '
        f'placeholder="Atenção / notas humanas sobre o contextual de {safe_beam}..." '
        f'style="{css}"></textarea>'
        "</div>"
        '<div class="fv-human-tab-panel" data-htab-panel="points">'
        '<div class="fv-points-help">'
        "Ative <b>Ponto</b> no viewer (ao lado de Reset zoom) e clique num "
        "elemento do desenho. O ponto segue o elemento no pan/zoom; a nota "
        "descreve exatamente aquele ponto."
        "</div>"
        '<div class="points-list-head">'
        '<button type="button" class="copy-all-points" hidden '
        'title="copiar referência de todos os pontos">📋 copiar todos os pontos</button>'
        "</div>"
        '<div class="fv-points-list points-list"></div>'
        "</div></div>"
    )


_SA_HL_FACE_RE = re.compile(
    r"(<(?:path|polygon)\b)(?![^>]*\bdata-fv-hl=)([^>]*?)"
    r'(style="fill: #(?:e53935|ec407a); opacity: 0\.38")',
    re.I,
)
_SA_HL_EDGE_RE = re.compile(
    r"(<(?:path|polygon)\b)(?![^>]*\bdata-fv-hl=)([^>]*?)"
    r'(style="fill: none; stroke: #(?:ff1744|f8bbd0); stroke-width: 0\.5;)',
    re.I,
)
_SA_HL_TAG_RE = re.compile(
    r"(<(?:path|polygon)\b)(?![^>]*\bdata-fv-hl=)([^>]*?)"
    r'(style="fill: #(?:b71c1c|ad1457); opacity: 0\.95;)',
    re.I,
)


def stamp_sa_highlight_attrs(markup: str) -> str:
    """Mark SA face / contour / tag paths so ghost CSS+JS can target them.

    Matplotlib inlines hex in ``style="..."``. Live DOM often canonicalizes
    that to ``rgb()``, so attribute selectors on the authored hex miss.
    """
    if not markup or "<path" not in markup:
        return markup

    def _insert(kind: str):
        def _sub(m: re.Match[str]) -> str:
            return f'{m.group(1)} data-fv-hl="{kind}"{m.group(2)}{m.group(3)}'

        return _sub

    markup = _SA_HL_FACE_RE.sub(_insert("face"), markup)
    markup = _SA_HL_EDGE_RE.sub(_insert("edge"), markup)
    markup = _SA_HL_TAG_RE.sub(_insert("tag"), markup)
    return markup


def sanitize_inline_svg(markup: str) -> str:
    """Strip XML decl / DOCTYPE so the SVG can live inside HTML.

    Also drop matplotlib ``clip-path`` when the matching ``clipPath`` rect
    lost ``width``/``height`` (a past sanitizer stripped those globally and
    the empty clip hides every CAD stroke — only the grey axes fill remains).
    """
    if not markup:
        return ""
    s = re.sub(r"<\?xml[^>]*\?>", "", markup, flags=re.I)
    s = re.sub(r"<!DOCTYPE[^>]*>", "", s, flags=re.I | re.S)
    i = s.find("<svg")
    if i < 0:
        return ""
    s = s[i:].strip()
    s = re.sub(r'(<svg\b[^>]*?)\s(width|height)="[^"]*"', r"\1", s, count=4)
    if _svg_has_broken_clip(s):
        s = re.sub(r'\sclip-path="[^"]*"', "", s)
    return s


def _svg_has_broken_clip(markup: str) -> bool:
    for m in re.finditer(
        r"<clipPath\b[^>]*>(.*?)</clipPath>", markup, flags=re.I | re.S
    ):
        inner = m.group(1)
        if "<rect" not in inner.lower():
            continue
        low = inner.lower()
        if "width=" not in low or "height=" not in low:
            return True
    return False


def _path_xy(d: str) -> tuple[list[float], list[float]]:
    vals = [
        float(tok)
        for tok in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", d)
    ]
    return vals[0::2], vals[1::2]


def repair_n3_inline_svg(markup: str) -> str:
    """Unclip broken matplotlib N3 SVGs and crop viewBox to the CAD strokes."""
    s = sanitize_inline_svg(markup)
    if "<svg" not in s:
        return s
    if 'data-n3-composed="1"' in s:
        return s
    xs: list[float] = []
    ys: list[float] = []
    for d in re.findall(r'<path\b[^>]*\bd="([^"]+)"', s, flags=re.I):
        px, py = _path_xy(d)
        if not px or not py:
            continue
        span_x = max(px) - min(px)
        span_y = max(py) - min(py)
        if span_x > 800 and span_y > 80:
            continue
        xs.extend(px)
        ys.extend(py)
    for m in re.finditer(
        r"<text\b[^>]*\bx=['\"]([^'\"]+)['\"][^>]*\by=['\"]([^'\"]+)['\"]",
        s,
        flags=re.I,
    ):
        try:
            xs.append(float(m.group(1)))
            ys.append(float(m.group(2)))
        except ValueError:
            continue
    if len(xs) < 4 or len(ys) < 4:
        return s
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    pad_x = max(6.0, span_x * 0.02)
    pad_y = max(8.0, span_y * 0.25)
    vb = (
        f"{min_x - pad_x:.3f} {min_y - pad_y:.3f} "
        f"{span_x + 2 * pad_x:.3f} {span_y + 2 * pad_y:.3f}"
    )
    if re.search(r'viewBox="[^"]*"', s):
        s = re.sub(r'viewBox="[^"]*"', f'viewBox="{vb}"', s, count=1)
    else:
        s = re.sub(r"<svg\b", f'<svg viewBox="{vb}"', s, count=1)
    s = re.sub(r"fill:\s*#212830\b", "fill:#0a0a0a", s)
    return s


def wrap_panzoom_viewer(
    cid: str,
    svg_markup: str,
    *,
    height_css: str | None = None,
    mode: str = "local",
    agent_svg: str = "",
    proposal_src: str = "",
    n3_svg: str = "",
    n3_src: str = "",
    seg_labels: Sequence[str] | None = None,
) -> str:
    """Wrap SVG in pan/zoom chrome. Contextual mode adds SA/agent/N3 toggle."""
    svg_markup = stamp_sa_highlight_attrs(svg_markup or "")
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
    ghost_btn = SA_GHOST_BTN_HTML if mode == "contextual" else ""
    pt_btn = PT_BTN_HTML
    if mode != "contextual":
        return (
            f'<div id="{safe_cid}" data-panzoom="1" style="{outer}">'
            f'<div id="{safe_cid}-inner" style="{INNER_STYLE}">{svg_markup or ""}</div>'
            f"{pt_btn}{btn}</div>"
        )

    # Contextual: SA + 3 camadas agênticas (looping cego) + N3 robô + toggle
    beam_guess = cid.replace("fvctx_", "")

    def _prop_src(layer: int) -> str:
        return proposal_src or f"propostas/{beam_guess}_qa_proposta_c{layer}.svg"

    def _agent_inner(layer: int) -> str:
        if layer == 1 and agent_svg:
            return agent_svg
        src = _prop_src(layer)
        return (
            f'<div class="fv-agent-status">Sem proposta da camada {layer} ainda.<br>'
            f'<span style="font-size:11px;opacity:.75">Arquivo esperado: {html_lib.escape(src)}</span></div>'
        )

    n3_path = n3_src or f"n3/{beam_guess}_n3.svg"
    n3_inner = repair_n3_inline_svg(n3_svg)
    n3_attrs = f' data-n3-src="{html_lib.escape(n3_path, quote=True)}"'
    if "<svg" not in n3_inner:
        n3_inner = (
            f'<div class="fv-agent-status">N3 (robô SA) ainda não materializado.<br>'
            f'<span style="font-size:11px;opacity:.75">Arquivo: {html_lib.escape(n3_path)}</span></div>'
        )

    toggle = (
        '<div class="fv-layer-toggle" id="fv-layer-toggle" role="toolbar" aria-label="Alternar destaques">'
        '<button type="button" class="fv-hl-btn active" data-hl="sa" title="Destaque SA (motor)">'
        '🔴 SA<span class="fv-tab-seals" data-seals="sa"></span></button>'
        '<button type="button" class="fv-hl-btn" data-hl="c1" title="Camada agêntica 1">'
        '🔵 C1<span class="fv-tab-seals" data-seals="c1"></span></button>'
        '<button type="button" class="fv-hl-btn" data-hl="c2" title="Camada agêntica 2">'
        '🟣 C2<span class="fv-tab-seals" data-seals="c2"></span></button>'
        '<button type="button" class="fv-hl-btn" data-hl="c3" title="Camada agêntica 3">'
        '🟠 C3<span class="fv-tab-seals" data-seals="c3"></span></button>'
        '<button type="button" class="fv-hl-btn" data-hl="n3" title="N3 robô SA (interpretação Fase-4/6)">'
        '🟦 N3</button>'
        '<span class="fv-hl-legend"><b class="sa">SA</b> vermelho/rosa · '
        '<b class="ag">QA</b> ciano/verde · <b class="n3">N3</b> robô</span></div>'
    )
    _labs = [str(x) for x in (seg_labels or []) if str(x).strip()]
    _seg_btns = [
        '<button type="button" class="fv-seg-btn active" data-seg="todos">Todos</button>'
    ]
    for lab in _labs:
        safe_lab = html_lib.escape(lab, quote=True)
        _seg_btns.append(
            f'<button type="button" class="fv-seg-btn" data-seg="{safe_lab}">'
            f"{html_lib.escape(lab)}</button>"
        )
    subtabs = (
        f'<div class="fv-seg-subtabs" data-for-layers="sa,n3" data-seg-count="{len(_labs)}">'
        f"{''.join(_seg_btns)}</div>"
    )
    layer_divs = "".join(
        f'<div class="fv-layer fv-layer-c{layer} fv-layer-hidden" data-visible="0" '
        f'data-proposal-src="{html_lib.escape(_prop_src(layer), quote=True)}">'
        f"{_agent_inner(layer)}</div>"
        for layer in (1, 2, 3)
    )
    n3_layer = (
        f'<div class="fv-layer fv-layer-n3 fv-layer-hidden" data-visible="0"{n3_attrs}>'
        f"{n3_inner}</div>"
    )
    layers = (
        f'<div data-ctx-layers="1" style="position:relative;width:100%;height:100%">'
        f'<div class="fv-layer fv-layer-sa" data-visible="1">{svg_markup or ""}</div>'
        f"{layer_divs}{n3_layer}"
        f"</div>"
    )
    return (
        f"{toggle}{subtabs}"
        f'<div id="{safe_cid}" data-panzoom="1" style="{outer}">'
        f'<div id="{safe_cid}-inner" style="{INNER_STYLE}">{layers}</div>'
        f"{ghost_btn}{pt_btn}{btn}</div>"
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


def _segs_are_vertical(segs: list[dict]) -> bool:
    """True se a maioria dos painéis é mais alta que larga (viga vertical)."""
    if not segs:
        return False
    votes = 0
    for s in segs:
        bb = s["bbox"]
        w = max(bb[2] - bb[0], 1e-6)
        h = max(bb[3] - bb[1], 1e-6)
        if h >= w * 1.15:
            votes += 1
        elif w >= h * 1.15:
            votes -= 1
    return votes > 0


def _view_envelope(
    segs: list[dict], mode: str
) -> tuple[float, float, float, float, float]:
    """Return vx0,vx1,vy0,vy1,view_h.

    Recorte **quadrado** centrado no conteúdo, lado = max(span+pad, tag room).
    Assim o viewer preenche a área (sem faixa preta retangular estreita).
    """
    bbs = [s["bbox"] for s in segs]
    xmin = min(b[0] for b in bbs)
    ymin = min(b[1] for b in bbs)
    xmax = max(b[2] for b in bbs)
    ymax = max(b[3] for b in bbs)
    span_x = max(xmax - xmin, 1.0)
    span_y = max(ymax - ymin, 1.0)
    vertical = _segs_are_vertical(segs)
    # margem de contexto simétrica (proporcional ao lado maior)
    major = max(span_x, span_y)
    if mode == "contextual":
        ctx_pad = max(120.0, major * 0.12, min(span_x, span_y) * 0.8)
    else:
        ctx_pad = max(80.0, major * 0.18, min(span_x, span_y) * 1.2)
    # espaço para tags (esquerda se vertical; acima se horizontal)
    tag_pad = (TAG_DX + 50.0) if vertical else (TAG_DY + 40.0)
    content_w = span_x + 2.0 * ctx_pad + (tag_pad if vertical else 0.0)
    content_h = span_y + 2.0 * ctx_pad + (0.0 if vertical else tag_pad)
    side = max(content_w, content_h, major + 2.0 * ctx_pad)
    cx = 0.5 * (xmin + xmax)
    cy = 0.5 * (ymin + ymax)
    # em vertical, desloca o centro um pouco à esquerda para caber a tag
    if vertical:
        cx = cx - tag_pad * 0.25
    else:
        cy = cy + tag_pad * 0.15
    half = side * 0.5
    vx0, vx1 = cx - half, cx + half
    vy0, vy1 = cy - half, cy + half
    return vx0, vx1, vy0, vy1, max(vy1 - vy0, 1.0)


def _agent_seg_colors(index: int) -> tuple[str, str, str, str]:
    """Ciano / verde claro (proposta QA)."""
    cyan = index % 2 == 0
    face = "#00e5ff" if cyan else "#69f0ae"
    edge = "#00b8d4" if cyan else "#00c853"
    tag_bg = "#006064" if cyan else "#1b5e20"
    tag_edge = face
    return face, edge, tag_bg, tag_edge


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
    highlight_mode: str = "sa",
    proposed_segments: Sequence[dict] | None = None,
    show_sa_ghost: bool = True,
    also_png_path: str | None = None,
) -> str:
    """Render HI-FI SVG markup (no XML decl). Empty string on failure.

    ``also_png_path``: se informado, salva TAMBÉM um PNG direto do matplotlib
    (mesma figura, antes de fechar) — mais confiável que SVG→cairosvg, que
    historicamente descartou o fundo estrutural (linhas/textos) silenciosamente
    e deixou só os polígonos de destaque. Usar sempre que o PNG for a evidência
    que um agente vai enxergar (looping cego).

    ``mode``:
      - ``local``: frame first/only segment neighborhood
      - ``contextual``: frame all segments, highlight every one

    ``highlight_mode``:
      - ``sa``: vermelho/rosa S# (motor)
      - ``agent``: mesmo DXF estrutural + proposta ciano/verde P#
      - ``both``: N1 fraco + proposta forte

    ``show_sa_ghost``: em ``highlight_mode="agent"``/``"both"``, desenha (ou
    não) o fundo vermelho/rosa com tags ``S#`` por trás da proposta. Usar
    ``False`` quando ``segments`` NÃO é o Destaque SA real (ex.: looping
    cego camada 2/3, onde ``segments`` é só a referência de enquadramento —
    a sugestão da camada anterior — e não deve ganhar tags ``S#`` que
    confundiriam com o motor).
    """
    segs = _normalize_segments(segments)
    prop_segs = _normalize_segments(proposed_segments or [])
    if not segs and not prop_segs:
        return ""
    mode = "contextual" if mode == "contextual" else "local"
    hl = (highlight_mode or "sa").lower()
    if hl not in ("sa", "agent", "both"):
        hl = "sa"
    frame_src = segs if segs else prop_segs
    if mode == "local":
        segs_draw = frame_src[:1]
        width = width or DEFAULT_LOC_W
        height = height or DEFAULT_LOC_H
        default_aria = f"N1 / SA local · Seg {segs_draw[0]['label']}"
        default_alt = "N1 / SA local"
    else:
        segs_draw = frame_src
        width = width or DEFAULT_CTX_W
        height = height or DEFAULT_CTX_H
        if hl == "sa":
            default_aria = f"N1 / SA contextual · {len(segs_draw)} segmentos"
            default_alt = "N1 / SA contextual"
        else:
            n_p = len(prop_segs) if prop_segs else len(segs_draw)
            default_aria = f"QA proposta · {n_p} painéis · HI-FI estrutural"
            default_alt = "QA proposta agêntica HI-FI"
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

        # Highlights + tags (SA vermelho/rosa e/ou proposta ciano/verde)
        def _draw_hl(items, *, palette: str, tag_prefix: str, alpha_face: float, z0: int):
            for i, s in enumerate(items):
                if palette == "agent":
                    face, edge, tag_bg, tag_edge = _agent_seg_colors(i)
                else:
                    face, edge, tag_bg, tag_edge = _seg_colors(int(s.get("index", i)))
                ax.add_patch(
                    MplPolygon(
                        s["poly"],
                        closed=True,
                        fill=True,
                        facecolor=face,
                        edgecolor="none",
                        lw=0,
                        alpha=alpha_face,
                        zorder=z0,
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
                        zorder=z0 + 1,
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
                    zorder=z0 + 2,
                )
                lab = str(s["label"])
                if tag_prefix and not lab.upper().startswith(tag_prefix):
                    # pure number -> P1 / S1
                    if lab.isdigit():
                        lab = f"{tag_prefix}{lab}"
                    else:
                        lab = f"{tag_prefix}{lab}"
                text = lab if tag_prefix else f"S{s['label']}"
                bb = s["bbox"]
                seg_w = max(bb[2] - bb[0], 1e-6)
                seg_h = max(bb[3] - bb[1], 1e-6)
                is_vert = seg_h >= seg_w * 1.15
                if is_vert:
                    # tag à ESQUERDA e menor — não cobrir a faixa vertical
                    tag_xy = (cx - TAG_DX, cy)
                    tag_ha, tag_va = "right", "center"
                    tag_fs = TAG_FS_V
                    mut = 7
                    pad = 0.18
                else:
                    tag_xy = (cx, cy + TAG_DY)
                    tag_ha, tag_va = "center", "bottom"
                    tag_fs = TAG_FS_H
                    mut = 9
                    pad = 0.28
                ax.annotate(
                    text,
                    xy=(cx, cy),
                    xytext=tag_xy,
                    color="#ffffff",
                    fontsize=tag_fs,
                    fontweight="bold",
                    ha=tag_ha,
                    va=tag_va,
                    zorder=z0 + 2,
                    bbox=dict(
                        boxstyle=f"round,pad={pad}",
                        facecolor=tag_bg,
                        edgecolor=tag_edge,
                        linewidth=0.9 if is_vert else 1.0,
                        alpha=0.95,
                    ),
                    arrowprops=dict(
                        arrowstyle="-|>",
                        color=edge,
                        lw=0.65 if is_vert else 0.7,
                        mutation_scale=mut,
                        shrinkA=2,
                        shrinkB=2,
                        connectionstyle="arc3,rad=0",
                    ),
                )

        if hl == "sa":
            _draw_hl(segs_draw, palette="sa", tag_prefix="S", alpha_face=0.38, z0=8)
        elif hl == "agent":
            # N1 motor fraco (se houver) + proposta forte
            if segs and show_sa_ghost:
                _draw_hl(segs, palette="sa", tag_prefix="S", alpha_face=0.12, z0=7)
            use = prop_segs if prop_segs else segs_draw
            _draw_hl(use, palette="agent", tag_prefix="P", alpha_face=0.42, z0=9)
        else:  # both
            if segs and show_sa_ghost:
                _draw_hl(segs, palette="sa", tag_prefix="S", alpha_face=0.18, z0=7)
            use = prop_segs if prop_segs else segs_draw
            _draw_hl(use, palette="agent", tag_prefix="P", alpha_face=0.42, z0=9)

        if also_png_path:
            try:
                fig.savefig(also_png_path, format="png", facecolor=BG, dpi=dpi, pad_inches=0)
            except Exception as exc:
                print(f"[render] PNG direto falhou: {exc}", flush=True)
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
    return stamp_sa_highlight_attrs(svg.strip())



def render_fv_hifi_proposal_svg(
    dxf_data: dict | None,
    proposed_segments: Sequence[dict],
    n1_segments: Sequence[dict] | None = None,
    *,
    mode: str = "contextual",
    width: int | None = None,
    height: int | None = None,
    dpi: int = DEFAULT_DPI,
    show_n1_ghost: bool = True,
) -> str:
    """Mesmo HI-FI estrutural do SA + destaques ciano/verde da proposta QA.

    ``show_n1_ghost=False``: usar quando ``n1_segments`` NÃO é o Destaque SA
    real (looping cego camada 2/3 — ``n1_segments`` é só a sugestão da
    camada anterior, usada apenas para enquadrar a view, sem ganhar tags
    ``S#`` que confundiriam com o motor).
    """
    n1 = list(n1_segments or [])
    prop = list(proposed_segments or [])
    # frame com N1 se existir (alinha com Destaque SA); senão proposta
    frame = n1 if n1 else prop
    return render_fv_hifi_n1_svg(
        dxf_data,
        frame,
        mode=mode,
        width=width,
        height=height,
        dpi=dpi,
        highlight_mode="agent",
        proposed_segments=prop,
        show_sa_ghost=show_n1_ghost,
        aria_label=f"QA proposta agêntica · {len(prop) or len(frame)} painéis · HI-FI",
        alt="QA proposta agêntica HI-FI estrutural",
    )
