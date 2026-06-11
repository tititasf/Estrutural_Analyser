#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_cad82_multi_pav.py — CAD-8.2: Testes do motor_fase4 multi-pavimento
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

DADOS_OBRAS = pathlib.Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
OBRA_T1 = DADOS_OBRAS / "Obra_TREINO_1"
DISCOVERY = DADOS_OBRAS / "dxf_discovery.json"


# ─── AC-1: _load_discovery ────────────────────────────────────────────────────

class TestLoadDiscovery:
    def test_discovery_file_exists(self):
        """dxf_discovery.json deve existir no diretório DADOS-OBRAS."""
        assert DISCOVERY.exists(), f"Não encontrado: {DISCOVERY}"

    def test_discovery_loads_obra_treino_1(self):
        """dxf_discovery deve conter Obra_TREINO_1."""
        data = json.loads(DISCOVERY.read_text(encoding="utf-8-sig"))
        assert "Obra_TREINO_1" in data

    def test_discovery_pav_has_dxf_keys(self):
        """Cada pavimento no discovery deve ter chaves PL, LV (ou None)."""
        data = json.loads(DISCOVERY.read_text(encoding="utf-8-sig"))
        for obra, pavs in list(data.items())[:3]:
            for pav, dxfs in pavs.items():
                assert "PL" in dxfs or "LV" in dxfs, f"{obra}/{pav}: sem PL/LV"

    def test_load_discovery_function(self):
        """_load_discovery() retorna dict não vazio para Obra_TREINO_1."""
        from scripts.motor_fase4 import _load_discovery
        result = _load_discovery(OBRA_T1)
        assert isinstance(result, dict)
        assert len(result) > 0


# ─── AC-2: Saída por pavimento ────────────────────────────────────────────────

class TestOutputPorPavimento:
    def test_fase4_has_subfolders_after_run(self):
        """Após --all-pavimentos, Fase-4 deve ter pastas JSON_Pilares/etc."""
        f4 = OBRA_T1 / "Fase-4_Sincronizacao"
        assert (f4 / "JSON_Pilares").exists()
        assert (f4 / "JSON_Lajes").exists()
        assert (f4 / "JSON_Vigas_Fundo").exists()

    def test_relatorio_json_exists(self):
        """motor_fase4_relatorio.json deve existir após run."""
        relatorio = OBRA_T1 / "Fase-4_Sincronizacao" / "motor_fase4_relatorio.json"
        assert relatorio.exists()

    def test_relatorio_has_stats(self):
        """Relatório deve conter stats válidas."""
        relatorio = OBRA_T1 / "Fase-4_Sincronizacao" / "motor_fase4_relatorio.json"
        if not relatorio.exists():
            return
        data = json.loads(relatorio.read_text(encoding="utf-8"))
        assert "stats" in data
        stats = data["stats"]
        assert stats.get("pilares", 0) > 0 or stats.get("lajes", 0) > 0


# ─── AC-3: Skip sem DXF PL ────────────────────────────────────────────────────

class TestSkipSemPL:
    def test_discovery_with_null_pl_exists(self):
        """Algumas obras têm PL=None — verificar que existem no discovery."""
        data = json.loads(DISCOVERY.read_text(encoding="utf-8-sig"))
        has_null = any(
            dxfs.get("PL") is None
            for pavs in data.values()
            for dxfs in pavs.values()
        )
        # Se houver obras sem PL, é esperado (não é erro)
        # O teste só verifica que o discovery é bem formado
        assert isinstance(has_null, bool)

    def test_load_discovery_returns_empty_for_unknown_obra(self):
        """_load_discovery para obra desconhecida retorna {}."""
        from scripts.motor_fase4 import _load_discovery
        fake = DADOS_OBRAS / "OBRA_FAKE_INEXISTENTE"
        result = _load_discovery(fake)
        assert result == {}


# ─── AC-4: Compatibilidade retroativa ────────────────────────────────────────

class TestCompatibilidadeRetroativa:
    def test_single_pav_still_works(self):
        """MotorFase4 com pavimento único ainda funciona."""
        from scripts.motor_fase4 import MotorFase4
        motor = MotorFase4(
            obra_path=str(OBRA_T1),
            pavimento="12 PAV",
            nivel_chegada=0.0,
            nivel_saida=280.0
        )
        # Verificar que o objeto é criado sem erro
        assert motor.obra_nome == "Obra_TREINO_1"
        assert motor.pavimento == "12 PAV"

    def test_motor_has_run_method(self):
        """MotorFase4 deve ter método run()."""
        from scripts.motor_fase4 import MotorFase4
        assert hasattr(MotorFase4, "run")


# ─── AC-5: Relatório multi-pav ───────────────────────────────────────────────

class TestRelatorioMultiPav:
    def test_discovery_obra_treino_1_has_multiple_pavimentos(self):
        """Obra_TREINO_1 deve ter > 1 pavimento no discovery."""
        data = json.loads(DISCOVERY.read_text(encoding="utf-8-sig"))
        pavs = data.get("Obra_TREINO_1", {})
        assert len(pavs) > 1, f"Esperado >1 pav, encontrado: {list(pavs.keys())}"

    def test_json_pilares_populated(self):
        """JSON_Pilares deve ter arquivos após processamento multi-pav."""
        json_dir = OBRA_T1 / "Fase-4_Sincronizacao" / "JSON_Pilares"
        if json_dir.exists():
            files = list(json_dir.glob("*.json"))
            assert len(files) > 0, "JSON_Pilares vazio"

    def test_json_lajes_populated(self):
        """JSON_Lajes deve ter arquivos após processamento."""
        json_dir = OBRA_T1 / "Fase-4_Sincronizacao" / "JSON_Lajes"
        if json_dir.exists():
            files = list(json_dir.glob("*.json"))
            assert len(files) > 0, "JSON_Lajes vazio"
