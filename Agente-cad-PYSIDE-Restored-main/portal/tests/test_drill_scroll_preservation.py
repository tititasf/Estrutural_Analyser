"""A atualização do drill preserva rolagem sem misturar listas distintas."""
import shutil
import subprocess
from pathlib import Path
import pytest


def test_scroll_survives_status_and_item_changes_and_restores_class():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node indisponível')
    source = (Path(__file__).resolve().parents[1] / 'app/static/drill_grade.js').read_text(encoding='utf-8')
    render = source[source.index('  var drillScrollPositions ='):source.index('\n  function handle(')]
    script = r'''
const assert = require('node:assert/strict');
var scroll = null;
var root = {
  querySelector: () => scroll,
  querySelectorAll: () => [],
  set innerHTML(value) { scroll = {scrollTop: 0}; }
};
var state = {level:'itens', pav:'13_PAV', etapaTab:'estrutura', etapa:'sa', classe:'pilares'};
var recoverQaRunsFromJobs = () => {};
var ensureVigasConfig = () => {};
var backLabel = () => '';
var renderItens = () => 'itens';
var renderTabs = () => '';
var crumbHtml = () => 'Obra';
var esc = value => value;
var syncNavigationUrl = () => {};
'''+render+r'''
render();
scroll.scrollTop = 240;
render();
assert.equal(scroll.scrollTop, 240, 'atualização de status');
state.itemId = 'P35';
render();
assert.equal(scroll.scrollTop, 240, 'troca de item na mesma lista');
state.classe = 'lajes';
render();
assert.equal(scroll.scrollTop, 0, 'nova lista começa no topo');
scroll.scrollTop = 80;
state.classe = 'pilares';
render();
assert.equal(scroll.scrollTop, 240, 'retorno aos pilares');
state.classe = 'lajes';
render();
assert.equal(scroll.scrollTop, 80, 'retorno às lajes');
'''
    result = subprocess.run([node, '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
