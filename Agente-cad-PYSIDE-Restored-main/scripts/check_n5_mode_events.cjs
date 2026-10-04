// Unit test of the template's actual event handlers, without browser/network IO.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const template = fs.readFileSync('portal/app/templates/obra_detalhe.html', 'utf8');
const begin = template.indexOf("  (function () {\n    var root = document.getElementById('detalhe-n5-pavimento');");
const end = template.indexOf('  })();', begin) + 8;
assert(begin >= 0);
const code = template.slice(begin, end).replace(/\{\{ obra.id \}\}/g, 'obra-test')
  .replace(/\{\{ pavimento \}\}/g, '13_PAV').replace(/\{\{ n5_modo_ativo \}\}/g, 'NOVA');
async function scenario(n3, n5) {
  const handlers = {};
  const button = {dataset:{n5SelectMode:'INI'},addEventListener:(event, fn)=>handlers[event]=fn,
    closest:()=>panel};
  const panel = {dataset:{n5Panel:'PL'},querySelector:()=>({dataset:{pillarGroup:'PASSA'}})};
  const root = {querySelectorAll:selector=>selector==='[data-n5-select-mode]'?[button]:[]};
  const alerts = [];
  const context = {document:{getElementById:()=>root},URL,URLSearchParams,
    window:{location:{href:'https://example.test/obras/obra-test?classe=pilares',search:''},alert:message=>alerts.push(message)},
    fetch:async()=>({ok:true,json:async()=>({modes:{INI:{n3,n5}}})}),ativarZoomEmContainer:()=>{}};
  vm.runInNewContext(code, context);
  handlers.click();
  await new Promise(resolve=>setImmediate(resolve));
  if(!n3 || !n5) {
    assert.equal(alerts.length,1);
    assert(alerts[0].includes(!n3?'N3':'Unificado'));
    assert.equal(context.window.location.href,'https://example.test/obras/obra-test?classe=pilares');
  } else {
    const url = new URL(context.window.location.href);
    assert.equal(url.searchParams.get('modo_desenho'),'INI');
    assert.equal(url.searchParams.get('grupo_pilares'),'PASSA');
    assert.equal(alerts.length,0);
  }
}
function checkChooser(availableModes) {
  const buttons = ['NOVA','INI'].map(value=>({value,disabled:false,querySelector:()=>({textContent:''}),addEventListener:()=>{}}));
  const dialog = {setAttribute:()=>{},addEventListener:()=>{},remove:()=>{},showModal:()=>{},querySelectorAll:()=>buttons};
  const context = {window:{},document:{createElement:()=>dialog,body:{appendChild:()=>{}}}};
  vm.runInNewContext(fs.readFileSync('portal/app/static/drawing_mode.js','utf8'),context);
  context.window.escolherModoDesenho({availableModes});
  assert.deepEqual(buttons.map(button=>button.disabled),availableModes===null?[false,false]:['NOVA','INI'].map(mode=>!availableModes.includes(mode)));
}
(async()=>{await scenario(false,false);await scenario(true,false);await scenario(true,true);
checkChooser(null);checkChooser(['NOVA']);checkChooser([]);
console.log('6 N5 mode event and chooser scenarios passed');})().catch(error=>{console.error(error);process.exitCode=1;});
