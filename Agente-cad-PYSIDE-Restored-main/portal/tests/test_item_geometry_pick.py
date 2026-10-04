"""Unit execution of the delegated pick controller; browser proof is separate."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_highlight_pick_identity_drawing_drag_and_class():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node unavailable')
    source = (Path(__file__).resolve().parents[1] / 'app/static/item_geometry.js').read_text(encoding='utf-8')
    block = source[source.index('    var pickingClass=false;'):source.index("    items.addEventListener('change',chooseItem);")]
    script = """
const assert=require('node:assert/strict');
const listeners={};
let loads=0, selection=null, target=null, loading=false, choices=0;
const row={item_id:'unique-seg-2',beam_name:'V9',segmento:2};
let rows=[row];
const cls={value:'fundo',addEventListener(){},dispatchEvent(){}};
const items={value:''},segs={value:''},name={value:'',dispatchEvent(){}},status={};
const chk={checked:false},saveButton={disabled:false};
const document={getElementById(){return {open:false};}};
function beamClass(c){return c==='fundo'||c.startsWith('lateral_');}
function beamName(r){return r.beam_name;}
function chooseItem(){choices++;selection={beam:beamClass(cls.value)?row.beam_name:null,segmento:row.segmento};name.value=row.beam_name||row.item_id;}
function chooseSegment(){}
function loadItems(){loads++;return Promise.resolve();}
const poly={_geometryItem:{classe_sa:'fundo',item_id:row.item_id},isPointInFill(){return true;},isPointInStroke(){return false;}};
const overlay={getScreenCTM(){return {inverse(){return {};}}},createSVGPoint(){return {matrixTransform(){return {};}}},querySelectorAll(){return [poly];}};
const vp={contains(){return true;},querySelector(){return overlay;}};
const container={isConnected:true,addEventListener(k,fn){listeners[k]=fn;},querySelector(){return vp;}};
function down(){listeners.pointerdown({clientX:10,clientY:10,pointerId:1});}
function click(){listeners.click({clientX:10,clientY:10,target:{},preventDefault(){},stopPropagation(){}});}
""" + block + """
(async()=>{
 down();click();await Promise.resolve();
 assert.equal(items.value,'V9');assert.equal(segs.value,'unique-seg-2');assert.match(status.textContent,/S2/);
 const before=choices;
 chk.checked=true;down();click();await Promise.resolve();assert.equal(choices,before);
 chk.checked=false;down();listeners.pointermove({clientX:30,clientY:10,pointerId:1});click();
 await Promise.resolve();assert.equal(choices,before); // even if drag returns to origin
 row.item_id='L1';row.beam_name=null;poly._geometryItem={classe_sa:'lajes',item_id:'L1'};
 down();click();await Promise.resolve();assert.equal(cls.value,'lajes');assert.equal(items.value,'L1');assert.equal(loads,1);
 saveButton.disabled=true;down();click();await Promise.resolve();assert.equal(loads,1);
 console.log('pick identity, class, drawing, drag and busy guards passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    result = subprocess.run([node, '-e', script], text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
