(function () {
  'use strict';
  var formatter = new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: 0, maximumFractionDigits: 1, useGrouping: false
  });
  var levelFormatter = new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: false
  });
  function level(value) {
    if (value === null || value === undefined || value === '') return '—';
    var parsed = Number(String(value).replace(',', '.'));
    return Number.isFinite(parsed) ? levelFormatter.format(parsed).replace(/^-0,00$/, '0,00') : String(value);
  }
  function levelHtml(value) {
    return '<span data-level-number>' + level(value).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</span>';
  }
  function number(value) {
    var parsed = Number(String(value).replace(',', '.'));
    return Number.isFinite(parsed) ? formatter.format(parsed === 0 ? 0 : parsed).replace(/^-0$/, '0') : String(value);
  }
  function text(value) {
    // Only displayed decimal quantities. Do not rewrite item IDs, dates, URLs or paths.
    return String(value == null ? '' : value).split(/(https?:\/\/[^\s]+|[A-Za-z]:[\\/][^\s]+|\b[\w.-]+\.(?:dxf|dwg|json|svg|png|jpg|pdf)\b)/gi).map(function(part, index) {
      if (index % 2) return part;
      var levels = [];
      part = part.replace(/((?:n[ií]ve(?:l|is)(?:\s+(?:de\s+)?(?:chegada|sa[ií]da|do elemento|da laje|da viga|do trecho|superior|inferior))?|element_level|pillar_top_level|nivel_chegada|nivel_saida|laje_nivel)\s*["']?\s*[:=]?\s*\(?\s*)([+-]?\d+(?:[.,]\d+)?)(?![\d.,]|\s*(?:cm|mm)\b)/gi, function(_, prefix, raw) {
        levels.push(prefix + level(raw)); return '\uE000' + (levels.length - 1) + '\uE001';
      });
      return part.replace(/(?:(?<![\w.,-])|(?<=\dx))-?\d+[.,]\d+(?:e[+-]?\d+)?(?![\d.]|,\d)(?=$|[^A-Za-z_]|(?:cm|mm|m2|m|pt|px)\b|x\d)/gi, function(raw) { return number(raw); }).replace(/\uE000(\d+)\uE001/g, function(_, index) { return levels[Number(index)]; });
    }).join('');
  }
  function inputValue(input) {
    return input.dataset.exactNumber !== undefined && input.value === input.dataset.displayNumber
      ? input.dataset.exactNumber : input.value.replace(',', '.');
  }
  function prepareInput(input) {
    if (!input || input.dataset.exactDisplay !== undefined) return;
    // Convert only audited measurement editors, not arbitrary numeric site controls.
    if (!input.closest('#fv-ficha-root,#lv-ficha-root,#laje-ficha-root,#pillar-n3-editor,#pillar-n3-editor-n3') &&
        input.dataset.exactNumber === undefined && input.dataset.measureNumber === undefined) return;
    var measure = input.dataset.measureNumber !== undefined || input.inputMode === 'decimal' ||
      (input.type === 'number' && Number(input.step) > 0 && Number(input.step) < 1);
    if (!measure) return;
    var raw = input.getAttribute('data-exact-length') !== null && input.value === input.getAttribute('data-display-length')
      ? input.getAttribute('data-exact-length') : inputValue(input);
    if (raw !== '' && !Number.isFinite(Number(raw))) return;
    input.dataset.measureNumber = '1';
    input.type = 'text'; input.inputMode = 'decimal';
    input.dataset.exactNumber = raw;
    input.dataset.displayNumber = raw === '' ? '' : (input.dataset.levelNumber !== undefined ? level(raw) : number(raw));
    input.value = input.dataset.displayNumber;
  }
  window.PortalNumbers = {number:number, level:level, levelHtml:levelHtml, text:text, inputValue:inputValue, prepareInput:prepareInput};
  function render(node) {
    if (!node || !node.isConnected) return;
    if (node.nodeType === 3) {
      var parent = node.parentElement;
      if (!parent || parent.closest('script,style,textarea,input,[contenteditable="true"],[data-exact-display],[data-level-number]')) return;
      var formatted = text(node.nodeValue);
      if (formatted !== node.nodeValue) node.nodeValue = formatted;
      return;
    }
    if (node.nodeType !== 1 || node.matches('script,style,[contenteditable="true"],[data-exact-display]')) return;
    if (node.matches('input')) { prepareInput(node); return; }
    if (node.matches('textarea')) {
      if (node.readOnly) node.value = text(node.value);
      return;
    }
    Array.prototype.forEach.call(node.childNodes, render);
  }
  function start() {
    render(document.body);
    document.addEventListener('blur', function(event) {
      if (event.target.matches('input[data-measure-number]')) prepareInput(event.target);
    }, true);
    new MutationObserver(function(records) {
      // Update only changed subtrees; no page-wide polling or replacement of controls.
      records.forEach(function(record) {
        if (record.type === 'characterData') render(record.target);
        else Array.prototype.forEach.call(record.addedNodes, render);
      });
    }).observe(document.body, {subtree:true, childList:true, characterData:true});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
