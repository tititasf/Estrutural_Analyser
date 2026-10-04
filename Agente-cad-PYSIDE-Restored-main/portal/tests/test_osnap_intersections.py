"""Real OSNAP JS functions, synthetic geometry for dense/long crossings."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_local_crossings_survive_dense_index_and_win_over_line_projection():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    text = (Path(__file__).resolve().parents[1] / 'app/templates/obra_detalhe.html').read_text(encoding='utf-8')
    geometry = text[text.index('  function segIntersect('):text.index('  function coletarSnapCandidates(')]
    nearest = text[text.index('  function nearestSnapClient('):text.index('  // compat: antigo nearestSnap')]
    script = "const assert=require('node:assert/strict');const window={};function snapThrUser(){return 24;}\n" + geometry + nearest + """
window._snapCell=10;window._snapGrid={};window._snapSegCell=10;
window._snapSegs=[];
// >80 irrelevant segments precede the actual crossing in the same bucket.
for(let i=0;i<120;i++)window._snapSegs.push([0,200+i,2000,200+i]);
window._snapSegs.push([0,100,2000,100],[1000,0,1000,1000]);
window._snapSegGrid={'100,10':window._snapSegs.map((_,i)=>i)};
assert.deepEqual(nearestSnapClient({},0,0,{x:1002,y:103}),
 {x:1000,y:100,dist:Math.sqrt(13),px:false});
// T-junction at a diagonal endpoint.
window._snapSegs=[[0,100,2000,100],[1000,100,1100,200]];
window._snapSegGrid={'100,10':[0,1]};
assert.equal(nearestSnapClient({},0,0,{x:1002,y:103}).y,100);
// No vertex/crossing nearby: line extension must NOT attract.
window._snapSegs=[[0,100,2000,100]];window._snapSegGrid={'100,10':[0]};
assert.equal(nearestSnapClient({},0,0,{x:1002,y:103}),null);
// A real endpoint remains selectable.
window._snapPts=[[1000,100]];window._snapGrid={'100,10':[[1000,100]]};
assert.equal(nearestSnapClient({},0,0,{x:1002,y:103}).x,1000);
"""
    result = subprocess.run([node, '-e', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'segs.length < MAX_SEGS' not in text
    assert 'maxX = minX + 8' not in text
