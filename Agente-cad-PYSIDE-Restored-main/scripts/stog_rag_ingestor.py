#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stog_rag_ingestor.py — EPIC-STOG-3
====================================
Indexa 535 KB JSONs do STOG Intelligence no LanceDB para busca semântica cross-obra.

Estratégia de chunking (4 chunks por KB):
  1. header      — identidade: obra, classe, pavimento, total_entities
  2. inventory   — top layers + contagens
  3. semantics   — roles estruturais dos layers (robot/pattern_match/discovery)
  4. nomenclaturas — IDs de elementos detectados (P1, V1, L1, etc.)

Embedder: nvidia/nv-embed-v1 via NVIDIA NIM API (4096-dim, qualidade máxima)
Fallback: paraphrase-multilingual-mpnet-base-v2 (offline, 768-dim)
Store: LanceDB local em D:/Agente-cad-PYSIDE/DADOS-OBRAS/stog_rag_db/

Uso:
    python stog_rag_ingestor.py             # ingere tudo
    python stog_rag_ingestor.py --query "pilares com SARR_2.2x7"
    python stog_rag_ingestor.py --status    # mostra stats do índice
"""

import argparse
import gc
import json
import sys
from pathlib import Path

import numpy as np

DB_PATH = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/stog_rag_db")
KB_BASE = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
TABLE_NAME = "stog_kbs"
TOP_LAYERS_MAX = 20
TOP_NOMS_MAX = 30

# Embedder: NVIDIA NIM (qualidade máxima, 4096-dim) com fallback local
NVIDIA_MODEL = "nvidia/nv-embed-v1"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
LOCAL_MODEL = "paraphrase-multilingual-mpnet-base-v2"
EMBED_DIM = 4096        # nv-embed-v1
EMBED_BATCH = 16        # batch menor para API (evitar timeout)
NVIDIA_API_KEY = None   # carregado lazy do env


# ---------------------------------------------------------------------------
# Serialização JSON → texto semântico (4 chunks)
# ---------------------------------------------------------------------------

def _get_fidelidade_score(obra_dir: Path, classe: str) -> tuple[float | None, bool | None]:
    """Lê score e aprovado do JSON de fidelidade para a classe."""
    cls_map = {"PL": "fidelidade_pilares.json", "LV": "fidelidade_vigas.json",
               "FV": "fidelidade_vigas.json", "LJ": "fidelidade_lajes.json"}
    fname = cls_map.get(classe)
    if not fname:
        return None, None
    f = obra_dir / "Fase-7_Consolidacao" / fname
    if not f.exists():
        return None, None
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        if classe in ("LV", "FV"):
            sub = d.get("sub_tipos", {}).get(classe, {})
            return sub.get("score"), sub.get("aprovado")
        return d.get("score"), d.get("aprovado")
    except Exception:
        return None, None


def _extract_obra_nome(kb_file: str) -> str:
    """Extrai nome legível da obra a partir do nome do arquivo KB."""
    # Ex: "ALIMONTI - PARAISO - TIPO - 3° AO 12° PAV.- PL - R00.dxf" → "ALIMONTI - PARAISO"
    parts = kb_file.replace(".dxf", "").split(" - ")
    # Ignorar sufixos de classe e revisão no final
    skip_suffixes = {"PL", "LV", "FV", "LJ", "GF", "GD", "CP", "VG", "CB",
                     "R00", "R01", "R02", "R00 (2)", "R2018", "ASCII", "ODA"}
    nome_parts = []
    for p in parts:
        p_clean = p.strip()
        if p_clean.upper() in skip_suffixes or p_clean.startswith("R0") or "PAV" in p_clean.upper():
            break
        nome_parts.append(p_clean)
    return " - ".join(nome_parts[:3]) if nome_parts else kb_file[:40]


def kb_to_chunks(kb: dict, kb_path: Path) -> list[dict]:
    """
    Converte um KB JSON em lista de dicts com {text, metadata}.
    Gera até 4 chunks por KB.
    """
    obra = kb.get("obra") or "?"
    # Inferir obra do path: .../Obra_TREINO_X/Fase-0_STOG_KB/PL/arquivo_kb.json
    obra_dir = None
    for part in kb_path.parts:
        if "TREINO" in part or "Obra_" in part:
            obra = part.replace("Obra_", "")
            # Reconstruir path da obra para buscar fidelidade
            idx = list(kb_path.parts).index(part)
            obra_dir = Path(*kb_path.parts[:idx + 1])
            break

    classe = kb.get("classe", kb_path.parent.name)
    pavimento = kb.get("pavimento", "")
    inventory = kb.get("inventory", {})
    total_entities = inventory.get("total_entities", 0) or sum(inventory.get("by_layer", {}).values())
    by_layer = inventory.get("by_layer", {})
    layer_semantics = kb.get("semantic_analysis", {}).get("layer_semantics", {})
    text_content = kb.get("text_content", {})
    class_specific = kb.get("class_specific", {})
    kb_file = kb.get("file", kb_path.name)

    # Enriquecimento: fidelidade score + nome real
    fid_score, fid_aprovado = _get_fidelidade_score(obra_dir, classe) if obra_dir else (None, None)
    obra_nome = _extract_obra_nome(kb_file)

    base_meta = {
        "obra": obra,
        "obra_nome": obra_nome,
        "classe": classe,
        "pavimento": pavimento,
        "total_entities": int(total_entities),
        "kb_file": kb_file,
        "kb_path": str(kb_path),
        "fidelidade_score": float(fid_score) if fid_score is not None else -1.0,
        "fidelidade_aprovado": str(fid_aprovado) if fid_aprovado is not None else "N/A",
    }

    chunks = []

    # --- CHUNK 1: Header / Identidade ---
    tipo = class_specific.get("tipo", "")
    subtipo = class_specific.get("subtipo", "")
    tipo_str = f", tipo {tipo}" if tipo else ""
    subtipo_str = f", subtipo {subtipo}" if subtipo else ""
    header_text = (
        f"Obra {obra} — classe {classe}{tipo_str}{subtipo_str}, "
        f"pavimento {pavimento or 'N/A'}, "
        f"{total_entities} entidades totais. "
        f"Arquivo: {kb_file}."
    )
    chunks.append({"text": header_text, **base_meta, "chunk_type": "header"})

    # --- CHUNK 2: Inventory (top layers) ---
    if by_layer:
        top_layers = sorted(by_layer.items(), key=lambda x: -x[1])[:TOP_LAYERS_MAX]
        layers_str = ", ".join(f"{l}({c})" for l, c in top_layers)
        n_unique = len(by_layer)
        inv_text = (
            f"Obra {obra} classe {classe} pavimento {pavimento or 'N/A'}: "
            f"{n_unique} layers únicos, top layers: {layers_str}."
        )
        chunks.append({"text": inv_text, **base_meta, "chunk_type": "inventory"})

    # --- CHUNK 3: Semântica dos layers ---
    if layer_semantics:
        robot_layers = [l for l, s in layer_semantics.items() if s.get("source") == "robot"]
        pattern_layers = [l for l, s in layer_semantics.items() if s.get("source") == "pattern_match"]
        discovery_layers = [l for l, s in layer_semantics.items() if s.get("source") == "autonomous_discovery"]
        roles = list({s.get("role", "") for s in layer_semantics.values() if s.get("role")})

        sem_text = (
            f"Obra {obra} classe {classe} análise semântica: "
            f"layers confirmados pelos robôs: {', '.join(robot_layers[:15]) or 'nenhum'}. "
            f"Layers por padrão: {', '.join(pattern_layers[:10]) or 'nenhum'}. "
            f"Layers de autoria/carimbo: {', '.join(discovery_layers[:5]) or 'nenhum'}. "
            f"Roles estruturais: {', '.join(roles[:10]) or 'N/A'}."
        )
        chunks.append({"text": sem_text, **base_meta, "chunk_type": "semantics"})

    # --- CHUNK 4: Nomenclaturas (IDs de elementos) ---
    raw_noms = text_content.get("nomenclaturas_detected", [])
    noms = []
    for n in raw_noms:
        if isinstance(n, dict):
            c = n.get("content", "")
        else:
            c = str(n)
        if c:
            noms.append(c)

    if noms:
        sample = noms[:TOP_NOMS_MAX]
        nom_text = (
            f"Obra {obra} classe {classe} pavimento {pavimento or 'N/A'} "
            f"IDs detectados ({len(noms)} total): {', '.join(sample)}."
        )
        chunks.append({"text": nom_text, **base_meta, "chunk_type": "nomenclaturas"})

    return chunks


# ---------------------------------------------------------------------------
# Coleta de KBs
# ---------------------------------------------------------------------------

def collect_kb_paths(kb_base: Path) -> list[Path]:
    """Lista todos os *_kb.json nas obras TREINO_*."""
    paths = []
    for obra_dir in sorted(kb_base.glob("Obra_TREINO_*")):
        stog_kb = obra_dir / "Fase-0_STOG_KB"
        if not stog_kb.exists():
            continue
        for kb_file in sorted(stog_kb.rglob("*_kb.json")):
            paths.append(kb_file)
    return paths


# ---------------------------------------------------------------------------
# Embedder — NVIDIA NIM (qualidade máxima) com fallback local
# ---------------------------------------------------------------------------

_nvidia_client = None
_local_model = None


def _get_nvidia_client():
    global _nvidia_client, NVIDIA_API_KEY
    if _nvidia_client is None:
        import os, openai
        NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
        if not NVIDIA_API_KEY:
            return None
        _nvidia_client = openai.OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)
    return _nvidia_client


def _embed_nvidia(texts: list[str], input_type: str = "passage") -> np.ndarray | None:
    """Embeda via NVIDIA NIM em batches de EMBED_BATCH."""
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
            print(f"  [WARN] NVIDIA embed falhou: {e} — abortando batch")
            return None
    return np.array(all_vecs, dtype=np.float32)


def _get_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[INFO] Fallback: carregando modelo local {LOCAL_MODEL}")
        _local_model = SentenceTransformer(LOCAL_MODEL)
    return _local_model


def embed_texts(texts: list[str], use_nvidia: bool = True, input_type: str = "passage") -> np.ndarray:
    """
    Embeda textos — tenta NVIDIA primeiro, fallback para local.

    input_type:
      "passage" — documentos sendo indexados
      "query"   — query do usuário em tempo de busca (DIFERENTE para modelos assimétricos)
    """
    if use_nvidia:
        vecs = _embed_nvidia(texts, input_type=input_type)
        if vecs is not None:
            return vecs
        print("  [FALLBACK] Usando modelo local.")
    model = _get_local_model()
    vecs = model.encode(texts, show_progress_bar=False, batch_size=32, normalize_embeddings=True)
    return np.array(vecs, dtype=np.float32)


# ---------------------------------------------------------------------------
# LanceDB
# ---------------------------------------------------------------------------

def get_or_create_table(db, embed_dim: int, overwrite: bool = False):
    import pyarrow as pa
    schema = pa.schema([
        pa.field("vector", pa.list_(pa.float32(), embed_dim)),
        pa.field("text", pa.string()),
        pa.field("obra", pa.string()),
        pa.field("obra_nome", pa.string()),
        pa.field("classe", pa.string()),
        pa.field("pavimento", pa.string()),
        pa.field("total_entities", pa.int32()),
        pa.field("kb_file", pa.string()),
        pa.field("kb_path", pa.string()),
        pa.field("chunk_type", pa.string()),
        pa.field("fidelidade_score", pa.float32()),
        pa.field("fidelidade_aprovado", pa.string()),
    ])
    existing = db.list_tables().tables
    if overwrite:
        return db.create_table(TABLE_NAME, schema=schema, mode="overwrite")
    if TABLE_NAME in existing:
        return db.open_table(TABLE_NAME)
    return db.create_table(TABLE_NAME, schema=schema)


# ---------------------------------------------------------------------------
# Ingestão
# ---------------------------------------------------------------------------

def ingest(rebuild: bool = False):
    import lancedb

    print(f"[INFO] DB path: {DB_PATH}")
    db = lancedb.connect(str(DB_PATH))

    kb_paths = collect_kb_paths(KB_BASE)
    print(f"[INFO] KBs encontradas: {len(kb_paths)}")

    if not kb_paths:
        print("[ERRO] Nenhuma KB encontrada em KB_BASE.")
        return

    # Detectar dim real do embedder antes de criar tabela
    print("[INFO] Detectando dimensão do embedder...")
    sample_vecs = embed_texts(["dimensão probe"], use_nvidia=True)
    actual_dim = sample_vecs.shape[1]
    print(f"[INFO] Embed dim detectado: {actual_dim}")

    if rebuild:
        print(f"[INFO] Rebuild solicitado — recriando tabela com schema v2.")

    table = get_or_create_table(db, actual_dim, overwrite=rebuild)

    # Verificar KBs já indexadas
    try:
        existing = set(table.to_pandas()["kb_path"].tolist())
    except Exception:
        existing = set()

    print(f"[INFO] KBs já indexadas: {len(existing)}")

    new_paths = [p for p in kb_paths if str(p) not in existing]
    print(f"[INFO] KBs novas a processar: {len(new_paths)}")

    if not new_paths:
        print("[INFO] Nada a fazer — índice já está completo.")
        _print_stats(table)
        return

    # Processar em batches de 50 KBs para não explodir RAM
    BATCH_SIZE = 50
    total_chunks = 0

    for batch_start in range(0, len(new_paths), BATCH_SIZE):
        batch = new_paths[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(new_paths) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"[BATCH {batch_num}/{total_batches}] Processando {len(batch)} KBs...")

        all_chunks = []
        for kb_path in batch:
            try:
                kb = json.loads(kb_path.read_text(encoding="utf-8"))
                chunks = kb_to_chunks(kb, kb_path)
                all_chunks.extend(chunks)
            except Exception as e:
                print(f"  [WARN] Erro em {kb_path.name}: {e}")

        if not all_chunks:
            continue

        texts = [c["text"] for c in all_chunks]
        print(f"  Embedding {len(texts)} chunks...")
        vectors = embed_texts(texts)

        rows = []
        for chunk, vec in zip(all_chunks, vectors):
            rows.append({
                "vector": vec.tolist(),
                "text": chunk["text"],
                "obra": chunk["obra"],
                "obra_nome": chunk.get("obra_nome", ""),
                "classe": chunk["classe"],
                "pavimento": chunk["pavimento"],
                "total_entities": int(chunk["total_entities"]),
                "kb_file": chunk["kb_file"],
                "kb_path": chunk["kb_path"],
                "chunk_type": chunk["chunk_type"],
                "fidelidade_score": float(chunk.get("fidelidade_score", -1.0)),
                "fidelidade_aprovado": str(chunk.get("fidelidade_aprovado", "N/A")),
            })

        table.add(rows)
        total_chunks += len(rows)
        print(f"  +{len(rows)} chunks inseridos. Total acumulado: {total_chunks}")

        gc.collect()

    print(f"\n[OK] Ingestão completa. {total_chunks} chunks novos indexados.")

    # Criar/atualizar índice FTS (inverted index) para hybrid search
    print("[INFO] Criando índice FTS (inverted) na coluna 'text'...")
    try:
        table.create_fts_index("text", replace=True)
        print("[OK] Índice FTS criado. Hybrid search disponível com --hybrid.")
    except Exception as e:
        print(f"[WARN] Índice FTS não criado: {e}")

    _print_stats(table)


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

def _print_results(df, q: str, filters: dict | None, mode: str = "dense"):
    """Exibe resultados de busca formatados."""
    print(f"\n[QUERY-{mode.upper()}] '{q}'")
    if filters:
        print(f"[FILTER] {filters}")
    print(f"[RESULTADOS] Top {len(df)}:\n")
    for i, row in df.iterrows():
        fid = row.get("fidelidade_score", -1.0)
        aprov = row.get("fidelidade_aprovado", "N/A")
        fid_str = f" | Fidelidade={fid:.1f} ({aprov})" if fid >= 0 else ""
        obra_nome = row.get("obra_nome", "")
        nome_str = f" ({obra_nome})" if obra_nome and obra_nome != row["obra"] else ""
        print(f"  {i+1}. [{row['chunk_type'].upper()}] Obra={row['obra']}{nome_str} Classe={row['classe']} Pav={row['pavimento']}{fid_str}")
        print(f"     Entidades={row['total_entities']} | Arquivo: {row['kb_file']}")
        print(f"     Texto: {row['text'][:200]}...")
        print()


def query(q: str, n_results: int = 5, filters: dict | None = None, hybrid: bool = False):
    import lancedb

    db = lancedb.connect(str(DB_PATH))
    if TABLE_NAME not in db.list_tables().tables:
        print("[ERRO] Índice não encontrado. Rode sem --query primeiro para indexar.")
        return

    table = db.open_table(TABLE_NAME)

    where_clause = None
    if filters:
        parts = []
        for k, v in filters.items():
            parts.append(f'{k} = "{v}"')
        where_clause = " AND ".join(parts)

    if hybrid:
        # Hybrid = dense (vetorial) + FTS (BM25) — resultados únicos por kb_path+chunk_type
        print("[INFO] Modo hybrid: dense + FTS")

        # 1. Dense search
        vec = embed_texts([q], input_type="query")[0]
        dense_q = table.search(vec).limit(n_results * 2)
        if where_clause:
            dense_q = dense_q.where(where_clause)
        try:
            df_dense = dense_q.to_pandas()
        except Exception:
            df_dense = None

        # 2. FTS search (BM25 — inverted index)
        try:
            fts_q = table.search(q, query_type="fts").limit(n_results * 2)
            if where_clause:
                fts_q = fts_q.where(where_clause)
            df_fts = fts_q.to_pandas()
        except Exception as e:
            print(f"  [WARN] FTS indisponível: {e}. Usando apenas dense.")
            df_fts = None

        # 3. Merge: dense pesa 0.6, FTS pesa 0.4 — Reciprocal Rank Fusion simplificado
        seen = {}  # kb_path+chunk_type → {row, score}
        if df_dense is not None:
            for rank, (_, row) in enumerate(df_dense.iterrows()):
                key = f"{row['kb_path']}|{row['chunk_type']}"
                score = 1.0 / (rank + 1) * 0.6
                seen[key] = {"row": row, "score": score}
        if df_fts is not None:
            for rank, (_, row) in enumerate(df_fts.iterrows()):
                key = f"{row['kb_path']}|{row['chunk_type']}"
                fts_score = 1.0 / (rank + 1) * 0.4
                if key in seen:
                    seen[key]["score"] += fts_score
                else:
                    seen[key] = {"row": row, "score": fts_score}

        merged = sorted(seen.values(), key=lambda x: -x["score"])[:n_results]
        if not merged:
            print("[INFO] Nenhum resultado encontrado.")
            return

        import pandas as pd
        df = pd.DataFrame([m["row"] for m in merged]).reset_index(drop=True)
        _print_results(df, q, filters, mode="hybrid")
    else:
        vec = embed_texts([q], input_type="query")[0]
        results = table.search(vec).limit(n_results)
        if where_clause:
            results = results.where(where_clause)
        df = results.to_pandas()
        _print_results(df, q, filters, mode="dense")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def _print_stats(table):
    try:
        df = table.to_pandas()
        print(f"\n[STATS] Tabela '{TABLE_NAME}':")
        print(f"  Total chunks: {len(df)}")
        print(f"  Embed dim: {len(df['vector'].iloc[0]) if len(df) > 0 else 'N/A'}")
        print(f"  Por obra:  {dict(df['obra'].value_counts().head(10))}")
        print(f"  Por classe: {dict(df['classe'].value_counts())}")
        print(f"  Por chunk_type: {dict(df['chunk_type'].value_counts())}")
        kbs_unicos = df['kb_path'].nunique()
        print(f"  KBs únicos indexados: {kbs_unicos}")
        # Fidelidade stats (apenas headers para não duplicar)
        if "fidelidade_score" in df.columns:
            hdr = df[df["chunk_type"] == "header"]
            com_fid = hdr[hdr["fidelidade_score"] >= 0]
            if len(com_fid) > 0:
                aprovados = com_fid[com_fid["fidelidade_aprovado"] == "True"]
                print(f"  Fidelidade: {len(com_fid)} KBs com score, "
                      f"{len(aprovados)}/{len(com_fid)} aprovados "
                      f"({100*len(aprovados)//len(com_fid)}%), "
                      f"média={com_fid['fidelidade_score'].mean():.1f}")
    except Exception as e:
        print(f"  [WARN] Erro ao ler stats: {e}")


def status():
    import lancedb
    db = lancedb.connect(str(DB_PATH))
    if TABLE_NAME not in db.list_tables().tables:
        print("[INFO] Índice ainda não criado.")
        return
    table = db.open_table(TABLE_NAME)
    _print_stats(table)
    # FTS index status
    try:
        stats = table.index_stats("text_idx")
        print(f"  FTS index: OK ({stats})")
    except Exception:
        print("  FTS index: não criado (use --build-fts para criar)")


def build_fts():
    """Cria/recria índice FTS (inverted) na tabela existente."""
    import lancedb
    db = lancedb.connect(str(DB_PATH))
    if TABLE_NAME not in db.list_tables().tables:
        print("[ERRO] Tabela não encontrada. Execute a ingestão primeiro.")
        return
    table = db.open_table(TABLE_NAME)
    print("[INFO] Criando índice FTS (inverted) na coluna 'text'...")
    table.create_fts_index("text", replace=True)
    print("[OK] Índice FTS criado. Hybrid search disponível com --hybrid.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="STOG RAG Ingestor — EPIC-STOG-3")
    parser.add_argument("--query", "-q", type=str, help="Query semântica")
    parser.add_argument("--top", type=int, default=5, help="Número de resultados (default: 5)")
    parser.add_argument("--filter-obra", type=str, help="Filtrar por obra (ex: TREINO_1)")
    parser.add_argument("--filter-classe", type=str, help="Filtrar por classe (ex: PL)")
    parser.add_argument("--hybrid", action="store_true", help="Modo hybrid: dense + FTS BM25")
    parser.add_argument("--status", action="store_true", help="Mostrar stats do índice")
    parser.add_argument("--rebuild", action="store_true", help="Recriar índice do zero")
    parser.add_argument("--build-fts", action="store_true", help="Criar/recriar índice FTS na tabela existente")
    args = parser.parse_args()

    if args.status:
        status()
    elif getattr(args, "build_fts", False):
        build_fts()
    elif args.query:
        filters = {}
        if args.filter_obra:
            filters["obra"] = args.filter_obra
        if args.filter_classe:
            filters["classe"] = args.filter_classe
        query(args.query, n_results=args.top, filters=filters or None, hybrid=args.hybrid)
    else:
        ingest(rebuild=args.rebuild)
