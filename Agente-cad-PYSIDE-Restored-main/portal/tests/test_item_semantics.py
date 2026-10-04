"""SA manual: reconhecimento local, geometria soberana, vizinhos intocados."""
import copy
import json
from time import perf_counter

import pytest

from portal.app import item_geometry, item_semantics


@pytest.mark.parametrize("classe", ["fundo", "lateral_a_para", "lateral_b_passa"])
def test_only_selected_segment_is_interpreted(tmp_path, classe):
    points = [[0, 0], [100, 0], [100, 14], [0, 14]]
    sibling = {"uid": "other", "beam_name": "V1", "segment_label": "2",
               "points": points, "level": 999, "beam_height": 77}
    state = {"slabs": [{"name": "L1", "points": [[0, 14], [100, 14], [100, 200], [0, 200]],
                         "nivel": 100}],
             "segmentos": {classe: [{"uid": "selected", "beam_name": "V1", "segment_label": "1",
                                      "points": points}, copy.deepcopy(sibling)]}}
    path = tmp_path / "estado_13_PAV.json"
    path.write_text(json.dumps(state))
    texts = [{"text": "14/55", "pos": [50, 20]}]
    result = item_geometry.mutate(tmp_path, "13_PAV", classe, "selected", points=points, semantic_texts=texts)
    after = json.loads(path.read_text())
    selected, other = after["segmentos"][classe]
    assert selected["points"][:4] == points
    assert selected["beam_height"] == 55
    assert selected["section_dim"] == "14/55"
    assert other == sibling
    assert result["interpretation"]["scope"] == "segment"
    assert not selected["is_validated"]


def test_tiny_new_segment_persists_across_republication(tmp_path):
    path = tmp_path / "estado_14_PAV.json"
    path.write_text('{"segmentos":{"fundo":[]}}')
    result = item_geometry.mutate(tmp_path, "14_PAV", "fundo", "", create={"name": "V1", "segment": 1},
                                  points=[[0, 0], [1, 0], [1, 14], [0, 14]], semantic_texts=[])
    key = result["affected"][0]["item_id"]
    state = item_geometry.apply_state({"segmentos": {"fundo": []}}, tmp_path, "14_PAV")
    assert len(state["segmentos"]["fundo"]) == 1
    assert state["segmentos"]["fundo"][0]["uid"] == key
    assert result["interpretation"]["fields"]["section_dim"]["source"] == "unresolved"
    with pytest.raises(ValueError, match="já existe"):
        item_geometry.mutate(tmp_path, "14_PAV", "fundo", "", create={"name": "V1", "segment": 1},
                             points=[[0, 0], [1, 0], [1, 14], [0, 14]], semantic_texts=[])
    item_geometry.mutate(tmp_path, "14_PAV", "fundo", key, delete=True)
    assert not item_geometry.apply_state({"segmentos": {"fundo": []}}, tmp_path, "14_PAV")["segmentos"]["fundo"]


def test_pillar_dimension_not_stolen_and_cached_read(tmp_path):
    import ezdxf
    path = tmp_path / "plan.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_text("P1", dxfattribs={"insert": (50, 25)})
    doc.modelspace().add_text("14/66", dxfattribs={"insert": (50, 10)})
    doc.saveas(path)
    first = item_semantics.source_texts(path)
    hits = item_semantics._texts.cache_info().hits
    second = item_semantics.source_texts(path)
    assert item_semantics._texts.cache_info().hits == hits + 1
    assert first == second
    row = {"points": [[0, 0], [100, 0], [100, 14], [0, 14]], "width": 14}
    patch, evidence = item_semantics.recognize(row, "fundo", {}, first)
    assert patch["beam_height"] is None
    assert evidence["geometry_preserved"]


def test_pillar_scope_and_slab_contact():
    row = {"name": "P1", "points": [[0, 0], [20, 0], [20, 60], [0, 60]]}
    state = {"slabs": [{"name": "L1", "points": [[20, 0], [200, 0], [200, 60], [20, 60]]}]}
    patch, evidence = item_semantics.recognize(row, "pilares", state, [], beams=[])
    assert evidence["scope"] == "item"
    assert patch["lajes"][0]["side"] == "B"
    assert patch["face_beams"] == {}
    assert "points" not in patch


def test_segment_semantics_warm_performance():
    row = {"points": [[0, 0], [100, 0], [100, 14], [0, 14]], "width": 14}
    texts = [{"text": "14/55", "pos": [50, 20]}] * 1000
    item_semantics.recognize(row, "fundo", {}, texts)
    start = perf_counter()
    for _ in range(10):
        item_semantics.recognize(row, "fundo", {}, texts)
    assert (perf_counter() - start) / 10 < 0.1


def test_dimension_reader_parity_with_canonical_fv():
    from src.core.beam_interpreters.fundo_viga import FundoVigaInterpreter as FV
    from src.core.beam_section_texts import dimension_texts
    texts = [{"text": "P1", "pos": [20, 30]}, {"text": "19/66", "pos": [20, 15]},
             {"text": "14/55", "pos": [80, 10]}, {"text": "14/55", "pos": [80, 10]},
             {"text": "19,5/120", "pos": [200, 30]}, {"text": "L1", "pos": [50, 60]}]
    assert dimension_texts(texts) == FV._iter_dimension_texts({"geometry": {"texts": texts}})


def test_one_cm_panel_keeps_real_section_axis():
    row = {"points": [[0,0],[1,0],[1,14],[0,14]], "width": 1, "length": 14}
    patch, proof = item_semantics.recognize(row, "fundo", {}, [{"text":"14/55", "pos":[1,20]}])
    assert patch["length"] == 1
    assert patch["width"] == 14
    assert patch["beam_height"] == 55
