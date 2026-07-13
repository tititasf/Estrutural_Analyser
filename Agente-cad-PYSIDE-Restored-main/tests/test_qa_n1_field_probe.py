from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.arete.qa_content_cache import ContentAddressedCache
from scripts.arete.qa_n1_field_probe import REQUEST_SCHEMA, run_probe


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        CREATE TABLE projects (
          id TEXT PRIMARY KEY, work_name TEXT, pavement_name TEXT, updated_at TEXT
        );
        CREATE TABLE pillars (
          id TEXT PRIMARY KEY, project_id TEXT, name TEXT, points_json TEXT,
          sides_data_json TEXT, links_json TEXT, conf_map_json TEXT, extra_data_json TEXT
        );
        CREATE TABLE beams (
          id TEXT PRIMARY KEY, project_id TEXT, name TEXT, data_json TEXT,
          sides_data_json TEXT, links_json TEXT
        );
        CREATE TABLE slabs (
          id TEXT PRIMARY KEY, project_id TEXT, name TEXT, points_json TEXT,
          links_json TEXT, extra_data_json TEXT
        );
        """
    )
    con.execute("INSERT INTO projects VALUES ('p', 'OBRA', '13_PAV', '2026-07-13')")
    pillar_links = {
        "p_sD_v_passa_esq_n": {"label": [{"text": "V328", "source": "face_adapter"}]},
        "p_sD_v_passa_esq_d": {"label": [{"text": "19/55", "source": "face_adapter"}]},
    }
    con.execute(
        "INSERT INTO pillars VALUES ('pil', 'p', 'P35', ?, '{}', ?, '{}', '{}')",
        (json.dumps([[0, 0], [60, 0], [60, 19], [0, 19], [0, 0]]), json.dumps(pillar_links)),
    )
    beam = {
        "fields": {"nome": "V328", "dimensao": "19/55"},
        "links": {"viga_segs": {"seg_bottom": [{"points": [[0, 10], [80, 10], [80, 29], [0, 29], [0, 10]]}]}},
    }
    con.execute("INSERT INTO beams VALUES ('v', 'p', 'V328', ?, '{}', '{}')", (json.dumps(beam),))
    return con


def _request() -> dict:
    return {
        "schema": REQUEST_SCHEMA,
        "project_id": "p",
        "question": "A viga vinculada à face D tem identidade, dimensão e contato coerentes?",
        "fields": [
            {"id": "pillar.beam.name", "class": "PIL", "item": "P35", "source": "payload", "path": "p_sD_v_passa_esq_n.label.0.text", "transform": "entity"},
            {"id": "pillar.beam.dim", "class": "PIL", "item": "P35", "source": "payload", "path": "p_sD_v_passa_esq_d.label.0.text", "transform": "dimension"},
            {"id": "pillar.bbox", "class": "PIL", "item": "P35", "source": "geometry", "path": "", "transform": "bbox"},
            {"id": "beam.name", "class": "FV", "item": "V328", "source": "payload", "path": "fields.nome", "transform": "entity"},
            {"id": "beam.dim", "class": "FV", "item": "V328", "source": "payload", "path": "fields.dimensao", "transform": "dimension"},
            {"id": "beam.bbox", "class": "FV", "item": "V328", "source": "payload", "path": "links.viga_segs.seg_bottom.0.points", "transform": "bbox"},
        ],
        "checks": [
            {"id": "identity", "op": "same_entity", "left": "pillar.beam.name", "right": "beam.name"},
            {"id": "dimension", "op": "dimension_equal", "left": "pillar.beam.dim", "right": "beam.dim", "order_sensitive": True},
            {"id": "touch", "op": "bbox_intersects", "left": "pillar.bbox", "right": "beam.bbox"},
        ],
    }


def test_probe_crosses_classes_and_validates_only_declared_checks(tmp_path: Path):
    con = _db()
    result = run_probe(
        con, _request(), cache=ContentAddressedCache(tmp_path / "cache"),
    )
    assert result["overall"] == "PASS"
    assert result["scope_authority"].startswith("field_checks_only")
    assert result["provenance"]["cross_class"] == ["FV", "PIL"]
    assert result["runtime"]["loaded_rows"] == 2
    assert result["runtime"]["requested_fields"] == 6
    pillar_name = next(row for row in result["fields"] if row["id"] == "pillar.beam.name")
    assert "sides_data_json" not in pillar_name["selected_columns"]
    con.close()


def test_probe_cache_hits_and_invalidates_when_snapshot_changes(tmp_path: Path):
    con = _db()
    cache = ContentAddressedCache(tmp_path / "cache")
    first = run_probe(con, _request(), cache=cache)
    second = run_probe(con, _request(), cache=cache)
    assert first["runtime"]["cache_hit"] is False
    assert second["runtime"]["cache_hit"] is True
    assert first["runtime"]["cache_key"] == second["runtime"]["cache_key"]

    changed = {
        "p_sD_v_passa_esq_n": {"label": [{"text": "V999", "source": "face_adapter"}]},
        "p_sD_v_passa_esq_d": {"label": [{"text": "19/55", "source": "face_adapter"}]},
    }
    con.execute("UPDATE pillars SET links_json=? WHERE id='pil'", (json.dumps(changed),))
    third = run_probe(con, _request(), cache=cache)
    assert third["runtime"]["cache_hit"] is False
    assert third["runtime"]["cache_key"] != first["runtime"]["cache_key"]
    assert third["overall"] == "FAIL"
    con.close()


def test_cached_probe_does_not_need_to_decode_large_json_again(tmp_path: Path, monkeypatch):
    con = _db()
    cache = ContentAddressedCache(tmp_path / "cache")
    run_probe(con, _request(), cache=cache)

    def forbidden_decode(_value):
        raise AssertionError("cache hit não deve desserializar payload")

    monkeypatch.setattr("scripts.arete.qa_n1_field_probe.json_value", forbidden_decode)
    second = run_probe(con, _request(), cache=cache)
    assert second["runtime"]["cache_hit"] is True
    assert second["overall"] == "PASS"
    con.close()


def test_probe_overlay_tests_candidate_without_writing_db(tmp_path: Path):
    con = _db()
    result = run_probe(
        con, _request(), overlay={"fields": {"pillar.beam.name": "V999"}},
        cache=ContentAddressedCache(tmp_path / "cache"),
    )
    assert result["overall"] == "FAIL"
    assert next(row for row in result["fields"] if row["id"] == "pillar.beam.name")["overridden"] is True
    persisted = json.loads(con.execute("SELECT links_json FROM pillars WHERE id='pil'").fetchone()[0])
    assert persisted["p_sD_v_passa_esq_n"]["label"][0]["text"] == "V328"
    con.close()


def test_probe_present_and_absent_are_field_level_results(tmp_path: Path):
    con = _db()
    request = {
        "schema": REQUEST_SCHEMA,
        "project_id": "p",
        "question": "O slot opcional está ausente?",
        "fields": [
            {"id": "slot", "class": "PIL", "item": "P35", "source": "payload", "path": "slot_inexistente"},
        ],
        "checks": [
            {"id": "must_exist", "op": "present", "left": "slot"},
            {"id": "must_be_absent", "op": "absent", "left": "slot"},
        ],
    }
    result = run_probe(con, request, cache=ContentAddressedCache(tmp_path / "cache"))
    assert result["overall"] == "FAIL"
    assert [row["status"] for row in result["checks"]] == ["FAIL", "PASS"]
    con.close()
