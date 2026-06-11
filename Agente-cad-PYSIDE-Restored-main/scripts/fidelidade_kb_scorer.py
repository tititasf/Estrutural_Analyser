#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fidelidade_kb_scorer.py — EPIC-STOG-5
======================================
KB-enhanced fidelidade scoring usando knowledge base pré-computada pelo STOG Intelligence.

Melhoria sobre o scorer legacy:
  1. Pesos semânticos por layer: robot-known=1.0, pattern_match=0.7, autonomous_discovery=0.3
     → Layers de carimbo/autoria (00-FELIPE, CARIMBO) não penalizam o gerado
  2. Reutiliza KB pré-computada (mais rápido, sem re-scan STOG)
  3. Ciente de anomalias: se KB detectou INSERTs em FV como válidos, não penaliza
  4. Class-specific: LV tipo (sarrafeado vs grade) para scoring correto de tipo

Uso:
    from fidelidade_kb_scorer import load_kb, score_with_kb

    kb = load_kb(obra_path, "LV", "1° PAV")
    if kb:
        result = score_with_kb(kb, gerado_path, critical_layers, ids_data)
    else:
        result = score_legacy(...)  # fallback

"""

import gc
import json
import re
from pathlib import Path
from collections import Counter

try:
    import ezdxf
except ImportError:
    ezdxf = None

try:
    import psutil as _psutil
    _PSUTIL_OK = True
except ImportError:
    _psutil = None
    _PSUTIL_OK = False

# ---------------------------------------------------------------------------
# Memory guard — evita OOM em PCs com pouca RAM
# ---------------------------------------------------------------------------
MEM_LIMIT_MB = 600  # Aborta leitura de DXF se RAM livre < este valor (MB)
# Nota: ezdxf lê DXFs de 2-10 MB — não precisa de 1.8 GB livres.
# 1800 MB causava falso-positivo 40.0 quando batch esgotava RAM (ex: TREINO_13/16/18/20).


def _check_memory(label: str = "") -> bool:
    """
    Retorna True se há RAM suficiente para continuar.
    Se psutil não estiver disponível, sempre retorna True.
    """
    if not _PSUTIL_OK:
        return True
    vm = _psutil.virtual_memory()
    free_mb = vm.available / (1024 * 1024)
    if free_mb < MEM_LIMIT_MB:
        print(f"[WARN] RAM disponível baixa: {free_mb:.0f} MB < {MEM_LIMIT_MB} MB"
              + (f" ({label})" if label else "") + " — pulando leitura DXF")
        gc.collect()
        return False
    return True


def _gc_after_dxf():
    """Força GC após operação pesada de DXF."""
    gc.collect()


def safe_readfile(dxf_path, label: str = "") -> object | None:
    """
    Wrapper de ezdxf.readfile com memory guard.
    Retorna o doc ezdxf ou None se RAM insuficiente / erro.
    SEMPRE chamar `del doc; gc.collect()` após usar o resultado.
    """
    if ezdxf is None:
        return None
    if not _check_memory(label or Path(dxf_path).name):
        return None
    try:
        return ezdxf.readfile(str(dxf_path))
    except Exception as e:
        print(f"  [WARN] Erro ao ler {Path(dxf_path).name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Pesos semânticos por source do KB
# ---------------------------------------------------------------------------
SOURCE_WEIGHTS = {
    "robot":              1.00,   # Confirmado pelos robôs reais — crítico
    "pattern_match":      0.70,   # Padrão inferido — provável
    "numeric_layer":      0.50,   # Layer numérico — estrutural mas genérico
    "autonomous_discovery": 0.20, # Descoberta autônoma — não gerado, não penaliza
    "unknown":            0.40,
}

# Layers que o gerado NUNCA deve ter (penalizar presença)
CARIMBO_LAYERS = {"CARIMBO", "00 - FELIPE", "00-FELIPE", "Romaneio", "FOLHA MB"}

# Layers que NÃO devem ser exigidos no gerado:
# - Camadas editoriais/de edição (SARR_EDITAR, Defpoints)
# - Camadas arquitetônicas que aparecem no STOG mas não são estruturais
# - Camadas de forma (FO-*) geradas pelo software de projeto, não pelo gerador STOG
NON_STOG_REQUIRED: set[str] = {
    "SARR_EDITAR",        # layer de marcação editorial
    "Defpoints",          # AutoCAD padrão, nunca estrutural
    "ALVENARIA", "ESCADA", "PAREDE", "ESTRUTURA METALICA",
    "CONTRA-FLECHA", "NIVEL-ARQUITETURA",
    "CORTE-FORMA", "CORTES", "SETAS", "TENSOR",
    "SEM LAJE", "LAYER", "FOLHA",
    "P-M", "P-N", "__Met", "___HIDRAULICA",
}
# Prefixos que identificam layers não-STOG (ex: FO-VIGAS, FO-Eixos, A-FLOR-IDEN)
NON_STOG_PREFIXES = ("FO-", "A-FLOR-", "S-BEAM", "S-COLS", "S-SLAB")

# Cache dos baselines cross-obra (carregado lazy)
_BASELINES_CACHE: dict | None = None
_BASELINES_PATH = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/cross_obra_baselines.json")


def _get_baselines() -> dict:
    """Carrega baselines cross-obra com cache."""
    global _BASELINES_CACHE
    if _BASELINES_CACHE is None:
        try:
            _BASELINES_CACHE = json.loads(_BASELINES_PATH.read_text(encoding='utf-8'))
        except Exception:
            _BASELINES_CACHE = {}
    return _BASELINES_CACHE


def get_universal_layers(classe: str, min_obras: int = 12) -> set:
    """
    Retorna layers que aparecem em >= min_obras obras para uma classe.
    Esses layers são tratados como peso 1.0 independente do source.

    Baseado em cross_obra_baselines.json gerado sobre 19 obras reais.
    """
    baselines = _get_baselines()
    class_data = baselines.get(classe, {})
    layers_seen = class_data.get("layers_seen_in_n_obras", {})
    return {layer for layer, count in layers_seen.items() if count >= min_obras}


# ---------------------------------------------------------------------------
# Carregar KB
# ---------------------------------------------------------------------------
def load_kb(obra_path: Path, classe: str, pavimento: str) -> dict | None:
    """
    Carrega KB JSON pré-computada para o par (classe, pavimento) de uma obra.

    Retorna dict com o KB, ou None se não existir.
    """
    kb_dir = obra_path / "Fase-0_STOG_KB" / classe
    if not kb_dir.exists():
        return None

    # Normalizar pavimento para matching
    pav_norm = _normalize_pav(pavimento)

    best_kb = None
    best_score = -1

    for kb_file in kb_dir.glob("*_kb.json"):
        try:
            with open(kb_file, encoding="utf-8") as f:
                kb = json.load(f)
        except Exception:
            continue

        kb_pav = kb.get("pavimento", "")
        match_score = _pav_match_score(pav_norm, _normalize_pav(kb_pav))
        if match_score > best_score:
            best_score = match_score
            best_kb = kb

    # Só retornar se match razoável (score > 0 = alguma correspondência)
    if best_score > 0 and best_kb:
        return best_kb
    return None


def load_kb_by_file(kb_dir: Path, dxf_stem: str) -> dict | None:
    """
    Carrega KB pelo stem do arquivo DXF (nome sem extensão).
    O extrator salva KB com o mesmo nome do DXF, substituindo chars especiais por _.

    Robusto a acentos: tenta múltiplas formas de sanitização para lidar
    com diferenças de encoding entre Windows e Python (ex: Á → _  vs  Á literal).
    """
    kb_dir = Path(kb_dir)
    if not kb_dir.exists():
        return None

    # Tentar busca exata por nome do arquivo KB
    for kb_file in kb_dir.glob("*_kb.json"):
        # Reconstruir o stem original do DXF a partir do nome da KB
        # KB name = safe_dxf_stem + "_kb.json"
        kb_stem = kb_file.stem  # remove .json
        if not kb_stem.endswith("_kb"):
            continue
        # Comparação: sanitizar o dxf_stem e comparar com kb_stem sem "_kb"
        expected_kb_base = kb_stem[:-3]  # remove "_kb"

        # Método 1: sanitização padrão (ASCII only)
        safe_ascii = re.sub(r'[^a-zA-Z0-9._-]', '_', dxf_stem)
        if safe_ascii == expected_kb_base:
            try:
                return json.loads(kb_file.read_text(encoding='utf-8'))
            except Exception:
                return None

        # Método 2: preservar chars latinos (À-ÿ) — para Á, É, etc.
        safe_latin = re.sub(r'[^a-zA-Z0-9._\-\u00C0-\u00FF]', '_', dxf_stem)
        if safe_latin == expected_kb_base:
            try:
                return json.loads(kb_file.read_text(encoding='utf-8'))
            except Exception:
                return None

        # Método 3: comparação após normalizar ambos (colapsa múltiplos _ e trimma)
        norm_stem = re.sub(r'_+', '_', safe_ascii).rstrip('_')
        norm_base = re.sub(r'_+', '_', expected_kb_base).rstrip('_')
        if norm_stem == norm_base:
            try:
                return json.loads(kb_file.read_text(encoding='utf-8'))
            except Exception:
                return None

        # Método 4: strip total de não-ASCII em ambos (resolve º vs °, Á vs  variantes)
        ascii_stem = re.sub(r'[^a-zA-Z0-9_-]', '_', dxf_stem)
        ascii_base = re.sub(r'[^a-zA-Z0-9_-]', '_', expected_kb_base)
        norm4_stem = re.sub(r'_+', '_', ascii_stem).strip('_')
        norm4_base = re.sub(r'_+', '_', ascii_base).strip('_')
        if norm4_stem == norm4_base:
            try:
                return json.loads(kb_file.read_text(encoding='utf-8'))
            except Exception:
                return None

    # Fallback: prefixo seguro (primeiros 25 chars)
    safe_stem = re.sub(r'[^a-zA-Z0-9._-]', '_', dxf_stem)
    prefix = safe_stem[:25]
    matches = sorted(kb_dir.glob(f"{prefix}*_kb.json"))
    if matches:
        try:
            return json.loads(matches[0].read_text(encoding='utf-8'))
        except Exception:
            return None

    return None


def _normalize_pav(pav: str) -> str:
    """Normaliza string de pavimento para comparação."""
    pav = pav.upper().strip()
    # Remove acentos comuns
    pav = pav.replace("°", "").replace("º", "").replace("°", "")
    pav = re.sub(r'\s+', ' ', pav)
    return pav


def _pav_match_score(a: str, b: str) -> float:
    """Score de matching entre duas strings de pavimento (0 a 1)."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Extrai números
    nums_a = set(re.findall(r'\d+', a))
    nums_b = set(re.findall(r'\d+', b))
    if nums_a and nums_b and nums_a & nums_b:
        return 0.8  # Compartilha algum número
    # TERREO, TIPO, COBERTURA
    keywords = {"TERREO", "TERREO", "TIPO", "COBERTURA", "PAV", "PAV."}
    shared_kw = {k for k in keywords if k in a and k in b}
    if shared_kw:
        return 0.5
    return 0.0


# ---------------------------------------------------------------------------
# Contagem de layers no DXF gerado
# ---------------------------------------------------------------------------
def _contar_layers_gerado(dxf_path: Path) -> dict:
    """Conta entidades por layer no DXF gerado."""
    if ezdxf is None:
        return {}
    if not _check_memory(f"leitura {Path(dxf_path).name}"):
        return {}
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        counter = Counter()
        for entity in msp:
            counter[entity.dxf.layer] += 1
        result = dict(counter)
        del doc
        _gc_after_dxf()
        return result
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Scoring principal KB-enhanced
# ---------------------------------------------------------------------------
def score_with_kb(
    kb: dict,
    gerado_path: Path,
    critical_layers: list,
    ids_data: dict | None = None,
    verbose: bool = False,
) -> dict:
    """
    Score 0-100 usando KB semântica + DXF gerado.

    Breakdown:
      - ID match:          30 pts (mesma lógica do legacy)
      - Entity coverage:   40 pts (critical_layers primário + semântica secundária)
      - Layer presence:    20 pts (apenas robot-known layers contam para presença)
      - Anti-hallucination: 10 pts (penaliza CARIMBO_LAYERS e excess)

    Args:
        kb: KB dict carregado por load_kb()
        gerado_path: Path para o DXF gerado
        critical_layers: lista de layers críticos para boost de cobertura
        ids_data: dict com IDs do elemento (de _load_validation_vigas ou similar)
                  Campos usados: gt_count, gerado_count (para subset normalization)

    Returns:
        dict com score e breakdown detalhado
    """
    inventory = kb.get("inventory", {})
    stog_by_layer = inventory.get("by_layer", {})
    stog_total = sum(stog_by_layer.values())
    layer_semantics = kb.get("semantic_analysis", {}).get("layer_semantics", {})
    classe = kb.get("classe", "")
    class_specific = kb.get("class_specific", {})

    gerado_by_layer = _contar_layers_gerado(gerado_path)
    gerado_total = sum(gerado_by_layer.values())

    # --- Subset normalization (igual ao legacy) ---
    # Se STOG cobre mais elementos que o gerado (ex: multi-pavimento vs 1 pavimento),
    # escalar o stog_total proporcionalmente ao ratio de IDs.
    ids_scale = 1.0
    if ids_data:
        stog_id_count = ids_data.get("gt_count", 0)
        gerado_id_count = ids_data.get("gerado_count", 0) or max(gerado_total, 1)
        if stog_id_count > 0 and gerado_id_count > 0 and stog_id_count > 2 * gerado_id_count:
            ids_scale = gerado_id_count / stog_id_count  # < 1.0

    # --- 1. ID match (30 pts) ---
    id_result = _score_id_match(kb, gerado_path, ids_data)

    # --- 2. Entity coverage com critical_layers primário + semântica (40 pts) ---
    coverage_result = _score_coverage_semantic(
        stog_by_layer, gerado_by_layer, stog_total, gerado_total,
        layer_semantics, critical_layers, class_specific, ids_scale=ids_scale
    )

    # --- 3. Layer presence — robot-known + universal layers (20 pts) ---
    presence_result = _score_layer_presence_semantic(
        stog_by_layer, gerado_by_layer, layer_semantics, classe=classe
    )

    # --- 4. Anti-hallucination (10 pts) ---
    hall_result = _score_anti_hallucination(
        stog_by_layer, gerado_by_layer, stog_total, gerado_total
    )

    score_total = round(min(
        id_result["score"] +
        coverage_result["score"] +
        presence_result["score"] +
        hall_result["score"],
        100.0
    ), 1)

    result = {
        "score": score_total,
        "scorer": "kb-enhanced",
        "kb_file": kb.get("file", ""),
        "kb_pavimento": kb.get("pavimento", ""),
        "stog_entities": stog_total,
        "gerado_entities": gerado_total,
        "details": {
            "id_match":           id_result,
            "entity_coverage":    coverage_result,
            "layer_presence":     presence_result,
            "anti_hallucination": hall_result,
        }
    }

    if verbose:
        print(f"  [KB-SCORE] {score_total}/100 | "
              f"ID={id_result['score']:.1f} "
              f"COV={coverage_result['score']:.1f} "
              f"PRE={presence_result['score']:.1f} "
              f"HALL={hall_result['score']:.1f}")

    return result


def _score_id_match(kb: dict, gerado_path: Path, ids_data: dict | None) -> dict:
    """30 pts — fração dos IDs gerados que existem no STOG KB."""
    if not ids_data:
        # Sem dados de ID — neutro
        return {"score": 15.0, "max": 30, "id_match_rate": None, "note": "no_ids_data"}

    # IDs esperados do STOG via KB text_content
    tc = kb.get("text_content", {})
    # nomenclaturas_detected é lista de dicts {content, layer, insert}
    raw_noms = tc.get("nomenclaturas_detected", [])
    stog_ids_raw = set(
        n["content"] if isinstance(n, dict) else n
        for n in raw_noms
        if n  # ignora vazios
    )
    gerado_ids = set(ids_data.get("gerado_ids", []))

    if not gerado_ids:
        return {"score": 15.0, "max": 30, "id_match_rate": None, "note": "no_gerado_ids"}

    if stog_ids_raw:
        matched = len(gerado_ids & stog_ids_raw)
        rate = matched / len(gerado_ids)
    else:
        # KB não tem IDs extraídos — usar fallback de ids_data
        stog_ids_fallback = set(ids_data.get("stog_ids", []))
        if stog_ids_fallback:
            matched = len(gerado_ids & stog_ids_fallback)
            rate = matched / len(gerado_ids)
        else:
            return {"score": 15.0, "max": 30, "id_match_rate": None, "note": "no_stog_ids"}

    score = rate * 30.0
    # Penalizar hallucination de IDs (IDs gerados que não existem no STOG)
    hallucinated = len(gerado_ids - stog_ids_raw) if stog_ids_raw else 0
    hall_rate = hallucinated / len(gerado_ids) if gerado_ids else 0
    score = max(0, score - hall_rate * 10.0)

    return {
        "score": round(score, 1),
        "max": 30,
        "id_match_rate": round(rate, 4),
        "hallucinated_ids": hallucinated,
        "hall_rate": round(hall_rate, 4),
    }


def _score_coverage_semantic(
    stog_by_layer: dict,
    gerado_by_layer: dict,
    stog_total: int,
    gerado_total: int,
    layer_semantics: dict,
    critical_layers: list,
    class_specific: dict,
    ids_scale: float = 1.0,
) -> dict:
    """
    40 pts — cobertura de entidades.

    Estratégia dual (igual ao legacy, mas com boost semântico):
      - Primário (70%): critical_layers — mesmos que o legacy usa
      - Secundário (30%): global ratio (com subset normalization via ids_scale)

    ids_scale < 1.0 quando STOG tem mais elementos que o gerado (subset generation).
    """
    if not stog_by_layer:
        return {"score": 20.0, "max": 40, "note": "no_stog_layers"}

    # Aplicar subset normalization no stog_total
    stog_total_norm = max(stog_total * ids_scale, 1) if ids_scale < 1.0 else stog_total
    global_ratio = min(gerado_total / stog_total_norm, 1.0)

    # Boost: layers universais cross-obra recebem peso máximo
    classe = class_specific.get("classe_generica", "")
    universal_layers = get_universal_layers(classe, min_obras=12) if classe else set()

    # --- Primário: critical_layers (igual ao legacy) ---
    crit_ratios = []
    layer_details = {}
    for layer in critical_layers:
        s = stog_by_layer.get(layer, 0)
        g = gerado_by_layer.get(layer, 0)
        if s > 0:
            s_norm = s * ids_scale if ids_scale < 1.0 else s
            ratio = min(g / max(s_norm, 1), 1.0)
            crit_ratios.append(ratio)
            layer_details[layer] = {"stog": s, "gerado": g, "ratio": round(ratio, 3), "critical": True}

    crit_avg = (sum(crit_ratios) / len(crit_ratios)) if crit_ratios else global_ratio

    # --- Secundário KB: layers robot-known ou universais não-críticos ---
    kb_bonus_ratios = []
    for layer, count in stog_by_layer.items():
        if layer in CARIMBO_LAYERS or layer in critical_layers:
            continue
        sem = layer_semantics.get(layer, {})
        source = sem.get("source", "unknown")
        # Universal layers (aparecem em 12+ obras) têm peso máximo
        if layer in universal_layers:
            weight = 1.0
        elif source in ("robot", "pattern_match"):
            weight = SOURCE_WEIGHTS.get(source, 0.7)
        else:
            continue  # Ignorar layers não-confirmados
        if count < 5:
            continue
        g = gerado_by_layer.get(layer, 0)
        s_norm = count * ids_scale if ids_scale < 1.0 else count
        ratio = min(g / max(s_norm, 1), 1.0)
        kb_bonus_ratios.append(ratio * weight)
        layer_details[layer] = {"stog": count, "gerado": g, "ratio": round(ratio, 3), "critical": False, "universal": layer in universal_layers}

    # Se temos bonus KB, usar blended entre crit_avg e kb_bonus
    if kb_bonus_ratios:
        kb_avg = sum(kb_bonus_ratios) / len(kb_bonus_ratios)
        primary = 0.80 * crit_avg + 0.20 * kb_avg  # KB como ajuste menor
    else:
        primary = crit_avg

    # Blended final: 70% critical/kb + 30% global_ratio
    blended = 0.70 * primary + 0.30 * global_ratio
    score = blended * 40.0

    return {
        "score": round(score, 1),
        "max": 40,
        "crit_avg": round(crit_avg, 4),
        "global_ratio": round(global_ratio, 4),
        "ids_scale": round(ids_scale, 4),
        "critical_layers_count": len(crit_ratios),
        "kb_bonus_layers": len(kb_bonus_ratios),
        "layer_details": layer_details,
    }


def _score_layer_presence_semantic(
    stog_by_layer: dict,
    gerado_by_layer: dict,
    layer_semantics: dict,
    classe: str = "",
) -> dict:
    """
    20 pts — presença de layers, mas apenas os robot-known contam.

    Autonomous discovery layers (carimbo, 00-FELIPE) não devem estar
    no gerado — não penalizar sua ausência.

    Universal layers (aparecem em 12+ obras) são sempre obrigatórios,
    independente do source no KB.
    """
    # Layers universais cross-obra: sempre obrigatórios (peso máximo)
    universal_layers = get_universal_layers(classe, min_obras=12) if classe else set()

    def _is_non_stog(layer: str) -> bool:
        """Retorna True se o layer não deve ser exigido no gerado."""
        if layer in CARIMBO_LAYERS or layer in NON_STOG_REQUIRED:
            return True
        if any(layer.startswith(p) for p in NON_STOG_PREFIXES):
            return True
        return False

    # Layers robot/pattern_match do KB atual (excluindo não-STOG)
    kb_required = {
        layer for layer, sem in layer_semantics.items()
        if sem.get("source") in ("robot", "pattern_match")
        and not _is_non_stog(layer)
        and stog_by_layer.get(layer, 0) > 5
    }

    # Layers universais presentes no STOG desta obra (com >5 entidades)
    universal_required = {
        layer for layer in universal_layers
        if not _is_non_stog(layer)
        and stog_by_layer.get(layer, 0) > 5
    }

    # União: KB required + universal required
    required_set = kb_required | universal_required
    required_layers = list(required_set)

    if not required_layers:
        # Fallback: usar todos os layers do STOG (exceto carimbo e não-STOG)
        required_layers = [
            l for l in stog_by_layer
            if not _is_non_stog(l) and stog_by_layer[l] > 5
        ]

    if not required_layers:
        return {"score": 10.0, "max": 20, "note": "no_required_layers"}

    gerado_set = set(gerado_by_layer.keys())
    present = [l for l in required_layers if l in gerado_set]
    missing = [l for l in required_layers if l not in gerado_set]

    presence_ratio = len(present) / len(required_layers)
    score = presence_ratio * 20.0

    return {
        "score": round(score, 1),
        "max": 20,
        "present": len(present),
        "missing": len(missing),
        "required_layers": len(required_layers),
        "missing_list": missing[:10],  # Top 10 ausentes
    }


def _score_anti_hallucination(
    stog_by_layer: dict,
    gerado_by_layer: dict,
    stog_total: int,
    gerado_total: int,
) -> dict:
    """
    10 pts — penaliza:
      1. Excesso de entidades (gerado >> stog)
      2. Layers de carimbo presentes no gerado (não devem estar lá)
    """
    score = 10.0

    # Penalizar excess (gerado muito maior que stog)
    if stog_total > 0:
        ratio = gerado_total / stog_total
        if ratio > 2.0:
            excess_penalty = min((ratio - 2.0) * 2.0, 5.0)
            score -= excess_penalty

    # Penalizar carimbo layers no gerado
    carimbo_in_gerado = [l for l in CARIMBO_LAYERS if l in gerado_by_layer]
    if carimbo_in_gerado:
        score -= len(carimbo_in_gerado) * 1.5

    return {
        "score": round(max(score, 0.0), 1),
        "max": 10,
        "gerado_stog_ratio": round(gerado_total / max(stog_total, 1), 3),
        "carimbo_layers_in_gerado": carimbo_in_gerado,
    }


# ---------------------------------------------------------------------------
# Comparação direta KB vs KB (para cross-obra benchmarking)
# ---------------------------------------------------------------------------
def compare_kb_to_kb(stog_kb: dict, gerado_kb: dict) -> dict:
    """
    Compara dois KBs diretamente (ambos gerados pelo extrator).
    Útil para benchmarking cross-obra sem precisar do DXF gerado.

    Retorna dict com score e análise de divergência de layers.
    """
    stog_inv = stog_kb.get("inventory", {})
    gerado_inv = gerado_kb.get("inventory", {})

    stog_layers = stog_inv.get("by_layer", {})
    gerado_layers = gerado_inv.get("by_layer", {})

    stog_types = stog_inv.get("by_type", {})
    gerado_types = gerado_inv.get("by_type", {})

    # Layer comparison
    all_layers = set(stog_layers) | set(gerado_layers)
    layer_diffs = {}
    for layer in all_layers:
        s = stog_layers.get(layer, 0)
        g = gerado_layers.get(layer, 0)
        if s == 0 and g == 0:
            continue
        ratio = g / max(s, 1)
        layer_diffs[layer] = {
            "stog": s,
            "gerado": g,
            "ratio": round(ratio, 3),
            "delta": g - s,
        }

    # Type comparison
    type_diffs = {}
    all_types = set(stog_types) | set(gerado_types)
    for t in all_types:
        s = stog_types.get(t, 0)
        g = gerado_types.get(t, 0)
        if s == 0 and g == 0:
            continue
        type_diffs[t] = {
            "stog": s,
            "gerado": g,
            "ratio": round(g / max(s, 1), 3),
        }

    # Aggregate score
    total_stog = stog_inv.get("total_entities", 0)
    total_gerado = gerado_inv.get("total_entities", 0)
    overall_ratio = total_gerado / max(total_stog, 1)

    return {
        "stog_file": stog_kb.get("file", ""),
        "gerado_file": gerado_kb.get("file", ""),
        "classe": stog_kb.get("classe", ""),
        "stog_entities": total_stog,
        "gerado_entities": total_gerado,
        "overall_ratio": round(overall_ratio, 3),
        "layer_diffs": layer_diffs,
        "type_diffs": type_diffs,
    }


# ---------------------------------------------------------------------------
# Baselines cross-obra (carrega summary de múltiplas obras)
# ---------------------------------------------------------------------------
def build_cross_obra_baselines(obras_base_path: Path) -> dict:
    """
    Constrói baselines de entity counts por classe, agregando todas as obras
    que já têm KB em Fase-0_STOG_KB/obra_summary.json.

    Retorna:
        {
          "FV": {"entity_median": 748, "entity_p10": 540, "entity_p90": 986, ...},
          "LV": {...},
          ...
        }
    """
    from statistics import median, quantiles

    per_class = {}
    summaries_found = 0

    for obra_dir in sorted(obras_base_path.iterdir()):
        summary_path = obra_dir / "Fase-0_STOG_KB" / "obra_summary.json"
        if not summary_path.exists():
            continue
        try:
            with open(summary_path, encoding="utf-8") as f:
                summary = json.load(f)
        except Exception:
            continue
        summaries_found += 1

        by_class = summary.get("by_class", {})
        for classe, data in by_class.items():
            if classe not in per_class:
                per_class[classe] = {"total_entities": [], "file_counts": [], "layers_seen": {}}
            count = data.get("count", 0)
            total_ents = data.get("total_entities", 0)
            if count > 0 and total_ents > 0:
                per_class[classe]["total_entities"].append(total_ents // count)  # per-file avg
                per_class[classe]["file_counts"].append(count)
            # Aggregate layers
            for layer, cnt in data.get("all_layers", {}).items():
                per_class[classe]["layers_seen"][layer] = \
                    per_class[classe]["layers_seen"].get(layer, 0) + 1

    baselines = {"obras_analyzed": summaries_found}
    for classe, data in per_class.items():
        ents = data["total_entities"]
        if len(ents) < 2:
            continue
        q = quantiles(ents, n=10)  # deciles
        baselines[classe] = {
            "entity_per_file": {
                "median": round(median(ents)),
                "p10": round(q[0]),
                "p90": round(q[-1]),
                "min": min(ents),
                "max": max(ents),
            },
            "layers_seen_in_n_obras": {
                layer: count
                for layer, count in sorted(
                    data["layers_seen"].items(),
                    key=lambda x: -x[1]
                )
            },
            "obras_with_class": len(ents),
        }

    return baselines


# ---------------------------------------------------------------------------
# CLI — diagnóstico e teste
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse, sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="KB Scorer — diagnóstico e teste")
    sub = parser.add_subparsers(dest="cmd")

    # Mostrar KB de uma obra/classe/pavimento
    sp_show = sub.add_parser("show-kb", help="Mostrar KB para obra/classe/pavimento")
    sp_show.add_argument("--obra", required=True)
    sp_show.add_argument("--classe", required=True)
    sp_show.add_argument("--pavimento", default="")

    # Baselines cross-obra
    sp_base = sub.add_parser("baselines", help="Construir baselines cross-obra")
    sp_base.add_argument("--obras-path", default="D:/Agente-cad-PYSIDE/DADOS-OBRAS")

    # Score KB vs gerado
    sp_score = sub.add_parser("score", help="Score KB vs DXF gerado")
    sp_score.add_argument("--obra", required=True)
    sp_score.add_argument("--classe", required=True)
    sp_score.add_argument("--pavimento", required=True)
    sp_score.add_argument("--gerado", required=True)

    args = parser.parse_args()

    if args.cmd == "show-kb":
        obra_path = Path(args.obra)
        kb = load_kb(obra_path, args.classe, args.pavimento)
        if kb:
            print(f"KB encontrada: {kb.get('file')}")
            print(f"  Pavimento: {kb.get('pavimento')}")
            inv = kb.get("inventory", {})
            print(f"  Total entidades: {inv.get('total_entities', inv.get('by_layer', {}))}")
            sa = kb.get("semantic_analysis", {})
            ls = sa.get("layer_semantics", {})
            print(f"  Layers semânticos: {len(ls)}")
            for layer, sem in list(ls.items())[:5]:
                print(f"    {layer}: {sem.get('role')} [{sem.get('source')}]")
        else:
            print(f"KB não encontrada para {args.classe}/{args.pavimento} em {args.obra}")

    elif args.cmd == "baselines":
        obras_path = Path(args.obras_path)
        baselines = build_cross_obra_baselines(obras_path)
        print(f"Obras analisadas: {baselines.get('obras_analyzed', 0)}")
        for classe in sorted(k for k in baselines if k != "obras_analyzed"):
            b = baselines[classe]
            ents = b.get("entity_per_file", {})
            print(f"\n{classe}: {b.get('obras_with_class')} obras | "
                  f"entities/file: median={ents.get('median')} "
                  f"[p10={ents.get('p10')}, p90={ents.get('p90')}]")
            top_layers = list(b.get("layers_seen_in_n_obras", {}).items())[:8]
            print(f"  Layers mais comuns: {top_layers}")

    elif args.cmd == "score":
        obra_path = Path(args.obra)
        gerado_path = Path(args.gerado)
        kb = load_kb(obra_path, args.classe, args.pavimento)
        if not kb:
            print(f"KB não encontrada — use o extrator primeiro")
            sys.exit(1)
        from fidelidade_vigas import CRITICAL_LAYERS_LV, CRITICAL_LAYERS_FV
        crit = CRITICAL_LAYERS_LV if args.classe == "LV" else CRITICAL_LAYERS_FV
        result = score_with_kb(kb, gerado_path, crit, verbose=True)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    else:
        parser.print_help()
