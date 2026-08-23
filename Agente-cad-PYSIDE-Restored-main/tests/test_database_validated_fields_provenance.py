"""`validated_fields`/`na_fields` existem em produção em dois formatos:
lista simples de nomes (legado) e dicionário de proveniência
(`{"campo": [{"origem": "qa_agente", "quando": "..."}]}`, formato real do
13_PAV — 100% dos pilares). `save_pillar`/`save_beam`/`save_slab` faziam
`b.get('validated_fields', []) + val_fields`, que explode com `TypeError`
quando qualquer um dos dois lados é dict — e o `except` de cada método só
loga, então o save "funcionava" sem gravar nada. Estes testes cobrem os
helpers de merge e o round-trip real de cada tabela nos dois formatos.
"""
from src.core.database import DatabaseManager


# --- _merge_validated_field_tracking -----------------------------------

def test_merge_list_list_dedupes():
    got = DatabaseManager._merge_validated_field_tracking(
        ["a", "b"], ["b", "c"],
    )
    assert set(got) == {"a", "b", "c"}
    assert isinstance(got, list)


def test_merge_list_list_empty_sides():
    assert DatabaseManager._merge_validated_field_tracking([], []) == []
    assert DatabaseManager._merge_validated_field_tracking(None, None) == []
    assert DatabaseManager._merge_validated_field_tracking(None, ["a"]) == ["a"]


def test_merge_dict_dict_unions_provenance_entries():
    old = {"dim": [{"origem": "humano_app", "quando": "2026-08-01"}]}
    new = {"dim": [{"origem": "qa_agente", "quando": "2026-08-20"}], "name": [{"origem": "qa_agente", "quando": None}]}
    got = DatabaseManager._merge_validated_field_tracking(old, new)
    assert isinstance(got, dict)
    assert {"origem": "humano_app", "quando": "2026-08-01"} in got["dim"]
    assert {"origem": "qa_agente", "quando": "2026-08-20"} in got["dim"]
    assert len(got["dim"]) == 2
    assert got["name"] == [{"origem": "qa_agente", "quando": None}]


def test_merge_dict_dict_does_not_duplicate_identical_entries():
    entry = {"origem": "qa_agente", "quando": "2026-08-20"}
    got = DatabaseManager._merge_validated_field_tracking({"dim": [entry]}, {"dim": [entry]})
    assert got["dim"] == [entry]


def test_merge_dict_list_promotes_result_to_dict_without_losing_names():
    old = {"dim": [{"origem": "humano_app", "quando": None}]}
    new = ["dim", "name"]
    got = DatabaseManager._merge_validated_field_tracking(old, new)
    assert isinstance(got, dict)
    assert set(got.keys()) == {"dim", "name"}
    assert got["dim"] == [{"origem": "humano_app", "quando": None}]
    assert got["name"] == []


def test_merge_list_dict_promotes_result_to_dict_without_losing_names():
    old = ["dim"]
    new = {"name": [{"origem": "qa_agente", "quando": "2026-08-20"}]}
    got = DatabaseManager._merge_validated_field_tracking(old, new)
    assert isinstance(got, dict)
    assert set(got.keys()) == {"dim", "name"}
    assert got["dim"] == []
    assert got["name"] == [{"origem": "qa_agente", "quando": "2026-08-20"}]


# --- _validated_field_names ---------------------------------------------

def test_validated_field_names_from_dict():
    assert DatabaseManager._validated_field_names(
        {"dim": [{"origem": "qa_agente"}], "name": []},
    ) == {"dim", "name"}


def test_validated_field_names_from_list():
    assert DatabaseManager._validated_field_names(["dim", "name"]) == {"dim", "name"}


def test_validated_field_names_from_empty_or_none():
    assert DatabaseManager._validated_field_names([]) == set()
    assert DatabaseManager._validated_field_names(None) == set()
    assert DatabaseManager._validated_field_names({}) == set()


# --- save_pillar round-trip, formato de proveniência real do 13_PAV -----

def test_save_pillar_survives_provenance_dict_format(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.vision"))
    project_id = "project"
    pillar_id = "project_p_1"

    original = {
        "id": pillar_id,
        "name": "P11",
        "type": "Pilar",
        "area_val": 900.0,
        "dim": "30/30",
        "validated_fields": {
            "dim": [{"origem": "humano_app", "quando": "2026-08-01T00:00:00"}],
        },
    }
    db.save_pillar(original, project_id, trust_current_validation=True)

    updated = {
        "id": pillar_id,
        "name": "P11",
        "type": "Pilar",
        "area_val": 900.0,
        "dim": "40/40",  # tentativa de recomputar sem trust_current_validation
        "validated_fields": {
            "name": [{"origem": "qa_agente", "quando": "2026-08-23T00:00:00"}],
        },
    }
    db.save_pillar(updated, project_id)

    saved = db.load_pillars(project_id)[0]
    assert saved["dim"] == "30/30", "campo validado por humano não pode ser sobrescrito"
    assert isinstance(saved["validated_fields"], dict)
    assert set(saved["validated_fields"].keys()) == {"dim", "name"}
    assert saved["validated_fields"]["dim"] == [
        {"origem": "humano_app", "quando": "2026-08-01T00:00:00"},
    ]


def test_save_pillar_legacy_list_format_still_works(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.vision"))
    project_id = "project"
    pillar_id = "project_p_2"

    original = {
        "id": pillar_id,
        "name": "P12",
        "type": "Pilar",
        "area_val": 400.0,
        "dim": "20/20",
        "validated_fields": ["dim"],
    }
    db.save_pillar(original, project_id, trust_current_validation=True)

    updated = {
        "id": pillar_id,
        "name": "P12",
        "type": "Pilar",
        "area_val": 400.0,
        "dim": "99/99",
        "validated_fields": [],
    }
    db.save_pillar(updated, project_id)

    saved = db.load_pillars(project_id)[0]
    assert saved["dim"] == "20/20"
    assert saved["validated_fields"] == ["dim"]


# --- save_beam round-trip -------------------------------------------------

def test_save_beam_survives_provenance_dict_format(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.vision"))
    project_id = "project"
    beam_id = "project_b_1"

    original = {
        "id": beam_id,
        "name": "VF301",
        "id_item": "01",
        "type": "Viga",
        "fields": {"viga_fundo_seg_1_dim": "14/55"},
        "validated_fields": {
            "viga_fundo_seg_1_dim": [{"origem": "humano_app", "quando": "2026-08-01T00:00:00"}],
        },
    }
    db.save_beam(original, project_id, trust_current_validation=True)

    fresh = {
        "id": beam_id,
        "name": "VF301",
        "id_item": "01",
        "type": "Viga",
        "fields": {"viga_fundo_seg_1_dim": "19/66"},
        "validated_fields": {},
    }
    db.save_beam(fresh, project_id)

    saved = db.load_beams(project_id)[0]
    assert saved["fields"]["viga_fundo_seg_1_dim"] == "14/55"
    assert isinstance(saved["validated_fields"], dict)
    assert "viga_fundo_seg_1_dim" in saved["validated_fields"]


def test_save_beam_legacy_list_format_still_works(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.vision"))
    project_id = "project"
    beam_id = "project_b_2"

    original = {
        "id": beam_id,
        "name": "V308",
        "id_item": "02",
        "type": "Viga",
        "fields": {"viga_fundo_seg_1_dim": "14/55"},
        "validated_fields": ["viga_fundo_seg_1_dim"],
    }
    db.save_beam(original, project_id, trust_current_validation=True)

    fresh = {
        "id": beam_id,
        "name": "V308",
        "id_item": "02",
        "type": "Viga",
        "fields": {"viga_fundo_seg_1_dim": "19/66"},
        "validated_fields": [],
    }
    db.save_beam(fresh, project_id)

    saved = db.load_beams(project_id)[0]
    assert saved["fields"]["viga_fundo_seg_1_dim"] == "14/55"
    assert saved["validated_fields"] == ["viga_fundo_seg_1_dim"]


# --- save_slab round-trip --------------------------------------------------

def test_save_slab_survives_provenance_dict_format(tmp_path):
    db = DatabaseManager(str(tmp_path / "test.vision"))
    project_id = "project"
    slab_id = "project_s_1"

    original = {
        "id": slab_id,
        "name": "L1",
        "type": "Laje",
        "espessura": "12",
        "validated_fields": {
            "espessura": [{"origem": "humano_app", "quando": "2026-08-01T00:00:00"}],
        },
    }
    db.save_slab(original, project_id, trust_current_validation=True)

    updated = {
        "id": slab_id,
        "name": "L1",
        "type": "Laje",
        "espessura": "15",
        "validated_fields": {},
    }
    db.save_slab(updated, project_id)

    saved = db.load_slabs(project_id)[0]
    assert saved["espessura"] == "12"
    assert isinstance(saved["validated_fields"], dict)
    assert "espessura" in saved["validated_fields"]
