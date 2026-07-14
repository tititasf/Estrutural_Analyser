#!/usr/bin/env python3
"""Paridade declarativa contrato → payload → DXF → HTML por campo/variante."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ezdxf

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.arete.qa_content_cache import ContentAddressedCache, content_hash
from scripts.arete.qa_n1_field_probe import (
    evaluate_check,
    select_path,
    summarize_value,
    transform_value,
)


ENGINE_VERSION = "1.1.0"
SPEC_SCHEMA = "arete.qa_artifact_parity/v1"
RESULT_SCHEMA = "arete.qa_artifact_parity_result/v1"
DEFAULT_CACHE = Path(__file__).resolve().parent / ".cache" / "qa_fastpaths"
DEFAULT_REPORTS = Path(__file__).resolve().parent / "relatorios" / "qa_artifact_parity"


def _sha256_file(path: Path) -> str:
    digest = __import__("hashlib").sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_path(base_dir: Path, raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser()
    return (base_dir / path).resolve() if not path.is_absolute() else path.resolve()


def _load_variant(base_dir: Path, name: str, spec: dict[str, Any]) -> dict[str, Any]:
    loaded: dict[str, Any] = {"name": name, "paths": {}, "hashes": {}, "data": {}}
    for source in ("contract", "payload", "html", "dxf"):
        path = _resolve_path(base_dir, spec.get(source))
        if path is None:
            continue
        if not path.is_file():
            raise ValueError(f"artefato ausente: {name}.{source}={path}")
        loaded["paths"][source] = str(path)
        loaded["hashes"][source] = _sha256_file(path)
        if source in {"contract", "payload"}:
            loaded["data"][source] = json.loads(path.read_text(encoding="utf-8"))
        elif source == "html":
            loaded["data"][source] = path.read_text(encoding="utf-8", errors="replace")
        else:
            loaded["data"][source] = ezdxf.readfile(path)
    return loaded


def _dxf_value(document: Any, source: str, path: str) -> Any:
    modelspace = document.modelspace()
    if source == "dxf_entity_count":
        kind = path.upper()
        return sum(entity.dxftype() == kind for entity in modelspace)
    if source == "dxf_layer_count":
        return sum(str(entity.dxf.layer) == path for entity in modelspace)
    if source == "dxf_header":
        return document.header.get(path)
    if source in {"dxf_texts", "dxf_text_blob"}:
        texts: list[str] = []
        for entity in modelspace:
            kind = entity.dxftype()
            if kind in {"TEXT", "ATTRIB", "ATTDEF"}:
                value = str(entity.dxf.text or "").strip()
            elif kind == "MTEXT":
                value = str(entity.plain_text() or "").strip()
            else:
                continue
            if value:
                texts.append(value)
        return "\n".join(texts) if source == "dxf_text_blob" else texts
    if source == "dxf_layers":
        return sorted({str(entity.dxf.layer) for entity in modelspace})
    if source == "dxf_entity_types":
        return sorted({entity.dxftype() for entity in modelspace})
    if source == "dxf_xdata":
        values: list[Any] = []
        for entity in modelspace:
            try:
                tags = entity.get_xdata(path)
            except (ezdxf.DXFValueError, ValueError):
                continue
            values.extend(tag.value for tag in tags)
        return values
    raise ValueError(f"fonte DXF desconhecida: {source}")


def run_parity(
    spec: dict[str, Any], *, base_dir: Path,
    cache: ContentAddressedCache | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    if spec.get("schema") != SPEC_SCHEMA:
        raise ValueError(f"schema esperado: {SPEC_SCHEMA}")
    variants_spec = spec.get("variants")
    if not isinstance(variants_spec, dict) or not variants_spec:
        raise ValueError("spec exige variants")
    fields_spec = spec.get("fields")
    checks_spec = spec.get("checks")
    if not isinstance(fields_spec, list) or not fields_spec:
        raise ValueError("spec exige fields não vazio")
    if not isinstance(checks_spec, list) or not checks_spec:
        raise ValueError("spec exige checks não vazio")
    empty_variants = [
        name for name, row in variants_spec.items()
        if not isinstance(row, dict)
        or not any(row.get(key) for key in ("contract", "payload", "dxf", "html"))
    ]
    if empty_variants:
        raise ValueError(f"variants sem artefatos: {', '.join(empty_variants)}")
    variants = {
        name: _load_variant(base_dir, name, variant_spec)
        for name, variant_spec in variants_spec.items()
    }
    input_hashes = {
        f"{variant}.{source}": digest
        for variant, loaded in variants.items()
        for source, digest in loaded["hashes"].items()
    }
    cache_inputs = {"spec": spec, "input_hashes": input_hashes}

    def compute() -> dict[str, Any]:
        values: dict[str, Any] = {}
        fields: list[dict[str, Any]] = []
        for field in fields_spec:
            field_id = str(field.get("id") or "")
            variant_name = str(field.get("variant") or "")
            source = str(field.get("source") or "")
            path = str(field.get("path") or "")
            transform = str(field.get("transform") or "raw")
            if not field_id or variant_name not in variants:
                raise ValueError("field exige id e variant existente")
            variant = variants[variant_name]
            if source in {"contract", "payload", "html"}:
                if source not in variant["data"]:
                    raise ValueError(f"artefato requerido ausente: {variant_name}.{source}")
                data = variant["data"].get(source)
                raw = select_path(data, path) if path else data
            elif source.startswith("dxf_"):
                document = variant["data"].get("dxf")
                if document is None:
                    raise ValueError(f"artefato requerido ausente: {variant_name}.dxf")
                raw = _dxf_value(document, source, path) if document is not None else None
            else:
                raise ValueError(f"source desconhecido: {source}")
            value = transform_value(raw, transform)
            values[field_id] = value
            fields.append({
                "id": field_id, "variant": variant_name, "source": source,
                "path": path, "transform": transform, "value": summarize_value(value),
                "artifact_hash": variant["hashes"].get("dxf" if source.startswith("dxf_") else source),
            })
        checks = [evaluate_check(check, values) for check in checks_spec]
        statuses = {check["status"] for check in checks}
        overall = "FAIL" if "FAIL" in statuses else "PENDENTE" if "PENDENTE" in statuses else "PASS"
        return {
            "schema": RESULT_SCHEMA,
            "engine_version": ENGINE_VERSION,
            "question": str(spec.get("question") or ""),
            "overall": overall,
            "scope_authority": "declared_artifact_fields_only; visual reading remains separate",
            "variants": {
                name: {"paths": loaded["paths"], "hashes": loaded["hashes"]}
                for name, loaded in variants.items()
            },
            "fields": fields,
            "checks": checks,
            "provenance": {
                "chain": [
                    source for source in ("contract", "payload", "dxf", "html")
                    if any(source in loaded["paths"] for loaded in variants.values())
                ],
                "missing_dxf_metadata": any(
                    field["source"] == "dxf_xdata" and not field["value"] for field in fields
                ),
            },
        }

    if cache is None:
        result, hit, cache_key, cache_path = compute(), False, None, None
    else:
        cached = cache.get_or_compute(
            "artifact_parity", engine_version=ENGINE_VERSION, inputs=cache_inputs,
            compute=compute, input_hashes=input_hashes,
        )
        result, hit, cache_key, cache_path = cached.value, cached.hit, cached.key, str(cached.path)
    result = copy.deepcopy(result)
    result["executed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result["runtime"] = {
        "cache_hit": hit, "cache_key": cache_key, "cache_path": cache_path,
        "total_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "variants": len(variants), "fields": len(fields_spec),
        "checks": len(checks_spec),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica paridade declarada entre contrato, payload, DXF e HTML.")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)
    spec_path = args.spec.resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    result = run_parity(
        spec, base_dir=spec_path.parent,
        cache=ContentAddressedCache(args.cache_dir, enabled=not args.no_cache),
    )
    output = args.out.resolve() if args.out else DEFAULT_REPORTS / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{content_hash(spec)[:10]}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"overall": result["overall"], "out": str(output), "cache_hit": result["runtime"]["cache_hit"]}, ensure_ascii=False))
    return 0 if result["overall"] == "PASS" else 1 if result["overall"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
