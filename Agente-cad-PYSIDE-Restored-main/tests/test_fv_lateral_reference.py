"""D-76: laterais como referencia NAO rigida do fundo (fundo_viga_lateral_ref).

Cenas sinteticas: V1 horizontal, faixa y 0..19, x 0..1000, paredes com linha real.
"""

from __future__ import annotations

import pytest

import src.core.lv_beam_scene as scene_mod
from src.core.beam_interpreters.fundo_viga_lateral_ref import apply_lateral_reference_all
from src.core.lv_beam_scene import LvScene


def _scene(name: str, t_lo: float, t_hi: float, start: float = 0.0, end: float = 1000.0) -> LvScene:
    scene = LvScene(name, True, t_lo, t_hi, start, end)
    scene.sections = [{"start": start, "end": end, "dim": "19/55", "width": 19.0, "depth": 55.0}]
    scene.face_coverage = {"A": [[start, end]], "B": [[start, end]]}
    return scene


def _panel(x0: float, x1: float, y0: float, y1: float, **extra) -> dict:
    link = {"type": "poly", "closed": True, "geometry_role": "area_fundo",
            "points": [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]}
    link.update(extra)
    return {"contour": [link]}


def _beam(name: str, panels: list[dict]) -> dict:
    links = {f"viga_fundo_seg_{i}_area_segs": p for i, p in enumerate(panels, start=1)}
    return {"name": name, "fv_is_h": True, "pos": [100.0, 30.0], "dim": "19/55",
            "fields": {"dimensao": "19/55"}, "links": links}


def _spans(beam: dict) -> list[tuple[float, float]]:
    out = []
    for key in sorted(beam["links"], key=lambda k: (len(k), k)):
        if key.startswith("viga_fundo_seg_") and key.endswith("_area_segs"):
            pts = beam["links"][key]["contour"][0]["points"]
            xs = [p[0] for p in pts]
            out.append((round(min(xs), 1), round(max(xs), 1)))
    return out


@pytest.fixture
def scenes(monkeypatch):
    table: dict[str, list[LvScene]] = {}
    monkeypatch.setattr(scene_mod, "build_scene_runs", lambda *a, **k: table)
    return table


def test_trecho_com_as_duas_paredes_sem_fundo_prolonga_o_painel(scenes):
    scenes["V1"] = [_scene("V1", 0.0, 19.0)]
    beam = _beam("V1", [_panel(0.0, 300.0, 0.0, 19.0)])
    report = apply_lateral_reference_all([beam], [], [], {})
    assert _spans(beam) == [(0.0, 1000.0)]
    assert report["V1"]["criados"] == [[300.0, 1000.0]]
    assert beam["geometry"]["classified"]["merged_bottom_groups_coords"] == [[0.0, 1000.0]]


def test_parede_sem_linha_real_nao_gera_fundo(scenes):
    sc = _scene("V1", 0.0, 19.0)
    sc.face_coverage = {"A": [[0.0, 300.0]], "B": [[0.0, 1000.0]]}
    scenes["V1"] = [sc]
    beam = _beam("V1", [_panel(0.0, 300.0, 0.0, 19.0)])
    apply_lateral_reference_all([beam], [], [], {})
    assert _spans(beam) == [(0.0, 300.0)]


def test_painel_na_faixa_de_outra_viga_volta_para_a_dona(scenes):
    scenes["V1"] = [_scene("V1", 0.0, 19.0)]
    scenes["V2"] = [_scene("V2", 500.0, 519.0)]
    v1 = _beam("V1", [_panel(0.0, 400.0, 0.0, 19.0)])
    v2 = _beam("V2", [_panel(0.0, 1000.0, 500.0, 519.0), _panel(420.0, 1000.0, 0.0, 19.0)])
    report = apply_lateral_reference_all([v1, v2], [], [], {})
    assert report["V2"]["removidos"] == [2]
    assert _spans(v2) == [(0.0, 1000.0)]
    assert _spans(v1) == [(0.0, 1000.0)]


def test_hachura_na_faixa_e_pilar_e_fica_sem_fundo(scenes):
    scenes["V1"] = [_scene("V1", 0.0, 19.0)]
    beam = _beam("V1", [_panel(0.0, 300.0, 0.0, 19.0)])
    hatch = [{"start": [x, 0.0], "end": [x + 19.0, 19.0]} for x in (500.0, 512.0, 524.0, 536.0)]
    apply_lateral_reference_all([beam], [], hatch, {})
    assert _spans(beam) == [(0.0, 500.0), (555.0, 1000.0)]


def test_x_de_dois_tracos_nao_e_hachura(scenes):
    scenes["V1"] = [_scene("V1", 0.0, 19.0)]
    beam = _beam("V1", [_panel(0.0, 300.0, 0.0, 19.0)])
    x_mark = [{"start": [500.0, 0.0], "end": [519.0, 19.0]}, {"start": [500.0, 19.0], "end": [519.0, 0.0]}]
    apply_lateral_reference_all([beam], [], x_mark, {})
    assert _spans(beam) == [(0.0, 1000.0)]


def test_fundo_validado_por_humano_nao_muda(scenes):
    scenes["V1"] = [_scene("V1", 0.0, 19.0)]
    beam = _beam("V1", [_panel(0.0, 300.0, 0.0, 19.0, validated=True)])
    report = apply_lateral_reference_all([beam], [], [], {})
    assert _spans(beam) == [(0.0, 300.0)]
    assert "V1" not in report


def test_pilar_fica_fora_e_trecho_encostado_prolonga_o_vizinho(scenes):
    sc = _scene("V1", 0.0, 19.0, 0.0, 1000.0)
    scenes["V1"] = [sc]
    beam = _beam("V1", [_panel(0.0, 600.0, 0.0, 19.0), _panel(640.0, 1000.0, 0.0, 19.0)])
    # 600..620 e' pilar (sem parede); 620..640 sem fundo encosta no painel seguinte
    sc.face_coverage = {"A": [[0.0, 600.0], [620.0, 1000.0]], "B": [[0.0, 600.0], [620.0, 1000.0]]}
    sc.pillars = {"A": [{"name": "P1", "start": 600.0, "end": 620.0, "classification": ""}],
                  "B": [{"name": "P1", "start": 600.0, "end": 620.0, "classification": ""}]}
    apply_lateral_reference_all([beam], [], [], {})
    assert _spans(beam) == [(0.0, 600.0), (620.0, 1000.0)]
