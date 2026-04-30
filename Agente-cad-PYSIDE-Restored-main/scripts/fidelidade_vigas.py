#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fidelidade_vigas.py — Fidelidade geométrica: LV_gerado + FV_gerado vs STOG originais (CAD-10.3)
================================================================================================
Avalia dois sub-tipos separadamente e produz score consolidado:
  - LV (laterais): LV_gerado.dxf vs STOG LV
  - FV (fundos):   FV_gerado.dxf vs STOG FV

Score LV limiar: >= 85 | Score FV limiar: >= 80
Score global vigas = 0.6 * LV + 0.4 * FV

Saída: Fase-7_Consolidacao/fidelidade_vigas.json

CLI:
  python scripts/fidelidade_vigas.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import argparse
import re
from pathlib import Path
from collections import Counter

try:
    import ezdxf
except ImportError:
    print("[ERRO] ezdxf não encontrado. Instale: pip install ezdxf")
    sys.exit(1)


CRITICAL_LAYERS_LV = ["Painéis", "COTA", "Texto Seção", "NOMENCLATURA", "SARR_2.2x7"]
CRITICAL_LAYERS_FV = ["Painéis", "COTA", "Texto Seção", "NOMENCLATURA", "SARR_2.2x7", "SARR_2.2x10"]


def _find_stog(obra_path: Path, tipo: str, pavimento: str) -> Path | None:
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not fase1.exists():
        return None
    candidates = sorted(fase1.glob(f"*{tipo}*.dxf"))
    pav_num = re.search(r'\d+', pavimento)
    if pav_num and candidates:
        num = pav_num.group()
        ranked = [f for f in candidates if num in f.name]
        if ranked:
            return ranked[0]
    return candidates[0] if candidates else None


def _find_gerado(obra_path: Path, tipo: str) -> Path | None:
    """Preferência: stog_quality (ezdxf fiel ao STOG). Fallback: gerado (assembly)."""
    fase6 = obra_path / "Fase-6_Execucao_CAD"
    # Tentar stog_quality primeiro (melhor representação para comparação)
    for suffix in ("_stog_quality_v2.dxf", "_stog_quality.dxf"):
        p = fase6 / f"{tipo}{suffix}"
        if p.exists():
            return p
    # Tentar gerado com timestamp (LV_stog_HHMMSS.dxf)
    candidates = sorted(fase6.glob(f"{tipo}_stog_*.dxf"), key=lambda x: x.stat().st_size, reverse=True)
    if candidates:
        return candidates[0]
    # Fallback assembly
    p = fase6 / f"{tipo}_gerado.dxf"
    return p if p.exists() else None


def _contar_layers(dxf_path: Path) -> dict:
    counts = Counter()
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        for e in msp:
            counts[e.dxf.layer] += 1
    except Exception as ex:
        print(f"  [WARN] Erro ao ler {dxf_path.name}: {ex}")
    return dict(counts)


def _extrair_ids_texto(dxf_path: Path, prefixo: str = "V") -> set:
    ids = set()
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        pat = re.compile(rf'\b{prefixo}(\d+)\b', re.IGNORECASE)
        for e in msp:
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            try:
                txt = e.plain_text() if e.dxftype() == "MTEXT" else (e.dxf.text or "")
            except Exception:
                txt = ""
            for m in pat.finditer(txt.strip()):
                ids.add(f"V{m.group(1)}")
    except Exception as ex:
        print(f"  [WARN] Erro ao extrair IDs de {dxf_path.name}: {ex}")
    return ids


def _load_validation_vigas(obra_path: Path) -> dict:
    p = obra_path / "Fase-6_Execucao_CAD" / "validation_coletivo.json"
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("elementos", {}).get("vigas", {})
    except Exception:
        return {}


def _calcular_score_subtipo(
    stog_path: Path,
    gerado_path: Path,
    critical_layers: list,
    coletivo_ids: dict,
    prefixo: str = "V",
) -> dict:
    """Score 0-100 para um sub-tipo (LV ou FV)."""

    # IDs
    if coletivo_ids:
        id_match  = coletivo_ids.get("id_match", 0.0)
        hall_rate = coletivo_ids.get("hallucination_rate", 1.0)
        gt_count  = coletivo_ids.get("gt_count", 0)
        gerado_count = coletivo_ids.get("gerado_count", 0)
        missed    = coletivo_ids.get("missed", [])
        hallucinated = coletivo_ids.get("hallucinated", [])
    else:
        stog_ids   = _extrair_ids_texto(stog_path, prefixo)
        gerado_ids = _extrair_ids_texto(gerado_path, prefixo)
        correct    = stog_ids & gerado_ids
        hallucinated = sorted(gerado_ids - stog_ids)
        missed     = sorted(stog_ids - gerado_ids)
        gt_count   = len(stog_ids)
        gerado_count = len(gerado_ids)
        id_match   = len(correct) / len(stog_ids) if stog_ids else 0.0
        hall_rate  = len(hallucinated) / len(gerado_ids) if gerado_ids else 1.0

    score_id   = id_match * 30.0
    score_hall = (1.0 - hall_rate) * 10.0

    # Entity coverage
    stog_layers   = _contar_layers(stog_path)
    gerado_layers = _contar_layers(gerado_path)
    stog_total    = sum(stog_layers.values()) or 1
    gerado_total  = sum(gerado_layers.values())

    critical_ratios = []
    for ly in critical_layers:
        s = stog_layers.get(ly, 0)
        g = gerado_layers.get(ly, 0)
        if s > 0:
            critical_ratios.append(min(g / s, 1.0))
    crit_avg     = (sum(critical_ratios) / len(critical_ratios)) if critical_ratios else 0.0
    global_ratio = min(gerado_total / stog_total, 1.0)
    coverage     = 0.70 * crit_avg + 0.30 * global_ratio
    score_coverage = coverage * 40.0

    # Layer presence
    stog_layer_set   = set(stog_layers.keys())
    gerado_layer_set = set(gerado_layers.keys())
    present          = stog_layer_set & gerado_layer_set
    missing_layers   = sorted(stog_layer_set - gerado_layer_set)
    presence_ratio   = len(present) / len(stog_layer_set) if stog_layer_set else 0.0
    score_presence   = presence_ratio * 20.0

    score_total = round(min(score_id + score_coverage + score_presence + score_hall, 100.0), 1)

    return {
        "stog_dxf": stog_path.name,
        "gerado_dxf": gerado_path.name,
        "score": score_total,
        "detalhes": {
            "id_match": {
                "score": round(score_id, 1), "max": 30,
                "gt_count": gt_count, "gerado_count": gerado_count,
                "id_match_rate": round(id_match, 4),
                "hallucination_rate": round(hall_rate, 4),
                "missed": missed, "hallucinated": hallucinated,
            },
            "entity_coverage": {
                "score": round(score_coverage, 1), "max": 40,
                "stog_total": stog_total, "gerado_total": gerado_total,
                "global_ratio": round(global_ratio, 4),
                "critical_avg": round(crit_avg, 4),
            },
            "layer_presence": {
                "score": round(score_presence, 1), "max": 20,
                "stog_layers": len(stog_layer_set),
                "present": len(present),
                "missing": missing_layers,
            },
            "anti_hallucination": {
                "score": round(score_hall, 1), "max": 10,
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Fidelidade geométrica — Vigas (LV + FV)")
    parser.add_argument("--obra",      required=True)
    parser.add_argument("--pavimento", default="12 PAV")
    parser.add_argument("--verbose",   action="store_true")
    parser.add_argument("--out",       default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    if not obra_path.exists():
        print(f"[ERRO] Obra não encontrada: {obra_path}")
        sys.exit(1)

    coletivo_vigas = _load_validation_vigas(obra_path)
    resultados = {}
    scores_validos = []

    for tipo, critical_layers, limiar in [
        ("LV", CRITICAL_LAYERS_LV, 85.0),
        ("FV", CRITICAL_LAYERS_FV, 80.0),
    ]:
        stog_path   = _find_stog(obra_path, tipo, args.pavimento)
        gerado_path = _find_gerado(obra_path, tipo)

        if not stog_path or not stog_path.exists():
            print(f"[WARN] DXF STOG {tipo} não encontrado — skip")
            resultados[tipo] = {"score": None, "aprovado": None, "erro": "STOG não encontrado"}
            continue
        if not gerado_path or not gerado_path.exists():
            print(f"[WARN] {tipo}_gerado.dxf não encontrado — skip")
            resultados[tipo] = {"score": None, "aprovado": None, "erro": "Gerado não encontrado"}
            continue

        print(f"\n[INFO] {tipo} — STOG: {stog_path.name}")
        print(f"[INFO] {tipo} — Gerado: {gerado_path.name}")

        # Para FV não temos IDs separados no validation_coletivo, usar fallback
        ids_data = coletivo_vigas if tipo == "LV" else {}
        r = _calcular_score_subtipo(stog_path, gerado_path, critical_layers, ids_data)
        r["aprovado"] = r["score"] >= limiar
        r["limiar"]   = limiar

        if args.verbose:
            status = "✅" if r["aprovado"] else "❌"
            print(f"\n  {status} {tipo}: {r['score']}/100")
            d = r["detalhes"]
            print(f"    ID match       : {d['id_match']['score']:5.1f}/30  (id_rate={d['id_match']['id_match_rate']:.2%})")
            print(f"    Entity coverage: {d['entity_coverage']['score']:5.1f}/40  (global_ratio={d['entity_coverage']['global_ratio']:.2f})")
            print(f"    Layer presence : {d['layer_presence']['score']:5.1f}/20  ({d['layer_presence']['present']}/{d['layer_presence']['stog_layers']} layers)")
            print(f"    Anti-hall      : {d['anti_hallucination']['score']:5.1f}/10")
            if d["layer_presence"]["missing"]:
                print(f"    ❌ Layers ausentes: {d['layer_presence']['missing'][:5]}")

        resultados[tipo] = r
        scores_validos.append((tipo, r["score"]))

    # Score global vigas: 60% LV + 40% FV
    if scores_validos:
        pesos = {"LV": 0.60, "FV": 0.40}
        soma = sum(pesos.get(t, 0.5) * s for t, s in scores_validos)
        total_peso = sum(pesos.get(t, 0.5) for t, _ in scores_validos)
        score_global = round(soma / total_peso, 1)
    else:
        score_global = 0.0

    aprovado_global = score_global >= 82.0  # limiar global vigas

    resultado_final = {
        "tipo": "vigas",
        "score": score_global,
        "aprovado": aprovado_global,
        "limiar": 82.0,
        "sub_tipos": resultados,
    }

    # Salvar
    out_dir  = obra_path / "Fase-7_Consolidacao"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / "fidelidade_vigas.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultado_final, f, indent=2, ensure_ascii=False)

    status = "✅ APROVADO" if aprovado_global else "❌ REPROVADO"
    print(f"\n[{status}] Vigas score global: {score_global}/100  (limiar={resultado_final['limiar']})")
    for tipo, score in scores_validos:
        sub = resultados[tipo]
        st  = "✅" if sub.get("aprovado") else "❌"
        print(f"  {st} {tipo}: {score}/100  (limiar={sub.get('limiar')})")
    print(f"[INFO] Salvo em: {out_path}")

    sys.exit(0 if aprovado_global else 1)


if __name__ == "__main__":
    main()
