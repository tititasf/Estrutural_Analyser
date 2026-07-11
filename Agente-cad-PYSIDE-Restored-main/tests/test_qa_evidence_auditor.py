from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pytest

from scripts.arete.qa_evidence_auditor import (
    LajEvidenceAuditor,
    REQUIRED_LAJ_FIELDS,
    Slab,
    cmd_apply,
    cmd_audit,
    cmd_rollback,
)


def slab(
    name: str,
    *,
    level: str | None = None,
    level_link: dict | None = None,
    links: dict | None = None,
    validated: set[str] | None = None,
    sealed: bool = False,
) -> Slab:
    all_links = links or {}
    if level_link is not None:
        all_links.setdefault("laje_nivel", {})["label"] = [level_link]
    extra = {"fields": {"nome": name, "laje_dim": "h=10"}}
    if level is not None:
        extra["fields"]["laje_nivel"] = level
        extra["laje_nivel"] = level
    raw = {
        "links_json": json.dumps(all_links),
        "validated_fields_json": json.dumps(sorted(validated or set())),
        "na_fields_json": "[]",
        "validated_link_classes_json": "{}",
        "na_link_classes_json": "{}",
        "na_reasons_json": "{}",
        "extra_data_json": json.dumps(extra),
        "is_validated": int(sealed),
    }
    return Slab(
        id=name, project_id="p", name=name,
        points=[[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]],
        links=all_links, validated_fields=set(validated or set()), na_fields=set(),
        validated_link_classes={}, na_link_classes={}, na_reasons={}, extra=extra,
        is_validated=sealed, raw_columns=raw,
    )


def test_bare_dimension_does_not_become_level_anchor():
    source = slab(
        "L1", level="852.12",
        level_link={"text": "852.12", "layer": "3", "validated": True},
        validated={"laje_nivel"}, sealed=True,
    )
    contaminated = slab(
        "L2", level="402.5",
        level_link={"text": "402.5", "layer": "2"},
    )
    auditor = LajEvidenceAuditor([source, contaminated], "run")
    assert auditor.levels["L1"] == pytest.approx(852.12)
    assert "L2" not in auditor.levels


def test_neighbor_wrong_level_is_replaced_from_trusted_source():
    source = slab(
        "L1", level="852.12",
        level_link={"text": "852.12", "layer": "3", "validated": True},
        validated={"laje_nivel"}, sealed=True,
    )
    target = slab(
        "L2",
        links={
            "laje_vizinhas_niveis": {
                "neighbor_east": [
                    {"text": "L1", "source": "orthogonal_neighbor_identity", "source_slab": "L1", "is_inferred": True},
                    {"text": "402.5", "source": "orthogonal_neighbor_level", "source_slab": "L1", "is_inferred": True},
                ]
            }
        },
    )
    auditor = LajEvidenceAuditor([source, target], "run")
    decision = auditor._audit_laje_vizinhas_niveis(target)
    assert decision.decision == "CONFIRMAR"
    assert any(op["op"] == "remove_link" for op in decision.operations)
    assert any(op["op"] == "add_link" and op["link"]["text"] == "852.12" for op in decision.operations)
    assert any(x["code"] == "LAJ-NEIGHBOR-LEVEL-CONTAMINATION" for x in auditor.findings)


def test_sealed_ambiguous_level_is_not_resolved_by_neighbor_continuity():
    source = slab("L1", level="852.12", validated={"laje_nivel"}, sealed=True)
    source.extra["laje_nivel"] = "852.19"
    target = slab(
        "L2",
        links={
            "laje_vizinhas_niveis": {
                "neighbor_east": [
                    {"text": "L1", "source": "orthogonal_neighbor_identity", "source_slab": "L1", "is_inferred": True},
                    {"text": "402.5", "source": "orthogonal_neighbor_level", "source_slab": "L1", "is_inferred": True},
                    {"text": "852.12", "source": "orthogonal_neighbor_level", "source_slab": "L1", "is_inferred": True},
                ]
            }
        },
    )
    auditor = LajEvidenceAuditor([source, target], "run")
    assert "L1" not in auditor.levels
    assert "L1" in auditor.blocked_level_sources
    decision = auditor._audit_laje_vizinhas_niveis(target)
    assert decision.decision == "REVISAR_HUMANO"
    assert sum(op["op"] == "remove_link" for op in decision.operations) == 1
    assert any(
        finding["code"] == "LAJ-NEIGHBOR-LEVEL-CONTAMINATION" and finding["evidence"][0]["wrong"] == "402.5"
        for finding in auditor.findings
    )
    assert not any(op["op"] == "add_link" for op in decision.operations)


def test_distant_pillar_is_removed_but_touching_support_is_kept():
    target = slab(
        "L2",
        links={
            "laje_pilares_apoio": {
                "pillar_geom": [
                    {
                        "text": "Pilar de apoio detectado", "is_inferred": True,
                        "distance_to_slab": 0.0, "points": [[0, 10], [10, 10], [10, 20], [0, 20], [0, 10]],
                        "ficha": {"pillar_name": "P1", "pillar_side": "A", "touch_face": "ESQ"},
                    },
                    {
                        "text": "Pilar de apoio detectado", "is_inferred": True,
                        "distance_to_slab": 30.0, "points": [[0, -40], [10, -40], [10, -30], [0, -30], [0, -40]],
                        "ficha": {"pillar_name": "P2", "pillar_side": "NULO", "touch_face": "NULO"},
                    },
                ]
            }
        },
    )
    auditor = LajEvidenceAuditor([target], "run")
    decision = auditor._audit_laje_pilares_apoio(target)
    assert decision.decision == "CONFIRMAR"
    assert sum(op["op"] == "remove_link" for op in decision.operations) == 1
    assert "LAJ-PILLAR-NOT-TOUCHING" in decision.rule_codes


def test_distant_cut_component_is_removed():
    target = slab(
        "L2",
        links={
            "laje_visao_corte": {
                "cut_view_geom": [
                    {"is_inferred": True, "distance_to_slab": 0.0, "points": [[0, 0], [20, 0], [20, 10], [10, 10], [0, 0]]},
                    {"is_inferred": True, "distance_to_slab": 60.0, "points": [[0, -70], [20, -70], [20, -60], [10, -60], [0, -70]]},
                ]
            }
        },
    )
    auditor = LajEvidenceAuditor([target], "run")
    decision = auditor._audit_laje_visao_corte(target)
    assert decision.decision == "CONFIRMAR"
    assert sum(op["op"] == "remove_link" for op in decision.operations) == 1


def test_explicit_delta_level_resolves_after_unicode_normalization():
    source = slab(
        "L1", level="852.12",
        level_link={"text": "852.12", "layer": "3", "validated": True},
        validated={"laje_nivel"}, sealed=True,
    )
    target = slab(
        "L2", level="859.12",
        level_link={
            "text": "859.12", "role": "Nivel inferido",
            "source": "cut_view_delta from L1 (Δ=+7.0cm)", "source_slab": None,
        },
    )
    auditor = LajEvidenceAuditor([source, target], "run")
    assert auditor.levels["L2"] == pytest.approx(859.12)
    assert "delta explícito" in auditor.level_reasons["L2"]


def create_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE slabs (
            id TEXT PRIMARY KEY, project_id TEXT, name TEXT, points_json TEXT,
            links_json TEXT, validated_fields_json TEXT, na_fields_json TEXT,
            validated_link_classes_json TEXT, na_link_classes_json TEXT,
            na_reasons_json TEXT, extra_data_json TEXT, is_validated INTEGER
        );
        """
    )
    source_links = {
        "laje_nivel": {"label": [{"text": "852.12", "layer": "3", "validated": True}]},
    }
    target_links = {
        "laje_vizinhas_niveis": {"neighbor_east": [
            {"text": "L1", "source": "orthogonal_neighbor_identity", "source_slab": "L1", "is_inferred": True},
            {"text": "402.5", "source": "orthogonal_neighbor_level", "source_slab": "L1", "is_inferred": True},
        ]},
        "laje_nivel": {"label": [{"text": "852.12", "layer": "3"}]},
    }
    source_fields = {"fields": {"nome": "L1", "laje_dim": "h=10", "laje_nivel": "852.12"}, "laje_nivel": "852.12"}
    target_fields = {"fields": {"nome": "L2", "laje_dim": "h=10", "laje_nivel": "852.12"}, "laje_nivel": "852.12"}
    points = json.dumps([[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]])
    con.execute(
        "INSERT INTO slabs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("1", "p", "L1", points, json.dumps(source_links), json.dumps(list(REQUIRED_LAJ_FIELDS)), json.dumps(["laje_islands"]), "{}", "{}", "{}", json.dumps(source_fields), 1),
    )
    completed_except_neighbor = set(REQUIRED_LAJ_FIELDS) - {"laje_vizinhas_niveis"}
    con.execute(
        "INSERT INTO slabs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("2", "p", "L2", points, json.dumps(target_links), json.dumps(sorted(completed_except_neighbor)), json.dumps(["laje_islands"]), "{}", "{}", "{}", json.dumps(target_fields), 0),
    )
    con.commit()
    con.close()


def test_apply_is_transactional_seals_complete_and_rollback_restores(tmp_path: Path):
    db = tmp_path / "test.vision"
    create_db(db)
    run_dir = tmp_path / "run"
    cmd_audit(argparse.Namespace(db=str(db), project_id="p", item=["L2"], include_sealed=False, run_id="run", out_dir=str(run_dir)))
    cmd_apply(argparse.Namespace(db=str(db), project_id="p", run=str(run_dir), decision_file=None, seal_complete=True))
    con = sqlite3.connect(db)
    row = con.execute("SELECT is_validated, links_json FROM slabs WHERE id='2'").fetchone()
    assert row[0] == 1
    texts = [x["text"] for x in json.loads(row[1])["laje_vizinhas_niveis"]["neighbor_east"]]
    assert "402.5" not in texts
    assert "852.12" in texts
    con.close()
    cmd_rollback(argparse.Namespace(db=str(db), project_id="p", run=str(run_dir)))
    con = sqlite3.connect(db)
    row = con.execute("SELECT is_validated, links_json FROM slabs WHERE id='2'").fetchone()
    assert row[0] == 0
    assert "402.5" in [x["text"] for x in json.loads(row[1])["laje_vizinhas_niveis"]["neighbor_east"]]
    con.close()


def test_apply_rejects_stale_snapshot(tmp_path: Path):
    db = tmp_path / "test.vision"
    create_db(db)
    run_dir = tmp_path / "run"
    cmd_audit(argparse.Namespace(db=str(db), project_id="p", item=["L2"], include_sealed=False, run_id="run", out_dir=str(run_dir)))
    con = sqlite3.connect(db)
    con.execute("UPDATE slabs SET na_reasons_json=? WHERE id='2'", (json.dumps({"changed": True}),))
    con.commit()
    con.close()
    with pytest.raises(RuntimeError, match="snapshot obsoleto"):
        cmd_apply(argparse.Namespace(db=str(db), project_id="p", run=str(run_dir), decision_file=None, seal_complete=True))
