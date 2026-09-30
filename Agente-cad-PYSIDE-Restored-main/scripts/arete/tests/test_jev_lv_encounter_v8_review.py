"""Independent adversarial checks of the v8 source encounter boundary."""
import math
import json

from scripts.arete.jev_calibration.adapters_lv_v8 import (
    extract_four_contracts, match_encounter, source_encounter_identity,
)


def source(at=(0.0, 0.0)):
    return {"pavimento": "TEST", "beam": "V1", "face": "A",
            "wall_handle": "A1", "at": list(at),
            "wall_segment": [[0.0, 0.0], [0.0, 100.0]], "facts": {}}


def test_interior_coordinate_is_not_a_wall_endpoint():
    src = source((0.0, 25.0))
    assert source_encounter_identity(src) is None


def test_nonfinite_coordinate_is_not_an_identity():
    for bad in (math.nan, math.inf, -math.inf):
        assert source_encounter_identity(source((0.0, bad))) is None


def test_missing_wall_geometry_cannot_claim_encounter_identity():
    src = source()
    src.pop("wall_segment")
    assert source_encounter_identity(src) is None


def test_missing_pavement_cannot_collide_with_other_sources():
    src = source()
    src.pop("pavimento")
    assert source_encounter_identity(src) is None


def test_wrong_beam_baseline_cannot_match_same_coordinates():
    baseline = {"name": "V2", "links": {}}
    for side in ("a", "b"):
        for suffix in ("comprimento_total", "comp_total_passa"):
            baseline["links"][f"viga_{side}_seg_1_{suffix}"] = {
                f"seg_side_{side}": [{"points": [[0.0, 0.0], [0.0, 40.0]]}]
            }
    match = match_encounter(source=source(), n1_contracts=extract_four_contracts(baseline))
    assert match["pack_ready"] is False
    assert match["semantic_verdict"] is None
    assert match["status"] != "MATCHED_ENCOUNTER"


def test_inventory_tamper_cannot_reuse_embedded_hash(tmp_path, monkeypatch):
    from scripts.arete import jev_lv_encounter_identity_v8 as audit
    from scripts.arete.jev_calibration.hashing import sha256_json
    inventory = {"encounters": [], "source_dxf_sha256": "source"}
    expected = sha256_json(inventory)
    inventory["inventory_sha256"] = expected
    inventory["encounters"] = [{"beam": "V1", "at": [999, 999]}]
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")
    monkeypatch.setitem(audit.PAVEMENT_SPECS_V6, "TEST", {
        "inventory": path, "expected_inventory_sha256": expected, "project_id": "P1",
    })
    loaded = audit._load_frozen_encounters("TEST", {"V1"})
    assert loaded["sha_match"] is False


def test_changed_source_blocks_match_before_geometry(monkeypatch):
    from scripts.arete import jev_lv_encounter_identity_v8 as audit
    monkeypatch.setattr(audit, "TARGETS", ({"pavimento": "13_PAV", "beam": "V1",
                                           "catalog_project_id": "P1"},))
    monkeypatch.setattr(audit, "_payloads_by_item", lambda: {
        ("13_PAV", "V1"): {"identity_join": True, "payload": {},
                              "local_source_dxf_sha256": "changed"},
    })
    monkeypatch.setattr(audit, "_load_frozen_encounters", lambda *args: {
        "sha_match": True, "source_dxf_sha256": "frozen", "encounters": [source()],
    })
    def must_not_match(**kwargs):
        raise AssertionError("unsafe source reached geometry comparison")
    monkeypatch.setattr(audit, "match_encounter", must_not_match)
    result = audit.audit_comparisons()
    assert result["n_eligible"] == 0
    assert result["refusal_counts"] == {"ABSTAIN_SOURCE_IDENTITY": 1}
