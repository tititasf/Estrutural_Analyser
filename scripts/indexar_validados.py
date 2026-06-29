#!/usr/bin/env python3
"""
indexar_validados.py - Indexacao incremental de fichas validadas.

Indexa somente registros T1/T2 de `reverse_eng_fichas` ainda nao indexados.
No estado atual, se tudo estiver draft/extracted, o script deve reportar zero
candidatos e nao escrever nada.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from rag_tier import (
    get_reverse_ficha_source_ids,
    get_tier,
    is_indexable,
    load_tombstones,
)

DEFAULT_DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
FAISS_DIR = Path("D:/Agente-cad-PYSIDE/data/vectors/faiss")
MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DIM = 384

CLASS_TO_TIPO = {
    "PIL": "pilar",
    "PL": "pilar",
    "LAJ": "laje",
    "LJ": "laje",
    "LV": "viga",
    "FV": "viga",
    "VIG": "viga",
}
PLURAL = {"pilar": "pilares", "viga": "vigas", "laje": "lajes"}


def normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return (vecs / norms).astype(np.float32)


def _json_loads(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        data = json.loads(str(raw))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def tipo_from_classe(classe: str) -> str:
    return CLASS_TO_TIPO.get(str(classe or "").upper(), str(classe or "").lower() or "elemento")


def format_reverse_eng_text(row: dict[str, Any]) -> str:
    campos = _json_loads(row.get("campos_json"))
    classe = str(row.get("classe") or "").upper()
    tipo = tipo_from_classe(classe)
    elemento = row.get("elemento_id") or campos.get("nome") or campos.get("numero") or row.get("id")
    obra = row.get("obra_name") or row.get("obra") or "?"
    pav = row.get("pavimento") or "?"

    parts = [
        f"{tipo.title()} {elemento}",
        f"classe={classe}",
        f"obra={obra}",
        f"pavimento={pav}",
        f"status={row.get('status', '')}",
        f"confianca={row.get('confianca', '')}",
    ]

    for key in (
        "comprimento",
        "largura",
        "altura",
        "area_cm2",
        "espessura",
        "grade_1",
        "grade_2",
        "modo_distribuicao",
    ):
        if key in campos:
            parts.append(f"{key}={campos.get(key)}")

    return ", ".join(str(p) for p in parts if p is not None)


def row_to_meta(row: dict[str, Any]) -> dict[str, Any]:
    campos = _json_loads(row.get("campos_json"))
    classe = str(row.get("classe") or "").upper()
    tipo = tipo_from_classe(classe)
    tier = get_tier(row)
    text = format_reverse_eng_text(row)
    legacy_source_id, versioned_source_id = get_reverse_ficha_source_ids(row)
    return {
        "text": text,
        "tipo": tipo,
        "id": row.get("elemento_id") or campos.get("nome") or row.get("id"),
        "obra": row.get("obra_name"),
        "pavimento": row.get("pavimento"),
        "classe": classe,
        "source_table": "reverse_eng_fichas",
        "source_id": versioned_source_id,
        "legacy_source_id": legacy_source_id,
        "ficha_id": row.get("id"),
        "tier": tier,
        "arquivo_fonte": "project_data.vision",
        "dados": campos,
    }


def fetch_candidate_rows(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    include_indexed: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    tombstones = load_tombstones()
    where = "" if include_indexed else "WHERE COALESCE(rag_indexed,0)=0"
    sql = f"""
        SELECT id, obra_name, pavimento, classe, elemento_id, campos_json,
               confianca, status, aprovado_at, rag_indexed, created_at, updated_at
        FROM reverse_eng_fichas
        {where}
        ORDER BY id
    """
    if limit:
        sql += f" LIMIT {int(limit)}"

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute(sql).fetchall()]

    return [row for row in rows if is_indexable(row, tombstones=tombstones)]


def _load_index_and_meta(name: str) -> tuple[Any, list[dict[str, Any]], Path, Path]:
    FAISS_DIR.mkdir(parents=True, exist_ok=True)
    index_path = FAISS_DIR / f"{name}.index"
    meta_path = FAISS_DIR / f"{name}_meta.json"
    if index_path.exists():
        index = faiss.read_index(str(index_path))
    else:
        index = faiss.IndexFlatIP(EMBED_DIM)
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    else:
        meta = []
    return index, meta, index_path, meta_path


def _save_index_and_meta(index: Any, meta: list[dict[str, Any]], index_path: Path, meta_path: Path) -> None:
    faiss.write_index(index, str(index_path))
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def apply_indexing(rows: list[dict[str, Any]], db_path: Path = DEFAULT_DB_PATH) -> int:
    if not rows:
        return 0

    metas = [row_to_meta(row) for row in rows]
    model = SentenceTransformer(MODEL_NAME)

    index, all_meta, index_path, meta_path = _load_index_and_meta("estruturais")
    offset = len(all_meta)
    vecs = normalize(model.encode([m["text"] for m in metas], show_progress_bar=False))
    index.add(vecs)
    for i, meta in enumerate(metas):
        meta["faiss_id"] = offset + i
        all_meta.append(meta)
    _save_index_and_meta(index, all_meta, index_path, meta_path)

    for tipo, plural in PLURAL.items():
        tipo_metas = [m for m in metas if m.get("tipo") == tipo]
        if not tipo_metas:
            continue
        tipo_index, tipo_meta, tipo_index_path, tipo_meta_path = _load_index_and_meta(plural)
        tipo_vecs = normalize(model.encode([m["text"] for m in tipo_metas], show_progress_bar=False))
        tipo_index.add(tipo_vecs)
        tipo_meta.extend(tipo_metas)
        _save_index_and_meta(tipo_index, tipo_meta, tipo_index_path, tipo_meta_path)

    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "UPDATE reverse_eng_fichas SET rag_indexed=1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [(row["id"],) for row in rows],
        )
        conn.commit()

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa somente reverse_eng_fichas T1/T2")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path do project_data.vision")
    parser.add_argument("--apply", action="store_true", help="Grava nos indices FAISS e marca rag_indexed")
    parser.add_argument("--dry-run", action="store_true", help="Audita sem gravar (padrao)")
    parser.add_argument("--include-indexed", action="store_true", help="Tambem considera rows rag_indexed=1")
    parser.add_argument("--limit", type=int, help="Limite de rows lidas antes do filtro de tier")
    args = parser.parse_args()

    rows = fetch_candidate_rows(
        Path(args.db),
        include_indexed=args.include_indexed,
        limit=args.limit,
    )
    by_class: dict[str, int] = {}
    for row in rows:
        cls = str(row.get("classe") or "?").upper()
        by_class[cls] = by_class.get(cls, 0) + 1

    print(f"[reverse_eng_fichas] candidatos T1/T2 nao indexados: {len(rows)} by_class={by_class}")
    for row in rows[:5]:
        print(
            f"  - id={row.get('id')} {row.get('classe')} {row.get('elemento_id')} "
            f"{row.get('obra_name')} {row.get('pavimento')} status={row.get('status')}"
        )

    if not args.apply:
        print("[dry-run] Nenhuma escrita realizada. Use --apply apos validacao humana.")
        return

    total = apply_indexing(rows, Path(args.db))
    print(f"[OK] indexados={total}")


if __name__ == "__main__":
    main()
