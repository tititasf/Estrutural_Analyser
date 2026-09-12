"""Overrides web persistentes para detalhes manuais das laterais de viga."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LOCK = threading.RLock()
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _path(obra_dir: Path, pavimento: str, behavior: str, beam: str) -> Path:
    if behavior not in {"para", "passa"} or not _NAME_RE.fullmatch(beam):
        raise ValueError("identidade de lateral inválida")
    return Path(obra_dir) / ".portal_overrides" / "lv" / pavimento / behavior / f"{beam}.json"


def load_override(obra_dir: Path, pavimento: str, behavior: str, beam: str) -> dict[str, Any]:
    path = _path(obra_dir, pavimento, behavior, beam)
    if not path.is_file():
        return {"schema": "portal.lv.override/v1", "sides": {"A": {}, "B": {}}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("override LV inválido") from exc
    data.setdefault("sides", {"A": {}, "B": {}})
    return data


def _positive(value: Any, label: str, *, zero: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} inválido") from exc
    if not math.isfinite(result) or result < (0 if zero else 0.001):
        raise ValueError(f"{label} inválido")
    return round(result, 3)


def save_pillar_openings(
    obra_dir: Path,
    pavimento: str,
    behavior: str,
    beam: str,
    side: str,
    index: int,
    openings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    side = side.upper()
    if side not in {"A", "B"} or index < 1:
        raise ValueError("segmento lateral inválido")
    cleaned = []
    for opening in openings:
        pillar = str((opening or {}).get("pillar") or "").strip().upper()
        if not pillar:
            raise ValueError("informe o pilar da abertura")
        cleaned.append({
            "pillar": pillar[:80],
            "position_cm": _positive(opening.get("position_cm"), "posição", zero=True),
            "width_cm": _positive(opening.get("width_cm"), "largura"),
            "height_cm": _positive(opening.get("height_cm"), "altura"),
        })
    with _LOCK:
        data = load_override(obra_dir, pavimento, behavior, beam)
        data["sides"].setdefault(side, {})[str(index)] = {"pillar_openings": cleaned}
        data.update({
            "beam": beam,
            "behavior": behavior,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        path = _path(obra_dir, pavimento, behavior, beam)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{beam}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return cleaned

