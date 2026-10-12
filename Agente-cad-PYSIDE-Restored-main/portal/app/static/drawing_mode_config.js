(function () {
  'use strict';
  var dialog = document.getElementById('drawing-mode-config-dialog');
  if (!dialog) return;
  var data, mode = 'INI', cls = 'PL', busy = false, category = 'components';
  var params=new URLSearchParams(location.search);mode=params.get('modo')||mode;cls=params.get('classe')||cls;category=params.get('categoria')||category;
  var fields = document.getElementById('drawing-config-fields');
  var status = document.getElementById('drawing-config-status');
  var form = document.getElementById('drawing-config-form');
  var labels = {text_scale:'Escala dos textos',dimension_scale:'Escala dos textos e setas de cotas',hatch_scale:'Escala das hachuras',hatch_angle:'Ângulo das hachuras (graus)',FACE_SPACING:'Distância entre faces ABCD (cm)',ZONE_ABCD_X:'Origem ABCD X (cm)',ZONE_CIMA_X:'Origem Cima X (cm)',ZONE_GRADES_X:'Origem Grades X (cm)',NOM_H:'Altura do nome (cm)',NOM_ABOVE:'Distância do nome acima (cm)',LABEL_ABOVE:'Distância das etiquetas acima (cm)',LABEL_H:'Altura das etiquetas (cm)',DIM_BELOW:'Afastamento da cota individual (cm)',DIM_TOTAL_BELOW:'Afastamento da cota total (cm)',TIER_STEP:'Distância entre níveis de cotas (cm)',DIM_B_RIGHT:'Afastamento da cota B (cm)',DIM_H_RIGHT:'Afastamento da cota de altura (cm)',PID_H:'Altura do identificador de painel (cm)',GAP_VIGAS:'Distância entre vigas (cm)',GAP_ROW:'Distância entre linhas (cm)',LV_UNIT_GAP:'Distância entre unidades (cm)',DIM_HORIZONTAL_OFFSET_CM:'Afastamento horizontal das cotas (cm)',DIM_VERTICAL_OFFSET_CM:'Afastamento vertical das cotas (cm)',GAP_X:'Distância entre colunas (cm)',GAP_Y:'Distância entre linhas (cm)',PAD:'Margem do quadro (cm)',TITULO_H:'Altura do cabeçalho (cm)',CARIMBO_H:'Altura do carimbo (cm)'};
  Object.assign(labels,{GAP_ROW_LV:'Distância entre linhas de laterais (cm)',GAP_AB:'Distância entre faces A e B (cm)',LV_SARR_INSET:'Recuo dos sarrafos verticais (cm)',SARR_INSET_H:'Recuo dos sarrafos horizontais (cm)',SECT_GAP:'Distância do corte à lateral (cm)',DRAW_HATCHES_LAJE:'Incluir hachura de concreto/laje',DRAW_HATCHES_PAINEL:'Incluir hachura dos painéis',SARR_RECUO:'Recuo dos sarrafos (cm)',SARR_MAX_GAP:'Distância máxima entre sarrafos (cm)',SARR_MAX_LEN:'Comprimento máximo dos sarrafos (cm)',SARRAFO_GAP:'Distância do par de sarrafos (cm)',PILAR_HATCH_STEP:'Distância entre linhas da hachura de pilar (cm)'});
  function el(tag, text, className) { var n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (className) n.className = className; return n; }
  function tabs(id, values, selected, change) {
    var root = document.getElementById(id); root.replaceChildren();
    Object.keys(values).forEach(function (key) {
      var button = el('button', values[key], 'n5-pav-tab' + (key === selected ? ' on' : ''));
      button.type = 'button'; button.setAttribute('role','tab'); button.setAttribute('aria-selected',String(key === selected));
      button.disabled = busy;
      button.addEventListener('click',function () { change(key); }); root.appendChild(button);
    });
  }
  function section(title, key) { var group = el('fieldset',undefined,'drawing-config-section'); group.hidden = category !== key; group.appendChild(el('legend',title)); fields.appendChild(group); return group; }
  function panZoom(canvas, svg) {
    var home=svg.getAttribute('viewBox').trim().split(/[\s,]+/).map(Number),view=home.slice(),pending=0,last,rect;
    svg.setAttribute('preserveAspectRatio','xMidYMid meet');
    // Keep the camera in numbers: no SVG layout reads after each viewBox write.
    function schedule() { if(pending)return;pending=requestAnimationFrame(function(){pending=0;if(canvas.isConnected)svg.setAttribute('viewBox',view.join(' '));}); }
    function reset() { view=home.slice();schedule(); }
    function scale() { return Math.min(rect.width/view[2],rect.height/view[3]); }
    function zoom(f,point) { var w=view[2]*f,h=view[3]*f;if(w<home[2]*.01||w>home[2]*8)return;point=point||{x:view[0]+view[2]/2,y:view[1]+view[3]/2};view=[point.x-(point.x-view[0])*f,point.y-(point.y-view[1])*f,w,h];schedule(); }
    canvas.addEventListener('wheel',function(event){event.preventDefault();rect=canvas.getBoundingClientRect();var s=scale();if(!s)return;var p={x:view[0]+(event.clientX-rect.left-(rect.width-view[2]*s)/2)/s,y:view[1]+(event.clientY-rect.top-(rect.height-view[3]*s)/2)/s};zoom(event.deltaY<0?.88:1.14,p);},{passive:false});
    canvas.addEventListener('pointerdown',function(event){if(event.button!==0&&event.button!==1)return;event.preventDefault();rect=canvas.getBoundingClientRect();last={x:event.clientX,y:event.clientY,id:event.pointerId};canvas.classList.add('dragging');canvas.setPointerCapture(event.pointerId);});
    canvas.addEventListener('pointermove',function(event){if(!last||last.id!==event.pointerId)return;var s=scale();if(!s)return;view[0]-=(event.clientX-last.x)/s;view[1]-=(event.clientY-last.y)/s;last.x=event.clientX;last.y=event.clientY;schedule();});
    function stop(event){if(last&&event.pointerId!==last.id)return;last=null;canvas.classList.remove('dragging');}
    canvas.addEventListener('pointerup',stop);canvas.addEventListener('pointercancel',stop);canvas.addEventListener('lostpointercapture',stop);canvas.addEventListener('auxclick',function(event){if(event.button===1)event.preventDefault();});canvas.addEventListener('dblclick',reset);
    return {reset:reset,zoom:zoom};
  }
  async function uploadResult(response) {
    var body=await response.text(),result;
    try { result=JSON.parse(body); } catch(error) {
      if([502,503,504].includes(response.status))throw new Error('Portal temporariamente indisponível (HTTP '+response.status+'). Aguarde alguns segundos e tente enviar novamente.');
      if(response.status===413)throw new Error('O servidor recusou o tamanho do arquivo (HTTP 413).');
      if(response.redirected)throw new Error('Sua sessão expirou. Entre novamente no portal antes de enviar.');
      throw new Error('O servidor devolveu uma resposta inesperada (HTTP '+response.status+'). Tente novamente.');
    }
    if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Falha ao enviar DXF (HTTP '+response.status+').');
    return result;
  }
  function framePanel(examples, legends) {
    // Documentos separados por modo, classe e coleção; cada envio acrescenta uma aba.
    var noun=legends?'índices e legendas':'moldura', Noun=legends?'Índices e Legendas':'Moldura';
    var box=section(examples?'Exemplos — até 10 DXFs':Noun,examples?'examples':(legends?'legends':'frame')), selectedMode=mode, selectedClass=cls;
    box.appendChild(el('p',examples?'Guarde até dez documentos de exemplo, separados por modo e classe.':'Envie DXFs para visualizar e guardar '+(legends?'os índices e legendas':'a moldura')+' deste modo e desta classe.'));
    var label=el('label','Documentos DXF (até 20 MB por arquivo)'),file=el('input');file.type='file';file.accept='.dxf';file.multiple=true;file.disabled=!data.can_edit;label.appendChild(file);box.appendChild(label);
    var upload=el('button','Enviar DXFs','btn');upload.type='button';upload.disabled=!data.can_edit;box.appendChild(upload);
    var message=el('p','Carregando '+noun+'…');message.setAttribute('role','status');box.appendChild(message);
    var reset=el('button','Enquadrar desenho');reset.type='button';reset.hidden=true;box.appendChild(reset);
    var zoomIn=el('button','Ampliar'),zoomOut=el('button','Reduzir');[zoomIn,zoomOut].forEach(function(b){b.type='button';b.hidden=true;box.appendChild(b);});
    var canvas=el('div',undefined,'drawing-frame-viewer');box.appendChild(canvas);
    box.appendChild(el('p','Scroll: zoom · arraste: mover · duplo clique: enquadrar.'));
    var url='/app/configuracao-modos/'+selectedMode+'/'+selectedClass+(examples?'/exemplos':(legends?'/indices-legendas':'/moldura'));
    var exampleList=el('nav',undefined,'n5-pav-tabs'),documents=[],selectedDocument=null;exampleList.setAttribute('aria-label',examples?'Documentos de exemplo':Noun);exampleList.setAttribute('role','tablist');canvas.before(exampleList);
    var remove=el('button',examples?'Remover exemplo selecionado':'Remover '+noun,'btn-sec btn');remove.type='button';remove.hidden=true;message.after(remove);
    async function listing(items, current) {documents=items;exampleList.replaceChildren();items.forEach(function(item,i){var tab=el('button',examples?'Exemplo '+(i+1):((legends?'Documento ':'Moldura ')+(i+1)+' · '+item.filename),'n5-pav-tab');tab.type='button';tab.title=item.filename;tab.setAttribute('role','tab');tab.onclick=function(){show(item).catch(function(e){message.textContent=e.message;});};exampleList.appendChild(tab);});await show(items.find(function(item){return current&&item.id===current.id;})||(items.length?items[items.length-1]:null));}
    remove.onclick=async function(){if(!selectedDocument||busy)return;busy=true;remove.disabled=true;dialog.querySelectorAll('[role=tab]').forEach(function(b){b.disabled=true;});try{var r=await fetch(url+'/'+selectedDocument.id,{method:'DELETE'}),v=await r.json();if(!r.ok)throw new Error(v.detail||'Falha ao remover.');await listing(examples?v.examples:v.documents,v.frame);message.textContent=examples?'Exemplo removido. '+(v.examples.length?'Selecione outro documento na lista.':'Nenhum exemplo enviado.'):Noun+(legends?' removidos':' removida')+'. Você pode enviar outro DXF.';}catch(e){message.textContent=e.message;}finally{busy=false;remove.disabled=false;dialog.querySelectorAll('[role=tab]').forEach(function(b){b.disabled=false;});}};
    var loadVersion=0, cropUI=null;
    if(examples && selectedClass!=='LJ')cropUI=exampleCropControls(box,canvas,selectedMode,selectedClass,function(frame,crop){return show(frame,crop);},function(){return selectedDocument;});
    async function show(frame,crop) {
      if(!box.isConnected)return;
      var version=++loadVersion;
      var freshCanvas=canvas.cloneNode(false);canvas.replaceWith(freshCanvas);canvas=freshCanvas;reset.hidden=true;zoomIn.hidden=true;zoomOut.hidden=true;selectedDocument=frame;remove.hidden=!frame||!data.can_edit;remove.setAttribute('aria-label',frame?(examples?'Remover exemplo: ':'Remover '+noun+': ')+frame.filename:remove.textContent);Array.from(exampleList.children).forEach(function(tab,i){tab.setAttribute('aria-selected',String(frame&&documents[i].id===frame.id));tab.classList.toggle('on',Boolean(frame&&documents[i].id===frame.id));});
      if(!frame){if(cropUI)cropUI.select(null,null);message.textContent='Nenhum DXF enviado para este modo e esta classe.';return;}
      message.textContent=frame.filename+' · '+Math.ceil(frame.size/1024)+' KB';
      var previewUrl=url+'/'+frame.id+(crop?'/recortes/'+crop.id+'/preview':'/preview');
      if(cropUI)await cropUI.select(frame,crop&&crop.id!=='original'?crop:null);
      var response=await fetch(previewUrl);if(!response.ok)throw new Error('Não foi possível carregar o desenho.');
      var source=await response.text();if(!box.isConnected||version!==loadVersion)return;
      var doc=new DOMParser().parseFromString(source,'image/svg+xml');
      if(doc.querySelector('parsererror'))throw new Error('Preview inválido.');
      doc.querySelectorAll('script,foreignObject').forEach(function(n){n.remove();});
      doc.querySelectorAll('*').forEach(function(n){Array.from(n.attributes).forEach(function(a){if(/^on/i.test(a.name)||((a.name==='href'||a.name==='xlink:href')&&!a.value.startsWith('#')))n.removeAttribute(a.name);});});
      if(!box.isConnected||version!==loadVersion)return;
      var svg=document.importNode(doc.documentElement,true);svg.removeAttribute('width');svg.removeAttribute('height');canvas.appendChild(svg);reset.hidden=false;zoomIn.hidden=false;zoomOut.hidden=false;var navigation=panZoom(canvas,svg);if(cropUI)cropUI.attach(canvas,svg,frame,crop);reset.onclick=navigation.reset;zoomIn.onclick=function(){navigation.zoom(.8);};zoomOut.onclick=function(){navigation.zoom(1.25);};
    }
    fetch(url,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('Não foi possível carregar '+(legends?'os índices e legendas':'a moldura')+'.');return r.json();}).then(function(r){return listing(examples?r.examples:r.documents,r.frame);}).catch(function(e){message.textContent=e.message;});
    upload.addEventListener('click',async function(){
      if(busy)return;
      var selected=Array.from(file.files);
      if(!selected.length){message.textContent='Selecione um ou mais DXFs.';return;}
      var invalid=selected.find(function(item){return !/\.dxf$/i.test(item.name)||item.size>20*1024*1024;});
      if(invalid){message.textContent=invalid.name+': selecione um DXF de até 20 MB.';return;}
      if(examples&&documents.length+selected.length>10){message.textContent='Limite de 10 exemplos por modo e classe. Há '+(10-documents.length)+' vaga(s) disponível(is).';return;}
      busy=true;dialog.querySelectorAll('[role=tab]').forEach(function(b){b.disabled=true;});upload.disabled=true;file.disabled=true;
      var completed=0,failures=[],failedFiles=[],latest=null;
      try{
        for(var i=0;i<selected.length;i++){
          message.textContent='Enviando '+(i+1)+' de '+selected.length+': '+selected[i].name+'…';
          try{
            var payload=new FormData();payload.append('arquivo',selected[i]);
            var response=await fetch(url,{method:'POST',body:payload}),result=await uploadResult(response);
            latest=result;completed++;
          }catch(error){failedFiles.push(selected[i]);failures.push(selected[i].name+': '+error.message);}
        }
        if(latest)await listing(examples?latest.examples:latest.documents,latest.frame);
        if(failedFiles.length){var retryFiles=new DataTransfer();failedFiles.forEach(function(item){retryFiles.items.add(item);});file.files=retryFiles.files;}else file.value='';
        message.textContent=completed+' de '+selected.length+' arquivo(s) enviado(s).'+(failures.length?' Falhas: '+failures.join(' · '):' Selecione uma aba para visualizar.');
      }catch(error){message.textContent=completed+' arquivo(s) enviado(s). '+error.message;}
      finally{busy=false;dialog.querySelectorAll('[role=tab]').forEach(function(b){b.disabled=false;});upload.disabled=!data.can_edit;file.disabled=!data.can_edit;}
    });
  }
  function exampleCropControls(box,initialCanvas,selectedMode,selectedClass,show,current) {
    var root=el('fieldset',undefined,'drawing-config-section');root.appendChild(el('legend','Recortes do exemplo'));initialCanvas.before(root);
    var base='/app/configuracao-modos/'+selectedMode+'/'+selectedClass+'/exemplos/',types={},items=[],selected=null,documentId=null,version=0,active=false,rectangles=[],home=null,svg=null,canvas=null;
    var list=el('div',undefined,'n5-pav-tabs'),note=el('p','Selecione um exemplo para ver seus recortes.');root.append(list,note);
    var start=el('button','Recortar exemplo','btn'),clear=el('button','Limpar seleção'),save=el('button','Recortar e salvar','btn'),cancel=el('button','Cancelar recorte'),remove=el('button','Remover recorte');
    [start,clear,save,cancel,remove].forEach(function(b){b.type='button';root.appendChild(b);});
    var options=el('div'),details=[];root.appendChild(options);
    function rows(){options.replaceChildren();rectangles.forEach(function(r,i){var value=details[i]||(details[i]={kind:'',name:''}),row=el('div',undefined,'drawing-config-grid'),type=el('select'),name=el('input');type.appendChild(new Option('Selecione o tipo…',''));Object.keys(types).forEach(function(k){type.appendChild(new Option(types[k],k));});type.value=value.kind;type.onchange=function(){value.kind=type.value;};name.maxLength=120;name.value=value.name;name.oninput=function(){value.name=name.value;};var label=el('label','Recorte '+(i+1)+' — Tipo / vista');label.appendChild(type);row.appendChild(label);label=el('label','Recorte '+(i+1)+' — Nome (opcional)');label.appendChild(name);row.appendChild(label);var discard=el('button','×','btn-sec');discard.type='button';discard.style.width='32px';discard.style.height='32px';discard.style.alignSelf='end';discard.style.justifySelf='end';discard.setAttribute('aria-label','Excluir seleção do recorte '+(i+1));discard.title='Excluir este retângulo';discard.onclick=function(){if(busy)return;rectangles.splice(i,1);details.splice(i,1);draw();rows();};row.appendChild(discard);options.appendChild(row);});options.hidden=!active||!rectangles.length;}
    function controls(){start.hidden=active||!documentId||!data.can_edit;clear.hidden=save.hidden=cancel.hidden=!active;options.hidden=!active||!rectangles.length;remove.hidden=!selected||!data.can_edit;}
    function draw(){if(!svg)return;svg.querySelectorAll('.example-crop-area').forEach(function(n){n.remove();});rectangles.forEach(function(r){var n=document.createElementNS('http://www.w3.org/2000/svg','rect');n.setAttribute('class','example-crop-area');n.setAttribute('x',home[0]+r[0]*home[2]);n.setAttribute('y',home[1]+r[1]*home[3]);n.setAttribute('width',(r[2]-r[0])*home[2]);n.setAttribute('height',(r[3]-r[1])*home[3]);n.setAttribute('fill','#22aaff');n.setAttribute('fill-opacity','.12');n.setAttribute('stroke','#22aaff');n.setAttribute('stroke-width','2');n.setAttribute('vector-effect','non-scaling-stroke');svg.appendChild(n);});}
    async function request(url,opts){var r=await fetch(url,opts),v=await r.json();if(!r.ok)throw new Error(typeof v.detail==='string'?v.detail:'Falha no recorte.');return v;}
    function renderList(){list.replaceChildren();var original=el('button','Original','n5-pav-tab'+(!selected?' on':''));original.type='button';original.onclick=function(){if(busy)return;active=false;show(current()).catch(fail);};list.appendChild(original);items.forEach(function(item){var b=el('button',item.label+' · '+item.name,'n5-pav-tab'+(selected&&selected.id===item.id?' on':''));b.type='button';b.onclick=function(){if(busy)return;active=false;show(current(),item).catch(fail);};list.appendChild(b);});controls();}
    function fail(e){note.textContent=e.message;}
    async function select(frame,crop){var v=++version;selected=crop||null;active=false;rectangles=[];details=[];rows();documentId=frame&&frame.id;controls();if(!frame){list.replaceChildren();return;}try{var result=await request(base+frame.id+'/recortes');if(v!==version||!root.isConnected)return;items=result.crops;types=result.types;renderList();note.textContent=crop?crop.entities+' entidades no recorte.':'Desenhe um ou mais retângulos, escolha o tipo e salve.';}catch(e){fail(e);}}
    start.onclick=async function(){var frame=current();if(!frame||busy)return;start.disabled=true;note.textContent='Preparando recorte…';try{await request(base+frame.id+'/recortes/original');await show(frame,{id:'original',name:'Original'});active=true;selected=null;rectangles=[];controls();note.textContent='Arraste com o botão esquerdo para recortar; botão do meio para mover; scroll para zoom.';}catch(e){fail(e);}finally{start.disabled=false;}};
    clear.onclick=function(){if(busy)return;rectangles=[];details=[];draw();rows();};cancel.onclick=function(){if(busy)return;active=false;show(current()).catch(fail);};
    save.onclick=async function(){if(busy)return;if(!rectangles.length||rectangles.some(function(r,i){return !details[i]||!details[i].kind;})){note.textContent='Desenhe as áreas e selecione o tipo de cada recorte.';return;}busy=true;save.disabled=clear.disabled=cancel.disabled=true;var done=0,last=null,total=rectangles.length;dialog.querySelectorAll('[role=tab]').forEach(function(n){n.disabled=true;});options.querySelectorAll('input,select').forEach(function(n){n.disabled=true;});try{for(var i=0;i<total;i++){note.textContent='Processando recorte '+(i+1)+' de '+total+'…';var result=await request(base+documentId+'/recortes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:details[i].kind,name:details[i].name,rectangles:[rectangles[i]]})});done++;last=result.crop;items=result.crops;}active=false;await show(current(),last);}catch(e){rectangles.splice(0,done);details.splice(0,done);renderList();rows();draw();note.textContent=done+' de '+total+' recortes salvos. '+e.message+' Os restantes continuam selecionados.';}finally{busy=false;save.disabled=clear.disabled=cancel.disabled=false;dialog.querySelectorAll('[role=tab]').forEach(function(n){n.disabled=false;});options.querySelectorAll('input,select').forEach(function(n){n.disabled=false;});}};
    remove.onclick=async function(){if(!selected||busy)return;busy=true;remove.disabled=true;try{await request(base+documentId+'/recortes/'+selected.id,{method:'DELETE'});await show(current());}catch(e){fail(e);}finally{busy=false;remove.disabled=false;}};
    controls();
    return {select:select,attach:function(c,s,frame,crop){canvas=c;svg=s;home=s.getAttribute('viewBox').split(/[\s,]+/).map(Number);var begin=null,index=-1;
      function point(e){var p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;var m=svg.getScreenCTM();if(!m)return null;p=p.matrixTransform(m.inverse());return [Math.max(0,Math.min(1,(p.x-home[0])/home[2])),Math.max(0,Math.min(1,(p.y-home[1])/home[3]))];}
      canvas.addEventListener('pointerdown',function(e){if(!active||e.button!==0)return;e.preventDefault();e.stopImmediatePropagation();if(busy)return;begin=point(e);if(!begin)return;index=rectangles.length;rectangles.push([begin[0],begin[1],begin[0],begin[1]]);canvas.setPointerCapture(e.pointerId);},true);
      canvas.addEventListener('pointermove',function(e){if(!begin)return;e.stopImmediatePropagation();var p=point(e);if(!p)return;rectangles[index]=[Math.min(begin[0],p[0]),Math.min(begin[1],p[1]),Math.max(begin[0],p[0]),Math.max(begin[1],p[1])];draw();},true);
      function stop(e){if(!begin)return;e.stopImmediatePropagation();var r=rectangles[index];if(r[2]-r[0]<.001||r[3]-r[1]<.001)rectangles.splice(index,1);begin=null;draw();rows();}
      canvas.addEventListener('pointerup',stop,true);canvas.addEventListener('pointercancel',stop,true);
    }};
  }
  function select(parent, text, value, choices, update) {
    var label = el('label'); label.appendChild(el('span',text)); var control = el('select'); control.disabled = !data.can_edit;
    choices.forEach(function(choice){var option=el('option',choice === 'PRESERVAR' ? 'Manter desenho atual' : choice);option.value=choice;control.appendChild(option);});control.value=value;
    control.addEventListener('change',function(){update(control.value);status.textContent='Alterações ainda não salvas nesta aba.';});label.appendChild(control);parent.appendChild(label);
  }
  function input(parent, text, value, type, update) {
    var label = el('label'); var control = el('input'); control.type = type; control.disabled = !data.can_edit;
    if (type === 'checkbox') control.checked = value; else control.value = value;
    if (type === 'number') control.step = 'any';
    control.addEventListener('input', function () { update(type === 'checkbox' ? control.checked : type === 'number' ? Number(control.value) : control.value); status.textContent = 'Alterações ainda não salvas nesta aba.'; });
    if (type === 'checkbox') { label.appendChild(control); label.appendChild(el('span',text)); } else { label.appendChild(el('span',text)); label.appendChild(control); }
    parent.appendChild(label); return control;
  }
  function render() {
    var address=new URL(location.href);address.searchParams.set('modo',mode);address.searchParams.set('classe',cls);address.searchParams.set('categoria',category);history.replaceState(null,'',address);

    tabs('drawing-config-modes',data.mode_labels,mode,function (key) { mode = key; render(); });
    tabs('drawing-config-classes',data.classes,cls,function (key) { cls = key; render(); });
    var sub=document.getElementById('drawing-config-categories');if(!sub){sub=el('div');sub.id='drawing-config-categories';sub.setAttribute('role','tablist');sub.setAttribute('aria-label','Tipos de configuração');fields.before(sub);}
    var categories={components:'Componentes',texts:'Textos',hatches:'Hachuras',dimensions:'Cotas',layout:'Disposição',layers:'Layers',frame:'Moldura',legends:'Índices e Legendas',examples:'Exemplos',special:'Detalhes especiais',legacy:'Referência legada'};
    if(cls==='PL')categories.drilling='Furações';
    if(!categories[category])category='components';
    tabs('drawing-config-categories',categories,category,function(key){category=key;render();});
    fields.replaceChildren(); status.textContent = data.can_edit ? 'Os campos editáveis influenciam a próxima geração N3.' : 'Somente o dono pode alterar configurações globais.';
    form.querySelector('[type=submit]').disabled = !data.can_edit || busy;
    form.querySelector('[type=submit]').hidden = category === 'frame' || category === 'legends' || category === 'examples' || category === 'legacy';
    var value = data.modes[mode][cls];
    if(mode==='INI'&&cls==='LJ'&&!['frame','legends','examples','legacy'].includes(category)){
      status.textContent='Lajes INI usam o mesmo desenho e perfil NOVA. Altere os campos em Modo Nova → Lajes.';
      form.querySelector('[type=submit]').disabled=true;
      fields.appendChild(el('p',status.textContent));
      var shared=el('button','Editar perfil NOVA de lajes','btn');shared.type='button';
      shared.onclick=function(){mode='NOVA';render();};fields.appendChild(shared);
      return;
    }
    var roles=data.roles[cls];
    if(category==='drilling'&&cls==='PL'){
      var drill=value.drilling,box=section('Furações dos painéis A–H','drilling'),grid=el('div',undefined,'drawing-config-grid');box.appendChild(grid);
      box.appendChild(el('p','O X acompanha os eixos dos parafusos realmente desenhados na visão cima, na escala real do painel. Faces sem parafuso não recebem furação. O Y parte da base e soma os intervalos abaixo; aberturas e limites dos painéis são respeitados.'));
      input(grid,'Gerar furações na próxima geração N3',drill.enabled,'checkbox',function(v){drill.enabled=v;});
      input(grid,'Diâmetro do furo (cm)',drill.diameter_cm,'number',function(v){drill.diameter_cm=v;});
      input(grid,'Afastamento mínimo do eixo à borda (cm)',drill.edge_clearance_cm,'number',function(v){drill.edge_clearance_cm=v;});
      Object.keys(drill.faces).forEach(function(face){input(grid,'Face '+face,drill.faces[face],'checkbox',function(v){drill.faces[face]=v;});});
      ['ab','cdefgh'].forEach(function(key){var group=drill[key],part=section(key==='ab'?'Distribuição vertical — A / B':'Distribuição vertical — C / D / E / F / G / H','drilling'),g=el('div',undefined,'drawing-config-grid');part.appendChild(g);
        input(g,'Base até o primeiro furo (cm)',group.first_cm,'number',function(v){group.first_cm=v;});
        input(g,'Distância mínima até o topo do painel (cm)',group.top_clearance_cm,'number',function(v){group.top_clearance_cm=v;});
        group.steps_cm.forEach(function(step,i){input(g,'Furo '+(i+1)+' → '+(i+2)+' (cm)',step,'number',function(v){group.steps_cm[i]=v;});});
        part.appendChild(el('small','Referência vertical do legado: 30 cm da base, 50 cm entre os dois primeiros e 55 cm nos seguintes. Após o décimo, repete o último intervalo. A configuração fica isolada neste modo.'));
      });
    }
    if(['texts','hatches','dimensions'].indexOf(category)>=0 && data.current){
      fields.appendChild(el('p',data.current.verified?'Padrões extraídos dos geradores atuais. Contratos verificados: '+data.current.contracts.join('; ')+'. Categorias com mais de um valor preservam suas variações.':'Os geradores mudaram após esta medição. Os valores abaixo são referências da última verificação; os padrões variáveis foram preservados. Atualize a medição para preencher os valores atuais.'));
    }
    if(category==='components')Object.keys(value.view_components).forEach(function(view){
      var box=section('Componentes — '+roles.views[view],'components'),g=el('div',undefined,'drawing-config-grid');box.appendChild(g);
      Object.keys(value.view_components[view]).forEach(function(key){input(g,data.components[key],value.view_components[view][key],'checkbox',function(v){value.view_components[view][key]=v;});});
    });
    ['texts','hatches','dimensions'].forEach(function(group){
      if(category!==group)return;
      Object.keys(value[group]).forEach(function(role){
        var box=section(roles[group][role],group),g=el('div',undefined,'drawing-config-grid');box.appendChild(g);
        var options=value[group][role];
        var measured=data.current&&data.current.modes[mode]&&data.current.modes[mode][cls];
        var actual=measured&&measured[group]&&measured[group][role];
        if(actual){
          var actualLabels={height:'Altura (cm)',text_height:'Texto da cota (cm)',arrow_size:'Seta / traço (cm)',pattern_scale:'Escala DXF',pattern:'Padrão',angle:'Ângulo',rotation:'Rotação',style:'Estilo',color:'ACI da entidade',resolved_color:'ACI do layer / entidade',dimension_text_color:'ACI do texto da cota',dimension_line_color:'ACI da linha da cota',dimension_extension_color:'ACI da extensão',precision:'Decimais',gap:'Distância texto / linha'};
          var details=Object.keys(actualLabels).filter(function(key){return actual[key]&&actual[key].length;}).map(function(key){return actualLabels[key]+': '+actual[key].join(' / ');});
          box.appendChild(el('p','Valores medidos no N3 atual: '+details.join(' · ')));
        }else box.appendChild(el('p','Não emitido nos contratos verificados. Mantém a regra atual quando o componente existir; nenhum valor foi copiado do legado.'));
        box.appendChild(el('small','Valores únicos estão preenchidos. -1 / PRESERVAR mantêm valores variáveis; os fatores multiplicam o tamanho atual.'));
        input(g,'Incluir',options.enabled,'checkbox',function(v){options.enabled=v;});
        input(g,group==='hatches'?'Fator da escala do padrão':group==='dimensions'?'Fator da altura do texto da cota':'Fator da altura do texto',options.scale,'number',function(v){options.scale=v;});
        input(g,'Cor ACI (0 mantém; 256 ByLayer)',options.color,'number',function(v){options.color=v;});
        if(group==='hatches'){
          input(g,'Escala DXF do padrão (-1 mantém)',options.pattern_scale,'number',function(v){options.pattern_scale=v;});
          select(g,'Padrão',options.pattern,Array.from(new Set(['PRESERVAR','SOLID','ANSI31','ANSI32','AR-CONC',options.pattern].concat(actual&&actual.pattern||[]))),function(v){options.pattern=v;});
          input(g,'Ângulo (999 mantém o atual)',options.angle,'number',function(v){options.angle=v;});
        }else{
          input(g,'Estilo (PRESERVAR mantém o atual)',options.style,'text',function(v){options.style=v;});
          if(group==='texts'){
            input(g,'Altura do texto em cm (-1 mantém)',options.height,'number',function(v){options.height=v;});
            input(g,'Rotação (999 mantém a atual)',options.rotation,'number',function(v){options.rotation=v;});
          }
          else{
            input(g,'Altura do texto da cota em cm (-1 mantém)',options.text_height,'number',function(v){options.text_height=v;});
            input(g,'Tamanho da seta / traço em cm (-1 mantém)',options.arrow_size,'number',function(v){options.arrow_size=v;});
            input(g,'Fator do tamanho das setas',options.arrow_scale,'number',function(v){options.arrow_scale=v;});
            input(g,'Casas decimais (-1 mantém)',options.precision,'number',function(v){options.precision=v;});
            input(g,'Distância texto / linha (-1 mantém)',options.gap,'number',function(v){options.gap=v;});
          }
        }
      });
    });
    if(category==='layout'){
    var layout=section('Disposição do desenho','layout'),layoutGrid=el('div',undefined,'drawing-config-grid');layout.appendChild(layoutGrid);
    Object.keys(value.layout).forEach(function(key){input(layoutGrid,labels[key]||key,value.layout[key],typeof value.layout[key]==='boolean'?'checkbox':'number',function(v){value.layout[key]=v;});});
    }
    if(category==='special'){
    var special=section('Detalhes especiais — '+data.mode_labels[mode],'special');
    special.appendChild(el('p',mode==='INI'?'O Modo iNI usa os nomes e a paleta dos layers legados e cores por layer. Os sarrafos sólidos são convertidos em MLINE central SAR3, com largura da seção. Sarrafos HIDDEN e DASHED continuam como linhas. A geometria estrutural é preservada.':mode==='MOLDE_1'&&cls==='LJ'?'Lajes Formascia: contorno e divisões verdes; geometria, nomes, cotas e hachuras preservados. Consulte as regras completas abaixo.':mode==='MOLDE_1'&&['PL','FV'].includes(cls)?'Formascia usa o padrão aprovado desta classe. Painéis verdes; sarrafos vermelhos e detalhes nativos do original. Consulte as regras completas abaixo.':mode==='NOVA'?'O Modo Nova conserva o desenho atual: sarrafos com a representação geométrica emitida pelo motor, layers e cores atuais.':'Este modo começou como uma cópia independente da configuração do Modo Nova. Alterações feitas aqui não modificam o Nova nem os outros Moldes.'));
    if(cls==='PL'&&mode==='MOLDE_1')special.appendChild(el('p','Grades Formascia: horizontais a 50 / 120 / 180 cm acima da base; fechamento superior apenas com dois ou mais montantes contíguos. A lista é editável em Disposição.'));
    if(cls==='PL'&&mode!=='MOLDE_1')special.appendChild(el('p','As posições horizontais das grades também diferem: o padrão iNI começa em 60 / 170 / 280 cm; o padrão Nova em 30 / 120 / 210 cm. A lista completa é editável em Disposição.'));
    if(cls==='LJ')special.appendChild(el('p','Lajes não possuem um remapeamento de layers legado específico. As opções salvas deste modo controlam planta, textos, cotas e hachuras.'));
    var specialGrid=el('div',undefined,'drawing-config-grid');special.appendChild(specialGrid);
    select(specialGrid,'Representação dos sarrafos sólidos',value.special.sarrafo_representation,['PADRAO','LINE','MLINE'],function(v){value.special.sarrafo_representation=v;});
    select(specialGrid,'Cores por layer',value.special.bylayer,['PADRAO','SIM','NAO'],function(v){value.special.bylayer=v;});
    special.appendChild(el('p',mode==='MOLDE_1'&&cls==='LJ'?'Lajes Formascia preservam o desenho do motor e alteram somente a cor do contorno e das divisões dos painéis para verde ACI 3. Não há conversão de sarrafos nesta classe.':mode==='MOLDE_1'&&cls==='FV'?'Fundos Formascia usam MLINE FORMASCIA-FV-7: seção 7 cm, horizontal 30 cm, recuo 2 cm; reforço extra curto junto ao recorte e vertical prolongado 7 cm. Chanfros acompanham a diagonal.':mode==='MOLDE_1'&&cls==='PL'?'Formascia preserva MLINE nativa: EEEEEEEE/SAR15 nos pilares e FORMASCIA-FV-7 nos fundos. C/D a partir de 30 cm têm somente sarrafos horizontais nas extremidades. Linhas tracejadas são preservadas.':'PADRAO segue o modo. LINE conserva a geometria em linhas/polilinhas. MLINE usa SAR3 nos sarrafos sólidos; linhas tracejadas são preservadas.'));
    var noteLabel=el('label','Anotações humanas'),note=el('textarea');note.rows=6;note.maxLength=20000;note.value=value.human_notes;note.disabled=!data.can_edit;note.addEventListener('input',function(){value.human_notes=note.value;status.textContent='Anotações ainda não salvas.';});noteLabel.appendChild(note);special.appendChild(noteLabel);
    }
    if(category==='layers'){
    var styles = section('Tipos de linha e padrões de hachura por layer','layers');
    Object.keys(value.layer_styles).forEach(function(source){
      var row=el('div',undefined,'drawing-config-grid');styles.appendChild(el('h4',source));styles.appendChild(row);
      select(row,'Tipo de linha',value.layer_styles[source].linetype,['PRESERVAR','CONTINUOUS','DASHED','HIDDEN','CENTER'],function(v){value.layer_styles[source].linetype=v;});
      select(row,'Hachura',value.layer_styles[source].hatch_pattern,['PRESERVAR','SOLID','ANSI31','ANSI32','AR-CONC'],function(v){value.layer_styles[source].hatch_pattern=v;});
    });
    if (value.grade_positions_cm) {
      var grades = section('Grades de pilares','layout');
      input(grades,'Posições horizontais desde a base, em cm (separadas por ponto e vírgula)',value.grade_positions_cm.join('; '),'text',function(v) { value.grade_positions_cm = v.split(';').map(function(n){return Number(n.trim().replace(',','.'));}); });
    }
    var layers = section('Layers — nome, cor ACI e inclusão','layers');
    Object.keys(value.layers).forEach(function (source) {
      var row = el('div',undefined,'drawing-config-layer'); layers.appendChild(row); row.appendChild(el('span',source));
      var measuredLayers=data.current&&data.current.modes[mode]&&data.current.modes[mode][cls]&&data.current.modes[mode][cls].layers;
      var measuredLayer=measuredLayers&&measuredLayers[source];
      if(measuredLayer)row.appendChild(el('small',(data.current.verified?'N3 atual':'Última medição — desatualizada')+' — ACI: '+(measuredLayer.color||['layer ausente']).join(' / ')+(measuredLayer.entity_linetype?' · linhas: '+measuredLayer.entity_linetype.join(' / '):'')+(measuredLayer.hatch_pattern?' · hachuras: '+measuredLayer.hatch_pattern.join(' / '):'')));
      input(row,'Nome',value.layers[source].name,'text',function(v){value.layers[source].name=v;});
      var color = input(row,'Cor ACI',value.layers[source].color,'number',function(v){value.layers[source].color=v;}); color.min=1; color.max=255; color.step=1;
      input(row,'Incluir',value.layers[source].enabled,'checkbox',function(v){value.layers[source].enabled=v;});
    });
    }
    if(category==='legacy'){
    var legacy = el('details',undefined,'drawing-config-legacy'); fields.appendChild(legacy);
    legacy.hidden=category!=='legacy';legacy.open=true;
    legacy.appendChild(el('summary','Configurações originais do PySide — inventário completo'));
    legacy.appendChild(el('p','Referência do legado. Os comandos AutoCAD/LISP e os campos sem equivalência implementada no motor Python ainda não são editáveis. Use os controles acima para configurar o N3.'));
    var native = data.legacy[cls.split('_')[0]];
    Object.keys(native).forEach(function(zone){
      legacy.appendChild(el('h4',zone)); var table=el('table'); legacy.appendChild(table);
      function walk(values,path) { Object.keys(values).forEach(function(key){var v=values[key], p=path.concat(key); if(v && typeof v==='object' && !Array.isArray(v)){walk(v,p);return;} var row=el('tr'); row.appendChild(el('td',p.join(' / '))); row.appendChild(el('td',Array.isArray(v)?v.join('; '):String(v))); table.appendChild(row);}); }
      walk(native[zone].values,[]);
    });
    }
    if(category==='frame'||category==='legends'||category==='examples'){status.textContent='Documentos guardados separadamente para visualização.';framePanel(category==='examples',category==='legends');}
  }
  async function load() {
    fields.textContent='Carregando configurações…';status.textContent='';
    try { var response=await fetch('/app/configuracao-modos',{cache:'no-store'});if(!response.ok)throw new Error('Não foi possível carregar as configurações.');data=await response.json();
      if(!data.modes[mode])mode='INI';if(!data.classes[cls])cls='PL';
      if(['components','texts','hatches','dimensions','layout','layers','frame','legends','examples','special','legacy','drilling'].indexOf(category)<0)category='components';render();
    }catch(error){fields.textContent=error.message;form.querySelector('[type=submit]').disabled=true;}
  }
  load();
  form.addEventListener('submit',async function(event){
    event.preventDefault(); if(busy || !data || !data.can_edit)return;
    busy=true;dialog.querySelectorAll('[role=tab]').forEach(function(button){button.disabled=true;});form.querySelector('[type=submit]').disabled=true;status.textContent='Salvando…';
    var savedMode=mode,savedClass=cls;
    try { var response=await fetch('/app/configuracao-modos/'+savedMode+'/'+savedClass,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:data.revision,settings:data.modes[savedMode][savedClass]})}); var result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Verifique os campos da configuração.');data.revision=result.revision;data.modes[savedMode][savedClass]=result.settings;status.textContent='Configuração '+data.mode_labels[savedMode]+' / '+data.classes[savedClass]+' salva. Gere o N3 para aplicar.'; }
    catch(error){status.textContent=error.message;}
    finally{busy=false;dialog.querySelectorAll('[role=tab]').forEach(function(button){button.disabled=false;});form.querySelector('[type=submit]').disabled=false;}
  });
}());
