#!/usr/bin/env python3
"""
rag_validation_events.py - Hooks de validacao humana para o RAG.

Este modulo registra eventos e aplica mudancas de tier sem fazer bulk indexing.
Validacao humana promove somente o item alvo. Desvalidacao gera tombstone TX.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

try:
    from .rag_tier import (
        assert_human_validation_origin,
        clear_revocation,
        get_reverse_ficha_source_ids,
        revoke_item,
    )
except ImportError:
    from rag_tier import (
        assert_human_validation_origin,
        clear_revocation,
        get_reverse_ficha_source_ids,
        revoke_item,
    )

DEFAULT_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_ARTIFACT_MEMORY_ROOT = Path(
    "D:/Agente-cad-PYSIDE/data/artifact_memory"
)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_artifact_validation_schema(
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    db_path = Path(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rag_artifact_validations (
                source_id TEXT PRIMARY KEY,
                obra_name TEXT NOT NULL,
                pavimento TEXT,
                classe TEXT NOT NULL,
                item_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                artifact_path TEXT,
                artifact_sha256 TEXT,
                status TEXT NOT NULL,
                validation_origin TEXT NOT NULL,
                validated_at TEXT,
                revoked_at TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = _columns(conn, "rag_artifact_validations")
        migrations = {
            "thumbnail_path": "TEXT",
            "thumbnail_sha256": "TEXT",
            "renderer_version": "TEXT",
            "render_status": "TEXT",
            "render_error": "TEXT",
            "manifest_path": "TEXT",
        }
        for column, sql_type in migrations.items():
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE rag_artifact_validations "
                    f"ADD COLUMN {column} {sql_type}"
                )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_rag_artifact_scope_status
            ON rag_artifact_validations(scope, status, classe)
            """
        )
        conn.commit()


def _artifact_identity(
    base_source_id: str,
    artifact_path: str | Path | None,
) -> tuple[str, str | None, str]:
    path = Path(artifact_path) if artifact_path else None
    digest = None
    normalized_path = str(path) if path else ""
    if path and path.exists() and path.is_file():
        hasher = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        digest = hasher.hexdigest()
    source_id = f"{base_source_id}:{digest[:16]}" if digest else base_source_id
    return source_id, digest, normalized_path


def _record_artifact_validation(
    *,
    base_source_id: str,
    obra_name: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    artifact_path: str | Path | None,
    human_validated: bool,
    db_path: str | Path,
    artifact_memory_root: str | Path,
) -> dict[str, Any]:
    ensure_artifact_validation_schema(db_path)
    source_id, digest, normalized_path = _artifact_identity(
        base_source_id,
        artifact_path,
    )
    now = _now()
    status = "validated" if human_validated else "revoked"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO rag_artifact_validations (
                source_id, obra_name, pavimento, classe, item_id, scope,
                artifact_path, artifact_sha256, status, validation_origin,
                validated_at, revoked_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,'human_ui',?,?,?)
            ON CONFLICT(source_id) DO UPDATE SET
                artifact_path=excluded.artifact_path,
                artifact_sha256=excluded.artifact_sha256,
                status=excluded.status,
                validation_origin='human_ui',
                validated_at=CASE
                    WHEN excluded.status='validated' THEN excluded.validated_at
                    ELSE rag_artifact_validations.validated_at
                END,
                revoked_at=excluded.revoked_at,
                updated_at=excluded.updated_at
            """,
            (
                source_id,
                obra_name,
                pavimento,
                classe,
                item_id,
                scope,
                normalized_path,
                digest,
                status,
                now if human_validated else None,
                now if not human_validated else None,
                now,
            ),
        )
        conn.commit()
    result = {
        "source_id": source_id,
        "artifact_path": normalized_path,
        "artifact_sha256": digest,
        "status": status,
    }
    if not human_validated:
        return result

    render_data: dict[str, Any] = {}
    if not digest or not normalized_path:
        render_data = {
            "render_status": "missing_artifact",
            "render_error": "DXF path ausente ou inexistente",
        }
    else:
        try:
            try:
                from .dxf_artifact_renderer import (
                    RENDERER_VERSION,
                    render_canonical_dxf,
                )
            except ImportError:
                from dxf_artifact_renderer import (
                    RENDERER_VERSION,
                    render_canonical_dxf,
                )

            safe_scope = "".join(c for c in scope.upper() if c.isalnum() or c in "_-")
            safe_class = "".join(c for c in classe.upper() if c.isalnum() or c in "_-")
            png_path = (
                Path(artifact_memory_root)
                / safe_scope
                / safe_class
                / digest[:2]
                / f"{digest}.png"
            )
            manifest = render_canonical_dxf(normalized_path, png_path)
            render_data = {
                "thumbnail_path": manifest["png_path"],
                "thumbnail_sha256": manifest["png_sha256"],
                "renderer_version": RENDERER_VERSION,
                "render_status": "ready",
                "render_error": None,
                "manifest_path": manifest["manifest_path"],
            }
            result["render_manifest"] = manifest
        except Exception as exc:
            render_data = {
                "render_status": "error",
                "render_error": str(exc),
            }

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            UPDATE rag_artifact_validations
            SET thumbnail_path=?,
                thumbnail_sha256=?,
                renderer_version=?,
                render_status=?,
                render_error=?,
                manifest_path=?,
                updated_at=?
            WHERE source_id=?
            """,
            (
                render_data.get("thumbnail_path"),
                render_data.get("thumbnail_sha256"),
                render_data.get("renderer_version"),
                render_data.get("render_status"),
                render_data.get("render_error"),
                render_data.get("manifest_path"),
                _now(),
                source_id,
            ),
        )
        conn.commit()
    result.update(render_data)
    return result


def record_training_event(
    *,
    event_type: str,
    project_id: str,
    role: str,
    context: dict[str, Any],
    target_value: Any,
    status: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> str | None:
    """Insere evento no schema legado `training_events`, se existir."""
    db_path = Path(db_path)
    if not db_path.exists():
        return None

    event_id = str(uuid.uuid4())
    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "training_events"):
            return None
        cols = _columns(conn, "training_events")
        payload = {
            "id": event_id,
            "project_id": project_id,
            "type": event_type,
            "role": role,
            "context_dna_json": _json(context),
            "target_value": str(target_value),
            "status": status,
            "timestamp": _now(),
        }
        available = [key for key in payload if key in cols]
        placeholders = ",".join("?" for _ in available)
        conn.execute(
            f"INSERT INTO training_events ({','.join(available)}) VALUES ({placeholders})",
            [payload[key] for key in available],
        )
        conn.commit()
    return event_id


def _fetch_reverse_ficha(
    conn: sqlite3.Connection,
    *,
    obra_name: str,
    classe: str,
    elemento_id: str,
    recorte_path: str | None = None,
) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    base_cols = """
        id, obra_name, pavimento, classe, elemento_id, campos_json,
        confianca, status, aprovado_at, rag_indexed, created_at, updated_at
    """
    if recorte_path:
        row = conn.execute(
            f"SELECT {base_cols} FROM reverse_eng_fichas WHERE recorte_path=? ORDER BY id DESC LIMIT 1",
            (recorte_path,),
        ).fetchone()
        if row:
            return dict(row)

    row = conn.execute(
        f"""
        SELECT {base_cols}
        FROM reverse_eng_fichas
        WHERE obra_name=? AND classe=? AND elemento_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (obra_name, classe, elemento_id),
    ).fetchone()
    return dict(row) if row else None


def record_reverse_hub_approval(
    *,
    obra_name: str,
    classe: str,
    elemento_id: str,
    recorte_path: str,
    db_path: str | Path = DEFAULT_DB_PATH,
    auto_index: bool = True,
    validation_origin: str | None = None,
) -> dict[str, Any]:
    """Promove a ficha F5 alvo para T1 se a validacao vier da UI humana.

    Chamadas CLI/looper/headless sem `validation_origin='human_ui'` gravam apenas
    um evento em quarentena. Isso impede que validacoes sinteticas contaminem o
    RAG global como se fossem revisao humana.
    """
    db_path = Path(db_path)
    result = {"event_id": None, "ficha_id": None, "indexed": 0, "status": "event_only"}
    context = {
        "source": "diagnostic_reverse_hub",
        "validation_origin": validation_origin or "missing",
        "obra_name": obra_name,
        "classe": classe,
        "elemento_id": elemento_id,
        "recorte_path": recorte_path,
    }
    try:
        assert_human_validation_origin(validation_origin)
        can_promote = True
    except ValueError as exc:
        can_promote = False
        result["status"] = "blocked_non_human_origin"
        result["blocked_reason"] = str(exc)

    result["event_id"] = record_training_event(
        event_type="rag_reverse_hub_human_approved" if can_promote else "rag_reverse_hub_machine_candidate",
        project_id=obra_name,
        role=classe,
        context=context,
        target_value=elemento_id,
        status="validated" if can_promote else "quarantine",
        db_path=db_path,
    )

    if not can_promote:
        return result

    if not db_path.exists():
        return result

    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "reverse_eng_fichas"):
            return result
        row = _fetch_reverse_ficha(
            conn,
            obra_name=obra_name,
            classe=classe,
            elemento_id=elemento_id,
            recorte_path=recorte_path,
        )
        if not row:
            return result

        conn.execute(
            """
            UPDATE reverse_eng_fichas
            SET status='aprovado',
                aprovado_at=COALESCE(aprovado_at, CURRENT_TIMESTAMP),
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (row["id"],),
        )
        conn.commit()
        row["status"] = "aprovado"
        result["ficha_id"] = row["id"]
        result["status"] = "promoted_t1"
        legacy_source_id, versioned_source_id = get_reverse_ficha_source_ids(row)
        source_ids_to_restore = (
            (legacy_source_id, versioned_source_id)
            if row.get("rag_indexed")
            else (versioned_source_id,)
        )
        result["revocations_cleared"] = sum(
            1 for source_id in source_ids_to_restore if clear_revocation(source_id)
        )
        result["revocation_cleared"] = result["revocations_cleared"] > 0

    if auto_index:
        try:
            from indexar_validados import apply_indexing

            row["rag_indexed"] = row.get("rag_indexed") or 0
            if not row["rag_indexed"]:
                result["indexed"] = apply_indexing([row], db_path)
        except Exception as exc:
            result["index_error"] = str(exc)

    return result


def record_reverse_hub_revocation(
    *,
    obra_name: str,
    classe: str,
    elemento_id: str,
    recorte_path: str | None = None,
    reason: str,
    db_path: str | Path = DEFAULT_DB_PATH,
    validation_origin: str | None = None,
) -> dict[str, Any]:
    """Revoga uma ficha F5 humana sem apagar a linha nem o vetor físico."""
    db_path = Path(db_path)
    result = {"event_id": None, "ficha_id": None, "revoked": False}
    context = {
        "source": "diagnostic_reverse_hub_f5",
        "validation_origin": validation_origin or "missing",
        "obra_name": obra_name,
        "classe": classe,
        "elemento_id": elemento_id,
        "recorte_path": recorte_path,
        "reason": reason,
    }
    try:
        assert_human_validation_origin(validation_origin)
        can_revoke = True
    except ValueError as exc:
        can_revoke = False
        result["status"] = "blocked_non_human_origin"
        result["blocked_reason"] = str(exc)

    result["event_id"] = record_training_event(
        event_type=(
            "rag_reverse_hub_human_revoked"
            if can_revoke
            else "rag_reverse_hub_machine_revocation_candidate"
        ),
        project_id=obra_name,
        role=classe,
        context=context,
        target_value=elemento_id,
        status="revoked" if can_revoke else "quarantine",
        db_path=db_path,
    )
    if not can_revoke or not db_path.exists():
        return result

    with sqlite3.connect(db_path) as conn:
        if not _table_exists(conn, "reverse_eng_fichas"):
            result["status"] = "event_only"
            return result
        row = _fetch_reverse_ficha(
            conn,
            obra_name=obra_name,
            classe=classe,
            elemento_id=elemento_id,
            recorte_path=recorte_path,
        )
        if not row:
            result["status"] = "event_only"
            return result
        conn.execute(
            """
            UPDATE reverse_eng_fichas
            SET status='revoked',
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (row["id"],),
        )
        conn.commit()

    result["ficha_id"] = row["id"]
    legacy_source_id, versioned_source_id = get_reverse_ficha_source_ids(row)
    result["tombstones"] = [
        revoke_item(
            source_id,
            reason=reason,
            revoked_by="human_ui",
        )
        for source_id in (legacy_source_id, versioned_source_id)
    ]
    result["tombstone"] = result["tombstones"][-1]
    result["revoked"] = True
    result["status"] = "revoked_tx"
    return result


def record_comparison_human_validation(
    *,
    obra_name: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    human_validated: bool,
    db_path: str | Path = DEFAULT_DB_PATH,
    validation_origin: str | None = None,
    artifact_path: str | Path | None = None,
    artifact_memory_root: str | Path = DEFAULT_ARTIFACT_MEMORY_ROOT,
) -> dict[str, Any]:
    """Registra validacao/desvalidacao humana no Comparison Engine.

    Validacao/desvalidacao efetiva exige `validation_origin='human_ui'`.
    Loopers automaticos podem registrar candidatos, mas nao validam nem tombstonam.
    """
    source_id = f"comparison_engine:{obra_name}:{pavimento}:{classe}:{item_id}:{scope}"
    context = {
        "source": "comparison_engine",
        "source_id": source_id,
        "validation_origin": validation_origin or "missing",
        "obra_name": obra_name,
        "pavimento": pavimento,
        "classe": classe,
        "item_id": item_id,
        "scope": scope,
        "artifact_path": str(artifact_path or ""),
    }
    try:
        assert_human_validation_origin(validation_origin)
        can_apply = True
    except ValueError as exc:
        can_apply = False

    event_id = record_training_event(
        event_type=(
            "rag_comparison_human_validated"
            if human_validated and can_apply
            else "rag_comparison_human_revoked"
            if can_apply
            else "rag_comparison_machine_candidate"
        ),
        project_id=f"{obra_name}:{pavimento}",
        role=scope,
        context=context,
        target_value=item_id,
        status="validated" if human_validated and can_apply else "revoked" if can_apply else "quarantine",
        db_path=db_path,
    )
    result = {"event_id": event_id, "source_id": source_id, "revoked": False}
    if not can_apply:
        result["status"] = "blocked_non_human_origin"
        result["blocked_reason"] = "human validation requires explicit validation_origin='human_ui'"
        return result
    artifact = _record_artifact_validation(
        base_source_id=source_id,
        obra_name=obra_name,
        pavimento=pavimento,
        classe=classe,
        item_id=item_id,
        scope=scope,
        artifact_path=artifact_path,
        human_validated=human_validated,
        db_path=db_path,
        artifact_memory_root=artifact_memory_root,
    )
    result["artifact"] = artifact
    if not human_validated:
        result["tombstone"] = revoke_item(
            artifact["source_id"],
            reason="comparison_engine_human_unchecked",
            revoked_by="human",
        )
        result["revoked"] = True
    return result


if __name__ == "__main__":
    print("rag_validation_events: importable helpers only")
