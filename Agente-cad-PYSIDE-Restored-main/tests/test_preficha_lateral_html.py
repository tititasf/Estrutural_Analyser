from pathlib import Path

from bs4 import BeautifulSoup

from src.ui.widgets.preficha_lateral_html import write_lateral_pages
from src.ui.widgets.pre_validation_dialog import _segment_geometry_metrics


class _FakeDialog:
    _obra = "Obra_TESTE"
    _pavimento = "13_PAV"
    _beams = [{
        "id": "beam-1",
        "name": "V301",
        "fields": {
            "viga_a_seg_1_h1": "55",
            "viga_b_seg_1_h1": "55",
        },
        "links": {},
    }]

    def _find_beam_dxf(self, class_prefix, item_name, n4=False):
        assert class_prefix == "LV"
        # item_name deve vir com sufixo _A/_B (granularidade real dos DXFs
        # N3/N4 de LV, ver docstring de write_lateral_pages)
        assert item_name in ("V301_A", "V301_B")
        return f'{"n4" if n4 else "n3"}_{item_name}.dxf'

    def _find_n2_recorte_dxf(self, class_prefix, item_name):
        assert class_prefix == "LV"
        assert item_name == "V301"
        return "n2_V301.dxf"

    def _render_pilar_dxf_context_b64(
        self, points, width=1000, height=680, focus_mode="pillar", fmt="png"
    ):
        assert focus_mode == "segment"
        if fmt == "svg":
            return '<svg viewBox="0 0 10 10"><text>SA</text></svg>'
        return "U0E="

    def _render_ezdxf_b64(self, path, width=950, height=620, fmt="png"):
        assert (width, height) == (1900, 1240)
        if fmt == "svg":
            return '<svg viewBox="0 0 10 10"><text>DXF</text></svg>'
        return "RFhG"

    def _n2_ficha_html(self, class_prefix, item_name):
        assert class_prefix == "LV"
        return "<table><tr><td>N2 completo (ambos os lados)</td></tr></table>"

    def _n3_ficha_html_beam(self, class_prefix, item_name):
        assert class_prefix == "LV"
        return "<table><tr><td>N3 completo (1 lado)</td></tr></table>"


def _lateral_row(side: str, behavior: str, segment_index: int, points: list[tuple]) -> dict:
    side_key = side.lower()
    return {
        "Comprimento": "10.0",
        "Status": "valid",
        "Atenção": "",
        "_beam": "V301",
        "_points": points,
        "_segment": {
            "uid": f"lateral_{side_key}_{behavior.lower()}|beam-1|{segment_index}|1",
            "beam_name": "V301",
            "beam_identity": "beam-1",
            "segment_label": str(segment_index),
            "segment_index": segment_index,
            "occurrence": 1,
            "side": side,
            "behavior": behavior,
            "length": 1264.0,
            "height": "55",
            "width": "19/55",
            "points": points,
            "tag": f"Lado {side}",
            "ficha": {},
            "details": {
                "support_start": {"name": "P41", "dimension": "19x50", "level": "852.19"},
                "support_end": {"name": "P44", "dimension": "19x50", "level": "852.19"},
                "beam_level": "",
                "slabs": [{"name": "L301", "level": "852.12", "height": "12"}],
                "continuity": "",
                "adjustment": {"initial": "", "final": "", "total": ""},
                "passing_pillars": [],
                "beam_openings": [],
            },
            "source_key": f"viga_{side_key}_seg_{segment_index}_comprimento_total",
            "source_slot": f"seg_side_{side_key}",
        },
    }


def test_lateral_writer_creates_one_page_per_beam_with_side_a_and_side_b(tmp_path: Path):
    points = [(0, 0), (10, 0)]
    rows_by_kind = {
        "lateral_a_para": [_lateral_row("A", "Para", 1, points)],
        "lateral_b_para": [_lateral_row("B", "Para", 1, points)],
        "lateral_a_passa": [],
        "lateral_b_passa": [],
    }

    result = write_lateral_pages(
        dialog=_FakeDialog(),
        title="Laterais de Viga",
        rows_by_kind=rows_by_kind,
        output_dir=str(tmp_path),
        page_css="",
        javascript="",
        photo_fn=lambda points: "",
        metrics_fn=_segment_geometry_metrics,
    )

    assert result == ("laterais_viga/index.html", "Laterais de Viga", 1)
    page = tmp_path / "laterais_viga" / "V301.html"
    assert page.is_file()
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")

    # 1 página só por viga, não por lado nem por lado×comportamento.
    assert len(list((tmp_path / "laterais_viga").glob("V301*.html"))) == 1

    text = soup.get_text(" ", strip=True)
    assert "Lado A" in text
    assert "Lado B" in text
    assert "N2 completo (ambos os lados)" in text
    assert "N3 completo (1 lado)" in text
    assert "limitação conhecida" in text.lower()

    # N1 por segmento (2: um em cada lado) + N2/N3/N4 por lado (3 x 2 lados) = 8
    assert len(soup.select(".evidence-card svg")) == 8

    # checkbox de erro presente e com a chave certa
    checkbox = soup.select_one("#erro_check")
    textarea = soup.select_one("#erro_nota")
    assert checkbox is not None and checkbox.get("type") == "checkbox"
    assert textarea is not None
    assert "aten_erro_lv_Obra_TESTE_13_PAV_V301" in page.read_text(encoding="utf-8")

    # sidebar expõe data-viga + flag de erro oculta
    sidebar_item = soup.select_one('.sidebar li[data-viga="V301"]')
    assert sidebar_item is not None
    assert sidebar_item.select_one(".erro-flag") is not None

    # vínculos de contexto (apoio/laje) aparecem na ficha N1 do segmento
    assert "Apoio início" in text
    assert "Lajes adjacentes" in text


def test_lateral_writer_marks_missing_n4_side_as_ausente(tmp_path: Path):
    class _DialogMissingN4B(_FakeDialog):
        def _find_beam_dxf(self, class_prefix, item_name, n4=False):
            if n4 and item_name == "V301_B":
                return ""
            return super()._find_beam_dxf(class_prefix, item_name, n4=n4)

    points = [(0, 0), (10, 0)]
    rows_by_kind = {
        "lateral_a_para": [_lateral_row("A", "Para", 1, points)],
        "lateral_b_para": [_lateral_row("B", "Para", 1, points)],
        "lateral_a_passa": [],
        "lateral_b_passa": [],
    }

    write_lateral_pages(
        dialog=_DialogMissingN4B(),
        title="Laterais de Viga",
        rows_by_kind=rows_by_kind,
        output_dir=str(tmp_path),
        page_css="",
        javascript="",
        photo_fn=lambda points: "",
        metrics_fn=_segment_geometry_metrics,
    )

    page_html = (tmp_path / "laterais_viga" / "V301.html").read_text(encoding="utf-8")
    assert "artefato ausente" in page_html
