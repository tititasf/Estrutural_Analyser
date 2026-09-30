#!/usr/bin/env python
"""Exporta fichas HTML de pilares com tabelas ABCD a partir do DB (sem Qt).

Uso:
  py -3.12 scripts/arete/export_pilares_abcd_fichas.py \\
    --project-id dd238e47-1dc6-4f63-a760-4e7ce19a7386 \\
    --obra Obra_TREINO_1 --pav 13_PAV --open
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sqlite3
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.pillar_abcd_tables import (  # noqa: E402
    build_abcd_tables_from_pillar,
    format_abcd_tables_html,
)
from src.core.niveis_extractor import get_pavimento_niveis_abs  # noqa: E402
from src.core.pil_qa_notes_chrome import (  # noqa: E402
    css_pil_qa,
    js_pil_qa,
    n1_layer_toggle_and_layers,
    notes_grid_html,
    notes_store_tag,
    wrap_n1_panzoom,
)

OUT_BASE = Path(__file__).resolve().parent / "html_fichas"


def _render_n1_svg(
    dxf_path: Path,
    pillar_pts: list,
    *,
    context_view: str = "near",
    width: int = 900,
    height: int = 640,
) -> str:
    """N1 próximo/contexto a partir do DXF do pavimento (sem Qt)."""
    if not dxf_path.is_file() or not pillar_pts:
        return ""
    try:
        import ezdxf
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        from matplotlib.patches import Polygon as MplPolygon
        from src.ui.widgets.svg_embed_utils import strip_fixed_size

        xs = [float(p[0]) for p in pillar_pts]
        ys = [float(p[1]) for p in pillar_pts]
        pw, ph = max(xs) - min(xs), max(ys) - min(ys)
        if context_view == "far":
            margin = max(max(pw, ph) * 10.0 + 320.0, (max(pw, ph) * 3.0 + 60) * 3.6)
        else:
            margin = (max(pw, ph) * 3.0 + 60) * 1.3
        vx0, vx1 = min(xs) - margin, max(xs) + margin
        vy0, vy1 = min(ys) - margin, max(ys) + margin

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        dpi = 140
        with matplotlib.rc_context({"svg.fonttype": "none", "path.simplify": False}):
            fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set_facecolor("#0d0d0d")
            fig.patch.set_facecolor("#0d0d0d")
            ctx = RenderContext(doc)
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(msp)
            # Destaque do pilar (N1 próximo e contexto): vermelho forte +
            # contorno fino, fill translúcido — legível no fundo escuro do DXF.
            poly = list(zip(xs, ys))
            if len(poly) >= 3:
                ax.add_patch(
                    MplPolygon(
                        poly,
                        closed=True,
                        facecolor="#ff1744",
                        edgecolor="none",
                        alpha=0.38,
                        zorder=40,
                    )
                )
                ax.add_patch(
                    MplPolygon(
                        poly,
                        closed=True,
                        fill=False,
                        edgecolor="#ff1744",
                        linewidth=1.15,
                        alpha=1.0,
                        zorder=41,
                    )
                )
                # halo externo fino (contraste sobre traços do DXF)
                ax.add_patch(
                    MplPolygon(
                        poly,
                        closed=True,
                        fill=False,
                        edgecolor="#ff8a80",
                        linewidth=0.55,
                        alpha=0.85,
                        zorder=42,
                        linestyle="-",
                    )
                )
            ax.set_xlim(vx0, vx1)
            ax.set_ylim(vy0, vy1)
            ax.set_aspect("equal")
            ax.axis("off")
            import io

            buf = io.BytesIO()
            fig.savefig(buf, format="svg", dpi=dpi, facecolor="#0d0d0d", bbox_inches="tight")
            plt.close(fig)
        buf.seek(0)
        return strip_fixed_size(buf.read().decode("utf-8"))
    except Exception as exc:
        print(f"[N1] render falhou ({context_view}): {exc}", flush=True)
        return f'<p class="muted">N1 {context_view} indisponível ({html_mod.escape(str(exc))})</p>'


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


def _page_css() -> str:
    return """
body{background:#111;color:#d0d0d0;font:13px/1.45 Consolas,monospace;margin:0;padding:16px}
h2{color:#7eb8f7;font-size:18px;margin:0 0 10px}
.tag{display:inline-block;background:#282828;color:#999;font-size:11px;padding:2px 7px;border-radius:3px;margin-left:6px}
.sec{margin:12px 0;border:1px solid #2a2a2a;border-radius:4px}
.sec-title{background:#1e1e1e;color:#4fc3a1;padding:6px 10px;font-size:13px;font-weight:bold}
.sec-body{padding:10px}
.muted{color:#666}
.nav-bar{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 14px}
.nav-bar a{color:#7eb8f7;text-decoration:none;border:1px solid #335;padding:4px 10px;border-radius:3px;font-size:12px}
table.meta td{padding:4px 10px;border-bottom:1px solid #222;font-size:13px}
table.meta td:first-child{color:#888;width:150px}
"""


def build_pillar_page(
    name: str,
    classif: str,
    tables: dict,
    *,
    obra: str,
    pav: str,
    niveis: dict,
    idx: int,
    total: int,
    nav_links: str,
    n1_near: str = "",
    n1_near_plain: str = "",
    n1_far: str = "",
    l1_svg: str = "",
    l2_svg: str = "",
    l3_svg: str = "",
) -> str:
    tables_html = format_abcd_tables_html(tables, compact=True)
    cheg = niveis.get("chegada_abs")
    saida = niveis.get("saida_abs")
    alt = niveis.get("altura_cm")
    n1_block = ""
    if n1_near or n1_near_plain or n1_far:
        # Padrão de uso: embutir SA plain + SA tags + L1 (zoom imediato).
        # L2/L3 só sob demanda (fetch) — 5 SVGs embutidos (~15MB) trava o browser.
        near_layers = n1_layer_toggle_and_layers(
            sa_svg=n1_near or "",
            sa_plain_svg=n1_near_plain or "",
            l1_svg=l1_svg or "",
            l2_svg="",  # fetch L2
            l3_svg="",  # fetch L3
            item=name,
            sa_plain_src=f"../propostas/{name}_sa_plain.svg",
            sa_tags_src=f"../propostas/{name}_sa_motor.svg",
            l1_src=f"../propostas/{name}_qa_L1.svg",
            l2_src=f"../propostas/{name}_qa_L2.svg",
            l3_src=f"../propostas/{name}_qa_L3.svg",
            proposal_src=f"../propostas/{name}_qa_proposta.svg",
            viewer_id=f"pil-n1-near-{name}",
        )
        far_viewer = wrap_n1_panzoom(
            n1_far or '<p class="muted">indisponível</p>',
            viewer_id=f"pil-n1-far-{name}",
        )
        n1_block = f"""
<div class="sec"><div class="sec-title">Foto N1 — SA + camadas</div>
<div class="sec-body">
<div class="n1-tabs" role="tablist">
  <button type="button" class="n1-tab active" data-n1tab="near" role="tab" aria-selected="true">N1 próximo</button>
  <button type="button" class="n1-tab" data-n1tab="far" role="tab" aria-selected="false">N1 distante</button>
</div>
<div class="n1-panel active" data-n1panel="near" role="tabpanel">
  {near_layers}
</div>
<div class="n1-panel" data-n1panel="far" role="tabpanel" hidden>
  {far_viewer}
</div>
</div></div>"""
    notes_block = notes_grid_html(obra, pav, name)
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>{html_mod.escape(name)} — Interpretação ABCD</title>
<style>{_page_css()}
{css_pil_qa()}
.n1-tabs{{display:flex;gap:0;margin:0 0 8px;border-bottom:1px solid #333}}
.n1-tab{{background:transparent;border:1px solid transparent;border-bottom:none;color:#888;
  padding:6px 12px;font:12px/1 Consolas,monospace;cursor:pointer;border-radius:4px 4px 0 0;margin-bottom:-1px}}
.n1-tab:hover{{color:#ccc;background:#1a1a1a}}
.n1-tab.active{{color:#7eb8f7;background:#151515;border-color:#333;border-bottom-color:#151515;font-weight:bold}}
.n1-panel{{display:none}}
.n1-panel.active{{display:block}}
.n1-svg{{background:#0d0d0d;border:1px solid #222;border-radius:3px;padding:4px;overflow:auto}}
.n1-svg svg{{display:block;width:100%;height:auto;max-height:none}}
</style>
<script>
document.addEventListener('DOMContentLoaded',function(){{
  var tabs=document.querySelectorAll('.n1-tab');
  if(!tabs.length) return;
  tabs.forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var id=btn.getAttribute('data-n1tab');
      tabs.forEach(function(b){{
        var on=b===btn;
        b.classList.toggle('active',on);
        b.setAttribute('aria-selected',on?'true':'false');
      }});
      document.querySelectorAll('.n1-panel').forEach(function(p){{
        var on=p.getAttribute('data-n1panel')===id;
        p.classList.toggle('active',on);
        if(on) p.removeAttribute('hidden'); else p.setAttribute('hidden','');
      }});
    }});
  }});
}});
</script>
{js_pil_qa()}
</head><body>
{notes_store_tag()}
<h2>{html_mod.escape(name)}<span class="tag">{html_mod.escape(classif or '—')}</span>
<span class="tag">{idx}/{total}</span></h2>
<div class="nav-bar">{nav_links}</div>
<div class="sec"><div class="sec-title">Identidade</div><div class="sec-body">
<table class="meta">
<tr><td>Obra / Pav</td><td>{html_mod.escape(obra)} / {html_mod.escape(pav)}</td></tr>
<tr><td>Nível saída</td><td><b>{saida}cm</b></td></tr>
<tr><td>Nível chegada</td><td><b>{cheg}cm</b></td></tr>
<tr><td>Pé-direito</td><td><b>{alt}cm</b></td></tr>
</table></div></div>
{notes_block}
{n1_block}
<div class="sec"><div class="sec-title">Interpretação ABCD — tabelas por face</div>
<div class="sec-body">
<div style="font-size:12px;color:#888;margin-bottom:6px">
Família · nome · dim · nível · canto · <b>d.esq</b>/<b>d.dir</b>
(dist. dos cantos esq/dir da face; passantes = —; lajes/chegam/interior quando houver geometria)</div>
{tables_html}
</div></div>
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--skip-n1", action="store_true", help="Não renderiza SVGs N1 (mais rápido)")
    ap.add_argument("--item", nargs="*", help="Só estes pilares (ex: P2 P1)")
    ap.add_argument(
        "--with-agentic",
        action="store_true",
        help=(
            "LEGADO: no-op — SA+tags e camadas L1/L2/L3 já são SEMPRE geradas "
            "(espelho FV V303). Mantido só por compat de scripts antigos."
        ),
    )
    ap.add_argument(
        "--no-layers",
        action="store_true",
        help="Só N1 SA com tags (sem gravar L1/L2/L3 em propostas/) — raríssimo",
    )
    args = ap.parse_args()

    db = Path(args.db)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    # DXF do projeto
    dxf_path = None
    prow = conn.execute(
        "SELECT dxf_path FROM projects WHERE id=?", (args.project_id,)
    ).fetchone()
    if prow and prow["dxf_path"]:
        dxf_path = Path(prow["dxf_path"])

    niveis = get_pavimento_niveis_abs(args.obra, args.pav) or {
        "chegada_abs": 852.19,
        "saida_abs": 848.98,
        "altura_cm": 321.0,
    }
    # slabs maps + geometria
    slab_h, slab_n, slab_pts = {}, {}, {}
    for r in conn.execute(
        "SELECT name, points_json, extra_data_json FROM slabs WHERE project_id=?",
        (args.project_id,),
    ):
        ex = json.loads(r["extra_data_json"] or "{}") if r["extra_data_json"] else {}
        fields = ex.get("fields") if isinstance(ex.get("fields"), dict) else {}
        h = fields.get("laje_dim") or ex.get("laje_dim") or ""
        h = str(h).replace("h=", "").replace("cm", "").strip()
        n = fields.get("laje_nivel") or ex.get("laje_nivel") or ""
        slab_h[r["name"]] = h
        slab_n[r["name"]] = str(n)
        try:
            slab_pts[r["name"]] = json.loads(r["points_json"] or "[]")
        except Exception:
            slab_pts[r["name"]] = []

    beams = []
    for r in conn.execute(
        "SELECT name, data_json FROM beams WHERE project_id=?",
        (args.project_id,),
    ):
        d = json.loads(r["data_json"] or "{}")
        d["name"] = r["name"]
        beams.append(d)

    pillars = []
    for r in conn.execute(
        "SELECT name, points_json, sides_data_json, extra_data_json, type "
        "FROM pillars WHERE project_id=? ORDER BY name",
        (args.project_id,),
    ):
        pts = json.loads(r["points_json"] or "[]")
        extra = json.loads(r["extra_data_json"] or "{}") if r["extra_data_json"] else {}
        if not isinstance(extra, dict):
            extra = {}
        classif = "INDETERMINADO"
        pillars.append(
            {
                "name": r["name"],
                "points": pts,
                "orientation": "",  # resolvido da geometria abaixo
                "lajes": extra.get("lajes_adjacentes") or [],
                "face_beams": extra.get("face_beams") or {},
                "classification": classif,
                "type": r["type"] if "type" in r.keys() else None,
            }
        )

    # sort natural
    pillars.sort(key=lambda p: _natural_key(p["name"]))
    if args.item:
        wanted = {str(x).strip().upper() for x in args.item}
        pillars = [p for p in pillars if str(p["name"]).strip().upper() in wanted]
        if not pillars:
            print(f"[ERR] nenhum pilar em --item {args.item}", flush=True)
            return 2
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_BASE / args.obra / f"{args.pav}_{ts}_pilares_abcd"
    pil_dir = out_dir / "pilares"
    pil_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "propostas").mkdir(parents=True, exist_ok=True)
    readme_prop = out_dir / "propostas" / "README.txt"
    if not readme_prop.is_file():
        readme_prop.write_text(
            "Destaques PIL — SA motor + looping 3 camadas (espelho FV V303).\n"
            "  {PILAR}_sa_plain.svg     — SA sem tags (N1 estrutural + marco)\n"
            "  {PILAR}_sa_motor.svg     — SA com tags (interpretação do motor)\n"
            "  {PILAR}_qa_L1.svg        — Camada 1 (julga SA)\n"
            "  {PILAR}_qa_L2.svg        — Camada 2 (julga L1, cega)\n"
            "  {PILAR}_qa_L3.svg        — Camada 3 (alvo pré-fix motor)\n"
            "  {PILAR}_qa_proposta.svg  — alias L1 (legado)\n"
            "  {PILAR}_qa_proposta.json — meta + faces\n"
            "Padrão tags: docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md\n"
            "Loop: docs/LOOPING-AGENTICO-INTERPRETACAO-PILARES-ABCD.md\n",
            encoding="utf-8",
        )

    estado_pilares = []
    pages = []
    for p in pillars:
        # orientation from geometry
        try:
            xs = [float(pt[0]) for pt in p["points"]]
            ys = [float(pt[1]) for pt in p["points"]]
            p["orientation"] = (
                "vertical" if (max(ys) - min(ys)) > (max(xs) - min(xs)) else "horizontal"
            )
        except Exception:
            pass
        tables = build_abcd_tables_from_pillar(
            p,
            slab_height_map=slab_h,
            slab_nivel_map=slab_n,
            slab_points_map=slab_pts,
            beams=beams,
            nivel_viga_default=f"{niveis.get('chegada_abs')}cm",
        )
        p["interpretacao_abcd"] = tables
        pages.append((p, tables))

    # nav + render (SA sempre com tags; L1/L2/L3 no mesmo paint)
    names = [p["name"] for p, _ in pages]
    print(
        f"[N1] DXF={'ok' if dxf_path and dxf_path.is_file() else 'ausente'} "
        f"skip={args.skip_n1} layers={'off' if args.no_layers else 'SA+L1/L2/L3'}",
        flush=True,
    )

    # carrega render_agentic_svg uma vez
    _render_tagged = None
    _process_item = None
    if not args.skip_n1 and dxf_path and dxf_path.is_file():
        import importlib.util

        _ag_path = Path(__file__).resolve().parent / "pil_agentic_highlight_draw.py"
        _spec = importlib.util.spec_from_file_location(
            "pil_agentic_highlight_draw", _ag_path
        )
        _mod = importlib.util.module_from_spec(_spec)
        assert _spec.loader is not None
        _spec.loader.exec_module(_mod)
        _render_tagged = _mod.render_agentic_svg
        _process_item = _mod.process_item

    nivel_v = f"{niveis.get('chegada_abs')}cm"
    for i, (p, tables) in enumerate(pages):
        nav = []
        if i > 0:
            nav.append(f'<a href="{names[i-1]}.html">◀ {names[i-1]}</a>')
        nav.append(f'<a href="index.html">Índice</a>')
        if i + 1 < len(names):
            nav.append(f'<a href="{names[i+1]}.html">{names[i+1]} ▶</a>')
        n1_near = n1_near_plain = n1_far = ""
        l1_svg = l2_svg = l3_svg = ""
        pts = p.get("points") or []
        if not args.skip_n1 and dxf_path and dxf_path.is_file():
            print(f"  N1+tags {p['name']} ({i+1}/{len(pages)})…", flush=True)
            # SA sem tags = N1 estrutural + marco vermelho (sempre)
            n1_near_plain = _render_n1_svg(dxf_path, pts, context_view="near")
            n1_far = _render_n1_svg(dxf_path, pts, context_view="far")
            prop = out_dir / "propostas"
            prop.mkdir(parents=True, exist_ok=True)
            (prop / f"{p['name']}_sa_plain.svg").write_text(
                n1_near_plain, encoding="utf-8"
            )

            def _read_svg(fn: str) -> str:
                fp = prop / fn
                if not fp.is_file():
                    return ""
                return re.sub(
                    r"<\?xml[^?]*\?>", "", fp.read_text(encoding="utf-8")
                ).strip()

            if not args.no_layers and _process_item:
                # process_item grava SA com tags + L1/L2/L3
                try:
                    r = _process_item(
                        p,
                        dxf_path=dxf_path,
                        slab_h=slab_h,
                        slab_n=slab_n,
                        slab_pts=slab_pts,
                        beams=beams,
                        nivel_v=nivel_v,
                        pack=out_dir,
                        obra=args.obra,
                        pav=args.pav,
                        layers=("sa", "l1", "l2", "l3"),
                    )
                    n1_near = _read_svg(f"{p['name']}_sa_motor.svg")
                    l1_svg = _read_svg(f"{p['name']}_qa_L1.svg")
                    l2_svg = _read_svg(f"{p['name']}_qa_L2.svg")
                    l3_svg = _read_svg(f"{p['name']}_qa_L3.svg")
                    print(f"    SA plain+tags + L1/L2/L3 · {r.get('verdict')}", flush=True)
                except Exception as exc:
                    print(f"    [WARN] process_item: {exc}", flush=True)
            if not n1_near and _render_tagged:
                n1_near = _render_tagged(dxf_path, pts, tables, layer="sa")
                (prop / f"{p['name']}_sa_motor.svg").write_text(
                    n1_near, encoding="utf-8"
                )
                if not args.no_layers:
                    for ly in ("l1", "l2", "l3"):
                        svg_ly = _render_tagged(dxf_path, pts, tables, layer=ly)
                        out_name = f"{p['name']}_qa_L{ly[-1]}.svg"
                        (prop / out_name).write_text(svg_ly, encoding="utf-8")
                        if ly == "l1":
                            l1_svg = svg_ly
                            (prop / f"{p['name']}_qa_proposta.svg").write_text(
                                svg_ly, encoding="utf-8"
                            )
                        elif ly == "l2":
                            l2_svg = svg_ly
                        else:
                            l3_svg = svg_ly
            if not n1_near:
                # sem tags fallback = plain
                n1_near = n1_near_plain
        html_page = build_pillar_page(
            p["name"],
            p.get("classification") or "—",
            tables,
            obra=args.obra,
            pav=args.pav,
            niveis=niveis,
            idx=i + 1,
            total=len(pages),
            nav_links="".join(nav),
            n1_near=n1_near,
            n1_near_plain=n1_near_plain,
            n1_far=n1_far,
            l1_svg=l1_svg,
            l2_svg=l2_svg,
            l3_svg=l3_svg,
        )
        (pil_dir / f"{p['name']}.html").write_text(html_page, encoding="utf-8")
        estado_pilares.append(
            {
                "key": p["name"],
                "name": p["name"],
                "classification": p.get("classification") or "INDETERMINADO",
                "orientation": p.get("orientation") or "vertical",
                "points": p.get("points") or [],
                "lajes": p.get("lajes") or [],
                "face_beams": p.get("face_beams") or {},
                "interpretacao_abcd": tables,
                "nivel_str": "",
                "lado_A": "",
                "lado_B": "",
                "lado_C": "",
                "lado_D": "",
                "atencao": "",
            }
        )

    # index
    links = "".join(
        f'<li><a href="pilares/{html_mod.escape(n)}.html">{html_mod.escape(n)}</a></li>'
        for n in names
    )
    index = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>Pilares ABCD — {html_mod.escape(args.obra)} / {html_mod.escape(args.pav)}</title>
<style>body{{background:#111;color:#ccc;font:13px sans-serif;padding:20px}}
a{{color:#7eb8f7}} li{{margin:4px 0}}</style></head><body>
<h2>Pilares — Interpretação ABCD</h2>
<p>{html_mod.escape(args.obra)} / {html_mod.escape(args.pav)} — {len(names)} itens — {ts}</p>
<ul>{links}</ul>
</body></html>"""
    (out_dir / "index.html").write_text(index, encoding="utf-8")

    # estado snapshot for portal
    estado = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "obra": args.obra,
        "pavimento": args.pav,
        "db_path": str(args.db),
        "project_id": args.project_id,
        "pilares": estado_pilares,
        "slabs": [
            {"name": n, "height": slab_h.get(n, ""), "nivel": slab_n.get(n, "")}
            for n in sorted(set(slab_h) | set(slab_n))
        ],
        "cortes": [],
        "segmentos": {},
    }
    estado_path = OUT_BASE / args.obra / f"estado_{args.pav}_pilares_abcd.json"
    estado_path.parent.mkdir(parents=True, exist_ok=True)
    estado_path.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] {len(pages)} fichas em {out_dir}")
    print(f"[OK] estado: {estado_path}")
    print(
        f"[OK] SA+tags + L1/L2/L3 → {out_dir / 'propostas'} "
        f"(padrão: docs/PADRAO-TAGS-DESTAQUE-AGENTICO-PIL.md · espelho FV V303)",
        flush=True,
    )
    if args.with_agentic:
        print("[INFO] --with-agentic é no-op (já embutido no export)", flush=True)

    p2 = out_dir / "pilares" / "P2.html"
    if p2.is_file():
        print(f"[OK] P2: {p2}")
        if args.open:
            webbrowser.open(p2.as_uri())
            webbrowser.open((out_dir / "index.html").as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
