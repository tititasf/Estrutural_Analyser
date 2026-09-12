(function () {
  'use strict';
  var cfg = window.PORTAL_UI_FEEDBACK;
  if (!cfg) return;

  var startButton = document.getElementById('ui-feedback-start');
  var openButton = document.getElementById('ui-feedback-open');
  var dialog = document.getElementById('ui-feedback-dialog');
  var editor = document.getElementById('ui-feedback-editor');
  var history = document.getElementById('ui-feedback-history');
  var hoverBox = document.getElementById('ui-feedback-hover-box');
  var modeHint = document.getElementById('ui-feedback-mode');
  var preview = document.getElementById('ui-feedback-preview');
  var textInput = document.getElementById('ui-feedback-text');
  var message = document.getElementById('ui-feedback-message');
  var selectedMeta = document.getElementById('ui-feedback-selected-meta');
  var list = document.getElementById('ui-feedback-list');
  var onlyMine = document.getElementById('ui-feedback-only-mine');
  var selected = null;
  var selecting = false;

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char];
    });
  }

  function cssEscape(value) {
    if (window.CSS && CSS.escape) return CSS.escape(value);
    return String(value).replace(/[^a-zA-Z0-9_-]/g, function (char) {
      return '\\' + char.charCodeAt(0).toString(16) + ' ';
    });
  }

  function selectorFor(element) {
    if (element.id) return '#' + cssEscape(element.id);
    var parts = [];
    var node = element;
    while (node && node.nodeType === 1 && node !== document.body && parts.length < 7) {
      var part = node.tagName.toLowerCase();
      var testId = node.getAttribute('data-testid');
      if (testId) {
        part += '[data-testid="' + String(testId).replace(/"/g, '\\"') + '"]';
        parts.unshift(part);
        break;
      }
      var parent = node.parentElement;
      if (parent) {
        var siblings = Array.prototype.filter.call(parent.children, function (item) {
          return item.tagName === node.tagName;
        });
        if (siblings.length > 1) part += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(' > ');
  }

  function safeText(element) {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(element.tagName)) {
      return element.getAttribute('aria-label') || element.getAttribute('placeholder') || element.tagName.toLowerCase();
    }
    return String(element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 2000);
  }

  function elementInfo(element) {
    var rect = element.getBoundingClientRect();
    var attrs = {};
    ['id','name','type','title','aria-label','aria-describedby','placeholder','data-action','data-acao','data-fv-layer','data-fv-seg'].forEach(function (name) {
      var value = element.getAttribute(name);
      if (value) attrs[name] = value.slice(0, 500);
    });
    var heading = element.closest('section,article,aside,main,nav');
    var headingNode = heading && heading.querySelector('h1,h2,h3,h4,[role="heading"]');
    return {
      tag: element.tagName.toLowerCase(),
      role: element.getAttribute('role') || '',
      selector: selectorFor(element),
      text: safeText(element),
      attributes: attrs,
      section: headingNode ? safeText(headingNode).slice(0, 500) : '',
      rect: {left:rect.left,top:rect.top,width:rect.width,height:rect.height}
    };
  }

  function api(path, options) {
    return fetch('/apontamentos-ui' + path, Object.assign({
      headers: {'Content-Type':'application/json'}
    }, options || {})).then(function (response) {
      if (!response.ok) return response.json().catch(function(){ return {}; }).then(function(body){
        throw new Error(body.detail || ('HTTP ' + response.status));
      });
      return response.json();
    });
  }

  function stopSelecting() {
    selecting = false;
    document.body.classList.remove('ui-feedback-selecting');
    hoverBox.hidden = true;
    modeHint.hidden = true;
    document.removeEventListener('pointermove', hoverTarget, true);
    document.removeEventListener('click', chooseTarget, true);
    document.removeEventListener('keydown', cancelWithEscape, true);
  }

  function cancelSelection() {
    stopSelecting();
    if (selected && selected.element) selected.element.classList.remove('ui-feedback-captured-target');
    selected = null;
  }

  function cancelWithEscape(event) {
    if (event.key === 'Escape') cancelSelection();
  }

  function ignored(target) {
    return !target || target.closest('[data-ui-feedback-ignore]');
  }

  function hoverTarget(event) {
    var target = event.target;
    if (ignored(target)) { hoverBox.hidden = true; return; }
    var rect = target.getBoundingClientRect();
    hoverBox.style.left = Math.max(0, rect.left) + 'px';
    hoverBox.style.top = Math.max(0, rect.top) + 'px';
    hoverBox.style.width = Math.max(1, Math.min(rect.width, innerWidth - Math.max(0, rect.left))) + 'px';
    hoverBox.style.height = Math.max(1, Math.min(rect.height, innerHeight - Math.max(0, rect.top))) + 'px';
    hoverBox.hidden = false;
  }

  function makeScreenshot(clickX, clickY) {
    if (typeof window.html2canvas !== 'function') return Promise.resolve(null);
    hoverBox.hidden = true;
    modeHint.hidden = true;
    return window.html2canvas(document.body, {
      x: window.scrollX,
      y: window.scrollY,
      width: window.innerWidth,
      height: window.innerHeight,
      scale: Math.min(window.devicePixelRatio || 1, 1.25),
      backgroundColor: '#ffffff',
      logging: false,
      useCORS: true,
      imageTimeout: 3000,
      ignoreElements: function (element) { return element.hasAttribute && element.hasAttribute('data-ui-feedback-ignore'); }
    }).then(function (canvas) {
      var scaleX = canvas.width / window.innerWidth;
      var scaleY = canvas.height / window.innerHeight;
      var context = canvas.getContext('2d');
      context.beginPath();
      context.arc(clickX * scaleX, clickY * scaleY, 12 * Math.max(scaleX, scaleY), 0, Math.PI * 2);
      context.fillStyle = 'rgba(239,68,68,.32)'; context.fill();
      context.lineWidth = 4 * Math.max(scaleX, scaleY); context.strokeStyle = '#ef4444'; context.stroke();
      return canvas.toDataURL('image/jpeg', .76);
    }).catch(function () { return null; });
  }

  function chooseTarget(event) {
    if (ignored(event.target)) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    stopSelecting();
    var element = event.target;
    element.classList.add('ui-feedback-captured-target');
    var info = elementInfo(element);
    selected = {
      element: element,
      info: info,
      clickX: event.clientX,
      clickY: event.clientY,
      pageX: event.pageX,
      pageY: event.pageY,
      screenshot: null
    };
    selectedMeta.innerHTML = '<b>' + esc(info.tag + (info.role ? ' · ' + info.role : '')) + '</b><br>' +
      esc(info.selector) + (info.text ? '<br>“' + esc(info.text.slice(0, 260)) + (info.text.length > 260 ? '…' : '') + '”' : '');
    preview.hidden = true;
    textInput.value = '';
    message.className = 'ui-feedback-message';
    message.textContent = 'Gerando captura marcada…';
    editor.hidden = false; history.hidden = true;
    // Capture antes de abrir o dialogo: assim a foto representa exatamente a
    // tela apontada, sem backdrop/modal cobrindo o elemento escolhido.
    makeScreenshot(event.clientX, event.clientY).then(function (dataUrl) {
      if (!selected) return;
      selected.screenshot = dataUrl;
      if (dataUrl) { preview.src = dataUrl; preview.hidden = false; message.textContent = ''; }
      else { message.className = 'ui-feedback-message error'; message.textContent = 'Não foi possível gerar a captura; os demais dados ainda podem ser salvos.'; }
      if (!dialog.open) dialog.showModal();
      textInput.focus();
    });
  }

  function beginSelection() {
    if (dialog.open) dialog.close();
    cancelSelection();
    selecting = true;
    document.body.classList.add('ui-feedback-selecting');
    modeHint.hidden = false;
    document.addEventListener('pointermove', hoverTarget, true);
    document.addEventListener('click', chooseTarget, true);
    document.addEventListener('keydown', cancelWithEscape, true);
  }

  function closeDialog() {
    if (dialog.open) dialog.close();
    cancelSelection();
  }

  function savePoint() {
    if (!selected) return;
    var texto = textInput.value.trim();
    if (!texto) { message.className='ui-feedback-message error'; message.textContent='Escreva o comentário do apontamento.'; textInput.focus(); return; }
    var button = dialog.querySelector('[data-ui-feedback-save]');
    button.disabled = true;
    message.className='ui-feedback-message'; message.textContent='Salvando apontamento…';
    api('', {method:'POST', body:JSON.stringify({
      texto:texto,
      obra_id:cfg.obraId || null,
      pagina_url:window.location.href,
      pagina_titulo:document.title,
      seletor_elemento:selected.info.selector,
      elemento_tag:selected.info.tag,
      elemento_role:selected.info.role,
      elemento_texto:selected.info.text,
      elemento:selected.info,
      clique_x:selected.clickX,
      clique_y:selected.clickY,
      pagina_x:selected.pageX,
      pagina_y:selected.pageY,
      viewport_largura:window.innerWidth,
      viewport_altura:window.innerHeight,
      captura_data_url:selected.screenshot
    })}).then(function () {
      message.textContent='Apontamento salvo para a comunidade.';
      if (selected && selected.element) selected.element.classList.remove('ui-feedback-captured-target');
      selected=null;
      setTimeout(function(){ showHistory(); }, 350);
    }).catch(function(error){ message.className='ui-feedback-message error'; message.textContent='Falha ao salvar: '+error.message; })
      .finally(function(){ button.disabled=false; });
  }

  function formatDate(value) {
    try { return new Date(value).toLocaleString('pt-BR'); } catch (e) { return value || ''; }
  }

  function loadHistory() {
    list.innerHTML='<p>Carregando apontamentos…</p>';
    api(onlyMine.checked ? '?meus=true' : '').then(function(data){
      if (!data.apontamentos.length) { list.innerHTML='<p>Nenhum apontamento registrado neste filtro.</p>'; return; }
      list.innerHTML=data.apontamentos.map(function(point){
        var capture = point.tem_captura ? '<a href="/apontamentos-ui/'+encodeURIComponent(point.id)+'/captura" target="_blank" rel="noopener">Ver captura marcada ↗</a>' : '<span>Sem captura</span>';
        return '<article class="ui-feedback-card"><div class="ui-feedback-card-head"><b>'+esc(point.autor_nome || point.autor_login)+'</b><time>'+esc(formatDate(point.created_at))+'</time></div>'+
          '<p>'+esc(point.texto)+'</p><div class="ui-feedback-card-meta">'+(point.obra_nome ? 'obra: '+esc(point.obra_nome)+'<br>' : 'contexto geral do portal<br>')+esc((point.elemento_tag || 'elemento')+(point.elemento_role ? ' · '+point.elemento_role : ''))+'<br>'+esc(point.seletor_elemento || '')+'<br>ponto ('+esc(Math.round(point.clique_x))+', '+esc(Math.round(point.clique_y))+') · '+esc(point.viewport_largura+'×'+point.viewport_altura)+'</div>'+
          '<div class="ui-feedback-card-head"><a href="'+esc(point.pagina_url)+'" title="Abrir a localização registrada">Abrir página registrada ↗</a>'+capture+'</div></article>';
      }).join('');
    }).catch(function(error){ list.innerHTML='<p class="ui-feedback-message error">Falha ao carregar: '+esc(error.message)+'</p>'; });
  }

  function showHistory() {
    editor.hidden=true; history.hidden=false;
    document.getElementById('ui-feedback-dialog-title').textContent='Apontamentos do portal';
    document.getElementById('ui-feedback-dialog-subtitle').textContent='Feedback global do portal, identificado por usuário';
    if (!dialog.open) dialog.showModal();
    loadHistory();
  }

  startButton.addEventListener('click', beginSelection);
  openButton.addEventListener('click', showHistory);
  dialog.querySelector('[data-ui-feedback-close]').addEventListener('click', closeDialog);
  dialog.querySelector('[data-ui-feedback-cancel]').addEventListener('click', closeDialog);
  dialog.querySelector('[data-ui-feedback-save]').addEventListener('click', savePoint);
  dialog.querySelector('[data-ui-feedback-refresh]').addEventListener('click', loadHistory);
  onlyMine.addEventListener('change', loadHistory);
  dialog.addEventListener('cancel', function(event){ event.preventDefault(); closeDialog(); });
})();
