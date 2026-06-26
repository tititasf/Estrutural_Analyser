# src/core/learning/baseline_runner.py
"""
Baseline Runner - roda um pavimento sem learning e registra o hit rate base.
Permite medir a melhoria real trazida pelo learning store.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Callable, Optional


def run_baseline_detection(
    pavimento_path: str,
    class_type: str,
    project_uuid: str,
    detection_fn: Callable,
    ground_truth_fn: Callable,
    base_dir: str = "",
) -> dict:
    """Roda deteccao sem learning e calcula hit rate por campo.

    Args:
        pavimento_path: caminho do DXF do pavimento
        class_type: "slab" | "pillar" | "lateral_beam" | "bottom_beam"
        project_uuid: UUID do projeto
        detection_fn: funcao que roda deteccao sem learning params.
            Deve retornar dict: {element_id: {field_name: predicted_value}}
        ground_truth_fn: funcao que retorna ground truth.
            Deve retornar dict: {element_id: {field_name: actual_value}}
        base_dir: diretorio base

    Returns:
        dict com:
            - "class_type": str
            - "pavimento_path": str
            - "timestamp": str
            - "hit_rate_per_field": dict {field_name: hit_rate}
            - "hit_rate_general": float
            - "element_count": int
            - "details": list de dicts por elemento
    """
    # Rodar deteccao sem learning
    detected = detection_fn()
    ground_truth = ground_truth_fn()

    if not detected or not ground_truth:
        return {
            "class_type": class_type,
            "pavimento_path": pavimento_path,
            "timestamp": datetime.now().isoformat(),
            "hit_rate_per_field": {},
            "hit_rate_general": 0.0,
            "element_count": 0,
            "details": [],
            "error": "Deteccao ou ground truth vazios",
        }

    # Comparar campo por campo
    field_hits = {}  # field_name -> [bool, ...]
    field_counts = {}  # field_name -> total
    details = []

    for element_id, gt_fields in ground_truth.items():
        det_fields = detected.get(element_id, {})
        elem_detail = {
            "element_id": element_id,
            "fields": {},
        }
        for field_name, gt_value in gt_fields.items():
            pred_value = det_fields.get(field_name)
            is_correct = _values_match(pred_value, gt_value)

            if field_name not in field_hits:
                field_hits[field_name] = []
                field_counts[field_name] = 0
            field_hits[field_name].append(is_correct)
            field_counts[field_name] += 1

            elem_detail["fields"][field_name] = {
                "predicted": pred_value,
                "actual": gt_value,
                "correct": is_correct,
            }
        details.append(elem_detail)

    # Calcular hit rates
    hit_rate_per_field = {}
    total_hits = 0
    total_fields = 0
    for field_name, hits in field_hits.items():
        hr = sum(hits) / len(hits) if hits else 0.0
        hit_rate_per_field[field_name] = round(hr, 4)
        total_hits += sum(hits)
        total_fields += len(hits)

    hit_rate_general = total_hits / total_fields if total_fields else 0.0

    result = {
        "class_type": class_type,
        "pavimento_path": pavimento_path,
        "timestamp": datetime.now().isoformat(),
        "hit_rate_per_field": hit_rate_per_field,
        "hit_rate_general": round(hit_rate_general, 4),
        "element_count": len(ground_truth),
        "field_count": total_fields,
        "details": details,
    }

    # Salvar baseline
    baseline_dir = os.path.join(
        base_dir or os.getcwd(),
        "projects_repo", project_uuid, "learning"
    )
    os.makedirs(baseline_dir, exist_ok=True)

    ts_safe = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    baseline_path = os.path.join(
        baseline_dir, f"baseline_{class_type}_{ts_safe}.json"
    )

    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Log
    print(f"[BASELINE] {class_type} - {pavimento_path}")
    for fn, hr in hit_rate_per_field.items():
        status = "OK" if hr >= 0.8 else "WARN" if hr >= 0.5 else "BAD"
        print(f"  {fn}: {hr*100:.1f}% [{status}]")
    print(f"  Geral: {hit_rate_general*100:.1f}%")
    print(f"  Salvo: {baseline_path}")

    return result


def _values_match(predicted: Any, actual: Any, tolerance: float = 0.01) -> bool:
    """Compara dois valores com tolerancia para floats."""
    if predicted is None or actual is None:
        return predicted == actual
    if isinstance(predicted, (int, float)) and isinstance(actual, (int, float)):
        return abs(predicted - actual) <= tolerance
    if isinstance(predicted, str) and isinstance(actual, str):
        return predicted.strip().upper() == actual.strip().upper()
    return predicted == actual
