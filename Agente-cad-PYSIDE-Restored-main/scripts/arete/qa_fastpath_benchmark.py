#!/usr/bin/env python3
"""Benchmark reproduzível dos probes N1 ultragranulares.

Compara a execução sem reutilização com o caminho aquecido pelo cache. O
benchmark mede somente o request declarado; não certifica item, ficha ou gate.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.arete.qa_content_cache import ContentAddressedCache
from scripts.arete.qa_n1_field_probe import DEFAULT_CACHE, DEFAULT_DB, run_probe


SCHEMA = "arete.qa_fastpath_benchmark/v1"


def _stats(samples: list[float]) -> dict[str, float]:
    return {
        "min_ms": round(min(samples), 3),
        "median_ms": round(statistics.median(samples), 3),
        "max_ms": round(max(samples), 3),
        "mean_ms": round(statistics.fmean(samples), 3),
    }


def benchmark_probe(
    con: sqlite3.Connection,
    request: dict[str, Any],
    *,
    iterations: int,
    cache_dir: Path,
    project_id: str | None = None,
    obra: str | None = None,
    pav: str | None = None,
) -> dict[str, Any]:
    if iterations < 1:
        raise ValueError("iterations deve ser >= 1")

    uncached: list[float] = []
    uncached_result: dict[str, Any] | None = None
    disabled_cache = ContentAddressedCache(cache_dir, enabled=False)
    for _ in range(iterations):
        uncached_result = run_probe(
            con, request, project_id=project_id, obra=obra, pav=pav,
            cache=disabled_cache,
        )
        uncached.append(float(uncached_result["runtime"]["total_ms"]))

    enabled_cache = ContentAddressedCache(cache_dir)
    seed = run_probe(
        con, request, project_id=project_id, obra=obra, pav=pav,
        cache=enabled_cache,
    )
    warm: list[float] = []
    warm_hits = 0
    warm_result: dict[str, Any] | None = None
    for _ in range(iterations):
        warm_result = run_probe(
            con, request, project_id=project_id, obra=obra, pav=pav,
            cache=enabled_cache,
        )
        warm.append(float(warm_result["runtime"]["total_ms"]))
        warm_hits += int(bool(warm_result["runtime"]["cache_hit"]))

    assert uncached_result is not None and warm_result is not None
    uncached_stats = _stats(uncached)
    warm_stats = _stats(warm)
    baseline = uncached_stats["median_ms"]
    accelerated = warm_stats["median_ms"]
    speedup = baseline / accelerated if accelerated > 0 else None
    return {
        "schema": SCHEMA,
        "executed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope_authority": "performance_only; never validates full item or ficha",
        "iterations": iterations,
        "overall": warm_result["overall"],
        "same_semantic_result": uncached_result["checks"] == warm_result["checks"],
        "uncached": uncached_stats,
        "warm_cache": {
            **warm_stats,
            "hits": warm_hits,
            "seed_hit": bool(seed["runtime"]["cache_hit"]),
        },
        "median_speedup": round(speedup, 3) if speedup is not None else None,
        "loaded_rows_per_run": warm_result["runtime"]["loaded_rows"],
        "requested_fields": warm_result["runtime"]["requested_fields"],
        "requested_checks": warm_result["runtime"]["requested_checks"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mede o fast path de um request N1 de campos.")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--project-id")
    parser.add_argument("--obra")
    parser.add_argument("--pav")
    parser.add_argument("--iterations", type=int, default=15)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    request = json.loads(args.request.read_text(encoding="utf-8"))
    with sqlite3.connect(args.db) as con:
        result = benchmark_probe(
            con, request, iterations=args.iterations, cache_dir=args.cache_dir,
            project_id=args.project_id, obra=args.obra, pav=args.pav,
        )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["same_semantic_result"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
