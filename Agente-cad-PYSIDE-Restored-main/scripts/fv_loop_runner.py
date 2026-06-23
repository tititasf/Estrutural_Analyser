"""
FV Loop Runner — executa comparação N1×N2 para Fundo de Vigas sem GUI.

Lê N1 de beam_elements e N2 de reverse_eng_fichas no project_data.vision.
Grava eventos em engrev_fv_n1_interpretacao_learning.vision.

Uso:
    python scripts/fv_loop_runner.py --obra Obra_TREINO_1 --pav 13
    python scripts/fv_loop_runner.py --obra Obra_TREINO_1          # todos os pavimentos
    python scripts/fv_loop_runner.py --obra Obra_TREINO_1 --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Garantir que o src/ está no path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
LEARNING_DB_PATH = Path("D:/Agente-cad-PYSIDE/engrev_fv_n1_interpretacao_learning.vision")


# ── helpers ──────────────────────────────────────────────────────────────────

def _seg_length(pts: list) -> float:
    total = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        total += math.sqrt(dx * dx + dy * dy)
    return total


def _parse_h(dim_text: str | None) -> float | None:
    """h da viga = dimensão MENOR do par (ex: '120/19' → 19, '19/55' → 19)."""
    if not dim_text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)", dim_text)
    if not m:
        return None
    first = float(m.group(1).replace(",", "."))
    second = float(m.group(2).replace(",", "."))
    return min(first, second)


def _parse_dim_pair(dim_text: str | None) -> tuple[float, float] | None:
    if not dim_text:
        return None
    m = re.search(r"\(?\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*\)?", str(dim_text))
    if not m:
        return None
    first = float(m.group(1).replace(",", "."))
    second = float(m.group(2).replace(",", "."))
    return min(first, second), max(first, second)


def _normalize_viga(name: str) -> str:
    return re.sub(r"^[FLfl]\.", "", name).strip()


def _normalize_label(name: str | None) -> str:
    txt = str(name or "").strip().upper()
    txt = re.sub(r"^[FL]\.", "", txt)
    return re.sub(r"\s+", "", txt)


def _support_pair_ok(n1_ini: str | None, n1_fim: str | None, n2_left: str | None, n2_right: str | None) -> bool:
    n1_pair = {_normalize_label(n1_ini), _normalize_label(n1_fim)} - {""}
    n2_pair = {_normalize_label(n2_left), _normalize_label(n2_right)} - {""}
    return bool(n1_pair and n2_pair and n1_pair == n2_pair)


def _candidate_score(n1: dict, n2: dict) -> float:
    n2_panels = len(n2.get("panels", []))
    n2_comp = float(n2.get("total_height", 0) or 0)
    n2_h = float(n2.get("total_width", 0) or 0)
    n1_panels = int(n1.get("panels_n1") or 0)
    n1_comp = float(n1.get("comprimento_n1") or 0)
    n1_h = float(n1.get("h_n1") or 0)
    n1_dim = float(n1.get("dim_width_n1") or 0)

    checks = [
        n2_panels > 0 and n1_panels == n2_panels,
        n2_comp > 0 and abs(n1_comp - n2_comp) / n2_comp < 0.05,
        n2_h > 0 and abs(n1_h - n2_h) <= 2,
        n2_h > 0 and n1_dim > 0 and abs(n1_dim - n2_h) <= 2,
        _support_pair_ok(
            n1.get("apoio_inicial_n1"),
            n1.get("apoio_final_n1"),
            n2.get("label_left"),
            n2.get("label_right"),
        ),
    ]
    return 100.0 * sum(1 for ok in checks if ok) / len(checks)


# ── DB loaders ────────────────────────────────────────────────────────────────

def load_n2_fv(obra_name: str, pav_filter: str | None, db_path: Path) -> dict[str, dict]:
    """Retorna {elemento_id: campos_json} para FV da obra/pav."""
    conn = sqlite3.connect(str(db_path))
    try:
        if pav_filter:
            rows = conn.execute(
                "SELECT elemento_id, campos_json FROM reverse_eng_fichas "
                "WHERE classe='FV' AND obra_name=? AND pavimento LIKE ?",
                [obra_name, f"%{pav_filter}%"],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT elemento_id, campos_json FROM reverse_eng_fichas "
                "WHERE classe='FV' AND obra_name=?",
                [obra_name],
            ).fetchall()
        result: dict[str, dict] = {}
        for elem_id, cj in rows:
            try:
                result[elem_id] = json.loads(cj)
            except Exception:
                pass
        return result
    finally:
        conn.close()


def load_n1_fv(obra_name: str, pav_filter: str | None, db_path: Path) -> list[dict]:
    """Retorna lista de beams FV do N1 (beam_elements + beams.validated_fields_json)."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Encontrar project_ids da obra+pav
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

        # beam_elements FV — excluir fragmentos L.* (laterais) e F.* (fundo-sub)
        rows = conn.execute(
            f"SELECT viga_nome, n_segmentos, campos_json FROM beam_elements "
            f"WHERE classe='FV' AND project_id IN ({ph}) "
            f"AND viga_nome NOT LIKE 'L.%' AND viga_nome NOT LIKE 'F.%'",
            pids,
        ).fetchall()

        # Também buscar validated_fields e dimensao dos beams
        # (beams.validated_fields_json tem comprimento_total_fundo e dimensao)
        beams_extra: dict[str, dict] = {}
        beam_rows = conn.execute(
            f"SELECT name, validated_fields_json, data_json FROM beams WHERE project_id IN ({ph})",
            pids,
        ).fetchall()
        for br in beam_rows:
            name = br["name"]
            dj = {}
            try:
                dj = json.loads(br["data_json"] or "{}")
            except Exception:
                pass
            fields = dj.get("fields", {})
            # validated_fields_json é lista de dicts {field, value}
            vf_raw = []
            try:
                vf_raw = json.loads(br["validated_fields_json"] or "[]")
                if not isinstance(vf_raw, list):
                    vf_raw = []
            except Exception:
                pass
            vf = {item["field"]: item["value"] for item in vf_raw if isinstance(item, dict) and "field" in item}
            beams_extra[name] = {
                "comprimento_total_fundo": (
                    vf.get("comprimento_total_fundo")
                    or fields.get("comprimento_total_fundo")
                ),
                "dimensao": vf.get("dimensao") or fields.get("dimensao") or "",
                "seg_c": dj.get("seg_c", 0),
            }

        result = []
        for row in rows:
            viga_nome = row["viga_nome"]
            if viga_nome.endswith(".C") or viga_nome.startswith("FV-"):
                continue
            n_seg = row["n_segmentos"] or 0
            try:
                cj = json.loads(row["campos_json"] or "{}")
            except Exception:
                cj = {}

            extra = beams_extra.get(viga_nome, {})
            seg_fichas = [
                s.get("ficha") for s in cj.get("segmentos_fundo", [])
                if isinstance(s, dict) and isinstance(s.get("ficha"), dict)
            ]
            segmentos = [s for s in cj.get("segmentos_fundo", []) if isinstance(s, dict)]
            ficha0 = seg_fichas[0] if seg_fichas else {}
            seg0 = segmentos[0] if segmentos else {}

            def _ficha_float(ficha: dict, key: str) -> float:
                try:
                    return float(str(ficha.get(key, 0)).replace(",", ".") or 0)
                except Exception:
                    return 0.0

            ficha_comp = sum(_ficha_float(f, "comprimento_total_fundo") for f in seg_fichas)
            ficha_h = _ficha_float(ficha0, "largura_total_fundo")
            dim_text_n1 = seg0.get("dim_text") or cj.get("dim") or extra.get("dimensao") or ""
            dim_pair_n1 = _parse_dim_pair(dim_text_n1)
            dim_width_n1 = (
                float(seg0.get("dim_width") or 0)
                or (dim_pair_n1[0] if dim_pair_n1 else 0.0)
            )
            dim_height_n1 = (
                float(seg0.get("dim_height") or 0)
                or (dim_pair_n1[1] if dim_pair_n1 else 0.0)
            )
            abertura_n1 = sum(
                1 for f in seg_fichas
                if str(f.get("abertura_especial", "")).strip().lower() not in {"", "n/a", "0"}
            )
            chanfro_n1 = sum(
                1 for f in seg_fichas
                for k in ("chanfro_esq_top", "chanfro_esq_fun", "chanfro_dir_top", "chanfro_dir_fun")
                if str(f.get(k, "")).strip().lower() not in {"", "n/a", "0"}
            )

            # Prioridade: campos escritos pelo headless runner (mais precisos)
            # → fallback para cálculo legacy dos segmentos

            # panels: n_paineis_logicos (merged_lengths count) > seg_c > n_segmentos
            panels_n1 = (
                cj.get("n_paineis_logicos")
                or extra.get("seg_c")
                or n_seg
            )

            # comprimento: headless > beams.validated_fields > geometry sum
            comprimento = (
                ficha_comp
                or
                cj.get("comprimento_total_fundo")
                or extra.get("comprimento_total_fundo")
                or sum(_seg_length(s.get("geometry", [])) for s in cj.get("segmentos_fundo", []) if s.get("geometry"))
                or 0.0
            )

            # h: h_espessura (headless, proxima ao beam) > dim text > validated
            h = (
                ficha_h
                or
                cj.get("h_espessura")
                or _parse_h(cj.get("dim") or extra.get("dimensao"))
            )

            result.append({
                "viga_nome": viga_nome,
                "panels_n1": panels_n1,
                "comprimento_n1": float(comprimento),
                "h_n1": h or 0.0,
                "dim_text_n1": dim_text_n1,
                "dim_width_n1": dim_width_n1,
                "dim_height_n1": dim_height_n1,
                "apoio_inicial_n1": seg0.get("apoio_inicial") or ficha0.get("apoio_inicial", ""),
                "apoio_final_n1": seg0.get("apoio_final") or ficha0.get("apoio_final", ""),
                "aberturas_n1": abertura_n1,
                "chanfros_n1": chanfro_n1,
                "raw_n_segmentos": n_seg,
            })

        return result

    finally:
        conn.close()


# ── comparação ────────────────────────────────────────────────────────────────

def compare_fv(
    n1_list: list[dict],
    n2_dict: dict[str, dict],
) -> list[dict]:
    """Compara N1 vs N2 e retorna lista de resultados por viga."""
    results = []
    for b in n1_list:
        vn = b["viga_nome"]
        clean = _normalize_viga(vn)
        n2 = n2_dict.get(clean) or n2_dict.get(vn)

        if not n2:
            results.append({"viga": vn, "matched": False, **b})
            continue

        n2_panels = len(n2.get("panels", []))
        n2_comp = float(n2.get("total_height", 0) or 0)
        n2_h = float(n2.get("total_width", 0) or 0)
        n2_holes = len([h for h in n2.get("holes", []) if isinstance(h, dict) and h.get("active")])

        n1_segs = b["panels_n1"]
        n1_comp = b["comprimento_n1"]
        n1_h = b["h_n1"] or 0.0
        n1_dim_width = float(b.get("dim_width_n1") or 0.0)
        n1_dim_height = float(b.get("dim_height_n1") or 0.0)
        n1_holes = int(b.get("aberturas_n1") or 0)
        apoios_ok = _support_pair_ok(
            b.get("apoio_inicial_n1"),
            b.get("apoio_final_n1"),
            n2.get("label_left"),
            n2.get("label_right"),
        )

        segs_ok = n2_panels > 0 and n1_segs == n2_panels
        comp_ok = (
            n2_comp > 0 and abs(n1_comp - n2_comp) / n2_comp < 0.05
        ) if n2_comp else False
        h_ok = (n2_h > 0 and abs(n1_h - n2_h) <= 2) if n2_h else False
        dim_geom_ok = (n1_dim_width > 0 and n1_h > 0 and abs(n1_dim_width - n1_h) <= 2)
        dim_ok = (n2_h > 0 and n1_dim_width > 0 and abs(n1_dim_width - n2_h) <= 2 and dim_geom_ok) if n2_h else False
        holes_ok = n1_holes == n2_holes if (n1_holes or n2_holes) else None

        checks = [segs_ok, comp_ok, h_ok, dim_ok]
        if holes_ok is not None:
            checks.append(holes_ok)
        score = 100.0 * sum(1 for ok in checks if ok) / len(checks)
        best_alt_name = ""
        best_alt_score = 0.0
        for cand in n1_list:
            if cand is b:
                continue
            alt_score = _candidate_score(cand, n2)
            if alt_score > best_alt_score:
                best_alt_score = alt_score
                best_alt_name = cand.get("viga_nome", "")

        results.append({
            "viga": vn,
            "matched": True,
            "panels_n1": n1_segs,
            "panels_n2": n2_panels,
            "comprimento_n1": round(n1_comp, 1),
            "comprimento_n2": round(n2_comp, 1),
            "h_n1": n1_h,
            "h_n2": n2_h,
            "dim_text_n1": b.get("dim_text_n1", ""),
            "dim_width_n1": n1_dim_width,
            "dim_height_n1": n1_dim_height,
            "dim_ok": dim_ok,
            "dim_geom_ok": dim_geom_ok,
            "apoio_inicial_n1": b.get("apoio_inicial_n1", ""),
            "apoio_final_n1": b.get("apoio_final_n1", ""),
            "label_left_n2": n2.get("label_left", ""),
            "label_right_n2": n2.get("label_right", ""),
            "apoios_ok": apoios_ok,
            "aberturas_n1": n1_holes,
            "aberturas_n2": n2_holes,
            "chanfros_n1": b.get("chanfros_n1", 0),
            "segs_ok": segs_ok,
            "comp_ok": comp_ok,
            "h_ok": h_ok,
            "holes_ok": holes_ok,
            "score": round(score, 1),
            "best_alt_viga": best_alt_name,
            "best_alt_score": round(best_alt_score, 1),
        })

    return results


# ── gravação de eventos ───────────────────────────────────────────────────────

def record_events(
    results: list[dict],
    obra_name: str,
    pavimento: str,
    learning_db: Path,
) -> int:
    from src.core.engrev_fv_n1_interpretacao_learning_store import (
        record_engrev_fv_n1_interpretacao_event,
    )

    count = 0
    for r in results:
        if not r["matched"]:
            continue
        try:
            record_engrev_fv_n1_interpretacao_event(
                event_type="engrev_assisted_generated",
                elemento_id=r["viga"],
                analysis_mode="engrev_assisted",
                obra_name=obra_name,
                pavimento=pavimento,
                features={
                    "panels_n1": r["panels_n1"],
                    "panels_n2": r["panels_n2"],
                    "comprimento_n1": r["comprimento_n1"],
                    "comprimento_n2": r["comprimento_n2"],
                    "h_n1": r["h_n1"],
                    "h_n2": r["h_n2"],
                    "dim_text_n1": r.get("dim_text_n1", ""),
                    "dim_width_n1": r.get("dim_width_n1", 0),
                    "dim_height_n1": r.get("dim_height_n1", 0),
                    "dim_matched": 1 if r.get("dim_ok") else 0,
                    "dim_geom_matched": 1 if r.get("dim_geom_ok") else 0,
                    "apoio_inicial_n1": r.get("apoio_inicial_n1", ""),
                    "apoio_final_n1": r.get("apoio_final_n1", ""),
                    "label_left_n2": r.get("label_left_n2", ""),
                    "label_right_n2": r.get("label_right_n2", ""),
                    "apoios_matched": 1 if r.get("apoios_ok") else 0,
                    "aberturas_n1": r.get("aberturas_n1", 0),
                    "aberturas_n2": r.get("aberturas_n2", 0),
                    "chanfros_n1": r.get("chanfros_n1", 0),
                    "segs_matched": 1 if r["segs_ok"] else 0,
                    "holes_matched": None if r.get("holes_ok") is None else (1 if r["holes_ok"] else 0),
                    "score": r["score"],
                },
                learning_db_path=learning_db,
            )
            count += 1
        except Exception as e:
            print(f"  [WARN] Evento {r['viga']}: {e}")
    return count


# ── relatório ─────────────────────────────────────────────────────────────────

def print_report(results: list[dict], obra: str, pav: str | None):
    matched = [r for r in results if r["matched"]]
    total = len(results)
    avg_score = sum(r["score"] for r in matched) / len(matched) if matched else 0

    print(f"\n{'='*70}")
    print(f"FV LOOP REPORT — {obra} | pav={pav or 'TODOS'}")
    print(f"{'='*70}")
    print(f"Vigas N1: {total}  |  Matchadas N2: {len(matched)}  |  Score médio: {avg_score:.1f}%")
    print()

    # Header
    print(f"{'Viga':<10} {'SegsN1':>6} {'SegsN2':>6} {'S':>3} {'CompN1':>8} {'CompN2':>8} {'C':>3} {'hN1':>5} {'hN2':>5} {'H':>3} {'Dim':>5} {'D':>3} {'Score':>6}")
    print("-" * 70)

    for r in results:
        if not r["matched"]:
            print(f"{r['viga']:<10} {'(sem N2)':>6}")
            continue
        s = "OK" if r["segs_ok"] else "--"
        c = "OK" if r["comp_ok"] else "--"
        h = "OK" if r["h_ok"] else "--"
        d = "OK" if r.get("dim_ok") else "--"
        score_str = f"{r['score']:.0f}%"
        print(
            f"{r['viga']:<10} {r['panels_n1']:>6} {r['panels_n2']:>6} {s:>3} "
            f"{r['comprimento_n1']:>8.1f} {r['comprimento_n2']:>8.1f} {c:>3} "
            f"{r['h_n1']:>5} {r['h_n2']:>5} {h:>3} {r.get('dim_width_n1', 0):>5.0f} {d:>3} {score_str:>6}"
        )

    print()
    # Diagnóstico automático dos padrões de falha
    segs_fail = sum(1 for r in matched if not r["segs_ok"])
    comp_fail = sum(1 for r in matched if not r["comp_ok"])
    h_fail = sum(1 for r in matched if not r["h_ok"])
    dim_fail = sum(1 for r in matched if not r.get("dim_ok"))
    apoio_fail = sum(1 for r in matched if not r.get("apoios_ok"))
    print("DIAGNOSTICO:")
    if matched:
        print(f"  Segmentos (panels) errados: {segs_fail}/{len(matched)} ({100*segs_fail/len(matched):.0f}%)")
        print(f"  Comprimento fora +-5%:      {comp_fail}/{len(matched)} ({100*comp_fail/len(matched):.0f}%)")
        print(f"  h fora +-2cm:               {h_fail}/{len(matched)} ({100*h_fail/len(matched):.0f}%)")
        print(f"  Dimensao textual divergente:{dim_fail}/{len(matched)} ({100*dim_fail/len(matched):.0f}%)")
        print(f"  Apoios inicial/final diverg.:{apoio_fail}/{len(matched)} ({100*apoio_fail/len(matched):.0f}%)")
        swaps = [
            r for r in matched
            if r.get("best_alt_viga") and r.get("best_alt_score", 0) > r.get("score", 0)
        ]
        swaps = sorted(swaps, key=lambda r: r.get("best_alt_score", 0) - r.get("score", 0), reverse=True)[:8]
        if swaps:
            print("  Possiveis trocas de identidade:")
            for r in swaps:
                print(
                    f"    {r['viga']}: exato={r['score']:.0f}% | "
                    f"alt={r['best_alt_viga']} ({r['best_alt_score']:.0f}%)"
                )
    print(f"{'='*70}\n")


# ── main ──────────────────────────────────────────────────────────────────────

def run(
    obra_name: str,
    pav_filter: str | None = None,
    db_path: Path = DB_PATH,
    learning_db: Path = LEARNING_DB_PATH,
    dry_run: bool = False,
) -> list[dict]:
    print(f"[FV Loop] obra={obra_name} pav={pav_filter or 'TODOS'} dry_run={dry_run}")

    n2 = load_n2_fv(obra_name, pav_filter, db_path)
    print(f"  N2 FV fichas: {len(n2)}")

    n1 = load_n1_fv(obra_name, pav_filter, db_path)
    print(f"  N1 FV beams:  {len(n1)}")

    if not n1:
        print("  [WARN] Nenhum beam FV encontrado no DB. Rode a Análise Geral primeiro.")
        return []

    results = compare_fv(n1, n2)

    if not dry_run:
        pav_label = pav_filter or "ALL"
        n_events = record_events(results, obra_name, pav_label, learning_db)
        print(f"  Eventos gravados: {n_events}")
    else:
        print("  [dry-run] Sem gravação.")

    print_report(results, obra_name, pav_filter)
    return results


def main():
    parser = argparse.ArgumentParser(description="FV Loop Runner — headless sem GUI")
    parser.add_argument("--obra", required=True, help="Nome da obra (ex: Obra_TREINO_1)")
    parser.add_argument("--pav", default=None, help="Filtro parcial do pavimento (ex: 13)")
    parser.add_argument("--db", default=str(DB_PATH), help="Caminho do project_data.vision")
    parser.add_argument("--learning-db", default=str(LEARNING_DB_PATH), help="Caminho do learning .vision")
    parser.add_argument("--dry-run", action="store_true", help="Sem gravação no DB")
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
