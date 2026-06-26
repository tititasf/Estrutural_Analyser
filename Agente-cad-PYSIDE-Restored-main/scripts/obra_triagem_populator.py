#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obra_triagem_populator.py — Popula SQLite obra_triagem com sugestões do RAG.

Lê obra_dxf_inventory (LanceDB) para a obra e grava sugestões na tabela
SQLite obra_triagem, mapeando classified_type → categoria da Fase 2.

Mapeamento de categorias (compatível com project_documents.category):
  bruto      → "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)"
  detalhe    → "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)"
  rev_eng    → "Projetos Finais Para Engenharia Reversa (suporte a dwg e dxf)"
  desconhecido → não adiciona

Regras de auto-aprovação:
  confidence >= 0.85 → status='pending', auto_approve=True (aprovado por threshold)
  0.60 <= conf < 0.85 → status='pending' (revisar manualmente)
  conf < 0.60        → status='review_required'

Uso:
  python obra_triagem_populator.py --obra "Obra_TREINO_1"
  python obra_triagem_populator.py --obra "Obra_TREINO_1" --reset
"""

from __future__ import annotations

import argparse
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
    ensure_obra_triagem_table,
    upsert_triagem,
    get_obra_db,
)

# Mapeamento classified_type → categoria canônica da Fase 2
CATEGORY_MAP = {
    "bruto":   "Estruturais dos Pavimentos, Estado Bruto (.DWG/.DXF)",
    "detalhe": "Detalhes Estruturais (.DWG/.PDF/.DXF/.MD)",
    "rev_eng": "Projetos Finais Para Engenharia Reversa (suporte a dwg e dxf)",
}

# Ordenação sugerida por subtipo (para facilitar triagem visual)
SUBTYPE_ORDER = {
    "PL": 1, "LV": 2, "FV": 3, "LJ": 4, "GF": 5, "GD": 6,
    "pavimento_tipo": 10, "pavimento_cobertura": 11,
    "pavimento_terreo": 12, "pavimento_subsolo": 13,
    "pavimento_desconhecido": 20,
    "detalhe_estrutural": 30,
    "stog_finalizado": 40, "desconhecido": 99,
}


def populate_triagem(obra_name: str, reset: bool = False) -> dict:
    """
    Lê obra_dxf_inventory e popula obra_triagem.

    Returns: {inserted: int, skipped: int, errors: list}
    """
    ensure_obra_triagem_table()

    try:
        db    = get_obra_db(obra_name)
        names = db.list_tables().tables if hasattr(db.list_tables(), "tables") else db.table_names()
        if "obra_dxf_inventory" not in names:
            return {"inserted": 0, "skipped": 0, "errors": ["obra_dxf_inventory não encontrado — rode dxf_classifier primeiro"]}
        table = db.open_table("obra_dxf_inventory")
        df    = table.to_pandas()
    except Exception as e:
        return {"inserted": 0, "skipped": 0, "errors": [str(e)]}

    if df.empty:
        return {"inserted": 0, "skipped": 0, "errors": []}

    # Filtrar apenas a obra solicitada (segurança)
    df = df[df["obra_name"] == obra_name]

    if reset:
        import sqlite3
        from scripts.obra_rag_utils import DB_SQLITE
        conn = sqlite3.connect(str(DB_SQLITE))
        conn.execute("DELETE FROM obra_triagem WHERE obra_name=?", (obra_name,))
        conn.commit()
        conn.close()

    now      = datetime.now().isoformat()
    rows     = []
    skipped  = 0
    errors   = []

    # Ordenar por subtipo para apresentação consistente na Fase 2
    df = df.sort_values(
        by=["classified_type", "classified_subtype", "dxf_name"],
        ignore_index=True,
    )

    for _, row in df.iterrows():
        c_type    = row.get("classified_type", "desconhecido")
        c_subtype = row.get("classified_subtype", "desconhecido")
        conf      = float(row.get("confidence", 0.0))

        category = CATEGORY_MAP.get(c_type)
        if not category:
            skipped += 1
            continue

        # Verificar se o arquivo ainda existe no disco (evita entradas stale)
        dxf_path_str = row.get("dxf_path", "")
        if dxf_path_str and not Path(dxf_path_str).exists():
            skipped += 1
            continue

        # Determinar status
        if conf >= 0.85:
            status = "pending"
            notes  = "auto_approve=true"
        elif conf >= 0.60:
            status = "pending"
            notes  = "revisar_manual"
        else:
            status = "review_required"
            notes  = f"baixa_confianca={conf:.2f}"

        order = SUBTYPE_ORDER.get(c_subtype, 50)

        # Usar informação de pavimento para refinar a nota
        pav = row.get("pavimento_inferred", "")
        if pav:
            notes += f" | pav={pav}"

        rows.append({
            "id":                 str(uuid.uuid4()),
            "obra_name":          obra_name,
            "file_path":          row.get("dxf_path", ""),
            "file_name":          row.get("dxf_name", ""),
            "file_ext":           Path(row.get("dxf_name", "")).suffix.lower(),
            "suggested_category": category,
            "suggested_order":    order,
            "confidence":         conf,
            "status":             status,
            "classifier":         row.get("classifier_method", ""),
            "notes":              notes,
            "created_at":         now,
        })

    if rows:
        try:
            upsert_triagem(rows)
        except Exception as e:
            errors.append(str(e))
            return {"inserted": 0, "skipped": skipped, "errors": errors}

    # Resumo por categoria e status
    by_cat: dict[str, dict] = {}
    for r in rows:
        cat = r["suggested_category"]
        if cat not in by_cat:
            by_cat[cat] = {"total": 0, "auto": 0, "review": 0}
        by_cat[cat]["total"] += 1
        if r["status"] == "pending" and "auto_approve=true" in r["notes"]:
            by_cat[cat]["auto"] += 1
        else:
            by_cat[cat]["review"] += 1

    print(f"\n  📋 obra_triagem populada para {obra_name}:")
    for cat, counts in by_cat.items():
        short = cat.split("(")[0].strip()
        print(f"     {short}: {counts['total']} total — {counts['auto']} auto | {counts['review']} revisar")

    return {"inserted": len(rows), "skipped": skipped, "errors": errors}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Popula obra_triagem com sugestões do RAG")
    ap.add_argument("--obra",  required=True, help="Nome da obra")
    ap.add_argument("--reset", action="store_true", help="Limpar sugestões anteriores da obra")
    args = ap.parse_args()

    print(f"📌 Populando triagem — {args.obra}")
    result = populate_triagem(args.obra, reset=args.reset)
    print(f"\n✅ {result['inserted']} inseridos, {result['skipped']} pulados")
    if result["errors"]:
        print(f"⚠ Erros:")
        for e in result["errors"]:
            print(f"  • {e}")
