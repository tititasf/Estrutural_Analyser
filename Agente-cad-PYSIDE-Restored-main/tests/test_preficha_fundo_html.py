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
                "contour": [{
                    "points": [(0, 0), (10, 0), (10, 4), (0, 4)],
                    "evidence_segments": [{"source_segment": 1}],
                }]
            },
            "viga_fundo_seg_1_local_ini": {
                "label": [{"text": "P1", "scope": "segment_local"}]
            },
            "viga_fundo_seg_1_local_fim": {
                "label": [{"text": "P2", "scope": "segment_local"}]
            },
            "apoios": {
                "inicio": [{"text": "P1", "scope": "beam_global"}],
                "fim": [{"text": "P2", "scope": "beam_global"}],
            },
        },
    }]

    def _find_beam_dxf(self, class_prefix, item_name, n4=False):
        return f'{"n4" if n4 else "n3"}_{class_prefix}_{item_name}.dxf'

    def _find_n2_recorte_dxf(self, class_prefix, item_name):
        return f"n2_{class_prefix}_{item_name}.dxf"

    def _render_fv_hifi_n1_svg(self, segments, mode="local", **kwargs):
        assert mode in {"local", "contextual"}
        assert segments
        if mode == "local":
            lab = segments[0].get("label", "1")
            return (
                f'<svg viewBox="0 0 10 10" class="img-fv-hifi" role="img" '
                f'aria-label="N1 / SA local" alt="N1 / SA local">'
                f"<text>S{lab}</text></svg>"
            )
        return (
            '<svg viewBox="0 0 10 10" class="img-fv-hifi" role="img" '
            'aria-label="N1 / SA contextual" alt="N1 / SA contextual">'
            "<text>CTX</text></svg>"
        )

    def _render_pilar_dxf_context_b64(
        self, points, width=1000, height=680, focus_mode="pillar", fmt="png", **kwargs
    ):
        # Legado (outras classes / fallback) — FV usa _render_fv_hifi_n1_svg
        assert focus_mode == "segment"
        assert fmt == "svg"
        return '<svg viewBox="0 0 10 10"><text>SA</text></svg>'

    def _render_ezdxf_b64(self, path, width=950, height=620, fmt="png"):
        assert (width, height) == (1900, 1240)
        if fmt == "svg":
            return '<svg viewBox="0 0 10 10"><text>DXF</text></svg>'
        return "RFhG"

    def _n2_ficha_html(self, class_prefix, item_name):
        return "<table><tr><td>N2 completo</td></tr></table>"

    def _n3_ficha_html_beam(self, class_prefix, item_name):
        return "<table><tr><td>N3 completo</td></tr></table>"


def _fundo_row(label: str, segment_index: int, points: list[tuple]) -> dict:
    return {
        "Comprimento": "10.0",
        "Largura": "4",
        "Status": "valid",
        "Atenção": "",
        "_beam": "V301",
        "_points": points,
        "_segment": {
            "uid": f"fundo|beam-1|{segment_index}|1",
            "beam_name": "V301",
            "beam_identity": "beam-1",
            "segment_label": label,
            "segment_index": segment_index,
            "occurrence": 1,
            "side": "Fundo",
            "behavior": "Fundo",
            "length": 10.0,
            "width": "4",
            "points": points,
            "source_key": f"viga_fundo_seg_{segment_index}_area_segs",
            "source_slot": "contour",
            "tag": "Fundo",
            "ficha": {"largura_total_fundo": 4},
        },
    }


def test_fundo_writer_creates_granular_page_with_four_visual_stages(tmp_path: Path):
    rows = [_fundo_row(
        "1", 1, [(0, 0), (10, 0), (10, 4), (0, 4), (0, 0)]
    )]

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
    page = tmp_path / "fundos_viga" / "V301.html"
    raw = page.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")
    # 1 local + 1 contextual HI-FI + N2 + N3 + N4
    assert len(soup.select("svg")) >= 5
    assert len(soup.select('svg[alt="N1 / SA local"]')) == 1
    assert len(soup.select('svg[alt="N1 / SA contextual"]')) == 1
    assert "data-panzoom" in raw
    assert "fv-hifi-panzoom" in raw or "initPanZoom" in raw
    assert "<!--FVCTX_START-->" in raw
    style = soup.style.get_text()
    assert "grid-template-columns:1fr!important" in style
    assert "max-height:none!important" in style
    text = soup.get_text(" ", strip=True)
    assert "N1 / SA" in text
    assert "Contextual unificado" in text
    assert "N2 / STOG real" in text
    assert "N3 / Robô SA" in text
    assert "N3 / NOVA" in text
    assert "N4 / Robô ER" in text
    assert "Vértices brutos do contorno" in text
    assert "evidence_segments" in text
    assert "apoios locais do segmento" in text
    assert "limites globais da viga" in text
    assert "furos/recortes no contexto local" in text
    assert "Quality gates da viga FV" in text
    assert "Marcar esta ficha como ERRADA" in text
    assert soup.select_one("#erro_check") is not None
    assert soup.select_one("#erro_nota") is not None
    assert "aten_erro_fv_Obra_TESTE_13_PAV_V301" in raw
    sidebar_item = soup.select_one('.sidebar li[data-viga="V301"]')
    assert sidebar_item is not None
    assert sidebar_item.select_one(".erro-flag") is not None
    # 1 local note + 1 ctx note (+ optional error fields)
    assert len(soup.select("[data-atkey]")) >= 2


def test_fundo_writer_groups_segments_and_renders_shared_stages_once(tmp_path: Path):
    rows = [
        _fundo_row("1", 1, [(0, 0), (10, 0), (10, 4), (0, 4), (0, 0)]),
        _fundo_row("2", 2, [(10, 0), (20, 0), (20, 4), (10, 4), (10, 0)]),
    ]

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
    section = tmp_path / "fundos_viga"
    assert (section / "V301.html").is_file()
    assert not (section / "V301_1.html").exists()
    assert not (section / "V301_2.html").exists()

    raw = (section / "V301.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")
    # Locais por segmento; contextual unificado UMA vez (não isolado)
    assert len(soup.select('svg[alt="N1 / SA local"]')) == 2
    assert len(soup.select('svg[alt="N1 / SA contextual"]')) == 1
    assert raw.count("data-panzoom") >= 3  # 1 ctx + 2 local
    assert len(soup.select('svg[alt="N2"]')) == 1
    assert len(soup.select('svg[alt="N3 / NOVA"]')) == 1
    assert len(soup.select('svg[alt="N4"]')) == 1
    text = soup.get_text(" ", strip=True)
    assert "segmento 1" in text
    assert "segmento 2" in text
    assert "Contextual unificado" in text
    assert text.count("N2 completo") == 1
    assert text.count("N3 completo") == 1
    # 2 local notes + 1 ctx note
    assert len(soup.select("[data-atkey]")) >= 3


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
