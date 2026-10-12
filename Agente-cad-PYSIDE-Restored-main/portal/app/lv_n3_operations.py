"""Contratos N3 editáveis de LV sem modificar a rodada SA original."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from src.core.vigas_drawing_config import apply_lv_config, normalize_lv_assembly, prepare_lv_sources


_BEAM = re.compile(r"(?:V|VF)\d+[A-Z]?", re.IGNORECASE)
_PANEL_FIELDS = ("width", "height1", "height2")
_SIDE_FIELDS = ("total_width", "total_height", "h_section")


def _identity(behavior: str, beam: str) -> tuple[str, str]:
    behavior = str(behavior or "").lower()
    beam = str(beam or "").upper()
    if behavior not in {"para", "passa"} or not _BEAM.fullmatch(beam):
        raise ValueError("identidade de lateral inválida")
    return behavior, beam


def _source_paths(obra_dir: Path, pavimento: str, behavior: str, beam: str) -> dict[str, Path]:
    behavior, beam = _identity(behavior, beam)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(pavimento or "")):
        raise ValueError("pavimento inválido")
    root = Path(obra_dir) / "Fase-6_Execucao_CAD" / "production_sa" / pavimento
    for run in sorted(root.glob("*/n3/contracts_lv"), reverse=True):
        paths = {
            side: run / f"LV-{behavior.upper()}" / f"{beam}_{side}.json"
            for side in ("A", "B")
        }
        if all(path.is_file() for path in paths.values()):
            return paths
    legacy = Path(obra_dir) / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais" / f"LV-{behavior.upper()}"
    paths = {side: legacy / f"{beam}_{side}.json" for side in ("A", "B")}
    if all(path.is_file() for path in paths.values()):
        return paths
    raise FileNotFoundError(f"contratos N3 LV ausentes para {beam}/{behavior}/{pavimento}")


def _read_source(obra_dir: Path, pavimento: str, behavior: str, beam: str) -> tuple[dict, str]:
    behavior, beam = _identity(behavior, beam)
    paths = _source_paths(obra_dir, pavimento, behavior, beam)
    raw = {side: paths[side].read_bytes() for side in ("A", "B")}
    fingerprint = hashlib.sha256(raw["A"] + b"\0" + raw["B"]).hexdigest()
    contracts = {side: json.loads(raw[side]) for side in ("A", "B")}
    for side, contract in contracts.items():
        if not isinstance(contract, dict) or not isinstance(contract.get("panels"), list):
            raise ValueError(f"contrato N3 LV {side} inválido")
        if str(contract.get("behavior") or "").lower() != behavior:
            raise ValueError(f"comportamento do contrato N3 LV {side} divergente")
    return contracts, fingerprint


def _override_path(obra_dir: Path, pavimento: str, behavior: str, beam: str, assembly=None) -> Path:
    behavior, beam = _identity(behavior, beam)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", pavimento):
        raise ValueError("pavimento inválido")
    root = Path(obra_dir) / ".portal_overrides" / "lv_n3" / pavimento / behavior
    if assembly is not None:
        root /= normalize_lv_assembly(assembly)
    return root / f"{beam}.json"


def _positive(value: Any, name: str, *, zero: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} inválido") from exc
    if not math.isfinite(number) or number < (0 if zero else 0.001) or number > 100000:
        raise ValueError(f"{name} inválido")
    return round(number, 3)


def _variant_source(source, obra_dir, pavimento, behavior, beam, fingerprint, assembly, mode=None):
    source = prepare_lv_sources(source, mode=mode)
    source = {side:apply_lv_config(contract, {'comportamento_laterais_vigas':assembly})
              for side,contract in source.items()}
    # Preserve existing manual dimensions as a common starting point. New edits
    # are subsequently stored under the independent assembly namespace.
    legacy = _override_path(obra_dir,pavimento,behavior,beam)
    if legacy.is_file():
        old = json.loads(legacy.read_text(encoding='utf8'))
        if old.get('source_hash') == fingerprint:
            cleaned = _validated_sides(source,old['sides'])
            for side in ('A','B'):
                source[side].update({key:cleaned[side][key] for key in _SIDE_FIELDS})
                for panel,edited in zip(source[side]['panels'],cleaned[side]['panels']):
                    panel.update({key:edited[key] for key in _PANEL_FIELDS})
                    panel['body_height_cm'] = max(0.,panel['height1']-panel['top_band_cm'])
    return source


def _editable(contracts: dict[str, dict]) -> dict[str, dict]:
    return {
        side: {
            **{key: contract.get(key) for key in _SIDE_FIELDS},
            "panels": [
                {**{key: panel.get(key) for key in _PANEL_FIELDS},
                 "panel_type": panel.get("panel_type", "Sarrafeado"),
                 "grade_h1": panel.get("grade_h1", 0), "grade_h2": panel.get("grade_h2", 0),
                 "body_height_cm": panel.get("body_height_cm"), "top_band_cm": panel.get("top_band_cm"),
                 "segment_index": panel.get("structural_segment_index", panel.get("segment_index"))}
                for panel in contract["panels"]
            ],
        }
        for side, contract in contracts.items()
    }


def _validated_sides(source: dict[str, dict], sides: dict) -> dict[str, dict]:
    if not isinstance(sides, dict) or set(sides) != {"A", "B"}:
        raise ValueError("ficha N3 LV deve conter os lados A e B")
    cleaned = {}
    for side in ("A", "B"):
        draft = sides[side]
        panels = draft.get("panels") if isinstance(draft, dict) else None
        original = source[side]["panels"]
        if not isinstance(panels, list) or len(panels) != len(original):
            raise ValueError(f"quantidade de painéis da face {side} mudou; recarregue a ficha")
        if any(not isinstance(panel, dict) for panel in panels):
            raise ValueError(f"painéis da face {side} inválidos")
        cleaned[side] = {
            **{key: _positive(draft.get(key), f"{side}.{key}", zero=key == "h_section") for key in _SIDE_FIELDS},
            "panels": [
                {key: _positive(panel.get(key), f"{side}.painel{index + 1}.{key}", zero=key != "width")
                 for key in _PANEL_FIELDS}
                for index, panel in enumerate(panels)
            ],
        }
    for side in ("A", "B"):
        for index, panel in enumerate(cleaned[side]["panels"]):
            original = source[side]["panels"][index]
            if original.get("panel_type") == "Grade":
                for field, height in (("grade_h1", "height1"), ("grade_h2", "height2")):
                    panel[field] = _positive(sides[side]["panels"][index].get(field, original.get(field, 0)), field, zero=True)
                    if panel[field] > panel[height]:
                        raise ValueError(f"{side}: altura da grade excede a altura do painel")
    return cleaned


def load_ficha(obra_dir: Path, pavimento: str, behavior: str, beam: str, assembly=None, mode=None) -> dict:
    source, fingerprint = _read_source(obra_dir, pavimento, behavior, beam)
    if assembly is not None:
        assembly = normalize_lv_assembly(assembly)
        source = _variant_source(source,obra_dir,pavimento,behavior,beam,fingerprint,assembly,mode)
    if mode == 'NOVA' and any((segment.get('lv_cell') or {}).get('pillar_openings')
            for contract in source.values() for segment in contract.get('structural_segments', [])):
        from .ficha_reader import ler_estado_pavimento
        state = ler_estado_pavimento(obra_dir, pavimento) or {}
        from src.core.lv_nova_sa_adapter import attach_pillar_faces
        source = attach_pillar_faces(source, state.get('pilares') or [])
    path = _override_path(obra_dir, pavimento, behavior, beam, assembly)
    override = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    stale = bool(override) and override.get("source_hash") != fingerprint
    sides = _editable(source)
    if override and not stale:
        validated = _validated_sides(source, override.get("sides"))
        for side in ("A", "B"):
            sides[side].update({key: validated[side][key] for key in _SIDE_FIELDS})
            for panel, edited in zip(sides[side]["panels"], validated[side]["panels"]):
                panel.update(edited)
    return {
        "source_hash": fingerprint,
        "assembly_variant": assembly,
        "revision": int(override.get("revision", 0)) if not stale else 0,
        "stale": stale,
        "sides": sides,
    }


def save_ficha(obra_dir: Path, pavimento: str, behavior: str, beam: str, draft: dict, assembly=None, mode=None) -> dict:
    source, fingerprint = _read_source(obra_dir, pavimento, behavior, beam)
    if assembly is not None:
        assembly = normalize_lv_assembly(assembly)
        source = _variant_source(source,obra_dir,pavimento,behavior,beam,fingerprint,assembly,mode)
    if mode == 'NOVA' and any((segment.get('lv_cell') or {}).get('pillar_openings')
            for contract in source.values() for segment in contract.get('structural_segments', [])):
        from .ficha_reader import ler_estado_pavimento
        state = ler_estado_pavimento(obra_dir, pavimento) or {}
        from src.core.lv_nova_sa_adapter import attach_pillar_faces
        source = attach_pillar_faces(source, state.get('pilares') or [])
    if draft.get("source_hash") != fingerprint:
        raise ValueError("contrato SA mudou; recarregue a ficha antes de salvar")
    sides = _validated_sides(source, draft.get("sides"))
    path = _override_path(obra_dir, pavimento, behavior, beam, assembly)
    old = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if old.get("source_hash") == fingerprint and int(draft.get("revision", -1)) != int(old.get("revision", 0)):
        raise ValueError("ficha N3 LV foi alterada em outra sessão; recarregue antes de salvar")
    if not old and int(draft.get("revision", -1)) != 0:
        raise ValueError("revisão da ficha N3 LV inválida; recarregue")
    revision = int(old.get("revision", 0)) + 1
    saved = {"schema": "portal.lv.n3.override/v1", "source_hash": fingerprint,
             "revision": revision, "sides": sides}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{beam}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(saved, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return load_ficha(obra_dir, pavimento, behavior, beam, assembly, mode=mode)


def effective_contracts(obra_dir: Path, pavimento: str, behavior: str, beam: str, assembly=None, mode=None) -> dict[str, dict]:
    source, fingerprint = _read_source(obra_dir, pavimento, behavior, beam)
    if assembly is not None:
        assembly = normalize_lv_assembly(assembly)
        source = _variant_source(source,obra_dir,pavimento,behavior,beam,fingerprint,assembly,mode)
    if mode == 'NOVA' and any((segment.get('lv_cell') or {}).get('pillar_openings')
            for contract in source.values() for segment in contract.get('structural_segments', [])):
        from .ficha_reader import ler_estado_pavimento
        state = ler_estado_pavimento(obra_dir, pavimento) or {}
        from src.core.lv_nova_sa_adapter import attach_pillar_faces
        source = attach_pillar_faces(source, state.get('pilares') or [])
    path = _override_path(obra_dir, pavimento, behavior, beam, assembly)
    if not path.is_file():
        return source
    override = json.loads(path.read_text(encoding="utf-8"))
    if override.get("source_hash") != fingerprint:
        raise ValueError("contrato SA mudou; revise e salve a ficha N3 LV")
    validated = _validated_sides(source, override.get("sides"))
    result = deepcopy(source)
    for side in ("A", "B"):
        result[side].update({key: validated[side][key] for key in _SIDE_FIELDS})
        for panel, edited in zip(result[side]["panels"], validated[side]["panels"]):
            panel.update(edited)
            if panel.get('top_band_cm') is not None:
                panel['body_height_cm'] = max(0., panel['height1']-panel['top_band_cm'])
    return result
