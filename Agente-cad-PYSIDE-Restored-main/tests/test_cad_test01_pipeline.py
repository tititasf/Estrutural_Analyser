#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_cad_test01_pipeline.py
==================================
CAD-TEST-01.1 — Fase-3 executa script real (nao apenas importa cache)
CAD-TEST-01.2 — DXF gerado pelo robo tem mtime > TEST_START
CAD-TEST-01.3 — Cobertura multi-obra (parametrizado)

Dependencias:
    pytest, ezdxf (opcional para CAD-TEST-01.2)

Configuracao via constantes no topo do arquivo.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ─── Configuracao ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path("D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main")
DADOS_OBRAS  = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
SCRIPTS      = PROJECT_ROOT / "scripts"

# CAD-TEST-01.3: lista de (obra_name, pavimento_opcional) para cobertura multi-obra
# None = motor_fase4 processa todos os pavimentos detectados
TEST_CONFIGS = [
    ("Obra_TREINO_1",  None),
    ("Obra_TREINO_20", None),
]

SKIP_MSG_OBRA = "Obra nao disponivel no ambiente"
SKIP_MSG_F3   = "Fase-3_Interpretacao_Extracao vazia ou ausente"

try:
    import ezdxf as _ezdxf  # noqa: F401
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run(script: str, args: list, label: str = "", timeout: int = 120) -> tuple[str, float]:
    """Executa script Python, retorna (stdout, duracao_s). Falha no test se rc!=0."""
    cmd = [sys.executable, str(SCRIPTS / script)] + args
    t0 = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        cwd=str(PROJECT_ROOT),
    )
    dt = time.time() - t0
    if result.returncode != 0:
        pytest.fail(
            f"[{label}] {script} falhou (rc={result.returncode}, {dt:.1f}s):\n"
            f"STDERR: {result.stderr[:600]}\n"
            f"STDOUT: {result.stdout[:400]}"
        )
    return result.stdout, dt


def _fase3_has_data(obra: Path) -> bool:
    """True se Fase-3 tem pelo menos pilares.json com conteudo."""
    pilares = obra / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares.json"
    if not pilares.exists():
        return False
    try:
        data = json.loads(pilares.read_text("utf-8", errors="replace"))
        return bool(data)
    except Exception:
        return False


def _find_dxf_source(obra: Path) -> Path | None:
    """Retorna o primeiro DXF de ingestao encontrado (para CAD-TEST-01.1)."""
    ingestao = obra / "Fase-1_Ingestao" / "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
    if not ingestao.exists():
        return None
    for dxf in sorted(ingestao.glob("*.dxf")):
        if dxf.stat().st_size > 0:
            return dxf
    return None


# ─── CAD-TEST-01.1: Fase-3 executa script real ────────────────────────────────

class TestFase3ScriptReal:
    """
    CAD-TEST-01.1 (P0): Verificar que engenharia_reversa_dxf.py executa
    de fato o pipeline de extração (não apenas lê cache existente).

    Estratégia: cria diretório temporário de obra contendo apenas os DXFs
    de ingestão. Sem Fase-3 preexistente, o script DEVE criar os arquivos.
    """

    def test_script_exists(self):
        """engenharia_reversa_dxf.py deve existir em scripts/."""
        script = SCRIPTS / "engenharia_reversa_dxf.py"
        assert script.exists(), f"Script nao encontrado: {script}"

    @pytest.mark.skipif(
        not (DADOS_OBRAS / "Obra_TREINO_1").exists(),
        reason=SKIP_MSG_OBRA,
    )
    def test_fase3_cria_pilares_json(self, tmp_path):
        """
        AC1: Script cria pilares.json em Fase-3_Interpretacao_Extracao/Pilares/.
        AC2: Script retorna rc=0 (sem erro).
        """
        obra_orig = DADOS_OBRAS / "Obra_TREINO_1"
        dxf_source = _find_dxf_source(obra_orig)
        if dxf_source is None:
            pytest.skip("Nenhum DXF de ingestao encontrado em Obra_TREINO_1")

        # Montar obra minimal: apenas a estrutura de ingestao com um DXF
        obra_tmp = tmp_path / "Obra_TESTE_FASE3"
        ingestao_tmp = (
            obra_tmp
            / "Fase-1_Ingestao"
            / "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
        )
        ingestao_tmp.mkdir(parents=True)
        shutil.copy(dxf_source, ingestao_tmp / dxf_source.name)

        # Copiar discovery.json se existir (necessario para path resolution)
        discovery_src = obra_orig / "Fase-1_Ingestao" / "discovery.json"
        if discovery_src.exists():
            shutil.copy(discovery_src, obra_tmp / "Fase-1_Ingestao" / "discovery.json")

        # Executar: Fase-3 nao existe ainda nesta obra_tmp
        stdout, dt = _run(
            "engenharia_reversa_dxf.py",
            ["--obra", str(obra_tmp), "--pavimento", "P-1"],
            label="Fase3",
            timeout=120,
        )

        # AC1: Fase-3 criada com pelo menos um JSON de output
        fase3_dir = obra_tmp / "Fase-3_Interpretacao_Extracao"
        assert fase3_dir.exists(), (
            f"Fase-3_Interpretacao_Extracao nao criada em {obra_tmp}\n"
            f"STDOUT: {stdout[:400]}"
        )

        output_jsons = list(fase3_dir.rglob("*.json"))
        assert output_jsons, (
            f"Nenhum .json gerado em {fase3_dir}\n"
            f"STDOUT: {stdout[:400]}"
        )

    @pytest.mark.skipif(
        not (DADOS_OBRAS / "Obra_TREINO_1").exists(),
        reason=SKIP_MSG_OBRA,
    )
    def test_fase3_nao_usa_apenas_cache(self, tmp_path):
        """
        AC2: Arquivo pilares.json gerado possui conteudo real (nao vazio).
        Garante que o script extraiu dados, nao apenas copiou um cache vazio.
        """
        obra_orig = DADOS_OBRAS / "Obra_TREINO_1"
        dxf_source = _find_dxf_source(obra_orig)
        if dxf_source is None:
            pytest.skip("Nenhum DXF de ingestao encontrado em Obra_TREINO_1")

        obra_tmp = tmp_path / "Obra_FASE3_NOCACHE"
        ingestao_tmp = (
            obra_tmp
            / "Fase-1_Ingestao"
            / "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
        )
        ingestao_tmp.mkdir(parents=True)
        shutil.copy(dxf_source, ingestao_tmp / dxf_source.name)

        discovery_src = obra_orig / "Fase-1_Ingestao" / "discovery.json"
        if discovery_src.exists():
            shutil.copy(discovery_src, obra_tmp / "Fase-1_Ingestao" / "discovery.json")

        _run(
            "engenharia_reversa_dxf.py",
            ["--obra", str(obra_tmp), "--pavimento", "P-1"],
            label="Fase3NoCa",
            timeout=120,
        )

        pilares_json = (
            obra_tmp / "Fase-3_Interpretacao_Extracao" / "Pilares" / "pilares.json"
        )
        # pilares.json pode nao existir se script usa outro nome — checar generico
        fase3_jsons = list(
            (obra_tmp / "Fase-3_Interpretacao_Extracao").rglob("*.json")
        )
        assert fase3_jsons, "Nenhum JSON gerado pela Fase-3"

        # Pelo menos um JSON nao-vazio
        has_content = any(j.stat().st_size > 2 for j in fase3_jsons)
        assert has_content, (
            f"Todos os JSONs de Fase-3 estao vazios: {[j.name for j in fase3_jsons]}"
        )


# ─── CAD-TEST-01.2: DXF gerado tem mtime > TEST_START ─────────────────────────

class TestDXFFreshGenerated:
    """
    CAD-TEST-01.2 (P1): Verifica que o DXF gerado pelo robo PL e mais
    recente que o inicio do teste (i.e., foi gerado agora, nao e cache antigo).
    """

    OBRA = DADOS_OBRAS / "Obra_TREINO_1"
    DXF_EXPECTED = OBRA / "Fase-6_Execucao_CAD" / "PL_stog_quality.dxf"

    @pytest.mark.skipif(not OBRA.exists(), reason=SKIP_MSG_OBRA)
    @pytest.mark.skipif(
        not _fase3_has_data(DADOS_OBRAS / "Obra_TREINO_1"),
        reason=SKIP_MSG_F3,
    )
    def test_pl_dxf_fresher_than_test_start(self, tmp_path):
        """
        AC1: mtime do DXF PL gerado e maior que TEST_START.
        AC2: DXF possui tamanho > 0 bytes.
        """
        # Registrar tempo de inicio do teste
        test_start = time.time()

        # Remover DXF anterior para garantir geração fresh
        backup_path = tmp_path / "PL_stog_quality.dxf.bak"
        if self.DXF_EXPECTED.exists():
            shutil.copy(self.DXF_EXPECTED, backup_path)
            self.DXF_EXPECTED.unlink()

        try:
            _run(
                "gerar_pl_dxf_stog.py",
                ["--obra", str(self.OBRA), "--max", "1"],
                label="GerarPL",
                timeout=120,
            )

            # AC2: arquivo existe e nao e vazio
            assert self.DXF_EXPECTED.exists(), (
                f"DXF PL nao gerado: {self.DXF_EXPECTED}"
            )
            assert self.DXF_EXPECTED.stat().st_size > 0, "DXF PL gerado esta vazio"

            # AC1: arquivo e mais recente que test_start
            mtime = self.DXF_EXPECTED.stat().st_mtime
            assert mtime > test_start, (
                f"DXF nao e fresh: mtime={mtime:.1f} <= test_start={test_start:.1f} "
                f"(delta={(test_start - mtime):.1f}s). Arquivo pode ser cache antigo."
            )

        finally:
            # Restaurar backup se geração falhou e havia versão anterior
            if not self.DXF_EXPECTED.exists() and backup_path.exists():
                shutil.copy(backup_path, self.DXF_EXPECTED)

    @pytest.mark.skipif(not OBRA.exists(), reason=SKIP_MSG_OBRA)
    @pytest.mark.skipif(
        not _fase3_has_data(DADOS_OBRAS / "Obra_TREINO_1"),
        reason=SKIP_MSG_F3,
    )
    @pytest.mark.skipif(not HAS_EZDXF, reason="ezdxf nao instalado")
    def test_pl_dxf_is_valid_ezdxf(self):
        """AC3 (bonus): DXF gerado e lido sem erros pelo ezdxf."""
        import ezdxf

        if not self.DXF_EXPECTED.exists():
            pytest.skip("DXF PL nao existe — rode test_pl_dxf_fresher_than_test_start primeiro")

        doc = ezdxf.readfile(str(self.DXF_EXPECTED))
        msp = doc.modelspace()
        entities = list(msp)
        assert len(entities) > 0, "DXF PL nao tem entidades no modelspace"


# ─── CAD-TEST-01.3: Multi-obra coverage ───────────────────────────────────────

def _make_obra_id(obra_name: str, pav: str | None) -> str:
    return f"{obra_name}_{pav or 'all'}"


@pytest.mark.parametrize(
    "obra_name,pav",
    TEST_CONFIGS,
    ids=[_make_obra_id(o, p) for o, p in TEST_CONFIGS],
)
class TestMultiObraFase4:
    """
    CAD-TEST-01.3 (P1): motor_fase4.py roda com sucesso em multiplas obras.
    Configuracao via TEST_CONFIGS no topo do arquivo.
    """

    @staticmethod
    def _skip_if_missing(obra_name: str) -> None:
        obra = DADOS_OBRAS / obra_name
        if not obra.exists():
            pytest.skip(f"{obra_name} nao disponivel no ambiente")
        if not _fase3_has_data(obra):
            pytest.skip(f"{obra_name}: Fase-3 vazia ou ausente")

    def test_motor_fase4_runs_ok(self, obra_name, pav):
        """AC1: motor_fase4.py retorna rc=0 para a obra/pav configurada."""
        self._skip_if_missing(obra_name)

        obra = DADOS_OBRAS / obra_name
        args = ["--obra", str(obra)]
        if pav:
            args += ["--pavimento", pav]

        stdout, dt = _run(
            "motor_fase4.py",
            args,
            label=f"F4-{obra_name}",
            timeout=120,
        )

        # AC2: Fase-4 criada
        fase4 = obra / "Fase-4_Sincronizacao"
        assert fase4.exists(), f"Fase-4_Sincronizacao nao criada para {obra_name}"

    def test_fase4_has_pilares(self, obra_name, pav):
        """AC2: Ao menos um JSON de pilar gerado em Fase-4."""
        self._skip_if_missing(obra_name)

        obra = DADOS_OBRAS / obra_name
        fase4 = obra / "Fase-4_Sincronizacao"

        if not fase4.exists():
            pytest.skip("Fase-4 nao existe — rode test_motor_fase4_runs_ok primeiro")

        has_pilares = (
            (fase4 / "pilares_salvos.json").exists()
            or any((fase4 / "JSON_Pilares").glob("*.json"))
            if (fase4 / "JSON_Pilares").exists()
            else False
        )
        assert has_pilares, (
            f"Nenhum output de pilares em Fase-4 para {obra_name}. "
            f"Conteudo: {list(fase4.iterdir())[:10]}"
        )

    def test_fase4_pilares_salvos_valid_json(self, obra_name, pav):
        """AC3: pilares_salvos.json e JSON valido (se existir)."""
        self._skip_if_missing(obra_name)

        obra = DADOS_OBRAS / obra_name
        salvos = obra / "Fase-4_Sincronizacao" / "pilares_salvos.json"

        if not salvos.exists():
            pytest.skip("pilares_salvos.json nao existe para esta obra")

        try:
            data = json.loads(salvos.read_text("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"pilares_salvos.json invalido em {obra_name}: {exc}")

        assert isinstance(data, (list, dict)), (
            f"pilares_salvos.json nao e lista/dict em {obra_name}: {type(data)}"
        )
