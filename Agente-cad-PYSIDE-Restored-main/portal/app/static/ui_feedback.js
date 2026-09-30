(function () {
  'use strict';
  var cfg = window.PORTAL_UI_FEEDBACK;
  if (!cfg) return;

  var startButton = document.getElementById('ui-feedback-start');
  var addPageNavButton = document.getElementById('ui-feedback-add-page');
  var openButton = document.getElementById('ui-feedback-open');
  var dialog = document.getElementById('ui-feedback-dialog');
  var editor = document.getElementById('ui-feedback-editor');
  var history = document.getElementById('ui-feedback-history');
  var sessionViewer = document.getElementById('ui-feedback-session-viewer');
  var viewerTitle = document.getElementById('ui-feedback-viewer-title');
  var viewerMeta = document.getElementById('ui-feedback-viewer-meta');
  var viewerTabs = document.getElementById('ui-feedback-viewer-tabs');
  var viewerPoints = document.getElementById('ui-feedback-viewer-points');
  var hoverBox = document.getElementById('ui-feedback-hover-box');
  var modeHint = document.getElementById('ui-feedback-mode');
  var message = document.getElementById('ui-feedback-message');
  var sessionTitle = document.getElementById('ui-feedback-session-title');
  var pageTabs = document.getElementById('ui-feedback-page-tabs');
  var pointsBox = document.getElementById('ui-feedback-points');
  var list = document.getElementById('ui-feedback-list');
  var onlyMine = document.getElementById('ui-feedback-only-mine');
  var selected = null;
  var selecting = false;
  var selectionSequence = 0;
  var lastTrigger = null;
  var cachedPageCssText = null;
  var draft = null;
  var activePageIndex = 0;
  var selectionIntent = 'same';
  var draftDbPromise = null;
  var viewedSession = null;
  var viewedPageIndex = 0;
  var viewedPointIndex = 0;

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
      rect: {left:rect.left,top:rect.top,width:rect.width,height:rect.height},
      ancestry: ancestryFor(element)
    };
  }

  function ancestryFor(element) {
    var result = [];
    var node = element;
    while (node && node.nodeType === 1 && node !== document.body && result.length < 6) {
      var label = node.getAttribute('aria-label') || node.getAttribute('title') || safeText(node).slice(0, 120);
      result.push({tag:node.tagName.toLowerCase(), selector:selectorFor(node).slice(0, 400), label:label});
      node = node.parentElement;
    }
    return result;
  }

  function visible(element) {
    if (!element) return false;
    var rect = element.getBoundingClientRect();
    var style = window.getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  }

  function selectedControlInfo(element) {
    var data = {};
    Array.prototype.forEach.call(element.attributes || [], function (attr) {
      if (attr.name.indexOf('data-') === 0 && attr.value) data[attr.name] = attr.value.slice(0, 200);
    });
    return {
      selector: selectorFor(element).slice(0, 400),
      text: safeText(element).slice(0, 160),
      data: data
    };
  }

  function pageState() {
    var query = {};
    new URLSearchParams(window.location.search).forEach(function (value, key) {
      if (key !== '_apontamento') query[key] = value;
    });
    var selectedControls = [];
    var selectedSelector = [
      '[aria-selected="true"]', '[aria-pressed="true"]',
      'button.active', 'button.ativo', 'tr.selected',
      '[data-lj-layer].active', '[data-fv-layer].active',
      '[data-lv-layer].active', '[data-lv-side].active',
      '[data-lv-segment-tab].active'
    ].join(',');
    Array.prototype.forEach.call(document.querySelectorAll(selectedSelector), function (element) {
      if (!visible(element) || selectedControls.length >= 8) return;
      var item = selectedControlInfo(element);
      if (!selectedControls.some(function (known) { return known.selector === item.selector; })) selectedControls.push(item);
    });
    var itemHeading = document.querySelector('#laje-ficha-root h2,#fv-ficha-root h2,#lv-ficha-root h2,#pillar-ficha-root h2');
    var layer = document.querySelector('[data-lj-layer].active,[data-fv-layer].active,[data-lv-layer].active');
    var side = document.querySelector('[data-lv-side].active');
    var segment = document.querySelector('[data-lv-segment-tab].active,[data-fv-focus].active,.fv-web-seg-row.selected');
    var svgs = [];
    Array.prototype.forEach.call(document.querySelectorAll('svg'), function (svg) {
      if (!visible(svg) || svgs.length >= 6) return;
      var box = svg.viewBox && svg.viewBox.baseVal;
      svgs.push({
        selector: selectorFor(svg),
        viewBox: box ? {x:box.x,y:box.y,width:box.width,height:box.height} : null
      });
    });
    var drillState = window.DrillGrade && window.DrillGrade.state;
    var scrollContainers = [];
    Array.prototype.forEach.call(document.querySelectorAll('.drill-scroll,.painel-obra-corpo,#painel-status-corpo,.fv-web-table-scroll,.ui-feedback-history'), function (element) {
      if (!visible(element) || scrollContainers.length >= 12 || (element.scrollHeight <= element.clientHeight && element.scrollWidth <= element.clientWidth)) return;
      scrollContainers.push({selector:selectorFor(element),top:element.scrollTop,left:element.scrollLeft});
    });
    return {
      version: 3,
      location: {pathname:window.location.pathname, query:query, hash:window.location.hash},
      scroll: {x:window.scrollX, y:window.scrollY},
      viewport: {
        width:window.innerWidth, height:window.innerHeight,
        devicePixelRatio:window.devicePixelRatio || 1,
        visualScale:window.visualViewport ? window.visualViewport.scale : 1
      },
      context: {
        breadcrumb:safeText(document.getElementById('drill-root') || document.body).slice(0, 700),
        item:itemHeading ? safeText(itemHeading).slice(0, 200) : '',
        layer:layer ? (layer.getAttribute('data-lj-layer') || layer.getAttribute('data-fv-layer') || layer.getAttribute('data-lv-layer') || safeText(layer).slice(0, 100)) : '',
        side:side ? (side.getAttribute('data-lv-side') || safeText(side).slice(0, 100)) : '',
        segment:segment ? safeText(segment).slice(0, 160) : ''
      },
      navigation: {
        drill: drillState ? {
          level:drillState.level, pav:drillState.pav, etapa:drillState.etapa,
          classe:drillState.classe, vigaKey:drillState.vigaKey,
          itemId:drillState.itemId, selDoc:drillState.selDoc,
          rightTorre:!!drillState.rightTorre
        } : null
      },
      selectedControls:selectedControls,
      scrollContainers:scrollContainers,
      visibleSvgViewBoxes:svgs,
      focusedElement:document.activeElement && document.activeElement !== document.body ? selectorFor(document.activeElement) : ''
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
    document.removeEventListener('pointerdown', startBox, true);
    endBoxTracking();
  }

  function cancelSelection() {
    selectionSequence += 1;
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
    if (boxDrag && boxDrag.active) { hoverBox.hidden = true; return; }
    var target = event.target;
    if (ignored(target)) { hoverBox.hidden = true; return; }
    var rect = target.getBoundingClientRect();
    hoverBox.style.left = Math.max(0, rect.left) + 'px';
    hoverBox.style.top = Math.max(0, rect.top) + 'px';
    hoverBox.style.width = Math.max(1, Math.min(rect.width, innerWidth - Math.max(0, rect.left))) + 'px';
    hoverBox.style.height = Math.max(1, Math.min(rect.height, innerHeight - Math.max(0, rect.top))) + 'px';
    hoverBox.hidden = false;
  }

  function captureScale() {
    // Preserve the capture quality already used by the portal. Performance is
    // gained by flattening complex CAD graphics, not by lowering resolution.
    return Math.min(Math.max(window.devicePixelRatio || 1, 1), 1.25);
  }

  function isVisibleInViewport(element) {
    var rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.right > 0 && rect.bottom > 0 &&
      rect.left < window.innerWidth && rect.top < window.innerHeight;
  }

  function capturePlaceholder(element) {
    var rect = element.getBoundingClientRect();
    var style = window.getComputedStyle(element);
    var placeholder = document.createElement('div');
    placeholder.setAttribute('data-ui-feedback-capture-placeholder', '');
    placeholder.setAttribute('aria-hidden', 'true');
    placeholder.style.boxSizing = 'border-box';
    placeholder.style.display = style.display === 'inline' ? 'inline-block' : style.display;
    placeholder.style.width = Math.max(1, rect.width) + 'px';
    placeholder.style.height = Math.max(1, rect.height) + 'px';
    placeholder.style.background = style.backgroundColor || '#101827';
    placeholder.style.border = style.border;
    placeholder.style.borderRadius = style.borderRadius;
    return placeholder;
  }

  function pageCssText() {
    if (cachedPageCssText !== null) return cachedPageCssText;
    var css = '';
    Array.prototype.forEach.call(document.styleSheets, function (sheet) {
      try {
        Array.prototype.forEach.call(sheet.cssRules || [], function (rule) { css += rule.cssText + '\n'; });
      } catch (error) {
        // Cross-origin stylesheets cannot be inspected. SVG presentation
        // attributes and same-origin portal CSS still preserve the drawing.
      }
    });
    cachedPageCssText = css;
    return cachedPageCssText;
  }

  function rasterizeSvg(svg, scale, cssText) {
    var rect = svg.getBoundingClientRect();
    if (!rect.width || !rect.height) return Promise.resolve(null);
    var clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', rect.width);
    clone.setAttribute('height', rect.height);
    if (cssText) {
      var style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
      style.textContent = cssText;
      clone.insertBefore(style, clone.firstChild);
    }
    var source = new XMLSerializer().serializeToString(clone);
    var sourceUrl = URL.createObjectURL(new Blob([source], {type:'image/svg+xml;charset=utf-8'}));
    return new Promise(function (resolve) {
      var image = new Image();
      image.onload = function () {
        var canvas = document.createElement('canvas');
        canvas.setAttribute('data-ui-feedback-capture-raster', '');
        canvas.setAttribute('aria-hidden', 'true');
        canvas.width = Math.max(1, Math.ceil(rect.width * scale));
        canvas.height = Math.max(1, Math.ceil(rect.height * scale));
        canvas.style.width = rect.width + 'px';
        canvas.style.height = rect.height + 'px';
        var svgStyle = window.getComputedStyle(svg);
        canvas.style.display = svgStyle.display;
        // Camadas sobrepostas (ex.: destaques do viewer) são SVG absolutos com
        // z-index; sem copiar o posicionamento o canvas cai no fluxo, por baixo do fundo.
        if (svgStyle.position !== 'static') {
          canvas.style.position = svgStyle.position;
          canvas.style.left = svgStyle.left;
          canvas.style.top = svgStyle.top;
          canvas.style.zIndex = svgStyle.zIndex;
        }
        try {
          canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
          resolve(canvas);
        } catch (error) { resolve(null); }
        URL.revokeObjectURL(sourceUrl);
      };
      image.onerror = function () { URL.revokeObjectURL(sourceUrl); resolve(null); };
      image.src = sourceUrl;
    });
  }

  function prepareCaptureGraphics(scale) {
    var replacements = [];
    var graphics = Array.prototype.filter.call(document.querySelectorAll('svg'), function (svg) {
      // Nested SVGs travel together with their outer drawing.
      return !svg.parentElement || !svg.parentElement.closest('svg');
    });
    var cssText = pageCssText();
    return Promise.all(graphics.map(function (svg) {
      var complex = svg.getElementsByTagName('*').length > 80;
      if (!complex) return Promise.resolve();
      if (!isVisibleInViewport(svg)) {
        var offscreenPlaceholder = capturePlaceholder(svg);
        if (svg.parentNode) {
          svg.parentNode.replaceChild(offscreenPlaceholder, svg);
          replacements.push({original:svg, replacement:offscreenPlaceholder});
        }
        return Promise.resolve();
      }
      return rasterizeSvg(svg, scale, cssText).then(function (raster) {
        if (raster && svg.parentNode) {
          svg.parentNode.replaceChild(raster, svg);
          replacements.push({original:svg, replacement:raster});
        }
      });
    })).then(function () {
      return function restoreGraphics() {
        replacements.reverse().forEach(function (entry) {
          if (entry.replacement.parentNode) entry.replacement.parentNode.replaceChild(entry.original, entry.replacement);
        });
      };
    });
  }

  function encodeCapture(canvas) {
    var webp = canvas.toDataURL('image/webp', .92);
    if (webp.indexOf('data:image/webp;base64,') === 0) return webp;
    return canvas.toDataURL('image/jpeg', .92);
  }

  function markTarget(context, targetRect, scaleX, scaleY) {
    if (!targetRect) return;
    var left = Math.max(0, targetRect.left) * scaleX;
    var top = Math.max(0, targetRect.top) * scaleY;
    var right = Math.min(window.innerWidth, targetRect.left + targetRect.width) * scaleX;
    var bottom = Math.min(window.innerHeight, targetRect.top + targetRect.height) * scaleY;
    if (right <= left || bottom <= top) return;
    context.save();
    context.strokeStyle = '#ef4444';
    context.lineWidth = 3 * Math.max(scaleX, scaleY);
    context.setLineDash([8 * scaleX, 5 * scaleX]);
    context.strokeRect(left + 2, top + 2, Math.max(1, right - left - 4), Math.max(1, bottom - top - 4));
    context.restore();
  }

  function makeScreenshot(clickX, clickY, targetRect) {
    if (typeof window.html2canvas !== 'function') return Promise.resolve(null);
    hoverBox.hidden = true;
    modeHint.hidden = true;
    var scale = captureScale();
    var restoreGraphics = function () {};
    return prepareCaptureGraphics(scale).then(function (restore) {
      restoreGraphics = restore;
      return window.html2canvas(document.body, {
        x: window.scrollX,
        y: window.scrollY,
        width: window.innerWidth,
        height: window.innerHeight,
        scale: scale,
        backgroundColor: '#ffffff',
        logging: false,
        useCORS: true,
        imageTimeout: 3000,
        ignoreElements: function (element) { return element.hasAttribute && element.hasAttribute('data-ui-feedback-ignore'); }
      });
    }).then(function (canvas) {
      var scaleX = canvas.width / window.innerWidth;
      var scaleY = canvas.height / window.innerHeight;
      var context = canvas.getContext('2d');
      markTarget(context, targetRect, scaleX, scaleY);
      if (clickX != null) {
      context.beginPath();
      context.arc(clickX * scaleX, clickY * scaleY, 12 * Math.max(scaleX, scaleY), 0, Math.PI * 2);
      context.fillStyle = 'rgba(239,68,68,.32)'; context.fill();
      context.lineWidth = 4 * Math.max(scaleX, scaleY); context.strokeStyle = '#ef4444'; context.stroke();
      }
      return encodeCapture(canvas);
    }).catch(function () { return null; }).finally(function () { restoreGraphics(); });
  }

  function draftKey() { return 'member:' + cfg.membroId; }

  function openDraftDb() {
    if (draftDbPromise) return draftDbPromise;
    draftDbPromise = new Promise(function (resolve, reject) {
      var request = indexedDB.open('cad-portal-ui-feedback', 1);
      request.onupgradeneeded = function () { if (!request.result.objectStoreNames.contains('drafts')) request.result.createObjectStore('drafts'); };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error); };
    });
    return draftDbPromise;
  }

  function storeDraft() {
    updateNavButtons();
    return openDraftDb().then(function (db) { return new Promise(function (resolve, reject) {
      var tx=db.transaction('drafts','readwrite');
      if (draft) tx.objectStore('drafts').put(draft,draftKey()); else tx.objectStore('drafts').delete(draftKey());
      tx.oncomplete=resolve; tx.onerror=function(){reject(tx.error);};
    }); }).catch(function () { /* rascunho segue vivo nesta aba */ });
  }

  function restoreDraft() {
    return openDraftDb().then(function (db) { return new Promise(function (resolve, reject) {
      var request=db.transaction('drafts','readonly').objectStore('drafts').get(draftKey());
      request.onsuccess=function(){resolve(request.result||null);}; request.onerror=function(){reject(request.error);};
    }); }).then(function (saved) {
      draft=saved; activePageIndex=Math.max(0,Math.min((draft&&draft.activePage)||0,(draft&&draft.pages.length-1)||0)); updateNavButtons();
    }).catch(function(){ updateNavButtons(); });
  }

  function updateNavButtons() {
    var label=startButton.querySelector('.nav-texto');
    if (label) label.textContent=draft?'Continuar apontamento':'Fazer apontamento';
    startButton.title=draft?'Abrir o rascunho do apontamento':'Selecione qualquer elemento desta página para registrar um comentário';
    addPageNavButton.hidden=!draft;
  }

  function syncDraftFromEditor() {
    if (!draft || editor.hidden) return;
    draft.title=sessionTitle.value.slice(0,500);
    var page=draft.pages[activePageIndex];
    if (!page) return;
    pointsBox.querySelectorAll('[data-ui-feedback-point-text]').forEach(function (field) {
      var index=Number(field.getAttribute('data-ui-feedback-point-text'));
      if (page.points[index]) page.points[index].text=field.value.slice(0,4000);
    });
    draft.activePage=activePageIndex;
  }

  function pointNav(index,total,attr) {
    if(total<2) return '';
    var style='style="border:1px solid #7dd3fc;background:#fff;border-radius:6px;cursor:pointer;font-size:1rem;line-height:1;padding:3px 10px;margin-left:6px"';
    return '<span class="ui-feedback-point-nav" style="display:inline-flex;align-items:center;margin-left:8px">'+
      '<button type="button" '+style+' '+attr+'="-1" aria-label="Ponto anterior" title="Ponto anterior"'+(index<=0?' disabled':'')+'>‹</button>'+
      '<button type="button" '+style+' '+attr+'="1" aria-label="Próximo ponto" title="Próximo ponto"'+(index>=total-1?' disabled':'')+'>›</button></span>';
  }

  function pointContext(point) {
    var context=point.pageState&&point.pageState.context;
    var parts=context?[context.item,context.layer,context.side,context.segment].filter(Boolean):[];
    var sel=point.selection;
    if(sel){
      var names=(sel.destaques||[]).map(function(item){return item.rotulo;}).filter(Boolean);
      if(names.length) parts.push((sel.modo==='box'?'Box: ':'Destaque: ')+names.slice(0,12).join(', ')+(names.length>12?' … +'+(names.length-12):''));
      else if(sel.modo==='box') parts.push('Box: '+(sel.elementos||[]).length+' elemento(s)');
      if(sel.estrutural){
        var labels=(sel.estrutural.textos||[]).map(function(item){return item.texto;}).filter(function(text){return /^(V|VF|VB|P|L|LJ)\s?-?\d/i.test(text);});
        labels=labels.filter(function(text,index){return labels.indexOf(text)===index;});
        parts.push('Estrutural: '+sel.estrutural.total+' entidade(s)'+(labels.length?' ('+labels.slice(0,15).join(', ')+(labels.length>15?' …':'')+')':''));
      } else if(sel.regioes_dxf&&sel.regioes_dxf.length) parts.push('Região DXF registrada');
    }
    return parts.join(' · ');
  }

  function setupImageZoom(root) {
    if (!root) return;
    root.querySelectorAll('[data-ui-feedback-zoom]').forEach(function(viewport){
      var image=viewport.querySelector('img');
      if(!image)return;
      var scale=1, panX=0, panY=0, dragging=false, startX=0, startY=0, startPanX=0, startPanY=0;
      var level=viewport.querySelector('[data-ui-feedback-zoom-level]');
      var reset=viewport.querySelector('[data-ui-feedback-zoom-reset]');
      function clampPan(){
        var rect=viewport.getBoundingClientRect();
        var maxX=Math.max(0,rect.width*(scale-1)/2), maxY=Math.max(0,rect.height*(scale-1)/2);
        panX=Math.max(-maxX,Math.min(maxX,panX)); panY=Math.max(-maxY,Math.min(maxY,panY));
      }
      function paint(){
        clampPan(); image.style.transform='translate('+panX+'px,'+panY+'px) scale('+scale+')';
        viewport.classList.toggle('is-zoomed',scale>1.001); if(level)level.textContent=Math.round(scale*100)+'%';
      }
      function resetZoom(){scale=1;panX=0;panY=0;paint();}
      viewport.addEventListener('wheel',function(event){
        event.preventDefault();
        var rect=viewport.getBoundingClientRect(), oldScale=scale;
        scale=Math.max(1,Math.min(6,scale*Math.exp(-event.deltaY*.0015)));
        var ratio=scale/oldScale, localX=event.clientX-(rect.left+rect.width/2), localY=event.clientY-(rect.top+rect.height/2);
        panX=localX-(localX-panX)*ratio; panY=localY-(localY-panY)*ratio; paint();
      },{passive:false});
      viewport.addEventListener('pointerdown',function(event){
        if(scale<=1 || event.button!==0 || event.target.closest('button,a'))return;
        dragging=true;startX=event.clientX;startY=event.clientY;startPanX=panX;startPanY=panY;
        viewport.classList.add('is-dragging');viewport.setPointerCapture(event.pointerId);event.preventDefault();
      });
      viewport.addEventListener('pointermove',function(event){if(!dragging)return;panX=startPanX+event.clientX-startX;panY=startPanY+event.clientY-startY;paint();});
      function stopDrag(event){if(!dragging)return;dragging=false;viewport.classList.remove('is-dragging');if(viewport.hasPointerCapture(event.pointerId))viewport.releasePointerCapture(event.pointerId);}
      viewport.addEventListener('pointerup',stopDrag);viewport.addEventListener('pointercancel',stopDrag);
      viewport.addEventListener('dblclick',function(event){if(!event.target.closest('button,a'))resetZoom();});
      viewport.addEventListener('keydown',function(event){
        if(event.key==='0'||event.key==='Home'){event.preventDefault();resetZoom();return;}
        if(event.key!=='+'&&event.key!=='='&&event.key!=='-')return;
        event.preventDefault();scale=Math.max(1,Math.min(6,scale*(event.key==='-'?.8:1.25)));paint();
      });
      if(reset)reset.addEventListener('click',resetZoom);
      paint();
    });
  }

  function renderDraft() {
    if (!draft || !draft.pages.length) return;
    editor.hidden=false; history.hidden=true; sessionViewer.hidden=true;
    sessionTitle.value=draft.title||'';
    pageTabs.innerHTML=draft.pages.map(function(page,index){return '<button type="button" role="tab" aria-selected="'+(index===activePageIndex?'true':'false')+'" data-ui-feedback-page="'+index+'">Página '+(index+1)+'<small>'+esc(page.title||'Página do portal')+'</small><b>'+page.points.length+' ponto(s)</b></button>';}).join('');
    var page=draft.pages[activePageIndex];
    var activePointIndex=Math.max(0,Math.min(Number(page.activePoint)||0,page.points.length-1));
    page.activePoint=activePointIndex;
    var activePoint=page.points[activePointIndex];
    var capture='<div class="ui-feedback-capture-loading">Preparando captura…</div>';
    if(activePoint&&activePoint.screenshot) capture='<img src="'+activePoint.screenshot+'" alt="Captura marcada do ponto '+(activePointIndex+1)+' da página '+(activePageIndex+1)+'">';
    pointsBox.innerHTML='<section class="ui-feedback-capture-stage" aria-label="Captura da página selecionada"><div class="ui-feedback-page-summary"><div><b>Página '+(activePageIndex+1)+' · ponto '+(activePointIndex+1)+' de '+page.points.length+pointNav(activePointIndex,page.points.length,'data-ui-feedback-step-point')+'</b><span>'+esc(page.url)+'</span></div><a href="'+esc(page.url)+'">Abrir localização ↗</a></div><div class="ui-feedback-point-media" data-ui-feedback-zoom tabindex="0" aria-label="Captura com zoom. Use a roda do mouse para ampliar ou reduzir e arraste para mover."><div class="ui-feedback-zoom-tools"><span data-ui-feedback-zoom-level>100%</span><button type="button" data-ui-feedback-zoom-reset>Redefinir zoom</button></div>'+capture+'</div></section><section class="ui-feedback-comments-pane" aria-label="Apontamentos desta página"><div class="ui-feedback-comments-head"><div><b>Apontamentos desta página</b><span>Selecione um ponto para visualizar sua captura acima.</span></div><strong>'+page.points.length+' ponto(s)</strong></div><div class="ui-feedback-comments-scroll">'+page.points.map(function(point,index){var context=pointContext(point);return '<article class="ui-feedback-point-card'+(index===activePointIndex?' active':'')+'"><div class="ui-feedback-point-card-head"><button type="button" class="ui-feedback-point-select" data-ui-feedback-show-point="'+index+'" aria-pressed="'+(index===activePointIndex?'true':'false')+'"><span class="ui-feedback-point-number">'+(index+1)+'</span><span>Ver captura do ponto '+(index+1)+'</span></button><button type="button" class="ui-feedback-remove-point" data-ui-feedback-remove-point="'+index+'">Remover ponto</button></div><div class="ui-feedback-point-form"><div class="ui-feedback-selected-meta"><b>'+esc(point.info.tag+(point.info.role?' · '+point.info.role:''))+'</b><span>'+esc(point.info.selector)+'</span>'+(context?'<span><strong>Contexto:</strong> '+esc(context)+'</span>':'')+(point.info.text?'<span>“'+esc(point.info.text.slice(0,260))+(point.info.text.length>260?'…':'')+'”</span>':'')+'</div><label>O que deve ser ajustado neste ponto?<textarea maxlength="4000" rows="3" data-ui-feedback-point-text="'+index+'" placeholder="Descreva o comportamento esperado ou o problema observado">'+esc(point.text||'')+'</textarea></label></div></article>';}).join('')+'</div></section>';
    setupImageZoom(pointsBox);
    pageTabs.querySelectorAll('[data-ui-feedback-page]').forEach(function(button){button.addEventListener('click',function(){syncDraftFromEditor();activePageIndex=Number(button.dataset.uiFeedbackPage);renderDraft();storeDraft();});});
    pointsBox.querySelectorAll('[data-ui-feedback-step-point]').forEach(function(button){button.addEventListener('click',function(){syncDraftFromEditor();page.activePoint=Math.max(0,Math.min(page.points.length-1,activePointIndex+Number(button.dataset.uiFeedbackStepPoint)));renderDraft();storeDraft();});});
    pointsBox.querySelectorAll('[data-ui-feedback-show-point]').forEach(function(button){button.addEventListener('click',function(){syncDraftFromEditor();page.activePoint=Number(button.dataset.uiFeedbackShowPoint);renderDraft();storeDraft();});});
    pointsBox.querySelectorAll('[data-ui-feedback-remove-point]').forEach(function(button){button.addEventListener('click',function(){syncDraftFromEditor();var index=Number(button.dataset.uiFeedbackRemovePoint);page.points.splice(index,1);page.activePoint=Math.max(0,Math.min(Number(page.activePoint)||0,page.points.length-1));if(!page.points.length){draft.pages.splice(activePageIndex,1);activePageIndex=Math.max(0,activePageIndex-1);}if(!draft.pages.length){draft=null;if(dialog.open)dialog.close();}else renderDraft();storeDraft();});});
    pointsBox.querySelectorAll('[data-ui-feedback-point-text]').forEach(function(field){field.addEventListener('input',function(){syncDraftFromEditor();storeDraft();});});
    message.className='ui-feedback-message'; message.textContent='Rascunho salvo automaticamente. Você pode minimizar e navegar sem perder as capturas.';
    document.getElementById('ui-feedback-dialog-title').textContent='Montar apontamento';
    document.getElementById('ui-feedback-dialog-subtitle').textContent='Várias páginas e pontos dentro do mesmo apontamento';
    if (!dialog.open) dialog.showModal();
  }

  // ---- Seleção por box e leitura do que está sob o ponto/box -------------
  // Clique simples = ponto; arrastar = box. Os dois registram os destaques do
  // viewer sob a seleção (rótulo do <title>) e a região em coordenadas DXF.
  var boxDrag = null;
  var dragBox = document.createElement('div');
  dragBox.setAttribute('data-ui-feedback-ignore', '');
  dragBox.hidden = true;
  dragBox.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;border:2px dashed #ef4444;background:rgba(239,68,68,.08);box-sizing:border-box';
  document.body.appendChild(dragBox);
  var BOX_MIN_PX = 8;

  function startBox(event) {
    if (event.button !== 0 || ignored(event.target)) return;
    // Em modo apontamento o arraste é do box, não do pan do viewer.
    event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation();
    boxDrag = {x:event.clientX, y:event.clientY, active:false};
    document.addEventListener('pointermove', moveBox, true);
    document.addEventListener('pointerup', finishBox, true);
    document.addEventListener('pointercancel', endBoxTracking, true);
  }

  function boxRectFrom(event) {
    var left = Math.min(boxDrag.x, event.clientX), top = Math.min(boxDrag.y, event.clientY);
    return {left:left, top:top, width:Math.abs(event.clientX - boxDrag.x), height:Math.abs(event.clientY - boxDrag.y)};
  }

  function moveBox(event) {
    if (!boxDrag) return;
    var rect = boxRectFrom(event);
    if (!boxDrag.active && rect.width < BOX_MIN_PX && rect.height < BOX_MIN_PX) return;
    boxDrag.active = true; hoverBox.hidden = true;
    dragBox.style.left = rect.left + 'px'; dragBox.style.top = rect.top + 'px';
    dragBox.style.width = rect.width + 'px'; dragBox.style.height = rect.height + 'px';
    dragBox.hidden = false;
  }

  function endBoxTracking() {
    boxDrag = null; dragBox.hidden = true;
    document.removeEventListener('pointermove', moveBox, true);
    document.removeEventListener('pointerup', finishBox, true);
    document.removeEventListener('pointercancel', endBoxTracking, true);
  }

  function swallowNextClick() {
    function swallow(event) { event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation(); done(); }
    function done() { document.removeEventListener('click', swallow, true); }
    document.addEventListener('click', swallow, true);
    setTimeout(done, 400);
  }

  function finishBox(event) {
    if (!boxDrag) return;
    var active = boxDrag.active, rect = boxRectFrom(event);
    endBoxTracking();
    if (!active) return; // clique simples: o handler de click registra o ponto
    event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation();
    stopSelecting(); swallowNextClick();
    var cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
    var element = document.elementFromPoint(cx, cy) || document.body;
    if (ignored(element)) element = document.body;
    registerCapture(element, {clientX:null, clientY:null, pageX:cx + window.scrollX, pageY:cy + window.scrollY}, rect);
  }

  function pointInRect(x, y, r) { return x >= r.left && x <= r.left + r.width && y >= r.top && y <= r.top + r.height; }

  function pointInPolygon(x, y, pts) {
    var inside = false;
    for (var i = 0, j = pts.length - 1; i < pts.length; j = i++) {
      var xi = pts[i][0], yi = pts[i][1], xj = pts[j][0], yj = pts[j][1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-9) + xi)) inside = !inside;
    }
    return inside;
  }

  function segmentsCross(a, b, c, d) {
    function orient(p, q, r) { return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]); }
    var o1 = orient(a, b, c), o2 = orient(a, b, d), o3 = orient(c, d, a), o4 = orient(c, d, b);
    return ((o1 > 0) !== (o2 > 0)) && ((o3 > 0) !== (o4 > 0));
  }

  // 'dentro' | 'toca' | null — polígono (tela) contra o retângulo da seleção.
  function polygonVsRect(pts, r) {
    if (!pts.length) return null;
    var inCount = pts.filter(function (p) { return pointInRect(p[0], p[1], r); }).length;
    if (inCount === pts.length) return 'dentro';
    if (inCount) return 'toca';
    var corners = [[r.left, r.top], [r.left + r.width, r.top], [r.left + r.width, r.top + r.height], [r.left, r.top + r.height]];
    if (corners.some(function (c) { return pointInPolygon(c[0], c[1], pts); })) return 'toca';
    for (var i = 0; i < pts.length; i++) {
      var a = pts[i], b = pts[(i + 1) % pts.length];
      for (var k = 0; k < 4; k++) if (segmentsCross(a, b, corners[k], corners[(k + 1) % 4])) return 'toca';
    }
    return null;
  }

  function screenPoints(poly) {
    var ctm = poly.getScreenCTM && poly.getScreenCTM();
    if (!ctm || !poly.points) return [];
    var out = [];
    for (var i = 0; i < poly.points.numberOfItems; i++) {
      var p = poly.points.getItem(i);
      out.push([ctm.a * p.x + ctm.c * p.y + ctm.e, ctm.b * p.x + ctm.d * p.y + ctm.f]);
    }
    return out;
  }

  function round1(value) { return Math.round(value * 10) / 10; }

  // Retângulo de tela → coordenadas do DXF (inverso de dxf_preview.dxf_para_px).
  function dxfRegion(overlay, r) {
    var bbox, fonte;
    try { bbox = JSON.parse(overlay.getAttribute('data-bbox-dxf') || 'null'); } catch (e) { bbox = null; }
    try { fonte = JSON.parse(overlay.getAttribute('data-fonte') || 'null'); } catch (e) { fonte = null; }
    var home = (overlay.getAttribute('data-home-vb') || '').split(/\s+/).map(Number);
    var ctm = overlay.getScreenCTM && overlay.getScreenCTM();
    if (!bbox || bbox.length !== 4 || home.length !== 4 || !ctm) return null;
    var inv = ctm.inverse(), w = home[2] || 1, h = home[3] || 1;
    function toDxf(sx, sy) {
      var px = inv.a * sx + inv.c * sy + inv.e, py = inv.b * sx + inv.d * sy + inv.f;
      return [bbox[0] + px / w * (bbox[2] - bbox[0]), bbox[3] - py / h * (bbox[3] - bbox[1])];
    }
    var p0 = toDxf(r.left, r.top), p1 = toDxf(r.left + r.width, r.top + r.height);
    return {
      pavimento: overlay.getAttribute('data-pavimento') || '', fonte: fonte,
      x0: round1(Math.min(p0[0], p1[0])), y0: round1(Math.min(p0[1], p1[1])),
      x1: round1(Math.max(p0[0], p1[0])), y1: round1(Math.max(p0[1], p1[1]))
    };
  }

  var BOX_ELEMENT_QUERY = '[data-handle],[data-layer],button,a,[role="tab"],tr,th,h1,h2,h3,h4,label,svg text';

  function collectSelection(r, modo) {
    var destaques = [], regioes = [], elementos = [];
    Array.prototype.forEach.call(document.querySelectorAll('svg.destaque-overlay'), function (overlay) {
      if (!visible(overlay)) return;
      var vr = overlay.getBoundingClientRect();
      var clip = {left:Math.max(r.left, vr.left), top:Math.max(r.top, vr.top)};
      clip.width = Math.min(r.left + r.width, vr.right) - clip.left;
      clip.height = Math.min(r.top + r.height, vr.bottom) - clip.top;
      if (clip.width < 0 || clip.height < 0) return;
      var region = dxfRegion(overlay, clip);
      if (region) regioes.push(region);
      Array.prototype.forEach.call(overlay.querySelectorAll('polygon'), function (poly) {
        if (destaques.length >= 80) return;
        var estado = polygonVsRect(screenPoints(poly), r);
        if (!estado) return;
        var title = poly.querySelector('title');
        destaques.push({rotulo:(poly.getAttribute('data-rotulo') || (title && title.textContent) || '').slice(0, 120),
          grupo:poly.getAttribute('data-grupo') || '', estado:estado});
      });
    });
    if (modo === 'box') {
      Array.prototype.forEach.call(document.querySelectorAll(BOX_ELEMENT_QUERY), function (element) {
        if (elementos.length >= 40 || ignored(element) || element.closest('svg.destaque-overlay')) return;
        var er = element.getBoundingClientRect();
        if (er.width <= 0 && er.height <= 0) return;
        var dentro = er.left >= r.left && er.top >= r.top && er.right <= r.left + r.width && er.bottom <= r.top + r.height;
        var toca = !(er.right < r.left || er.left > r.left + r.width || er.bottom < r.top || er.top > r.top + r.height);
        if (!toca) return;
        var item = {tag:element.tagName.toLowerCase(), estado:dentro ? 'dentro' : 'toca', texto:safeText(element).slice(0, 120)};
        ['data-handle', 'data-layer', 'data-type'].forEach(function (name) { var v = element.getAttribute(name); if (v) item[name] = v.slice(0, 80); });
        if (!item.texto && !item['data-handle']) return;
        item.seletor = selectorFor(element).slice(0, 200);
        elementos.push(item);
      });
    }
    return {modo:modo, box:{left:round1(r.left), top:round1(r.top), width:round1(r.width), height:round1(r.height)},
      destaques:destaques, regioes_dxf:regioes, elementos:elementos};
  }

  var pendingWork = [];
  function trackPending(promise) {
    pendingWork.push(promise);
    promise.then(function(){pendingWork=pendingWork.filter(function(item){return item!==promise;});},function(){pendingWork=pendingWork.filter(function(item){return item!==promise;});});
  }

  function fetchStructural(selection) {
    var region=(selection.regioes_dxf||[])[0];
    if(!region||!cfg.obraId||!region.pavimento) return Promise.resolve(null);
    var q='x0='+region.x0+'&y0='+region.y0+'&x1='+region.x1+'&y1='+region.y1;
    return fetch('/obras/'+encodeURIComponent(cfg.obraId)+'/viewer/'+encodeURIComponent(region.pavimento)+'/regiao?'+q,{credentials:'same-origin'})
      .then(function(response){return response.ok?response.json():null;})
      .then(function(data){
        if(!data) return null;
        return {arquivo:data.arquivo,total:data.total,truncado:data.truncado,por_layer:data.por_layer,textos:data.textos,entidades:data.entidades};
      }).catch(function(){return null;});
  }

  function chooseTarget(event) {
    if (ignored(event.target)) return;
    event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation(); stopSelecting();
    registerCapture(event.target, event, null);
  }

  function registerCapture(element, event, box) {
    element.classList.add('ui-feedback-captured-target');
    var info=elementInfo(element), state=pageState(), captureId=++selectionSequence;
    // Ponto: tolerância de 8 px em volta do clique para achar o destaque sob o dedo.
    var selRect=box||{left:event.clientX-8,top:event.clientY-8,width:16,height:16};
    var selection=collectSelection(selRect, box?'box':'ponto');
    var structuralRequest=box?fetchStructural(selection):null;
    if(box) info.rect={left:box.left,top:box.top,width:box.width,height:box.height};
    selected={id:captureId,element:element};
    if (!draft) draft={version:3,title:'',pages:[],activePage:0,createdAt:new Date().toISOString()};
    var page;
    if (selectionIntent==='new' || !draft.pages.length) {
      page={id:'page-'+Date.now()+'-'+Math.random().toString(16).slice(2),url:window.location.href,title:document.title,points:[],activePoint:0};
      draft.pages.push(page); activePageIndex=draft.pages.length-1;
    } else page=draft.pages[activePageIndex];
    var point={id:'point-'+Date.now()+'-'+Math.random().toString(16).slice(2),text:'',info:info,pageState:state,selection:selection,clickX:event.clientX,clickY:event.clientY,pageX:event.pageX,pageY:event.pageY,viewportWidth:window.innerWidth,viewportHeight:window.innerHeight,screenshot:null};
    page.points.push(point); page.activePoint=page.points.length-1; draft.activePage=activePageIndex; selectionIntent='same';
    editor.setAttribute('aria-busy','true'); renderDraft(); storeDraft();
    if(structuralRequest) trackPending(structuralRequest.then(function(result){ if(result){selection.estrutural=result; if(dialog.open)renderDraft(); storeDraft();} }));
    makeScreenshot(event.clientX,event.clientY,info.rect).then(function(dataUrl){
      if (!draft) return; point.screenshot=dataUrl; editor.setAttribute('aria-busy','false');
      if(selected&&selected.id===captureId&&selected.element)selected.element.classList.remove('ui-feedback-captured-target');
      selected=null; if(dialog.open)renderDraft(); storeDraft();
      if(!dataUrl){message.className='ui-feedback-message error';message.textContent='Não foi possível gerar esta captura; o contexto e o comentário ainda podem ser salvos.';}
    });
  }

  function beginSelection(intent) {
    lastTrigger=intent==='new'?addPageNavButton:startButton; syncDraftFromEditor();
    storeDraft().then(function(){if(dialog.open)dialog.close();cancelSelection();selectionIntent=intent||'same';selecting=true;document.body.classList.add('ui-feedback-selecting');modeHint.hidden=false;modeHint.textContent=(selectionIntent==='new'?'Clique no primeiro ponto da nova página':'Clique em outro ponto desta página')+' ou arraste um box · Esc cancela';document.addEventListener('pointermove',hoverTarget,true);document.addEventListener('pointerdown',startBox,true);document.addEventListener('click',chooseTarget,true);document.addEventListener('keydown',cancelWithEscape,true);});
  }

  function minimizeDialog() { syncDraftFromEditor();storeDraft();if(dialog.open)dialog.close();updateNavButtons(); }

  function closeDialog() { if(editor.hidden){if(dialog.open)dialog.close();}else minimizeDialog();if(lastTrigger)lastTrigger.focus(); }

  function discardDraft() { if(!draft)return;if(!confirm('Descartar todas as páginas, capturas e comentários deste rascunho?'))return;draft=null;activePageIndex=0;storeDraft();if(dialog.open)dialog.close(); }

  // Comentário por ponto é opcional; o backend exige texto, então vai o título
  // do apontamento ou um marcador explícito.
  function pointText(point) { return (point.text||'').trim() || ((draft&&draft.title||'').trim() ? '(sem comentário no ponto) '+draft.title.trim() : '(sem comentário no ponto)'); }

  // O servidor recusa contexto > 20 KB: corta primeiro as listas longas da seleção.
  function fitSelection(point) {
    var sel=point.selection; if(!sel) return null;
    var copy=JSON.parse(JSON.stringify(sel));
    function size(){return JSON.stringify({target:point.info,pageState:point.pageState,selection:copy}).length;}
    var lists=[function(){return copy.estrutural&&copy.estrutural.entidades;},function(){return copy.elementos;},function(){return copy.estrutural&&copy.estrutural.textos;},function(){return copy.destaques;}];
    for(var i=0;i<lists.length&&size()>18500;i++){var list=lists[i]();while(list&&list.length&&size()>18500){list.pop();copy.cortado=true;}}
    return copy;
  }

  function pointPayload(point,page) { return {texto:pointText(point).slice(0,4000),pagina_url:page.url,pagina_titulo:page.title,seletor_elemento:point.info.selector,elemento_tag:point.info.tag,elemento_role:point.info.role,elemento_texto:point.info.text,elemento:{version:3,target:point.info,pageState:point.pageState,selection:fitSelection(point),capture:{mime:point.screenshot?point.screenshot.slice(5,point.screenshot.indexOf(';')):null,scale:captureScale(),width:Math.round(point.viewportWidth*captureScale()),height:Math.round(point.viewportHeight*captureScale())}},clique_x:point.clickX!=null?point.clickX:(point.info.rect?point.info.rect.left+point.info.rect.width/2:null),clique_y:point.clickY!=null?point.clickY:(point.info.rect?point.info.rect.top+point.info.rect.height/2:null),pagina_x:point.pageX,pagina_y:point.pageY,viewport_largura:point.viewportWidth,viewport_altura:point.viewportHeight,captura_data_url:point.screenshot}; }

  function saveSession() {
    if(pendingWork.length){message.className='ui-feedback-message';message.textContent='Lendo o estrutural do box…';Promise.all(pendingWork).then(saveSession,saveSession);return;}
    syncDraftFromEditor();
    var button=dialog.querySelector('[data-ui-feedback-save]');button.disabled=true;message.className='ui-feedback-message';message.textContent='Salvando '+draft.pages.length+' página(s)…';
    var body={obra_id:cfg.obraId||null,titulo:(draft.title||'').trim()||null,paginas:draft.pages.map(function(page){return {pagina_url:page.url,pagina_titulo:page.title,pontos:page.points.map(function(point){return pointPayload(point,page);})};})};
    api('/sessoes',{method:'POST',body:JSON.stringify(body)}).then(function(){draft=null;activePageIndex=0;return storeDraft();}).then(function(){showHistory();}).catch(function(error){message.className='ui-feedback-message error';message.textContent='Falha ao salvar: '+error.message;}).finally(function(){button.disabled=false;});
  }

  function formatDate(value) {
    try { return new Date(value).toLocaleString('pt-BR'); } catch (e) { return value || ''; }
  }

  var RESTORE_PARAM = '_apontamento';
  var RESTORE_PREFIX = 'cad.portal.feedback.restore.';

  function feedbackRestoreUrl(url, point) {
    if (!point || !point.id) return url;
    try {
      var target = new URL(url, window.location.origin);
      target.searchParams.set(RESTORE_PARAM, point.id);
      return target.pathname + target.search + target.hash;
    } catch (e) { return url; }
  }

  function rememberRestoreState(point) {
    var state=point&&point.elemento&&point.elemento.pageState;
    if (!point || !point.id || !state) return;
    try { window.sessionStorage.setItem(RESTORE_PREFIX+point.id,JSON.stringify(state)); } catch (e) { /* URL simples continua válido */ }
  }

  function selectedNow(element) {
    return element && (element.classList.contains('active') || element.classList.contains('ativo') || element.classList.contains('selected') || element.getAttribute('aria-selected')==='true' || element.getAttribute('aria-pressed')==='true');
  }

  function findByData(data) {
    var keys=Object.keys(data||{});
    for(var k=0;k<keys.length;k++) {
      var key=keys[k], nodes=document.querySelectorAll('['+key+']');
      for(var i=0;i<nodes.length;i++) if(nodes[i].getAttribute(key)===String(data[key])) return nodes[i];
    }
    return null;
  }

  function replaySelectedControls(state, attempt) {
    var controls=(state.selectedControls||[]).slice().sort(function(a,b){
      function priority(item){var d=item.data||{};if(d['data-lv-side'])return 1;if(d['data-lv-segment']||d['data-lv-segment-tab']||d['data-fv-focus'])return 2;if(d['data-lj-layer']||d['data-fv-layer']||d['data-lv-layer'])return 3;return 4;}
      return priority(a)-priority(b);
    });
    var missing=false;
    controls.forEach(function(control){
      var element=findByData(control.data);
      if (!element && control.selector) { try { element=document.querySelector(control.selector); } catch(e) { element=null; } }
      if (!element) { missing=true; return; }
      if (!selectedNow(element) && typeof element.click==='function') element.click();
    });
    if(missing && attempt<12) window.setTimeout(function(){replaySelectedControls(state,attempt+1);},350);
  }

  function restoreViewportState(state) {
    (state.visibleSvgViewBoxes||[]).forEach(function(saved){
      var svg; try { svg=document.querySelector(saved.selector); } catch(e) { svg=null; }
      if(svg&&saved.viewBox) svg.setAttribute('viewBox',[saved.viewBox.x,saved.viewBox.y,saved.viewBox.width,saved.viewBox.height].join(' '));
    });
    (state.scrollContainers||[]).forEach(function(saved){
      var element; try { element=document.querySelector(saved.selector); } catch(e) { element=null; }
      if(element){element.scrollTop=Number(saved.top)||0;element.scrollLeft=Number(saved.left)||0;}
    });
    if(state.scroll) window.scrollTo(Number(state.scroll.x)||0,Number(state.scroll.y)||0);
  }

  function restoreDrillState(state, attempt) {
    var snapshot=state.navigation&&state.navigation.drill;
    if(!snapshot) { replaySelectedControls(state,0);window.setTimeout(function(){restoreViewportState(state);},700);return; }
    if(!window.DrillGrade) {
      if(attempt<20) window.setTimeout(function(){restoreDrillState(state,attempt+1);},250);
      return;
    }
    if(snapshot.etapa==='sa'&&snapshot.classe&&snapshot.pav) window.DrillGrade.openSaClasse(snapshot.classe,snapshot.pav);
    window.setTimeout(function(){
      function clickDrill(act,id){if(!id)return false;var nodes=document.querySelectorAll('[data-drill="'+act+'"]');for(var i=0;i<nodes.length;i++){if(nodes[i].getAttribute('data-id')===String(id)){if(!selectedNow(nodes[i]))nodes[i].click();return true;}}return false;}
      if(snapshot.selDoc&&!snapshot.classe) clickDrill('doc',snapshot.selDoc);
      if(snapshot.vigaKey) clickDrill('viga',snapshot.vigaKey);
      window.setTimeout(function(){
        if(snapshot.itemId) clickDrill('item',snapshot.itemId);
        window.setTimeout(function(){replaySelectedControls(state,0);window.setTimeout(function(){restoreViewportState(state);},900);},500);
      },450);
    },650);
  }

  function restoreRequestedNavigation() {
    var params=new URLSearchParams(window.location.search), id=params.get(RESTORE_PARAM);
    if(!id)return;
    var raw=null;
    try { raw=window.sessionStorage.getItem(RESTORE_PREFIX+id);window.sessionStorage.removeItem(RESTORE_PREFIX+id); } catch(e) { raw=null; }
    params.delete(RESTORE_PARAM);
    window.history.replaceState(null,'',window.location.pathname+(params.toString()?'?'+params.toString():'')+window.location.hash);
    if(!raw)return;
    try {
      var state=JSON.parse(raw);
      restoreDrillState(state,0);
      modeHint.hidden=false;modeHint.textContent='Restaurando a navegação registrada no apontamento…';
      window.setTimeout(function(){modeHint.textContent='Navegação do apontamento restaurada.';window.setTimeout(function(){modeHint.hidden=true;},1800);},2600);
    } catch(e) { /* link permanece útil mesmo sem restauração */ }
  }

  function renderSavedSession() {
    if(!viewedSession || !viewedSession.paginas.length) return;
    var pages=viewedSession.paginas;
    viewedPageIndex=Math.max(0,Math.min(viewedPageIndex,pages.length-1));
    var page=pages[viewedPageIndex], points=page.pontos||[];
    viewedPointIndex=Math.max(0,Math.min(viewedPointIndex,Math.max(0,points.length-1)));
    var point=points[viewedPointIndex];
    viewerTitle.textContent=viewedSession.titulo||('Apontamento de '+(viewedSession.autor_nome||viewedSession.autor_login));
    viewerMeta.textContent=(viewedSession.autor_nome||viewedSession.autor_login)+' · '+formatDate(viewedSession.created_at)+' · '+pages.length+' página(s)';
    viewerTabs.innerHTML=pages.map(function(item,index){return '<button type="button" role="tab" aria-selected="'+(index===viewedPageIndex?'true':'false')+'" data-ui-feedback-view-page="'+index+'">Página '+(index+1)+'<small>'+esc(item.pagina_titulo||'Página do portal')+'</small><b>'+item.pontos.length+' ponto(s)</b></button>';}).join('');
    var capture=point&&point.tem_captura?'<img src="/apontamentos-ui/'+encodeURIComponent(point.id)+'/captura" alt="Captura marcada do ponto '+(viewedPointIndex+1)+' da página '+(viewedPageIndex+1)+'">':'<div class="ui-feedback-capture-loading">Este ponto não possui captura.</div>';
    viewerPoints.innerHTML='<section class="ui-feedback-capture-stage" aria-label="Captura registrada"><div class="ui-feedback-page-summary"><div><b>Página '+(viewedPageIndex+1)+' · ponto '+(viewedPointIndex+1)+' de '+points.length+pointNav(viewedPointIndex,points.length,'data-ui-feedback-step-view-point')+'</b><span>'+esc(page.pagina_url)+'</span></div>'+(point?'<a href="'+esc(feedbackRestoreUrl(page.pagina_url,point))+'" data-ui-feedback-view-restore="'+esc(point.id)+'">Abrir estado registrado ↗</a>':'')+'</div><div class="ui-feedback-point-media" data-ui-feedback-zoom tabindex="0" aria-label="Captura com zoom. Use a roda do mouse para ampliar ou reduzir e arraste para mover."><div class="ui-feedback-zoom-tools"><span data-ui-feedback-zoom-level>100%</span><button type="button" data-ui-feedback-zoom-reset>Redefinir zoom</button></div>'+capture+'</div></section><section class="ui-feedback-comments-pane" aria-label="Comentários registrados"><div class="ui-feedback-comments-head"><div><b>Apontamentos desta página</b><span>Selecione um ponto para visualizar sua captura acima.</span></div><strong>'+points.length+' ponto(s)</strong></div><div class="ui-feedback-comments-scroll">'+points.map(function(item,index){var state=item.elemento&&item.elemento.pageState,context=state&&state.context,contextText=context?[context.item,context.layer,context.side,context.segment].filter(Boolean).join(' · '):'';return '<article class="ui-feedback-point-card'+(index===viewedPointIndex?' active':'')+'"><div class="ui-feedback-point-card-head"><button type="button" class="ui-feedback-point-select" data-ui-feedback-view-point="'+index+'" aria-pressed="'+(index===viewedPointIndex?'true':'false')+'"><span class="ui-feedback-point-number">'+(index+1)+'</span><span>Ver captura do ponto '+(index+1)+'</span></button><a href="'+esc(feedbackRestoreUrl(page.pagina_url,item))+'" data-ui-feedback-view-restore="'+esc(item.id)+'">Abrir estado deste ponto ↗</a></div><div class="ui-feedback-selected-meta">'+(contextText?'<span><strong>Contexto:</strong> '+esc(contextText)+'</span>':'')+(item.elemento_texto?'<span>“'+esc(item.elemento_texto.slice(0,260))+(item.elemento_texto.length>260?'…':'')+'”</span>':'')+'</div><div class="ui-feedback-saved-comment"><b>Comentário</b><p>'+esc(item.texto)+'</p></div></article>';}).join('')+'</div></section>';
    viewerPoints.querySelectorAll('[data-ui-feedback-step-view-point]').forEach(function(button){button.addEventListener('click',function(){viewedPointIndex=Math.max(0,Math.min(points.length-1,viewedPointIndex+Number(button.dataset.uiFeedbackStepViewPoint)));renderSavedSession();});});
    setupImageZoom(viewerPoints);
    viewerTabs.querySelectorAll('[data-ui-feedback-view-page]').forEach(function(button){button.addEventListener('click',function(){viewedPageIndex=Number(button.dataset.uiFeedbackViewPage);viewedPointIndex=0;renderSavedSession();});});
    viewerPoints.querySelectorAll('[data-ui-feedback-view-point]').forEach(function(button){button.addEventListener('click',function(){viewedPointIndex=Number(button.dataset.uiFeedbackViewPoint);renderSavedSession();});});
    viewerPoints.querySelectorAll('[data-ui-feedback-view-restore]').forEach(function(link){link.addEventListener('click',function(){var target=points.filter(function(item){return item.id===link.dataset.uiFeedbackViewRestore;})[0];rememberRestoreState(target);});});
  }

  function openSavedSession(session) {
    viewedSession=session;viewedPageIndex=0;viewedPointIndex=0;
    editor.hidden=true;history.hidden=true;sessionViewer.hidden=false;
    document.getElementById('ui-feedback-dialog-title').textContent='Visualizar apontamento';
    document.getElementById('ui-feedback-dialog-subtitle').textContent='Capturas, páginas e comentários registrados';
    renderSavedSession();
  }

  function loadHistory() {
    list.innerHTML='<p>Carregando apontamentos…</p>';
    api('/sessoes'+(onlyMine.checked?'?meus=true':'')).then(function(data){
      if (!data.sessoes.length) { list.innerHTML='<p>Nenhum apontamento registrado neste filtro.</p>'; return; }
      var sessions={};
      list.innerHTML=data.sessoes.map(function(session){sessions[session.id]=session;var total=session.paginas.reduce(function(sum,page){return sum+page.pontos.length;},0),name=session.titulo||('Apontamento de '+(session.autor_nome||session.autor_login));return '<button type="button" class="ui-feedback-history-row" data-ui-feedback-view-session="'+esc(session.id)+'"><span><b>'+esc(name)+'</b><small>'+esc(session.autor_nome||session.autor_login)+' · '+esc(formatDate(session.created_at))+'</small></span><strong>'+session.paginas.length+' página(s) · '+total+' ponto(s)</strong></button>';}).join('');
      list.querySelectorAll('[data-ui-feedback-view-session]').forEach(function(button){button.addEventListener('click',function(){openSavedSession(sessions[button.dataset.uiFeedbackViewSession]);});});
    }).catch(function(error){ list.innerHTML='<p class="ui-feedback-message error">Falha ao carregar: '+esc(error.message)+'</p>'; });
  }

  function showHistory() {
    lastTrigger=openButton;
    editor.hidden=true; sessionViewer.hidden=true; history.hidden=false;
    document.getElementById('ui-feedback-dialog-title').textContent='Apontamentos do portal';
    document.getElementById('ui-feedback-dialog-subtitle').textContent='Feedback global do portal, identificado por usuário';
    if (!dialog.open) dialog.showModal();
    loadHistory();
  }

  startButton.addEventListener('click', function(){if(draft)renderDraft();else beginSelection('new');});
  addPageNavButton.addEventListener('click', function(){beginSelection('new');});
  openButton.addEventListener('click', showHistory);
  dialog.querySelector('[data-ui-feedback-close]').addEventListener('click', closeDialog);
  dialog.querySelector('[data-ui-feedback-minimize]').addEventListener('click', minimizeDialog);
  dialog.querySelector('[data-ui-feedback-discard]').addEventListener('click', discardDraft);
  dialog.querySelector('[data-ui-feedback-add-point]').addEventListener('click', function(){beginSelection('same');});
  dialog.querySelector('[data-ui-feedback-add-page]').addEventListener('click', function(){beginSelection('new');});
  dialog.querySelector('[data-ui-feedback-save]').addEventListener('click', saveSession);
  dialog.querySelector('[data-ui-feedback-refresh]').addEventListener('click', loadHistory);
  dialog.querySelector('[data-ui-feedback-back-list]').addEventListener('click', showHistory);
  onlyMine.addEventListener('change', loadHistory);
  dialog.addEventListener('cancel', function(event){ event.preventDefault(); closeDialog(); });
  window.addEventListener('pagehide', function(){syncDraftFromEditor();storeDraft();});
  restoreDraft();
  restoreRequestedNavigation();
})();
