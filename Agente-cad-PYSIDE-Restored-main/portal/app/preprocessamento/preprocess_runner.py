"""Execução isolada do pré-processamento pelo worker do portal.

O job publica pacotes de contexto; o consumo posterior pelo SA é opcional e
independente deste processo. Nenhum estado estrutural é alterado aqui.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any, Mapping

from .runner import RunnerError
from .service import read_tower, run_floor
from ..structural_review import inventory_items, load, status, restore_generated


_SAFE = re.compile(r"^[A-Za-z0-9_.-]+$")


def execute_inventory_job(
    *, obra_dir: Path, obra_id: str, pavimento: str, job_id: str,
    frozen_sources: Mapping[str, str], declarations: list[dict[str, str]],
    progress=None, known_floors=(),
) -> dict[str, Any]:
    if (not _SAFE.fullmatch(pavimento) or ".." in pavimento
            or not _SAFE.fullmatch(job_id) or ".." in job_id):
        raise RunnerError("identidade do job ou pavimento inválida")
    started_at = time.time()
    result = run_floor(
        obra_dir=obra_dir, obra_id=obra_id, pavimento=pavimento,
        declarations=declarations, frozen_sources=dict(frozen_sources), run_id=job_id,
        progress=progress, known_floors=known_floors,
    )
    level_observed = 0
    candidate_segments = 0
    collected_segments = 0
    items_with_levels = 0
    interpreted_cut_count = 0
    decisions = load(obra_dir, pavimento)
    for source_id, reference in result["towers"].items():
        if reference["status"] == "failed":
            continue
        package = read_tower(obra_dir, result, source_id)
        restore_generated(obra_dir, pavimento, started_at,
                          inventory=package.get('beam_sections') or {})
        decisions = load(obra_dir, pavimento)
        interpreted_cut_count += sum(status(decisions, uid, entry) != 'deleted'
            for uid, entry in inventory_items(package.get('beam_sections') or {}))
        level_data = package.get("level_inventory") or {}
        level_observed += (level_data.get("coverage") or {}).get("slab_levels_observed", 0)
        candidate_segments += (level_data.get("segment_coverage") or {}).get("candidate_segments", 0)
        collected_segments += (level_data.get('sa_evidence') or {}).get('segments', 0)
        items_with_levels += (level_data.get('sa_evidence') or {}).get('items_with_levels', 0)
    return {
        "status": result["status"],
        "run_id": result["run_id"],
        "tower_count": len(result["towers"]),
        "source_count": len(result["sources"]),
        "coverage": result["coverage"],
        "level_observed": level_observed,
        "candidate_segments": candidate_segments,
        "collected_segments": collected_segments,
        "items_with_levels": items_with_levels,
        "interpreted_cut_count": interpreted_cut_count,
        "sa_consumption": result['sa_consumption'],
    }
