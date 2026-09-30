"""Compositor da ficha nativa HI-FI de fundos de viga do portal.

O estado estruturado do SA continua sendo a fonte de verdade do N1. O HTML
persistido pelo headless e' uma fonte de artefatos visuais/QA: dele extraimos o
SVG contextual, as camadas e a tabela N3 ja materializada. Nunca executamos JS
do pack nem usamos valores N2/N4 para preencher silenciosamente o N1.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from bs4 import BeautifulSoup

from . import ficha_reader, fv_operations
from src.core.fv_generation_contract import compute_panel_modules


SCHEMA = "portal.fv.ficha/v1"
_BEAM_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _segment_number(value: Any) -> int:
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else 0


def _number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    match = _NUMBER_RE.search(str(value))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _display_number(value: Optional[float]) -> Optional[int | float]:
    if value is None:
        return None
    return int(value) if value.is_integer() else value


def _strip_xml(svg: str) -> str:
    return re.sub(r"^\s*<\?xml[^>]*>\s*", "", svg or "", count=1).strip()


def _safe_read_svg(path: Path) -> Optional[str]:
    try:
        if not path.is_file() or path.suffix.lower() != ".svg":
            return None
        return _strip_xml(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def _candidate_htmls(
    obra_dir: Path, pavimento: str, beam: str, html_fichas_root: Optional[Path],
) -> list[Path]:
    candidates: list[Path] = []
    for pack in Path(obra_dir).glob(f"{pavimento}_*"):
        candidate = pack / "fundos_viga" / f"{beam}.html"
        if candidate.is_file():
            candidates.append(candidate)
    if html_fichas_root and Path(html_fichas_root).is_dir():
        for candidate in Path(html_fichas_root).rglob(f"{beam}.html"):
            parts_lower = {part.lower() for part in candidate.parts}
            if candidate.parent.name != "fundos_viga":
                continue
            if ".parity_failed" in parts_lower:
                continue
            candidates.append(candidate)
    unique = {str(path.resolve()): path for path in candidates}
    return sorted(
        unique.values(),
        key=lambda path: (path.stat().st_mtime, str(path)),
        reverse=True,
    )


def encontrar_ficha_fv(
    obra_dir: Path, pavimento: str, beam: str, html_fichas_root: Optional[Path] = None,
) -> Optional[Path]:
    if not beam or not _BEAM_RE.fullmatch(beam):
        return None
    candidates = _candidate_htmls(obra_dir, pavimento, beam, html_fichas_root)
    return candidates[0] if candidates else None


def _mini_fields(block) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in block.select(".fv-mini-field"):
        label = field.find("span")
        value = field.find("b")
        if label is not None:
            values[label.get_text(" ", strip=True)] = (
                value.get_text(" ", strip=True) if value is not None else None
            )
    return values


def _detail_from_row(detail) -> dict[str, Any]:
    result: dict[str, Any] = {"panels": [], "chamfers": {}, "openings": {}}
    if detail is None:
        return result
    for block in detail.select(".fv-mini-block"):
        title_el = block.select_one(".fv-mini-title")
        title = title_el.get_text(" ", strip=True).lower() if title_el else ""
        if "pain" in title:
            for row in block.select(".fv-panel-table tbody tr"):
                cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
                if len(cells) >= 3:
                    result["panels"].append({
                        "index": _segment_number(cells[0]),
                        "length_cm": _display_number(_number(cells[1])),
                        "width_cm": _display_number(_number(cells[2])),
                    })
        elif "chanfro" in title:
            result["chamfers"] = _mini_fields(block)
        elif "abertura" in title:
            result["openings"] = _mini_fields(block)
    return result


def _external_layer(layer, html_path: Path) -> Optional[str]:
    svg = layer.find("svg")
    if svg is not None:
        return str(svg)
    relative = layer.get("data-proposal-src") or layer.get("data-n3-src")
    if not relative:
        return None
    candidate = (html_path.parent / relative).resolve()
    try:
        candidate.relative_to(html_path.parent.resolve())
    except ValueError:
        return None
    return _safe_read_svg(candidate)


@lru_cache(maxsize=48)
def _parse_hifi_html(path_str: str, mtime_ns: int) -> dict[str, Any]:
    del mtime_ns  # faz parte da chave do cache
    path = Path(path_str)
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    segments: list[dict[str, Any]] = []
    for row in soup.select(".fv-seg-table tbody tr.fv-seg-item"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td", recursive=False)]
        if len(cells) < 9:
            continue
        index = _segment_number(row.get("data-seg") or cells[1])
        detail = row.find_next_sibling("tr", class_="fv-seg-detail")
        n3 = _detail_from_row(detail)
        n3["available"] = bool(n3["panels"])
        segments.append({
            "index": index,
            "length_cm": _display_number(_number(cells[2])),
            "width_cm": _display_number(_number(cells[3])),
            "beam_height_cm": _display_number(_number(cells[4])),
            "level": _display_number(_number(cells[5])),
            "support_start": cells[6] or None,
            "support_end": cells[7] or None,
            "n3": n3,
        })

    layers: dict[str, dict[str, Any]] = {
        name: {"available": False, "svg": None, "segments": []}
        for name in ("sa", "c1", "c2", "c3", "n3")
    }
    for name in ("sa", "c1", "c2", "c3", "n3"):
        layer = soup.select_one(f".fv-layer-{name}")
        svg = _external_layer(layer, path) if layer is not None else None
        layers[name] = {"available": bool(svg), "svg": svg}

    return {"segments": segments, "layers": layers, "html_version": "2.0"}


def _parse_hifi(path: Optional[Path]) -> dict[str, Any]:
    if path is None:
        return {"segments": [], "layers": {}, "html_version": None}
    try:
        return _parse_hifi_html(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError):
        return {"segments": [], "layers": {}, "html_version": None}


def _current_n3_contract(obra_dir: Path, pavimento: str, beam: str) -> tuple[Optional[Path], dict[str, Any]]:
    run = ficha_reader._latest_production_run(Path(obra_dir), pavimento)
    if run is None:
        return None, {}
    path = run / "n3" / "contracts" / f"{beam}_fundo.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, {}
    return path, payload if isinstance(payload, dict) else {}


def _contract_segments(contract: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    rows = contract.get("segments_rich") or contract.get("panels") or []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        length = _number(row.get("comprimento_total_fundo") or row.get("total_width") or row.get("width"))
        width = _number(row.get("largura_total_fundo") or contract.get("total_width"))
        modules = row.get("panels") if isinstance(row.get("panels"), list) else compute_panel_modules(length)
        panels = []
        for panel_index, module in enumerate(modules, 1):
            if isinstance(module, dict):
                module_length = _number(module.get("length") or module.get("width"))
            else:
                module_length = _number(module)
            panels.append({
                "index": panel_index,
                "length_cm": _display_number(module_length),
                "width_cm": _display_number(width),
            })
        result.append({
            "index": index,
            "length_cm": _display_number(length),
            "width_cm": _display_number(width),
            "beam_height_cm": _display_number(_number(row.get("altura_total") or contract.get("total_height"))),
            "level": _display_number(_number(row.get("nivel") or row.get("level"))),
            "support_start": row.get("texto_esq") or row.get("apoio_inicial") or None,
            "support_end": row.get("texto_dir") or row.get("apoio_final") or None,
            "n3": {"available": bool(panels), "panels": panels, "chamfers": {}, "openings": {}},
        })
    return result


def _state_segment(item: dict, slabs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    fields = item.get("campos") or {}
    from src.core.fundo_segment_levels import derive_fundo_segment_level
    stored_level = _number(fields.get("Nível"))
    level_result = derive_fundo_segment_level(
        item.get("points") or [], slabs or [], explicit_levels=(fields.get("Nível"),)
    )
    return {
        "id": item.get("item_id"),
        "index": _segment_number(fields.get("Segmento")),
        "length_cm": _display_number(_number(fields.get("Comprimento"))),
        "width_cm": _display_number(_number(fields.get("Largura"))),
        "beam_height_cm": None,
        "level": _display_number(level_result["value"]),
        "level_source": (item.get("level_source") if stored_level is not None else level_result["source"]),
        "level_slabs": (item.get("level_slabs") if stored_level is not None else level_result["slabs"]),
        "level_distance_cm": (
            item.get("level_distance_cm") if stored_level is not None else level_result.get("distance_cm")
        ),
        "support_start": None,
        "support_end": None,
        "n1": {"points": item.get("points") or [], "available": bool(item.get("points"))},
        "n3": {"available": False, "panels": [], "chamfers": {}, "openings": {}},
    }


def _merge_segment(base: dict[str, Any], rich: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not rich:
        return {**base, "enrichment_status": "absent"}
    base_length = _number(base.get("length_cm"))
    rich_length = _number(rich.get("length_cm"))
    base_width = _number(base.get("width_cm"))
    rich_width = _number(rich.get("width_cm"))
    length_matches = (
        base_length is None or rich_length is None or abs(base_length - rich_length) <= 0.20
    )
    width_matches = (
        base_width is None or rich_width is None or abs(base_width - rich_width) <= 0.05
    )
    if not (length_matches and width_matches):
        # Um HTML de outra segmentacao serve como evidencia, nunca como fonte
        # silenciosa para sobrescrever a geometria SA ativa.
        return {
            **base,
            "enrichment_status": "mismatch",
            "hifi_reference": {
                "length_cm": rich.get("length_cm"),
                "width_cm": rich.get("width_cm"),
            },
        }
    merged = dict(base)
    # Comprimento e largura permanecem os valores do SA atual. O HI-FI so'
    # completa os campos ausentes e o N3 quando a geometria corresponde.
    for key in ("beam_height_cm", "level", "support_start", "support_end", "n3"):
        if rich.get(key) is not None:
            merged[key] = rich[key]
    merged["enrichment_status"] = "matched"
    return merged


def montar_ficha_fv(
    obra_dir: Path,
    pavimento: str,
    beam: str,
    estado: dict,
    html_fichas_root: Optional[Path] = None,
    visual_mode: str | None = None,
) -> dict[str, Any]:
    """Monta uma ficha por viga, sem alterar qualquer artefato da obra."""
    if not _BEAM_RE.fullmatch(str(beam or "")):
        raise ValueError("nome de viga invalido")
    all_items = ficha_reader.listar_itens_n1(estado, "fundo")
    beams = sorted(
        {str(item.get("beam_name") or "") for item in all_items if item.get("beam_name")},
        key=lambda value: [int(part) if part.isdigit() else part.lower()
                           for part in re.split(r"(\d+)", value)],
    )
    if beam not in beams:
        raise LookupError("viga de fundo nao encontrada")
    state_items = [item for item in all_items if item.get("beam_name") == beam]
    state_segments = sorted(
        (_state_segment(item, estado.get("slabs") or []) for item in state_items),
        key=lambda item: item["index"],
    )

    override = fv_operations.load_override(obra_dir, pavimento, beam)
    source_beam = str(override.get("source_beam") or beam)
    contract_path, contract = _current_n3_contract(obra_dir, pavimento, beam)
    if not contract_path and source_beam != beam:
        contract_path, contract = _current_n3_contract(obra_dir, pavimento, source_beam)
    current_segments = _contract_segments(contract)
    html_path = encontrar_ficha_fv(obra_dir, pavimento, beam, html_fichas_root)
    hifi = _parse_hifi(html_path)
    # O contrato da rodada atual e' a fonte ativa do desenho. O HTML antigo
    # permanece apenas como referência de comparação e nunca preenche campos.
    rich_by_index = {segment["index"]: segment for segment in current_segments}
    segments = [_merge_segment(segment, rich_by_index.get(segment["index"])) for segment in state_segments]
    for segment in segments:
        custom = (override.get("segments") or {}).get(str(segment["index"]))
        if custom:
            segment["n3"] = {
                "available": bool(custom.get("panels")),
                "panels": custom.get("panels") or [],
                "chamfers": custom.get("chamfers") or [],
                "openings": custom.get("openings") or [],
                "manual_override": True,
            }
    enrichment = {
        status: sum(segment.get("enrichment_status") == status for segment in segments)
        for status in ("matched", "mismatch", "absent")
    }

    # Um pack mais novo pode conter uma tabela rica ainda nao espelhada no
    # snapshot lido pelo portal. Ela melhora a exibicao, mas nao ganha poder de
    # criar/remover segmentos N1: so enriquecemos indices ja presentes.
    index = beams.index(beam)
    layers: dict[str, dict[str, Any]] = {
        name: {"available": False, "svg": None}
        for name in ("sa", "c1", "c2", "c3", "n3")
    }
    hifi_sa = (hifi.get("layers") or {}).get("sa") or {}
    if hifi_sa.get("available") and hifi_sa.get("svg"):
        # A camada SA dos fundos é a representação contextual completa. Os
        # dados tabulares continuam vindo exclusivamente do estado SA atual.
        layers["sa"] = {"available": True, "svg": hifi_sa["svg"], "segments": []}
        sa_visual_origin = "hifi_contextual"
    else:
        # Não desenhar o polígono mínimo: ele aparenta ser uma ficha válida,
        # mas não contém cotas, textos, apoios nem o contexto estrutural.
        sa_visual_origin = "unavailable"
    if html_path:
        adopted_svg = _safe_read_svg(html_path.parent / "adotados" / f"{beam}_sa.svg")
        if adopted_svg:
            layers["sa"] = {"available": True, "svg": adopted_svg, "segments": []}
            sa_visual_origin = "human_adopted_agent_layer"
        proposals = html_path.parent / "propostas"
        for layer_name in ("c1", "c2", "c3"):
            proposal_svg = _safe_read_svg(
                proposals / f"{beam}_qa_proposta_{layer_name}.svg"
            )
            if proposal_svg:
                try:
                    layer_segments = fv_operations.proposal_segments(
                        proposals / f"{beam}_qa_proposta_{layer_name}.json", beam,
                    )
                except (OSError, ValueError):
                    layer_segments = []
                layers[layer_name] = {
                    "available": True, "svg": proposal_svg, "segments": layer_segments,
                }
    if state_segments:
        first = state_items[0]
        photo_item = dict(first)
        if source_beam != beam:
            photo_item["beam_name"] = source_beam
        current = ficha_reader.extrair_fotos_producao(
            obra_dir, pavimento, "fundo", photo_item, visual_mode,
        )
        layers["n3"] = {
            "available": bool(current.get("n3")), "svg": current.get("n3"),
            "segments": [{"index": row["index"]} for row in segments],
        }
    layers["sa"]["segments"] = [{"index": row["index"]} for row in segments]

    return {
        "schema": SCHEMA,
        "visual_mode": ficha_reader.modo_visual_n3(
            obra_dir, pavimento, "fundo", state_items[0] if state_items else {"beam_name": beam},
            visual_mode=visual_mode,
        ),
        "available_visual_modes": ficha_reader.modos_visuais_n3_disponiveis(
            obra_dir, pavimento, "fundo", state_items[0] if state_items else {"beam_name": beam},
        ),
        "obra": {"pavimento": pavimento},
        "beam": {
            "name": beam,
            "position": index + 1,
            "total_beams": len(beams),
            "segment_count": len(segments),
            "previous": beams[index - 1] if index > 0 else None,
            "next": beams[index + 1] if index + 1 < len(beams) else None,
        },
        "segments": segments,
        "human_notes": override.get("notes") or {},
        "annotations": override.get("annotations") or [],
        "context": {"layers": layers},
        "source": {
            "kind": "sa_state_plus_current_n3_contract" if contract_path else "sa_state",
            "contract": str(contract_path) if contract_path else None,
            "legacy_html_reference": html_path.name if html_path else None,
            "sa_visual_origin": sa_visual_origin,
            "segment_enrichment": enrichment,
        },
    }
