# -*- coding: utf-8 -*-
"""
Coverage Reporting Engine
Generates metrics and analysis reports for rule coverage
"""

import json
import logging
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CoverageMetric:
    """Métricas de cobertura para um tipo de entidade."""
    entity_type: str
    total_rules: int
    active_rules: int
    prod_rules: int
    avg_coverage: float
    avg_accuracy: float
    avg_confidence: float


@dataclass
class CoverageReport:
    """Relatório completo de cobertura."""
    generated_at: str
    total_rules: int
    active_rules: int
    overall_coverage: float
    metrics_by_type: Dict[str, CoverageMetric]
    recommendations: List[str]


class CoverageReporter:
    """
    Gera relatórios de cobertura do processamento.

    Quantifica quantas regras foram aplicadas, sua precisão,
    e gera recomendações para melhoria.
    """

    def __init__(self, db_path: str):
        """Initialize coverage reporter."""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect_db()

    def _connect_db(self):
        """Connect to database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {self.db_path}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self.conn = None

    def generate_coverage_report(self) -> Optional[CoverageReport]:
        """Gera relatório completo de cobertura de regras."""
        if not self.conn:
            return None

        try:
            cursor = self.conn.cursor()

            # Busca métricas agrupadas por tipo de entidade
            cursor.execute("""
                SELECT
                    entity_type,
                    COUNT(*) as total_rules,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_rules,
                    SUM(CASE WHEN status = 'production' THEN 1 ELSE 0 END) as prod_rules,
                    AVG(COALESCE(coverage, 0)) as avg_coverage,
                    AVG(COALESCE(accuracy, 0)) as avg_accuracy,
                    AVG(COALESCE(confidence, 0)) as avg_confidence
                FROM transformation_rules
                GROUP BY entity_type
            """)

            metrics_by_type: Dict[str, CoverageMetric] = {}
            for row in cursor.fetchall():
                metric = CoverageMetric(
                    entity_type=row["entity_type"],
                    total_rules=row["total_rules"],
                    active_rules=row["active_rules"],
                    prod_rules=row["prod_rules"],
                    avg_coverage=row["avg_coverage"] or 0.0,
                    avg_accuracy=row["avg_accuracy"] or 0.0,
                    avg_confidence=row["avg_confidence"] or 0.0,
                )
                metrics_by_type[row["entity_type"]] = metric

            # Calcula cobertura geral
            all_metrics = list(metrics_by_type.values())
            if all_metrics:
                overall_coverage = sum(m.avg_coverage for m in all_metrics) / len(all_metrics)
            else:
                overall_coverage = 0.0

            # Gera recomendações
            recommendations = self._generate_recommendations(metrics_by_type, overall_coverage)

            total_rules = sum(m.total_rules for m in all_metrics)
            active_rules = sum(m.active_rules for m in all_metrics)

            report = CoverageReport(
                generated_at=datetime.now().isoformat(),
                total_rules=total_rules,
                active_rules=active_rules,
                overall_coverage=overall_coverage,
                metrics_by_type=metrics_by_type,
                recommendations=recommendations,
            )

            logger.info("Generating coverage report")
            return report

        except Exception as e:
            logger.error(f"Failed to generate coverage report: {e}")
            return None

    def _generate_recommendations(
        self,
        metrics: Dict[str, CoverageMetric],
        overall: float,
    ) -> List[str]:
        """Generate recommendations based on coverage metrics."""
        recommendations = []

        if overall < 30:
            recommendations.append(
                f"Overall coverage is low ({overall:.1f}%). "
                f"Focus on extracting more rules from existing data."
            )
        elif overall < 70:
            recommendations.append(
                f"Coverage is moderate ({overall:.1f}%). "
                f"Consider extracting additional rules from underrepresented entity types."
            )
        else:
            recommendations.append(
                f"Excellent coverage ({overall:.1f}%)! "
                f"Consider promoting rules to production."
            )

        # Analisa tipos com baixa cobertura
        for entity_type, metric in metrics.items():
            if metric.avg_coverage < 30:
                recommendations.append(
                    f"{entity_type}: Coverage is low ({metric.avg_coverage:.1f}%). "
                    f"Need more training data for this entity type."
                )

        # Analisa tipos com baixa precisão
        low_accuracy = {
            k: v for k, v in metrics.items() if v.avg_accuracy < 50 and v.total_rules > 0
        }
        if low_accuracy:
            types = ", ".join(low_accuracy.keys())
            recommendations.append(
                f"Low accuracy for: {types}. "
                f"Review and retrain rules for these entity types."
            )

        return recommendations

    def get_rule_statistics(self) -> Optional[Dict[str, Any]]:
        """Get detailed rule statistics."""
        if not self.conn:
            return None

        try:
            cursor = self.conn.cursor()

            # Total de regras
            cursor.execute("SELECT COUNT(*) as count FROM transformation_rules")
            row = cursor.fetchone()
            total_rules = row["count"] if row else 0

            # Distribuição por status
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM transformation_rules
                GROUP BY status
            """)
            status_dist = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Distribuição por versão
            cursor.execute("""
                SELECT version, COUNT(*) as count
                FROM transformation_rules
                GROUP BY version
            """)
            versions = {str(row["version"]): row["count"] for row in cursor.fetchall()}

            # Estatísticas de A/B tests
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed
                FROM ab_tests
            """)
            row = cursor.fetchone()
            ab_stats = {
                "total": row["total"] if row else 0,
                "success": row["success"] if row else 0,
                "completed": row["completed"] if row else 0,
            }

            return {
                "total_rules": total_rules,
                "status_distribution": status_dist,
                "version_distribution": versions,
                "ab_tests": ab_stats,
            }

        except Exception as e:
            logger.error(f"Failed to get rule statistics: {e}")
            return None

    def get_evaluation_metrics(self) -> Optional[Dict[str, Any]]:
        """Get rule evaluation metrics."""
        if not self.conn:
            return None

        try:
            cursor = self.conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN matched = 1 THEN 1 ELSE 0 END) as matched,
                    SUM(CASE WHEN passed_validation = 1 THEN 1 ELSE 0 END) as validated
                FROM rule_evaluations
            """)
            row = cursor.fetchone()
            stats = {
                "total_evaluations": row["total"] if row else 0,
                "matched": row["matched"] if row else 0,
                "passed_validation": row["validated"] if row else 0,
            }

            # Taxas de sucesso
            total = stats["total_evaluations"]
            if total > 0:
                stats["success"] = stats["matched"] / total
            else:
                stats["success"] = 0

            # Métricas agregadas
            cursor.execute("""
                SELECT
                    AVG(confidence) as avg_confidence,
                    AVG(execution_time) as avg_execution_time
                FROM rule_evaluations
            """)
            row = cursor.fetchone()
            if row:
                stats["avg_confidence"] = row["avg_confidence"] or 0
                stats["avg_execution_time"] = row["avg_execution_time"] or 0

            return stats

        except Exception as e:
            logger.error(f"Failed to get evaluation metrics: {e}")
            return None

    def export_report_markdown(self, report: CoverageReport) -> str:
        """Export report as markdown."""
        md = "# Rule Coverage Report\n\n"
        md += f"**Generated:** {report.generated_at}\n\n"

        md += "## Overview\n\n"
        md += f"- **Total Rules:** {report.total_rules}\n"
        md += f"- **Active Rules:** {report.active_rules}\n"
        md += f"- **Overall Coverage:** {report.overall_coverage:.1f}%\n\n"

        md += "## Coverage by Entity Type\n\n"
        md += "| Entity Type | Total | Active | Prod | Coverage | Accuracy | Confidence |\n"
        md += "|-------------|-------|--------|------|----------|----------|------------|\n"

        for entity_type, metrics in report.metrics_by_type.items():
            md += (
                f"| {entity_type} "
                f"| {metrics.total_rules} "
                f"| {metrics.active_rules} "
                f"| {metrics.prod_rules} "
                f"| {metrics.avg_coverage:.1f}% "
                f"| {metrics.avg_accuracy:.1f}% "
                f"| {metrics.avg_confidence:.2f} |\n"
            )

        md += "\n## Recommendations\n\n"
        for rec in report.recommendations:
            md += f"- {rec}\n"

        return md

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
