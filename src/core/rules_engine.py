"""
Rules Engine - Motor principal de avaliação de regras de transformação.
Carrega transformation_rules do DB e avalia entidades estruturais.
"""
import sqlite3
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class EntityType(Enum):
    VIGA = 'VIGA'
    PILAR = 'PILAR'
    LAJE = 'LAJE'
    GARFO = 'GARFO'
    FUNDO = 'FUNDO'


class RuleStatus(Enum):
    ACTIVE = 'active'
    DRAFT = 'draft'
    ARCHIVED = 'archived'


@dataclass
class Rule:
    id: str
    name: str
    entity_type: str
    rule_logic: Dict
    accuracy_pct: float = 0.0
    coverage_pct: float = 0.0
    version: str = 'latest'
    status: str = 'active'
    is_production: bool = False

    def to_dict(self) -> dict:
        """Convert rule to dictionary."""
        d = {
            'id': self.id,
            'name': self.name,
            'entity_type': self.entity_type,
            'rule_logic': json.dumps(self.rule_logic) if isinstance(self.rule_logic, dict) else self.rule_logic,
            'accuracy_pct': self.accuracy_pct,
            'coverage_pct': self.coverage_pct,
            'version': self.version,
            'status': self.status,
            'is_production': self.is_production,
        }
        return d


@dataclass
class RuleMatch:
    rule: Optional[Rule] = None
    matched: bool = False
    confidence: float = 0.0
    interpretation_result: Dict = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0


@dataclass
class CoverageMetrics:
    entity_type: str
    total_evaluations: int = 0
    matched: int = 0
    avg_confidence: float = 0.0
    avg_time_ms: float = 0.0
    coverage_pct: float = 0.0


class RulesEngine:
    """
    Motor principal de avaliação de regras de transformação.

    Args:
        db_path: Path to project_data.vision database
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._loaded_rules: Dict[str, List[Rule]] = {}
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

    def load_rules(self, entity_type: str, version: str = 'latest') -> List[Rule]:
        """
        Load rules for entity type.

        Args:
            entity_type: VIGA, PILAR, LAJE, etc.
            version: Specific rule version (default: latest production)

        Returns:
            List of applicable rules
        """
        cache_key = f'{entity_type}:{version}'
        if cache_key in self._loaded_rules:
            return self._loaded_rules[cache_key]

        if not self.conn:
            return []

        try:
            if version == 'latest':
                rows = self.conn.execute("""
                    SELECT * FROM transformation_rules
                    WHERE entity_type = ? AND status = 'active'
                    ORDER BY accuracy_pct DESC
                """, (entity_type,)).fetchall()
            else:
                rows = self.conn.execute("""
                    SELECT * FROM transformation_rules
                    WHERE entity_type = ? AND version = ?
                    AND status = 'active'
                    ORDER BY accuracy_pct DESC
                """, (entity_type, version)).fetchall()

            rules = [self._row_to_rule(row) for row in rows]
            self._loaded_rules[cache_key] = rules
            return rules
        except Exception as e:
            logger.error(f'Error loading rules for {entity_type}: {e}')
            return []

    def match_entity(self, entity: dict, entity_type: str) -> RuleMatch:
        """
        Match rules against entity.

        Args:
            entity: Entity data dictionary
            entity_type: Entity type (VIGA, PILAR, etc.)

        Returns:
            RuleMatch with matching rule or error
        """
        rules = self.load_rules(entity_type)
        if not rules:
            return RuleMatch(error=f'No rules found for {entity_type}')

        best_match = RuleMatch()
        for rule in rules:
            try:
                match = self._evaluate_rule(rule, entity)
                if match.matched and match.confidence > best_match.confidence:
                    best_match = match
            except Exception as e:
                logger.debug(f'Rule evaluation error: {e}')

        if best_match.rule:
            self._log_evaluation(best_match, entity_type)

        return best_match

    def _evaluate_rule(self, rule: Rule, entity: dict) -> RuleMatch:
        """
        Evaluate single rule against entity.

        Args:
            rule: Rule to evaluate
            entity: Entity data

        Returns:
            RuleMatch with result
        """
        start = time.time()
        try:
            logic = rule.rule_logic
            if isinstance(logic, str):
                logic = json.loads(logic)

            conditions = logic.get('conditions', [])
            actions = logic.get('actions', {})

            all_met = True
            for condition in conditions:
                if not self._check_condition(condition, entity):
                    all_met = False
                    break

            elapsed_ms = (time.time() - start) * 1000

            if all_met:
                return RuleMatch(
                    rule=rule,
                    matched=True,
                    confidence=rule.accuracy_pct / 100.0,
                    interpretation_result=actions,
                    execution_time_ms=elapsed_ms
                )
            else:
                return RuleMatch(
                    rule=rule,
                    matched=False,
                    confidence=0.0,
                    execution_time_ms=elapsed_ms
                )
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            return RuleMatch(error=str(e), execution_time_ms=elapsed_ms)

    def _check_condition(self, condition: dict, entity: dict) -> bool:
        """
        Check if condition is met.

        Args:
            condition: Condition definition
            entity: Entity data

        Returns:
            Whether condition is satisfied
        """
        operator = condition.get('operator', 'equals')
        field_name = condition.get('field', '')
        expected = condition.get('value')
        actual = entity.get(field_name)

        try:
            if operator == 'equals':
                return actual == expected
            elif operator == 'not_equals':
                return actual != expected
            elif operator == 'greater_than':
                return float(actual or 0) > float(expected or 0)
            elif operator == 'less_than':
                return float(actual or 0) < float(expected or 0)
            elif operator == 'contains':
                return expected in str(actual or '')
            elif operator == 'regex':
                import re
                return bool(re.match(str(expected), str(actual or '')))
            elif operator == 'exists':
                return actual is not None and actual != '' and actual != '?'
            else:
                return actual == expected
        except Exception:
            return False

    def _log_evaluation(self, match: RuleMatch, entity_type: str):
        """Log rule evaluation for metrics."""
        if not self.conn or not match.rule:
            return
        try:
            entity_id = match.interpretation_result.get('entity_id', '')
            self.conn.execute("""
                INSERT INTO rule_evaluation_log
                (rule_id, entity_id, entity_type, matched, confidence,
                 interpretation_result, execution_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (match.rule.id, entity_id, entity_type,
                  match.matched, match.confidence,
                  json.dumps(match.interpretation_result),
                  match.execution_time_ms))
            self.conn.commit()
        except Exception as e:
            logger.debug(f'Failed to log evaluation: {e}')

    def get_coverage_metrics(self, entity_type: str) -> CoverageMetrics:
        """
        Get coverage metrics for entity type.

        Args:
            entity_type: Entity type

        Returns:
            Coverage metrics
        """
        if not self.conn:
            return CoverageMetrics(entity_type=entity_type)

        try:
            row = self.conn.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN matched THEN 1 END) as matched,
                    AVG(confidence) as avg_confidence,
                    AVG(execution_time_ms) as avg_time
                FROM rule_evaluation_log
                WHERE entity_type = ?
            """, (entity_type,)).fetchone()

            total = row['total'] or 0
            matched = row['matched'] or 0
            return CoverageMetrics(
                entity_type=entity_type,
                total_evaluations=total,
                matched=matched,
                avg_confidence=row['avg_confidence'] or 0.0,
                avg_time_ms=row['avg_time'] or 0.0,
                coverage_pct=(matched / max(1, total)) * 100
            )
        except Exception as e:
            logger.error(f'Error getting coverage metrics: {e}')
            return CoverageMetrics(entity_type=entity_type)

    def _row_to_rule(self, row) -> Rule:
        """Convert database row to Rule object."""
        row_dict = dict(row) if not isinstance(row, dict) else row
        logic = row_dict.get('rule_logic', '{}')
        if isinstance(logic, str):
            try:
                logic = json.loads(logic)
            except json.JSONDecodeError:
                logic = {}

        return Rule(
            id=row_dict.get('id', ''),
            name=row_dict.get('name', ''),
            entity_type=row_dict.get('entity_type', ''),
            rule_logic=logic,
            accuracy_pct=row_dict.get('accuracy_pct', 0.0) or 0.0,
            coverage_pct=row_dict.get('coverage_pct', 0.0) or 0.0,
            version=row_dict.get('version', 'latest') or 'latest',
            status=row_dict.get('status', 'active') or 'active',
            is_production=bool(row_dict.get('is_production', False)),
        )

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
