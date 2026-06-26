#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
domain_knowledge_ingestor.py — RAG Forge / CAD Domain Knowledge
=================================================================
Indexa documentos de regras/semântica de domínio CAD no LanceDB existente.
Cria tabela `domain_knowledge` no mesmo DB que `stog_kbs`.

Complementa stog_kbs (inventário por-DXF) com conhecimento de REGRAS:
  - Semântica de campos (o que significa grade_1, h1, larg1_X, etc.)
  - Fórmulas de cálculo (grade = comprimento + 22, h3 = sobra, etc.)
  - Nomenclatura de faces, pavimentos, elementos estruturais
  - Bugs conhecidos e comportamentos esperados

Embedder: nvidia/nv-embed-v1 via NVIDIA NIM (4096-dim)
Fallback: paraphrase-multilingual-mpnet-base-v2 (768-dim, offline)
Store: D:/Agente-cad-PYSIDE/DADOS-OBRAS/stog_rag_db (mesma instância que stog_kbs)

Uso:
    python domain_knowledge_ingestor.py              # ingere todos os docs prioritários
    python domain_knowledge_ingestor.py --file docs/SEMANTICA-PILAR-NOVA.md
    python domain_knowledge_ingestor.py --query "o que é grade_1 pilar"
    python domain_knowledge_ingestor.py --status
    python domain_knowledge_ingestor.py --overwrite   # recriar tabela do zero
"""

import argparse
import re
import sys
from pathlib import Path

# ─── Configuração ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main")
DB_PATH      = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/stog_rag_db")
TABLE_NAME   = "domain_knowledge"

# Docs prioritários (caminho relativo a PROJECT_ROOT)
PRIORITY_DOCS = [
    "docs/SEMANTICA-PILAR-NOVA.md",
    "docs/CONTEXTUALIZACAO_VIGAS_SEGMENTOS_FUNDOS.md",
    "docs/REVERSE_ENGINEERING.md",
    "docs/ROBOS_GUIDE.md",
    "docs/DATA_FLOW.md",
    "docs/SPEC-GERADORES-DXF.md",
    "docs/schema_itens_estruturais.yaml",
    "docs/MASTERPLAN-INTERPRETACAO-VALIDACAO.md",
    "docs/VECTOR_SCHEMA.md",
    # Novos docs — algoritmos e padrões SCR (2026-06-04)
    "docs/CALCULOS_ALGORITMOS.md",
    "docs/ROBO_SCR_PATTERNS.md",
    # Semântica validada Sprint 1 (2026-06-04)
    "docs/SEMANTICA-VIGA-NOVA.md",
    "docs/SEMANTICA-LAJE-NOVA.md",
]

# Embedder (reutiliza lógica de stog_rag_ingestor)
NVIDIA_MODEL   = "nvidia/nv-embed-v1"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
LOCAL_MODEL    = "paraphrase-multilingual-mpnet-base-v2"
EMBED_DIM_NVIDIA = 4096
EMBED_DIM_LOCAL  = 768

# Chunking por seção markdown
MIN_CHUNK_CHARS = 80
MAX_CHUNK_CHARS = 1200


# ─── Chunking semântico por seção ─────────────────────────────────────────────

def _detect_doc_type(path: Path) -> str:
    """Classifica o documento por tipo para metadata."""
    name = path.name.lower()
    if "semantica" in name:         return "field_semantics"
    if "viga" in name:              return "field_semantics"
    if "laje" in name and "semantica" in name: return "field_semantics"
    if "contextualizacao" in name:  return "field_semantics"
    if "reverse" in name:           return "extractor_logic"
    if "calculos" in name:          return "calculation_algorithm"
    if "algoritmos" in name:        return "calculation_algorithm"
    if "scr_patterns" in name:      return "robot_drawing_rules"
    if "robo" in name:              return "robot_guide"
    if "data_flow" in name:         return "pipeline_architecture"
    if "spec" in name:              return "generator_spec"
    if "schema" in name:            return "data_schema"
    if "masterplan" in name:        return "validation_protocol"
    if "vector" in name:            return "data_schema"
    return "documentation"


def _extract_doc_tags(path: Path, content: str) -> list[str]:
    """Extrai tags semânticas do documento para filtros de retrieval."""
    tags = []
    name_lower = path.name.lower()

    # Tags por nome do arquivo
    for kw in ["pilar", "viga", "laje", "grade", "faces", "parafuso",
                "lancedb", "chromadb", "embed", "chunk", "rag",
                "nova", "stog", "fase3", "fase4", "scr", "robo",
                "algoritmo", "calculo", "layer", "bloco", "sarrafo",
                "abcd", "cima", "grades", "fundo", "lateral"]:
        if kw in name_lower or kw in content.lower()[:500]:
            tags.append(kw)

    # Tags por classe estrutural mencionada
    for cls in ["PL", "LV", "FV", "LJ", "GF"]:
        if cls in content:
            tags.append(cls.lower())

    return list(set(tags))[:10]


def _chunk_markdown(content: str, source_name: str, doc_type: str,
                    source_path: str, tags: list[str]) -> list[dict]:
    """
    Chunking por seção (##/###). Cada seção vira um chunk.
    Seções pequenas são mescladas com a anterior.
    """
    chunks = []

    # Dividir por headers ## ou ###
    pattern = r'^(#{1,3} .+)$'
    parts = re.split(pattern, content, flags=re.MULTILINE)

    current_header = source_name
    current_body = []

    def flush(header, body_lines):
        body = "\n".join(body_lines).strip()
        if len(body) < MIN_CHUNK_CHARS:
            return None
        text = f"{header}\n\n{body}"
        # Truncar se muito longo (manter semanticamente denso)
        if len(text) > MAX_CHUNK_CHARS:
            text = text[:MAX_CHUNK_CHARS] + "..."
        return {
            "text": text,
            "source_doc": source_name,
            "doc_type": doc_type,
            "section": header.lstrip("#").strip(),
            "source_path": source_path,
            "tags": ",".join(tags),
            "sprint_validated": "sprint1" in source_name.lower() or "semantica" in source_name.lower(),
        }

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if re.match(r'^#{1,3} ', part):
            # Flush anterior
            chunk = flush(current_header, current_body)
            if chunk:
                chunks.append(chunk)
            current_header = part
            current_body = []
        else:
            current_body.append(part)

    # Flush final
    chunk = flush(current_header, current_body)
    if chunk:
        chunks.append(chunk)

    return chunks


def doc_to_chunks(doc_path: Path) -> list[dict]:
    """Lê um documento e retorna lista de chunks com metadata."""
    content = doc_path.read_text(encoding="utf-8", errors="replace")
    doc_type = _detect_doc_type(doc_path)
    tags = _extract_doc_tags(doc_path, content)
    chunks = _chunk_markdown(
        content,
        source_name=doc_path.name,
        doc_type=doc_type,
        source_path=str(doc_path),
        tags=tags,
    )
    return chunks


# ─── Embedding (reutiliza lógica de stog_rag_ingestor) ────────────────────────

def _load_embedder():
    """Tenta NVIDIA NIM; fallback para local."""
    import os
    api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=NVIDIA_BASE_URL)
            # Test
            client.embeddings.create(input=["test"], model=NVIDIA_MODEL)
            print(f"[embed] NVIDIA NIM ({NVIDIA_MODEL}, {EMBED_DIM_NVIDIA}-dim)")
            return "nvidia", client, EMBED_DIM_NVIDIA
        except Exception as e:
            print(f"[embed] NVIDIA NIM falhou: {e} — usando local")

    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(LOCAL_MODEL)
        dim = model.get_sentence_embedding_dimension()
        print(f"[embed] Local ({LOCAL_MODEL}, {dim}-dim)")
        return "local", model, dim
    except ImportError:
        raise RuntimeError(
            "sentence-transformers não instalado. "
            "Instale com: pip install sentence-transformers"
        )


def embed_texts(embedder_type, embedder, texts: list[str]) -> list[list[float]]:
    """Gera embeddings para lista de textos."""
    if embedder_type == "nvidia":
        resp = embedder.embeddings.create(input=texts, model=NVIDIA_MODEL)
        return [e.embedding for e in resp.data]
    else:
        vecs = embedder.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return vecs.tolist()


# ─── LanceDB schema + table ───────────────────────────────────────────────────

def get_or_create_table(db, embed_dim: int, overwrite: bool = False):
    """Cria ou abre a tabela domain_knowledge."""
    import pyarrow as pa

    schema = pa.schema([
        pa.field("vector",           pa.list_(pa.float32(), embed_dim)),
        pa.field("text",             pa.utf8()),
        pa.field("source_doc",       pa.utf8()),
        pa.field("doc_type",         pa.utf8()),
        pa.field("section",          pa.utf8()),
        pa.field("source_path",      pa.utf8()),
        pa.field("tags",             pa.utf8()),
        pa.field("sprint_validated", pa.bool_()),
    ])

    if overwrite and TABLE_NAME in db.list_tables().tables:
        db.drop_table(TABLE_NAME)
        print(f"[db] Tabela '{TABLE_NAME}' removida (overwrite)")

    if TABLE_NAME not in db.list_tables().tables:
        tbl = db.create_table(TABLE_NAME, schema=schema)
        print(f"[db] Tabela '{TABLE_NAME}' criada (dim={embed_dim})")
    else:
        tbl = db.open_table(TABLE_NAME)
        print(f"[db] Tabela '{TABLE_NAME}' aberta ({tbl.count_rows()} rows existentes)")

    return tbl


# ─── Dedup: não reingerir docs já indexados ───────────────────────────────────

def get_indexed_docs(tbl) -> set[str]:
    """Retorna set de source_doc já indexados."""
    try:
        import pandas as pd
        df = tbl.to_pandas()
        return set(df["source_doc"].unique().tolist())
    except Exception:
        return set()


# ─── Ingestão ─────────────────────────────────────────────────────────────────

def ingest_doc(doc_path: Path, tbl, embedder_type, embedder, force: bool = False):
    """Ingere um documento no LanceDB. Pula se já indexado (a menos que force=True)."""
    indexed = get_indexed_docs(tbl)
    if doc_path.name in indexed and not force:
        print(f"  [skip] {doc_path.name} já indexado ({indexed})" if False else
              f"  [skip] {doc_path.name} já indexado")
        return 0

    chunks = doc_to_chunks(doc_path)
    if not chunks:
        print(f"  [warn] {doc_path.name}: 0 chunks gerados")
        return 0

    # Embed em batch
    texts = [c["text"] for c in chunks]
    BATCH = 16
    all_vectors = []
    for i in range(0, len(texts), BATCH):
        batch = texts[i:i + BATCH]
        vecs = embed_texts(embedder_type, embedder, batch)
        all_vectors.extend(vecs)

    # Montar rows
    import pyarrow as pa
    rows = []
    for chunk, vec in zip(chunks, all_vectors):
        rows.append({
            "vector":           vec,
            "text":             chunk["text"],
            "source_doc":       chunk["source_doc"],
            "doc_type":         chunk["doc_type"],
            "section":          chunk["section"],
            "source_path":      chunk["source_path"],
            "tags":             chunk["tags"],
            "sprint_validated": chunk["sprint_validated"],
        })

    tbl.add(rows)
    print(f"  [ok] {doc_path.name}: {len(rows)} chunks indexados")
    return len(rows)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def cmd_ingest(args):
    """Ingere docs prioritários (ou arquivo específico)."""
    import lancedb

    embedder_type, embedder, embed_dim = _load_embedder()
    db = lancedb.connect(str(DB_PATH))
    tbl = get_or_create_table(db, embed_dim, overwrite=args.overwrite)

    if args.file:
        doc_path = Path(args.file)
        if not doc_path.is_absolute():
            doc_path = PROJECT_ROOT / doc_path
        if not doc_path.exists():
            print(f"[erro] Arquivo não encontrado: {doc_path}")
            sys.exit(1)
        total = ingest_doc(doc_path, tbl, embedder_type, embedder, force=args.overwrite)
        print(f"\nTotal: {total} chunks indexados")
    else:
        total = 0
        missing = []
        for rel in PRIORITY_DOCS:
            doc_path = PROJECT_ROOT / rel
            if not doc_path.exists():
                missing.append(rel)
                print(f"  [miss] {rel}")
                continue
            n = ingest_doc(doc_path, tbl, embedder_type, embedder, force=args.overwrite)
            total += n

        print(f"\nTotal: {total} chunks indexados")
        if missing:
            print(f"Docs ausentes ({len(missing)}): {missing}")


def cmd_query(args):
    """Testa retrieval semântico."""
    import lancedb

    embedder_type, embedder, _ = _load_embedder()
    db = lancedb.connect(str(DB_PATH))

    if TABLE_NAME not in db.list_tables().tables:
        print(f"[erro] Tabela '{TABLE_NAME}' não existe. Execute sem --query primeiro.")
        sys.exit(1)

    tbl = db.open_table(TABLE_NAME)
    query_vec = embed_texts(embedder_type, embedder, [args.query])[0]

    results = (
        tbl.search(query_vec)
           .limit(5)
           .select(["text", "source_doc", "section", "doc_type"])
           .to_list()
    )

    print(f'\nResultados para: "{args.query}"\n')
    for i, r in enumerate(results, 1):
        score = r.get("_distance", "?")
        section_safe = r['section'].encode('ascii', errors='replace').decode('ascii')
        text_safe = r['text'][:200].encode('ascii', errors='replace').decode('ascii')
        print(f"[{i}] {r['source_doc']} | {section_safe} (dist={score:.4f})")
        print(f"     {text_safe}...")
        print()


def cmd_status(args):
    """Mostra status das tabelas RAG."""
    import lancedb
    import pandas as pd

    db = lancedb.connect(str(DB_PATH))
    print(f"DB: {DB_PATH}")
    print(f"Tabelas: {db.list_tables().tables}\n")

    for tname in db.list_tables().tables:
        tbl = db.open_table(tname)
        n = tbl.count_rows()
        df = tbl.to_pandas()
        print(f"  [{tname}] {n} rows")
        if "chunk_type" in df.columns:
            print(f"    chunk_types: {df['chunk_type'].value_counts().to_dict()}")
        if "doc_type" in df.columns:
            print(f"    doc_types:   {df['doc_type'].value_counts().to_dict()}")
        if "source_doc" in df.columns:
            docs = df["source_doc"].unique().tolist()
            print(f"    docs ({len(docs)}): {docs[:8]}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Domain Knowledge RAG Ingestor")
    parser.add_argument("--file",      help="Indexar arquivo específico")
    parser.add_argument("--query",     help="Testar retrieval com uma query")
    parser.add_argument("--status",    action="store_true", help="Status das tabelas")
    parser.add_argument("--overwrite", action="store_true", help="Recriar tabela + forçar re-ingestão")
    args = parser.parse_args()

    if args.status:
        cmd_status(args)
    elif args.query:
        cmd_query(args)
    else:
        cmd_ingest(args)


if __name__ == "__main__":
    main()
