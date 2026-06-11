#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stog_intelligence_extractor.py — EPIC-STOG-2
==============================================
Extrator granular de STOGs reais do escritório de engenharia.

Filosofia: explorar cada STOG como terreno desconhecido.
  - Extrai TUDO sem pré-filtrar por tipo ou layer
  - Cross-referencia com robôs SCR para semântica (guia, não prisão)
  - Reporta descobertas autônomas (layers/entidades inesperados)
  - Produz KB JSON por elemento, pronto para RAG e fidelidade

Uso:
  # Analisar um arquivo STOG
  python scripts/stog_intelligence_extractor.py \
      --dxf "DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/ALIMONTI - PARAISO - 1° PAV.- FV - R00.dxf"

  # Analisar obra inteira (todos os STOGs de um pavimento)
  python scripts/stog_intelligence_extractor.py \
      --obra "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1" \
      --pavimento "1° PAV"

  # Analisar obra inteira (todos os pavimentos)
  python scripts/stog_intelligence_extractor.py \
      --obra "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1" --all-pavimentos

Saída:
  {obra}/Fase-0_STOG_KB/{classe}/{pavimento}_{filename_base}_kb.json
  {obra}/Fase-0_STOG_KB/obra_summary.json
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import argparse
import re
import math
from pathlib import Path
from datetime import datetime

try:
    import ezdxf
    from ezdxf.math import Vec2, Vec3
except ImportError:
    print("[ERRO] ezdxf não encontrado. Instale: pip install ezdxf")
    sys.exit(1)

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Semântica de referência — baseada nos robôs SCR reais (_ROBOS_ABAS/)
# NÃO são schemas rígidos — são guias para inferência semântica
# ---------------------------------------------------------------------------
ROBOT_REFERENCE = {
    "FV": {
        "robot": "_ROBOS_ABAS/Robo_Fundos_de_Vigas/compactador-producao/Robo_fundos_TASF_limpo_copy_22.py",
        "expected_layers": {"Painéis", "SARR_2.2x7", "NOMENCLATURA", "5", "COTA", "HACHURACONCRETO"},
        "expected_no_inserts": True,
        "custom_commands": ["ex2", "Bextend", "app3", "ABFET", "HHHH"],
        "sarrafo_layers_pattern": re.compile(r'SARR', re.I),
    },
    "LV": {
        "robot": "_ROBOS_ABAS/Robo_Laterais_de_Vigas/robo_laterais_viga_limpo233.py",
        "expected_layers": {"Painéis", "SARR_2.2x7", "NOMENCLATURA", "5", "COTA"},
        "panel_types": ["sarrafeado", "grade"],
        "sarrafo_layers_pattern": re.compile(r'SARR', re.I),
        "has_inserts": True,
    },
    "LJ": {
        "robot": "_ROBOS_ABAS/Robo_Lajes/laje_src/services/gerar_script_scr.py",
        "expected_layers": {"concreto", "texto_nome", "texto_pavimento_laje", "cota", "texto_reaproveitamento", "Painéis"},
        "confirmed_no_sarrafos": True,
        "has_hlaz": True,
        "reaproveitamento_pattern": re.compile(r'^(hh+)$', re.I),
    },
    "PL": {
        "robot": "_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src/robots/",
        "subtypes": ["CIMA", "ABCD", "GRADES"],
        "expected_layers": {"Painéis", "COTA", "NOMENCLATURA", "Texto Seção", "Hachura"},
        "sarrafo_layers_pattern": re.compile(r'SARR', re.I),
        "has_inserts_abcd": True,
    },
    "GF": {
        "description": "Grades de Fundo — armação de fundo de viga",
        "expected_layers": {"Painéis", "COTA", "NOMENCLATURA"},
        "sarrafo_layers_pattern": re.compile(r'SARR', re.I),
    },
    "GD": {
        "description": "Grades Diagonais/Detalhes de armação",
        "expected_layers": set(),
        "sarrafo_layers_pattern": re.compile(r'SARR', re.I),
    },
}

# ---------------------------------------------------------------------------
# Utilitários geométricos
# ---------------------------------------------------------------------------

def _safe_point(pt) -> list:
    """Converte ponto ezdxf para [x, y], tolerante a None."""
    try:
        return [round(float(pt.x), 4), round(float(pt.y), 4)]
    except Exception:
        try:
            return [round(float(pt[0]), 4), round(float(pt[1]), 4)]
        except Exception:
            return [0.0, 0.0]


def _line_length(start, end) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    return round(math.sqrt(dx*dx + dy*dy), 4)


def _line_angle_deg(start, end) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    return round(math.degrees(math.atan2(dy, dx)), 2)


def _pline_bbox(vertices: list) -> dict:
    if not vertices:
        return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    mn_x, mx_x = min(xs), max(xs)
    mn_y, mx_y = min(ys), max(ys)
    return {
        "min_x": round(mn_x, 4), "min_y": round(mn_y, 4),
        "max_x": round(mx_x, 4), "max_y": round(mx_y, 4),
        "width": round(mx_x - mn_x, 4), "height": round(mx_y - mn_y, 4)
    }


def _pline_perimeter(vertices: list, closed: bool = False) -> float:
    total = 0.0
    for i in range(len(vertices) - 1):
        total += _line_length(vertices[i], vertices[i+1])
    if closed and len(vertices) >= 2:
        total += _line_length(vertices[-1], vertices[0])
    return round(total, 4)


# ---------------------------------------------------------------------------
# Extratores por tipo de entidade
# ---------------------------------------------------------------------------

def _extract_line(e) -> dict:
    start = _safe_point(e.dxf.start)
    end = _safe_point(e.dxf.end)
    length = _line_length(start, end)
    angle = _line_angle_deg(start, end)
    return {
        "type": "LINE",
        "layer": e.dxf.layer,
        "start": start,
        "end": end,
        "length": length,
        "angle_deg": angle,
        "is_horizontal": abs(angle) < 5 or abs(angle - 180) < 5,
        "is_vertical": abs(abs(angle) - 90) < 5,
    }


def _extract_lwpolyline(e) -> dict:
    try:
        pts = [[round(v[0], 4), round(v[1], 4)] for v in e.get_points()]
    except Exception:
        pts = []
    closed = bool(e.closed)
    bbox = _pline_bbox(pts)
    perim = _pline_perimeter(pts, closed)
    return {
        "type": "LWPOLYLINE",
        "layer": e.dxf.layer,
        "vertices": pts,
        "vertex_count": len(pts),
        "is_closed": closed,
        "perimeter": perim,
        "bbox": bbox,
    }


def _extract_text(e) -> dict:
    try:
        content = e.dxf.text
    except Exception:
        content = ""
    return {
        "type": "TEXT",
        "layer": e.dxf.layer,
        "content": content,
        "insert": _safe_point(e.dxf.insert),
        "height": round(float(e.dxf.height), 4) if hasattr(e.dxf, "height") else None,
        "rotation": round(float(e.dxf.rotation), 2) if hasattr(e.dxf, "rotation") else 0.0,
    }


def _extract_mtext(e) -> dict:
    try:
        content = e.text  # processa tags MTEXT
    except Exception:
        try:
            content = e.dxf.text
        except Exception:
            content = ""
    # remover tags de formatação comuns
    content_clean = re.sub(r'\\[A-Za-z][^;]*;|[{}]|\\P', ' ', content).strip()
    return {
        "type": "MTEXT",
        "layer": e.dxf.layer,
        "content": content,
        "content_clean": content_clean,
        "insert": _safe_point(e.dxf.insert) if hasattr(e.dxf, "insert") else [0, 0],
        "height": round(float(e.dxf.char_height), 4) if hasattr(e.dxf, "char_height") else None,
    }


def _extract_dimension(e) -> dict:
    try:
        measurement = e.get_measurement()
        if measurement is not None:
            measurement = round(float(measurement), 4)
    except Exception:
        measurement = None
    try:
        text_override = e.dxf.text
    except Exception:
        text_override = ""
    try:
        defpoint = _safe_point(e.dxf.defpoint)
    except Exception:
        defpoint = [0, 0]
    return {
        "type": "DIMENSION",
        "layer": e.dxf.layer,
        "dimtype": int(e.dxf.dimtype) if hasattr(e.dxf, "dimtype") else None,
        "text_override": text_override,
        "measurement": measurement,
        "defpoint": defpoint,
    }


def _extract_insert(e) -> dict:
    return {
        "type": "INSERT",
        "layer": e.dxf.layer,
        "block_name": e.dxf.name,
        "insert_point": _safe_point(e.dxf.insert),
        "scale_x": round(float(e.dxf.xscale), 4) if hasattr(e.dxf, "xscale") else 1.0,
        "scale_y": round(float(e.dxf.yscale), 4) if hasattr(e.dxf, "yscale") else 1.0,
        "rotation": round(float(e.dxf.rotation), 2) if hasattr(e.dxf, "rotation") else 0.0,
    }


def _extract_hatch(e) -> dict:
    try:
        pattern = e.dxf.pattern_name
    except Exception:
        pattern = ""
    try:
        paths_count = len(e.paths)
    except Exception:
        paths_count = 0
    # Estimar bbox do hatch pelo boundary path
    all_pts = []
    try:
        for path in e.paths:
            try:
                for edge in path.edges:
                    if hasattr(edge, 'start'):
                        all_pts.append(_safe_point(edge.start))
                    if hasattr(edge, 'end'):
                        all_pts.append(_safe_point(edge.end))
            except Exception:
                pass
    except Exception:
        pass
    bbox = _pline_bbox(all_pts) if all_pts else None
    return {
        "type": "HATCH",
        "layer": e.dxf.layer,
        "pattern_name": pattern,
        "paths_count": paths_count,
        "bbox": bbox,
    }


def _extract_arc(e) -> dict:
    return {
        "type": "ARC",
        "layer": e.dxf.layer,
        "center": _safe_point(e.dxf.center),
        "radius": round(float(e.dxf.radius), 4),
        "start_angle": round(float(e.dxf.start_angle), 2),
        "end_angle": round(float(e.dxf.end_angle), 2),
    }


def _extract_circle(e) -> dict:
    return {
        "type": "CIRCLE",
        "layer": e.dxf.layer,
        "center": _safe_point(e.dxf.center),
        "radius": round(float(e.dxf.radius), 4),
    }


def _extract_mline(e) -> dict:
    return {
        "type": "MLINE",
        "layer": e.dxf.layer,
        "start": _safe_point(e.dxf.start_point) if hasattr(e.dxf, "start_point") else [0, 0],
    }


def _extract_leader(e) -> dict:
    try:
        verts = [_safe_point(v) for v in e.vertices]
    except Exception:
        verts = []
    return {
        "type": "LEADER",
        "layer": e.dxf.layer,
        "vertices": verts,
    }


def _extract_generic(e) -> dict:
    """Fallback para tipos desconhecidos — captura o que for possível."""
    data = {"type": e.dxftype(), "layer": e.dxf.layer}
    for attr in ("insert", "start", "end", "center", "text"):
        try:
            val = getattr(e.dxf, attr)
            data[attr] = _safe_point(val) if hasattr(val, "x") else str(val)
        except Exception:
            pass
    return data


# ---------------------------------------------------------------------------
# Dispatcher principal
# ---------------------------------------------------------------------------

def _extract_entity(e) -> dict:
    t = e.dxftype()
    try:
        if t == "LINE":
            return _extract_line(e)
        elif t in ("LWPOLYLINE", "POLYLINE"):
            return _extract_lwpolyline(e)
        elif t == "TEXT":
            return _extract_text(e)
        elif t == "MTEXT":
            return _extract_mtext(e)
        elif t == "DIMENSION":
            return _extract_dimension(e)
        elif t == "INSERT":
            return _extract_insert(e)
        elif t == "HATCH":
            return _extract_hatch(e)
        elif t == "ARC":
            return _extract_arc(e)
        elif t == "CIRCLE":
            return _extract_circle(e)
        elif t == "MLINE":
            return _extract_mline(e)
        elif t == "LEADER":
            return _extract_leader(e)
        else:
            return _extract_generic(e)
    except Exception as ex:
        return {"type": t, "layer": getattr(e.dxf, "layer", "?"), "_extraction_error": str(ex)}


# ---------------------------------------------------------------------------
# Detecção de classe e pavimento a partir do nome do arquivo
# ---------------------------------------------------------------------------

CLASS_PATTERN = re.compile(
    r'\b(FV|LV|LJ|PL|GF|GD|VC)\b', re.I
)
PAV_PATTERN = re.compile(
    r'(\d+°?\s*(?:PAV|PV)(?:\w*)?|TIPO|COBERTURA|TERREO|TÉRREO)',
    re.I
)


def detect_class_from_filename(filename: str) -> str:
    """Detecta classe estrutural do nome do arquivo STOG."""
    m = CLASS_PATTERN.search(filename)
    return m.group(1).upper() if m else "UNKNOWN"


def detect_pavimento_from_filename(filename: str) -> str:
    """Detecta pavimento do nome do arquivo."""
    m = PAV_PATTERN.search(filename)
    return m.group(0).strip().upper() if m else "UNKNOWN"


# ---------------------------------------------------------------------------
# Análise semântica por classe
# ---------------------------------------------------------------------------

def _classify_layer_semantics(layer: str, classe: str, entity_types_in_layer: set) -> dict:
    """
    Infere semântica de um layer.
    Retorna: {role, confidence, source, notes}
    """
    ref = ROBOT_REFERENCE.get(classe, {})
    expected = ref.get("expected_layers", set())
    sarr_pat = ref.get("sarrafo_layers_pattern")

    # Layers conhecidos pelos robôs
    known_semantics = {
        "Painéis":           ("painel_estrutural_principal", "high", "robot"),
        "SARR_2.2x7":        ("sarrafo_2.2x7cm", "high", "robot"),
        "SARR_3.5x7":        ("sarrafo_3.5x7cm", "high", "inference"),
        "SARR_7x7":          ("sarrafo_7x7cm", "high", "inference"),
        "SARR_2.2x10":       ("sarrafo_2.2x10cm", "high", "inference"),
        "SARR_EDITAR":       ("sarrafo_a_editar", "medium", "inference"),
        "SARRAFO DE PRESSAO":("sarrafo_de_pressao", "high", "inference"),
        "Sarrafo de Pressão":("sarrafo_de_pressao", "high", "inference"),
        "NOMENCLATURA":      ("nomenclatura_elemento", "high", "robot"),
        "COTA":              ("cota_dimensional", "high", "robot"),
        "Cotas":             ("cota_dimensional", "high", "inference"),
        "5":                 ("layer_5_escopo_desconhecido", "low", "robot"),
        "HACHURACONCRETO":   ("hachura_concreto_fv", "high", "robot"),
        "Hachura":           ("hachura_concreto", "high", "inference"),
        "Texto Seção":       ("texto_de_secao", "high", "inference"),
        "CONCRETO":          ("concreto", "high", "inference"),
        "Madeira":           ("elemento_madeira", "high", "inference"),
        "CARIMBO":           ("carimbo_folha", "high", "inference"),
        "REAPROVEITAMENTO":  ("reaproveitamento_painel", "high", "inference"),
        "barrote":           ("barrote", "high", "inference"),
        "presilha":          ("presilha", "high", "inference"),
        "CHAPA":             ("chapa_metalica", "high", "inference"),
        "MEIO_PONT":         ("meio_pontalete", "medium", "inference"),
        "Perfil Metálico":   ("perfil_metalico", "high", "inference"),
        "TENSOR":            ("tensor", "high", "inference"),
        "TEXTO_GERAL":       ("texto_geral", "medium", "inference"),
        "texto":             ("texto_geral", "medium", "inference"),
        "Romaneio":          ("romaneio_material", "high", "inference"),
        "SCO-___-LAJ":       ("sco_laje", "medium", "inference"),
        "detalhes":          ("detalhes_construtivos", "medium", "inference"),
        "AUX00":             ("auxiliar", "low", "inference"),
        "0":                 ("layer_0_default_autocad", "high", "inference"),
        "FOLHA MB":          ("folha_mb", "medium", "inference"),
        "Sarr 2.2x7":        ("sarrafo_2.2x7cm_alternativo", "high", "inference"),
        "SARR_3.5x7":        ("sarrafo_3.5x7cm", "high", "inference"),
        "concreto":          ("painel_concreto_laje", "high", "robot"),
        "texto_nome":        ("nome_da_laje", "high", "robot"),
        "texto_pavimento_laje": ("pavimento_da_laje", "high", "robot"),
        "cota":              ("cota_dimensional", "high", "robot"),
        "texto_reaproveitamento": ("indicador_reaproveitamento", "high", "robot"),
    }

    # Layers numéricos (comuns em lajes)
    if re.match(r'^\d+$', layer):
        return {
            "role": f"layer_numerico_{layer}",
            "confidence": "medium",
            "source": "inference",
            "notes": f"Layer numérico — possível código interno do escritório. {len(entity_types_in_layer)} tipos de entidade."
        }

    # Layers de pavimento (ex: "NIVEL 1° PAV.")
    if re.search(r'NIVEL|PAV\.|PAVIMENTO', layer, re.I):
        return {
            "role": "nivel_pavimento",
            "confidence": "high",
            "source": "inference",
            "notes": f"Layer de nível de pavimento: {layer}"
        }

    if layer in known_semantics:
        role, conf, src = known_semantics[layer]
        in_expected = layer in expected
        return {
            "role": role,
            "confidence": conf,
            "source": src,
            "in_robot_expected": in_expected,
        }

    # SARR pattern genérico
    if sarr_pat and sarr_pat.search(layer):
        return {
            "role": f"sarrafo_{layer.lower()}",
            "confidence": "medium",
            "source": "pattern_match",
            "notes": "Matched SARR pattern — sarrafo de dimensão não catalogada"
        }

    # Layer autônomo — não reconhecido
    return {
        "role": "UNKNOWN_AUTONOMOUS_DISCOVERY",
        "confidence": "low",
        "source": "autonomous",
        "notes": f"Layer não nos robôs. Entidades: {sorted(entity_types_in_layer)}. Requer análise manual."
    }


def _detect_lv_type(layers_present: set) -> str:
    """Detecta tipo de painel LV: sarrafeado vs grade."""
    sarr_layers = {l for l in layers_present if re.search(r'SARR', l, re.I)}
    if sarr_layers:
        return "sarrafeado"
    # Grade: muitas LINEs sem sarrafos — detectado via entity analysis
    return "grade_ou_desconhecido"


def _check_class_anomalies(classe: str, types_count: dict, layers_count: dict) -> list:
    """Detecta anomalias específicas por classe."""
    anomalies = []
    ref = ROBOT_REFERENCE.get(classe, {})

    if classe == "FV":
        if types_count.get("INSERT", 0) > 0:
            anomalies.append({
                "type": "INSERT_EM_FV",
                "severity": "info",  # Obra-específico: TREINO_5 confirmou FV com INSERTs válidos
                "description": f"FV com INSERT blocks (obra-específico — não é anomalia crítica): {types_count['INSERT']}",
                "count": types_count["INSERT"]
            })

    if classe == "LJ":
        sarr = {l: c for l, c in layers_count.items() if re.search(r'SARR', l, re.I)}
        if sarr:
            anomalies.append({
                "type": "SARRAFO_EM_LAJE",
                "severity": "critical",
                "description": f"Laje NÃO deve ter sarrafos! Encontrado em layers: {sarr}",
                "layers": sarr
            })

    return anomalies


# ---------------------------------------------------------------------------
# Extrator principal de um arquivo DXF
# ---------------------------------------------------------------------------

def extract_stog(dxf_path: Path, output_dir: Path | None = None) -> dict:
    """
    Extrai KB granular de um arquivo DXF STOG.
    Retorna dict com knowledge base completa.
    """
    filename = dxf_path.name
    classe = detect_class_from_filename(filename)
    pavimento = detect_pavimento_from_filename(filename)

    print(f"\n[STOG-INTEL] Extraindo: {filename}")
    print(f"  Classe detectada: {classe} | Pavimento: {pavimento}")

    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as ex:
        return {"error": f"Falha ao abrir DXF: {ex}", "file": str(dxf_path)}

    msp = doc.modelspace()

    # --- Passo 1: Inventário completo ---
    entities_raw = []
    types_count = {}
    layers_count = {}
    layers_types = {}  # layer -> set of entity types

    for entity in msp:
        t = entity.dxftype()
        l = entity.dxf.layer
        types_count[t] = types_count.get(t, 0) + 1
        layers_count[l] = layers_count.get(l, 0) + 1
        layers_types.setdefault(l, set()).add(t)
        extracted = _extract_entity(entity)
        entities_raw.append(extracted)

    total_entities = len(entities_raw)
    print(f"  Total entidades: {total_entities}")
    print(f"  Tipos: {dict(sorted(types_count.items(), key=lambda x: -x[1]))}")
    print(f"  Layers ({len(layers_count)}): {list(layers_count.keys())[:10]}{'...' if len(layers_count) > 10 else ''}")

    # --- Passo 2: Análise semântica de layers ---
    semantic_dict = {}
    autonomous_discoveries = []
    known_layers = []

    ref = ROBOT_REFERENCE.get(classe, {})
    expected_layers = ref.get("expected_layers", set())

    for layer, count in layers_count.items():
        sem = _classify_layer_semantics(layer, classe, layers_types[layer])
        sem["count"] = count
        sem["entity_types"] = sorted(layers_types[layer])
        semantic_dict[layer] = sem

        if sem["source"] == "autonomous":
            autonomous_discoveries.append(layer)
        else:
            known_layers.append(layer)

    # Layers esperados ausentes
    missing_expected = [l for l in expected_layers if l not in layers_count]

    # --- Passo 3: Análise específica por classe ---
    class_analysis = _analyze_by_class(classe, entities_raw, layers_count, types_count)

    # --- Passo 4: Detecção de anomalias ---
    anomalies = _check_class_anomalies(classe, types_count, layers_count)

    # --- Passo 5: Extração de textos e nomenclaturas ---
    texts = [e for e in entities_raw if e["type"] in ("TEXT", "MTEXT")]
    dimensions = [e for e in entities_raw if e["type"] == "DIMENSION"]

    nomenclaturas = _extract_nomenclaturas(texts)
    dim_values = [d["measurement"] for d in dimensions if d.get("measurement") is not None]

    # --- Montagem da KB ---
    kb = {
        "file": filename,
        "file_path": str(dxf_path),
        "classe": classe,
        "pavimento": pavimento,
        "extraction_version": VERSION,
        "extraction_date": datetime.now().isoformat(),

        "inventory": {
            "total_entities": total_entities,
            "by_type": dict(sorted(types_count.items(), key=lambda x: -x[1])),
            "by_layer": dict(sorted(layers_count.items(), key=lambda x: -x[1])),
            "layers_count": len(layers_count),
        },

        "semantic_analysis": {
            "layer_semantics": semantic_dict,
            "known_layers_count": len(known_layers),
            "autonomous_discoveries": autonomous_discoveries,
            "autonomous_count": len(autonomous_discoveries),
            "missing_expected_layers": missing_expected,
            "coverage_pct": round(
                100 * len(known_layers) / max(len(layers_count), 1), 1
            ),
        },

        "text_content": {
            "total_texts": len(texts),
            "texts": texts[:200],  # primeiros 200 para não explodir a KB
            "nomenclaturas_detected": nomenclaturas,
            "dimension_values": dim_values[:100],
            "dimension_count": len(dimensions),
        },

        "class_specific": class_analysis,

        "anomalies": anomalies,
        "anomaly_count": len(anomalies),

        "entities": entities_raw,  # TODOS — granularidade extrema
    }

    # --- Salvar KB ---
    if output_dir:
        out_classe_dir = output_dir / classe
        out_classe_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r'[^\w\-_.]', '_', dxf_path.stem)
        out_path = out_classe_dir / f"{safe_name}_kb.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(kb, f, ensure_ascii=False, indent=2)
        print(f"  [OK] KB salva: {out_path}")
        kb["_kb_path"] = str(out_path)

    # Relatório de descobertas
    if autonomous_discoveries:
        print(f"  [DESCOBERTA] {len(autonomous_discoveries)} layers autônomos: {autonomous_discoveries}")
    if anomalies:
        for a in anomalies:
            sev = a['severity'].upper()
            prefix = "ANOMALIA" if sev in ("HIGH", "CRITICAL") else "DESCOBERTA"
            print(f"  [{prefix} {sev}] {a['type']}: {a['description']}")
    if missing_expected:
        print(f"  [INFO] Layers esperados ausentes: {missing_expected}")

    return kb


# ---------------------------------------------------------------------------
# Análise específica por classe
# ---------------------------------------------------------------------------

def _analyze_by_class(classe: str, entities: list, layers_count: dict, types_count: dict) -> dict:
    """Análise especializada por classe estrutural."""

    if classe == "FV":
        sarrafos = [e for e in entities if e["type"] == "LINE"
                    and re.search(r'SARR', e.get("layer", ""), re.I)]
        paineis = [e for e in entities if e["type"] == "LWPOLYLINE"
                   and e.get("layer") == "Painéis"]
        hatches = [e for e in entities if e["type"] == "HATCH"]
        inserts = [e for e in entities if e["type"] == "INSERT"]

        sarr_y = sorted(set(s["start"][1] for s in sarrafos if "start" in s))
        spacings = [round(sarr_y[i+1] - sarr_y[i], 4)
                    for i in range(len(sarr_y)-1)] if len(sarr_y) > 1 else []

        return {
            "fv_type": "standard",
            "insert_count": len(inserts),
            "has_inserts": len(inserts) > 0,
            "sarrafos": {
                "count": len(sarrafos),
                "y_positions": sarr_y[:50],
                "spacings": spacings[:20],
                "mean_spacing": round(sum(spacings)/len(spacings), 4) if spacings else None,
            },
            "paineis": {
                "count": len(paineis),
                "bboxes": [p.get("bbox") for p in paineis[:20]],
            },
            "concrete_hatches": {
                "count": len(hatches),
                "layers": list({h.get("layer") for h in hatches}),
            },
            "sarrafo_layers": sorted({e.get("layer") for e in sarrafos}),
        }

    elif classe == "LV":
        lv_type = _detect_lv_type(set(layers_count.keys()))
        sarrafos = [e for e in entities if e["type"] == "LINE"
                    and re.search(r'SARR', e.get("layer", ""), re.I)]
        paineis = [e for e in entities if e["type"] == "LWPOLYLINE"
                   and e.get("layer") == "Painéis"]
        hatches = [e for e in entities if e["type"] == "HATCH"]
        inserts = [e for e in entities if e["type"] == "INSERT"]

        sarrafo_layers = sorted({e.get("layer") for e in sarrafos})

        return {
            "lv_type": lv_type,
            "panel_count": len(paineis),
            "sarrafos": {
                "count": len(sarrafos),
                "layers": sarrafo_layers,
            },
            "hatches": {
                "count": len(hatches),
                "layers": sorted({h.get("layer") for h in hatches}),
            },
            "inserts": {
                "count": len(inserts),
                "block_names": sorted({i.get("block_name") for i in inserts})[:20],
            },
            "madeira_count": layers_count.get("Madeira", 0),
            "carimbo_count": layers_count.get("CARIMBO", 0),
        }

    elif classe == "LJ":
        sarr_layers = {l: c for l, c in layers_count.items() if re.search(r'SARR', l, re.I)}
        hatches = [e for e in entities if e["type"] == "HATCH"]

        # Detectar hh/hhh
        texts = [e for e in entities if e["type"] == "TEXT"]
        reap_texts = [t for t in texts
                      if re.match(r'^(hh+)$', t.get("content", "").strip(), re.I)]

        # Layer numérico dominante
        numeric_layers = {l: c for l, c in layers_count.items() if re.match(r'^\d+$', l)}

        paineis_lines = [e for e in entities if e["type"] == "LINE"
                         and e.get("layer") in ("Painéis", "concreto", "3", "4")]

        return {
            "confirmed_no_sarrafos": len(sarr_layers) == 0,
            "sarrafo_layers_if_any": dict(sarr_layers),
            "hlaz_hatches": {
                "count": len(hatches),
                "layers": sorted({h.get("layer") for h in hatches}),
            },
            "reaproveitamento": {
                "count": len(reap_texts),
                "texts": [t.get("content") for t in reap_texts[:20]],
            },
            "numeric_layers": numeric_layers,
            "panel_lines_count": len(paineis_lines),
        }

    elif classe == "PL":
        sarrafos = [e for e in entities if e["type"] in ("LINE", "LWPOLYLINE")
                    and re.search(r'SARR', e.get("layer", ""), re.I)]
        hatches = [e for e in entities if e["type"] == "HATCH"]
        inserts = [e for e in entities if e["type"] == "INSERT"]
        nivel_layers = {l: c for l, c in layers_count.items()
                        if re.search(r'NIVEL|PAV\.|PAVIMENTO', l, re.I)}

        sarrafo_layers = sorted({e.get("layer") for e in sarrafos})
        insert_blocks = sorted({i.get("block_name") for i in inserts})[:30]

        return {
            "sarrafos": {
                "count": len(sarrafos),
                "layers": sarrafo_layers,
            },
            "hatches": {
                "count": len(hatches),
                "layers": sorted({h.get("layer") for h in hatches})[:10],
            },
            "inserts": {
                "count": len(inserts),
                "block_names": insert_blocks,
            },
            "nivel_layers": nivel_layers,
            "chapa_count": layers_count.get("CHAPA", 0),
            "perfil_metalico_count": layers_count.get("Perfil Metálico", 0),
            "madeira_count": layers_count.get("Madeira", 0),
        }

    else:
        # GF, GD, VC, UNKNOWN — análise genérica
        sarrafos = [e for e in entities if re.search(r'SARR', e.get("layer", ""), re.I)]
        return {
            "classe_generica": classe,
            "sarrafos_count": len(sarrafos),
            "insert_count": types_count.get("INSERT", 0),
            "hatch_count": types_count.get("HATCH", 0),
        }


# ---------------------------------------------------------------------------
# Extração de nomenclaturas
# ---------------------------------------------------------------------------

NOMENCLATURA_PATTERNS = [
    re.compile(r'^([A-Z]{1,2}\d{1,4})$'),                   # V101, P23
    re.compile(r'^(\d+°?\s*(?:PAV|PV)\w*)$', re.I),          # 1°PAV, 2 PAV
    re.compile(r'^([A-Z]{1,3}-\d+)$'),                        # nf1, GRA-E
]


def _extract_nomenclaturas(texts: list) -> list:
    found = []
    for t in texts:
        content = t.get("content", "").strip()
        content_clean = t.get("content_clean", content).strip()
        for pat in NOMENCLATURA_PATTERNS:
            if pat.match(content_clean):
                found.append({
                    "content": content_clean,
                    "layer": t.get("layer"),
                    "insert": t.get("insert"),
                })
                break
    return found[:50]


# ---------------------------------------------------------------------------
# Análise de obra completa
# ---------------------------------------------------------------------------

def analyze_obra(obra_path: Path, pavimento_filter: str | None = None) -> dict:
    """
    Analisa todos os STOGs de uma obra.
    Se pavimento_filter fornecido, filtra por pavimento.
    """
    stog_dir = obra_path / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
    if not stog_dir.exists():
        print(f"[ERRO] Diretório STOG não encontrado: {stog_dir}")
        return {}

    output_dir = obra_path / "Fase-0_STOG_KB"
    output_dir.mkdir(exist_ok=True)

    dxf_files = sorted(stog_dir.glob("*.dxf"))
    if not dxf_files:
        print(f"[ERRO] Nenhum DXF encontrado em {stog_dir}")
        return {}

    # Filtrar por pavimento se especificado
    if pavimento_filter:
        dxf_files = [f for f in dxf_files
                     if pavimento_filter.lower().replace("°", "").replace(" ", "")
                     in f.name.lower().replace("°", "").replace(" ", "")]

    print(f"\n[STOG-INTEL] Obra: {obra_path.name}")
    print(f"[STOG-INTEL] STOGs encontrados: {len(dxf_files)}")
    if pavimento_filter:
        print(f"[STOG-INTEL] Filtro pavimento: {pavimento_filter}")

    summary = {
        "obra": obra_path.name,
        "obra_path": str(obra_path),
        "analysis_date": datetime.now().isoformat(),
        "total_stog_files": len(dxf_files),
        "by_class": {},
        "autonomous_discoveries_global": set(),
        "anomalies_global": [],
        "files_processed": [],
        "files_failed": [],
    }

    for dxf_path in dxf_files:
        try:
            kb = extract_stog(dxf_path, output_dir)
            classe = kb.get("classe", "UNKNOWN")

            if "error" in kb:
                summary["files_failed"].append({"file": dxf_path.name, "error": kb["error"]})
                continue

            # Acumular por classe
            if classe not in summary["by_class"]:
                summary["by_class"][classe] = {
                    "count": 0, "total_entities": 0,
                    "all_layers": {}, "anomaly_count": 0,
                    "autonomous_layers": [],
                }
            cls = summary["by_class"][classe]
            cls["count"] += 1
            cls["total_entities"] += kb["inventory"]["total_entities"]
            cls["anomaly_count"] += kb.get("anomaly_count", 0)

            for layer, count in kb["inventory"]["by_layer"].items():
                cls["all_layers"][layer] = cls["all_layers"].get(layer, 0) + count

            for layer in kb["semantic_analysis"]["autonomous_discoveries"]:
                summary["autonomous_discoveries_global"].add(layer)
                if layer not in cls["autonomous_layers"]:
                    cls["autonomous_layers"].append(layer)

            summary["files_processed"].append({
                "file": dxf_path.name,
                "classe": classe,
                "pavimento": kb.get("pavimento"),
                "entities": kb["inventory"]["total_entities"],
                "anomalies": kb.get("anomaly_count", 0),
                "kb_path": kb.get("_kb_path"),
            })

        except Exception as ex:
            summary["files_failed"].append({"file": dxf_path.name, "error": str(ex)})
            print(f"  [ERRO] {dxf_path.name}: {ex}")

    summary["autonomous_discoveries_global"] = sorted(summary["autonomous_discoveries_global"])
    summary["total_processed"] = len(summary["files_processed"])
    summary["total_failed"] = len(summary["files_failed"])

    # Salvar summary
    summary_path = output_dir / "obra_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n[STOG-INTEL] Concluído: {summary['total_processed']}/{len(dxf_files)} arquivos")
    print(f"[STOG-INTEL] Summary: {summary_path}")

    # Imprimir descobertas autônomas
    if summary["autonomous_discoveries_global"]:
        print(f"\n[DESCOBERTAS AUTÔNOMAS GLOBAIS] {len(summary['autonomous_discoveries_global'])} layers:")
        for l in summary["autonomous_discoveries_global"]:
            print(f"  - {l}")

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="STOG Intelligence Extractor — Compreensão granular de STOGs"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dxf", help="Path para um arquivo DXF específico")
    group.add_argument("--obra", help="Path para diretório da obra (analisa todos os STOGs)")

    parser.add_argument("--pavimento", default=None,
                        help="Filtrar por pavimento (ex: '1° PAV'). Usado com --obra.")
    parser.add_argument("--all-pavimentos", action="store_true",
                        help="Analisar todos os pavimentos (default com --obra)")
    parser.add_argument("--output", default=None,
                        help="Diretório de saída. Default: {obra}/Fase-0_STOG_KB/")
    parser.add_argument("--no-entities", action="store_true",
                        help="Excluir lista completa de entidades do JSON (menor saída)")

    args = parser.parse_args()

    if args.dxf:
        dxf_path = Path(args.dxf)
        if not dxf_path.exists():
            print(f"[ERRO] Arquivo não encontrado: {dxf_path}")
            sys.exit(1)

        out_dir = Path(args.output) if args.output else dxf_path.parent.parent.parent / "Fase-0_STOG_KB"
        kb = extract_stog(dxf_path, out_dir)

        if args.no_entities and "entities" in kb:
            del kb["entities"]

        print(f"\n[RESUMO] Classe: {kb.get('classe')} | Entidades: {kb.get('inventory', {}).get('total_entities')} | Anomalias: {kb.get('anomaly_count', 0)}")
        print(f"[RESUMO] Layers autônomos: {kb.get('semantic_analysis', {}).get('autonomous_discoveries', [])}")

    else:
        obra_path = Path(args.obra)
        if not obra_path.exists():
            print(f"[ERRO] Obra não encontrada: {obra_path}")
            sys.exit(1)

        pav = None if args.all_pavimentos else args.pavimento
        summary = analyze_obra(obra_path, pav)

        print(f"\n[OBRA] {summary.get('total_processed', 0)} STOGs processados")
        for classe, data in summary.get("by_class", {}).items():
            print(f"  {classe}: {data['count']} arquivos | {data['total_entities']} entidades | {data['anomaly_count']} anomalias")


if __name__ == "__main__":
    main()
