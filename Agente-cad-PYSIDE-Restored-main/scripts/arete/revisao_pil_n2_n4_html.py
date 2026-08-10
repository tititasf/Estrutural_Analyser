#!/usr/bin/env python3
"""Painel humano local para revisar recortes N2 de PIL contra N4 existente.

E' somente apresentacao: le o DB e os DXFs existentes, usa o renderizador SVG
canonico e nao executa comparacao, geracao, gate nem escrita no banco.
O estado humano vive no localStorage do navegador e pode ser exportado/importado.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARETE_DIR = Path(__file__).resolve().parent
if str(ARETE_DIR) not in sys.path:
    sys.path.insert(0, str(ARETE_DIR))

from ficha_adapter import get_recorte_path, query_fichas
from scripts.arete.dxf_to_svg_casos import render


N4_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n4")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_panel(pav: str, out_dir: Path) -> Path:
    rows = query_fichas("PIL", pav)
    cards: list[str] = []
    manifest: list[dict[str, str | None]] = []
    for row in rows:
        item = row["elemento_id"]
        n2 = get_recorte_path(item, "PIL", row=row)
        n4 = N4_DIR / f"PL_preview_{item}.dxf"
        n2_ok, n4_ok = bool(n2 and n2.is_file()), n4.is_file()
        n2_svg = render(n2, width=1500, height=1100, fmt="svg") if n2_ok else "<p>Recorte N2 ausente.</p>"
        n4_svg = render(n4, width=1500, height=1100, fmt="svg") if n4_ok else "<p>N4 combinado ausente.</p>"
        key = f"PIL::{pav}::{item}"
        manifest.append({
            "item": item, "state_key": key,
            "n2_path": str(n2) if n2_ok else None,
            "n2_sha256": sha256(n2) if n2_ok else None,
            "n4_path": str(n4) if n4_ok else None,
            "n4_sha256": sha256(n4) if n4_ok else None,
        })
        cards.append(f'''<article class="card" data-key="{html.escape(key)}" data-item="{html.escape(item)}">
  <header><h2>{html.escape(item)}</h2><span class="availability">N2: {"ok" if n2_ok else "ausente"} · N4: {"ok" if n4_ok else "ausente"}</span>
    <label class="decision"><input class="validated" type="checkbox"> Validado</label>
  </header>
  <div class="drawings"><section><h3>N2 · recorte humano</h3><div class="canvas zoomable" data-zoom="1" title="Roda do mouse: zoom · duplo clique: 100%"><div class="zoom-controls"><button class="zoom-out" type="button" aria-label="Diminuir zoom">−</button><button class="zoom-reset" type="button">100%</button><button class="zoom-in" type="button" aria-label="Aumentar zoom">+</button></div>{n2_svg}</div></section>
    <section><h3>N4 · gerado da ficha</h3><div class="canvas zoomable" data-zoom="1" title="Roda do mouse: zoom · duplo clique: 100%"><div class="zoom-controls"><button class="zoom-out" type="button" aria-label="Diminuir zoom">−</button><button class="zoom-reset" type="button">100%</button><button class="zoom-in" type="button" aria-label="Aumentar zoom">+</button></div>{n4_svg}</div></section></div>
  <label class="attention">Atenção / observação
    <textarea class="note" rows="3" placeholder="O que precisa de atenção? (salva automaticamente neste navegador)"></textarea>
  </label>
</article>''')

    out_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    document = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Revisão humana · PIL N2 × N4 · {html.escape(pav)}</title><style>
:root{{color-scheme:dark}}body{{margin:0;background:#11151b;color:#e9eef5;font:14px system-ui,sans-serif}}main{{max-width:1800px;margin:auto;padding:20px}}h1{{margin:.1rem 0}}.notice{{color:#a9b8c8}}.toolbar{{position:sticky;top:0;z-index:2;background:#1a2029;border:1px solid #354354;border-radius:8px;padding:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}button{{background:#2d77c9;color:white;border:0;border-radius:5px;padding:8px 12px;cursor:pointer}}button.secondary{{background:#465362}}#summary{{font-weight:600}}.card{{background:#181e27;border:1px solid #313c4a;border-radius:9px;padding:14px;margin:18px 0}}.card header{{display:flex;gap:14px;align-items:center;flex-wrap:wrap}}h2{{margin:0}}h3{{margin:6px 0;color:#bdceea}}.availability{{color:#9fb0c3}}.decision{{margin-left:auto;font-weight:700}}.validated{{width:18px;height:18px;vertical-align:middle}}.drawings{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:10px}}.canvas{{position:relative;background:white;overflow:auto;min-height:260px;max-height:720px;cursor:zoom-in}}.canvas svg{{display:block;width:100%;height:auto;min-width:0}}.zoom-controls{{position:sticky;top:6px;left:6px;z-index:2;display:flex;gap:4px;width:max-content;background:#1a2029e8;border-radius:5px;padding:4px}}.zoom-controls button{{padding:3px 8px;font:12px monospace}}.attention{{display:block;margin-top:12px;font-weight:600}}textarea{{display:block;box-sizing:border-box;width:100%;margin-top:5px;background:#10151c;color:#e9eef5;border:1px solid #46576a;border-radius:5px;padding:8px;font:inherit}}.only-pending .card.done{{display:none}}@media(max-width:900px){{.drawings{{grid-template-columns:1fr}}.decision{{margin-left:0}}}}
</style></head><body><main>
<h1>Revisão humana · Pilares N2 × N4</h1><p class="notice">{len(rows)} pilares · {html.escape(pav)} · gerado em {html.escape(generated)}. Painel de triagem humana: não altera banco nem sela gate.</p>
<div class="toolbar"><span id="summary"></span><button id="pending" class="secondary">Mostrar só pendentes</button><button id="export">Exportar respostas (.json)</button><label><button id="importBtn" class="secondary" type="button">Importar respostas</button><input id="import" type="file" accept="application/json" hidden></label><button id="clear" class="secondary">Limpar estado local</button></div>
{''.join(cards)}
</main><script>
const prefix='cad-analyzer/revisao-pil-n2-n4/'; const cards=[...document.querySelectorAll('.card')];
const stateKey=c=>prefix+c.dataset.key; const get=c=>JSON.parse(localStorage.getItem(stateKey(c))||'{{}}');
function save(c){{const s={{validated:c.querySelector('.validated').checked,note:c.querySelector('.note').value,updated_at:new Date().toISOString()}};localStorage.setItem(stateKey(c),JSON.stringify(s)); paint(c); summary();}}
function paint(c){{const s=get(c);c.querySelector('.validated').checked=!!s.validated;c.querySelector('.note').value=s.note||'';c.classList.toggle('done',!!s.validated);}}
function summary(){{const done=cards.filter(c=>get(c).validated).length;document.querySelector('#summary').textContent=`${{done}}/${{cards.length}} validados · ${{cards.length-done}} pendentes`;}}
cards.forEach(c=>{{paint(c);c.querySelector('.validated').addEventListener('change',()=>save(c));c.querySelector('.note').addEventListener('input',()=>save(c));}});summary();
document.querySelectorAll('.zoomable').forEach(box=>{{const svg=box.querySelector('svg'),reset=box.querySelector('.zoom-reset');const set=z=>{{z=Math.max(.5,Math.min(4,z));box.dataset.zoom=z;svg.style.width=(z*100)+'%';reset.textContent=Math.round(z*100)+'%';box.style.cursor=z>1?'zoom-out':'zoom-in';}};box.querySelector('.zoom-in').addEventListener('click',()=>set(Number(box.dataset.zoom)+.25));box.querySelector('.zoom-out').addEventListener('click',()=>set(Number(box.dataset.zoom)-.25));reset.addEventListener('click',()=>set(1));box.addEventListener('wheel',e=>{{e.preventDefault();set(Number(box.dataset.zoom)+(e.deltaY<0?.15:-.15));}},{{passive:false}});box.addEventListener('dblclick',()=>set(1));}});
let pending=false;document.querySelector('#pending').onclick=()=>{{pending=!pending;document.body.classList.toggle('only-pending',pending);document.querySelector('#pending').textContent=pending?'Mostrar todos':'Mostrar só pendentes';}};
document.querySelector('#export').onclick=()=>{{const data={{schema:'cad-analyzer.revisao-pil-n2-n4/v1',exported_at:new Date().toISOString(),items:Object.fromEntries(cards.map(c=>[c.dataset.key,get(c)]))}};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{{type:'application/json'}}));a.download='respostas_pil_n2_n4.json';a.click();URL.revokeObjectURL(a.href);}};
document.querySelector('#importBtn').onclick=()=>document.querySelector('#import').click();document.querySelector('#import').onchange=async e=>{{try{{const d=JSON.parse(await e.target.files[0].text());Object.entries(d.items||{{}}).forEach(([k,v])=>localStorage.setItem(prefix+k,JSON.stringify(v)));cards.forEach(paint);summary();}}catch(err){{alert('Arquivo de respostas inválido: '+err.message)}}}};
document.querySelector('#clear').onclick=()=>{{if(confirm('Limpar somente o estado desta revisão neste navegador?')){{cards.forEach(c=>localStorage.removeItem(stateKey(c)));cards.forEach(paint);summary();}}}};
</script></body></html>'''
    index = out_dir / "index.html"
    index.write_text(document, encoding="utf-8")
    (out_dir / "manifesto.json").write_text(json.dumps({"generated_at": generated, "pavimento": pav, "items": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Painel humano PIL N2 x N4, sem escrita no DB")
    parser.add_argument("--pav", default="13_PAV")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out_dir) if args.out_dir else ROOT / "scripts" / "arete" / "relatorios" / f"revisao_pil_n2_n4_{stamp}"
    print(build_panel(args.pav, out).resolve())


if __name__ == "__main__":
    main()
