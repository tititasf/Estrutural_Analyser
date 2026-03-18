"""
Rule Applier - Aplica regras de transformacao a entidades estruturais.
"""
import sqlite3
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class ConstraintViolation:
    constraint_name: str
    expected: Any
    actual: Any
    severity: str = "LOW"


@dataclass
class RuleApplicationContext:
    rule_id: str
    entity_id: str
    entity_type: str
    entity_data: Dict
    applied_constraints: List = field(default_factory=list)
    violations: List = field(default_factory=list)
    confidence: float = 0.0
    validation_passed: bool = False
    execution_time_ms: float = 0.0


class RuleApplier:
    """Applies transformation rules to structural entities."""

    def __init__(self, db_path: str):
        """Initialize rule applier with transformation_rules database."""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect_db()

    def _connect_db(self) -> None:
        """Open sqlite3 connection to the database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info("[OK] Connected to database: %s", self.db_path)
        except Exception as e:
            logger.error("[FAIL] Database connection failed: %s", e)
            self.conn = None

    def apply_rules_to_pilar(self, pilar_data: Dict[str, Any]) -> RuleApplicationContext:
        """Apply PILAR rules to pilar entity."""
        numero = pilar_data.get("numero", pilar_data.get("id", "unknown"))
        entity_id = f"pilar_{numero}"
        return self._apply_rules_to_entity(entity_id, "pilar", pilar_data)

    def apply_rules_to_laje(self, laje_data: Dict[str, Any]) -> RuleApplicationContext:
        """Apply LAJE rules to laje entity."""
        numero = laje_data.get("numero", laje_data.get("id", "unknown"))
        entity_id = f"laje_{numero}"
        return self._apply_rules_to_entity(entity_id, "laje", laje_data)

    def apply_rules_to_viga_lateral(self, viga_data: Dict[str, Any]) -> RuleApplicationContext:
        """Apply VIGA rules to viga entity."""
        numero = viga_data.get("numero", viga_data.get("id", "unknown"))
        entity_id = f"viga_{numero}"
        return self._apply_rules_to_entity(entity_id, "viga", viga_data)

    def apply_rules_to_fundos(self, fundo_data: Dict[str, Any]) -> RuleApplicationContext:
        """Apply FUNDO rules to fundo entity."""
        numero = fundo_data.get("numero", fundo_data.get("id", "unknown"))
        entity_id = f"fundo_{numero}"
        return self._apply_rules_to_entity(entity_id, "fundo", fundo_data)

    def apply_rules_to_garfos(self, garfo_data: Dict[str, Any]) -> RuleApplicationContext:
        """Apply GARFO rules to garfo entity."""
        numero = garfo_data.get("numero", garfo_data.get("id", "unknown"))
        entity_id = f"garfo_{numero}"
        return self._apply_rules_to_entity(entity_id, "garfo", garfo_data)

    def _apply_rules_to_entity(
        self, entity_id: str, entity_type: str, entity_data: Dict[str, Any]
    ) -> RuleApplicationContext:
        """Apply all applicable rules to an entity."""
        start_time = time.perf_counter()

        context = RuleApplicationContext(
            rule_id="",
            entity_id=entity_id,
            entity_type=entity_type,
            entity_data=entity_data,
        )

        if self.conn is None:
            context.execution_time_ms = (time.perf_counter() - start_time) * 1000
            return context

        try:
            cursor = self.conn.execute(
                """SELECT * FROM transformation_rules
                   WHERE entity_type=? AND status='active' AND is_production=TRUE
                   ORDER BY accuracy_pct DESC""",
                (entity_type,),
            )
            rules = cursor.fetchall()

            if not rules:
                logger.info("[INFO] No production rules for %s", entity_type)
                context.execution_time_ms = (time.perf_counter() - start_time) * 1000
                return context

            best_confidence = 0.0
            for rule in rules:
                self._apply_rule(rule, context)
                if context.confidence > best_confidence:
                    best_confidence = context.confidence
                    context.rule_id = rule["rule_id"]

            context.confidence = best_confidence
            context.validation_passed = len(context.violations) == 0

        except Exception as e:
            logger.error("[FAIL] Error applying rules to %s %s: %s", entity_type, entity_id, e)

        context.execution_time_ms = (time.perf_counter() - start_time) * 1000
        return context

    def _apply_rule(self, rule: sqlite3.Row, context: RuleApplicationContext) -> None:
        """Apply single rule to entity in context."""
        try:
            rule_logic_raw = rule["rule_logic"]
            if isinstance(rule_logic_raw, str):
                rule_logic = json.loads(rule_logic_raw)
            else:
                rule_logic = rule_logic_raw or {}

            constraints = rule_logic.get("constraints", [])
            entity_data = context.entity_data

            checked = 0
            passed = 0
            for constraint in constraints:
                checked += 1
                constraint_name = constraint.get("name", "unnamed")
                field_name = constraint.get("field", "")
                expected = constraint.get("expected", None)
                actual = entity_data.get(field_name, None)

                if actual is not None and expected is not None:
                    if self._check_constraint(constraint, actual):
                        passed += 1
                        context.applied_constraints.append(constraint_name)
                    else:
                        context.violations.append(
                            ConstraintViolation(
                                constraint_name=constraint_name,
                                expected=expected,
                                actual=actual,
                                severity=constraint.get("severity", "LOW"),
                            )
                        )
                else:
                    # Missing data -- cannot evaluate
                    passed += 1  # lenient: missing data is not a violation

            if checked > 0:
                context.confidence = passed / checked
            else:
                context.confidence = 1.0

        except Exception as e:
            logger.error("[FAIL] Error applying rule %s: %s", rule["rule_id"], e)

    @staticmethod
    def _check_constraint(constraint: Dict[str, Any], actual: Any) -> bool:
        """Check a single constraint value against actual data."""
        operator = constraint.get("operator", "equals")
        expected = constraint.get("expected")

        try:
            if operator == "equals":
                return actual == expected
            elif operator == "gte":
                return float(actual) >= float(expected)
            elif operator == "lte":
                return float(actual) <= float(expected)
            elif operator == "gt":
                return float(actual) > float(expected)
            elif operator == "lt":
                return float(actual) < float(expected)
            elif operator == "in":
                return actual in expected
            elif operator == "contains":
                return str(expected) in str(actual)
            elif operator == "range":
                min_val = float(constraint.get("min", 0))
                max_val = float(constraint.get("max", float("inf")))
                return min_val <= float(actual) <= max_val
            else:
                return actual == expected
        except (ValueError, TypeError):
            return False

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

    def close(self) -> None:
        """Close the database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            logger.info("[OK] Database connection closed")
