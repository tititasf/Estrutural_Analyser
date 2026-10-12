const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const context={window:{},module:{exports:{}}};vm.createContext(context);
vm.runInContext(fs.readFileSync('portal/app/static/viewer_regional.js','utf8'),context);
const {compactLines}=context.module.exports;
const path=(d,extra='',color='#abcdef')=>`<path d="${d}" clip-path="url(#clip)" style="fill: none; stroke: ${color}; stroke-dasharray: 2,3; stroke-dashoffset: 1" ${extra}/>`;
const source=Array.from({length:300},(_,i)=>path(`M ${i} ${i+1} L ${i+2} ${i+3}`)).join('\n');
const result=compactLines(source);
assert.equal((result.match(/<path/g)||[]).length,3,'bounded batches reduce 300 nodes to 3');
const segments=s=>Array.from(s.matchAll(/M\s+[-+\d.eE]+\s+[-+\d.eE]+\s+L\s+[-+\d.eE]+\s+[-+\d.eE]+/g),m=>m[0]);
assert.deepEqual(segments(result),segments(source),'every coordinate, duplicate and order retained');
assert.equal((result.match(/stroke-dashoffset: 1/g)||[]).length,3);
for(const extra of ['id="referenced"','opacity="0.5"','transform="translate(1)"','class="custom"']){
 const special=path('M 0 1 L 2 3',extra);assert.ok(compactLines(source+special+source).includes(special));
}
const curve=path('M 0 1 C 2 3 4 5 6 7');assert.ok(compactLines(source+curve+source).includes(curve));
const filled=path('M 0 1 L 2 3').replace('fill: none','fill: #ff0000');assert.ok(compactLines(filled).includes(filled));
const marker='<g data-cad-chunk="25"></g>';
assert.ok(compactLines(path('M 1 2 L 3 4')+marker+path('M 5 6 L 7 8')).includes(marker));
assert.equal((compactLines(path('M 1 2 L 3 4')+path('M 5 6 L 7 8','','#ff0000')).match(/<path/g)||[]).length,2,'paint order and distinct colors remain separate');
console.log('PASS: line batching, all geometry/order/dash origins, unsupported effects, fills, IDs and chunk markers');
