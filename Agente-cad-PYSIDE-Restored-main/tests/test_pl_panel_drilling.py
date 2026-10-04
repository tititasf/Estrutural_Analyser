from copy import deepcopy
import json
from pathlib import Path

import ezdxf
import pytest

from scripts import drawing_mode_config as config
from scripts.pl_panel_drilling import APPID, add_drilling, defaults, rows, top_stations, validate
from scripts import gerar_pl_dxf_stog as generator


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG', str(tmp_path / 'profiles.json'))


def payload():
    return json.loads((Path(__file__).parents[1] / 'scripts/arete/relatorios/20261002_nova_design/P28.json').read_text())


def holes(doc):
    return [e for e in doc.modelspace() if e.has_xdata(APPID)]


def test_cadence_clips_actual_height_and_repeats_last_interval():
    group = defaults()['ab']
    assert rows(280, group) == [30, 80, 135, 190, 245]
    assert rows(700, group)[-2:] == [575, 630]
    assert rows(20, group) == []
    bad = defaults()
    bad['ab']['steps_cm'][0] = 0
    with pytest.raises(ValueError): validate(bad)


def test_generation_projects_real_bolts_and_isolates_modes(tmp_path):
    p = payload()
    before = generator.setup_doc()
    generator.generate_pilar_zone(before.modelspace(), p, 'abcd', visual_mode='NOVA')
    assert holes(before)  # Approved Nova drilling is the default.
    value = config.effective('NOVA', 'PL')
    value['drilling']['enabled'] = True
    config.save('NOVA', 'PL', value, 0, 'test')
    doc = generator.setup_doc()
    generator.generate_pilar_zone(doc.modelspace(), p, 'abcd', visual_mode='NOVA')
    emitted = holes(doc)
    assert emitted
    original = deepcopy(p)
    stations = top_stations(generator.__dict__, p, 'NOVA')
    for entity in emitted:
        data = entity.get_xdata(APPID)
        assert data[1].value in stations[data[0].value]
        assert data[2].value in rows(321, value['drilling']['ab'])
    assert p == original
    ini = generator.setup_doc()
    generator.generate_pilar_zone(ini.modelspace(), p, 'abcd', visual_mode='INI')
    assert not holes(ini)
    value['drilling']['enabled'] = False
    config.save('NOVA', 'PL', value, 1, 'test')
    disabled = generator.setup_doc()
    generator.generate_pilar_zone(disabled.modelspace(), p, 'abcd', visual_mode='NOVA')
    assert not holes(disabled)
    value['drilling']['enabled'] = True
    doc.saveas(tmp_path / 'drilled.dxf')
    assert not ezdxf.readfile(tmp_path / 'drilled.dxf').audit().errors
    value['drilling']['ab']['first_cm'] = 35
    config.save('NOVA', 'PL', value, 2, 'test')
    changed = generator.setup_doc()
    generator.generate_pilar_zone(changed.modelspace(), p, 'abcd', visual_mode='NOVA')
    assert min(e.get_xdata(APPID)[2].value for e in holes(changed)) == 35


def test_openings_and_panel_edges_are_not_drilled():
    doc = ezdxf.new()
    panel = doc.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 280), (0, 280)], close=True)
    face = {'x': 0, 'width': 100, 'bottom': 0, 'entities': [panel],
            'openings': [{'lado': 'meio', 'x_inn_l': 40, 'x_inn_r': 60, 'y_bot': 60, 'y_top': 150}]}
    options = defaults()
    assert add_drilling(doc.modelspace(), {'A': face}, {'A': [-1, 50, 101]}, options) == 3
    assert [e.get_xdata(APPID)[2].value for e in holes(doc)] == [30, 190, 245]
    assert all(e.dxf.color == 2 for e in holes(doc))
    crosses = [e for e in doc.modelspace().query('LINE') if e.dxf.layer == 'COTAS FURACAO']
    assert len(crosses) == 6
    dims = list(doc.modelspace().query('DIMENSION'))
    # The opening suppresses the 80/135 cm holes: the real chain is 30/160/55.
    vertical = [e for e in dims if e.dxf.angle == 90]
    horizontal = [e for e in dims if e.dxf.angle == 0]
    assert [round(e.get_measurement(), 6) for e in vertical] == [30, 160, 55]
    assert [round(e.get_measurement(), 6) for e in horizontal] == [50, 50]
    assert not doc.audit().errors


def test_special_holes_use_approved_top_rod_axes():
    from src.core.pillar_nova_design import special_payload
    from src.core.pillar_nova_special import Drawing
    p = json.loads((Path(__file__).parents[1] / 'scripts/arete/relatorios/20261004_nova_design_parity/P26.json').read_text())
    prepared = generator._prepare_pj_for_visual(deepcopy(p), 'NOVA')
    d = Drawing(special_payload(prepared)); d.generate()
    stations = top_stations(generator.__dict__, p, 'NOVA')
    assert all(stations[f] for f in 'ABEF')
    # A/B holes lie on the horizontal through-rods; E/F holes on vertical
    # rods. Compare global axes, independently of the projection function.
    horizontal = [r.coords[0][1] for r in d.rod_axes if abs(r.coords[0][1]-r.coords[-1][1]) < 1e-6]
    vertical = [r.coords[0][0] for r in d.rod_axes if abs(r.coords[0][0]-r.coords[-1][0]) < 1e-6]
    ey = max(y for x,y in d.ring); ex = max(x for x,y in d.ring)
    assert all(any(abs(ey-(x-11)-y)<1e-6 for y in horizontal) for x in stations['A'])
    assert all(any(abs(ex-x-y)<1e-6 for y in vertical) for x in stations['F'])


def test_drilling_chain_swaps_height_with_matching_total_only():
    doc = ezdxf.new()
    ms = doc.modelspace()
    panel = ms.add_lwpolyline([(0, 0), (100, 0), (100, 280), (0, 280)], close=True)
    total = ms.add_linear_dim(base=(0, -43), p1=(0, 0), p2=(100, 0)).dimension
    unrelated = ms.add_linear_dim(base=(0, -19), p1=(0, 0), p2=(7, 0)).dimension
    face = {'x': 0, 'width': 100, 'bottom': 0, 'entities': [panel]}
    add_drilling(ms, {'A': face}, {'A': [50]}, defaults('NOVA'))
    assert total.dxf.defpoint.y == -70
    assert unrelated.dxf.defpoint.y == -19
    chain = [e for e in ms.query('DIMENSION') if e.dxf.layer == 'COTAS FURACAO' and e.dxf.angle == 0]
    assert len(chain) == 2
    assert all(e.dxf.defpoint.y == -43 for e in chain)
    assert [e.get_measurement() for e in chain] == [50, 50]
    assert not doc.audit().errors
