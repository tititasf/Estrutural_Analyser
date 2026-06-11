#!/usr/bin/env python3
"""
rag_commons.py — Base compartilhada para todos os módulos RAG do CAD-ANALYZER.
Importar em: rag_plausibility.py, rag_validator.py, rag_anomaly_detector.py, etc.
"""
import sys, json
from pathlib import Path

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FAISS_DIR  = Path('D:/Agente-cad-PYSIDE/data/vectors/faiss')
MODEL_NAME = 'all-MiniLM-L6-v2'
EMBED_DIM  = 384

# ── SINGLETON MODEL (carrega 1 vez, reutiliza) ──────────────────────────────
_model = None

def load_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

# ── NORMALIZAÇÃO ─────────────────────────────────────────────────────────────

def normalize(vecs: np.ndarray) -> np.ndarray:
    """L2-normalize para cosine similarity com FAISS FlatIP."""
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return (vecs / norms).astype(np.float32)

# ── CARREGAMENTO DE ÍNDICE ───────────────────────────────────────────────────

_index_cache: dict = {}
_meta_cache: dict = {}

def load_index(tipo: str = None) -> tuple:
    """
    Carrega índice FAISS + metadados (com cache).
    tipo=None → índice geral 'estruturais'
    tipo='pilar'|'viga'|'laje' → índice específico
    tipo='semantica' → conhecimento semântico de interpretação de formas
    """
    PLURAL = {
        'pilar': 'pilares',
        'viga': 'vigas',
        'laje': 'lajes',
        'semantica': 'semantica_formas',
    }
    nome = PLURAL.get(tipo, 'estruturais') if tipo else 'estruturais'

    if nome not in _index_cache:
        idx_path  = FAISS_DIR / f'{nome}.index'
        meta_path = FAISS_DIR / f'{nome}_meta.json'

        if not idx_path.exists():
            raise FileNotFoundError(
                f'Índice {idx_path} não encontrado. '
                'Execute: python scripts/rag_ingestor.py --rebuild'
            )

        _index_cache[nome] = faiss.read_index(str(idx_path))
        with open(meta_path, encoding='utf-8') as f:
            _meta_cache[nome] = json.load(f)

    return _index_cache[nome], _meta_cache[nome]

# ── FORMATADORES DE TEXTO ────────────────────────────────────────────────────

def fmt_pilar(id_: str, data: dict, obra: str, pav: str) -> str:
    b    = data.get('b') or data.get('largura') or '?'
    h    = data.get('h') or data.get('comprimento') or '?'
    alt  = data.get('altura', '?')
    conf = data.get('confidence', '?')
    src  = data.get('source', '')
    faces = ' '.join(data.get('faces_encontradas', data.get('sides', [])))
    nota = data.get('nota', '')
    bh_src = data.get('bh_source', '')
    return (
        f"Pilar {id_}, Obra: {obra}, Pavimento: {pav}, "
        f"b={b}cm h={h}cm altura={alt}cm, "
        f"confidence={conf}, source={src}, bh_source={bh_src}, "
        f"faces=[{faces}], nota={nota}"
    )

def fmt_viga(id_: str, data: dict, obra: str, pav: str) -> str:
    b    = data.get('b', '?')
    h    = data.get('h', '?')
    comp = data.get('comprimento', '?')
    conf = data.get('confidence', '?')
    src  = data.get('source', '')
    sides = ' '.join(data.get('sides', data.get('sides_encontrados', [])))
    nota = data.get('nota', '')
    return (
        f"Viga {id_}, Obra: {obra}, Pavimento: {pav}, "
        f"b={b}cm h={h}cm comprimento={comp}cm, "
        f"confidence={conf}, source={src}, "
        f"sides=[{sides}], nota={nota}"
    )

def fmt_laje(id_: str, data: dict, obra: str, pav: str) -> str:
    comp = data.get('comprimento', '?')
    larg = data.get('largura', '?')
    area = data.get('area_cm2', '?')
    conf = data.get('confidence', '?')
    src  = data.get('source', '')
    modo = data.get('modo_selecionado', '')
    nota = data.get('nota', '')
    n_coords = len(data.get('coordenadas', data.get('outline_segs', [])))
    return (
        f"Laje {id_}, Obra: {obra}, Pavimento: {pav}, "
        f"comprimento={comp}cm largura={larg}cm area={area}cm2, "
        f"confidence={conf}, source={src}, modo={modo}, "
        f"n_vertices={n_coords}, nota={nota}"
    )

def fmt_element(id_: str, tipo: str, data: dict, obra: str, pav: str = '1_PAV') -> str:
    """Dispatcher de formatadores por tipo."""
    if tipo == 'pilar':
        return fmt_pilar(id_, data, obra, pav)
    elif tipo == 'viga':
        return fmt_viga(id_, data, obra, pav)
    elif tipo == 'laje':
        return fmt_laje(id_, data, obra, pav)
    return f"{tipo} {id_}, Obra: {obra}"

# ── QUERY SEMÂNTICA ──────────────────────────────────────────────────────────

def query(text: str, tipo: str = None, obra: str = None,
          k: int = 5, threshold: float = 0.20) -> list:
    """
    Busca semântica no corpus RAG.

    Args:
        text: Texto de consulta em linguagem natural ou estruturado
        tipo: 'pilar'|'viga'|'laje' ou None (índice geral)
        obra: Filtrar por obra específica
        k: Número de resultados
        threshold: Score mínimo de similaridade

    Returns:
        Lista de dicts: [{'score': float, 'meta': dict}, ...]
    """
    model = load_model()
    index, meta = load_index(tipo)

    vec = model.encode([text], show_progress_bar=False)
    vec = normalize(vec)

    k_search = min(k * 5 if obra else k, index.ntotal)
    scores, ids = index.search(vec, k_search)
    scores = scores[0]
    ids    = ids[0]

    results = []
    for score, fid in zip(scores, ids):
        if fid < 0 or score < threshold:
            continue

        # Para índice geral, encontrar meta por faiss_id
        if tipo is None:
            m = next((m for m in meta if m.get('faiss_id') == fid), None)
        else:
            # Para índice por tipo, posição = índice direto
            m = meta[fid] if 0 <= fid < len(meta) else None

        if m is None:
            continue
        if obra and m.get('obra') != obra:
            continue

        results.append({'score': float(score), 'meta': m})
        if len(results) >= k:
            break

    return results

# ── REGISTRY ─────────────────────────────────────────────────────────────────

def load_registry() -> dict:
    """Carrega REGISTRY.json com estatísticas de ingestão."""
    reg_path = FAISS_DIR / 'REGISTRY.json'
    if not reg_path.exists():
        return {}
    with open(reg_path, encoding='utf-8') as f:
        return json.load(f)

def get_obras_ingeridas() -> list:
    """Retorna lista de obras já ingeridas."""
    reg = load_registry()
    return [r['obra'] for r in reg.get('ingestoes', [])]

# ── UTILITÁRIOS ──────────────────────────────────────────────────────────────

def get_anomaly_score(text: str, tipo: str = None) -> float:
    """
    Score de anomalia 0.0-1.0.
    0.0 = completamente normal (identical to corpus)
    1.0 = completamente anômalo (sem similar)
    """
    resultados = query(text, tipo=tipo, k=1, threshold=0.0)
    if not resultados:
        return 1.0
    return 1.0 - resultados[0]['score']

def get_plausibility(text: str, tipo: str = None) -> dict:
    """
    Verifica plausibilidade de elemento vs corpus.
    Returns: {'score': float, 'acao': str, 'similares': list}
    """
    resultados = query(text, tipo=tipo, k=3, threshold=0.0)

    if not resultados:
        return {'score': 0.0, 'acao': 'REVISÃO OBRIGATÓRIA', 'similares': []}

    top = resultados[0]['score']

    if top >= 0.85:
        acao = 'ACEITAR'
    elif top >= 0.65:
        acao = 'ACEITAR COM AVISO'
    elif top >= 0.40:
        acao = 'REVISÃO RECOMENDADA'
    else:
        acao = 'REVISÃO OBRIGATÓRIA'

    return {
        'score': top,
        'acao': acao,
        'similares': resultados,
    }
