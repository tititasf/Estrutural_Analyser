from __future__ import annotations

import ezdxf

from portal.app.preprocessamento.adapters.inventory import inventory_labels


def test_rotulos_de_lajes_vigas_e_duplicados_sem_geometria_inventada(tmp_path):
    path = tmp_path / "tower.dxf"
    document = ezdxf.new("R2010")
    model = document.modelspace()
    model.add_text("L301", dxfattribs={"insert": (0, 0)})
    model.add_text("L301", dxfattribs={"insert": (100, 0)})
    model.add_text("V302", dxfattribs={"insert": (0, 100)})
    model.add_text("NOTAS", dxfattribs={"insert": (0, 200)})
    document.saveas(path)

    result = inventory_labels(path, source_id="torre-1")
    assert result["counts"] == {"slabs": 2, "beams": 1, "ambiguous": 2}
    assert {item["display_name"] for item in result["items"]} == {"L301", "V302"}
    assert len({item["item_id"] for item in result["items"]}) == 3
    assert all(item["geometry"] is None for item in result["items"])
    assert result["status"] == "partial"


def test_ids_evidencia_nao_colidem_entre_torres(tmp_path):
    path = tmp_path / "tower.dxf"
    document = ezdxf.new("R2010")
    document.modelspace().add_text("V1", dxfattribs={"insert": (0, 0)})
    document.saveas(path)
    first = inventory_labels(path, source_id="torre-1")
    second = inventory_labels(path, source_id="torre-2")
    assert first["items"][0]["item_id"] != second["items"][0]["item_id"]


def test_contorno_fechado_unico_vincula_e_aninhamento_mantem_ambiguidade(tmp_path):
    path = tmp_path / 'tower.dxf'
    doc = ezdxf.new('R2010')
    model = doc.modelspace()
    model.add_text('L301', dxfattribs={'insert': (50, 50)})
    model.add_lwpolyline([(0,0),(100,0),(100,100),(0,100)], close=True)
    doc.saveas(path)
    item = inventory_labels(path, source_id='t')['items'][0]
    assert item['status'] == 'linked'
    assert item['geometry']['type'] == 'Polygon'
    assert len(item['source_entity_handles']) == 2
    model.add_lwpolyline([(20,20),(80,20),(80,80),(20,80)], close=True)
    doc.saveas(path)
    item = inventory_labels(path, source_id='t')['items'][0]
    assert item['geometry'] is None
    assert item['warnings'] == ['multiplos_contornos_candidatos']
