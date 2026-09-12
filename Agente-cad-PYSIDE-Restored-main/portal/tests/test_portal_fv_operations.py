from __future__ import annotations

import json
from pathlib import Path

import pytest

from portal.app import fv_operations


def _state(path: Path) -> Path:
    payload = {
        "segmentos": {"fundo": [
            {"uid": "v1-s1", "beam_name": "V1", "segment_label": "1", "points": [[0, 0], [10, 0], [10, 2], [0, 2], [0, 0]]},
            {"uid": "v1-s2", "beam_name": "V1", "segment_label": "2", "points": [[11, 0], [20, 0], [20, 2], [11, 2], [11, 0]]},
            {"uid": "v2-s1", "beam_name": "V2", "segment_label": "1", "points": [[0, 5], [5, 5], [5, 7], [0, 7], [0, 5]]},
        ]}
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _proposal(folder: Path, layer: str = "c1", *, rows: int = 3) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    proposed = []
    for index in range(rows):
        x = index * 12
        proposed.append({"label": str(index + 1), "points": [[x, 0], [x + 10, 0], [x + 10, 2], [x, 2], [x, 0]]})
    path = folder / f"V1_qa_proposta_{layer}.json"
    path.write_text(json.dumps({"beam": "V1", "proposed": proposed}), encoding="utf-8")
    (folder / f"V1_qa_proposta_{layer}.svg").write_text(
        '<svg viewBox="0 0 100 20"><text>S1</text></svg>', encoding="utf-8",
    )
    return path


def test_adotar_camada_substitui_sa_e_so_apaga_revisoes_apos_finalizar(tmp_path):
    _state(tmp_path / "estado_13_PAV.json")
    html = tmp_path / "pack" / "fundos_viga" / "V1.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html></html>", encoding="utf-8")
    for layer in ("c1", "c2", "c3"):
        _proposal(html.parent / "propostas", layer, rows=3 if layer == "c1" else 1)

    result = fv_operations.adopt_agent_layer(tmp_path, "13_PAV", "V1", html, "c1")

    state = json.loads((tmp_path / "estado_13_PAV.json").read_text(encoding="utf-8"))
    v1 = [row for row in state["segmentos"]["fundo"] if row["beam_name"] == "V1"]
    assert [row["segment_label"] for row in v1] == ["1", "2", "3"]
    assert [row["uid"] for row in v1[:2]] == ["v1-s1", "v1-s2"]
    assert any(row["beam_name"] == "V2" for row in state["segmentos"]["fundo"])
    assert result["segments"] == 3
    assert Path(result["backup"]).is_file()
    assert list((html.parent / "propostas").glob("V1_qa_proposta_c*.*"))
    fv_operations.finalize_agent_adoption(
        html, "V1", "c1", result["adopted_segments"],
    )
    assert (html.parent / "adotados" / "V1_sa.json").is_file()
    assert not list((html.parent / "propostas").glob("V1_qa_proposta_c*.*"))


def test_backup_restauravel_reverte_mutacao(tmp_path):
    state_path = _state(tmp_path / "estado_13_PAV.json")
    original = state_path.read_text(encoding="utf-8")
    result = fv_operations.update_segment(
        tmp_path, "13_PAV", "V1", 1, [[0, 0], [15, 0], [15, 3], [0, 3]],
    )
    fv_operations.restore_state_backup(Path(result["backup"]), state_path)
    assert state_path.read_text(encoding="utf-8") == original


def test_excluir_camada_move_somente_selecionada_para_lixeira(tmp_path):
    html = tmp_path / "pack" / "fundos_viga" / "V1.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html></html>", encoding="utf-8")
    _proposal(html.parent / "propostas", "c1", rows=2)
    _proposal(html.parent / "propostas", "c2", rows=1)

    result = fv_operations.delete_agent_layer(html, "V1", "c1")

    assert result["layer"] == "c1"
    assert not list((html.parent / "propostas").glob("V1_qa_proposta_c1.*"))
    assert list((html.parent / "propostas").glob("V1_qa_proposta_c2.*"))
    recovered = Path(result["recoverable_at"])
    assert (recovered / "V1_qa_proposta_c1.svg").is_file()
    assert (recovered / "V1_qa_proposta_c1.json").is_file()


def test_adotar_camada_sem_geometria_falha_sem_alterar_estado(tmp_path):
    state_path = _state(tmp_path / "estado_13_PAV.json")
    original = state_path.read_text(encoding="utf-8")
    html = tmp_path / "pack" / "fundos_viga" / "V1.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html></html>", encoding="utf-8")
    proposals = html.parent / "propostas"
    proposals.mkdir()
    (proposals / "V1_qa_proposta_c1.json").write_text('{"beam":"V1","proposed":[]}', encoding="utf-8")
    (proposals / "V1_qa_proposta_c1.svg").write_text('<svg></svg>', encoding="utf-8")

    with pytest.raises(ValueError, match="sem segmentos estruturados"):
        fv_operations.adopt_agent_layer(tmp_path, "13_PAV", "V1", html, "c1")
    assert state_path.read_text(encoding="utf-8") == original


def test_editar_e_excluir_segmento_sao_persistentes_e_guardam_backup(tmp_path):
    _state(tmp_path / "estado_13_PAV.json")
    edited = fv_operations.update_segment(
        tmp_path, "13_PAV", "V1", 1, [[0, 0], [15, 0], [15, 3], [0, 3]],
    )
    assert edited["length"] == 15
    assert edited["width"] == 3
    assert Path(edited["backup"]).is_file()

    deleted = fv_operations.delete_segment(tmp_path, "13_PAV", "V1", 2)
    assert deleted["removed_item_id"] == "v1-s2"
    assert deleted["segments"] == 1
    with pytest.raises(ValueError, match="ultimo segmento"):
        fv_operations.delete_segment(tmp_path, "13_PAV", "V1", 1)


def test_viewer_editado_usa_estrutural_completo_e_segmentos_em_px(tmp_path):
    class Transform:
        svg = b'<svg viewBox="0 0 100 50"><path id="estrutural" d="M0 0H100"/></svg>'

        @staticmethod
        def dxf_para_px(x, y):
            return x * 2, 50 - y * 2

    html = tmp_path / "fundos_viga" / "V1.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html></html>", encoding="utf-8")
    target = fv_operations.write_sa_visual(
        html, "V1", Transform(), [{"points": [[1, 1], [4, 1], [4, 2], [1, 2], [1, 1]]}],
    )
    rendered = target.read_text(encoding="utf-8")
    assert 'id="estrutural"' in rendered
    assert 'data-fv-seg="1"' in rendered
    assert ">S1</text>" in rendered


def test_override_n3_notas_e_apontamentos_ficam_fora_do_estado_sa(tmp_path):
    state_path = _state(tmp_path / "estado_13_PAV.json")
    original = state_path.read_text(encoding="utf-8")
    fv_operations.update_n3_override(tmp_path, "13_PAV", "V1", 1, {
        "panels": [{"length_cm": 8, "width_cm": 2}, {"length_cm": 2, "width_cm": 2}],
        "chamfers": [{"position": "te", "size_cm": 1.5}],
        "openings": [{"position_cm": 3, "width_cm": 1, "height_cm": .5}],
    })
    fv_operations.save_notes(tmp_path, "13_PAV", "V1", {"sa": "rever apoio"})
    point = fv_operations.add_annotation(tmp_path, "13_PAV", "V1", {
        "layer": "sa", "segment": "1", "x": 3, "y": 4,
        "element": "LINE.Paineis", "text": "alinhar aqui",
    })
    override = fv_operations.load_override(tmp_path, "13_PAV", "V1")
    assert override["segments"]["1"]["panels"][0]["length_cm"] == 8
    assert override["notes"]["sa"] == "rever apoio"
    assert override["annotations"][0]["id"] == point["id"]
    assert state_path.read_text(encoding="utf-8") == original


def test_override_e_aplicado_ao_contrato_n3(tmp_path):
    custom = {
        "segments": {"1": {
            "panels": [{"length_cm": 8, "width_cm": 2}, {"length_cm": 2, "width_cm": 2}],
            "chamfers": [{"position": "te", "size_cm": 1.5}],
            "openings": [{"position_cm": 9, "width_cm": 1, "height_cm": .5}],
        }}
    }
    contract = {"segments_rich": [{"width": 10}]}
    result = fv_operations.apply_n3_overrides(contract, custom)
    assert [row["width"] for row in result["segments_rich"][0]["panels"]] == [8, 2]
    assert result["segments_rich"][0]["panels"][0]["chanfros"]["te"] == 1.5
    assert result["segments_rich"][0]["panels"][1]["aberturas"] == [[1.0, .5, 1]]


def test_rename_beam_altera_pai_segmentos_e_sidecar(tmp_path):
    _state(tmp_path / "estado_13_PAV.json")
    fv_operations.save_notes(tmp_path, "13_PAV", "V1", {"sa": "nota"})
    result = fv_operations.rename_beam(tmp_path, "13_PAV", "V1", "VF10")
    state = json.loads((tmp_path / "estado_13_PAV.json").read_text(encoding="utf-8"))
    assert result["segments"] == 2
    assert [row["beam_name"] for row in state["segmentos"]["fundo"][:2]] == ["VF10", "VF10"]
    assert fv_operations.load_override(tmp_path, "13_PAV", "VF10")["notes"]["sa"] == "nota"
