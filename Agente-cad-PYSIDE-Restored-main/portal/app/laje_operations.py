"""Edições humanas persistentes da ficha web de lajes.

O estado SA pode receber correções cadastrais, sempre com backup. A geometria
N3 fica em um override separado: artefatos históricos de produção permanecem
imutáveis e o microciclo seguinte consome o override explicitamente.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_LOCK = threading.RLock()
_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_LAYERS = ("sa", "c1", "c2", "c3", "n3")


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"JSON inválido: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON inválido: {path.name}")
    return value


def _safe_name(name: Any) -> str:
    value = str(name or "").strip().upper()
    if not value or not _NAME_RE.fullmatch(value):
        raise ValueError("nome da laje inválido")
    return value


def _override_path(obra_dir: Path, pavimento: str, name: str) -> Path:
    return Path(obra_dir) / ".portal_overrides" / "lajes" / pavimento / f"{_safe_name(name)}.json"


def load_override(obra_dir: Path, pavimento: str, name: str) -> dict[str, Any]:
    path = _override_path(obra_dir, pavimento, name)
    if not path.is_file():
        return {
            "schema": "portal.laje.override/v1", "item": _safe_name(name),
            "n3": {"linhas_verticais": [], "linhas_horizontais": []},
            "notes": {layer: "" for layer in _LAYERS},
        }
    value = _read(path)
    value.setdefault("n3", {"linhas_verticais": [], "linhas_horizontais": []})
    value.setdefault("notes", {layer: "" for layer in _LAYERS})
    return value


def _save_override(obra_dir: Path, pavimento: str, name: str, value: dict[str, Any]) -> Path:
    path = _override_path(obra_dir, pavimento, name)
    value.update({
        "schema": "portal.laje.override/v1", "item": _safe_name(name),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    _atomic_json(path, value)
    return path


def _finite(value: Any, label: str, *, positive: bool = False) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} inválido") from exc
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError(f"{label} inválido")
    return round(number, 3)


def _state_path(obra_dir: Path, pavimento: str) -> Path:
    path = Path(obra_dir) / f"estado_{pavimento}.json"
    if not path.is_file():
        raise FileNotFoundError("estado SA do pavimento não encontrado")
    return path


def _backup_and_write(path: Path, state: dict[str, Any]) -> Path:
    backup_dir = path.parent / ".portal_backups" / "lajes"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"{path.name}.{stamp}.{uuid.uuid4().hex[:8]}.bak"
    shutil.copy2(path, backup)
    _atomic_json(path, state)
    return backup


def update_fields(obra_dir: Path, pavimento: str, name: str, fields: dict[str, Any]) -> dict[str, Any]:
    old_name = _safe_name(name)
    new_name = _safe_name(fields.get("name", old_name))
    level = _finite(fields.get("nivel"), "nível")
    height = _finite(fields.get("height"), "altura", positive=True)
    with _LOCK:
        path = _state_path(obra_dir, pavimento)
        state = _read(path)
        slabs = state.get("slabs") or []
        slab = next((row for row in slabs if str(row.get("name") or "").upper() == old_name), None)
        if slab is None:
            raise LookupError("laje não encontrada")
        if new_name != old_name and any(str(row.get("name") or "").upper() == new_name for row in slabs):
            raise ValueError("já existe uma laje com esse nome")
        slab["name"] = new_name
        slab["nivel"] = "" if level is None else level
        slab["height"] = "" if height is None else height
        if new_name != old_name:
            for cut in state.get("cortes") or []:
                for key in ("own_laje", "neigh_laje"):
                    if str(cut.get(key) or "").upper() == old_name:
                        cut[key] = new_name
        backup = _backup_and_write(path, state)
        old_override = _override_path(obra_dir, pavimento, old_name)
        if new_name != old_name and old_override.is_file():
            payload = _read(old_override)
            _save_override(obra_dir, pavimento, new_name, payload)
            old_override.unlink()
    return {"item": new_name, "backup": str(backup)}


def _lines(rows: Any, label: str, total: Any = None) -> list[dict[str, Any]]:
    clean = []
    for row in rows or []:
        if not isinstance(row, dict):
            raise ValueError(f"linha {label} inválida")
        clean.append({
            "value": _finite(row.get("value"), f"posição {label}", positive=True),
            "is_union": bool(row.get("is_union", False)),
        })
    clean = sorted(clean, key=lambda row: row["value"])
    values = [row["value"] for row in clean]
    if len(values) != len(set(values)):
        raise ValueError(f"posições {label}s repetidas")
    extent = _finite(total, f"limite {label}", positive=True)
    if extent is not None and any(value >= extent for value in values):
        raise ValueError(
            f"posição {label} deve ser menor que {extent:g} cm; "
            "os valores são posições acumuladas desde a borda da laje"
        )
    return clean


def update_n3(
    obra_dir: Path, pavimento: str, name: str, n3: dict[str, Any],
    *, comprimento: Any = None, largura: Any = None,
) -> dict[str, Any]:
    clean = {
        "linhas_verticais": _lines(n3.get("linhas_verticais"), "vertical", comprimento),
        "linhas_horizontais": _lines(n3.get("linhas_horizontais"), "horizontal", largura),
    }
    with _LOCK:
        payload = load_override(obra_dir, pavimento, name)
        payload["n3"] = clean
        path = _save_override(obra_dir, pavimento, name, payload)
    return {"item": _safe_name(name), "n3": clean, "override": str(path)}


def save_notes(obra_dir: Path, pavimento: str, name: str, notes: dict[str, Any]) -> dict[str, str]:
    clean = {layer: str(notes.get(layer) or "")[:8000] for layer in _LAYERS}
    with _LOCK:
        payload = load_override(obra_dir, pavimento, name)
        payload["notes"] = clean
        _save_override(obra_dir, pavimento, name, payload)
    return clean


def delete_slab(obra_dir: Path, pavimento: str, name: str) -> dict[str, Any]:
    target = _safe_name(name)
    with _LOCK:
        path = _state_path(obra_dir, pavimento)
        state = _read(path)
        slabs = state.get("slabs") or []
        kept = [row for row in slabs if str(row.get("name") or "").upper() != target]
        if len(kept) == len(slabs):
            raise LookupError("laje não encontrada")
        state["slabs"] = kept
        # Cortes dependentes são preservados, mas a referência removida fica explícita.
        for cut in state.get("cortes") or []:
            for key in ("own_laje", "neigh_laje"):
                if str(cut.get(key) or "").upper() == target:
                    cut[key] = None
        backup = _backup_and_write(path, state)
    return {"item": target, "backup": str(backup), "remaining": len(kept)}
