import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "Agente-cad-PYSIDE-Restored-main"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.ui.canvas import CADCanvas  # noqa: E402


def _slots(value):
    return list(CADCanvas._iter_renderable_link_slots(value))


def test_canonical_slot_list_is_rendered():
    link = {"type": "text", "text": "P1", "pos": [1, 2]}
    assert _slots({"label": [link]}) == [("label", [link])]


def test_legacy_direct_link_is_rendered():
    link = {"type": "poly", "points": [[0, 0], [1, 1]]}
    assert _slots(link) == [("value", [link])]


def test_semantic_connection_metadata_is_not_rendered():
    connections = {
        "lajes_conectadas": {
            "value": "L301",
            "details": [{"laje": "L301", "side": "B", "face": "DIR"}],
        }
    }
    assert _slots(connections) == []


def test_mixed_payload_filters_non_drawable_values():
    drawable = {"type": "line", "points": [[0, 0], [1, 1]]}
    slots = {"label": ["invalid", {"text": "missing type"}, drawable, None]}
    assert _slots(slots) == [("label", [drawable])]
