import json
import sqlite3

import pytest

from src.core.database import DatabaseManager
from src.core.sa_db_persistence import (
    fv_area_errors,
    merge_analysis_collection,
    merge_analysis_item,
    persist_analysis_snapshot,
)


def _contour(length, *, validated=False):
    link = {
        "points": [(0, 0), (length, 0), (length, 20), (0, 20)],
        "len": length,
    }
    if validated:
        link["validated"] = True
    return {"contour": [link]}


def test_unvalidated_item_is_replaced_by_fresh_analysis():
    old = {
        "id": "l1",
        "name": "L1",
        "fields": {"laje_nivel": "+1.00"},
        "links": {"laje_nivel": {"label": [{"text": "+1.00"}]}},
    }
    new = {
        "id": "new-l1",
        "name": "L1",
        "fields": {"laje_nivel": "+2.80"},
        "links": {"laje_nivel": {"label": [{"text": "+2.80"}]}},
    }

    result = merge_analysis_item(old, new, "LAJ")

    assert result["id"] == "l1"
    assert result["fields"]["laje_nivel"] == "+2.80"
    assert result["links"]["laje_nivel"]["label"][0]["text"] == "+2.80"


def test_laje_preserves_only_validated_geometry_and_slot():
    old = {
        "id": "l1",
        "name": "L1",
        "points": [(0, 0), (100, 0), (100, 80), (0, 80)],
        "fields": {"laje_nivel": "+1.00"},
        "validated_fields": ["laje_outline_segs"],
        "validated_link_classes": {
            "laje_pilares_apoio": ["pillar_geom"],
        },
        "links": {
            "laje_outline_segs": _contour(100),
            "laje_pilares_apoio": {
                "pillar_geom": [{"name": "P1"}],
                "pillar_label": [{"text": "P1"}],
            },
        },
    }
    new = {
        "id": "new-l1",
        "name": "L1",
        "points": [(0, 0), (999, 0), (999, 80), (0, 80)],
        "fields": {"laje_nivel": "+2.80"},
        "links": {
            "laje_outline_segs": _contour(999),
            "laje_pilares_apoio": {
                "pillar_geom": [{"name": "P99"}],
                "pillar_label": [{"text": "P99"}],
            },
        },
    }

    result = merge_analysis_item(old, new, "LAJ")

    assert result["points"] == old["points"]
    assert result["links"]["laje_outline_segs"] == old["links"]["laje_outline_segs"]
    assert result["fields"]["laje_nivel"] == "+2.80"
    assert result["links"]["laje_pilares_apoio"]["pillar_geom"] == [
        {"name": "P1"}
    ]
    assert result["links"]["laje_pilares_apoio"]["pillar_label"] == [
        {"text": "P99"}
    ]


def test_pilar_preserves_validated_field_but_refreshes_other_fields():
    old = {
        "id": "p1",
        "name": "P1",
        "validated_fields": ["dim"],
        "fields": {"dim": "20x60", "nivel": "+1.00"},
        "links": {
            "dim": {"label": [{"text": "20x60"}]},
            "nivel": {"label": [{"text": "+1.00"}]},
        },
    }
    new = {
        "id": "new-p1",
        "name": "P1",
        "fields": {"dim": "25x70", "nivel": "+2.80"},
        "links": {
            "dim": {"label": [{"text": "25x70"}]},
            "nivel": {"label": [{"text": "+2.80"}]},
        },
    }

    result = merge_analysis_item(old, new, "PIL")

    assert result["fields"]["dim"] == "20x60"
    assert result["links"]["dim"]["label"][0]["text"] == "20x60"
    assert result["fields"]["nivel"] == "+2.80"


def test_validation_metadata_is_copied_exactly_without_union_or_reordering():
    old = {
        "id": "p1",
        "name": "P1",
        "validated_fields": ["z_field", "a_field"],
        "validated_link_classes": {"z_field": ["slot_b", "slot_a"]},
        "na_fields": ["campo_na"],
        "na_link_classes": {"outro": ["slot_z"]},
        "na_reasons": {"campo_na": "humano"},
        "fields": {"z_field": "Z", "a_field": "A"},
        "links": {
            "z_field": {"slot_b": [], "slot_a": []},
            "a_field": {},
        },
    }
    new = {
        "id": "new-p1",
        "name": "P1",
        "validated_fields": ["automatico_incorreto"],
        "validated_link_classes": {"automatico_incorreto": ["slot"]},
        "fields": {"automatico_incorreto": "X"},
        "links": {"automatico_incorreto": {"slot": []}},
    }

    result = merge_analysis_item(old, new, "PIL")

    assert result["validated_fields"] == ["z_field", "a_field"]
    assert result["validated_link_classes"] == {
        "z_field": ["slot_b", "slot_a"]
    }
    assert result["na_fields"] == ["campo_na"]
    assert result["na_link_classes"] == {"outro": ["slot_z"]}
    assert result["na_reasons"] == {"campo_na": "humano"}


def test_fv_validation_locks_only_validated_segments_and_geometry():
    old = {
        "id": "b1",
        "name": "V1",
        "fields": {
            "viga_fundo_seg_1_dim": "20/50",
            "viga_fundo_seg_2_dim": "20/60",
        },
        "validated_link_classes": {
            "viga_fundo_seg_1_area_segs": ["contour"],
        },
        "links": {
            "viga_fundo_seg_1_area_segs": _contour(100, validated=True),
            "viga_fundo_seg_2_area_segs": _contour(80),
        },
    }
    new = {
        "id": "new-b1",
        "name": "V1",
        "fields": {
            "viga_fundo_seg_1_dim": "20/55",
            "viga_fundo_seg_2_dim": "20/65",
            "viga_fundo_seg_3_dim": "20/70",
        },
        "links": {
            "viga_fundo_seg_1_area_segs": _contour(999),
            "viga_fundo_seg_2_area_segs": _contour(888),
            "viga_fundo_seg_3_area_segs": _contour(777),
        },
    }

    result = merge_analysis_item(old, new, "BEAM")

    assert result["links"]["viga_fundo_seg_1_area_segs"] == (
        old["links"]["viga_fundo_seg_1_area_segs"]
    )
    assert "viga_fundo_seg_2_area_segs" not in result["links"]
    assert "viga_fundo_seg_3_area_segs" not in result["links"]
    assert result["fields"]["viga_fundo_seg_1_dim"] == "20/55"
    assert "viga_fundo_seg_2_dim" not in result["fields"]
    assert result["preficha_fundo_locked_source_keys"] == [
        "viga_fundo_seg_1_area_segs"
    ]


def test_lv_topology_is_locked_independently_for_each_side_and_behavior():
    old = {
        "id": "b1",
        "name": "V1",
        "validated_link_classes": {
            "viga_a_seg_1_comprimento_total": ["seg_side_a"],
        },
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [{"len": 100, "validated": True}]
            },
        },
    }
    new = {
        "id": "new-b1",
        "name": "V1",
        "links": {
            "viga_a_seg_1_comprimento_total": {
                "seg_side_a": [{"len": 999}]
            },
            "viga_a_seg_2_comprimento_total": {
                "seg_side_a": [{"len": 200}]
            },
            "viga_a_seg_1_comp_total_passa": {
                "seg_side_a": [{"len": 300}]
            },
            "viga_a_seg_2_comp_total_passa": {
                "seg_side_a": [{"len": 400}]
            },
        },
    }

    result = merge_analysis_item(old, new, "BEAM")

    assert result["links"]["viga_a_seg_1_comprimento_total"] == (
        old["links"]["viga_a_seg_1_comprimento_total"]
    )
    assert "viga_a_seg_2_comprimento_total" not in result["links"]
    assert "viga_a_seg_1_comp_total_passa" in result["links"]
    assert "viga_a_seg_2_comp_total_passa" in result["links"]


def test_fv_area_gate_rejects_automatic_line_and_accepts_closed_rectangle():
    beam = {
        "name": "V305",
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [{
            "type": "poly", "points": [(0, 0), (286, 0)],
        }]}},
    }
    assert fv_area_errors([beam]) == [
        "V305:viga_fundo_seg_1_area_segs:1:closed=False:area=0.000000"
    ]

    beam["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"] = [
        (0, 0), (286, 0), (286, 19), (0, 19), (0, 0),
    ]
    assert fv_area_errors([beam]) == []


def _empty_collections(project_id):
    return {
        "pillars": [{
            "id": "p1",
            "project_id": project_id,
            "name": "P1",
            "points": [],
            "links": {},
        }],
        "slabs": [],
        "beams": [],
    }


def test_transaction_rolls_back_all_classes_on_serialization_failure(tmp_path):
    db_path = tmp_path / "project_data.vision"
    DatabaseManager(str(db_path))
    project_id = "project-1"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id,name) VALUES (?,?)",
            (project_id, "Teste"),
        )

    good = _empty_collections(project_id)
    persist_analysis_snapshot(
        db_path=str(db_path),
        project_id=project_id,
        collections=good,
        run_id="run-good",
        html_dir="run-good",
        source_dxf="source.dxf",
        merge_stats={},
    )

    bad = _empty_collections(project_id)
    bad["pillars"][0]["name"] = "ALTERADO"
    bad["beams"] = [{
        "id": "b1",
        "project_id": project_id,
        "name": "V1",
        "not_json_serializable": object(),
    }]
    with pytest.raises(TypeError):
        persist_analysis_snapshot(
            db_path=str(db_path),
            project_id=project_id,
            collections=bad,
            run_id="run-bad",
            html_dir="run-bad",
            source_dxf="source.dxf",
            merge_stats={},
        )

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT name FROM pillars").fetchone()[0] == "P1"
        assert conn.execute(
            "SELECT COUNT(*) FROM sa_persistence_runs"
        ).fetchone()[0] == 1


def test_partial_laj_persistence_never_deletes_other_class_rows(tmp_path):
    """O lock por classe só é seguro se o commit parcial não apagar vizinhos."""
    db_path = tmp_path / "project_data.vision"
    DatabaseManager(str(db_path))
    project_id = "project-partial"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id,name) VALUES (?,?)", (project_id, "Teste"),
        )

    initial = _empty_collections(project_id)
    initial["slabs"] = [{
        "id": "l1", "project_id": project_id, "name": "L1", "points": [],
        "links": {}, "area": 1.0,
    }]
    persist_analysis_snapshot(
        db_path=str(db_path), project_id=project_id, collections=initial,
        run_id="run-initial", html_dir="run-initial", source_dxf="source.dxf",
        merge_stats={},
    )

    partial_laj = {
        "pillars": [],
        "slabs": [{
            "id": "l1", "project_id": project_id, "name": "L1", "points": [],
            "links": {"laje_dim": {"label": [{"text": "h=12"}]}}, "area": 2.0,
        }],
        "beams": [],
    }
    persist_analysis_snapshot(
        db_path=str(db_path), project_id=project_id, collections=partial_laj,
        run_id="run-partial-laj", html_dir="run-partial-laj", source_dxf="source.dxf",
        merge_stats={}, delete_missing=False,
    )

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM pillars").fetchone()[0] == 1
        assert conn.execute("SELECT area FROM slabs WHERE id='l1'").fetchone()[0] == 2.0


def test_laj_duplicate_label_keeps_closed_polygon_and_partial_commit_cleans_stale_row(tmp_path):
    """Uma segunda região com o mesmo rótulo não pode virar outra laje N1."""
    project_id = "project-laj-identity"
    closed = {
        "id": "candidate-closed", "project_id": project_id, "name": "L9",
        "points": [(0, 0), (100, 0), (100, 60), (0, 60), (0, 0)],
        "area": 6000.0, "links": {}, "confidence_score": 0.30,
    }
    fragment = {
        "id": "candidate-fragment", "project_id": project_id, "name": "L9",
        "points": [(0, 0), (100, 0), (100, 60), (0, 0)],
        "area": 3000.0, "links": {}, "confidence_score": 0.95,
    }
    merged, stats = merge_analysis_collection(
        old_items=[], new_items=[fragment, closed], kind="LAJ", project_id=project_id,
    )
    assert len(merged) == 1
    assert merged[0]["id"] == "candidate-closed"
    assert stats["duplicatas_laj_descartadas_da_analise"] == 1

    db_path = tmp_path / "project_data.vision"
    DatabaseManager(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO projects (id,name) VALUES (?,?)", (project_id, "Teste"))

    # Simula a sobra de uma rodada granular antiga, antes da invariável.
    persist_analysis_snapshot(
        db_path=str(db_path), project_id=project_id,
        collections={"pillars": [], "slabs": [closed, fragment], "beams": []},
        run_id="dup-initial", html_dir="dup-initial", source_dxf="source.dxf",
        merge_stats={}, delete_missing=False,
    )
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM slabs WHERE name='L9'").fetchone()[0] == 1
        assert conn.execute("SELECT id FROM slabs WHERE name='L9'").fetchone()[0] == "candidate-closed"


def test_laj_duplicate_with_human_validation_is_the_canonical_record(tmp_path):
    project_id = "project-laj-protected"
    db_path = tmp_path / "project_data.vision"
    DatabaseManager(str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO projects (id,name) VALUES (?,?)", (project_id, "Teste"))

    current = {
        "id": "current", "project_id": project_id, "name": "L10",
        "points": [(0, 0), (100, 0), (100, 60), (0, 60), (0, 0)],
        "area": 6000.0, "links": {},
    }
    protected = {
        "id": "protected", "project_id": project_id, "name": "L10",
        "points": [(0, 0), (50, 0), (50, 60), (0, 60), (0, 0)],
        "area": 3000.0, "links": {}, "validated_fields": ["laje_outline_segs"],
    }
    persist_analysis_snapshot(
        db_path=str(db_path), project_id=project_id,
        collections={"pillars": [], "slabs": [current, protected], "beams": []},
        run_id="dup-protected", html_dir="dup-protected", source_dxf="source.dxf",
        merge_stats={}, delete_missing=False,
    )
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM slabs WHERE name='L10'").fetchone()[0] == 1
        assert conn.execute("SELECT id FROM slabs WHERE name='L10'").fetchone()[0] == "protected"
