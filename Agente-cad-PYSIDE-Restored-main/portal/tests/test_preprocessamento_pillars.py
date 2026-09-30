from __future__ import annotations

import ezdxf

from portal.app.preprocessamento.adapters.pillars import inventory_pillars


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
