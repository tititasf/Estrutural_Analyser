"""Restore the selected viewer after the asynchronous recorte catalog arrives."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_recorte_link_waits_for_catalog_and_respects_later_navigation():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'app/static/drill_grade.js').read_text(encoding='utf-8')
    start = source.index('  function onDataReady()')
    body = source[start:source.index('  window.DrillGrade =', start)]
    script = r"""
const assert = require('node:assert/strict');
var window = {}, state, catalog, opened;
var _urlRestoreStarted, _urlRestoreDone, _urlPavBootDone, _pendingDocRestore, _urlIntent;
var ensureDocsDetalhe=()=>{},setObraModo=()=>{},render=()=>{},syncNavigationUrl=()=>{};
var activeTab=()=> 'recortes', recortesDoPav=()=>catalog;
var pickDefaultDoc=()=>catalog[0],openDoc=doc=>opened.push(doc.id);
function reset(id='rec:EST:torre_1') {
 state={};catalog=[];opened=[];
 _urlRestoreStarted=false;_urlRestoreDone=false;_urlPavBootDone=false;_pendingDocRestore=null;
 _urlIntent={pav:'TIPO_TESTE',doc:id};
}
""" + body + r"""
reset();onDataReady();assert.deepEqual(opened,[]);
catalog=[{id:'rec:EST:torre_1'}];onDataReady();onDataReady();
assert.deepEqual(opened,['rec:EST:torre_1']);
reset('bruto:EST');onDataReady();catalog=[{id:'bruto:EST'}];onDataReady();
assert.deepEqual(opened,['bruto:EST']);
reset();catalog=[{id:'rec:EST:torre_1'}];onDataReady();onDataReady();
assert.deepEqual(opened,['rec:EST:torre_1']);
reset();onDataReady();state.selDoc='rec:EST:detalhes';
catalog=[{id:'rec:EST:torre_1'},{id:'rec:EST:detalhes'}];onDataReady();
assert.deepEqual(opened,[]);assert.equal(_pendingDocRestore,null);
reset();onDataReady();state.pav='OUTRO';catalog=[{id:'rec:EST:torre_1'}];onDataReady();
assert.deepEqual(opened,[]);assert.equal(_pendingDocRestore,null);
"""
    result = subprocess.run([node, '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
