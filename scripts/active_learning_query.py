#!/usr/bin/env python3
"""Consulta segura aos stores de Active Learning versionados."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

VECTOR_ROOT = Path("D:/Agente-cad-PYSIDE/data/vectors/active_learning")
MODEL_NAME = "all-MiniLM-L6-v2"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_store(store: str, vector_root: Path) -> tuple[Any, list[dict[str, Any]]]:
    store_dir = vector_root / store
    pointer = json.loads((store_dir / "CURRENT.json").read_text(encoding="utf-8"))
    index_path = store_dir / pointer["index_file"]
    meta_path = store_dir / pointer["meta_file"]
    if _sha256(index_path) != pointer["index_sha256"]:
        raise RuntimeError(f"hash do índice {store} inválido")
    if _sha256(meta_path) != pointer["meta_sha256"]:
        raise RuntimeError(f"hash dos metadados {store} inválido")
    index = faiss.read_index(str(index_path))
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if index.ntotal != len(metadata):
        raise RuntimeError(f"store {store} inconsistente")
    return index, metadata


def query_active_learning(
    text: str,
    *,
    limit: int = 5,
    include_candidates: bool = False,
    vector_root: str | Path = VECTOR_ROOT,
    model: Any | None = None,
) -> list[dict[str, Any]]:
    """Produção consulta apenas `approved`; candidatos exigem opt-in explícito."""
    store = "candidates" if include_candidates else "approved"
    try:
        index, metadata = _load_store(store, Path(vector_root))
    except (OSError, KeyError, ValueError, RuntimeError):
        return []
    if index.ntotal == 0:
        return []
    model = model or SentenceTransformer(MODEL_NAME)
    vector = np.asarray(model.encode([text], show_progress_bar=False), dtype=np.float32)
    norm = np.linalg.norm(vector, axis=1, keepdims=True)
    vector = vector / np.where(norm == 0, 1, norm)
    scores, ids = index.search(vector.astype(np.float32), min(max(limit, 1), index.ntotal))
    results = []
    for score, position in zip(scores[0], ids[0]):
        if position < 0:
            continue
        meta = dict(metadata[position])
        if include_candidates:
            if meta.get("tier") != "T0" or meta.get("status") != "PROPOSED":
                continue
        elif meta.get("tier") not in {"T1", "T2"} or meta.get("status") not in {"APPROVED", "INDEXED"}:
            continue
        results.append({"score": float(score), "meta": meta})
    return results
