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
    value = ficha.get("comprimento_total_fundo") or segment.get("length")
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
    longitudinal_segments = [
        segment for segment in all_source_segments
        if not _is_transverse_contaminant(segment)
    ]
    # Remova cruzamentos curtos somente quando houver uma alternativa melhor.
    # Se o SA entregou apenas esse trecho, preserve a unica geometria disponivel
    # para que N1->N3 consiga materializar uma ficha revisavel.
    contaminant_fallback = bool(
        all_source_segments and not longitudinal_segments
    )
    source_segments = longitudinal_segments or all_source_segments
    segments: list[dict[str, Any]] = []
    segment_widths: list[float] = []
    segment_heights: list[float] = []
    first_support = ""
    last_support = ""

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
        explicit_panels = source.get("panels") or ficha.get("panels")
        if isinstance(explicit_panels, list) and explicit_panels:
            segment["panels"] = explicit_panels
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
    if contaminant_fallback:
        contract["quality_warnings"] = [
            "FV N1 possui somente segmento curto com o mesmo apoio; "
            "geometria preservada para revisao humana"
        ]
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
