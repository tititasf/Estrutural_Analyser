(function () {
  'use strict';
  var drafts = Object.create(null);
  var labels = {sa:'SA', c1:'Camada 1', c2:'Camada 2', c3:'Camada 3', n3:'N3'};
  function esc(value) { return String(value || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function api(url, method, body) {
    return fetch(url, {method:method || 'GET', cache:'no-store', headers:{'Content-Type':'application/json'},
      body:body ? JSON.stringify(body) : undefined}).then(function(r) {
      return r.json().then(function(data) { if (!r.ok) throw new Error(data.detail || ('HTTP '+r.status)); return data; });
    });
  }
  function mount(root, options) {
    var base='/obras/'+encodeURIComponent(options.obraId);
    var url=base+'/qa-notas/'+options.classe+'/'+encodeURIComponent(options.item)+
      '?pavimento='+encodeURIComponent(options.pavimento)+'&behavior='+encodeURIComponent(options.behavior || 'para');
    var draft=drafts[url] || (drafts[url]={notes:{}, dirty:false});
    var available=true;
    root.innerHTML='<div><strong>QA agentivo e Humano</strong><span>'+
      (available ? 'Cada revisão recebe as notas humanas salvas. Confiança declarada pelo agente; ainda não calibrada com acertos reais.' : 'Anotações disponíveis. A fila de revisão desta classe ainda não está integrada.')+
      '</span></div><div class="fv-qa-version-grid">'+Object.keys(labels).map(function(key,index) {
        var review=index>0 && index<4;
        return '<article class="fv-qa-version"><button type="button" '+
          (review && available ? 'data-human-review="L'+index+'" disabled' : 'disabled')+
          (!available && review ? ' title="Fila QA ainda não integrada para esta classe"' : '')+'>'+
          (key==='sa' ? 'Interpretação Motor SA' : (key==='n3' ? 'Desenho N3' : 'Solicitar revisão · '+labels[key]))+
          '</button><label>Anotações humanas · '+labels[key]+'<textarea disabled data-human-note="'+key+'" placeholder="Opinião humana sobre esta versão">'+
          esc(draft.notes[key])+'</textarea></label><label>Opinião agêntica · '+labels[key]+
          '<textarea readonly data-agent-note="'+key+'" placeholder="Ainda não revisado"></textarea></label></article>';
      }).join('')+'</div><button type="button" class="human-qa-save" disabled>Salvar anotações humanas</button>'+
      '<div class="fv-qa-status" role="status">Carregando anotações…</div><section class="human-qa-candidates"></section>';
    var status=root.querySelector('[role=status]'), save=root.querySelector('.human-qa-save');
    function message(text, error) { status.textContent=text; status.classList.toggle('error', !!error); }
    var candidates=root.querySelector('.human-qa-candidates');
    var candidateUrl=base+'/qa-camadas/'+options.classe+'/'+encodeURIComponent(options.item);
    var query='?pavimento='+encodeURIComponent(options.pavimento)+'&behavior='+encodeURIComponent(options.behavior || 'para');
    function changed() {
      refreshReviews();
      if(window.DrillGrade && window.DrillGrade.refreshItems) window.DrillGrade.refreshItems();
      if(options.onReviewed) options.onReviewed();
    }
    function panzoom(host) {
      var svg=host.querySelector('svg'); if(!svg) return;
      var initial=svg.getAttribute('viewBox'); if(!initial) return;
      var box=initial.trim().split(/[ ,]+/).map(Number), start;
      svg.addEventListener('wheel',function(e) {
        e.preventDefault(); var rect=svg.getBoundingClientRect(), factor=e.deltaY>0 ? 1.15 : 1/1.15;
        var x=(e.clientX-rect.left)/rect.width,y=(e.clientY-rect.top)/rect.height;
        box=[box[0]+box[2]*x*(1-factor),box[1]+box[3]*y*(1-factor),box[2]*factor,box[3]*factor];
        svg.setAttribute('viewBox',box.join(' '));
      },{passive:false});
      svg.addEventListener('pointerdown',function(e){if(e.button!==0)return; start={x:e.clientX,y:e.clientY,box:box.slice()};svg.setPointerCapture(e.pointerId);});
      svg.addEventListener('pointermove',function(e){if(!start)return;var rect=svg.getBoundingClientRect();box=[start.box[0]-(e.clientX-start.x)/rect.width*start.box[2],start.box[1]-(e.clientY-start.y)/rect.height*start.box[3],start.box[2],start.box[3]];svg.setAttribute('viewBox',box.join(' '));});
      svg.addEventListener('pointerup',function(){start=null;});
      svg.addEventListener('pointercancel',function(){start=null;});
      svg.addEventListener('dblclick',function(){box=initial.trim().split(/[ ,]+/).map(Number);svg.setAttribute('viewBox',initial);});
    }
    function showCandidates(data) {
      var effective=data.effective_sa, latest=data.latest_agentic;
      candidates.innerHTML='<p>'+esc(effective ? 'SA vigente: '+effective.layer+' validada por humano em '+effective.at : 'SA vigente: interpretação original ou edição manual.')+'</p>'+
        (latest ? '<p><strong>Resultado agêntico mais atual: '+esc(latest.layer)+'</strong> · aguarda validação humana.</p>' : '')+
        Object.keys(data.agent_reviews || {}).map(function(layer){var r=data.agent_reviews[layer];return r.viewer_generated ? '<details data-candidate="'+esc(layer)+'"><summary>Examinar '+esc(layer)+(r.stale ? ' · expirada' : '')+'</summary><div class="human-qa-candidate-body"></div></details>' : '';}).join('')+
        Object.keys(data.agent_reviews || {}).map(function(layer){var r=data.agent_reviews[layer];return r.unit_reviews ? '<details><summary>Conferência por unidade · '+esc(layer)+'</summary><pre>'+esc(JSON.stringify(r.unit_reviews,null,2))+'</pre></details>' : '';}).join('')+
        (effective ? '<button type="button" class="human-qa-save" data-rollback>Desfazer adoção do SA vigente</button>' : '')+
        '<details><summary>Histórico de validações humanas</summary><pre>'+esc(JSON.stringify(data.history || [],null,2))+'</pre></details>';
      candidates.querySelectorAll('[data-candidate]').forEach(function(details){
        details.addEventListener('toggle',function(){if(!details.open || details.dataset.loaded)return;
          var body=details.querySelector('.human-qa-candidate-body'),layer=details.dataset.candidate;
          body.textContent='Carregando candidato…';
          api(candidateUrl+'/'+layer+query).then(function(r){
            if(!details.isConnected)return; details.dataset.loaded='1';
            body.innerHTML='<div class="human-qa-preview"></div><p>'+esc('Auditoria posterior: '+((r.post_review || {}).note || 'Não concluída.'))+'</p>'+
              '<details><summary>Interpretação candidata e alterações</summary><pre>'+esc(JSON.stringify({candidate:r.candidate_interpretation,changes:r.field_corrections,post_review:r.post_review},null,2))+'</pre></details>'+
              '<label><input type="checkbox" data-human-accept> Revisei esta camada e suas pendências; validar este resultado como SA.</label><br><button type="button" class="human-qa-save" data-promote disabled>Validar '+esc(layer)+' e substituir SA</button>';
            var host=body.querySelector('.human-qa-preview');host.innerHTML=r.svg || '';panzoom(host);
            var button=body.querySelector('[data-promote]'),ack=body.querySelector('[data-human-accept]');
            var allowed=r.promotion_ready && !r.stale && r.candidate_sha256;
            ack.disabled=!allowed;ack.addEventListener('change',function(){button.disabled=!allowed || !ack.checked;});
            if(!allowed){var blocker=document.createElement('p');blocker.textContent=(r.promotion_blockers || ['Camada expirada ou incompleta.']).join(' ');body.appendChild(blocker);}
            button.addEventListener('click',function(){button.disabled=true;api(candidateUrl+'/validar'+query,'POST',{layer:layer,round_id:r.round_id,candidate_sha256:r.candidate_sha256,acknowledge_pending:ack.checked}).then(function(){message('Camada validada por humano e adotada como SA.');changed();}).catch(function(e){button.disabled=false;message(e.message,true);});});
          }).catch(function(e){body.textContent=e.message;});
        });
      });
      var rollback=candidates.querySelector('[data-rollback]');
      if(latest){var current=candidates.querySelector('[data-candidate="'+latest.layer+'"]');if(current)current.open=true;}
      if(rollback)rollback.addEventListener('click',function(){rollback.disabled=true;api(candidateUrl+'/desfazer'+query,'POST',{expected_round_id:effective.round_id}).then(function(){message('Adoção desfeita; SA anterior restaurado.');changed();}).catch(function(e){rollback.disabled=false;message(e.message,true);});});
    }
    function saveNotes() {
      save.disabled=true;
      var snapshot=Object.assign({},draft.notes);
      return api(url,'PUT',{notes:snapshot}).then(function() {
        if (JSON.stringify(draft.notes)===JSON.stringify(snapshot)) draft.dirty=false;
        message('Anotações humanas salvas.');
      }).finally(function() { save.disabled=false; });
    }
    root.querySelectorAll('[data-human-note]').forEach(function(field) {
      field.addEventListener('input',function() { draft.notes[field.dataset.humanNote]=field.value; draft.dirty=true; });
    });
    save.addEventListener('click',function() { saveNotes().catch(function(e) { message('Falha ao salvar: '+e.message,true); }); });
    root.querySelectorAll('[data-human-review]').forEach(function(button) {
      button.addEventListener('click',function() {
        var layer=button.dataset.humanReview; button.disabled=true;
        message('Salvando notas e enfileirando revisão '+layer+'…');
        saveNotes().then(function() { return api(base+'/qa-agentico','POST',{
          items:[options.item], classe:options.classe, pavimento:options.pavimento, layer:layer, behavior:options.behavior || 'para'});
        }).then(function(round) {
          function poll() {
            if (!root.isConnected) return;
            api('/qa-rounds/'+encodeURIComponent(round.round_id)).then(function(detail) {
              if (['queued','running','na_fila'].indexOf(detail.status)>=0) {
                message('QA '+layer+' · '+detail.status+'…'); window.setTimeout(poll,2500); return;
              }
              button.disabled=false;
              var result=(detail.items || [])[0] || {};
              if (result.status!=='completed') { message('Revisão não concluída: '+(detail.job_error || detail.status),true); return; }
              message(layer+' · '+(result.verdict || detail.status)+' · '+(result.note || 'Sem observação.'));
              if (window.DrillGrade && window.DrillGrade.refreshItems) window.DrillGrade.refreshItems();
              refreshReviews();
              if(options.onReviewed) options.onReviewed();
            }).catch(function(e) { button.disabled=false; message('Falha ao acompanhar: '+e.message,true); });
          }
          poll();
        }).catch(function(e) { button.disabled=false; message('Falha ao solicitar revisão: '+e.message,true); });
      });
    });
    function refreshReviews() { return api(url).then(function(data) {
      root.querySelectorAll('[data-agent-note]').forEach(function(field) {
        var layer={sa:'L1',c1:'L2',c2:'L3'}[field.dataset.agentNote];
        var review=(data.agent_reviews || {})[layer];
        field.value=review ? (review.assessment==='inconclusive' ? 'Inconclusivo' : (review.verdict==='validou' ? 'Aprovado' : 'Reprovado'))+
          ' · Confiança declarada: '+window.PortalNumbers.number(review.confidence_percent)+'%\n'+window.PortalNumbers.text(review.note)+
          (review.confidence_basis ? '\nBase da confiança: '+window.PortalNumbers.text(review.confidence_basis) : '')+
          (review.coverage ? '\nCritérios: '+review.coverage.pass+' comprovados, '+review.coverage.fail+' falhos, '+review.coverage.uncertain+' incertos.' : '')+
          (review.unit_coverage ? '\nConferência de '+review.unit_coverage.units+' unidade(s): '+review.unit_coverage.pass+' verificações comprovadas, '+review.unit_coverage.fail+' falhas, '+review.unit_coverage.uncertain+' incertas. Cobertura de revisão; não é acurácia medida.' : '')+
          '\n'+(review.checks || []).map(function(check){return window.PortalNumbers.text(check.criterion+': '+check.observation)+' ('+check.status+')';}).join('\n')+
          '\n'+review.provider+' · '+review.model+(review.stale ? '\nVersão anterior alterada; solicite nova revisão.' : '') : '';
      });
      root.querySelectorAll('[data-human-review]').forEach(function(button) {
        var allowed=!!data.qa_available && !!(data.review_allowed || {})[button.dataset.humanReview];
        button.disabled=!allowed;
        button.title=allowed ? '' : 'Exige viewer populado e atual da camada anterior';
      });
      showCandidates(data);
      return data;
    }); }
    refreshReviews().then(function(data) {
      if (!draft.dirty) draft.notes=data.notes || {};
      root.querySelectorAll('[data-human-note]').forEach(function(field) { field.value=draft.notes[field.dataset.humanNote] || ''; field.disabled=false; });
      save.disabled=false;

      message(draft.dirty ? 'Anotações ainda não salvas.' : 'Pronto.');
    }).catch(function(e) { message('Falha ao carregar anotações: '+e.message,true); });
  }
  window.HumanQa={mount:mount};
})();
