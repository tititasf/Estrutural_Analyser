import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from classe_registry import canonicalize_class, load_registry, registered_classes, validate_registry


def test_default_registry_has_eight_dimensions_and_core_classes():
    registry = load_registry(ROOT / "data" / "classe_registry.json")
    assert [item["id"] for item in registry["dimensions"]] == list(range(1, 9))
    assert registered_classes(registry) == {"PIL", "LV", "FV", "LAJ"}


def test_aliases_are_safe_and_ambiguous_viga_is_preserved():
    registry = load_registry(ROOT / "data" / "classe_registry.json")
    assert canonicalize_class("pilar", registry) == ("PIL", True)
    assert canonicalize_class("laje", registry) == ("LAJ", True)
    assert canonicalize_class("viga", registry) == ("VIGA", False)
    assert canonicalize_class("garfo", registry) == ("GARFO", False)


def test_duplicate_alias_is_rejected():
    registry = json.loads((ROOT / "data" / "classe_registry.json").read_text(encoding="utf-8"))
    registry["classes"][1]["aliases"].append("PILAR")
    with pytest.raises(ValueError, match="alias duplicado"):
        validate_registry(registry)
