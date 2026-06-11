#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obra_rag_pipeline.py — Orquestrador do pipeline RAG semântico da Fase 1.

Executa em sequência:
  0–25%   obra_pdf_ingestor      PDFs/MDs → LanceDB obra_docs
  25–50%  obra_dxf_classifier    DXFs Brutos → obra_dxf_inventory
  50–65%  obra_dxf_classifier    DXFs Detalhes → obra_dxf_inventory
  65–80%  obra_dxf_classifier    DXFs Eng.Reversa → obra_dxf_inventory
  80–90%  obra_triagem_populator → SQLite obra_triagem
  90–100% obras_rag_consolidator → summary narrativo

Pode ser chamado:
  - CLI: python obra_rag_pipeline.py --obra "Obra_TREINO_1"
  - Import: run_pipeline(obra_name, progress_cb=callback)

progress_cb(pct: int, msg: str) → chamado a cada etapa
"""

from __future__ import annotations

import argparse
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import time
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def run_pipeline(
    obra_name: str,
    force: bool = False,
    progress_cb=None,
) -> dict:
    """
    Executa o pipeline RAG semântico completo para uma obra.

    progress_cb(pct: int, msg: str) — atualização de progresso (0-100)

    Returns: {
        status: "ok" | "error",
        doc_chunks:   int,
        dxf_indexed:  int,
        triagem_rows: int,
        errors: list[str],
        duration_s: float,
    }
    """

    def _cb(pct: int, msg: str):
        if progress_cb:
            progress_cb(pct, msg)
        else:
            print(f"  [{pct:3d}%] {msg}")

    t0     = time.time()
    errors = []

    # ── Etapa 1: PDFs/MDs ──────────────────────────────────────────────────
    _cb(0, "Indexando documentos (PDFs/MDs)...")
    try:
        from scripts.obra_pdf_ingestor import ingest_obra_docs

        def _pdf_progress(fi, total, fname):
            pct = 2 + int((fi / max(total, 1)) * 22)
            _cb(pct, f"PDF [{fi+1}/{total}] {fname}")

        pdf_result = ingest_obra_docs(obra_name, force=force, progress_cb=_pdf_progress)
        errors.extend(pdf_result.get("errors", []))
        doc_chunks = pdf_result.get("indexed", 0)
        _cb(25, f"✅ PDFs: {doc_chunks} chunks indexados")
    except Exception as e:
        errors.append(f"pdf_ingestor: {e}")
        doc_chunks = 0
        _cb(25, f"⚠ PDFs falhou: {e}")

    # ── Etapa 2: DXFs Brutos ───────────────────────────────────────────────
    _cb(26, "Classificando DXFs Brutos...")
    try:
        from scripts.obra_dxf_classifier import classify_and_index_folder

        def _dxf_progress(fi, total, fname):
            pct = 27 + int((fi / max(total, 1)) * 22)
            _cb(pct, f"DXF Bruto [{fi+1}/{total}] {fname}")

        br_result = classify_and_index_folder(obra_name, "brutos", force=force, progress_cb=_dxf_progress)
        errors.extend(br_result.get("errors", []))
        dxf_brutos = br_result.get("indexed", 0)
        _cb(50, f"✅ DXFs brutos: {dxf_brutos} classificados")
    except Exception as e:
        errors.append(f"dxf_classifier brutos: {e}")
        dxf_brutos = 0
        _cb(50, f"⚠ DXFs brutos falhou: {e}")

    # ── Etapa 3: DXFs Detalhes ────────────────────────────────────────────
    _cb(51, "Classificando DXFs Detalhes...")
    try:
        from scripts.obra_dxf_classifier import classify_and_index_folder

        def _det_progress(fi, total, fname):
            pct = 52 + int((fi / max(total, 1)) * 12)
            _cb(pct, f"DXF Detalhe [{fi+1}/{total}] {fname}")

        dt_result = classify_and_index_folder(obra_name, "detalhes", force=force, progress_cb=_det_progress)
        errors.extend(dt_result.get("errors", []))
        dxf_detalhes = dt_result.get("indexed", 0)
        _cb(65, f"✅ DXFs detalhes: {dxf_detalhes} classificados")
    except Exception as e:
        errors.append(f"dxf_classifier detalhes: {e}")
        dxf_detalhes = 0
        _cb(65, f"⚠ DXFs detalhes falhou: {e}")

    # ── Etapa 4: DXFs Eng. Reversa ────────────────────────────────────────
    _cb(66, "Classificando DXFs Engenharia Reversa...")
    try:
        from scripts.obra_dxf_classifier import classify_and_index_folder

        def _rev_progress(fi, total, fname):
            pct = 67 + int((fi / max(total, 1)) * 12)
            _cb(pct, f"DXF RevEng [{fi+1}/{total}] {fname}")

        re_result = classify_and_index_folder(obra_name, "rev_eng", force=force, progress_cb=_rev_progress)
        errors.extend(re_result.get("errors", []))
        dxf_reveng = re_result.get("indexed", 0)
        _cb(80, f"✅ DXFs eng.reversa: {dxf_reveng} classificados")
    except Exception as e:
        errors.append(f"dxf_classifier rev_eng: {e}")
        dxf_reveng = 0
        _cb(80, f"⚠ DXFs eng.reversa falhou: {e}")

    dxf_indexed = dxf_brutos + dxf_detalhes + dxf_reveng

    # ── Etapa 4b: Limpeza de entradas stale no LanceDB ───────────────────
    if force:
        try:
            from scripts.obra_rag_utils import get_obra_db
            import sqlite3 as _sqlite3

            # LanceDB: drop + recreate (única forma confiável de limpar)
            db = get_obra_db(obra_name)
            try:
                names = db.table_names()
            except Exception:
                names = []
            if "obra_dxf_inventory" in names:
                db.drop_table("obra_dxf_inventory")
                _cb(81, "🧹 LanceDB: obra_dxf_inventory dropada (será re-indexada)")
            if "obra_docs" in names:
                db.drop_table("obra_docs")
                _cb(81, "🧹 LanceDB: obra_docs dropada (será re-indexada)")

            # Limpeza triagem: deletar apenas pending/review_required (preservar approved)
            from scripts.obra_rag_utils import DB_SQLITE
            conn = _sqlite3.connect(str(DB_SQLITE))
            conn.execute(
                "DELETE FROM obra_triagem WHERE obra_name=? AND status IN ('pending','review_required')",
                (obra_name,)
            )
            conn.commit()
            conn.close()
            _cb(81, "🧹 Triagem: entradas pending/review limpas (aprovadas preservadas)")
        except Exception as e:
            errors.append(f"cleanup_stale: {e}")

    # ── Etapa 5: Triagem Populator ────────────────────────────────────────
    _cb(81, "Populando sugestões de triagem...")
    try:
        from scripts.obra_triagem_populator import populate_triagem
        tr_result    = populate_triagem(obra_name, reset=False)
        errors.extend(tr_result.get("errors", []))
        triagem_rows = tr_result.get("inserted", 0)
        _cb(90, f"✅ Triagem: {triagem_rows} sugestões gravadas")
    except Exception as e:
        errors.append(f"triagem_populator: {e}")
        triagem_rows = 0
        _cb(90, f"⚠ Triagem falhou: {e}")

    # ── Etapa 6: Summary ──────────────────────────────────────────────────
    _cb(91, "Gerando summary da obra...")
    try:
        _generate_obra_summary(obra_name, doc_chunks, dxf_indexed, triagem_rows)
        _cb(100, "✅ Pipeline concluído")
    except Exception as e:
        errors.append(f"summary: {e}")
        _cb(100, "✅ Pipeline concluído (summary falhou)")

    duration = time.time() - t0

    return {
        "status":       "ok" if not errors else "partial",
        "doc_chunks":   doc_chunks,
        "dxf_indexed":  dxf_indexed,
        "triagem_rows": triagem_rows,
        "errors":       errors,
        "duration_s":   round(duration, 1),
    }


def _generate_obra_summary(obra_name: str, doc_chunks: int, dxf_indexed: int, triagem_rows: int):
    """Indexa um chunk de summary narrativo da obra no RAG."""
    from scripts.obra_rag_utils import (
        embed_texts, detect_embed_dim, get_obra_db, get_or_create_obra_docs_table
    )
    from datetime import datetime

    summary_text = (
        f"Obra: {obra_name}. "
        f"Documentos indexados: {doc_chunks} chunks de PDFs/MDs. "
        f"DXFs classificados: {dxf_indexed} arquivos (brutos + detalhes + engenharia reversa). "
        f"Sugestões de triagem: {triagem_rows} items aguardando aprovação. "
        f"Pipeline RAG executado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}."
    )

    embed_dim = detect_embed_dim()
    db        = get_obra_db(obra_name)
    table     = get_or_create_obra_docs_table(db, embed_dim)
    vec       = embed_texts([summary_text])[0]

    table.add([{
        "vector":        vec.tolist(),
        "text":          summary_text,
        "obra_name":     obra_name,
        "file_name":     "__obra_summary__",
        "file_type":     "summary",
        "page_num":      0,
        "section_title": "Resumo da Obra",
        "chunk_index":   0,
        "chunk_type":    "summary",
        "created_at":    datetime.now().isoformat(),
    }])


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Pipeline RAG semântico da Fase 1")
    ap.add_argument("--obra",  required=True, help="Nome da obra")
    ap.add_argument("--force", action="store_true", help="Re-processar tudo")
    args = ap.parse_args()

    print(f"🚀 Pipeline RAG Semântico — {args.obra}")
    print("=" * 60)

    result = run_pipeline(args.obra, force=args.force)

    print("\n" + "=" * 60)
    print(f"STATUS:   {result['status'].upper()}")
    print(f"Docs:     {result['doc_chunks']} chunks")
    print(f"DXFs:     {result['dxf_indexed']} classificados")
    print(f"Triagem:  {result['triagem_rows']} sugestões")
    print(f"Tempo:    {result['duration_s']}s")
    if result["errors"]:
        print(f"\n⚠ Erros ({len(result['errors'])}):")
        for e in result["errors"]:
            print(f"  • {e}")
