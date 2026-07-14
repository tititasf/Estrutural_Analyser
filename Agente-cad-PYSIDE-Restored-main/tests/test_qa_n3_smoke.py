from __future__ import annotations

import json
from pathlib import Path

import ezdxf

from scripts.arete.qa_n3_smoke import build_smoke_spec, run_n3_smoke


def _variant(tmp_path: Path, label: str, item: str) -> tuple[Path, Path]:
    contract = tmp_path / f"{label}.json"
    contract.write_text(json.dumps({"nome": item}), encoding="utf-8")
    dxf = tmp_path / f"{label}.dxf"
    doc = ezdxf.new("R2010")
    doc.layers.add("NOMENCLATURA")
    doc.layers.add("Painéis")
    msp = doc.modelspace()
    msp.add_text(f"{item}.A", dxfattribs={"layer": "NOMENCLATURA"})
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "Painéis"})
    doc.saveas(dxf)
    return contract, dxf


def _profile() -> dict:
    return {
        "class": "PIL", "version": "test",
        "n3": {
            "motor": "TEST", "variants": ["PARA", "PASSA"],
            "identity_path": "nome", "expected_layers": ["NOMENCLATURA", "Painéis"],
        },
    }


def test_n3_smoke_checks_each_variant_without_visual_claim(tmp_path: Path):
    para = _variant(tmp_path, "PARA", "P35")
    passa = _variant(tmp_path, "PASSA", "P35")
    result = run_n3_smoke(
        profile=_profile(), item="P35",
        contracts={"PARA": para[0], "PASSA": passa[0]},
        dxfs={"PARA": para[1], "PASSA": passa[1]}, cache=None,
    )
    assert result["overall"] == "PASS"
    assert result["profile"]["authority"].startswith("n3_structural_smoke_only")
    assert result["runtime"]["variants"] == 2


def test_n3_smoke_rejects_unpaired_variants(tmp_path: Path):
    contract, dxf = _variant(tmp_path, "PARA", "P35")
    try:
        build_smoke_spec(
            profile=_profile(), item="P35",
            contracts={"PARA": contract}, dxfs={"PASSA": dxf},
        )
    except ValueError as exc:
        assert "mesmos rótulos" in str(exc)
    else:
        raise AssertionError("variantes desemparelhadas foram aceitas")


def test_n3_smoke_rejects_variant_outside_profile(tmp_path: Path):
    contract, dxf = _variant(tmp_path, "INVENTADA", "P35")
    try:
        build_smoke_spec(
            profile=_profile(), item="P35",
            contracts={"INVENTADA": contract}, dxfs={"INVENTADA": dxf},
        )
    except ValueError as exc:
        assert "fora do perfil PIL" in str(exc)
    else:
        raise AssertionError("variante fora do perfil foi aceita")


def test_n3_smoke_accepts_layers_declared_per_variant(tmp_path: Path):
    contract, dxf = _variant(tmp_path, "CORTE", "P35")
    profile = _profile()
    profile["n3"]["variants"] = ["CORTE"]
    profile["n3"]["expected_layers_by_variant"] = {"CORTE": ["PainÃ©is"]}
    spec = build_smoke_spec(
        profile=profile, item="P35",
        contracts={"CORTE": contract}, dxfs={"CORTE": dxf},
    )
    paths = {field["path"] for field in spec["fields"] if field["source"] == "dxf_layer_count"}
    assert paths == {"PainÃ©is"}
