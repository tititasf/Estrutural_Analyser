"""D-76: laterais como referencia NAO rigida do fundo (fundo_viga_lateral_ref).

Cenas sinteticas: V1 horizontal, faixa y 0..19, x 0..1000, paredes com linha real.
"""

from __future__ import annotations

import pytest

import src.core.lv_beam_scene as scene_mod
from src.core.beam_interpreters.fundo_viga_lateral_ref import (
    apply_lateral_reference_all,
    needs_area_repair,
    resolve_automatic_overlaps_all,
    complete_measured_junctions_all,
)
from src.core.lv_beam_scene import LvScene


def _scene(name: str, t_lo: float, t_hi: float, start: float = 0.0, end: float = 1000.0) -> LvScene:
    scene = LvScene(name, True, t_lo, t_hi, start, end)
    scene.sections = [{"start": start, "end": end, "dim": "19/55", "width": 19.0, "depth": 55.0}]
    scene.face_coverage = {"A": [[start, end]], "B": [[start, end]]}
    return scene


def test_fundo_recupera_paredes_quando_cota_vizinha_indica_largura_errada():
    # VF404: rotulo fora da faixa de 14 cm; a secao proxima de 19 cm e' de outra viga.
    label = {"text": "VF404", "pos": [2606.31, 3110.71], "rotation": 90}
    edges = scene_mod._EdgeIndex([
        (2611.09, 3103.025, 2611.09, 3188.025),
        (2625.09, 3103.025, 2625.09, 3174.025),
    ])
    section = {"text": "19/55", "pos": [2606.31, 3120.0], "rotation": 90,
               "section": (19.0, 55.0)}
    args = ({"name": "VF404"}, [label], edges, [section], [label], [])
    assert scene_mod.build_band_scene(*args) is None
    recovered = scene_mod.build_band_scene(*args, allow_width_hint_fallback=True)
    assert recovered is not None
    assert recovered.width == pytest.approx(14.0)


def test_fundo_sem_cota_nao_pareia_parede_distante_do_rotulo():
    label = {"text": "VF404", "pos": [2606.31, 3110.71], "rotation": 90}
    edges = scene_mod._EdgeIndex([
        (2573.09, 2700.0, 2573.09, 3000.0),
        (2611.09, 3103.025, 2611.09, 3188.025),
        (2625.09, 3103.025, 2625.09, 3174.025),
    ])
    # O par de 38 cm envolve o texto, mas nao existe ao longo dele.
    assert scene_mod._find_band(label, False, edges, None) == (2573.1, 2611.1)
    recovered = scene_mod.build_band_scene(
        {"name": "VF404"}, [label], edges, [], [label], [],
        allow_width_hint_fallback=True,
    )
    assert recovered is not None
    assert recovered.width == pytest.approx(14.0)


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


def test_painel_isolado_de_um_centimetro_nao_e_ignorado(scenes):
    sc = _scene("V1", 0.0, 19.0)
    sc.face_coverage = {"A": [[0.0, 300.0], [500.0, 501.0]],
                        "B": [[0.0, 300.0], [500.0, 501.0]]}
    scenes["V1"] = [sc]
    beam = _beam("V1", [_panel(0.0, 300.0, 0.0, 19.0)])
    report = apply_lateral_reference_all([beam], [], [], {})
    assert _spans(beam) == [(0.0, 300.0), (500.0, 501.0)]
    assert report["V1"]["criados"] == [[500.0, 501.0]]


def test_nasce_sobreposto_nao_libera_secao_de_outro_pilar_incerto(scenes):
    sc = _scene("V1", 0.0, 19.0)
    sc.pillars = {side: [{"name": "PINC", "start": 400., "end": 419.,
                         "classification": "INDETERMINADO", "miolo": True}]
                  for side in ("A", "B")}
    sc.incidents = {side: [{"name": "V2", "start": 400., "end": 419.,
                           "depth": 120., "crossing": True}]
                    for side in ("A", "B")}
    # The incident was recorded before its ends were trimmed to the support.
    scenes["V1"] = [sc]
    scenes["V2"] = [LvScene("V2", False, 400., 419., 98., 400.)]
    beam = _beam("V1", [_panel(0., 400., 0., 19.), _panel(419., 1000., 0., 19.)])
    nasce = {"PN": {"classification": "NASCE", "bbox": [390., 0., 440., 19.]}}
    apply_lateral_reference_all([beam], [], [], nasce)
    assert _spans(beam) == [(0., 400.), (419., 1000.)]


def test_pilar_solido_nao_e_disprovado_por_caixa_nasce_sobreposta(scenes):
    sc = _scene("V1", 0.0, 19.0)
    sc.pillars = {side: [{"name": "PS", "start": 400., "end": 419.,
                         "classification": "SEGUE", "miolo": True}]
                  for side in ("A", "B")}
    scenes["V1"] = [sc]
    beam = _beam("V1", [_panel(0., 400., 0., 19.), _panel(419., 1000., 0., 19.)])
    apply_lateral_reference_all([beam], [], [], {"PN": {"classification": "NASCE", "bbox": [390., 0., 440., 19.]}})
    assert _spans(beam) == [(0., 400.), (419., 1000.)]


def test_painel_reancorado_inteiramente_contido_nao_duplica_fundo():
    beam = _beam("V1", [_panel(10., 20., 0., 19.), _panel(0., 100., 0., 19.)])
    report = resolve_automatic_overlaps_all([beam])
    assert _spans(beam) == [(0., 100.)]
    assert report["V1"]["duplicados_contidos"] == [1]


@pytest.mark.parametrize('solid', [False, True])
def test_quadrado_do_encontro_tem_um_dono_e_nao_atravessa_pilar(scenes, solid):
    from shapely.geometry import Polygon
    h = _scene('VH', 0., 19., 0., 200.)
    v = LvScene('VV', False, 90., 109., -100., 100.)
    v.sections=[{'start':-100.,'end':100.,'dim':'19/55','width':19.,'depth':55.}]
    scenes['VH']=[h]
    scenes['VV']=[v]
    bh=_beam('VH',[_panel(0.,90.,0.,19.),_panel(109.,200.,0.,19.)])
    bv=_beam('VV',[_panel(90.,109.,-100.,0.),_panel(90.,109.,19.,100.)])
    bv['fv_is_h']=False
    pillars={'PS':{'classification':'SEGUE','points':[[90.,0.],[109.,0.],[109.,19.],[90.,19.],[90.,0.]]}} if solid else {}
    complete_measured_junctions_all([bh,bv],[],[],pillars)
    resolve_automatic_overlaps_all([bh,bv])
    area=sum(Polygon(p['contour'][0]['points']).intersection(Polygon([(90.,0.),(109.,0.),(109.,19.),(90.,19.)])).area
             for b in (bh,bv) for key,p in b['links'].items() if key.endswith('_area_segs'))
    assert area == (0. if solid else 361.)


def test_junction_repairs_self_intersection_created_by_snap(scenes, monkeypatch):
    from shapely.geometry import Polygon
    import src.core.beam_interpreters.fundo_viga_lateral_ref as ref

    h = _scene('VH', 0., 19., 0., 200.)
    v = LvScene('VV', False, 90., 109., -100., 100.)
    v.sections = [{'start': -100., 'end': 100., 'dim': '19/55', 'width': 19., 'depth': 55.}]
    scenes.update(VH=[h], VV=[v])
    bh = _beam('VH', [_panel(0., 90., 0., 19.), _panel(109., 200., 0., 19.)])
    bv = _beam('VV', [_panel(90., 109., -100., 0.), _panel(90., 109., 19., 100.)])
    bv['fv_is_h'] = False
    invalid = Polygon([(90., 0.), (109., 19.), (90., 19.), (109., 0.), (90., 0.)])
    assert not invalid.is_valid
    monkeypatch.setattr(ref, 'snap', lambda *args: invalid)
    complete_measured_junctions_all([bh, bv], [], [], {})
    assert all(poly.is_valid for beam in (bh, bv) for _, _, poly in ref._panels(beam))


def test_painel_lateral_comum_nao_e_reconstruido_depois_de_medido(scenes):
    scenes["V1"] = [_scene("V1", 0.0, 19.0)]
    beam = _beam("V1", [_panel(0.0, 300.0, 0.0, 19.0)])

    apply_lateral_reference_all([beam], [], [], {})

    assert _spans(beam) == [(0.0, 1000.0)]
    assert needs_area_repair(beam) is False


def test_caixa_bruta_de_pilar_nao_recorta_faces_que_a_cena_deixou_passar(
    scenes, monkeypatch,
):
    scenes["V1"] = [_scene("V1", 0.0, 19.0)]
    beam = _beam("V1", [_panel(0.0, 300.0, 0.0, 19.0)])

    # Synthetic scene: no solid support exclusion was measured. A raw box
    # alone must not run a second, conflicting segmentation pass.
    from shapely.geometry import box
    monkeypatch.setattr(
        scene_mod,
        "_pillar_polygons",
        lambda _report: [("PBOX", {}, box(500.0, 0.0, 550.0, 19.0))],
    )

    apply_lateral_reference_all([beam], [], [], {"PBOX": {}})

    assert _spans(beam) == [(0.0, 1000.0)]


def _orthogonal_tail_case(scenes, tail_length: float, host_end: float = 80.0):
    host_scene = _scene("VHOST", 0.0, 19.0, 0.0, 100.0)
    host_scene.face_coverage = {"A": [[0.0, host_end]], "B": [[0.0, 100.0]]}
    host_scene.incidents["A"] = [{
        "name": "VEND", "start": 80.0, "end": 100.0,
        "crossing": False, "width": 20.0,
    }]
    incident_scene = LvScene("VEND", False, 80.0, 100.0, -tail_length, 0.0)
    incident_scene.sections = [{
        "start": -tail_length, "end": 0.0, "dim": "20/55",
        "width": 20.0, "depth": 55.0,
    }]
    incident_scene.face_coverage = {
        "A": [[-tail_length, 0.0]], "B": [[-tail_length, 0.0]],
    }
    scenes["VHOST"] = [host_scene]
    scenes["VEND"] = [incident_scene]
    host = _beam("VHOST", [_panel(0.0, host_end, 0.0, 19.0)])
    incident = {
        "name": "VEND", "fv_is_h": False, "is_h": False, "dim": "20/55",
        "fields": {"dimensao": "20/55"},
        "links": {
            "viga_fundo_seg_1_area_segs": _panel(
                80.0, 100.0, -tail_length, 0.0,
            ),
        },
    }
    return host, incident


def test_l_ortogonal_conserva_dois_paineis_d82(scenes):
    host, incident = _orthogonal_tail_case(scenes, 10.0)
    report = apply_lateral_reference_all([host, incident], [], [], {})

    link = host["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert not link.get("special_geometry")
    assert min(p[1] for p in link["points"]) == 0.0
    assert any(key.endswith("_area_segs") for key in incident["links"])
    assert not report.get("VHOST", {}).get("contornos_l")


def test_l_angulado_continua_um_painel_sem_divisao_no_nascimento(scenes):
    from shapely.geometry import Polygon
    angled = _scene("VANGLE", 0.0, 10.0, 0.0, 140.0)
    angled.angle = 45.0
    corner = LvScene("VANGLE", False, 100.0, 110.0, 90.0, 130.0)
    corner.provenance["band_source"] = "trecho_de_canto_em_L"
    scenes["VANGLE"] = [angled, corner]
    body = [[0.0, 0.0], [100.0, 100.0], [110.0, 90.0], [10.0, -10.0], [0.0, 0.0]]
    beam = _beam("VANGLE", [{"contour": [{
        "type": "poly", "closed": True, "points": body,
        "geometry_role": "area_fundo", "fv_lateral_reference": True,
    }]}])
    complete_measured_junctions_all([beam], [], [], {})
    panels = [value for key, value in beam["links"].items() if key.endswith("_area_segs")]
    assert len(panels) == 1
    link = panels[0]["contour"][0]
    assert link["special_geometry"] == "diagonal_corner_l"
    polygon = Polygon(link["points"])
    assert polygon.is_valid
    assert polygon.covers(Polygon(body))
    assert polygon.bounds[3] == 130.0


def test_l_ortogonal_conserva_painel_isolado_de_um_centimetro(scenes):
    host, incident = _orthogonal_tail_case(scenes, 1.0)
    apply_lateral_reference_all([host, incident], [], [], {})

    link = host["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert not link.get("special_geometry")
    tail = incident["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert min(p[1] for p in tail["points"]) == -1.0
    assert max(p[1] for p in tail["points"]) == 0.0


def test_l_fecha_folga_numerica_de_centesimos_no_encontro(scenes):
    host, incident = _orthogonal_tail_case(scenes, 10.0, host_end=79.98)
    apply_lateral_reference_all([host, incident], [], [], {})

    link = host["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert not link.get("special_geometry")
    assert any(key.endswith("_area_segs") for key in incident["links"])


def test_l_reconhece_corpo_que_ja_inclui_o_quadrado_do_encontro(scenes):
    host, incident = _orthogonal_tail_case(scenes, 10.0)
    host["links"]["viga_fundo_seg_1_area_segs"] = _panel(0.0, 100.0, 0.0, 19.0)
    apply_lateral_reference_all([host, incident], [], [], {})

    link = host["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert not link.get("special_geometry")
    assert any(key.endswith("_area_segs") for key in incident["links"])


def test_cauda_sem_painel_principal_adjacente_permanece_isolada(scenes):
    host, incident = _orthogonal_tail_case(scenes, 10.0, host_end=70.0)
    report = apply_lateral_reference_all([host, incident], [], [], {})

    host_link = host["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert not host_link.get("special_geometry")
    assert any(key.endswith("_area_segs") for key in incident["links"])
    assert not report.get("VHOST", {}).get("contornos_l")


def test_perna_ortogonal_maior_que_o_corpo_nao_inverte_o_dono_do_l(scenes):
    host, incident = _orthogonal_tail_case(scenes, 100.0)
    report = apply_lateral_reference_all([host, incident], [], [], {})

    host_link = host["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert not host_link.get("special_geometry")
    assert any(key.endswith("_area_segs") for key in incident["links"])
    assert not report.get("VHOST", {}).get("contornos_l")


def test_segundo_corpo_de_porte_parecido_permanece_painel_isolado(scenes):
    # Engenharia reversa do 13_PAV: V304 x V329 mede 199 x 141 cm e o N4
    # manteve dois paineis. Nao e' uma pequena aba como os 10/30 x 418 da V303.
    host, incident = _orthogonal_tail_case(scenes, 60.0)
    report = apply_lateral_reference_all([host, incident], [], [], {})

    host_link = host["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert not host_link.get("special_geometry")
    assert any(key.endswith("_area_segs") for key in incident["links"])
    assert not report.get("VHOST", {}).get("contornos_l")


def test_cauda_no_inicio_nao_e_anexada_ao_painel_seguinte(scenes):
    host_scene = _scene("VHOST", 0.0, 19.0, 0.0, 160.0)
    host_scene.face_coverage = {"A": [[20.0, 160.0]], "B": [[0.0, 160.0]]}
    host_scene.incidents["A"] = [{
        "name": "VEND", "start": 0.0, "end": 20.0,
        "crossing": False, "width": 20.0,
    }]
    incident_scene = LvScene("VEND", False, 0.0, 20.0, -10.0, 0.0)
    incident_scene.sections = [{
        "start": -10.0, "end": 0.0, "dim": "20/55",
        "width": 20.0, "depth": 55.0,
    }]
    incident_scene.face_coverage = {"A": [[-10.0, 0.0]], "B": [[-10.0, 0.0]]}
    scenes["VHOST"] = [host_scene]
    scenes["VEND"] = [incident_scene]
    host = _beam("VHOST", [_panel(0.0, 160.0, 0.0, 19.0)])
    incident = {
        "name": "VEND", "fv_is_h": False, "is_h": False, "dim": "20/55",
        "fields": {"dimensao": "20/55"},
        "links": {"viga_fundo_seg_1_area_segs": _panel(0.0, 20.0, -10.0, 0.0)},
    }

    report = apply_lateral_reference_all([host, incident], [], [], {})

    assert not host["links"]["viga_fundo_seg_1_area_segs"]["contour"][0].get("special_geometry")
    assert any(key.endswith("_area_segs") for key in incident["links"])
    assert not report.get("VHOST", {}).get("contornos_l")


def test_cruzamento_ortogonal_fica_com_um_unico_dono():
    # A viga longa/principal vence o empate de 19/55; a viga que chega comeca
    # na face oposta, sem o quadrado 19x19 contado duas vezes.
    main = _beam("VMAIN", [_panel(0.0, 1000.0, 0.0, 19.0)])
    arriving = {
        "name": "VEND", "fv_is_h": False, "is_h": False, "dim": "19/55",
        "fields": {"dimensao": "19/55"},
        "links": {"viga_fundo_seg_1_area_segs": _panel(981.0, 1000.0, 0.0, 300.0)},
    }
    report = resolve_automatic_overlaps_all([main, arriving])
    main_poly = main["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"]
    arriving_link = arriving["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert min(point[1] for point in arriving_link["points"]) == 19.0
    assert max(point[1] for point in arriving_link["points"]) == 300.0
    assert main_poly == _panel(0.0, 1000.0, 0.0, 19.0)["contour"][0]["points"]
    assert report["VEND"]["conflitos_recortados"][0]["area_cm2"] == 361.0


def test_no_diagonal_recorta_triangulo_sem_retangularizar():
    main = _beam("V306", [_panel(0.0, 1000.0, 0.0, 19.0)])
    diagonal_link = {
        "type": "poly", "closed": True,
        "geometry_source": "fundo_viga_lateral_reference_special_diagonal",
        "points": [[-20.0, 19.0], [20.0, 0.0], [30.0, 10.0],
                   [-10.0, 29.0], [-20.0, 19.0]],
        "ficha": {"largura_total_fundo": "14"},
    }
    diagonal = {
        "name": "VF202", "fv_is_h": True, "dim": "14/55",
        "fields": {"dimensao": "14/55"},
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [diagonal_link]}},
    }
    report = resolve_automatic_overlaps_all([main, diagonal])
    clipped = diagonal["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]
    assert clipped["fv_overlap_trimmed"] is True
    assert len({tuple(point) for point in clipped["points"]}) >= 4
    assert clipped["geometry_source"].endswith("special_diagonal")
    assert report["VF202"]["conflitos_recortados"][0]["area_cm2"] > 0


def test_fundo_validado_vence_conflito_sem_ser_alterado():
    validated_panel = _panel(0.0, 100.0, 0.0, 19.0, validated=True)
    validated = _beam("VH", [validated_panel])
    automatic = _beam("VA", [_panel(80.0, 180.0, 0.0, 19.0)])
    original = list(validated_panel["contour"][0]["points"])
    resolve_automatic_overlaps_all([automatic, validated])
    assert validated_panel["contour"][0]["points"] == original
    auto_points = automatic["links"]["viga_fundo_seg_1_area_segs"]["contour"][0]["points"]
    assert min(point[0] for point in auto_points) == 100.0


def test_recorte_preserva_slot_legado_sem_poligono_da_mesma_viga():
    main = _beam("VMAIN", [_panel(0.0, 200.0, 0.0, 19.0)])
    arriving = _beam("VEND", [
        _panel(180.0, 280.0, 0.0, 19.0),
        {"contour": [{"type": "legacy", "points": []}]},
    ])

    resolve_automatic_overlaps_all([main, arriving])

    slots = [
        value["contour"][0]
        for key, value in arriving["links"].items()
        if key.startswith("viga_fundo_seg_") and key.endswith("_area_segs")
    ]
    assert any(slot.get("type") == "legacy" for slot in slots)
    clipped = next(slot for slot in slots if slot.get("fv_overlap_trimmed"))
    assert min(point[0] for point in clipped["points"]) == 200.0


def test_paineis_parcialmente_sobrepostos_da_mesma_viga_preservam_uniao():
    from shapely.geometry import Polygon
    beam = _beam("VLOCAL", [
        _panel(0.0, 100.0, 0.0, 19.0),
        _panel(90.0, 200.0, 0.0, 19.0),
    ])
    report = resolve_automatic_overlaps_all([beam])
    polygons = [Polygon(v["contour"][0]["points"]) for k, v in beam["links"].items()
                if k.endswith("_area_segs")]
    assert len(polygons) == 1
    assert polygons[0].area == 200.0 * 19.0
    assert report["VLOCAL"]["conflitos_recortados"][0]["com"] == ["VLOCAL"]


def test_continuidade_vence_soma_de_vaos_sem_prioridade_por_orientacao():
    for swap in (False, True):
        fragmented = _beam("VLONG", [_panel(0, 200, 0, 19), _panel(250, 800, 0, 19)])
        continuous = _beam("VCONT", [_panel(300, 319, -100, 300)])
        continuous["fv_is_h"] = False
        if swap:
            for beam in (fragmented, continuous):
                beam["fv_is_h"] = not beam["fv_is_h"]
                for value in beam["links"].values():
                    for link in value.get("contour", []):
                        link["points"] = [[y, x] for x, y in link["points"]]
        resolve_automatic_overlaps_all([fragmented, continuous])
        from shapely.geometry import Polygon
        panels = [Polygon(v["contour"][0]["points"]) for k,v in continuous["links"].items() if k.endswith("_area_segs")]
        assert len(panels) == 1
        assert panels[0].area == 19 * 400


def test_costura_coplanar_preserva_metadados_e_abertura_real_de_um_cm():
    beam = _beam("VA", [_panel(0, 1, 0, 19), _panel(1, 100, 0, 19), _panel(101, 120, 0, 19)])
    beam["fields"]["viga_fundo_seg_2_dim"] = "19/55"
    beam["fields"]["viga_fundo_seg_2_local_ini"] = "P1"
    resolve_automatic_overlaps_all([beam])
    assert _spans(beam) == [(0.0, 100.0), (101.0, 120.0)]
    assert beam["fields"]["viga_fundo_seg_1_local_ini"] == "P1"


def test_costura_nao_une_mudanca_de_secao():
    beam = _beam("VA", [_panel(0, 1, 0, 19), _panel(1, 100, 0, 19)])
    beam["fields"].update(viga_fundo_seg_1_dim="19/55", viga_fundo_seg_2_dim="19/66")
    resolve_automatic_overlaps_all([beam])
    assert len(_spans(beam)) == 2


def test_residuo_de_recorte_nao_vira_painel_mas_um_cm_real_permanece():
    main = _beam("VM", [_panel(0, 1000, 0, 19)])
    arriving = _beam("VA", [_panel(900, 1000.0025, 0, 19)])
    tiny = _beam("VT", [_panel(1100, 1101, 0, 19)])
    report = resolve_automatic_overlaps_all([main, arriving, tiny])
    assert _spans(arriving) == []
    assert _spans(tiny) == [(1100.0, 1101.0)]
    assert report["VA"]["residuos_numericos_cm2"]
