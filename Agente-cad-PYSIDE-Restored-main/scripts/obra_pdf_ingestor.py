#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obra_pdf_ingestor.py — Indexa PDFs/MDs da Fase-1 de uma obra no RAG por-obra.

Varre:
  Fase-1_Ingestao/Documentos_Atas_de_Reunioes/**  (e aliases)

Para cada arquivo:
  PDF → PyMuPDF (texto digital) + pytesseract fallback (escaneado)
      → chunking por seção (detecta headers por font-size)
      → fallback sliding window 512t / overlap 64t
  MD  → chunking por seção markdown (## headers)

Output: chunks indexados em LanceDB obra_rag_db/obra_docs

Uso:
  python obra_pdf_ingestor.py --obra "Obra_TREINO_1"
  python obra_pdf_ingestor.py --obra "Obra_TREINO_1" --force
"""

from __future__ import annotations

import argparse
import json
import re
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import uuid
from datetime import datetime
from pathlib import Path

# Adiciona o projeto ao path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.obra_rag_utils import (
    DADOS_OBRAS_ROOT,
    embed_texts,
    detect_embed_dim,
    get_obra_db,
    get_or_create_obra_docs_table,
)

# Pastas de documentos (todos os aliases conhecidos)
DOC_FOLDERS = [
    "Documentos_Atas_de_Reunioes",
    "Documentos_e_Atas_de_Reunioes_PDF_MD",
    "Documentos_e_Atas_de_ReunioesPDF_MD",
    "Documentos_e_Atas_de_Reunioes",
]

MAX_CHUNK_TOKENS = 512
OVERLAP_TOKENS   = 64
MIN_CHUNK_CHARS  = 80   # ignorar chunks muito curtos


# ── Chunking MD ───────────────────────────────────────────────────────────────

def _chunk_markdown(text: str, file_name: str) -> list[dict]:
    """Divide markdown por seções (## headers). Fallback: parágrafos."""
    sections = re.split(r"\n(?=#{1,3} )", text.strip())
    chunks = []
    for i, sec in enumerate(sections):
        sec = sec.strip()
        if len(sec) < MIN_CHUNK_CHARS:
            continue
        # Extrair título da seção se houver
        first_line = sec.split("\n")[0].strip()
        title = re.sub(r"^#+\s*", "", first_line) if first_line.startswith("#") else ""
        chunks.append({
            "text":          sec,
            "section_title": title,
            "chunk_index":   i,
            "chunk_type":    "section",
            "page_num":      0,
            "file_type":     "md",
        })
    if not chunks:
        # fallback: parágrafos
        for i, para in enumerate(text.split("\n\n")):
            para = para.strip()
            if len(para) >= MIN_CHUNK_CHARS:
                chunks.append({
                    "text": para, "section_title": "", "chunk_index": i,
                    "chunk_type": "paragraph", "page_num": 0, "file_type": "md",
                })
    return chunks


# ── Chunking PDF ──────────────────────────────────────────────────────────────

def _sliding_window(text: str, page_num: int, file_type: str) -> list[dict]:
    """Divide texto em janelas de MAX_CHUNK_TOKENS palavras com overlap."""
    words = text.split()
    chunks = []
    i = 0
    idx = 0
    while i < len(words):
        window = words[i:i + MAX_CHUNK_TOKENS]
        chunk_text = " ".join(window).strip()
        if len(chunk_text) >= MIN_CHUNK_CHARS:
            chunks.append({
                "text": chunk_text, "section_title": "", "chunk_index": idx,
                "chunk_type": "sliding", "page_num": page_num, "file_type": file_type,
            })
        i += MAX_CHUNK_TOKENS - OVERLAP_TOKENS
        idx += 1
    return chunks


def _extract_pdf_text_fitz(pdf_path: Path) -> list[dict]:
    """Extrai texto de PDF com PyMuPDF, chunking por seção via font-size."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return []

    chunks = []
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        print(f"  [WARN] fitz não conseguiu abrir {pdf_path.name}: {e}")
        return []

    for page_num, page in enumerate(doc):
        try:
            blocks = page.get_text("dict")["blocks"]
        except Exception:
            continue

        # Detectar tamanho médio de fonte para identificar headers
        all_sizes = []
        for b in blocks:
            if b.get("type") != 0:  # somente texto
                continue
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        all_sizes.append(span.get("size", 12))
        avg_size = (sum(all_sizes) / len(all_sizes)) if all_sizes else 12
        header_threshold = avg_size * 1.2

        current_section = ""
        current_title   = ""
        section_chunks  = []

        for b in blocks:
            if b.get("type") != 0:
                continue
            block_text = ""
            is_header  = False
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    t = span.get("text", "").strip()
                    if not t:
                        continue
                    if span.get("size", 12) >= header_threshold and len(t) < 120:
                        is_header = True
                    block_text += t + " "

            block_text = block_text.strip()
            if not block_text:
                continue

            if is_header and len(current_section) >= MIN_CHUNK_CHARS:
                section_chunks.append({
                    "text": current_section.strip(), "section_title": current_title,
                    "chunk_type": "section", "page_num": page_num + 1, "file_type": "pdf",
                })
                current_section = ""
                current_title   = block_text if is_header else ""

            if is_header:
                current_title = block_text
            else:
                current_section += block_text + " "

        # último bloco da página
        if len(current_section.strip()) >= MIN_CHUNK_CHARS:
            section_chunks.append({
                "text": current_section.strip(), "section_title": current_title,
                "chunk_type": "section", "page_num": page_num + 1, "file_type": "pdf",
            })

        # Se não gerou chunks por seção → sliding window
        if not section_chunks:
            page_text = page.get_text("text").strip()
            if page_text:
                section_chunks = _sliding_window(page_text, page_num + 1, "pdf")

        for i, c in enumerate(section_chunks):
            c["chunk_index"] = len(chunks) + i
        chunks.extend(section_chunks)

    doc.close()
    return chunks


def _extract_pdf_ocr(pdf_path: Path) -> list[dict]:
    """Fallback OCR com pytesseract para PDFs escaneados."""
    try:
        import fitz
        import pytesseract
        from PIL import Image
        import io
    except ImportError as e:
        print(f"  [WARN] OCR não disponível ({e}) — pulando {pdf_path.name}")
        return []

    chunks = []
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return []

    for page_num, page in enumerate(doc):
        try:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text = pytesseract.image_to_string(img, lang="por")
        except Exception as e:
            print(f"  [WARN] OCR página {page_num+1}: {e}")
            continue
        if text.strip():
            chunks.extend(_sliding_window(text, page_num + 1, "pdf_ocr"))

    doc.close()
    # renumerar
    for i, c in enumerate(chunks):
        c["chunk_index"] = i
    return chunks


def _process_pdf(pdf_path: Path) -> list[dict]:
    """Extrai chunks de PDF — digital primeiro, OCR como fallback."""
    chunks = _extract_pdf_text_fitz(pdf_path)
    # Se extraiu < 3 chars por chunk em média → provavelmente escaneado
    if chunks:
        avg_len = sum(len(c["text"]) for c in chunks) / len(chunks)
        if avg_len < 50:
            print(f"  [INFO] {pdf_path.name} parece escaneado (avg={avg_len:.0f}c) — tentando OCR")
            ocr_chunks = _extract_pdf_ocr(pdf_path)
            if ocr_chunks:
                return ocr_chunks
    elif not chunks:
        print(f"  [INFO] {pdf_path.name} sem texto digital — tentando OCR")
        return _extract_pdf_ocr(pdf_path)
    return chunks


# ── Ingestão ──────────────────────────────────────────────────────────────────

def ingest_obra_docs(obra_name: str, force: bool = False, progress_cb=None) -> dict:
    """
    Indexa todos os PDFs/MDs da obra no LanceDB por-obra.

    Returns: {indexed: int, skipped: int, errors: list}
    """
    obra_path = DADOS_OBRAS_ROOT / obra_name
    if not obra_path.is_dir():
        return {"indexed": 0, "skipped": 0, "errors": [f"Obra não encontrada: {obra_path}"]}

    # Encontrar pasta de documentos
    fase1 = obra_path / "Fase-1_Ingestao"
    doc_roots = []
    if fase1.is_dir():
        for folder in DOC_FOLDERS:
            p = fase1 / folder
            if p.is_dir():
                doc_roots.append(p)
    # Fallback: busca recursiva pela obra por qualquer pasta com "Reunioes" ou "Documentos"
    if not doc_roots:
        for d in obra_path.rglob("*"):
            if d.is_dir() and any(k in d.name for k in ["Reunioes", "Documentos", "Atas"]):
                doc_roots.append(d)

    if not doc_roots:
        print(f"  [INFO] Nenhuma pasta de documentos encontrada para {obra_name}")
        return {"indexed": 0, "skipped": 0, "errors": []}

    # Coletar arquivos
    files: list[Path] = []
    for root in doc_roots:
        for ext in ["*.pdf", "*.PDF", "*.md", "*.MD"]:
            files.extend(root.rglob(ext))
    files = sorted(set(files))

    if not files:
        return {"indexed": 0, "skipped": 0, "errors": []}

    embed_dim = detect_embed_dim()
    db    = get_obra_db(obra_name)
    table = get_or_create_obra_docs_table(db, embed_dim)

    # Verificar quais já estão indexados
    already = set()
    if not force:
        try:
            existing = table.to_pandas()
            already = set(existing["file_name"].tolist())
        except Exception:
            pass

    indexed = 0
    skipped = 0
    errors  = []
    now     = datetime.now().isoformat()

    for fi, fpath in enumerate(files):
        if progress_cb:
            progress_cb(fi, len(files), fpath.name)

        if fpath.name in already and not force:
            skipped += 1
            continue

        print(f"  [{fi+1}/{len(files)}] {fpath.name}")

        try:
            if fpath.suffix.lower() == ".md":
                text = fpath.read_text(encoding="utf-8", errors="replace")
                chunks = _chunk_markdown(text, fpath.name)
            else:
                chunks = _process_pdf(fpath)
        except Exception as e:
            errors.append(f"{fpath.name}: {e}")
            continue

        if not chunks:
            print(f"    [SKIP] Sem chunks gerados")
            skipped += 1
            continue

        texts = [c["text"] for c in chunks]
        vecs  = embed_texts(texts)

        rows = []
        for c, v in zip(chunks, vecs):
            rows.append({
                "vector":        v.tolist(),
                "text":          c["text"],
                "obra_name":     obra_name,
                "file_name":     fpath.name,
                "file_type":     c["file_type"],
                "page_num":      c["page_num"],
                "section_title": c.get("section_title", ""),
                "chunk_index":   c["chunk_index"],
                "chunk_type":    c["chunk_type"],
                "created_at":    now,
            })

        try:
            table.add(rows)
            indexed += len(rows)
            print(f"    ✅ {len(rows)} chunks indexados")
        except Exception as e:
            errors.append(f"{fpath.name} (add): {e}")

    return {"indexed": indexed, "skipped": skipped, "errors": errors}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Indexa PDFs/MDs da obra no RAG por-obra")
    ap.add_argument("--obra", required=True, help="Nome da obra (ex: Obra_TREINO_1)")
    ap.add_argument("--force", action="store_true", help="Re-indexar arquivos já indexados")
    args = ap.parse_args()

    print(f"📄 Ingestão de documentos — {args.obra}")
    result = ingest_obra_docs(args.obra, force=args.force)
    print(f"\n✅ Concluído: {result['indexed']} chunks indexados, {result['skipped']} pulados")
    if result["errors"]:
        print(f"⚠ Erros ({len(result['errors'])}):")
        for e in result["errors"]:
            print(f"  • {e}")
