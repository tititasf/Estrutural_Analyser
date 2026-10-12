/* Exact Float64 geometry, independent of the mounted SVG painting regions. */
(function(root) {
  'use strict';
  function build(segments) {
    const order = Array.from({length:segments.length/4},(_,i)=>i), nodes=[];
    function split(start,end) {
      const at=nodes.length/8;
      let x0=Infinity,y0=Infinity,x1=-Infinity,y1=-Infinity;
      for(let j=start;j<end;j++) {const i=order[j]*4;
        x0=Math.min(x0,segments[i],segments[i+2]); y0=Math.min(y0,segments[i+1],segments[i+3]);
        x1=Math.max(x1,segments[i],segments[i+2]); y1=Math.max(y1,segments[i+1],segments[i+3]);}
      nodes.push(x0,y0,x1,y1,start,end-start,-1,-1);
      if(end-start>32) {
        const axis=x1-x0>=y1-y0?0:1;
        const sorted=order.slice(start,end).sort((a,b)=>(segments[a*4+axis]+segments[a*4+axis+2])-(segments[b*4+axis]+segments[b*4+axis+2])||a-b);
        for(let j=0;j<sorted.length;j++) order[start+j]=sorted[j];
        const mid=(start+end)>>>1; nodes[at*8+6]=split(start,mid);nodes[at*8+7]=split(mid,end);
      }
      return at;
    }
    if(order.length) split(0,order.length);
    return {segments,nodes:new Float64Array(nodes),order:new Uint32Array(order)};
  }
  function nearest(index,x,y,threshold,vertices) {
    const s=index.segments,n=index.nodes,o=index.order,ids=[],stack=n.length?[0]:[];
    while(stack.length) {const at=stack.pop()*8;
      if(n[at]>x+threshold||n[at+2]<x-threshold||n[at+1]>y+threshold||n[at+3]<y-threshold) continue;
      if(n[at+6]>=0) {stack.push(n[at+7],n[at+6]);continue;}
      for(let j=n[at+4];j<n[at+4]+n[at+5];j++) ids.push(o[j]);
    }
    ids.sort((a,b)=>a-b); // deterministic original painting order for ties
    let best=null,distance=threshold*threshold,cross=null,crossDistance=distance;
    function point(a,b) {const d=(a-x)**2+(b-y)**2;if(d<distance){distance=d;best={x:a,y:b};}}
    const local=[];
    for(const id of ids) {const i=id*4,a=s[i],b=s[i+1],c=s[i+2],d=s[i+3],dx=c-a,dy=d-b,len=dx*dx+dy*dy;
      point(a,b);point(c,d);
      if(len<1e-12) continue;
      const t=Math.max(0,Math.min(1,((x-a)*dx+(y-b)*dy)/len));
      if((a+t*dx-x)**2+(b+t*dy-y)**2<=(threshold*1.2)**2) local.push(i);
    }
    for(let a=0;a<local.length;a++) {const i=local[a];
      for(let b=a+1;b<local.length;b++) {const j=local[b];
        const den=(s[i]-s[i+2])*(s[j+1]-s[j+3])-(s[i+1]-s[i+3])*(s[j]-s[j+2]);
        if(Math.abs(den)<1e-14) continue;
        const t=((s[i]-s[j])*(s[j+1]-s[j+3])-(s[i+1]-s[j+1])*(s[j]-s[j+2]))/den;
        const u=-((s[i]-s[i+2])*(s[i+1]-s[j+1])-(s[i+1]-s[i+3])*(s[i]-s[j]))/den;
        if(t < -1e-9||t>1+1e-9||u < -1e-9||u>1+1e-9) continue;
        const px=s[i]+t*(s[i+2]-s[i]),py=s[i+1]+t*(s[i+3]-s[i+1]),dd=(px-x)**2+(py-y)**2;
        if(dd<crossDistance){crossDistance=dd;cross={x:px,y:py};}
      }
    }
    if(vertices) for(const p of vertices) point(p[0],p[1]);
    const result=cross||best;
    if(result){result.dist=Math.sqrt(cross?crossDistance:distance);result.px=false;}
    return result;
  }
  root.CadSpatial={build,nearest};
  if(typeof module!=='undefined') module.exports=root.CadSpatial;
})(typeof self!=='undefined'?self:globalThis);
