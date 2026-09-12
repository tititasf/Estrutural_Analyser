import re
from pathlib import Path

from bs4 import BeautifulSoup

from src.ui.widgets.fv_hifi_n1_render import (
    repair_n3_inline_svg,
    sanitize_inline_svg,
    stamp_sa_highlight_attrs,
)
from src.ui.widgets.preficha_fundo_html import (
    _n3_stog_panels_from_rows,
    _parse_dim_wh,
    overlay_n3_segment_tags,
    relayout_existing_fv_page,
    render_n3_svg_from_seg_rows,
    write_fundo_pages,
)
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
        "fields": {
            "viga_fundo_seg_1_largura": 19,
            "viga_fundo_seg_1_dim": "19/50",
            "viga_fundo_seg_2_dim": "19/120",
            "viga_a_seg_1_nivel_viga": "852.12",
            "viga_b_seg_1_nivel_viga": "852.19",
            "altura_h1": 50.0,
            "dimensao": "19/50",
        },
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
    assert "Viewer Unificado N1-N3" in text
    assert "Interpretação dos segmentos" in text
    assert "Nível da viga" in text
    assert "Painéis N3" in text
    assert "fv-seg-item" in raw
    assert "fv-seg-table" in raw
    assert "fv-seg-detail" in raw
    assert "fv-seg-solo" in raw
    assert "fv-sa-ghost-btn" in raw
    assert "fv-sa-ghost" in raw
    assert "_applySaGhostVisual" in raw
    assert "_markSaHl" in raw
    assert "[data-fv-hl='face']" in raw
    assert "fv-pt-btn" in raw
    assert "toggleFvPointMode" in raw
    assert "onFvPointClick" in raw
    assert "Anotações Pontos" in raw
    assert "SA / Camadas" in raw
    assert "fv-points-list" in raw
    assert raw.count("fv-pt-btn") >= 2
    assert "Chanfros" in text
    assert "Aberturas" in text
    assert "× 50" in raw or "50</b>" in raw or ">50<" in raw
    assert "852.19" in raw
    assert "852.12 / 852.19" not in raw
    assert 'data-seg="todos"' in raw
    assert "fv-seg-subtabs" in raw
    assert "fv-ficha-summary" in raw
    notes_at = raw.find('class="fv-ctx-notes"')
    pan_at = raw.find('data-panzoom="1"')
    assert pan_at > 0 and notes_at > pan_at
    assert "<!DOCTYPE svg" not in raw.split("<!--FVCTX_START-->", 1)[-1].split(
        "<!--FVCTX_END-->", 1
    )[0]
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
    assert "Viewer Unificado N1-N3" in text
    assert raw.count('data-seg="todos"') >= 1
    assert "Quantidade de segmentos" in text
    assert "Nível da viga" in text
    assert "Painéis N3" in text
    assert "fv-seg-item" in raw
    assert "fv-seg-table" in raw
    assert "fv-seg-detail" in raw
    assert "fv-seg-solo" in raw
    assert "852.19" in text
    assert "852.12 / 852.19" not in text
    assert ">50<" in raw
    assert ">120<" in raw
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


def test_nivel_viga_uses_highest_value_only():
    from src.ui.widgets.preficha_fundo_html import _niveis_from_beam_fields

    assert _niveis_from_beam_fields({
        "viga_a_seg_1_nivel_viga": "852.12",
        "viga_b_seg_1_nivel_viga": "852.19",
        "nivel_lado_a": 0,
    }) == "852.19"


def test_n3_stog_panels_one_segment_per_ficha_row():
    panels = _n3_stog_panels_from_rows([
        {"label": "1", "comprimento": 305.5, "largura": 19, "ponto_inicial": "P1", "ponto_final": "P9"},
        {"label": "2", "comprimento": 100, "largura": 19, "ponto_inicial": "V312", "ponto_final": "P9"},
    ])
    assert [p["total_width"] for p in panels] == [305.5, 100.0]
    assert [x["width"] for x in panels[0]["panels"]] == [244.0, 61.5]
    assert panels[0]["texto_esq"] == "P1"
    assert panels[1]["texto_dir"] == "P9"


def test_n3_ficha_draw_uses_50cm_gap_and_right_wall_b_dim():
    from src.ui.widgets.preficha_fundo_html import (
        N3_DIM_B_OFFSET_CM,
        N3_SEG_GAP_CM,
        _n3_stog_panels_from_rows,
        _stog_fv_mod,
    )

    panels = _n3_stog_panels_from_rows([
        {"label": "1", "comprimento": 305.5, "largura": 19},
        {"label": "2", "comprimento": 100.0, "largura": 19},
    ])
    stog = _stog_fv_mod()
    doc = stog.setup_doc()
    foot = stog.draw_viga(
        doc.modelspace(),
        0,
        0,
        panels,
        19.0,
        "V301.C",
        inter_segment_gap=N3_SEG_GAP_CM,
        dim_b_every_segment=True,
        dim_b_offset=N3_DIM_B_OFFSET_CM,
        coalesce_junction_labels=True,
    )
    assert abs(foot - (305.5 + 100.0 + N3_SEG_GAP_CM)) < 0.2
    dim_xs = []
    for ent in doc.modelspace():
        if ent.dxftype() != "DIMENSION":
            continue
        try:
            if abs(float(ent.dxf.angle) - 90) < 1:
                dim_xs.append(float(ent.dxf.defpoint.x))
        except Exception:
            continue
    assert any(abs(x - (305.5 + N3_DIM_B_OFFSET_CM)) < 1.5 for x in dim_xs)
    assert any(abs(x - (305.5 + N3_SEG_GAP_CM + 100.0 + N3_DIM_B_OFFSET_CM)) < 1.5 for x in dim_xs)


def test_chain_linear_apoios_replaces_copied_global_end():
    from src.core.fv_generation_contract import chain_linear_segment_apoios

    rows = [
        {"label": "1", "ponto_inicial": "P1", "ponto_final": "P9"},
        {"label": "2", "ponto_inicial": "V312", "ponto_final": "P9"},
        {"label": "3", "ponto_inicial": "P11", "ponto_final": "P9"},
        {"label": "4", "ponto_inicial": "P8", "ponto_final": "P9"},
    ]
    out = chain_linear_segment_apoios(rows)
    assert [r["ponto_final"] for r in out] == ["V312", "P11", "P8", "P9"]


def test_n3_junction_same_apoio_once_different_stacked():
    from src.ui.widgets.preficha_fundo_html import (
        N3_DIM_B_OFFSET_CM,
        N3_SEG_GAP_CM,
        _n3_stog_panels_from_rows,
        _stog_fv_mod,
    )

    stog = _stog_fv_mod()

    def _texts(rows):
        panels = _n3_stog_panels_from_rows(rows)
        doc = stog.setup_doc()
        stog.draw_viga(
            doc.modelspace(), 0, 0, panels, 19.0, "V301.C",
            inter_segment_gap=N3_SEG_GAP_CM,
            dim_b_every_segment=True,
            dim_b_offset=N3_DIM_B_OFFSET_CM,
            coalesce_junction_labels=True,
        )
        return [
            e.dxf.text for e in doc.modelspace()
            if e.dxftype() == "TEXT" and e.dxf.layer == "5"
        ]

    same = _texts([
        {"label": "1", "comprimento": 100, "largura": 19,
         "ponto_inicial": "P1", "ponto_final": "P9"},
        {"label": "2", "comprimento": 100, "largura": 19,
         "ponto_inicial": "P9", "ponto_final": "P2"},
    ])
    assert same.count("P9") == 1
    assert "P1" in same and "P2" in same

    diff = _texts([
        {"label": "1", "comprimento": 100, "largura": 19,
         "ponto_inicial": "P1", "ponto_final": "P9"},
        {"label": "2", "comprimento": 100, "largura": 19,
         "ponto_inicial": "V312", "ponto_final": "P2"},
    ])
    assert "P9" in diff and "V312" in diff
    assert "P1" in diff and "P2" in diff


def test_render_n3_from_ficha_uses_244_modules_and_keeps_stog_style(tmp_path: Path):
    svg = render_n3_svg_from_seg_rows(
        [
            {"label": "1", "comprimento": 305.5, "largura": 19, "ponto_inicial": "P1", "ponto_final": "P9"},
            {"label": "2", "comprimento": 100.0, "largura": 19, "ponto_inicial": "V312", "ponto_final": "P9"},
        ],
        "V301",
        out_svg=str(tmp_path / "V301_n3.svg"),
    )
    assert "<svg" in svg
    tagged = overlay_n3_segment_tags(svg, [
        {"label": "1", "comprimento": 305.5},
        {"label": "2", "comprimento": 100.0},
    ])
    assert tagged.count('class="fv-n3-seg"') == 2
    assert ">S1<" in tagged
    assert ">S2<" in tagged
    assert "fv-n3-panel" not in tagged
    assert "244" in tagged
    assert "305" in tagged
    assert "100" in tagged


def test_overlay_n3_tags_keep_robot_strokes_and_follow_ficha_lengths():
    raw = (
        '<svg viewBox="0 0 1000 40">'
        '<path d="M 50 22 L 950 22 L 950 30 L 50 30 Z" '
        'style="fill:none;stroke:#00ffff;stroke-width:0.6"/>'
        '<path d="M 50 22 L 950 22" style="fill:none;stroke:#ffbf00"/>'
        "</svg>"
    )
    out = overlay_n3_segment_tags(raw, [
        {"label": "1", "comprimento": 300},
        {"label": "2", "comprimento": 100},
    ])
    assert 'stroke:#00ffff' in out
    assert 'stroke:#ffbf00' in out
    assert 'data-n3-composed' not in out
    assert out.count('class="fv-n3-seg"') == 2
    assert ">S1<" in out
    assert ">S2<" in out
    x1 = float(re.search(r'<text class="fv-n3-tag" x="([^"]+)"', out).group(1))
    x2 = float(re.findall(r'<text class="fv-n3-tag" x="([^"]+)"', out)[1])
    assert x1 < x2
    # 300 vs 100 → S1 centroid at 3/8, S2 at 7/8 of the strip
    assert x1 < 450
    assert x2 > 650


def test_n3_panels_split_length_at_244_and_width_at_122():
    from src.ui.widgets.preficha_fundo_html import _n3_panels_for_segment

    panels = _n3_panels_for_segment(305.5, 19)
    assert [p["comprimento"] for p in panels] == [244.0, 61.5]
    assert [p["largura"] for p in panels] == [19.0, 19.0]
    wide = _n3_panels_for_segment(200, 150)
    assert [p["comprimento"] for p in wide] == [200.0, 200.0]
    assert [p["largura"] for p in wide] == [122.0, 28.0]


def test_parse_dim_wh_uses_larger_number_as_beam_height():
    assert _parse_dim_wh("19/50") == ("19", "50")
    assert _parse_dim_wh("25/120") == ("25", "120")
    assert _parse_dim_wh("19/120") == ("19", "120")
    assert _parse_dim_wh("9.2/50") == ("9.2", "50")
    assert _parse_dim_wh("120/19") == ("19", "120")


def test_sanitize_inline_svg_strips_doctype():
    raw = (
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
        '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
        '<svg viewBox="0 0 10 10" width="10" height="10"><circle r="1"/></svg>'
    )
    out = sanitize_inline_svg(raw)
    assert out.startswith("<svg")
    assert "<!DOCTYPE" not in out
    assert "<?xml" not in out


def test_sanitize_inline_svg_drops_empty_clippath_that_hides_geometry():
    raw = (
        '<svg viewBox="0 0 100 20" width="100" height="20">'
        '<path d="M 10 8 L 90 8 L 90 12 L 10 12 Z" '
        'clip-path="url(#p1)" style="fill:#00ffff"/>'
        '<defs><clipPath id="p1"><rect x="1.44" y="1.44"/></clipPath></defs>'
        "</svg>"
    )
    out = sanitize_inline_svg(raw)
    assert "clip-path" not in out
    assert "M 10 8" in out
    assert 'width="100"' not in out.split(">", 1)[0]


def test_repair_n3_inline_svg_crops_viewbox_to_strokes():
    raw = (
        '<svg viewBox="0 0 1154.88 146.88" width="1600" height="200">'
        '<path d="M 0 146.88 L 1154.88 146.88 L 1154.88 0 L 0 0 Z" '
        'style="fill:#212830"/>'
        '<path d="M 60 65 L 400 65 L 400 80 L 60 80 Z" '
        'clip-path="url(#p1)" style="fill:none;stroke:#00ffff"/>'
        '<path d="M 420 65 L 1080 65 L 1080 80 L 420 80 Z" '
        'clip-path="url(#p1)" style="fill:none;stroke:#bf00ff"/>'
        '<defs><clipPath id="p1"><rect x="1.44" y="1.44"/></clipPath></defs>'
        "</svg>"
    )
    out = repair_n3_inline_svg(raw)
    assert "clip-path" not in out
    m = re.search(r'viewBox="([^"]+)"', out)
    assert m
    x, y, w, h = [float(p) for p in m.group(1).split()]
    assert x > 0
    assert y > 0
    assert w < 1100
    assert h < 80


def test_relayout_strips_n3_doctype_and_keeps_unified_layout(tmp_path: Path):
    rows = [
        _fundo_row("1", 1, [(0, 0), (10, 0), (10, 4), (0, 4), (0, 0)]),
        _fundo_row("2", 2, [(10, 0), (20, 0), (20, 4), (10, 4), (10, 0)]),
    ]
    write_fundo_pages(
        dialog=_FakeDialog(),
        title="Fundos",
        rows=rows,
        output_dir=str(tmp_path),
        page_css="",
        javascript="",
        photo_fn=lambda points: "",
        metrics_fn=_segment_geometry_metrics,
    )
    page = tmp_path / "fundos_viga" / "V301.html"
    raw = page.read_text(encoding="utf-8")
    poisoned = raw.replace(
        '<div class="fv-layer fv-layer-n3 fv-layer-hidden" data-visible="0"',
        '<div class="fv-layer fv-layer-n3 fv-layer-hidden" data-visible="0"',
        1,
    )
    poisoned = poisoned.replace(
        '<div class="fv-layer fv-layer-n3 fv-layer-hidden" data-visible="0" data-n3-src="n3/V301_n3.svg">',
        '<div class="fv-layer fv-layer-n3 fv-layer-hidden" data-visible="0" data-n3-src="n3/V301_n3.svg">'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">',
        1,
    )
    if "<!DOCTYPE svg" not in poisoned:
        poisoned = raw.replace(
            "<svg viewBox",
            '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "x"><svg viewBox',
            1,
        )
    out = relayout_existing_fv_page(
        poisoned, n3_dir=str(tmp_path / "fundos_viga" / "n3")
    )
    ctx = out.split("<!--FVCTX_START-->", 1)[1].split("<!--FVCTX_END-->", 1)[0]
    assert "<!DOCTYPE svg" not in ctx
    assert "Viewer Unificado N1-N3" in out
    assert "Interpretação dos segmentos" in out
    assert out.find("data-panzoom") < out.find('class="fv-ctx-notes"')
    assert 'data-seg="todos"' in out
    assert 'data-seg="1"' in out
    assert 'data-seg="2"' in out


def test_stamp_sa_highlight_attrs_marks_face_edge_and_leaves_tags():
    svg = """
    <svg>
     <path d="M 0 0 L 10 0 L 10 4 L 0 4 z"
      style="fill: #e53935; opacity: 0.38"/>
     <path d="M 0 0 L 10 0 L 10 4 L 0 4 z"
      style="fill: none; stroke: #ff1744; stroke-width: 0.5; stroke-linejoin: miter"/>
     <path d="M 1 1 L 2 1 L 2 2 L 1 2 z"
      style="fill: #b71c1c; opacity: 0.95; stroke: #ff8a80; stroke-linejoin: miter"/>
     <path d="M 0 0 L 1 1"
      style="fill: none; stroke: #ff1744; stroke-width: 0.7; stroke-linecap: round"/>
    </svg>
    """
    out = stamp_sa_highlight_attrs(svg)
    assert out.count('data-fv-hl="face"') == 1
    assert out.count('data-fv-hl="edge"') == 1
    assert out.count('data-fv-hl="tag"') == 1
    assert 'stroke-width: 0.7' in out
    assert out == stamp_sa_highlight_attrs(out)
