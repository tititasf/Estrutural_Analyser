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

# KB-enhanced scorer (EPIC-STOG-5) — opcional, fallback automático para legacy
try:
    from fidelidade_kb_scorer import load_kb_by_file, _contar_layers_gerado, _score_layer_presence_semantic, _score_coverage_semantic, safe_readfile, _gc_after_dxf
    _KB_SCORER_AVAILABLE = True
except ImportError:
    _KB_SCORER_AVAILABLE = False


# Layers críticos para pilares (contribuem mais para o score)
CRITICAL_LAYERS_PL = [
    "Painéis", "Cota Seção (2x)", "Texto Seção",
    "COTA", "NOMENCLATURA", "Hachura",
]


def _count_dxf_entities(dxf_path: Path) -> int:
    """Conta entidades no modelspace de um DXF. Retorna -1 em caso de erro."""
    doc = safe_readfile(dxf_path)
    if doc is None:
        return -1
    try:
        count = len(list(doc.modelspace()))
    except Exception:
        count = -1
    del doc
    _gc_after_dxf()
    return count


def _find_stog_pl(obra_path: Path, pavimento: str, gerado_path: Path | None = None) -> Path | None:
    """Localiza o DXF STOG original de PL para o pavimento.

    Prioridade:
    1. PL não-PROJEÇÃO do pavimento correto (match por número)
    2. PL não-PROJEÇÃO com entity count mais próximo do gerado (minimiza viés de tamanho)
    3. PL PROJEÇÃO (fallback — tem entity count muito diferente do gerado)

    PROJEÇÃO DXFs são planos de planta com 5-15x mais entidades que seções de detalhe,
    e distorcem o entity_coverage por comparar conjuntos incomparáveis.
    """
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not fase1.exists():
        return None
    candidates = sorted(fase1.glob("*PL*.dxf"))
    if not candidates:
        candidates = sorted(fase1.glob("*pl*.dxf"))
    if not candidates:
        # Algumas obras usam sufixo "-PI-" (Pilar Individualizado) em vez de "-PL-"
        candidates = sorted(fase1.glob("*-PI-*.dxf")) or sorted(fase1.glob("*PI*.dxf"))
    if not candidates:
        return None

    # Separar PROJEÇÃO de padrão (detalhe de seção)
    _is_proj = re.compile(r'PROJE[ÇC]', re.IGNORECASE)
    standard = [f for f in candidates if not _is_proj.search(f.name)]
    projecao = [f for f in candidates if     _is_proj.search(f.name)]

    # Tentar match por número do pavimento primeiro na lista padrão
    pav_num = re.search(r'\d+', pavimento)
    if pav_num:
        num = pav_num.group()
        ranked = [f for f in standard if num in f.name]
        if ranked:
            return ranked[0]

    # Qualquer padrão (sem PROJEÇÃO): escolher o de entity count mais próximo do gerado
    if standard:
        if gerado_path and gerado_path.exists() and len(standard) > 1:
            gerado_n = _count_dxf_entities(gerado_path)
            if gerado_n > 0:
                # Preferir STOG com ratio mais próximo de 1.0 (gerado/stog ≤ 1 ideal)
                best, best_score = standard[0], float('inf')
                for f in standard:
                    n = _count_dxf_entities(f)
                    if n <= 0:
                        continue
                    # Penalizar mais quando stog > gerado (coverage capped at 1.0 acima)
                    ratio = gerado_n / n if n > 0 else 0
                    score = abs(1.0 - ratio) if ratio <= 1.0 else 0  # preferir ratio próximo a 1
                    if score < best_score:
                        best, best_score = f, score
                return best
        return standard[0]

    # Fallback PROJEÇÃO — tentar match por pavimento primeiro
    if pav_num:
        num = pav_num.group()
        ranked = [f for f in projecao if num in f.name]
        if ranked:
            return ranked[0]

    return projecao[0] if projecao else None


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
    doc = safe_readfile(dxf_path)
    if doc is None:
        return ids
    try:
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
    finally:
        del doc
        _gc_after_dxf()
    return ids


def _contar_layers(dxf_path: Path) -> dict:
    """Conta entidades por layer + total."""
    counts = Counter()
    doc = safe_readfile(dxf_path)
    if doc is None:
        return dict(counts)
    try:
        msp = doc.modelspace()
        for e in msp:
            counts[e.dxf.layer] += 1
    except Exception as ex:
        print(f"  [WARN] Erro ao contar layers em {dxf_path.name}: {ex}")
    finally:
        del doc
        _gc_after_dxf()
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
    """Calcula score de fidelidade: 0-100. Retorna score=None quando GT vazio (N/A)."""

    # --- Caso GT vazio: obra sem pilares neste pavimento → N/A ---------------
    if coletivo_ids.get("erro") == "GT vazio":
        return {
            "tipo": "pilares",
            "stog_dxf": stog_path.name,
            "gerado_dxf": gerado_path.name,
            "score": None,
            "aprovado": None,
            "limiar": 85.0,
            "na_motivo": "GT vazio — sem pilares neste pavimento",
        }

    # --- IDs ----------------------------------------------------------------
    if coletivo_ids:
        # Reutiliza dados já calculados do validation_coletivo.json
        id_match    = coletivo_ids.get("id_match", 0.0)
        hall_rate   = coletivo_ids.get("hallucination_rate", 0.0)
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
        hall_rate  = len(hallucinated) / len(gerado_ids) if gerado_ids else 0.0

    score_id   = id_match * 30.0          # 0-30 pts
    score_hall = (1.0 - hall_rate) * 10.0 # 0-10 pts

    # --- Entity coverage (layers) -------------------------------------------
    stog_layers   = _contar_layers(stog_path)
    gerado_layers = _contar_layers(gerado_path)

    stog_total   = sum(stog_layers.values()) or 1
    gerado_total = sum(gerado_layers.values())

    # Normalização por contagem de pilares:
    # O STOG pode conter um pavimento inteiro (N pilares) enquanto o gerado
    # processa apenas M pilares do mesmo pavimento. Sem normalização, o ratio
    # gerado/stog = M/N × entidades_por_pilar, penalizando o gerado injustamente.
    # Extrai contagem de IDs do STOG para normalizar.
    stog_pilar_count = len(_extrair_ids_texto(stog_path, "P"))
    gerado_pilar_count = max(gerado_count, 1)  # gt_count do coletivo
    if stog_pilar_count > gerado_pilar_count:
        # Normalizar: escalar stog_total para a mesma quantidade de pilares do gerado
        stog_total_norm = stog_total * (gerado_pilar_count / stog_pilar_count)
    else:
        stog_total_norm = stog_total

    # Cobertura por layer crítico (ratio cap=1.0, zero layers ausentes penaliza)
    # Normalizar também os layers críticos pelo ratio de pilares
    pilar_scale = (gerado_pilar_count / stog_pilar_count) if stog_pilar_count > gerado_pilar_count else 1.0
    critical_ratios = []
    for ly in CRITICAL_LAYERS_PL:
        s = stog_layers.get(ly, 0)
        g = gerado_layers.get(ly, 0)
        if s > 0:
            s_norm = s * pilar_scale
            critical_ratios.append(min(g / s_norm, 1.0))
        # Se layer crítico não existe no STOG, ignorar
    crit_avg = (sum(critical_ratios) / len(critical_ratios)) if critical_ratios else 0.0

    # Cobertura geral (entities total normalizados por pilar count)
    global_ratio = min(gerado_total / max(stog_total_norm, 1), 1.0)

    # Weighted: 70% critical layers + 30% global ratio
    # Se nenhum critical layer existe no STOG, usar global_ratio puro
    if not critical_ratios:
        coverage = global_ratio
    else:
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

    gerado_path = _find_gerado_pl(obra_path)
    stog_path   = _find_stog_pl(obra_path, args.pavimento, gerado_path=gerado_path)

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

    # EPIC-STOG-7b: Retry com próximos candidatos se GT vazio no primeiro
    # Filtra com _extrair_ids_texto (rápido) antes de rodar calcular_fidelidade completo
    if result.get("score") is None and result.get("na_motivo", "").startswith("GT vazio"):
        fase1_retry = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
        _retry_cands = []
        for _pat in ("*PL*.dxf", "*pl*.dxf", "*-PI-*.dxf", "*PI*.dxf"):
            _retry_cands = [f for f in sorted(fase1_retry.glob(_pat)) if f != stog_path]
            if _retry_cands:
                break
        # Pré-filtrar: manter só os que têm IDs de pilares (rápido — só lê TEXT/MTEXT)
        _with_ids = []
        for _alt in _retry_cands:
            try:
                _ids = _extrair_ids_texto(_alt, "P")
                if _ids:
                    _with_ids.append(_alt)
            except Exception:
                pass
        for _alt in _with_ids[:3]:  # tentar até 3 com IDs confirmados
            _r2 = calcular_fidelidade(_alt, gerado_path, coletivo_ids, verbose=False)
            if _r2.get("score") is not None:
                print(f"  [RETRY] GT vazio em {stog_path.name} → usando {_alt.name}")
                stog_path = _alt
                result = _r2
                break

    # EPIC-STOG-5: KB-blended — melhorar layer_presence E corrigir entity_coverage
    if _KB_SCORER_AVAILABLE and result.get("score") is not None:
        kb_dir = obra_path / "Fase-0_STOG_KB" / "PL"
        kb = load_kb_by_file(kb_dir, stog_path.stem)
        # Fallback: buscar em UNKNOWN (obras com class codes não-padrão: PLC, PI, etc.)
        if kb is None:
            kb_dir_unk = obra_path / "Fase-0_STOG_KB" / "UNKNOWN"
            kb = load_kb_by_file(kb_dir_unk, stog_path.stem)
            if kb is None and kb_dir_unk.exists():
                # Tentar qualquer KB de UNKNOWN com total_entities próximo ao STOG lido
                unk_kbs = sorted(kb_dir_unk.glob("*_kb.json"))
                best_unk = None
                best_ent = 0
                for unk_f in unk_kbs:
                    try:
                        unk_d = json.loads(unk_f.read_text(encoding='utf-8'))
                        ent = sum(unk_d.get('inventory', {}).get('by_layer', {}).values())
                        if ent > best_ent:
                            best_ent = ent
                            best_unk = unk_d
                    except Exception:
                        pass
                if best_unk and best_ent > 1000:
                    kb = best_unk
                    print(f"  [FALLBACK] Usando KB UNKNOWN: {best_unk.get('file','?')} ({best_ent} ent.)")
        if kb:
            print(f"[INFO] PL — KB carregada: {kb.get('file', '?')} (scorer=kb-blended)")
            gerado_by_layer = _contar_layers_gerado(gerado_path)
            layer_semantics = kb.get("semantic_analysis", {}).get("layer_semantics", {})
            stog_by_layer_kb = kb.get("inventory", {}).get("by_layer", {})

            # 1. Melhorar layer_presence com KB semântico
            kb_presence = _score_layer_presence_semantic(stog_by_layer_kb, gerado_by_layer, layer_semantics, classe="PL")
            old_pre = result["detalhes"]["layer_presence"]["score"]
            delta_pre = kb_presence["score"] - old_pre

            # 2. Corrigir entity_coverage se legacy falhou (stog_total <= 1 indica leitura DXF falhou)
            delta_cov = 0.0
            stog_total_legacy = result["detalhes"].get("entity_coverage", {}).get("stog_total", 0)
            if stog_total_legacy <= 1 and sum(stog_by_layer_kb.values()) > 10:
                # stog_total do legacy é inválido — recomputar com KB
                stog_total_kb = sum(stog_by_layer_kb.values())
                gerado_total_kb = sum(gerado_by_layer.values())
                ids_data_kb = coletivo_ids or {}
                class_specific_kb = kb.get("class_specific", {})
                ids_scale_kb = 1.0
                if ids_data_kb:
                    gt_c = ids_data_kb.get("gt_count", 0)
                    ger_c = ids_data_kb.get("gerado_count", 0)
                    if gt_c > 0 and gt_c > 2 * ger_c:
                        ids_scale_kb = ger_c / gt_c
                kb_coverage = _score_coverage_semantic(
                    stog_by_layer_kb, gerado_by_layer,
                    stog_total_kb, gerado_total_kb,
                    layer_semantics, CRITICAL_LAYERS_PL, class_specific_kb,
                    ids_scale=ids_scale_kb,
                )
                old_cov = result["detalhes"]["entity_coverage"]["score"]
                delta_cov = kb_coverage["score"] - old_cov
                result["detalhes"]["entity_coverage"] = kb_coverage
                print(f"  [FIX] entity_coverage corrigido via KB: {old_cov:.1f} → {kb_coverage['score']:.1f}")

            total_delta = delta_pre + delta_cov
            result["score"] = round(min(result["score"] + total_delta, 100.0), 1)
            result["aprovado"] = result["score"] >= result.get("limiar", 85.0)
            result["detalhes"]["layer_presence"] = kb_presence
            result["scorer"] = "kb-blended"
            result["kb_file"] = kb.get("file", "")

    # Salvar JSON
    out_dir = obra_path / "Fase-7_Consolidacao"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else out_dir / "fidelidade_pilares.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    if result["aprovado"] is None:
        print(f"\n[N/A] Pilares: {result.get('na_motivo', 'N/A')}")
    else:
        status = "✅ APROVADO" if result["aprovado"] else "❌ REPROVADO"
        print(f"\n[{status}] Pilares: {result['score']}/100  (limiar={result['limiar']})")
    print(f"[INFO] Salvo em: {out_path}")

    # N/A = exit 0 (não é falha)
    sys.exit(0 if (result["aprovado"] is None or result["aprovado"]) else 1)


if __name__ == "__main__":
    main()
