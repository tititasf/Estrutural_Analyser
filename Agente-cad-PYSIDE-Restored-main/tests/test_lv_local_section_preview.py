from copy import deepcopy

import ezdxf
import pytest

from scripts.arete.lv_n3_cut_draw import generate_local_sections


def section(height, a_height, b_height):
    return dict(beam='V1', beam_type='inverted', form_role='top_cap',
                width_cm=19., height_cm=height, base_level_m=850.,
                top_level_m=850.+height/100,
                slabs={'A': [], 'B': []},
                mounting={side: dict(panel_base_cm=height-face,
                                    panel_top_cm=height, h1_cm=face,
                                    lower_slab=False)
                          for side, face in [('A', a_height), ('B', b_height)]},
                rules=dict(face_allowance_cm=4., panel_cm=2., wood_cm=14., cap_cm=4.4))


def test_local_preview_keeps_distinct_sections_and_does_not_mix_side_maxima(tmp_path):
    low = section(71., 56., 49.)
    high = section(120., 108., 105.)
    sides = {side: {'structural_segments': [dict(section_contract=deepcopy(c))
                                          for c in [low, high, low]]}
             for side in ('A', 'B')}
    original = deepcopy(sides)
    target = tmp_path/'sections.dxf'
    generated = generate_local_sections(sides, target)
    assert sides == original
    assert [(c['height_cm'], c['mounting']['A']['h1_cm'],
             c['mounting']['B']['h1_cm']) for c in generated] == [
                 (71., 56., 49.), (120., 108., 105.)]
    doc = ezdxf.readfile(target)
    texts = [e.dxf.text for e in doc.modelspace().query('TEXT')]
    assert texts.count('VIGA INVERTIDA') == 2
    assert texts.count('LISO') == 2
    assert 'V1 (71x19)' in texts and 'V1 (120x19)' in texts
    assert 'pontalete' not in ' '.join(texts).casefold()
    assert doc.audit().has_errors is False


def test_missing_local_profile_cannot_fall_back_to_global_height(tmp_path):
    with pytest.raises(ValueError, match='Seção local ausente'):
        generate_local_sections({'A': {'structural_segments': [{}]}}, tmp_path/'bad.dxf')
    assert not (tmp_path/'bad.dxf').exists()


def test_local_panels_preserve_narrow_stations_and_heights(tmp_path):
    from scripts.arete.lv_n3_cut_draw import generate_local_panels
    panels = [dict(width=w, height1=h, height2=h, holes=[], grade_h1=0.,
                   grade_h2=0., panel_type='Sarrafeado')
              for w, h in [(13.963, 56.), (157.912, 56.), (25.163, 112.),
                           (19., 124.), (98.556, 105.), (12.406, 105.), (200., 108.)]]
    sides = {'A': dict(beam_name='V1', generation_ready=True,
                      vertical_pending=False, panels=panels)}
    original = deepcopy(sides)
    target = tmp_path/'panels.dxf'
    units = generate_local_panels(sides, target, 'A')
    assert sides == original
    assert sum(p['width'] for u in units for p in u['panels']) == pytest.approx(527.)
    assert [(u['panels'][0]['width'], u['height']) for u in units] == [
        (p['width'], p['height1']) for p in panels]
    doc = ezdxf.readfile(target)
    texts = [e.dxf.text for e in doc.modelspace().query('TEXT')]
    assert all(f'V1.A#{i}' in texts for i in range(1, 8))
    assert not doc.audit().has_errors
