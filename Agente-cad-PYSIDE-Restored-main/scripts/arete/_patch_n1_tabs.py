"""Converte N1 empilhado → abas (próximo / distante) sem re-render SVG."""
from __future__ import annotations

import re
import sys
from pathlib import Path

N1_CSS = """
.n1-hint{font-size:12px;color:#888;margin:0 0 10px;line-height:1.45}
.n1-tabs{display:flex;gap:0;margin:0 0 10px;border-bottom:1px solid #333}
.n1-tab{background:transparent;border:1px solid transparent;border-bottom:none;color:#888;
  padding:8px 16px;font:13px/1 Consolas,monospace;cursor:pointer;border-radius:4px 4px 0 0;margin-bottom:-1px}
.n1-tab:hover{color:#ccc;background:#1a1a1a}
.n1-tab.active{color:#7eb8f7;background:#151515;border-color:#333;border-bottom-color:#151515;font-weight:bold}
.n1-panel{display:none}
.n1-panel.active{display:block}
.n1-view-note{color:#777;font-size:12px;margin-bottom:6px}
.n1-svg{background:#0d0d0d;border:1px solid #222;border-radius:3px;padding:4px;overflow:auto}
.n1-svg svg{display:block;width:100%;height:auto;max-height:none}
"""

N1_JS = """
<script>
document.addEventListener('DOMContentLoaded',function(){
  var tabs=document.querySelectorAll('.n1-tab');
  if(!tabs.length) return;
  tabs.forEach(function(btn){
    btn.addEventListener('click',function(){
      var id=btn.getAttribute('data-n1tab');
      tabs.forEach(function(b){
        var on=b===btn;
        b.classList.toggle('active',on);
        b.setAttribute('aria-selected',on?'true':'false');
      });
      document.querySelectorAll('.n1-panel').forEach(function(p){
        var on=p.getAttribute('data-n1panel')===id;
        p.classList.toggle('active',on);
        if(on) p.removeAttribute('hidden'); else p.setAttribute('hidden','');
      });
    });
  });
});
</script>
"""


def extract_svg_blocks(html: str) -> tuple[str, str] | None:
    """Pega os dois blocos .n1-svg (near, far) do layout antigo."""
    svgs = re.findall(
        r'<div class="n1-svg">(.*?)</div>\s*</div>',
        html,
        flags=re.S,
    )
    if len(svgs) >= 2:
        return svgs[0], svgs[1]
    # fallback: open div n1-svg until next closing after svg
    parts = re.findall(r'<div class="n1-svg">([\s\S]*?)</div>\s*(?=<div class="n1-view"|</div>\s*</div>\s*</div>)', html)
    if len(parts) >= 2:
        return parts[0], parts[1]
    return None


def patch_one(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if 'data-n1tab="near"' in html:
        return False  # already tabs

    # Extract SVGs from old structure
    m = re.search(
        r'(<div class="sec"><div class="sec-title">Foto N1.*?</div>\s*</div>\s*</div>)',
        html,
        flags=re.S,
    )
    if not m:
        # try alternate title
        m = re.search(
            r'(<div class="sec"><div class="sec-title">Foto N1[\s\S]*?</div></div>)',
            html,
            flags=re.S,
        )
    if not m:
        print("  no N1 block", path.name)
        return False

    old_block = m.group(1)
    # find both n1-svg contents more carefully
    svg_matches = list(re.finditer(r'<div class="n1-svg">', old_block))
    if len(svg_matches) < 2:
        print("  <2 n1-svg", path.name, len(svg_matches))
        return False

    def grab_svg_inner(start_pos: int) -> str:
        # start after <div class="n1-svg">
        i = start_pos
        # find matching close for this div - content may have nested divs in svg? usually not
        # SVG is flat; close is first </div> after start that's at depth 1
        depth = 1
        j = i
        while j < len(old_block) and depth:
            if old_block.startswith("<div", j):
                depth += 1
                j += 4
            elif old_block.startswith("</div>", j):
                depth -= 1
                if depth == 0:
                    return old_block[i:j]
                j += 6
            else:
                j += 1
        return old_block[i:j]

    near = grab_svg_inner(svg_matches[0].end())
    far = grab_svg_inner(svg_matches[1].end())

    new_block = f"""<div class="sec"><div class="sec-title">Foto N1 (SA)</div>
<div class="sec-body">
<div class="n1-hint">Leitura em duas escalas — só um recorte visível por vez. O vínculo vale quando
<b>próximo</b> (contato) e <b>distante</b> (eixo/etiqueta) forem compatíveis.</div>
<div class="n1-tabs" role="tablist">
  <button type="button" class="n1-tab active" data-n1tab="near" role="tab" aria-selected="true">N1 próximo</button>
  <button type="button" class="n1-tab" data-n1tab="far" role="tab" aria-selected="false">N1 distante</button>
</div>
<div class="n1-panel active" data-n1panel="near" role="tabpanel">
  <div class="n1-view-note">Contato/local — face tocada, seção, cota e chegada/passagem no contorno do pilar.</div>
  <div class="n1-svg">{near}</div>
</div>
<div class="n1-panel" data-n1panel="far" role="tabpanel" hidden>
  <div class="n1-view-note">Contexto distante — continuidade e nome fora do recorte próximo (não cria vínculo sozinho).</div>
  <div class="n1-svg">{far}</div>
</div>
</div></div>"""

    html2 = html.replace(old_block, new_block, 1)

    # CSS: replace old n1-views block if present, else inject
    html2 = re.sub(
        r"\.n1-views\{[^}]+\}",
        "",
        html2,
    )
    html2 = re.sub(
        r"\.n1-view-label\{[^}]+\}",
        "",
        html2,
    )
    if ".n1-tabs{" not in html2:
        html2 = html2.replace("</style>", N1_CSS + "\n</style>", 1)
    if "data-n1tab" in html2 and "querySelectorAll('.n1-tab')" not in html2:
        html2 = html2.replace("</head>", N1_JS + "\n</head>", 1)

    if html2 != html:
        path.write_text(html2, encoding="utf-8")
        return True
    return False


def main() -> int:
    pack = Path(
        r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete"
        r"\html_fichas\Obra_TREINO_1\13_PAV_20260730_210556_pilares_abcd\pilares"
    )
    if len(sys.argv) > 1:
        pack = Path(sys.argv[1])
    n = 0
    for f in sorted(pack.glob("P*.html")):
        ok = patch_one(f)
        print(("ok" if ok else "skip"), f.name)
        if ok:
            n += 1
    print(f"[OK] {n} patched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
