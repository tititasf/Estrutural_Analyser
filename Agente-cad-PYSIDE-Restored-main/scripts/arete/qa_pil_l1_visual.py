#!/usr/bin/env python
"""QA agêntico PIL — **somente Camada 1** (vs SA motor com tags).

Para cada pilar do pack:
  1. Lê tabelas ABCD (estado ou re-build do DB)
  2. Roda ``analyze_verdict`` (heurística L1)
  3. Grava notes L1 (verdict + texto) sem tocar L2/L3
  4. Compara tags embutidas em ``_sa_motor.svg`` vs ``_qa_L1.svg``
  5. Relatório pack: validou / invalidou / divergência de tags

Uso:
  py -3.12 scripts/arete/qa_pil_l1_visual.py \\
    --pack .../13_PAV_..._pilares_abcd \\
    --items P1 P2 ... P10
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.pil_qa_notes_chrome import pil_keys  # noqa: E402


def _extract_tag_comments(svg_text: str) -> list[str]:
    """Comentários matplotlib do tipo <!-- V.chega BC -->."""
    tags = re.findall(r"<!--\s*((?:V\.(?:chega|passa|interior)|laje)[^>]*)\s*-->", svg_text)
    # fallback: texto multilinha já path — pega labels do JSON se existir
    return [t.strip() for t in tags if t.strip()]


def _face_summary_from_json(jpath: Path) -> dict:
    if not jpath.is_file():
        return {}
    try:
        return json.loads(jpath.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _merge_notes(notes_path: Path, updates: dict) -> dict:
    doc = {
        "version": 1,
        "page": notes_path.stem.replace(".notes", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "notes": {},
    }
    if notes_path.is_file():
        try:
            old = json.loads(notes_path.read_text(encoding="utf-8"))
            doc["notes"] = dict(old.get("notes") or {})
            if old.get("page"):
                doc["page"] = old["page"]
        except Exception:
            pass
    doc["notes"].update(updates)
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return doc


def _patch_html_notes_store(html_path: Path, notes_doc: dict) -> None:
    if not html_path.is_file():
        return
    html = html_path.read_text(encoding="utf-8")
    store_tag = (
        '<script type="application/json" id="pil-notes-store">\n'
        f"{json.dumps(notes_doc, ensure_ascii=False)}\n</script>"
    )
    if 'id="pil-notes-store"' in html:
        html2 = re.sub(
            r'<script type="application/json" id="pil-notes-store">[\s\S]*?</script>',
            store_tag,
            html,
            count=1,
        )
        if html2 != html:
            html_path.write_text(html2, encoding="utf-8")


def run_pack(
    pack: Path,
    *,
    items: list[str],
    obra: str,
    pav: str,
    project_id: str,
    db: Path,
) -> dict:
    # import agent draw helpers
    import importlib.util

    ag_path = Path(__file__).resolve().parent / "pil_agentic_highlight_draw.py"
    spec = importlib.util.spec_from_file_location("pil_agentic_highlight_draw", ag_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    dxf_path, slab_h, slab_n, slab_pts, beams, pillars = mod.load_project(
        db, project_id, obra, pav
    )
    from src.core.niveis_extractor import get_pavimento_niveis_abs
    from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar

    niveis = get_pavimento_niveis_abs(obra, pav) or {"chegada_abs": 852.19}
    nivel_v = f"{niveis.get('chegada_abs')}cm"

    wanted = {x.strip().upper() for x in items} if items else None
    batch = [p for p in pillars if not wanted or p["name"].upper() in wanted]
    if not batch and items:
        # fallback: só nomes do pack
        batch = [{"name": n, "points": [], "face_beams": {}, "lajes": []} for n in items]

    prop = pack / "propostas"
    pil_dir = pack / "pilares"
    results = []

    for p in batch:
        name = p["name"]
        keys = pil_keys(obra, pav, name)
        tables = build_abcd_tables_from_pillar(
            p,
            slab_height_map=slab_h,
            slab_nivel_map=slab_n,
            slab_points_map=slab_pts,
            beams=beams,
            nivel_viga_default=nivel_v,
        )
        verdict, agent_text = mod.analyze_verdict(name, tables, p)
        lines = mod.face_lines_from_tables(tables)

        # Artefatos
        sa_path = prop / f"{name}_sa_motor.svg"
        l1_path = prop / f"{name}_qa_L1.svg"
        plain_path = prop / f"{name}_sa_plain.svg"
        jpath = prop / f"{name}_qa_proposta.json"

        sa_tags = _extract_tag_comments(sa_path.read_text(encoding="utf-8")) if sa_path.is_file() else []
        l1_tags = _extract_tag_comments(l1_path.read_text(encoding="utf-8")) if l1_path.is_file() else []
        # se SVG path sem comments, usa faces do JSON / tables
        if not sa_tags and not l1_tags:
            flat = []
            for fid in "ABCD":
                for bit in lines.get(fid) or []:
                    flat.append(f"{fid}:{bit.splitlines()[0]}")
            sa_tags = list(flat)
            l1_tags = list(flat)

        tags_equal = sorted(sa_tags) == sorted(l1_tags)
        sa_exists = sa_path.is_file()
        l1_exists = l1_path.is_file()
        plain_exists = plain_path.is_file()

        # Re-render L1 only se faltar (não reescreve SA)
        if dxf_path and dxf_path.is_file() and p.get("points") and not l1_exists:
            svg_l1 = mod.render_agentic_svg(
                dxf_path, p.get("points") or [], tables, layer="l1"
            )
            prop.mkdir(parents=True, exist_ok=True)
            l1_path.write_text(svg_l1, encoding="utf-8")
            (prop / f"{name}_qa_proposta.svg").write_text(svg_l1, encoding="utf-8")
            l1_exists = True
            l1_tags = _extract_tag_comments(svg_l1) or l1_tags

        # notes: L1 + legado agent
        l1_header = (
            f"[Camada 1 QA · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}Z]\n"
            f"Comparação vs SA motor (tags): "
            f"{'IGUAL' if tags_equal else 'DIVERGE'} · "
            f"artefatos sa={sa_exists} l1={l1_exists} plain={plain_exists}\n\n"
        )
        agent_l1_text = l1_header + agent_text
        if not tags_equal:
            agent_l1_text += (
                "\n\n[TAGS] SA≠L1 no SVG — revisar se L1 foi redesenhado "
                "com interpretação alternativa.\n"
                f"SA sample: {sa_tags[:8]}\nL1 sample: {l1_tags[:8]}\n"
            )
        else:
            agent_l1_text += (
                "\n\n[TAGS] L1 usa as **mesmas tags** do SA motor nesta passagem "
                "(leitura compartilhada face_beams/ABCD). "
                "Veredito L1 = julgamento heurístico da coerência da interpretação, "
                "não um segundo motor geométrico.\n"
            )

        updates = {
            keys["agent_verdict_l1"]: verdict,
            keys["agent_l1"]: agent_l1_text,
            # legado espelha L1
            keys["agent_verdict"]: verdict,
            keys["agent"]: agent_l1_text,
        }
        notes_path = pil_dir / f"{name}.notes.json"
        notes_doc = _merge_notes(notes_path, updates)
        notes_doc["page"] = name
        _patch_html_notes_store(pil_dir / f"{name}.html", notes_doc)

        # atualiza JSON proposta com meta L1
        payload = _face_summary_from_json(jpath)
        payload.update(
            {
                "item": name,
                "class": "PIL",
                "layer_qa": "l1",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "verdict": verdict,
                "verdict_source": "analyze_verdict_l1",
                "tags_sa_vs_l1": "equal" if tags_equal else "diverge",
                "tags_sa_n": len(sa_tags),
                "tags_l1_n": len(l1_tags),
                "faces": lines,
                "agent_text": agent_l1_text,
            }
        )
        prop.mkdir(parents=True, exist_ok=True)
        jpath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        row = {
            "item": name,
            "verdict": verdict,
            "tags_equal": tags_equal,
            "sa_tags_n": len(sa_tags),
            "l1_tags_n": len(l1_tags),
            "sa_motor": sa_exists,
            "qa_l1": l1_exists,
            "sa_plain": plain_exists,
            "summary": agent_text.split("\n")[0][:120],
        }
        results.append(row)
        mark = "✓" if verdict == "validou" else "✗"
        te = "=" if tags_equal else "≠"
        print(f"  {mark} {name}: {verdict} · tags SA{te}L1 · n={len(l1_tags)}", flush=True)

    n_ok = sum(1 for r in results if r["verdict"] == "validou")
    n_bad = sum(1 for r in results if r["verdict"] == "invalidou")
    n_div = sum(1 for r in results if not r["tags_equal"])
    report = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "pack": str(pack),
        "obra": obra,
        "pav": pav,
        "layer": "l1",
        "scope": "somente_camada_1",
        "n": len(results),
        "validou": n_ok,
        "invalidou": n_bad,
        "tags_divergem": n_div,
        "nota": (
            "L1 nesta passagem julga a interpretação SA (mesmas tags face_beams/ABCD). "
            "Divergência de tags só se L1 SVG foi redesenhado com outra leitura. "
            "invalidou = heurística (dualidade, banda topo, C.passa, horizontal…)."
        ),
        "items": results,
    }
    out = pack / "qa_l1_visual_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # HTML resumo curto
    rows_html = "".join(
        f"<tr class='{r['verdict']}'><td>{r['item']}</td><td>{r['verdict']}</td>"
        f"<td>{'igual' if r['tags_equal'] else 'diverge'}</td>"
        f"<td>{r['sa_tags_n']}/{r['l1_tags_n']}</td>"
        f"<td>{'Y' if r['sa_plain'] else 'N'}/{'Y' if r['sa_motor'] else 'N'}/"
        f"{'Y' if r['qa_l1'] else 'N'}</td>"
        f"<td>{r['summary']}</td></tr>"
        for r in results
    )
    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<title>QA L1 visual — {obra}/{pav}</title>
<style>
body{{background:#111;color:#ccc;font:13px Consolas,monospace;padding:16px}}
h2{{color:#7eb8f7}} table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #333;padding:6px 8px;text-align:left}}
th{{background:#1a1a1a;color:#4fc3a1}}
tr.validou td:nth-child(2){{color:#9fdfb0}}
tr.invalidou td:nth-child(2){{color:#f0a0a0}}
.meta{{color:#888;margin-bottom:12px;line-height:1.45}}
a{{color:#7eb8f7}}
</style></head><body>
<h2>QA agêntico — Camada 1 (só)</h2>
<div class="meta">
pack: {pack.name}<br>
validou={n_ok} · invalidou={n_bad} · tags divergem={n_div} · n={len(results)}<br>
{report['nota']}
</div>
<table>
<tr><th>Pilar</th><th>Veredito L1</th><th>Tags SA vs L1</th><th>n tags SA/L1</th>
<th>plain/motor/L1</th><th>Resumo</th></tr>
{rows_html}
</table>
<p><a href="index.html">Índice pack</a></p>
</body></html>"""
    (pack / "qa_l1_visual_report.html").write_text(html, encoding="utf-8")
    print(f"[OK] report → {out}", flush=True)
    print(f"[OK] html   → {pack / 'qa_l1_visual_report.html'}", flush=True)
    print(f"[SUM] validou={n_ok} invalidou={n_bad} tags_div={n_div}", flush=True)
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--items", nargs="*", default=[])
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--project-id", default="dd238e47-1dc6-4f63-a760-4e7ce19a7386")
    ap.add_argument("--db", default=str(ROOT.parent / "project_data.vision"))
    args = ap.parse_args()
    pack = Path(args.pack)
    if not pack.is_dir():
        print(f"[ERR] pack {pack}")
        return 2
    items = args.items
    if not items:
        # auto: pilares/*.html
        items = sorted(
            p.stem for p in (pack / "pilares").glob("*.html") if p.stem.upper().startswith("P")
        )
    print(f"[RUN] QA L1 visual · {len(items)} itens · pack={pack.name}", flush=True)
    run_pack(
        pack,
        items=items,
        obra=args.obra,
        pav=args.pav,
        project_id=args.project_id,
        db=Path(args.db),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
