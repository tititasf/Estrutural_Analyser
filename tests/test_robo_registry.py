import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from motor_reverso_base import ExtractionCandidate
from robo_registry import audit_module_contracts, get_class_plugin, load_robot_registry


def test_registry_maps_all_current_classes_to_real_contracts():
    registry = load_robot_registry()
    rows = audit_module_contracts(registry)

    assert {entry["class_id"] for entry in registry["classes"]} == {"PIL", "LV", "FV", "LAJ"}
    assert all(row["module_found"] for row in rows)
    assert all(row["callable_found"] for row in rows)
    assert get_class_plugin("PIL", registry)["extractor"]["callable"] == "extrair_ficha_pilar"


def test_registry_rejects_unknown_class(tmp_path):
    payload = json.loads((ROOT / "data" / "robo_registry.json").read_text(encoding="utf-8"))
    payload["classes"][0]["class_id"] = "ESC"
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="classe desconhecida"):
        load_robot_registry(path)


def test_new_extractors_cannot_self_promote():
    candidate = ExtractionCandidate(fields={"altura": 280}, confidence=0.8)
    assert candidate.tier == "T0"

    with pytest.raises(ValueError, match="T0"):
        ExtractionCandidate(fields={}, confidence=1.0, tier="T1")
