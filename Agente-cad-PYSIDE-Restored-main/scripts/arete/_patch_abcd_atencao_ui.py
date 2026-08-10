"""Patch em fichas ABCD existentes: remove checklist + injeta campo Atenção.

Preserva N1/SVGs. Não re-renderiza.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.arete.export_pilares_abcd_fichas import (  # noqa: E402
    _js_atencao,
    _page_css,
)


ATENCAO_HTML = """
<div class="sec atencao-sec"><div class="sec-title">Atenção / correções</div>
<div class="sec-body">
<p class="atencao-hint">Escreva o que estiver <b>errado ou incompleto</b> nesta interpretação
(face, família, nome, dim, d.esq/d.dir, dualidade…). Salva ao digitar.
Com o servidor local ativo, grava em JSON no disco para o agente ler depois.</p>
<textarea id="atencao-text" class="atencao-ta" spellcheck="true"
  placeholder="Ex.: Face B — chega VF301 d.esq deveria ser 52 não 47; laje A falta L301…"></textarea>
<div class="atencao-bar">
  <span id="atencao-status" class="atencao-status">—</span>
</div>
</div></div>
"""


def patch_file(path: Path, obra: str, pav: str) -> bool:
    html = path.read_text(encoding="utf-8")
    name = path.stem
    # remove checklist section
    html2 = re.sub(
        r'<div class="sec"><div class="sec-title">Checklist de aprovação</div>.*?</div></div>\s*',
        "",
        html,
        count=1,
        flags=re.S,
    )
    # strip old checkbox JS
    html2 = re.sub(
        r"<script>\s*function toggleValidacao[\s\S]*?</script>",
        "",
        html2,
        count=1,
    )
    # inject CSS extras if missing
    if "atencao-ta" not in html2:
        extra_css = """
.atencao-sec .sec-title{color:#f0b840}
.atencao-hint{font-size:10px;color:#777;margin:0 0 8px;line-height:1.45}
.atencao-ta{width:100%;min-height:110px;box-sizing:border-box;background:#0d0d0d;color:#e8e8e8;
  border:1px solid #3a3520;border-radius:4px;padding:8px;font:12px/1.45 Consolas,monospace;resize:vertical}
.atencao-ta:focus{outline:none;border-color:#f0b840;box-shadow:0 0 0 1px #f0b84044}
.atencao-bar{display:flex;align-items:center;gap:10px;margin-top:6px;font-size:10px;color:#666}
.atencao-status{color:#888}
.atencao-status.ok{color:#4fc3a1}
.atencao-status.warn{color:#f0b840}
.atencao-status.err{color:#f07178}
"""
        html2 = html2.replace("</style>", extra_css + "\n</style>", 1)
    # inject JS
    js = _js_atencao(obra, pav, name)
    if "atencao-text" not in html2 or "abcd_atencao::" not in html2:
        # remove previous atencao js if any
        html2 = re.sub(
            r"<script>\s*\(function\(\)\{\s*var OBRA=[\s\S]*?</script>",
            "",
            html2,
        )
        html2 = html2.replace("</head>", js + "\n</head>", 1)
    # inject atencao block before </body>
    if 'id="atencao-text"' not in html2:
        html2 = html2.replace("</body>", ATENCAO_HTML + "\n</body>")
    else:
        # already has block; ensure checklist gone
        pass

    if html2 != html:
        path.write_text(html2, encoding="utf-8")
        return True
    return False


def main() -> int:
    pack = Path(
        r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
        r"\Obra_TREINO_1\13_PAV_20260730_210556_pilares_abcd"
    )
    if len(sys.argv) > 1:
        pack = Path(sys.argv[1])
    obra, pav = "Obra_TREINO_1", "13_PAV"
    pil = pack / "pilares"
    n = 0
    for f in sorted(pil.glob("P*.html")):
        if patch_file(f, obra, pav):
            n += 1
            print("patched", f.name)
        else:
            print("unchanged", f.name)
    # index note
    idx = pack / "index.html"
    if idx.is_file():
        t = idx.read_text(encoding="utf-8")
        if "serve_abcd_fichas" not in t:
            note = (
                "<p style='color:#f0b840;font-size:12px'>Para gravar <b>Atenção</b> no disco "
                "(agente lê depois), abra via:<br>"
                "<code>py -3.12 scripts/arete/serve_abcd_fichas.py --dir \""
                + str(pack).replace("\\", "/")
                + "\" --open</code></p>"
            )
            t = t.replace("</body>", note + "\n</body>")
            idx.write_text(t, encoding="utf-8")
            print("patched index")
    print(f"[OK] {n} fichas em {pack}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
