"""Compatibilidade de payload PIL entre snapshots desktop e headless."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def hydrate_pillar_lajes_from_db(
    db_path: str | Path, project_id: str, pillars: list[dict],
) -> int:
    """Restaura vínculos de laje preservando as duas chaves históricas.

    A UI antiga gravava ``lajes_adjacentes``; o N1 headless grava ``lajes``.
    Consumidores sem essa compatibilidade fazem uma obra virgem parecer sem
    lajes e alteram indevidamente as regras de borda/topo.
    """
    by_name = {
        str(pillar.get("name") or "").strip().upper(): pillar
        for pillar in pillars or [] if isinstance(pillar, dict)
    }
    changed = 0
    connection = sqlite3.connect(str(db_path))
    try:
        rows = connection.execute(
            "SELECT name, extra_data_json FROM pillars WHERE project_id=?",
            (project_id,),
        ).fetchall()
    finally:
        connection.close()
    for name, raw_extra in rows:
        pillar = by_name.get(str(name or "").strip().upper())
        if pillar is None:
            continue
        try:
            extra = json.loads(raw_extra or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        lajes = extra.get("lajes") or extra.get("lajes_adjacentes") or []
        if lajes and pillar.get("lajes") != lajes:
            pillar["lajes"] = lajes
            changed += 1
        # Metadados geométricos são necessários para faces especiais A-F.
        # O loader visual histórico lia apenas ``format`` e descartava o
        # ``shape_type`` canônico produzido pelo detector.
        for key in (
            "shape_type", "classification", "format", "geometry_type",
            "face_ids", "face_geometry",
        ):
            if extra.get(key) is not None and pillar.get(key) != extra.get(key):
                pillar[key] = extra[key]
    return changed
