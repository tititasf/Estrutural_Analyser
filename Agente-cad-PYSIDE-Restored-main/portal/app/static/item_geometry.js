(function () {
  'use strict';
  var root = document.getElementById('drill-root');
  if (!root) return;
  var obra = root.dataset.obra, target = null, pending = null, selection = null;
  function pav() { return (window.DrillGrade && window.DrillGrade.state.pav) || new URLSearchParams(location.search).get('pavimento'); }
  function endpoint(t, suffix) {
    return '/obras/' + encodeURIComponent(obra) + '/itens/' + encodeURIComponent(t.classe) + '/' +
      encodeURIComponent(t.itemId) + (suffix || '') + '?pavimento=' + encodeURIComponent(t.pavimento || pav());
  }
  function api(url, method, body) {
    return fetch(url, {method:method || 'GET',headers:{'Content-Type':'application/json'},
      body:body === undefined ? undefined : JSON.stringify(body)}).then(function (r) {
      return r.json().then(function (data) {
        if (!r.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Falha na operação (' + r.status + ')');
        return data;
      });
    });
  }
  function beamClass(c) { return c === 'fundo' || c.indexOf('lateral_') === 0; }
  function beamName(i) { return i.beam_name || String(i.titulo || '').replace(/\s*\(segmento.*$/i,''); }
  function segment(i) { return i.segmento || (i.campos && (i.campos.Segmento || i.campos.segmento)) || ''; }
  function reload(t, deleted) {
    var u = new URL(location.href);
    u.searchParams.set('pavimento',t.pavimento || pav()); u.searchParams.set('etapa','sa');
    var c=t.classe, id=t.itemId;
    if (c.indexOf('lateral_') === 0) {
      var side=c.indexOf('lateral_b_') === 0 ? 'B' : 'A';
      c='laterais_' + c.split('_').pop(); id=side+'::'+id;
    }
    u.searchParams.set('classe',c);
    ['item','viga','segmento','vista','subvista'].forEach(function (k) {u.searchParams.delete(k);});
    if (!deleted) {
      u.searchParams.set('item',id);
      if (t.beam) u.searchParams.set('viga',t.beam);
      if (t.segmento) u.searchParams.set('segmento',t.segmento);
    }
    location.assign(u.href);
  }
  function save(t, points) { return api(endpoint(t,'/geometria'),'PUT',{points:points}); }
  function remove(t, whole) { return api(endpoint(t)+(whole ? '&inteiro=true' : ''),'DELETE'); }
  function deleteItem(t, whole) {
    if (!t || !t.itemId) return;
    if (!confirm(whole ? 'Excluir a viga '+(t.beam || t.itemId)+' e todos os seus segmentos desta ficha?' :
      'Excluir '+(t.beam ? 'o segmento '+(t.segmento || '')+' de '+t.beam : 'o item '+t.itemId)+'?')) return;
    remove(t,whole).then(function () {reload(t,true);}).catch(function (e) {alert(e.message);});
  }
  function open(t) {
    pending=Object.assign({pavimento:pav()},t); target=null;
    window.DrillGrade.openTorreCriar(t.classe,t.beam || '');
  }
  function wire(container) {
    var cls=document.getElementById('criar-item-classe'), items=document.getElementById('criar-item-existente');
    if (!items || items.dataset.geometryWired) return;
    items.dataset.geometryWired='1';
    var segs=document.getElementById('editar-item-segmento'), name=document.getElementById('criar-item-nome');
    var redraw=document.getElementById('btn-item-redesenhar'), del=document.getElementById('btn-item-excluir');
    var delSeg=document.getElementById('btn-segmento-excluir'), cancel=document.getElementById('btn-item-cancelar');
    var saveButton=document.getElementById('btn-criar-item-salvar'), chk=document.getElementById('chk-criar-item-geo');
    var status=document.getElementById('criar-item-status'), rows=[], generation=0, loading=false;
    function option(value,text) {var o=document.createElement('option');o.value=value;o.textContent=text;return o;}
    function clearDrawing() {
      window._polyGeoms=[];window._polyAtual=[];window._polyHover=null;
      if(window.redesenharPolylines) window.redesenharPolylines(container);
    }
    function stop() {
      target=null;cancel.hidden=true;saveButton.textContent='Criar item →';
      clearDrawing();chk.checked=false;chk.dispatchEvent(new Event('change'));
    }
    function chooseSegment() {
      var row=rows.find(function (i) {return i.item_id===segs.value;});
      if(!beamClass(cls.value)) row=rows.find(function (i) {return i.item_id===items.value;});
      selection=row ? {classe:cls.value,itemId:row.item_id,beam:beamClass(cls.value)?beamName(row):null,
        segmento:segment(row),pavimento:pav()} : null;
      redraw.disabled=!selection;del.disabled=!selection;delSeg.disabled=!selection;
      if(selection) {
        name.value=selection.beam || (row.nome || row.titulo || row.item_id);
        var st=window.DrillGrade.state; st.itemId=selection.itemId;st.vigaKey=selection.beam || null;
      }
    }
    function chooseItem() {
      if(target) stop();
      var isBeam=beamClass(cls.value);segs.hidden=!isBeam;delSeg.hidden=!isBeam;
      segs.replaceChildren();
      if(isBeam) {
        rows.filter(function (i) {return beamName(i)===items.value;}).sort(function(a,b){return Number(segment(a))-Number(segment(b));})
          .forEach(function (i) {segs.appendChild(option(i.item_id,'S'+segment(i)));});
      }
      chooseSegment();
    }
    function begin() {
      if(!selection) return;
      target=Object.assign({},selection);clearDrawing();
      cancel.hidden=false;saveButton.textContent='Salvar geometria';
      var detail=document.getElementById('criar-item-coll');if(detail) detail.open=true;
      chk.checked=true;chk.dispatchEvent(new Event('change'));
      document.getElementById('criar-item-seg-wrap').hidden=true;
      status.textContent='Redesenhando '+(target.beam ? target.beam+' · S'+target.segmento : target.itemId)+
        ' · marque pelo menos 3 pontos; Enter fecha; Salvar geometria confirma.';
    }
    function loadItems() {
      stop(); selection=null;loading=true;var seq=++generation, c=cls.value;
      redraw.disabled=del.disabled=delSeg.disabled=true;items.disabled=true;
      items.replaceChildren(option('','Carregando itens…'));
      segs.hidden=!beamClass(c);delSeg.hidden=!beamClass(c);
      api('/obras/'+encodeURIComponent(obra)+'/n1/'+encodeURIComponent(c)+'?pavimento='+encodeURIComponent(pav()))
        .then(function(data){
          if(seq!==generation) return;
          rows=data.itens || []; items.replaceChildren(option('','Itens já populados'));
          var seen={};rows.forEach(function(i){var key=beamClass(c)?beamName(i):i.item_id;
            if(!seen[key]) {seen[key]=true;items.appendChild(option(key,beamClass(c)?key:(i.titulo || i.item_id)));}});
          items.disabled=false;loading=false;
          if(pending && pending.classe===c) {
            var desired=pending;pending=null;
            var row=rows.find(function(i){return i.item_id===desired.itemId;});
            if(!row) {status.textContent='Item não encontrado nesta classe/pavimento.';return;}
            items.value=beamClass(c)?beamName(row):row.item_id;chooseItem();
            if(beamClass(c)) {segs.value=row.item_id;chooseSegment();}
            begin();
          } else chooseItem();
        }).catch(function(e){if(seq===generation){loading=false;status.textContent=e.message;items.replaceChildren(option('','Falha ao listar itens'));}});
    }
    cls.addEventListener('change',loadItems);
    items.addEventListener('change',chooseItem);
    segs.addEventListener('change',function(){if(target)stop();chooseSegment();});
    redraw.addEventListener('click',begin);
    cancel.addEventListener('click',function(){stop();status.textContent='Edição cancelada.';});
    del.addEventListener('click',function(){if(selection){var t=Object.assign({},selection);if(beamClass(t.classe))t.itemId=t.beam;deleteItem(t,beamClass(t.classe));}});
    delSeg.addEventListener('click',function(){deleteItem(selection,false);});
    saveButton.addEventListener('click',function(e){
      if(!target) return;
      e.preventDefault();e.stopImmediatePropagation();
      if(window._polyAtual && window._polyAtual.length>=3) window.fecharPolylineAtual();
      var geom=window._polyGeoms && window._polyGeoms[0];
      if(!geom || geom.points.length<3) {status.textContent='Marque pelo menos 3 pontos para formar o contorno.';return;}
      var overlay=container.querySelector('.destaque-overlay'), bbox=overlay && JSON.parse(overlay.getAttribute('data-bbox-dxf') || 'null');
      var vb=overlay && (overlay.dataset.homeVb || '').split(/\s+/).map(Number);
      if(!bbox || !vb || !vb[2] || !vb[3]) {status.textContent='Transformação do estrutural não disponível. Aguarde o desenho carregar.';return;}
      var pts=geom.points.map(function(p){return [bbox[0]+(p.x-vb[0])/vb[2]*(bbox[2]-bbox[0]),bbox[3]-(p.y-vb[1])/vb[3]*(bbox[3]-bbox[1])];});
      saveButton.disabled=true;status.textContent='Salvando geometria…';
      save(target,pts).then(function(){reload(target,false);}).catch(function(err){saveButton.disabled=false;status.textContent=err.message;});
    },true);
    if(pending) cls.value=pending.classe;
    loadItems();
  }
  function pillarTarget() {
    var st=window.DrillGrade.state;
    return {classe:st.classe,itemId:st.itemId,pavimento:st.pav};
  }
  function interpret(t,button) {
    button.disabled=true;var original=button.textContent;button.textContent='Solicitando interpretação SA…';
    api(endpoint(t,'/interpretar-sa'),'POST').then(function(job){
      function poll() {
        api('/jobs/'+encodeURIComponent(job.job_id)).then(function(j){
          var state=j.status || j.estado;
          if(['na_fila','queued','executando','running','rodando'].indexOf(state)>=0){button.textContent='Interpretando este item…';setTimeout(poll,2500);}
          else if(['concluido','completed','done','sucesso'].indexOf(state)>=0) reload(t,false);
          else {button.disabled=false;button.textContent=original;alert(j.erro_msg || 'Interpretação não concluída: '+state);}
        }).catch(failed);
      }
      poll();
    }).catch(failed);
    function failed(e){button.disabled=false;button.textContent=original;alert(e.message);}
  }
  window.ItemGeometry={open:open,delete:deleteItem,remove:remove,save:save,isEditing:function(){return !!target;}};
  var oldWire=window.wireCriarItemPanel;
  window.wireCriarItemPanel=function(container,id){oldWire(container,id);wire(container);};
  document.addEventListener('click',function(e){
    var b=e.target.closest('button');if(!b)return;
    if(b.matches('[data-pillar-geometry]')) open(pillarTarget());
    if(b.matches('[data-pillar-interpret]')) interpret(pillarTarget(),b);
  });
  var oldAction=window.acaoFichaItem;
  window.acaoFichaItem=function(id,action){
    if(action==='excluir'){var t=pillarTarget();t.itemId=id;deleteItem(t,false);}
    else return oldAction.apply(this,arguments);
  };
})();
