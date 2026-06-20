# src/core/learning/context_signature.py
"""
Assinatura geometrica (Context Key) para o Learning Store.
Gera hash normalizado da geometria + propriedades topologicas.
Mesma forma geometrica = mesma assinatura, independente de posicao/rotacao.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def _bucketize(value: float, bins: list = None) -> str:
    """Agrupa valor em bins definidos. Retorna string do bucket."""
    if bins is None:
        bins = [0, 2, 4, 6, 8, 10, 15, 20, 30, 50, 100]
    if value is None or value < 0:
        return "neg"
    for i in range(len(bins) - 1):
        if bins[i] <= value < bins[i + 1]:
            return f"b{i}"
    return "max"


def _aspect_ratio(coords: list) -> float:
    """Calcula aspect ratio aproximado de um poligono."""
    if not coords or len(coords) < 2:
        return 1.0
    xs = [c[0] for c in coords] if isinstance(coords[0], (list, tuple)) else []
    ys = [c[1] for c in coords] if isinstance(coords[0], (list, tuple)) else []
    if not xs or not ys:
        return 1.0
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if h == 0:
        return 1.0
    ratio = w / h
    if ratio < 1.0:
        ratio = 1.0 / ratio
    return round(ratio, 1)


def compute_context_signature(element_data: dict, class_type: str) -> str:
    """
    Gera hash normalizado da geometria + propriedades topologicas.
    Mesma forma geometrica = mesma assinatura, independente de posicao/rotacao.

    Args:
        element_data: dict com propriedades do elemento
        class_type: "slab" | "pillar" | "lateral_beam" | "bottom_beam"

    Returns:
        Hash MD5 de 16 caracteres (hex)
    """
    sig = {}

    if class_type == "slab":
        coords = element_data.get("coordenadas", [])
        sig["vertex_count"] = len(coords)
        sig["area_bucket"] = _bucketize(
            element_data.get("area", 0),
            bins=[0, 5, 10, 20, 50, 100]
        )
        sig["aspect_ratio_bucket"] = _bucketize(
            _aspect_ratio(coords),
            bins=[0, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0]
        )
        sig["has_pontaletes"] = element_data.get("pontaletes_total", 0) > 0
        sig["obstacle_count"] = len(element_data.get("obstaculos", []))

    elif class_type == "pillar":
        # NAO usa face_count (sempre 8, nao discrimina)
        sig["section_width_bucket"] = _bucketize(
            element_data.get("secao_comprimento", 0),
            bins=[0, 20, 25, 30, 35, 40, 50]
        )
        sig["section_height_bucket"] = _bucketize(
            element_data.get("secao_largura", 0),
            bins=[0, 20, 25, 30, 35, 40, 50]
        )
        vinculos = element_data.get("vinculos", {}) or {}
        beams_str = str(vinculos.get("beams", ""))
        sig["has_middle_beam"] = "V" in beams_str
        sig["adjacent_beam_count"] = element_data.get("adjacent_beam_count", 0)
        sig["laje_count"] = element_data.get("laje_count", 0)
        sig["pavimento_type"] = element_data.get("pavimento_type", "tipico")

    elif class_type == "bottom_beam":
        sig["segment_count"] = len(element_data.get("segments", []))
        sig["length_bucket"] = _bucketize(
            element_data.get("comprimento", 0),
            bins=[0, 1, 2, 3, 4, 5, 6, 8, 10, 15]
        )
        sig["has_painel_w"] = element_data.get("painel_w") is not None

    elif class_type == "lateral_beam":
        sig["segment_count"] = len(element_data.get("segments", []))
        sig["has_holes"] = len(element_data.get("holes", [])) > 0
        sig["length_bucket"] = _bucketize(
            element_data.get("comprimento", 0),
            bins=[0, 1, 2, 3, 4, 5, 6, 8, 10, 15]
        )

    # Gerar hash estavel
    sig_str = json.dumps(sig, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(sig_str.encode("utf-8")).hexdigest()[:16]
