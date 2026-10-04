"""Correções humanas da tabela ABCD, isoladas do snapshot imutável do SA."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path


ROLES = {"lajes", "passa", "chega", "interior"}
FIELDS = {"nome", "dim", "nivel", "canto"}


def _path(obra_dir: Path, pavimento: str, pillar_name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", pavimento) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", pillar_name):
        raise ValueError("pavimento ou pilar inválido")
    return obra_dir / ".portal_overrides" / "pilares_abcd" / pavimento / f"{pillar_name}.json"


def _key(face: str, role: str, index: int) -> str:
    return f"{face}:{role}:{index}"


def _read(path: Path) -> dict:
    if not path.is_file():
        return {"revision": 0, "rows": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) and isinstance(data.get("rows"), dict) else {"revision": 0, "rows": {}}


def apply_review(tables: dict, obra_dir: Path, pavimento: str, pillar_name: str) -> dict:
    saved = _read(_path(obra_dir, pavimento, pillar_name))
    for face, body in (tables.get("faces") or {}).items():
        for role in ROLES:
            for index, row in enumerate(body.get(role) or []):
                patch = saved["rows"].get(_key(face, role, index)) or {}
                if patch.get("source_name") != row.get("nome") or patch.get("source_corner") != row.get("canto"):
                    continue
                for field, value in (patch.get("values") or {}).items():
                    if field not in FIELDS:
                        continue
                    row[field] = value
                    row[f"{field}_status"] = "human"
                    row[f"{field}_motivo"] = "Valor editado manualmente nesta obra."
    return tables


def save_review(obra_dir: Path, pavimento: str, pillar_name: str, tables: dict, edits: list[dict]) -> int:
    if not edits or len(edits) > 100:
        raise ValueError("informe de 1 a 100 alterações")
    path = _path(obra_dir, pavimento, pillar_name)
    saved = _read(path)
    for edit in edits:
        face, role, field = edit.get("face"), edit.get("role"), edit.get("field")
        index, value = edit.get("index"), str(edit.get("value") or "").strip()
        if face not in (tables.get("faces") or {}) or role not in ROLES or field not in FIELDS:
            raise ValueError("campo ABCD inválido")
        if not isinstance(index, int) or isinstance(index, bool):
            raise ValueError("índice de linha inválido")
        rows = tables["faces"][face].get(role) or []
        if index < 0 or index >= len(rows) or rows[index].get("nome") in ("", "—", "nenhuma"):
            raise ValueError("linha ABCD inválida")
        if not value or len(value) > 64 or any(c in value for c in "<>\r\n"):
            raise ValueError("valor inválido")
        if field == "nome" and not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", value):
            raise ValueError("nome inválido")
        if field == "dim" and not re.fullmatch(r"\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?", value):
            raise ValueError("dimensão inválida")
        if field == "nivel" and not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?(?:\s*cm)?", value):
            raise ValueError("nível inválido")
        if field == "canto":
            value = value.upper()
            if not re.fullmatch(r"[A-F]{2}", value):
                raise ValueError("canto inválido")
        key = _key(face, role, index)
        row = rows[index]
        patch = saved["rows"].get(key)
        if not patch or patch.get("source_name") != row.get("nome") or patch.get("source_corner") != row.get("canto"):
            patch = {"source_name": row.get("nome"), "source_corner": row.get("canto"), "values": {}}
        patch["values"][field] = value
        saved["rows"][key] = patch
    saved["revision"] = int(saved.get("revision") or 0) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(saved, stream, ensure_ascii=False, indent=2)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return saved["revision"]
