"""Painel leve de revisão humana PIL: N2, N4 CIMA e N4 ABCD.

Os SVGs ficam em arquivos separados e são carregados sob demanda. Assim o
estado dos checkboxes/notas é inicializado antes do desenho pesado.
"""
from __future__ import annotations

from datetime import datetime
import html
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ARETE_DIR = Path(__file__).resolve().parent
for entry in (ROOT, ARETE_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from ficha_adapter import get_recorte_path, query_fichas
from scripts.arete.dxf_to_svg_casos import render

N4_DIR = Path('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n4')


def save_svg(source: Path | None, target: Path) -> bool:
    if not source or not source.is_file():
        return False
    target.write_text(render(source, width=1500, height=1100, fmt='svg'), encoding='utf-8')
    return True


def build(pav: str, out_path: Path) -> Path:
    assets = out_path.parent / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    # Evita reutilizar o SVG de uma geração anterior no cache do navegador.
    asset_revision = datetime.now().strftime('%Y%m%d%H%M%S')
    cards: list[str] = []
    for row in query_fichas('PIL', pav):
        item = row['elemento_id']
        n2 = get_recorte_path(item, 'PIL', row=row)
        sources = {
            'n2': Path(n2) if n2 else None,
            'cima': N4_DIR / f'PL_CIMA_preview_{item}.dxf',
            'abcd': N4_DIR / f'PL_ABCD_preview_{item}.dxf',
        }
        efgh = N4_DIR / f'PL_EFGH_preview_{item}.dxf'
        if efgh.is_file():
            sources['efgh'] = efgh
        views = []
        titles = [('n2', 'N2 · recorte humano'), ('cima', 'N4 · visão CIMA'), ('abcd', 'N4 · visão ABCD')]
        if 'efgh' in sources:
            titles.append(('efgh', 'N4 · faces E/F (pilar L)'))
        for kind, title in titles:
            asset_name = f'{item}_{kind}.svg'
            ok = save_svg(sources[kind], assets / asset_name)
            body = (f'<div class="canvas" data-src="assets/{html.escape(asset_name)}?rev={asset_revision}"><span>Carregando SVG…</span></div>'
                    if ok else '<div class="canvas missing">Artefato ausente.</div>')
            views.append(f'<section><h3>{title}</h3>{body}</section>')
        key = f'PIL::{pav}::{item}'
        cards.append(f'''<article class="card" data-key="{html.escape(key)}">
<header><h2>{html.escape(item)}</h2><label><input class="validated" type="checkbox"> Validado</label></header>
<div class="views">{''.join(views)}</div>
<label class="attention">Atenção / observação<textarea class="note" rows="3" placeholder="Salva automaticamente neste navegador"></textarea></label>
</article>''')
    doc = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Revisão PIL · N2 × N4 CIMA/ABCD</title>
<script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
<style>:root{{color-scheme:dark}}body{{margin:0;background:#11151b;color:#e9eef5;font:14px system-ui,sans-serif}}main{{max-width:2100px;margin:auto;padding:18px}}h1{{margin:0}}.notice{{color:#a9b8c8}}.toolbar{{position:sticky;top:0;z-index:5;background:#1a2029;border:1px solid #354354;border-radius:8px;padding:10px;margin:12px 0;display:flex;gap:16px;align-items:center}}#save-status{{color:#9ee5ba}}.card{{background:#181e27;border:1px solid #313c4a;border-radius:9px;padding:14px;margin:16px 0}}header{{display:flex;justify-content:space-between;align-items:center}}h2,h3{{margin:0 0 7px}}h3{{color:#bdceea;font-size:14px}}.views{{display:grid;grid-template-columns:repeat(auto-fit,minmax(390px,1fr));gap:10px}}.canvas{{height:570px;background:#fff;overflow:hidden;cursor:grab;color:#27313d;display:grid;place-items:center}}.canvas:active{{cursor:grabbing}}.canvas svg{{width:100%;height:100%;display:block}}.missing{{color:#a00;padding:16px}}.attention{{display:block;margin-top:10px;font-weight:600}}textarea{{display:block;box-sizing:border-box;width:100%;margin-top:4px;background:#10151c;color:#e9eef5;border:1px solid #46576a;border-radius:5px;padding:8px;font:inherit}}.validated{{width:18px;height:18px;vertical-align:middle}}@media(max-width:1250px){{.views{{grid-template-columns:1fr}}.canvas{{height:620px}}}}</style></head><body><main>
<h1>Pilares · N2 × N4 por vista</h1><p class="notice">SVGs são carregados ao se aproximarem da tela. Roda do mouse amplia/reduz; depois de ampliar, segure o botão esquerdo e arraste para mover.</p><div class="toolbar"><span id="summary"></span><span id="save-status" aria-live="polite">Estado pronto</span></div>{''.join(cards)}
</main><script>
const prefix='cad_analyzer_review_';const cards=[...document.querySelectorAll('.card')];const status=document.querySelector('#save-status');
function cookieName(card){{return prefix+card.dataset.key.replace(/[^a-zA-Z0-9]/g,'_');}}
function read(card){{try{{const name=cookieName(card)+'=';const part=document.cookie.split('; ').find(row=>row.startsWith(name));return part?JSON.parse(decodeURIComponent(part.slice(name.length))):{{}};}}catch(e){{status.textContent='Não foi possível ler o estado salvo';return {{}}}}}}
function paint(card){{const data=read(card);card.querySelector('.validated').checked=!!data.validated;card.querySelector('.note').value=data.note||'';}}
function summary(){{document.querySelector('#summary').textContent=`${{cards.filter(card=>read(card).validated).length}}/${{cards.length}} validados`;}}
const pendingSync={{}};let syncTimer=0;
function sync(key,data){{pendingSync[key]=data;clearTimeout(syncTimer);syncTimer=setTimeout(()=>{{const batch=Object.assign({{}},pendingSync);Object.keys(pendingSync).forEach(key=>delete pendingSync[key]);fetch('/api/state',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(batch)}}).catch(()=>{{Object.assign(pendingSync,batch);}});}},300);}}
function save(card){{const data={{validated:card.querySelector('.validated').checked,note:card.querySelector('.note').value,updated_at:new Date().toISOString()}};try{{const value=encodeURIComponent(JSON.stringify(data));if(value.length>3500)throw Error('nota longa');document.cookie=`${{cookieName(card)}}=${{value}}; Max-Age=31536000; Path=/; SameSite=Lax`;sync(card.dataset.key,data);status.textContent='Salvo às '+new Date().toLocaleTimeString();}}catch(e){{status.textContent='Nota muito longa para salvar (limite: cerca de 3.500 caracteres)';}}summary();}}
cards.forEach(card=>{{paint(card);const saved=read(card);if(saved.validated||saved.note)sync(card.dataset.key,saved);card.querySelector('.validated').addEventListener('change',()=>save(card));card.querySelector('.note').addEventListener('input',()=>save(card));}});summary();window.addEventListener('beforeunload',()=>cards.forEach(save));
function activate(canvas){{if(canvas.dataset.loaded)return;canvas.dataset.loaded='1';fetch(canvas.dataset.src).then(r=>{{if(!r.ok)throw Error();return r.text()}}).then(markup=>{{canvas.innerHTML=markup;const svg=canvas.querySelector('svg');if(typeof svgPanZoom==='function'&&svg)svgPanZoom(svg,{{zoomEnabled:true,panEnabled:true,controlIconsEnabled:true,mouseWheelZoomEnabled:true,dblClickZoomEnabled:false,fit:true,center:true,minZoom:.4,maxZoom:12,preventMouseEventsDefault:true}});}}).catch(()=>canvas.textContent='Não foi possível carregar o SVG.');}}
const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{{if(entry.isIntersecting){{activate(entry.target);observer.unobserve(entry.target);}}}}),{{rootMargin:'900px 0px'}});document.querySelectorAll('.canvas[data-src]').forEach(canvas=>observer.observe(canvas));
</script></body></html>'''
    out_path.write_text(doc, encoding='utf-8')
    return out_path


if __name__ == '__main__':
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target = ROOT / 'scripts' / 'arete' / 'relatorios' / f'revisao_pil_vistas_{stamp}' / 'index.html'
    print(build('13_PAV', target))
