#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fidelidade_lajes.py — Fidelidade geométrica: LJ_gerado.dxf vs STOG LJ original (CAD-10.4)
============================================================================================
Lajes têm geometria mais variável que pilares/vigas (lajes especiais, faixas estreitas).
Limiar rebaixado: >= 75 (vs 85 para pilares).

Métricas:
  - ID match       (30 pts)
  - Entity coverage(40 pts)
  - Layer presence (20 pts)
  - Anti-hall      (10 pts)

Saída: Fase-7_Consolidacao/fidelidade_lajes.json

CLI:
  python scripts/fidelidade_lajes.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
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


CRITICAL_LAYERS_LJ = ["AUX00", "COTA", "Texto Seção", "NOMENCLATURA", "4", "3", "2", "1"]
LIMIAR = 75.0


def _find_stog_lj(obra_path: Path, pavimento: str) -> Path | None:
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not fase1.exists():
        return None
    candidates = sorted(fase1.glob("*LJ*.dxf"))
    if not candidates:
        candidates = sorted(fase1.glob("*lj*.dxf"))
    pav_num = re.search(r'\d+', pavimento)
    if pav_num and candidates:
        num = pav_num.group()
        ranked = [f for f in candidates if num in f.name]
        if ranked:
            return ranked[0]
    return candidates[0] if candidates else None


def _find_gerado_lj(obra_path: Path) -> Path | None:
    """Preferência: LJ_stog_quality.dxf (ezdxf fiel ao STOG). Fallback: LJ_gerado.dxf."""
    fase6 = obra_path / "Fase-6_Execucao_CAD"
    p_quality = fase6 / "LJ_stog_quality.dxf"
    if p_quality.exists():
        return p_quality
    p_gerado = fase6 / "LJ_gerado.dxf"
    return p_gerado if p_gerado.exists() else None


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


def _extrair_ids_lajes(dxf_path: Path) -> set:
    """Extrai IDs tipo L{n} de entidades TEXT/MTEXT."""
    ids = set()
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        pat = re.compile(r'\bL(\d+)\b', re.IGNORECASE)
        for e in msp:
            if e.dxftype() not in ("TEXT", "MTEXT"):
                continue
            try:
                txt = e.plain_text() if e.dxftype() == "MTEXT" else (e.dxf.text or "")
            except Exception:
                txt = ""
            # Pegar só a primeira linha do texto para evitar dimensões virarem IDs
            first_line = txt.strip().split("\n")[0]
            m = pat.match(first_line.strip())
            if m:
                ids.add(f"L{m.group(1)}")
    except Exception as ex:
        print(f"  [WARN] Erro ao extrair IDs de {dxf_path.name}: {ex}")
    return ids


def _load_validation_lajes(obra_path: Path) -> dict:
    p = obra_path / "Fase-6_Execucao_CAD" / "validation_coletivo.json"
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("elementos", {}).get("lajes", {})
    except Exception:
        return {}


def calcular_fidelidade(
    stog_path: Path,
    gerado_path: Path,
    coletivo_ids: dict,
    verbose: bool = False,
) -> dict:

    # IDs
    if coletivo_ids:
        id_match     = coletivo_ids.get("id_match", 0.0)
        hall_rate    = coletivo_ids.get("hallucination_rate", 1.0)
        gt_count     = coletivo_ids.get("gt_count", 0)
        gerado_count = coletivo_ids.get("gerado_count", 0)
        missed       = coletivo_ids.get("missed", [])
        hallucinated = coletivo_ids.get("hallucinated", [])
    else:
        stog_ids   = _extrair_ids_lajes(stog_path)
        gerado_ids = _extrair_ids_lajes(gerado_path)
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
    for ly in CRITICAL_LAYERS_LJ:
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

    result = {
        "tipo": "lajes",
        "stog_dxf": stog_path.name,
        "gerado_dxf": gerado_path.name,
        "score": score_total,
        "aprovado": score_total >= LIMIAR,
        "limiar": LIMIAR,
        "nota": "Lajes têm geometria mais variável — limiar rebaixado para 75",
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

    if verbose:
        d = result["detalhes"]
        status = "✅" if result["aprovado"] else "❌"
        print(f"\n{'='*60}")
        print(f"  FIDELIDADE DXF — Lajes  {status} {result['score']}/100")
        print(f"{'='*60}")
        print(f"  STOG:   {result['stog_dxf']}")
        print(f"  Gerado: {result['gerado_dxf']}")
        id_d = d["id_match"]
        print(f"\n  IDs: {id_d['gt_count']} no STOG | {id_d['gerado_count']} no gerado")
        if id_d["missed"]:
            print(f"  ❌ Missed: {id_d['missed']}")
        if id_d["hallucinated"]:
            print(f"  ⚠️  Extras: {id_d['hallucinated']}")
        cov = d["entity_coverage"]
        print(f"\n  Entidades: stog={cov['stog_total']} gerado={cov['gerado_total']} ratio={cov['global_ratio']:.2f}")
        lp = d["layer_presence"]
        if lp["missing"]:
            print(f"  ❌ Layers ausentes: {lp['missing'][:5]}")
        print(f"\n  Score breakdown:")
        print(f"    ID match       : {d['id_match']['score']:5.1f}/30")
        print(f"    Entity coverage: {d['entity_coverage']['score']:5.1f}/40")
        print(f"    Layer presence : {d['layer_presence']['score']:5.1f}/20")
        print(f"    Anti-hall      : {d['anti_hallucination']['score']:5.1f}/10")
        print(f"    TOTAL          : {result['score']:5.1f}/100  {'✅ APROVADO' if result['aprovado'] else '❌ REPROVADO'}")
        if id_d["missed"]:
            print(f"\n  ℹ️  {len(id_d['missed'])} lajes não extraídas pelo pipeline (L-N, faixas especiais).")

    return result


def main():
    parser = argparse.ArgumentParser(description="Fidelidade geométrica — Lajes (LJ_gerado vs STOG)")
    parser.add_argument("--obra",      required=True)
    parser.add_argument("--pavimento", default="12 PAV")
    parser.add_argument("--verbose",   action="store_true")
    parser.add_argument("--out",       default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    if not obra_path.exists():
        print(f"[ERRO] Obra não encontrada: {obra_path}")
        sys.exit(1)

    stog_path   = _find_stog_lj(obra_path, args.pavimento)
    gerado_path = _find_gerado_lj(obra_path)

    if not stog_path or not stog_path.exists():
        print(f"[ERRO] DXF STOG LJ não encontrado em {obra_path}/Fase-1_Ingestao/")
        sys.exit(1)
    if not gerado_path or not gerado_path.exists():
        print(f"[ERRO] LJ_gerado.dxf não encontrado em {obra_path}/Fase-6_Execucao_CAD/")
        sys.exit(1)

    print(f"[INFO] STOG LJ : {stog_path.name}")
    print(f"[INFO] Gerado  : {gerado_path.name}")

    coletivo_ids = _load_validation_lajes(obra_path)
    result = calcular_fidelidade(stog_path, gerado_path, coletivo_ids, verbose=args.verbose)

    out_dir  = obra_path / "Fase-7_Consolidacao"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / "fidelidade_lajes.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    status = "✅ APROVADO" if result["aprovado"] else "❌ REPROVADO"
    print(f"\n[{status}] Lajes: {result['score']}/100  (limiar={result['limiar']})")
    print(f"[INFO] Salvo em: {out_path}")

    sys.exit(0 if result["aprovado"] else 1)


if __name__ == "__main__":
    main()
