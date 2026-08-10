#!/usr/bin/env python
"""Injeta APONTAMENTOS ESTRUTURADOS dentro de cada caixa agêntica (L1/L2/L3).

Correção de rumo (2026-08-07, pedido humano): a 1ª versão punha o formulário no
lado humano — mas o humano não vai preencher formulário, e não deve ser requisito
dele. Quem preenche é o **agente QA de cada camada**: ao registrar seu veredito,
ele deixa o apontamento estruturado (face/canto/papel/ação), e a camada seguinte
usa isso como INSTRUÇÃO DE DESENHO em vez de reinterpretar português.

Chaves: ``aten_pil_struct_l1|l2|l3_{obra}_{pav}_{item}`` (JSON array).
Plugga no autosave do chrome via ``<textarea hidden data-atkey>`` — não altera
``src/core/pil_qa_notes_chrome.py`` (core compartilhado).

Uso:
  py -3.12 scripts/arete/_patch_abcd_struct_atencao.py <pack_dir> [obra] [pav]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MARK = "pil-struct-agentic-v2"

ACOES = [
    ("", "— escolha a ação —"),
    ("falta", "FALTA — elemento ausente"),
    ("sobra", "SOBRA — não deveria estar"),
    ("papel_errado", "PAPEL ERRADO — é passa/chega/interior diferente"),
    ("identidade_errada", "IDENTIDADE ERRADA — nome da viga é outro"),
    ("dim_errada", "DIMENSÃO ERRADA"),
    ("canto_errado", "CANTO ERRADO"),
    ("duplicado", "DUPLICADO"),
    ("geometria_invalida", "GEOMETRIA INVÁLIDA — vínculo do pilar (vai p/ blocklist)"),
    ("pilar_especial", "PILAR ESPECIAL — precisa mais faces (L: A–F)"),
    ("desenho", "DESENHO — tag sobreposta / ponto fora do lugar"),
]
FACES = ["", "A", "B", "C", "D", "E", "F"]
CANTOS = ["", "AC", "AD", "BC", "BD", "CA", "CB", "DA", "DB", "AA", "BB", "CC", "DD"]
PAPEIS = ["", "laje", "passa", "chega", "interior"]

CSS = """
.pil-struct-block{margin:8px 0 2px;padding:7px;border:1px dashed #3a4b5c;border-radius:6px;background:#0b1016}
.pil-struct-head{font:10px Consolas,monospace;color:#7a8a99;margin-bottom:5px}
.pil-struct-head b{color:#9ecbff}
.pil-struct-row{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin-bottom:4px}
.pil-struct-row select,.pil-struct-row input{background:#0d0d0d;color:#e8e8e8;border:1px solid #33465a;
  border-radius:3px;padding:2px 4px;font:10px Consolas,monospace}
.pil-struct-row select[data-f='acao']{min-width:17em}
.pil-struct-row input[data-f='nome']{width:6em}
.pil-struct-row input[data-f='obs']{flex:1;min-width:8em}
.pil-struct-lbl{color:#5d6d7c;font:9px Consolas,monospace}
.pil-struct-del{background:#2a1010;color:#ef9a9a;border:1px solid #6a2525;border-radius:3px;
  cursor:pointer;padding:2px 6px;font:10px Consolas,monospace}
.pil-struct-add{background:#0d1f0f;color:#a5d6a7;border:1px solid #2e7d32;border-radius:3px;
  cursor:pointer;padding:3px 9px;font:10px Consolas,monospace}
.pil-struct-add:hover{border-color:#66bb6a}
.pil-struct-empty{color:#55636f;font:10px Consolas,monospace;padding:2px 0}
"""

JS = """
<script>
(function(){
  var ACOES = __ACOES__, FACES = __FACES__, CANTOS = __CANTOS__, PAPEIS = __PAPEIS__;
  function opts(arr, val){
    return arr.map(function(o){
      var v = (o instanceof Array) ? o[0] : o, t = (o instanceof Array) ? o[1] : (o || '—');
      return '<option value="'+v+'"'+(String(v)===String(val)?' selected':'')+'>'+t+'</option>';
    }).join('');
  }
  function rowHtml(e){
    return '<div class="pil-struct-row">'
      + '<select data-f="acao">'+opts(ACOES, e.acao)+'</select>'
      + '<span class="pil-struct-lbl">face</span><select data-f="face">'+opts(FACES, e.face)+'</select>'
      + '<span class="pil-struct-lbl">canto</span><select data-f="canto">'+opts(CANTOS, e.canto)+'</select>'
      + '<span class="pil-struct-lbl">papel</span><select data-f="papel">'+opts(PAPEIS, e.papel)+'</select>'
      + '<input data-f="nome" placeholder="viga" value="'+(e.nome||'')+'">'
      + '<input data-f="obs" placeholder="obs / evidência" value="'+String(e.obs||'').replace(/"/g,'&quot;')+'">'
      + '<button type="button" class="pil-struct-del">x</button></div>';
  }
  function ctl(block){
    return {
      hidden: block.querySelector('.pil-struct-hidden'),
      list:   block.querySelector('.pil-struct-list')
    };
  }
  function read(h){ try { return JSON.parse(h.value||'[]')||[]; } catch(e){ return []; } }
  function render(block){
    var c = ctl(block), entries = read(c.hidden);
    c.list.innerHTML = entries.length
      ? entries.map(rowHtml).join('')
      : '<div class="pil-struct-empty">sem apontamento estruturado nesta camada</div>';
  }
  function collect(block){
    var out = [];
    ctl(block).list.querySelectorAll('.pil-struct-row').forEach(function(r){
      var e = {};
      r.querySelectorAll('[data-f]').forEach(function(el){ e[el.dataset.f]=el.value||''; });
      if (e.acao) out.push(e);
    });
    return out;
  }
  function write(block){
    var c = ctl(block), entries = collect(block);
    c.hidden.value = entries.length ? JSON.stringify(entries) : '';
    if (window.persistAllNotes) window.persistAllNotes(true);
  }
  document.querySelectorAll('.pil-struct-block').forEach(function(block){
    var c = ctl(block);
    render(block);
    block.addEventListener('change', function(ev){ if(ev.target.closest('.pil-struct-row')) write(block); });
    block.addEventListener('input',  function(ev){ if(ev.target.closest('.pil-struct-row')) write(block); });
    block.addEventListener('click', function(ev){
      if (ev.target.classList.contains('pil-struct-del')){
        ev.target.closest('.pil-struct-row').remove(); write(block);
      } else if (ev.target.classList.contains('pil-struct-add')){
        var e = collect(block); e.push({acao:'',face:'',canto:'',papel:'',nome:'',obs:''});
        c.hidden.value = JSON.stringify(e); render(block);
      }
    });
    var last = c.hidden.value;
    setInterval(function(){
      if (c.hidden.value === last) return;
      last = c.hidden.value;
      if (!block.contains(document.activeElement)) render(block);
    }, 800);
  });
})();
</script>
"""

BLOCK = """<div class="pil-struct-block" data-layer="__N__">
<div class="pil-struct-head">&#9881; Apontamentos estruturados — <b>Camada __N__</b>
(preenchidos pelo agente QA; viram instrução de desenho para a camada seguinte)</div>
<div class="pil-struct-list"></div>
<button type="button" class="pil-struct-add">+ apontamento</button>
<textarea class="pil-struct-hidden" data-atkey="__KEY__" style="display:none"></textarea>
</div>"""


def patch_file(path: Path, obra: str, pav: str) -> bool:
    html = path.read_text(encoding="utf-8")
    name = path.stem

    # remove a v1 (formulário do lado humano) e seu JS/CSS
    html = re.sub(r'<div class="sec pil-struct-sec">[\s\S]*?</div>\s*(?=<)', "", html, count=1)
    html = re.sub(r'<script>\s*\(function\(\)\{\s*var KEY = "aten_pil_struct_[\s\S]*?</script>\s*', "", html)
    html = html.replace("<!-- pil-struct-atencao -->", "")

    if MARK in html:
        return False

    if "pil-struct-block" not in html:
        if "</style>" in html:
            html = html.replace("</style>", CSS + "\n</style>", 1)
        # injeta um bloco dentro de cada caixa agêntica, logo após a textarea da camada
        def _inject(m):
            box = m.group(0)
            ta = re.search(r'<textarea class="pil-ta-agent"[\s\S]*?</textarea>', box)
            lay = re.search(r'data-layer="(\d)"', box)
            if not ta or not lay:
                return box
            n = lay.group(1)
            key = f"aten_pil_struct_l{n}_{obra}_{pav}_{name}".replace(" ", "_")
            blk = BLOCK.replace("__N__", n).replace("__KEY__", key)
            return box.replace(ta.group(0), ta.group(0) + blk, 1)

        html = re.sub(r'<div class="pil-agent-box"[\s\S]*?</textarea>\s*</div>', _inject, html)

    js = (JS.replace("__ACOES__", json.dumps(ACOES, ensure_ascii=False))
            .replace("__FACES__", json.dumps(FACES))
            .replace("__CANTOS__", json.dumps(CANTOS))
            .replace("__PAPEIS__", json.dumps(PAPEIS)))
    html = html.replace("</body>", js + f"\n<!-- {MARK} -->\n</body>", 1)
    path.write_text(html, encoding="utf-8")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: _patch_abcd_struct_atencao.py <pack_dir> [obra] [pav]")
        return 2
    pack = Path(sys.argv[1])
    obra = sys.argv[2] if len(sys.argv) > 2 else "Obra_TREINO_1"
    pav = sys.argv[3] if len(sys.argv) > 3 else "13_PAV"
    n = 0
    for f in sorted((pack / "pilares").glob("P*.html")):
        if patch_file(f, obra, pav):
            n += 1
    print(f"[OK] {n} fichas com apontamentos estruturados por camada (L1/L2/L3)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
