const fs = require('fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('portal/app/static/drill_grade.js', 'utf8');
const start = source.indexOf('  function latestClassGeneration(');
const end = source.indexOf('  function classGenerationTime(', start);
const latest = new Function(source.slice(start, end) + '; return latestClassGeneration;')();
const job = (id, extra={}, status='concluido', time='2026-10-05T01:49:20Z') =>
  ({id,status,finalizado_em:time,meta:{pav:'13_PAV',etapa:'sa',classe_ui:'laterais_para',...extra}});
const jobs = [job('valid'),job('failed',{},'erro','2026-10-05T02:00:00Z'),
  job('otherfloor',{pav:'14_PAV'}),job('single',{item:'V301'}),
  job('otherclass',{classe_ui:'fundo'}),job('missingfloor',{pav:null}),
  job('invalidtime',{},'concluido','bad')];
assert.equal(latest(jobs,'13_PAV','laterais_para','laterais_viga','LV','sa').id,'valid');
assert.equal(latest(jobs,'13_PAV','laterais_para','laterais_viga','LV','n3'),null);
assert.equal(latest([job('new',{},'concluido','2026-10-05T02:00:00Z'),...jobs],
  '13_PAV','laterais_para','laterais_viga','LV','sa').id,'new');
assert.equal(latest([job('scoped',{classe_ui:null,secao:['fundos_viga']})],
  '13_PAV','laterais_para','laterais_viga','LV','sa'),null);
console.log('Timestamp scope, completion, ordering and single-item exclusions passed');
