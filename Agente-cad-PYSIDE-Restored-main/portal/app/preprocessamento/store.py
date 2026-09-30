"""Publicação atômica e leitura dos pacotes de pré-processamento."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .contracts import ContextEnvelope, ContractError


_SAFE_DIR = re.compile(r"^[A-Za-z0-9_.-]+$")


class StoreError(RuntimeError):
    """Falha de integridade ou publicação do armazenamento."""


@dataclass(frozen=True)
class StoredPackage:
    envelope: ContextEnvelope
    directory: Path
    manifest_path: Path
    manifest_hash: str


def _json_bytes(payload: Any) -> bytes:
    try:
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StoreError(f"payload não serializável: {exc}") from exc


def _safe_dir(name: str, value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or not _SAFE_DIR.fullmatch(normalized) or ".." in normalized:
        raise StoreError(f"{name} inválido")
    return normalized


def _relative_payload_path(value: str) -> Path:
    path = Path(value)
    if (
        path.is_absolute()
        or bool(path.anchor)
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise StoreError("path de payload inválido")
    if path.name == "manifest.json":
        raise StoreError("manifest.json é reservado")
    return path


class PreprocessStore:
    def __init__(self, *, obra_dir: Path, conn: sqlite3.Connection) -> None:
        self.obra_dir = obra_dir.resolve()
        self.root = self.obra_dir / "preprocessamento" / "v1"
        self.conn = conn

    def _run_dir(self, envelope: ContextEnvelope) -> Path:
        floor = _safe_dir("pavimento_id", envelope.scope.pavimento_id)
        run = _safe_dir("run_id", envelope.run_id)
        return self.root / floor / run

    @staticmethod
    def _write_file(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

    def publish(
        self,
        envelope: ContextEnvelope,
        *,
        payloads: Mapping[str, Any] | None = None,
        job_id: str | None = None,
        engine_version: str | None = None,
    ) -> StoredPackage:
        """Publica filesystem primeiro e indexa depois.

        Uma falha antes do rename deixa somente staging. Uma falha após o
        rename deixa um pacote íntegro recuperável por ``recover_unindexed``.
        """
        final_dir = self._run_dir(envelope)
        if final_dir.exists():
            raise StoreError("run_id já publicado; pacotes são imutáveis")
        staging_root = final_dir.parent / ".staging"
        staging = staging_root / f"{envelope.run_id}.{uuid.uuid4().hex}"
        staging.mkdir(parents=True, exist_ok=False)

        files: dict[str, str] = {}
        for raw_path, payload in sorted((payloads or {}).items()):
            relative = _relative_payload_path(raw_path)
            content = _json_bytes(payload)
            self._write_file(staging / relative, content)
            files[relative.as_posix()] = hashlib.sha256(content).hexdigest()

        manifest = envelope.to_dict()
        manifest["payload_files"] = files
        manifest_content = _json_bytes(manifest)
        self._write_file(staging / "manifest.json", manifest_content)

        final_dir.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(final_dir)
        package = StoredPackage(
            envelope=envelope,
            directory=final_dir,
            manifest_path=final_dir / "manifest.json",
            manifest_hash=hashlib.sha256(manifest_content).hexdigest(),
        )
        self._index(package, job_id=job_id, engine_version=engine_version)
        return package

    def _index(
        self,
        package: StoredPackage,
        *,
        job_id: str | None = None,
        engine_version: str | None = None,
    ) -> None:
        envelope = package.envelope
        relative = package.manifest_path.relative_to(self.obra_dir).as_posix()
        with self.conn:
            self.conn.execute(
                """INSERT OR IGNORE INTO portal_preprocess_runs
                   (run_id, obra_id, pavimento_id, recorte_id, job_id,
                    input_manifest_hash, source_revision, schema_version,
                    engine_version, status, manifest_relative_path, created_at,
                    finished_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    envelope.run_id,
                    envelope.scope.obra_id,
                    envelope.scope.pavimento_id,
                    envelope.scope.recorte_id,
                    job_id,
                    package.manifest_hash,
                    envelope.scope.source_revision,
                    envelope.schema_version,
                    engine_version,
                    envelope.status.value,
                    relative,
                    envelope.created_at,
                    envelope.created_at,
                ),
            )

    def _load_manifest(self, path: Path) -> StoredPackage:
        try:
            content = path.read_bytes()
            raw = json.loads(content)
            payload_files = raw.pop("payload_files", {})
            envelope = ContextEnvelope.from_dict(raw)
        except (OSError, json.JSONDecodeError, TypeError, ContractError) as exc:
            raise StoreError(f"manifesto inválido: {exc}") from exc
        for relative_raw, expected_hash in payload_files.items():
            relative = _relative_payload_path(relative_raw)
            payload_path = path.parent / relative
            if not payload_path.is_file():
                raise StoreError(f"payload ausente: {relative.as_posix()}")
            actual_hash = hashlib.sha256(payload_path.read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                raise StoreError(f"payload corrompido: {relative.as_posix()}")
        return StoredPackage(
            envelope=envelope,
            directory=path.parent,
            manifest_path=path,
            manifest_hash=hashlib.sha256(content).hexdigest(),
        )

    def read(self, run_id: str) -> StoredPackage:
        row = self.conn.execute(
            "SELECT manifest_relative_path FROM portal_preprocess_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise StoreError("run não indexada")
        manifest = (self.obra_dir / row["manifest_relative_path"]).resolve()
        if self.root.resolve() not in manifest.parents:
            raise StoreError("índice aponta para fora do armazenamento de pré-processamento")
        package = self._load_manifest(manifest)
        if package.envelope.run_id != run_id or package.directory != self._run_dir(package.envelope):
            raise StoreError("índice e identidade do pacote divergem")
        return package

    def recover_unindexed(self) -> int:
        """Indexa pacotes íntegros publicados antes de uma queda do DB."""
        recovered = 0
        if not self.root.exists():
            return 0
        for manifest in sorted(self.root.glob("*/*/manifest.json")):
            package = self._load_manifest(manifest)
            if package.directory != self._run_dir(package.envelope):
                raise StoreError("diretório e identidade do pacote divergem")
            before = self.conn.total_changes
            self._index(package)
            if self.conn.total_changes > before:
                recovered += 1
        return recovered
