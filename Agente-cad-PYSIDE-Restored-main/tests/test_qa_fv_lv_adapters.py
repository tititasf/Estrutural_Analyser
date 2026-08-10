"""Adaptadores CAD FV/LV — prova geométrica e contratos isolados."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.arete.qa_fv_lv_adapters import (
    FvEvidenceAuditor,
    LvEvidenceAuditor,
    load_beam_records,
    load_name_index,
)


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "t.vision"
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY, work_name TEXT, pavement_name TEXT, updated_at TEXT);
        CREATE TABLE pillars (
            id TEXT PRIMARY KEY, project_id TEXT, name TEXT, points_json TEXT
        );
        CREATE TABLE beams (
            id TEXT PRIMARY KEY, project_id TEXT, name TEXT, data_json TEXT,
            links_json TEXT, validated_fields_json TEXT, na_fields_json TEXT,
            is_validated INTEGER
        );
        """
    )
    pid = "p1"
    con.execute("INSERT INTO projects VALUES (?,?,?,?)", (pid, "O", "13", "t"))
    con.execute(
        "INSERT INTO pillars VALUES (?,?,?,?)",
        ("pil1", pid, "P1", json.dumps([[0, 0], [20, 0], [20, 20], [0, 20], [0, 0]])),
    )
    # FV segment: 100 x 19 rectangle
    contour = {
        "contour": [{
            "type": "poly",
            "points": [[0, 0], [100, 0], [100, 19], [0, 19], [0, 0]],
            "len": 100,
        }]
    }
    data = {
        "fields": {
            "nome": "V301",
            "possui_corte": False,
            "viga_fundo_seg_1_dim": "19/100",
            "viga_fundo_seg_1_local_ini": "P1",
            "viga_fundo_seg_1_local_fim": "P1",
            "viga_a_seg_1_dim": "19/55",
            "viga_b_seg_1_dim": "19/55",
            "viga_a_seg_1_end_name": "P1",
            "viga_a_seg_4_abert_pilar_esq_dist": "9",
            "viga_a_seg_4_abert_pilar_esq_larg": "72",
        },
        # Faces DXF classificadas: contorno [0..19] ancora nas linhas y=0 e y=19
        "geometry": {
            "classified": {
                "seg_bottom": [
                    [[0, 0], [100, 0]],
                    [[0, 19], [100, 19]],
                ],
                "merged_bottom_groups_coords": [[0, 100]],
            }
        },
        "links": {
            "viga_segs": {
                "seg_bottom": [{
                    "points": [[0, 0], [100, 0], [100, 19], [0, 19], [0, 0]],
                    "len": 100,
                    "closed": True,
                }]
            },
            "viga_fundo_seg_1_area_segs": contour,
            "cortes": [],
            "aberturas": {
                "pilar": [{"name": "P1", "text": "P1", "pos": [1, 2]}],
                "viga": [],
            },
            "viga_a_seg_4_abert_pilar_esq": {
                "label": [{"text": "P1", "name": "P1"}],
            },
        },
        "lv_generation_contracts": {
            "Para": {
                "A": {
                    "side": "A", "behavior": "Para", "contract_id": "LV_A_PARA",
                    "generation_ready": True,
                    "structural_segments": [{
                        "width": 100, "points": [[0, 0], [100, 0], [100, 1], [0, 1]],
                        "source_key": "viga_a_seg_1_comprimento_total",
                        "source_slot": "seg_side_a",
                    }],
                    "_sa_meta": {"behavior_isolated": True, "fv_dimension_fallback": False},
                },
                "B": {
                    "side": "B", "behavior": "Para", "contract_id": "LV_B_PARA",
                    "generation_ready": True,
                    "structural_segments": [{
                        "width": 100, "points": [[0, 0], [100, 0], [100, 1], [0, 1]],
                        "source_key": "viga_b_seg_1_comprimento_total",
                        "source_slot": "seg_side_b",
                    }],
                    "_sa_meta": {"behavior_isolated": True, "fv_dimension_fallback": False},
                },
            },
            "Passa": {
                "A": {
                    "side": "A", "behavior": "Passa", "contract_id": "LV_A_PASSA",
                    "generation_ready": True,
                    "structural_segments": [{
                        "width": 100, "points": [[0, 0], [100, 0], [100, 1], [0, 1]],
                        "source_key": "viga_a_seg_1_comp_total_passa",
                        "source_slot": "seg_side_a",
                    }],
                    "_sa_meta": {"behavior_isolated": True, "fv_dimension_fallback": False},
                },
                "B": {
                    "side": "B", "behavior": "Passa", "contract_id": "LV_B_PASSA",
                    "generation_ready": True,
                    "structural_segments": [{
                        "width": 100, "points": [[0, 0], [100, 0], [100, 1], [0, 1]],
                        "source_key": "viga_b_seg_1_comp_total_passa",
                        "source_slot": "seg_side_b",
                    }],
                    "_sa_meta": {"behavior_isolated": True, "fv_dimension_fallback": False},
                },
            },
        },
    }
    con.execute(
        "INSERT INTO beams VALUES (?,?,?,?,?,?,?,?)",
        ("b1", pid, "V301", json.dumps(data), "{}", "[]", "[]", 0),
    )
    con.commit()
    con.close()
    return path


def test_fv_adapter_confirms_segment_geometry(tmp_path: Path):
    db = _db(tmp_path)
    con = sqlite3.connect(db)
    beams = load_beam_records(con, "p1")
    names = load_name_index(con, "p1")
    auditor = FvEvidenceAuditor(beams, names, "run1")
    decisions = auditor.audit(selected={"V301"})
    by_field = {d.field_id: d for d in decisions}
    assert by_field["name"].decision == "CONFIRMAR"
    assert by_field["viga_fundo_seg_1_exists"].decision == "CONFIRMAR"
    assert by_field["viga_fundo_seg_1_area_segs"].decision == "CONFIRMAR"
    assert by_field["viga_fundo_seg_1_dim"].decision == "CONFIRMAR"
    assert by_field["viga_fundo_seg_1_local_ini"].decision == "CONFIRMAR"
    assert by_field["cortes"].decision == "N/A_CONFIRMADO"
    assert by_field["aberturas"].decision == "CONFIRMAR"
    assert by_field["viga_fundo_seg_1_exists"].operations
    con.close()


def test_fv_adapter_blocks_orange_when_contour_floats_off_structure(tmp_path: Path):
    """Tamanho certo + flutuando: PENDENTE — não grava qa_agente / selo laranja."""
    db = _db(tmp_path)
    con = sqlite3.connect(db)
    row = con.execute("SELECT data_json FROM beams WHERE id='b1'").fetchone()
    data = json.loads(row[0])
    # Contorno com C×L 100×19 mas deslocado (+8 cm) das faces y=0 e y=19
    data["links"]["viga_fundo_seg_1_area_segs"] = {
        "contour": [{
            "type": "poly",
            "points": [[0, 8], [100, 8], [100, 27], [0, 27], [0, 8]],
            "len": 100,
        }]
    }
    data["links"]["viga_segs"]["seg_bottom"][0]["points"] = [
        [0, 8], [100, 8], [100, 27], [0, 27], [0, 8],
    ]
    con.execute("UPDATE beams SET data_json=? WHERE id='b1'", (json.dumps(data),))
    con.commit()
    beams = load_beam_records(con, "p1")
    names = load_name_index(con, "p1")
    auditor = FvEvidenceAuditor(beams, names, "run_float")
    decisions = auditor.audit(selected={"V301"})
    by_field = {d.field_id: d for d in decisions}
    assert by_field["viga_fundo_seg_1_exists"].decision == "PENDENTE"
    assert by_field["viga_fundo_seg_1_area_segs"].decision == "PENDENTE"
    assert by_field["viga_fundo_seg_1_dim"].decision == "PENDENTE"
    assert not by_field["viga_fundo_seg_1_area_segs"].operations
    assert "estrutural" in by_field["viga_fundo_seg_1_area_segs"].reason.lower() or (
        "face DXF" in by_field["viga_fundo_seg_1_area_segs"].reason
    )
    con.close()


def test_lv_adapter_confirms_four_contracts(tmp_path: Path):
    db = _db(tmp_path)
    con = sqlite3.connect(db)
    beams = load_beam_records(con, "p1")
    names = load_name_index(con, "p1")
    auditor = LvEvidenceAuditor(beams, names, "run1")
    decisions = auditor.audit(selected={"V301"})
    by_field = {d.field_id: d for d in decisions}
    for key in (
        "lv_contract_PARA_A", "lv_contract_PARA_B",
        "lv_contract_PASSA_A", "lv_contract_PASSA_B",
        "viga_a_seg_1_dim", "viga_b_seg_1_dim",
        "viga_a_seg_4_abert_pilar_esq",
    ):
        assert by_field[key].decision == "CONFIRMAR", (key, by_field[key].decision, by_field[key].reason)
    con.close()
