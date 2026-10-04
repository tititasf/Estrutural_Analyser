"""Several active QA rounds must not trigger each other through sidebar render."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_dismiss_notification_preserves_result_and_reopens_for_new_event():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node indisponível')
    source = (Path(__file__).resolve().parents[1]/'app/static/drill_grade.js').read_text(encoding='utf-8')
    helpers = source[source.index('  function qaNotificationFingerprint('):source.index('  function controlQaJob(')]
    script = r'''
const assert = require('node:assert/strict');
let qaDismissed = {}, stored, renders = 0, QA_DISMISSED_KEY = 'test';
let run = {roundId:'one',jobId:'job',pavimento:'13',qaClass:'FV',layer:'L1',status:'failed',done:0,total:1,failed:1};
let qaRunKey = (p,c,l) => [p,c,l].join('|');
let qaRunFor = () => run;
let qaIsActive = r => ['queued','running'].includes(r.status);
let render = () => renders++;
let window = {localStorage:{setItem:(key,value)=>stored=value}};
''' + helpers + r'''
assert.equal(qaNotificationDismissed(run),false);
let original = JSON.stringify(run);
dismissQaNotification('L1');
assert.equal(JSON.stringify(run),original,'QA badge/history must stay unchanged');
assert.equal(qaNotificationDismissed(run),true);
qaDismissed = JSON.parse(stored);
assert.equal(qaNotificationDismissed({...run,updatedAt:'new poll'}),true);
for (let patch of [{roundId:'two'},{status:'completed'},{done:1},{qaClass:'LV'},{pavimento:'14'}]) {
  assert.equal(qaNotificationDismissed({...run,...patch}),false);
}
run = {...run,status:'running'};
dismissQaNotification('L1');
assert.equal(renders,1,'running and paused controls must stay visible');
run.status = 'paused'; dismissQaNotification('L1');
assert.equal(renders,1);
'''
    result = subprocess.run([node,'-e',script],capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stderr


def test_render_does_not_amplify_round_polling():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node indisponível')
    source = (Path(__file__).resolve().parents[1]/'app/static/drill_grade.js').read_text(encoding='utf-8')
    polling = source[source.index('  function pollQaRound('):source.index('  function recoverQaRunsFromJobs(')]
    script = r'''
const assert = require('node:assert/strict');
let qaRoundLoading = {}, qaPollTimers = {}, calls = [], timers = new Map(), serial = 0;
let state = {qaRuns:{},level:'pavs'};
let saveQaRuns = () => {};
let qaRunKey = (p,c,l) => c;
let qaProgressFromDetail = d => d;
let qaIsActive = r => r.status === 'running';
let qaClassId = x => x;
let setTimeout = (fn,ms) => {timers.set(++serial,{fn,ms}); return serial;};
let clearTimeout = id => timers.delete(id);
let active = ['a','b','c','d'];
let render = () => active.forEach(id => pollQaRound(id));
let fetch = url => {
  calls.push(url);
  return Promise.resolve({ok:true,json:() => Promise.resolve({status:'running',qaClass:url})});
};
''' + polling + r'''
(async () => {
  render();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length,4,'one initial request per active round');
  for(let i=0;i<25;i++) render();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length,4,'render cannot bypass polling intervals');
  assert.equal(timers.size,4);
  let [id,timer] = [...timers][0];
  timers.delete(id); timer.fn();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length,5,'one elapsed timer refreshes only its own round');
  assert.equal(timers.size,4);
  fetch = () => Promise.reject(new Error('offline'));
  [id,timer] = [...timers][0]; timers.delete(id); timer.fn();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(timers.size,4,'network failure retains exactly one retry');
  assert.ok([...timers.values()].some(t => t.ms===5000));
})().catch(e => {console.error(e);process.exitCode=1;});
'''
    result = subprocess.run([node,'-e',script],capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stderr
