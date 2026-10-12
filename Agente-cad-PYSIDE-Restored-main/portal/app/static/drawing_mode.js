(function () {
  'use strict';

  var modeLabels={INI:'Modo iNI',NOVA:'Modo Nova',MOLDE_1:'Formascia',MOLDE_2:'Modo Molde 2',MOLDE_3:'Modo Molde 3'};
  function normalize(value) {
    var mode=String(value||'NOVA').trim().toUpperCase();return modeLabels[mode]?mode:'NOVA';
  }

  function label(value) { return modeLabels[normalize(value)]; }

  function syncUrl(value) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set('modo_desenho', normalize(value));
      window.history.replaceState(window.history.state, '', url.toString());
    } catch (_error) { /* viewer continua funcional sem History API */ }
  }

  function choose(options) {
    options = options || {};
    var current = normalize(options.currentMode);
    return new Promise(function (resolve) {
      var dialog = document.createElement('dialog');
      dialog.className = 'drawing-mode-dialog';
      dialog.setAttribute('aria-labelledby', 'drawing-mode-title');
      dialog.innerHTML =
        '<form method="dialog">' +
          '<div class="drawing-mode-head"><div><small>ESTILO DO ARTEFATO</small>' +
          '<h2 id="drawing-mode-title">Escolha o modo de desenho</h2></div>' +
          '<button value="cancel" aria-label="Cancelar">×</button></div>' +
          '<p>' + (options.description || 'O modo escolhido será gravado no N3 e mantido na unificação N5.') + '</p>' +
          '<div class="drawing-mode-options">' + Object.keys(modeLabels).map(function(mode){return '<button value="'+mode+'" class="'+(current===mode?'selected':'')+'"><strong>'+modeLabels[mode]+'</strong><span>'+(mode==='INI'?'Perfil visual dos templates iniciais.':mode==='NOVA'?'Desenho atual.':'Perfil independente baseado no Nova.')+'</span></button>';}).join('') +
          '</div><button value="cancel" class="drawing-mode-cancel">Cancelar</button>' +
        '</form>';
      document.body.appendChild(dialog);
      var settled = false;
      function finish(value) {
        if (settled) return;
        settled = true;
        dialog.remove();
        resolve(Boolean(modeLabels[value]) ? value : null);
      }
      dialog.addEventListener('close', function () { finish(dialog.returnValue); });
      dialog.addEventListener('cancel', function (event) { event.preventDefault(); finish(null); });
      dialog.querySelectorAll('.drawing-mode-options button').forEach(function (button) {
        button.addEventListener('click', function (event) {
          event.preventDefault();
          finish(button.value);
        });
      });
      if (options.availableModes) {
        dialog.querySelectorAll('.drawing-mode-options button').forEach(function (button) {
          if (options.availableModes.indexOf(button.value) < 0) {
            button.disabled = true;
            button.querySelector('span').textContent = 'N3 deste modo ainda não está completo. Gere o N3 primeiro.';
          }
        });
      }
      dialog.showModal();
    });
  }

  function applyBadge(viewport, mode, options) {
    if (!viewport) return null;
    options = options || {};
    viewport.querySelectorAll(':scope > .drawing-mode-badge').forEach(function (badge) { badge.remove(); });
    if (!viewport.parentNode) return null;
    var tabs = viewport.previousElementSibling;
    if (!tabs || !tabs.classList.contains('drawing-mode-tabs')) {
      tabs = document.createElement('nav');
      tabs.className = 'n5-pav-tabs drawing-mode-tabs';
      tabs.setAttribute('role', 'tablist');
      tabs.setAttribute('aria-label', 'Modo de desenho N3');
      viewport.parentNode.insertBefore(tabs, viewport);
    }
    tabs.replaceChildren();
    Object.keys(modeLabels).forEach(function (next) {
      var tab = document.createElement('button');
      tab.type = 'button';
      tab.textContent = label(next);
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', next === normalize(mode) ? 'true' : 'false');
      tab.classList.toggle('active', next === normalize(mode));
      tab.disabled = !options.onChange;
      tab.onclick = function () {
        if (next === normalize(mode)) return;
        syncUrl(next);
        options.onChange(next);
      };
      tabs.appendChild(tab);
    });
    return tabs;
  }

  window.DrawingMode = { normalize: normalize, label: label, choose: choose, applyBadge: applyBadge, syncUrl: syncUrl };
  window.escolherModoDesenho = choose;
  window.aplicarTagModoDesenho = applyBadge;
  window.atualizarModoDesenhoUrl = syncUrl;
})();
