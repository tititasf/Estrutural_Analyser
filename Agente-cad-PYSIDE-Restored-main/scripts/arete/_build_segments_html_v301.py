# -*- coding: utf-8 -*-
"""HTML E2E multi-segmento V301 com RENDER DXF real (ezdxf), não wireframe.

Gabarito = recorte N2 original clipado por face_unit.
Candidato = N4 VIEW_A/B clipado na banda do label.

Uso:
  python scripts/arete/_build_segments_html_v301.py --open
"""
from __future__ import annotations

import argparse
import html
import json
import sys
import webbrowser
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import ezdxf  # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402

ARETE = Path(__file__).resolve().parent
SCRIPTS = ARETE.parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO))

from arete.geometry_lv_units import (  # noqa: E402
    n2_anchor,
    n4_anchor,
    pair_units,
    split_n4_view,
    unit_label,
)
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402
import gerar_lv_dxf_stog as lv_motor  # noqa: E402
from lv_n4_face_unit_selection import select_n4_face_units  # noqa: E402

GATE = ARETE / "relatorios" / "g2v" / "v301_geometry_gate"
PREV = GATE / "previews_dxf"
N4_DIR = Path(
    r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n4"
)
PREV.mkdir(parents=True, exist_ok=True)


def render_dxf_clip(
    dxf_path: Path,
    out_png: Path,
    *,
    clip: tuple[float, float, float, float] | None,
    title: str,
    width_px: int = 900,
    height_px: int = 520,
    dpi: int = 140,
) -> bool:
    """Render DXF real (cores/layers/cotas do ezdxf drawing). clip=(xmin,ymin,xmax,ymax) abs."""
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        fig_w, fig_h = width_px / dpi, height_px / dpi
        fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
        ax = fig.add_axes([0.02, 0.04, 0.96, 0.90])
        ax.set_facecolor("#ffffff")
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(msp, finalize=True)
        # O finalize do backend DXF pode redimensionar a figura conforme a
        # extensão global do desenho. Reponha o viewport contratado para que
        # N2 e N4 tenham exatamente o mesmo quadro em pixels.
        fig.set_size_inches(fig_w, fig_h, forward=True)
        ax.set_position([0.02, 0.04, 0.96, 0.90])
        if clip is not None:
            xmin, ymin, xmax, ymax = clip
            # Respiro visual: expande o recorte em 20% para cada direção.
            # A mesma regra vale para N2 e N4, preservando a comparação.
            dx = max(5.0, (xmax - xmin) * 0.20)
            dy = max(5.0, (ymax - ymin) * 0.20)
            ax.set_xlim(xmin - dx, xmax + dx)
            ax.set_ylim(ymin - dy, ymax + dy)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(title, fontsize=9, color="#0f172a", pad=4)
        ax.tick_params(labelsize=6)
        # O DXF pode conter textos/cotas com bounding boxes muito afastados do
        # recorte. ``bbox_inches='tight'`` tenta incluí-los e, no Windows, pode
        # produzir uma imagem de dimensão inválida (Errno 22). Os limites do
        # eixo acima já são o contrato visual do segmento; preserve o quadro
        # fixo e deixe o clipping do Matplotlib cuidar do restante.
        fig.savefig(out_png, dpi=dpi, facecolor="#f8fafc")
        plt.close(fig)
        return out_png.is_file()
    except Exception as ex:
        print("render fail", dxf_path.name, ex)
        try:
            plt.close("all")
        except Exception:
            pass
        return False


def _cls(v: str) -> str:
    if "PASS" in v:
        return "ok"
    if "FAIL" in v:
        return "fail"
    return "sus"


def build() -> Path:
    data = json.loads((GATE / "V301_GEOMETRY_GATE.json").read_text(encoding="utf-8"))
    results = list(data.get("results") or [])
    n2_path = Path(data["n2"])

    entry = _entry_from_live_recorte("V301")
    fus = select_n4_face_units(
        lv_motor, entry.get("face_units") or [], "V301"
    ) if entry else []
    n2_by_side: dict[str, list] = {"A": [], "B": []}
    for i, u in enumerate(fus):
        side = str(u.get("side") or "?").upper()
        if side in n2_by_side:
            uu = dict(u)
            uu["_idx"] = i
            n2_by_side[side].append(uu)

    # LV_preview_V301_VIEW_A/B.dxf sao renders de UMA ocorrencia so (uso
    # canonico: ficha focada). O combinado _A.dxf tem TODAS as ocorrencias
    # (A e B, absolutas) na mesma folha — fonte real p/ split multi-unidade
    # (split_n4_view ja filtra por sufixo .A/.B do label).
    _n4_combined = N4_DIR / "LV_preview_V301_A.dxf"
    n4_paths = {
        "A": _n4_combined,
        "B": _n4_combined,
    }
    # Versiona as imagens pela revisão efetiva dos DXFs. Isso impede que o
    # navegador reutilize previews do motor anterior e evita sobrescrever PNGs
    # que estejam momentaneamente abertos pelo servidor no Windows.
    preview_tag = str(
        max(
            [n2_path.stat().st_mtime_ns, Path(__file__).stat().st_mtime_ns]
            + [p.stat().st_mtime_ns for p in n4_paths.values() if p.exists()]
        )
    )
    n4_units = {
        s: split_n4_view(p, s) if p.exists() else [] for s, p in n4_paths.items()
    }

    # mapa label N2 -> unit dict for clip
    n2_by_label: dict[str, dict] = {}
    for side, units in n2_by_side.items():
        for u in units:
            n2_by_label[unit_label(u, u.get("_idx", 0))] = u

    # full face renders (qualidade DXF)
    full_prev = {}
    for side, p in n4_paths.items():
        if p.exists():
            out = PREV / f"FULL_N4_VIEW_{side}_{preview_tag}.png"
            ok = render_dxf_clip(
                p, out, clip=None, title=f"N4 VIEW_{side} completo (DXF real)", width_px=1200, height_px=420
            )
            full_prev[side] = f"previews_dxf/{out.name}" if ok else None

    # N2 full (overview) — recorte inteiro
    out_n2 = PREV / f"FULL_N2_recorte_{preview_tag}.png"
    ok_n2 = render_dxf_clip(
        n2_path, out_n2, clip=None, title="N2 recorte completo (DXF original)", width_px=1200, height_px=520
    )
    full_n2 = f"previews_dxf/{out_n2.name}" if ok_n2 else None

    # per-result previews: clip N2 bbox + clip N4 band
    pairs_by_side = {
        s: pair_units(n2_by_side[s], n4_units[s]) for s in ("A", "B")
    }
    # index by n2 label for n4 unit lookup from gate results
    n4_lookup = {}
    for side, pairs in pairs_by_side.items():
        for pr in pairs:
            if pr.get("status") != "paired":
                continue
            u2, u4 = pr["n2"], pr["n4"]
            lab = unit_label(u2, u2.get("_idx", 0))
            n4_lookup.setdefault((side, lab), []).append((u2, u4))

    lookup_occurrence = {}

    for i, r in enumerate(results):
        r["preview_n2"] = None
        r["preview_n4"] = None
        side = str(r.get("side") or "")
        lab = str(r.get("label") or "")
        if side not in ("A", "B"):
            continue
        key = (side, lab)
        if key not in n4_lookup:
            # try n4_label match
            for (s, l), pairs in n4_lookup.items():
                if s == side and (
                    l == lab
                    or any(p[1].get("label") == r.get("n4_label") for p in pairs)
                ):
                    key = (s, l)
                    break
        if key not in n4_lookup:
            continue
        occurrence = lookup_occurrence.get(key, 0)
        pairs = n4_lookup[key]
        u2, u4 = pairs[min(occurrence, len(pairs) - 1)]
        lookup_occurrence[key] = occurrence + 1
        a2 = n2_anchor(u2)
        a4 = n4_anchor(u4, widths_fallback=a2["panel_widths"])
        ox2, oy2 = a2["origin"]
        # clip N2 em coords absolutas do recorte
        c2 = a2["clip"]  # rel
        clip_n2 = (ox2 + c2[0], oy2 + c2[1], ox2 + c2[2], oy2 + c2[3])
        ox4, oy4 = a4["origin"]
        c4 = a4["clip"]
        clip_n4 = (ox4 + c4[0], oy4 + c4[1], ox4 + c4[2], oy4 + c4[3])

        p2 = PREV / f"seg_{i:02d}_N2_{preview_tag}.png"
        p4 = PREV / f"seg_{i:02d}_N4_{preview_tag}.png"
        t2 = f"N2 · {lab} (clip face_unit DXF original)"
        t4 = f"N4 · {r.get('n4_label')} (clip banda VIEW_{side})"
        if render_dxf_clip(n2_path, p2, clip=clip_n2, title=t2, width_px=700, height_px=400):
            r["preview_n2"] = f"previews_dxf/{p2.name}"
        n4p = n4_paths[side]
        if n4p.exists() and render_dxf_clip(n4p, p4, clip=clip_n4, title=t4, width_px=700, height_px=400):
            r["preview_n4"] = f"previews_dxf/{p4.name}"

    def sort_key(r):
        lab = str(r.get("label") or "")
        side = str(r.get("side") or "")
        primary = 0 if lab in ("V301.A", "V301.B") else (1 if "CONT" in lab else 2)
        return (side, primary, lab)

    ordered = sorted(
        enumerate(
            r for r in results
            if str(r.get("side") or "").upper() in {"A", "B"}
            and str(r.get("pair_status") or "") == "paired"
        ),
        key=lambda t: sort_key(t[1]),
    )
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    prim = [r for r in results if r.get("label") in ("V301.A", "V301.B")]

    parts = [
        """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"/>
<title>V301 · Segmentos DXF real N2×N4</title>
<style>
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e5e7eb;margin:0}
header{padding:16px 22px;background:#0f172a;border-bottom:1px solid #1f2937}
h1{margin:0 0 6px;font-size:1.25rem}.mut{color:#94a3b8;font-size:.9rem}
.ok{color:#34d399;font-weight:700}.fail{color:#f87171;font-weight:700}.sus{color:#fbbf24;font-weight:700}
main{padding:18px 22px 60px;max-width:1600px;margin:0 auto}
.card{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:14px;margin:14px 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:1000px){.grid2{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th,td{border-bottom:1px solid #1f2937;padding:7px 8px;text-align:left;vertical-align:top}
th{color:#94a3b8}
.primary{outline:1px solid #34d39966;background:#052e1a44}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.75rem;font-weight:700}
.badge.ok{background:#064e3b;color:#6ee7b7}.badge.fail{background:#7f1d1d;color:#fca5a5}.badge.sus{background:#78350f;color:#fcd34d}
img.preview{width:100%;border-radius:8px;border:1px solid #334155;background:#fff}
code{color:#fde68a}.kpi{font-size:1.35rem;font-weight:800}
.warn{background:#422006;border:1px solid #b45309;color:#fde68a;padding:10px 12px;border-radius:8px;margin:10px 0}
.segment-head{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap}
.validated{width:18px;height:18px;vertical-align:middle}.validation{white-space:nowrap;font-weight:700}
.attention{display:block;margin-top:10px;font-weight:700}.note{display:block;box-sizing:border-box;width:100%;margin-top:4px;background:#0b1220;color:#e5e7eb;border:1px solid #475569;border-radius:6px;padding:8px;font:inherit}
</style></head><body>
<header>
<h1>V301 · Segmentos com DXF real (ezdxf)</h1>
<p class="mut">N2 = recorte original clipado · N4 = VIEW gerada clipada · cores/layers/cotas via Frontend ezdxf (não wireframe de ledger).</p>
</header><main>
<div class="warn"><b>Transparência:</b> o HTML anterior usava só linhas do GeometryIndex (fidelidade baixa).
Este usa render do DXF. O gate numérico (R/G) continua no ledger; o visual abaixo é o desenho de verdade para você julgar se “parece N2”.</div>
"""
    ]

    # full overviews
    parts.append('<div class="card"><h2>Visão completa DXF</h2><div class="grid2">')
    if full_n2:
        parts.append(f'<div><div class="mut">N2 recorte</div><img class="preview" src="{html.escape(full_n2)}"/></div>')
    for side in ("A", "B"):
        if full_prev.get(side):
            parts.append(
                f'<div><div class="mut">N4 VIEW_{side}</div>'
                f'<img class="preview" src="{html.escape(full_prev[side])}"/></div>'
            )
    parts.append("</div></div>")

    parts.append('<div class="card"><h2>Faces nominais A/B (métricas gate)</h2><div class="grid2">')
    for r in prim:
        m = r.get("metrics") or {}
        v = r["verdict"]
        parts.append(
            f"""<div class="primary" style="padding:12px;border-radius:10px">
<div><span class="badge {_cls(v)}">{html.escape(v)}</span>
 <b>{html.escape(str(r.get('label')))}</b> ↔ <code>{html.escape(str(r.get('n4_label')))}</code></div>
<div class="kpi">R {100*float(m.get('r_match') or 0):.0f}% · G {100*float(m.get('g_match') or 0):.0f}%</div>
<div class="mut">inventadas {html.escape(str(m.get('invented_r') or []))}</div>
</div>"""
        )
    parts.append("</div></div>")

    parts.append('<div class="card"><h2>Resumo multi-segmento</h2><ul>')
    for k in ("PASS E2E", "FAIL E2E", "SUSPEITO"):
        if counts.get(k):
            parts.append(f"<li class='{_cls(k)}'>{k}: <b>{counts[k]}</b></li>")
    parts.append(f"</ul><p class='mut'>Total: {len(results)} · {html.escape(str(data.get('schema')))}</p></div>")

    parts.append('<div class="card"><h2>Tabela</h2><table>')
    parts.append(
        "<tr><th>#</th><th>N2</th><th>N4</th><th>Side</th><th>Pair</th>"
        "<th>Veredito</th><th>R%</th><th>G%</th><th>Inv</th><th>Motivos</th></tr>"
    )
    for i, r in ordered:
        m = r.get("metrics") or {}
        v = r["verdict"]
        lab = str(r.get("label") or "")
        row = "primary" if lab in ("V301.A", "V301.B") else ""
        parts.append(
            f"<tr class='{row}'><td>{i}</td>"
            f"<td><code>{html.escape(lab)}</code></td>"
            f"<td><code>{html.escape(str(r.get('n4_label') or '—'))}</code></td>"
            f"<td>{html.escape(str(r.get('side')))}</td>"
            f"<td class='mut'>{html.escape(str(r.get('pair_status')))}</td>"
            f"<td class='{_cls(v)}'>{html.escape(v)}</td>"
            f"<td>{100*float(m.get('r_match') or 0):.0f}%</td>"
            f"<td>{100*float(m.get('g_match') or 0):.0f}%</td>"
            f"<td>{html.escape(str(m.get('invented_r') or [])[:40])}</td>"
            f"<td class='mut'>{html.escape(' · '.join(r.get('reasons') or [])[:140])}</td></tr>"
        )
    parts.append("</table></div>")

    parts.append('<div class="card"><h2>Revisão por segmento (N2 clip | N4 clip)</h2><p class="mut">Cada cartão tem obrigatoriamente seu par N2×N4. A nomenclatura é sequencial por lado: SEGMENTO 1A, 2A, …, 1B, 2B.</p>')
    segment_ordinals = {"A": 0, "B": 0}
    for i, r in ordered:
        m = r.get("metrics") or {}
        v = r["verdict"]
        lab = str(r.get("label") or "")
        side = str(r.get("side") or "").upper()
        segment_ordinals[side] += 1
        segment_name = f"SEGMENTO {segment_ordinals[side]}{side}"
        box = "primary" if lab in ("V301.A", "V301.B") else ""
        legacy_key = f"LV::13_PAV::V301::{r.get('side')}::{lab}::{r.get('n4_label') or 'ausente'}"
        review_key = f"LV::13_PAV::V301::{segment_name}::{i}::{lab}::{r.get('n4_label') or 'ausente'}"
        parts.append(
            f'<article class="card segment-card {box}" '
            f'data-key="{html.escape(review_key, quote=True)}" '
            f'data-legacy-key="{html.escape(legacy_key, quote=True)}" '
            'style="margin:10px 0">'
        )
        parts.append(
            f"<div class='segment-head'><div><span class='badge {_cls(v)}'>{html.escape(v)}</span> "
            f"<b>{segment_name}</b> <span class='mut'>#{i}</span> <code>{html.escape(lab)}</code> ↔ "
            f"<code>{html.escape(str(r.get('n4_label') or '—'))}</code> · "
            f"R {100*float(m.get('r_match') or 0):.0f}% · G {100*float(m.get('g_match') or 0):.0f}%</div>"
            "<label class='validation'><input class='validated' type='checkbox'> Validado</label></div>"
        )
        p2, p4 = r.get("preview_n2"), r.get("preview_n4")
        if p2 or p4:
            parts.append('<div class="grid2">')
            if p2:
                parts.append(f'<div><div class="mut">N2 original (clip)</div><img class="preview" src="{html.escape(p2)}"/></div>')
            if p4:
                parts.append(f'<div><div class="mut">N4 gerado (clip)</div><img class="preview" src="{html.escape(p4)}"/></div>')
            parts.append("</div>")
        else:
            parts.append("<p class='mut'>sem par clipável (n2_only / n4_only / CORTE)</p>")
        parts.append(
            f"<p class='mut'>{html.escape(' · '.join(r.get('reasons') or [])[:220])}</p>"
            "<label class='attention'>Atenção / observação"
            "<textarea class='note' rows='3' placeholder='Salva automaticamente neste navegador'></textarea>"
            "</label></article>"
        )
    parts.append("""</div></main><script>
const prefix='cad_analyzer_review_';
const cards=[...document.querySelectorAll('.segment-card')];
function cookieNameFor(key){return prefix+key.replace(/[^a-zA-Z0-9]/g,'_');}
function cookieName(card){return cookieNameFor(card.dataset.key);}
function readCookie(key){try{const name=cookieNameFor(key)+'=';const part=document.cookie.split('; ').find(row=>row.startsWith(name));return part?JSON.parse(decodeURIComponent(part.slice(name.length))):{};}catch(_){return {};}}
function read(card){const current=readCookie(card.dataset.key);if(current.validated||current.note)return current;return readCookie(card.dataset.legacyKey||'');}
function sync(key,data){fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({[key]:data})}).catch(()=>{});}
function save(card){const data={validated:card.querySelector('.validated').checked,note:card.querySelector('.note').value,updated_at:new Date().toISOString()};try{const value=encodeURIComponent(JSON.stringify(data));if(value.length>3500)throw Error('nota longa');document.cookie=`${cookieName(card)}=${value}; Max-Age=31536000; Path=/; SameSite=Lax`;sync(card.dataset.key,data);}catch(_){alert('Nota muito longa para salvar (limite: cerca de 3.500 caracteres).');}}
cards.forEach(card=>{const saved=read(card);card.querySelector('.validated').checked=!!saved.validated;card.querySelector('.note').value=saved.note||'';if(saved.validated||saved.note)sync(card.dataset.key,saved);card.querySelector('.validated').addEventListener('change',()=>save(card));card.querySelector('.note').addEventListener('input',()=>save(card));});
</script></body></html>""")

    out = GATE / "V301_SEGMENTS_E2E.html"
    out.write_text("".join(parts), encoding="utf-8")
    print("previews in", PREV)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()
    path = build()
    print("HTML", path)
    if args.open:
        webbrowser.open(path.resolve().as_uri())


if __name__ == "__main__":
    main()
