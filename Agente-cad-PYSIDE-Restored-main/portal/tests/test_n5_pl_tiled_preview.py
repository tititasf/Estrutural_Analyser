import json
from pathlib import Path
import xml.etree.ElementTree as ET

import ezdxf

from portal.app.routers.jobs_routes import _n5_pl_tiled_svg


def test_split_preview_loads_only_three_views_and_keeps_group_in_tile_urls(tmp_path):
    dxf = tmp_path / "N5_PL_13_PAV_NOVA_PASSA.dxf"
    dxf.write_bytes(b"DXF")
    dxf.with_suffix(".json").write_text(json.dumps({"items": [{
        "item_id": "P1", "status": "ok", "source": "a.dxf;b.dxf;c.dxf",
    }]}), encoding="utf-8")
    root = ET.fromstring(_n5_pl_tiled_svg("obra", "13_PAV", dxf, pillar_group="PASSA"))
    images = root.findall("{http://www.w3.org/2000/svg}image")
    assert len(images) == 3
    assert all("pillar_group=PASSA" in image.attrib["href"] for image in images)
    assert "/2?" in images[-1].attrib["href"]


def test_n5_pl_preview_is_46_rows_by_5_vector_tiles(tmp_path: Path):
    dxf = tmp_path / "N5_PL_13_PAV.dxf"
    dxf.write_bytes(b"DXF")
    items = [
        {
            "item_id": f"P{number}",
            "status": "ok",
            "source": ";".join(f"/n3/P{number}_{view}.dxf" for view in range(5)),
        }
        for number in range(1, 47)
    ]
    dxf.with_suffix(".json").write_text(
        json.dumps({"items": items}), encoding="utf-8",
    )

    svg = _n5_pl_tiled_svg("obra id", "13_PAV", dxf).decode("utf-8")

    assert svg.count("<image ") == 46 * 5
    assert svg.count("<text ") == 46
    assert "P1</text>" in svg
    assert "P46</text>" in svg
    assert "/foto-tile/P1/0?" in svg
    assert "/foto-tile/P1/4?" in svg
    assert "pavimento=13_PAV" in svg
    assert "/obras/obra%20id/" in svg


def _make_box(path: Path, width: float, height: float) -> None:
    doc = ezdxf.new("R2018")
    doc.modelspace().add_lwpolyline(
        [(0, 0), (width, 0), (width, height), (0, height)], close=True,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(path)


def test_n5_pl_preview_preserves_native_scale_between_tiles(tmp_path: Path):
    dxf = tmp_path / "N5_PL_13_PAV.dxf"
    dxf.write_bytes(b"DXF")
    sizes = [(200, 100), (100, 50), (100, 50), (100, 50), (100, 50)]
    sources = []
    for index, (width, height) in enumerate(sizes):
        source = tmp_path / "n3" / f"P1_{index}.dxf"
        _make_box(source, width, height)
        sources.append(str(source))
    dxf.with_suffix(".json").write_text(
        json.dumps({"items": [{
            "item_id": "P1", "status": "ok", "source": ";".join(sources),
        }]}),
        encoding="utf-8",
    )

    svg = _n5_pl_tiled_svg("obra", "13_PAV", dxf)
    root = ET.fromstring(svg)
    images = root.findall("{http://www.w3.org/2000/svg}image")

    assert [float(image.attrib["width"]) for image in images] == [
        200.0, 100.0, 100.0, 100.0, 100.0,
    ]
    assert [float(image.attrib["height"]) for image in images] == [
        100.0, 50.0, 50.0, 50.0, 50.0,
    ]
