const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const context={window:{},module:{exports:{}},setTimeout,clearTimeout,performance,
 requestAnimationFrame:f=>setTimeout(f,0),console};
vm.createContext(context);vm.runInContext(fs.readFileSync('portal/app/static/viewer_regional.js','utf8'),context);
const {Controller}=context.module.exports;
const pause=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
 const manifest={home:[0,0,100,100],shell_paths:0,units:[
   {id:0,bounds:[0,0,20,20],paths:1},{id:1,bounds:[70,70,100,100],paths:1}]};
 const c=new Controller('/raw/foto',manifest,{aborted:false});
 c.responsive=true;c.viewport={dataset:{regionalReadyMs:'1'},getBoundingClientRect:()=>({width:100,height:100})};
 c.svg={isConnected:true};c.slots=[{innerHTML:'old',replaceChildren(){this.innerHTML='';}},{innerHTML:'',replaceChildren(){this.innerHTML='';}}];
 c.active.add(0);let release,fetches=0,commits=0;
 c.chunks=async ids=>{fetches++;await new Promise(r=>release=r);ids.forEach(id=>c.cache.set(id,'complete-'+id));};
 c.camera([75,75,10,10],()=>commits++);
 assert.equal(commits,1,'camera must move before network starts');assert.equal(fetches,0);
 await pause(120);assert.equal(fetches,1);assert.equal(c.slots[0].innerHTML,'old','retain geometry while fetching');
 c.camera([80,80,10,10],()=>commits++);assert.equal(commits,2,'in-flight HTTP must not block newer camera');
 release();await pause(130);await pause(10);
 // Cached chunks are reused for the latest target by our stub without another wait.
 if(release)release();await pause(20);
 assert.equal(commits,2,'old request must not roll camera back');
 assert.equal(c.slots[1].innerHTML,'complete-1');assert.equal(c.viewport.dataset.regionalLoading,'0');
 c.dispose();const prior=commits;c.camera([0,0,10,10],()=>commits++);await pause(110);assert.equal(commits,prior);
 const initial=new Controller('/raw/foto',manifest,{aborted:false});initial.viewport={dataset:{},getBoundingClientRect:()=>({width:100,height:100})};
 initial.svg={isConnected:true};initial.slots=c.slots;let ready=false;
 initial.chunks=async ids=>{await pause(10);ids.forEach(id=>initial.cache.set(id,'full-'+id));};
 initial.camera([0,0,10,10],()=>ready=true);assert.equal(ready,false,'initial delivery still requires complete geometry');
 await pause(40);assert.equal(ready,true);initial.dispose();
 console.log('PASS: immediate navigation, in-flight coalescing, no stale camera, complete initial delivery, disposal');
})().catch(e=>{console.error(e);process.exitCode=1;});
