import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from rag_tier import T0, T1, get_tier, is_indexable


def test_cli_approved_row_stays_quarantined():
    row = {
        "id": "P103",
        "status": "aprovado",
        "validation_origin": "cli_auto",
    }

    assert get_tier(row) == T0
    assert is_indexable(row) is False


def test_synthetic_metadata_blocks_t1_even_if_status_approved():
    row = {
        "id": "L999",
        "status": "aprovado",
        "metadata_json": '{"source":"looper","score":0.99}',
    }

    assert get_tier(row) == T0
    assert is_indexable(row) is False


def test_human_ui_approved_row_can_be_t1():
    row = {
        "id": "P101",
        "status": "aprovado",
        "validation_origin": "human_ui",
    }

    assert get_tier(row) == T1
    assert is_indexable(row) is True

