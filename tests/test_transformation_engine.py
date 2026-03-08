# -*- coding: utf-8 -*-
"""
Testes para TransformationEngine - GAP-1 CRÍTICO

Testes unitários e de integração para a engine de derivação de regras.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, r"D:\Agente-cad-PYSIDE\src")

from pipeline.transformation_engine import (
    TrainingEvent,
    TransformationRule,
    TransformationEngine,
)


class TestTrainingEvent(unittest.TestCase):
    """Testes para a classe TrainingEvent."""

    def test_context_dna_parse(self):
        """Testa o parse do JSON context_dna."""
        event = TrainingEvent(
            id="test-1",
            project_id="proj-1",
            type="manual_correction",
            role="Laje_name",
            context_dna_json='{"level_2_item": {"dna_vector": [1.0, 2.0, 3.0]}}',
            target_value="L1",
            status="valid",
            timestamp="2026-03-05 10:00:00",
        )
        self.assertEqual(event.context_dna["level_2_item"]["dna_vector"], [1.0, 2.0, 3.0])

    def test_dna_vector_extraction(self):
        """Testa a extração do DNA vector."""
        event = TrainingEvent(
            id="test-1",
            project_id="proj-1",
            type="manual_correction",
            role="Laje_name",
            context_dna_json='{"level_2_item": {"dna_vector": [1.0, 2.0, 3.0, 4.0]}}',
            target_value="L1",
            status="valid",
            timestamp="2026-03-05 10:00:00",
        )
        self.assertEqual(event.dna_vector, [1.0, 2.0, 3.0, 4.0])

    def test_target_label_from_context(self):
        """Testa a extração do target_label do context_dna."""
        event = TrainingEvent(
            id="test-1",
            project_id="proj-1",
            type="manual_correction",
            role="Laje_name",
            context_dna_json='{"target_label": "L2"}',
            target_value="L1",
            status="valid",
            timestamp="2026-03-05 10:00:00",
        )
        self.assertEqual(event.target_label, "L2")

    def test_target_label_fallback(self):
        """Testa o fallback para target_value quando não há target_label."""
        event = TrainingEvent(
            id="test-1",
            project_id="proj-1",
            type="manual_correction",
            role="Laje_name",
            context_dna_json="{}",
            target_value="L1",
            status="valid",
            timestamp="2026-03-05 10:00:00",
        )
        self.assertEqual(event.target_label, "L1")

    def test_empty_dna_vector(self):
        """Testa DNA vector vazio."""
        event = TrainingEvent(
            id="test-1",
            project_id="proj-1",
            type="manual_correction",
            role="Laje_name",
            context_dna_json='{"level_2_item": {}}',
            target_value="L1",
            status="valid",
            timestamp="2026-03-05 10:00:00",
        )
        self.assertEqual(event.dna_vector, [])


class TestTransformationRule(unittest.TestCase):
    """Testes para a classe TransformationRule."""

    def test_to_dict(self):
        """Testa a conversão para dicionário."""
        rule = TransformationRule(
            name="Laje_name",
            entity_type="Laje",
            description="Test rule",
            rule_logic={"dna_frequency_map": {"1.0,2.0": {"most_common": "L1", "count": 10}}},
            version="1.0.0",
            coverage_pct=50.0,
            accuracy_pct=80.0,
        )
        d = rule.to_dict()
        self.assertEqual(d["name"], "Laje_name")
        self.assertEqual(d["entity_type"], "Laje")
        self.assertIn("id", d)
        self.assertEqual(d["coverage_pct"], 50.0)
        self.assertEqual(d["accuracy_pct"], 80.0)
        self.assertIsInstance(d["rule_logic"], str)  # JSON string


class TestTransformationEngine(unittest.TestCase):
    """Testes para a classe TransformationEngine."""

    @classmethod
    def setUpClass(cls):
        """Cria um banco de dados temporário para testes."""
        cls.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".vision")
        cls.temp_db_path = cls.temp_db.name
        cls.temp_db.close()

        # Criar schema e dados de teste
        conn = sqlite3.connect(cls.temp_db_path)
        cursor = conn.cursor()

        # Criar tabela training_events
        cursor.execute("""
            CREATE TABLE training_events (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                type TEXT,
                role TEXT,
                context_dna_json TEXT,
                target_value TEXT,
                status TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Criar tabela transformation_rules
        cursor.execute("""
            CREATE TABLE transformation_rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                description TEXT,
                rule_logic JSON NOT NULL,
                version TEXT NOT NULL,
                coverage_pct REAL DEFAULT 0.0,
                accuracy_pct REAL DEFAULT 0.0,
                error_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                is_production BOOLEAN DEFAULT FALSE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, version)
            )
        """)

        # Inserir dados de teste - 20 eventos para Laje_name (>= threshold)
        for i in range(20):
            cursor.execute("""
                INSERT INTO training_events (id, project_id, type, role, context_dna_json, target_value, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f"test-{i}",
                "proj-1",
                "manual_correction",
                "Laje_name",
                json.dumps({
                    "level_2_item": {"dna_vector": [1.0, 2.0, 3.0, 4.0]},
                    "target_label": f"L{i % 3 + 1}"  # L1, L2, L3
                }),
                f"L{i % 3 + 1}",
                "valid",
            ))

        # Inserir dados de teste - 15 eventos para Pilar_dim (>= threshold)
        for i in range(15):
            cursor.execute("""
                INSERT INTO training_events (id, project_id, type, role, context_dna_json, target_value, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f"pilar-{i}",
                "proj-1",
                "manual_correction",
                "Pilar_dim",
                json.dumps({
                    "level_2_item": {"dna_vector": [10.0, 20.0, 30.0, 40.0]},
                    "target_label": "(19x229)" if i < 10 else "(20x300)"
                }),
                "(19x229)" if i < 10 else "(20x300)",
                "valid",
            ))

        # Inserir dados de teste - 5 eventos para Viga_name (< threshold, não deve gerar regra)
        for i in range(5):
            cursor.execute("""
                INSERT INTO training_events (id, project_id, type, role, context_dna_json, target_value, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f"viga-{i}",
                "proj-1",
                "manual_correction",
                "Viga_name",
                json.dumps({
                    "level_2_item": {"dna_vector": [5.0, 6.0, 7.0, 8.0]},
                    "target_label": "V1"
                }),
                "V1",
                "valid",
            ))

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        """Remove o banco de dados temporário."""
        if os.path.exists(cls.temp_db_path):
            os.unlink(cls.temp_db_path)

    def setUp(self):
        """Cria uma nova engine para cada teste."""
        self.engine = TransformationEngine(self.temp_db_path)

    def tearDown(self):
        """Fecha a engine."""
        self.engine.close()

    def test_init(self):
        """Testa a inicialização da engine."""
        self.assertEqual(self.engine.db_path, self.temp_db_path)
        self.assertEqual(len(self.engine.training_events), 0)
        self.assertEqual(len(self.engine.rules), 0)

    def test_load_training_events(self):
        """Testa o carregamento de training_events."""
        count = self.engine.load_training_events()
        self.assertEqual(count, 40)  # 20 + 15 + 5
        self.assertEqual(len(self.engine.training_events), 40)

    def test_derive_rules(self):
        """Testa a derivação de regras."""
        self.engine.load_training_events()
        rules = self.engine.derive_rules()

        # Deve criar regras apenas para roles com >= 10 eventos
        self.assertIn("Laje_name", rules)
        self.assertIn("Pilar_dim", rules)
        self.assertNotIn("Viga_name", rules)  # Apenas 5 eventos

        # Verificar entity_type
        self.assertEqual(rules["Laje_name"].entity_type, "Laje")
        self.assertEqual(rules["Pilar_dim"].entity_type, "Pilar")

    def test_derive_rules_threshold(self):
        """Testa o threshold de eventos mínimos."""
        # Reduzir threshold para 5
        TransformationEngine.MIN_EVENTS_THRESHOLD = 5
        try:
            self.engine.load_training_events()
            rules = self.engine.derive_rules()
            self.assertIn("Viga_name", rules)  # Agora deve criar regra
        finally:
            TransformationEngine.MIN_EVENTS_THRESHOLD = 10

    def test_apply_rule(self):
        """Testa a aplicação de uma regra."""
        self.engine.load_training_events()
        self.engine.derive_rules()

        # Testar com DNA vector conhecido
        result = self.engine.apply_rule("Laje_name", [1.0, 2.0, 3.0, 4.0])
        self.assertIn(result, ["L1", "L2", "L3"])

        # Testar com role inexistente
        result = self.engine.apply_rule("NonExistent", [1.0, 2.0])
        self.assertIsNone(result)

    def test_apply_rule_pilar_dim(self):
        """Testa aplicação de regra para Pilar_dim."""
        self.engine.load_training_events()
        self.engine.derive_rules()

        # (19x229) aparece 10 vezes, (20x300) aparece 5 vezes
        result = self.engine.apply_rule("Pilar_dim", [10.0, 20.0, 30.0, 40.0])
        self.assertEqual(result, "(19x229)")  # Mais frequente

    def test_calculate_coverage_accuracy(self):
        """Testa o cálculo de coverage e accuracy."""
        self.engine.load_training_events()
        self.engine.derive_rules()

        coverage, accuracy = self.engine.calculate_coverage_accuracy("Laje_name")
        self.assertGreater(coverage, 0)
        self.assertGreaterEqual(accuracy, 0)
        self.assertLessEqual(accuracy, 100)

    def test_persist_rules(self):
        """Testa a persistência de regras."""
        self.engine.load_training_events()
        self.engine.derive_rules()

        count = self.engine.persist_rules()
        self.assertEqual(count, 2)  # Laje_name e Pilar_dim

        # Verificar no banco
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transformation_rules")
        db_count = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(db_count, 2)

    def test_get_rule_stats(self):
        """Testa as estatísticas das regras."""
        self.engine.load_training_events()
        self.engine.derive_rules()

        stats = self.engine.get_rule_stats()
        self.assertEqual(stats["total_rules"], 2)
        self.assertEqual(stats["total_training_events"], 40)
        self.assertIn("avg_coverage_pct", stats)
        self.assertIn("avg_accuracy_pct", stats)
        self.assertIn("rules_by_entity", stats)
        self.assertEqual(stats["rules_by_entity"], {"Laje": 1, "Pilar": 1})

    def test_load_rules_from_db(self):
        """Testa o carregamento de regras do banco."""
        # Primeiro persistir regras
        self.engine.load_training_events()
        self.engine.derive_rules()
        self.engine.persist_rules()

        # Criar nova engine e carregar regras
        new_engine = TransformationEngine(self.temp_db_path)
        try:
            count = new_engine.load_rules_from_db()
            self.assertEqual(count, 2)
            self.assertIn("Laje_name", new_engine.rules)
            self.assertIn("Pilar_dim", new_engine.rules)
        finally:
            new_engine.close()

    def test_dna_to_key_and_back(self):
        """Testa conversão DNA vector <-> key."""
        dna = [1.0, 2.5, 3.14159, 4.0]
        key = self.engine._dna_to_key(dna)
        dna_back = self.engine._key_to_dna(key)
        # Verificar com tolerância para floating point
        for i, (a, b) in enumerate(zip(dna, dna_back)):
            self.assertAlmostEqual(a, b, places=4)

    def test_empty_dna_vector_key(self):
        """Testa conversão de DNA vector vazio."""
        key = self.engine._dna_to_key([])
        self.assertEqual(key, "empty")
        dna_back = self.engine._key_to_dna(key)
        self.assertEqual(dna_back, [])


class TestIntegrationRealDB(unittest.TestCase):
    """Testes de integração com o banco de dados real."""

    @classmethod
    def setUpClass(cls):
        """Verifica se o banco de dados real existe."""
        cls.real_db_path = r"D:\Agente-cad-PYSIDE\project_data.vision"
        cls.db_exists = os.path.exists(cls.real_db_path)

    @unittest.skipUnless(os.path.exists(r"D:\Agente-cad-PYSIDE\project_data.vision"),
                         "Banco de dados real não encontrado")
    def test_load_real_training_events(self):
        """Testa carregamento de eventos reais."""
        engine = TransformationEngine(self.real_db_path)
        try:
            count = engine.load_training_events()
            self.assertGreater(count, 0)
            self.assertGreaterEqual(count, 800)  # Esperado ~805
        finally:
            engine.close()

    @unittest.skipUnless(os.path.exists(r"D:\Agente-cad-PYSIDE\project_data.vision"),
                         "Banco de dados real não encontrado")
    def test_derive_rules_real_db(self):
        """Testa derivação de regras no banco real."""
        engine = TransformationEngine(self.real_db_path)
        try:
            engine.load_training_events()
            rules = engine.derive_rules()

            # Deve derivar pelo menos 10 regras
            self.assertGreater(len(rules), 10)

            # Verificar regras para campos mais frequentes
            self.assertIn("Laje_name", rules)
            self.assertIn("Pilar_name", rules)
            self.assertIn("Laje_laje_outline_segs", rules)
        finally:
            engine.close()

    @unittest.skipUnless(os.path.exists(r"D:\Agente-cad-PYSIDE\project_data.vision"),
                         "Banco de dados real não encontrado")
    def test_apply_rule_real_db(self):
        """Testa aplicação de regras no banco real."""
        engine = TransformationEngine(self.real_db_path)
        try:
            engine.load_training_events()
            engine.derive_rules()

            # Testar aplicação para Laje_name
            result = engine.apply_rule("Laje_name", [1.0, 5.0, 200.0, 150.0])
            self.assertIsNotNone(result)

            # Testar aplicação para Pilar_name
            result = engine.apply_rule("Pilar_name", [4351.0, 0.0, 7.5, 1000.0])
            self.assertIsNotNone(result)
        finally:
            engine.close()

    @unittest.skipUnless(os.path.exists(r"D:\Agente-cad-PYSIDE\project_data.vision"),
                         "Banco de dados real não encontrado")
    def test_rules_persisted_in_db(self):
        """Verifica se regras foram persistidas no banco."""
        conn = sqlite3.connect(self.real_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transformation_rules")
        count = cursor.fetchone()[0]
        conn.close()

        # Deve ter pelo menos 10 regras persistidas
        self.assertGreaterEqual(count, 10)

    @unittest.skipUnless(os.path.exists(r"D:\Agente-cad-PYSIDE\project_data.vision"),
                         "Banco de dados real não encontrado")
    def test_rule_accuracy_high_for_common_fields(self):
        """Verifica accuracy alta para campos comuns."""
        engine = TransformationEngine(self.real_db_path)
        try:
            engine.load_training_events()
            engine.derive_rules()

            # Campos comuns devem ter accuracy >= 70%
            for role in ["Pilar_name", "Pilar_dim", "Viga_viga_segs"]:
                if role in engine.rules:
                    self.assertGreaterEqual(
                        engine.rules[role].accuracy_pct,
                        70.0,
                        f"Accuracy para {role} deve ser >= 70%"
                    )
        finally:
            engine.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
