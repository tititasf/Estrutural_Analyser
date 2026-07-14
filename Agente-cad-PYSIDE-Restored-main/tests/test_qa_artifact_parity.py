from __future__ import annotations

import json
from pathlib import Path

import ezdxf
import pytest

from scripts.arete.qa_artifact_parity import SPEC_SCHEMA, run_parity
from scripts.arete.qa_content_cache import ContentAddressedCache


def _artifacts(tmp_path: Path) -> dict:
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"opening": {"width": 11}}), encoding="utf-8")
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"abertura_A_1": {"largura": 11}}), encoding="utf-8")
    html = tmp_path / "index.html"
    html.write_text("<html><body>Abertura A: 11 cm</body></html>", encoding="utf-8")
    dxf = tmp_path / "item.dxf"
    document = ezdxf.new("R2010")
    document.layers.add("PAINEIS")
    document.modelspace().add_line((0, 0), (10, 0), dxfattribs={"layer": "PAINEIS"})
    document.modelspace().add_text("P35.A")
    document.saveas(dxf)
    return {
        "contract": contract.name, "payload": payload.name,
        "html": html.name, "dxf": dxf.name,
    }


def _spec(tmp_path: Path) -> dict:
    return {
        "schema": SPEC_SCHEMA,
        "question": "A largura declarada percorre contrato, payload, DXF e HTML?",
        "variants": {"PARA": _artifacts(tmp_path)},
        "fields": [
            {"id": "contract.width", "variant": "PARA", "source": "contract", "path": "opening.width", "transform": "number"},
            {"id": "payload.width", "variant": "PARA", "source": "payload", "path": "abertura_A_1.largura", "transform": "number"},
            {"id": "payload.width_text", "variant": "PARA", "source": "payload", "path": "abertura_A_1.largura", "transform": "text"},
            {"id": "html", "variant": "PARA", "source": "html", "path": "", "transform": "text"},
            {"id": "dxf.lines", "variant": "PARA", "source": "dxf_entity_count", "path": "LINE", "transform": "number"},
            {"id": "dxf.texts", "variant": "PARA", "source": "dxf_texts", "path": "", "transform": "raw"},
            {"id": "dxf.text_blob", "variant": "PARA", "source": "dxf_text_blob", "path": "", "transform": "text"},
            {"id": "dxf.layers", "variant": "PARA", "source": "dxf_layers", "path": "", "transform": "raw"},
            {"id": "dxf.types", "variant": "PARA", "source": "dxf_entity_types", "path": "", "transform": "raw"},
        ],
        "checks": [
            {"id": "contract_payload", "op": "number_close", "left": "contract.width", "right": "payload.width"},
            {"id": "payload_html", "op": "contains", "left": "html", "right": "payload.width_text"},
            {"id": "dxf_line", "op": "number_close", "left": "dxf.lines", "value": 1},
            {"id": "dxf_text_list", "op": "contains", "left": "dxf.texts", "value": "P35.A"},
            {"id": "dxf_text_blob", "op": "contains", "left": "dxf.text_blob", "value": "P35"},
            {"id": "dxf_layer", "op": "contains", "left": "dxf.layers", "value": "PAINEIS"},
            {"id": "dxf_type", "op": "contains", "left": "dxf.types", "value": "TEXT"},
        ],
    }


def test_artifact_parity_checks_declared_chain_and_reuses_cache(tmp_path: Path):
    spec = _spec(tmp_path)
    cache = ContentAddressedCache(tmp_path / "cache")
    first = run_parity(spec, base_dir=tmp_path, cache=cache)
    second = run_parity(spec, base_dir=tmp_path, cache=cache)
    assert first["overall"] == "PASS"
    assert first["runtime"]["cache_hit"] is False
    assert second["runtime"]["cache_hit"] is True
    assert first["scope_authority"].startswith("declared_artifact_fields_only")
    assert set(first["variants"]["PARA"]["hashes"]) == {"contract", "payload", "html", "dxf"}


def test_artifact_parity_exposes_missing_dxf_metadata(tmp_path: Path):
    spec = _spec(tmp_path)
    spec["fields"].append({
        "id": "dxf.opening_metadata", "variant": "PARA",
        "source": "dxf_xdata", "path": "ARETE_QA", "transform": "raw",
    })
    spec["checks"].append({
        "id": "metadata_present", "op": "present", "left": "dxf.opening_metadata",
    })
    result = run_parity(spec, base_dir=tmp_path, cache=None)
    assert result["overall"] == "FAIL"
    assert result["provenance"]["missing_dxf_metadata"] is True
    assert result["checks"][-1]["status"] == "FAIL"


@pytest.mark.parametrize("missing", ["fields", "checks"])
def test_artifact_parity_rejects_empty_proof(missing: str, tmp_path: Path):
    spec = _spec(tmp_path)
    spec[missing] = []
    with pytest.raises(ValueError, match=missing):
        run_parity(spec, base_dir=tmp_path, cache=None)


def test_artifact_parity_rejects_variant_without_artifact(tmp_path: Path):
    spec = _spec(tmp_path)
    spec["variants"] = {"PARA": {}}
    with pytest.raises(ValueError, match="sem artefatos"):
        run_parity(spec, base_dir=tmp_path, cache=None)
