"""Testes reais de recortes_reader.py (2026-07-06) — usa os recortes reais já
em disco (RecorteMotor rodou de verdade nesta sessão, múltiplas vezes, cada
rodada grava um arquivo NOVO com timestamp — este módulo tem que escolher
sempre o mais recente por item). Pulados se os artefatos reais não existirem.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from portal.app import recortes_reader as rr

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OBRA_DIR = _REPO_ROOT / "DADOS-OBRAS" / "thierry.tasf@gmail.com" / "TMC-EST-PE-6000-13P-R03"

pytestmark = pytest.mark.skipif(
    not (_OBRA_DIR / "Fase-2_Triagem" / "recortes_reversos").exists(),
    reason="recortes reais da obra TMC-EST-PE-6000-13P-R03 ausentes nesta máquina",
)


def test_listar_classes_recorte_acha_laj_real():
    classes = rr.listar_classes_recorte(_OBRA_DIR)
    por_classe = {c["classe"]: c["total"] for c in classes}
    assert por_classe.get("LAJ") == 31  # 31 lajes reais desta obra


def test_listar_itens_recorte_dedup_por_versao_mais_recente():
    itens = rr.listar_itens_recorte(_OBRA_DIR, "LAJ")
    ids = [i["item_id"] for i in itens]
    assert len(ids) == len(set(ids))  # nenhum item duplicado (varias rodadas -> 1 so')
    assert "L301" in ids


def test_listar_itens_recorte_escolhe_de_verdade_o_ultimo_timestamp():
    itens_dict = {i["item_id"]: Path(i["recorte_path"]) for i in rr.listar_itens_recorte(_OBRA_DIR, "LAJ")}
    escolhido = itens_dict["L301"]
    diretorio = _OBRA_DIR / "Fase-2_Triagem" / "recortes_reversos"
    candidatos = sorted(diretorio.glob("LAJ_L301_motor_*.dxf"))
    assert escolhido == candidatos[-1]  # o de MAIOR timestamp, nao qualquer um


def test_obter_item_recorte_encontra_e_none_quando_nao_existe():
    assert rr.obter_item_recorte(_OBRA_DIR, "LAJ", "L301") is not None
    assert rr.obter_item_recorte(_OBRA_DIR, "LAJ", "L999_NAO_EXISTE") is None


def test_classe_sem_recortes_devolve_lista_vazia():
    assert rr.listar_itens_recorte(_OBRA_DIR, "PIL") == []  # motor nao achou PIL nesta obra


def test_obter_detalhes_recorte_real():
    """[2026-07-06] painel 'Detalhes e Convenções' — metadados reais lidos do
    DXF (nao inventados): entidades, camadas, tipos, dimensoes do bbox."""
    item = rr.obter_item_recorte(_OBRA_DIR, "LAJ", "L301")
    detalhes = rr.obter_detalhes_recorte(Path(item["recorte_path"]))
    assert detalhes["entidades"] > 0
    assert detalhes["largura"] > 0
    assert detalhes["altura"] > 0
    assert isinstance(detalhes["camadas"], list)
    assert isinstance(detalhes["tipos_entidade"], list)


def test_listar_brutos_recorte_dedup_dwg_dxf_mesmo_stem():
    """[2026-07-07] navegação por bruto (não mais por classe) — dwg+dxf do
    mesmo arquivo contam como 1 bruto só (a obra real tem os dois)."""
    brutos = rr.listar_brutos_recorte(_OBRA_DIR)
    assert len(brutos) == 1
    assert brutos[0]["nome"] == "TMC-EST-PE-6000-13P-R03.dxf"


def test_listar_brutos_recorte_sem_entrada_devolve_vazio(tmp_path):
    assert rr.listar_brutos_recorte(tmp_path / "obra_sem_entrada") == []


def test_listar_todos_recortes_achatado_com_classe_por_item():
    itens = rr.listar_todos_recortes(_OBRA_DIR)
    assert len(itens) == 31  # só LAJ tem itens reais nesta obra
    assert all(i["classe"] == "LAJ" for i in itens)
    assert any(i["item_id"] == "L301" for i in itens)


def test_obra_sem_pasta_de_recortes_mostra_as_4_classes_zeradas(tmp_path):
    """[2026-07-06] as 4 classes (pastas) do RecorteMotor aparecem sempre,
    mesmo com 0 itens — mostra a estrutura real (PIL/LV/FV/LAJ) mesmo antes
    de qualquer recorte rodar, em vez de esconder tudo."""
    classes = rr.listar_classes_recorte(tmp_path / "obra_nova_sem_recortes")
    assert {c["classe"] for c in classes} == {"PIL", "LV", "FV", "LAJ"}
    assert all(c["total"] == 0 for c in classes)
    assert rr.listar_itens_recorte(tmp_path / "obra_nova_sem_recortes", "LAJ") == []
