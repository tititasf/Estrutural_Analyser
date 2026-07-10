"""Testes reais de torre_crop.py (2026-07-07) — motor de recorte por
bruto/torre+detalhes (scripts/obra_crop_engine, DBSCAN), o que a aba
Recortes do portal REALMENTE deve mostrar (não os 31 recortes por-laje do
RecorteMotor, que é outro motor pra outro fim). Usa o DXF de entrada real
da obra TMC-EST-PE-6000-13P-R03 já em disco.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from portal.app import torre_crop

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OBRA_DIR = _REPO_ROOT / "DADOS-OBRAS" / "thierry.tasf@gmail.com" / "TMC-EST-PE-6000-13P-R03"
_DXF_BRUTO = _OBRA_DIR / "entrada" / "TMC-EST-PE-6000-13P-R03.dxf"

pytestmark = pytest.mark.skipif(
    not _DXF_BRUTO.is_file(),
    reason="DXF de entrada real da obra TMC-EST-PE-6000-13P-R03 ausente nesta máquina",
)


def test_gerar_recortes_bruto_real_produz_torre_e_detalhes():
    resultado = torre_crop.gerar_recortes_bruto(
        _OBRA_DIR, _DXF_BRUTO, "TMC-EST-PE-6000-13P-R03", force=True,
    )
    assert resultado["error"] is None
    assert len(resultado["torres"]) == 1
    assert resultado["torres"][0]["entidades"] > 1000  # planta real, não crop minúsculo
    assert resultado["detalhes"] is not None
    assert resultado["detalhes"]["entidades"] > 0


def test_listar_recortes_bruto_acha_torre_1_e_detalhes():
    torre_crop.gerar_recortes_bruto(_OBRA_DIR, _DXF_BRUTO, "TMC-EST-PE-6000-13P-R03", force=True)
    itens = torre_crop.listar_recortes_bruto(_OBRA_DIR, "TMC-EST-PE-6000-13P-R03")
    ids = {i["item_id"] for i in itens}
    assert ids == {"torre_1", "detalhes"}


def test_gerar_recortes_bruto_cache_pula_regeracao_sem_force():
    torre_crop.gerar_recortes_bruto(_OBRA_DIR, _DXF_BRUTO, "TMC-EST-PE-6000-13P-R03", force=True)
    resultado = torre_crop.gerar_recortes_bruto(_OBRA_DIR, _DXF_BRUTO, "TMC-EST-PE-6000-13P-R03", force=False)
    assert resultado["cached"] is True


def test_obter_recorte_bruto_none_para_item_inexistente():
    torre_crop.gerar_recortes_bruto(_OBRA_DIR, _DXF_BRUTO, "TMC-EST-PE-6000-13P-R03", force=True)
    assert torre_crop.obter_recorte_bruto(_OBRA_DIR, "TMC-EST-PE-6000-13P-R03", "torre_99") is None
    item = torre_crop.obter_recorte_bruto(_OBRA_DIR, "TMC-EST-PE-6000-13P-R03", "torre_1")
    assert item is not None and Path(item["path"]).is_file()


def test_listar_recortes_bruto_sem_geracao_devolve_vazio(tmp_path):
    assert torre_crop.listar_recortes_bruto(tmp_path / "obra_nova", "algum_bruto") == []


def test_gerar_recortes_bruto_dxf_com_poucas_entidades_devolve_erro(tmp_path):
    import ezdxf

    obra_dir = tmp_path / "obra_minima"
    dxf_path = obra_dir / "entrada" / "minimo.dxf"
    dxf_path.parent.mkdir(parents=True)
    doc = ezdxf.new()
    doc.modelspace().add_line((0, 0), (1, 1))
    doc.saveas(dxf_path)

    resultado = torre_crop.gerar_recortes_bruto(obra_dir, dxf_path, "minimo", force=True)
    assert resultado["error"] is not None
    assert torre_crop.listar_recortes_bruto(obra_dir, "minimo") == []
