"""
src/core/services/ml_feedback_service.py -- CAD-13
Feedback ML: correction_log.json -> training data + model insights.

Usage:
    from src.core.services.ml_feedback_service import MLFeedbackService
    ml = MLFeedbackService('D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    print(ml.get_model_insights())
    print(ml.export_training_data())
    print(ml.apply_calibration())
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_LOG_PATH = Path('Fase-3_Interpretacao_Extracao') / 'correction_log.json'
_TRAINING_PATH = Path('Fase-3_Interpretacao_Extracao') / 'training_data.json'


class MLFeedbackService:
    """
    Reads correction_log.json and derives training signals for the interpreter.

    Parameters
    ----------
    obra_path : str | Path
    """

    def __init__(self, obra_path: str | Path):
        self.obra_path = Path(obra_path)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_log(self) -> list[dict]:
        log_path = self.obra_path / _LOG_PATH
        if not log_path.exists():
            return []
        try:
            return json.loads(log_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            log.warning(f"[MLFeedback] Cannot read correction_log: {e}")
            return []

    @staticmethod
    def _safe_delta(old, new) -> float | None:
        """Numeric delta between old and new values, or None."""
        try:
            return abs(float(new) - float(old))
        except (TypeError, ValueError):
            return None

    # ── Public API ────────────────────────────────────────────────────────────

    def export_training_data(self) -> dict[str, Any]:
        """
        Convert correction_log.json to a structured training_data.json.

        Each entry: {field, old_value, new_value, item_id, item_type, delta, timestamp}
        Groups by field to show uncertainty patterns.

        Returns
        -------
        {entries, top_uncertain_fields, export_path}
        """
        entries = self._load_log()
        if not entries:
            return {'entries': 0, 'top_uncertain_fields': [], 'export_path': None}

        training = []
        field_counts: dict[str, int] = defaultdict(int)

        for e in entries:
            field = e.get('field', '')
            old_v = e.get('old_value')
            new_v = e.get('new_value')
            delta = self._safe_delta(old_v, new_v)
            record = {
                'field':     field,
                'old_value': old_v,
                'new_value': new_v,
                'item_id':   e.get('item_id', ''),
                'item_type': e.get('item_type', ''),
                'delta':     delta,
                'timestamp': e.get('timestamp', ''),
            }
            training.append(record)
            field_counts[field] += 1

        top_uncertain = sorted(field_counts.items(), key=lambda x: x[1], reverse=True)
        top_uncertain_fields = [{'field': f, 'corrections': c} for f, c in top_uncertain[:10]]

        export_path = self.obra_path / _TRAINING_PATH
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            json.dumps({'training': training, 'top_uncertain_fields': top_uncertain_fields},
                       indent=2, ensure_ascii=False),
            encoding='utf-8',
        )

        return {
            'entries': len(training),
            'top_uncertain_fields': top_uncertain_fields,
            'export_path': str(export_path),
        }

    def apply_calibration(self) -> dict[str, Any]:
        """
        Apply all corrections from correction_log back to Fase-4 JSONs.
        Delegates to correction_service.apply_from_log().

        Returns
        -------
        {applied, skipped, errors, by_type}
        """
        try:
            from src.core.services.correction_service import apply_from_log
            return apply_from_log(str(self.obra_path))
        except ImportError as e:
            log.error(f"[MLFeedback] correction_service unavailable: {e}")
            return {'applied': 0, 'skipped': 0, 'errors': [str(e)], 'by_type': {}}

    def get_model_insights(self) -> dict[str, Any]:
        """
        Analyse correction_log to surface uncertainty patterns.

        Returns
        -------
        {insights, accuracy_by_field, total_corrections}
        """
        entries = self._load_log()
        if not entries:
            return {
                'insights': ['Nenhuma correcao registrada ainda.'],
                'accuracy_by_field': {},
                'total_corrections': 0,
            }

        # Aggregate per field
        field_stats: dict[str, dict] = defaultdict(
            lambda: {'count': 0, 'deltas': [], 'items': set()}
        )
        for e in entries:
            field = e.get('field', 'unknown')
            old_v = e.get('old_value')
            new_v = e.get('new_value')
            delta = self._safe_delta(old_v, new_v)
            s = field_stats[field]
            s['count'] += 1
            if delta is not None:
                s['deltas'].append(delta)
            item_id = e.get('item_id', '')
            if item_id:
                s['items'].add(item_id)

        total = len(entries)
        accuracy_by_field: dict[str, dict] = {}
        insights: list[str] = []

        for field, s in sorted(field_stats.items(), key=lambda x: x[1]['count'], reverse=True):
            count = s['count']
            avg_delta = (sum(s['deltas']) / len(s['deltas'])) if s['deltas'] else None
            accuracy_by_field[field] = {
                'corrections': count,
                'avg_delta': round(avg_delta, 2) if avg_delta is not None else None,
                'items_affected': len(s['items']),
            }

        # Insights: fields corrected in >50% of entries
        for field, info in accuracy_by_field.items():
            pct = info['corrections'] / total * 100
            if pct >= 50:
                insights.append(
                    f"Campo '{field}' corrigido em {pct:.0f}% dos casos "
                    f"(delta medio: {info['avg_delta']}) -- sistematicamente incerto"
                )
            elif info['corrections'] >= 3:
                insights.append(
                    f"Campo '{field}' corrigido {info['corrections']}x "
                    f"em {info['items_affected']} item(ns)"
                )

        if not insights:
            insights.append(f"Total: {total} correcao(oes) registrada(s). Nenhum padrao critico detectado.")

        return {
            'insights': insights,
            'accuracy_by_field': accuracy_by_field,
            'total_corrections': total,
        }
