/* Versioned lossless painting units; original SVG remains the fallback. */
(function() {
  'use strict';
  const VERSION='regional-ml-v1';
  // Verified LineCollection fragments contain independent opaque strokes.
  // Batch consecutive identical paints; each M retains its own dash origin.
  // Original packets, source DXF and Float64 snap segments remain untouched.
  function compactLines(text) {
    let output='',end=0,batch=[],key=null,attrs='';
    const flush=()=>{if(batch.length){output+='<path '+attrs+' d="'+batch.join(' ')+'"/>';batch=[];}};
    const number='[-+]?(?:\\d*\\.\\d+|\\d+\\.?\\d*)(?:[eE][-+]?\\d+)?';
    const linear=new RegExp('^\\s*M\\s*'+number+'\\s+'+number+'\\s*L\\s*'+number+'\\s+'+number+'\\s*$');
    for(const match of text.matchAll(/<path\b[^>]*?\/>/gs)) {
      const gap=text.slice(end,match.index),node=match[0];
      const pairs=Array.from(node.matchAll(/([\w:-]+)="([^"]*)"/g),m=>[m[1],m[2]]);
      const values=Object.fromEntries(pairs),style=values.style||'';
      const properties=style.split(';').map(p=>p.trim()).filter(Boolean).map(p=>p.split(':').map(v=>v.trim()));
      const paint=Object.fromEntries(properties);
      const safe=pairs.every(([name])=>['d','style','clip-path'].includes(name)) &&
        pairs.length===Object.keys(values).length && linear.test(values.d||'') && paint.fill==='none' &&
        /^#[0-9a-f]{6}$/i.test(paint.stroke||'') &&
        properties.every(([name,value])=>value!==undefined&&['fill','stroke','stroke-width','stroke-dasharray','stroke-dashoffset','stroke-linecap','stroke-linejoin'].includes(name));
      const current=safe?JSON.stringify(pairs.filter(([name])=>name!=='d').sort(([a],[b])=>a.localeCompare(b))):null;
      if(!safe||gap.trim()||current!==key||batch.length>=128){flush();output+=gap;key=current;attrs=pairs.filter(([name])=>name!=='d').map(([name,value])=>name+'="'+value+'"').join(' ');}
      if(safe)batch.push(values.d);else output+=node;
      end=match.index+node.length;
    }
    flush();return output+text.slice(end);
  }
  async function digest(buffer) {
    return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),x=>x.toString(16).padStart(2,'0')).join('');
  }
  function initialCamera(manifest,width,height,zoom=1) {
    const h=manifest.home, scores=new Float64Array(16);
    for(const unit of manifest.units) {
      const b=unit.bounds,x=(b[0]+b[2])/2,y=(b[1]+b[3])/2;
      const ix=Math.floor((x-h[0])/h[2]*4),iy=Math.floor((y-h[1])/h[3]*4);
      if(ix>=0&&ix<4&&iy>=0&&iy<4) scores[iy*4+ix]+=unit.paths;
    }
    let best=5,score=-Infinity;
    scores.forEach((value,i)=>{const center=1-.12*Math.hypot(i%4-1.5,Math.floor(i/4)-1.5),candidate=Math.log1p(value)*center;
      if(candidate>score){score=candidate;best=i;}});
    if(!(scores[best]>0)) return h.slice();
    const ratio=width>0&&height>0?width/height:h[2]/h[3];
    const w=Math.min(h[2]*.55,h[3]*.45*ratio)*zoom,hh=w/ratio;
    return [Math.max(h[0],Math.min(h[0]+h[2]-w,h[0]+(best%4+.5)*h[2]/4-w/2)),
      Math.max(h[1],Math.min(h[1]+h[3]-hh,h[1]+(Math.floor(best/4)+.5)*h[3]/4-hh/2)),w,hh];
  }
  function visibleUnits(manifest,camera,width,height,prefetch=.06) {
    let [x,y,w,h]=camera;
    const scale=Math.min(width/w,height/h);
    if(!(scale>0)) return manifest.units.map(u=>u.id);
    const vw=width/scale,vh=height/scale;
    x-=(vw-w)/2;y-=(vh-h)/2;w=vw;h=vh;
    // Include meet letterboxing, non-scaling stroke and a prefetch margin.
    const margin=Math.max(2/scale,Math.max(w,h)*prefetch);
    return manifest.units.filter(u=>u.bounds[0]<=x+w+margin&&u.bounds[2]>=x-margin&&
      u.bounds[1]<=y+h+margin&&u.bounds[3]>=y-margin).map(u=>u.id);
  }
  async function response(url,signal) {
    const r=await fetch(url,{signal,cache:'no-cache'});
    if(!r.ok) {const error=new Error('Viewer HTTP '+r.status);error.status=r.status;throw error;}
    return r;
  }
  class Controller {
    constructor(src,manifest,signal) {
      this.src=src;this.base=src.replace(/\/foto(?:\?.*)?$/,'/viewer-package/');
      this.manifest=manifest;this.signal=signal;this.cache=new Map();this.cacheBytes=0;
      this.started=performance.now();
      this.generation=0;this.active=new Set();this.disposed=false;this.workers=new Set();
    }
    url(asset) {return this.base+asset+'?revision='+encodeURIComponent(this.manifest.revision);}
    async chunks(ids) {
      const missing=ids.filter(id=>!this.cache.has(id)&&!this.active.has(id));
      const batches=[];for(let start=0;start<missing.length;start+=128)batches.push(missing.slice(start,start+128));
      let cursor=0;
      const fetchBatch=async()=>{while(cursor<batches.length){
        const indexes=batches[cursor++], data=await(await response(this.url('chunks')+'&ids='+indexes.join(','),this.signal)).json();
        if(data.revision!==this.manifest.revision||data.fragments.length!==indexes.length) throw new Error('Revisão inconsistente');
        const expected=new Set(indexes);
        const prepared=await Promise.all(data.fragments.map(async item=>{
          if(!expected.delete(item.id)) throw new Error('Fragmento inesperado');
          const unit=this.manifest.units[item.id];
          const bytes=new TextEncoder().encode(item.svg);
          if(bytes.length!==unit.bytes||await digest(bytes)!==unit.sha256) throw new Error('Fragmento corrompido');
          return {item,bytes};
        }));
        for(const {item} of prepared) if(!this.cache.has(item.id)){
          const display=compactLines(item.svg);
          this.cache.set(item.id,display);this.cacheBytes+=new TextEncoder().encode(display).length;
        }
        if(this.disposed) throw new Error('Viewer encerrado');
      }};
      await Promise.all([fetchBatch(),fetchBatch()]);
    }
    attach(svg,viewport,options={}) {
      this.svg=svg;this.viewport=viewport;
      this.responsive=Boolean(options.responsive);
      svg._cadRegional=this;
      this.slots=Array.from(svg.querySelectorAll('[data-cad-chunk]'));
      if(this.slots.length!==this.manifest.units.length) throw new Error('Shell incompleto');
      viewport.dataset.regional='1';viewport.dataset.totalPaths=this.manifest.path_count;
      const rect=viewport.getBoundingClientRect();
      svg._cadInitialCamera=initialCamera(this.manifest,rect.width,rect.height,options.initialZoom || 1);
      svg.dataset.homeVb=this.manifest.home.join(" ");
      const initial=svg._cadInitialCamera.slice();
      this.camera(initial,()=>svg.setAttribute("viewBox",initial.join(" ")));
    }
    mount(ids) {
      const next=new Set(ids);
      for(const id of this.active) if(!next.has(id)) this.slots[id].replaceChildren();
      for(const id of next) if(!this.active.has(id)) this.slots[id].innerHTML=this.cache.get(id);
      this.active=next;
      // Keep source strings bounded. Active units are in DOM and may be fetched
      // again after eviction; no permanent loss of any geometry.
      for(const [id,value] of this.cache) {
        if(this.cacheBytes<=20*1024*1024) break;
        if(!next.has(id)){this.cache.delete(id);this.cacheBytes-=new TextEncoder().encode(value).length;}
      }
      // Mounted DOM is sufficient: full-home must not retain a second complete
      // drawing as source strings. Re-fetch only when a removed unit returns.
      for(const [id,value] of this.cache) {
        if(this.cacheBytes<=20*1024*1024) break;
        this.cache.delete(id);this.cacheBytes-=new TextEncoder().encode(value).length;
      }
      if(this.viewport) this.viewport.dataset.activePaths=String(this.manifest.shell_paths+ids.reduce((n,id)=>n+this.manifest.units[id].paths,0));
    }
    camera(box,commit) {
      if(this.disposed) return;
      // Once complete initial geometry exists, navigation never waits on HTTP.
      // Keep the displayed vectors while the latest region is prepared separately.
      if(this.responsive && this.viewport.dataset.regionalReadyMs) {
        commit();
        this.desired={box,commit:()=>{}};
        clearTimeout(this.refreshTimer);
        this.refreshTimer=setTimeout(()=>{this.refreshTimer=null;this.drainCamera();},100);
        return;
      }
      this.desired={box,commit};
      this.drainCamera();
    }
    drainCamera() {
      if(this.draining || this.refreshTimer || this.disposed) return;
      this.draining=true;
      const drain=async()=>{
        try {while(this.desired&&!this.disposed&&!this.refreshTimer){const target=this.desired;this.desired=null;await this.applyCamera(target.box,target.commit);}}
        catch(error){console.error('[viewer-regional] região indisponível',error);if(this.viewport)this.viewport.dataset.regionalError='1';}
        finally{this.draining=false;if(this.desired&&!this.refreshTimer&&!this.disposed)this.drainCamera();}
      };
      drain();
    }
    async applyCamera(box,commit) {
      if(this.disabled){commit();return;}
      const generation=++this.generation;
      const rect=this.viewport.getBoundingClientRect();
      const ids=visibleUnits(this.manifest,box,rect.width,rect.height,this.responsive?.18:.06);
      if(ids.every(id=>this.active.has(id))) {
        // Zooming in must release units that left the visible region. Otherwise
        // returning from full-home keeps the entire 392k-path DOM indefinitely.
        if(ids.length!==this.active.size) {
          if(this.responsive) { if(!await this.mountResponsive(ids,generation)) return; }
          else this.mount(ids);
        }
        commit();return;
      }
      const initial=!this.viewport.dataset.regionalReadyMs;
      this.viewport.dataset.regionalLoading=initial?'1':'0';
      this.viewport.dataset.regionalRefreshing=initial?'0':'1';
      try {
        await this.chunks(ids);
        if(this.disposed||this.desired||generation!==this.generation||!this.svg.isConnected) return;
        if(this.responsive) { if(!await this.mountResponsive(ids,generation)) return; }
        else this.mount(ids);
        commit();
        if(!this.viewport.dataset.regionalReadyMs)this.viewport.dataset.regionalReadyMs=(performance.now()-this.started).toFixed(1);
      } catch(error) {
        if(this.disposed||this.signal.aborted||generation!==this.generation) return;
        console.warn('[viewer-regional] fallback integral',error);
        await this.fallback();
        if(!this.disposed&&generation===this.generation) commit();
      } finally {
        if(generation===this.generation) {
          this.viewport.dataset.regionalLoading='0';this.viewport.dataset.regionalRefreshing='0';
        }
      }
    }
    async mountResponsive(ids,generation) {
      let started=performance.now();
      for(const id of ids) {
        if(this.disposed||this.desired||generation!==this.generation) return false;
        if(!this.active.has(id)) {
          this.slots[id].innerHTML=this.cache.get(id);
          this.active.add(id);
        }
        // Split large DOM insertions so input and painting get a turn.
        if(performance.now()-started>=6) {
          await new Promise(resolve=>requestAnimationFrame(resolve));
          started=performance.now();
        }
      }
      if(this.disposed||this.desired||generation!==this.generation) return false;
      this.mount(ids);
      return true;
    }
    async fallback() {
      if(this.disabled) return;
      const r=await response(this.src,this.signal);
      if(r.headers.get('ETag')!==this.manifest.source_revision) throw new Error('Desenho alterado; reabra o viewer');
      const text=await r.text();
      const root=new DOMParser().parseFromString(text,'image/svg+xml').documentElement;
      if(root.localName!=='svg') throw new Error('SVG integral inválido');
      const layers=Array.from(this.svg.querySelectorAll('g.poly-draw-layer,g.crop-svg-layer'));
      this.svg.replaceChildren(...Array.from(root.childNodes).map(n=>document.importNode(n,true)),...layers);
      this.disabled=true;this.viewport.dataset.regional='fallback';
      this.cache.clear();this.cacheBytes=0;
    }
    async buildSnap(extraSegments) {
      if(this.disabled) return null;
      const r=await response(this.url('segments'),this.signal), buffer=await r.arrayBuffer();
      if(buffer.byteLength!==this.manifest.segment_count*32||await digest(buffer)!==this.manifest.segments_sha256) throw new Error('Geometria OSNAP inconsistente');
      const base=new Float64Array(buffer),all=new Float64Array(base.length+extraSegments.length*4);
      all.set(base);extraSegments.forEach((s,i)=>all.set(s,base.length+i*4));
      return new Promise((resolve,reject)=>{
        const worker=new Worker('/static/viewer_snap_worker.js?v=regional-ml-v1-i5');this.workers.add(worker);
        const id=this.manifest.revision;
        const finish=()=>{worker.terminate();this.workers.delete(worker);this.signal.removeEventListener('abort',abort);};
        const abort=()=>{finish();reject(new Error('Viewer encerrado'));};
        worker.onerror=error=>{finish();reject(error);};
        worker.onmessage=event=>{finish();const data=event.data;
          if(this.disposed||data.id!==id||data.error) reject(new Error(data.error||'Índice obsoleto'));else resolve(data.index);};
        this.signal.addEventListener('abort',abort,{once:true});
        worker.postMessage({id,buffer:all.buffer},[all.buffer]);
      });
    }
    dispose() {clearTimeout(this.refreshTimer);this.desired=null;this.disposed=true;this.generation++;for(const worker of this.workers) worker.terminate();this.workers.clear();this.cache.clear();}
  }
  async function load(src,signal) {
    const base=src.replace(/\/foto(?:\?.*)?$/,'/viewer-package/');
    const manifest=await(await response(base+'manifest',signal)).json();
    if(manifest.version!==VERSION||!Array.isArray(manifest.units)||!Array.isArray(manifest.home)) throw new Error('Manifesto inválido');
    const controller=new Controller(src,manifest,signal);
    const bytes=await(await response(controller.url('shell'),signal)).arrayBuffer();
    if(await digest(bytes)!==manifest.shell_sha256) throw new Error('Shell corrompido');
    const original=new TextDecoder().decode(bytes);
    const text=original.replace(/(<g\s+id="LineCollection_[\w.-]+"\s*>)([\s\S]*?)(<\/g\s*>)/g,
      (_,open,body,close)=>open+compactLines(body)+close);
    return {text,regional:controller,chars:text.length,paths:manifest.path_count,initial:initialCamera(manifest)};
  }
  window.CadRegional={load,visibleUnits,initialCamera};
  if(typeof module!=="undefined") module.exports={Controller,visibleUnits,initialCamera,compactLines};
})();
