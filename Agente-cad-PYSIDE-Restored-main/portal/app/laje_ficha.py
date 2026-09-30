"""Contrato enxuto da ficha web de lajes, com camadas carregadas sob demanda."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import ficha_reader, laje_operations


def _natural(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def _latest_contract(obra_dir: Path, pavimento: str, name: str) -> tuple[dict[str, Any], Path | None]:
    root = Path(obra_dir) / "Fase-6_Execucao_CAD" / "production_sa" / pavimento
    candidates = sorted(root.glob(f"*/n3/contracts_lj/{name}.json"), reverse=True)
    for path in candidates:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value, path
        except (OSError, json.JSONDecodeError):
            continue
    fallback = Path(obra_dir) / "Fase-4_Sincronizacao" / "JSON_Lajes" / f"{name}.json"
    try:
        value = json.loads(fallback.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            return value, fallback
    except (OSError, json.JSONDecodeError):
        pass
    return {}, None


def _line_rows(value: Any) -> list[dict[str, Any]]:
    result = []
    for row in value or []:
        if isinstance(row, dict) and row.get("value") is not None:
            result.append({"value": row.get("value"), "is_union": bool(row.get("is_union", False))})
    return result


def _panel_rows(lines: list[dict[str, Any]], total: Any) -> list[dict[str, Any]]:
    """Traduz posições acumuladas de juntas nas larguras que o desenho exibe."""
    try:
        extent = round(float(total), 3)
    except (TypeError, ValueError):
        return []
    if extent <= 0:
        return []
    positions = sorted({round(float(row["value"]), 3) for row in lines})
    positions = [value for value in positions if 0 < value < extent]
    boundaries = [0.0, *positions, extent]
    result = []
    for index, (start, end) in enumerate(zip(boundaries, boundaries[1:]), start=1):
        result.append({
            "index": index,
            "start": start,
            "end": end,
            "value": round(end - start, 3),
            "is_remainder": index == len(boundaries) - 1,
        })
    return result


def montar_ficha_laje(
    obra_dir: Path, pavimento: str, name: str, estado: dict[str, Any], *,
    include_svgs: bool = False, visual_mode: str | None = None,
) -> dict[str, Any]:
    items = ficha_reader.listar_itens_n1(estado, "lajes")
    item = next((row for row in items if str(row.get("item_id") or "").upper() == name.upper()), None)
    if item is None:
        raise LookupError("laje não encontrada")
    names = sorted((str(row.get("item_id")) for row in items if row.get("item_id")), key=_natural)
    canonical = str(item["item_id"])
    position = names.index(canonical)
    contract, contract_path = _latest_contract(obra_dir, pavimento, canonical)
    override = laje_operations.load_override(obra_dir, pavimento, canonical)
    override_n3 = override.get("n3") or {}
    has_override = bool(override_n3.get("linhas_verticais") or override_n3.get("linhas_horizontais"))
    n3 = override_n3 if has_override else contract
    photos = {"n1": None, "n3": None}
    if include_svgs:
        # O SA contextual e o N3 compacto vêm da mesma leitura de produção.
        # Assim a carga embutida e a carga sob demanda exibem exatamente os
        # mesmos artefatos, inclusive após um microciclo de regeneração.
        photos.update(ficha_reader.extrair_fotos_producao(
            obra_dir, pavimento, "lajes", item, visual_mode,
        ))
    vertical_lines = _line_rows(n3.get("linhas_verticais"))
    horizontal_lines = _line_rows(n3.get("linhas_horizontais"))
    vertical_panels = _panel_rows(vertical_lines, contract.get("comprimento"))
    horizontal_panels = _panel_rows(horizontal_lines, contract.get("largura"))
    return {
        "schema": "cad.portal.laje_ficha/v1",
        "visual_mode": ficha_reader.modo_visual_n3(
            obra_dir, pavimento, "lajes", item, visual_mode=visual_mode,
        ),
        "available_visual_modes": ficha_reader.modos_visuais_n3_disponiveis(
            obra_dir, pavimento, "lajes", item,
        ),
        "item": {
            "id": canonical, "name": canonical,
            "nivel": (item.get("campos") or {}).get("Nível"),
            "height": (item.get("campos") or {}).get("Altura"),
            "points": item.get("points") or [],
            "position": position + 1, "total": len(names),
            "previous": names[position - 1] if position > 0 else None,
            "next": names[position + 1] if position + 1 < len(names) else None,
        },
        "n3": {
            "comprimento": contract.get("comprimento"), "largura": contract.get("largura"),
            "modo_selecionado": contract.get("modo_selecionado"),
            "linhas_verticais": vertical_lines,
            "linhas_horizontais": horizontal_lines,
            "paineis_verticais": vertical_panels,
            "paineis_horizontais": horizontal_panels,
            "sobra_vertical": vertical_panels[-1]["value"] if vertical_panels else None,
            "sobra_horizontal": horizontal_panels[-1]["value"] if horizontal_panels else None,
            "source": "override_humano" if has_override else (str(contract_path) if contract_path else None),
            "has_override": has_override,
        },
        "layers": {
            "sa": {"available": True, "lazy": not include_svgs, "svg": photos.get("n1")},
            "c1": {"available": False, "lazy": False, "svg": None},
            "c2": {"available": False, "lazy": False, "svg": None},
            "c3": {"available": False, "lazy": False, "svg": None},
            "n3": {"available": bool(contract_path), "lazy": not include_svgs, "svg": photos.get("n3")},
        },
        "notes": override.get("notes") or {},
    }


def resolver_camada_laje(
    obra_dir: Path, pavimento: str, name: str, estado: dict[str, Any], layer: str,
    visual_mode: str | None = None,
) -> dict[str, Any]:
    if layer not in {"sa", "n3"}:
        raise ValueError("camada de laje inválida")
    item = ficha_reader.obter_item_n1(estado, "lajes", name)
    if item is None:
        raise LookupError("laje não encontrada")
    if layer == "n3":
        photo = {
            "svg": ficha_reader.extrair_fotos_producao(
                obra_dir, pavimento, "lajes", item, visual_mode,
            ).get("n3"),
            "origem": "artefato_producao",
        }
    else:
        photo = {
            "svg": ficha_reader.extrair_fotos_producao(
                obra_dir, pavimento, "lajes", item,
            ).get("n1"),
            "origem": "recorte_contextual_estrutural",
        }
    return {"layer": layer, "available": bool(photo.get("svg")), **photo}
