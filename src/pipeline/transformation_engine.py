# -*- coding: utf-8 -*-
"""TransformationEngine - GAP-1 CRITICO

Engine para derivar regras de transformação a partir dos training_events no SQLite.
Pipeline de 8 fases para transformar DXFs/PDFs de obras → DXFs finais para engenharia estrutural.
"""

import json, logging, sqlite3, uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@dataclass
class TrainingEvent:
    id: str
    project_id: str
    type: str
    role: str
    context_dna_json: str
    target_value: str
    status: str
    timestamp: str

    @property
    def context_dna(self) -> Dict[str, Any]:
        return json.loads(self.context_dna_json) if self.context_dna_json else {}

    @property
    def dna_vector(self) -> List[float]:
        context = self.context_dna
        level_2 = context.get("level_2_item", {})
        return level_2.get("dna_vector", [])

    @property
    def target_label(self) -> str:
        context = self.context_dna
        return context.get("target_label", self.target_value)

@dataclass
class TransformationRule:
    name: str
    entity_type: str
    description: str
    rule_logic: Dict[str, Any]
    version: str = "1.0.0"
    coverage_pct: float = 0.0
    accuracy_pct: float = 0.0
    error_count: int = 0
    status: str = "active"
    is_production: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()), "name": self.name, "entity_type": self.entity_type,
            "description": self.description, "rule_logic": json.dumps(self.rule_logic),
            "version": self.version, "coverage_pct": self.coverage_pct,
            "accuracy_pct": self.accuracy_pct, "error_count": self.error_count,
            "status": self.status, "is_production": self.is_production,
        }

class TransformationEngine:
    MIN_EVENTS_THRESHOLD = 10

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.training_events: List[TrainingEvent] = []
        self.rules: Dict[str, TransformationRule] = {}
        self.conn: Optional[sqlite3.Connection] = None
        logger.info(f"TransformationEngine inicializada com DB: {db_path}")

    def connect(self) -> sqlite3.Connection:
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def load_training_events(self) -> int:
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id, project_id, type, role, context_dna_json, target_value, status, timestamp FROM training_events ORDER BY timestamp DESC")
        self.training_events = []
        for row in cursor.fetchall():
            event = TrainingEvent(
                id=row["id"], project_id=row["project_id"], type=row["type"], role=row["role"],
                context_dna_json=row["context_dna_json"], target_value=row["target_value"],
                status=row["status"], timestamp=row["timestamp"] if row["timestamp"] else str(datetime.now())
            )
            self.training_events.append(event)
        logger.info(f"Carregados {len(self.training_events)} training_events")
        return len(self.training_events)

    def derive_rules(self) -> Dict[str, TransformationRule]:
        if not self.training_events:
            logger.warning("Nenhum training_event carregado.")
            return {}
        events_by_role: Dict[str, List[TrainingEvent]] = defaultdict(list)
        for event in self.training_events:
            events_by_role[event.role].append(event)
        logger.info(f"Derivando regras para {len(events_by_role)} roles únicos")
        self.rules = {}
        for role, events in events_by_role.items():
            if len(events) < self.MIN_EVENTS_THRESHOLD:
                continue
            entity_type = role.split("_")[0] if "_" in role else role
            dna_to_targets: Dict[str, Counter] = defaultdict(Counter)
            all_targets: Counter = Counter()
            for event in events:
                dna_key = self._dna_to_key(event.dna_vector)
                target = event.target_label
                dna_to_targets[dna_key][target] += 1
                all_targets[target] += 1
            rule_logic = {
                "dna_frequency_map": {}, "global_frequency_map": dict(all_targets),
                "total_events": len(events), "unique_dna_vectors": len(dna_to_targets),
            }
            for dna_key, target_counter in dna_to_targets.items():
                most_common_target, count = target_counter.most_common(1)[0]
                rule_logic["dna_frequency_map"][dna_key] = {
                    "most_common": most_common_target, "count": count, "distribution": dict(target_counter),
                }
            coverage_pct = (len(events) / len(self.training_events)) * 100 if self.training_events else 0
            correct_predictions = sum(counter.most_common(1)[0][1] for counter in dna_to_targets.values())
            accuracy_pct = (correct_predictions / len(events)) * 100 if events else 0
            rule = TransformationRule(
                name=role, entity_type=entity_type,
                description=f"Regra derivada para {role} baseada em {len(events)} eventos",
                rule_logic=rule_logic, version="1.0.0", coverage_pct=round(coverage_pct, 2),
                accuracy_pct=round(accuracy_pct, 2), status="active", is_production=False,
            )
            self.rules[role] = rule
            logger.info(f"Regra derivada: {role} (coverage={coverage_pct:.2f}%, accuracy={accuracy_pct:.2f}%)")
        logger.info(f"Total de regras derivadas: {len(self.rules)}")
        return self.rules

    def _dna_to_key(self, dna_vector: List[float]) -> str:
        if not dna_vector:
            return "empty"
        return ",".join(f"{v:.4f}" for v in dna_vector)

    def _key_to_dna(self, key: str) -> List[float]:
        if key == "empty":
            return []
        return [float(x) for x in key.split(",")]

    def calculate_coverage_accuracy(self, rule_name: str) -> Tuple[float, float]:
        if rule_name not in self.rules:
            return 0.0, 0.0
        rule = self.rules[rule_name]
        events_for_role = [e for e in self.training_events if e.role == rule_name]
        if not events_for_role:
            return 0.0, 0.0
        coverage_pct = (len(events_for_role) / len(self.training_events)) * 100
        correct = 0
        for event in events_for_role:
            dna_key = self._dna_to_key(event.dna_vector)
            if dna_key in rule.rule_logic.get("dna_frequency_map", {}):
                dna_data = rule.rule_logic["dna_frequency_map"][dna_key]
                if dna_data["most_common"] == event.target_label:
                    correct += 1
            else:
                global_map = rule.rule_logic.get("global_frequency_map", {})
                if global_map and max(global_map, key=global_map.get) == event.target_label:
                    correct += 1
        accuracy_pct = (correct / len(events_for_role)) * 100 if events_for_role else 0
        return round(coverage_pct, 2), round(accuracy_pct, 2)

    def persist_rules(self, min_coverage: float = 0.0) -> int:
        if not self.rules:
            logger.warning("Nenhuma regra para persistir.")
            return 0
        conn = self.connect()
        cursor = conn.cursor()
        persisted_count = 0
        for role, rule in self.rules.items():
            if rule.coverage_pct < min_coverage:
                continue
            try:
                data = rule.to_dict()
                cursor.execute("SELECT id FROM transformation_rules WHERE name = ? AND version = ?", (rule.name, rule.version))
                existing = cursor.fetchone()
                if existing:
                    cursor.execute("""UPDATE transformation_rules SET entity_type = ?, description = ?, rule_logic = ?,
                        coverage_pct = ?, accuracy_pct = ?, error_count = ?, status = ?, is_production = ?,
                        updated_at = CURRENT_TIMESTAMP WHERE name = ? AND version = ?""",
                        (rule.entity_type, rule.description, data["rule_logic"], rule.coverage_pct, rule.accuracy_pct,
                         rule.error_count, rule.status, rule.is_production, rule.name, rule.version))
                else:
                    cursor.execute("""INSERT INTO transformation_rules (id, name, entity_type, description, rule_logic,
                        version, coverage_pct, accuracy_pct, error_count, status, is_production)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (data["id"], rule.name, rule.entity_type, rule.description, data["rule_logic"],
                         rule.version, rule.coverage_pct, rule.accuracy_pct, rule.error_count, rule.status, rule.is_production))
                persisted_count += 1
            except Exception as e:
                logger.error(f"Erro ao persistir regra {role}: {e}")
                conn.rollback()
                continue
        conn.commit()
        logger.info(f"Persistidas {persisted_count} regras na tabela transformation_rules")
        return persisted_count

    def apply_rule(self, role: str, dna_vector: List[float]) -> Optional[str]:
        if role not in self.rules:
            return None
        rule = self.rules[role]
        dna_key = self._dna_to_key(dna_vector)
        dna_map = rule.rule_logic.get("dna_frequency_map", {})
        if dna_key in dna_map:
            return dna_map[dna_key]["most_common"]
        global_map = rule.rule_logic.get("global_frequency_map", {})
        if global_map:
            return max(global_map, key=global_map.get)
        return None

    def get_rule_stats(self) -> Dict[str, Any]:
        if not self.rules:
            return {}
        coverages = [r.coverage_pct for r in self.rules.values()]
        accuracies = [r.accuracy_pct for r in self.rules.values()]
        event_counts = [r.rule_logic.get("total_events", 0) for r in self.rules.values()]
        entity_counts: Dict[str, int] = defaultdict(int)
        for rule in self.rules.values():
            entity_counts[rule.entity_type] += 1
        return {
            "total_rules": len(self.rules), "total_training_events": len(self.training_events),
            "avg_coverage_pct": round(sum(coverages) / len(coverages), 2) if coverages else 0,
            "avg_accuracy_pct": round(sum(accuracies) / len(accuracies), 2) if accuracies else 0,
            "max_coverage_pct": round(max(coverages), 2) if coverages else 0,
            "max_accuracy_pct": round(max(accuracies), 2) if accuracies else 0,
            "total_events_covered": sum(event_counts), "rules_by_entity": dict(entity_counts),
        }

    def load_rules_from_db(self) -> int:
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT name, entity_type, description, rule_logic, version, coverage_pct, accuracy_pct, status, is_production FROM transformation_rules WHERE status = 'active'")
        self.rules = {}
        for row in cursor.fetchall():
            rule = TransformationRule(
                name=row["name"], entity_type=row["entity_type"], description=row["description"],
                rule_logic=json.loads(row["rule_logic"]), version=row["version"],
                coverage_pct=row["coverage_pct"] or 0, accuracy_pct=row["accuracy_pct"] or 0,
                status=row["status"], is_production=bool(row["is_production"]),
            )
            self.rules[row["name"]] = rule
        logger.info(f"Carregadas {len(self.rules)} regras do banco")
        return len(self.rules)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="TransformationEngine - Deriva regras de transformação")
    parser.add_argument("--db", type=str, default=r"D:\Agente-cad-PYSIDE\project_data.vision")
    parser.add_argument("--derive", action="store_true")
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--load", action="store_true")
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--min-events", type=int, default=10)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    TransformationEngine.MIN_EVENTS_THRESHOLD = args.min_events
    print("=" * 70)
    print("TRANSFORMATION ENGINE - CAD-ANALYZER")
    print("=" * 70)
    engine = TransformationEngine(args.db)
    try:
        if args.load:
            print("\n[1] Carregando regras existentes...")
            count = engine.load_rules_from_db()
            print(f"    -> {count} regras carregadas")
        if args.derive:
            print("\n[1] Carregando training_events...")
            event_count = engine.load_training_events()
            print(f"    -> {event_count} eventos carregados")
            print("\n[2] Derivando regras...")
            rules = engine.derive_rules()
            print(f"    -> {len(rules)} regras derivadas")
            print("\n[3] Estatísticas das regras:")
            stats = engine.get_rule_stats()
            print(f"    -> Total regras: {stats.get('total_rules', 0)}")
            print(f"    -> Coverage médio: {stats.get('avg_coverage_pct', 0):.2f}%")
            print(f"    -> Accuracy médio: {stats.get('avg_accuracy_pct', 0):.2f}%")
            print(f"    -> Regras por entidade: {stats.get('rules_by_entity', {})}")
            print("\n[4] Top 10 regras por coverage:")
            sorted_rules = sorted(engine.rules.values(), key=lambda r: r.coverage_pct, reverse=True)[:10]
            for i, rule in enumerate(sorted_rules, 1):
                print(f"    {i:2}. {rule.name:35} coverage={rule.coverage_pct:5.2f}%  accuracy={rule.accuracy_pct:5.2f}%")
        if args.persist:
            print("\n[5] Persistindo regras...")
            persisted = engine.persist_rules()
            print(f"    -> {persisted} regras persistidas")
        if args.test or (args.derive and not args.persist):
            print("\n[6] Testando aplicação de regras...")
            test_roles = ["Laje_name", "Pilar_name", "Laje_laje_outline_segs", "Pilar_dim"]
            for role in test_roles:
                if role in engine.rules:
                    rule = engine.rules[role]
                    dna_map = rule.rule_logic.get("dna_frequency_map", {})
                    if dna_map:
                        dna_key = list(dna_map.keys())[0]
                        dna_vector = engine._key_to_dna(dna_key)
                        predicted = engine.apply_rule(role, dna_vector)
                        print(f"    -> {role}: DNA {dna_key[:30]}... -> {predicted}")
                    else:
                        print(f"    -> {role}: Sem DNA vectors no frequency map")
                else:
                    print(f"    -> {role}: Regra não encontrada")
        print("\n" + "=" * 70)
        print("EXECUÇÃO CONCLUÍDA")
        print("=" * 70)
    finally:
        engine.close()

if __name__ == "__main__":
    main()
