from __future__ import annotations

import ezdxf

from portal.app.preprocessamento.adapters.pillar_convention import extract_pillar_convention


def _save_convention(path, *, labels=("NASCE", "SEGUE", "MORRE"), with_header=True):
    document = ezdxf.new("R2010")
    model = document.modelspace()
    if with_header:
        model.add_text("CONVENÇÃO DE PILARES", dxfattribs={"insert": (0, 100)})
    for x, label in zip((0, 250, 500), labels):
        model.add_text(label, dxfattribs={"insert": (x, 0)})
    model.add_line((-20, -20), (20, 20))
    model.add_line((-20, 20), (20, -20))
    model.add_line((230, -20), (270, 20))
    model.add_line((230, -30), (270, 10))
    document.saveas(path)


def test_extrai_rotulos_reais_sem_mapear_assinatura_para_semantica(tmp_path):
    path = tmp_path / "conv.dxf"
    _save_convention(path)

    result = extract_pillar_convention(path)
    entries = {entry["label"]: entry for entry in result["entries"]}

    assert entries["NASCE"]["signature"] == "CROSS"
    assert entries["SEGUE"]["signature"] == "DIAG"
    assert entries["MORRE"]["signature"] == "EMPTY"
    assert result["status"] == "complete"


def test_legenda_invertida_preserva_os_rotulos_do_desenho(tmp_path):
    path = tmp_path / "invertida.dxf"
    _save_convention(path, labels=("MORRE", "NASCE", "SEGUE"))

    result = extract_pillar_convention(path)
    index = result["signature_index"]

    assert index["CROSS"] == ["MORRE"]
    assert index["DIAG"] == ["NASCE"]
    assert index["EMPTY"] == ["SEGUE"]


def test_sem_cabecalho_nao_aplica_fallback_hardcoded(tmp_path):
    path = tmp_path / "sem-header.dxf"
    _save_convention(path, with_header=False)

    result = extract_pillar_convention(path)

    assert result["status"] == "partial"
    assert result["entries"] == []
    assert result["warnings"]


def test_assinatura_ambigua_retorna_todas_as_alternativas(tmp_path):
    path = tmp_path / "ambigua.dxf"
    document = ezdxf.new("R2010")
    model = document.modelspace()
    model.add_text("LEGENDA PILAR", dxfattribs={"insert": (0, 100)})
    model.add_text("TIPO A", dxfattribs={"insert": (0, 0)})
    model.add_text("TIPO B", dxfattribs={"insert": (250, 0)})
    document.saveas(path)

    result = extract_pillar_convention(path)

    assert result["signature_index"]["EMPTY"] == ["TIPO A", "TIPO B"]
    assert result["conflicts"] == [{"signature": "EMPTY", "labels": ["TIPO A", "TIPO B"]}]
    assert result["status"] == "partial"
