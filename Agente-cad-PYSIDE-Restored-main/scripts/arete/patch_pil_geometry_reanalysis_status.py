#!/usr/bin/env python3
"""Marca visualmente fichas PIL cuja geometria-base foi reprovada.

O banner é deliberadamente só uma fila visual: não tenta corrigir tags e não
dispara processo algum no browser. O orquestrador QA lê o mesmo sinal antes de
avaliar L2/L3 e deve então executar o microciclo SA do item.
"""
from __future__ import annotations

import sys
from pathlib import Path


MARK = "<!-- pil-geometry-reanalysis-status -->"

CSS = """
.pil-geometry-reanalysis{margin:10px 0;padding:12px 14px;border:2px solid #ff7043;
 border-radius:8px;background:#2a100d;color:#ffe5dc;font:13px/1.4 system-ui,sans-serif}
.pil-geometry-reanalysis b{color:#ffab91}.pil-geometry-reanalysis code{color:#ffd180}
"""

JS = r"""
<script>
(function(){
  var item = (location.pathname.match(/\/pilares\/([^/]+)\.html$/)||[])[1];
  if(!item) return;
  function hasInvalidGeometry(notes){
    var values = Object.keys(notes||{}).map(function(k){ return String(notes[k]||''); });
    return values.some(function(v){
      if(/geometria vinculada errada|geometria inv[aá]lida/i.test(v)) return true;
      try { return JSON.parse(v).some(function(e){ return e && e.acao === 'geometria_invalida'; }); }
      catch(_){ return false; }
    });
  }
  fetch('/api/notes/'+encodeURIComponent(item), {cache:'no-store'})
    .then(function(r){ return r.ok ? r.json() : {}; })
    .then(function(doc){
      if(!hasInvalidGeometry(doc.notes)) return;
      var old=document.querySelector('.pil-geometry-reanalysis'); if(old) old.remove();
      var box=document.createElement('section'); box.className='pil-geometry-reanalysis';
      box.innerHTML='<b>⚠ Geometria-base reprovada</b><br>'+
        'Não interpretar ou validar tags/ABCD desta ficha nesta rodada. '+
        'O próximo QA deve <code>invalidar a geometria atual → rodar microciclo SA deste pilar → '+
        'avaliar a nova candidata</code>. A Camada 2/3 só volta após a geometria ser coerente.';
      var anchor=document.querySelector('.pil-agent-box, .sec, main, body');
      anchor.parentNode.insertBefore(box, anchor);
      document.body.classList.add('pil-geometry-reanalysis-pending');
    }).catch(function(){});
})();
</script>
"""


def patch_file(path: Path) -> bool:
    html = path.read_text(encoding="utf-8")
    if MARK in html:
        return False
    if "</style>" in html:
        html = html.replace("</style>", CSS + "\n</style>", 1)
    html = html.replace("</body>", JS + "\n" + MARK + "\n</body>", 1)
    path.write_text(html, encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print("uso: patch_pil_geometry_reanalysis_status.py <pack_dir>")
        return 2
    pack = Path(sys.argv[1])
    changed = sum(patch_file(path) for path in (pack / "pilares").glob("P*.html"))
    print(f"[OK] {changed} fichas receberam estado visual de reanálise de geometria")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
