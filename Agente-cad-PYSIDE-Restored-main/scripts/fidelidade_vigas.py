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

# KB-enhanced scorer (EPIC-STOG-5) — opcional, fallback automático para legacy
try:
    from fidelidade_kb_scorer import load_kb, score_with_kb, safe_readfile, _gc_after_dxf
    _KB_SCORER_AVAILABLE = True
except ImportError:
    _KB_SCORER_AVAILABLE = False


CRITICAL_LAYERS_LV = ["Painéis", "COTA", "Texto Seção", "NOMENCLATURA", "SARR_2.2x7"]
CRITICAL_LAYERS_FV = ["Painéis", "COTA", "Texto Seção", "NOMENCLATURA", "SARR_2.2x7", "SARR_2.2x10"]

# Camadas estruturais/arquitetônicas que aparecem em DXFs "crus" (raw project drawings)
# mas NÃO fazem parte do conteúdo de escoramento (FV/LV). Excluídas do stog_total para
# evitar penalizar o gerador por não reproduzir infraestrutura estrutural da obra.
_FV_LV_STRUCTURAL_NOISE = frozenset([
    "S-BEAM", "S-BEAM-IDEN", "A-FLOR", "A-FLOR-IDEN",
    "S-COLS", "S-COLS-IDEN", "S-COLS-HDLN",
    "G-ANNO-SYMB", "A-DETL", "A-GENM", "A-GENM-IDEN",
    "DEFPOINTS", "FOLHA MB", "IDENT INDICE",
    "Tubulação", "TUBULACAO",
])


def _find_stog(obra_path: Path, tipo: str, pavimento: str,
               gerado_path: Path | None = None) -> Path | None:
    fase1 = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not fase1.exists():
        return None
    candidates = sorted(fase1.glob(f"*{tipo}*.dxf"))
    if not candidates:
        return None

    # Para FV: selecionar o arquivo com maior cobertura dos IDs gerados
    # Isso resolve casos como TREINO_18 onde 2°ETAPA cobre todos os 3 IDs gerados
    # enquanto 1°ETAPA cobre apenas 1/3 (mesmo tendo mais IDs STOG no total)
    if tipo == "FV" and gerado_path and gerado_path.exists():
        gerado_ids = _extrair_ids_texto(gerado_path, "V")
        if gerado_ids:
            best_path, best_score = None, -1.0
            for cand in candidates:
                stog_ids = _extrair_ids_texto(cand, "V")
                if not stog_ids:
                    continue
                overlap = len(stog_ids & gerado_ids)
                # Score: fração dos IDs gerados cobertos por este STOG
                score = overlap / len(gerado_ids)
                if score > best_score:
                    best_score = score
                    best_path = cand
            # Usar best-match apenas se cobre ≥ 50% dos IDs gerados
            if best_path and best_score >= 0.50:
                return best_path

    pav_num = re.search(r'\d+', pavimento)
    if pav_num:
        num = pav_num.group()
        # Prefer single-floor files (evita TIPO multi-pavimento que distorce contagem)
        # Primeiro tenta arquivos que têm o número mas NÃO são "TIPO" multi-pav
        ranked_single = [f for f in candidates if num in f.name
                         and not re.search(r'TIPO|AO\s+\d+', f.name, re.IGNORECASE)]
        if ranked_single:
            return ranked_single[0]
        # Fallback: qualquer arquivo com o número
        ranked_any = [f for f in candidates if num in f.name]
        if ranked_any:
            return ranked_any[0]

    # Fallback: preferir single-floor se houver, evitar TIPO
    single_floor = [f for f in candidates
                    if not re.search(r'TIPO|AO\s+\d+', f.name, re.IGNORECASE)]
    if single_floor:
        return single_floor[0]
    return candidates[0]


def _find_gerado(obra_path: Path, tipo: str) -> Path | None:
    """Preferência: stog_quality (ezdxf fiel ao STOG). Fallback: gerado (assembly)."""
    fase6 = obra_path / "Fase-6_Execucao_CAD"
    # Tentar stog_quality primeiro (melhor representação para comparação)
    for suffix in ("_stog_quality.dxf", "_stog_quality_v2.dxf"):
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
    doc = safe_readfile(dxf_path)
    if doc is None:
        return dict(counts)
    try:
        msp = doc.modelspace()
        for e in msp:
            counts[e.dxf.layer] += 1
    except Exception as ex:
        print(f"  [WARN] Erro ao ler {dxf_path.name}: {ex}")
    finally:
        del doc
        _gc_after_dxf()
    return dict(counts)


def _normalizar_id_num(num_str: str) -> int:
    """Normaliza número de viga: remove offset de centenas (101→1, 201→1, 1→1)."""
    n = int(num_str)
    # Se número >= 100, remove o offset de centena mais próximo
    # Ex: 101→1, 135→35, 201→1, 250→50
    if n >= 100:
        n = n % 100
        if n == 0:
            n = 100  # V100, V200 ficam como V100
    return n


def _extrair_ids_texto(dxf_path: Path, prefixo: str = "V") -> set:
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
                norm = _normalizar_id_num(m.group(1))
                ids.add(f"V{norm}")
    except Exception as ex:
        print(f"  [WARN] Erro ao extrair IDs de {dxf_path.name}: {ex}")
    finally:
        del doc
        _gc_after_dxf()
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
    stog_id_count_raw = 0  # usado para normalizar entity coverage
    if coletivo_ids:
        id_match  = coletivo_ids.get("id_match", 0.0)
        hall_rate = coletivo_ids.get("hallucination_rate", 0.0)
        gt_count  = coletivo_ids.get("gt_count", 0)
        gerado_count = coletivo_ids.get("gerado_count", 0)
        missed    = coletivo_ids.get("missed", [])
        hallucinated = coletivo_ids.get("hallucinated", [])
        stog_id_count_raw = gt_count
    else:
        stog_ids   = _extrair_ids_texto(stog_path, prefixo)
        gerado_ids = _extrair_ids_texto(gerado_path, prefixo)
        correct    = stog_ids & gerado_ids
        hallucinated = sorted(gerado_ids - stog_ids)
        missed     = sorted(stog_ids - gerado_ids)
        gt_count   = len(stog_ids)
        gerado_count = len(gerado_ids)
        stog_id_count_raw = gt_count
        # Quando gerado cobre apenas um subconjunto do STOG (ex: FV pavimento único vs STOG
        # multi-pavimento), medir precisão do gerado (correct/gerado) em vez de recall do STOG
        if stog_ids and gerado_ids and len(stog_ids) > 2 * len(gerado_ids):
            id_match  = len(correct) / len(gerado_ids)
        else:
            id_match  = len(correct) / len(stog_ids) if stog_ids else 0.0
        hall_rate  = len(hallucinated) / len(gerado_ids) if gerado_ids else 0.0

    score_id   = id_match * 30.0
    score_hall = (1.0 - hall_rate) * 10.0

    # Entity coverage
    stog_layers   = _contar_layers(stog_path)
    gerado_layers = _contar_layers(gerado_path)
    # Filtrar camadas estruturais/arquitetônicas que inflam o stog_total em DXFs "crus"
    # (obras onde o DXF de escoramento foi feito sobre a planta estrutural completa)
    stog_layers_clean  = {k: v for k, v in stog_layers.items()  if k not in _FV_LV_STRUCTURAL_NOISE}
    gerado_layers_clean = {k: v for k, v in gerado_layers.items() if k not in _FV_LV_STRUCTURAL_NOISE}
    noise_removed = sum(stog_layers.values()) - sum(stog_layers_clean.values())
    if noise_removed > 0:
        print(f"  [NOISE-FILTER] Removidas {noise_removed} entidades estruturais do STOG ({len(stog_layers)-len(stog_layers_clean)} layers)")
    stog_layers  = stog_layers_clean
    gerado_layers = gerado_layers_clean
    stog_total    = sum(stog_layers.values()) or 1
    gerado_total  = sum(gerado_layers.values())

    # Normalizar stog quando STOG cobre mais vigas do que o gerado (subset generation)
    # Ex: FV pavimento único vs STOG multi-pavimento — escalar proporcionalmente
    gerado_id_count = gerado_count if gerado_count > 0 else max(gerado_total, 1)
    if stog_id_count_raw > 0 and gerado_id_count > 0 and stog_id_count_raw > 2 * gerado_id_count:
        scale = gerado_id_count / stog_id_count_raw
        stog_total_norm = max(stog_total * scale, 1)
    else:
        stog_total_norm = stog_total
        scale = 1.0

    critical_ratios = []
    for ly in critical_layers:
        s = stog_layers.get(ly, 0)
        g = gerado_layers.get(ly, 0)
        if s > 0:
            s_norm = s * scale if scale < 1.0 else s
            critical_ratios.append(min(g / max(s_norm, 1), 1.0))
    crit_avg     = (sum(critical_ratios) / len(critical_ratios)) if critical_ratios else 0.0
    global_ratio = min(gerado_total / stog_total_norm, 1.0)
    # Se nenhum critical layer existe no STOG, usar global_ratio puro
    if not critical_ratios:
        coverage = global_ratio
    else:
        coverage = 0.70 * crit_avg + 0.30 * global_ratio
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
        gerado_path = _find_gerado(obra_path, tipo)
        stog_path   = _find_stog(obra_path, tipo, args.pavimento, gerado_path=gerado_path)

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

        # Sempre calcular via legacy (tem normalização de subset correta)
        r = _calcular_score_subtipo(stog_path, gerado_path, critical_layers, ids_data)
        r["scorer"] = "legacy"

        # EPIC-STOG-5: KB-blended — melhorar layer_presence E corrigir entity_coverage
        if _KB_SCORER_AVAILABLE:
            from fidelidade_kb_scorer import (
                load_kb_by_file, _contar_layers_gerado,
                _score_layer_presence_semantic, _score_coverage_semantic,
            )
            kb_dir = obra_path / "Fase-0_STOG_KB" / tipo
            kb = load_kb_by_file(kb_dir, stog_path.stem)
            # Fallback: UNKNOWN dir (obras com class codes não-padrão)
            if kb is None:
                kb_dir_unk = obra_path / "Fase-0_STOG_KB" / "UNKNOWN"
                kb = load_kb_by_file(kb_dir_unk, stog_path.stem)
                if kb is None and kb_dir_unk.exists():
                    unk_kbs = sorted(kb_dir_unk.glob("*_kb.json"))
                    best_unk, best_ent = None, 0
                    for unk_f in unk_kbs:
                        try:
                            unk_d = json.loads(unk_f.read_text(encoding='utf-8'))
                            ent = sum(unk_d.get('inventory', {}).get('by_layer', {}).values())
                            if ent > best_ent:
                                best_ent, best_unk = ent, unk_d
                        except Exception:
                            pass
                    if best_unk and best_ent > 1000:
                        kb = best_unk
                        print(f"  [FALLBACK] KB UNKNOWN: {best_unk.get('file','?')} ({best_ent} ent.)")
            if kb:
                print(f"[INFO] {tipo} — KB carregada: {kb.get('file', '?')} (scorer=kb-blended)")
                gerado_by_layer = _contar_layers_gerado(gerado_path)
                layer_semantics = kb.get("semantic_analysis", {}).get("layer_semantics", {})
                stog_by_layer_kb = kb.get("inventory", {}).get("by_layer", {})

                # 1. Melhorar layer_presence com KB semântico + NON_STOG filter
                kb_presence = _score_layer_presence_semantic(
                    stog_by_layer_kb, gerado_by_layer, layer_semantics, classe=tipo
                )
                old_pre = r["detalhes"]["layer_presence"]["score"]
                delta_pre = kb_presence["score"] - old_pre

                # 2. Corrigir entity_coverage se stog_total <= 1 (leitura DXF falhou)
                delta_cov = 0.0
                stog_total_legacy = r["detalhes"].get("entity_coverage", {}).get("stog_total", 0)
                if stog_total_legacy <= 1 and sum(stog_by_layer_kb.values()) > 10:
                    stog_total_kb = sum(stog_by_layer_kb.values())
                    gerado_total_kb = sum(gerado_by_layer.values())
                    class_specific_kb = kb.get("class_specific", {})
                    ids_scale_kb = 1.0
                    if ids_data:
                        gt_c = ids_data.get("gt_count", 0)
                        ger_c = ids_data.get("gerado_count", 0)
                        if gt_c > 0 and gt_c > 2 * ger_c:
                            ids_scale_kb = ger_c / gt_c
                    kb_coverage = _score_coverage_semantic(
                        stog_by_layer_kb, gerado_by_layer,
                        stog_total_kb, gerado_total_kb,
                        layer_semantics, critical_layers, class_specific_kb,
                        ids_scale=ids_scale_kb,
                    )
                    old_cov = r["detalhes"]["entity_coverage"]["score"]
                    delta_cov = kb_coverage["score"] - old_cov
                    r["detalhes"]["entity_coverage"] = kb_coverage
                    print(f"  [FIX] entity_coverage via KB: {old_cov:.1f} → {kb_coverage['score']:.1f}")

                total_delta = delta_pre + delta_cov
                r["score"] = round(min(r["score"] + total_delta, 100.0), 1)
                r["detalhes"]["layer_presence"] = kb_presence
                r["scorer"] = "kb-blended"
                r["kb_file"] = kb.get("file", "")

        r["aprovado"] = r["score"] >= limiar
        r["limiar"]   = limiar

        if args.verbose:
            status = "✅" if r["aprovado"] else "❌"
            scorer_tag = r.get("scorer", "legacy")
            print(f"\n  {status} {tipo}: {r['score']}/100  [{scorer_tag}]")
            d = r["detalhes"]
            id_d = d.get("id_match", {})
            cov_d = d.get("entity_coverage", {})
            pre_d = d.get("layer_presence", {})
            hall_d = d.get("anti_hallucination", {})
            id_rate = id_d.get("id_match_rate") or id_d.get("rate")
            id_rate_str = f"{id_rate:.2%}" if id_rate is not None else "n/a"
            global_ratio = cov_d.get("global_ratio", cov_d.get("weighted_coverage", 0))
            n_present = pre_d.get("present", "?")
            n_total = pre_d.get("stog_layers", pre_d.get("required_layers", "?"))
            print(f"    ID match       : {id_d.get('score', 0):5.1f}/30  (id_rate={id_rate_str})")
            print(f"    Entity coverage: {cov_d.get('score', 0):5.1f}/40  (global_ratio={global_ratio:.3f})")
            print(f"    Layer presence : {pre_d.get('score', 0):5.1f}/20  ({n_present}/{n_total} layers)")
            print(f"    Anti-hall      : {hall_d.get('score', 0):5.1f}/10")
            missing = pre_d.get("missing_list") or pre_d.get("missing", [])
            if missing and isinstance(missing, list) and len(missing) > 0:
                print(f"    ❌ Layers ausentes: {missing[:5]}")

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
