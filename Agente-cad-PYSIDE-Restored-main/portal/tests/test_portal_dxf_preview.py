"""Testes reais de dxf_preview.py (2026-07-06) — usa DXFs reais gerados nesta
sessão (recorte real do RecorteMotor + o DXF de entrada convertido pela
triagem) como fixture. Se não existirem nesta máquina, os testes são pulados.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from portal.app import dxf_preview as dp

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OBRA_DIR = _REPO_ROOT / "DADOS-OBRAS" / "thierry.tasf@gmail.com" / "TMC-EST-PE-6000-13P-R03"
_RECORTES_DIR = _OBRA_DIR / "Fase-2_Triagem" / "recortes_reversos"
_ENTRADA_DXF = _OBRA_DIR / "entrada" / "TMC-EST-PE-6000-13P-R03.dxf"


def _um_recorte_real() -> Path | None:
    if not _RECORTES_DIR.exists():
        return None
    candidatos = sorted(_RECORTES_DIR.glob("LAJ_L301_motor_*.dxf"))
    return candidatos[-1] if candidatos else None


pytestmark = pytest.mark.skipif(
    _um_recorte_real() is None or not _ENTRADA_DXF.is_file(),
    reason="recortes/entrada reais da obra TMC-EST-PE-6000-13P-R03 ausentes nesta máquina",
)


def test_obter_bbox_dxf_real():
    bbox = dp.obter_bbox_dxf(_um_recorte_real())
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    assert x1 > x0 and y1 > y0  # bbox real, com area positiva


def test_renderizar_dxf_png_recorte_real():
    png = dp.renderizar_dxf_png(_um_recorte_real())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # assinatura real de PNG
    assert len(png) > 1000  # nao e' um PNG vazio/1x1


def test_renderizar_dxf_png_com_bbox_recorta_regiao():
    bbox = dp.obter_bbox_dxf(_um_recorte_real())
    png_bruto = dp.renderizar_dxf_png(_ENTRADA_DXF, bbox=bbox)
    png_completo = dp.renderizar_dxf_png(_ENTRADA_DXF)
    assert png_bruto[:8] == b"\x89PNG\r\n\x1a\n"
    # recortado por bbox e' uma imagem DIFERENTE do dxf inteiro (regiao menor)
    assert png_bruto != png_completo


def test_renderizar_dxf_png_cacheado_grava_e_reusa(tmp_path):
    cache_dir = tmp_path / ".previews"
    png1 = dp.renderizar_dxf_png_cacheado(_um_recorte_real(), cache_dir)
    arquivos_cache = list(cache_dir.glob("*.png"))
    assert len(arquivos_cache) == 1
    png2 = dp.renderizar_dxf_png_cacheado(_um_recorte_real(), cache_dir)
    assert png1 == png2
    assert len(list(cache_dir.glob("*.png"))) == 1  # nao duplicou o cache
