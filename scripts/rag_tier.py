#!/usr/bin/env python3
"""
rag_tier.py - Politica de confianca do RAG CAD-Analyzer.

Centraliza tiers:
T0 = quarentena, T1 = validado, T2 = consolidado, TX = revogado.

Este modulo nao indexa nada. Ele apenas decide se um registro pode participar
do RAG global e aplica tombstones de desvalidacao humana.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

FAISS_DIR = Path("D:/Agente-cad-PYSIDE/data/vectors/faiss")
DEFAULT_TOMBSTONES_PATH = FAISS_DIR / "rag_tombstones.json"

T0 = "T0"
T1 = "T1"
T2 = "T2"
TX = "TX"

TIER_ORDER = {T0: 0, T1: 1, T2: 2}
REVOKED_STATUSES = {
    "revogado",
    "revoked",
    "invalidado",
    "invalidated",
    "desvalidado",
    "rejected",
    "rejeitado",
    "superseded",
    "tx",
}
VALIDATED_STATUSES = {
    "aprovado",
    "approved",
    "validated",
    "validado",
    "revisado",
    "reviewed",
}
CONSOLIDATED_STATUSES = {
    "consolidado",
    "consolidated",
    "default",
    "canonico",
    "canônico",
}
QUARANTINE_STATUSES = {
    "draft",
    "extracted",
    "extraido",
    "extraído",
    "pendente",
    "pending",
    "quarantine",
    "quarentena",
    "t0",
}

MACHINE_VALIDATION_MARKERS = {
    "agent",
    "ai",
    "auto",
    "automatic",
    "batch",
    "cli",
    "headless",
    "looper",
    "machine",
    "pipeline",
    "script",
    "synthetic",
    "sintetico",
    "sintético",
    "test",
}
HUMAN_VALIDATION_ORIGINS = {
    "human",
    "human_ui",
    "manual",
    "operator",
    "ui",
    "ui_click",
    "user",
    "user_click",
}
VALIDATION_PROVENANCE_KEYS = (
    "validation_origin",
    "validation_source",
    "validation_channel",
    "validated_origin",
    "validated_source",
    "approved_origin",
    "approved_source",
    "created_by",
    "updated_by",
    "approved_by",
    "validated_by",
    "source",
    "event_source",
    "method",
)


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "sim", "y", "s"}
    return bool(value)


def _has_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) > 0
    if isinstance(value, str):
        raw = value.strip()
        return raw not in {"", "{}", "[]", "null", "None"}
    return bool(value)


def _contains_machine_marker(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, Mapping):
        return any(_contains_machine_marker(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_machine_marker(v) for v in value)
    raw = _norm(value).replace("-", "_")
    if not raw:
        return False
    parts = {part for part in raw.replace(":", "_").replace("/", "_").split("_") if part}
    return bool(parts & MACHINE_VALIDATION_MARKERS) or any(
        marker in raw for marker in MACHINE_VALIDATION_MARKERS
    )


def _json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    raw = value.strip()
    if not raw or raw[0] not in "{[":
        return value
    try:
        return json.loads(raw)
    except Exception:
        return value


def has_machine_validation_provenance(row: Mapping[str, Any]) -> bool:
    """True when a row was approved/validated by automation, CLI or synthetic flow.

    Machine provenance always blocks T1/T2 promotion. Automated loopers can still
    create candidates/events, but they cannot become global RAG teachers.
    """
    for key in VALIDATION_PROVENANCE_KEYS:
        if _contains_machine_marker(row.get(key)):
            return True
    for key in ("metadata_json", "context_dna_json", "provenance_json"):
        if _contains_machine_marker(_json_value(row.get(key))):
            return True
    return False


def has_explicit_human_validation_origin(row: Mapping[str, Any]) -> bool:
    """Return True only for explicit UI/manual human validation markers."""
    if has_machine_validation_provenance(row):
        return False
    for key in VALIDATION_PROVENANCE_KEYS:
        raw = _norm(row.get(key)).replace("-", "_")
        if raw in HUMAN_VALIDATION_ORIGINS:
            return True
    return _truthy(row.get("human_validated")) or _truthy(row.get("human_reviewed"))


def assert_human_validation_origin(origin: str | None, *, allow_legacy: bool = False) -> None:
    """Reject synthetic/CLI validation attempts that try to act as human approval."""
    raw = _norm(origin).replace("-", "_")
    if not raw:
        if allow_legacy:
            return
        raise ValueError("human validation requires explicit validation_origin='human_ui'")
    if _contains_machine_marker(raw) or raw not in HUMAN_VALIDATION_ORIGINS:
        raise ValueError(f"non-human validation origin cannot promote RAG tier: {origin!r}")


def normalize_tier(value: Any) -> str | None:
    raw = _norm(value)
    if raw in {"tx", "revogado", "revoked", "invalidado", "invalidated"}:
        return TX
    if raw in {"t2", "consolidado", "consolidated"}:
        return T2
    if raw in {"t1", "validado", "validated", "aprovado", "approved"}:
        return T1
    if raw in {"t0", "draft", "extracted", "quarentena", "quarantine"}:
        return T0
    return None


def get_source_id(row: Mapping[str, Any]) -> str:
    """Retorna um ID estavel para tombstone/dedupe."""
    for key in (
        "rag_id",
        "source_id",
        "global_id",
        "uuid",
        "id",
        "elemento_id",
        "item_id",
    ):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)

    parts = [
        row.get("obra") or row.get("obra_name") or row.get("project"),
        row.get("pavimento") or row.get("pav"),
        row.get("tipo") or row.get("classe"),
        row.get("nome") or row.get("name"),
        row.get("faiss_id"),
    ]
    joined = "::".join(str(p) for p in parts if p not in (None, ""))
    return joined or "<unknown>"


def get_reverse_ficha_source_ids(row: Mapping[str, Any]) -> tuple[str, str]:
    """Retorna IDs legado e versionado pelo conteúdo de uma F5."""
    legacy = f"reverse_eng_fichas:{row.get('id')}"
    raw = row.get("campos_json")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            pass
    canonical = json.dumps(
        raw,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return legacy, f"{legacy}:{digest}"


def load_tombstones(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    tombstone_path = Path(path) if path else DEFAULT_TOMBSTONES_PATH
    if not tombstone_path.exists():
        return {}
    with open(tombstone_path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and isinstance(data.get("items"), dict):
        return data["items"]
    if isinstance(data, dict):
        return data
    return {}


def save_tombstones(
    tombstones: Mapping[str, Mapping[str, Any]],
    path: str | Path | None = None,
) -> None:
    tombstone_path = Path(path) if path else DEFAULT_TOMBSTONES_PATH
    tombstone_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "items": dict(tombstones),
    }

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{tombstone_path.name}.",
        suffix=".tmp",
        dir=str(tombstone_path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_name, tombstone_path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def revoke_item(
    row_or_id: Mapping[str, Any] | str,
    *,
    reason: str = "",
    revoked_by: str = "human",
    path: str | Path | None = None,
    superseded_by_id: str | None = None,
) -> dict[str, Any]:
    source_id = get_source_id(row_or_id) if isinstance(row_or_id, Mapping) else str(row_or_id)
    tombstones = load_tombstones(path)
    event = {
        "source_id": source_id,
        "revoked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "revoked_by": revoked_by,
        "revoked_reason": reason,
        "superseded_by_id": superseded_by_id,
    }
    tombstones[source_id] = event
    save_tombstones(tombstones, path)
    return event


def clear_revocation(
    row_or_id: Mapping[str, Any] | str,
    *,
    path: str | Path | None = None,
) -> bool:
    """Remove um tombstone somente após nova validação humana explícita."""
    source_id = get_source_id(row_or_id) if isinstance(row_or_id, Mapping) else str(row_or_id)
    tombstones = load_tombstones(path)
    if source_id not in tombstones:
        return False
    del tombstones[source_id]
    save_tombstones(tombstones, path)
    return True


def is_revoked(
    row: Mapping[str, Any],
    tombstones: Mapping[str, Any] | None = None,
) -> bool:
    status = _norm(row.get("status"))
    explicit_tier = normalize_tier(row.get("tier") or row.get("confianca"))
    if explicit_tier == TX or status in REVOKED_STATUSES:
        return True
    if _has_payload(row.get("revoked_at")) or _truthy(row.get("is_revoked")):
        return True
    if tombstones is not None and get_source_id(row) in tombstones:
        return True
    return False


def get_tier(
    row: Mapping[str, Any],
    *,
    tombstones: Mapping[str, Any] | None = None,
) -> str:
    if is_revoked(row, tombstones=tombstones):
        return TX
    if has_machine_validation_provenance(row):
        return T0

    explicit = normalize_tier(row.get("tier") or row.get("confianca"))
    if explicit:
        return explicit

    status = _norm(row.get("status"))
    if status in CONSOLIDATED_STATUSES:
        return T2
    if status in VALIDATED_STATUSES:
        return T1
    if status in QUARANTINE_STATUSES:
        return T0

    if _truthy(row.get("is_consolidated")):
        return T2
    if _truthy(row.get("is_validated")) or _truthy(row.get("validated")):
        return T1
    if _truthy(row.get("revisado")) or _truthy(row.get("reviewed")):
        return T1
    if _has_payload(row.get("validated_fields_json")):
        return T1

    return T0


def tier_at_least(tier: str, min_tier: str = T1) -> bool:
    if tier == TX:
        return False
    return TIER_ORDER.get(tier, -1) >= TIER_ORDER.get(min_tier, TIER_ORDER[T1])


def is_indexable(
    row: Mapping[str, Any],
    *,
    min_tier: str = T1,
    tombstones: Mapping[str, Any] | None = None,
) -> bool:
    return tier_at_least(get_tier(row, tombstones=tombstones), min_tier=min_tier)


def filter_visible_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    min_tier: str = T1,
    tombstones: Mapping[str, Any] | None = None,
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if is_indexable(row, min_tier=min_tier, tombstones=tombstones)
    ]


def _selftest() -> None:
    tombstones = {"P999": {"revoked_reason": "selftest"}}
    samples = {
        "draft": ({"id": "P1", "status": "draft"}, T0, False),
        "extracted": ({"id": "P2", "status": "extracted"}, T0, False),
        "approved": ({"id": "P101", "status": "aprovado"}, T1, True),
        "approved_human_ui": (
            {"id": "P102", "status": "aprovado", "validation_origin": "human_ui"},
            T1,
            True,
        ),
        "approved_cli_blocked": (
            {"id": "P103", "status": "aprovado", "validation_origin": "cli_auto"},
            T0,
            False,
        ),
        "approved_synthetic_metadata_blocked": (
            {"id": "P104", "status": "aprovado", "metadata_json": '{"source":"looper"}'},
            T0,
            False,
        ),
        "is_validated": ({"id": "L308", "is_validated": 1}, T1, True),
        "validated_fields": ({"id": "V7", "validated_fields_json": '{"b": 20}'}, T1, True),
        "consolidated": ({"id": "P3", "status": "consolidado"}, T2, True),
        "revoked_status": ({"id": "P4", "status": "revogado"}, TX, False),
        "revoked_tombstone": ({"id": "P999", "status": "aprovado"}, TX, False),
        "unknown": ({"id": "P5"}, T0, False),
    }
    for name, (row, expected_tier, expected_indexable) in samples.items():
        tier = get_tier(row, tombstones=tombstones)
        assert tier == expected_tier, f"{name}: expected {expected_tier}, got {tier}"
        indexable = is_indexable(row, tombstones=tombstones)
        assert indexable is expected_indexable, (
            f"{name}: expected indexable={expected_indexable}, got {indexable}"
        )
    print("[OK] rag_tier selftest passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Politica de tiers do RAG CAD-Analyzer")
    parser.add_argument("--selftest", action="store_true", help="Executa selftest local")
    parser.add_argument("--revoke-id", help="Registra tombstone para um ID")
    parser.add_argument("--reason", default="", help="Motivo da revogacao")
    parser.add_argument("--revoked-by", default="human", help="Autor da revogacao")
    parser.add_argument("--tombstones", help="Caminho alternativo do arquivo tombstone")
    args = parser.parse_args()

    if args.selftest:
        _selftest()
        return
    if args.revoke_id:
        event = revoke_item(
            args.revoke_id,
            reason=args.reason,
            revoked_by=args.revoked_by,
            path=args.tombstones,
        )
        print(json.dumps(event, ensure_ascii=False, indent=2))
        return
    parser.print_help()


if __name__ == "__main__":
    main()
