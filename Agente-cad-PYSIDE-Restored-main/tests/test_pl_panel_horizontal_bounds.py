"""Abertura de viga/laje maior que a face nunca amplia o painel N3."""
import copy
import json
import sys
from pathlib import Path

import ezdxf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from scripts import pl_abcd_visual_nova as visual
from scripts import gerar_pl_dxf_stog as generator
from scripts.pl_panel_drilling import Recorder


@pytest.mark.parametrize('side,offset,size,expected', [
    ('direito', 0, 34, (0, 24)), ('esquerdo', 0, 34, (0, 24)),
    ('meio', -10, 20, (0, 10)), ('meio', 20, 30, (20, 4)),
    ('meio', 30, 10, (24, 0)), ('meio', -30, 10, (0, 0)),
    ('meio', 5, 10, (5, 10)),
])
def test_horizontal_intersection_and_idempotence(side, offset, size, expected):
    raw = dict(lado=side, x_offset=offset, largura=size, altura=50)
    clipped = visual._clip_opening_to_panel(raw, 24)
    assert clipped['largura'] == clipped['larg'] == expected[1]
    if side == 'meio':
        assert clipped['x_offset'] == expected[0]
    assert visual._clip_opening_to_panel(clipped, 24) == clipped
    assert raw['largura'] == size


@pytest.mark.parametrize('side', ['direito', 'esquerdo', 'meio'])
def test_voids_and_slab_extensions_cannot_escape(side):
    rects = visual.void_rects_for_face(
        x_left=10, x_right=34,
        openings=[dict(lado=side, larg=90, y_bot=150, y_top=280,
                       x_inn_l=-30, x_inn_r=90)],
        rebaixo_cm=7, vazio_laje_cm=14, y_face_top=280,
        y_panel_content_top=259)
    assert rects
    assert all(10 <= x <= x+w <= 34 for x, y, w, h in rects)


def test_full_width_and_overlapping_openings_have_no_outside_marco():
    msp = ezdxf.new().modelspace()
    opening = dict(lado='direito', larg=24, y_bot=100, y_top=200)
    assert visual.draw_opening_sarrafos(msp, x_left=10, x_right=34,
                                       openings=[opening]) == 0
    assert visual.draw_dual_marco_sarrs(
        msp, x_left=10, x_right=34,
        openings=[opening, dict(opening, lado='esquerdo')],
        rebaixo_cm=0, vazio_laje_cm=0, y_face_top=200) == 0
    assert len(msp) == 0


@pytest.mark.parametrize('mode', ['INI', 'NOVA', 'MOLDE_1', 'MOLDE_2', 'MOLDE_3'])
def test_real_p28_prepared_geometry_stays_inside_face(mode):
    source = Path(__file__).resolve().parents[1] / 'scripts/arete/relatorios/20261002_nova_design/P28.json'
    raw = json.loads(source.read_text(encoding='utf8'))
    original = copy.deepcopy(raw)
    prepared = generator._prepare_pj_for_visual(copy.deepcopy(raw), mode)
    assert prepared['abertura_C_1']['largura'] == 24
    assert prepared['abertura_C_2']['largura'] == 24
    record = Recorder(generator.setup_doc().modelspace(), panels=True)
    generator.generate_pilar_zone(record, prepared, 'abcd', visual_mode=mode)
    face = record.faces['C']
    for entity in face['entities']:
        points = [entity.dxf.start, entity.dxf.end] if entity.dxftype() == 'LINE' else entity.get_points()
        assert all(face['x']-1e-6 <= p[0] <= face['x']+face['width']+1e-6 for p in points)
    assert raw == original
    assert not record.doc.audit().errors
