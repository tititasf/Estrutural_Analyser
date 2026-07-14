from __future__ import annotations

from pathlib import Path

import pytest

from scripts.arete.qa_content_cache import ContentAddressedCache
from scripts.arete.qa_profile_probe import PROFILE_SCHEMA, load_profile, main, run_profile_probe
from scripts.arete.qa_n1_sources import load_requested_fields
from tests.test_qa_n1_field_probe import _db


def test_profile_resolves_cross_class_item_without_hardcoding(tmp_path: Path):
    profile = {
        "schema": PROFILE_SCHEMA,
        "class": "PIL",
        "version": "test",
        "authority": "checks_only",
        "n1": {"probes": {"face": {
            "question": "vínculo?",
            "fields": [
                {"id": "ref", "class": "PIL", "item": "{item}", "source": "payload", "path": "p_sD_v_passa_esq_n.label.0.text", "transform": "entity"},
                {"id": "beam", "class": "FV", "item_from": "ref", "source": "payload", "path": "fields.nome", "transform": "entity"},
            ],
            "checks": [{"id": "identity", "op": "same_entity", "left": "ref", "right": "beam"}],
        }}},
    }
    con = _db()
    result = run_profile_probe(
        con, profile, probe_id="face", item="P35", project_id="p",
        cache=ContentAddressedCache(tmp_path / "cache"),
    )
    assert result["overall"] == "PASS"
    assert result["profile"]["resolved_cross_class"]["beam"]["item"] == "V328"
    assert result["scope_authority"].startswith("field_checks_only")
    con.close()


def test_profile_fails_closed_when_reference_is_missing(tmp_path: Path):
    profile = {
        "schema": PROFILE_SCHEMA,
        "class": "PIL",
        "version": "test",
        "n1": {"probes": {"face": {
            "fields": [
                {"id": "ref", "class": "PIL", "item": "{item}", "source": "payload", "path": "missing"},
                {"id": "beam", "class": "FV", "item_from": "ref", "source": "payload", "path": "fields.nome"},
            ],
            "checks": [{"id": "identity", "op": "same_entity", "left": "ref", "right": "beam"}],
        }}},
    }
    con = _db()
    result = run_profile_probe(
        con, profile, probe_id="face", item="P35", project_id="p",
        cache=ContentAddressedCache(tmp_path / "cache"),
    )
    assert result["overall"] == "PENDENTE"
    assert "referência cross-classe ausente" in result["reason"]
    con.close()


def test_fv_cannot_read_lv_family_from_shared_beam_payload():
    con = _db()
    try:
        load_requested_fields(
            con, project_id="p", classe="FV", item="V328",
            fields=[{"id": "leak", "source": "payload", "path": "lv_generation_contracts.Para.A"}],
        )
    except ValueError as exc:
        assert "fora da família semântica de FV" in str(exc)
    else:
        raise AssertionError("FV leu família LV")
    con.close()


def test_lv_cannot_read_fv_family_from_shared_beam_payload():
    con = _db()
    try:
        load_requested_fields(
            con, project_id="p", classe="LV", item="V328",
            fields=[{"id": "leak", "source": "payload", "path": "fields.viga_fundo_seg_1_dim"}],
        )
    except ValueError as exc:
        assert "fora da família semântica de LV" in str(exc)
    else:
        raise AssertionError("LV leu família FV")
    con.close()


def test_fv_column_source_cannot_bypass_lv_allowlist():
    con = _db()
    try:
        load_requested_fields(
            con, project_id="p", classe="FV", item="V328",
            fields=[{"id": "leak", "source": "column", "path": "data_json.lv_generation_contracts"}],
        )
    except ValueError as exc:
        assert "fora da família semântica de FV" in str(exc)
    else:
        raise AssertionError("source=column contornou a fronteira FV/LV")
    con.close()


@pytest.mark.parametrize("classe", ["PIL", "LAJ", "FV", "LV"])
def test_real_class_profiles_have_executable_n1_and_n3_contract(classe: str):
    profile = load_profile(classe)
    assert profile["n1"]["probes"]
    assert profile["n3"]["identity_path"]
    assert profile["n3"]["expected_layers"]
    assert profile["n3"]["equivalence_strategy"]


def test_profile_cli_never_uses_sample_scope_implicitly():
    with pytest.raises(SystemExit) as exc:
        main(["--classe", "PIL", "--probe", "face_beam_identity_dimension_contact", "--item", "P35"])
    assert exc.value.code == 2
