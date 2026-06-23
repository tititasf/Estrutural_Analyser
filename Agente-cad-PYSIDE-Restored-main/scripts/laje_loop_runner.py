"""
LAJ Loop Runner - compara N1 x N2 para Lajes sem GUI.

Le N1 de slab_elements e N2 de reverse_eng_fichas no project_data.vision.
Grava eventos em engrev_laj_n1_interpretacao_learning.vision.

Uso:
    python -X utf8 scripts/laje_loop_runner.py --obra Obra_TREINO_1 --pav 13
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
LEARNING_DB_PATH = Path("D:/Agente-cad-PYSIDE/engrev_laj_n1_interpretacao_learning.vision")


def _normalize_laje(name: str) -> str:
    text = (name or "").upper().strip()
    m = re.search(r"L\s*[-_\.]?\s*(\d+[A-Z0-9_]*)", text)
    if not m:
        return re.sub(r"\s+", "", text)
    return f"L{m.group(1)}"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _count_pontaletes(value: Any) -> int:
    if not value:
        return 0
    if isinstance(value, dict):
        total = value.get("total") or value.get("pont_total") or value.get("quantidade")
        if total is not None:
            return int(_safe_float(total, 0))
        return sum(1 for v in value.values() if v)
    if isinstance(value, list):
        return len(value)
    return int(_safe_float(value, 0))


def ensure_slab_elements_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS slab_elements (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            laje_nome TEXT,
            classe TEXT DEFAULT 'LAJ',
            campos_json TEXT,
            n_linhas INTEGER DEFAULT 0,
            is_validated BOOLEAN DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_slab_elements_project "
        "ON slab_elements(project_id, classe, laje_nome)"
    )


def load_n2_laj(obra_name: str, pav_filter: str | None, db_path: Path) -> dict[str, dict]:
    conn = sqlite3.connect(str(db_path))
    try:
        if pav_filter:
            rows = conn.execute(
                "SELECT elemento_id, campos_json FROM reverse_eng_fichas "
                "WHERE classe='LAJ' AND obra_name=? AND pavimento LIKE ?",
                [obra_name, f"%{pav_filter}%"],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT elemento_id, campos_json FROM reverse_eng_fichas "
                "WHERE classe='LAJ' AND obra_name=?",
                [obra_name],
            ).fetchall()
        out: dict[str, dict] = {}
        for elem_id, campos_json in rows:
            try:
                data = json.loads(campos_json or "{}")
            except Exception:
                continue
            out[_normalize_laje(elem_id)] = data
        return out
    finally:
        conn.close()


def load_n1_laj(obra_name: str, pav_filter: str | None, db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        ensure_slab_elements_schema(conn)
        if pav_filter:
            projs = conn.execute(
                "SELECT id FROM projects WHERE work_name=? AND pavement_name LIKE ?",
                [obra_name, f"%{pav_filter}%"],
            ).fetchall()
        else:
            projs = conn.execute(
                "SELECT id FROM projects WHERE work_name=?",
                [obra_name],
            ).fetchall()
        if not projs:
            return []

        pids = [p["id"] for p in projs]
        ph = ",".join("?" * len(pids))
        rows = conn.execute(
            f"SELECT laje_nome, campos_json, n_linhas FROM slab_elements "
            f"WHERE classe='LAJ' AND project_id IN ({ph})",
            pids,
        ).fetchall()

        out = []
        for row in rows:
            try:
                campos = json.loads(row["campos_json"] or "{}")
            except Exception:
                campos = {}
            out.append(
                {
                    "laje_nome": row["laje_nome"],
                    "comprimento_n1": _safe_float(campos.get("comprimento")),
                    "largura_n1": _safe_float(campos.get("largura")),
                    "area_n1": _safe_float(campos.get("area_cm2")),
                    "linhas_v_n1": int(_safe_float(campos.get("linhas_verticais_count"), 0)),
                    "linhas_h_n1": int(_safe_float(campos.get("linhas_horizontais_count"), 0)),
                    "linhas_total_n1": int(row["n_linhas"] or 0),
                    "pontaletes_n1": _count_pontaletes(campos.get("pontaletes")),
                    "cut_view_count": int(_safe_float(campos.get("cut_view_count"), 0)),
                    "human_cut_view_count": int(_safe_float(campos.get("human_cut_view_count"), 0)),
                    "has_cut_view": bool(campos.get("has_cut_view")),
                    "method": campos.get("method"),
                    "confidence": _safe_float(campos.get("confidence_score")),
                }
            )
        return out
    finally:
        conn.close()


def compare_laj(n1_list: list[dict], n2_dict: dict[str, dict]) -> list[dict]:
    results = []
    for item in n1_list:
        name = item["laje_nome"]
        key = _normalize_laje(name)
        n2 = n2_dict.get(key)
        if not n2:
            results.append({"laje": name, "matched": False, **item})
            continue

        n2_comp = _safe_float(n2.get("comprimento"))
        n2_larg = _safe_float(n2.get("largura"))
        n2_area = _safe_float(n2.get("area_cm2"))
        n2_lv = len(n2.get("linhas_verticais") or [])
        n2_lh = len(n2.get("linhas_horizontais") or [])
        n2_lines = n2_lv + n2_lh
        n2_pont = _count_pontaletes(n2.get("pontaletes"))

        n1_comp = item["comprimento_n1"]
        n1_larg = item["largura_n1"]
        n1_area = item["area_n1"]

        dims_a = n2_comp > 0 and n2_larg > 0 and (
            abs(n1_comp - n2_comp) / n2_comp <= 0.05
            and abs(n1_larg - n2_larg) / n2_larg <= 0.05
        )
        dims_b = n2_comp > 0 and n2_larg > 0 and (
            abs(n1_comp - n2_larg) / n2_larg <= 0.05
            and abs(n1_larg - n2_comp) / n2_comp <= 0.05
        )
        dims_ok = bool(dims_a or dims_b)
        comp_ok = dims_ok
        area_ok = bool(n2_area > 0 and abs(n1_area - n2_area) / n2_area <= 0.05)
        linhas_ok = item["linhas_total_n1"] == n2_lines
        pont_ok = item["pontaletes_n1"] == n2_pont

        score = (
            (30.0 if comp_ok else 0.0)
            + (30.0 if area_ok else 0.0)
            + (30.0 if linhas_ok else 0.0)
            + (10.0 if pont_ok else 0.0)
        )

        results.append(
            {
                "laje": name,
                "matched": True,
                "comprimento_n1": round(n1_comp, 1),
                "comprimento_n2": round(n2_comp, 1),
                "largura_n1": round(n1_larg, 1),
                "largura_n2": round(n2_larg, 1),
                "area_n1": round(n1_area, 1),
                "area_n2": round(n2_area, 1),
                "linhas_n1": item["linhas_total_n1"],
                "linhas_n2": n2_lines,
                "linhas_v_n1": item["linhas_v_n1"],
                "linhas_h_n1": item["linhas_h_n1"],
                "linhas_v_n2": n2_lv,
                "linhas_h_n2": n2_lh,
                "pontaletes_n1": item["pontaletes_n1"],
                "pontaletes_n2": n2_pont,
                "cut_view_count": item.get("cut_view_count", 0),
                "human_cut_view_count": item.get("human_cut_view_count", 0),
                "has_cut_view": item.get("has_cut_view", False),
                "comp_ok": comp_ok,
                "area_ok": area_ok,
                "linhas_ok": linhas_ok,
                "pont_ok": pont_ok,
                "score": round(score, 1),
                "method": item.get("method"),
                "confidence": item.get("confidence"),
            }
        )
    return results


def record_events(
    results: list[dict],
    obra_name: str,
    pavimento: str,
    learning_db: Path,
) -> int:
    from src.core.engrev_laj_n1_interpretacao_learning_store import (
        record_engrev_laj_n1_interpretacao_event,
    )

    count = 0
    for r in results:
        if not r["matched"]:
            continue
        try:
            record_engrev_laj_n1_interpretacao_event(
                event_type="engrev_assisted_generated",
                elemento_id=r["laje"],
                analysis_mode="engrev_assisted",
                obra_name=obra_name,
                pavimento=pavimento,
                features={
                    "area_cm2": r["area_n1"],
                    "comprimento_n1": r["comprimento_n1"],
                    "comprimento_n2": r["comprimento_n2"],
                    "largura_n1": r["largura_n1"],
                    "largura_n2": r["largura_n2"],
                    "area_n1": r["area_n1"],
                    "area_n2": r["area_n2"],
                    "linhas_n1": r["linhas_n1"],
                    "linhas_n2": r["linhas_n2"],
                    "pontaletes_n1": r["pontaletes_n1"],
                    "pontaletes_n2": r["pontaletes_n2"],
                    "score": r["score"],
                    "method": r.get("method"),
                    "confidence": r.get("confidence"),
                },
                learning_db_path=learning_db,
            )
            count += 1
        except Exception as e:
            print(f"  [WARN] Evento {r['laje']}: {e}")
    return count


def print_report(results: list[dict], obra: str, pav: str | None) -> None:
    matched = [r for r in results if r["matched"]]
    avg_score = sum(r["score"] for r in matched) / len(matched) if matched else 0.0

    print(f"\n{'=' * 92}")
    print(f"LAJ LOOP REPORT - {obra} | pav={pav or 'TODOS'}")
    print(f"{'=' * 92}")
    print(
        f"Lajes N1: {len(results)}  |  Matchadas N2: {len(matched)}  |  "
        f"Score medio: {avg_score:.1f}%"
    )
    print()
    print(
        f"{'Laje':<8} {'CxL N1':>15} {'CxL N2':>15} {'D':>3} "
        f"{'AreaN1':>9} {'AreaN2':>9} {'A':>3} {'LinN1':>5} {'LinN2':>5} "
        f"{'L':>3} {'P':>3} {'Score':>6} {'Metodo':>10}"
    )
    print("-" * 92)
    for r in sorted(results, key=lambda x: _normalize_laje(x["laje"])):
        if not r["matched"]:
            print(f"{r['laje']:<8} {'(sem N2)':>15}")
            continue
        d = "OK" if r["comp_ok"] else "--"
        a = "OK" if r["area_ok"] else "--"
        l = "OK" if r["linhas_ok"] else "--"
        p = "OK" if r["pont_ok"] else "--"
        print(
            f"{r['laje']:<8} "
            f"{r['comprimento_n1']:>6.1f}x{r['largura_n1']:<6.1f} "
            f"{r['comprimento_n2']:>6.1f}x{r['largura_n2']:<6.1f} {d:>3} "
            f"{r['area_n1']:>9.1f} {r['area_n2']:>9.1f} {a:>3} "
            f"{r['linhas_n1']:>5} {r['linhas_n2']:>5} {l:>3} "
            f"{p:>3} {r['score']:>5.0f}% {str(r.get('method') or ''):>10}"
        )

    print()
    if matched:
        dims_fail = sum(1 for r in matched if not r["comp_ok"])
        area_fail = sum(1 for r in matched if not r["area_ok"])
        lines_fail = sum(1 for r in matched if not r["linhas_ok"])
        pont_fail = sum(1 for r in matched if not r["pont_ok"])
        cut_detected = [r for r in results if r.get("cut_view_count")]
        cut_human = [r for r in results if r.get("human_cut_view_count")]
        cut_human_hit = [r for r in results if r.get("human_cut_view_count") and r.get("cut_view_count")]
        print("DIAGNOSTICO:")
        print(f"  CxL fora +-5%:        {dims_fail}/{len(matched)} ({100*dims_fail/len(matched):.0f}%)")
        print(f"  Area fora +-5%:       {area_fail}/{len(matched)} ({100*area_fail/len(matched):.0f}%)")
        print(f"  Linhas/cotas erradas: {lines_fail}/{len(matched)} ({100*lines_fail/len(matched):.0f}%)")
        print(f"  Pontaletes errados:   {pont_fail}/{len(matched)} ({100*pont_fail/len(matched):.0f}%)")
        if cut_human or cut_detected:
            recall = 100 * len(cut_human_hit) / len(cut_human) if cut_human else 0.0
            print("  Visao corte N1:")
            print(f"    lajes detectadas:   {len(cut_detected)} -> {', '.join(r['laje'] for r in cut_detected) or '-'}")
            print(f"    seeds humanos:      {len(cut_human)} -> {', '.join(r['laje'] for r in cut_human) or '-'}")
            print(f"    recall seeds:       {len(cut_human_hit)}/{len(cut_human)} ({recall:.0f}%)")
    print(f"{'=' * 92}\n")


def run(
    obra_name: str,
    pav_filter: str | None = None,
    db_path: Path = DB_PATH,
    learning_db: Path = LEARNING_DB_PATH,
    dry_run: bool = False,
) -> list[dict]:
    print(f"[LAJ Loop] obra={obra_name} pav={pav_filter or 'TODOS'} dry_run={dry_run}")

    n2 = load_n2_laj(obra_name, pav_filter, db_path)
    print(f"  N2 LAJ fichas: {len(n2)}")

    n1 = load_n1_laj(obra_name, pav_filter, db_path)
    print(f"  N1 LAJ slabs:  {len(n1)}")

    if not n1:
        print("  [WARN] Nenhuma laje N1 encontrada. Rode laje_analise_geral_headless primeiro.")
        return []

    results = compare_laj(n1, n2)

    if not dry_run:
        n_events = record_events(results, obra_name, pav_filter or "ALL", learning_db)
        print(f"  Eventos gravados: {n_events}")
    else:
        print("  [dry-run] Sem gravacao.")

    print_report(results, obra_name, pav_filter)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="LAJ Loop Runner headless")
    parser.add_argument("--obra", required=True)
    parser.add_argument("--pav", default=None)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--learning-db", default=str(LEARNING_DB_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(
        obra_name=args.obra,
        pav_filter=args.pav,
        db_path=Path(args.db),
        learning_db=Path(args.learning_db),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
