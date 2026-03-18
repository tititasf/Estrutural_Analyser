"""
Rule Validator - Valida entidades contra as regras de transformação.
Verifica constraints geométricas, semânticas e de nomenclatura.
"""
import sqlite3
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ConstraintType(Enum):
    GEOMETRIC = 'geometric'
    SEMANTIC = 'semantic'
    NOMENCLATURE = 'nomenclature'
    SPATIAL = 'spatial'


class ValidationStatus(Enum):
    PASSED = 'passed'
    FAILED = 'failed'
    WARNING = 'warning'
    SKIPPED = 'skipped'


@dataclass
class ConstraintViolation:
    constraint_type: ConstraintType
    field_name: str
    expected: Any
    actual: Any
    severity: str = 'LOW'
    description: str = ''


@dataclass
class ValidationResult:
    entity_id: str
    entity_type: str
    status: ValidationStatus = ValidationStatus.PASSED
    confidence: float = 0.0
    violations: List[ConstraintViolation] = field(default_factory=list)
    rules_applied: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


class RuleValidator:
    """Valida entidades contra as regras de transformação do DB."""

    def __init__(self, db_path: str):
        """Initialize rule validator."""
        self.db_path = db_path
        self.conn = None
        self._session_results: List[ValidationResult] = []
        self._connect_db()

    def _connect_db(self):
        """Connect to database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f'Connected to database: {self.db_path}')
        except Exception as e:
            logger.error(f'Database connection failed: {e}')
            self.conn = None

    def validate_entity(self, entity_id: str, entity_type: str,
                        entity_data: dict) -> ValidationResult:
        """
        Validate entity against applicable rules.

        Args:
            entity_id: Entity identifier
            entity_type: Entity type (VIGA, PILAR, LAJE, etc.)
            entity_data: Entity properties

        Returns:
            Validation result
        """
        logger.debug(f'Validating entity {entity_id} of type {entity_type}')
        start = time.time()

        result = ValidationResult(entity_id=entity_id, entity_type=entity_type)

        if not self.conn:
            result.status = ValidationStatus.SKIPPED
            return result

        try:
            rows = self.conn.execute("""
                SELECT * FROM transformation_rules
                WHERE entity_type LIKE ? AND status = 'active'
                ORDER BY accuracy_pct DESC
            """, (f'%{entity_type}%',)).fetchall()

            if not rows:
                result.status = ValidationStatus.SKIPPED
                result.execution_time_ms = (time.time() - start) * 1000
                return result

            all_violations = []
            for rule_row in rows:
                rule_result = self._validate_against_rule(
                    dict(rule_row), entity_id, entity_type, entity_data
                )
                all_violations.extend(rule_result.violations)
                result.rules_applied.append(rule_row['name'] or rule_row['id'])

            result.violations = all_violations
            result.confidence = 1.0 - min(1.0, len(all_violations) * 0.2)
            result.status = (
                ValidationStatus.PASSED if not all_violations
                else ValidationStatus.WARNING if all(
                    v.severity in ('LOW', 'MEDIUM') for v in all_violations
                )
                else ValidationStatus.FAILED
            )
        except Exception as e:
            logger.error(f'Validation error for {entity_id}: {e}')
            result.status = ValidationStatus.SKIPPED

        result.execution_time_ms = (time.time() - start) * 1000
        self._session_results.append(result)
        return result

    def _validate_against_rule(self, rule: dict, entity_id: str,
                                entity_type: str, entity_data: dict) -> ValidationResult:
        """Validate entity against specific rule."""
        result = ValidationResult(entity_id=entity_id, entity_type=entity_type)

        logic_raw = rule.get('rule_logic', '{}')
        try:
            logic = json.loads(logic_raw) if isinstance(logic_raw, str) else logic_raw
        except json.JSONDecodeError:
            return result

        constraints = logic.get('constraints', [])
        classification = logic.get('classification', {})
        nomenclature = logic.get('nomenclature', {})

        violations = []
        violations.extend(self._check_geometric_constraints(constraints, entity_data))
        violations.extend(self._check_semantic_constraints(classification, entity_data))
        violations.extend(self._check_nomenclature(nomenclature, entity_data))

        result.violations = violations
        return result

    def _check_geometric_constraints(self, constraints: list,
                                     entity_data: dict) -> List[ConstraintViolation]:
        """Check geometric constraints."""
        violations = []
        for constraint in constraints:
            if not isinstance(constraint, dict):
                continue
            field_name = constraint.get('field', '')
            min_val = constraint.get('min')
            max_val = constraint.get('max')
            actual = entity_data.get(field_name)

            if actual is None:
                continue

            try:
                actual_f = float(actual)
                if min_val is not None and actual_f < float(min_val):
                    violations.append(ConstraintViolation(
                        constraint_type=ConstraintType.GEOMETRIC,
                        field_name=field_name,
                        expected=f'>= {min_val}',
                        actual=actual_f,
                        severity='MEDIUM',
                        description=f'{field_name}={actual_f} out of range [{min_val}, {max_val}]'
                    ))
                if max_val is not None and actual_f > float(max_val):
                    violations.append(ConstraintViolation(
                        constraint_type=ConstraintType.GEOMETRIC,
                        field_name=field_name,
                        expected=f'<= {max_val}',
                        actual=actual_f,
                        severity='MEDIUM',
                        description=f'{field_name}={actual_f} out of range [{min_val}, {max_val}]'
                    ))
            except (ValueError, TypeError) as e:
                logger.debug(f'Geometric constraint check failed: {e}')

        return violations

    def _check_semantic_constraints(self, classification: dict,
                                    entity_data: dict) -> List[ConstraintViolation]:
        """Check semantic constraints."""
        violations = []
        hints = classification.get('semantic_hints', [])
        label = entity_data.get('label', entity_data.get('name', ''))

        for hint in hints:
            if not isinstance(hint, str):
                continue
            try:
                if hint.startswith('^') or hint.endswith('$') or '\\' in hint:
                    # regex hint
                    if not re.match(hint, str(label or ''), re.IGNORECASE):
                        violations.append(ConstraintViolation(
                            constraint_type=ConstraintType.SEMANTIC,
                            field_name='label',
                            expected=hint,
                            actual=label,
                            severity='LOW',
                            description=f"Label '{label}' does not match semantic hint '{hint}'"
                        ))
                        break
            except re.error:
                pass

        return violations

    def _check_nomenclature(self, nomenclature: dict,
                            entity_data: dict) -> List[ConstraintViolation]:
        """Check nomenclature patterns."""
        violations = []
        sample_labels = nomenclature.get('sample_labels', [])
        if not sample_labels:
            return violations

        label = entity_data.get('label', entity_data.get('name', ''))
        if not label:
            return violations

        expected_style = self._get_label_style(sample_labels[0]) if sample_labels else 'unknown'
        actual_style = self._get_label_style(str(label))

        if expected_style != actual_style and expected_style != 'unknown':
            violations.append(ConstraintViolation(
                constraint_type=ConstraintType.NOMENCLATURE,
                field_name='label',
                expected=expected_style,
                actual=actual_style,
                severity='LOW',
                description=f'Label style mismatch: expected {expected_style}, got {actual_style}'
            ))

        return violations

    @staticmethod
    def _get_label_style(label: str) -> str:
        """Determine label style (numeric, alpha, alphanumeric)."""
        if not label:
            return 'unknown'
        if label.isdigit():
            return 'numeric'
        if label.isalpha():
            return 'alpha'
        return 'alphanumeric'

    def get_validation_metrics(self) -> dict:
        """Get validation session metrics."""
        if not self._session_results:
            return {'total': 0, 'passed': 0, 'failed': 0, 'warnings': 0, 'skipped': 0}

        counts = {s.value: 0 for s in ValidationStatus}
        for r in self._session_results:
            counts[r.status.value] = counts.get(r.status.value, 0) + 1

        total = len(self._session_results)
        return {
            'total': total,
            'passed': counts.get('passed', 0),
            'failed': counts.get('failed', 0),
            'warnings': counts.get('warning', 0),
            'skipped': counts.get('skipped', 0),
            'pass_rate': counts.get('passed', 0) / max(1, total),
        }

    def store_validation_results(self) -> dict:
        """Store validation results in database."""
        if not self.conn:
            return {'success': False, 'error': 'no connection'}

        stored = 0
        for result in self._session_results:
            for rule_id in result.rules_applied:
                try:
                    self.conn.execute("""
                        INSERT INTO rule_evaluation_log
                        (rule_id, entity_id, entity_type, matched, confidence, validation_passed)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (rule_id, result.entity_id, result.entity_type,
                          len(result.rules_applied) > 0,
                          result.confidence,
                          result.status == ValidationStatus.PASSED))
                    stored += 1
                except Exception as e:
                    logger.debug(f'Store error: {e}')

        try:
            self.conn.commit()
        except Exception:
            pass

        return {'success': True, 'stored': stored}

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
