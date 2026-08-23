"""Ficha de dúvida: padrão aprovado pelo dono em 2026-08-20."""
import re

import pytest

from scripts.arete.gerar_duvida_html import Destaque, Duvida, Leitura, Nota, gerar

ezdxf = pytest.importorskip("ezdxf")


@pytest.fixture
def dxf(tmp_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (100, 0), dxfattribs={"layer": "3"})
    msp.add_line((0, 20), (100, 20), dxfattribs={"layer": "3"})
    msp.add_text("V1", dxfattribs={"layer": "4"}).set_placement((10, 25))
    path = tmp_path / "recorte.dxf"
    doc.saveas(path)
    return path


def _gerar(tmp_path, dxf, **extra):
    saida = tmp_path / "duvida.html"
    gerar(Duvida(
        titulo="V1 chega em P1?",
        pergunta="A viga V1 chega no pilar P1?",
        dxf=dxf, janela=(-10, -10, 110, 40), saida=saida,
        legenda="O vão entre os dois.",
        destaques=[Destaque("V1 — viga", 0, 0, 100, 20, "#2563eb")],
        notas=[Nota("vao", 50, 10)],
        leituras=[Leitura("Chega", "encosta", "implemento alcance")],
        **extra,
    ))
    return saida.read_text(encoding="utf-8")


def test_o_desenho_vira_svg_com_viewbox_do_dxf(tmp_path, dxf):
    page = _gerar(tmp_path, dxf)

    assert '<svg viewBox="-10 -40 120 50"' in page
    # Y do DXF sobe, do SVG desce: o recorte é espelhado, não redesenhado.
    assert 'y1="-0.00"' in page or 'y1="0.00"' in page


def test_panzoom_usa_viewbox_e_nunca_css_scale(tmp_path, dxf):
    page = _gerar(tmp_path, dxf)

    assert "setAttribute('viewBox'" in page
    assert "transform:scale" not in page
    assert "scale(" not in re.sub(r"viewBox[^\"]*\"[^\"]*\"", "", page)


def test_pergunta_aparece_no_topo_e_no_pedido_final(tmp_path, dxf):
    page = _gerar(tmp_path, dxf)

    assert page.count("A viga V1 chega no pilar P1?") == 2


def test_destaques_viram_legenda_e_realce(tmp_path, dxf):
    page = _gerar(tmp_path, dxf)

    assert "V1 — viga" in page
    assert '<rect x="0.00"' in page


def test_leituras_e_consequencias_ficam_lado_a_lado(tmp_path, dxf):
    page = _gerar(tmp_path, dxf)

    assert "Chega" in page and "implemento alcance" in page
    assert "Se for essa" in page


def test_texto_do_desenho_e_escapado(tmp_path, dxf):
    doc = ezdxf.readfile(str(dxf))
    doc.modelspace().add_text("<b>&", dxfattribs={"layer": "4"}).set_placement((50, 30))
    doc.saveas(dxf)

    page = _gerar(tmp_path, dxf)

    assert "&lt;b&gt;&amp;" in page


def test_tema_claro_e_escuro_sem_cor_orfa(tmp_path, dxf):
    page = _gerar(tmp_path, dxf)

    assert "--bg:#fff" in page
    assert "prefers-color-scheme:dark" in page
    assert '[data-theme="dark"]' in page
