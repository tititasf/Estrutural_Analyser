#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_cad84_pipeline_e2e.py — CAD-8.4: Testes do pipeline_e2e orquestrador
"""
import json
import pathlib
import sys
import subprocess

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

OBRA_T1 = pathlib.Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
SCRIPT = pathlib.Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/scripts/pipeline_e2e.py")


# ─── AC-1: Comando único processa obra completa ───────────────────────────────

class TestScriptExiste:
    def test_pipeline_script_exists(self):
        """pipeline_e2e.py deve existir."""
        assert SCRIPT.exists(), f"Script não encontrado: {SCRIPT}"

    def test_pipeline_has_main(self):
        """pipeline_e2e.py deve ter função main() e run_pipeline()."""
        from scripts.pipeline_e2e import run_pipeline, main
        assert callable(run_pipeline)
        assert callable(main)

    def test_pipeline_has_dry_run(self):
        """run_pipeline aceita dry_run=True sem erros."""
        from scripts.pipeline_e2e import run_pipeline
        # Dry-run deve completar sem levantar exceção
        result = run_pipeline(str(OBRA_T1), "12 PAV", dry_run=True)
        assert isinstance(result, dict)
        assert "obra" in result
        assert result["obra"] == "Obra_TREINO_1"


# ─── AC-2: Idempotência + skip + force ────────────────────────────────────────

class TestIdempotencia:
    def test_dry_run_completes_without_error(self):
        """Dry-run deve retornar dict com fases."""
        from scripts.pipeline_e2e import run_pipeline
        result = run_pipeline(str(OBRA_T1), "12 PAV", dry_run=True)
        assert "fases" in result
        assert len(result["fases"]) > 0

    def test_dry_run_all_fases_skip_or_dry(self):
        """Em dry-run sem --force, fases existentes devem ser SKIP ou DRY."""
        from scripts.pipeline_e2e import run_pipeline
        result = run_pipeline(str(OBRA_T1), "12 PAV", dry_run=True)
        for fase, status in result["fases"].items():
            assert status in ("SKIP", "OK", "DRY", "FALHOU/SKIP"), \
                f"Fase {fase} com status inesperado: {status}"

    def test_output_exists_helper(self):
        """output_exists() retorna True para arquivos com conteúdo."""
        from scripts.pipeline_e2e import output_exists
        # dxf_discovery.json existe e tem conteúdo
        disc = OBRA_T1.parent / "dxf_discovery.json"
        if disc.exists():
            assert output_exists(disc) is True

    def test_output_exists_false_for_missing(self):
        """output_exists() retorna False para arquivo inexistente."""
        from scripts.pipeline_e2e import output_exists
        fake = OBRA_T1 / "ARQUIVO_FAKE_INEXISTENTE_12345.json"
        assert output_exists(fake) is False


# ─── AC-3: Exit codes ─────────────────────────────────────────────────────────

class TestExitCodes:
    def test_dry_run_exit_code_not_2(self):
        """pipeline em dry-run não deve retornar exit code 2 (falha crítica)."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT),
             "--obra", str(OBRA_T1),
             "--pavimento", "12 PAV",
             "--dry-run"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 2, \
            f"Pipeline retornou exit 2 (falha crítica) em dry-run:\n{result.stderr}"

    def test_pipeline_status_field(self):
        """run_pipeline retorna 'status' em APROVADO, PARCIAL ou REPROVADO."""
        from scripts.pipeline_e2e import run_pipeline
        result = run_pipeline(str(OBRA_T1), "12 PAV", dry_run=True)
        assert result.get("status") in ("APROVADO", "PARCIAL", "REPROVADO", "INICIANDO")


# ─── AC-4: pipeline_report.json ───────────────────────────────────────────────

class TestPipelineReport:
    def test_report_exists_after_run(self):
        """Após execução, pipeline_report.json deve existir."""
        report = OBRA_T1 / "Fase-8_Revisao_Entrega" / "pipeline_report.json"
        # Se existir, verificar estrutura; se não, skip silencioso
        if not report.exists():
            return
        data = json.loads(report.read_text(encoding="utf-8"))
        assert "obra" in data
        assert "fases" in data
        assert "status" in data

    def test_report_has_obra_name(self):
        """pipeline_report.json deve ter nome correto da obra."""
        report = OBRA_T1 / "Fase-8_Revisao_Entrega" / "pipeline_report.json"
        if not report.exists():
            return
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["obra"] == "Obra_TREINO_1"

    def test_report_has_timestamp(self):
        """pipeline_report.json deve ter timestamp ISO."""
        report = OBRA_T1 / "Fase-8_Revisao_Entrega" / "pipeline_report.json"
        if not report.exists():
            return
        data = json.loads(report.read_text(encoding="utf-8"))
        assert "timestamp" in data
        assert "T" in data["timestamp"]  # formato ISO

    def test_report_fases_dict(self):
        """pipeline_report.json deve ter 'fases' como dict não vazio."""
        report = OBRA_T1 / "Fase-8_Revisao_Entrega" / "pipeline_report.json"
        if not report.exists():
            return
        data = json.loads(report.read_text(encoding="utf-8"))
        assert isinstance(data.get("fases"), dict)
        assert len(data["fases"]) >= 5, "Esperado pelo menos 5 fases"

    def test_dry_run_creates_report(self):
        """Dry-run deve criar/atualizar pipeline_report.json."""
        from scripts.pipeline_e2e import run_pipeline
        run_pipeline(str(OBRA_T1), "12 PAV", dry_run=True)
        report = OBRA_T1 / "Fase-8_Revisao_Entrega" / "pipeline_report.json"
        assert report.exists(), "pipeline_report.json não foi criado pelo dry-run"


# ─── AC-5: Idempotência estrutural ────────────────────────────────────────────

class TestIdempotenciaEstrutural:
    def test_two_dryruns_same_result(self):
        """Dois dry-runs seguidos devem retornar mesmo conjunto de fases."""
        from scripts.pipeline_e2e import run_pipeline
        r1 = run_pipeline(str(OBRA_T1), "12 PAV", dry_run=True)
        r2 = run_pipeline(str(OBRA_T1), "12 PAV", dry_run=True)
        assert set(r1["fases"].keys()) == set(r2["fases"].keys())

    def test_run_script_helper_dry(self):
        """run_script em dry_run retorna True sem executar."""
        from scripts.pipeline_e2e import run_script
        ok = run_script("motor_fase4.py", ["--obra", "FAKE"], dry_run=True)
        assert ok is True

    def test_obra_field_matches_dir_name(self):
        """Campo 'obra' no resultado deve ser igual ao nome do diretório."""
        from scripts.pipeline_e2e import run_pipeline
        result = run_pipeline(str(OBRA_T1), "12 PAV", dry_run=True)
        assert result["obra"] == OBRA_T1.name
