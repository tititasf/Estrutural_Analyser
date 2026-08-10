#!/usr/bin/env python
"""Patch nas fichas ABCD existentes: injeta botão "Próximo pendente" na nav-bar.

Não re-renderiza SVG/tabelas — só injeta CSS/HTML/JS na nav-bar de cada
pilares/P*.html. Idempotente (não duplica se já injetado).

O botão pula, a partir do item atual, para o próximo pilar cujo estado
(via GET /api/notes/{P}) seja: SA invalidado pelo humano e NENHUMA camada
(SA/L1/L2/L3) ainda validada — mesmo critério de "st-bad" do index.html.

Uso:
  py -3.12 scripts/arete/_patch_abcd_next_invalid_btn.py <pack_dir>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ORDER = [f"P{i}" for i in range(1, 36)] + [f"P{i}" for i in range(41, 52)]

MARK = "nav-next-invalid-btn"

CSS = """
.nav-next-invalid-btn{color:#ef9a9a;text-decoration:none;border:1px solid #7a2b2b;
  background:#1f0d0d;padding:4px 10px;border-radius:3px;font-size:12px;cursor:pointer;
  font-family:inherit}
.nav-next-invalid-btn:hover{border-color:#ef5350;background:#2a1010}
.nav-next-invalid-btn:disabled{opacity:.5;cursor:default}
"""

JS_TMPL = """
<script>
(function(){
  var ORDER = __ORDER__;
  var CUR = __CUR__;
  var btn = document.getElementById('nav-next-invalid');
  if(!btn) return;
  function isPending(notes){
    var sa = null, anyValidou = false;
    Object.keys(notes || {}).forEach(function(k){
      if(k.indexOf('aten_pil_hl_') !== 0 || k.indexOf('_human_') === -1) return;
      var v = notes[k];
      if(k.indexOf('aten_pil_hl_sa_human_') === 0) sa = v;
      if(v === 'validou') anyValidou = true;
    });
    return sa === 'invalidou' && !anyValidou;
  }
  btn.addEventListener('click', function(){
    btn.disabled = true;
    var orig = btn.textContent;
    btn.textContent = 'buscando…';
    var i0 = ORDER.indexOf(CUR);
    var seq = [];
    for(var k = 1; k <= ORDER.length; k++){
      seq.push(ORDER[(i0 + k) % ORDER.length]);
    }
    (function step(idx){
      if(idx >= seq.length){
        btn.textContent = 'nenhum pendente';
        setTimeout(function(){ btn.textContent = orig; btn.disabled = false; }, 1600);
        return;
      }
      var name = seq[idx];
      fetch('/api/notes/' + encodeURIComponent(name))
        .then(function(r){ return r.json(); })
        .then(function(data){
          if(isPending((data || {}).notes)){
            location.href = name + '.html';
          } else {
            step(idx + 1);
          }
        })
        .catch(function(){ step(idx + 1); });
    })(0);
  });
})();
</script>
"""


def patch_file(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    name = path.stem
    if name not in ORDER:
        return False
    if MARK in html:
        return False  # já patcheado

    if "</style>" in html:
        html = html.replace("</style>", CSS + "\n</style>", 1)

    m = re.search(r'(<div class="nav-bar">.*?</div>)', html, flags=re.S)
    if not m:
        return False
    btn_html = (
        '<button type="button" id="nav-next-invalid" class="nav-next-invalid-btn">'
        "⚠ Próximo pendente ▶</button>"
    )
    new_nav = m.group(1)[:-6] + btn_html + "</div>"  # antes do </div> final
    html = html.replace(m.group(1), new_nav, 1)

    import json as _json
    js = JS_TMPL.replace("__ORDER__", _json.dumps(ORDER)).replace("__CUR__", _json.dumps(name))
    html = html.replace("</body>", js + "\n</body>", 1)

    path.write_text(html, encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: pil_patch_next_invalid_btn.py <pack_dir>")
        return 2
    pack = Path(sys.argv[1])
    pil = pack / "pilares"
    n = 0
    for f in sorted(pil.glob("P*.html")):
        if patch_file(f):
            n += 1
    print(f"[OK] {n} fichas patcheadas em {pil}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
