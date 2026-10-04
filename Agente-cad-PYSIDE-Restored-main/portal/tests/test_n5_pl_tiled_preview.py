import json
from pathlib import Path
import xml.etree.ElementTree as ET

import ezdxf

from portal.app.routers.jobs_routes import _n5_pl_tiled_svg


def test_fv_framed_preview_routes_each_page_to_fv(tmp_path):
    dxf=tmp_path/'N5_FV_13_PAV_NOVA.dxf';dxf.write_bytes(b'DXF')
    dxf.with_suffix('.json').write_text(json.dumps({'frame_layout':{'kind':'nova_frames_v1',
        'pages':[{'origin':[0,0]},{'origin':[1585,0]}]}}))
    root=ET.fromstring(_n5_pl_tiled_svg('obra','13_PAV',dxf,classe='FV'))
    images=root.findall('{http://www.w3.org/2000/svg}image')
    assert len(images)==2
    assert '/n5/FV/foto-sheet/1?' in images[1].attrib['href']
    assert 'pillar_group' not in images[1].attrib['href']


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


def test_framed_preview_preserves_four_columns_and_outside_grade_sheets(tmp_path):
    dxf = tmp_path / 'N5_PL_13_PAV_NOVA_PARA.dxf'
    dxf.write_bytes(b'DXF')
    pages = [{'origin': [0, 0]}, {'origin': [1585, 0]},
             {'origin': [0, -1150]}, {'origin': [6740, -2300]}]
    dxf.with_suffix('.json').write_text(json.dumps({
        'frame_layout': {'kind': 'nova_frames_v1', 'pages': pages},
    }), encoding='utf8')
    root = ET.fromstring(_n5_pl_tiled_svg('obra', '13_PAV', dxf, pillar_group='PARA'))
    images = root.findall('{http://www.w3.org/2000/svg}image')
    assert len(images) == 4
    assert [(float(e.attrib['x']), float(e.attrib['y'])) for e in images] == [
        (0, 0), (1585, 0), (0, 1150), (6740, 2300)]
    assert all(float(e.attrib['width']) == 1485 and float(e.attrib['height']) == 1050 for e in images)
    assert all('/foto-sheet/' in e.attrib['href'] and 'pillar_group=PARA' in e.attrib['href'] for e in images)


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
