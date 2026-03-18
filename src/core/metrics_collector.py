"""
Metrics Collector - Coleta metricas de aplicacao de regras.
"""
import sqlite3
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class RuleApplicationMetrics:
    rule_id: str
    entity_type: str
    total_evaluations: int = 0
    passed: int = 0
    avg_confidence: float = 0.0
    avg_execution_time_ms: float = 0.0
    compliance_pct: float = 0.0


class MetricsCollector:
    """Collects and stores metrics from rule application cycles."""

    def __init__(self, db_path: str):
        """Initialize metrics collector with database connection."""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect_db()

    def _connect_db(self) -> None:
        """Open sqlite3 connection to the metrics database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info("[OK] Connected to metrics database: %s", self.db_path)
        except Exception as e:
            logger.error("[FAIL] Database connection failed: %s", e)
            self.conn = None

    def record_rule_application(self, context: Dict[str, Any]) -> None:
        """Record metrics from rule application context."""
        try:
            compliance_pct = context.get("compliance_pct", 0.0)

            metric = RuleApplicationMetrics(
                rule_id=context.get("rule_id", ""),
                entity_type=context.get("entity_type", ""),
                total_evaluations=context.get("total_evaluations", 1),
                passed=context.get("passed", 0),
                avg_confidence=context.get("confidence", 0.0),
                avg_execution_time_ms=context.get("execution_time_ms", 0.0),
                compliance_pct=compliance_pct,
            )

            self._write_to_evaluation_log(metric, context)
            logger.info(
                "[OK] Recorded rule_id=%s entity_type=%s compliance=%.1f%%",
                metric.rule_id,
                metric.entity_type,
                compliance_pct,
            )
        except Exception as e:
            logger.error("[FAIL] Error recording rule application: %s", e)

    def _write_to_evaluation_log(
        self, metric: RuleApplicationMetrics, context: Dict[str, Any]
    ) -> None:
        """Write a single evaluation record to rule_evaluation_log."""
        if self.conn is None:
            return
        try:
            self.conn.execute(
                """INSERT INTO rule_evaluation_log
                   (rule_id, entity_id, entity_type, validation_passed,
                    confidence, execution_time_ms, constraints_checked,
                    constraints_passed, violations_count, evaluated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    metric.rule_id,
                    context.get("entity_id", ""),
                    metric.entity_type,
                    context.get("validation_passed", False),
                    metric.avg_confidence,
                    metric.avg_execution_time_ms,
                    context.get("constraints_checked", 0),
                    context.get("constraints_passed", 0),
                    context.get("violations_count", 0),
                    datetime.utcnow().isoformat(),
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error("[FAIL] Error writing to evaluation log: %s", e)

    def get_rule_statistics(self, rule_id: str) -> Dict[str, Any]:
        """Return aggregate statistics for a specific rule."""
        if self.conn is None:
            return {"total_evaluations": 0}
        try:
            cursor = self.conn.execute(
                """SELECT
                       COUNT(*) as total_evaluations,
                       SUM(CASE WHEN validation_passed=TRUE THEN 1 ELSE 0 END) as passed,
                       AVG(confidence) as avg_confidence,
                       AVG(execution_time_ms) as avg_execution_time,
                       AVG(constraints_checked) as avg_constraints_checked,
                       AVG(constraints_passed) as avg_constraints_passed,
                       SUM(violations_count) as total_violations
                   FROM rule_evaluation_log
                   WHERE rule_id=?""",
                (rule_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return {"total_evaluations": 0}
            return {
                "total_evaluations": row["total_evaluations"] or 0,
                "passed": row["passed"] or 0,
                "avg_confidence": row["avg_confidence"] or 0.0,
                "avg_execution_time": row["avg_execution_time"] or 0.0,
                "avg_constraints_checked": row["avg_constraints_checked"] or 0.0,
                "avg_constraints_passed": row["avg_constraints_passed"] or 0.0,
                "total_violations": row["total_violations"] or 0,
            }
        except Exception as e:
            logger.error("[FAIL] Error getting rule statistics: %s", e)
            return {"total_evaluations": 0}

    def get_entity_type_statistics(self, entity_type: str) -> Dict[str, Any]:
        """Return aggregate statistics for a specific entity type."""
        if self.conn is None:
            return {}
        try:
            cursor = self.conn.execute(
                """SELECT
                       entity_type,
                       COUNT(DISTINCT rule_id) as total_rules,
                       COUNT(*) as total_evaluations,
                       SUM(CASE WHEN validation_passed=TRUE THEN 1 ELSE 0 END) as passed,
                       AVG(confidence) as avg_confidence,
                       AVG(execution_time_ms) as avg_execution_time,
                       SUM(violations_count) as total_violations
                   FROM rule_evaluation_log
                   WHERE entity_type=?
                   GROUP BY entity_type""",
                (entity_type,),
            )
            row = cursor.fetchone()
            if row is None:
                return {}
            return {
                "entity_type": row["entity_type"],
                "total_rules": row["total_rules"] or 0,
                "total_evaluations": row["total_evaluations"] or 0,
                "passed": row["passed"] or 0,
                "avg_confidence": row["avg_confidence"] or 0.0,
                "avg_execution_time": row["avg_execution_time"] or 0.0,
                "total_violations": row["total_violations"] or 0,
            }
        except Exception as e:
            logger.error("[FAIL] Error getting entity type statistics: %s", e)
            return {}

    def update_transformation_rules(self) -> int:
        """Update accuracy_pct and coverage_pct in transformation_rules from evaluation log data."""
        if self.conn is None:
            return 0
        try:
            cursor = self.conn.execute(
                "SELECT DISTINCT rule_id FROM rule_evaluation_log"
            )
            rule_ids = [row["rule_id"] for row in cursor.fetchall()]

            updated = 0
            for rule_id in rule_ids:
                stats = self.get_rule_statistics(rule_id)
                total = stats.get("total_evaluations", 0)
                passed = stats.get("passed", 0)
                if total > 0:
                    accuracy_pct = (passed / total) * 100.0
                else:
                    accuracy_pct = 0.0
                # coverage_pct is same as accuracy_pct for now (based on eval data)
                coverage_pct = accuracy_pct

                self.conn.execute(
                    """UPDATE transformation_rules
                       SET accuracy_pct=?, coverage_pct=?
                       WHERE rule_id=?""",
                    (accuracy_pct, coverage_pct, rule_id),
                )
                updated += 1

            self.conn.commit()
            logger.info("[OK] Updated %d transformation rules with metrics", updated)
            return updated
        except Exception as e:
            logger.error("[FAIL] Error updating transformation rules: %s", e)
            return 0

    def export_metrics(self) -> Dict[str, Any]:
        """Export metrics summary grouped by entity_type."""
        if self.conn is None:
            return {"entity_types": []}
        try:
            cursor = self.conn.execute(
                """SELECT
                       entity_type,
                       COUNT(DISTINCT rule_id) as total_rules,
                       COUNT(*) as total_evaluations,
                       SUM(CASE WHEN validation_passed=TRUE THEN 1 ELSE 0 END) as passed,
                       AVG(confidence) as avg_confidence,
                       AVG(execution_time_ms) as avg_execution_time,
                       SUM(violations_count) as total_violations
                   FROM rule_evaluation_log
                   GROUP BY entity_type
                   ORDER BY total_evaluations DESC"""
            )
            rows = cursor.fetchall()
            entity_types = []
            for row in rows:
                total = row["total_evaluations"] or 0
                passed = row["passed"] or 0
                entity_types.append(
                    {
                        "entity_type": row["entity_type"],
                        "total_rules": row["total_rules"] or 0,
                        "total_evaluations": total,
                        "passed": passed,
                        "compliance_pct": (passed / total * 100.0) if total > 0 else 0.0,
                        "avg_confidence": row["avg_confidence"] or 0.0,
                        "avg_execution_time": row["avg_execution_time"] or 0.0,
                        "total_violations": row["total_violations"] or 0,
                    }
                )
            return {"entity_types": entity_types}
        except Exception as e:
            logger.error("[FAIL] Error exporting metrics: %s", e)
            return {"entity_types": []}

    def close(self) -> None:
        """Close the database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            logger.info("[OK] Metrics database connection closed")
