"""
src/core/services/audit_exporter.py — CAD-10.5
Exporta relatório de auditoria tri-fonte (GT / Fase-4 / DB) para JSON + Markdown.

Uso:
    exporter = AuditExporter(obra_path, project_id, db)
    report   = exporter.build_report(tipos=['pilar', 'viga', 'laje'])
    exporter.save(report, output_dir)
    # → comparison_audit_{timestamp}.json + comparison_audit_{timestamp}.md
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.services.comparison_service import ComparisonService, FieldStatus

log = logging.getLogger(__name__)

DADOS_OBRAS_ROOT = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
_TIPOS_MAP = {
    'pilar':  ('JSON_Pilares',       'Pilar'),
    'viga':   ('JSON_Vigas_Laterais','Viga'),
    'laje':   ('JSON_Lajes',         'Laje'),
}


def _load_db_items(db, project_id: str, tipo: str) -> list[dict]:
    """Carrega itens do DB por tipo."""
    try:
        t = tipo.lower()
        if 'pilar' in t:
            return db.load_pillars(project_id) or []
        elif 'viga' in t:
            return db.load_beams(project_id) or []
        elif 'laje' in t:
            return db.load_slabs(project_id) or []
    except Exception as e:
        log.warning(f"[AuditExporter] DB load error for {tipo}: {e}")
    return []


def _score_item(item_data: dict, obra_path: str) -> dict:
    """Roda ComparisonService e retorna summary do item."""
    svc = ComparisonService(item_data, obra_path)
    if not svc.has_fase4:
        return {
            'id':          item_data.get('id_item', '?'),
            'type':        item_data.get('type', '?'),
            'score':       None,
            'completude':  None,
            'match_gt_f4': None,
            'match_f4_db': None,
            'conflicts':   [],
            'has_fase4':   False,
        }

    rows  = svc.build_rows()
    sc    = svc.score()

    conflicts = [r.field_id for r in rows if r.status == FieldStatus.CONFLITO]

    # Calcular match GT-F4: campos onde GT e F4 ambos existem e concordam
    rows_with_gt = [r for r in rows if r.gt_value is not None]
    gt_f4_match  = sum(1 for r in rows_with_gt
                       if _vals_eq(r.gt_value, r.f4_value)) if rows_with_gt else 0

    return {
        'id':          item_data.get('id_item', '?'),
        'type':        item_data.get('type', '?'),
        'score':       sc['match_pct'],
        'completude':  sc['completude_pct'],
        'match_gt_f4': round(100 * gt_f4_match / len(rows_with_gt), 1) if rows_with_gt else None,
        'match_f4_db': sc['match_pct'],
        'conflicts':   conflicts,
        'has_fase4':   True,
    }


def _vals_eq(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) < 0.05
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


# ─── Exporter ─────────────────────────────────────────────────────────────────

class AuditExporter:
    """Exporta relatório de auditoria tri-fonte para uma obra/pavimento."""

    def __init__(self, obra_path: str | Path, project_id: str, db):
        self.obra_path  = Path(obra_path)
        self.project_id = project_id
        self.db         = db
        self.obra_name  = self.obra_path.name

    def build_report(self, tipos: list[str] | None = None) -> dict:
        """
        Constrói dict do relatório completo.
        tipos: ['pilar', 'viga', 'laje'] ou subconjunto. None = todos.
        """
        if tipos is None:
            tipos = ['pilar', 'viga', 'laje']

        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        summary   = {}
        all_items = []

        for tipo in tipos:
            items = _load_db_items(self.db, self.project_id, tipo)
            if not items:
                continue

            tipo_key = self._tipo_key(tipo)
            item_scores = []

            for item in items:
                result = _score_item(item, str(self.obra_path))
                item_scores.append(result)
                all_items.append(result)

            valid_scores = [i['score'] for i in item_scores if i['score'] is not None]
            avg_score = round(sum(valid_scores) / len(valid_scores), 1) if valid_scores else 0.0

            summary[tipo_key] = {
                'total':        len(item_scores),
                'with_fase4':   sum(1 for i in item_scores if i['has_fase4']),
                'avg_score':    avg_score,
                'avg_completude': round(
                    sum(i['completude'] for i in item_scores if i['completude'] is not None)
                    / max(1, sum(1 for i in item_scores if i['completude'] is not None)), 1
                ),
                'total_conflicts': sum(len(i['conflicts']) for i in item_scores),
            }

        return {
            'obra':       self.obra_name,
            'project_id': self.project_id,
            'timestamp':  timestamp,
            'summary':    summary,
            'items':      all_items,
        }

    def save(self, report: dict, output_dir: str | Path | None = None) -> Path:
        """Salva report como JSON + Markdown. Retorna path do JSON."""
        if output_dir is None:
            output_dir = self.obra_path / "Fase-8_Revisao_Entrega"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ts = report['timestamp'].replace(':', '').replace('-', '')[:15]
        json_path = output_dir / f"comparison_audit_{ts}.json"
        md_path   = output_dir / f"comparison_audit_{ts}.md"

        # ── JSON ──────────────────────────────────────────────────────────────
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        # ── Markdown ─────────────────────────────────────────────────────────
        md_lines = [
            f"# Relatório de Auditoria — {report['obra']}",
            f"**Data:** {report['timestamp']}  ",
            f"**Project ID:** {report['project_id']}  ",
            "",
            "## Resumo por Tipo",
            "",
            "| Tipo | Total | Com Fase-4 | Score Médio | Completude Média | Conflitos |",
            "|------|-------|-----------|-------------|-----------------|-----------|",
        ]
        for tipo_key, s in report['summary'].items():
            md_lines.append(
                f"| {tipo_key} | {s['total']} | {s['with_fase4']} | "
                f"{s['avg_score']}% | {s['avg_completude']}% | {s['total_conflicts']} |"
            )

        md_lines += [
            "",
            "## Itens Detalhados",
            "",
            "| ID | Tipo | Completude | Match F4-DB | Conflitos |",
            "|----|------|-----------|-------------|-----------|",
        ]
        for item in report['items']:
            conf  = f"{item['completude']}%" if item['completude'] is not None else "—"
            match = f"{item['match_f4_db']}%" if item['match_f4_db'] is not None else "—"
            conf_list = ', '.join(item['conflicts'][:3]) + ('...' if len(item['conflicts']) > 3 else '')
            md_lines.append(
                f"| {item['id']} | {item['type']} | {conf} | {match} | {conf_list or '—'} |"
            )

        md_path.write_text('\n'.join(md_lines), encoding='utf-8')

        log.info(f"[AuditExporter] Salvo: {json_path}")
        return json_path

    @staticmethod
    def _tipo_key(tipo: str) -> str:
        t = tipo.lower()
        if 'pilar' in t:     return 'pilares'
        if 'viga_fundo' in t: return 'vigas_fundo'
        if 'viga' in t:      return 'vigas_laterais'
        if 'laje' in t:      return 'lajes'
        return t
