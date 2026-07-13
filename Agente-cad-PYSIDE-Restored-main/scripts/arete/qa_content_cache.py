#!/usr/bin/env python3
"""Cache por conteúdo para fast paths QA.

O cache nunca decide autoridade. Ele apenas reutiliza um resultado quando o
namespace, a versão do motor e todos os inputs canônicos mantêm o mesmo hash.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


CACHE_SCHEMA = "arete.qa_content_cache/v1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CacheResult:
    key: str
    value: Any
    hit: bool
    path: Path


class ContentAddressedCache:
    """Cache JSON atômico, particionado por namespace e prefixo do hash."""

    def __init__(self, root: Path, *, enabled: bool = True):
        self.root = Path(root).resolve()
        self.enabled = enabled

    @staticmethod
    def key(namespace: str, *, engine_version: str, inputs: Any) -> str:
        return content_hash({
            "schema": CACHE_SCHEMA,
            "namespace": namespace,
            "engine_version": engine_version,
            "inputs": inputs,
        })

    def path_for(self, namespace: str, key: str) -> Path:
        safe_namespace = "".join(char if char.isalnum() or char in "-_" else "_" for char in namespace)
        return self.root / safe_namespace / key[:2] / f"{key}.json"

    def get(self, namespace: str, key: str) -> CacheResult | None:
        if not self.enabled:
            return None
        path = self.path_for(namespace, key)
        if not path.is_file():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if envelope.get("schema") != CACHE_SCHEMA or envelope.get("key") != key:
            return None
        return CacheResult(key=key, value=copy.deepcopy(envelope.get("value")), hit=True, path=path)

    def put(
        self, namespace: str, key: str, value: Any, *,
        engine_version: str, input_hashes: dict[str, str] | None = None,
    ) -> CacheResult:
        path = self.path_for(namespace, key)
        if not self.enabled:
            return CacheResult(key=key, value=copy.deepcopy(value), hit=False, path=path)
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "schema": CACHE_SCHEMA,
            "namespace": namespace,
            "key": key,
            "engine_version": engine_version,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "input_hashes": input_hashes or {},
            "value": value,
        }
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
        return CacheResult(key=key, value=copy.deepcopy(value), hit=False, path=path)

    def get_or_compute(
        self, namespace: str, *, engine_version: str, inputs: Any,
        compute: Callable[[], Any], input_hashes: dict[str, str] | None = None,
    ) -> CacheResult:
        key = self.key(namespace, engine_version=engine_version, inputs=inputs)
        cached = self.get(namespace, key)
        if cached is not None:
            return cached
        return self.put(
            namespace, key, compute(), engine_version=engine_version,
            input_hashes=input_hashes,
        )
