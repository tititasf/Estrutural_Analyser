// Unit test of the real shared helper, using a minimal DOM test double.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
class Element {
  constructor(tag) { this.tagName=tag; this.children=[]; this.attrs={}; this.className=''; this.classList={contains:c=>this.className.split(' ').includes(c),toggle:(c,on)=>{this.className=this.className.split(' ').filter(x=>x&&x!==c).concat(on?[c]:[]).join(' ');}}; }
  setAttribute(k,v) { this.attrs[k]=v; }
  appendChild(e) { e.parentNode=this; this.children.push(e); }
  insertBefore(e,b) { e.parentNode=this; this.children.splice(this.children.indexOf(b),0,e); }
  replaceChildren() { this.children=[]; }
  get previousElementSibling() { return this.parentNode?.children[this.parentNode.children.indexOf(this)-1]; }
  querySelectorAll() { return this.children.filter(e=>e.classList.contains('drawing-mode-badge')); }
  remove() { this.parentNode.children=this.parentNode.children.filter(e=>e!==this); }
}
let href='https://example.test/?modo_desenho=NOVA';
const window={location:{get href(){return href;}},history:{replaceState:(_s,_t,url)=>{href=url;}}};
vm.runInNewContext(fs.readFileSync('portal/app/static/drawing_mode.js','utf8'),{window,document:{createElement:t=>new Element(t)},URL});
for(const viewer of ['PIL','FV','LJ']) {
  const parent=new Element('section'), viewport=new Element('div'), old=new Element('button');
  old.className='drawing-mode-badge'; viewport.appendChild(old); parent.appendChild(viewport);
  let selected=null;
  const tabs=window.DrawingMode.applyBadge(viewport,'NOVA',{onChange:m=>{selected=m;}});
  assert.equal(parent.children[0],tabs); assert.equal(parent.children[1],viewport);
  assert.equal(viewport.children.length,0); assert.equal(tabs.children.length,2);
  assert.equal(tabs.children[0].attrs['aria-selected'],'true');
  tabs.children[0].onclick(); assert.equal(selected,null);
  tabs.children[1].onclick(); assert.equal(selected,'INI'); assert.equal(new URL(href).searchParams.get('modo_desenho'),'INI');
  assert.equal(window.DrawingMode.applyBadge(viewport,'INI',{onChange:()=>{}}),tabs);
  assert.equal(parent.children.length,2); assert.equal(tabs.children[1].attrs['aria-selected'],'true');
  console.log(viewer+': placement, switching, URL and no duplicates OK');
}
