"""Referências geométricas FV/LV para cortes; não altera a interpretação SA.

O símbolo do corte é uma seção, não um painel nem um comprimento de viga.
Sobreposição/proximidade local só produz uma hipótese rastreável. FV e LV
vêm do mesmo SA: concordância entre eles não é validação independente do DXF.
"""
from __future__ import annotations

import math
import re

from shapely.geometry import LineString, Polygon
from shapely.validation import make_valid


CLASSES = {
    "fundo": "Referência · fundos de viga",
    "lateral_a_para": "Referência · lateral A Para",
    "lateral_b_para": "Referência · lateral B Para",
    "lateral_a_passa": "Referência · lateral A Passa",
    "lateral_b_passa": "Referência · lateral B Passa",
}


def _geometry(points, polygon=False):
    try:
        pts = [(float(p[0]), float(p[1])) for p in points or []]
        if not all(math.isfinite(v) for p in pts for v in p):
            return None
        if len(pts) < (3 if polygon else 2):
            return None
        geom = make_valid(Polygon(pts)) if polygon else LineString(pts)
        if geom.is_empty or (polygon and geom.area <= 0):
            return None
        return geom
    except (TypeError, ValueError, IndexError):
        return None


def preparar_segmentos(estado: dict) -> list[tuple]:
    """Geometrias reais do snapshot atual, sem pesquisa pelo nome do corte."""
    result = []
    for classe in CLASSES:
        for segment in (estado.get("segmentos") or {}).get(classe, []) or []:
            if not isinstance(segment, dict):
                continue
            name = str(segment.get("beam_name") or "").strip()
            if not name or not segment.get("uid"):
                continue
            geom = _geometry(segment.get("points"), polygon=classe == "fundo")
            if geom is None:
                continue
            # Largura da faixa, não altura (19/55 -> 19 cm). Apenas delimita
            # o entorno pesquisado; nunca impõe compatibilidade dimensional.
            match = re.match(r"\s*(\d+(?:[.,]\d+)?)", str(segment.get("width") or ""))
            width = float(match[1].replace(",", ".")) if match else 0.0
            if not width and classe == "fundo":
                corners = list(geom.minimum_rotated_rectangle.exterior.coords)
                width = min(math.dist(a, b) for a, b in zip(corners, corners[1:]))
            result.append((classe, segment, geom, width))
    return result


def associar_referencias(corte: dict, segmentos: list[tuple]) -> dict:
    geom = _geometry(corte.get("pts"), polygon=True)
    result = {"nome_sugerido": None, "status": "sem_referencia", "candidatos": [],
              "segmentos": {k: [] for k in CLASSES},
              "origem": "segmentos_sa_geometria_local", "altera_sa": False}
    if geom is None:
        result["motivo"] = "Geometria do corte ausente ou inválida; associação pendente."
        return result
    x0, y0, x1, y1 = geom.bounds
    span = max(x1 - x0, y1 - y0)
    by_name = {}
    for classe, segment, target, width in segmentos:
        distance = geom.distance(target)
        # Uma faixa de largura conhecida ou 1/4 do símbolo quando ausente.
        # 0,5 cm absorve arredondamento CAD, não cria vínculo semântico.
        tolerance = max(0.5, width or span * 0.25)
        if distance > tolerance:
            continue
        name = str(segment["beam_name"]).strip()
        reference = {
            "classe": classe, "item_id": str(segment["uid"]), "beam_name": name,
            "segment_label": str(segment.get("segment_label") or "?"),
            "side": segment.get("side"), "behavior": segment.get("behavior"),
            "distancia_cm": round(distance, 2), "contato": distance <= 0.5,
            "lajes": segment.get("level_slabs") or [],
        }
        group = by_name.setdefault(name, {"fundo": [], "lateral": [], "refs": []})
        group["fundo" if classe == "fundo" else "lateral"].append(reference)
        group["refs"].append(reference)
    # FV e LV no mesmo local corroboram uma hipótese. Para/Passa e A/B
    # não são votos repetidos, e empate de nomes continua ambíguo.
    supported = [name for name, group in by_name.items()
                 if any(r["contato"] for r in group["fundo"]) and group["lateral"]]
    result["candidatos"] = sorted(by_name)
    if len(supported) == 1 and len(by_name) == 1:
        name = supported[0]
        result["nome_sugerido"] = name
        same = name.casefold() == str(corte.get("beam_name") or "").strip().casefold()
        result["status"] = "concordante" if same else "divergente"
        result["motivo"] = (
            f"FV e LV locais definem {name} para este corte; "
            + ("concordam com o nome SA." if same else "divergem do nome SA.")
            + " Nome aplicado à ficha, à lista e ao destaque do corte."
        )
    elif len(by_name) > 1:
        result["status"] = "ambigua"
        result["motivo"] = "Referências locais com nomes concorrentes: " + ", ".join(sorted(by_name)) + ". Associação pendente."
    elif by_name:
        result["status"] = "parcial"
        result["motivo"] = "Referência parcial: sem contato de fundo corroborado por lateral. Associação pendente."
    else:
        result["motivo"] = "Nenhum segmento FV/LV no entorno do corte; associação pendente."
    for group in by_name.values():
        for ref in group["refs"]:
            result["segmentos"][ref["classe"]].append(ref)
    for refs in result["segmentos"].values():
        refs.sort(key=lambda r: (r["distancia_cm"], r["beam_name"], r["segment_label"], r["item_id"]))
    return result


def campos_referencia(result: dict) -> dict:
    fields = {
        "Viga definida · FV/LV": result["nome_sugerido"] or "Pendente",
        "Associação · referência": result["motivo"],
    }
    for classe, label in CLASSES.items():
        refs = result["segmentos"][classe]
        fields[label] = "; ".join(
            f"{r['beam_name']} · segmento {r['segment_label']}"
            + (" · contato" if r["contato"] else f" · a {r['distancia_cm']:g} cm")
            for r in refs
        ) or "Sem referência local"
    return fields
