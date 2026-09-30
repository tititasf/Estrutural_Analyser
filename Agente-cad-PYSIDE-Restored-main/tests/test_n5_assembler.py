import json
import sqlite3
from pathlib import Path

import ezdxf

from src.core.n5_assembler import _entity_bbox, assemble_n5, _discover_item_ids, _find_n3_preview
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


def _make_lj_preview(path: Path, x0: float = 0.0, y0: float = 0.0) -> None:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(x0, y0), (x0 + 418, y0), (x0 + 418, y0 + 122), (x0, y0 + 122)],
        close=True,
        dxfattribs={"layer": "PAINEIS"},
    )
    # Dimension geometry extends beyond the panel and must not define its anchor.
    msp.add_line(
        (x0, y0 - 30),
        (x0 + 418, y0 - 30),
        dxfattribs={"layer": "COTA"},
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)


def test_lj_n5_records_ini_without_changing_current_geometry(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    run = obra / "Fase-6_Execucao_CAD" / "production_sa" / "13_PAV" / "run-ini"
    preview = run / "n3" / "dxf" / "LJ_preview_L1.dxf"
    _make_lj_preview(preview, x0=10.0, y0=20.0)
    (run / "production_manifest.json").write_text(
        json.dumps({"visual_mode": "INI"}), encoding="utf-8",
    )

    result = assemble_n5(
        obra, "LJ", item_ids=["L1"], pavimento="13_PAV", visual_mode="INI",
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["visual_mode"] == "INI"
    assert result.output_path.name == "N5_LJ_13_PAV_INI.dxf"
    assert result.manifest_path.name == "N5_LJ_13_PAV_INI.json"
    assert result.ok_count == 1
    assert len(list(ezdxf.readfile(result.output_path).modelspace())) > 0


def _make_lj_stepped_preview(
    path: Path, *, x0: float, y0: float, width: float, body_height: float,
    downward_step: float,
) -> None:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [
            (x0, y0 + downward_step),
            (x0 + width * 0.75, y0 + downward_step),
            (x0 + width * 0.75, y0),
            (x0 + width, y0),
            (x0 + width, y0 + downward_step + body_height),
            (x0, y0 + downward_step + body_height),
        ],
        close=True,
        dxfattribs={"layer": "PAINEIS"},
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)


def test_assemble_lj_n5_uses_sa_panel_position_not_dimension_bbox(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_lj_preview(fase6 / "LJ_preview_L312.dxf", x0=4041.07, y0=2280.94)

    result = assemble_n5(
        obra,
        "LJ",
        item_ids=["L312"],
        pavimento="13_PAV",
        item_positions={"L312": (2496.5, 2680.0)},
    )

    assert result.ok_count == 1
    out_doc = ezdxf.readfile(str(result.output_path))
    panel = list(out_doc.modelspace().query('LWPOLYLINE[layer=="PAINEIS"]'))[0]
    xs = [point[0] for point in panel.vertices()]
    ys = [point[1] for point in panel.vertices()]
    assert min(xs) == 2496.5
    assert min(ys) == 2680.0


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


def test_assemble_fv_n5_reads_latest_production_sa_run(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    production = obra / "Fase-6_Execucao_CAD" / "production_sa" / "13_PAV"
    old = production / "20260913_120000_1" / "n3" / "dxf" / "FV_preview_V8.dxf"
    latest = production / "20260914_120000_2" / "n3" / "dxf" / "FV_preview_V8.dxf"
    _make_fv_preview(old, x0=100)
    _make_fv_preview(latest, x0=800)

    assert "V8" in _discover_item_ids(obra, "FV", "13_PAV")
    assert _find_n3_preview(obra, "FV", "V8", "13_PAV") == latest
    result = assemble_n5(obra, "FV", pavimento="13_PAV")

    assert result.ok_count == 1
    assert result.missing_count == 0
    assert result.items[0].source == str(latest)


def test_assemble_fv_n5_prefers_web_production_over_legacy_root(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    legacy = fase6 / "FV_preview_V8.dxf"
    current = (
        fase6 / "production_sa" / "13_PAV" / "20260914_120000_2"
        / "n3" / "dxf" / "FV_preview_V8.dxf"
    )
    _make_fv_preview(legacy, x0=100)
    _make_fv_preview(current, x0=800)

    assert _find_n3_preview(obra, "FV", "V8", "13_PAV") == current
    result = assemble_n5(obra, "FV", item_ids=["V8"], pavimento="13_PAV")

    assert result.ok_count == 1
    assert result.items[0].source == str(current)


def test_assemble_lj_n5_prefers_web_production_geometry_over_legacy_root(tmp_path):
    obra = tmp_path / "Obra_TESTE"
    fase6 = obra / "Fase-6_Execucao_CAD"
    legacy = fase6 / "LJ_preview_L312.dxf"
    current = (
        fase6 / "production_sa" / "13_PAV" / "20260917_120000_2"
        / "n3" / "dxf" / "LJ_preview_L312.dxf"
    )
    _make_lj_preview(legacy, x0=100, y0=100)
    _make_lj_stepped_preview(
        current,
        x0=800,
        y0=200,
        width=650,
        body_height=210,
        downward_step=35,
    )

    assert "L312" in _discover_item_ids(obra, "LJ", "13_PAV")
    assert _find_n3_preview(obra, "LJ", "L312", "13_PAV") == current
    result = assemble_n5(
        obra,
        "LJ",
        item_ids=["L312"],
        pavimento="13_PAV",
        item_positions={"L312": (1200, 900)},
    )

    assert result.ok_count == 1
    assert result.items[0].source == str(current)
    out_doc = ezdxf.readfile(str(result.output_path))
    panel = list(out_doc.modelspace().query('LWPOLYLINE[layer=="PAINEIS"]'))[0]
    xs = [point[0] for point in panel.vertices()]
    ys = [point[1] for point in panel.vertices()]
    assert max(xs) - min(xs) == 650
    assert max(ys) - min(ys) == 245


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
    mode_root = fase6 / "n3_modes" / "INI" / "pilares"
    ordered = [
        ("para", "CIMA"),
        ("passa", "ABCD"),
        ("passa", "GRADES"),
        ("para", "ABCD"),
        ("para", "GRADES"),
    ]
    sources = []
    for semantic, part in ordered:
        source = mode_root / semantic / f"PL_{part}_preview_P1.dxf"
        _make_sarrafo_preview(source)
        sources.append(source)

    result = assemble_n5(
        obra, "PL", item_ids=["P1"], pavimento="PAV", visual_mode="INI"
    )

    assert result.ok_count == 1
    assert result.items[0].source.split(";") == [str(path) for path in sources]
    out_doc = ezdxf.readfile(str(result.output_path))
    mlines = list(out_doc.modelspace().query("MLINE"))
    assert len(mlines) == 5
    assert all(entity.dxf.scale_factor == 7.0 for entity in mlines)
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


def _make_pillar_production_set(
    obra: Path, run: str, item_id: str, local_x: float = 0.0,
) -> list[Path]:
    base = obra / "Fase-6_Execucao_CAD" / "production_sa" / "13_PAV" / run / "n3" / "pil"
    ordered = [
        ("para", "CIMA"),
        ("passa", "ABCD"),
        ("passa", "GRADES"),
        ("para", "ABCD"),
        ("para", "GRADES"),
    ]
    paths = []
    for index, (mode, part) in enumerate(ordered, start=1):
        path = base / mode / f"PL_{part}_preview_{item_id}.dxf"
        doc = ezdxf.new("R2018")
        doc.modelspace().add_line(
            (local_x, index * 10),
            (local_x + 40 + index, index * 10),
            dxfattribs={"layer": f"VISTA_{index}"},
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(path)
        paths.append(path)
    return paths


def test_assemble_pl_n5_uses_five_current_views_in_contract_order(tmp_path):
    obra = tmp_path / "Obra_PL_PROD"
    expected = _make_pillar_production_set(obra, "20260917_120000", "P1", local_x=9000)
    # Um combinado legado nao pode substituir a publicacao granular atual.
    _make_sarrafo_preview(obra / "Fase-6_Execucao_CAD" / "PL_preview_P1.dxf")

    result = assemble_n5(obra, "PL", item_ids=["P1"], pavimento="13_PAV")

    assert result.ok_count == 1
    assert result.items[0].source.split(";") == [str(path) for path in expected]
    assert "5 preview(s)" in result.items[0].message
    out_doc = ezdxf.readfile(str(result.output_path))
    lines = list(out_doc.modelspace().query("LINE"))
    assert len(lines) == 5
    assert [line.dxf.layer for line in lines] == [f"VISTA_{n}" for n in range(1, 6)]
    assert all(
        lines[index].dxf.start.x < lines[index + 1].dxf.start.x
        for index in range(4)
    )


def test_pl_split_groups_share_cima_and_preserve_native_views(tmp_path):
    obra = tmp_path / "Obra_PL_SPLIT"
    _make_pillar_production_set(obra, "20260930_120000", "P1", local_x=9000)
    for group, expected in [("PARA", [1, 4, 5]), ("PASSA", [1, 2, 3])]:
        result = assemble_n5(obra, "PL", item_ids=["P1"], pavimento="13_PAV", pillar_group=group)
        assert result.ok_count == 1 and result.missing_count == 0
        assert result.output_path.name == f"N5_PL_13_PAV_NOVA_{group}.dxf"
        lines = list(ezdxf.readfile(result.output_path).modelspace().query("LINE"))
        assert [line.dxf.layer for line in lines] == [f"VISTA_{n}" for n in expected]
        assert [round(line.dxf.end.x - line.dxf.start.x) for line in lines] == [40+n for n in expected]
        assert len(result.items[0].source.split(";")) == 3


def test_assemble_pl_n5_preserves_each_preview_native_scale(tmp_path):
    """N5 deve apenas posicionar: CIMA 2x e demais vistas 1x ficam intactas."""
    obra = tmp_path / "Obra_PL_SCALE"
    base = (
        obra
        / "Fase-6_Execucao_CAD"
        / "production_sa"
        / "13_PAV"
        / "20260917_120000"
        / "n3"
        / "pil"
    )
    ordered = [
        ("para", "CIMA", 200.0),
        ("passa", "ABCD", 100.0),
        ("passa", "GRADES", 100.0),
        ("para", "ABCD", 100.0),
        ("para", "GRADES", 100.0),
    ]
    for index, (mode, part, length) in enumerate(ordered, start=1):
        path = base / mode / f"PL_{part}_preview_P1.dxf"
        doc = ezdxf.new("R2018")
        doc.modelspace().add_line(
            (0, index * 10),
            (length, index * 10),
            dxfattribs={"layer": f"ESCALA_{index}"},
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(path)

    result = assemble_n5(obra, "PL", item_ids=["P1"], pavimento="13_PAV")

    assert result.ok_count == 1
    out_doc = ezdxf.readfile(str(result.output_path))
    lengths = [
        round((line.dxf.end - line.dxf.start).magnitude, 6)
        for line in out_doc.modelspace().query("LINE")
    ]
    assert lengths == [200.0, 100.0, 100.0, 100.0, 100.0]


def test_assemble_pl_n5_prefers_complete_web_variants_over_older_run(tmp_path):
    obra = tmp_path / "Obra_PL_ALIAS"
    _make_pillar_production_set(obra, "20260917_120000", "P26", local_x=9000)
    variants = obra / "Fase-6_Execucao_CAD" / "n3_variants"
    ordered = [
        ("para", "CIMA"),
        ("passa", "ABCD"),
        ("passa", "GRADES"),
        ("para", "ABCD"),
        ("para", "GRADES"),
    ]
    expected = []
    for index, (mode, part) in enumerate(ordered, start=1):
        path = variants / mode / f"PL_{part}_preview_P26.dxf"
        doc = ezdxf.new("R2018")
        doc.modelspace().add_line((0, 0), (100 + index, 0))
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(path)
        expected.append(path)

    result = assemble_n5(obra, "PL", item_ids=["P26"], pavimento="13_PAV")

    assert result.ok_count == 1
    assert result.items[0].source.split(";") == [str(path) for path in expected]


def test_assemble_pl_n5_places_exactly_one_pillar_per_row(tmp_path):
    obra = tmp_path / "Obra_PL_ROWS"
    _make_pillar_production_set(obra, "20260917_120000", "P1", local_x=8000)
    _make_pillar_production_set(obra, "20260917_120000", "P2", local_x=-4000)

    result = assemble_n5(
        obra, "PL", item_ids=["P1", "P2"], pavimento="13_PAV"
    )

    assert result.ok_count == 2
    out_doc = ezdxf.readfile(str(result.output_path))
    lines = list(out_doc.modelspace().query("LINE"))
    assert len(lines) == 10
    first_row = lines[:5]
    second_row = lines[5:]
    assert len({round(line.dxf.start.y, 6) for line in first_row}) == 1
    assert len({round(line.dxf.start.y, 6) for line in second_row}) == 1
    assert first_row[0].dxf.start.y > second_row[0].dxf.start.y
    assert all(
        row[index].dxf.start.x < row[index + 1].dxf.start.x
        for row in (first_row, second_row)
        for index in range(4)
    )


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
    run = fase6 / "production_sa" / "PAV" / "20260918_120000"
    source = run / "n3" / "dxf" / "FV_preview_V4.dxf"
    _make_sarrafo_preview(source)
    source_doc = ezdxf.readfile(str(source))
    apply_visual_mode(source_doc, "INI", "FV")
    source_doc.saveas(source)
    (run / "production_manifest.json").write_text(
        json.dumps({"visual_mode": "INI"}), encoding="utf-8"
    )

    result = assemble_n5(
        obra, "FV", item_ids=["V4"], pavimento="PAV", visual_mode="INI"
    )

    out_doc = ezdxf.readfile(str(result.output_path))
    mlines = list(out_doc.modelspace().query("MLINE"))
    assert len(mlines) == 1
    style = out_doc.mline_styles.get("SAR3")
    assert style.dxf.flags & style.FILL
    assert mlines[0].dxf.style_handle == style.dxf.handle
    assert list(mlines[0].virtual_entities())


# --------------------------------------------------------------------------- #
# P5 — item manual no disco + completude DB (não some em silêncio)
# --------------------------------------------------------------------------- #

def test_discover_inclui_recorte_web_manual(tmp_path):
    obra = tmp_path / "Obra_WEB"
    rec = obra / "Fase-2_Triagem" / "recortes_web" / "13_PAV" / "PIL_P900.dxf"
    rec.parent.mkdir(parents=True)
    rec.write_text("0\nSECTION\n", encoding="utf-8")
    ids = _discover_item_ids(obra, "PL")
    assert "P900" in ids
    assert _find_n3_preview(obra, "PL", "P900") == rec


def test_assemble_n5_item_no_banco_sem_preview_vira_missing(tmp_path):
    """G-3: item no DB sem N3 no disco → missing_count > 0 (não ok_count verde)."""
    obra = tmp_path / "Obra_DB"
    obra.mkdir()
    db = tmp_path / "sa.vision"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "obra_name TEXT, pavimento TEXT, classe TEXT, elemento_id TEXT, status TEXT)"
    )
    conn.execute(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?)",
        (obra.name, "13_PAV", "PIL", "P900", "manual"),
    )
    conn.commit()
    conn.close()

    result = assemble_n5(obra, "PL", pavimento="13_PAV", db_path=db)
    assert result.missing_count == 1
    assert result.ok_count == 0
    assert result.items[0].item_id == "P900"
    assert result.items[0].status == "missing"


def test_assemble_n5_item_manual_com_preview_entra_ok(tmp_path):
    obra = tmp_path / "Obra_DB2"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_sarrafo_preview(fase6 / "PL_preview_P901.dxf")
    db = tmp_path / "sa2.vision"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "obra_name TEXT, pavimento TEXT, classe TEXT, elemento_id TEXT, status TEXT)"
    )
    conn.execute(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?)",
        (obra.name, "13_PAV", "PIL", "P901", "manual"),
    )
    conn.commit()
    conn.close()

    result = assemble_n5(obra, "PL", pavimento="13_PAV", db_path=db)
    assert result.ok_count == 1
    assert result.missing_count == 0
    assert result.items[0].item_id == "P901"


def test_assemble_n5_filtra_itens_de_outro_pavimento_e_audita_extras(tmp_path):
    obra = tmp_path / "Obra_PURA"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_sarrafo_preview(fase6 / "PL_preview_P1.dxf")
    _make_sarrafo_preview(fase6 / "PL_preview_P101.dxf")
    db = tmp_path / "sa_pura.vision"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "obra_name TEXT, pavimento TEXT, classe TEXT, elemento_id TEXT, status TEXT)"
    )
    conn.execute(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?)",
        (obra.name, "13_PAV", "PIL", "P1", "draft"),
    )
    conn.commit()
    conn.close()

    result = assemble_n5(obra, "PL", pavimento="13_PAV", db_path=db)

    assert [item.item_id for item in result.items] == ["P1"]
    assert result.extra_ids == ["P101"]
    assert result.extra_count == 1
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["extra_count"] == 1
    assert manifest["extra_ids"] == ["P101"]


def test_assemble_lj_n5_carrega_posicao_stog_do_banco(tmp_path):
    obra = tmp_path / "Obra_LJ_DB"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_lj_preview(fase6 / "LJ_preview_L301.dxf", x0=0, y0=0)
    db = tmp_path / "sa_lj.vision"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "obra_name TEXT, pavimento TEXT, classe TEXT, elemento_id TEXT, "
        "status TEXT, campos_json TEXT)"
    )
    conn.execute(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?,?)",
        (obra.name, "13_PAV", "LAJ", "L301", "draft", json.dumps({
            "coordenadas": [[0, 0], [418, 0], [418, 122], [0, 122]],
            "_stog_pose": {"x": 2742.57, "y": 2610.94},
        })),
    )
    conn.commit()
    conn.close()

    result = assemble_n5(obra, "LJ", pavimento="13_PAV", db_path=db)

    assert result.ok_count == 1
    out_doc = ezdxf.readfile(str(result.output_path))
    panel = list(out_doc.modelspace().query('LWPOLYLINE[layer=="PAINEIS"]'))[0]
    assert min(point[0] for point in panel.vertices()) == 2742.57
    assert min(point[1] for point in panel.vertices()) == 2610.94


def test_assemble_lj_n5_alinha_topo_quando_degrau_desce_abaixo_do_corpo(tmp_path):
    obra = tmp_path / "Obra_LJ_DEGRAU"
    fase6 = obra / "Fase-6_Execucao_CAD"
    _make_lj_preview(fase6 / "LJ_preview_L316.dxf", x0=100, y0=100)
    _make_lj_preview(fase6 / "LJ_preview_L317.dxf", x0=100, y0=100)
    _make_lj_stepped_preview(
        fase6 / "LJ_preview_L318.dxf",
        x0=100,
        y0=51,
        width=3139,
        body_height=152,
        downward_step=49,
    )
    db = tmp_path / "sa_lj_degrau.vision"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE reverse_eng_fichas ("
        "obra_name TEXT, pavimento TEXT, classe TEXT, elemento_id TEXT, "
        "status TEXT, campos_json TEXT)"
    )
    common = {
        "coordenadas": [[0, 0], [418, 0], [418, 122], [0, 122]],
        "_stog_pose": {"x": 1000, "y": 500},
    }
    stepped = {
        "coordenadas": [[0, 0], [3139, 0], [3139, 152], [0, 152]],
        "comprimento": 3139,
        "largura": 152,
        "_stog_pose": {"x": 1000, "y": 500},
    }
    conn.executemany(
        "INSERT INTO reverse_eng_fichas VALUES (?,?,?,?,?,?)",
        [
            (obra.name, "13_PAV", "LAJ", "L316", "draft", json.dumps(common)),
            (obra.name, "13_PAV", "LAJ", "L317", "draft", json.dumps(common)),
            (obra.name, "13_PAV", "LAJ", "L318", "draft", json.dumps(stepped)),
        ],
    )
    conn.commit()
    conn.close()

    result = assemble_n5(obra, "LJ", pavimento="13_PAV", db_path=db)

    assert result.ok_count == 3
    out_doc = ezdxf.readfile(str(result.output_path))
    panels = list(out_doc.modelspace().query('LWPOLYLINE[layer=="PAINEIS"]'))
    l318 = max(panels, key=lambda panel: max(p[0] for p in panel.vertices()))
    ys = [point[1] for point in l318.vertices()]
    assert max(ys) == 652.0  # topo do corpo: pose y + largura logica
    assert min(ys) == 451.0  # o degrau continua 49 cm abaixo, sem deformacao


def test_pl_n5_excludes_nasce_even_with_explicit_ids_and_old_drawings(tmp_path):
    from src.core.pillar_sa_review import save
    obra = tmp_path / "Obra_PL_SA"
    _make_pillar_production_set(obra, "20260930_120000", "P1")
    _make_pillar_production_set(obra, "20260930_120000", "P2")
    (obra / "estado_13_PAV.json").write_text(json.dumps({"pilares": [
        {"name": "P1", "classification": "NASCE"}, {"name": "P2", "classification": "SEGUE"}
    ]}))
    result = assemble_n5(obra, "PL", item_ids=["P1", "P2"], pavimento="13_PAV")
    assert [item.item_id for item in result.items] == ["P2"]
    assert result.ok_count == 1
    save(obra, "13_PAV", "P1", {"classificacao": "MORRE"})
    result = assemble_n5(obra, "PL", item_ids=["P1", "P2"], pavimento="13_PAV")
    assert [item.item_id for item in result.items] == ["P1", "P2"]
    assert result.ok_count == 2


def test_preflight_blocks_other_mode_and_partial_pillar_sources(tmp_path):
    from src.core.n5_assembler import n3_mode_readiness
    obra = tmp_path / "Obra_modes"
    _make_pillar_production_set(obra, "001", "P1")
    (obra / "estado_13_PAV.json").write_text(json.dumps({"pilares": [
        {"name": "P1", "classification": "SEGUE"}, {"name": "P2", "classification": "NASCE"}
    ]}))
    assert n3_mode_readiness(obra, "PL", "13_PAV", "NOVA")["ready"]
    assert n3_mode_readiness(obra, "PL", "13_PAV", "INI")["missing"] == ["P1"]
    run = obra / "Fase-6_Execucao_CAD" / "production_sa" / "13_PAV" / "001"
    (run / "production_manifest.json").write_text('{"visual_mode":"INI"}')
    assert not n3_mode_readiness(obra, "PL", "13_PAV", "NOVA")["ready"]
    assert n3_mode_readiness(obra, "PL", "13_PAV", "INI")["ready"]
    next((run / "n3" / "pil").rglob('PL_GRADES_preview_P1.dxf')).unlink()
    assert not n3_mode_readiness(obra, "PL", "13_PAV", "INI")["ready"]
    assert not (obra / "Fase-6_Execucao_CAD" / "n5").exists()


def test_preflight_has_no_ready_mode_when_all_pillars_are_nasce(tmp_path):
    from src.core.n5_assembler import n3_mode_readiness
    obra = tmp_path / "Obra_only_nasce"
    _make_pillar_production_set(obra, "001", "P1")
    (obra / "estado_13_PAV.json").write_text(json.dumps({"pilares": [
        {"name": "P1", "classification": "NASCE"}
    ]}))
    assert n3_mode_readiness(obra, "PL", "13_PAV", "NOVA") == {"ready": False, "total": 0, "missing": []}
