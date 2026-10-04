from pathlib import Path
import subprocess,shutil
import pytest


def test_clipboard_image_attaches_to_its_point_and_plain_text_is_unchanged():
    node=shutil.which('node')
    if not node:pytest.skip('Node indisponível')
    source=(Path(__file__).resolve().parents[1]/'app/static/ui_feedback.js').read_text(encoding='utf-8')
    handler=source.split("field.addEventListener('paste',function(event){",1)[1].split('\n    });});',1)[0]
    script='''const assert=require('node:assert/strict');
var field={dataset:{uiFeedbackPointText:'2'}};
var calls=[];var prevented=false;
var image={name:'print.png'};
var addFilesToPoint=(files,index)=>calls.push({files,index});
var paste=function(event){'''+handler+'''};
paste({clipboardData:{items:[{kind:'file',type:'image/png',getAsFile:()=>image}]},preventDefault:()=>prevented=true});
assert.equal(prevented,true);assert.equal(calls[0].index,2);assert.equal(calls[0].files[0],image);
prevented=false;
paste({clipboardData:{items:[{kind:'string',type:'text/plain'}]},preventDefault:()=>prevented=true});
assert.equal(prevented,false);assert.equal(calls.length,1);
'''
    result=subprocess.run([node,'-e',script],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
