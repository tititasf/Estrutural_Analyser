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
    apply_operation,
    cmd_apply,
    cmd_audit,
    discover_class_inventory,
    generic_class_review,
    load_rag_consultations,
    resolve_project_scope,
    cmd_rollback,
    reconcile_web_evidence,
    WebEvidenceResolver,
)


def test_global_discovery_keeps_beam_families_separate_and_is_read_only(tmp_path: Path):
    db = tmp_path / "global.vision"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY, work_name TEXT, pavement_name TEXT, updated_at TEXT);
        CREATE TABLE beams (id TEXT PRIMARY KEY, project_id TEXT, name TEXT, data_json TEXT, is_validated INTEGER);
        """
    )
    con.execute("INSERT INTO projects VALUES ('p', 'OBRA', 'PAV', '2026-07-12')")
    payload = {"viga_fundo_seg_1_exists": True, "fv_detail": {}, "viga_a_seg_1_dim": "19/55", "lv_detail": {}}
    con.execute("INSERT INTO beams VALUES ('b', 'p', 'V1', ?, 0)", (json.dumps(payload),))
    assert resolve_project_scope(con, project_id=None, obra="OBRA", pav="PAV") == "p"
    fv = discover_class_inventory(con, project_id="p", classe="FV", selected=None, include_sealed=True)
    lv = discover_class_inventory(con, project_id="p", classe="LV", selected=None, include_sealed=True)
    assert fv["validation_mode"] == "diagnostic_only"
    assert set(fv["field_frequency"]) == {"viga_fundo_seg_1_exists", "fv_detail"}
    assert set(lv["field_frequency"]) == {"viga_a_seg_1_dim", "lv_detail"}
    assert con.execute("SELECT is_validated FROM beams WHERE id='b'").fetchone()[0] == 0
    con.close()


def test_generic_review_fails_closed_and_explains_missing_contract(tmp_path: Path):
    db = tmp_path / "review.vision"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE beams (
          id TEXT PRIMARY KEY, project_id TEXT, name TEXT, data_json TEXT,
          is_validated INTEGER, validated_fields_json TEXT, na_fields_json TEXT
        );
        """
    )
    con.execute(
        "INSERT INTO beams VALUES ('b', 'p', 'V1', ?, 0, '[]', '[]')",
        (json.dumps({"viga_fundo_seg_1_dim": "19/55"}),),
    )
    decisions, findings, questions, records = generic_class_review(
        con, project_id="p", classe="FV", run_id="run", selected=None, include_sealed=True,
    )
    assert not findings
    assert len(records) == 1
    assert decisions[0].decision == "PENDENTE"
    assert decisions[0].operations == []
    assert questions[0]["reasoning"]["rejected"] == [
        "usar o valor N1 como prova de si mesmo", "copiar convenção de LAJ", "inferir por proximidade ou por N2/N4",
    ]
    assert con.execute("SELECT is_validated FROM beams WHERE id='b'").fetchone()[0] == 0
    con.close()


def test_generic_review_labels_internal_trace_without_confirming_semantics(tmp_path: Path):
    db = tmp_path / "trace.vision"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE beams (
          id TEXT PRIMARY KEY, project_id TEXT, name TEXT, data_json TEXT,
          is_validated INTEGER, validated_fields_json TEXT, na_fields_json TEXT
        );
        """
    )
    payload = {
        "viga_fundo_seg_1_dim": {
            "label": [{"source": "dxf_entity:42", "text": "19/55"}],
        },
    }
    con.execute(
        "INSERT INTO beams VALUES ('b', 'p', 'V1', ?, 0, '[]', '[]')",
        (json.dumps(payload),),
    )
    decisions, findings, questions, records = generic_class_review(
        con, project_id="p", classe="FV", run_id="run", selected=None, include_sealed=True,
    )
    assert not findings
    assert not questions
    assert len(records) == 1
    assert decisions[0].decision == "TRILHA_N1_OBSERVADA"
    assert decisions[0].confidence == "medium"
    assert decisions[0].operations == []
    assert "não confirma geometria ou vínculo" in decisions[0].reason
    assert con.execute("SELECT is_validated FROM beams WHERE id='b'").fetchone()[0] == 0
    con.close()


def test_rag_consultation_is_contextual_and_partitioned_by_class(tmp_path: Path):
    db = tmp_path / "rag.vision"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE semantic_rag_kb (
          id TEXT PRIMARY KEY, classe TEXT, regra_semantica TEXT,
          obra_contexto TEXT, confianca REAL, created_at TEXT
        );
        """
    )
    con.execute("INSERT INTO semantic_rag_kb VALUES ('1', 'FV', 'Regra FV', 'obra', .9, '2026-07-12')")
    context = load_rag_consultations(con, ["FV", "LAJ"])
    assert context["FV"][0]["rag_id"] == "1"
    assert context["LAJ"] == []
    assert context["FV"][0]["authority"].startswith("consultative_only")
    assert context["FV"][0]["partition"]["exact"] is True
    con.close()


def test_rag_consultation_applies_typed_field_tier_and_scope_filters(tmp_path: Path):
    db = tmp_path / "rag_typed.vision"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE semantic_rag_kb (
          id TEXT PRIMARY KEY, classe TEXT, regra_semantica TEXT,
          obra_contexto TEXT, confianca REAL, created_at TEXT,
          familia TEXT, campo TEXT, tier TEXT, pavimento TEXT
        );
        """
    )
    con.execute("INSERT INTO semantic_rag_kb VALUES ('1','PIL','Regra certa','OBRA',.9,'2026-07-13','face','vazio_topo','T1','13_PAV')")
    con.execute("INSERT INTO semantic_rag_kb VALUES ('2','PIL','Outra regra','OBRA',.9,'2026-07-13','face','abertura','T3','13_PAV')")
    context = load_rag_consultations(
        con, ["PIL"], family="face", field="vazio_topo",
        tiers=["T1", "T2"], obra="OBRA", pav="13_PAV",
    )
    assert [entry["rag_id"] for entry in context["PIL"]] == ["1"]
    assert context["PIL"][0]["partition"]["exact"] is True
    assert set(context["PIL"][0]["partition"]["applied"]) == {"family", "field", "tier", "obra", "pav"}
    assert context["PIL"][0]["tier"] == "T1"
    con.close()


def test_rag_consultation_marks_unavailable_partition_as_degraded(tmp_path: Path):
    db = tmp_path / "rag_legacy.vision"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE semantic_rag_kb (
          id TEXT PRIMARY KEY, classe TEXT, regra_semantica TEXT,
          obra_contexto TEXT, confianca REAL, created_at TEXT
        );
        """
    )
    con.execute("INSERT INTO semantic_rag_kb VALUES ('1','PIL','Contexto legado','OBRA',.8,'2026-07-13')")
    context = load_rag_consultations(con, ["PIL"], field="vazio_topo", tiers=["T1"])
    assert context["PIL"][0]["partition"]["exact"] is False
    assert set(context["PIL"][0]["partition"]["unavailable"]) == {"field", "tier"}
    assert context["PIL"][0]["authority"].startswith("consultative_only")
    con.close()


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


def test_web_evidence_resolver_records_versioned_html_without_trusting_ui_state(tmp_path: Path):
    page = tmp_path / "Obra" / "run" / "lajes" / "L100.html"
    page.parent.mkdir(parents=True)
    page.write_text(
        '<html><title>Laje — L100</title>'
        '<td>Nome</td><td>L100</td><td>Nível</td><td>852.19</td>'
        '<td>Espessura</td><td>12</td><td>Área do contorno</td><td>1000</td>'
        '<div class="evidence-title"><b>N1 / SA</b></div><svg></svg>'
        '<div class="artifact-path">C:/obra/L100.dxf</div>'
        '<script>localStorage.setItem("val_L100", "1")</script></html>',
        encoding="utf-8",
    )
    evidence = WebEvidenceResolver(tmp_path).resolve_laj("L100")
    assert evidence["state"] == "available"
    assert evidence["identity"] == {"name": "L100", "level": "852.19", "thickness": "12", "area": "1000"}
    assert evidence["visual"]["embedded_svg_count"] == 1
    assert evidence["authority"].startswith("presentation_only")


def test_auditor_references_available_web_evidence_in_its_decision():
    target = slab("L100", links={"laje_outline_segs": {"contour": [{"points": [[0, 0], [1, 0]]}]}})
    evidence = {"L100": {"state": "available", "evidence_id": "web-x", "sha256": "abc", "path": "C:/ficha/L100.html"}}
    auditor = LajEvidenceAuditor([target], "run", web_evidence=evidence)
    decision = auditor._audit_laje_outline_segs(target)
    assert decision.evidence[-1]["kind"] == "web_granular_ficha"
    assert decision.evidence[-1]["evidence_id"] == "web-x"


def test_web_snapshot_with_different_contour_area_is_rejected_as_stale():
    target = slab("L100", level="852.19")
    target.extra["fields"]["laje_dim"] = "h=12"
    evidence = {
        "state": "available", "item": "L100",
        "identity": {"name": "L100", "level": "852.19", "thickness": "12", "area": "9000"},
    }
    reconciled = reconcile_web_evidence(target, evidence)
    assert reconciled["state"] == "stale"
    assert reconciled["persisted_comparison"]["mismatches"][0]["field"] == "area"


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


def test_sealed_level_outlier_is_corrected_when_root_label_and_cluster_agree():
    stable_a = slab(
        "L1", level="852.19",
        level_link={"text": "852.19", "layer": "3", "validated": True},
        validated={"laje_nivel"}, sealed=True,
    )
    stable_b = slab(
        "L2", level="852.19",
        level_link={"text": "852.19", "layer": "3", "validated": True},
        validated={"laje_nivel"}, sealed=True,
    )
    outlier = slab(
        "L3", level="845.19",
        level_link={"text": "852.19", "layer": "3", "validated": True},
        validated={"laje_nivel"}, sealed=True,
    )
    outlier.extra["laje_nivel"] = "852.19"
    auditor = LajEvidenceAuditor([stable_a, stable_b, outlier], "run")
    decision = auditor._audit_laje_nivel(outlier)
    assert decision.decision == "CORRIGIR"
    assert decision.confidence == "high"
    assert decision.operations == [{"op": "set_level", "value": "852.19", "reason": "root+rótulo+cluster corroborado"}]
    assert any(finding["code"] == "LAJ-LEVEL-OUTLIER-CORRECTION" for finding in auditor.findings)


def test_ambiguous_sealed_level_question_explains_reasoning_chain():
    stable_low = slab(
        "L1", level="852.12",
        level_link={"text": "852.12", "layer": "3", "validated": True},
        validated={"laje_nivel"}, sealed=True,
    )
    stable_high = slab(
        "L2", level="852.19",
        level_link={"text": "852.19", "layer": "3", "validated": True},
        validated={"laje_nivel"}, sealed=True,
    )
    ambiguous = slab("L3", level="852.12", validated={"laje_nivel"}, sealed=True)
    ambiguous.extra["laje_nivel"] = "852.19"
    auditor = LajEvidenceAuditor([stable_low, stable_high, ambiguous], "run")
    decision = auditor._audit_laje_nivel(ambiguous)
    assert decision.decision == "REVISAR_HUMANO"
    question = auditor.questions[-1]
    assert set(question["reasoning"]) == {"observed", "attempted", "rejected", "impasse", "requested_rule"}
    assert question["reasoning"]["observed"]["field_cluster"]["count"] >= 1
    assert question["reasoning"]["observed"]["root_cluster"]["count"] >= 1


def test_neighbors_do_not_duplicate_question_for_the_same_ambiguous_source():
    stable_low = slab("L1", level="852.12", level_link={"text": "852.12", "layer": "3", "validated": True}, validated={"laje_nivel"}, sealed=True)
    stable_high = slab("L2", level="852.19", level_link={"text": "852.19", "layer": "3", "validated": True}, validated={"laje_nivel"}, sealed=True)
    ambiguous = slab("L3", level="852.12", validated={"laje_nivel"}, sealed=True)
    ambiguous.extra["laje_nivel"] = "852.19"
    dependent = slab("L4", links={"laje_vizinhas_niveis": {"neighbor_west": [
        {"text": "L3", "source": "orthogonal_neighbor_identity", "source_slab": "L3", "is_inferred": True},
    ]}})
    auditor = LajEvidenceAuditor([stable_low, stable_high, ambiguous, dependent], "run")
    auditor._audit_laje_nivel(ambiguous)
    decision = auditor._audit_laje_vizinhas_niveis(dependent)
    assert decision.decision == "REVISAR_HUMANO"
    assert len(auditor.questions) == 1
    assert auditor.questions[0]["item"] == "L3"
    assert auditor.questions[0]["reasoning"]["observed"]["dependent_neighbors"] == [{"item": "L4", "slot": "neighbor_west"}]


def test_touching_pillar_consensus_can_resolve_ambiguous_slab_level():
    ambiguous = slab("L1", level="852.12", validated={"laje_nivel"}, sealed=True)
    ambiguous.extra["laje_nivel"] = "852.19"
    auditor = LajEvidenceAuditor(
        [ambiguous], "run",
        consultive_context={"L1": {"pillars": [
            {"name": "P1", "level": "852.19", "distance": 0.0, "validated": False},
            {"name": "P2", "level": "852.19", "distance": 0.0, "validated": False},
        ], "beams": [{"name": "V1", "level": None, "distance": 0.0, "validated": False}]}},
    )
    decision = auditor._audit_laje_nivel(ambiguous)
    assert decision.decision == "CORRIGIR"
    assert decision.operations == [{"op": "set_level", "value": "852.19", "reason": "consenso PIL em contato + root"}]
    assert decision.evidence[0]["kind"] == "consultive_pillar_level_consensus"
    assert [x["name"] for x in decision.evidence[0]["pillars"]] == ["P1", "P2"]


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


def test_cut_ficha_negative_distance_requires_human_review_with_reasoning():
    target = slab(
        "L2",
        links={
            "laje_visao_corte": {
                "cut_view_geom": [{
                    "is_inferred": True, "distance_to_slab": 0.0,
                    "points": [[0, 0], [20, 0], [20, 10], [0, 10], [0, 0]],
                    "ficha": {
                        "beam_name": "V1", "beam_height": "55", "neigh_slab_height": "57.2",
                        "neighbor_dist_top": "30", "neighbor_dist_bottom": "-32.2",
                        "neigh_dist_fundo_formula": "bh(55) - H_laje_viz(57.2) - d_topo(30) = -32.2",
                    },
                }]
            }
        },
    )
    auditor = LajEvidenceAuditor([target], "run")
    decision = auditor._audit_laje_visao_corte(target)
    assert decision.decision == "REVISAR_HUMANO"
    assert decision.rule_codes == ["LAJ-CUT-CALC-INCONSISTENT"]
    assert auditor.questions[-1]["reasoning"]["observed"][0]["code"] == "negative_distance"
    assert "V1" in auditor.questions[-1]["question"]
    assert "distância negativa" in auditor.questions[-1]["question"]


def test_cut_ficha_semantic_neighbor_height_repairs_negative_distance_without_guessing():
    target = slab(
        "L2",
        links={
            "laje_visao_corte": {
                "cut_view_geom": [{
                    "is_inferred": True, "distance_to_slab": 0.0,
                    "points": [[0, 0], [20, 0], [20, 10], [0, 10], [0, 0]],
                    "ficha": {
                        "beam_name": "V1", "beam_height": "55", "neighbor_height": "14",
                        "neigh_slab_height": "57.2", "neighbor_dist_top": "30", "neighbor_dist_bottom": "-32.2",
                    },
                }]
            }
        },
    )
    auditor = LajEvidenceAuditor([target], "run")
    decision = auditor._audit_laje_visao_corte(target)
    assert decision.decision == "CORRIGIR"
    repair = next(op for op in decision.operations if op["op"] == "repair_cut_ficha")
    state = {"links": target.links, "validated_fields": set(), "na_fields": set(), "validated_link_classes": {}, "na_link_classes": {}, "na_reasons": {}, "extra": {}}
    apply_operation(state, repair)
    ficha = state["links"]["laje_visao_corte"]["cut_view_geom"][0]["ficha"]
    assert ficha["neigh_slab_height"] == "14"
    assert ficha["neighbor_dist_bottom"] == "11"


def test_outline_decision_contains_polygon_area_and_perimeter():
    target = slab("L2", links={"laje_outline_segs": {"contour": [{"points": [[0, 0], [1, 0]]}]}})
    auditor = LajEvidenceAuditor([target], "run")
    decision = auditor._audit_laje_outline_segs(target)
    assert decision.decision == "CONFIRMAR"
    assert decision.evidence[0]["area"] == pytest.approx(10000.0)
    assert decision.evidence[0]["perimeter"] == pytest.approx(400.0)


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


def test_apply_corrects_sealed_outlier_only_with_explicit_flag(tmp_path: Path):
    db = tmp_path / "test.vision"
    create_db(db)
    con = sqlite3.connect(db)
    extra = {
        "fields": {"nome": "L1", "laje_dim": "h=10", "laje_nivel": "845.19"},
        "laje_nivel": "852.19",
    }
    outlier_links = {"laje_nivel": {"label": [{"text": "852.19", "layer": "3", "validated": True}]}}
    con.execute("UPDATE slabs SET extra_data_json=?, links_json=? WHERE id='1'", (json.dumps(extra), json.dumps(outlier_links)))
    stable_extra = {
        "fields": {"nome": "L2", "laje_dim": "h=10", "laje_nivel": "852.19"},
        "laje_nivel": "852.19",
    }
    stable_links = {"laje_nivel": {"label": [{"text": "852.19", "layer": "3", "validated": True}]}}
    con.execute("UPDATE slabs SET extra_data_json=?, links_json=? WHERE id='2'", (json.dumps(stable_extra), json.dumps(stable_links)))
    con.commit()
    con.close()
    run_dir = tmp_path / "run"
    cmd_audit(argparse.Namespace(db=str(db), project_id="p", item=["L1"], include_sealed=True, run_id="run", out_dir=str(run_dir)))
    cmd_apply(argparse.Namespace(
        db=str(db), project_id="p", run=str(run_dir), decision_file=None,
        seal_complete=False, allow_sealed_corrections=True,
    ))
    con = sqlite3.connect(db)
    extra = json.loads(con.execute("SELECT extra_data_json FROM slabs WHERE id='1'").fetchone()[0])
    assert extra["fields"]["laje_nivel"] == "852.19"
    assert extra["laje_nivel"] == "852.19"
    con.close()
