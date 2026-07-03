#!/usr/bin/env python
"""Diagnóstico numérico headless entre os fundos de viga N1 e N2."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_STATE_ROOT = SCRIPT_DIR / "html_fichas"
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "relatorios" / "diagnosticos_fv"


def _slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))
    return clean.strip("._") or "item"


def _float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _relative_delta(detected: float | None, expected: float | None) -> float | None:
    if detected is None or expected is None:
        return None
    return abs(detected - expected) / max(abs(expected), 1e-9)


def classify_delta(delta: float | None) -> str:
    if delta is None:
        return "INDETERMINADO"
    if delta <= 0.02:
        return "EXCELENTE"
    if delta <= 0.05:
        return "BOM"
    if delta <= 0.10:
        return "REGULAR"
    return "RUIM"


def _pav_number(value: str) -> int | None:
    text = str(value or "").upper()
    for pattern in (r"(?<!\d)(\d+)\s*[_ -]*PAV", r"(?<!\d)(\d+)\s*P(?:\D|$)"):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _same_pavimento(first: str, second: str) -> bool:
    if str(first or "").strip().casefold() == str(second or "").strip().casefold():
        return True
    first_number = _pav_number(first)
    second_number = _pav_number(second)
    return first_number is not None and first_number == second_number


def resolve_state_path(
    obra: str,
    pavimento: str,
    state_path: str | Path | None = None,
    state_root: str | Path = DEFAULT_STATE_ROOT,
) -> Path:
    if state_path:
        path = Path(state_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Estado N1 não encontrado: {path}")
        return path

    obra_dir = Path(state_root) / obra
    matches: list[tuple[float, Path]] = []
    for candidate in obra_dir.glob("estado_*.json"):
        try:
            state = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(state.get("obra") or "") != obra:
            continue
        if not _same_pavimento(str(state.get("pavimento") or ""), pavimento):
            continue
        matches.append((candidate.stat().st_mtime, candidate))
    if not matches:
        raise FileNotFoundError(
            f"Nenhum estado N1 de {obra}/{pavimento} em {obra_dir}"
        )
    return max(matches, key=lambda item: item[0])[1].resolve()


def _geometry_long_span(points: list | tuple | None) -> float | None:
    clean: list[tuple[float, float]] = []
    for point in points or []:
        try:
            clean.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    if not clean:
        return None
    xs = [point[0] for point in clean]
    ys = [point[1] for point in clean]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def load_n1_beams(state_path: str | Path) -> tuple[dict, dict[str, dict]]:
    path = Path(state_path)
    state = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = {}
    for segment in ((state.get("segmentos") or {}).get("fundo") or []):
        if not isinstance(segment, dict):
            continue
        if "ignor" in str(segment.get("status") or "").casefold():
            continue
        name = str(segment.get("beam_name") or "").strip().upper()
        if name:
            grouped.setdefault(name, []).append(segment)

    beams: dict[str, dict] = {}
    for name, segments in grouped.items():
        lengths = [value for value in (_float(item.get("length")) for item in segments) if value is not None]
        widths = [value for value in (_float(item.get("width")) for item in segments) if value is not None]
        geometry_spans = [
            value
            for value in (_geometry_long_span(item.get("points")) for item in segments)
            if value is not None
        ]
        beams[name] = {
            "largura": statistics.median(widths) if widths else None,
            "larguras": widths,
            "comprimento_total": sum(lengths) if lengths else None,
            "comprimentos": lengths,
            "comprimento_geometrico_total": sum(geometry_spans) if geometry_spans else None,
            "segmentos": len(segments),
            "furos_ativos": None,
        }
    return state, beams


def _n2_length(data: dict) -> float | None:
    declared = _float(data.get("total_height"))
    if declared is not None:
        return declared
    segments = data.get("segments_rich") or data.get("panels") or []
    values = [
        value
        for value in (
            _float(item.get("total_width") or item.get("width"))
            for item in segments
            if isinstance(item, dict)
        )
        if value is not None
    ]
    return sum(values) if values else None


def load_n2_beams(
    db_path: str | Path,
    obra: str,
    pavimento: str,
) -> dict[str, dict]:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"DB N2 não encontrado: {path}")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT id, elemento_id, pavimento, campos_json, status, confianca "
            "FROM reverse_eng_fichas WHERE obra_name=? AND classe='FV' "
            "ORDER BY id DESC",
            (obra,),
        ).fetchall()
    finally:
        connection.close()

    beams: dict[str, dict] = {}
    for row_id, item, row_pavimento, raw_json, status, confidence in rows:
        name = str(item or "").strip().upper()
        if not name or name in beams or not _same_pavimento(str(row_pavimento or ""), pavimento):
            continue
        try:
            data = json.loads(raw_json or "{}")
        except json.JSONDecodeError:
            continue
        segments = data.get("segments_rich") or data.get("panels") or []
        holes = data.get("holes") or []
        beams[name] = {
            "largura": _float(data.get("total_width") or data.get("largura_total_fundo")),
            "comprimento_total": _n2_length(data),
            "segmentos": len(segments),
            "furos_ativos": sum(
                1 for hole in holes if isinstance(hole, dict) and hole.get("active")
            ),
            "ficha_id": row_id,
            "status": status,
            "confianca_origem": _float(confidence),
        }
    return beams


def diagnose_item(
    name: str,
    n1: dict | None,
    n2: dict | None,
    *,
    obra: str,
    pavimento: str,
    generated_at: str,
) -> dict:
    width_delta = _relative_delta(
        (n1 or {}).get("largura"), (n2 or {}).get("largura")
    )
    length_delta = _relative_delta(
        (n1 or {}).get("comprimento_total"), (n2 or {}).get("comprimento_total")
    )
    available_deltas = [value for value in (width_delta, length_delta) if value is not None]
    max_delta = max(available_deltas) if available_deltas else None
    quality = classify_delta(max_delta)
    segments_match = bool(
        n1 is not None
        and n2 is not None
        and n1.get("segmentos") == n2.get("segmentos")
    )

    if n1 is None or n2 is None:
        cause = "schema_gap"
        description = (
            "Item presente apenas no N2; falta representação FV no estado N1."
            if n1 is None
            else "Item presente apenas no N1; falta ficha FV correspondente no N2."
        )
        confidence = 0.99
    elif quality in {"REGULAR", "RUIM"}:
        cause = "extractor_bug"
        description = (
            "Dimensões do fundo de viga divergem entre a interpretação N1 e a ficha N2."
        )
        confidence = 0.95 if quality == "RUIM" else 0.85
    elif not segments_match:
        cause = "schema_gap"
        description = (
            "As dimensões principais são compatíveis, mas a quantidade de segmentos N1 e N2 diverge."
        )
        confidence = 0.75
    else:
        cause = None
        description = "Sem divergência numérica relevante entre N1 e N2."
        confidence = 0.98 if quality == "EXCELENTE" else 0.90

    evidence = {
        "classificacao": quality,
        "delta_relativo_max": max_delta,
        "deltas": {
            "largura": width_delta,
            "comprimento_total": length_delta,
        },
        "segmentos_match": segments_match,
        "n1": n1,
        "n2": n2,
    }
    return {
        "data": generated_at,
        "obra": obra,
        "pavimento": pavimento,
        "classe": "FV",
        "item": name,
        "marcado_por": "auto",
        "nota_original": None,
        "causa_raiz": cause,
        "causa_descricao": description,
        "confianca": confidence,
        "evidencia": evidence,
        "campos_afetados": ["N1", "N2"],
        "concordancia": "pendente",
        "status": "aberto" if cause else "nao_reproduzido",
        "fix_aplicado": None,
        "verificado_em": None,
    }


def _run_id(state: dict) -> str:
    raw = str(state.get("gerado_em") or "")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        parsed = datetime.now()
    return parsed.strftime("%Y%m%d_%H%M%S")


def run_diagnostic(
    *,
    obra: str,
    pavimento: str,
    state_path: str | Path | None = None,
    state_root: str | Path = DEFAULT_STATE_ROOT,
    db_path: str | Path = DEFAULT_DB,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[dict, Path, Path]:
    resolved_state = resolve_state_path(obra, pavimento, state_path, state_root)
    state, n1_beams = load_n1_beams(resolved_state)
    n2_beams = load_n2_beams(db_path, obra, pavimento)
    generated_at = datetime.now(timezone.utc).isoformat()
    items = [
        diagnose_item(
            name,
            n1_beams.get(name),
            n2_beams.get(name),
            obra=obra,
            pavimento=pavimento,
            generated_at=generated_at,
        )
        for name in sorted(set(n1_beams) | set(n2_beams), key=_natural_key)
    ]
    quality_counts = Counter(item["evidencia"]["classificacao"] for item in items)
    alerts = [item for item in items if item["causa_raiz"]]
    state_hash = hashlib.sha256(resolved_state.read_bytes()).hexdigest()
    report = {
        "schema_version": 2,
        "gerado_em": generated_at,
        "obra": obra,
        "pavimento": pavimento,
        "run_id": _run_id(state),
        "fontes": {
            "n1_estado": str(resolved_state),
            "n1_estado_sha256": state_hash,
            "n2_db": str(Path(db_path).resolve()),
        },
        "resumo": {
            "itens": len(items),
            "n1_itens": len(n1_beams),
            "n2_itens": len(n2_beams),
            "alertas": len(alerts),
            "classificacoes": dict(sorted(quality_counts.items())),
        },
        "itens": items,
    }

    run_dir = (
        Path(output_root)
        / _slug(obra)
        / _slug(pavimento)
        / report["run_id"]
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "diagnostico_fv_n1_n2.json"
    jsonl_path = run_dir / "triagem_auto_fv.jsonl"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with jsonl_path.open("w", encoding="utf-8") as file:
        for item in alerts:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")
    return report, json_path, jsonl_path


def _natural_key(value: str) -> list[Any]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara numericamente fundos de viga N1×N2 sem abrir a UI"
    )
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav", default="13_PAV")
    parser.add_argument("--estado", default=None)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    report, json_path, jsonl_path = run_diagnostic(
        obra=args.obra,
        pavimento=args.pav,
        state_path=args.estado,
        db_path=args.db,
        output_root=args.output_root,
    )
    print(json.dumps(report["resumo"], ensure_ascii=False, indent=2))
    print(f"JSON:  {json_path}")
    print(f"JSONL: {jsonl_path}")
    sample = next((item for item in report["itens"] if item["causa_raiz"]), None)
    if sample:
        print("Amostra:")
        print(json.dumps(sample, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
