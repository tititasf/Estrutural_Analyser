"""Canonical identity and safe consolidation for structural beams.

Legacy database versions stored fund/side segment labels (``FV-*``/``LV-*``)
as if they were structural beam names. A structural beam must always retain
its drawing identifier (``V329``, ``VF202``); FV/LV are views of that beam.
"""

from __future__ import annotations

from copy import deepcopy
import math
import re
from typing import Any, Iterable


_STRUCTURAL_RE = re.compile(r"^(VF|V)\s*[-.]?\s*(\d+)([A-Z]?)$", re.IGNORECASE)
_LEGACY_RE = re.compile(
    r"^(?:FV-|LV-|F\.|L\.)\s*((?:VF|V)\s*[-.]?\s*\d+[A-Z]?)"
    r"(?:\.[ABC])?(?:-\d+)?$",
    re.IGNORECASE,
)


def _as_structural_name(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    match = _STRUCTURAL_RE.fullmatch(text)
    if not match:
        return None
    return f"{match.group(1).upper()}{match.group(2)}{match.group(3).upper()}"


def _legacy_payload_name(value: Any) -> str | None:
    match = _LEGACY_RE.fullmatch(str(value or "").strip())
    return _as_structural_name(match.group(1)) if match else None


def _point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def _nearest_drawing_name(beam: dict[str, Any]) -> str | None:
    anchor = _point(beam.get("pos"))
    if anchor is None:
        return None

    candidates: list[tuple[float, str]] = []
    for item in beam.get("texts") or []:
        if not isinstance(item, dict):
            continue
        name = _as_structural_name(item.get("text"))
        pos = _point(item.get("pos"))
        if name and pos:
            candidates.append((math.dist(anchor, pos), name))
    return min(candidates, default=(0.0, None), key=lambda entry: entry[0])[1]


def canonical_beam_name(beam: dict[str, Any]) -> str:
    """Return the structural name, never an FV/LV segment-view identifier."""
    current = _as_structural_name(beam.get("name"))
    if current:
        field_name = _as_structural_name(
            (beam.get("fields") or {}).get("nome")
        )
        nearest = _nearest_drawing_name(beam)
        # A legacy rename could alter only ``name`` while retaining the
        # original traced geometry and its authoritative field/label.
        if (
            field_name
            and field_name != current
            and (nearest is None or nearest == field_name)
        ):
            return field_name
        return current

    legacy = _legacy_payload_name(beam.get("name"))
    if legacy:
        # In contaminated records the FV suffix was edited to another beam,
        # while ``pos`` still points to the original drawing label.
        return _nearest_drawing_name(beam) or legacy

    return str(beam.get("name") or "").strip()


def _identity_anchor(beam: dict[str, Any]) -> tuple[float, float] | None:
    pos = _point(beam.get("pos"))
    return (round(pos[0], 3), round(pos[1], 3)) if pos else None


def _primary_score(beam: dict[str, Any], canonical: str, index: int) -> tuple[int, int, int]:
    original = str(beam.get("name") or "").strip()
    plain_match = _as_structural_name(original) == canonical
    legacy_match = _legacy_payload_name(original) == canonical
    validated = len(beam.get("validated_fields") or [])
    return (2000 if plain_match else 1000 if legacy_match else 0, validated, -index)


def _field_coherence(beam: dict[str, Any], field: str, canonical: str) -> int:
    values = (beam.get("links") or {}).get(field)
    if not isinstance(values, dict):
        return 0
    texts = {
        _as_structural_name(item.get("text"))
        for slot in values.values()
        for item in (slot if isinstance(slot, list) else [])
        if isinstance(item, dict)
    }
    if canonical in texts:
        return 2
    return 0 if not any(texts) else -1


def _merge_unique(target: list[Any], source: Iterable[Any]) -> None:
    for value in source:
        if value not in target:
            target.append(deepcopy(value))


def _merge_duplicate(
    primary: dict[str, Any],
    duplicates: list[dict[str, Any]],
    canonical: str,
) -> None:
    all_sources = [primary, *duplicates]
    primary_fields = primary.setdefault("fields", {})
    primary_links = primary.setdefault("links", {})
    primary_validated = primary.setdefault("validated_fields", [])

    all_validated = {
        field
        for source in all_sources
        for field in (source.get("validated_fields") or [])
    }
    for field in sorted(all_validated):
        candidates = sorted(
            all_sources,
            key=lambda source: (
                _field_coherence(source, field, canonical),
                field in (source.get("fields") or {}),
                field in source,
            ),
            reverse=True,
        )
        winner = candidates[0]
        if field not in primary_validated:
            primary_validated.append(field)
        if field in (winner.get("fields") or {}) and field not in primary_fields:
            primary_fields[field] = deepcopy(winner["fields"][field])
        if field in winner and field not in primary:
            primary[field] = deepcopy(winner[field])
        if field in (winner.get("links") or {}) and field not in primary_links:
            primary_links[field] = deepcopy(winner["links"][field])

    target_na = primary.setdefault("na_fields", [])
    for source in duplicates:
        _merge_unique(target_na, source.get("na_fields") or [])

    for dict_key in ("validated_link_classes", "na_link_classes"):
        target = primary.setdefault(dict_key, {})
        for source in duplicates:
            for field, slots in (source.get(dict_key) or {}).items():
                _merge_unique(target.setdefault(field, []), slots or [])

    primary["is_validated"] = any(bool(source.get("is_validated")) for source in all_sources)
    primary["name"] = canonical
    if "name" in primary_fields:
        primary_fields["name"] = canonical


def consolidate_beam_identities(
    beams: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], int]:
    """Canonicalize names and collapse records sharing name and drawing anchor.

    Returns ``(beams, removed_ids, changed_count)``. Inputs are copied so a DB
    migration can be committed only after successful consolidation.
    """
    copied = [deepcopy(beam) for beam in beams if isinstance(beam, dict)]
    groups: dict[
        tuple[str, tuple[float, float] | None],
        list[tuple[int, dict[str, Any]]],
    ] = {}
    for index, beam in enumerate(copied):
        canonical = canonical_beam_name(beam)
        groups.setdefault((canonical, _identity_anchor(beam)), []).append((index, beam))

    consolidated: list[tuple[int, dict[str, Any]]] = []
    removed_ids: list[str] = []
    changed = 0
    for (canonical, _anchor), entries in groups.items():
        primary_index, primary = max(
            entries,
            key=lambda entry: _primary_score(entry[1], canonical, entry[0]),
        )
        duplicates = [beam for index, beam in entries if index != primary_index]
        old_name = str(primary.get("name") or "")
        _merge_duplicate(primary, duplicates, canonical)
        if old_name != canonical:
            changed += 1
        changed += len(duplicates)
        removed_ids.extend(
            str(beam["id"])
            for beam in duplicates
            if beam.get("id") and beam.get("id") != primary.get("id")
        )
        consolidated.append((min(index for index, _beam in entries), primary))

    consolidated.sort(key=lambda entry: entry[0])
    return [beam for _index, beam in consolidated], removed_ids, changed
