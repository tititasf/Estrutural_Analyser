from __future__ import annotations

from pathlib import Path

from scripts.arete.qa_fastpath_benchmark import SCHEMA, benchmark_probe
from tests.test_qa_n1_field_probe import _db, _request


def test_benchmark_compares_same_declared_checks_and_hits_cache(tmp_path: Path):
    con = _db()
    result = benchmark_probe(
        con, _request(), iterations=3, cache_dir=tmp_path / "cache",
    )
    assert result["schema"] == SCHEMA
    assert result["same_semantic_result"] is True
    assert result["warm_cache"]["hits"] == 3
    assert result["loaded_rows_per_run"] == 2
    assert result["requested_checks"] == 3
    assert result["scope_authority"].startswith("performance_only")
    con.close()
