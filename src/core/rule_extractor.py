"""
Rule Extractor - Extrai regras de transformacao a partir de dados de obras.
"""
import sqlite3
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ExtractionPattern:
    pattern_type: str  # 'geometric', 'semantic', 'nomenclature'
    entity_type: str
    pattern: str
    confidence: float = 0.0
    sample_count: int = 0


@dataclass
class ExtractedRule:
    name: str
    entity_type: str
    rule_logic: Dict
    coverage_pct: float = 0.0
    accuracy_pct: float = 0.0
    source_obra: str = ""


class RuleExtractor:
    """Extracts transformation rules from construction project data (obras)."""

    def __init__(self, db_path: str):
        """Initialize rule extractor with database connection."""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect_db()

    def _connect_db(self) -> None:
        """Open sqlite3 connection."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info("Connected to database: %s", self.db_path)
        except Exception as e:
            logger.error("Database connection failed: %s", e)
            self.conn = None

    def extract_from_obra(self, obra_name: str) -> Dict[str, Any]:
        """Extract rules from a complete obra (project)."""
        if self.conn is None:
            return {"rules": [], "metrics": {"total_types": 0}}

        try:
            # Look up obra_id from name
            cursor = self.conn.execute(
                "SELECT id FROM obras WHERE name=? LIMIT 1", (obra_name,)
            )
            obra_row = cursor.fetchone()
            obra_id = obra_row["id"] if obra_row else obra_name

            cursor = self.conn.execute(
                """SELECT type, COUNT(*) as count,
                          GROUP_CONCAT(label, ',') as labels
                   FROM structural_entities
                   WHERE obra_id=?
                   GROUP BY type""",
                (obra_id,),
            )
            rows = cursor.fetchall()

            rules: List[ExtractedRule] = []
            for row in rows:
                entity_type = row["type"]
                entity_data = {
                    "count": row["count"],
                    "labels": row["labels"] or "",
                }
                extracted = self._extract_type_rule(entity_type, entity_data)
                if extracted is not None:
                    extracted.source_obra = obra_name
                    rules.append(extracted)

            return {
                "rules": rules,
                "metrics": {
                    "total_types": len(rows),
                    "total_rules_extracted": len(rules),
                    "obra_name": obra_name,
                },
            }
        except Exception as e:
            logger.error("Error extracting from obra %s: %s", obra_name, e)
            return {"rules": [], "metrics": {"total_types": 0, "error": str(e)}}

    def _extract_type_rule(
        self, entity_type: str, entity_data: Dict[str, Any]
    ) -> Optional[ExtractedRule]:
        """Extract rule for specific entity type."""
        try:
            logic_name = f"interpret_{entity_type}"
            classification = self._get_classification_logic(entity_type)
            constraints = self._get_constraints(entity_type)
            nomenclature = self._get_nomenclature_pattern(entity_type, entity_data)

            rule_logic = {
                "name": logic_name,
                "classification": classification,
                "constraints": constraints,
                "nomenclature": nomenclature,
            }

            count = entity_data.get("count", 0)
            coverage = min(100.0, count * 10.0) if count > 0 else 0.0

            return ExtractedRule(
                name=f"rule_{entity_type}",
                entity_type=entity_type,
                rule_logic=rule_logic,
                coverage_pct=coverage,
                accuracy_pct=0.0,  # To be updated after validation
            )
        except Exception as e:
            logger.error("Error extracting type rule for %s: %s", entity_type, e)
            return None

    def _get_classification_logic(self, entity_type: str) -> Dict[str, Any]:
        """Get classification logic for entity type."""
        logic_map: Dict[str, Dict[str, Any]] = {
            "vigas": {
                "condition": "horizontal_span > 1000",
                "field": "horizontal_span",
                "threshold": 1000,
                "description": "Vigas identified by horizontal span exceeding 1000mm",
            },
            "viga": {
                "condition": "horizontal_span > 1000",
                "field": "horizontal_span",
                "threshold": 1000,
                "description": "Viga identified by horizontal span exceeding 1000mm",
            },
            "pilares": {
                "condition": "vertical_extent > 500",
                "field": "vertical_extent",
                "threshold": 500,
                "description": "Pilares identified by vertical extent exceeding 500mm",
            },
            "pilar": {
                "condition": "vertical_extent > 500",
                "field": "vertical_extent",
                "threshold": 500,
                "description": "Pilar identified by vertical extent exceeding 500mm",
            },
            "laje": {
                "condition": "area > 10000",
                "field": "area",
                "threshold": 10000,
                "description": "Laje identified by area exceeding 10000mm2",
            },
            "fundo": {
                "condition": "is_bottom_face",
                "field": "is_bottom_face",
                "threshold": True,
                "description": "Fundo identified as bottom face of structural element",
            },
            "garfo": {
                "condition": "is_fork_connection",
                "field": "is_fork_connection",
                "threshold": True,
                "description": "Garfo identified as fork connection element",
            },
        }
        return logic_map.get(entity_type, {"condition": "unknown", "field": "", "threshold": 0})

    def _get_constraints(self, entity_type: str) -> List[Dict[str, Any]]:
        """Get validation constraints for entity type."""
        constraint_map: Dict[str, List[Dict[str, Any]]] = {
            "pilar": [
                {"name": "shape", "type": "geometric", "values": ["rectangular", "circular", "L", "T"]},
                {"name": "min_dimension", "type": "geometric", "min": 100, "max": 2000},
            ],
            "pilares": [
                {"name": "shape", "type": "geometric", "values": ["rectangular", "circular", "L", "T"]},
            ],
            "viga": [
                {"name": "shape", "type": "geometric", "values": ["rectangular"]},
                {"name": "tipo", "type": "semantic", "values": ["reta", "cambotada"]},
            ],
            "vigas": [
                {"name": "shape", "type": "geometric", "values": ["rectangular"]},
            ],
            "laje": [
                {"name": "shape", "type": "geometric", "values": ["rectangular", "irregular"]},
            ],
            "fundo": [
                {"name": "is_bottom", "type": "semantic", "values": [True]},
            ],
            "garfo": [
                {"name": "is_fork", "type": "semantic", "values": [True]},
            ],
        }
        return constraint_map.get(entity_type, [])

    def _get_nomenclature_pattern(
        self, entity_type: str, entity_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract nomenclature patterns from labels."""
        labels_raw = entity_data.get("labels", "")
        if not labels_raw:
            return {"pattern": "", "sample_labels": [], "style": "unknown"}

        labels = [lbl.strip() for lbl in labels_raw.split(",") if lbl.strip()]
        sample_labels = labels[:10]  # Keep first 10 as samples

        # Try to detect pattern from labels
        if labels:
            first = labels[0]
            if re.match(r"^[A-Z]+\d+", first):
                style = "alphanumeric_prefix"
                pattern = re.sub(r"\d+", "{N}", first)
            elif re.match(r"^\d+", first):
                style = "numeric"
                pattern = "{N}"
            else:
                style = "alpha"
                pattern = first
        else:
            style = "unknown"
            pattern = ""

        return {
            "pattern": pattern,
            "sample_labels": sample_labels,
            "style": style,
            "total_labels": len(labels),
        }

    def store_rules(
        self, rules: List[ExtractedRule], source_obra: str
    ) -> Dict[str, Any]:
        """Store extracted rules into transformation_rules table."""
        if self.conn is None:
            return {"success": False, "stored": 0, "error": "No database connection"}

        logger.info("Storing %d rules from obra %s", len(rules), source_obra)

        stored = 0
        errors = []
        for rule in rules:
            try:
                rule_logic_json = json.dumps(rule.rule_logic, ensure_ascii=False)
                self.conn.execute(
                    """INSERT INTO transformation_rules
                       (name, entity_type, rule_logic, coverage_pct, accuracy_pct,
                        source_obra, status, is_production)
                       VALUES (?, ?, ?, ?, ?, ?, 'active', FALSE)""",
                    (
                        rule.name,
                        rule.entity_type,
                        rule_logic_json,
                        rule.coverage_pct,
                        rule.accuracy_pct,
                        source_obra,
                    ),
                )
                stored += 1
            except Exception as e:
                errors.append({"rule": rule.name, "error": str(e)})
                logger.error("Error storing rule %s: %s", rule.name, e)

        self.conn.commit()
        logger.info("[OK] Stored %d/%d rules", stored, len(rules))
        return {"success": len(errors) == 0, "stored": stored, "errors": errors}

    def get_extraction_summary(self) -> Dict[str, Any]:
        """Get summary of all extracted rules grouped by entity type."""
        if self.conn is None:
            return {"success": False, "summary": []}
        try:
            cursor = self.conn.execute(
                """SELECT entity_type,
                          COUNT(*) as count,
                          AVG(coverage_pct) as avg_coverage
                   FROM transformation_rules
                   WHERE status='active'
                   GROUP BY entity_type"""
            )
            rows = cursor.fetchall()
            summary = [
                {
                    "entity_type": row["entity_type"],
                    "count": row["count"],
                    "avg_coverage": row["avg_coverage"] or 0.0,
                }
                for row in rows
            ]
            return {"success": True, "summary": summary}
        except Exception as e:
            logger.error("Error getting extraction summary: %s", e)
            return {"success": False, "summary": [], "error": str(e)}

    def close(self) -> None:
        """Close the database connection."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")
