"""Compositor da ficha web de laterais de viga (Lado A/B, Para/Passa)."""

from __future__ import annotations

import re
import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Optional

from . import dxf_preview, ficha_reader, lv_operations
from src.core.preficha_segments import _touching_slabs, _text_from_entity, _cell_adjustment
from src.core.fundo_segment_levels import derive_fundo_segment_level


_BEAM_RE = re.compile(r"(?:V|VF)\d+[A-Z]?", re.IGNORECASE)
_CLASSES = {
    "para": {"A": "lateral_a_para", "B": "lateral_b_para"},
    "passa": {"A": "lateral_a_passa", "B": "lateral_b_passa"},
}


def _natural(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _number(value: Any) -> float | None:
    if value in (None, "", "—", "-"):
        return None
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value))
    return float(match.group(0).replace(",", ".")) if match else None


def _dimensions(value: Any) -> tuple[float | None, float | None]:
    values = re.findall(r"[-+]?\d+(?:[.,]\d+)?", str(value or ""))
    parsed = [float(item.replace(",", ".")) for item in values]
    return (parsed[0] if parsed else None, parsed[1] if len(parsed) > 1 else None)


def _slabs_on_side(points: list, side: str, slabs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Restringe a associação de cota à mesma face da lateral."""
    if len(points) < 2:
        return []
    first, last = points[0], points[-1]
    horizontal = abs(last[0] - first[0]) >= abs(last[1] - first[1])
    middle = (first[1] + last[1]) / 2 if horizontal else (first[0] + last[0]) / 2
    selected = []
    for slab in slabs:
        polygon = slab.get("points") or []
        if len(polygon) < 3:
            continue
        center = sum(float(p[1] if horizontal else p[0]) for p in polygon) / len(polygon)
        on_side = (center >= middle if side == "A" else center <= middle) if horizontal else (
            center <= middle if side == "A" else center >= middle
        )
        if on_side:
            selected.append(slab)
    return selected


def _opening_from_link(slots: dict[str, Any]) -> dict[str, Any] | None:
    labels = slots.get("arr_label") or slots.get("label") or []
    dims = slots.get("arr_dim") or []
    label = next((text for value in labels if (text := _text_from_entity(value))), "")
    match = _BEAM_RE.search(label)
    if not match:
        return None
    name = match.group(0).upper()
    dimension = next((text for value in dims if (text := _text_from_entity(value))), "")
    level = next((value for entity in labels + dims if isinstance(entity, dict)
                  for value in ((entity.get("ficha") or {}).get("nivel_viga"),
                                (entity.get("ficha") or {}).get("nivel"))
                  if _number(value) is not None), None)
    return {"name": name, "dimension": dimension, "level": _number(level)}


def _segment(
    obra_dir: Path,
    pavimento: str,
    classe: str,
    item: dict[str, Any],
    *,
    include_svgs: bool,
    slabs: list[dict[str, Any]] | None = None,
    beam_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fields = item.get("campos") or {}
    width, height = _dimensions(fields.get("Largura"))
    index = int(_number(fields.get("Segmento")) or 0)
    side = classe.split("_")[1].upper()
    beam_record = beam_record or {}
    prefix = f"viga_{side.lower()}_seg_{index}"
    direct_level = _number(beam_record.get(f"{prefix}_nivel_viga"))
    touching = _touching_slabs(item.get("points") or [], side, slabs or [], limit=None)
    slab_rows = [{"name": slab.get("name"), "level": slab.get("level")}
                 for slab in touching if slab.get("name")]
    slab_levels = [_number(row["level"]) for row in slab_rows]
    slab_levels = [value for value in slab_levels if value is not None]
    stored_level = _number(fields.get("Nível"))
    nearest = None
    if stored_level is None and direct_level is None and not slab_levels:
        nearest = derive_fundo_segment_level(
            item.get("points") or [],
            _slabs_on_side(item.get("points") or [], side, slabs or []),
        )
    level = stored_level if stored_level is not None else (
        direct_level if direct_level is not None else (
            max(slab_levels) if slab_levels else (nearest or {}).get("value")
        )
    )
    openings = []
    link_key = f"{prefix}_{'comprimento_total' if classe.endswith('para') else 'comp_total_passa'}"
    links = beam_record.get("links") or {}
    if not isinstance(links, dict):
        links = {}
    linked = (links.get(link_key) or {}).get(f"seg_side_{side.lower()}") or []
    cell = item.get("lv_cell") or (linked[0].get("lv_cell") if linked else None) or {}
    if linked:
        # Exported cells can predate the current analysis. Use the current
        # association only for this exact physical span, never the first row
        # of a split link or a neighbouring segment.
        def span_key(points):
            return tuple(sorted((round(float(p[0]), 2), round(float(p[1]), 2))
                                for p in points or []))
        key = span_key(item.get('points'))
        current_cells = [row['lv_cell'] for row in linked
                         if isinstance(row, dict) and isinstance(row.get('lv_cell'), dict)
                         and key and span_key(row.get('points')) == key]
        if len(current_cells) == 1:
            cell = current_cells[0]
    # The canonical cell already resolves directed A/B geometry and slab regions.
    # A second generic side search can reverse the displayed slab while retaining
    # the cell's level. Project its associations, including an explicit empty set.
    if isinstance(cell.get("slabs"), list):
        slab_rows = [dict(row) for row in cell["slabs"]
                     if isinstance(row, dict) and row.get("name")]
        slab_levels = [value for row in slab_rows
                       if (value := _number(row.get("level"))) is not None]
        if stored_level is None and direct_level is None:
            level = _number(cell.get("level"))
            if level is None and slab_levels:
                level = max(slab_levels)
            nearest = None
        elif item.get('level_source') in ('lv_cell_slabs', 'lv_cell_estimado'):
            # This scalar is derived from the cell, not an independent beam
            # annotation. A fresh local cell must supersede the stale exported
            # scalar; explicit/manual beam levels keep their precedence.
            current_level = _number(cell.get('level'))
            if current_level is not None:
                level = current_level
    for opening in cell.get("beam_openings") or []:
        if isinstance(opening, dict) and opening.get("name"):
            openings.append({"name": opening["name"], "dimension": opening.get("dim") or "",
                             "level": _number(opening.get("level") or opening.get("nivel"))})
            position = _number(opening.get("pos_inicio"))
            opening_width = _number(opening.get("largura"))
            length = _number(fields.get("Comprimento"))
            if position is not None and opening_width is not None and length is not None:
                left = max(0.0, position)
                right = max(0.0, length - position - opening_width)
                openings[-1].update({
                    "position_cm": position, "width_cm": opening_width,
                    "distance_left_cm": round(left, 2), "distance_right_cm": round(right, 2),
                    "location": "esquerda" if left <= 0.5 else "direita" if right <= 0.5 else "interna",
                    "opening_width_cm": opening.get("abertura_largura"),
                    "opening_height_cm": opening.get("abertura_altura"),
                    "remaining_height_cm": opening.get("sobra"),
                })
    if not cell:
        for key, slots in links.items():
            if str(key).startswith(f"{prefix}_abert_viga_") and isinstance(slots, dict):
                opening = _opening_from_link(slots)
                if opening:
                    openings.append(opening)
    openings_status = "verified" if cell or any(
        str(key).startswith(f"{prefix}_abert_viga_") for key in links
    ) else "sa_data_unavailable"
    photos = (
        ficha_reader.resolver_fotos_portal(obra_dir, pavimento, classe, item)
        if include_svgs else {"n1": None, "n3": None}
    )
    return {
        "id": item.get("item_id"),
        "index": index,
        "length_cm": _number(fields.get("Comprimento")),
        "width_cm": width,
        "beam_height_cm": height,
        "level": level,
        "level_source": (item.get("level_source") if stored_level is not None else
                         "sa_beam_segment" if direct_level is not None else
                         "sa_touching_slabs" if slab_levels else
                         "sa_nearest_same_side_slab" if level is not None else "unresolved"),
        "level_distance_cm": (nearest or {}).get("distance_cm"),
        "slabs": slab_rows,
        "beam_openings": openings,
        "beam_openings_status": openings_status,
        "adjustment": _cell_adjustment(cell),
        "support_start": dict(cell.get("support_start") or {}),
        "support_end": dict(cell.get("support_end") or {}),
        "status": fields.get("Status"),
        "attention": item.get("atencao") or "",
        "points": item.get("points") or [],
        "pillar_openings": [],
        "layers": {
            "sa": {"available": bool(photos.get("n1")) if include_svgs else True,
                   "lazy": not include_svgs, "svg": photos.get("n1")},
            "c1": {"available": False, "svg": None},
            "c2": {"available": False, "svg": None},
            "c3": {"available": False, "svg": None},
            "n3_panels": {"available": bool(photos.get("n3")) if include_svgs else True,
                          "lazy": not include_svgs, "svg": photos.get("n3")},
        },
    }


def _beam_records(estado: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Lê apenas os registros de viga referidos pelos segmentos do estado SA."""
    if estado.get('_section_beam_records') is not None:
        return dict(estado['_section_beam_records'])
    path = Path(str(estado.get("db_path") or ""))
    if not path.is_file():
        # Ephemeral preprocessing/second-pass context carries the same scoped
        # records directly; it must not query an unrelated production database.
        return dict(estado.get("_section_beam_records") or {})
    ids = {str(item.get("item_id") or "").split("|")[1]
           for item in items if len(str(item.get("item_id") or "").split("|")) > 1}
    if not ids:
        return {}
    result = {}
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as conn:
        for beam_id in ids:
            row = conn.execute("SELECT data_json, project_id FROM beams WHERE id = ?", (beam_id,)).fetchone()
            if row and row[0]:
                result[beam_id] = {**json.loads(row[0]), 'project_id': row[1]}
    return result


def _complete_opening_levels(
    estado: dict[str, Any], sides: dict[str, dict[str, Any]], records: dict[str, dict[str, Any]],
    reference_context: dict | None = None,
) -> None:
    """Cruza a abertura com cotas explícitas da própria viga incidente no SA."""
    for side in sides.values():
        for segment in side["segments"]:
            for opening in segment["beam_openings"]:
                if opening.get("level") is not None:
                    opening["level_source"] = "sa_opening"
    pending = {opening["name"] for side in sides.values() for segment in side["segments"]
               for opening in segment["beam_openings"] if opening.get("level") is None}
    if not pending:
        return
    levels: dict[str, set[float]] = {name: set() for name in pending}
    for items in (estado.get("segmentos") or {}).values():
        for raw in items or []:
            name = str(raw.get("beam_name") or "").upper()
            if name in levels and (value := _number(raw.get("level"))) is not None:
                levels[name].add(value)
    path = Path(str(estado.get("db_path") or ""))
    project_ids = {str(record.get("project_id")) for record in records.values()
                   if record.get("project_id")}
    if path.is_file() and len(project_ids) == 1:
        # One section inventory revisits incident beams across both behaviors.
        # Reuse only within that inventory's snapshot, never across requests.
        cache = reference_context.setdefault('opening_levels', {}) if reference_context is not None else {}
        project = next(iter(project_ids))
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as conn:
            for name in pending:
                cache_key = (str(path.resolve()), project, name)
                if cache_key in cache:
                    levels[name].update(cache[cache_key])
                    continue
                found = set()
                for (raw_json,) in conn.execute(
                    "SELECT data_json FROM beams WHERE project_id = ? AND UPPER(name) = ?",
                    (project, name),
                ):
                    raw = json.loads(raw_json or "{}")
                    for key, value in raw.items():
                        if (key == "nivel_viga" or re.fullmatch(r"viga_[ab]_seg_\d+_nivel_viga", key)):
                            if (number := _number(value)) is not None:
                                found.add(number)
                cache[cache_key] = frozenset(found)
                levels[name].update(found)
    for side in sides.values():
        for segment in side["segments"]:
            for opening in segment["beam_openings"]:
                if opening.get("level") is not None:
                    continue
                candidates = levels.get(opening["name"], set())
                if len(candidates) == 1:
                    opening["level"] = next(iter(candidates))
                    opening["level_source"] = "sa_related_beam"
                else:
                    opening["level_source"] = "conflict" if candidates else "unresolved"
                    # Bounds can prove clearance without selecting a datum
                    # from conflicting local occurrences of the same beam.
                    opening['level_candidates_m'] = sorted(candidates)


def _cut_views(
    obra_dir: Path,
    pavimento: str,
    beam: str,
    estado: dict[str, Any],
    *,
    include_svgs: bool,
    sides: dict | None = None,
    records: dict | None = None,
    inventory: dict | None = None,
    reference_context: dict | None = None,
) -> list[dict[str, Any]]:
    from .lv_cut_sources import load_sources
    from . import corte_references
    from src.core.lv_cut_inventory import pair_sections, section_svg
    # Request-local reuse: every beam sees the same snapshot, but sources can
    # differ by project. Key associations by their actual geometry and SA name.
    context = reference_context if reference_context is not None else {}
    project_key = frozenset(r.get('project_id') for r in (records or {}).values()
                            if r.get('project_id'))
    sources = context.setdefault('sources', {})
    if project_key not in sources:
        sources[project_key] = load_sources(obra_dir, pavimento, estado, records or {})
    slabs, explicit, receipt = sources[project_key]
    if 'segments' not in context:
        context['segments'] = corte_references.preparar_segmentos(estado)
    references = context['segments']
    associations = context.setdefault('associations', {})
    result = []
    pending = []
    from src.core.lv_cut_datum import connected_soffit_beams
    neighbor_names = connected_soffit_beams(beam, (estado.get('segmentos') or {}).get('fundo', []))
    neighboring_originals = []
    for raw in explicit:
        reference_key = (str(raw.get('beam_name') or ''),
                         json.dumps(raw.get('pts') or [], sort_keys=True))
        if reference_key not in associations:
            associations[reference_key] = corte_references.associar_referencias(raw, references)
        refs = associations[reference_key]
        selected_name = refs.get('nome_sugerido') or raw.get('beam_name')
        if not selected_name or not _BEAM_RE.fullmatch(str(selected_name)):
            pending.append({'id': raw['uid'], 'label':raw.get('raw_text') or 'Corte sem viga',
                            'origins':raw['origins'], 'evidence_ids':raw['evidence_ids'], 'status':'Associação pendente'})
        if str(selected_name or "").upper() != beam.upper():
            if selected_name in neighbor_names:
                neighboring_originals.append(dict(id=raw['uid'], beam=selected_name,
                                                  kind='identified', source_cut=raw))
            continue
        raw = dict(raw, beam_name=beam)
        item = ficha_reader._normalizar_corte(raw, {  # fonte canônica já usada pelo portal
            slab.get("name"): slab for slab in estado.get("slabs") or [] if slab.get("name")
        })
        photos = (
            ficha_reader.resolver_fotos_portal(obra_dir, pavimento, "cortes", item)
            if include_svgs else {"n1": None, "n3": None}
        )
        result.append({
            "id": item.get("item_id"),
            "kind": "identified",
            "origins": raw.get('origins'),
            "evidence_ids": raw.get('evidence_ids'),
            "ficha": raw.get('ficha') or {},
            "source_cut": raw,
            "references": refs,
            "association_source": "fv_lv_geometry" if refs.get('nome_sugerido') else "sa_assignment",
            "pairs": [],
            "beam": beam,
            "own_slab": raw.get("own_laje"),
            "neighbor_slab": raw.get("neigh_laje"),
            "beam_height_cm": _number(raw.get("beam_h")),
            "confidence_percent": raw.get("conf_pct"),
            "status": raw.get("status"),
            "attention": raw.get("atencao") or ("Associação SA a confirmar" if not refs.get('nome_sugerido') else ""),
            "layers": {
                "sa": {"available": bool(photos.get("n1")) if include_svgs else True,
                       "lazy": not include_svgs, "svg": photos.get("n1")},
                "n3_cut": {"available": False, "svg": None},
            },
        })
    from src.core.lv_cut_inventory import prepare_slab_regions
    regions = context.setdefault('slab_regions', {})
    if project_key not in regions:
        regions[project_key] = prepare_slab_regions(slabs)
    calculated, diagnostic = pair_sections(beam, "passa" if (sides or {}).get('A',{}).get('class','').endswith('passa') else 'para', sides or {}, slabs, estado.get('pilares') or [], slab_regions=regions[project_key])
    cap_sections = []
    # Contact queries need concrete at beam crossings even when the lateral
    # wall has an opening there. Keep this inventory separate from drawings.
    physical_sections, _ = pair_sections(beam, 'passa' if (sides or {}).get('A',{}).get('class','').endswith('passa') else 'para',
        sides or {}, slabs, estado.get('pilares') or [], retain_opening_intervals=True, slab_regions=regions[project_key])
    from src.core.lv_cut_datum import apply_original_datums
    calculated = apply_original_datums(calculated, result, slabs, regions[project_key],
                                       neighboring_originals=neighboring_originals,
                                       regional_originals=[dict(id=r['uid'], beam=r.get('beam_name'),
                                           kind='identified', source_cut=r) for r in explicit])
    # Original schematic dimensions anchor the displayed section. They do not
    # establish an independent collision datum for every remote beam joint.
    # Keep contact/collision evidence local until that joint is confirmed.
    if any((r.get('source_cut') or {}).get('section_semantics', {}).get('confirmed') for r in result):
        from src.core.beam_vertical_context import apply_inverted_sections
        calculated = apply_inverted_sections(calculated, result)
        from src.core.beam_vertical_context import attach_local_inverted_references
        labels = [label for record in (records or {}).values()
                  if str(record.get('name') or (record.get('fields') or {}).get('nome') or '').upper() == beam.upper()
                  for label in (record.get('links') or {}).get('dimensoes') or []]
        labels.extend(receipt.get('dimension_labels') or [])
        calculated = attach_local_inverted_references(calculated, labels, slabs)
        # A lateral opening does not necessarily interrupt a cap above the
        # incident beam. Keep this additional coverage out of LV wall drawings.
        # A pillar cannot provide the inverted beam's vertical datum. Cap
        # clearance retains its strict support exclusions.
        unmasked = apply_inverted_sections(physical_sections, result)
        unmasked = attach_local_inverted_references(unmasked, labels, slabs)
        from src.core.beam_vertical_context import clear_top_cap_interferences
        cap_sections = clear_top_cap_interferences(unmasked, calculated)
        physical_sections = [*calculated, *cap_sections]
    from .structural_review import apply_levels, load as load_section_reviews
    decisions = estado.get('_section_review')
    if decisions is None:
        decisions = load_section_reviews(obra_dir, pavimento)
    calculated = apply_levels(calculated, decisions, beam, slabs)
    physical_sections = apply_levels(physical_sections, decisions, beam, slabs)
    for cut in calculated:
        svg = section_svg(cut) if include_svgs else None
        cut['layers'] = {'sa': {'available': bool(section_svg(cut)), 'lazy':not include_svgs, 'svg':svg},
                         'n3_cut': {'available':False, 'svg':None}}
    result.extend(calculated)
    from src.core.lv_cut_equivalence import group_equivalent_cuts
    identified_count = len(result)-len(calculated)
    source_count = len(result)
    # Physical SA occurrences are retained before executive N3 equivalence.
    # The structural viewer places these against every soffit segment.
    from copy import deepcopy
    sa_sections = deepcopy(result)
    result = group_equivalent_cuts(result)
    from . import lv_n3_cuts
    for cut in result:
        cut['layers']['n3_cut'] = lv_n3_cuts.layer(cut)
    if inventory is not None:
        inventory.update(schema='cad.sa.lv_cut_inventory/v1', calculated_sections=len(calculated),
                         identified_cuts=identified_count, unique_sections=len(result),
                         source_sections=source_count, merged_sections=source_count-len(result), preprocessing=receipt,
                         pending=pending, **diagnostic)
        inventory['sa_sections'] = sa_sections
        inventory['cap_sections'] = cap_sections
        inventory['physical_sections'] = physical_sections
    return result


def montar_ficha_lv(
    obra_dir: Path,
    pavimento: str,
    beam: str,
    behavior: str,
    estado: dict[str, Any],
    *,
    include_svgs: bool = True,
    reference_context: dict | None = None,
) -> dict[str, Any]:
    behavior = str(behavior or "").lower()
    if behavior not in _CLASSES:
        raise ValueError("comportamento deve ser para ou passa")
    if not _BEAM_RE.fullmatch(str(beam or "")):
        raise ValueError("nome de viga lateral inválido")

    override = lv_operations.load_override(obra_dir, pavimento, behavior, beam)
    by_side: dict[str, dict[str, Any]] = {}
    all_beams: set[str] = set()
    all_selected = [item for side_class in _CLASSES[behavior].values()
                    for item in ficha_reader.listar_itens_n1(estado, side_class)
                    if str(item.get("beam_name") or "").upper() == beam.upper()]
    beam_records = _beam_records(estado, all_selected)
    for side, classe in _CLASSES[behavior].items():
        all_items = ficha_reader.listar_itens_n1(estado, classe)
        all_beams.update(str(item.get("beam_name") or "") for item in all_items if item.get("beam_name"))
        selected = [item for item in all_items if str(item.get("beam_name") or "").upper() == beam.upper()]
        segments = sorted(
            (_segment(obra_dir, pavimento, classe, item, include_svgs=include_svgs,
                      slabs=estado.get("slabs") or [],
                      beam_record=beam_records.get(str(item.get("item_id") or "").split("|")[1], {})
                      if len(str(item.get("item_id") or "").split("|")) > 1 else {})
             for item in selected),
            key=lambda item: item["index"],
        )
        side_overrides = (override.get("sides") or {}).get(side) or {}
        for segment in segments:
            manual = side_overrides.get(str(segment["index"])) or {}
            segment["pillar_openings"] = list(manual.get("pillar_openings") or [])
        by_side[side] = {
            "class": classe,
            "segments": segments,
        }

    _complete_opening_levels(estado, by_side, beam_records, reference_context)
    from .lv_segment_relations import pillar_passages
    for side_data in by_side.values():
        for segment in side_data["segments"]:
            segment["pillar_passages"] = pillar_passages(
                segment["points"], estado.get("pilares") or [], behavior,
            )

    beams = sorted(all_beams, key=_natural)
    canonical = next((name for name in beams if name.upper() == beam.upper()), None)
    if canonical is None:
        raise LookupError("viga lateral não encontrada")
    position = beams.index(canonical)
    cut_inventory = {}
    cuts = _cut_views(obra_dir, pavimento, canonical, estado, include_svgs=include_svgs,
                      sides=by_side, records=beam_records, inventory=cut_inventory,
                      reference_context=reference_context)
    return {
        "schema": "cad.portal.lv_ficha/v1",
        "beam": {
            "name": canonical,
            "behavior": behavior,
            "behavior_label": (
                "Segmentos param nos pilares" if behavior == "para"
                else "Segmentos passam pelos pilares"
            ),
            "position": position + 1,
            "total_beams": len(beams),
            "previous": beams[position - 1] if position > 0 else None,
            "next": beams[position + 1] if position + 1 < len(beams) else None,
        },
        "sides": by_side,
        "cut_views": cuts,
        "sa_cut_views": cut_inventory.pop('sa_sections', cuts),
        "cap_cut_views": cut_inventory.pop('cap_sections', []),
        "physical_cut_views": cut_inventory.pop('physical_sections', []),
        "cut_inventory": cut_inventory,
    }


def _torre_context_payload(
    obra_id: str, fonte: dict[str, Any], itens: list[dict[str, Any]],
    frame_px: tuple[float, float], pad_px: float = 140.0,
) -> dict[str, Any]:
    """Recorte (viewBox) + destaques sobre a MESMA torre limpa do pavimento.

    Reaproveita a fonte de verdade que já funciona no destaque do estrutural
    limpo (`/obras/{id}/viewer/{pavimento}`): a viga aparece com o entorno
    estrutural real e uma tag, em vez do plot isolado (sem contexto, sem
    nome) que a ficha HTML gera para o card "N1 próximo/local".

    `pontos_px`/`viewbox` estão no espaço px do transform (`frame_px`), não
    nas unidades do SVG da foto (matplotlib emite em pt: 1200px -> 864pt). O
    cliente converte px -> unidades do SVG, como o overlay do estrutural limpo.
    """
    xs = [float(p[0]) for item in itens for p in item["pontos_px"]]
    ys = [float(p[1]) for item in itens for p in item["pontos_px"]]
    x0, x1 = min(xs) - pad_px, max(xs) + pad_px
    y0, y1 = min(ys) - pad_px, max(ys) + pad_px
    return {
        "mode": "torre_context",
        "svg_url": (
            f"/obras/{obra_id}/recortes/brutos/{fonte['bruto_id']}"
            f"/{fonte['item_id']}/foto"
        ),
        "viewbox": [x0, y0, max(x1 - x0, 1.0), max(y1 - y0, 1.0)],
        "frame_px": [float(frame_px[0]), float(frame_px[1])],
        "highlights": [
            {"points": item["pontos_px"], "label": item["rotulo"]}
            for item in itens
        ],
    }


def _torre_context_itens(
    obra_dir: Path, pavimento: str, estado: dict[str, Any], classe: str,
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]], tuple[float, float]]:
    """Torre limpa + geometria/px de uma classe SA, via a mesma via do viewer.

    Import local para não acoplar o boot deste módulo de serviço ao pacote de
    routers (evita risco de import circular; `viewer_routes` não importa nada
    deste arquivo, então a dependência é só nesta direção, só aqui dentro).
    """
    from .routers import viewer_routes

    fonte = viewer_routes.encontrar_estrutural_limpo(obra_dir, {}, pavimento)
    if fonte is None:
        return None, [], (0.0, 0.0)
    caminho = Path(fonte["path"])
    if not caminho.is_file():
        return None, [], (0.0, 0.0)
    try:
        transform = dxf_preview.transform_preview_completo(
            caminho, cache_dir=obra_dir / ".previews",
        )
    except Exception:  # noqa: BLE001 - DXF pode ter geometria não suportada
        return None, [], (0.0, 0.0)
    if transform is None:
        return None, [], (0.0, 0.0)
    return (
        fonte,
        viewer_routes._geometria_dos_itens(estado, classe, transform),
        (float(transform.largura_px), float(transform.altura_px)),
    )


def _torre_context_one(
    obra_dir: Path, pavimento: str, obra_id: str, estado: dict[str, Any],
    classe: str, beam: str, segment_index: int,
) -> Optional[dict[str, Any]]:
    fonte, itens, frame_px = _torre_context_itens(obra_dir, pavimento, estado, classe)
    if fonte is None:
        return None
    alvo = next(
        (item for item in itens
         if str(item.get("beam_name") or "").upper() == beam.upper()
         and str(item.get("segmento") or "").strip() == str(segment_index)),
        None,
    )
    if alvo is None:
        return None
    return _torre_context_payload(obra_id, fonte, [alvo], frame_px)


def _torre_context_all(
    obra_dir: Path, pavimento: str, obra_id: str, estado: dict[str, Any],
    classe: str, beam: str,
) -> Optional[dict[str, Any]]:
    fonte, itens, frame_px = _torre_context_itens(obra_dir, pavimento, estado, classe)
    if fonte is None:
        return None
    alvos = [
        item for item in itens
        if str(item.get("beam_name") or "").upper() == beam.upper()
    ]
    if not alvos:
        return None
    return _torre_context_payload(obra_id, fonte, alvos, frame_px)


def _stack_cut_svgs(drawings: list[str]) -> str | None:
    if not drawings:
        return None
    if len(drawings) == 1:
        return drawings[0]
    namespace = "http://www.w3.org/2000/svg"
    # A string é inserida em HTML: ns0:svg seria um elemento HTML desconhecido.
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}svg")
    offset = 0.0
    for index, drawing in enumerate(drawings):
        # IDs dos desenhos independentes não podem colidir na visão Todos.
        node = ET.fromstring(drawing)
        ids = {item.get("id"): f"vc{index}_{item.get('id')}" for item in node.iter() if item.get("id")}
        for item in node.iter():
            for attr, value in list(item.attrib.items()):
                if attr == "id":
                    item.set(attr, ids[value])
                else:
                    for original, renamed in ids.items():
                        value = value.replace(f"url(#{original})", f"url(#{renamed})")
                        if value == f"#{original}":
                            value = f"#{renamed}"
                    item.set(attr, value)
        box = [float(value) for value in re.split(r"[ ,]+", node.get("viewBox", "0 0 1200 700").strip())]
        height = 1200 * box[3] / box[2]
        node.set("x", "0")
        node.set("y", str(offset))
        node.set("width", "1200")
        node.set("height", str(height))
        root.append(node)
        offset += height
    root.set("viewBox", f"0 0 1200 {offset}")
    return ET.tostring(root, encoding="unicode")


def resolver_camada_lv(
    obra_dir: Path,
    pavimento: str,
    beam: str,
    behavior: str,
    estado: dict[str, Any],
    layer: str,
    *,
    obra_id: str,
    side: str = "A",
    segment_index: int = 1,
    cut_index: int = 0,
    visual_mode: str = "NOVA",
    assembly: str = "sarrafeadas",
) -> dict[str, Any]:
    """Materializa apenas a camada atualmente visível, preservando o SVG canônico.

    `segment_index <= 0` e `cut_index < 0` são os sentinelas da aba "Todos"
    (todos os segmentos do lado / todos os cortes). N3 Visão Corte materializa
    cada contrato SA em artefato derivado próprio e reúne seus SVGs; painéis
    continuam utilizando as cartas laterais canônicas.
    """
    behavior = behavior.lower()
    side = side.upper()
    if behavior not in _CLASSES or side not in {"A", "B"}:
        raise ValueError("lateral inválida")
    classe = _CLASSES[behavior][side]

    if layer in {"c1", "c2", "c3"}:
        from .qa_versions import availability
        return {"layer":layer, **availability(obra_dir, pavimento, "LV", beam, behavior)[1].get(layer, {"available":False, "svg":None})}

    if layer == "n3_panels":
        from . import lv_n3_panels
        return dict(lv_n3_panels.resolve(obra_dir,pavimento,behavior,beam,side,
                    segment_index,visual_mode,assembly),layer=layer)
    if layer == "cut_map":
        from .lv_cut_map import structural_payload
        data = montar_ficha_lv(obra_dir, pavimento, beam, behavior, estado, include_svgs=False)
        payload = structural_payload(Path(obra_dir), pavimento, obra_id, estado, beam, behavior, data)
        return {"layer": layer, "available": bool(payload), **(payload or {})}

    if layer in {"sa_cut", "n3_cut"}:
        from src.core.lv_cut_inventory import section_svg
        cut_data = montar_ficha_lv(obra_dir, pavimento, beam, behavior, estado, include_svgs=False)
        cuts = cut_data['cut_views']
        if layer == 'sa_cut' and cut_index < 0:
            from .lv_cut_map import structural_payload
            payload = structural_payload(Path(obra_dir), pavimento, obra_id, estado,
                                         beam, behavior, cut_data)
            return {'layer':layer, 'available':bool(payload), **(payload or {})}
        if layer == 'sa_cut' and 0 <= cut_index < len(cuts) :
            from .lv_cut_map import structural_payload
            payload = structural_payload(Path(obra_dir), pavimento, obra_id, estado,
                                         beam, behavior, cut_data, cut_index=cut_index)
            if payload and payload.get('section_drawings'):
                return {'layer':layer, 'available':True, **payload}
            # Preserve the original viewer when geometry cannot be oriented safely.
            if cuts[cut_index]['kind'] == 'calculated':
                return {'layer':layer, 'available':False, **(payload or {})}
        def sa_photo(cut):
            if cut['kind']=='calculated':
                return {'svg':section_svg(cut),'origem':'sa_pares_ab'}
            item = ficha_reader._normalizar_corte(cut['source_cut'], {s.get('name'):s for s in estado.get('slabs',[])})
            return ficha_reader.resolver_foto_portal(obra_dir, pavimento, 'cortes', item, 'n1')
        if cut_index < 0 and layer == "n3_cut":
            from . import lv_n3_cuts
            drawings = []
            blocked = []
            for cut in cuts:
                info = cut['layers']['n3_cut']
                if not info['available']:
                    blocked.append({'id':cut['id'],'reason':info.get('reason')})
                    continue
                drawings.append(lv_n3_cuts.resolve(obra_dir,pavimento,behavior,cut,visual_mode,assembly)['svg'])
            svg = _stack_cut_svgs(drawings)
            return {"layer":layer,"available":bool(svg),"svg":svg,"origin":"sa_cut_contract",
                    "generated_cuts":len(drawings),"blocked_cuts":blocked}
        if cut_index < 0:
            # Montagem dos cortes SA publicados, preservando cada viewBox.
            drawings = []
            for item in cuts:
                photo = sa_photo(item)
                if photo.get("svg"):
                    drawings.append(photo["svg"])
            svg = _stack_cut_svgs(drawings)
            return {"layer": layer, "available": bool(svg), "svg": svg, "origin": "sa_cortes" if svg else None}
        if cut_index >= len(cuts):
            raise LookupError("visão de corte não encontrada")
        if layer == 'n3_cut':
            from . import lv_n3_cuts
            if not cuts[cut_index]['layers']['n3_cut']['available']:
                return dict(cuts[cut_index]['layers']['n3_cut'],layer=layer)
            return dict(lv_n3_cuts.resolve(obra_dir,pavimento,behavior,cuts[cut_index],visual_mode,assembly),layer=layer)
        photo = sa_photo(cuts[cut_index])
        svg = photo.get("svg")
        return {"layer": layer, "available": bool(svg), "svg": svg,
                "origin": photo.get("origem")}

    if layer not in {"sa", "n3_panels"}:
        raise ValueError("camada lateral inválida")

    if layer == "sa":
        from .qa_interpretation import effective_svg
        adopted = effective_svg(obra_dir, pavimento, 'LV', beam, estado, behavior)
        if adopted:
            return {'layer':'sa', 'available':True, 'svg':adopted, 'origin':'human_validated_qa'}
        card = (
            _torre_context_all(obra_dir, pavimento, obra_id, estado, classe, beam)
            if segment_index <= 0
            else _torre_context_one(obra_dir, pavimento, obra_id, estado, classe, beam, segment_index)
        )
        if card is not None:
            return {"layer": "sa", "available": True, "origin": "torre_limpa", **card}
        # Fallback: estrutural limpo ainda não gerado para este pavimento —
        # mantém o card local da ficha (sem contexto) em vez de ficar vazio.
        if segment_index <= 0:
            return {"layer": "sa", "available": False, "svg": None, "origin": None}
        items = [
            item for item in ficha_reader.listar_itens_n1(estado, classe)
            if str(item.get("beam_name") or "").upper() == beam.upper()
            and int(_number((item.get("campos") or {}).get("Segmento")) or 0) == segment_index
        ]
        if not items:
            raise LookupError("segmento lateral não encontrado")
        photo = ficha_reader.resolver_foto_portal(obra_dir, pavimento, classe, items[0], "n1")
        svg = photo.get("svg")
        return {"layer": "sa", "available": bool(svg), "svg": svg, "origin": photo.get("origem")}

    # layer == "n3_panels"
    if segment_index <= 0:
        svg = ficha_reader.extrair_svg_lateral_global(
            obra_dir, pavimento, classe, beam, f"N3 · Lateral {side}",
        )
        return {"layer": layer, "available": bool(svg), "svg": svg,
                 "origin": "ficha_html_global" if svg else None}
    items = [
        item for item in ficha_reader.listar_itens_n1(estado, classe)
        if str(item.get("beam_name") or "").upper() == beam.upper()
        and int(_number((item.get("campos") or {}).get("Segmento")) or 0) == segment_index
    ]
    if not items:
        raise LookupError("segmento lateral não encontrado")
    photo = ficha_reader.resolver_foto_portal(obra_dir, pavimento, classe, items[0], "n3")
    svg = photo.get("svg")
    return {"layer": layer, "available": bool(svg), "svg": svg, "origin": photo.get("origem")}
