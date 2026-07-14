from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.arete.qa_pil_coverage import build_pil_coverage


def _link(text: str) -> dict:
    return {"label": [{"text": text, "role": "label", "pos": [0, 0]}]}


def _variant(tmp_path: Path, mode: str) -> dict:
    artifacts = {}
    for kind, suffix in (("json", ".json"), ("abcd", ".dxf"), ("grades", ".dxf")):
        path = tmp_path / f"{mode}_{kind}{suffix}"
        path.write_text("artifact", encoding="utf-8")
        artifacts[kind] = str(path)
    faces = {
        face: {
            "vazio_topo": {"valor_cm": 0.0, "fonte": "nulo", "evidencia": "sem fonte", "confianca": "alta"},
            "viga_passante_referencia": None,
            "aberturas_vigas_que_param": [],
            "aberturas_vigas_que_passam": [],
            "aberturas_vigas_que_chegam": [],
            "fontes_n1": {"lajes": [], "passa": [], "chega": [], "interior": []},
        }
        for face in "ABCD"
    }
    contract = {
        "modo_semantico": mode.upper(),
        "altura_pilar": {"nivel_saida": 280.0, "nivel_chegada": 0.0, "altura": 280.0},
        "faces": faces,
    }
    payload = {
        "nome": "P1", "comprimento": 60.0, "largura": 19.0, "altura": 280.0,
        "nivel_saida": 280.0, "nivel_chegada": 0.0,
        "_sa_meta": {}, "_sa_mode_contract": contract, "_sa_mode_variant": mode.upper(),
        **{f"grade_{index}": 0.0 for index in range(1, 4)},
        "distancia_1": 0.0, "distancia_2": 0.0,
        **{f"par_{index}_{index + 1}": 0.0 for index in range(1, 9)},
    }
    return {"contract": contract, "payload": payload, "artifacts": artifacts}


def _db(tmp_path: Path, *, broken_dimension: bool = False) -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute(
        """
        CREATE TABLE pillars (
          id TEXT, project_id TEXT, name TEXT, links_json TEXT, points_json TEXT,
          sides_data_json TEXT, extra_data_json TEXT, conf_map_json TEXT
        )
        """
    )
    links = {
        "name": _link("P1"),
        "pilar_segs": {"segments": [{"points": [[0, 0], [1, 0], [1, 1], [0, 1]]}]},
    }
    for face in "ABCD":
        links[f"p_s{face}_l1_n"] = _link("Vazio (X)")
    links["p_sA_v_passa_esq_n"] = _link("V101")
    links["p_sA_v_passa_esq_d"] = _link("V101" if broken_dimension else "19/55")
    extra = {
        "fields": {"Dimensão (b x h)": "19x60"},
        "pl_n3_variants": {"para": _variant(tmp_path, "para"), "passa": _variant(tmp_path, "passa")},
    }
    con.execute(
        "INSERT INTO pillars VALUES (?,?,?,?,?,?,?,?)",
        (
            "id", "project", "P1", json.dumps(links),
            json.dumps([[0, 0], [1, 0], [1, 1], [0, 1]]), "{}", json.dumps(extra), "{}",
        ),
    )
    return con


def test_pil_coverage_covers_all_families_without_promoting_authority(tmp_path: Path):
    con = _db(tmp_path)
    result = build_pil_coverage(con, project_id="project", item="P1")
    assert result["structural_complete"] is True
    assert result["ready_for_visual"] is True
    assert set(result["families"]) == {"identity_geometry", "faces", "para", "passa", "assembly"}
    assert result["authority"].startswith("diagnostic_only")
    assert "promoção QG7 do adaptador PIL para validation_ready" in result["human_checkpoints"]
    con.close()


def test_pil_coverage_detects_name_used_as_dimension_like_p35(tmp_path: Path):
    con = _db(tmp_path, broken_dimension=True)
    result = build_pil_coverage(con, project_id="project", item="P1")
    assert result["structural_complete"] is False
    finding = next(row for row in result["findings"] if row["code"] == "beam_dimension")
    assert finding["evidence"]["beam"] == "V101"
    assert finding["evidence"]["observed"] == "V101"
    assert result["ready_for_visual"] is False
    con.close()
