"""Teste de paridade — `services.ficha_service.encontrar_dir_fichas` (cópia
isolada, STORY-05 escape hatch) vs `portal.app.pipeline_runner.
encontrar_dir_fichas` (original). Garante que a cópia nunca diverge do
comportamento real do portal."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_REPO_ROOT = _PROJECT_ROOT.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from services.ficha_service import encontrar_dir_fichas as copia  # noqa: E402
from portal.app.pipeline_runner import encontrar_dir_fichas as original  # noqa: E402


def _monta_run_dirs(obra_dir: Path, nomes_com_manifest: list[str], nomes_sem_manifest: list[str]):
    for nome in nomes_com_manifest:
        d = obra_dir / nome
        d.mkdir(parents=True)
        (d / "arete_manifest.json").write_text("{}", encoding="utf-8")
    for nome in nomes_sem_manifest:
        (obra_dir / nome).mkdir(parents=True)


def test_paridade_multiplos_runs_pega_o_mais_recente(tmp_path: Path):
    obra_dir = tmp_path / "obra"
    obra_dir.mkdir()
    _monta_run_dirs(
        obra_dir,
        nomes_com_manifest=["TERREO_20260101_000000", "TERREO_20260102_000000"],
        nomes_sem_manifest=["Fase-4_Sincronizacao"],
    )
    assert copia(obra_dir) == original(obra_dir)
    assert copia(obra_dir).name == "TERREO_20260102_000000"


def test_paridade_sem_nenhum_run(tmp_path: Path):
    obra_dir = tmp_path / "obra_vazia"
    obra_dir.mkdir()
    assert copia(obra_dir) == original(obra_dir) is None


def test_paridade_obra_dir_inexistente(tmp_path: Path):
    obra_dir = tmp_path / "nao_existe"
    assert copia(obra_dir) == original(obra_dir) is None


def test_paridade_dir_sem_manifest_ignorado(tmp_path: Path):
    obra_dir = tmp_path / "obra2"
    obra_dir.mkdir()
    _monta_run_dirs(
        obra_dir,
        nomes_com_manifest=[],
        nomes_sem_manifest=["TERREO_lixo_sem_manifest"],
    )
    assert copia(obra_dir) == original(obra_dir) is None
