from pathlib import Path

from bs4 import BeautifulSoup

from src.ui.widgets.preficha_laje_html import write_laje_pages
from src.ui.widgets.pre_validation_dialog import PreValidationDialog
from src.ui.widgets.pre_validation_dialog import _segment_geometry_metrics


class _FakeDialog:
    _obra = "Obra_TESTE"
    _pavimento = "13_PAV"
    _db_path = None

    def _find_beam_dxf(self, class_prefix, item_name, n4=False):
        assert class_prefix == "LJ"
        return f'{"n4" if n4 else "n3"}_{class_prefix}_{item_name}.dxf'

    def _find_n2_recorte_dxf(self, class_prefix, item_name):
        assert class_prefix == "LAJ"
        return f"n2_{class_prefix}_{item_name}.dxf"

    def _render_pilar_dxf_context_b64(
        self, points, width=1000, height=680, focus_mode="pillar", fmt="png",
        focus_label="SEGMENTO", context_view="near",
    ):
        assert (width, height) == (1820, 1300)
        assert focus_mode == "slab"
        assert focus_label == "L301"
        assert context_view in {"near", "far"}
        if fmt == "svg":
            return f'<svg viewBox="0 0 10 10"><text>SA-{context_view}</text></svg>'
        return "U0E="

    def _render_ezdxf_b64(self, path, width=950, height=620, fmt="png"):
        assert (width, height) == (1900, 1240)
        if fmt == "svg":
            return '<svg viewBox="0 0 10 10"><text>DXF</text></svg>'
        return "RFhG"

    def _n2_ficha_html(self, class_prefix, item_name):
        assert class_prefix == "LAJ"
        return "<table><tr><td>N2 completo</td></tr></table>"


def test_laje_writer_creates_granular_page_with_two_n1_svg_evidences(tmp_path: Path):
    rows = [{
        "Nome": "L301",
        "Nível": "+3.05",
        "Espessura": "10 cm",
        "Atenção": "",
        "Detalhes": "DIMENSÕES E NÍVEL\nAltura: 10 cm\nNível: +3.05",
        "_points": [(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)],
        "_slab": {"name": "L301", "area": 80.0},
        "_name": "L301",
    }]

    result = write_laje_pages(
        dialog=_FakeDialog(),
        title="Lajes",
        rows=rows,
        output_dir=str(tmp_path),
        page_css="",
        javascript="",
        photo_fn=lambda points: "",
        metrics_fn=_segment_geometry_metrics,
    )

    assert result == ("lajes/index.html", "Lajes", 1)
    page = tmp_path / "lajes" / "L301.html"
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    assert len(soup.select(".evidence-card svg")) == 5
    style = soup.style.get_text()
    assert "grid-template-columns:1fr!important" in style
    assert "max-height:none!important" in style
    text = soup.get_text(" ", strip=True)
    assert "N1 próximo / SA" in text
    assert "N1 contexto / SA" in text
    assert "Prova local" in text
    assert "não prova apoio por proximidade" in text
    assert "N2 / STOG real" in text
    assert "N3 / Robô SA" in text
    assert "N4 / Robô ER" in text
    assert "Vértices brutos do contorno" in text
    assert "Quality gates da ficha LJ" in text
    assert "N2 completo" in text
    assert len(soup.select("[data-atkey]")) == 4


def test_find_beam_dxf_accepts_lj_prefix():
    dialog = PreValidationDialog.__new__(PreValidationDialog)
    dialog._obra = "Obra_Que_Nao_Existe"
    dialog._n3_preview_dir = ""

    assert dialog._find_beam_dxf("LJ", "L301", n4=False) == ""
    assert dialog._find_beam_dxf("XX", "L301", n4=False) == ""


def test_laje_page_has_error_marker_as_last_field_persisted_via_localstorage(
    tmp_path: Path,
):
    rows = [{
        "Nome": "L301",
        "Nível": "+3.05",
        "Espessura": "10 cm",
        "Atenção": "",
        "Detalhes": "",
        "_points": [(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)],
        "_slab": {"name": "L301", "area": 80.0},
        "_name": "L301",
    }]

    write_laje_pages(
        dialog=_FakeDialog(),
        title="Lajes",
        rows=rows,
        output_dir=str(tmp_path),
        page_css="",
        javascript="",
        photo_fn=lambda points: "",
        metrics_fn=_segment_geometry_metrics,
    )

    page_html = (tmp_path / "lajes" / "L301.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(page_html, "html.parser")

    checkbox = soup.select_one("#erro_check")
    textarea = soup.select_one("#erro_nota")
    assert checkbox is not None and checkbox.get("type") == "checkbox"
    assert textarea is not None

    # marcador de erro deve ser o último elemento de #main-content antes do
    # fechamento das divs de layout (último "campo" do html, como pedido).
    main_content = soup.select_one(".main-content")
    last_block = main_content.find_all("div", class_="sec", recursive=False)[-1]
    assert "Marcação de erro" in last_block.get_text()

    # a chave de localStorage usa o prefixo aten_ para reaproveitar o
    # exportAnotacoes() já existente nas outras fichas granulares.
    assert "aten_erro_lj_Obra_TESTE_13_PAV_L301" in page_html

    # sem botão de exportação no índice: a leitura é feita depois via
    # scripts/arete/qa_error_review.py (perfil de navegador persistente).
    index_html = (tmp_path / "lajes" / "index.html").read_text(encoding="utf-8")
    assert "exportarErros" not in index_html

    # sidebar expõe data-laje + span oculto para o script de flag de erro
    # marcar visualmente (⚠️) quem já foi revisado como errado.
    sidebar_li = soup.select_one('.sidebar li[data-laje="L301"]')
    assert sidebar_li is not None
    flag = sidebar_li.select_one(".erro-flag")
    assert flag is not None and flag.get("style") == "display:none"
    assert "aten_erro_lj_" in page_html
    assert ".sidebar li[data-laje]" in page_html
