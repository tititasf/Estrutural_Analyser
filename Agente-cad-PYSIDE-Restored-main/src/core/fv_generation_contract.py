"""Canonical input contract shared by the FV N3/N4 generator."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

FV_ENGINE_ID = "ROBOT_FV_N3_N4"
FV_CONTRACT_VERSION = 3
PANEL_MODULE = 244.0
PANEL_MINIMUM = 30.0


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _dim_pair(value: Any) -> tuple[float, float]:
    match = re.search(
        r"\(?\s*(\d+(?:[.,]\d+)?)\s*[/xX]\s*(\d+(?:[.,]\d+)?)\s*\)?",
        str(value or ""),
    )
    if not match:
        return 0.0, 0.0
    values = sorted(_number(part) for part in match.groups())
    return values[0], values[1]


def _segment_length(segment: dict[str, Any]) -> float:
    ficha = segment.get("ficha") if isinstance(segment.get("ficha"), dict) else {}
    # ``length`` pertence ao segmento recém-publicado pelo SA e é a fonte
    # soberana. A subficha pode conservar um valor de uma interpretação
    # anterior; ela só serve como fallback quando o SA atual não mediu.
    value = segment.get("length") or ficha.get("comprimento_total_fundo")
    if _number(value) > 0:
        return _number(value)
    coord = segment.get("coord")
    if isinstance(coord, (list, tuple)) and len(coord) >= 2:
        return abs(_number(coord[1]) - _number(coord[0]))
    points = segment.get("geometry") or []
    if isinstance(points, list) and len(points) >= 2:
        total = 0.0
        for start, end in zip(points, points[1:]):
            if len(start) >= 2 and len(end) >= 2:
                dx = _number(end[0]) - _number(start[0])
                dy = _number(end[1]) - _number(start[1])
                total += (dx * dx + dy * dy) ** 0.5
        return total
    return 0.0


def compute_panel_modules(length: Any) -> list[float]:
    """Same generic panel distribution used by the current FV engine."""
    total = _number(length)
    if total <= 0:
        return []
    if total <= PANEL_MODULE:
        return [total]
    full = int(total // PANEL_MODULE)
    remainder = total - full * PANEL_MODULE
    if remainder < 0.5:
        return [PANEL_MODULE] * full
    if remainder < PANEL_MINIMUM:
        return [PANEL_MODULE] * (full - 1) + [PANEL_MODULE + remainder]
    return [PANEL_MODULE] * full + [remainder]


def _blank_apoio(text: Any) -> bool:
    t = str(text or "").strip()
    return t in ("", "—", "-", "N/A", "n/a", "None", "none", "null")


def chain_linear_segment_apoios(
    rows: list[dict[str, Any]],
    *,
    start_key: str = "ponto_inicial",
    end_key: str = "ponto_final",
) -> list[dict[str, Any]]:
    """If every span copied the beam-global end, set fim[i] = ini[i+1]."""
    if len(rows) < 2:
        return rows
    starts = [str(row.get(start_key) or "").strip() for row in rows]
    ends = [str(row.get(end_key) or "").strip() for row in rows]
    valid_ends = [end for end in ends if not _blank_apoio(end)]
    common = ""
    if valid_ends:
        common, count = Counter(valid_ends).most_common(1)[0]
        if count < max(2, (len(valid_ends) + 1) // 2):
            common = ""
    for i in range(len(rows) - 1):
        nxt = starts[i + 1]
        cur = ends[i]
        if _blank_apoio(nxt):
            continue
        copied_global = bool(common) and cur == common and nxt != common
        if _blank_apoio(cur) or copied_global:
            rows[i][end_key] = nxt
            ends[i] = nxt
    return rows


def merge_fv_source_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Consolidate every SA occurrence that belongs to the same canonical beam.

    ``BeamTracer`` can legitimately return more than one occurrence for a beam
    name (for example, interrupted/overlapping runs of V301).  The production
    adapter used to store contracts in a dict by name, so the last occurrence
    silently replaced the others.  This merge happens before the N3 contract is
    built, keeping all segments and ordering them on the structural axis.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for source in results or []:
        if not isinstance(source, dict):
            continue
        raw_name = str(source.get("viga_nome") or source.get("name") or "")
        match = re.search(r"(V[F]?\d+[A-Z]?)", raw_name.upper())
        name = match.group(1) if match else raw_name.upper().replace(".C", "")
        if not name:
            continue
        if name not in grouped:
            grouped[name] = []
            order.append(name)
        grouped[name].append(source)

    merged: list[dict[str, Any]] = []
    for name in order:
        sources = grouped[name]
        base = deepcopy(sources[0])
        segments: list[dict[str, Any]] = []
        for source in sources:
            for segment in source.get("segmentos_fundo") or []:
                if isinstance(segment, dict):
                    segments.append(deepcopy(segment))

        horizontal_votes = [bool(s.get("is_horizontal", True)) for s in sources]
        is_horizontal = Counter(horizontal_votes).most_common(1)[0][0]
        # A ordem publicada pelo SA define S1..Sn. Reordenar novamente pela
        # coordenada invertia vigas verticais e dissociava a ficha do viewer.
        # Ocorrências repetidas continuam consolidadas na ordem em que o SA as
        # forneceu; apenas a numeração final é normalizada.
        for index, segment in enumerate(segments, 1):
            segment["seg_index"] = index
        base["viga_nome"] = name
        base["is_horizontal"] = is_horizontal
        base["segmentos_fundo"] = segments
        base["panels_n1"] = len(segments)
        base["merged_lengths_count"] = len(segments)
        base["comprimento_fundo"] = round(sum(_segment_length(s) for s in segments), 3)
        merged.append(base)
    return merged


def overlay_fv_state_measurements(
    merged_results: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Overlay the exact structured SA measurements onto the N3 adapter input.

    The saved production state is the same source consumed by the web ficha.
    Pairing by canonical beam and SA segment order prevents stale values nested
    in an older per-segment ``ficha`` from replacing current measurements.
    """
    rows_by_beam: dict[str, list[dict[str, Any]]] = {}
    for row in state_rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("beam_name") or row.get("viga_nome") or "").upper()
        match = re.search(r"(V[F]?\d+[A-Z]?)", name)
        if match:
            rows_by_beam.setdefault(match.group(1), []).append(row)

    output = deepcopy(merged_results)
    for source in output:
        raw_name = str(source.get("viga_nome") or source.get("name") or "").upper()
        match = re.search(r"(V[F]?\d+[A-Z]?)", raw_name)
        name = match.group(1) if match else raw_name
        segments = source.get("segmentos_fundo") or []
        rows = rows_by_beam.get(name) or []
        if len(rows) != len(segments):
            continue
        for index, (segment, row) in enumerate(zip(segments, rows), 1):
            measured = _number(row.get("length"))
            if measured > 0:
                segment["length"] = measured
            points = row.get("points")
            if isinstance(points, list) and len(points) >= 2:
                segment["geometry"] = deepcopy(points)
            width = _number(row.get("width"))
            if width > 0:
                segment["dim_width"] = width
            segment["seg_index"] = index
            segment["sa_status"] = row.get("status") or "valid"
            if row.get("level") not in (None, ""):
                segment["nivel"] = row.get("level")
                segment["nivel_origem"] = row.get("level_source") or "sa_state"
                segment["nivel_lajes"] = list(row.get("level_slabs") or [])
                segment["nivel_distancia_cm"] = row.get("level_distance_cm")
        source["comprimento_fundo"] = round(
            sum(_number(segment.get("length")) for segment in segments), 3
        )
    return output


def _is_transverse_contaminant(segment: dict[str, Any]) -> bool:
    """Reject a short crossing mistakenly captured as longitudinal FV."""
    left = str(segment.get("apoio_inicial") or "").strip().upper()
    right = str(segment.get("apoio_final") or "").strip().upper()
    if not left or left != right:
        return False
    ficha = segment.get("ficha") if isinstance(segment.get("ficha"), dict) else {}
    depth = _number(segment.get("dim_height") or ficha.get("altura_total"))
    return _segment_length(segment) <= max(100.0, depth * 2.0)


def normalize_fv_generation_contract(
    viga_nome: str,
    ficha: dict[str, Any],
    *,
    floor: str = "Pavimento",
) -> dict[str, Any]:
    """Return the common FV schema consumed by the single N3/N4 engine.

    Rich N4 fields are never recomputed: this function only copies the ficha
    and fills fields absent from either lineage.
    """
    result = deepcopy(ficha) if isinstance(ficha, dict) else {}
    name_match = re.search(r"(V[F]?\d+[A-Z]?)", str(viga_nome).upper())
    name = name_match.group(1) if name_match else str(viga_nome).upper().replace(".C", "")
    segments = result.get("segments_rich")
    if not isinstance(segments, list):
        panels = result.get("panels")
        segments = panels if isinstance(panels, list) else []
    number_match = re.search(r"\d+", name)

    result.setdefault("contract_version", FV_CONTRACT_VERSION)
    result.setdefault("motor_id", FV_ENGINE_ID)
    result.setdefault("number", number_match.group(0) if number_match else name)
    result.setdefault("name", name)
    result.setdefault("floor", floor or "Pavimento")
    result.setdefault("side", "C")
    result.setdefault("total_width", 0.0)
    result.setdefault("total_height", 0.0)
    result["segments_rich"] = segments
    result["panels"] = segments
    result.setdefault("holes", [])
    result.setdefault("label_left", "")
    result.setdefault("label_right", "")
    result.setdefault(
        "pillar_left",
        {"active": False, "label": "", "width": 0.0, "length": 0.0},
    )
    result.setdefault(
        "pillar_right",
        {"active": False, "label": "", "width": 0.0, "length": 0.0},
    )
    result.setdefault("sarrafo_left_id", 0)
    result.setdefault("sarrafo_right_id", 0)
    return result


def build_fv_generation_contract(
    viga_nome: str,
    source_data: dict[str, Any],
    *,
    floor: str = "Pavimento",
) -> dict[str, Any]:
    """Convert the current SA/N1 FV result to the rich N3/N4 input schema."""
    name_match = re.search(r"(V[F]?\d+[A-Z]?)", str(viga_nome).upper())
    name = name_match.group(1) if name_match else str(viga_nome).upper().replace(".C", "")
    dim_width, dim_height = _dim_pair(
        source_data.get("dim") or source_data.get("dim_text")
    )
    all_source_segments = [
        segment for segment in source_data.get("segmentos_fundo", [])
        if isinstance(segment, dict)
    ]
    # O SA é a autoridade geométrica desta etapa. Um segmento curto ou com o
    # mesmo apoio nas duas pontas pode representar um vão real medido; o
    # adaptador N3 não pode reinterpretá-lo nem descartá-lo por heurística.
    # Eventuais contaminantes devem ser resolvidos no próprio motor SA, antes
    # da publicação do snapshot estruturado.
    source_segments = all_source_segments
    segments: list[dict[str, Any]] = []
    segment_widths: list[float] = []
    segment_heights: list[float] = []
    first_support = ""
    last_support = ""
    is_horizontal = bool(source_data.get("is_horizontal", True))

    for index, source in enumerate(source_segments):
        ficha = source.get("ficha") if isinstance(source.get("ficha"), dict) else {}
        length = _segment_length(source)
        if length <= 0:
            continue
        width = _number(
            source.get("dim_width")
            or ficha.get("largura_total_fundo")
            or dim_width
        )
        if source.get("special_geometry") == "orthogonal_l":
            # O snapshot estruturado mede a bbox do L (29/49 no V303), nao a
            # largura do corpo principal (19). Para modular o painel, a secao
            # declarada do segmento continua sendo a largura transversal real.
            declared_width, _declared_height = _dim_pair(
                source.get("dim_text") or source_data.get("dim_text")
            )
            if declared_width > 0:
                width = declared_width
        height = _number(
            source.get("dim_height") or ficha.get("altura_total") or dim_height
        )
        dim_width = dim_width or width
        dim_height = dim_height or height
        if width > 0:
            segment_widths.append(round(width, 3))
        if height > 0:
            segment_heights.append(round(height, 3))
        left = str(source.get("apoio_inicial") or "").strip()
        right = str(source.get("apoio_final") or "").strip()
        first_support = first_support or left
        last_support = right or last_support
        segment: dict[str, Any] = {
            "total_width": round(length, 3),
            "width": round(length, 3),
            "dim_text": source.get("dim_text") or source_data.get("dim_text") or "",
            "largura_total_fundo": round(width, 3),
            "comprimento_total_fundo": round(length, 3),
            "altura_total": round(height, 3),
            "texto_esq": left,
            "texto_dir": right,
            "row_break": index > 0,
        }
        if source.get("nivel") not in (None, ""):
            segment["nivel"] = source.get("nivel")
            segment["nivel_origem"] = source.get("nivel_origem") or source.get("level_source") or "sa"
            segment["nivel_lajes"] = list(source.get("nivel_lajes") or source.get("level_slabs") or [])
            segment["nivel_distancia_cm"] = source.get("nivel_distancia_cm", source.get("level_distance_cm"))
        explicit_panels = source.get("panels") or ficha.get("panels")
        if isinstance(explicit_panels, list) and explicit_panels:
            segment["panels"] = explicit_panels
        elif source.get("special_geometry") == "orthogonal_l":
            points = source.get("geometry") or []
            try:
                axis_values = [float(point[0 if is_horizontal else 1]) for point in points]
                transverse_values = [float(point[1 if is_horizontal else 0]) for point in points]
                axis_min = min(axis_values)
                axis_max = max(axis_values)
                transverse_span = max(transverse_values) - min(transverse_values)
                internal_axes = sorted({
                    value - axis_min for value in axis_values
                    if value > axis_min + 1e-3 and value < axis_max - 1e-3
                })
            except (IndexError, TypeError, ValueError):
                internal_axes = []
                transverse_span = 0.0
            if internal_axes and transverse_span > width:
                main_width = internal_axes[-1]
                leaf_width = max(0.0, length - main_width)
                modules = compute_panel_modules(main_width)
                segment["panels"] = [
                    {"width": round(module, 3), "height": round(width, 3)}
                    for module in modules
                ]
                segment["panels"].append({
                    "width": round(leaf_width, 3),
                    "height": round(transverse_span, 3),
                    "is_L_drop": True,
                    "l_side": "right",
                    "l_drop_depth": round(transverse_span - width, 3),
                    "special_geometry": "orthogonal_l",
                    "fv_l_incident": source.get("fv_l_incident") or "",
                })
                segment["special_geometry"] = "orthogonal_l"
        # Sem topologia explicita no N1, nao congele aqui uma regra de paineis.
        # O motor comum N3/N4 deve aplicar sua regra mais recente em draw_viga().
        # Isso evita que o adaptador N1 continue reproduzindo uma distribuicao
        # antiga depois que o gerador FV for refinado.
        for key in (
            "abertura_especial", "chanfro_esq_top", "chanfro_esq_fun",
            "chanfro_dir_top", "chanfro_dir_fun", "abertura_topo_esq",
            "abertura_topo_dir", "abertura_fundo_esq", "abertura_fundo_dir",
            "holes", "_multiplier",
        ):
            value = source.get(key, ficha.get(key))
            if value not in (None, "", "N/A"):
                segment[key] = value
        segments.append(segment)

    # A ficha do segmento e mais recente/especifica que o dim_text agregado da
    # viga. Em obras reais o cabecalho pode conservar 14/55 enquanto o fundo
    # validado do segmento e 19/55; o motor N4 usa a largura do segmento.
    if segment_widths:
        dim_width = Counter(segment_widths).most_common(1)[0][0]
    if segment_heights:
        dim_height = Counter(segment_heights).most_common(1)[0][0]

    contract = {
        "contract_version": FV_CONTRACT_VERSION,
        "motor_id": FV_ENGINE_ID,
        "name": name,
        "floor": floor or "Pavimento",
        "side": "C",
        "total_width": round(dim_width, 3),
        "total_height": round(dim_height, 3),
        "panels": segments,
        "segments_rich": segments,
        "holes": list(source_data.get("holes") or []),
        "label_left": first_support,
        "label_right": last_support,
        "pillar_left": {"active": bool(first_support), "label": first_support, "width": 0.0, "length": 0.0},
        "pillar_right": {"active": bool(last_support), "label": last_support, "width": 0.0, "length": 0.0},
        "apoio_inicial": first_support,
        "apoio_final": last_support,
        "observations": "Fonte: Structural Analyzer N1; contrato canonico FV N3/N4",
    }
    return normalize_fv_generation_contract(name, contract, floor=floor)


def materialize_fv_contract_from_db(
    *,
    db_path: str | Path,
    project_id: str,
    item_id: str,
    output_dir: str | Path,
    floor: str = "Pavimento",
) -> Path | None:
    """Materialize one current SA beam_element without touching DXF artifacts."""
    match = re.search(r"(V[F]?\d+[A-Z]?)", str(item_id).upper())
    wanted = match.group(1) if match else str(item_id).upper()
    with sqlite3.connect(str(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT viga_nome, campos_json FROM beam_elements "
            "WHERE project_id=? AND classe='FV' ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
    for row in rows:
        found = re.search(r"(V[F]?\d+[A-Z]?)", str(row["viga_nome"]).upper())
        if not found or found.group(1) != wanted:
            continue
        try:
            source = json.loads(row["campos_json"] or "{}")
        except json.JSONDecodeError:
            return None
        contract = build_fv_generation_contract(wanted, source, floor=floor)
        if not contract["segments_rich"]:
            return None
        target = Path(output_dir) / f"{wanted}_fundo.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
    return None
