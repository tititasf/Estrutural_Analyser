#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loop headless de validacao dos recortes LAJ da engenharia reversa.

Roda o RecorteMotor LAJ sobre o DXF de engenharia reversa, extrai fichas dos
recortes candidatos e compara com os recortes N2 aprovados/humanos.
Nao grava no banco e nao sobrescreve os recortes aprovados.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.core.recorte_motor import RecorteMotor  # noqa: E402
from scripts.arete_lj_batch_13pav import (  # noqa: E402
    DB_PATH,
    OBRA_NAME,
    PAVIMENTO,
    db_items,
    preferred_recorte,
)
from scripts.arete_lj_canonico import canonical, diff, render_side_by_side  # noqa: E402
from scripts.motor_reverso_laj import extrair_ficha_laje  # noqa: E402


DADOS = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
DEFAULT_SOURCE = (
    DADOS
    / OBRA_NAME
    / "Fase-1_Ingestao"
    / "Projetos_Finalizados_para_Engenharia_Reversa"
    / "ALIMONTI - PARAISO - 13° PAV.- LJ - R00.dxf"
)
DEFAULT_OUT = Path("D:/Agente-cad-PYSIDE/validacao_visual/engrev_laj_recorte_loop")


def _item_sort(eid: str) -> tuple[int, str]:
    digits = "".join(ch for ch in str(eid) if ch.isdigit())
    return (int(digits or 0), str(eid))


def _norm_text(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in norm if not unicodedata.combining(c)).upper()


def infer_pavimento_from_path(path: Path) -> str:
    norm = _norm_text(path.parent.name)
    import re

    m = re.search(r"(\d+)\s*(?:°|O|º)?\s*PAV", norm)
    if m:
        return f"{m.group(1)}_PAV"
    if "TIPO" in norm:
        return "TIPO"
    if "TERREO" in norm:
        return "TERREO"
    if "COB" in norm:
        return "COBERTURA"
    return ""


def _approved_items() -> list[dict[str, Any]]:
    rows = []
    for row in db_items():
        eid = str(row["id"])
        recorte = preferred_recorte(eid, row.get("db_recorte"))
        if recorte and recorte.exists() and infer_pavimento_from_path(recorte) == PAVIMENTO:
            rows.append({"id": eid, "approved": recorte})
    return sorted(rows, key=lambda r: _item_sort(r["id"]))


def _bbox_from_canonical(fc: dict) -> tuple[float, float] | None:
    outline = fc.get("outline") or {}
    try:
        return (float(outline.get("comprimento")), float(outline.get("largura")))
    except Exception:
        return None


def _score_diff(ref_fc: dict, cand_fc: dict) -> tuple[int, list[str]]:
    d = diff(ref_fc, cand_fc)
    bad = d.get("diffs") or {}
    if not bad:
        return 100, []
    weights = {
        "outline": 50,
        "linhas_verticais": 15,
        "linhas_horizontais": 15,
        "hlaz": 10,
        "cotas_valor": 5,
        "obstaculos": 5,
    }
    penalty = sum(weights.get(k, 5) for k in bad)
    return max(0, 100 - penalty), sorted(bad.keys())


def _geometry_score(ref_fc: dict, cand_fc: dict) -> tuple[int, list[str]]:
    ref = ref_fc.get("outline") or {}
    cand = cand_fc.get("outline") or {}
    gaps = []
    try:
        rw = float(ref.get("comprimento") or 0)
        rh = float(ref.get("largura") or 0)
        cw = float(cand.get("comprimento") or 0)
        ch = float(cand.get("largura") or 0)
    except Exception:
        return 0, ["outline_parse"]
    if rw <= 0 or rh <= 0 or cw <= 0 or ch <= 0:
        return 0, ["outline_missing"]

    dw = abs(rw - cw)
    dh = abs(rh - ch)
    if dw > 1.5:
        gaps.append("comprimento")
    if dh > 1.5:
        gaps.append("largura")

    area_ref = rw * rh
    area_cand = cw * ch
    area_delta = abs(area_ref - area_cand) / max(area_ref, 1.0)
    if area_delta > 0.01:
        gaps.append("area")

    excess_w = max(0.0, dw - 1.5)
    excess_h = max(0.0, dh - 1.5)
    excess_area = max(0.0, area_delta - 0.01)
    penalty = min(100, int(round(excess_w * 8 + excess_h * 8 + excess_area * 1000)))
    return max(0, 100 - penalty), gaps


def _read_db_confidence(path: Path) -> float | None:
    if not Path(DB_PATH).exists():
        return None
    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            "SELECT confidence FROM reverse_eng_recortes WHERE recorte_path=? ORDER BY id DESC LIMIT 1",
            (str(path),),
        ).fetchone()
        if row and row[0] is not None:
            return float(row[0])
    finally:
        conn.close()
    return None


def run(source: Path, out_root: Path, *, keep_existing: bool = False, render_limit: int = 12) -> dict[str, Any]:
    out_root.mkdir(parents=True, exist_ok=True)
    motor_dir = out_root / "motor_recortes"
    if motor_dir.exists() and not keep_existing:
        shutil.rmtree(motor_dir)
    motor_dir.mkdir(parents=True, exist_ok=True)

    motor = RecorteMotor(str(source), er_type="LAJ")
    motor_results = motor.run(motor_dir, db_path=None, overwrite=True)
    motor_by_id = {str(r["elemento_id"]): Path(r["recorte_path"]) for r in motor_results}

    approved = _approved_items()
    items = []
    pass_count = 0
    near_count = 0
    missing_count = 0
    png_dir = out_root / "png"
    png_count = 0

    for row in approved:
        eid = row["id"]
        ref_path = row["approved"]
        cand_path = motor_by_id.get(eid)
        item: dict[str, Any] = {
            "id": eid,
            "approved_recorte": str(ref_path),
            "motor_recorte": str(cand_path) if cand_path else None,
            "approved_confidence": _read_db_confidence(ref_path),
        }
        if not cand_path or not cand_path.exists():
            item["status"] = "MISSING"
            missing_count += 1
            items.append(item)
            continue

        try:
            ref_fc = canonical(ref_path)
            cand_fc = canonical(cand_path)
            score, gaps = _score_diff(ref_fc, cand_fc)
            geom_score, geom_gaps = _geometry_score(ref_fc, cand_fc)
            item["score"] = score
            item["gaps"] = gaps
            item["geometry_score"] = geom_score
            item["geometry_gaps"] = geom_gaps
            item["approved_outline"] = _bbox_from_canonical(ref_fc)
            item["motor_outline"] = _bbox_from_canonical(cand_fc)
            item["motor_ficha"] = {
                k: extrair_ficha_laje(str(cand_path), eid, OBRA_NAME).get(k)
                for k in ("comprimento", "largura", "linhas_verticais", "linhas_horizontais", "_hlaz", "_stog_pose")
            }
            if score == 100:
                item["status"] = "PASS"
                pass_count += 1
            elif score >= 85:
                item["status"] = "NEAR"
                near_count += 1
            else:
                item["status"] = "FAIL"

            if score < 100 and png_count < render_limit:
                png = png_dir / f"{eid}_approved_vs_motor.png"
                if render_side_by_side(ref_path, cand_path, png):
                    item["png"] = str(png)
                    png_count += 1
        except Exception as exc:
            item["status"] = "ERROR"
            item["error"] = str(exc)
        items.append(item)

    total = len(approved)
    report = {
        "source": str(source),
        "out_root": str(out_root),
        "total_approved": total,
        "motor_generated": len(motor_results),
        "pass": pass_count,
        "near": near_count,
        "missing": missing_count,
        "fail": sum(1 for i in items if i.get("status") == "FAIL"),
        "error": sum(1 for i in items if i.get("status") == "ERROR"),
        "pass_rate": round(pass_count / total * 100, 2) if total else 0.0,
        "pass_or_near_rate": round((pass_count + near_count) / total * 100, 2) if total else 0.0,
        "geometry_pass": sum(1 for i in items if i.get("geometry_score", 0) >= 95),
        "geometry_pass_rate": round(
            sum(1 for i in items if i.get("geometry_score", 0) >= 95) / total * 100,
            2,
        ) if total else 0.0,
        "items": items,
    }
    (out_root / "engrev_laj_recorte_loop_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({k: report[k] for k in ("total_approved", "motor_generated", "pass", "near", "missing", "fail", "error", "pass_rate", "pass_or_near_rate", "geometry_pass", "geometry_pass_rate")}, ensure_ascii=False))
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Loop headless dos recortes LAJ ER")
    ap.add_argument("--source", default=str(DEFAULT_SOURCE))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--keep-existing", action="store_true")
    ap.add_argument("--render-limit", type=int, default=12)
    args = ap.parse_args()
    run(Path(args.source), Path(args.out), keep_existing=args.keep_existing, render_limit=args.render_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
