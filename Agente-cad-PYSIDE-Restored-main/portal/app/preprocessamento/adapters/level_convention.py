"""Leitura conservadora da convenção de níveis, sem alterar o extrator SA.

O helper legado reconhece apenas cotas positivas acima de 100. Anotações fora
desse domínio são preservadas como evidência pendente, não normalizadas por
suposição ou descartadas silenciosamente.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.core.niveis_extractor import extract_elevacao_tipica


_COTA = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
_FLOOR = re.compile(r"\b(?:\d+\s*[º°oa]?\s*PAV\.?|COBERTURA|T[EÉ]RREO|FUNDA[CÇ][AÃ]O)\b", re.I)
_METERS = re.compile(r"\b(?:METROS?|METERS?|M)\b", re.I)
_CENTIMETERS = re.compile(r"\b(?:CENT[IÍ]METROS?|CENTIMETERS?|CM)\b", re.I)
_LEVEL_UNIT = re.compile(
    r"\b(?:N[IÍ]VEIS|COTAS?)\s+EM\s+"
    r"(CENT[IÍ]METROS?|CENTIMETERS?|CM|METROS?|METERS?|M)\b", re.I,
)


def _declared_level_units(declarations: list[dict]) -> set[str]:
    """Separa a unidade das cotas da unidade geral do desenho.

    Uma prancha pode declarar medidas geométricas em cm e níveis em m na
    mesma anotação. Só a declaração que nomeia níveis/cotas governa cotas.
    """
    specific = [match.group(1) for text in declarations
                for match in _LEVEL_UNIT.finditer(text["text"])]
    if specific:
        return {"cm" if _CENTIMETERS.fullmatch(value) else "m" for value in specific}
    return {"cm" if _CENTIMETERS.search(text["text"]) else "m"
            for text in declarations}


def _direct_floor_levels(labels: list[dict], cotas: list[dict], unit: str | None) -> list[dict]:
    """Pareia somente cota na mesma linha; empates continuam alternativas."""
    readings: list[dict] = []
    for label in labels:
        options = [
            cota for cota in cotas
            if abs(cota["pos"][1] - label["pos"][1]) <= 60.0
            and 0.0 < cota["pos"][0] - label["pos"][0] <= 600.0
        ]
        if options:
            nearest = min(abs(cota["pos"][1] - label["pos"][1]) for cota in options)
            options = [
                cota for cota in options
                if abs(abs(cota["pos"][1] - label["pos"][1]) - nearest) <= 1e-6
            ]
        candidates = [{
            "raw": cota["text"],
            "value": float(cota["text"].replace(",", ".")),
            "unit": unit,
            "text_handle": cota["handle"] or None,
            "position": list(cota["pos"]),
        } for cota in options]
        readings.append({
            "floor_label": label["text"],
            "floor_text_handle": label["handle"] or None,
            "status": "direct" if len(candidates) == 1 else "ambiguous" if candidates else "unknown",
            "selected": candidates[0] if len(candidates) == 1 else None,
            "candidates": candidates,
            "datum": None,
        })
    owners: dict[str, int] = {}
    for reading in readings:
        selected = reading["selected"]
        if selected and selected["text_handle"]:
            handle = selected["text_handle"]
            owners[handle] = owners.get(handle, 0) + 1
    for reading in readings:
        selected = reading["selected"]
        if selected and selected["text_handle"] and owners[selected["text_handle"]] > 1:
            reading["status"] = "ambiguous"
            reading["selected"] = None
            reading["warnings"] = ["cota_compartilhada_por_pavimentos"]
    return readings


def extract_level_convention(dxf_path: Path) -> dict[str, Any]:
    import ezdxf

    document = ezdxf.readfile(str(dxf_path))
    texts: list[dict[str, Any]] = []
    for entity in document.modelspace():
        if entity.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        try:
            raw = entity.dxf.text if entity.dxftype() == "TEXT" else entity.plain_mtext()
            insertion = entity.dxf.insert
            texts.append({
                "text": str(raw).strip(),
                "pos": (float(insertion.x), float(insertion.y)),
                "handle": str(entity.dxf.handle or ""),
            })
        except (AttributeError, TypeError, ValueError):
            continue

    labels = [text for text in texts if _FLOOR.search(text["text"])]
    raw_cotas = [text for text in texts if _COTA.fullmatch(text["text"])]
    declarations = [text for text in texts if _METERS.search(text["text"]) or _CENTIMETERS.search(text["text"])]
    units_seen = _declared_level_units(declarations)
    unit = next(iter(units_seen)) if len(units_seen) == 1 else None
    rows = extract_elevacao_tipica(texts)
    direct_levels = _direct_floor_levels(labels, raw_cotas, unit)
    warnings: list[str] = []
    if not labels:
        warnings.append("rotulo_pavimento_ausente")
    if not raw_cotas:
        warnings.append("cotas_ausentes")
    if not units_seen:
        warnings.append("unidade_nao_declarada")
    if len(units_seen) > 1:
        warnings.append("unidades_conflitantes")
    if any(float(text["text"].replace(",", ".")) <= 100 for text in raw_cotas):
        warnings.append("cotas_fora_do_dominio_do_extrator_legado")
    if any(row["chegada"] == "?" for row in rows):
        warnings.append("chegada_indeterminada")
    return {
        "status": "complete" if rows and all(row["chegada"] != "?" for row in rows) and not warnings else "partial",
        "unit": unit,
        "datum": None,
        "unit_declarations": declarations,
        "floor_labels": labels,
        "raw_cotas": raw_cotas,
        "rows": rows,
        "direct_floor_levels": direct_levels,
        "warnings": warnings,
        "provenance": "src.core.niveis_extractor.extract_elevacao_tipica",
    }
