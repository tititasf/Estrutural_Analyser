"""Helpers compartilhados pelos diagnósticos numéricos headless N1×N2 por classe.

Extraído de `diagnostico_fv_n1_n2.py` (primeira implementação, FV) ao construir
o equivalente para PIL — mesma lógica de resolução de estado, casamento de
pavimento e classificação de qualidade, reaproveitável quando LV entrar no
loop (ver checklist §6 de `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md`). Não é
específico de nenhuma classe.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or ""))
    return clean.strip("._") or "item"


def as_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def relative_delta(detected: float | None, expected: float | None) -> float | None:
    if detected is None or expected is None:
        return None
    return abs(detected - expected) / max(abs(expected), 1e-9)


def classify_delta(delta: float | None) -> str:
    if delta is None:
        return "INDETERMINADO"
    if delta <= 0.02:
        return "EXCELENTE"
    if delta <= 0.05:
        return "BOM"
    if delta <= 0.10:
        return "REGULAR"
    return "RUIM"


def natural_key(value: str) -> list[Any]:
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]


def _pav_number(value: str) -> int | None:
    text = str(value or "").upper()
    for pattern in (r"(?<!\d)(\d+)\s*[_ -]*PAV", r"(?<!\d)(\d+)\s*P(?:\D|$)"):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def same_pavimento(first: str, second: str) -> bool:
    if str(first or "").strip().casefold() == str(second or "").strip().casefold():
        return True
    first_number = _pav_number(first)
    second_number = _pav_number(second)
    return first_number is not None and first_number == second_number


def resolve_state_path(
    obra: str,
    pavimento: str,
    state_path: str | Path | None,
    state_root: str | Path,
) -> Path:
    if state_path:
        path = Path(state_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Estado N1 não encontrado: {path}")
        return path

    obra_dir = Path(state_root) / obra
    matches: list[tuple[float, Path]] = []
    for candidate in obra_dir.glob("estado_*.json"):
        try:
            state = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(state.get("obra") or "") != obra:
            continue
        if not same_pavimento(str(state.get("pavimento") or ""), pavimento):
            continue
        matches.append((candidate.stat().st_mtime, candidate))
    if not matches:
        raise FileNotFoundError(
            f"Nenhum estado N1 de {obra}/{pavimento} em {obra_dir}"
        )
    return max(matches, key=lambda item: item[0])[1].resolve()
