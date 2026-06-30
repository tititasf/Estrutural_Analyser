"""Contrato puro entre os segmentos produzidos pelo SA e a pre-ficha.

Este modulo nao depende de Qt. A UI apenas apresenta as entradas retornadas por
``collect_preficha_segments`` e devolve decisoes para
``apply_preficha_segment_decisions``. Assim, a geometria exibida e a mesma
referencia que permanece no objeto de viga depois da confirmacao.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable


SEGMENT_TAB_SPECS: dict[str, dict[str, str]] = {
    "fundo": {
        "title": "Segmentos Fundos",
        "side": "Fundo",
        "behavior": "Fundo",
        "slot": "contour",
    },
    "lateral_a_para": {
        "title": "Segmentos Lateral A Para",
        "side": "A",
        "behavior": "Para",
        "slot": "seg_side_a",
    },
    "lateral_b_para": {
        "title": "Segmentos Lateral B Para",
        "side": "B",
        "behavior": "Para",
        "slot": "seg_side_b",
    },
    "lateral_a_passa": {
        "title": "Segmentos Lateral A Passa",
        "side": "A",
        "behavior": "Passa",
        "slot": "seg_side_a",
    },
    "lateral_b_passa": {
        "title": "Segmentos Lateral B Passa",
        "side": "B",
        "behavior": "Passa",
        "slot": "seg_side_b",
    },
}

_FUNDO_RE = re.compile(r"^viga_fundo_seg_(\d+)_area_segs$")
_LATERAL_RE = re.compile(
    r"^viga_([ab])_seg_(\d+)_(comprimento_total|comp_total_passa)$"
)


def _polyline_length(points: Iterable[Any]) -> float:
    clean: list[tuple[float, float]] = []
    for point in points or []:
        try:
            clean.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return sum(
        math.hypot(x2 - x1, y2 - y1)
        for (x1, y1), (x2, y2) in zip(clean, clean[1:])
    )


def _kind_for_link(link_key: str) -> tuple[str, int, str] | None:
    fundo_match = _FUNDO_RE.match(link_key)
    if fundo_match:
        return "fundo", int(fundo_match.group(1)), "contour"

    lateral_match = _LATERAL_RE.match(link_key)
    if not lateral_match:
        return None
    side, segment_index, suffix = lateral_match.groups()
    behavior = "para" if suffix == "comprimento_total" else "passa"
    return f"lateral_{side}_{behavior}", int(segment_index), f"seg_side_{side}"


def collect_preficha_segments(beams: list[dict] | None) -> dict[str, list[dict]]:
    """Normaliza os links SA nas cinco listas de segmentos da pre-ficha.

    Cada entrada conserva referencias internas para a viga e para o link. Essas
    referencias nao devem ser serializadas; elas garantem que aplicar uma decisao
    altere exatamente o objeto que foi exibido.
    """
    result = {kind: [] for kind in SEGMENT_TAB_SPECS}
    for beam_index, beam in enumerate(beams or []):
        if not isinstance(beam, dict):
            continue
        beam_name = str(beam.get("parent_name") or beam.get("name") or f"Viga {beam_index + 1}")
        beam_identity = str(beam.get("id") or beam.get("name") or f"beam-{beam_index + 1}")
        stored = beam.get("preficha_segmentos") or {}
        links = beam.get("links") or {}
        if not isinstance(links, dict):
            continue

        for link_key, slots in links.items():
            parsed = _kind_for_link(str(link_key))
            if not parsed or not isinstance(slots, dict):
                continue
            kind, segment_index, slot = parsed
            raw_entries = slots.get(slot) or []
            if not isinstance(raw_entries, list):
                continue
            spec = SEGMENT_TAB_SPECS[kind]
            for occurrence, link in enumerate(raw_entries, start=1):
                if not isinstance(link, dict):
                    continue
                points = link.get("points") or []
                uid = f"{kind}|{beam_identity}|{segment_index}|{occurrence}"
                previous = stored.get(uid) if isinstance(stored, dict) else {}
                length = link.get("len")
                try:
                    length = float(length)
                except (TypeError, ValueError):
                    length = _polyline_length(points)
                ficha = dict(link.get("ficha") or {})
                fields = beam.get("fields") or {}
                width = (
                    ficha.get("largura_total_fundo")
                    or fields.get(f"viga_fundo_seg_{segment_index}_largura")
                    or fields.get(f"viga_fundo_seg_{segment_index}_dim")
                    or ""
                )
                result[kind].append({
                    "uid": uid,
                    "kind": kind,
                    "beam_name": beam_name,
                    "beam_identity": beam_identity,
                    "segment_index": segment_index,
                    "occurrence": occurrence,
                    "segment_label": (
                        str(segment_index)
                        if len(raw_entries) == 1
                        else f"{segment_index}.{occurrence}"
                    ),
                    "side": spec["side"],
                    "behavior": spec["behavior"],
                    "length": round(length, 2),
                    "width": str(width),
                    "points": points,
                    "tag": str(link.get("tag") or spec["side"]),
                    "ficha": ficha,
                    "status": str((previous or {}).get("status") or "valid"),
                    "attention": str((previous or {}).get("attention") or ""),
                    "source_key": str(link_key),
                    "source_slot": slot,
                    "_beam_ref": beam,
                    "_link_ref": link,
                })

    for entries in result.values():
        entries.sort(key=lambda item: (
            _natural_key(item["beam_name"]),
            item["segment_index"],
            item["occurrence"],
        ))
    return result


def apply_preficha_segment_decisions(
    beams: list[dict] | None,
    decisions: dict[str, dict] | None,
) -> dict[str, int]:
    """Persiste notas/status e remove links ignorados dos mesmos objetos SA."""
    decisions = decisions or {}
    collected = collect_preficha_segments(beams)
    entries = [entry for values in collected.values() for entry in values]
    removed = 0
    reviewed = 0

    # Remover por identidade em uma segunda passagem evita deslocamento de indices.
    removals: list[tuple[dict, str, dict]] = []
    for entry in entries:
        decision = decisions.get(entry["uid"], {})
        status = str(decision.get("status") or entry.get("status") or "valid")
        attention = str(decision.get("attention") or "").strip()
        beam = entry["_beam_ref"]
        beam.setdefault("preficha_segmentos", {})[entry["uid"]] = {
            "status": status,
            "attention": attention,
            "source_key": entry["source_key"],
            "saved_by": "preficha_sa",
        }
        reviewed += 1
        if status == "ignore":
            removals.append((beam, entry["source_key"], entry["_link_ref"]))

    for beam, source_key, link_ref in removals:
        slots = (beam.get("links") or {}).get(source_key) or {}
        parsed = _kind_for_link(source_key)
        if not parsed:
            continue
        kind, segment_index, slot_name = parsed
        values = slots.get(slot_name) or []
        for index in range(len(values) - 1, -1, -1):
            if values[index] is link_ref:
                values.pop(index)
                removed += 1
                break
        if values:
            continue
        if kind == "fundo":
            beam[f"viga_fundo_seg_{segment_index}_exists"] = False
            continue
        side = SEGMENT_TAB_SPECS[kind]["side"].lower()
        related_keys = (
            f"viga_{side}_seg_{segment_index}_comprimento_total",
            f"viga_{side}_seg_{segment_index}_comp_total_passa",
        )
        has_related_link = any(
            any((beam.get("links") or {}).get(key, {}).get(f"seg_side_{side}") or [])
            for key in related_keys
        )
        if not has_related_link:
            beam[f"viga_{side}_seg_{segment_index}_exists"] = False

    return {"reviewed": reviewed, "removed": removed}


def serializable_segment(entry: dict) -> dict:
    """Remove referencias internas para logs, HTML e testes."""
    return {key: value for key, value in entry.items() if not key.startswith("_")}


def _natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]
