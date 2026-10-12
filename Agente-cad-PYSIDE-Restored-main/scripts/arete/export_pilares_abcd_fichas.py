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
import time
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
from src.core.number_presentation import display_level, display_number  # noqa: E402
from src.core.pil_qa_notes_chrome import (  # noqa: E402
    css_pil_qa,
    js_pil_qa,
    n1_layer_toggle_and_layers,
    notes_grid_html,
    notes_store_tag,
    wrap_n1_panzoom,
)

OUT_BASE = Path(__file__).resolve().parent / "html_fichas"


def _absolute_level(value):
    """Convention levels are metres; missing evidence stays unknown."""
    return f"{display_level(value)} m" if value is not None and value != "" else ""


def _published_pillars(db_pillars, snapshot_path):
    """Use the published SA geometry after a read-only analysis, without changing DB."""
    if snapshot_path is None:
        return db_pillars
    state = json.loads(Path(snapshot_path).read_text(encoding='utf-8'))
    rows = state.get('pilares')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Published SA snapshot has no pillar inventory')
    by_name = {row['name']: row for row in db_pillars}
    result, seen = [], set()
    for row in rows:
        name = row.get('name') if isinstance(row, dict) else None
        if not name or name in seen:
            raise ValueError('Published SA snapshot has an invalid or duplicate pillar name')
        seen.add(name)
        points = row.get('points') or []
        if len(points) < 3:
            raise ValueError(f'Published SA geometry missing: {name}')
        result.append(dict(by_name.get(name, {}), **row))
    return result


def _write_publication_text(path, text):
    """Keep room for portal logs and never expose a half-written asset."""
    import os
    import shutil
    import tempfile
    path = Path(path)
    required = sum(len(text[i:i+1024**2].encode('utf-8'))
                   for i in range(0, len(text), 1024**2))
    free = shutil.disk_usage(path.parent).free
    if free < required + 128*1024**2:
        raise RuntimeError(f'Sem espaço para publicar {path.name}: '
                           f'necessário {required} bytes + reserva; disponível {free}')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                        dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _render_tag_worker(payload: tuple[str, str, list, dict]) -> tuple[str, str]:
    """Worker isolado: matplotlib/ezdxf não compartilham estado entre pilares."""
    name, dxf_path, points, tables = payload
    from scripts.arete.pil_agentic_highlight_draw import render_agentic_svg

    return name, render_agentic_svg(Path(dxf_path), points, tables, layer="sa")


def _render_full_worker(payload):
    """Preserve all three views, using the same renderers in one isolated process."""
    name, dxf_path, points, tables = payload
    started = time.perf_counter()
    near = _render_n1_svg(Path(dxf_path), points, context_view='near')
    near_done = time.perf_counter()
    far = _render_n1_svg(Path(dxf_path), points, context_view='far')
    far_done = time.perf_counter()
    _, tagged = _render_tag_worker(payload)
    print(f"[PERF] render {name}: near={near_done-started:.3f}s "
          f"far={far_done-near_done:.3f}s tags={time.perf_counter()-far_done:.3f}s", flush=True)
    return name, tagged, near, far


def _write_spooled_svg(directory, svg):
    """IPC carries a path, never a full structural SVG for every future."""
    import gzip
    import uuid
    target = Path(directory) / (uuid.uuid4().hex + '.svg.gz')
    with gzip.open(target, 'wt', encoding='utf-8', compresslevel=1) as stream:
        stream.write(svg)
    return str(target)


def _read_spooled_svg(path):
    import gzip
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        svg = stream.read()
    Path(path).unlink()
    return svg


def _render_spooled_worker(task):
    payload, directory, full = task
    name, dxf_path, points, _ = payload
    paths = []
    # Release each view before rendering the next, retaining every SVG stroke.
    if full:
        for view in ('near', 'far'):
            paths.append(_write_spooled_svg(directory, _render_n1_svg(
                Path(dxf_path), points, context_view=view)))
    _, tagged = _render_tag_worker(payload)
    return name, _write_spooled_svg(directory, tagged), *paths


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
        from src.core.pillar_special_faces import special_physical_face_segments
        physical_l = bool(special_physical_face_segments(pillar_pts))
        if context_view == "far":
            margin = max(max(pw, ph) * 10.0 + 320.0, (max(pw, ph) * 3.0 + 60) * 3.6)
        else:
            margin = (max(pw, ph) * 3.0 + 60) * 1.3
            if physical_l:
                margin = (max(pw, ph) * 0.7 + 60) * 1.3
        vx0, vx1 = min(xs) - margin, max(xs) + margin
        vy0, vy1 = min(ys) - margin, max(ys) + margin

        dpi = 140
        with matplotlib.rc_context({"svg.fonttype": "none", "path.simplify": False}):
            from src.core.cad_render_cache import prepared_cad_canvas
            with prepared_cad_canvas(dxf_path, width, height, dpi) as (fig, ax):
                if physical_l:
                    fig.set_size_inches(width / dpi, height / dpi, forward=True)
                    ax.set_position([0, 0, 1, 1])
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
                if physical_l:
                    ax.set_aspect("equal", adjustable="box")
                else:
                    ax.set_aspect("equal")
                ax.axis("off")
                import io

                buf = io.BytesIO()
                from src.core.cad_render_cache import visible_cad_strokes
                with visible_cad_strokes(ax):
                    fig.savefig(buf, format="svg", dpi=dpi, facecolor="#0d0d0d", bbox_inches="tight")
        buf.seek(0)
        svg = buf.read()
        # Preserve individual paint operations: merging overlapping paths changes
        # antialiasing. Only discard redundant containers in the plain views.
        try:
            from portal.app.svg_compact import compact_svg_structure, compact_svg_serialization
            svg = compact_svg_serialization(compact_svg_structure(svg))
        except Exception as exc:
            print(f"[N1] compactação estrutural ignorada ({context_view}): {exc}", flush=True)
        return strip_fixed_size(svg.decode("utf-8"))
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
    n1_far_src: str = "",
) -> str:
    tables_html = format_abcd_tables_html(tables, compact=True)
    cheg = _absolute_level(niveis.get("chegada_abs")) or "—"
    saida = _absolute_level(niveis.get("saida_abs")) or "—"
    alt_value = niveis.get("altura_cm")
    alt = f"{display_number(alt_value)} cm" if alt_value is not None else "—"
    n1_block = ""
    if n1_near or n1_near_plain or n1_far:
        # All views use their published SVG asset; do not duplicate the active
        # tagged drawing inside each HTML page. Existing loader fetches it once.
        near_layers = n1_layer_toggle_and_layers(
            sa_svg="",
            sa_plain_svg="",
            l1_svg="",
            l2_svg="",  # fetch L2
            l3_svg="",  # fetch L3
            item=name,
            sa_plain_src=f"../propostas/{name}_sa_plain.svg",
            sa_tags_src=f"../propostas/{name}_sa_plain.svg" if n1_near_plain and n1_near == n1_near_plain else f"../propostas/{name}_sa_motor.svg",
            l1_src=f"../propostas/{name}_qa_L1.svg",
            l2_src=f"../propostas/{name}_qa_L2.svg",
            l3_src=f"../propostas/{name}_qa_L3.svg",
            proposal_src=f"../propostas/{name}_qa_proposta.svg",
            viewer_id=f"pil-n1-near-{name}",
        )
        far_viewer = wrap_n1_panzoom(
            n1_far or '<p class="muted">indisponível</p>',
            viewer_id=f"pil-n1-far-{name}",
            svg_src=n1_far_src,
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
        if(on && window.loadPilView) window.loadPilView(p);
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
<tr><td>Nível saída</td><td><b>{saida}</b></td></tr>
<tr><td>Nível chegada</td><td><b>{cheg}</b></td></tr>
<tr><td>Pé-direito</td><td><b>{alt}</b></td></tr>
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
    ap.add_argument("--snapshot-path", type=Path,
                    help="Published SA inventory; authoritative for read-only portal analyses.")
    ap.add_argument(
        "--output-root",
        type=Path,
        default=OUT_BASE,
        help=(
            "Raiz onde o pack sera criado. O portal usa uma raiz de staging "
            "e so promove o pacote depois dos gates de paridade."
        ),
    )
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
    ap.add_argument(
        "--tags-only",
        action="store_true",
        help=(
            "Produção web: gera somente {PILAR}_sa_motor.svg. Não renderiza "
            "SA plain/distante nem camadas QA; evita três renders redundantes."
        ),
    )
    ap.add_argument(
        "--workers", type=int, default=3,
        help="Processos de render, limitados pela CPU/memória disponível; 1 = sequencial.",
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

    niveis = get_pavimento_niveis_abs(args.obra, args.pav) or {}
    # slabs maps + geometria
    slab_h, slab_n, slab_pts, slab_regions = {}, {}, {}, {}
    for r in conn.execute(
        "SELECT name, points_json, extra_data_json FROM slabs WHERE project_id=?",
        (args.project_id,),
    ):
        ex = json.loads(r["extra_data_json"] or "{}") if r["extra_data_json"] else {}
        fields = ex.get("fields") if isinstance(ex.get("fields"), dict) else {}
        h = fields.get("laje_dim") or ex.get("laje_dim") or ""
        h = str(h).replace("h=", "").replace("cm", "").strip()
        n = fields.get("laje_nivel")
        if n is None or n == "":
            n = ex.get("laje_nivel")
        slab_h[r["name"]] = h
        slab_n[r["name"]] = "" if n is None else str(n)
        slab_regions[r['name']] = ex.get('slab_steps') or []
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

    pillars = _published_pillars(pillars, args.snapshot_path)
    # sort natural
    pillars.sort(key=lambda p: _natural_key(p["name"]))
    if args.item:
        wanted = {str(x).strip().upper() for x in args.item}
        pillars = [p for p in pillars if str(p["name"]).strip().upper() in wanted]
        if not pillars:
            print(f"[ERR] nenhum pilar em --item {args.item}", flush=True)
            return 2
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.output_root / args.obra / f"{args.pav}_{ts}_pilares_abcd"
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
            slab_regions_map=slab_regions,
            beams=beams,
            nivel_viga_default=_absolute_level(niveis.get("chegada_abs")),
        )
        from src.core.pillar_special_faces import enrich_special_pillar_tables
        tables = enrich_special_pillar_tables(
            tables, p, slab_height_map=slab_h, slab_nivel_map=slab_n,
            slab_points_map=slab_pts, beams=beams,
            nivel_viga_default=_absolute_level(niveis.get("chegada_abs")),
        )
        p["interpretacao_abcd"] = tables
        pages.append((p, tables))

    # nav + render (SA sempre com tags; L1/L2/L3 no mesmo paint)
    names = [p["name"] for p, _ in pages]
    print(
        f"[N1] DXF={'ok' if dxf_path and dxf_path.is_file() else 'ausente'} "
        f"skip={args.skip_n1} tags_only={args.tags_only} "
        f"layers={'off' if args.no_layers or args.tags_only else 'SA+L1/L2/L3'}",
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

    nivel_v = _absolute_level(niveis.get("chegada_abs"))
    tagged_cache: dict[str, str] = {}
    plain_cache: dict[str, tuple[str, str]] = {}
    import tempfile
    render_spool = tempfile.TemporaryDirectory(prefix="cad-svg-")
    parallel_full = args.no_layers and not args.tags_only and not args.skip_n1
    if (args.tags_only or parallel_full) and dxf_path and dxf_path.is_file() and pages and args.workers > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        from src.core.cad_render_cache import render_worker_limit
        workers = render_worker_limit(int(args.workers or 1), len(pages))
        print(f"[PERF] render workers={workers}", flush=True)
        payloads = [
            (p["name"], str(dxf_path), p.get("points") or [], tables)
            for p, tables in pages
        ]
        try:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(_render_spooled_worker,
                    (payload, render_spool.name, parallel_full)) for payload in payloads]
                for done_index, future in enumerate(as_completed(futures), start=1):
                    result = future.result()
                    name, svg = result[:2]
                    tagged_cache[name] = svg
                    if parallel_full:
                        plain_cache[name] = (result[2], result[3])
                    print(f"  N1+tags {name} ({done_index}/{len(pages)}) ✓", flush=True)
        except Exception as exc:
            # Fail-safe: o loop abaixo regenera sequencialmente apenas os
            # itens ausentes do cache, sem produzir pack parcialmente válido.
            print(f"  [WARN] pool tags: {exc}; fallback sequencial", flush=True)

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
            if not args.tags_only:
                print(f"  N1+tags {p['name']} ({i+1}/{len(pages)})…", flush=True)
            prop = out_dir / "propostas"
            prop.mkdir(parents=True, exist_ok=True)
            tagged_path = tagged_cache.pop(p["name"], None)
            n1_near = _read_spooled_svg(tagged_path) if tagged_path else ""
            if n1_near:
                _write_publication_text(prop / f"{p['name']}_sa_motor.svg", n1_near)
            if not args.tags_only:
                # O pack humano completo conserva os dois contextos sem tags.
                # A produção web já os possui no HTML canônico e pede somente
                # a evidência tagueada que faltava.
                if p['name'] in plain_cache:
                    near_path, far_path = plain_cache.pop(p['name'])
                    n1_near_plain = _read_spooled_svg(near_path)
                    n1_far = _read_spooled_svg(far_path)
                else:
                    n1_near_plain = _render_n1_svg(dxf_path, pts, context_view="near")
                    n1_far = _render_n1_svg(dxf_path, pts, context_view="far")
                _write_publication_text(prop / f"{p['name']}_sa_plain.svg", n1_near_plain)
                _write_publication_text(prop / f"{p['name']}_sa_far.svg", n1_far)

            def _read_svg(fn: str) -> str:
                fp = prop / fn
                if not fp.is_file():
                    return ""
                return re.sub(
                    r"<\?xml[^?]*\?>", "", fp.read_text(encoding="utf-8")
                ).strip()

            if not args.no_layers and not args.tags_only and _process_item:
                # process_item grava SA com tags + L1/L2/L3
                try:
                    r = _process_item(
                        p,
                        dxf_path=dxf_path,
                        slab_h=slab_h,
                        slab_n=slab_n,
                        slab_pts=slab_pts,
                        slab_regions=slab_regions,
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
                _write_publication_text(prop / f"{p['name']}_sa_motor.svg", n1_near)
                if not args.no_layers and not args.tags_only:
                    for ly in ("l1", "l2", "l3"):
                        svg_ly = _render_tagged(dxf_path, pts, tables, layer=ly)
                        out_name = f"{p['name']}_qa_L{ly[-1]}.svg"
                        _write_publication_text(prop / out_name, svg_ly)
                        if ly == "l1":
                            l1_svg = svg_ly
                            _write_publication_text(prop / f"{p['name']}_qa_proposta.svg", svg_ly)
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
            n1_far_src=f"../propostas/{p['name']}_sa_far.svg" if n1_far else "",
        )
        _write_publication_text(pil_dir / f"{p['name']}.html", html_page)
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
    # Microciclo não substitui o inventário global pelo subconjunto filtrado.
    estado_path = (
        out_dir / "estado_pilares_abcd.json"
        if args.item
        else OUT_BASE / args.obra / f"estado_{args.pav}_pilares_abcd.json"
    )
    estado_path.parent.mkdir(parents=True, exist_ok=True)
    estado_path.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] {len(pages)} fichas em {out_dir}")
    print(f"[OK] estado: {estado_path}")
    if args.skip_n1:
        artefatos_label = "sem SVG N1 (--skip-n1)"
    elif args.tags_only or args.no_layers:
        artefatos_label = "somente SA+tags"
    else:
        artefatos_label = "SA+tags + L1/L2/L3"
    print(
        f"[OK] {artefatos_label} → {out_dir / 'propostas'} "
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
