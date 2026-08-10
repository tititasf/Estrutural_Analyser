#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
obra_crop_engine.py — Motor de recorte automático de DXFs brutos.

Algoritmo:
  1. Extrai centros de todas as entidades do DXF
  2. DBSCAN por densidade → clusters de entidades
  3. Maior cluster (por score = área × contagem) = torre principal
  4. Clusters menores → unificados num único detalhes.dxf

Output por pavimento:
  {obra}/Fase-2_Triagem/recortes/{pav_name}/
      torre_1.dxf          ← planta baixa estrutural principal
      torre_2.dxf          ← segunda torre (se n_torres=2)
      detalhes.dxf         ← TODO o restante unificado num único arquivo
  recortes_log.json        ← dataset de aprendizado

  FUTURO — motor semântico de detalhes:
    Os detalhes têm semântica diferente das torres (leitura/compreensão,
    não medição). Um segundo motor de extração semântica será desenvolvido
    após validação dos recortes manuais. Objetivo: extrair anotações,
    notas do projetista, cotas de referência e legendas dos detalhes.
"""

from __future__ import annotations

import json
import uuid
import math
from datetime import datetime
from pathlib import Path
from typing import Optional

def _force_write_text(path_obj, text):
    import stat
    if path_obj.exists():
        try:
            path_obj.chmod(stat.S_IWRITE)
        except Exception:
            pass
    path_obj.write_text(text, encoding="utf-8")


# ─── Dependências ────────────────────────────────────────────────────────────
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

try:
    from sklearn.cluster import DBSCAN as _DBSCAN
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

try:
    import ezdxf
    from ezdxf.math import Vec2
    _HAS_EZDXF = True
except ImportError:
    _HAS_EZDXF = False

DB_SQLITE = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DADOS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")


# ─── Helpers geométricos ─────────────────────────────────────────────────────

def _entity_center(entity) -> Optional[tuple[float, float]]:
    """Retorna (cx, cy) de uma entidade DXF, ou None se não aplicável."""
    try:
        t = entity.dxftype()
        if t == "LINE":
            s = entity.dxf.start
            e = entity.dxf.end
            return ((s.x + e.x) / 2.0, (s.y + e.y) / 2.0)
        elif t in ("CIRCLE", "ARC"):
            c = entity.dxf.center
            return (c.x, c.y)
        elif t in ("INSERT", "POINT"):
            p = entity.dxf.insert
            return (p.x, p.y)
        elif t in ("LWPOLYLINE", "POLYLINE"):
            pts = list(entity.get_points())
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                return (sum(xs) / len(xs), sum(ys) / len(ys))
        elif t == "TEXT":
            p = entity.dxf.insert
            return (p.x, p.y)
        elif t == "MTEXT":
            p = entity.dxf.insert
            return (p.x, p.y)
        elif t == "DIMENSION":
            p = entity.dxf.defpoint
            return (p.x, p.y)
        elif t in ("HATCH", "SOLID"):
            # Aproximação pelo bounding box do hatch
            try:
                bb = entity.bounding_box()
                if bb:
                    return ((bb.extmin.x + bb.extmax.x) / 2, (bb.extmin.y + bb.extmax.y) / 2)
            except Exception:
                pass
            return None
    except Exception:
        return None
    return None


def _bbox_of_points(pts: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    """Retorna (x_min, y_min, x_max, y_max) de uma lista de pontos."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def _bbox_area(bbox: tuple) -> float:
    x1, y1, x2, y2 = bbox
    return max(0, (x2 - x1) * (y2 - y1))


def _point_in_bbox(x: float, y: float, bbox: tuple, padding: float = 0.0) -> bool:
    x1, y1, x2, y2 = bbox
    return (x1 - padding) <= x <= (x2 + padding) and (y1 - padding) <= y <= (y2 + padding)


def _point_in_polygon(x: float, y: float, poligono: list[tuple[float, float]]) -> bool:
    """Ray casting padrão. `poligono` é uma lista de (x, y) em coordenada DXF,
    não precisa estar fechada (o último ponto liga ao primeiro implicitamente).
    """
    dentro = False
    n = len(poligono)
    if n < 3:
        return False
    x1, y1 = poligono[-1]
    for x2, y2 in poligono:
        if ((y1 > y) != (y2 > y)) and (
            x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
        ):
            dentro = not dentro
        x1, y1 = x2, y2
    return dentro


def crop_dxf_by_polygon(
    input_path: str | Path,
    output_path: str | Path,
    poligono: list[tuple[float, float]],
) -> dict:
    """Copia para `output_path` as entidades de `input_path` cujo CENTRO cai
    dentro do polígono (coordenada DXF, ray casting).

    Existe para o laço de desenho do viewer web (P3): o operador desenha uma
    linha contínua sobre o estrutural limpo, os pontos (já convertidos px->DXF
    pela transform do render) chegam aqui como `poligono`, e o recorte sai só
    com o que estava dentro do traço — igual ao lasso do app desktop, sem
    dependência de retângulo (`crop_dxf`/`crop_dxf_multi` só cortam bbox).

    Mesma limitação estrutural de `_entity_center`: entidade sem centro
    calculável (tipo não mapeado) não entra nunca, mesmo dentro do laço — não
    é rejeição por estar fora, é ausência de suporte a esse tipo.

    Retorna: {"output": str, "entities_copied": int, "bbox": [...] | None,
              "error": None | str}
    """
    if not _HAS_EZDXF:
        return {"error": "ezdxf não instalado"}
    if len(poligono) < 3:
        return {"error": "poligono precisa de pelo menos 3 pontos"}

    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        doc = ezdxf.readfile(str(input_path))
    except Exception as e:
        return {"error": f"Falha ao ler DXF: {e}"}

    msp = doc.modelspace()
    new_doc = ezdxf.new("R2018")
    try:
        for layer in doc.layers:
            lname = layer.dxf.name
            if lname not in new_doc.layers:
                new_layer = new_doc.layers.new(lname)
                new_layer.dxf.color = layer.dxf.get("color", 7)
    except Exception:
        pass

    new_msp = new_doc.modelspace()
    copied = 0
    pontos_copiados: list[tuple[float, float]] = []

    for entity in msp:
        centro = _entity_center(entity)
        if centro is None:
            continue
        if not _point_in_polygon(centro[0], centro[1], poligono):
            continue
        try:
            new_msp.add_entity(entity.copy())
            copied += 1
            pontos_copiados.append(centro)
        except Exception:
            pass

    try:
        new_doc.saveas(str(output_path))
    except Exception as e:
        return {"error": f"Falha ao salvar DXF: {e}"}

    bbox = list(_bbox_of_points(pontos_copiados)) if pontos_copiados else None
    return {"output": str(output_path), "entities_copied": copied, "bbox": bbox, "error": None}


# ─── Detecção de regiões (DBSCAN) ────────────────────────────────────────────

def detect_regions(
    dxf_path: str | Path,
    n_torres: int = 1,
    eps_factor: float = 0.025,
    min_samples: int = 8,
    bad_bboxes: list[list[float]] | None = None,
) -> dict:
    """
    Detecta regiões de torre e detalhes por densidade de entidades (DBSCAN).

    Parâmetros:
        dxf_path    : caminho do DXF bruto
        n_torres    : número de torres esperadas (1 ou 2)
        eps_factor  : fração do tamanho total do DXF usado como epsilon DBSCAN
        min_samples : mínimo de entidades para formar um cluster

    Retorna:
        {
          "torres":   [{"idx": 0, "bbox": [...], "area": float, "count": int}, ...],
          "detalhes": [{"idx": 1, "bbox": [...], "area": float, "count": int}, ...],
          "total_entities": int,
          "total_clusters": int,
          "eps_used": float,
          "error": None | str,
        }
    """
    if not _HAS_EZDXF:
        return {"error": "ezdxf não instalado. pip install ezdxf"}
    if not _HAS_NUMPY:
        return {"error": "numpy não instalado. pip install numpy"}
    if not _HAS_SKLEARN:
        return {"error": "scikit-learn não instalado. pip install scikit-learn"}

    dxf_path = Path(dxf_path)
    if not dxf_path.exists():
        return {"error": f"Arquivo não encontrado: {dxf_path}"}

    # ── 1. Carregar entidades ─────────────────────────────────────────────────
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        return {"error": f"Falha ao abrir DXF: {e}"}

    msp = doc.modelspace()
    centers = []
    for entity in msp:
        c = _entity_center(entity)
        if c:
            centers.append(c)

    if len(centers) < 20:
        return {"error": f"DXF com poucas entidades ({len(centers)}) — impossível detectar regiões"}

    pts = np.array(centers)

    # ── 2. Calcular epsilon adaptivo ─────────────────────────────────────────
    x_range = pts[:, 0].max() - pts[:, 0].min()
    y_range = pts[:, 1].max() - pts[:, 1].min()
    overall = max(x_range, y_range)
    eps = overall * eps_factor

    # ── 3. DBSCAN ─────────────────────────────────────────────────────────────
    db = _DBSCAN(eps=eps, min_samples=min_samples).fit(pts)
    labels = db.labels_

    unique_labels = [l for l in set(labels) if l != -1]
    if not unique_labels:
        return {"error": "DBSCAN não encontrou clusters. Tente aumentar eps_factor."}

    # ── 4. Caracterizar cada cluster ─────────────────────────────────────────
    clusters = []
    for lbl in unique_labels:
        mask = labels == lbl
        cpts = pts[mask]
        bbox = _bbox_of_points(list(map(tuple, cpts)))
        area = _bbox_area(bbox)
        count = int(mask.sum())
        score = area * math.sqrt(count)   # score = área × √contagem
        clusters.append({
            "idx":   lbl,
            "bbox":  list(bbox),
            "area":  area,
            "count": count,
            "score": score,
        })

    # ── 4.5 Penalizar clusters inválidos (Anti-Repetição) ────────────────────
    if bad_bboxes:
        def _iou(bA, bB):
            xA = max(bA[0], bB[0]); yA = max(bA[1], bB[1])
            xB = min(bA[2], bB[2]); yB = min(bA[3], bB[3])
            iA = max(0, xB - xA) * max(0, yB - yA)
            if iA == 0: return 0.0
            aA = (bA[2] - bA[0]) * (bA[3] - bA[1])
            aB = (bB[2] - bB[0]) * (bB[3] - bB[1])
            return iA / float(aA + aB - iA)
            
        for c in clusters:
            for bad in bad_bboxes:
                if _iou(c["bbox"], bad) > 0.5:
                    c["score"] = -1  # Força a virar detalhe, nunca torre
                    break

    # ── 5. Ordenar por score (maior primeiro) ─────────────────────────────────
    clusters.sort(key=lambda c: c["score"], reverse=True)

    torres   = clusters[:n_torres]
    detalhes = clusters[n_torres:]

    # Numerar detalhes
    for i, d in enumerate(detalhes):
        d["detalhe_num"] = i + 1

    return {
        "torres":        torres,
        "detalhes":      detalhes,
        "total_entities": len(centers),
        "total_clusters": len(clusters),
        "eps_used":       round(eps, 2),
        "error":          None,
    }


# ─── Extração de recorte (crop) ───────────────────────────────────────────────

def crop_dxf(
    input_path: str | Path,
    output_path: str | Path,
    bbox: tuple | list,
    padding_pct: float = 0.01,
    selection_mode: str = "center",
) -> dict:
    """
    Extrai entidades dentro de bbox (com padding) do DXF input e salva em output.

    Retorna: {"output": str, "entities_copied": int, "error": None | str}
    """
    if not _HAS_EZDXF:
        return {"error": "ezdxf não instalado"}

    input_path  = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        doc = ezdxf.readfile(str(input_path))
    except Exception as e:
        return {"error": f"Falha ao ler DXF: {e}"}

    x1, y1, x2, y2 = bbox
    padding = max(x2 - x1, y2 - y1) * padding_pct
    if selection_mode not in {"center", "contained"}:
        return {"error": f"selection_mode invalido: {selection_mode}"}

    msp = doc.modelspace()
    new_doc = ezdxf.new("R2018")

    # Copiar tabelas de layers do original
    try:
        for layer in doc.layers:
            lname = layer.dxf.name
            if lname not in new_doc.layers:
                new_layer = new_doc.layers.new(lname)
                new_layer.dxf.color = layer.dxf.get("color", 7)
    except Exception:
        pass

    new_msp = new_doc.modelspace()
    copied = 0

    if selection_mode == "contained":
        from ezdxf import bbox as ezbbox
        caixas = ezbbox.multi_flat(msp, fast=True)
    else:
        caixas = (None for _ in msp)

    skipped_outside = 0
    skipped_no_bbox = 0
    for entity, caixa in zip(msp, caixas):
        if selection_mode == "contained":
            incluir = bool(
                caixa is not None and caixa.has_data
                and caixa.extmin.x >= x1 - padding
                and caixa.extmin.y >= y1 - padding
                and caixa.extmax.x <= x2 + padding
                and caixa.extmax.y <= y2 + padding
            )
            if caixa is None or not caixa.has_data:
                skipped_no_bbox += 1
        else:
            c = _entity_center(entity)
            incluir = bool(c and _point_in_bbox(c[0], c[1], (x1, y1, x2, y2), padding))
        if incluir:
            try:
                new_msp.add_entity(entity.copy())
                copied += 1
            except Exception:
                pass
        else:
            skipped_outside += 1

    if selection_mode == "contained" and copied == 0:
        return {"error": "Nenhuma entidade ficou integralmente dentro do recorte"}

    try:
        new_doc.saveas(str(output_path))
    except Exception as e:
        return {"error": f"Falha ao salvar DXF: {e}"}

    return {
        "output": str(output_path),
        "entities_copied": copied,
        "entities_skipped_outside": skipped_outside,
        "entities_skipped_no_bbox": skipped_no_bbox,
        "selection_bbox": [float(x1), float(y1), float(x2), float(y2)],
        "selection_mode": selection_mode,
        "error": None,
    }


def crop_dxf_multi(
    input_path: str | Path,
    output_path: str | Path,
    bboxes: list[tuple | list],
    padding_pct: float = 0.01,
    selection_mode: str = "center",
) -> dict:
    """
    Extrai entidades de MÚLTIPLAS bboxes do DXF e salva num único arquivo.

    Usado para unificar todos os clusters de detalhes em um só detalhes.dxf.
    Retorna: {"output": str, "entities_copied": int, "error": None | str}
    """
    if not _HAS_EZDXF:
        return {"error": "ezdxf não instalado"}
    if not bboxes:
        return {"error": "Nenhuma bbox fornecida"}
    if selection_mode not in {"center", "contained"}:
        return {"error": f"selection_mode invalido: {selection_mode}"}

    input_path  = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        doc = ezdxf.readfile(str(input_path))
    except Exception as e:
        return {"error": f"Falha ao ler DXF: {e}"}

    # Pré-calcular paddings por bbox
    padded_bboxes = []
    for bbox in bboxes:
        x1, y1, x2, y2 = bbox
        padding = max(x2 - x1, y2 - y1) * padding_pct
        padded_bboxes.append((x1, y1, x2, y2, padding))

    msp = doc.modelspace()
    new_doc = ezdxf.new("R2018")

    try:
        for layer in doc.layers:
            lname = layer.dxf.name
            if lname not in new_doc.layers:
                new_layer = new_doc.layers.new(lname)
                new_layer.dxf.color = layer.dxf.get("color", 7)
    except Exception:
        pass

    new_msp = new_doc.modelspace()
    copied = 0

    if selection_mode == "contained":
        from ezdxf import bbox as ezbbox
        caixas = ezbbox.multi_flat(msp, fast=True)
    else:
        caixas = (None for _ in msp)

    skipped_outside = 0
    skipped_no_bbox = 0
    for entity, caixa in zip(msp, caixas):
        c = _entity_center(entity) if selection_mode == "center" else None
        if selection_mode == "center" and not c:
            skipped_outside += 1
            continue
        if selection_mode == "contained" and (caixa is None or not caixa.has_data):
            skipped_no_bbox += 1
            skipped_outside += 1
            continue
        incluir = False
        for (x1, y1, x2, y2, pad) in padded_bboxes:
            if selection_mode == "contained":
                incluir = bool(
                    caixa.extmin.x >= x1 - pad and caixa.extmin.y >= y1 - pad
                    and caixa.extmax.x <= x2 + pad and caixa.extmax.y <= y2 + pad
                )
            else:
                incluir = _point_in_bbox(c[0], c[1], (x1, y1, x2, y2), pad)
            if incluir:
                try:
                    new_msp.add_entity(entity.copy())
                    copied += 1
                except Exception:
                    pass
                break  # evitar duplicatas se cai em múltiplas bboxes
        if not incluir:
            skipped_outside += 1

    if selection_mode == "contained" and copied == 0:
        return {"error": "Nenhuma entidade ficou integralmente dentro dos recortes"}

    try:
        new_doc.saveas(str(output_path))
    except Exception as e:
        return {"error": f"Falha ao salvar DXF: {e}"}

    return {
        "output": str(output_path),
        "entities_copied": copied,
        "entities_skipped_outside": skipped_outside,
        "entities_skipped_no_bbox": skipped_no_bbox,
        "selection_bboxes": [[float(v) for v in b] for b in bboxes],
        "selection_mode": selection_mode,
        "error": None,
    }


def crop_dxf_from_entities(
    input_path: str | Path,
    output_path: str | Path,
    entity_handles: set[str] | None = None,
    viewport_bbox: tuple | None = None,
    padding_pct: float = 0.0,
) -> dict:
    """
    Exporta entidades de um DXF filtradas por handles específicos OU por
    viewport_bbox (bbox visível no canvas).  Usado pelo botão 'Salvar' do viewer.

    Retorna: {"output": str, "entities_copied": int, "error": None | str}
    """
    if not _HAS_EZDXF:
        return {"error": "ezdxf não instalado"}

    input_path  = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        doc = ezdxf.readfile(str(input_path))
    except Exception as e:
        return {"error": f"Falha ao ler DXF: {e}"}

    msp = doc.modelspace()
    new_doc = ezdxf.new("R2018")

    try:
        for layer in doc.layers:
            lname = layer.dxf.name
            if lname not in new_doc.layers:
                new_layer = new_doc.layers.new(lname)
                new_layer.dxf.color = layer.dxf.get("color", 7)
    except Exception:
        pass

    new_msp = new_doc.modelspace()
    copied = 0

    # Padding para viewport_bbox
    pad = 0.0
    if viewport_bbox:
        x1, y1, x2, y2 = viewport_bbox
        pad = max(x2 - x1, y2 - y1) * padding_pct

    for entity in msp:
        include = False
        if entity_handles and entity.dxf.handle in entity_handles:
            include = True
        elif viewport_bbox:
            c = _entity_center(entity)
            if c and _point_in_bbox(c[0], c[1], viewport_bbox, pad):
                include = True
        elif not entity_handles and not viewport_bbox:
            include = True  # sem filtro → copia tudo

        if include:
            try:
                new_msp.add_entity(entity.copy())
                copied += 1
            except Exception:
                pass

    try:
        new_doc.saveas(str(output_path))
    except Exception as e:
        return {"error": f"Falha ao salvar DXF: {e}"}

    return {"output": str(output_path), "entities_copied": copied, "error": None}


# ─── Pipeline completo de recorte por pavimento ───────────────────────────────

def process_pavimento_crops(
    obra_name: str,
    pavimento_name: str,
    dxf_bruto_path: str | Path,
    n_torres: int = 1,
    force: bool = False,
) -> dict:
    """
    Detecta regiões e gera arquivos de recorte para um pavimento.

    Saída:
      DADOS_ROOT/{obra}/Fase-2_Triagem/recortes/{pav}/
          torre_1.dxf, torre_2.dxf (se n_torres=2)
          detalhe_001.dxf, detalhe_002.dxf, ...

    Retorna dict com resultado e caminho dos arquivos gerados.
    """
    dxf_bruto_path = Path(dxf_bruto_path)
    out_dir = DADOS_ROOT / obra_name / "Fase-2_Triagem" / "recortes" / pavimento_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Verificar se já foi processado
    if not force and (out_dir / "crop_result.json").exists():
        existing = json.loads((out_dir / "crop_result.json").read_text(encoding="utf-8"))
        return {**existing, "cached": True}

    result = {
        "obra_name":       obra_name,
        "pavimento_name":  pavimento_name,
        "dxf_bruto":       str(dxf_bruto_path),
        "n_torres":        n_torres,
        "out_dir":         str(out_dir),
        "torres":          [],
        "detalhes":        [],
        "errors":          [],
        "processed_at":    datetime.now().isoformat(),
        "cached":          False,
    }

    # Carregar parâmetros aprendidos (ou defaults se ainda não há histórico)
    learned     = load_learned_params(obra_name)
    eps_factor  = learned.get("eps_factor",  0.025)
    padding_pct = learned.get("padding_pct", 0.01)
    min_samples = learned.get("min_samples", 8)
    if learned.get("samples", 0) > 0:
        print(f"[crop_engine] Usando parâmetros aprendidos: "
              f"eps_factor={eps_factor}, padding_pct={padding_pct}, "
              f"samples={learned['samples']}", flush=True)

    # 1. Detectar regiões
    regions = detect_regions(dxf_bruto_path, n_torres=n_torres,
                             eps_factor=eps_factor, min_samples=min_samples)
    if regions.get("error"):
        result["errors"].append(f"detect_regions: {regions['error']}")
        return result

    result["detection"] = {
        "total_entities": regions["total_entities"],
        "total_clusters": regions["total_clusters"],
        "eps_used":       regions["eps_used"],
    }

    # 2. Recortar torres
    for i, torre in enumerate(regions["torres"], 1):
        out_path = out_dir / f"torre_{i}.dxf"
        crop_result = crop_dxf(dxf_bruto_path, out_path, torre["bbox"],
                               padding_pct=padding_pct)
        entry = {
            "type":             f"torre_{i}",
            "output_path":      str(out_path),
            "bbox":             torre["bbox"],
            "area":             torre["area"],
            "entity_count":     torre["count"],
            "entities_copied":  crop_result.get("entities_copied", 0),
            "status":           "pending",
            "approved":         False,
            "approved_at":      None,
        }
        if crop_result.get("error"):
            entry["error"] = crop_result["error"]
            result["errors"].append(f"crop torre_{i}: {crop_result['error']}")
        result["torres"].append(entry)

    # 3. Recortar detalhes — unificados num único detalhes.dxf
    if regions["detalhes"]:
        det_bboxes  = [d["bbox"] for d in regions["detalhes"]]
        det_area    = sum(d["area"]  for d in regions["detalhes"])
        det_count   = sum(d["count"] for d in regions["detalhes"])
        out_path    = out_dir / "detalhes.dxf"
        crop_result = crop_dxf_multi(dxf_bruto_path, out_path, det_bboxes,
                                     padding_pct=padding_pct)
        entry = {
            "type":             "detalhes",
            "output_path":      str(out_path),
            "bboxes":           det_bboxes,       # todas as bboxes individuais
            "area":             det_area,
            "entity_count":     det_count,
            "entities_copied":  crop_result.get("entities_copied", 0),
            "clusters":         len(regions["detalhes"]),
            "status":           "pending",
            "approved":         False,
            "approved_at":      None,
        }
        if crop_result.get("error"):
            entry["error"] = crop_result["error"]
            result["errors"].append(f"crop detalhes: {crop_result['error']}")
        result["detalhes"].append(entry)

    # 4. Salvar resultado
    _force_write_text(out_dir / "crop_result.json", json.dumps(result, ensure_ascii=False, indent=2))

    # 5. Atualizar log global da obra (dataset de aprendizado)
    _append_to_recortes_log(obra_name, result)

    return result


def _append_to_recortes_log(obra_name: str, crop_result: dict):
    """Adiciona entrada ao recortes_log.json da obra (dataset de aprendizado)."""
    log_path = DADOS_ROOT / obra_name / "recortes_log.json"
    try:
        log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
        # Remover entrada anterior do mesmo pavimento
        log = [e for e in log if e.get("pavimento_name") != crop_result.get("pavimento_name")]
        log.append({
            "pavimento_name":  crop_result["pavimento_name"],
            "dxf_bruto":       crop_result["dxf_bruto"],
            "n_torres":        crop_result["n_torres"],
            "detection":       crop_result.get("detection", {}),
            "torres_count":    len(crop_result.get("torres", [])),
            "detalhes_count":  len(crop_result.get("detalhes", [])),
            "auto_bboxes": {
                "torres":   [t["bbox"] for t in crop_result.get("torres", [])],
                "detalhes": [d.get("bbox") or d.get("bboxes") for d in crop_result.get("detalhes", [])],
            },
            "approved_bboxes": None,   # preenchido quando usuário aprovar
            "processed_at":    crop_result["processed_at"],
        })
        _force_write_text(log_path, json.dumps(log, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[crop_engine] Aviso: falha ao gravar recortes_log.json: {e}")


def approve_recorte(
    obra_name: str,
    pavimento_name: str,
    recorte_type: str,
    final_bbox: Optional[list] = None,
) -> bool:
    """
    Marca um recorte como aprovado e atualiza o log de aprendizado.

    Se final_bbox é diferente do auto-detectado, registra a correção.
    """
    out_dir = DADOS_ROOT / obra_name / "Fase-2_Triagem" / "recortes" / pavimento_name
    result_file = out_dir / "crop_result.json"
    if not result_file.exists():
        return False

    try:
        result = json.loads(result_file.read_text(encoding="utf-8"))
        approved_at = datetime.now().isoformat()

        # Atualizar status no result
        for entry in result.get("torres", []) + result.get("detalhes", []):
            if entry["type"] == recorte_type:
                entry["status"] = "approved"
                entry["approved"] = True
                entry["approved_at"] = approved_at
                if final_bbox:
                    entry["approved_bbox"] = final_bbox
                break

        _force_write_text(result_file, json.dumps(result, ensure_ascii=False, indent=2))

        # Atualizar log de aprendizado
        _update_learning_log(obra_name, pavimento_name, recorte_type, final_bbox)
        return True
    except Exception as e:
        print(f"[crop_engine] Erro ao aprovar recorte: {e}")
        return False


def _update_learning_log(obra_name, pavimento_name, recorte_type, approved_bbox):
    """Salva bbox aprovada vs auto no dataset de aprendizado."""
    log_path = DADOS_ROOT / obra_name / "recortes_log.json"
    if not log_path.exists():
        return
    try:
        log = json.loads(log_path.read_text(encoding="utf-8"))
        for entry in log:
            if entry.get("pavimento_name") == pavimento_name:
                if entry.get("approved_bboxes") is None:
                    entry["approved_bboxes"] = {}
                if approved_bbox:
                    entry["approved_bboxes"][recorte_type] = approved_bbox
                    entry["had_manual_correction"] = True
                else:
                    entry["approved_bboxes"][recorte_type] = "auto_accepted"
                break
        _force_write_text(log_path, json.dumps(log, ensure_ascii=False, indent=2))
    except Exception:
        pass


# ─── Sistema de aprendizado ──────────────────────────────────────────────────

LEARNED_PARAMS_FILE = "crop_params_learned.json"


def _dxf_actual_bbox(dxf_path: str | Path) -> Optional[list]:
    """Lê o bounding box real de todas as entidades de um DXF aprovado."""
    if not _HAS_EZDXF or not _HAS_NUMPY:
        return None
    try:
        doc   = ezdxf.readfile(str(dxf_path))
        msp   = doc.modelspace()
        pts   = [_entity_center(e) for e in msp]
        pts   = [p for p in pts if p is not None]
        if not pts:
            return None
        arr   = __import__('numpy').array(pts)
        return [float(arr[:,0].min()), float(arr[:,1].min()),
                float(arr[:,0].max()), float(arr[:,1].max())]
    except Exception:
        return None


def record_approval_bbox(obra_name: str, pavimento_name: str,
                         recorte_type: str, output_path: str | Path) -> None:
    """
    Chamado imediatamente após aprovação de um recorte.
    Lê o bbox real do DXF aprovado e salva no log de aprendizado.
    Detecta automaticamente se houve correção manual comparando com bbox_auto.
    """
    log_path = DADOS_ROOT / obra_name / "recortes_log.json"
    if not log_path.exists():
        return

    approved_bb = _dxf_actual_bbox(output_path)
    if not approved_bb:
        return

    try:
        log = json.loads(log_path.read_text(encoding="utf-8"))
        for entry in log:
            if entry.get("pavimento_name") != pavimento_name:
                continue

            # Inicializar dict de bboxes aprovadas
            if entry.get("approved_bboxes") is None:
                entry["approved_bboxes"] = {}
            entry["approved_bboxes"][recorte_type] = approved_bb

            # Detectar correção manual: comparar com bbox_auto
            auto_bboxes = entry.get("auto_bboxes", {})
            auto_key    = "torres" if recorte_type.startswith("torre") else "detalhes"
            auto_list   = auto_bboxes.get(auto_key, [])
            auto_bb     = auto_list[0] if auto_list else None

            if auto_bb and len(auto_bb) == 4:
                auto_area  = _bbox_area(tuple(auto_bb))
                appr_area  = _bbox_area(tuple(approved_bb))
                ratio      = appr_area / auto_area if auto_area > 0 else 1.0
                entry["approved_area_ratio"]   = round(ratio, 4)
                # Considera correção manual se diferença > 5%
                entry["had_manual_correction"] = abs(ratio - 1.0) > 0.05
            else:
                entry["approved_area_ratio"]   = 1.0
                entry["had_manual_correction"] = False

            break

        _force_write_text(log_path, json.dumps(log, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"[crop_engine] Aviso record_approval_bbox: {e}")


def compute_learned_params(obra_name: str) -> dict:
    """
    Analisa todos os recortes aprovados e deriva parâmetros calibrados.

    Lógica:
      - eps_factor_learned  : mediana dos eps_used / tamanho_dxf (de aprovações sem correção)
      - padding_correction  : mediana dos approved_area_ratio (se > 1 → DBSCAN cortou curto)
      - min_samples_learned : fixo em 8 por enquanto (poucas amostras)

    Salva em DADOS_ROOT/{obra}/crop_params_learned.json.
    Retorna o dict de parâmetros.
    """
    log_path = DADOS_ROOT / obra_name / "recortes_log.json"
    defaults = {"eps_factor": 0.025, "min_samples": 8, "padding_pct": 0.01,
                "samples": 0, "computed_at": None}

    if not log_path.exists():
        return defaults

    try:
        log = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception:
        return defaults

    approved_entries = [
        e for e in log
        if e.get("approved_bboxes") and e.get("detection")
    ]

    if len(approved_entries) < 2:
        return defaults  # não há amostras suficientes

    import statistics

    # ── eps_factor calibrado ─────────────────────────────────────────────────
    # eps_used = eps_factor × overall_size, recuperamos o fator via DB
    # Como não temos overall_size salvo, usamos os valores de eps_used diretamente
    # e estimamos um factor a partir da distribuição
    eps_values = [e["detection"]["eps_used"] for e in approved_entries
                  if e["detection"].get("eps_used")]

    # Filtrar outliers (±1.5 IQR) antes de calibrar
    if len(eps_values) >= 4:
        q1 = statistics.quantiles(eps_values, n=4)[0]
        q3 = statistics.quantiles(eps_values, n=4)[2]
        iqr = q3 - q1
        eps_values = [v for v in eps_values if (q1 - 1.5*iqr) <= v <= (q3 + 1.5*iqr)]

    # ── padding_correction calibrada ─────────────────────────────────────────
    ratios = [e.get("approved_area_ratio", 1.0) for e in approved_entries
              if e.get("approved_area_ratio") is not None]
    median_ratio    = statistics.median(ratios) if ratios else 1.0
    # Se mediana_ratio > 1 → aprovações foram maiores que o auto → aumentar padding
    # padding_pct_learned = 0.01 × sqrt(median_ratio)
    padding_learned = round(0.01 * (median_ratio ** 0.5), 4)
    padding_learned = max(0.005, min(0.08, padding_learned))  # clamp 0.5%–8%

    # ── contagem de correções manuais ─────────────────────────────────────────
    n_manual = sum(1 for e in approved_entries if e.get("had_manual_correction"))
    correction_rate = n_manual / len(approved_entries) if approved_entries else 0.0

    # Se taxa de correção > 30% → eps pode estar muito pequeno → aumentar 10%
    eps_factor_base = 0.025
    if correction_rate > 0.30:
        eps_factor_base = round(0.025 * 1.10, 4)
    elif correction_rate < 0.10 and len(approved_entries) >= 5:
        # Quase nenhuma correção → podemos ser um pouco mais agressivos
        eps_factor_base = round(0.025 * 0.95, 4)

    params = {
        "eps_factor":       eps_factor_base,
        "min_samples":      8,
        "padding_pct":      padding_learned,
        "median_eps_used":  round(statistics.median(eps_values), 2) if eps_values else None,
        "median_ratio":     round(median_ratio, 4),
        "correction_rate":  round(correction_rate, 3),
        "samples":          len(approved_entries),
        "computed_at":      datetime.now().isoformat(),
    }

    out_path = DADOS_ROOT / obra_name / LEARNED_PARAMS_FILE
    _force_write_text(out_path, json.dumps(params, ensure_ascii=False, indent=2))
    print(f"[crop_engine] Parâmetros aprendidos salvos: {out_path}")
    return params


def load_learned_params(obra_name: str) -> dict:
    """Carrega parâmetros aprendidos, ou retorna defaults se não existir."""
    params_path = DADOS_ROOT / obra_name / LEARNED_PARAMS_FILE
    if not params_path.exists():
        return {"eps_factor": 0.025, "min_samples": 8, "padding_pct": 0.01}
    try:
        return json.loads(params_path.read_text(encoding="utf-8"))
    except Exception:
        return {"eps_factor": 0.025, "min_samples": 8, "padding_pct": 0.01}


def get_pavimento_recortes(obra_name: str, pavimento_name: str) -> Optional[dict]:
    """Carrega o resultado de recortes de um pavimento (ou None se não processado)."""
    result_file = DADOS_ROOT / obra_name / "Fase-2_Triagem" / "recortes" / pavimento_name / "crop_result.json"
    if not result_file.exists():
        return None
    try:
        return json.loads(result_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_obra_recortes_summary(obra_name: str) -> dict:
    """Retorna resumo do estado de todos recortes de uma obra."""
    base = DADOS_ROOT / obra_name / "Fase-2_Triagem" / "recortes"
    if not base.exists():
        return {"total": 0, "processados": 0, "aprovados": 0, "pendentes": 0}

    total = processados = aprovados = 0
    for pav_dir in base.iterdir():
        if not pav_dir.is_dir():
            continue
        total += 1
        result_file = pav_dir / "crop_result.json"
        if not result_file.exists():
            continue
        processados += 1
        try:
            r = json.loads(result_file.read_text(encoding="utf-8"))
            all_items = r.get("torres", []) + r.get("detalhes", [])
            if all_items and all(i.get("approved") for i in all_items):
                aprovados += 1
        except Exception:
            pass

    return {
        "total":       total,
        "processados": processados,
        "aprovados":   aprovados,
        "pendentes":   total - aprovados,
    }


def ensure_recortes_in_db(
    obra_name: str,
    pavimento_name: str,
    dxf_bruto_path: str,
    crop_result: dict,
) -> int:
    """
    Persiste os recortes de crop_result na tabela obra_recortes (SQLite).
    Retorna o número de rows inseridas/atualizadas.
    """
    import sqlite3, json as _json
    if not DB_SQLITE.exists() and not crop_result:
        return 0

    # Garantir que a tabela existe
    try:
        from scripts.obra_rag_utils import ensure_obra_recortes_table
        ensure_obra_recortes_table()
    except Exception:
        # Fallback: create inline
        conn = sqlite3.connect(str(DB_SQLITE))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS obra_recortes (
                id TEXT PRIMARY KEY,
                obra_name TEXT NOT NULL,
                pavimento_name TEXT NOT NULL,
                dxf_bruto_path TEXT NOT NULL,
                recorte_type TEXT NOT NULL,
                recorte_index INTEGER DEFAULT 0,
                output_path TEXT,
                bbox_auto TEXT,
                bbox_approved TEXT,
                entity_count INTEGER DEFAULT 0,
                score REAL DEFAULT 0.0,
                status TEXT DEFAULT 'auto',
                n_torres INTEGER DEFAULT 1,
                created_at TEXT,
                approved_at TEXT,
                UNIQUE(obra_name, pavimento_name, recorte_type, recorte_index)
            )
        """)
        conn.commit()
        conn.close()

    now = datetime.now().isoformat()
    rows = []
    n_torres = crop_result.get("n_torres", 1)

    for i, torre in enumerate(crop_result.get("torres", [])):
        bbox = torre.get("bbox", [])
        rows.append({
            "id":              str(uuid.uuid4()),
            "obra_name":       obra_name,
            "pavimento_name":  pavimento_name,
            "dxf_bruto_path":  dxf_bruto_path,
            "recorte_type":    "torre",
            "recorte_index":   i,
            "output_path":     torre.get("output_path", ""),
            "bbox_auto":       _json.dumps(bbox) if bbox else None,
            "bbox_approved":   None,
            "entity_count":    torre.get("entity_count", 0),
            "score":           torre.get("area", 0.0),
            "status":          "auto",
            "n_torres":        n_torres,
            "created_at":      now,
            "approved_at":     None,
        })

    for i, det in enumerate(crop_result.get("detalhes", [])):
        bbox = det.get("bbox", [])
        rows.append({
            "id":              str(uuid.uuid4()),
            "obra_name":       obra_name,
            "pavimento_name":  pavimento_name,
            "dxf_bruto_path":  dxf_bruto_path,
            "recorte_type":    "detalhe",
            "recorte_index":   i,
            "output_path":     det.get("output_path", ""),
            "bbox_auto":       _json.dumps(bbox) if bbox else None,
            "bbox_approved":   None,
            "entity_count":    det.get("entity_count", 0),
            "score":           det.get("area", 0.0),
            "status":          "auto",
            "n_torres":        n_torres,
            "created_at":      now,
            "approved_at":     None,
        })

    if not rows:
        return 0

    try:
        conn = sqlite3.connect(str(DB_SQLITE))
        conn.executemany("""
            INSERT OR REPLACE INTO obra_recortes
                (id, obra_name, pavimento_name, dxf_bruto_path, recorte_type,
                 recorte_index, output_path, bbox_auto, bbox_approved,
                 entity_count, score, status, n_torres, created_at, approved_at)
            VALUES
                (:id, :obra_name, :pavimento_name, :dxf_bruto_path, :recorte_type,
                 :recorte_index, :output_path, :bbox_auto, :bbox_approved,
                 :entity_count, :score, :status, :n_torres, :created_at, :approved_at)
        """, rows)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[crop_engine] Erro ao persistir recortes no DB: {e}")
        return 0

    return len(rows)


def load_approved_brutos_from_triagem(obra_name: str) -> list[dict]:
    """
    Carrega da tabela obra_triagem os itens aprovados do tipo bruto para a obra.
    Retorna lista de {file_name, file_path, confidence, approved_at}
    """
    import sqlite3
    if not DB_SQLITE.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_SQLITE))
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """SELECT id, file_name, file_path, confidence, notes, created_at
               FROM obra_triagem
               WHERE obra_name=? AND status='approved'
               AND (suggested_category LIKE '%Bruto%' OR suggested_category LIKE '%bruto%'
                    OR classifier LIKE '%bruto%' OR notes LIKE '%bruto%')
               ORDER BY suggested_order ASC, file_name ASC""",
            (obra_name,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[crop_engine] Erro ao carregar brutos aprovados: {e}")
        return []


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Motor de recorte automático de DXFs brutos")
    ap.add_argument("--obra",     required=True, help="Nome da obra")
    ap.add_argument("--pav",      required=True, help="Nome do pavimento")
    ap.add_argument("--dxf",      required=True, help="Caminho do DXF bruto")
    ap.add_argument("--torres",   type=int, default=1, help="Número de torres (1 ou 2)")
    ap.add_argument("--force",    action="store_true", help="Reprocessar mesmo se já existir")
    args = ap.parse_args()

    print(f"🔪 Processando recortes: {args.obra} / {args.pav}")
    result = process_pavimento_crops(
        obra_name=args.obra,
        pavimento_name=args.pav,
        dxf_bruto_path=args.dxf,
        n_torres=args.torres,
        force=args.force,
    )

    if result.get("errors"):
        print(f"\n⚠ Erros: {result['errors']}")
    print(f"\nTorres:   {len(result.get('torres', []))}")
    print(f"Detalhes: {len(result.get('detalhes', []))}")
    print(f"Saída:    {result.get('out_dir')}")
