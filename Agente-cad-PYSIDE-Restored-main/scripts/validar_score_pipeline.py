#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validar_score_pipeline.py — Compara fichas extraídas pelo pipeline com ground truth.

Métricas calculadas:
  - count_accuracy: % de elementos corretos (IDs encontrados no GT)
  - hallucination_rate: % de elementos no pipeline que NÃO existem no GT
  - miss_rate: % de elementos no GT que o pipeline NÃO encontrou
  - score_final: (1 - hallucination_rate) * 0.5 + (1 - miss_rate) * 0.5

CLI:
  python scripts/validar_score_pipeline.py \\
    --obra ../DADOS-OBRAS/Obra_TREINO_21 \\
    --elemento pilares
"""

import argparse
import json
import os
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_ids(fichas: dict) -> set:
    """Extrai IDs de elementos (ignora _meta)."""
    return {k for k in fichas.keys() if not k.startswith('_')}


def validate(pipeline_ids: set, gt_ids: set) -> dict:
    """
    Calcula métricas de validação.
    """
    if not gt_ids:
        return {"erro": "Ground truth vazio — execute engenharia_reversa_dxf.py primeiro"}

    # IDs no pipeline mas NÃO no GT = alucinações
    hallucinated = pipeline_ids - gt_ids
    # IDs no GT mas NÃO no pipeline = faltando
    missed = gt_ids - pipeline_ids
    # IDs em ambos = corretos
    correct = pipeline_ids & gt_ids

    hallucination_rate = len(hallucinated) / len(pipeline_ids) if pipeline_ids else 1.0
    miss_rate = len(missed) / len(gt_ids)
    count_accuracy = len(correct) / len(gt_ids)
    score = (1 - hallucination_rate) * 0.5 + (1 - miss_rate) * 0.5

    return {
        "pipeline_count": len(pipeline_ids),
        "gt_count": len(gt_ids),
        "correct": len(correct),
        "hallucinated": sorted(hallucinated),
        "missed": sorted(missed),
        "hallucination_rate": round(hallucination_rate, 4),
        "miss_rate": round(miss_rate, 4),
        "count_accuracy": round(count_accuracy, 4),
        "score": round(score, 4),
        "score_percent": round(score * 100, 1),
        "aprovado": score >= 0.75,
    }


def run(obra_path: str, elemento: str) -> None:
    obra = Path(obra_path)
    fase3 = obra / "Fase-3_Interpretacao_Extracao"
    elem_map = {
        "pilares": ("Pilares/pilares.json", "Pilares/pilares_ground_truth.json"),
        "vigas": ("Vigas/vigas.json", "Vigas/vigas_ground_truth.json"),
        "lajes": ("Lajes/lajes.json", "Lajes/lajes_ground_truth.json"),
    }

    if elemento not in elem_map:
        print(f"[ERROR] Elemento deve ser: {list(elem_map.keys())}")
        sys.exit(1)

    pipeline_file, gt_file = elem_map[elemento]
    pipeline_path = fase3 / pipeline_file
    gt_path = fase3 / gt_file

    print(f"[INFO] === validar_score_pipeline.py | {elemento} ===")
    print(f"[INFO] Pipeline: {pipeline_path}")
    print(f"[INFO] GT:       {gt_path}")

    pipeline_data = load_json(pipeline_path)
    gt_data = load_json(gt_path)

    if not pipeline_data:
        print(f"[ERROR] Pipeline fichas não encontradas: {pipeline_path}")
        print(f"        Execute o pipeline Fase 3 primeiro")
        sys.exit(1)

    if not gt_data:
        print(f"[ERROR] Ground truth não encontrado: {gt_path}")
        print(f"        Execute: python scripts/engenharia_reversa_dxf.py --obra {obra_path} --pavimento '12 PAV'")
        sys.exit(1)

    pipeline_ids = extract_ids(pipeline_data)
    gt_ids = extract_ids(gt_data)

    result = validate(pipeline_ids, gt_ids)

    print(f"\n[RESULTADO] {elemento.upper()}")
    print(f"  Pipeline count:  {result['pipeline_count']}")
    print(f"  Ground truth:    {result['gt_count']}")
    print(f"  Corretos:        {result['correct']}")
    if result.get('hallucinated'):
        print(f"  Alucinados:      {result['hallucinated']}")
    if result.get('missed'):
        print(f"  Faltando:        {result['missed']}")
    print(f"\n  Hallucination:   {result['hallucination_rate']:.1%}")
    print(f"  Miss rate:       {result['miss_rate']:.1%}")
    print(f"  Count accuracy:  {result['count_accuracy']:.1%}")
    print(f"\n  SCORE:           {result['score_percent']:.1f}%")
    status = "APROVADO (>=75%)" if result['aprovado'] else "REPROVADO (meta: >= 75%)"
    print(f"  STATUS:          {status}")

    # Save result
    out_path = fase3 / f"validation_{elemento}.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n[INFO] Resultado salvo: {out_path}")


def main():
    parser = argparse.ArgumentParser(description='Valida score do pipeline contra ground truth')
    parser.add_argument('--obra', required=True, help='Path para o diretório da obra')
    parser.add_argument('--elemento', default='pilares',
                        choices=['pilares', 'vigas', 'lajes'],
                        help='Tipo de elemento a validar')
    args = parser.parse_args()
    run(args.obra, args.elemento)


if __name__ == '__main__':
    main()
