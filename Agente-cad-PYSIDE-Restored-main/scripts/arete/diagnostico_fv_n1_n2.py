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

import ezdxf


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_STATE_ROOT = SCRIPT_DIR / "html_fichas"
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "relatorios" / "diagnosticos_fv"
SEGMENT_LENGTH_TOLERANCE_CM = 0.05


def _slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))
    return clean.strip("._") or "item"


def _float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _repeat_count(value: Any) -> int | None:
    """Retorna repetição física declarada em formas como 5, "5x" ou "x5"."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        count = int(value)
        return count if count > 1 and abs(float(value) - count) <= 1e-6 else None
    text = str(value or "").strip().lower().replace("×", "x")
    match = re.fullmatch(r"(?:x\s*)?(\d+)\s*x?", text)
    if not match:
        return None
    count = int(match.group(1))
    return count if count > 1 else None


def _segment_json_repeat(segment: dict) -> int:
    for key in (
        "_multiplier",
        "multiplier",
        "multiplicador",
        "repeticoes",
        "repetições",
        "repeat",
        "repeats",
        "count",
        "quantity",
        "qtd",
    ):
        count = _repeat_count(segment.get(key))
        if count:
            return count
    return 1


def _dxf_text_entities(path: Path) -> list[tuple[str, float, float]]:
    if not path.is_file():
        return []
    try:
        doc = ezdxf.readfile(path)
    except Exception:
        return []
    texts: list[tuple[str, float, float]] = []
    for entity in doc.modelspace():
        try:
            if entity.dxftype() == "TEXT":
                text = str(entity.dxf.text or "").strip()
                point = entity.dxf.insert
            elif entity.dxftype() == "MTEXT":
                text = str(entity.text or "").strip()
                point = entity.dxf.insert
            else:
                continue
        except Exception:
            continue
        if text:
            texts.append((text, float(point.x), float(point.y)))
    return texts


def _dxf_length_multipliers(path_value: Any) -> dict[float, int]:
    """Mapeia comprimento -> multiplicador físico usando textos do recorte N2.

    O motor reverso antigo nem sempre persistiu `_multiplier` em `segments_rich`.
    No recorte, porém, a cota multiplicadora aparece como texto `5x` próximo da
    cota de comprimento que ela repete. Ex.: V306 tem `5x` alinhado ao texto
    `418`, então o segmento de 418 cm representa cinco segmentos físicos.
    """
    path = Path(str(path_value or ""))
    texts = _dxf_text_entities(path)
    if not texts:
        return {}

    numbers: list[tuple[float, float, float]] = []
    multipliers: list[tuple[int, float, float]] = []
    for text, x, y in texts:
        clean = text.replace(",", ".").replace("×", "x").strip()
        count = _repeat_count(clean) if "x" in clean.lower() else None
        if count:
            multipliers.append((count, x, y))
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", clean):
            value = _float(clean)
            if value is not None:
                numbers.append((value, x, y))

    result: dict[float, int] = {}
    for count, mx, my in multipliers:
        candidates = []
        for value, nx, ny in numbers:
            dx = abs(nx - mx)
            dy = abs(ny - my)
            # Nas fichas FV a cota "Nx" fica colada acima/abaixo da cota que
            # multiplica. Mantemos tolerância ampla em desenho, mas exigimos
            # proximidade real para não aplicar multiplicador a qualquer texto.
            if dx <= 35.0 and dy <= 80.0:
                candidates.append((dx + dy * 0.25, value))
        if not candidates:
            continue
        _, length = min(candidates, key=lambda item: item[0])
        result[round(float(length), 3)] = max(count, result.get(round(float(length), 3), 1))
    return result


def _n2_source_dxf_path(data: dict) -> Any:
    meta = data.get("_er_meta")
    if isinstance(meta, dict) and meta.get("dxf_path"):
        return meta.get("dxf_path")
    # Registros antigos podem acumular snapshots aninhados em _fase4_ref.
    ref = data.get("_fase4_ref")
    seen = 0
    while isinstance(ref, dict) and seen < 8:
        meta = ref.get("_er_meta")
        if isinstance(meta, dict) and meta.get("dxf_path"):
            return meta.get("dxf_path")
        ref = ref.get("_fase4_ref")
        seen += 1
    return None


def _n2_segment_lengths(data: dict) -> tuple[list[float], list[dict]]:
    segments = data.get("segments_rich") or data.get("panels") or []
    dxf_multipliers = _dxf_length_multipliers(_n2_source_dxf_path(data))
    physical_lengths: list[float] = []
    details: list[dict] = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue
        length = _float(segment.get("total_width") or segment.get("width"))
        if length is None:
            continue
        multiplier = _segment_json_repeat(segment)
        if multiplier == 1:
            multiplier = dxf_multipliers.get(round(float(length), 3), 1)
        physical_lengths.extend([length] * multiplier)
        details.append({
            "index": index,
            "comprimento_cm": length,
            "multiplicador": multiplier,
            "origem_multiplicador": (
                "json" if _segment_json_repeat(segment) > 1
                else "dxf_text" if multiplier > 1
                else "unitario"
            ),
        })
    return physical_lengths, details


def _relative_delta(detected: float | None, expected: float | None) -> float | None:
    if detected is None or expected is None:
        return None
    return abs(detected - expected) / max(abs(expected), 1e-9)


def _compare_segment_measures(
    detected: list[float],
    expected: list[float],
    tolerance: float = SEGMENT_LENGTH_TOLERANCE_CM,
) -> dict:
    """Compara o multiconjunto de comprimentos físicos dos segmentos.

    A ordem de emissão no estado N1 não é contrato. Por isso os comprimentos são
    ordenados antes do pareamento; posição e sequência permanecem sob o N1-V.
    """
    n1_values = sorted(float(value) for value in detected)
    n2_values = sorted(float(value) for value in expected)
    pairs = []
    for index in range(max(len(n1_values), len(n2_values))):
        n1_value = n1_values[index] if index < len(n1_values) else None
        n2_value = n2_values[index] if index < len(n2_values) else None
        delta = (
            abs(n1_value - n2_value)
            if n1_value is not None and n2_value is not None
            else None
        )
        pairs.append({
            "n1_cm": n1_value,
            "n2_cm": n2_value,
            "delta_abs_cm": delta,
            "passa": delta is not None and delta <= tolerance,
        })
    return {
        "tolerancia_cm": tolerance,
        "metodo": "multiconjunto_ordenado",
        "match": len(n1_values) == len(n2_values)
        and all(pair["passa"] for pair in pairs),
        "pares": pairs,
    }


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


def _segment_physical_length(segment: dict) -> float | None:
    measure_source = str(segment.get("measure_source") or "")
    if measure_source.startswith("special_diagonal") or measure_source.startswith(
        "chamfer_half_cm_snap"
    ):
        measured = _float(segment.get("measure_length"))
        if measured is None:
            measured = _float(segment.get("length"))
        if measured is not None:
            return measured
    declared = _float(segment.get("length"))
    bbox = _geometry_long_span(segment.get("points"))
    points = segment.get("points") or []
    if (
        declared is not None
        and bbox is not None
        and len(points) >= 6
        and bbox > declared * 1.15
    ):
        return declared
    return _geometry_long_span(segment.get("points"))


def _segment_physical_width(segment: dict) -> float | None:
    if str(segment.get("measure_source") or "").startswith("special_diagonal"):
        measured = _float(segment.get("measure_width"))
        if measured is not None:
            return measured
    return _float(segment.get("width"))


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
        widths = [
            value
            for value in (_segment_physical_width(item) for item in segments)
            if value is not None
        ]
        geometry_spans = [
            value
            for value in (_segment_physical_length(item) for item in segments)
            if value is not None
        ]
        physical_lengths = (
            geometry_spans
            if len(geometry_spans) == len(segments)
            else lengths
        )
        beams[name] = {
            "largura": statistics.median(widths) if widths else None,
            "larguras": widths,
            "comprimento_total": sum(physical_lengths) if physical_lengths else None,
            "comprimentos": physical_lengths,
            "comprimento_declarado_total": sum(lengths) if lengths else None,
            "comprimento_geometrico_total": sum(geometry_spans) if geometry_spans else None,
            "segmentos": len(segments),
            "furos_ativos": None,
        }
    return state, beams


def _n2_length(data: dict) -> float | None:
    physical_lengths, _ = _n2_segment_lengths(data)
    if physical_lengths:
        return sum(physical_lengths)
    declared = _float(data.get("total_height"))
    return declared


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
        segment_lengths, segment_details = _n2_segment_lengths(data)
        holes = data.get("holes") or []
        beams[name] = {
            "largura": _float(data.get("total_width") or data.get("largura_total_fundo")),
            "comprimento_total": (
                sum(segment_lengths) if segment_lengths else _n2_length(data)
            ),
            "comprimentos": segment_lengths,
            "segmentos": len(segment_lengths),
            "segmentos_logicos": len(segment_details),
            "detalhe_segmentos_n2": segment_details,
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
    segment_measure_comparison = (
        _compare_segment_measures(
            list(n1.get("comprimentos") or []),
            list(n2.get("comprimentos") or []),
        )
        if n1 is not None and n2 is not None
        else None
    )
    segment_measures_match = bool(
        segment_measure_comparison
        and segment_measure_comparison["match"]
    )

    if n1 is None or n2 is None:
        cause = "schema_gap"
        description = (
            "Item presente apenas no N2; falta representação FV no estado N1."
            if n1 is None
            else "Item presente apenas no N1; falta ficha FV correspondente no N2."
        )
        confidence = 0.99
    elif not segments_match:
        cause = "schema_gap"
        description = (
            "A quantidade física de segmentos do fundo diverge entre N1 e N2."
        )
        confidence = 0.95
    elif not segment_measures_match:
        cause = "extractor_bug"
        description = (
            "A quantidade de segmentos coincide, mas uma ou mais medidas individuais "
            "divergem além de ±0,05 cm."
        )
        confidence = 0.95
    elif quality in {"REGULAR", "RUIM"}:
        cause = "extractor_bug"
        description = (
            "Dimensões do fundo de viga divergem entre a interpretação N1 e a ficha N2."
        )
        confidence = 0.95 if quality == "RUIM" else 0.85
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
        "medidas_segmentos_match": segment_measures_match,
        "comparacao_medidas_segmentos": segment_measure_comparison,
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
    comparable_segments = [
        item for item in items
        if item["evidencia"]["n1"] is not None
        and item["evidencia"]["n2"] is not None
    ]
    segment_count_pass = sum(
        bool(item["evidencia"]["segmentos_match"])
        for item in comparable_segments
    )
    segment_measure_pass = sum(
        bool(item["evidencia"]["medidas_segmentos_match"])
        for item in comparable_segments
    )
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
            "segmentacao": {
                "comparaveis": len(comparable_segments),
                "quantidade_pass": segment_count_pass,
                "quantidade_fail": len(comparable_segments) - segment_count_pass,
                "medidas_pass": segment_measure_pass,
                "medidas_fail": len(comparable_segments) - segment_measure_pass,
                "tolerancia_medida_cm": SEGMENT_LENGTH_TOLERANCE_CM,
            },
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
