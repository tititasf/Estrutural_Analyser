"""Atualiza a vista com tags a partir da tabela ABCD consultiva do portal."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path


def _source_dxf(obra_dir: Path, estado: dict) -> Path | None:
    db_path = Path(str(estado.get("db_path") or ""))
    if not db_path.is_file():
        return None
    project_id = None
    for segment in ((estado.get("segmentos") or {}).get("fundo") or []):
        match = re.search(r"\|([a-f0-9-]{36})_b_", str(segment.get("uid") or ""))
        if match:
            project_id = match.group(1)
            break
    if not project_id:
        return None
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute("SELECT dxf_path FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row or not row[0]:
        return None
    path = Path(row[0]).resolve()
    return path if path.is_file() and path.is_relative_to(obra_dir.resolve()) else None


def refreshed_tag_svg(obra_dir: Path, pavimento: str, pillar_name: str,
                      estado: dict, tables: dict) -> str | None:
    pillar = next((p for p in estado.get("pilares") or [] if p.get("name") == pillar_name), None)
    if not pillar or not pillar.get("points"):
        return None
    source = _source_dxf(obra_dir, estado)
    if source is None:
        return None
    fingerprint = hashlib.sha256(json.dumps({
        "tables": tables, "dxf": str(source), "mtime": source.stat().st_mtime_ns,
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", pavimento) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", pillar_name):
        return None
    path = obra_dir / ".portal_cache" / "pilares_abcd_tags" / pavimento / pillar_name / f"{fingerprint}.svg"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    from scripts.arete.pil_agentic_highlight_draw import render_agentic_svg

    svg = render_agentic_svg(source, pillar["points"], tables, layer="sa")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{fingerprint}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(svg)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return svg
