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
  function pointsToDxf(points,bbox,vb) {
    return points.map(function(p){return [bbox[0]+(p.x-vb[0])/vb[2]*(bbox[2]-bbox[0]),
      bbox[3]-(p.y-vb[1])/vb[3]*(bbox[3]-bbox[1])];});
  }
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
    if (!deleted && !t.structural) {
      u.searchParams.set('item',id);
      if (t.beam) u.searchParams.set('viga',t.beam);
      if (t.segmento) u.searchParams.set('segmento',t.segmento);
    }
    location.assign(u.href);
  }
  function save(t, points) { return api(endpoint(t,'/geometria'),'PUT',{points:points}); }
  function remove(t, whole, comment) { return api(endpoint(t)+(whole ? '&inteiro=true' : ''),'DELETE',
    t.classe==='cortes_interpretados' ? {comentario:comment || ''} : undefined); }
  var deletionDialog = null;
  var refreshDeleted = null;
  function deleteItem(t, whole) {
    if (!t || !t.itemId || deletionDialog) return;
    // Native confirm can be suppressed by embedded browsers. Keep confirmation
    // and request feedback inside the page, without silently cancelling a click.
    t=Object.assign({},t);
    var previousFocus=document.activeElement;
    var backdrop=document.createElement('div'), box=document.createElement('section');
    backdrop.dataset.itemDeleteDialog='';
    backdrop.style.cssText='position:fixed;inset:0;z-index:100000;background:#0008;display:grid;place-items:center;padding:24px';
    box.setAttribute('role','dialog');box.setAttribute('aria-modal','true');
    box.setAttribute('aria-label','Confirmar exclusão');
    box.style.cssText='background:white;color:#172033;border-radius:12px;padding:24px;max-width:480px;width:100%;box-shadow:0 12px 48px #0005';
    var message=document.createElement('p'), status=document.createElement('p');
    message.textContent=whole ? 'Excluir a viga '+(t.beam || t.itemId)+' e todos os seus segmentos desta ficha?' :
      'Excluir '+(t.beam ? 'o segmento '+(t.segmento || '')+' de '+t.beam : 'o item '+t.itemId)+'?';
    status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    var comment=null;
    if(t.classe==='cortes_interpretados') {
      var label=document.createElement('label');label.textContent='Comentário (opcional)';
      comment=document.createElement('textarea');comment.maxLength=4000;comment.rows=3;
      comment.style.cssText='display:block;width:100%;box-sizing:border-box;margin:8px 0 12px';
      comment.placeholder='Explique o motivo da exclusão para o apontamento';
      label.append(comment);box.append(message,label);
    } else box.append(message);
    var cancel=document.createElement('button'), accept=document.createElement('button'), busy=false, persisted=false;
    cancel.type=accept.type='button';cancel.textContent='Cancelar';accept.textContent='Confirmar exclusão';
    cancel.style.cssText='padding:10px 16px;margin-right:12px';
    accept.style.cssText='padding:10px 16px;background:#b91c1c;color:white;border:0;border-radius:6px';
    function close() {
      if(busy) return;
      document.removeEventListener('keydown',onKey);
      backdrop.remove();deletionDialog=null;
      if(previousFocus && previousFocus.isConnected) previousFocus.focus();
    }
    function onKey(e) {
      if(e.key==='Escape'){e.preventDefault();close();}
      if(e.key==='Tab') {
        e.preventDefault();if(busy)return;
        var controls=(comment ? [comment,cancel,accept] : [cancel,accept]);
        var current=controls.indexOf(document.activeElement);
        controls[(current+(e.shiftKey ? controls.length-1 : 1)+controls.length)%controls.length].focus();
      }
    }
    cancel.addEventListener('click',close);
    accept.addEventListener('click',function(){
      if(busy)return;busy=true;cancel.disabled=accept.disabled=true;
      status.textContent=persisted ? '75% · Atualizando a tela…' : '25% · Excluindo… aguarde a confirmação do servidor.';
      if(comment)comment.disabled=true;
      (persisted ? Promise.resolve() : remove(t,whole,comment && comment.value)).then(function(){
        persisted=true;
        status.textContent='75% · Excluído. Atualizando a lista e o desenho…';
        if(!refreshDeleted) throw new Error('Atualização dinâmica indisponível.');
        return refreshDeleted(t,whole);
      }).then(function(){
        busy=false;close();
      }).catch(function(e){
        busy=false;cancel.disabled=accept.disabled=false;
        if(comment)comment.disabled=persisted;
        status.textContent=(persisted ? 'Já excluído no servidor; falha ao atualizar a tela: ' : 'Não foi possível excluir: ')+e.message;
        accept.textContent=persisted ? 'Atualizar tela' : 'Confirmar exclusão';
        accept.focus();
      });
    });
    box.append(status,cancel,accept);backdrop.append(box);document.body.append(backdrop);
    deletionDialog=backdrop;document.addEventListener('keydown',onKey);cancel.focus();
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
    var validate=document.getElementById('btn-corte-validar');
    var status=document.getElementById('criar-item-status'), rows=[], generation=0, loading=false;
    var cutFields=document.createElement('fieldset'), cutValues=null, cutSequence=0;
    cutFields.hidden=true;cutFields.style.cssText='display:none;gap:12px;flex-wrap:wrap;margin:12px 0';
    status.before(cutFields);
    function showCutFields() {
      var sequence=++cutSequence;cutFields.replaceChildren();cutFields.hidden=true;cutFields.style.display='none';cutValues=null;
      if(!selection || selection.classe!=='cortes')return;
      var t=Object.assign({},selection);
      api(endpoint(t,'/dados-edicao')).then(function(data){
        if(sequence!==cutSequence)return;
        if(!data.editable_fields)return;
        cutValues=data.fields;var legend=document.createElement('legend');legend.textContent='Medidas e lajes do corte original';cutFields.append(legend);
        var schema=[['beam_name','Viga'],['beam_w','Largura da viga (cm)'],['beam_h','Altura da viga (cm)'],
          ['own_laje','Laje própria'],['neigh_laje','Laje vizinha'],['own_slab_height','Espessura própria (cm)'],
          ['own_dist_top','Rebaixo próprio (cm)'],['neigh_slab_height','Espessura vizinha (cm)'],['neighbor_dist_top','Rebaixo vizinho (cm)']];
        schema.forEach(function(field){var label=document.createElement('label'),input=document.createElement('input');
          label.textContent=field[1]+' ';input.dataset.cutField=field[0];input.value=cutValues[field[0]]==null?(cutValues.ficha[field[0]]==null?'':cutValues.ficha[field[0]]):cutValues[field[0]];
          input.style.width='110px';label.append(input);cutFields.append(label);});
        var button=document.createElement('button');button.type='button';button.textContent='Salvar medidas do corte';cutFields.append(button);
        button.addEventListener('click',function(){
          var fields=JSON.parse(JSON.stringify(cutValues)),numeric=['beam_w','beam_h','own_slab_height','own_dist_top','neigh_slab_height','neighbor_dist_top'];
          try {
            cutFields.querySelectorAll('input').forEach(function(input){var key=input.dataset.cutField,value=input.value.trim();
              if(numeric.indexOf(key)>=0){if(!value)return;value=Number(value.replace(',','.'));if(!Number.isFinite(value))throw new Error('Informe medidas numéricas.');}
              if(['beam_name','beam_w','beam_h','own_laje','neigh_laje'].indexOf(key)>=0)fields[key]=value;else fields.ficha[key]=value;});
            fields.ficha.beam_height=fields.beam_h;fields.ficha.beam_bottom_dim=fields.beam_w;fields.ficha.beam_name=fields.beam_name;
            var direction=String(fields.ficha.direction || '').toLowerCase();
            var ownSide=['norte','leste','east','north'].indexOf(direction)>=0?'a':
              ['sul','oeste','south','west'].indexOf(direction)>=0?'b':
              (cutValues.own_laje===cutValues.ficha.side_a_laje_name?'a':'b');
            var otherSide=ownSide==='a'?'b':'a';
            fields.ficha['side_'+ownSide+'_laje_name']=fields.own_laje;
            fields.ficha['side_'+otherSide+'_laje_name']=fields.neigh_laje;
            fields.ficha['side_'+ownSide+'_laje_height']=fields.ficha.own_slab_height;
            fields.ficha['side_'+otherSide+'_laje_height']=fields.ficha.neigh_slab_height;
            fields.ficha['beam_lajes_side_'+ownSide]=fields.own_laje?'1':'0';
            fields.ficha['beam_lajes_side_'+otherSide]=fields.neigh_laje?'1':'0';
            ['own','neighbor'].forEach(function(prefix){var height=fields.ficha[prefix==='own'?'own_slab_height':'neigh_slab_height'];
              if(height!=null)fields.ficha[prefix+'_dist_bottom']=Number(fields.beam_h)-Number(fields.ficha[prefix+'_dist_top'])-Number(height);});
            button.disabled=true;status.textContent='Salvando correção e comparação antes/depois…';
            api(endpoint(t,'/geometria'),'PUT',{fields:fields}).then(function(){return container._refreshDestaques('cortes');})
              .then(function(){status.textContent='Medidas salvas · comparação disponível em Ver apontamentos.';showCutFields();})
              .catch(function(e){status.textContent=e.message;}).finally(function(){button.disabled=false;});
          } catch(e){status.textContent=e.message;}
        });
        cutFields.hidden=false;cutFields.style.display='flex';
      }).catch(function(e){if(sequence===cutSequence)status.textContent=e.message;});
    }
    function option(value,text) {var o=document.createElement('option');o.value=value;o.textContent=text;return o;}
    function clearDrawing() {
      window._polyGeoms=[];window._polyAtual=[];window._polyHover=null;
      var segmentList=document.getElementById('criar-item-seg-lista');
      if(segmentList){segmentList.replaceChildren();segmentList.hidden=true;}
      if(window.redesenharPolylines) window.redesenharPolylines(container);
    }
    function stop() {
      target=null;cancel.hidden=true;saveButton.textContent='Criar item →';
      clearDrawing();chk.checked=false;chk.dispatchEvent(new Event('change'));
      var segWrap=document.getElementById('criar-item-seg-wrap');
      if(segWrap) segWrap.hidden=!beamClass(cls.value);
      if(container._renderDestaques) container._renderDestaques();
    }
    function chooseSegment() {
      var row=rows.find(function (i) {return i.item_id===segs.value;});
      if(!beamClass(cls.value)) row=rows.find(function (i) {return i.item_id===items.value;});
      selection=row ? {classe:cls.value,itemId:row.item_id,beam:beamClass(cls.value)?beamName(row):null,
        segmento:segment(row),pavimento:pav(),structural:true} : null;
      redraw.disabled=!selection;del.disabled=!selection;delSeg.disabled=!selection;
      var interpreted=cls.value==='cortes_interpretados';
      redraw.hidden=interpreted;saveButton.hidden=interpreted;chk.disabled=interpreted;
      validate.hidden=!interpreted;validate.disabled=!selection;
      showCutFields();
      if(selection) {
        name.value=selection.beam || (row.nome || row.titulo || row.item_id);
        if(container._selectDestaqueClass) container._selectDestaqueClass(selection.classe);
      }
      if(container._renderDestaques) container._renderDestaques();
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
      if(!selection || selection.classe==='cortes_interpretados') return;
      target=Object.assign({},selection);clearDrawing();
      if(container._renderDestaques) container._renderDestaques();
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
      return api('/obras/'+encodeURIComponent(obra)+(c==='cortes_interpretados'?'/cortes-interpretados':'/n1/'+encodeURIComponent(c))+'?pavimento='+encodeURIComponent(pav()))
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
            if(c!=='cortes_interpretados') begin();
          } else chooseItem();
        }).catch(function(e){if(seq===generation){loading=false;status.textContent=e.message;items.replaceChildren(option('','Falha ao listar itens'));}});
    }
    refreshDeleted=function(deletedTarget,whole) {
      if(!container.isConnected || !container._refreshDestaques)
        return Promise.reject(new Error('Viewer não disponível. Abra o estrutural novamente.'));
      var priorItem=items.value, priorSegment=segs.value;
      pending=null;stop();selection=null;
      return container._refreshDestaques(deletedTarget.classe).then(function(){
        if(window._criarItemItensPorClasse) delete window._criarItemItensPorClasse[deletedTarget.classe];
        return loadItems();
      }).then(function(){
        if(loading || items.disabled) throw new Error('Não foi possível atualizar os segmentos.');
        if(Array.from(items.options).some(function(o){return o.value===priorItem;})) {
          items.value=priorItem;chooseItem();
          if(Array.from(segs.options).some(function(o){return o.value===priorSegment;})) {
            segs.value=priorSegment;chooseSegment();
          }
        }
        window._criarItemItensPorClasse=window._criarItemItensPorClasse || {};
        var freshRows=rows.slice();freshRows._loaded=true;
        window._criarItemItensPorClasse[cls.value]=freshRows;
        var nextSegment=document.getElementById('criar-item-segmento');
        if(nextSegment)nextSegment.value='';
        name.dispatchEvent(new Event('change'));
        var detail=Object.assign({},deletedTarget,{deleted:true,whole:whole});
        document.dispatchEvent(new CustomEvent('portal:item-saved',{detail:detail}));
        return window.DrillGrade && window.DrillGrade.refreshItems ? window.DrillGrade.refreshItems(detail) : Promise.resolve();
      }).then(function(){
        if(deletedTarget.structural && window.mostrarDetalhe) window.mostrarDetalhe('triagem');
        var u=new URL(location.href);
        if(u.searchParams.get('item')===deletedTarget.itemId || whole) {
          ['item','segmento','vista','subvista'].forEach(function(k){u.searchParams.delete(k);});
          if(whole)u.searchParams.delete('viga');
          history.replaceState(history.state,'',u.href);
        }
        status.textContent='100% · Concluído · '+(deletedTarget.beam || deletedTarget.itemId)+
          (!whole && deletedTarget.segmento ? ' · S'+deletedTarget.segmento : '')+' excluído. Lista e destaque atualizados.';
      });
    };
    var pickingClass=false;
    cls.addEventListener('change',function(){if(!pickingClass)loadItems();});
    // Delegated geometric picking leaves the overlay transparent to pan/zoom.
    // The drawing toggle is checked at every event, not only when wiring.
    var pickSequence=0, pointerStart=null;
    container.addEventListener('pointerdown',function(e){
      pointerStart={x:e.clientX,y:e.clientY,id:e.pointerId,dragged:false};
    },true);
    container.addEventListener('pointermove',function(e){
      if(pointerStart && e.pointerId===pointerStart.id &&
        Math.hypot(e.clientX-pointerStart.x,e.clientY-pointerStart.y)>5) pointerStart.dragged=true;
    },true);
    container.addEventListener('click',function(e){
      if(chk.checked || saveButton.disabled || target || !pointerStart || pointerStart.dragged ||
        Math.hypot(e.clientX-pointerStart.x,e.clientY-pointerStart.y)>5) return;
      var vp=container.querySelector('.zoom-pan-viewport');
      if(!vp || !vp.contains(e.target)) return;
      var overlay=vp.querySelector('.destaque-overlay');
      if(!overlay || !overlay.getScreenCTM()) return;
      var point=overlay.createSVGPoint();point.x=e.clientX;point.y=e.clientY;
      point=point.matrixTransform(overlay.getScreenCTM().inverse());
      var polys=Array.from(overlay.querySelectorAll('polygon')).reverse();
      // Overlay stays transparent to pan/zoom. Pick the complete tag rectangle
      // geometrically, including its transparent interior, before narrow lines.
      var tags=Array.from(overlay.querySelectorAll('.tag-label-box, .tag-leader-text')).reverse();
      var hit=tags.find(function(tag){
        if(!tag._geometryItem) return false;
        var box=tag.getBoundingClientRect();
        return e.clientX>=box.left && e.clientX<=box.right &&
          e.clientY>=box.top && e.clientY<=box.bottom;
      }) || polys.find(function(poly){return poly._geometryItem &&
        (poly.isPointInFill(point) || poly.isPointInStroke(point));});
      if(!hit) return;
      e.preventDefault();e.stopPropagation();
      var item=hit._geometryItem, seq=++pickSequence;
      if(!item.classe_sa || !item.item_id) return;
      var ready=Promise.resolve();
      if(cls.value!==item.classe_sa || loading){
        pickingClass=true;cls.value=item.classe_sa;cls.dispatchEvent(new Event('change'));pickingClass=false;
        ready=loadItems();
      }
      ready.then(function(){
        if(seq!==pickSequence || chk.checked || !container.isConnected) return;
        var row=rows.find(function(i){return i.item_id===item.item_id;});
        if(!row){status.textContent='Item não encontrado na lista atual.';return;}
        items.value=beamClass(cls.value)?beamName(row):row.item_id;chooseItem();
        if(beamClass(cls.value)){segs.value=row.item_id;chooseSegment();}
        name.dispatchEvent(new Event('change'));
        var detail=document.getElementById('criar-item-coll');if(detail)detail.open=true;
        status.textContent='Selecionado · '+(selection.beam || name.value)+
          (selection.beam ? ' · S'+selection.segmento : '')+
          (cls.value==='cortes_interpretados'?' · escolha Validar referência de nível ou Excluir.':' · escolha Redesenhar ou Excluir.');
      });
    },true);
    items.addEventListener('change',chooseItem);
    segs.addEventListener('change',function(){if(target)stop();chooseSegment();});
    redraw.addEventListener('click',begin);
    validate.addEventListener('click',function(){
      if(!selection || selection.classe!=='cortes_interpretados')return;
      var t=Object.assign({},selection);validate.disabled=true;
      status.textContent='Validando referência local de nível…';
      api(endpoint(t,'/validar'),'POST').then(function(){
        return container._refreshDestaques(t.classe);
      }).then(function(){
        if(window.DrillGrade && window.DrillGrade.refreshItems)
          return window.DrillGrade.refreshItems(Object.assign({},t,{structural:true}));
      }).then(function(){status.textContent='Corte validado · referência de nível de alta confiança. Registro salvo em Ver apontamentos.';})
        .catch(function(e){status.textContent=e.message;}).finally(function(){validate.disabled=false;});
    });
    cancel.addEventListener('click',function(){stop();status.textContent='Edição cancelada.';});
    del.addEventListener('click',function(){if(selection){var t=Object.assign({},selection);if(beamClass(t.classe))t.itemId=t.beam;deleteItem(t,beamClass(t.classe));}});
    delSeg.addEventListener('click',function(){deleteItem(selection,false);});
    saveButton.addEventListener('click',function(e){
      e.preventDefault();e.stopImmediatePropagation();
      if(window._polyAtual && window._polyAtual.length>=3) window.fecharPolylineAtual();
      var geom=window._polyGeoms && window._polyGeoms[0];
      if(!geom || geom.points.length<3) {status.textContent='Marque pelo menos 3 pontos para formar o contorno.';return;}
      var overlay=container.querySelector('.destaque-overlay'), bbox=overlay && JSON.parse(overlay.getAttribute('data-bbox-dxf') || 'null');
      // Os cliques e OSNAP pertencem ao SVG de fundo (pt), não ao overlay
      // (px). Use a extensão inicial dessa mesma camada, nunca o zoom atual.
      var vp=container.querySelector('.zoom-pan-viewport');
      var drawingSvg=vp && ((vp._pz && vp._pz.svg) || vp.querySelector('svg:not(.destaque-overlay)'));
      var vb=drawingSvg && (drawingSvg.dataset.homeVb || '').split(/\s+/).map(Number);
      if(!bbox || !vb || !vb[2] || !vb[3]) {status.textContent='Transformação do estrutural não disponível. Aguarde o desenho carregar.';return;}
      var pts=pointsToDxf(geom.points,bbox,vb);
      var editing=!!target, geometries=editing ? [geom] : window._polyGeoms.slice();
      var savedTarget=editing ? Object.assign({},target) : {classe:cls.value,beam:name.value.trim().toUpperCase(),pavimento:pav(),structural:true};
      if(!editing && !savedTarget.beam) {status.textContent='Informe o nome do item.';return;}
      if(!editing && !beamClass(cls.value) && geometries.length!==1) {status.textContent='Crie um pilar ou laje por vez, com um contorno fechado.';return;}
      if(geometries.some(function(g){return !g.points || g.points.length<3;})) {status.textContent='Cada contorno precisa de pelo menos 3 pontos.';return;}
      var persisted=false, completed=0;
      function progress(percent,message) {
        status.setAttribute('role','status');status.setAttribute('aria-live','polite');
        status.textContent=percent+'% · '+message;
      }
      var controls=Array.from(document.querySelectorAll('#criar-item-coll button, #criar-item-coll input, #criar-item-coll select'));
      var disabledBefore=controls.map(function(el){return el.disabled;});
      controls.forEach(function(el){el.disabled=true;});
      progress(25,'Contorno preparado. Gravando e interpretando somente este item/segmento…');
      var started=Date.now();
      var waiting=setInterval(function(){
        if(!persisted) progress(25,'SA granular e gravação: aguardando confirmação ('+Math.floor((Date.now()-started)/1000)+' s). Sem reprocessar a viga.');
      },1000);
      var operation=editing ? save(savedTarget,pts) : geometries.reduce(function(chain,g){
        return chain.then(function(){
          return api('/obras/'+encodeURIComponent(obra)+'/itens/'+encodeURIComponent(savedTarget.classe)+'/geometria?pavimento='+encodeURIComponent(savedTarget.pavimento),
            'POST',{name:savedTarget.beam,segment:beamClass(savedTarget.classe)?Number(g.segmento):null,points:pointsToDxf(g.points,bbox,vb)})
            .then(function(result){
              completed++;window._polyGeoms=geometries.slice(completed);
              savedTarget.itemId=result.affected[0].item_id;
              progress(25,'SA granular concluído para '+completed+'/'+geometries.length+' contorno(s).');
              return result;
            });
        });
      },Promise.resolve());
      operation.then(function(result){
        persisted=true;clearInterval(waiting);
        savedTarget.interpretation=result.interpretation;
        progress(75,'Geometria e SA granular gravados. Atualizando destaque e lista N1…');
        // Libera o alvo para que o destaque persistido reapareça no renderer.
        target=null;
        if(!container._refreshDestaques) throw new Error('Atualização dinâmica do viewer indisponível.');
        return container._refreshDestaques(savedTarget.classe).then(function(){
          if(window._criarItemItensPorClasse) delete window._criarItemItensPorClasse[savedTarget.classe];
          document.dispatchEvent(new CustomEvent('portal:item-saved',{detail:savedTarget}));
          return Promise.all([loadItems(),window.DrillGrade && window.DrillGrade.refreshItems ? window.DrillGrade.refreshItems(savedTarget) : Promise.resolve()]);
        });
      }).then(function(){
        stop();progress(100,'Concluído · '+(savedTarget.beam || savedTarget.itemId)+
          (savedTarget.segmento ? ' · S'+savedTarget.segmento : '')+' salvo, interpretado e destacado. Campos pendentes exigem revisão humana.');
      }).catch(function(err){
        status.textContent=(persisted ? 'Geometria e SA já gravados; falha ao atualizar destaque. Não salve novamente. ' :
          (completed ? completed+' contorno(s) gravado(s); somente os restantes foram preservados. ' : 'Não foi possível confirmar o salvamento; desenho preservado. '))+err.message;
        if(completed && container._refreshDestaques) container._refreshDestaques(savedTarget.classe);
      }).finally(function(){
        clearInterval(waiting);controls.forEach(function(el,i){el.disabled=disabledBefore[i];});
        saveButton.disabled=false;cancel.disabled=false;chooseSegment();
      });
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
  window.ItemGeometry={open:open,delete:deleteItem,remove:remove,save:save,isEditing:function(){return !!target;},
    isSelected:function(item){return !!selection && item.classe_sa===selection.classe && item.item_id===selection.itemId;},
    hides:function(item){
      // Edição: apenas o alvo. Criação: nenhum destaque existente. O SVG
      // estrutural e seu índice OSNAP não dependem desta camada de realce.
      if(target) return item.classe_sa!==target.classe || item.item_id!==target.itemId;
      return !!window._modoPolylineAtivo;
    }};
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
