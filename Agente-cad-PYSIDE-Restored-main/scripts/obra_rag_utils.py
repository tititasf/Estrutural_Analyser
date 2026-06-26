#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obra_rag_utils.py — Utilitários compartilhados para o RAG por-obra.

Fornece:
  - embed_texts()            — NVIDIA NIM (4096-dim) com fallback local (768-dim)
  - get_obra_db()            — conexão LanceDB isolada por obra
  - get_or_create_obra_docs_table()      — tabela chunks de PDFs/MDs
  - get_or_create_obra_dxf_table()       — tabela inventário DXFs classificados
  - detect_embed_dim()       — detecta dim real do env (4096 ou 768)

LanceDB por-obra: DADOS-OBRAS/{Obra_X}/obra_rag_db/
"""

from __future__ import annotations

import os
import gc
import numpy as np
from pathlib import Path
from typing import Optional

# ── Configuração ──────────────────────────────────────────────────────────────

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")

NVIDIA_MODEL    = "nvidia/nv-embed-v1"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
LOCAL_MODEL     = "paraphrase-multilingual-mpnet-base-v2"
EMBED_BATCH     = 16

# ── Embedder (reutiliza lógica do stog_rag_ingestor) ─────────────────────────

_nvidia_client = None
_local_model   = None


def _get_nvidia_client():
    global _nvidia_client
    if _nvidia_client is None:
        import openai
        key = os.environ.get("NVIDIA_API_KEY", "")
        if not key:
            return None
        _nvidia_client = openai.OpenAI(api_key=key, base_url=NVIDIA_BASE_URL)
    return _nvidia_client


def _embed_nvidia(texts: list[str], input_type: str = "passage") -> Optional[np.ndarray]:
    client = _get_nvidia_client()
    if client is None:
        return None
    all_vecs = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        try:
            resp = client.embeddings.create(
                input=batch,
                model=NVIDIA_MODEL,
                encoding_format="float",
                extra_body={"input_type": input_type, "truncate": "END"},
            )
            for d in resp.data:
                all_vecs.append(d.embedding)
        except Exception as e:
            print(f"  [WARN] NVIDIA embed falhou: {e}")
            return None
    return np.array(all_vecs, dtype=np.float32)


def _get_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[INFO] Carregando modelo local {LOCAL_MODEL} ...")
        _local_model = SentenceTransformer(LOCAL_MODEL)
    return _local_model


def embed_texts(
    texts: list[str],
    use_nvidia: bool = True,
    input_type: str = "passage",
) -> np.ndarray:
    """Embeda textos — NVIDIA NIM primeiro, fallback local."""
    if not texts:
        return np.array([], dtype=np.float32)
    if use_nvidia:
        vecs = _embed_nvidia(texts, input_type=input_type)
        if vecs is not None:
            return vecs
        print("  [FALLBACK] Usando modelo local.")
    model = _get_local_model()
    vecs = model.encode(
        texts,
        show_progress_bar=False,
        batch_size=32,
        normalize_embeddings=True,
    )
    return np.array(vecs, dtype=np.float32)


def detect_embed_dim() -> int:
    """Retorna 4096 se NVIDIA disponível, 768 caso contrário."""
    if _get_nvidia_client() is not None:
        return 4096
    key = os.environ.get("NVIDIA_API_KEY", "")
    if key:
        return 4096
    return 768


# ── LanceDB por-obra ──────────────────────────────────────────────────────────

def get_obra_rag_path(obra_name: str) -> Path:
    return DADOS_OBRAS_ROOT / obra_name / "obra_rag_db"


def get_obra_db(obra_name: str):
    """Retorna conexão LanceDB isolada para a obra."""
    import lancedb
    db_path = get_obra_rag_path(obra_name)
    db_path.mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(db_path))


# ── Schemas ───────────────────────────────────────────────────────────────────

def get_or_create_obra_docs_table(db, embed_dim: int, overwrite: bool = False):
    """
    Tabela `obra_docs` — chunks de PDFs/MDs da obra.
    Campos: vector, text, obra_name, file_name, file_type,
            page_num, section_title, chunk_index, chunk_type, created_at
    """
    import pyarrow as pa
    TABLE = "obra_docs"
    schema = pa.schema([
        pa.field("vector",        pa.list_(pa.float32(), embed_dim)),
        pa.field("text",          pa.string()),
        pa.field("obra_name",     pa.string()),
        pa.field("file_name",     pa.string()),
        pa.field("file_type",     pa.string()),   # pdf | md
        pa.field("page_num",      pa.int32()),
        pa.field("section_title", pa.string()),
        pa.field("chunk_index",   pa.int32()),
        pa.field("chunk_type",    pa.string()),   # section | paragraph | sliding | summary
        pa.field("created_at",    pa.string()),
    ])
    existing = db.list_tables().tables if hasattr(db.list_tables(), "tables") else db.table_names()
    if overwrite and TABLE in existing:
        return db.create_table(TABLE, schema=schema, mode="overwrite")
    if TABLE in existing:
        return db.open_table(TABLE)
    return db.create_table(TABLE, schema=schema)


def get_or_create_obra_dxf_table(db, embed_dim: int, overwrite: bool = False):
    """
    Tabela `obra_dxf_inventory` — DXFs classificados da obra.
    Campos: vector, text, obra_name, dxf_path, dxf_name,
            source_folder, classified_type, classified_subtype,
            confidence, pavimento_inferred, classifier_method,
            entity_count, top_layers, created_at
    """
    import pyarrow as pa
    TABLE = "obra_dxf_inventory"
    schema = pa.schema([
        pa.field("vector",              pa.list_(pa.float32(), embed_dim)),
        pa.field("text",                pa.string()),
        pa.field("obra_name",           pa.string()),
        pa.field("dxf_path",            pa.string()),
        pa.field("dxf_name",            pa.string()),
        pa.field("source_folder",       pa.string()),
        pa.field("classified_type",     pa.string()),   # bruto | detalhe | rev_eng | desconhecido
        pa.field("classified_subtype",  pa.string()),   # PL | LV | FV | LJ | pavimento | cobertura | fundacao | ...
        pa.field("confidence",          pa.float32()),
        pa.field("pavimento_inferred",  pa.string()),
        pa.field("classifier_method",   pa.string()),   # filename | layers | embedding
        pa.field("entity_count",        pa.int32()),
        pa.field("top_layers",          pa.string()),   # JSON list serializado
        pa.field("created_at",          pa.string()),
    ])
    existing = db.list_tables().tables if hasattr(db.list_tables(), "tables") else db.table_names()
    if overwrite and TABLE in existing:
        return db.create_table(TABLE, schema=schema, mode="overwrite")
    if TABLE in existing:
        return db.open_table(TABLE)
    return db.create_table(TABLE, schema=schema)


# ── SQLite — obra_triagem ─────────────────────────────────────────────────────

DB_SQLITE = Path("D:/Agente-cad-PYSIDE/project_data.vision")


def ensure_obra_triagem_table():
    """Cria a tabela obra_triagem no SQLite global se não existir."""
    import sqlite3
    conn = sqlite3.connect(str(DB_SQLITE))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS obra_triagem (
            id                TEXT PRIMARY KEY,
            obra_name         TEXT NOT NULL,
            file_path         TEXT NOT NULL,
            file_name         TEXT NOT NULL,
            file_ext          TEXT,
            suggested_category TEXT,
            suggested_order   INTEGER DEFAULT 0,
            confidence        REAL DEFAULT 0.0,
            status            TEXT DEFAULT 'pending',
            classifier        TEXT,
            notes             TEXT,
            created_at        TEXT,
            UNIQUE(obra_name, file_path)
        )
    """)
    conn.commit()
    conn.close()


def ensure_obra_recortes_table():
    """Cria a tabela obra_recortes no SQLite global se não existir."""
    import sqlite3
    conn = sqlite3.connect(str(DB_SQLITE))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS obra_recortes (
            id                TEXT PRIMARY KEY,
            obra_name         TEXT NOT NULL,
            pavimento_name    TEXT NOT NULL,
            dxf_bruto_path    TEXT NOT NULL,
            recorte_type      TEXT NOT NULL,   -- torre | detalhe
            recorte_index     INTEGER DEFAULT 0,
            output_path       TEXT,
            bbox_auto         TEXT,            -- JSON [xmin,ymin,xmax,ymax]
            bbox_approved     TEXT,            -- JSON [xmin,ymin,xmax,ymax] após edição
            entity_count      INTEGER DEFAULT 0,
            score             REAL DEFAULT 0.0,
            status            TEXT DEFAULT 'auto',  -- auto | approved | rejected
            n_torres          INTEGER DEFAULT 1,
            created_at        TEXT,
            approved_at       TEXT,
            UNIQUE(obra_name, pavimento_name, recorte_type, recorte_index)
        )
    """)
    conn.commit()
    conn.close()


def upsert_recortes(rows: list[dict]):
    """
    Insere/atualiza recortes em obra_recortes.
    Cada row: {id, obra_name, pavimento_name, dxf_bruto_path, recorte_type,
               recorte_index, output_path, bbox_auto, bbox_approved,
               entity_count, score, status, n_torres, created_at}
    """
    import sqlite3
    if not rows:
        return
    conn = sqlite3.connect(str(DB_SQLITE))
    conn.executemany("""
        INSERT OR REPLACE INTO obra_recortes
            (id, obra_name, pavimento_name, dxf_bruto_path, recorte_type,
             recorte_index, output_path, bbox_auto, bbox_approved,
             entity_count, score, status, n_torres, created_at)
        VALUES
            (:id, :obra_name, :pavimento_name, :dxf_bruto_path, :recorte_type,
             :recorte_index, :output_path, :bbox_auto, :bbox_approved,
             :entity_count, :score, :status, :n_torres, :created_at)
    """, rows)
    conn.commit()
    conn.close()


def upsert_triagem(rows: list[dict]):
    """
    Insere/atualiza sugestões em obra_triagem.
    Cada row: {id, obra_name, file_path, file_name, file_ext,
               suggested_category, suggested_order, confidence,
               status, classifier, notes, created_at}

    Regra: INSERT OR IGNORE — não sobrescreve linhas existentes.
    Isso preserva status aprovados/rejeitados pelo usuário entre re-runs do RAG.
    Para atualizar confiança/categoria em linhas existentes,
    usa UPDATE apenas nos campos técnicos (nunca toca em status).
    """
    import sqlite3
    if not rows:
        return
    conn = sqlite3.connect(str(DB_SQLITE))
    # 1. Inserir apenas arquivos NOVOS (preserva status de aprovações/rejeições existentes)
    conn.executemany("""
        INSERT OR IGNORE INTO obra_triagem
            (id, obra_name, file_path, file_name, file_ext,
             suggested_category, suggested_order, confidence,
             status, classifier, notes, created_at)
        VALUES
            (:id, :obra_name, :file_path, :file_name, :file_ext,
             :suggested_category, :suggested_order, :confidence,
             :status, :classifier, :notes, :created_at)
    """, rows)
    # 2. Para linhas já existentes: atualizar apenas dados técnicos (nunca status/id)
    conn.executemany("""
        UPDATE obra_triagem
           SET confidence        = :confidence,
               suggested_category= :suggested_category,
               suggested_order   = :suggested_order,
               classifier        = :classifier,
               notes             = :notes
         WHERE obra_name = :obra_name
           AND file_path = :file_path
           AND status    = 'pending'
    """, rows)
    conn.commit()
    conn.close()
