# -*- coding: utf-8 -*-
"""Geometry gate LV — N2×N4 multi-unidade via GeometryIndex.

Uso:
  python scripts/arete/run_geometry_gate_lv.py V301
  python scripts/arete/run_geometry_gate_lv.py V301 --no-regen --no-open

Saídas em:
  scripts/arete/relatorios/g2v/{item}_geometry_gate/
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import subprocess
import sys
import webbrowser
from collections import Counter
from pathlib import Path

ARETE = Path(__file__).resolve().parent
REPO = ARETE.parent.parent
SCRIPTS = ARETE.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO))

from arete.geometry_index import GeometryIndex  # noqa: E402
from arete.geometry_lv_units import (  # noqa: E402
    n2_anchor,
    n4_anchor,
    pair_units,
    panel_widths,
    split_n4_view,
    unit_label,
)
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402
from arete.vision_anti_hallucination import (  # noqa: E402
    merge_arete_verdict,
    vision_gate_unit,
)
import gerar_lv_dxf_stog as lv_motor  # noqa: E402
from lv_n4_face_unit_selection import select_n4_face_units  # noqa: E402

DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
OBRA = Path(r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1")
N4_DIR = OBRA / "Fase-6_Execucao_CAD" / "n4"


def resolve_n2(item: str) -> Path:
    conn = sqlite3.connect(str(DB))
    row = conn.execute(
        "SELECT recorte_path FROM reverse_eng_recortes "
        "WHERE UPPER(elemento_id)=? AND UPPER(classe)='LV' "
        "ORDER BY id DESC LIMIT 1",
        (item.upper(),),
    ).fetchone()
    conn.close()
    if not row:
        raise SystemExit(f"N2 recorte não encontrado para {item}")
    p = Path(row[0])
    if not p.exists():
        raise SystemExit(f"N2 path missing: {p}")
    return p


def build_html(item: str, results: list[dict], out: Path, meta: dict) -> Path:
    counts = Counter(r["verdict"] for r in results)
    parts = [
        f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"/>
<title>{html.escape(item)} Geometry Gate N2×N4</title>
<style>
body{{font-family:system-ui,sans-serif;background:#0b1220;color:#e5e7eb;margin:0}}
header{{padding:16px 22px;background:#0f172a;border-bottom:1px solid #1f2937}}
h1{{margin:0 0 6px;font-size:1.2rem}}.mut{{color:#94a3b8}}
.ok{{color:#34d399;font-weight:700}}.fail{{color:#f87171;font-weight:700}}
.sus{{color:#fbbf24;font-weight:700}}
main{{padding:18px 22px 48px;max-width:1400px;margin:0 auto}}
table{{width:100%;border-collapse:collapse;font-size:.82rem}}
th,td{{border-bottom:1px solid #1f2937;padding:7px 8px;text-align:left;vertical-align:top}}
th{{color:#94a3b8}}.card{{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:12px;margin:14px 0}}
code{{color:#fde68a}}
</style></head><body><header>
<h1>{html.escape(item)} · Geometry Gate (structured retrieval)</h1>
<p class="mut">N2×N4 · GeometryIndex · sem RAG · PNG fora deste gate</p>
</header><main>
<div class="card"><h2>Resumo</h2><ul>
"""
    ]
    for k in ("PASS E2E", "FAIL E2E", "SUSPEITO", "NÃO VALIDADO"):
        if counts.get(k):
            cls = "ok" if "PASS" in k else ("fail" if "FAIL" in k else "sus")
            parts.append(f"<li class='{cls}'>{k}: <b>{counts[k]}</b></li>")
    parts.append(
        f"</ul><p class='mut'>N2 <code>{html.escape(meta.get('n2',''))}</code><br/>"
        f"protocolo <code>geometry_index_v1</code></p></div>"
    )
    parts.append("<div class='card'><h2>Tabela</h2><table>")
    parts.append(
        "<tr><th>#</th><th>Label</th><th>Side</th><th>Pair</th><th>Veredito</th>"
        "<th>R%</th><th>G%</th><th>Visão</th><th>Inventadas</th><th>Motivos</th></tr>"
    )
    for i, r in enumerate(results):
        v = r["verdict"]
        cls = "ok" if "PASS" in v else ("fail" if "FAIL" in v else "sus")
        m = r.get("metrics") or {}
        vis = r.get("vision") or {}
        vv = str(vis.get("vision_verdict") or "—")
        vcls = (
            "ok"
            if "PASS" in vv
            else ("fail" if "FAIL" in vv else ("sus" if vv != "—" else "mut"))
        )
        parts.append(
            "<tr>"
            f"<td>{i}</td>"
            f"<td><code>{html.escape(str(r.get('label')))}</code></td>"
            f"<td>{html.escape(str(r.get('side')))}</td>"
            f"<td class='mut'>{html.escape(str(r.get('pair_status')))} sc={r.get('pair_score')}</td>"
            f"<td class='{cls}'>{html.escape(v)}</td>"
            f"<td>{100*float(m.get('r_match') or 0):.0f}%</td>"
            f"<td>{100*float(m.get('g_match') or 0):.0f}%</td>"
            f"<td class='{vcls}'>{html.escape(vv)}</td>"
            f"<td>{html.escape(str(m.get('invented_r') or [])[:60])}</td>"
            f"<td class='mut'>{html.escape(' · '.join(r.get('reasons') or [])[:180])}</td>"
            "</tr>"
        )
    parts.append("</table></div></main></body></html>")
    path = out / f"{item}_GEOMETRY_GATE.html"
    path.write_text("".join(parts), encoding="utf-8")
    return path


def run_item(item: str, *, regen: bool, open_html: bool) -> dict:
    out = ARETE / "relatorios" / "g2v" / f"{item.lower()}_geometry_gate"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ledgers").mkdir(exist_ok=True)

    if regen:
        print(f"=== REGEN N4 {item} ===")
        env = dict(**__import__("os").environ)
        env["PYTHONPATH"] = (
            str(SCRIPTS)
            + __import__("os").pathsep
            + str(REPO)
            + __import__("os").pathsep
            + env.get("PYTHONPATH", "")
        )
        subprocess.run(
            [
                sys.executable, str(ARETE / "gerar_lv_n4_fichas.py"), item,
                "--refresh-from-recorte",
            ],
            cwd=str(REPO),
            env=env,
            check=False,
        )

    n2_path = resolve_n2(item)
    print("N2", n2_path)
    entry = _entry_from_live_recorte(item)
    if not entry:
        raise SystemExit("live recorte extract failed")
    fus = select_n4_face_units(lv_motor, entry.get("face_units") or [], item)
    print("face_units canonical", len(fus))

    # LV_preview_{item}_VIEW_A/B.dxf agora sao renders de UMA ocorrencia so
    # (uso canonico: ficha focada). O combinado _A.dxf tem TODAS as
    # ocorrencias (A e B, absolutas) na mesma folha — fonte real p/ split
    # por label/banda multi-unidade.
    n4_combined = N4_DIR / f"LV_preview_{item}_A.dxf"
    n4_by_side = {
        "A": split_n4_view(n4_combined, "A") if n4_combined.exists() else [],
        "B": split_n4_view(n4_combined, "B") if n4_combined.exists() else [],
    }
    print("N4 A", len(n4_by_side["A"]), "B", len(n4_by_side["B"]))

    n2_by_side: dict[str, list] = {"A": [], "B": []}
    for i, u in enumerate(fus):
        side = str(u.get("side") or "?").upper()
        if side in n2_by_side:
            u = dict(u)
            u["_idx"] = i
            n2_by_side[side].append(u)

    results = []
    for side in ("A", "B"):
        pairs = pair_units(n2_by_side[side], n4_by_side[side])
        n4_path = n4_combined
        for pr in pairs:
            status = pr["status"]
            if status == "n2_only":
                u2 = pr["n2"]
                lab = unit_label(u2, u2.get("_idx", 0))
                results.append(
                    {
                        "label": lab,
                        "side": side,
                        "verdict": "FAIL E2E",
                        "pair_status": status,
                        "pair_score": pr["score"],
                        "reasons": ["unidade N2 sem par N4"],
                        "metrics": {},
                    }
                )
                continue
            if status == "n4_only":
                u4 = pr["n4"]
                results.append(
                    {
                        "label": f"N4-only:{u4.get('label')}",
                        "side": side,
                        "verdict": "SUSPEITO",
                        "pair_status": status,
                        "pair_score": 0.0,
                        "reasons": ["unidade N4 sem face_unit N2"],
                        "metrics": {},
                    }
                )
                continue

            u2, u4 = pr["n2"], pr["n4"]
            lab = unit_label(u2, u2.get("_idx", 0))
            print(f"\n=== [{side}] {lab} ↔ {u4.get('label')} sc={pr['score']} ===")
            a2 = n2_anchor(u2)
            a4 = n4_anchor(u4, widths_fallback=a2["panel_widths"])
            try:
                idx2 = GeometryIndex.from_dxf(
                    n2_path,
                    origin=a2["origin"],
                    h_body=a2["h_body"],
                    total_w=a2["total_w"],
                    panel_widths=a2["panel_widths"],
                    clip=a2["clip"],
                    side=side,
                    label=lab,
                    role="gabarito",
                )
                idx4 = GeometryIndex.from_dxf(
                    n4_path,
                    origin=a4["origin"],
                    h_body=a4["h_body"],
                    total_w=a4["total_w"],
                    panel_widths=a4["panel_widths"] or a2["panel_widths"],
                    clip=a4["clip"],
                    side=f"N4{side}",
                    label=str(u4.get("label") or lab),
                    role="candidato",
                )
            except Exception as ex:
                results.append(
                    {
                        "label": lab,
                        "side": side,
                        "verdict": "SUSPEITO",
                        "pair_status": status,
                        "pair_score": pr["score"],
                        "reasons": [f"ledger fail: {ex}"],
                        "metrics": {},
                    }
                )
                continue

            sn = re.sub(r"[^\w.\-]+", "_", f"{side}_{lab}")[:70]
            (out / "ledgers" / f"{sn}_n2.json").write_text(
                json.dumps(idx2.ledger, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (out / "ledgers" / f"{sn}_n4.json").write_text(
                json.dumps(idx4.ledger, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            report = GeometryIndex.diff(idx2, idx4, pair="N2xN4")
            reasons = list(report["reasons"] or [])
            verdict = report["verdict"]
            vision = None
            # Camada VISÃO obrigatória nas faces nominais (anti-100% mentiroso)
            is_primary = bool(re.match(rf"^{re.escape(item)}\.[AB]$", lab, re.I))
            if is_primary:
                vis_dir = out / "vision"
                try:
                    vision = vision_gate_unit(
                        n2_path,
                        n4_path,
                        a2,
                        a4,
                        label=lab,
                        out_dir=vis_dir,
                        max_struct_extra=0,
                        max_extra_ratio=0.06,
                        max_extra_pixels=2200,
                    )
                    reasons = reasons + [
                        f"VISION:{vision.get('vision_verdict')}",
                        *(vision.get("reasons") or [])[:4],
                    ]
                    # veto: FAIL_VISION derruba; Arete 100% so se visão elege
                    if vision.get("vision_verdict") == "FAIL_VISION":
                        verdict = "FAIL E2E"
                        reasons.append("VETO visão anti-alucinação")
                    elif vision.get("arete_100_eligible"):
                        verdict = "PASS E2E"
                        reasons.append("Arete 100% confirmado por visão+geo (zero EXTRA)")
                    elif "Arete 100%" in " ".join(report.get("reasons") or []):
                        # geo pediu 100% mas visão não elege → não mentir
                        verdict = "SUSPEITO"
                        reasons.append(
                            "VETO: GeometryIndex 100% anulado — visão não elege Arete 100%"
                        )
                    else:
                        verdict = merge_arete_verdict(verdict, vision)
                except Exception as ex:
                    reasons.append(f"VISION error: {ex}")
                    if "Arete 100%" in " ".join(report.get("reasons") or []):
                        verdict = "SUSPEITO"
                        reasons.append("VETO: Arete 100% sem visão válida")

            print(" ", verdict, reasons[0] if reasons else "")
            results.append(
                {
                    "label": lab,
                    "n4_label": u4.get("label"),
                    "side": side,
                    "verdict": verdict,
                    "pair_status": status,
                    "pair_score": pr["score"],
                    "reasons": reasons,
                    "metrics": report["metrics"],
                    "vision": vision,
                    "ledger_n2": f"ledgers/{sn}_n2.json",
                    "ledger_n4": f"ledgers/{sn}_n4.json",
                }
            )

    # CORTE stub
    n4c = N4_DIR / f"LV_preview_{item}_CORTE.dxf"
    if n4c.exists():
        results.append(
            {
                "label": "CORTE",
                "side": "CORTE",
                "verdict": "SUSPEITO",
                "pair_status": "corte",
                "pair_score": 0.0,
                "reasons": [
                    "CORTE: GeometryIndex multi-unidade de seção ainda não ancorado no recorte N2",
                    f"path={n4c.name}",
                ],
                "metrics": {},
            }
        )

    summary = {
        "item": item,
        "classe": "LV",
        "schema": "geometry_index_v1",
        "n2": str(n2_path),
        "counts": dict(Counter(r["verdict"] for r in results)),
        "results": results,
    }
    (out / f"{item}_GEOMETRY_GATE.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    html_path = build_html(item, results, out, {"n2": str(n2_path)})
    print("\n=== SUMMARY ===", summary["counts"])
    print("HTML", html_path)
    print("JSON", out / f"{item}_GEOMETRY_GATE.json")
    if open_html:
        webbrowser.open(html_path.resolve().as_uri())
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("item", nargs="?", default="V301")
    ap.add_argument("--no-regen", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args(argv)
    run_item(args.item, regen=not args.no_regen, open_html=not args.no_open)


if __name__ == "__main__":
    main()
