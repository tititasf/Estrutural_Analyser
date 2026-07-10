"""Perfis visuais das travessas horizontais das grades de pilares.

O robô legado armazena posições acumuladas a partir da base da grade. A UI
expõe distâncias entre travessas e converte para este mesmo contrato antes de
persistir. O arquivo é compartilhado pelos geradores N3 e N4.
"""
from __future__ import annotations

import json
import math
import os
from copy import deepcopy
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "pl_grade_visual_profiles.json"
CONFIG_PATH = Path(
    os.environ.get("ARETE_PL_GRADE_VISUAL_CONFIG", str(DEFAULT_CONFIG_PATH))
).expanduser()
VALID_MODES = ("INI", "NOVA")

DEFAULT_PROFILES = {
    "schema_version": 1,
    "unidade": "cm",
    "referencia": "borda inferior da grade",
    "modos": {
        "INI": {
            "horizontal_positions_cm": [
                60.0, 170.0, 280.0, 390.0, 500.0,
                610.0, 720.0, 830.0, 940.0,
            ],
        },
        "NOVA": {
            "horizontal_positions_cm": [
                30.0, 120.0, 210.0, 300.0, 390.0,
                480.0, 720.0, 830.0, 940.0,
            ],
        },
    },
}


def normalize_mode(mode: object) -> str:
    value = str(mode or "NOVA").strip().upper()
    if value not in VALID_MODES:
        raise ValueError(f"Modo visual inválido: {mode!r}")
    return value


def validate_positions(values: Iterable[object]) -> list[float]:
    """Valida posições positivas, finitas e estritamente crescentes."""
    positions = [float(value) for value in values]
    if not positions:
        raise ValueError("Informe ao menos uma posição horizontal.")
    if len(positions) > 32:
        raise ValueError("São permitidas no máximo 32 posições horizontais.")
    if any(not math.isfinite(value) or value <= 0 for value in positions):
        raise ValueError("As posições horizontais devem ser números positivos.")
    if any(current <= previous for previous, current in zip(positions, positions[1:])):
        raise ValueError("As posições horizontais devem ser estritamente crescentes.")
    return [round(value, 4) for value in positions]


def positions_to_distances(values: Iterable[object]) -> list[float]:
    """Converte posições desde a base em intervalos base→H1 e Hn→Hn+1."""
    positions = validate_positions(values)
    distances = [positions[0]]
    distances.extend(
        round(current - previous, 4)
        for previous, current in zip(positions, positions[1:])
    )
    return distances


def distances_to_positions(values: Iterable[object]) -> list[float]:
    """Converte intervalos positivos em posições acumuladas desde a base."""
    distances = [float(value) for value in values]
    if not distances:
        raise ValueError("Informe ao menos uma distância horizontal.")
    if any(not math.isfinite(value) or value <= 0 for value in distances):
        raise ValueError("As distâncias entre horizontais devem ser positivas.")
    total = 0.0
    positions = []
    for distance in distances:
        total += distance
        positions.append(round(total, 4))
    return validate_positions(positions)


def load_profiles(path: Path | str = CONFIG_PATH) -> dict:
    """Carrega os dois modos; valores ausentes ou inválidos usam o padrão."""
    result = deepcopy(DEFAULT_PROFILES)
    config_path = Path(path)
    if not config_path.exists():
        return result
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result
    modes = payload.get("modos", {}) if isinstance(payload, dict) else {}
    for mode in VALID_MODES:
        raw_mode = modes.get(mode, {}) if isinstance(modes, dict) else {}
        raw_positions = raw_mode.get("horizontal_positions_cm") if isinstance(raw_mode, dict) else None
        try:
            if raw_positions is not None:
                result["modos"][mode]["horizontal_positions_cm"] = validate_positions(raw_positions)
        except (TypeError, ValueError):
            pass
    return result


def positions_for_mode(mode: object, path: Path | str = CONFIG_PATH) -> list[float]:
    normalized = normalize_mode(mode)
    return list(load_profiles(path)["modos"][normalized]["horizontal_positions_cm"])


def save_profiles(profiles: dict, path: Path | str = CONFIG_PATH) -> Path:
    """Persiste atomicamente somente dados validados dos modos INI/NOVA."""
    modes = profiles.get("modos", {}) if isinstance(profiles, dict) else {}
    payload = deepcopy(DEFAULT_PROFILES)
    for mode in VALID_MODES:
        raw_mode = modes.get(mode, {}) if isinstance(modes, dict) else {}
        raw_positions = raw_mode.get("horizontal_positions_cm") if isinstance(raw_mode, dict) else None
        if raw_positions is None:
            raise ValueError(f"Posições ausentes para o modo {mode}.")
        payload["modos"][mode]["horizontal_positions_cm"] = validate_positions(raw_positions)

    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temp_path, config_path)
    return config_path
