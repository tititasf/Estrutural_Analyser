from pathlib import Path
import shutil
import subprocess
import pytest


def test_decimal_presentation_preserves_identities_and_unedited_values():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node indisponível')
    source = (Path(__file__).resolve().parents[1]/'app/static/decimal_display.js').read_text(encoding='utf-8')
    script = "const assert=require('node:assert/strict');let window={},document={readyState:'loading',addEventListener:()=>{}};\n"+source+r'''
const fmt=window.PortalNumbers;
assert.equal(fmt.number(147.98),'148');
assert.equal(fmt.number('147,88'),'147,9');
assert.equal(fmt.number(0.000553),'0');
assert.equal(fmt.number(-0.001),'0');
assert.equal(fmt.text('[1178.8825, 3141.038] cm; 852.19cm'), '[1178,9, 3141] cm; 852,2cm');
assert.equal(fmt.text('8.912x30.958 pt; versão 1.2.3'), '8,9x31 pt; versão 1.2.3');
assert.equal(fmt.text('Erro 0.041835 cm; nível 852.19m; 147,88 cm; confiança 98.55%'),
 'Erro 0 cm; nível 852,19m; 147,9 cm; confiança 98,6%');
assert.equal(fmt.level(852),'852,00');
assert.equal(fmt.level('852,195'),'852,20');
assert.equal(fmt.level(-0.001),'0,00');
assert.equal(fmt.level(null),'—');
assert.equal(fmt.text('níveis (852.19 m)'), 'níveis (852,19 m)');
assert.equal(fmt.text('Nível da viga: +852.195 m; Nível do trecho: 852.1'), 'Nível da viga: 852,20 m; Nível do trecho: 852,10');
assert.equal(fmt.text('Nível 18.717 cm; Nível 18.717mm'), 'Nível 18,7 cm; Nível 18,7mm');
assert.equal(fmt.text(fmt.text('nível 852.10m; medida 18.717cm')), 'nível 852,10m; medida 18,7cm');
assert.equal(fmt.text('L301 P1 S2 13_PAV 2026-10-03 https://example.org/147.98 file147.98.json'),
 'L301 P1 S2 13_PAV 2026-10-03 https://example.org/147.98 file147.98.json');
assert.equal(fmt.inputValue({dataset:{exactNumber:'852.19',displayNumber:'852.2'},value:'852.2'}),'852.19');
assert.equal(fmt.inputValue({dataset:{exactNumber:'852.19',displayNumber:'852.2'},value:'853.1'}),'853.1');
assert.equal(fmt.inputValue({dataset:{exactNumber:'852.19cm',displayNumber:'852,2cm'},value:'852,2cm'}),'852.19cm');
assert.equal(fmt.inputValue({dataset:{exactNumber:'852.19cm',displayNumber:'852,2cm'},value:'853,1m'}),'853.1m');
let input={dataset:{},type:'number',step:'0.1',value:'18.717',closest:()=>true,getAttribute:()=>null};
fmt.prepareInput(input);
assert.equal(input.value,'18,7');
assert.equal(input.type,'text');
assert.equal(fmt.inputValue(input),'18.717');
input.value='19,88';
fmt.prepareInput(input);
assert.equal(input.value,'19,9');
assert.equal(fmt.inputValue(input),'19.88');
fmt.prepareInput(input);
assert.equal(fmt.inputValue(input),'19.88');
let count={dataset:{},type:'number',step:'1',value:'3',closest:()=>true,getAttribute:()=>null};
let levelInput={dataset:{levelNumber:'m'},inputMode:'decimal',type:'text',value:'852.195',closest:()=>true,getAttribute:()=>null};
fmt.prepareInput(levelInput);assert.equal(levelInput.value,'852,20');assert.equal(fmt.inputValue(levelInput),'852.195');
fmt.prepareInput(levelInput);assert.equal(levelInput.value,'852,20');assert.equal(fmt.inputValue(levelInput),'852.195');
fmt.prepareInput(count);assert.equal(count.type,'number');assert.equal(count.value,'3');
'''
    result = subprocess.run([node,'-e',script],capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stderr
