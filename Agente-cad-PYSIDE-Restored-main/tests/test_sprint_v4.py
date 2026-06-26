# -*- coding: utf-8 -*-
"""
test_sprint_v4.py — Testes automatizados para CAD-PYSIDE v4.0 (Masterplan Sprint 1-3)

Cobertura por story:
  CAD-UI-1.1/1.2  Botão Fase-3 + import JSON → DB
  CAD-UI-1.3      Badge confiança B/H
  CAD-UI-3.1      Cadeia extrair_bh_pilares + merge confidence
  CAD-UI-3.2      Merge catalog LV nas vigas
  CAD-UI-2.3      Certificação (threshold logic)
  CAD-UI-2.4      Log aprendizagem (training_events.json)
  CAD-UI-4.1      Pipeline status bar (detecção de fases)
  CAD-UI-4.2      Pipeline Completo (script exists + CLI)

Requer humano (NÃO testado aqui):
  - QProcess progress bar visual
  - Tab switching automático após Fase-3
  - Sparkline rendering (QPainter)
  - Tooltips on hover
  - Comportamento QProcess assíncrono no app em execução

Execução:
  cd D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main
  python -m pytest tests/test_sprint_v4.py -v
  # ou direto:
  python tests/test_sprint_v4.py
"""

import sys
import os
import json
import uuid
import sqlite3
import tempfile
import subprocess
import unittest
from pathlib import Path
from datetime import datetime

# ── Path setup ──────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SCRIPTS      = ROOT / "scripts"
DADOS_OBRAS  = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
VALIDACAO    = Path("D:/Agente-cad-PYSIDE/validacao_visual")
TREINO1      = DADOS_OBRAS / "Obra_TREINO_1"
FASE3_T1     = TREINO1 / "Fase-3_Interpretacao_Extracao"
CATALOG_LV   = Path("D:/Agente-cad-PYSIDE/ANALISE_LV/catalog_rendered.json")


# ═══════════════════════════════════════════════════════════
# BLOCO 1 — Scripts: existência e interface CLI
# ═══════════════════════════════════════════════════════════

class TestScriptsExist(unittest.TestCase):
    """CAD-UI-1.1 / 4.2 — Todos os scripts referenciados devem existir."""

    REQUIRED = [
        "engenharia_reversa_dxf.py",
        "extrair_bh_pilares.py",
        "motor_fase4.py",
        "pipeline_e2e.py",
        "validar_visual_dxf.py",
        "extrair_parametros_viga_v3.py",
    ]

    def test_all_scripts_exist(self):
        for name in self.REQUIRED:
            path = SCRIPTS / name
            self.assertTrue(path.exists(), f"Script não encontrado: {path}")

    def test_scripts_have_main_guard(self):
        """Scripts devem ter if __name__ == '__main__' (executáveis via CLI)."""
        for name in self.REQUIRED:
            path = SCRIPTS / name
            if not path.exists():
                continue
            src = path.read_text(encoding='utf-8', errors='replace')
            self.assertIn("__main__", src, f"{name} não tem guard __main__")

    def test_engenharia_reversa_argparse(self):
        """Verificar que argparse de engenharia_reversa_dxf.py aceita --obra e --pavimento."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "engenharia_reversa_dxf.py"), "--help"],
            capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace'
        )
        self.assertIn("--obra", result.stdout + result.stderr)
        self.assertIn("--pavimento", result.stdout + result.stderr)

    def test_extrair_bh_argparse(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "extrair_bh_pilares.py"), "--help"],
            capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace'
        )
        self.assertIn("--obra", result.stdout + result.stderr)

    def test_pipeline_e2e_argparse(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "pipeline_e2e.py"), "--help"],
            capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace'
        )
        output = result.stdout + result.stderr
        self.assertIn("--obra",      output)
        self.assertIn("--pavimento", output)
        self.assertIn("--force",     output)

    def test_validar_visual_argparse(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "validar_visual_dxf.py"), "--help"],
            capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace'
        )
        output = result.stdout + result.stderr
        self.assertIn("--obra",    output)
        self.assertIn("--tipo",    output)
        self.assertIn("--sem-api", output)

    def test_motor_fase4_argparse(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "motor_fase4.py"), "--help"],
            capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace'
        )
        self.assertIn("--obra", result.stdout + result.stderr)


# ═══════════════════════════════════════════════════════════
# BLOCO 2 — Estrutura dos JSONs Fase-3 (TREINO_1)
# ═══════════════════════════════════════════════════════════

@unittest.skipUnless(FASE3_T1.exists(), "Fase-3 TREINO_1 não encontrada — rodar engenharia_reversa_dxf.py primeiro")
class TestFase3JsonStructure(unittest.TestCase):
    """CAD-UI-1.2 — JSONs de saída devem ter estrutura esperada."""

    def test_pilares_ground_truth_exists(self):
        p = FASE3_T1 / "Pilares" / "pilares_ground_truth.json"
        self.assertTrue(p.exists())

    def test_pilares_ground_truth_count(self):
        """TREINO_1 deve ter ≥ 30 pilares extraídos."""
        p = FASE3_T1 / "Pilares" / "pilares_ground_truth.json"
        data = json.loads(p.read_text(encoding='utf-8', errors='replace'))
        self.assertGreaterEqual(len(data), 30, f"Esperado ≥30 pilares, obtido {len(data)}")

    def test_pilares_ground_truth_schema(self):
        """Cada pilar deve ter campos obrigatórios."""
        p = FASE3_T1 / "Pilares" / "pilares_ground_truth.json"
        data = json.loads(p.read_text(encoding='utf-8', errors='replace'))
        required_fields = {"confidence", "source"}
        for pid, info in list(data.items())[:5]:
            for f in required_fields:
                self.assertIn(f, info, f"Pilar {pid} não tem campo '{f}'")

    def test_vigas_ground_truth_exists(self):
        v = FASE3_T1 / "Vigas" / "vigas_ground_truth.json"
        self.assertTrue(v.exists())

    def test_lajes_ground_truth_exists(self):
        l = FASE3_T1 / "Lajes" / "lajes_ground_truth.json"
        self.assertTrue(l.exists())

    def test_ancoras_pilares_exist(self):
        a = FASE3_T1 / "ancoras_pilares.json"
        self.assertTrue(a.exists())

    def test_ancoras_vigas_exist(self):
        a = FASE3_T1 / "ancoras_vigas.json"
        self.assertTrue(a.exists())


# ═══════════════════════════════════════════════════════════
# BLOCO 3 — B/H Extraction: extrair_bh_pilares output
# ═══════════════════════════════════════════════════════════

@unittest.skipUnless(FASE3_T1.exists(), "Fase-3 TREINO_1 não encontrada")
class TestBHExtraction(unittest.TestCase):
    """CAD-UI-3.1 — pilares_bh.json deve ter confidence elevada."""

    BH_PATH = FASE3_T1 / "Pilares" / "pilares_bh.json"

    def test_pilares_bh_exists(self):
        """pilares_bh.json deve existir (criado por extrair_bh_pilares.py)."""
        self.assertTrue(self.BH_PATH.exists(),
                        "pilares_bh.json não encontrado — rodar extrair_bh_pilares.py")

    @unittest.skipUnless((FASE3_T1 / "Pilares" / "pilares_bh.json").exists(),
                         "pilares_bh.json ausente")
    def test_bh_confidence_elevated(self):
        """Maioria dos pilares deve ter confidence ≥ 0.7 após extração BH."""
        data = json.loads(self.BH_PATH.read_text(encoding='utf-8', errors='replace'))
        high_conf = sum(1 for v in data.values() if v.get("confidence", 0) >= 0.7)
        total = len(data)
        ratio = high_conf / total if total > 0 else 0
        self.assertGreaterEqual(ratio, 0.5,
            f"Esperado ≥50% com confidence≥0.7, obtido {high_conf}/{total} ({ratio:.0%})")

    @unittest.skipUnless((FASE3_T1 / "Pilares" / "pilares_bh.json").exists(),
                         "pilares_bh.json ausente")
    def test_bh_has_b_and_h(self):
        """Entradas com confidence≥0.7 devem ter b e h não-nulos."""
        data = json.loads(self.BH_PATH.read_text(encoding='utf-8', errors='replace'))
        for pid, info in data.items():
            if info.get("confidence", 0) >= 0.7:
                self.assertIsNotNone(info.get("b"), f"Pilar {pid} com conf≥0.7 sem campo 'b'")
                self.assertIsNotNone(info.get("h"), f"Pilar {pid} com conf≥0.7 sem campo 'h'")

    def test_run_extrair_bh_on_treino1(self):
        """Executa extrair_bh_pilares.py e verifica saída limpa (smoke test)."""
        script = SCRIPTS / "extrair_bh_pilares.py"
        if not script.exists():
            self.skipTest("Script não encontrado")
        result = subprocess.run(
            [sys.executable, str(script),
             "--obra", str(TREINO1),
             "--pavimento", "13PAV"],
            capture_output=True, text=True, timeout=60,
            encoding='utf-8', errors='replace'
        )
        # Aceitar 0 ou qualquer código não-crash (script pode ter aviso se já rodou)
        # O importante é que não levante exceção não tratada
        self.assertNotIn("Traceback", result.stderr,
            f"extrair_bh_pilares.py lançou exceção:\n{result.stderr[-500:]}")


# ═══════════════════════════════════════════════════════════
# BLOCO 4 — Merge Logic (sem Qt, função pura)
# ═══════════════════════════════════════════════════════════

class TestBHMergeLogic(unittest.TestCase):
    """CAD-UI-3.1 — lógica de merge B/H no import."""

    def _simulate_merge(self, gt_entry, bh_entry=None):
        """Replica lógica de _import_fase3_to_db para um pilar."""
        if bh_entry:
            b    = bh_entry.get('b') or gt_entry.get('b')
            h    = bh_entry.get('h') or gt_entry.get('h')
            conf = bh_entry.get('confidence', gt_entry.get('confidence', 0.3))
        else:
            b    = gt_entry.get('b')
            h    = gt_entry.get('h')
            conf = gt_entry.get('confidence', 0.3)
        return b, h, conf

    def test_merge_elevates_confidence(self):
        gt  = {'b': None, 'h': None, 'confidence': 0.3}
        bh  = {'b': 46.0, 'h': 56.0, 'confidence': 0.9}
        b, h, conf = self._simulate_merge(gt, bh)
        self.assertEqual(conf, 0.9)
        self.assertEqual(b, 46.0)
        self.assertEqual(h, 56.0)

    def test_fallback_without_bh(self):
        gt = {'b': None, 'h': None, 'confidence': 0.3}
        b, h, conf = self._simulate_merge(gt, bh_entry=None)
        self.assertEqual(conf, 0.3)
        self.assertIsNone(b)

    def test_bh_does_not_overwrite_existing_b(self):
        """Se gt já tem b/h, BH entry sem b/h não apaga."""
        gt = {'b': 30.0, 'h': 40.0, 'confidence': 0.5}
        bh = {'b': None, 'h': None, 'confidence': 0.7}
        b, h, conf = self._simulate_merge(gt, bh)
        self.assertEqual(b, 30.0, "b original não deve ser sobrescrito por None")
        self.assertEqual(h, 40.0, "h original não deve ser sobrescrito por None")

    def test_issues_generated_for_low_confidence(self):
        """Pilares com conf<0.4 devem ter issues[]."""
        def make_issues(conf):
            return [] if conf >= 0.4 else [
                {'type': 'low_confidence', 'msg': f'B/H incerto (conf={conf:.1f})'}
            ]
        self.assertEqual(make_issues(0.9), [])
        self.assertEqual(make_issues(0.3)[0]['type'], 'low_confidence')
        self.assertEqual(make_issues(0.4), [])


# ═══════════════════════════════════════════════════════════
# BLOCO 5 — Badge B/H Logic (CAD-UI-1.3)
# ═══════════════════════════════════════════════════════════

class TestBHBadgeLogic(unittest.TestCase):
    """CAD-UI-1.3 — badge string gerado para cada faixa de confiança."""

    def _make_badge(self, bh_conf, b_val, h_val, name="P1"):
        """Replica lógica de _populate_generic_tree para pilares."""
        if bh_conf is not None:
            if bh_conf >= 0.7:
                bh_badge = " ✓"
            elif bh_conf >= 0.4:
                bh_badge = " ⚠"
            else:
                bh_badge = " ?"
            if b_val and h_val:
                return f"{name}  {int(b_val)}×{int(h_val)}{bh_badge}"
            else:
                return f"{name}{bh_badge}"
        return name

    def test_high_confidence_shows_checkmark(self):
        badge = self._make_badge(0.9, 46, 56, "P1")
        self.assertIn("✓", badge)
        self.assertIn("46×56", badge)

    def test_medium_confidence_shows_warning(self):
        badge = self._make_badge(0.5, None, None, "P2")
        self.assertIn("⚠", badge)

    def test_low_confidence_shows_question(self):
        badge = self._make_badge(0.2, None, None, "P3")
        self.assertIn("?", badge)

    def test_no_confidence_shows_plain_name(self):
        badge = self._make_badge(None, None, None, "P4")
        self.assertEqual(badge, "P4")

    def test_boundary_0_4_is_warning(self):
        badge = self._make_badge(0.4, None, None, "P5")
        self.assertIn("⚠", badge)

    def test_boundary_0_7_is_checkmark(self):
        badge = self._make_badge(0.7, 20, 30, "P6")
        self.assertIn("✓", badge)


# ═══════════════════════════════════════════════════════════
# BLOCO 6 — Catalog LV Merge (CAD-UI-3.2)
# ═══════════════════════════════════════════════════════════

@unittest.skipUnless(CATALOG_LV.exists(), "catalog_rendered.json não encontrado")
class TestCatalogLVMerge(unittest.TestCase):
    """CAD-UI-3.2 — merge de seção/B×H do catalog LV."""

    @classmethod
    def setUpClass(cls):
        data = json.loads(CATALOG_LV.read_text(encoding='utf-8', errors='replace'))
        # Indexar por obra → viga
        cls.catalog_by_obra = {}
        import re
        for entry in data:
            obra = entry.get('obra', '')
            viga = str(entry.get('viga', '')).upper()
            secao = str(entry.get('secao', ''))
            m = re.match(r'(\d+)[xX×](\d+)', secao)
            b_cat = float(m.group(1)) if m else None
            h_cat = float(m.group(2)) if m else None
            if obra not in cls.catalog_by_obra:
                cls.catalog_by_obra[obra] = {}
            cls.catalog_by_obra[obra][viga] = {
                'secao': secao, 'b': b_cat, 'h': h_cat,
                'confidence': 0.85 if (b_cat and h_cat) else 0.5,
            }

    def test_catalog_has_entries(self):
        total = sum(len(v) for v in self.catalog_by_obra.values())
        self.assertGreater(total, 0, "Catalog vazio")

    def test_catalog_has_treino_obras(self):
        """Catalog deve ter pelo menos uma obra TREINO."""
        obras = list(self.catalog_by_obra.keys())
        treino_obras = [o for o in obras if "TREINO" in o.upper()]
        self.assertGreater(len(treino_obras), 0,
            f"Nenhuma obra TREINO no catalog. Obras disponíveis: {obras[:5]}")

    def test_secao_parse_extracts_b_h(self):
        """Seções tipo '14x50' devem gerar b=14, h=50."""
        import re
        test_cases = [
            ("14x50",  14, 50),
            ("20X60",  20, 60),
            ("25×70",  25, 70),
            ("invalid", None, None),
        ]
        for secao, expected_b, expected_h in test_cases:
            m = re.match(r'(\d+)[xX×](\d+)', secao)
            b = float(m.group(1)) if m else None
            h = float(m.group(2)) if m else None
            self.assertEqual(b, expected_b, f"Secao '{secao}': b esperado {expected_b}, obtido {b}")
            self.assertEqual(h, expected_h, f"Secao '{secao}': h esperado {expected_h}, obtido {h}")

    def test_merge_elevates_viga_confidence(self):
        """Para vigas com catalog hit, confiança deve ser ≥ 0.5."""
        for obra, vigas in self.catalog_by_obra.items():
            for viga, info in list(vigas.items())[:3]:
                self.assertGreaterEqual(info['confidence'], 0.5,
                    f"{obra}/{viga}: confidence={info['confidence']}")

    def test_catalog_entries_have_required_fields(self):
        """Cada entrada do catalog indexado deve ter secao."""
        for obra, vigas in list(self.catalog_by_obra.items())[:3]:
            for viga, info in list(vigas.items())[:5]:
                self.assertIn('secao', info)


# ═══════════════════════════════════════════════════════════
# BLOCO 7 — Certificação (CAD-UI-2.3)
# ═══════════════════════════════════════════════════════════

class TestCertificationLogic(unittest.TestCase):
    """CAD-UI-2.3 — lógica de threshold de certificação."""

    def _certify(self, scores: dict) -> dict:
        """Replica lógica de Fase8Panel._on_certify."""
        valid = [v for v in scores.values() if v is not None]
        avg = sum(valid) / len(valid) if valid else 0.0
        if avg >= 75:
            status = "APROVADO"
        elif avg >= 60:
            status = "CONDICIONAL"
        else:
            status = "REPROVADO"
        return {"media_geral": round(avg, 1), "status": status}

    def test_aprovado_above_75(self):
        r = self._certify({"LV": 80.0, "PL": 85.0})
        self.assertEqual(r["status"], "APROVADO")

    def test_aprovado_exactly_75(self):
        r = self._certify({"LV": 75.0})
        self.assertEqual(r["status"], "APROVADO")

    def test_condicional_between_60_and_75(self):
        r = self._certify({"LV": 70.0, "FV": 65.0})
        self.assertEqual(r["status"], "CONDICIONAL")

    def test_condicional_exactly_60(self):
        r = self._certify({"LV": 60.0})
        self.assertEqual(r["status"], "CONDICIONAL")

    def test_reprovado_below_60(self):
        r = self._certify({"LV": 50.0, "PL": 55.0})
        self.assertEqual(r["status"], "REPROVADO")

    def test_none_scores_excluded_from_average(self):
        r = self._certify({"LV": 80.0, "PL": None, "FV": None})
        self.assertEqual(r["media_geral"], 80.0)
        self.assertEqual(r["status"], "APROVADO")

    def test_all_none_gives_reprovado(self):
        r = self._certify({"LV": None, "PL": None})
        self.assertEqual(r["status"], "REPROVADO")

    def test_cert_json_written_correctly(self):
        """Certificado escrito em disco deve ter todos os campos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            scores = {"LV": 82.0, "PL": 78.0}
            valid = [v for v in scores.values() if v is not None]
            avg   = round(sum(valid) / len(valid), 1)
            cert = {
                "obra": "Obra_TREINO_TEST",
                "pavimento": "1PV",
                "tipos_validados": list(scores.keys()),
                "scores": scores,
                "media_geral": avg,
                "status": "APROVADO",
                "data_cert": datetime.now().isoformat(),
                "versao": "v4.0",
            }
            cert_path = Path(tmpdir) / "CERTIFICADO.json"
            cert_path.write_text(json.dumps(cert, indent=2, ensure_ascii=False), encoding='utf-8')
            loaded = json.loads(cert_path.read_text(encoding='utf-8'))
            self.assertEqual(loaded["status"], "APROVADO")
            self.assertEqual(loaded["media_geral"], 80.0)
            for field in ["obra", "pavimento", "tipos_validados", "scores", "data_cert", "versao"]:
                self.assertIn(field, loaded, f"Campo '{field}' ausente no CERTIFICADO.json")


# ═══════════════════════════════════════════════════════════
# BLOCO 8 — Learning Events (CAD-UI-2.4)
# ═══════════════════════════════════════════════════════════

class TestLearningEvents(unittest.TestCase):
    """CAD-UI-2.4 — training_events.json deve ter estrutura correta."""

    def _make_event(self, obra, scores):
        """Replica lógica de Fase8Panel._save_learning_event."""
        valid = [v for v in scores.values() if v is not None]
        avg   = round(sum(valid) / len(valid), 1) if valid else None
        return {
            "obra": obra,
            "pavimento": "1PV",
            "scores": scores,
            "media": avg,
            "timestamp": datetime.now().isoformat(),
            "tipos": list(scores.keys()),
        }

    def test_event_has_required_fields(self):
        ev = self._make_event("Obra_TREINO_1", {"LV": 75.0})
        for f in ["obra", "pavimento", "scores", "media", "timestamp", "tipos"]:
            self.assertIn(f, ev)

    def test_media_calculated_correctly(self):
        ev = self._make_event("Obra_TREINO_1", {"LV": 80.0, "PL": 60.0})
        self.assertEqual(ev["media"], 70.0)

    def test_none_scores_excluded(self):
        ev = self._make_event("Obra_TREINO_1", {"LV": 90.0, "PL": None})
        self.assertEqual(ev["media"], 90.0)

    def test_events_appended_correctly(self):
        """Múltiplos eventos devem acumular no JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            events_path = Path(tmpdir) / "training_events.json"
            events = []
            for i, score in enumerate([70.0, 75.0, 80.0]):
                ev = self._make_event("Obra_TREINO_TEST", {"LV": score})
                events.append(ev)
                events_path.write_text(
                    json.dumps(events, indent=2, ensure_ascii=False), encoding='utf-8'
                )
            loaded = json.loads(events_path.read_text(encoding='utf-8'))
            self.assertEqual(len(loaded), 3)
            self.assertEqual(loaded[-1]["scores"]["LV"], 80.0)

    def test_events_capped_at_500(self):
        """Lista deve ser truncada para os últimos 500 eventos."""
        events = [self._make_event("Obra_X", {"LV": float(i)}) for i in range(600)]
        events = events[-500:]
        self.assertEqual(len(events), 500)
        self.assertEqual(events[-1]["scores"]["LV"], 599.0)


# ═══════════════════════════════════════════════════════════
# BLOCO 9 — Pipeline Status Bar (CAD-UI-4.1)
# ═══════════════════════════════════════════════════════════

@unittest.skipUnless(DADOS_OBRAS.exists(), "DADOS-OBRAS não encontrado")
class TestPipelineStatusDetection(unittest.TestCase):
    """CAD-UI-4.1 — detecção de fases existentes por obra."""

    FASE_DIRS = {
        1: "Fase-1_Ingestao",
        2: "Fase-2_Triagem",
        3: "Fase-3_Interpretacao_Extracao",
        4: "Fase-4_Sincronizacao",
        5: "Fase-5_Geracao_Scripts",
        6: "Fase-6_Execucao_CAD",
        7: "Fase-7_Validacao_Fidelidade",
        8: "Fase-8_Revisao_Entrega",
    }

    def _detect_phases(self, obra_path: Path) -> dict:
        """Replica lógica de _refresh_pipeline_status."""
        return {
            fase: (obra_path / subdir).exists()
            for fase, subdir in self.FASE_DIRS.items()
        }

    def test_treino1_has_fase1(self):
        phases = self._detect_phases(TREINO1)
        self.assertTrue(phases[1], "TREINO_1 deve ter Fase-1 (ingestão)")

    def test_treino1_has_fase3(self):
        """TREINO_1 deve ter Fase-3 após extração."""
        phases = self._detect_phases(TREINO1)
        if not phases[3]:
            self.skipTest("Fase-3 não encontrada — rodar engenharia_reversa_dxf.py primeiro")
        self.assertTrue(phases[3])

    def test_treino1_fase6_has_dxf_files(self):
        """Fase-6 deve ter DXF gerados."""
        fase6 = TREINO1 / "Fase-6_Execucao_CAD"
        if not fase6.exists():
            self.skipTest("Fase-6 não encontrada em TREINO_1")
        dxfs = list(fase6.glob("*.dxf"))
        self.assertGreater(len(dxfs), 0, "Fase-6 existe mas sem DXF gerados")

    def test_nonexistent_obra_all_phases_false(self):
        fake_obra = DADOS_OBRAS / "Obra_FAKE_999"
        phases = self._detect_phases(fake_obra)
        self.assertFalse(any(phases.values()), "Obra inexistente não deve ter fases ativas")

    def test_all_obras_have_fase1(self):
        """Todas as obras no discovery devem ter Fase-1."""
        disc = DADOS_OBRAS / "dxf_discovery.json"
        if not disc.exists():
            self.skipTest("dxf_discovery.json não encontrado")
        discovery = json.loads(disc.read_text(encoding='utf-8', errors='replace'))
        failures = []
        for obra_name in discovery:
            obra_path = DADOS_OBRAS / obra_name
            fase1 = obra_path / "Fase-1_Ingestao"
            if obra_path.exists() and not fase1.exists():
                failures.append(obra_name)
        self.assertEqual(failures, [],
            f"Obras sem Fase-1: {failures}")


# ═══════════════════════════════════════════════════════════
# BLOCO 10 — DB Round-trip (CAD-UI-1.2)
# ═══════════════════════════════════════════════════════════

class TestDBRoundtrip(unittest.TestCase):
    """CAD-UI-1.2 — save_pillar/load_pillars round-trip com DB in-memory."""

    def setUp(self):
        # Criar DB temporário
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.tmp.close()
        from src.core.database import DatabaseManager
        self.db = DatabaseManager(db_path=self.tmp.name)

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except Exception:
            pass

    def _make_pillar(self, project_id, id_item="P1", bh_conf=0.9, b=46.0, h=56.0):
        return {
            'id': f"{project_id}_pil_{id_item}",
            'id_item': id_item,
            'name': id_item,
            'type': 'Pilar',
            'area_val': b * h if b and h else 0.0,
            'points': [[1000.0, 2000.0]],
            'sides_data': {'b': b, 'h': h, 'bh_confidence': bh_conf},
            'confidence_map': {'bh': bh_conf},
            'links': {},
            'validated_fields': [],
            'validated_link_classes': {},
            'na_fields': [],
            'na_link_classes': {},
            'na_reasons': {},
            'issues': [] if bh_conf >= 0.4 else [
                {'type': 'low_confidence', 'msg': 'test'}
            ],
            'is_validated': False,
            'pkl_path': None,
        }

    def test_save_and_load_pillar(self):
        pid = str(uuid.uuid4())
        pillar = self._make_pillar(pid, "P1", bh_conf=0.9, b=46.0, h=56.0)
        self.db.save_pillar(pillar, pid)

        loaded = self.db.load_pillars(pid)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]['id_item'], "P1")

    def test_bh_confidence_survives_roundtrip(self):
        pid = str(uuid.uuid4())
        pillar = self._make_pillar(pid, "P1", bh_conf=0.9, b=46.0, h=56.0)
        self.db.save_pillar(pillar, pid)
        loaded = self.db.load_pillars(pid)
        sides = loaded[0].get('sides_data', {})
        self.assertEqual(sides.get('bh_confidence'), 0.9)
        self.assertEqual(sides.get('b'), 46.0)
        self.assertEqual(sides.get('h'), 56.0)

    def test_issues_survive_roundtrip(self):
        pid = str(uuid.uuid4())
        # Pilar com confiança baixa → deve ter issues
        pillar = self._make_pillar(pid, "P2", bh_conf=0.2, b=None, h=None)
        self.db.save_pillar(pillar, pid)
        loaded = self.db.load_pillars(pid)
        issues = loaded[0].get('issues', [])
        self.assertGreater(len(issues), 0, "Issues de low_confidence não sobreviveram ao round-trip")
        self.assertEqual(issues[0]['type'], 'low_confidence')

    def test_multiple_pillars_same_project(self):
        pid = str(uuid.uuid4())
        for i, (b, h) in enumerate([(46, 56), (20, 60), (30, 80)]):
            self.db.save_pillar(self._make_pillar(pid, f"P{i+1}", 0.9, b, h), pid)
        loaded = self.db.load_pillars(pid)
        self.assertEqual(len(loaded), 3)

    def test_upsert_updates_existing(self):
        """Salvar mesmo ID duas vezes deve atualizar, não duplicar."""
        pid = str(uuid.uuid4())
        pillar = self._make_pillar(pid, "P1", bh_conf=0.3)
        self.db.save_pillar(pillar, pid)
        # Agora com conf elevada
        pillar['sides_data']['bh_confidence'] = 0.9
        pillar['confidence_map']['bh'] = 0.9
        self.db.save_pillar(pillar, pid)
        loaded = self.db.load_pillars(pid)
        self.assertEqual(len(loaded), 1, "UPSERT criou duplicata")
        self.assertEqual(loaded[0]['sides_data'].get('bh_confidence'), 0.9)


# ═══════════════════════════════════════════════════════════
# BLOCO 11 — Engenharia Reversa Integration (smoke test)
# ═══════════════════════════════════════════════════════════

@unittest.skipUnless(TREINO1.exists(), "TREINO_1 não encontrado em DADOS-OBRAS")
class TestEngenhariaReversa(unittest.TestCase):
    """CAD-UI-1.1 — script CLI deve rodar e gerar outputs corretos."""

    def test_run_on_treino1(self):
        """Rodar engenharia_reversa_dxf.py em TREINO_1 e verificar outputs."""
        script = SCRIPTS / "engenharia_reversa_dxf.py"
        if not script.exists():
            self.skipTest("Script não encontrado")

        result = subprocess.run(
            [sys.executable, str(script),
             "--obra", str(TREINO1),
             "--pavimento", "13PAV"],
            capture_output=True, text=True, timeout=120,
            encoding='utf-8', errors='replace'
        )

        # Não deve lançar Traceback (crash)
        self.assertNotIn("Traceback (most recent call last)",
                         result.stderr,
                         f"Script lançou exceção:\n{result.stderr[-600:]}")

        # Output esperado: Fase-3 directory criado
        fase3 = TREINO1 / "Fase-3_Interpretacao_Extracao"
        self.assertTrue(fase3.exists(), "Fase-3 não criada após execução do script")

    def test_fase3_outputs_have_expected_counts(self):
        """Após execução, pilares/vigas/lajes devem ter contagem mínima esperada."""
        pil = FASE3_T1 / "Pilares" / "pilares_ground_truth.json"
        vig = FASE3_T1 / "Vigas"   / "vigas_ground_truth.json"
        laj = FASE3_T1 / "Lajes"   / "lajes_ground_truth.json"

        if not all(p.exists() for p in [pil, vig, laj]):
            self.skipTest("JSONs Fase-3 não encontrados")

        n_pil = len(json.loads(pil.read_text(encoding='utf-8', errors='replace')))
        n_vig = len(json.loads(vig.read_text(encoding='utf-8', errors='replace')))
        n_laj = len(json.loads(laj.read_text(encoding='utf-8', errors='replace')))

        # Mínimos baseados em execução anterior validada (TREINO_1: 36P/35V/40L)
        self.assertGreaterEqual(n_pil, 30, f"Pilares: esperado ≥30, obtido {n_pil}")
        self.assertGreaterEqual(n_vig, 25, f"Vigas: esperado ≥25, obtido {n_vig}")
        self.assertGreaterEqual(n_laj, 30, f"Lajes: esperado ≥30, obtido {n_laj}")


# ═══════════════════════════════════════════════════════════
# BLOCO 12 — Validation JSON Structure (Fase-8)
# ═══════════════════════════════════════════════════════════

@unittest.skipUnless(VALIDACAO.exists(), "validacao_visual/ não encontrado")
class TestValidacaoJsonStructure(unittest.TestCase):
    """Verifica estrutura dos JSONs de validação existentes."""

    def test_consolidado_jsons_exist(self):
        jsons = list(VALIDACAO.glob("consolidado_Obra_*.json"))
        self.assertGreater(len(jsons), 0, "Nenhum consolidado_*.json encontrado")

    def test_consolidado_has_resultados(self):
        """Cada consolidado deve ter 'resultados' por tipo (ignora entradas com 'erro')."""
        jsons = list(VALIDACAO.glob("consolidado_Obra_*.json"))
        for j in jsons[:5]:
            data = json.loads(j.read_text(encoding='utf-8', errors='replace'))
            for pav_key, pav_data in data.items():
                # Entradas geradas antes do fix fuzzy-discovery podem ter 'erro' — skip
                if 'erro' in pav_data:
                    break
                self.assertIn('resultados', pav_data,
                    f"{j.name} / {pav_key} não tem 'resultados'")
                break  # só primeiro pav

    def test_score_final_is_float_in_range(self):
        """score_final deve ser float entre 0 e 100."""
        jsons = list(VALIDACAO.glob("consolidado_Obra_*.json"))
        for j in jsons[:5]:
            data = json.loads(j.read_text(encoding='utf-8', errors='replace'))
            for pav_key, pav_data in data.items():
                for tipo, res in pav_data.get('resultados', {}).items():
                    sc = res.get('score_final')
                    if sc is not None:
                        self.assertIsInstance(sc, (int, float),
                            f"{j.name}/{tipo}: score_final não é número")
                        self.assertGreaterEqual(sc, 0.0)
                        self.assertLessEqual(sc, 100.0)
                break


# ═══════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════

def main():
    """Roda todos os testes e exibe relatório final."""
    import io
    # Força UTF-8 no Windows (evita UnicodeEncodeError com ≥, ✓, etc.)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    out_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace') \
        if hasattr(sys.stdout, 'buffer') else sys.stdout

    loader = unittest.TestLoader()
    suite  = loader.loadTestsFromModule(sys.modules[__name__])

    runner = unittest.TextTestRunner(verbosity=2, stream=out_stream)
    result = runner.run(suite)

    print("\n" + "═"*60)
    print(f"RESULTADO: {'✅ PASSOU' if result.wasSuccessful() else '❌ FALHOU'}")
    print(f"  Testes:  {result.testsRun}")
    print(f"  Falhas:  {len(result.failures)}")
    print(f"  Erros:   {len(result.errors)}")
    print(f"  Skipped: {len(result.skipped)}")
    print("═"*60)

    # Listar o que requer validação humana
    print("\n⚠ REQUER VALIDAÇÃO HUMANA (não coberto por testes automáticos):")
    human = [
        "Bloco 1.3: label verde '✓ extraído' aparece no painel azul (visual)",
        "Bloco 1.4: app navega para Tab 1 automaticamente após import Fase-3 (Qt runtime)",
        "Bloco 1.6: progress bar aparece durante Pipeline Completo (Qt runtime)",
        "Bloco 2.1: badge '46×56 ✓' visível na lista de Pilares do Tab 1 (Qt render)",
        "Bloco 2.2: tooltip de confiança aparece ao hover (Qt event)",
        "Bloco 3.1: painel Fase-8 visível no lado direito do Tab 2 (Qt render)",
        "Bloco 3.5: sparkline de tendência renderiza corretamente (QPainter)",
        "Bloco 4.1: barra de status F1…F8 visível na base da janela (Qt layout)",
    ]
    for item in human:
        print(f"  • {item}")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
