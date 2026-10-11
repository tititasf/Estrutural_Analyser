from types import SimpleNamespace

from src.core.cut_beam_owner import fundo_polygons, owner_by_fundo


def _box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def _beam(name, *boxes):
    return {'name': name, 'links': {
        f'viga_fundo_seg_{i}_area_segs': {'contour': [{'points': b}]} for i, b in enumerate(boxes, 1)}}


# T do corte L311 sobre o V302 (13_PAV): o rótulo mais próximo era o do V314.
T_V302 = [[2203.8, 2685], [2258.8, 2685], [2258.8, 2671], [2236, 2671], [2236, 2641],
          [2226, 2641], [2226, 2671], [2203.8, 2671], [2203.8, 2685]]
BEAMS = [_beam('V302', _box(1800, 2641, 2400, 2661), _box(2400, 2641, 3000, 2661)),
         _beam('V314', _box(2226, 2100, 2246, 2641))]


def test_owner_is_beam_whose_fundo_covers_the_cut_symbol():
    assert owner_by_fundo(T_V302, fundo_polygons(BEAMS)) == ('V302', [])


def test_cut_outside_every_fundo_has_no_owner():
    far = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert owner_by_fundo(far, fundo_polygons(BEAMS)) == (None, [])


def test_two_beams_covering_the_cut_equally_are_a_tie():
    beams = [_beam('V306', _box(0, 0, 100, 20)), _beam('VF202', _box(0, 0, 100, 20))]
    owner, tied = owner_by_fundo(_box(40, 5, 60, 15), fundo_polygons(beams))
    assert owner is None and sorted(tied) == ['V306', 'VF202']


def _dialog(beam_texts, beams):
    from src.ui.widgets.pre_validation_dialog import PreValidationDialog
    fake = SimpleNamespace(_beam_texts=beam_texts, _beams=beams)
    fake._associate_beam_name = lambda *a: PreValidationDialog._associate_beam_name(fake, *a)
    return fake


def test_prevalidation_prefers_fundo_over_nearest_label():
    fake = _dialog([{'text': 'V314', 'pos': [2240, 2700]}, {'text': 'V302', 'pos': [2600, 2670]}], BEAMS)
    name, conf, cands = fake._associate_beam_name(2231, 2663, {}, T_V302)
    assert (name, conf) == ('V302', 100)
    assert [c['text'] for c in cands] == ['V302', 'V314']


def test_prevalidation_tie_is_decided_by_label_among_tied_beams():
    beams = [_beam('V306', _box(0, 0, 100, 20)), _beam('VF202', _box(0, 0, 100, 20))]
    texts = [{'text': 'V999', 'pos': [50, 12]}, {'text': 'VF202', 'pos': [50, 40]}, {'text': 'V306', 'pos': [50, 90]}]
    name, _, _ = _dialog(texts, beams)._associate_beam_name(50, 10, {}, _box(40, 5, 60, 15))
    assert name == 'VF202'
