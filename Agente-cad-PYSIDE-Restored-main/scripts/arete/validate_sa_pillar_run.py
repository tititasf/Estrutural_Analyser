"""Valida pack HTML N1 de pilares + re-enrich com motor atual.

Uso:
  py -3.12 scripts/arete/validate_sa_pillar_run.py
  py -3.12 scripts/arete/validate_sa_pillar_run.py --pack PATH
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HTML_ROOT = ROOT / "scripts" / "arete" / "html_fichas" / "Obra_TREINO_1"
DB = Path(r"D:/Agente-cad-PYSIDE/project_data.vision")


def latest_pack() -> Path | None:
    if not HTML_ROOT.is_dir():
        return None
    packs = sorted(
        [p for p in HTML_ROOT.iterdir() if p.is_dir() and "13P" in p.name],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return packs[0] if packs else None


def load_pillars_beams_from_db(project_id: str) -> tuple[list, list]:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    pillars_raw = conn.execute(
        "SELECT name, points_json, sides_data_json, links_json, extra_data_json "
        "FROM pillars WHERE project_id=?",
        (project_id,),
    ).fetchall()
    beams_raw = conn.execute(
        "SELECT name, data_json, sides_data_json, links_json FROM beams WHERE project_id=?",
        (project_id,),
    ).fetchall()
    conn.close()

    pillars, beams = [], []
    for r in pillars_raw:
        try:
            pts = json.loads(r["points_json"] or "[]")
        except Exception:
            pts = []
        try:
            extra = json.loads(r["extra_data_json"] or "{}")
        except Exception:
            extra = {}
        try:
            sides = json.loads(r["sides_data_json"] or "{}")
        except Exception:
            sides = {}
        lajes = extra.get("lajes") or extra.get("lajes_adjacentes") or []
        # lajes_adjacentes may be list of dicts without content_type
        pillars.append({
            "name": r["name"],
            "points": pts,
            "lajes": lajes,
            "sides_data": sides,
            "extra": extra,
            "fields": {
                k: v for k, v in extra.items()
                if str(k).startswith("p_s")
            },
        })
    def _pts_from_beam_data(data: dict) -> list:
        pts = data.get("points") or []
        if len(pts) >= 3:
            return pts
        geom = data.get("geometry") or {}
        if isinstance(geom, dict):
            poly = geom.get("poly") or geom.get("points") or []
            if len(poly) >= 3:
                return poly
            # bbox a partir de segmentos classificados (fundo/lados)
            xs, ys = [], []
            classified = geom.get("classified") or {}
            for key in (
                "seg_bottom", "seg_side_a", "seg_side_b",
                "lv_seg_side_a", "lv_seg_side_b",
            ):
                for seg in classified.get(key) or []:
                    for pt in seg:
                        try:
                            xs.append(float(pt[0]))
                            ys.append(float(pt[1]))
                        except Exception:
                            continue
            if xs and ys:
                return [
                    (min(xs), min(ys)),
                    (max(xs), min(ys)),
                    (max(xs), max(ys)),
                    (min(xs), max(ys)),
                ]
        return []

    for r in beams_raw:
        try:
            data = json.loads(r["data_json"] or "{}")
        except Exception:
            data = {}
        pts = _pts_from_beam_data(data)
        fields = data.get("fields") or {}
        lv_dim = (data.get("geometry") or {}).get("lv_dimension_text")
        lv_txt = lv_dim.get("text") if isinstance(lv_dim, dict) else ""
        dim = fields.get("dimensao") or data.get("dim") or lv_txt or ""
        beams.append({
            "name": r["name"] or data.get("name"),
            "points": pts,
            "dim": dim,
            "fields": fields,
            "is_h": data.get("is_h"),
        })
    return pillars, beams


def html_audit(pack: Path) -> dict:
    out = {
        "n_html": 0,
        "contorno_hits": 0,
        "passa_esquina_hits": 0,
        "chegada_hits": 0,
        "items": [],
    }
    files = sorted(
        p for p in pack.rglob("P*.html")
        if "n3_variants" not in str(p) and p.parent.name != "n3_variants"
    )
    for html in files:
        t = html.read_text(encoding="utf-8", errors="ignore")
        out["n_html"] += 1
        if "Contorno Esquerda" in t or "Contorno Direita" in t:
            out["contorno_hits"] += 1
        if "Esquina AC" in t or "Esquina AD" in t or "Passam — Esquina" in t or "Vigas que Passam" in t:
            out["passa_esquina_hits"] += 1
        if "Chegada 1" in t or "Viga de Chegada" in t or "vigas que chegam" in t.lower():
            out["chegada_hits"] += 1
        # face vals
        faces = re.findall(
            r'class="face-label"[^>]*>(.*?)</div>\s*<div class="face-val">(.*?)</div>',
            t,
            flags=re.S | re.I,
        )
        face_map = {}
        for lab, val in faces:
            lab_c = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", lab)).strip()
            val_c = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", val)).strip()
            face_map[lab_c[:50]] = val_c[:200]
        # mode notes
        modes = re.findall(r'class="mode-title[^"]*"[^>]*>(.*?)</div>', t, flags=re.S)
        modes = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m)).strip() for m in modes]
        # vigas text in validation
        vigas = re.findall(
            r"(Viga:\s*[^·<\n]+(?:·\s*dim:\s*[^<\n]+)?)",
            t,
        )
        if html.stem in ("P1", "P2", "P3", "P10", "P15", "P18", "P27") or len(out["items"]) < 6:
            out["items"].append({
                "item": html.stem,
                "path": str(html.relative_to(pack)),
                "faces": face_map,
                "modes": modes[:10],
                "vigas_mentions": vigas[:12],
                "has_contorno": "Contorno" in t and ("Esquerda" in t or "Direita" in t),
            })
    return out


def enrich_audit(pillars: list, beams: list) -> dict:
    from src.core.pillar_face_beams import enrich_pillar_report_with_beams

    report = {}
    for p in pillars:
        nm = str(p.get("name") or "").strip()
        if not nm:
            continue
        report[nm] = {
            "name": nm,
            "points": p.get("points") or [],
            "lajes": list(p.get("lajes") or []),
        }
    enrich_pillar_report_with_beams(report, beams)

    n = len(report)
    n_fb = sum(1 for e in report.values() if e.get("face_beams"))
    n_passa = 0
    n_para = 0
    n_dual_face = 0  # face with both esq and dir
    corner_c = Counter()
    samples = []
    for nm, e in sorted(report.items()):
        fb = e.get("face_beams") or {}
        dual = 0
        face_summary = {}
        for fid, d in fb.items():
            pe, pd = d.get("passa_esq"), d.get("passa_dir")
            if pe:
                n_passa += 1
                corner_c[d.get("corner_esq") or f"{fid}e"] += 1
            if pd:
                n_passa += 1
                corner_c[d.get("corner_dir") or f"{fid}d"] += 1
            if pe and pd:
                dual += 1
                n_dual_face += 1
            if d.get("para"):
                n_para += len(d["para"])
            face_summary[fid] = {
                "esq": pe,
                "dir": pd,
                "para": d.get("para") or [],
                "corners": (d.get("corner_esq"), d.get("corner_dir")),
            }
        if nm in ("P1", "P2", "P3", "P10", "P15", "P18", "P27") or (
            len(samples) < 10 and (n_passa or n_para)
        ):
            samples.append({
                "name": nm,
                "faces": face_summary,
                "viga_que_passa": e.get("viga_que_passa"),
                "viga_que_para": e.get("viga_que_para"),
                "lajes": e.get("lajes"),
            })
    return {
        "n_pillars": n,
        "n_with_face_beams": n_fb,
        "n_passa_slots": n_passa,
        "n_para_entries": n_para,
        "n_faces_with_both_corners": n_dual_face,
        "corners": dict(corner_c),
        "samples": samples,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=None)
    ap.add_argument(
        "--project-id",
        default="dd238e47-1dc6-4f63-a760-4e7ce19a7386",
    )
    args = ap.parse_args()
    pack = Path(args.pack) if args.pack else latest_pack()
    print("PACK", pack)

    html = html_audit(pack) if pack else {}
    print("\n=== HTML N1 AUDIT ===")
    print(json.dumps({k: v for k, v in html.items() if k != "items"}, indent=2))
    for it in html.get("items") or []:
        print(f"\n--- {it['item']} ({it['path']}) contorno={it['has_contorno']} ---")
        for k, v in (it.get("faces") or {}).items():
            print(f"  FACE {k}: {v[:120]}")
        print("  modes:", it.get("modes"))
        print("  vigas:", it.get("vigas_mentions")[:8])

    print("\n=== ENRICH MOTOR ATUAL (DB pillars+beams) ===")
    pillars, beams = load_pillars_beams_from_db(args.project_id)
    print(f"DB pillars={len(pillars)} beams={len(beams)}")
    if not pillars:
        # try other project ids for TREINO 13P
        conn = sqlite3.connect(str(DB))
        ids = conn.execute(
            "SELECT id FROM projects WHERE work_name='Obra_TREINO_1' AND name LIKE '%13P%'"
        ).fetchall()
        conn.close()
        for (pid,) in ids:
            pillars, beams = load_pillars_beams_from_db(pid)
            print(f"try {pid}: pillars={len(pillars)} beams={len(beams)}")
            if pillars:
                args.project_id = pid
                break

    enrich = enrich_audit(pillars, beams) if pillars else {"error": "no pillars"}
    print(json.dumps({k: v for k, v in enrich.items() if k != "samples"}, indent=2, default=str))
    for s in enrich.get("samples") or []:
        print(f"\n### {s['name']}")
        print("  global passa", s.get("viga_que_passa"))
        print("  global para", s.get("viga_que_para"))
        for fid, d in (s.get("faces") or {}).items():
            if d.get("esq") or d.get("dir") or d.get("para"):
                print(f"  {fid} corners={d['corners']} esq={d['esq']} dir={d['dir']} para={d['para']}")
        lajes = s.get("lajes") or []
        if lajes:
            print("  lajes", [
                (le.get("side"), le.get("laje"), le.get("content_type"))
                for le in lajes if isinstance(le, dict)
            ][:8])

    # verdict
    ok_html = (
        html.get("n_html", 0) > 0
        and html.get("contorno_hits", 0) == 0
        and html.get("passa_esquina_hits", 0) >= html.get("n_html", 1) * 0.5
    )
    ok_enrich = (
        enrich.get("n_pillars", 0) > 0
        and enrich.get("n_with_face_beams", 0) >= enrich.get("n_pillars", 1) * 0.8
        and enrich.get("n_passa_slots", 0) > 0
    )
    print("\n=== VERDICT ===")
    print("HTML contorno_eliminado:", html.get("contorno_hits") == 0, "passa_labels:", ok_html)
    print("ENRICH face_beams:", ok_enrich, enrich.get("n_passa_slots"), "passa slots /", enrich.get("n_para_entries"), "chegadas")
    print("OVERALL:", "PASS" if (ok_html and ok_enrich) else "PARTIAL/REVIEW")

    out = ROOT / "scripts" / "arete" / "relatorios" / "sa_pillar_headless_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "pack": str(pack),
                "project_id": args.project_id,
                "html": html,
                "enrich": enrich,
                "ok_html": ok_html,
                "ok_enrich": ok_enrich,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print("wrote", out)


if __name__ == "__main__":
    main()
