from __future__ import annotations

import ezdxf
import pytest

from portal.app.preprocessamento.adapters.pillars import inventory_pillars, _non_pillar_layer_reason


def _tower(path):
    document = ezdxf.new("R2010")
    model = document.modelspace()
    model.add_lwpolyline([(0, 0), (20, 0), (20, 20), (0, 20)], close=True)
    model.add_text("P1", dxfattribs={"insert": (10, 10)})
    model.add_line((2, 2), (18, 18))
    model.add_line((2, 18), (18, 2))
    model.add_lwpolyline([(100, 0), (120, 0), (120, 20), (100, 20)], close=True)
    model.add_text("P2", dxfattribs={"insert": (110, 10)})
    model.add_text("P3", dxfattribs={"insert": (300, 10)})
    document.saveas(path)


def test_inventario_liga_geometria_convencao_e_preserva_pendente(tmp_path):
    path = tmp_path / "tower.dxf"
    _tower(path)
    convention = {"signature_index": {"CROSS": ["NASCE"], "EMPTY": ["MORRE"]}}

    result = inventory_pillars(path, source_id="source-a", convention=convention)
    by_name = {item["display_name"]: item for item in result["items"]}

    assert by_name["P1"]["classification_raw"] == "NASCE"
    assert by_name["P2"]["classification_raw"] == "MORRE"
    assert by_name["P3"]["status"] == "geometry_missing"
    assert result["counts"] == {"total": 3, "linked": 2, "pending": 1}


def test_convencao_ambigua_nao_escolhe_primeiro_rotulo(tmp_path):
    path = tmp_path / "tower.dxf"
    _tower(path)
    convention = {"signature_index": {"CROSS": ["NASCE", "OUTRO"]}}

    result = inventory_pillars(path, source_id="source-a", convention=convention)
    p1 = next(item for item in result["items"] if item["display_name"] == "P1")

    assert p1["classification_raw"] is None
    assert p1["classification_alternatives"] == ["NASCE", "OUTRO"]
    assert p1["status"] == "ambiguous"


def test_ids_mudam_com_escopo_da_torre(tmp_path):
    path = tmp_path / "tower.dxf"
    _tower(path)

    a = inventory_pillars(path, source_id="tower-a")
    b = inventory_pillars(path, source_id="tower-b")
    ids_a = {item["item_id"] for item in a["items"]}
    ids_b = {item["item_id"] for item in b["items"]}

    assert ids_a.isdisjoint(ids_b)


@pytest.mark.parametrize("layer", ["MTH-LINHA-SEÇÃO", "MTH-LINHA-SE��O", "SECTION", "CORTE"])
@pytest.mark.parametrize("polytype", ["LWPOLYLINE", "POLYLINE"])
def test_section_entity_excluded_without_removing_coincident_pillar(tmp_path, layer, polytype):
    document = ezdxf.new("R2010")
    model = document.modelspace()
    points = [(1000, 500), (1020, 500), (1020, 520), (1000, 520)]
    structural = model.add_lwpolyline(points, close=True, dxfattribs={"layer": "PILAR-SEGUE"})
    if polytype == "LWPOLYLINE":
        annotation = model.add_lwpolyline(points, close=True, dxfattribs={"layer": layer})
    else:
        annotation = model.add_polyline2d(points, close=True, dxfattribs={"layer": layer})
    model.add_text("P1", dxfattribs={"insert": (1010, 510)})
    path = tmp_path / "coincident.dxf"
    document.saveas(path)
    result = inventory_pillars(path, source_id="any-source")
    assert result["counts"] == {"total": 1, "linked": 1, "pending": 0}
    assert result["items"][0]["source_entity_handles"] == [structural.dxf.handle]
    assert result["excluded_annotation_entities"] == [{
        "handle": annotation.dxf.handle, "layer": layer, "entity_type": polytype,
        "reason": "section_annotation_not_plan_pillar",
    }]
    assert len(ezdxf.readfile(path).modelspace().query("LWPOLYLINE POLYLINE")) == 2


def test_section_only_pillar_label_remains_pending(tmp_path):
    document = ezdxf.new("R2010")
    model = document.modelspace()
    model.add_lwpolyline([(0, 0), (20, 0), (20, 20), (0, 20)], close=True,
                         dxfattribs={"layer": "SECTION"})
    label = model.add_text("P99", dxfattribs={"insert": (10, 10)})
    path = tmp_path / "section-only.dxf"
    document.saveas(path)
    result = inventory_pillars(path, source_id="another-source")
    assert result["counts"] == {"total": 1, "linked": 0, "pending": 1}
    assert result["items"][0]["status"] == "geometry_missing"
    assert result["items"][0]["source_entity_handles"] == [label.dxf.handle]


@pytest.mark.parametrize("layer,reason", [
    ("MTH-COTAS7", "dimension_annotation_not_plan_pillar"),
    ("MTH-SOMB120", "shadow_annotation_not_plan_pillar"),
    ("MTH-SOMBRA20", "shadow_annotation_not_plan_pillar"),
    ("MTH-FACE-VIGA", "beam_face_not_plan_pillar"),
    ("MTH-PILAR-SEGUE", None), ("CONCRETE", None), ("MTH-224", None),
])
def test_source_roles_do_not_guess_unknown_layers(layer, reason):
    assert _non_pillar_layer_reason(layer) == reason


def test_l_shaped_pillar_label_uses_footprint_not_empty_bbox_center(tmp_path):
    document = ezdxf.new("R2010")
    model = document.modelspace()
    lshape = model.add_lwpolyline([(0,0),(20,0),(20,180),(300,180),(300,200),(0,200)],close=True)
    model.add_text("P7",dxfattribs={"insert":(-20,100)})
    other = model.add_lwpolyline([(140,70),(160,70),(160,90),(140,90)],close=True)
    model.add_text("P10",dxfattribs={"insert":(150,60)})
    path = tmp_path/'l-shape.dxf'
    document.saveas(path)
    result = inventory_pillars(path,source_id='any-project')
    by_name = {i['display_name']:i for i in result['items']}
    assert by_name['P7']['source_entity_handles']==[lshape.dxf.handle]
    assert by_name['P10']['source_entity_handles']==[other.dxf.handle]
    assert result['counts']=={'total':2,'linked':2,'pending':0}


def test_equidistant_labels_do_not_certify_association(tmp_path):
    document = ezdxf.new("R2010")
    model = document.modelspace()
    model.add_lwpolyline([(0,0),(20,0),(20,20),(0,20)],close=True)
    model.add_text('P1',dxfattribs={'insert':(-10,10)})
    model.add_text('P2',dxfattribs={'insert':(30,10)})
    path = tmp_path/'tie.dxf'
    document.saveas(path)
    result = inventory_pillars(path,source_id='tie-project')
    geometric = next(i for i in result['items'] if i['geometry'])
    assert geometric['status']=='ambiguous'
    assert 'rotulos_equidistantes_do_contorno' in geometric['warnings']


def test_circular_pillar_preserves_analytic_geometry_and_ignores_annotation_circle(tmp_path):
    document=ezdxf.new('R2010')
    model=document.modelspace()
    circle=model.add_circle((100,200),30,dxfattribs={'layer':'PILAR-SEGUE'})
    model.add_circle((100,200),40,dxfattribs={'layer':'COTAS'})
    model.add_text('P21',dxfattribs={'insert':(140,220)})
    path=tmp_path/'circle.dxf'
    document.saveas(path)
    result=inventory_pillars(path,source_id='arbitrary-source')
    assert len(result['items'])==1
    item=result['items'][0]
    assert item['geometry']=={'type':'Circle','center':[100.0,200.0],'radius':30.0}
    assert item['source_entity_handles']==[circle.dxf.handle]
    assert item['classification_raw'] is None
    assert item['warnings']==['circular_faces_require_analytic_consumer']
