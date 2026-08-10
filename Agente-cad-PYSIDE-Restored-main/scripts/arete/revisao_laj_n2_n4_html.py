#!/usr/bin/env python3
"""Painel humano local para revisar recortes N2 de LAJ contra N4 existente,
com pan/zoom real (svg-pan-zoom) — mesmo padrão de revisao_pil_n2_n4_html.py
(+ enhance_revisao_svg_panzoom.py), só que nativo (sem passo de "enhance"
separado) e adaptado a LAJ.

E' somente apresentacao: le o DB e os DXFs existentes, usa o renderizador SVG
canonico e nao executa comparacao, geracao, gate nem escrita no banco. O
estado humano (checkbox "Validado" + nota de atencao) vive no localStorage do
navegador e pode ser exportado/importado.
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
from src.core.n2_marco_highlight import motor_poly_from_recorte


N4_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/n4")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_panel(pav: str, out_dir: Path) -> Path:
    rows = query_fichas("LAJ", pav)
    cards: list[str] = []
    manifest: list[dict[str, str | None]] = []
    for row in rows:
        item = row["elemento_id"]
        obra_name = row.get("obra_name") or ""
        n2 = get_recorte_path(item, "LAJ", row=row)
        n4 = N4_DIR / f"LJ_preview_{item}.dxf"
        n2_ok, n4_ok = bool(n2 and n2.is_file()), n4.is_file()
        # Marco laranja no N2 = MESMO contorno que o Comparison Engine mostra
        # (src/core/n2_marco_highlight.py::motor_poly_from_recorte, motor
        # dinâmico live no recorte — equivalente ao contorno N4).
        marco = []
        if n2_ok:
            try:
                marco, _ficha = motor_poly_from_recorte(
                    n2, item, obra_name, pavimento=pav, prefer_live=True,
                )
            except Exception:
                marco = []
        n2_plain_svg = render(n2, width=1500, height=1100, fmt="svg") if n2_ok else "<p>Recorte N2 ausente.</p>"
        n2_marked_svg = render(n2, width=1500, height=1100, fmt="svg", highlight_polys=[marco] if marco else None) if n2_ok else "<p>Recorte N2 ausente.</p>"
        n4_svg = render(n4, width=1500, height=1100, fmt="svg") if n4_ok else "<p>N4 ausente.</p>"
        key = f"LAJ::{pav}::{item}"
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
  <div class="drawings"><section><h3>N2 · recorte humano (puro)</h3><div class="canvas zoomable">{n2_plain_svg}</div></section>
    <section><h3>N2 · área demarcada (marco = contorno N4)</h3><div class="canvas zoomable">{n2_marked_svg}</div></section>
    <section><h3>N4 · gerado da ficha</h3><div class="canvas zoomable">{n4_svg}</div></section></div>
  <label class="attention">Atenção / observação
    <textarea class="note" rows="3" placeholder="O que precisa de atenção? (salva automaticamente neste navegador)"></textarea>
  </label>
</article>''')

    out_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    document = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Revisão humana · LAJ N2 × N4 · {html.escape(pav)}</title>
<script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
<style>
:root{{color-scheme:dark}}body{{margin:0;background:#11151b;color:#e9eef5;font:14px system-ui,sans-serif}}main{{max-width:2400px;margin:auto;padding:20px}}h1{{margin:.1rem 0}}.notice{{color:#a9b8c8}}.toolbar{{position:sticky;top:0;z-index:2;background:#1a2029;border:1px solid #354354;border-radius:8px;padding:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}button{{background:#2d77c9;color:white;border:0;border-radius:5px;padding:8px 12px;cursor:pointer}}button.secondary{{background:#465362}}#summary{{font-weight:600}}#savestatus{{color:#9fb0c3;font-size:12px}}#savestatus.err{{color:#ff7676;font-weight:700}}.card{{background:#181e27;border:1px solid #313c4a;border-radius:9px;padding:14px;margin:18px 0}}.card header{{display:flex;gap:14px;align-items:center;flex-wrap:wrap}}h2{{margin:0}}h3{{margin:6px 0;color:#bdceea;font-size:13px}}.availability{{color:#9fb0c3}}.decision{{margin-left:auto;font-weight:700}}.validated{{width:18px;height:18px;vertical-align:middle}}.drawings{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-top:10px}}.canvas{{height:560px;background:#fff;overflow:hidden;cursor:grab;color:#27313d}}.canvas:active{{cursor:grabbing}}.canvas svg{{width:100%;height:100%;display:block}}.attention{{display:block;margin-top:12px;font-weight:600}}textarea{{display:block;box-sizing:border-box;width:100%;margin-top:5px;background:#10151c;color:#e9eef5;border:1px solid #46576a;border-radius:5px;padding:8px;font:inherit}}.only-pending .card.done{{display:none}}@media(max-width:1400px){{.drawings{{grid-template-columns:1fr}}}}@media(max-width:900px){{.decision{{margin-left:0}}}}
</style></head><body><main>
<h1>Revisão humana · Lajes N2 × N4</h1><p class="notice">{len(rows)} lajes · {html.escape(pav)} · gerado em {html.escape(generated)}. Painel de triagem humana: não altera banco nem sela gate. Roda do mouse amplia/reduz; depois de ampliar, arraste para mover.</p>
<div class="toolbar"><span id="summary"></span><span id="savestatus"></span><button id="pending" class="secondary">Mostrar só pendentes</button></div>
{''.join(cards)}
</main><script>
const cards=[...document.querySelectorAll('.card')];
let remote={{}};
const statusEl=document.querySelector('#savestatus');
function get(c){{return remote[c.dataset.key]||{{}};}}
function paint(c){{const s=get(c);c.querySelector('.validated').checked=!!s.validated;c.querySelector('.note').value=s.note||'';c.classList.toggle('done',!!s.validated);}}
function summary(){{const done=cards.filter(c=>get(c).validated).length;document.querySelector('#summary').textContent=`${{done}}/${{cards.length}} validados · ${{cards.length-done}} pendentes`;}}
async function persist(key, value){{
  try{{
    const res = await fetch('/api/state', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{[key]: value}})}});
    if (!res.ok) throw new Error('HTTP '+res.status);
    statusEl.textContent='salvo em revisoes_humanas.json'; statusEl.classList.remove('err');
  }}catch(err){{
    statusEl.textContent='ERRO ao salvar — abra via servidor_revisao_pil.py (não direto do arquivo)'; statusEl.classList.add('err');
  }}
}}
function save(c){{
  const s={{validated:c.querySelector('.validated').checked, note:c.querySelector('.note').value, updated_at:new Date().toISOString()}};
  remote[c.dataset.key]=s; paint(c); summary();
  clearTimeout(c._debounce); c._debounce=setTimeout(()=>persist(c.dataset.key, s), 400);
}}
async function loadState(){{
  try{{
    const res = await fetch('revisoes_humanas.json', {{cache:'no-store'}});
    if (res.ok) remote = await res.json();
    statusEl.textContent='conectado ao servidor';
  }}catch(err){{
    statusEl.textContent='ERRO ao carregar — abra via servidor_revisao_pil.py (não direto do arquivo)'; statusEl.classList.add('err');
  }}
  cards.forEach(paint); summary();
}}
cards.forEach(c=>{{
  c.querySelector('.validated').addEventListener('change', ()=>save(c));
  c.querySelector('.note').addEventListener('input', ()=>save(c));
}});
loadState();
if (typeof svgPanZoom === 'function') {{
  document.querySelectorAll('.zoomable svg').forEach(svg => svgPanZoom(svg, {{
    zoomEnabled: true, panEnabled: true, controlIconsEnabled: true,
    mouseWheelZoomEnabled: true, dblClickZoomEnabled: false,
    fit: true, center: true, minZoom: .4, maxZoom: 12,
    preventMouseEventsDefault: true
  }}));
}} else {{
  document.querySelector('.notice').textContent += ' · Controle SVG indisponível.';
}}
let pending=false;document.querySelector('#pending').onclick=()=>{{pending=!pending;document.body.classList.toggle('only-pending',pending);document.querySelector('#pending').textContent=pending?'Mostrar todos':'Mostrar só pendentes';}};
</script></body></html>'''
    index = out_dir / "index_panzoom.html"
    index.write_text(document, encoding="utf-8")
    (out_dir / "manifesto.json").write_text(json.dumps({"generated_at": generated, "pavimento": pav, "items": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    state_path = out_dir / "revisoes_humanas.json"
    if not state_path.exists():
        state_path.write_text("{}", encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description="Painel humano LAJ N2 x N4 com pan/zoom, sem escrita no DB")
    parser.add_argument("--pav", default="13_PAV")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--serve", action="store_true", help="Sobe servidor_revisao_pil.py apontado para a pasta gerada e abre o navegador (persistência real em revisoes_humanas.json, sem export manual)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(args.out_dir) if args.out_dir else ROOT / "scripts" / "arete" / "relatorios" / f"revisao_laj_n2_n4_{stamp}"
    index = build_panel(args.pav, out).resolve()
    print(index)
    if args.serve:
        import subprocess
        import webbrowser

        servidor = ARETE_DIR / "servidor_revisao_pil.py"
        url = f"http://127.0.0.1:{args.port}/{index.name}"
        print(f"Servindo em {url} (Ctrl+C para parar)")
        webbrowser.open(url)
        subprocess.run([
            sys.executable, str(servidor),
            "--directory", str(out.resolve()),
            "--port", str(args.port),
        ])


if __name__ == "__main__":
    main()
