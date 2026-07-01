#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch ARETE LAJ para Obra_TREINO_1 / 13_PAV.

Gera N4 a partir do motor reverso de cada recorte LAJ e valida:
- diff canonico de conteudo;
- marco fisico absoluto do contorno em coordenadas STOG.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import ezdxf

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
DADOS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
OBRA_NAME = "Obra_TREINO_1"
PAVIMENTO = "13_PAV"

sys.path.insert(0, str(SCRIPTS))

from arete_lj_canonico import canonical, diff, render_side_by_side  # noqa: E402
from motor_reverso_laj import extrair_ficha_laje  # noqa: E402


def _round(v: float) -> float:
    return round(float(v), 2)


def _item_sort(eid: str) -> tuple[int, str]:
    digits = "".join(ch for ch in eid if ch.isdigit())
    return (int(digits or 0), eid)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def infer_pavimento_from_path(path: Path) -> str:
    folder = path.parent.name
    norm = unicodedata.normalize("NFKD", folder)
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    m = re.search(r"(\d+)\s*[oO°]?\s*PAV", norm, re.IGNORECASE)
    if m:
        return f"{m.group(1)}_PAV"
    upper = norm.upper()
    if "TIPO" in upper:
        return "TIPO"
    if "TERREO" in upper:
        return "TERREO"
    if "COB" in upper:
        return "COBERTURA"
    return ""


def db_items() -> list[dict]:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    items: dict[str, dict] = {}
    cur.execute(
        "SELECT elemento_id, recorte_path FROM reverse_eng_fichas "
        "WHERE obra_name=? AND pavimento=? AND classe='LAJ' "
        "ORDER BY elemento_id",
        (OBRA_NAME, PAVIMENTO),
    )
    for eid, path in cur.fetchall():
        items[str(eid)] = {"id": str(eid), "db_recorte": path}
    cur.execute(
        "SELECT elemento_id, recorte_path FROM reverse_eng_recortes "
        "WHERE obra_name=? AND classe='LAJ' AND status='aprovado' "
        "ORDER BY elemento_id, created_at DESC",
        (OBRA_NAME,),
    )
    for eid, path in cur.fetchall():
        p = Path(path or "")
        if not eid or not p.exists() or infer_pavimento_from_path(p) != PAVIMENTO:
            continue
        items.setdefault(str(eid), {"id": str(eid), "db_recorte": str(p)})
    conn.close()
    return sorted(items.values(), key=lambda r: _item_sort(r["id"]))


def preferred_recorte(eid: str, db_path: str | None) -> Path | None:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        "SELECT recorte_path, created_at FROM reverse_eng_recortes "
        "WHERE obra_name=? AND classe='LAJ' AND elemento_id=? AND status='aprovado' "
        "ORDER BY created_at DESC",
        (OBRA_NAME, eid),
    )
    rows = cur.fetchall()
    conn.close()

    approved: list[Path] = []
    for recorte_path, _created_at in rows:
        p = Path(recorte_path or "")
        if p.exists() and infer_pavimento_from_path(p) == PAVIMENTO:
            approved.append(p)
    if approved:
        return approved[0]
    return None


def clean_ficha(ficha: dict, eid: str) -> dict:
    keep_private = {"_hlaz", "_stog_pose"}
    clean = {
        k: v for k, v in ficha.items()
        if not k.startswith("_") or k in keep_private
    }
    clean["nome"] = eid
    clean["pavimento"] = PAVIMENTO
    return clean

def _canonical_segments(total: float, lines: list[dict]) -> list[float]:
    positions = [0.0] + sorted(float(item["value"]) for item in lines) + [float(total)]
    return [
        round(round((positions[index + 1] - positions[index]) * 2) / 2, 1)
        for index in range(len(positions) - 1)
    ]


def abs_outline_bbox(ficha: dict) -> tuple[float, float, float, float] | None:
    coords = ficha.get("coordenadas") or []
    if len(coords) < 3:
        return None
    xs = [float(c[0]) for c in coords]
    ys = [float(c[1]) for c in coords]
    raw_x0 = min(xs)
    raw_y0 = min(ys)
    pose = ficha.get("_stog_pose") or {}
    off_x = float(pose.get("x", 0.0)) if pose and abs(raw_x0) <= 0.5 else 0.0
    off_y = float(pose.get("y", 0.0)) if pose and abs(raw_y0) <= 0.5 else 0.0
    abs_xs = [x + off_x for x in xs]
    abs_ys = [y + off_y for y in ys]
    return (_round(min(abs_xs)), _round(min(abs_ys)), _round(max(abs_xs)), _round(max(abs_ys)))


def close_bbox(a, b, tol: float = 0.5) -> bool:
    if not a or not b:
        return False
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def text_summary(path: Path) -> dict:
    doc = ezdxf.readfile(str(path))
    layers = Counter()
    types = Counter()
    texts = []
    for e in doc.modelspace():
        layers[e.dxf.layer] += 1
        types[e.dxftype()] += 1
        if e.dxftype() == "TEXT":
            texts.append(str(e.dxf.text))
        elif e.dxftype() == "MTEXT":
            texts.append(str(getattr(e, "text", "")))
    return {
        "layers": dict(layers),
        "types": dict(types),
        "texts": texts,
        "has_aux00": any(str(k).upper() == "AUX00" for k in layers),
        "has_c_equals": any(t.strip().lower().startswith("c=") for t in texts),
    }


def generate_n4(eid: str, ficha: dict, out_dir: Path) -> Path:
    obra = DADOS / OBRA_NAME
    json_dir = obra / "Fase-4_Sincronizacao" / "JSON_Lajes"
    json_dir.mkdir(parents=True, exist_ok=True)
    temp_item = f"{eid}_arete_batch"
    temp_json = json_dir / f"{temp_item}.json"
    temp_json.write_text(json.dumps(ficha, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        cmd = [
            sys.executable,
            str(SCRIPTS / "gerar_lj_dxf_stog.py"),
            "--obra",
            str(obra),
            "--mode",
            "planta",
            "--item",
            temp_item,
        ]
        proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError((proc.stdout + "\n" + proc.stderr)[-4000:])
        generated = obra / "Fase-6_Execucao_CAD" / f"LJ_preview_{temp_item}.dxf"
        if not generated.exists():
            raise RuntimeError(f"DXF nao gerado: {generated}")
        out_dir.mkdir(parents=True, exist_ok=True)
        final = out_dir / f"LJ_preview_{eid}.dxf"
        shutil.move(str(generated), str(final))
        return final
    finally:
        temp_json.unlink(missing_ok=True)


def make_contact_sheet(pngs: list[Path], out_path: Path) -> None:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return
    if not pngs:
        return
    thumbs = []
    for p in pngs:
        im = Image.open(p).convert("RGB")
        im.thumbnail((480, 220))
        canvas = Image.new("RGB", (500, 255), (10, 10, 20))
        canvas.paste(im, ((500 - im.width) // 2, 5))
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 232), p.stem.replace("ARETE_LJ_", ""), fill=(235, 235, 245))
        thumbs.append(canvas)
    cols = 3
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 500, rows * 255), (10, 10, 20))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % cols) * 500, (i // cols) * 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def render_overlay(recorte: Path, n4: Path, out_png: Path) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False

    def _segments(path: Path):
        doc = ezdxf.readfile(str(path))
        segs = []
        pts = []
        for e in doc.modelspace():
            try:
                if e.dxftype() == "LINE":
                    s = e.dxf.start
                    t = e.dxf.end
                    a = (float(s.x), float(s.y))
                    b = (float(t.x), float(t.y))
                    segs.append((a, b, e.dxf.layer))
                    pts.extend([a, b])
                elif e.dxftype() in {"LWPOLYLINE", "POLYLINE"}:
                    if e.dxftype() == "LWPOLYLINE":
                        poly = [(float(x), float(y)) for x, y, *_ in e.get_points()]
                    else:
                        poly = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
                    if len(poly) > 1:
                        if getattr(e, "closed", False) or bool(getattr(e, "is_closed", False)):
                            poly = poly + [poly[0]]
                        for a, b in zip(poly, poly[1:]):
                            segs.append((a, b, e.dxf.layer))
                        pts.extend(poly)
            except Exception:
                pass
        return segs, pts

    ref_segs, ref_pts = _segments(recorte)
    n4_segs, n4_pts = _segments(n4)
    if not ref_pts or not n4_pts:
        return False
    pts = ref_pts + n4_pts
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = 35.0

    fig, ax = plt.subplots(figsize=(8, 5), facecolor="#0b0b16")
    ax.set_facecolor("#202830")
    for a, b, layer in ref_segs:
        color = "#19ff49" if str(layer) in {"3", "Painéis", "Paineis", "Hachura", "4"} else "#56616c"
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=0.8, alpha=0.45, zorder=1)
    for a, b, _layer in n4_segs:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#ff2d55", lw=1.8, alpha=0.9, zorder=5)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_title(f"{recorte.stem.split('_')[1]} overlay CAD", color="white", fontsize=10)
    ax.tick_params(colors="#b9c0ca", labelsize=6)
    ax.grid(color="#39424d", linewidth=0.4, alpha=0.35)
    for spine in ax.spines.values():
        spine.set_color("#606b77")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_png, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    return True


def run(out_root: Path) -> dict:
    n4_dir = out_root / "n4"
    png_dir = out_root / "png"
    json_dir = out_root / "json"
    results = []
    pngs = []

    for row in db_items():
        eid = row["id"]
        recorte = preferred_recorte(eid, row.get("db_recorte"))
        item = {"id": eid, "recorte": str(recorte) if recorte else None}
        try:
            if not recorte:
                item.update({"resultado": "BLOCKED", "erro": "sem recorte aprovado"})
                results.append(item)
                print(f"BLOCK {eid} sem recorte aprovado", flush=True)
                continue
            ref_ficha = extrair_ficha_laje(str(recorte), eid, OBRA_NAME)
            n4 = generate_n4(eid, clean_ficha(ref_ficha, eid), n4_dir)
            n4_ficha = extrair_ficha_laje(str(n4), eid, OBRA_NAME)
            ref_fc = canonical(recorte)
            ref_fc["outline"] = {
                "comprimento": round(float(ref_ficha.get("comprimento") or 0) * 2) / 2,
                "largura": round(float(ref_ficha.get("largura") or 0) * 2) / 2,
                "coordenadas": ref_ficha.get("coordenadas") or [],
            }
            ref_fc["linhas_verticais"] = ref_ficha.get("linhas_verticais") or []
            ref_fc["linhas_horizontais"] = ref_ficha.get("linhas_horizontais") or []
            ref_fc["cotas_valor"] = sorted(
                _canonical_segments(ref_ficha.get("comprimento") or 0, ref_fc["linhas_verticais"])
                + _canonical_segments(ref_ficha.get("largura") or 0, ref_fc["linhas_horizontais"])
            )
            n4_fc = canonical(n4)
            d = diff(ref_fc, n4_fc)
            ref_bbox = abs_outline_bbox(ref_ficha)
            n4_bbox = abs_outline_bbox(n4_ficha)
            marco_ok = close_bbox(ref_bbox, n4_bbox)
            png = png_dir / f"ARETE_LJ_{eid}.png"
            render_side_by_side(recorte, n4, png)
            if png.exists():
                pngs.append(png)
            summary = text_summary(n4)
            item.update({
                "resultado": "PASS" if d["pass"] and marco_ok and not summary["has_aux00"] and not summary["has_c_equals"] else "FAIL",
                "conteudo_pass": bool(d["pass"]),
                "marco_pass": marco_ok,
                "ref_bbox_abs": ref_bbox,
                "n4_bbox_abs": n4_bbox,
                "comprimento": ref_ficha.get("comprimento"),
                "largura": ref_ficha.get("largura"),
                "linhas_verticais": ref_ficha.get("linhas_verticais"),
                "linhas_horizontais": ref_ficha.get("linhas_horizontais"),
                "hlaz": ref_ficha.get("_hlaz"),
                "stog_pose": ref_ficha.get("_stog_pose"),
                "n4": str(n4),
                "recorte_sha256": file_sha256(recorte),
                "n4_sha256": file_sha256(n4),
                "png": str(png),
                "diffs": d["diffs"],
                "n4_has_aux00": summary["has_aux00"],
                "n4_has_c_equals": summary["has_c_equals"],
                "n4_texts": summary["texts"],
            })
        except Exception as exc:
            item.update({"resultado": "ERROR", "erro": str(exc)})
        results.append(item)
        print(f"{item['resultado']:>5} {eid} conteudo={item.get('conteudo_pass')} marco={item.get('marco_pass')} recorte={Path(item['recorte']).name if item.get('recorte') else '-'}", flush=True)

    passed = sum(1 for r in results if r["resultado"] == "PASS")
    blocked = sum(1 for r in results if r["resultado"] == "BLOCKED")
    report = {
        "obra": OBRA_NAME,
        "pavimento": PAVIMENTO,
        "total": len(results),
        "pass": passed,
        "blocked": blocked,
        "fail": len(results) - passed,
        "items": results,
    }
    json_dir.mkdir(parents=True, exist_ok=True)
    report_path = json_dir / "arete_lj_13pav_batch_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    make_contact_sheet(pngs, out_root / "ARETE_LJ_13PAV_contact_sheet.png")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="D:/Agente-cad-PYSIDE/test_output/arete_lj/13_PAV_batch")
    args = ap.parse_args()
    report = run(Path(args.out))
    print(json.dumps({
        "obra": report["obra"],
        "pavimento": report["pavimento"],
        "total": report["total"],
        "pass": report["pass"],
        "fail": report["fail"],
        "out": args.out,
    }, ensure_ascii=False, indent=2))
    return 0 if report["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
