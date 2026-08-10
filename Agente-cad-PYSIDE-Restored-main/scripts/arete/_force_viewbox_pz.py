from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.core.pil_qa_notes_chrome import css_pil_qa, js_pil_qa  # noqa: E402

pack = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete"
    r"\html_fichas\Obra_TREINO_1\13_PAV_20260730_210556_pilares_abcd\pilares"
)
css = css_pil_qa()
js = js_pil_qa()
n = 0
for f in sorted(pack.glob("P*.html")):
    t = f.read_text(encoding="utf-8")
    t2 = t.replace("transform-origin:0 0;will-change:transform", "")
    # force latest JS
    t2, njs = re.subn(
        r'<script id="pil-qa-notes">[\s\S]*?</script>',
        js,
        t2,
        count=1,
    )
    # inject CSS marker if missing
    if "viewBox (igual FV)" not in t2 and "mesma tech do FV" not in t2:
        # JS has the comment; for CSS inject absolute layer rule
        pass
    # replace previous v2 css or inject
    marker = "/* pil-qa-css-v2-viewbox */"
    block = marker + "\n" + css
    if marker in t2:
        t2 = re.sub(
            r"/\* pil-qa-css-v2-viewbox \*/[\s\S]*?(?=</style>)",
            block + "\n",
            t2,
            count=1,
        )
    else:
        t2 = t2.replace("</style>", block + "\n</style>", 1)
    if t2 != t:
        f.write_text(t2, encoding="utf-8")
        n += 1
        print("ok", f.name, "js", njs)
    else:
        print("same", f.name)
print("updated", n)
