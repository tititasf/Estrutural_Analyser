from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import uuid
from datetime import UTC, datetime
from pathlib import Path


DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
PROTECTED_ROOT = Path("D:/Agente-cad-PYSIDE/protected_artifacts")


class ProtectedArtifactError(PermissionError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _norm(value) -> str:
    return str(value or "").strip()


def _norm_class(value: str) -> str:
    value = _norm(value).upper()
    return {"PIL": "PL", "LAJ": "LJ"}.get(value, value)


def _norm_scope(value: str) -> str:
    value = _norm(value).upper()
    if value not in {"N3", "N4"}:
        raise ValueError(f"Escopo protegido inválido: {value!r}")
    return value


def _norm_item(classe: str, value: str) -> str:
    classe = _norm_class(classe)
    item = re.sub(r"_(PARA|PASSA)$", "", _norm(value), flags=re.IGNORECASE)
    if classe in {"LV", "FV"}:
        item = re.sub(r"[_\.]([AB])$", "", item, flags=re.IGNORECASE)
    return item.upper()


def _resolved(path: Path | str) -> str:
    return str(Path(path).expanduser().resolve())


def _sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _writable(path: Path) -> None:
    if path.exists():
        path.chmod(path.stat().st_mode | stat.S_IWRITE)


def _readonly(path: Path) -> None:
    if path.exists():
        path.chmod(path.stat().st_mode & ~stat.S_IWRITE)


def ensure_governance_tables(db_path: Path | str = DB_PATH) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS artifact_validation_policies (
                id TEXT PRIMARY KEY,
                obra_name TEXT NOT NULL,
                pavimento TEXT NOT NULL,
                classe TEXT NOT NULL,
                item_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                locked INTEGER NOT NULL DEFAULT 1,
                validation_origin TEXT NOT NULL,
                updated_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_artifact_policy_lookup
                ON artifact_validation_policies(
                    obra_name, pavimento, classe, item_id, scope, locked
                );

            CREATE TABLE IF NOT EXISTS protected_artifacts (
                path TEXT PRIMARY KEY,
                policy_id TEXT NOT NULL,
                snapshot_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                protected_at TEXT NOT NULL,
                verified_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_protected_policy
                ON protected_artifacts(policy_id, active);

            CREATE TABLE IF NOT EXISTS motor_versions (
                motor_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                source_manifest_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(motor_id, version_id)
            );

            CREATE TABLE IF NOT EXISTS motor_runs (
                run_id TEXT PRIMARY KEY,
                motor_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                obra_name TEXT,
                pavimento TEXT,
                classe TEXT,
                item_id TEXT,
                scope TEXT,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                output_path TEXT NOT NULL,
                protected_path TEXT,
                output_sha256 TEXT,
                baseline_sha256 TEXT,
                effect TEXT,
                result_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_motor_runs_lookup
                ON motor_runs(motor_id, version_id, classe, item_id, scope, created_at);
            """
        )


def _policy_id(
    obra: str, pavimento: str, classe: str, item_id: str, scope: str
) -> str:
    return "|".join(
        [
            _norm(obra),
            _norm(pavimento),
            _norm_class(classe),
            _norm_item(classe, item_id),
            _norm_scope(scope),
        ]
    )


def infer_artifact_identity(path: Path | str) -> dict | None:
    path = Path(path)
    parts_upper = [part.upper() for part in path.parts]
    try:
        phase_index = parts_upper.index("FASE-6_EXECUCAO_CAD")
    except ValueError:
        return None
    if any(part in {".MOTOR_VERSIONS", ".VALIDATED"} for part in parts_upper):
        return None
    scope = "N4" if (
        len(parts_upper) > phase_index + 1
        and parts_upper[phase_index + 1] == "N4"
    ) else "N3"
    stem = path.stem
    match = re.match(
        r"^(PL|LV|FV|LJ)(?:_(?:ABCD|CIMA|GRADES|EFGH))?_PREVIEW_(.+)$",
        stem,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    classe = _norm_class(match.group(1))
    item_id = match.group(2)
    if classe == "LV":
        item_id = re.sub(
            r"_(?:CORTE|VIEW_A|VIEW_B)$", "", item_id, flags=re.IGNORECASE
        )
    item_id = _norm_item(classe, item_id)
    obra_name = path.parts[phase_index - 1] if phase_index > 0 else ""
    return {
        "obra_name": obra_name,
        "classe": classe,
        "item_id": item_id,
        "scope": scope,
    }


def _policy_locked_for_identity(
    identity: dict, db_path: Path | str = DB_PATH
) -> bool:
    ensure_governance_tables(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM artifact_validation_policies
            WHERE obra_name=? AND classe=? AND item_id=? AND scope=? AND locked=1
            LIMIT 1
            """,
            (
                identity["obra_name"],
                _norm_class(identity["classe"]),
                _norm_item(identity["classe"], identity["item_id"]),
                _norm_scope(identity["scope"]),
            ),
        ).fetchone()
    return row is not None


def is_validation_policy_locked(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    db_path: Path | str = DB_PATH,
) -> bool:
    ensure_governance_tables(db_path)
    policy_id = _policy_id(obra, pavimento, classe, item_id, scope)
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            """
            SELECT 1 FROM artifact_validation_policies
            WHERE id=? AND locked=1
            """,
            (policy_id,),
        ).fetchone()
    return row is not None


def is_artifact_protected(
    path: Path | str, db_path: Path | str = DB_PATH
) -> bool:
    ensure_governance_tables(db_path)
    resolved = _resolved(path)
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT 1 FROM protected_artifacts WHERE path=? AND active=1",
            (resolved,),
        ).fetchone()
    if row:
        return True
    identity = infer_artifact_identity(path)
    return bool(identity and _policy_locked_for_identity(identity, db_path))


def discover_level_artifacts(
    obra: str,
    classe: str,
    item_id: str,
    scope: str,
    data_root: Path | str = DADOS_OBRAS_ROOT,
) -> list[Path]:
    classe = _norm_class(classe)
    item_id = _norm_item(classe, item_id)
    scope = _norm_scope(scope)
    fase6 = Path(data_root) / _norm(obra) / "Fase-6_Execucao_CAD"
    root = fase6 / "n4" if scope == "N4" else fase6
    if not root.exists():
        return []
    found: list[Path] = []
    for path in root.glob("*.dxf"):
        identity = infer_artifact_identity(path)
        if not identity:
            continue
        if (
            identity["obra_name"] == _norm(obra)
            and identity["classe"] == classe
            and identity["item_id"] == item_id
            and identity["scope"] == scope
        ):
            found.append(path)
    return sorted(found)


def _snapshot_root_for(
    db_path: Path | str, protected_root: Path | str | None
) -> Path:
    if protected_root is not None:
        return Path(protected_root)
    if Path(db_path).resolve() == DB_PATH.resolve():
        return PROTECTED_ROOT
    return Path(db_path).parent / "protected_artifacts"


def set_validation_protection(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    locked: bool,
    *,
    db_path: Path | str = DB_PATH,
    data_root: Path | str | None = None,
    protected_root: Path | str | None = None,
    validation_origin: str = "human_ui",
    updated_by: str | None = None,
) -> dict:
    ensure_governance_tables(db_path)
    classe = _norm_class(classe)
    item_id = _norm_item(classe, item_id)
    scope = _norm_scope(scope)
    policy_id = _policy_id(obra, pavimento, classe, item_id, scope)
    now = _now()
    if data_root is None:
        data_root = (
            DADOS_OBRAS_ROOT
            if Path(db_path).resolve() == DB_PATH.resolve()
            else Path(db_path).parent / "DADOS-OBRAS"
        )
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO artifact_validation_policies
                (id, obra_name, pavimento, classe, item_id, scope, locked,
                 validation_origin, updated_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                locked=excluded.locked,
                validation_origin=excluded.validation_origin,
                updated_by=excluded.updated_by,
                updated_at=excluded.updated_at
            """,
            (
                policy_id,
                _norm(obra),
                _norm(pavimento),
                classe,
                item_id,
                scope,
                1 if locked else 0,
                _norm(validation_origin),
                _norm(updated_by),
                now,
                now,
            ),
        )

    if not locked:
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute(
                "SELECT path FROM protected_artifacts "
                "WHERE policy_id=? AND active=1",
                (policy_id,),
            ).fetchall()
            for (artifact_path,) in rows:
                _writable(Path(artifact_path))
            conn.execute(
                "UPDATE protected_artifacts SET active=0 WHERE policy_id=?",
                (policy_id,),
            )
        return {"locked": False, "artifacts": len(rows), "policy_id": policy_id}

    artifacts = discover_level_artifacts(
        obra, classe, item_id, scope, data_root=data_root
    )
    snapshot_root = _snapshot_root_for(db_path, protected_root)
    protected = []
    for artifact in artifacts:
        sha = _sha256(artifact)
        snapshot = (
            snapshot_root
            / _norm(obra)
            / _norm(pavimento)
            / scope
            / classe
            / item_id
            / sha
            / artifact.name
        )
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot.exists():
            shutil.copy2(artifact, snapshot)
        _readonly(snapshot)
        _readonly(artifact)
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                """
                INSERT INTO protected_artifacts
                    (path, policy_id, snapshot_path, sha256, size_bytes, active,
                     protected_at, verified_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    policy_id=excluded.policy_id,
                    snapshot_path=excluded.snapshot_path,
                    sha256=excluded.sha256,
                    size_bytes=excluded.size_bytes,
                    active=1,
                    protected_at=excluded.protected_at,
                    verified_at=excluded.verified_at
                """,
                (
                    _resolved(artifact),
                    policy_id,
                    _resolved(snapshot),
                    sha,
                    artifact.stat().st_size,
                    now,
                    now,
                ),
            )
        protected.append(str(artifact))
    return {"locked": True, "artifacts": protected, "policy_id": policy_id}


def ensure_artifact_integrity(
    path: Path | str, db_path: Path | str = DB_PATH
) -> bool:
    ensure_governance_tables(db_path)
    path = Path(path)
    resolved = _resolved(path)
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            """
            SELECT snapshot_path, sha256 FROM protected_artifacts
            WHERE path=? AND active=1
            """,
            (resolved,),
        ).fetchone()
    if not row:
        return True
    snapshot, expected_sha = Path(row[0]), row[1]
    current_ok = path.exists() and _sha256(path) == expected_sha
    if not current_ok:
        if not snapshot.exists() or _sha256(snapshot) != expected_sha:
            raise ProtectedArtifactError(
                f"Snapshot protegido ausente ou corrompido: {snapshot}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        _writable(path)
        shutil.copy2(snapshot, path)
    _readonly(path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "UPDATE protected_artifacts SET verified_at=? WHERE path=?",
            (_now(), resolved),
        )
    return current_ok


def restore_validation_artifacts(
    obra: str,
    pavimento: str,
    classe: str,
    item_id: str,
    scope: str,
    db_path: Path | str = DB_PATH,
) -> list[Path]:
    ensure_governance_tables(db_path)
    policy_id = _policy_id(obra, pavimento, classe, item_id, scope)
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT path FROM protected_artifacts
            WHERE policy_id=? AND active=1
            ORDER BY path
            """,
            (policy_id,),
        ).fetchall()
    paths = [Path(row[0]) for row in rows]
    for path in paths:
        ensure_artifact_integrity(path, db_path)
    return paths


def backfill_existing_human_validations(
    db_path: Path | str = DB_PATH,
    data_root: Path | str | None = None,
    protected_root: Path | str | None = None,
) -> dict:
    ensure_governance_tables(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        table = conn.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='item_attention_notes'
            """
        ).fetchone()
        if not table:
            return {"policies": 0, "artifacts": 0}
        rows = conn.execute(
            """
            SELECT obra_name, pavimento, classe, item_id, scope,
                   COALESCE(validation_origin, ''),
                   COALESCE(updated_by, '')
            FROM item_attention_notes
            WHERE COALESCE(human_validated, 0)=1
              AND UPPER(scope) IN ('N3', 'N4')
            """
        ).fetchall()

    artifact_count = 0
    for obra, pavimento, classe, item_id, scope, origin, updated_by in rows:
        result = set_validation_protection(
            obra,
            pavimento,
            classe,
            item_id,
            scope,
            True,
            db_path=db_path,
            data_root=data_root,
            protected_root=protected_root,
            validation_origin=origin or "legacy_human_ui",
            updated_by=updated_by,
        )
        artifact_count += len(result.get("artifacts", []))
    return {"policies": len(rows), "artifacts": artifact_count}


def register_motor_version(
    motor_id: str,
    source_paths: list[Path | str],
    db_path: Path | str = DB_PATH,
) -> str:
    ensure_governance_tables(db_path)
    manifest = []
    for source in sorted((Path(p) for p in source_paths), key=lambda p: str(p)):
        if source.exists():
            manifest.append(
                {
                    "path": _resolved(source),
                    "sha256": _sha256(source),
                    "size_bytes": source.stat().st_size,
                }
            )
    encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    version_id = hashlib.sha256(encoded).hexdigest()[:16]
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO motor_versions
                (motor_id, version_id, source_manifest_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                _norm(motor_id).upper(),
                version_id,
                json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                _now(),
            ),
        )
    return version_id


def _record_run(
    *,
    run_id: str,
    motor_id: str,
    version_id: str,
    identity: dict | None,
    mode: str,
    status: str,
    output_path: Path,
    protected_path: Path | None,
    output_sha: str | None,
    baseline_sha: str | None,
    effect: str,
    db_path: Path | str,
    result: dict | None = None,
) -> None:
    ensure_governance_tables(db_path)
    identity = identity or {}
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO motor_runs
                (run_id, motor_id, version_id, obra_name, pavimento, classe,
                 item_id, scope, mode, status, output_path, protected_path,
                 output_sha256, baseline_sha256, effect, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                _norm(motor_id).upper(),
                version_id,
                identity.get("obra_name", ""),
                identity.get("pavimento", ""),
                identity.get("classe", ""),
                identity.get("item_id", ""),
                identity.get("scope", ""),
                mode,
                status,
                _resolved(output_path),
                _resolved(protected_path) if protected_path else "",
                output_sha or "",
                baseline_sha or "",
                effect,
                json.dumps(result or {}, ensure_ascii=False, sort_keys=True),
                _now(),
            ),
        )


def _candidate_path(
    target: Path,
    identity: dict | None,
    motor_id: str,
    version_id: str,
    run_id: str,
) -> Path:
    parts_upper = [part.upper() for part in target.parts]
    try:
        phase_index = parts_upper.index("FASE-6_EXECUCAO_CAD")
        fase6 = Path(*target.parts[: phase_index + 1])
    except ValueError:
        fase6 = target.parent
    identity = identity or {}
    return (
        fase6
        / ".motor_versions"
        / "candidates"
        / identity.get("scope", "UNKNOWN")
        / identity.get("classe", "UNKNOWN")
        / identity.get("item_id", "UNKNOWN")
        / _norm(motor_id).upper()
        / version_id
        / run_id
        / target.name
    )


def _run_manifest_path(
    target: Path,
    motor_id: str,
    version_id: str,
    run_id: str,
) -> Path:
    parts_upper = [part.upper() for part in target.parts]
    try:
        phase_index = parts_upper.index("FASE-6_EXECUCAO_CAD")
        fase6 = Path(*target.parts[: phase_index + 1])
    except ValueError:
        fase6 = target.parent
    return (
        fase6
        / ".motor_versions"
        / "runs"
        / _norm(motor_id).upper()
        / version_id
        / run_id
        / "run_manifest.json"
    )


def guarded_saveas(
    doc,
    target: Path | str,
    *,
    motor_id: str,
    source_paths: list[Path | str],
    db_path: Path | str = DB_PATH,
) -> Path:
    target = Path(target)
    identity = infer_artifact_identity(target)
    version_id = register_motor_version(motor_id, source_paths, db_path)
    run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:10]}"
    protected = is_artifact_protected(target, db_path)
    headless = _norm(os.environ.get("CAD_MOTOR_HEADLESS")).lower() in {
        "1", "true", "yes", "on",
    }
    baseline_sha = _sha256(target) if target.exists() else None
    if protected or headless:
        if protected:
            ensure_artifact_integrity(target, db_path)
        output = _candidate_path(target, identity, motor_id, version_id, run_id)
        mode = "headless_candidate"
        status = "blocked_protected" if protected else "candidate_pending_test"
    else:
        output = target
        mode = "publish"
        status = "published"
        _writable(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(output))
    output_sha = _sha256(output)
    effect = (
        "identical"
        if baseline_sha and baseline_sha == output_sha
        else "changed"
        if baseline_sha
        else "new"
    )
    _record_run(
        run_id=run_id,
        motor_id=motor_id,
        version_id=version_id,
        identity=identity,
        mode=mode,
        status=status,
        output_path=output,
        protected_path=target if protected else None,
        output_sha=output_sha,
        baseline_sha=baseline_sha,
        effect=effect,
        db_path=db_path,
        result={
            "official_preserved": bool(protected or headless),
            "comparison_status": "pending" if protected or headless else "not_required",
        },
    )
    manifest = _run_manifest_path(
        target, motor_id, version_id, run_id
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "motor_id": _norm(motor_id).upper(),
                "version_id": version_id,
                "mode": mode,
                "status": status,
                "official_path": str(target),
                "output_path": str(output),
                "baseline_sha256": baseline_sha,
                "output_sha256": output_sha,
                "effect": effect,
                "created_at": _now(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output


def guarded_promote(
    generated: Path | str,
    target: Path | str,
    *,
    motor_id: str,
    source_paths: list[Path | str],
    db_path: Path | str = DB_PATH,
    move: bool = True,
) -> Path:
    generated = Path(generated)
    target = Path(target)
    identity = infer_artifact_identity(target)
    version_id = register_motor_version(motor_id, source_paths, db_path)
    run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:10]}"
    protected = is_artifact_protected(target, db_path)
    headless = _norm(os.environ.get("CAD_MOTOR_HEADLESS")).lower() in {
        "1", "true", "yes", "on",
    }
    baseline_sha = _sha256(target) if target.exists() else None
    if protected or headless:
        if protected:
            ensure_artifact_integrity(target, db_path)
        output = _candidate_path(target, identity, motor_id, version_id, run_id)
        mode = "headless_candidate"
        status = "blocked_protected" if protected else "candidate_pending_test"
    else:
        output = target
        mode = "publish"
        status = "published"
        _writable(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if move and not protected and not headless:
        try:
            os.replace(str(generated), str(output))
        except OSError:
            # os.replace falha entre drives distintos (C: → D:) — usa shutil.move
            shutil.move(str(generated), str(output))
    else:
        shutil.copy2(generated, output)
        if move:
            generated.unlink(missing_ok=True)
    output_sha = _sha256(output)
    effect = (
        "identical"
        if baseline_sha and baseline_sha == output_sha
        else "changed"
        if baseline_sha
        else "new"
    )
    _record_run(
        run_id=run_id,
        motor_id=motor_id,
        version_id=version_id,
        identity=identity,
        mode=mode,
        status=status,
        output_path=output,
        protected_path=target if protected else None,
        output_sha=output_sha,
        baseline_sha=baseline_sha,
        effect=effect,
        db_path=db_path,
        result={
            "official_preserved": bool(protected or headless),
            "comparison_status": "pending" if protected or headless else "not_required",
        },
    )
    manifest = _run_manifest_path(
        target, motor_id, version_id, run_id
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "motor_id": _norm(motor_id).upper(),
                "version_id": version_id,
                "mode": mode,
                "status": status,
                "official_path": str(target),
                "output_path": str(output),
                "baseline_sha256": baseline_sha,
                "output_sha256": output_sha,
                "effect": effect,
                "created_at": _now(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return output


def motor_history(
    motor_id: str | None = None,
    db_path: Path | str = DB_PATH,
) -> list[dict]:
    ensure_governance_tables(db_path)
    query = (
        "SELECT run_id, motor_id, version_id, obra_name, pavimento, classe, "
        "item_id, scope, mode, status, output_path, protected_path, "
        "output_sha256, baseline_sha256, effect, result_json, created_at "
        "FROM motor_runs"
    )
    params: tuple = ()
    if motor_id:
        query += " WHERE motor_id=?"
        params = (_norm(motor_id).upper(),)
    query += " ORDER BY created_at DESC, run_id DESC"
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def record_motor_test_result(
    run_id: str,
    result: dict,
    *,
    status: str = "tested",
    db_path: Path | str = DB_PATH,
) -> None:
    ensure_governance_tables(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT result_json FROM motor_runs WHERE run_id=?",
            (_norm(run_id),),
        ).fetchone()
        if not row:
            raise KeyError(f"Execução de motor não encontrada: {run_id}")
        previous = json.loads(row[0] or "{}")
        previous.update(result or {})
        conn.execute(
            """
            UPDATE motor_runs
            SET status=?, result_json=?
            WHERE run_id=?
            """,
            (
                _norm(status) or "tested",
                json.dumps(previous, ensure_ascii=False, sort_keys=True),
                _norm(run_id),
            ),
        )
