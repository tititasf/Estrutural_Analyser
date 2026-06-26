"""
src/core/services/completude_cache.py -- CAD-15
Score de Completude: calcula e caches completude_pct por item.

Usage:
    from src.core.services.completude_cache import compute_completude_batch, invalidate_cache
    scores = compute_completude_batch(items, obra_path)
    # scores: {item_id: completude_pct_float}
    invalidate_cache(project_id)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

try:
    from src.core.services.comparison_service import ComparisonService
except ImportError:
    ComparisonService = None  # type: ignore[assignment,misc]

# In-memory cache: {project_id: {item_id: completude_pct}}
_cache: dict[str, dict[str, float]] = {}


def invalidate_cache(project_id: str) -> None:
    """Remove entradas de cache para o projeto."""
    _cache.pop(project_id, None)


def _get_obra_path_for_item(item: dict, obra_path: str | Path | None) -> Path | None:
    """Resolve o caminho da obra a partir do item ou do argumento."""
    if obra_path:
        return Path(obra_path)
    # Fallback: tentar derivar do campo pkl_path
    pkl = item.get('pkl_path')
    if pkl:
        p = Path(pkl)
        # sobe até encontrar DADOS-OBRAS/<obra_name>/
        for parent in p.parents:
            if (parent / 'Fase-4_Sincronizacao').exists():
                return parent
    return None


def compute_completude_batch(
    items: list[dict],
    obra_path: str | Path | None = None,
    project_id: str | None = None,
) -> dict[str, float]:
    """
    Calcula completude_pct para cada item via ComparisonService.score().

    Parameters
    ----------
    items       : lista de dicts (pilares/lajes/vigas) com campos do DB
    obra_path   : caminho da obra (para localizar Fase-4 JSONs)
    project_id  : se fornecido, usa e popula o cache em memória

    Returns
    -------
    {item_id: completude_pct}  — completude_pct ∈ [0.0, 100.0]
    """
    if project_id and project_id in _cache:
        return dict(_cache[project_id])

    if ComparisonService is None:
        log.warning("[CompletudeCache] ComparisonService indisponivel")
        return {}

    scores: dict[str, float] = {}

    for item in items:
        item_id = item.get('id_item') or item.get('id') or ''
        item_type = item.get('type', item.get('item_type', 'Pilar'))

        op = _get_obra_path_for_item(item, obra_path)
        if not op:
            scores[item_id] = 0.0
            continue

        try:
            svc = ComparisonService(item, item_type, str(op))
            sc = svc.score()
            scores[item_id] = float(sc.get('completude_pct', 0.0))
        except Exception as exc:
            log.debug(f"[CompletudeCache] score falhou para {item_id}: {exc}")
            scores[item_id] = 0.0

    if project_id:
        _cache[project_id] = dict(scores)

    return scores


def get_completude(
    item: dict,
    obra_path: str | Path | None = None,
    project_id: str | None = None,
) -> float:
    """
    Score de completude para um único item.
    Usa cache quando project_id é fornecido.
    """
    item_id = item.get('id_item') or item.get('id') or ''
    if project_id and project_id in _cache:
        return _cache[project_id].get(item_id, 0.0)

    result = compute_completude_batch([item], obra_path, project_id)
    return result.get(item_id, 0.0)
