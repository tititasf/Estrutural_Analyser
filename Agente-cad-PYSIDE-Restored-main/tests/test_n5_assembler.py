from pathlib import Path

import ezdxf

from src.core.n5_assembler import _entity_bbox, assemble_n5
from scripts.visual_modes import apply_visual_mode


def _make_fv_preview(path: Path, x0: float = 1000.0, add_dim: bool = False) -> None:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(x0, 0), (x0 + 200, 0), (x0 + 200, 20), (x0, 20)],
        close=True,
        dxfattribs={"layer": "Paineis"},
    )
    msp.add_text("V1", dxfattribs={"insert": (x0, 35), "height": 12, "layer": "NOMENCLATURA"})
    if add_dim:
        dim = msp.add_linear_dim(
            base=(x0 + 100, -20),
            p1=(x0, 0),
            p2=(x0 + 200, 0),
            angle=0,
            dxfattribs={"layer": "COTA"},
        )
        dim.render()
    msp.add_line((-9500, 0), (-9490, 0), dxfattribs={"layer": "Escoras"})
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)


def test_assemble_fv_n5_ignores_off_frame_sentinel_entities(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_fv_preview(fase6 / "FV_preview_V1.dxf")

    result = assemble_n5(obra, "FV", item_ids=["V1"], pavimento="PAV")

    assert result.ok_count == 1
    out_doc = ezdxf.readfile(str(result.output_path))
    bb = _entity_bbox(out_doc)
    assert bb is not None
    assert bb[0] >= 0
    assert not any(
        entity.dxftype() == "LINE" and entity.dxf.start.x < -5000 and entity.dxf.end.x < -5000
        for entity in out_doc.modelspace()
    )


def test_assemble_fv_n5_resolves_virtual_item_aliases(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_fv_preview(fase6 / "FV_preview_V2.dxf")

    result = assemble_n5(obra, "FV", item_ids=["V2.C-1_Para"], pavimento="PAV")

    assert result.ok_count == 1
    assert result.items[0].status == "ok"
    assert result.items[0].source.endswith("FV_preview_V2.dxf")


def test_assemble_fv_n5_preserves_dimension_geometry(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_fv_preview(fase6 / "FV_preview_V3.dxf", add_dim=True)

    result = assemble_n5(obra, "FV", item_ids=["V3"], pavimento="PAV")

    assert result.ok_count == 1
    out_doc = ezdxf.readfile(str(result.output_path))
    dims = list(out_doc.modelspace().query("DIMENSION"))
    assert len(dims) == 1
    assert dims[0].dxf.geometry
    assert any(block.name.upper().startswith("*D") for block in out_doc.blocks)


def _make_sarrafo_preview(path: Path, layer: str = "SARR_2.2x7") -> None:
    doc = ezdxf.new("R2018")
    doc.layers.add(layer, color=40)
    doc.modelspace().add_line(
        (0, 0), (100, 0), dxfattribs={"layer": layer}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)


def test_assemble_pl_n5_accepts_zone_previews_and_applies_ini(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    source = fase6 / "PL_CIMA_preview_P1.dxf"
    _make_sarrafo_preview(source)

    result = assemble_n5(
        obra, "PL", item_ids=["P1"], pavimento="PAV", visual_mode="INI"
    )

    assert result.ok_count == 1
    assert result.items[0].source.endswith("PL_CIMA_preview_P1.dxf")
    out_doc = ezdxf.readfile(str(result.output_path))
    mlines = list(out_doc.modelspace().query("MLINE"))
    assert len(mlines) == 1
    assert mlines[0].dxf.scale_factor == 2.2
    style = out_doc.mline_styles.get("SAR3")
    assert style.dxf.flags & style.FILL


def test_assemble_pl_n5_combines_separate_zone_previews(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_sarrafo_preview(fase6 / "PL_CIMA_preview_P2.dxf")
    _make_sarrafo_preview(fase6 / "PL_ABCD_preview_P2.dxf")

    result = assemble_n5(
        obra, "PL", item_ids=["P2"], pavimento="PAV", visual_mode="NOVA"
    )

    assert result.ok_count == 1
    assert "2 preview(s)" in result.items[0].message
    out_doc = ezdxf.readfile(str(result.output_path))
    assert len(list(out_doc.modelspace().query("LINE"))) == 2


def test_assemble_lv_n5_nova_does_not_change_sarrafo_geometry(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_sarrafo_preview(fase6 / "LV_preview_V1_A.dxf")

    result = assemble_n5(
        obra, "LV", item_ids=["V1_A"], pavimento="PAV", visual_mode="NOVA"
    )

    out_doc = ezdxf.readfile(str(result.output_path))
    assert not list(out_doc.modelspace().query("MLINE"))
    assert len(list(out_doc.modelspace().query("LINE"))) == 1


def test_assemble_fv_n5_preserves_existing_mline(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    source = fase6 / "FV_preview_V4.dxf"
    _make_sarrafo_preview(source)
    source_doc = ezdxf.readfile(str(source))
    apply_visual_mode(source_doc, "INI", "FV")
    source_doc.saveas(source)

    result = assemble_n5(
        obra, "FV", item_ids=["V4"], pavimento="PAV", visual_mode="INI"
    )

    out_doc = ezdxf.readfile(str(result.output_path))
    mlines = list(out_doc.modelspace().query("MLINE"))
    assert len(mlines) == 1
    style = out_doc.mline_styles.get("SAR3")
    assert style.dxf.flags & style.FILL
