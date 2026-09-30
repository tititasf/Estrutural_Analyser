from pathlib import Path

pack = Path(
    r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\html_fichas"
    r"\Obra_TREINO_1\TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20"
    r"\fundos_viga"
)
pages = sorted(pack.glob("V*.html"))
print("pages", len(pages))
bad = []
for page in pages:
    t = page.read_text(encoding="utf-8")
    if "<!--FVCTX_START-->" not in t:
        bad.append((page.name, "no ctx"))
        continue
    ctx = t.split("<!--FVCTX_START-->", 1)[1].split("<!--FVCTX_END-->", 1)[0]
    checks = {
        "title": "Viewer Unificado N1-N3" in ctx,
        "table": "Interpretação dos segmentos" in ctx,
        "todos": 'data-seg="todos"' in ctx,
        "no_doctype": "<!DOCTYPE svg" not in ctx,
        "notes_after": ctx.find("data-panzoom") < ctx.find('class="fv-ctx-notes"'),
        "n3_layer": "fv-layer-n3" in ctx,
        "summary": "Quantidade de segmentos" in ctx,
    }
    n3_has_svg = "<svg" in ctx[ctx.find("fv-layer-n3") : ctx.find("fv-layer-n3") + 5000] if "fv-layer-n3" in ctx else False
    if not all(checks.values()):
        bad.append((page.name, {k: v for k, v in checks.items() if not v}, "n3svg", n3_has_svg))
    if page.name in ("V301.html", "V305.html", "V313.html"):
        n3i = ctx.find("fv-layer-n3")
        print(page.name, checks, "n3svg_near", "<svg" in ctx[n3i:n3i+800] if n3i>=0 else None)
        print("  n3 snippet", repr(ctx[n3i:n3i+180]))
        print("  notes after pan", checks["notes_after"])

print("bad", len(bad))
for item in bad[:8]:
    print(" ", item)
