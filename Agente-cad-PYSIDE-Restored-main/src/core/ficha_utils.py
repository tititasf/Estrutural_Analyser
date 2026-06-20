"""Canonical ficha helpers for F1-F9.

The helpers in this module are intentionally small and deterministic. They do
not interpret CAD content; they only stamp traceable IDs and schema metadata on
records already produced by the existing engines.
"""
from __future__ import annotations

import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "granular-v1.0"
SEMANTIC_REF_STATUS = "pending_domain_knowledge_link"
_BACKED_UP_DBS: set[str] = set()

CLASS_ALIASES = {
    "P": "PIL",
    "PILAR": "PIL",
    "PILARES": "PIL",
    "PIL": "PIL",
    "L": "LAJ",
    "LAJE": "LAJ",
    "LAJES": "LAJ",
    "LAJ": "LAJ",
    "VIGA FUNDO": "FV",
    "FUNDO": "FV",
    "FV": "FV",
    "VIGA LATERAL": "LV",
    "LATERAL": "LV",
    "VIGA": "LV",
    "VIGAS": "LV",
    "LV": "LV",
}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def stable_token(value: Any, fallback: str = "NA") -> str:
    """Return an uppercase ID-safe token."""
    text = _strip_accents(str(value or fallback)).upper()
    text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
    return text or fallback


def canonical_pavimento(value: Any) -> str:
    """Normalize common pavement labels to the DB convention used by F5 rows."""
    text = _strip_accents(str(value or "")).upper()
    if not text:
        return "GERAL"
    m = re.search(r"(\d{1,2})[^A-Z0-9]{0,6}P(?:AV|V)?(?:\b|[^A-Z0-9])", text)
    if m:
        return f"{int(m.group(1))}_PAV"
    if "TER" in text or "TERREO" in text:
        return "TERREO"
    if "FUN" in text or "FUNDA" in text:
        return "FUNDACAO"
    if "COB" in text or "COBER" in text:
        return "COBERTURA"
    if "ATICO" in text or "ATC" in text:
        return "ATICO"
    if "TIPO" in text or "TIP" in text:
        return "TIPO"
    return stable_token(text, "GERAL")


def canonical_classe(value: Any) -> str:
    text = _strip_accents(str(value or "")).upper().strip()
    return CLASS_ALIASES.get(text, stable_token(text, "CLASSE"))


def ficha_id(ficha: str, obra: Any, pavimento: Any = None, classe: Any = None, item: Any = None) -> str:
    """Build the locked deterministic F1-F9 ID."""
    f = stable_token(ficha).replace("_", "")
    parts = [f, stable_token(obra, "OBRA")]
    if pavimento is not None:
        parts.append(canonical_pavimento(pavimento))
    if classe is not None:
        parts.append(canonical_classe(classe))
    if item is not None:
        parts.append(stable_token(item, "ITEM"))
    return "-".join(parts)


def semantic_ref_map(data: dict[str, Any]) -> dict[str, str]:
    """Materialize per-field semantic_ref placeholders without changing values."""
    return {
        key: SEMANTIC_REF_STATUS
        for key in data.keys()
        if not str(key).startswith("_")
    }


def stamp_ficha_json(
    data: dict[str, Any] | str | None,
    ficha: str,
    obra: Any,
    pavimento: Any = None,
    classe: Any = None,
    item: Any = None,
    source: str = "",
) -> dict[str, Any]:
    """Return a dict with canonical ficha metadata."""
    if isinstance(data, str):
        try:
            payload = json.loads(data) if data else {}
        except Exception:
            payload = {"raw": data}
    else:
        payload = dict(data or {})

    fid = ficha_id(ficha, obra, pavimento, classe, item)
    payload["_ficha"] = {
        "id": fid,
        "tipo": stable_token(ficha).replace("_", ""),
        "obra": str(obra or ""),
        "pavimento": canonical_pavimento(pavimento) if pavimento is not None else "",
        "classe": canonical_classe(classe) if classe is not None else "",
        "item": str(item or ""),
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "created_or_updated_at": datetime.now().isoformat(),
    }
    payload["_schema"] = {
        "name": "SCHEMA-FICHA-GRANULAR",
        "version": SCHEMA_VERSION,
        "compatible_with": ["F5", "F7", "N1", "N2"],
    }
    payload["_semantic_refs"] = semantic_ref_map(payload)
    return payload


def ensure_db_backup(db_path: str | Path, label: str = "etapa1") -> Path | None:
    """Create one non-destructive backup of the real .vision DB before writes."""
    path = Path(db_path)
    if not path.exists():
        return None
    key = str(path.resolve()).lower()
    if key in _BACKED_UP_DBS:
        return None
    existing = sorted(path.parent.glob(f"{path.name}.{label}_*.bak"))
    if existing:
        _BACKED_UP_DBS.add(key)
        return existing[-1]
    backup = path.with_name(f"{path.name}.{label}_{datetime.now():%Y%m%d_%H%M%S}.bak")
    shutil.copy2(path, backup)
    _BACKED_UP_DBS.add(key)
    return backup
