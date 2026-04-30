#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fidelidade_pilares.py — Fidelidade geométrica: PL_gerado.dxf vs STOG PL original (CAD-10.2)
=============================================================================================
Métricas:
  - ID match       (30 pts): % IDs P{n} do STOG presentes no gerado
  - Entity coverage(40 pts): ratio de entidades por layers críticos (gerado/stog, cap=1.0)
  - Layer presence (20 pts): % dos layers STOG presentes no gerado
  - Anti-hall      (10 pts): penalidade por IDs extras (alucinação)

Score total = soma ponderada → 0-100
Limiar APROVADO: >= 85

Saída: Fase-7_Consolidacao/fidelidade_pilares.json

CLI:
  python scripts/fidelidade_pilares.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV"
  python scripts/fidelidade_pilares.py --obra DADOS-OBRAS/Obra_TREINO_21 --pavimento "12 PAV" --verbose
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


# Layers críticos para pilares (contribuem mais para o score)
CRITICAL_LAYERS_PL = [
    "Painéis", "Cota Seção (2x)", "Texto Seção",
    "COTA", "NOMENCLATURA", "Hachura",
]


def _find_stog_pl(obra_path: Path, pavimento: str) -> Path | None:
    """Localiza o DXF STOG original de PL para o pavimento."""
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not fase1.exists():
        return None
    # Tenta com número do pavimento ou "PAV" no nome
    candidates = sorted(fase1.glob("*PL*.dxf"))
    if not candidates:
        candidates = sorted(fase1.glob("*pl*.dxf"))
    # Preferir o que contém o pavimento
    pav_num = re.search(r'\d+', pavimento)
    if pav_num:
        num = pav_num.group()
        ranked = [f for f in candidates if num in f.name]
        if ranked:
            return ranked[0]
    # Fallback: primeiro PL encontrado
    return candidates[0] if candidates else None


def _find_gerado_pl(obra_path: Path) -> Path | None:
    """Localiza o melhor DXF gerado de PL para comparação de qualidade.

    Preferência: PL_stog_quality.dxf (gerador ezdxf de alta qualidade)
    Fallback:    PL_gerado.dxf (assembly de elementos individuais, muito simplificado)
    """
    fase6 = obra_path / "Fase-6_Execucao_CAD"
    # stog_quality = representação ezdxf que replica o formato STOG → comparação válida
    p_quality = fase6 / "PL_stog_quality.dxf"
    if p_quality.exists():
        return p_quality
    # Fallback: assembly (muito simplificado — ratio baixo esperado)
    p_gerado = fase6 / "PL_gerado.dxf"
    return p_gerado if p_gerado.exists() else None


def _extrair_ids_texto(dxf_path: Path, prefixo: str = "P") -> set:
    """Extrai IDs tipo P{n} de entidades TEXT/MTEXT no DXF."""
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
                ids.add(f"P{m.group(1)}")
    except Exception as ex:
        print(f"  [WARN] Erro ao ler {dxf_path.name}: {ex}")
    return ids


def _contar_layers(dxf_path: Path) -> dict:
    """Conta entidades por layer + total."""
    counts = Counter()
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        for e in msp:
            counts[e.dxf.layer] += 1
    except Exception as ex:
        print(f"  [WARN] Erro ao contar layers em {dxf_path.name}: {ex}")
    return dict(counts)


def _load_validation_coletivo(obra_path: Path) -> dict:
    """Lê validation_coletivo.json para obter dados de ID match já calculados."""
    p = obra_path / "Fase-6_Execucao_CAD" / "validation_coletivo.json"
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("elementos", {}).get("pilares", {})
    except Exception:
        return {}


def calcular_fidelidade(
    stog_path: Path,
    gerado_path: Path,
    coletivo_ids: dict,
    verbose: bool = False,
) -> dict:
    """Calcula score de fidelidade: 0-100."""

    # --- IDs ----------------------------------------------------------------
    if coletivo_ids:
        # Reutiliza dados já calculados do validation_coletivo.json
        id_match    = coletivo_ids.get("id_match", 0.0)
        hall_rate   = coletivo_ids.get("hallucination_rate", 1.0)
        gt_count    = coletivo_ids.get("gt_count", 0)
        gerado_count = coletivo_ids.get("gerado_count", 0)
        missed      = coletivo_ids.get("missed", [])
        hallucinated = coletivo_ids.get("hallucinated", [])
    else:
        # Fallback: extrai IDs dos próprios DXFs
        stog_ids   = _extrair_ids_texto(stog_path, "P")
        gerado_ids = _extrair_ids_texto(gerado_path, "P")
        correct    = stog_ids & gerado_ids
        hallucinated = sorted(gerado_ids - stog_ids)
        missed     = sorted(stog_ids - gerado_ids)
        gt_count   = len(stog_ids)
        gerado_count = len(gerado_ids)
        id_match   = len(correct) / len(stog_ids) if stog_ids else 0.0
        hall_rate  = len(hallucinated) / len(gerado_ids) if gerado_ids else 1.0

    score_id   = id_match * 30.0          # 0-30 pts
    score_hall = (1.0 - hall_rate) * 10.0 # 0-10 pts

    # --- Entity coverage (layers) -------------------------------------------
    stog_layers   = _contar_layers(stog_path)
    gerado_layers = _contar_layers(gerado_path)

    stog_total   = sum(stog_layers.values()) or 1
    gerado_total = sum(gerado_layers.values())

    # Cobertura por layer crítico (ratio cap=1.0, zero layers ausentes penaliza)
    critical_ratios = []
    for ly in CRITICAL_LAYERS_PL:
        s = stog_layers.get(ly, 0)
        g = gerado_layers.get(ly, 0)
        if s > 0:
            critical_ratios.append(min(g / s, 1.0))
        # Se layer crítico não existe no STOG, ignorar
    crit_avg = (sum(critical_ratios) / len(critical_ratios)) if critical_ratios else 0.0

    # Cobertura geral (entities total)
    global_ratio = min(gerado_total / stog_total, 1.0)

    # Weighted: 70% critical layers + 30% global ratio
    coverage = (0.70 * crit_avg + 0.30 * global_ratio)
    score_coverage = coverage * 40.0  # 0-40 pts

    # --- Layer presence -------------------------------------------------------
    stog_layer_set   = set(stog_layers.keys())
    gerado_layer_set = set(gerado_layers.keys())
    present = stog_layer_set & gerado_layer_set
    missing_layers = sorted(stog_layer_set - gerado_layer_set)
    presence_ratio = len(present) / len(stog_layer_set) if stog_layer_set else 0.0
    score_presence = presence_ratio * 20.0  # 0-20 pts

    # --- Score total ----------------------------------------------------------
    score_total = score_id + score_coverage + score_presence + score_hall
    score_total = round(min(score_total, 100.0), 1)

    result = {
        "tipo": "pilares",
        "stog_dxf": stog_path.name,
        "gerado_dxf": gerado_path.name,
        "score": score_total,
        "aprovado": score_total >= 85.0,
        "limiar": 85.0,
        "detalhes": {
            "id_match": {
                "score": round(score_id, 1),
                "max": 30,
                "gt_count": gt_count,
                "gerado_count": gerado_count,
                "id_match_rate": round(id_match, 4),
                "hallucination_rate": round(hall_rate, 4),
                "missed": missed,
                "hallucinated": hallucinated,
            },
            "entity_coverage": {
                "score": round(score_coverage, 1),
                "max": 40,
                "stog_total": stog_total,
                "gerado_total": gerado_total,
                "global_ratio": round(global_ratio, 4),
                "critical_avg": round(crit_avg, 4),
            },
            "layer_presence": {
                "score": round(score_presence, 1),
                "max": 20,
                "stog_layers": len(stog_layer_set),
                "present": len(present),
                "missing": missing_layers,
            },
            "anti_hallucination": {
                "score": round(score_hall, 1),
                "max": 10,
            },
        },
    }

    if verbose:
        _print_verbose(result, stog_layers, gerado_layers)

    return result


def _print_verbose(result: dict, stog_layers: dict, gerado_layers: dict):
    d = result["detalhes"]
    print(f"\n{'='*60}")
    print(f"  FIDELIDADE DXF — Pilares  {'✅' if result['aprovado'] else '❌'} {result['score']}/100")
    print(f"{'='*60}")
    print(f"  STOG:   {result['stog_dxf']}")
    print(f"  Gerado: {result['gerado_dxf']}")
    print()
    id_d = d["id_match"]
    print(f"  IDs: {id_d['gt_count']} no STOG | {id_d['gerado_count']} no gerado")
    if id_d["missed"]:
        print(f"  ❌ Missed: {id_d['missed']}")
    if id_d["hallucinated"]:
        print(f"  ⚠️  Extras: {id_d['hallucinated']}")

    cov = d["entity_coverage"]
    print(f"\n  Entidades: stog={cov['stog_total']} gerado={cov['gerado_total']} ratio={cov['global_ratio']:.2f}")
    print(f"  Layers críticos (média ratio): {cov['critical_avg']:.2f}")

    lp = d["layer_presence"]
    if lp["missing"]:
        print(f"\n  ❌ Layers ausentes: {lp['missing']}")

    print(f"\n  Score breakdown:")
    print(f"    ID match       : {d['id_match']['score']:5.1f}/30")
    print(f"    Entity coverage: {d['entity_coverage']['score']:5.1f}/40")
    print(f"    Layer presence : {d['layer_presence']['score']:5.1f}/20")
    print(f"    Anti-hall      : {d['anti_hallucination']['score']:5.1f}/10")
    print(f"    TOTAL          : {result['score']:5.1f}/100  {'✅ APROVADO' if result['aprovado'] else '❌ REPROVADO'}")


def main():
    parser = argparse.ArgumentParser(description="Fidelidade geométrica — Pilares (PL_gerado vs STOG)")
    parser.add_argument("--obra",      required=True,  help="Path da obra. Ex: DADOS-OBRAS/Obra_TREINO_21")
    parser.add_argument("--pavimento", default="12 PAV", help="Nome do pavimento (default: '12 PAV')")
    parser.add_argument("--verbose",   action="store_true", help="Exibe detalhes no console")
    parser.add_argument("--out",       default=None,   help="Override path de saída do JSON")
    args = parser.parse_args()

    obra_path = Path(args.obra)
    if not obra_path.exists():
        print(f"[ERRO] Obra não encontrada: {obra_path}")
        sys.exit(1)

    stog_path   = _find_stog_pl(obra_path, args.pavimento)
    gerado_path = _find_gerado_pl(obra_path)

    if not stog_path or not stog_path.exists():
        print(f"[ERRO] DXF STOG PL não encontrado em {obra_path}/Fase-1_Ingestao/")
        sys.exit(1)
    if not gerado_path or not gerado_path.exists():
        print(f"[ERRO] PL_gerado.dxf não encontrado em {obra_path}/Fase-6_Execucao_CAD/")
        print("       Execute pipeline_e2e.py e consolidar_dxf_pilares.py primeiro.")
        sys.exit(1)

    print(f"[INFO] STOG PL : {stog_path.name}")
    print(f"[INFO] Gerado  : {gerado_path.name}")

    coletivo_ids = _load_validation_coletivo(obra_path)
    if coletivo_ids:
        print(f"[INFO] Usando dados de ID match de validation_coletivo.json")

    result = calcular_fidelidade(stog_path, gerado_path, coletivo_ids, verbose=args.verbose)

    # Salvar JSON
    out_dir = obra_path / "Fase-7_Consolidacao"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / "fidelidade_pilares.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    status = "✅ APROVADO" if result["aprovado"] else "❌ REPROVADO"
    print(f"\n[{status}] Pilares: {result['score']}/100  (limiar={result['limiar']})")
    print(f"[INFO] Salvo em: {out_path}")

    sys.exit(0 if result["aprovado"] else 1)


if __name__ == "__main__":
    main()
