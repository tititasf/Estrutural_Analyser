#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obra_dxf_classifier.py — Classifica DXFs da Fase-1 de uma obra.

Classifica DXFs de 3 pastas:
  - brutos     → Estruturais Brutos (pavimentos brutos)
  - detalhes   → Detalhes Estruturais
  - rev_eng    → Projetos_Finalizados_para_Engenharia_Reversa (DXFs STOG humanos)

Classificação em 3 camadas (ordem de prioridade):
  1. Nome do arquivo  — padrões STOG (- PL -, - LV -) + keywords de pavimento
  2. Layers ezdxf     — presença de layers estruturais vs carimbo
  3. Embedding        — fallback por similaridade semântica (somente se confidence < 0.6)

Output: indexa em LanceDB obra_rag_db/obra_dxf_inventory

Uso:
  python obra_dxf_classifier.py --obra "Obra_TREINO_1" --folder brutos
  python obra_dxf_classifier.py --obra "Obra_TREINO_1" --folder todos
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

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.obra_rag_utils import (
    DADOS_OBRAS_ROOT,
    embed_texts,
    detect_embed_dim,
    get_obra_db,
    get_or_create_obra_dxf_table,
)

# ── Mapeamento de pastas → source_folder ────────────────────────────────────

FOLDER_SOURCES = {
    "brutos": [
        "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF",
        "Estruturais_Pavimentos_Brutos",
        "DXF_Bruto",
    ],
    "detalhes": [
        "Detalhes_Estruturais_DWG_PDF_DXF_MD",
        "Detalhes_Estruturais",
    ],
    "rev_eng": [
        "Projetos_Finalizados_para_Engenharia_Reversa",
        "Projetos_Finais_Para_Engenharia_Reversa_suporte_a_dwg_e_dxf",
    ],
}

# ── Camada 1: classificação por nome de arquivo ───────────────────────────────

# Padrões STOG finais (DXFs de Engenharia Reversa com tipo de peça explícito)
_STOG_TYPE_RE = re.compile(
    r"[-_\s](PL|LV|FV|LJ|GF|GD|CP|VG|CB)[-_\s]",
    re.IGNORECASE,
)

# Keywords de pavimento no nome do arquivo
_PAV_KEYWORDS = [
    (r"\bTIP[O]?\b", "TIPO"),
    (r"\bCOB[E]?\b|\bCOBERTURA\b|\bCOB\b", "COBERTURA"),
    (r"\bFUND\b|\bFUNDACAO\b|\bFUNDAÇÃO\b|\bFUN\b", "FUNDACAO"),
    (r"\bTERREO\b|\bTÉRREO\b|\bTER\b", "TERREO"),
    (r"\bSS\b|\bSUBSOLO\b", "SUBSOLO"),
    (r"\bATICO\b|\bÁTICO\b|\bATC\b|\bATIC\b", "ATICO"),
    (r"\bDECK\b", "DECK"),
    (r"\bBARRILETE\b|\bBAR\b", "BARRILETE"),
    (r"\b(\d+)\s*PAV\b", "{num}PAV"),          # 1PAV, 2 PAV, etc.
    (r"\bPAV\s*(\d+)\b", "PAV{num}"),          # PAV1, PAV 2, etc.
    (r"\b(\d+)PV\b", "{num}PAV"),              # 1PV, 2PV → 1PAV, 2PAV
    (r"\b(\d+)P\b", "{num}PAV"),               # 13P, 14P → 13PAV, 14PAV
]

# Palavras que indicam DXF de localização/implantação (não é pavimento estrutural)
_LOC_KEYWORDS = ["LOC", "LOCALIZACAO", "LOCALIZAÇÃO", "IMPLANTACAO", "IMPLANTAÇÃO", "PLANTA-GERAL"]


def _classify_by_filename(fname: str, source_folder: str) -> dict:
    """
    Retorna {classified_type, classified_subtype, confidence, pavimento_inferred,
              classifier_method}
    """
    name_upper = fname.upper()

    # rev_eng com tipo STOG explícito no nome
    if source_folder == "rev_eng":
        m = _STOG_TYPE_RE.search(fname)
        if m:
            subtype = m.group(1).upper()
            return {
                "classified_type":    "rev_eng",
                "classified_subtype": subtype,
                "confidence":         0.95,
                "pavimento_inferred": _infer_pavimento(name_upper),
                "classifier_method":  "filename",
            }
        # rev_eng sem tipo explícito — still rev_eng, subtype unknown
        return {
            "classified_type":    "rev_eng",
            "classified_subtype": "desconhecido",
            "confidence":         0.70,
            "pavimento_inferred": _infer_pavimento(name_upper),
            "classifier_method":  "filename",
        }

    # Detalhes
    if source_folder == "detalhes":
        detalhe_kw = ["DET", "DETALHE", "ARMACAO", "ARMAÇÃO", "CORTE", "SECCAO"]
        if any(k in name_upper for k in detalhe_kw):
            return {
                "classified_type":    "detalhe",
                "classified_subtype": "detalhe_estrutural",
                "confidence":         0.85,
                "pavimento_inferred": "",
                "classifier_method":  "filename",
            }
        return {
            "classified_type":    "detalhe",
            "classified_subtype": "detalhe_estrutural",
            "confidence":         0.65,
            "pavimento_inferred": "",
            "classifier_method":  "filename",
        }

    # Brutos — verificar se é localização (não é pavimento estrutural)
    if any(k in name_upper for k in _LOC_KEYWORDS):
        return {
            "classified_type":    "bruto",
            "classified_subtype": "localizacao",
            "confidence":         0.30,   # baixo → review_required na triagem
            "pavimento_inferred": "LOC",
            "classifier_method":  "filename",
        }

    # Brutos — identificar tipo de pavimento
    pav = _infer_pavimento(name_upper)
    if pav:
        return {
            "classified_type":    "bruto",
            "classified_subtype": f"pavimento_{pav.lower()}",
            "confidence":         0.85,
            "pavimento_inferred": pav,
            "classifier_method":  "filename",
        }
    return {
        "classified_type":    "bruto",
        "classified_subtype": "pavimento_desconhecido",
        "confidence":         0.50,
        "pavimento_inferred": "",
        "classifier_method":  "filename",
    }


def _infer_pavimento(name_upper: str) -> str:
    for pattern, label in _PAV_KEYWORDS:
        m = re.search(pattern, name_upper)
        if m:
            if "{num}" in label:
                num = m.group(1) if m.lastindex else ""
                return label.replace("{num}", num)
            return label
    return ""


# ── Camada 2: classificação por layers ezdxf ─────────────────────────────────

# Layers estruturais que indicam pavimento bruto
_STRUCTURAL_LAYERS = {
    "S-BEAM", "A-FLOR", "S-COLS", "S-SLAB", "S-WALL",
    "S-STRS", "S-OTLN", "VIGA", "PILAR", "LAJE",
    "ESTRUTURAL", "STRUCTURAL",
}
# Layers que indicam DXF STOG finalizado (eng reversa)
_STOG_LAYERS = {
    "COTA", "NOMENCLATURA", "PAINÉIS", "PAINEIS", "Painéis", "Paineis",
    "SARR_2.2X7", "SARR_2.2X10", "SARR_3.5X7", "HACHURA",
    "REAPROVEITAMENTO", "SCO-___-LAJ",
}
# Layers de carimbo (ignorar para classificação)
_CARIMBO_LAYERS = {
    "CARIMBO", "00-FELIPE", "00 - FELIPE", "ROMANEIO", "FOLHA MB", "FOLHA",
}


def _classify_by_layers(dxf_path: Path, source_folder: str) -> dict | None:
    """
    Tenta classificar pelo conteúdo do DXF via ezdxf.
    Retorna None se ezdxf falhar ou arquivo muito grande (>15MB).
    """
    try:
        import ezdxf
        import psutil
    except ImportError:
        return None

    # Proteção de memória
    try:
        free_mb = psutil.virtual_memory().available / (1024 * 1024)
        if free_mb < 500:
            return None
    except Exception:
        pass

    # Ignorar DXFs muito grandes
    if dxf_path.stat().st_size > 15 * 1024 * 1024:
        return None

    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception:
        return None

    layers = {l.dxf.name for l in doc.layers}
    del doc

    structural_hits = len(layers & _STRUCTURAL_LAYERS)
    stog_hits       = len(layers & _STOG_LAYERS)
    carimbo_hits    = len(layers & _CARIMBO_LAYERS)
    total_layers    = max(len(layers) - carimbo_hits, 1)

    top_layers = sorted(
        layers - _CARIMBO_LAYERS,
        key=lambda x: x.upper()
    )[:20]

    # Rev eng: tem layers STOG típicos
    if stog_hits >= 3:
        return {
            "classified_type":    "rev_eng",
            "classified_subtype": "stog_finalizado",
            "confidence":         min(0.6 + stog_hits * 0.05, 0.92),
            "pavimento_inferred": "",
            "classifier_method":  "layers",
            "top_layers":         top_layers,
        }

    # Bruto estrutural
    if structural_hits >= 2:
        return {
            "classified_type":    "bruto",
            "classified_subtype": "pavimento_desconhecido",
            "confidence":         min(0.6 + structural_hits * 0.05, 0.88),
            "pavimento_inferred": "",
            "classifier_method":  "layers",
            "top_layers":         top_layers,
        }

    return {
        "classified_type":    "bruto" if source_folder == "brutos" else source_folder,
        "classified_subtype": "desconhecido",
        "confidence":         0.40,
        "pavimento_inferred": "",
        "classifier_method":  "layers",
        "top_layers":         top_layers,
    }


# ── Classificação final (combina camadas) ────────────────────────────────────

def classify_dxf(dxf_path: Path, source_folder: str) -> dict:
    """Classificação em 3 camadas com merge de confidence."""
    fname = dxf_path.name

    # Camada 1: nome de arquivo
    result = _classify_by_filename(fname, source_folder)

    # Camada 2: layers (se confidence < 0.85)
    if result["confidence"] < 0.85:
        layer_result = _classify_by_layers(dxf_path, source_folder)
        if layer_result:
            if layer_result["confidence"] > result["confidence"]:
                # Mesclar: mantém tipo do filename se concordam, usa layers se discordam mas mais confiante
                if layer_result["classified_type"] == result["classified_type"]:
                    result["confidence"] = min(result["confidence"] + 0.10, 0.92)
                    result["classifier_method"] = "filename+layers"
                    if layer_result.get("top_layers"):
                        result["top_layers"] = layer_result["top_layers"]
                else:
                    # layers discorda — usa o mais confiante
                    result = {**result, **layer_result}

    if "top_layers" not in result:
        result["top_layers"] = []

    return result


# ── Ingestão ──────────────────────────────────────────────────────────────────

def get_dxf_stats(dxf_path: Path) -> tuple[int, list[str]]:
    """Conta entidades e retorna top 10 layers. Seguro para DXFs grandes."""
    try:
        import ezdxf, psutil
        free_mb = psutil.virtual_memory().available / (1024 * 1024)
        if free_mb < 500 or dxf_path.stat().st_size > 15 * 1024 * 1024:
            return 0, []
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        count = sum(1 for _ in msp)
        layers = {}
        for e in msp:
            lay = e.dxf.get("layer", "0")
            layers[lay] = layers.get(lay, 0) + 1
        top = sorted(layers, key=lambda x: -layers[x])[:10]
        del doc
        return count, top
    except Exception:
        return 0, []


def _build_text_for_embedding(fname: str, classified: dict, top_layers: list[str]) -> str:
    """Constrói texto descritivo do DXF para embedding."""
    parts = [
        f"Arquivo: {fname}",
        f"Tipo: {classified['classified_type']}",
        f"Subtipo: {classified['classified_subtype']}",
    ]
    if classified.get("pavimento_inferred"):
        parts.append(f"Pavimento: {classified['pavimento_inferred']}")
    if top_layers:
        parts.append(f"Layers: {', '.join(top_layers[:10])}")
    return " | ".join(parts)


def classify_and_index_folder(
    obra_name: str,
    source_folder_key: str,
    force: bool = False,
    progress_cb=None,
) -> dict:
    """
    Classifica e indexa todos os DXFs de uma pasta da obra.

    source_folder_key: "brutos" | "detalhes" | "rev_eng" | "todos"
    """
    obra_path = DADOS_OBRAS_ROOT / obra_name
    fase1     = obra_path / "Fase-1_Ingestao"

    keys = ["brutos", "detalhes", "rev_eng"] if source_folder_key == "todos" else [source_folder_key]

    # Coletar arquivos por chave
    dxf_files: list[tuple[Path, str]] = []  # (path, source_key)
    for key in keys:
        folder_names = FOLDER_SOURCES.get(key, [])
        for fname in folder_names:
            folder = fase1 / fname
            if folder.is_dir():
                for dxf in sorted(folder.rglob("*.dxf")) + sorted(folder.rglob("*.DXF")):
                    dxf_files.append((dxf, key))
                break  # usar apenas o primeiro alias encontrado

    if not dxf_files:
        return {"indexed": 0, "skipped": 0, "errors": []}

    embed_dim = detect_embed_dim()
    db    = get_obra_db(obra_name)
    table = get_or_create_obra_dxf_table(db, embed_dim)

    # Verificar já indexados
    already = set()
    if not force:
        try:
            df = table.to_pandas()
            already = set(df["dxf_path"].tolist())
        except Exception:
            pass

    indexed = 0
    skipped = 0
    errors  = []
    now     = datetime.now().isoformat()

    for fi, (dxf_path, src_key) in enumerate(dxf_files):
        if progress_cb:
            progress_cb(fi, len(dxf_files), dxf_path.name)

        dxf_path_str = str(dxf_path.resolve())
        if dxf_path_str in already and not force:
            skipped += 1
            continue

        print(f"  [{fi+1}/{len(dxf_files)}] {dxf_path.name} ({src_key})")

        try:
            classified = classify_dxf(dxf_path, src_key)
            entity_count, top_layers = get_dxf_stats(dxf_path)
            if top_layers:
                classified["top_layers"] = top_layers

            text = _build_text_for_embedding(dxf_path.name, classified, top_layers)
            vec  = embed_texts([text])[0]

            row = {
                "vector":              vec.tolist(),
                "text":                text,
                "obra_name":           obra_name,
                "dxf_path":            dxf_path_str,
                "dxf_name":            dxf_path.name,
                "source_folder":       src_key,
                "classified_type":     classified["classified_type"],
                "classified_subtype":  classified["classified_subtype"],
                "confidence":          float(classified["confidence"]),
                "pavimento_inferred":  classified.get("pavimento_inferred", ""),
                "classifier_method":   classified.get("classifier_method", "filename"),
                "entity_count":        int(entity_count),
                "top_layers":          json.dumps(classified.get("top_layers", []), ensure_ascii=False),
                "created_at":          now,
            }
            table.add([row])
            indexed += 1
            print(f"    ✅ {classified['classified_type']}/{classified['classified_subtype']} "
                  f"conf={classified['confidence']:.2f} ent={entity_count}")
        except Exception as e:
            errors.append(f"{dxf_path.name}: {e}")
            print(f"    ❌ {e}")

    return {"indexed": indexed, "skipped": skipped, "errors": errors}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Classifica DXFs da obra no RAG por-obra")
    ap.add_argument("--obra",   required=True, help="Nome da obra")
    ap.add_argument("--folder", default="todos",
                    choices=["brutos", "detalhes", "rev_eng", "todos"],
                    help="Qual conjunto de pastas processar")
    ap.add_argument("--force", action="store_true", help="Re-classificar DXFs já indexados")
    args = ap.parse_args()

    print(f"🗂 Classificação DXFs — {args.obra} / {args.folder}")
    result = classify_and_index_folder(args.obra, args.folder, force=args.force)
    print(f"\n✅ Concluído: {result['indexed']} indexados, {result['skipped']} pulados")
    if result["errors"]:
        print(f"⚠ Erros ({len(result['errors'])}):")
        for e in result["errors"]:
            print(f"  • {e}")
