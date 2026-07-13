#!/usr/bin/env python3
"""Provas ultragranares de campos/vínculos N1, sem executar o SA completo.

Cada request declara exatamente quais campos ler e quais hipóteses testar. Um
PASS confirma apenas os checks declarados; nunca valida a ficha ou o item inteiro.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.arete.qa_content_cache import ContentAddressedCache, content_hash
from scripts.arete.qa_n1_sources import json_value, load_requested_fields, resolve_project_scope


ENGINE_VERSION = "1.2.0"
REQUEST_SCHEMA = "arete.qa_n1_field_probe/v1"
RESULT_SCHEMA = "arete.qa_n1_field_probe_result/v1"
DEFAULT_DB = Path(r"D:\Agente-cad-PYSIDE\project_data.vision")
DEFAULT_CACHE = Path(__file__).resolve().parent / ".cache" / "qa_fastpaths"
DEFAULT_REPORTS = Path(__file__).resolve().parent / "relatorios" / "qa_field_probes"


class ProbeError(ValueError):
    pass


def _select(value: Any, path: str) -> Any:
    tokens = [token for token in str(path or "").split(".") if token != ""]

    def walk(current: Any, remaining: list[str]) -> Any:
        if not remaining:
            return current
        token, rest = remaining[0], remaining[1:]
        if token == "*":
            values = list(current.values()) if isinstance(current, dict) else current if isinstance(current, list) else []
            return [walk(entry, rest) for entry in values]
        if isinstance(current, dict):
            if token not in current:
                return None
            return walk(current[token], rest)
        if isinstance(current, list) and token.isdigit():
            index = int(token)
            return walk(current[index], rest) if 0 <= index < len(current) else None
        return None

    return walk(value, tokens)


def _flatten(value: Any) -> list[Any]:
    if isinstance(value, list):
        result: list[Any] = []
        for entry in value:
            result.extend(_flatten(entry))
        return result
    return [value]


def _parse_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[+-]?\d+(?:[.,]\d+)?", str(value))
    return float(match.group(0).replace(",", ".")) if match else None


def _dimension(value: Any, *, ordered: bool) -> list[float] | None:
    if isinstance(value, (list, tuple)) and all(isinstance(entry, (int, float)) for entry in value):
        numbers = [float(entry) for entry in value]
    else:
        numbers = [float(raw.replace(",", ".")) for raw in re.findall(r"\d+(?:[.,]\d+)?", str(value or ""))]
    if len(numbers) < 2:
        return None
    pair = numbers[:2]
    return pair if ordered else sorted(pair)


def _collect_points(value: Any) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    if isinstance(value, (list, tuple)):
        if len(value) >= 2 and all(isinstance(entry, (int, float)) for entry in value[:2]):
            points.append((float(value[0]), float(value[1])))
        else:
            for entry in value:
                points.extend(_collect_points(entry))
    elif isinstance(value, dict):
        if "points" in value:
            points.extend(_collect_points(value["points"]))
        elif "pos" in value:
            points.extend(_collect_points(value["pos"]))
    return points


def _bbox(value: Any) -> list[float] | None:
    points = _collect_points(value)
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def _has_trace(value: Any) -> bool:
    if isinstance(value, dict):
        for key in ("source", "points", "pos", "text", "entity", "handle"):
            if key in value and not _missing(value[key]):
                return True
        return any(_has_trace(entry) for entry in value.values())
    if isinstance(value, list):
        return any(_has_trace(entry) for entry in value)
    return False


def _canonical_text(value: Any) -> Any:
    if isinstance(value, list):
        return [_canonical_text(entry) for entry in value]
    if value is None:
        return None
    return " ".join(str(value).strip().upper().split())


def _entity_token(value: Any) -> Any:
    if isinstance(value, list):
        return [_entity_token(entry) for entry in value]
    if value is None:
        return None
    return re.sub(r"[^A-Z0-9_]", "", str(value).upper())


def _transform(value: Any, transform: str) -> Any:
    transform = transform or "raw"
    if transform == "raw":
        return value
    if transform == "text":
        return _canonical_text(value)
    if transform == "entity":
        return _entity_token(value)
    if transform == "number":
        return _parse_number(value)
    if transform == "dimension":
        return _dimension(value, ordered=True)
    if transform == "dimension_set":
        return _dimension(value, ordered=False)
    if transform == "bbox":
        return _bbox(value)
    if transform == "count":
        return len(value) if isinstance(value, (list, dict, str)) else 0 if value is None else 1
    if transform == "trace":
        return _has_trace(value)
    if transform == "flatten":
        return _flatten(value)
    raise ProbeError(f"transform desconhecido: {transform}")


def _missing(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _bbox_distance(left: list[float], right: list[float]) -> float:
    dx = max(left[0] - right[2], right[0] - left[2], 0.0)
    dy = max(left[1] - right[3], right[1] - left[3], 0.0)
    return math.hypot(dx, dy)


def _as_bbox(value: Any) -> list[float] | None:
    if isinstance(value, list) and len(value) == 4 and all(isinstance(entry, (int, float)) for entry in value):
        return [float(entry) for entry in value]
    return _bbox(value)


def _summary(value: Any, limit: int = 1200) -> Any:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(raw) <= limit:
        return value
    return {"truncated": True, "sha256": content_hash(value), "preview": raw[:limit]}


def _check(check: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    check_id = str(check.get("id") or "").strip()
    operation = str(check.get("op") or "").strip()
    if not check_id or not operation:
        raise ProbeError("todo check exige id e op")
    left_id = check.get("left")
    left = values.get(left_id) if left_id else None
    has_right_alias = "right" in check
    right = values.get(check.get("right")) if has_right_alias else check.get("value")
    right_required = operation not in {"present", "trace", "absent"}
    missing_refs = []
    if left_id and _missing(left) and operation not in {"present", "absent"}:
        missing_refs.append(str(left_id))
    if right_required and _missing(right):
        missing_refs.append(str(check.get("right") or "value"))
    if missing_refs:
        return {
            "id": check_id, "op": operation, "status": "PENDENTE",
            "reason": "campo necessário ausente: " + ", ".join(missing_refs),
            "left": _summary(left), "right": _summary(right),
        }

    tolerance = float(check.get("tolerance", 0.05))
    passed = False
    metric: dict[str, Any] = {}
    if operation == "present":
        passed = not _missing(left)
    elif operation == "absent":
        passed = _missing(left)
    elif operation == "trace":
        passed = _has_trace(left) if not isinstance(left, bool) else left
    elif operation == "equal":
        passed = left == right
    elif operation == "not_equal":
        passed = left != right
    elif operation == "same_entity":
        passed = _entity_token(left) == _entity_token(right)
    elif operation == "number_close":
        left_number, right_number = _parse_number(left), _parse_number(right)
        if left_number is None or right_number is None:
            return {"id": check_id, "op": operation, "status": "PENDENTE", "reason": "valor não numérico", "left": left, "right": right}
        metric = {"delta": abs(left_number - right_number), "tolerance": tolerance}
        passed = metric["delta"] <= tolerance
    elif operation == "dimension_equal":
        ordered = bool(check.get("order_sensitive", True))
        left_dim, right_dim = _dimension(left, ordered=ordered), _dimension(right, ordered=ordered)
        if left_dim is None or right_dim is None:
            return {"id": check_id, "op": operation, "status": "PENDENTE", "reason": "dimensão incompleta", "left": left, "right": right}
        deltas = [abs(a - b) for a, b in zip(left_dim, right_dim)]
        metric = {"deltas": deltas, "tolerance": tolerance, "order_sensitive": ordered}
        passed = all(delta <= tolerance for delta in deltas)
    elif operation == "contains":
        passed = right in left if isinstance(left, (list, str, dict)) else False
    elif operation == "one_of":
        passed = left in right if isinstance(right, list) else False
    elif operation in {"bbox_distance_le", "bbox_intersects"}:
        left_bbox, right_bbox = _as_bbox(left), _as_bbox(right)
        if not (isinstance(left_bbox, list) and len(left_bbox) == 4 and isinstance(right_bbox, list) and len(right_bbox) == 4):
            return {"id": check_id, "op": operation, "status": "PENDENTE", "reason": "bbox indisponível", "left": _summary(left), "right": _summary(right)}
        distance = _bbox_distance(left_bbox, right_bbox)
        threshold = 0.0 if operation == "bbox_intersects" else tolerance
        metric = {"distance": distance, "threshold": threshold}
        passed = distance <= threshold
    else:
        raise ProbeError(f"op desconhecida: {operation}")
    return {
        "id": check_id, "op": operation, "status": "PASS" if passed else "FAIL",
        "reason": str(check.get("reason") or f"{operation} {'satisfeita' if passed else 'divergente'}"),
        "left": _summary(left), "right": _summary(right), "metric": metric,
    }


# API compartilhada pelos fast paths de artefato. Mantém uma única semântica
# para seleção, transformação e checks, sem acoplar o motor ao CLI N1.
select_path = _select
transform_value = _transform
evaluate_check = _check
summarize_value = _summary


def _validate_request(request: dict[str, Any]) -> None:
    if request.get("schema") != REQUEST_SCHEMA:
        raise ProbeError(f"schema esperado: {REQUEST_SCHEMA}")
    fields = request.get("fields")
    checks = request.get("checks")
    if not isinstance(fields, list) or not fields:
        raise ProbeError("request exige fields não vazio")
    if not isinstance(checks, list) or not checks:
        raise ProbeError("request exige checks não vazio")
    ids = [str(field.get("id") or "") for field in fields]
    if any(not field_id for field_id in ids) or len(ids) != len(set(ids)):
        raise ProbeError("ids de fields devem ser únicos e não vazios")


def run_probe(
    con: sqlite3.Connection, request: dict[str, Any], *,
    project_id: str | None = None, obra: str | None = None, pav: str | None = None,
    overlay: dict[str, Any] | None = None,
    cache: ContentAddressedCache | None = None,
) -> dict[str, Any]:
    """Executa somente os campos/checks declarados e retorna prova limitada."""
    started = time.perf_counter()
    request = copy.deepcopy(request)
    overlay = copy.deepcopy(overlay or {})
    _validate_request(request)
    resolved_project = resolve_project_scope(
        con, project_id=project_id or request.get("project_id"),
        obra=obra or request.get("obra"), pav=pav or request.get("pav"),
    )
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for field in request["fields"]:
        classe = str(field.get("class") or "").upper()
        item = str(field.get("item") or "").strip()
        if not classe or not item:
            raise ProbeError("todo field exige class e item")
        grouped.setdefault((classe, item), []).append(field)

    loaded: dict[tuple[str, str], dict[str, Any]] = {}
    for key, fields in grouped.items():
        loaded[key] = load_requested_fields(
            con, project_id=resolved_project, classe=key[0], item=key[1],
            fields=fields,
        )
    loaded_ms = (time.perf_counter() - started) * 1000.0
    snapshots = {f"{classe}:{item}": row["snapshot_hash"] for (classe, item), row in loaded.items()}
    cache_inputs = {
        "project_id": resolved_project,
        "request": request,
        "overlay": overlay,
        "snapshots": snapshots,
    }

    def compute() -> dict[str, Any]:
        values: dict[str, Any] = {}
        field_rows: list[dict[str, Any]] = []
        overrides = overlay.get("fields", {}) if isinstance(overlay.get("fields", {}), dict) else {}
        for field in request["fields"]:
            field_id = str(field["id"])
            classe = str(field["class"]).upper()
            item = str(field["item"])
            source = str(field.get("source") or "payload")
            transform = str(field.get("transform") or "raw")
            row = loaded[(classe, item)]
            if field_id in overrides:
                raw_value = overrides[field_id]
            else:
                selected = row["raw_fields"][field_id]
                source_value = json_value(selected["value"])
                raw_value = (
                    source_value if selected["preselected"]
                    else _select(source_value, selected["remaining_path"])
                )
            value = _transform(raw_value, transform)
            values[field_id] = value
            field_rows.append({
                "id": field_id, "class": classe, "item": item,
                "source": source, "path": str(field.get("path") or ""),
                "transform": transform, "value": _summary(value),
                "overridden": field_id in overrides,
                "snapshot_hash": row["snapshot_hash"],
                "selected_columns": row["selected_columns"],
            })
        checks = [_check(check, values) for check in request["checks"]]
        statuses = {check["status"] for check in checks}
        overall = "FAIL" if "FAIL" in statuses else "PENDENTE" if "PENDENTE" in statuses else "PASS"
        return {
            "schema": RESULT_SCHEMA,
            "engine_version": ENGINE_VERSION,
            "project_id": resolved_project,
            "question": str(request.get("question") or ""),
            "overall": overall,
            "scope_authority": "field_checks_only; never validates full item or ficha",
            "fields": field_rows,
            "checks": checks,
            "snapshots": snapshots,
            "provenance": {
                "allowed": "persisted N1 + explicit candidate overlay",
                "forbidden": "N2/N4 as N1 proof or N3 input",
                "cross_class": sorted({field["class"].upper() for field in request["fields"]}),
            },
        }

    evaluated_at = time.perf_counter()
    if cache is None:
        result, cache_hit, cache_path, cache_key = compute(), False, None, None
    else:
        cache_result = cache.get_or_compute(
            "n1_field_probe", engine_version=ENGINE_VERSION, inputs=cache_inputs,
            compute=compute, input_hashes=snapshots,
        )
        result = cache_result.value
        cache_hit, cache_path, cache_key = cache_result.hit, str(cache_result.path), cache_result.key
    total_ms = (time.perf_counter() - started) * 1000.0
    result["executed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result["runtime"] = {
        "cache_hit": cache_hit, "cache_key": cache_key, "cache_path": cache_path,
        "db_load_ms": round(loaded_ms, 3),
        "evaluation_ms": round((time.perf_counter() - evaluated_at) * 1000.0, 3),
        "total_ms": round(total_ms, 3),
        "loaded_rows": len(loaded), "requested_fields": len(request["fields"]),
        "requested_checks": len(request["checks"]),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Testa campos/vínculos N1 específicos, inclusive cross-classe, sem headless completo."
    )
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--project-id")
    parser.add_argument("--obra")
    parser.add_argument("--pav")
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)
    request = json.loads(args.request.read_text(encoding="utf-8"))
    overlay = json.loads(args.overlay.read_text(encoding="utf-8")) if args.overlay else None
    cache = ContentAddressedCache(args.cache_dir, enabled=not args.no_cache)
    with sqlite3.connect(args.db) as con:
        result = run_probe(
            con, request, project_id=args.project_id, obra=args.obra, pav=args.pav,
            overlay=overlay, cache=cache,
        )
    if args.out:
        output = args.out.resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = DEFAULT_REPORTS / f"{timestamp}_{content_hash(request)[:10]}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "overall": result["overall"], "out": str(output),
        "cache_hit": result["runtime"]["cache_hit"],
        "total_ms": result["runtime"]["total_ms"],
    }, ensure_ascii=False))
    return 1 if result["overall"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
