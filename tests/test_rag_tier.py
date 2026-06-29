import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rag_tier import (  # noqa: E402
    T0,
    T1,
    T2,
    TX,
    filter_visible_rows,
    get_tier,
    is_indexable,
    load_tombstones,
    revoke_item,
)


def test_draft_and_extracted_are_quarantine():
    assert get_tier({"id": "P1", "status": "draft"}) == T0
    assert get_tier({"id": "P2", "status": "extracted"}) == T0
    assert not is_indexable({"id": "P1", "status": "draft"})


def test_validated_rows_are_indexable():
    assert get_tier({"id": "P101", "status": "aprovado"}) == T1
    assert get_tier({"id": "L308", "is_validated": 1}) == T1
    assert get_tier({"id": "V7", "validated_fields_json": '{"b": 20}'}) == T1
    assert is_indexable({"id": "P101", "status": "aprovado"})


def test_consolidated_rows_are_t2_and_indexable():
    row = {"id": "P9", "status": "consolidado"}
    assert get_tier(row) == T2
    assert is_indexable(row)


def test_revoked_status_overrides_validated_state():
    row = {"id": "P101", "status": "revogado", "is_validated": 1}
    assert get_tier(row) == TX
    assert not is_indexable(row)


def test_tombstone_overrides_approved_state(tmp_path):
    tombstones_path = tmp_path / "rag_tombstones.json"

    event = revoke_item(
        "P101",
        reason="validacao humana revertida",
        revoked_by="tester",
        path=tombstones_path,
    )

    assert event["source_id"] == "P101"
    raw = json.loads(tombstones_path.read_text(encoding="utf-8"))
    assert "P101" in raw["items"]

    tombstones = load_tombstones(tombstones_path)
    row = {"id": "P101", "status": "aprovado"}
    assert get_tier(row, tombstones=tombstones) == TX
    assert not is_indexable(row, tombstones=tombstones)


def test_filter_visible_rows_keeps_only_t1_plus_and_excludes_revoked():
    rows = [
        {"id": "P1", "status": "draft"},
        {"id": "P101", "status": "aprovado"},
        {"id": "L308", "is_validated": 1},
        {"id": "V3", "status": "revogado"},
    ]

    visible = filter_visible_rows(rows)
    assert [row["id"] for row in visible] == ["P101", "L308"]

