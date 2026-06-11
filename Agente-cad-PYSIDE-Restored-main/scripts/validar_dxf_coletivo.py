#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validar_dxf_coletivo.py — Valida DXFs coletivos gerados vs. IDs do ground truth.

Métricas:
  - count_match: N entidades no gerado >= N no GT
  - id_match: % dos IDs do GT presentes no gerado
  - hallucination: IDs no gerado que não existem no GT

Saída: Fase-6_Execucao_CAD/validation_coletivo.json

CLI:
  python scripts/validar_dxf_coletivo.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import ezdxf
except ImportError:
    print("[ERROR] ezdxf não encontrado. Instale: pip install ezdxf")
    sys.exit(1)


def extrair_ids_dxf(dxf_path: str, prefixo: str) -> set:
    """
    Extrai IDs de elementos (P{n}, V{n}, L{n}) de um DXF gerado.
    Busca em TEXT e MTEXT por padrão "{prefixo}{n}".
    """
    ids = set()
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        pattern = re.compile(rf'^{re.escape(prefixo)}(\d+[A-Z]?)', re.IGNORECASE)

        for e in msp:
            if e.dxftype() not in ('TEXT', 'MTEXT'):
                continue
            try:
                txt = e.plain_text() if e.dxftype() == 'MTEXT' else e.dxf.text or ''
            except AttributeError:
                txt = getattr(e.dxf, 'text', '') or ''
            txt = txt.strip().split('\n')[0]
            m = pattern.match(txt)
            if m:
                ids.add(f"{prefixo}{m.group(1).upper()}")
    except Exception as ex:
        print(f"  [WARN] Erro ao ler {dxf_path}: {ex}")
    return ids


def load_gt_ids(gt_path: str) -> set:
    """Carrega IDs do ground truth JSON. Filtra apenas IDs válidos (P*, V*, L* + dígito)."""
    import re as _re
    try:
        with open(gt_path, encoding='utf-8') as f:
            data = json.load(f)
        valid = {k for k in data.keys()
                 if not k.startswith('_') and _re.match(r'^[A-Za-z]\d', k)}
        return valid
    except Exception:
        return set()


def calcular_metricas(gerado_ids: set, gt_ids: set, tipo: str) -> dict:
    if not gt_ids:
        return {"erro": "GT vazio"}

    correct = gerado_ids & gt_ids
    hallucinated = gerado_ids - gt_ids
    missed = gt_ids - gerado_ids

    id_match = len(correct) / len(gt_ids) if gt_ids else 0.0
    hall_rate = len(hallucinated) / len(gerado_ids) if gerado_ids else 0.0
    count_match = len(gerado_ids) / len(gt_ids) if gt_ids else 0.0

    # Score = 60% id_match + 40% (1-hallucination)
    score = id_match * 0.60 + (1 - hall_rate) * 0.40

    return {
        "tipo": tipo,
        "gt_count": len(gt_ids),
        "gerado_count": len(gerado_ids),
        "correct": len(correct),
        "hallucinated": sorted(hallucinated),
        "missed": sorted(missed),
        "id_match": round(id_match, 4),
        "hallucination_rate": round(hall_rate, 4),
        "count_match": round(count_match, 4),
        "score": round(score, 4),
        "score_percent": round(score * 100, 1),
        "aprovado": score >= 0.90,
    }


def run(obra_path: str, pavimento: str) -> None:
    obra = Path(obra_path)
    fase3 = obra / "Fase-3_Interpretacao_Extracao"
    fase6 = obra / "Fase-6_Execucao_CAD"

    print(f"[INFO] === validar_dxf_coletivo.py | {obra.name} | {pavimento} ===")

    resultados = {}
    scores = []

    configs = [
        {
            "tipo": "pilares",
            "dxf": fase6 / "PL_gerado.dxf",
            "gt": fase3 / "Pilares" / "pilares_ground_truth.json",
            "prefixo": "P",
        },
        {
            "tipo": "vigas",
            "dxf": fase6 / "LV_gerado.dxf",
            # vigas.json usa os IDs extraídos do LV DXF (V101...) — mesma fonte do gerador.
            # vigas_ground_truth.json usa IDs do STOG planta (V301...) com dims nulas — incompatível.
            "gt": fase3 / "Vigas" / "vigas.json",
            "prefixo": "V",
        },
        {
            "tipo": "lajes",
            "dxf": fase6 / "LJ_gerado.dxf",
            # lajes.json usa IDs extraídos do LJ DXF (L101...) — mesma fonte do gerador.
            # lajes_ground_truth.json usa IDs do STOG planta (L301...) com dims nulas — incompatível.
            "gt": fase3 / "Lajes" / "lajes.json",
            "prefixo": "L",
        },
    ]

    for cfg in configs:
        tipo = cfg["tipo"]
        dxf_path = cfg["dxf"]
        gt_path = cfg["gt"]

        if not dxf_path.exists():
            print(f"  [SKIP] {tipo}: DXF coletivo não encontrado ({dxf_path.name})")
            resultados[tipo] = {"erro": f"{dxf_path.name} não encontrado"}
            continue

        if not gt_path.exists():
            print(f"  [SKIP] {tipo}: GT não encontrado ({gt_path.name})")
            resultados[tipo] = {"erro": f"{gt_path.name} não encontrado"}
            continue

        # GT marcado como ausente (LJ/LV DXF não existia na obra)
        try:
            _gt_check = json.loads(gt_path.read_text(encoding='utf-8'))
            if isinstance(_gt_check, dict) and _gt_check.get('_ausente'):
                print(f"  [SKIP] {tipo}: DXF fonte ausente na obra — peso excluído do score global")
                resultados[tipo] = {"erro": "DXF fonte ausente", "ausente": True}
                continue
        except Exception:
            pass

        print(f"\n  [{tipo.upper()}]")
        gerado_ids = extrair_ids_dxf(str(dxf_path), cfg["prefixo"])
        gt_ids = load_gt_ids(str(gt_path))

        metricas = calcular_metricas(gerado_ids, gt_ids, tipo)
        resultados[tipo] = metricas

        status = "APROVADO" if metricas.get("aprovado") else "REPROVADO"
        print(f"    GT: {metricas.get('gt_count')} | Gerado: {metricas.get('gerado_count')} | Corretos: {metricas.get('correct')}")
        print(f"    id_match: {metricas.get('id_match', 0)*100:.1f}% | hallucination: {metricas.get('hallucination_rate', 0)*100:.1f}%")
        print(f"    SCORE: {metricas.get('score_percent')}% — {status}")

        if metricas.get('missed'):
            print(f"    Missing: {metricas['missed'][:10]}")

        if metricas.get('score'):
            scores.append(metricas['score'])

    # Score global (ponderado: pilares 0.4, vigas 0.35, lajes 0.25)
    pesos = {'pilares': 0.4, 'vigas': 0.35, 'lajes': 0.25}
    score_global = 0.0
    peso_total = 0.0
    for tipo, peso in pesos.items():
        if tipo in resultados and 'score' in resultados[tipo]:
            score_global += resultados[tipo]['score'] * peso
            peso_total += peso
    if peso_total > 0:
        score_global /= peso_total

    print(f"\n[RESULTADO GLOBAL]")
    print(f"  Score global: {score_global*100:.1f}%")
    status_global = "APROVADO (>=90%)" if score_global >= 0.90 else "REPROVADO (meta: >=90%)"
    print(f"  Status: {status_global}")

    result = {
        "obra": obra.name,
        "pavimento": pavimento,
        "elementos": resultados,
        "score_global": round(score_global, 4),
        "score_global_percent": round(score_global * 100, 1),
        "aprovado": score_global >= 0.90,
    }

    out_path = fase6 / "validation_coletivo.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n[INFO] Salvo: {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--pavimento', default='12 PAV')
    args = parser.parse_args()
    run(args.obra, args.pavimento)


if __name__ == '__main__':
    main()
