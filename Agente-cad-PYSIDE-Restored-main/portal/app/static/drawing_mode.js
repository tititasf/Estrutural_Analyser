(function () {
  'use strict';

  function normalize(value) {
    return String(value || 'NOVA').trim().toUpperCase() === 'INI' ? 'INI' : 'NOVA';
  }

  function label(value) { return normalize(value) === 'INI' ? 'Ini' : 'Nova'; }

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
          '<div class="drawing-mode-options">' +
            '<button value="NOVA" class="' + (current === 'NOVA' ? 'selected' : '') + '">' +
              '<strong>Nova</strong><span>Design atual, com a qualidade usada hoje.</span></button>' +
            '<button value="INI" class="' + (current === 'INI' ? 'selected' : '') + '">' +
              '<strong>Ini</strong><span>Perfil visual legado dos templates iniciais.</span></button>' +
          '</div><button value="cancel" class="drawing-mode-cancel">Cancelar</button>' +
        '</form>';
      document.body.appendChild(dialog);
      var settled = false;
      function finish(value) {
        if (settled) return;
        settled = true;
        dialog.remove();
        resolve(value === 'NOVA' || value === 'INI' ? value : null);
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
    var badge = viewport.querySelector(':scope > .drawing-mode-badge');
    if (!badge) {
      badge = document.createElement(options.onChange ? 'button' : 'span');
      if (options.onChange) badge.type = 'button';
      badge.className = 'drawing-mode-badge';
      viewport.appendChild(badge);
    }
    badge.textContent = 'Modo de desenho: ' + label(mode) + (options.onChange ? ' · alterar' : '');
    badge.dataset.mode = normalize(mode);
    if (options.onChange) {
      badge.title = 'Alternar entre os desenhos Ini e Nova já gerados';
      badge.onclick = function (event) {
        event.preventDefault(); event.stopPropagation();
        var next = normalize(mode) === 'INI' ? 'NOVA' : 'INI';
        syncUrl(next);
        options.onChange(next);
      };
    }
    return badge;
  }

  window.DrawingMode = { normalize: normalize, label: label, choose: choose, applyBadge: applyBadge, syncUrl: syncUrl };
  window.escolherModoDesenho = choose;
  window.aplicarTagModoDesenho = applyBadge;
  window.atualizarModoDesenhoUrl = syncUrl;
})();
