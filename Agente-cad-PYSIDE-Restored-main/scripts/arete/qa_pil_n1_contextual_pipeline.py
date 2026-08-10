#!/usr/bin/env python
"""CLI looping agêntico PIL (espelho FV propose-draw / write-agent).

Uso:
  py -3.12 scripts/arete/qa_pil_n1_contextual_pipeline.py write-agent \\
    --pack .../13_PAV_..._pilares_abcd --item P2 --verdict invalidou --text "..."

  py -3.12 scripts/arete/qa_pil_n1_contextual_pipeline.py propose-draw \\
    --pack ... --item P2 --json path/to/proposta.json

  py -3.12 scripts/arete/qa_pil_n1_contextual_pipeline.py read-notes --pack ... --item P2
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.pil_qa_notes_chrome import pil_keys  # noqa: E402


def _pack_dir(p: str) -> Path:
    path = Path(p)
    if not path.is_dir():
        raise SystemExit(f"pack inexistente: {path}")
    return path.resolve()


def cmd_write_agent(args) -> int:
    pack = _pack_dir(args.pack)
    item = args.item
    keys = pil_keys(args.obra, args.pav, item)
    notes_path = pack / "pilares" / f"{item}.notes.json"
    data = {"version": 1, "page": item, "updated_at": "", "notes": {}}
    if notes_path.is_file():
        try:
            data = json.loads(notes_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    notes = data.setdefault("notes", {})
    notes[keys["agent_verdict"]] = args.verdict
    text = args.text or ""
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    notes[keys["agent"]] = text
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] write-agent {item} verdict={args.verdict} → {notes_path}")
    return 0


def cmd_propose_draw(args) -> int:
    """Grava JSON de proposta + SVG placeholder (HI-FI real vem do motor de desenho)."""
    pack = _pack_dir(args.pack)
    item = args.item
    prop_dir = pack / "propostas"
    prop_dir.mkdir(parents=True, exist_ok=True)
    if args.json:
        src = Path(args.json)
        payload = json.loads(src.read_text(encoding="utf-8"))
    else:
        payload = {
            "item": item,
            "class": "PIL",
            "proposed": json.loads(args.proposed or "[]"),
            "note": args.note or "",
        }
    payload.setdefault("item", item)
    payload.setdefault("class", "PIL")
    jpath = prop_dir / f"{item}_qa_proposta.json"
    jpath.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # SVG mínimo legível (não substitui HI-FI com DXF — documentado no procedimento)
    polys = []
    for i, seg in enumerate(payload.get("proposed") or [], 1):
        pts = seg.get("points") or []
        if len(pts) < 2:
            continue
        d = "M " + " L ".join(f"{float(p[0]):.2f},{float(-float(p[1])):.2f}" for p in pts)
        if len(pts) >= 3:
            d += " Z"
        label = seg.get("label") or str(i)
        color = "#00e5ff" if i % 2 else "#69f0ae"
        polys.append(
            f'<path d="{d}" fill="{color}" fill-opacity="0.25" stroke="{color}" '
            f'stroke-width="2"/><text x="{float(pts[0][0]):.1f}" '
            f'y="{(-float(pts[0][1])-8):.1f}" fill="{color}" font-size="14">P{label}</text>'
        )
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        'style="background:#0a0a0a">\n'
        f'<!-- PIL QA proposal {item} — prefer HI-FI overlay on N1 SVG -->\n'
        + "\n".join(polys)
        + "\n</svg>\n"
    )
    # se points em CAD, viewBox deve envolver — recalcula
    all_pts = []
    for seg in payload.get("proposed") or []:
        for p in seg.get("points") or []:
            all_pts.append((float(p[0]), float(p[1])))
    if all_pts:
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        pad = 40
        minx, maxx = min(xs) - pad, max(xs) + pad
        miny, maxy = min(ys) - pad, max(ys) + pad
        # y flip for svg
        w, h = maxx - minx, maxy - miny
        paths = []
        for i, seg in enumerate(payload.get("proposed") or [], 1):
            pts = seg.get("points") or []
            if len(pts) < 2:
                continue
            d = "M " + " L ".join(
                f"{float(p[0]):.2f},{float(maxy + miny - float(p[1])):.2f}" for p in pts
            )
            if len(pts) >= 3:
                d += " Z"
            label = seg.get("label") or str(i)
            color = "#00e5ff" if i % 2 else "#69f0ae"
            cx = sum(float(p[0]) for p in pts) / len(pts)
            cy = sum(float(maxy + miny - float(p[1])) for p in pts) / len(pts)
            paths.append(
                f'<path d="{d}" fill="{color}" fill-opacity="0.22" stroke="{color}" '
                f'stroke-width="1.5"/>'
                f'<text x="{cx:.1f}" y="{cy - 6:.1f}" fill="{color}" '
                f'font-size="12" text-anchor="middle">P{label}</text>'
            )
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx:.1f} {miny:.1f} {w:.1f} {h:.1f}" '
            f'style="background:#0a0a0a">\n'
            f"<!-- proposta agêntica {item} — overlay P# (completar com DXF HI-FI no export) -->\n"
            + "\n".join(paths)
            + "\n</svg>\n"
        )

    spath = prop_dir / f"{item}_qa_proposta.svg"
    spath.write_text(svg, encoding="utf-8")
    print(f"[OK] propose-draw {item} → {jpath.name} + {spath.name}")
    print("[NOTE] Overlay geométrico barato; ideal fundir no N1 SVG estrutural (HI-FI).")
    return 0


def cmd_read_notes(args) -> int:
    pack = _pack_dir(args.pack)
    item = args.item
    p = pack / "pilares" / f"{item}.notes.json"
    if not p.is_file():
        print(f"[empty] {p}")
        return 0
    print(p.read_text(encoding="utf-8"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="QA looping agêntico PIL")
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("write-agent")
    w.add_argument("--pack", required=True)
    w.add_argument("--item", required=True)
    w.add_argument("--verdict", choices=["validou", "invalidou"], required=True)
    w.add_argument("--text", default="")
    w.add_argument("--file", default="")

    p = sub.add_parser("propose-draw")
    p.add_argument("--pack", required=True)
    p.add_argument("--item", required=True)
    p.add_argument("--json", default="")
    p.add_argument("--proposed", default="[]")
    p.add_argument("--note", default="")

    r = sub.add_parser("read-notes")
    r.add_argument("--pack", required=True)
    r.add_argument("--item", required=True)

    args = ap.parse_args()
    if args.cmd == "write-agent":
        return cmd_write_agent(args)
    if args.cmd == "propose-draw":
        return cmd_propose_draw(args)
    if args.cmd == "read-notes":
        return cmd_read_notes(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
