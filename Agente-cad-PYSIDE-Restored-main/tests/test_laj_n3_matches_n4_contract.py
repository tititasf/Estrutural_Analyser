from pathlib import Path

import pytest

from src.core.laj_n3_stog_runner import assert_laj_n3_matches_n4_contract, build_laj_n3_args
from src.core.services.dxf_generator import DXFGeneratorService


def test_n3_laj_uses_same_generator_script_as_n4(tmp_path):
    obra = tmp_path / "Obra"
    n1_json = tmp_path / "n1_json"
    n3_out = tmp_path / "n3_out"
    script_n3, args_n3 = build_laj_n3_args(obra, n1_json_dir=n1_json, out_dir=n3_out, item="L327")
    script_n4, args_n4 = DXFGeneratorService(obra).build_args("LJ", item="L327")

    assert script_n3 == script_n4
    assert Path(script_n3).name == "gerar_lj_dxf_stog.py"
    assert "--json-dir" in args_n3
    assert str(n1_json) in args_n3
    assert "--out-dir" in args_n3
    assert str(n3_out) in args_n3
    assert "--json-dir" not in args_n4


def test_n3_contract_requires_matching_contour_and_internal_lines():
    n1 = {
        "coordenadas": [[0, 0], [100, 0], [100, 50], [0, 50]],
        "linhas_verticais": [{"value": 50.0}],
        "linhas_horizontais": [],
    }
    n4 = {
        "coordenadas": [[0, 0], [100, 0], [100, 50], [0, 50]],
        "linhas_verticais": [{"value": 50.0}],
        "linhas_horizontais": [],
    }
    assert_laj_n3_matches_n4_contract(n1, n4)
    n4["linhas_verticais"] = [{"value": 40.0}]
    with pytest.raises(ValueError, match="linhas_verticais"):
        assert_laj_n3_matches_n4_contract(n1, n4)
