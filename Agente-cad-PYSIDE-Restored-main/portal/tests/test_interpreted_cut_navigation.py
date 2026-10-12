"""The preprocessing list opens the structural reviewer for the selected cut."""
import shutil
import subprocess
from pathlib import Path
import pytest


def test_interpreted_inventory_navigation_and_review_labels():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'app/static/drill_grade.js').read_text(encoding='utf-8')
    parts = []
    for start, end in [('  function renderCortesPreprocessamento()', '  function renderUnifiedProcBox()'),
                       ('  function openItem(itemId)', '  function loadItens(done)'),
                       ('  function loadItens(done)', '  /**\n   * Abre Interpretação')]:
        parts.append(source[source.index(start):source.index(end, source.index(start))])
    script = """
const assert=require('node:assert/strict');
var state={classe:'cortes_interpretados',pav:'13_PAV',itens:[]},OBRA_ID='work1';
var lateralCombinada=()=>false,esc=s=>String(s),pavimentoTitulo=s=>s;
let requested,opened;
var window={ItemGeometry:{open:t=>{opened=t;}}};
var fetch=url=>{requested=url;return Promise.resolve({json:()=>Promise.resolve({itens:[
 {item_id:'interpreted:V330:71',titulo:'V330 · 71 cm',review_status:'validated'},
 {item_id:'interpreted:slab-step:L322',titulo:'L322 · Degrau de laje'}]})});};
""" + '\n'.join(parts) + """
(async()=>{
 await new Promise(resolve=>loadItens(resolve));
 assert.equal(requested,'/obras/work1/cortes-interpretados?pavimento=13_PAV');
 const html=renderCortesPreprocessamento();
 assert.match(html,/Visão de Cortes Interpretados/);
 assert.match(html,/V330 · 71 cm ✓/);
 assert.match(html,/L322 · Degrau de laje · revisar/);
 openItem('interpreted:slab-step:L322');
 assert.deepEqual(opened,{classe:'cortes_interpretados',itemId:'interpreted:slab-step:L322',pavimento:'13_PAV',structural:true});
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    result = subprocess.run([node, '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
