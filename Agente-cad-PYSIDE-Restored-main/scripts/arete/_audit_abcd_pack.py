"""Audita tabelas ABCD de um pack de pilares (sem N1, rápido).

Uso:
  py -3.12 scripts/arete/_audit_abcd_pack.py --pack 1 --size 10
  py -3.12 scripts/arete/_audit_abcd_pack.py --items P1 P2 P3
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core.niveis_extractor import get_pavimento_niveis_abs  # noqa: E402
from src.core.pillar_abcd_tables import build_abcd_tables_from_pillar  # noqa: E402

DB_DEFAULT = ROOT.parent / "project_data.vision"
PID_DEFAULT = "dd238e47-1dc6-4f63-a760-4e7ce19a7386"


def _natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


def _load_maps(conn, pid: str):
    slab_h, slab_n, slab_pts = {}, {}, {}
    for r in conn.execute(
        "SELECT name, points_json, extra_data_json FROM slabs WHERE project_id=?",
        (pid,),
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
        (pid,),
    ):
        d = json.loads(r["data_json"] or "{}")
        d["name"] = r["name"]
        beams.append(d)
    return slab_h, slab_n, slab_pts, beams


def _parse_cm(s) -> float | None:
    if s in (None, "", "—", "-"):
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(s))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return None


def _face_len_cm(pts, orientation: str, fid: str) -> float | None:
    if not pts:
        return None
    xs = [float(p[0]) for p in pts]
    ys = [float(p[1]) for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    if orientation == "vertical":
        return h if fid in ("A", "B") else w
    return w if fid in ("A", "B") else h


def audit_one(pillar, tables, *, slab_pts) -> list[dict]:
    """Heurísticas genéricas (sem hardcode de item)."""
    issues = []
    faces = tables.get("faces") or {}
    orient = tables.get("orientation") or pillar.get("orientation") or "vertical"
    pts = pillar.get("points") or []

    # 1) dualidade AC↔CA / BC↔CB: se chega A@AC com nome X, C deve ter passa@CA com X
    for face_long, canto_long, face_short, canto_short in (
        ("A", "AC", "C", "CA"),
        ("B", "BC", "C", "CB"),
    ):
        chega = [
            r
            for r in (faces.get(face_long, {}).get("chega") or [])
            if (r.get("nome") or "") not in ("", "—", "nenhuma")
            and (r.get("canto") or "").upper() == canto_long
        ]
        passa = [
            r
            for r in (faces.get(face_short, {}).get("passa") or [])
            if (r.get("nome") or "") not in ("", "—", "nenhuma")
            and (r.get("canto") or "").upper() == canto_short
        ]
        for r in chega:
            nomes_p = {(x.get("nome") or "").strip() for x in passa}
            if (r.get("nome") or "").strip() not in nomes_p:
                issues.append(
                    {
                        "code": "DUALIDADE_MISSING_PASSA",
                        "sev": "WARN",
                        "msg": (
                            f"chega {face_long}@{canto_long} {r.get('nome')} "
                            f"sem passa {face_short}@{canto_short}"
                        ),
                    }
                )

    # 2) chega AC/BC: d.esq+d.dir+width ≈ face_len; simetria banda se ambos top
    top_cheg = []
    for fid, canto in (("A", "AC"), ("B", "BC")):
        for r in faces.get(fid, {}).get("chega") or []:
            if (r.get("nome") or "") in ("", "—", "nenhuma"):
                continue
            if (r.get("canto") or "").upper() != canto:
                continue
            de = _parse_cm(r.get("dist_esq"))
            dd = _parse_cm(r.get("dist_dir"))
            fl = _face_len_cm(pts, orient, fid)
            if de is None or dd is None or fl is None:
                issues.append(
                    {
                        "code": "CHEGA_DIST_MISSING",
                        "sev": "WARN",
                        "msg": f"{fid}@{canto} {r.get('nome')} dist missing "
                        f"({r.get('dist_esq')}/{r.get('dist_dir')})",
                    }
                )
                continue
            band = fl - de - dd  # width occupied
            top_cheg.append((fid, r, de, dd, fl, band))
            # occupied width should be positive and < face
            if band < 1.5 or band > fl - 1.0:
                issues.append(
                    {
                        "code": "CHEGA_BAND_ODD",
                        "sev": "WARN",
                        "msg": (
                            f"{fid}@{canto} {r.get('nome')} band={band:.1f} "
                            f"face={fl:.1f} ({de}/{dd}) dim={r.get('dim')}"
                        ),
                    }
                )
            # se dim 1º nº ≈ face_len residual classico (19 de 19/66 com face 66)
            dim = str(r.get("dim") or "")
            m = re.match(r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)", dim)
            if m:
                a = float(m.group(1).replace(",", "."))
                b = float(m.group(2).replace(",", "."))
                # se 2º ≈ face longa e 1º ≈ pillar short, band não deve ser = a
                if fl and abs(b - fl) <= 2.0 and abs(band - a) <= 0.6:
                    issues.append(
                        {
                            "code": "CHEGA_USED_SECTION_AS_BAND",
                            "sev": "FAIL",
                            "msg": (
                                f"{fid}@{canto} {r.get('nome')} band={band:.0f} "
                                f"parece 1º nº da seção {dim} (face={fl:.0f})"
                            ),
                        }
                    )

    # se A e B ambos top chega: bandas devem ser ~iguais
    if len(top_cheg) >= 2:
        bands = [t[5] for t in top_cheg]
        if max(bands) - min(bands) > 1.5:
            issues.append(
                {
                    "code": "TOP_BAND_ASYMMETRY",
                    "sev": "FAIL",
                    "msg": (
                        "faixa topo A/B diverge: "
                        + ", ".join(f"{t[0]}={t[5]:.1f}" for t in top_cheg)
                    ),
                }
            )

    # 3) laje d.esq/d.dir: se tem laje e dist, de+dd <= face
    for fid in "ABCD":
        fl = _face_len_cm(pts, orient, fid)
        for r in faces.get(fid, {}).get("lajes") or []:
            if (r.get("nome") or "") in ("", "—", "nenhuma"):
                continue
            de = _parse_cm(r.get("dist_esq"))
            dd = _parse_cm(r.get("dist_dir"))
            if de is None or dd is None or fl is None:
                continue
            if de + dd > fl + 1.5:
                issues.append(
                    {
                        "code": "LAJE_DIST_OVERFLOW",
                        "sev": "WARN",
                        "msg": f"laje {fid} {r.get('nome')} {de}+{dd}>{fl:.1f}",
                    }
                )

    # 4) passa não deve ter dist numérica
    for fid in "ABCD":
        for r in faces.get(fid, {}).get("passa") or []:
            if r.get("dist_esq") not in ("", "—", None) or r.get("dist_dir") not in (
                "",
                "—",
                None,
            ):
                if r.get("dist_esq") not in ("—",) or r.get("dist_dir") not in ("—",):
                    if (r.get("nome") or "") not in ("", "—", "nenhuma"):
                        issues.append(
                            {
                                "code": "PASSA_HAS_DIST",
                                "sev": "INFO",
                                "msg": f"passa {fid} {r.get('nome')} "
                                f"dist={r.get('dist_esq')}/{r.get('dist_dir')}",
                            }
                        )

    # 5) empty face_beams
    fb = pillar.get("face_beams") or {}
    if not fb:
        issues.append(
            {"code": "NO_FACE_BEAMS", "sev": "FAIL", "msg": "face_beams vazio"}
        )

    return issues


def summarize_face(fid: str, face: dict) -> str:
    parts = []
    for kind in ("lajes", "passa", "chega", "interior"):
        rows = [
            r
            for r in (face.get(kind) or [])
            if (r.get("nome") or "") not in ("", "—", "nenhuma")
        ]
        if not rows:
            continue
        bits = []
        for r in rows:
            bit = r.get("nome") or "?"
            if r.get("dim") not in ("", "—", None):
                bit += f" {r['dim']}"
            if r.get("canto") not in ("", "—", None):
                bit += f"@{r['canto']}"
            if kind != "passa":
                de, dd = r.get("dist_esq"), r.get("dist_dir")
                if de not in ("", "—", None) or dd not in ("", "—", None):
                    bit += f" [{de}/{dd}]"
            bits.append(bit)
        parts.append(f"{kind[0].upper()}:{','.join(bits)}")
    return " | ".join(parts) if parts else "(vazio)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", default=PID_DEFAULT)
    ap.add_argument("--db", default=str(DB_DEFAULT))
    ap.add_argument("--obra", default="Obra_TREINO_1")
    ap.add_argument("--pav", default="13_PAV")
    ap.add_argument("--pack", type=int, default=1, help="1-based pack index")
    ap.add_argument("--size", type=int, default=10)
    ap.add_argument("--items", nargs="*", help="override: nomes explícitos")
    ap.add_argument("--export", action="store_true", help="também exporta HTML pack")
    ap.add_argument("--skip-n1", action="store_true", default=True)
    args = ap.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    slab_h, slab_n, slab_pts, beams = _load_maps(conn, args.project_id)
    niveis = get_pavimento_niveis_abs(args.obra, args.pav) or {
        "chegada_abs": 852.19,
        "saida_abs": 848.98,
        "altura_cm": 321.0,
    }
    nivel_v = f"{niveis.get('chegada_abs')}cm"

    pillars = []
    for r in conn.execute(
        "SELECT name, points_json, extra_data_json, type FROM pillars "
        "WHERE project_id=? ORDER BY name",
        (args.project_id,),
    ):
        pts = json.loads(r["points_json"] or "[]")
        extra = json.loads(r["extra_data_json"] or "{}") if r["extra_data_json"] else {}
        if not isinstance(extra, dict):
            extra = {}
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            orient = (
                "vertical"
                if (max(ys) - min(ys)) > (max(xs) - min(xs))
                else "horizontal"
            )
        except Exception:
            orient = "vertical"
        pillars.append(
            {
                "name": r["name"],
                "points": pts,
                "orientation": orient,
                "lajes": extra.get("lajes_adjacentes") or [],
                "face_beams": extra.get("face_beams") or {},
                "type": r["type"] if "type" in r.keys() else None,
            }
        )
    pillars.sort(key=lambda p: _natural_key(p["name"]))
    all_names = [p["name"] for p in pillars]
    print(f"[ALL] {len(all_names)} pilares: {', '.join(all_names)}")

    if args.items:
        wanted = {str(x).strip().upper() for x in args.items}
        pack = [p for p in pillars if str(p["name"]).strip().upper() in wanted]
    else:
        start = (args.pack - 1) * args.size
        end = start + args.size
        pack = pillars[start:end]
        print(
            f"[PACK {args.pack}] size={args.size} slice [{start}:{end}] "
            f"→ {len(pack)} itens: {', '.join(p['name'] for p in pack)}"
        )

    if not pack:
        print("[ERR] pack vazio")
        return 2

    n_fail = n_warn = 0
    rows_out = []
    for p in pack:
        tables = build_abcd_tables_from_pillar(
            p,
            slab_height_map=slab_h,
            slab_nivel_map=slab_n,
            slab_points_map=slab_pts,
            beams=beams,
            nivel_viga_default=nivel_v,
        )
        issues = audit_one(p, tables, slab_pts=slab_pts)
        fails = [i for i in issues if i["sev"] == "FAIL"]
        warns = [i for i in issues if i["sev"] == "WARN"]
        n_fail += len(fails)
        n_warn += len(warns)
        print(f"\n=== {p['name']} ({p['orientation']}) ===")
        for fid in "ABCD":
            print(f"  {fid}: {summarize_face(fid, tables['faces'][fid])}")
        if issues:
            for i in issues:
                print(f"  [{i['sev']}] {i['code']}: {i['msg']}")
        else:
            print("  [OK] sem issues heurísticas")
        rows_out.append(
            {
                "name": p["name"],
                "orientation": p["orientation"],
                "issues": issues,
                "faces": {
                    fid: summarize_face(fid, tables["faces"][fid]) for fid in "ABCD"
                },
            }
        )

    print(
        f"\n[SUMMARY] pack={args.pack if not args.items else 'custom'} "
        f"n={len(pack)} FAIL={n_fail} WARN={n_warn}"
    )

    out_dir = (
        ROOT
        / "scripts"
        / "arete"
        / "relatorios"
        / f"abcd_pack{args.pack if not args.items else 'custom'}_{args.obra}_{args.pav}.json"
    )
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    out_dir.write_text(
        json.dumps(
            {
                "pack": args.pack,
                "size": args.size,
                "items": [p["name"] for p in pack],
                "n_fail": n_fail,
                "n_warn": n_warn,
                "rows": rows_out,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[OK] relatório {out_dir}")

    if args.export:
        # reusa export script via subprocess-like import
        from scripts.arete import export_pilares_abcd_fichas as exp  # type: ignore

        # call main with sys.argv override
        names = [p["name"] for p in pack]
        sys.argv = [
            "export_pilares_abcd_fichas.py",
            "--project-id",
            args.project_id,
            "--db",
            args.db,
            "--obra",
            args.obra,
            "--pav",
            args.pav,
            "--item",
            *names,
            "--skip-n1",
        ]
        print(f"[EXPORT] {names} skip_n1…")
        return exp.main()

    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
