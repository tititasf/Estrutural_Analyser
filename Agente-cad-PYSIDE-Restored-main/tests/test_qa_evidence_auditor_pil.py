"""Adaptador CAD independente para PIL (qa_evidence_auditor.PilEvidenceAuditor).

Espelha o padrão de tests/test_qa_evidence_auditor.py (LAJ): cada teste
reproduz um caso geométrico real e verifica que o adaptador re-deriva o fato
da geometria bruta, sem confiar no que já está persistido.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.arete.qa_evidence_auditor import (
    PilEvidenceAuditor,
    Pillar,
    cmd_apply,
    load_beams_for_project,
    load_pillars,
    load_slabs,
    required_pil_fields_for_state,
)


def _create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY, work_name TEXT, pavement_name TEXT, updated_at TEXT);
        CREATE TABLE pillars (
            id TEXT PRIMARY KEY, project_id TEXT, name TEXT, points_json TEXT,
            sides_data_json TEXT, links_json TEXT, extra_data_json TEXT,
            validated_fields_json TEXT, na_fields_json TEXT,
            validated_link_classes_json TEXT, na_link_classes_json TEXT,
            na_reasons_json TEXT, is_validated INTEGER
        );
        CREATE TABLE beams (
            id TEXT PRIMARY KEY, project_id TEXT, name TEXT, data_json TEXT,
            links_json TEXT, is_validated INTEGER
        );
        CREATE TABLE slabs (
            id TEXT PRIMARY KEY, project_id TEXT, name TEXT, points_json TEXT,
            links_json TEXT, validated_fields_json TEXT, na_fields_json TEXT,
            validated_link_classes_json TEXT, na_link_classes_json TEXT,
            na_reasons_json TEXT, extra_data_json TEXT, is_validated INTEGER
        );
        """
    )


def _insert_pillar(con, *, pid, name, points, links, extra=None, sides_data=None):
    con.execute(
        "INSERT INTO pillars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            pid, "proj", name, json.dumps(points),
            json.dumps(sides_data or {}), json.dumps(links), json.dumps(extra or {}),
            json.dumps([]), json.dumps([]), json.dumps({}), json.dumps({}), json.dumps({}), 0,
        ),
    )


def _insert_beam(con, *, bid, name, data):
    con.execute("INSERT INTO beams VALUES (?,?,?,?,?,?)", (bid, "proj", name, json.dumps(data), json.dumps({}), 0))


def _insert_slab(con, *, sid, name, points):
    con.execute(
        "INSERT INTO slabs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (sid, "proj", name, json.dumps(points), json.dumps({}), json.dumps([]), json.dumps([]),
         json.dumps({}), json.dumps({}), json.dumps({}), json.dumps({}), 0),
    )


# Pilar horizontal 60x19 reproduzindo P35: face A/B longas (y=1963/1982),
# C/D curtas (x=4492.4/4552.4).
_P35_POINTS = [[4492.4, 1963.0], [4552.4, 1963.0], [4552.4, 1982.0], [4492.4, 1982.0]]

# V308: corre paralela a A/B (dim 19/55), termina no canto C — mesma largura
# (19) da espessura do pilar -> Caso 4 (interior) em C.
_V308_DATA = {
    "name": "V308", "dim": "19/55",
    "geometry": {"classified": {"seg_bottom": [
        [[4201.4, 1963.0], [4492.4, 1963.0]],
    ]}},
}

# V328: vertical (perpendicular a A/B), parede direita alinhada com a face D.
_V328_DATA = {
    "name": "V328", "dim": "19/55",
    "geometry": {"classified": {"seg_bottom": [
        [[4552.4, 1982.0], [4552.4, 2242.0]],
        [[4533.4, 1982.0], [4533.4, 2242.0]],
    ]}},
}


def test_face_viga_confirms_para_and_passa_from_independent_beam_geometry(tmp_path: Path):
    """Faces A/D re-derivadas da geometria da viga (não do texto persistido)."""
    db = tmp_path / "pil.vision"
    con = sqlite3.connect(db)
    _create_schema(con)
    links = {
        "name": {"label": [{"text": "P35"}]},
        "pilar_segs": {"segments": [{"type": "poly", "points": _P35_POINTS + [_P35_POINTS[0]]}]},
        "p_sA_l1_n": {"label": [{"text": "SEM LAJE"}]},
        "p_sA_v_passa_esq_n": {"label": [{"text": "V308"}]},
        "p_sD_l1_n": {"label": [{"text": "SEM LAJE"}]},
        "p_sD_v_passa_esq_n": {"label": [{"text": "V328"}]},
    }
    _insert_pillar(con, pid="pil1", name="P35", points=_P35_POINTS, links=links)
    _insert_beam(con, bid="b1", name="V308", data=_V308_DATA)
    _insert_beam(con, bid="b2", name="V328", data=_V328_DATA)
    con.commit()

    pillars = load_pillars(con, "proj")
    beams = load_beams_for_project(con, "proj")
    slabs = load_slabs(con, "proj")
    auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id="r1")
    decisions = {d.field_id: d for d in auditor.audit()}

    assert decisions["p_sA_v"].decision == "CONFIRMAR"
    assert "V308" in decisions["p_sA_v"].reason
    assert decisions["p_sD_v"].decision == "CONFIRMAR"
    assert "V328" in decisions["p_sD_v"].reason
    con.close()


def test_face_viga_interior_case4_confirms_without_opening_field(tmp_path: Path):
    """Face C sem p_s{face}_v_* persistido, mas motor acha Caso 4 -> CONFIRMAR."""
    db = tmp_path / "pil.vision"
    con = sqlite3.connect(db)
    _create_schema(con)
    links = {
        "name": {"label": [{"text": "P35"}]},
        "pilar_segs": {"segments": [{"type": "poly", "points": _P35_POINTS + [_P35_POINTS[0]]}]},
        "p_sC_l1_n": {"label": [{"text": "SEM LAJE"}]},
    }
    _insert_pillar(con, pid="pil1", name="P35", points=_P35_POINTS, links=links)
    _insert_beam(con, bid="b1", name="V308", data=_V308_DATA)
    con.commit()

    pillars = load_pillars(con, "proj")
    beams = load_beams_for_project(con, "proj")
    slabs = load_slabs(con, "proj")
    auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id="r1")
    decisions = {d.field_id: d for d in auditor.audit()}

    assert decisions["p_sC_v"].decision == "CONFIRMAR"
    assert "Caso 4" in decisions["p_sC_v"].reason
    assert decisions["p_sC_v"].operations, "CONFIRMAR de interior precisa gerar validate_field (achado do dono: sem isso o campo nunca ganha origem qa_agente)"
    con.close()


def test_face_viga_mismatch_between_motor_and_persisted_requires_human(tmp_path: Path):
    """Persistido diz V999 (viga inexistente); motor não encontra evidência -> REVISAR_HUMANO."""
    db = tmp_path / "pil.vision"
    con = sqlite3.connect(db)
    _create_schema(con)
    links = {
        "name": {"label": [{"text": "P35"}]},
        "pilar_segs": {"segments": [{"type": "poly", "points": _P35_POINTS + [_P35_POINTS[0]]}]},
        "p_sA_l1_n": {"label": [{"text": "SEM LAJE"}]},
        "p_sA_v_passa_esq_n": {"label": [{"text": "V999"}]},
    }
    _insert_pillar(con, pid="pil1", name="P35", points=_P35_POINTS, links=links)
    con.commit()

    pillars = load_pillars(con, "proj")
    beams = load_beams_for_project(con, "proj")
    slabs = load_slabs(con, "proj")
    auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id="r1")
    decisions = {d.field_id: d for d in auditor.audit()}

    assert decisions["p_sA_v"].decision == "REVISAR_HUMANO"
    assert decisions["p_sA_v"].requires_human
    con.close()


def test_face_laje_rejects_slab_too_far_to_be_real_contact(tmp_path: Path):
    """Reproduz achado real do P35: laje persistida a 556cm não é contato -> PENDENTE."""
    db = tmp_path / "pil.vision"
    con = sqlite3.connect(db)
    _create_schema(con)
    links = {
        "name": {"label": [{"text": "P35"}]},
        "pilar_segs": {"segments": [{"type": "poly", "points": _P35_POINTS + [_P35_POINTS[0]]}]},
        "p_sD_l1_n": {"label": [{"text": "L325"}]},
    }
    _insert_pillar(con, pid="pil1", name="P35", points=_P35_POINTS, links=links)
    far_slab_points = [[3807.4, 1982.0], [3936.4, 1982.0], [3936.4, 2441.0], [3807.4, 2441.0]]
    _insert_slab(con, sid="s1", name="L325", points=far_slab_points)
    con.commit()

    pillars = load_pillars(con, "proj")
    beams = load_beams_for_project(con, "proj")
    slabs = load_slabs(con, "proj")
    auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id="r1")
    decisions = {d.field_id: d for d in auditor.audit()}

    assert decisions["p_sD_l1_n"].decision == "PENDENTE"
    con.close()


def test_face_laje_confirms_real_geometric_contact(tmp_path: Path):
    """Laje realmente encostada na face -> CONFIRMAR com evidência de distância."""
    db = tmp_path / "pil.vision"
    con = sqlite3.connect(db)
    _create_schema(con)
    links = {
        "name": {"label": [{"text": "P35"}]},
        "pilar_segs": {"segments": [{"type": "poly", "points": _P35_POINTS + [_P35_POINTS[0]]}]},
        "p_sD_l1_n": {"label": [{"text": "L900"}]},
    }
    _insert_pillar(con, pid="pil1", name="P35", points=_P35_POINTS, links=links)
    touching_slab_points = [[4552.4, 1963.0], [4700.0, 1963.0], [4700.0, 1982.0], [4552.4, 1982.0]]
    _insert_slab(con, sid="s1", name="L900", points=touching_slab_points)
    con.commit()

    pillars = load_pillars(con, "proj")
    beams = load_beams_for_project(con, "proj")
    slabs = load_slabs(con, "proj")
    auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id="r1")
    decisions = {d.field_id: d for d in auditor.audit()}

    assert decisions["p_sD_l1_n"].decision == "CONFIRMAR"
    assert decisions["p_sD_l1_n"].evidence[0]["distance"] < 1.0
    con.close()


def test_dim_flags_mislabeled_link_and_never_confirms(tmp_path: Path):
    """Link 'dim' aponta pro rótulo de uma viga (achado real do P35): finding
    é registrado E 'dim' NUNCA confirma, mesmo que o bbox x ficha 'Dimensão
    (b x h)' bata por coincidência — vínculo contaminado exige revisão
    humana sempre (correção do dono, 2026-07-17: zero tolerância a vínculo
    desconexo, mesmo caso antigo permitia CONFIRMAR e escondia o problema).
    """
    db = tmp_path / "pil.vision"
    con = sqlite3.connect(db)
    _create_schema(con)
    links = {
        "name": {"label": [{"text": "P35"}]},
        "pilar_segs": {"segments": [{"type": "poly", "points": _P35_POINTS + [_P35_POINTS[0]]}]},
        "dim": {"label": [{"text": "V328"}]},
    }
    extra = {"fields": {"Dimensão (b x h)": "60x19"}}
    _insert_pillar(con, pid="pil1", name="P35", points=_P35_POINTS, links=links, extra=extra)
    con.commit()

    pillars = load_pillars(con, "proj")
    beams = load_beams_for_project(con, "proj")
    slabs = load_slabs(con, "proj")
    auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id="r1")
    decisions = {d.field_id: d for d in auditor.audit()}

    assert decisions["dim"].decision == "REVISAR_HUMANO"
    assert decisions["dim"].requires_human is True
    codes = {f["code"] for f in auditor.findings if f["item"] == "P35" and f["field_id"] == "dim"}
    assert "PIL-DIM-LINK-MISLABELED" in codes
    con.close()


# Geometria real de P11/V302 (13_PAV, Obra_TREINO_1) reproduzindo o achado
# 2026-07-16: viga corredor longa (passa por A/B) cuja parede também alinha
# com a face curta D via `enrich_pillar_report_with_beams` (source=
# beam_wall_alignment em `lajes`, NUNCA em `face_beams`).
_P11_POINTS = [[1572.8825, 2661.038], [1652.8825, 2661.038], [1652.8825, 2680.038], [1572.8825, 2680.038], [1572.8825, 2661.038]]
_V302_DATA = {
    "name": "V302", "dim": "19/55",
    "geometry": {"classified": {"seg_bottom": [
        [[1387.3825, 2680.038], [1197.8825, 2680.038]], [[1197.8825, 2661.038], [1380.3825, 2661.038]],
        [[1572.8825, 2680.038], [1387.3825, 2680.038]], [[1394.3825, 2661.038], [1572.8825, 2661.038]],
        [[1652.8825, 2661.038], [2040.3825, 2661.038]], [[2040.3825, 2680.038], [1652.8825, 2680.038]],
        [[2059.3825, 2661.038], [2477.3825, 2661.038]], [[2477.3825, 2680.038], [2059.3825, 2680.038]],
        [[2914.3825, 2680.038], [2496.3825, 2680.038]], [[2496.3825, 2661.038], [2914.3825, 2661.038]],
        [[3351.3825, 2680.038], [2933.3825, 2680.038]], [[2933.3825, 2661.038], [3360.8825, 2661.038]],
        [[3360.8825, 2661.038], [3797.8825, 2661.038]], [[3788.3825, 2680.038], [3370.3825, 2680.038]],
        [[3797.8825, 2661.038], [4174.8825, 2661.038]], [[4174.8825, 2680.038], [3807.3825, 2680.038]],
        [[4552.3825, 2661.038], [4668.8825, 2661.038]], [[4649.8825, 2680.038], [4542.8825, 2680.038]],
        [[4294.8825, 2661.038], [4533.3825, 2661.038]], [[4542.8825, 2680.038], [4294.8825, 2680.038]],
    ]}},
}


def test_connections_confirms_beam_wall_alignment_entry_not_in_face_beams(tmp_path: Path):
    """Achado 2026-07-16 (P11 face D): connections.details tem uma entrada
    source=beam_wall_alignment que só existe na lista `lajes` do motor, nunca
    em `face_beams`. Comparar só contra face_beams gerava REVISAR_HUMANO
    falso; a correção usa face_beams UNIÃO as entradas beam_wall_alignment de
    `lajes` do mesmo motor/rodada.
    """
    db = tmp_path / "pil.vision"
    con = sqlite3.connect(db)
    _create_schema(con)
    links = {
        "name": {"label": [{"text": "P11"}]},
        "pilar_segs": {"segments": [{"type": "poly", "points": _P11_POINTS}]},
        "connections": {"lajes_conectadas": {"details": [
            {"side": "D", "face": "VIGA", "content_type": "viga", "laje": None,
             "source": "beam_wall_alignment", "viga": {"name": "V302", "dim": "19/55"}},
        ]}},
    }
    _insert_pillar(con, pid="pil1", name="P11", points=_P11_POINTS, links=links)
    _insert_beam(con, bid="b1", name="V302", data=_V302_DATA)
    con.commit()

    pillars = load_pillars(con, "proj")
    beams = load_beams_for_project(con, "proj")
    slabs = load_slabs(con, "proj")
    auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id="r1")
    decisions = {d.field_id: d for d in auditor.audit()}

    assert decisions["connections"].decision == "CONFIRMAR", decisions["connections"].reason
    con.close()


def test_connections_still_flags_real_mismatch_as_revisar_humano(tmp_path: Path):
    """Regressão: a correção não deve deixar de pegar uma divergência real
    (viga persistida que nem o motor nem `lajes` confirmam em lugar nenhum).
    """
    db = tmp_path / "pil.vision"
    con = sqlite3.connect(db)
    _create_schema(con)
    links = {
        "name": {"label": [{"text": "P11"}]},
        "pilar_segs": {"segments": [{"type": "poly", "points": _P11_POINTS}]},
        "connections": {"lajes_conectadas": {"details": [
            {"side": "D", "face": "VIGA", "content_type": "viga", "laje": None,
             "source": "beam_wall_alignment", "viga": {"name": "V999_INEXISTENTE", "dim": "19/55"}},
        ]}},
    }
    _insert_pillar(con, pid="pil1", name="P11", points=_P11_POINTS, links=links)
    _insert_beam(con, bid="b1", name="V302", data=_V302_DATA)
    con.commit()

    pillars = load_pillars(con, "proj")
    beams = load_beams_for_project(con, "proj")
    slabs = load_slabs(con, "proj")
    auditor = PilEvidenceAuditor(pillars, beams, slabs, run_id="r1")
    decisions = {d.field_id: d for d in auditor.audit()}

    assert decisions["connections"].decision == "REVISAR_HUMANO"
    assert decisions["connections"].evidence[0]["observed"] == "V999_INEXISTENTE"
    con.close()


def test_required_pil_fields_are_dynamic_per_item_shape():
    """Campos obrigatórios variam com as faces realmente presentes no payload."""
    state_rect = {"links": {"p_sA_l1_n": {}, "p_sB_l1_n": {}, "p_sC_l1_n": {}, "p_sD_l1_n": {}}}
    required = required_pil_fields_for_state(state_rect)
    assert {"name", "pilar_segs", "dim", "connections"}.issubset(required)
    assert {"p_sA_l1_n", "p_sB_l1_n", "p_sC_l1_n", "p_sD_l1_n"}.issubset(required)
    assert "p_sE_l1_n" not in required


def test_apply_seal_stays_blocked_until_all_required_pil_fields_resolve(tmp_path: Path):
    """Ponta a ponta: review -> apply --seal-complete não sela enquanto uma
    face (aqui, D) permanecer PENDENTE — mesmo com todas as outras CONFIRMAR.
    """
    db = tmp_path / "pil.vision"
    con = sqlite3.connect(db)
    _create_schema(con)
    con.execute("INSERT INTO projects VALUES ('proj', 'OBRA', 'PAV', '2026-07-15')")
    links = {
        "name": {"label": [{"text": "P35"}]},
        "pilar_segs": {"segments": [{"type": "poly", "points": _P35_POINTS + [_P35_POINTS[0]]}]},
        "p_sA_l1_n": {"label": [{"text": "SEM LAJE"}]},
        "p_sB_l1_n": {"label": [{"text": "SEM LAJE"}]},
        "p_sC_l1_n": {"label": [{"text": "SEM LAJE"}]},
        "p_sD_l1_n": {"label": [{"text": "L325"}]},  # fica PENDENTE (sem contato)
    }
    extra = {"fields": {"Dimensão (b x h)": "60x19"}}
    _insert_pillar(con, pid="pil1", name="P35", points=_P35_POINTS, links=links, extra=extra)
    far_slab_points = [[3807.4, 1982.0], [3936.4, 1982.0], [3936.4, 2441.0], [3807.4, 2441.0]]
    _insert_slab(con, sid="s1", name="L325", points=far_slab_points)
    con.commit()
    con.close()

    from scripts.arete.qa_evidence_auditor import build_parser

    parser = build_parser()
    review_args = parser.parse_args([
        "review", "--db", str(db), "--project-id", "proj", "--classe", "PIL",
        "--out-dir", str(tmp_path / "out"),
    ])
    from scripts.arete.qa_evidence_auditor import cmd_review

    cmd_review(review_args)
    apply_args = parser.parse_args([
        "apply", "--db", str(db), "--project-id", "proj",
        "--run", str(tmp_path / "out"), "--seal-complete",
    ])
    cmd_apply(apply_args)

    con2 = sqlite3.connect(db)
    is_validated = con2.execute("SELECT is_validated FROM pillars WHERE name='P35'").fetchone()[0]
    validated_fields = json.loads(con2.execute("SELECT validated_fields_json FROM pillars WHERE name='P35'").fetchone()[0])
    con2.close()

    assert is_validated == 0
    assert "p_sD_l1_n" not in validated_fields
    assert "name" in validated_fields and "pilar_segs" in validated_fields
