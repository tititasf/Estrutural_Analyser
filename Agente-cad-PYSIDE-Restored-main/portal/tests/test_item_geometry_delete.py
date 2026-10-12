"""Execute the deletion confirmation controller, not just source-string checks."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_delete_confirmation_cancel_error_retry_and_scope():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    source = (Path(__file__).resolve().parents[1] / "app/static/item_geometry.js").read_text(encoding="utf-8")
    controller = source[source.index("  var deletionDialog ="):source.index("  function open(")]
    script = """
const assert=require('node:assert/strict');
class Element {
  constructor(tag){this.tag=tag;this.dataset={};this.style={};this.listeners={};this.children=[];this.isConnected=true;}
  setAttribute(k,v){this[k]=v;}
  addEventListener(k,fn){this.listeners[k]=fn;}
  append(...els){this.children.push(...els);}
  focus(){document.activeElement=this;}
  remove(){this.removed=true;this.isConnected=false;}
  click(){if(!this.disabled)this.listeners.click();}
}
const document={body:new Element('body'),activeElement:new Element('button'),
  createElement:t=>new Element(t), listeners:{},
  addEventListener(k,fn){this.listeners[k]=fn;},removeEventListener(k){delete this.listeners[k];}};
let requests=[],navigation=[],rejectRequest=true;
function remove(t,whole,comment){requests.push({t,whole,comment});return rejectRequest?Promise.reject(new Error('HTTP 403')):Promise.resolve({});}
function reload(t,deleted){navigation.push({t,deleted});}
""" + controller + """
(async()=>{
 const target={classe:'lajes',itemId:'LUX2',pavimento:'13_PAV'};
 const prior=document.activeElement;
 deleteItem(target,false);
 refreshDeleted=async(t,whole)=>{navigation.push({t,whole});};
 const first=deletionDialog,box=first.children[0];
 assert.equal(box.role,'dialog');assert.equal(box['aria-modal'],'true');
 assert.equal(box.children[0].textContent,'Excluir o item LUX2?');
 deleteItem(target,false);assert.equal(deletionDialog,first);
 box.children[2].click();assert.equal(deletionDialog,null);assert.equal(requests.length,0);
 assert.equal(document.activeElement,prior);
 deleteItem(target,false);
 document.listeners.keydown({key:'Escape',preventDefault(){}});
 assert.equal(deletionDialog,null);assert.equal(requests.length,0);
 deleteItem(target,false);
 const live=deletionDialog.children[0],cancel=live.children[2],accept=live.children[3];
 target.itemId='OTHER'; // Capture the confirmed identity, never a later selection.
 accept.click();accept.click();assert.equal(requests.length,1);
 assert.equal(requests[0].t.itemId,'LUX2');assert.equal(requests[0].whole,false);
 assert.equal(cancel.disabled,true);assert.match(live.children[1].textContent,/Excluindo/);
 document.listeners.keydown({key:'Escape',preventDefault(){}});assert.ok(deletionDialog);
 await new Promise(setImmediate);
 assert.match(live.children[1].textContent,/HTTP 403/);assert.equal(accept.disabled,false);
 assert.equal(navigation.length,0);
 rejectRequest=false;accept.click();await new Promise(setImmediate);
 assert.equal(navigation.length,1);assert.equal(deletionDialog,null);
 assert.equal(navigation[0].t.itemId,'LUX2');
 // A visual refresh failure must never repeat an already persisted DELETE.
 refreshDeleted=async()=>{throw new Error('viewer offline');};
 deleteItem({classe:'fundo',itemId:'segment7',beam:'V306',segmento:7},false);
 const retryBox=deletionDialog.children[0],retry=retryBox.children[3];
 retry.click();await new Promise(setImmediate);
 assert.match(retryBox.children[1].textContent,/Já excluído no servidor/);
 assert.equal(retry.textContent,'Atualizar tela');
 const requestCount=requests.length;
 refreshDeleted=async()=>{};retry.click();await new Promise(setImmediate);
 assert.equal(requests.length,requestCount);assert.equal(deletionDialog,null);
 // Interpreted cuts retain the optional human explanation with the captured target.
 deleteItem({classe:'cortes_interpretados',itemId:'interpreted:V307',structural:true},false);
 const interpreted=deletionDialog.children[0],label=interpreted.children[1];
 assert.equal(label.textContent,'Comentário (opcional)');
 const comment=label.children[0];
 comment.value='A laje está em outro nível';
 interpreted.children[4].click();await new Promise(setImmediate);
 assert.equal(requests.at(-1).comment,'A laje está em outro nível');
 assert.equal(requests.at(-1).t.itemId,'interpreted:V307');
 assert.equal(deletionDialog,null);
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
