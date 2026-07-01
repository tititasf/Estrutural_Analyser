from pathlib import Path

from bs4 import BeautifulSoup

from src.ui.widgets.preficha_fundo_html import write_fundo_pages
from src.ui.widgets.pre_validation_dialog import PreValidationDialog
from src.ui.widgets.pre_validation_dialog import _segment_geometry_metrics


def test_segment_geometry_metrics_exposes_bbox_area_and_duplicate_vertices():
    metrics = _segment_geometry_metrics([
        (0, 0), (10, 0), (10, 4), (0, 4), (0, 0),
    ])

    assert metrics["bbox"] == (0.0, 0.0, 10.0, 4.0)
    assert metrics["area"] == 40.0
    assert metrics["orientation"] == "horizontal"
    assert metrics["vertex_count"] == 5
    assert metrics["unique_vertex_count"] == 4
    assert metrics["closed"] is True


class _FakeDialog:
    _obra = "Obra_TESTE"
    _pavimento = "13_PAV"
    _beams = [{
        "id": "beam-1",
        "name": "V301",
        "fields": {"viga_fundo_seg_1_largura": 19},
        "links": {
            "viga_fundo_seg_1_area_segs": {
                "contour": [{"points": [(0, 0), (10, 0), (10, 4), (0, 4)]}]
            }
        },
    }]

    def _find_beam_dxf(self, class_prefix, item_name, n4=False):
        return f'{"n4" if n4 else "n3"}_{class_prefix}_{item_name}.dxf'

    def _find_n2_recorte_dxf(self, class_prefix, item_name):
        return f"n2_{class_prefix}_{item_name}.dxf"

    def _render_pilar_dxf_context_b64(
        self, points, width=1000, height=680, focus_mode="pillar"
    ):
        assert focus_mode == "segment"
        assert (width, height) == (2400, 600)
        return "U0E="

    def _render_ezdxf_b64(self, path, width=950, height=620):
        assert (width, height) == (1900, 1240)
        return "RFhG"

    def _n2_ficha_html(self, class_prefix, item_name):
        return "<table><tr><td>N2 completo</td></tr></table>"

    def _n3_ficha_html_beam(self, class_prefix, item_name):
        return "<table><tr><td>N3 completo</td></tr></table>"


def test_fundo_writer_creates_granular_page_with_four_visual_stages(tmp_path: Path):
    rows = [{
        "Comprimento": "10.0",
        "Largura": "4",
        "Status": "valid",
        "Atenção": "",
        "_beam": "V301",
        "_points": [(0, 0), (10, 0), (10, 4), (0, 4), (0, 0)],
        "_segment": {
            "uid": "fundo|beam-1|1|1",
            "beam_name": "V301",
            "beam_identity": "beam-1",
            "segment_label": "1",
            "segment_index": 1,
            "occurrence": 1,
            "side": "Fundo",
            "behavior": "Fundo",
            "length": 10.0,
            "width": "4",
            "points": [(0, 0), (10, 0), (10, 4), (0, 4), (0, 0)],
            "source_key": "viga_fundo_seg_1_area_segs",
            "source_slot": "contour",
            "tag": "Fundo",
            "ficha": {"largura_total_fundo": 4},
        },
    }]

    result = write_fundo_pages(
        dialog=_FakeDialog(),
        title="Fundos",
        rows=rows,
        output_dir=str(tmp_path),
        page_css="",
        javascript="",
        photo_fn=lambda points: "",
        metrics_fn=_segment_geometry_metrics,
    )

    assert result == ("fundos_viga/index.html", "Fundos", 1)
    page = tmp_path / "fundos_viga" / "V301_1.html"
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    assert len(soup.select(".evidence-card img")) == 4
    style = soup.style.get_text()
    assert "grid-template-columns:1fr!important" in style
    assert "max-height:none!important" in style
    text = soup.get_text(" ", strip=True)
    assert "N1 / SA" in text
    assert "N2 / STOG real" in text
    assert "N3 / Robô SA" in text
    assert "N3 / NOVA" in text
    assert "N4 / Robô ER" in text
    assert "Vértices brutos do contorno" in text
    assert "Quality gates da ficha FV" in text
    assert len(soup.select("[data-atkey]")) == 4


def test_isolated_n3_directory_never_falls_back_to_shared_preview(tmp_path):
    isolated = tmp_path / "n3_nova"
    isolated.mkdir()
    expected = isolated / "FV_preview_V301.dxf"
    expected.write_text("0\nEOF\n", encoding="ascii")

    dialog = PreValidationDialog.__new__(PreValidationDialog)
    dialog._obra = "Obra_Que_Nao_Existe"
    dialog._n3_preview_dir = str(isolated)

    assert dialog._find_beam_dxf("FV", "V301", n4=False) == str(expected)
    assert dialog._find_beam_dxf("FV", "V302", n4=False) == ""
