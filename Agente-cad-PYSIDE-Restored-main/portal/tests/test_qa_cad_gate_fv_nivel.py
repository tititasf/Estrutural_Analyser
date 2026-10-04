"""Nível FV: região de degrau tocada + padrão do pavimento com ausência de exceção provada no original."""
import json

import ezdxf
import pytest

from portal.app import qa_cad_gate as g


def _square(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def _slab(name, box, steps=()):
    return dict(name=name, height='12', nivel=None, points=_square(*box),
                slab_steps=[dict(uid=f'x:{uid}', points=_square(*b), height_cm=10, level_m=None) for uid, b in steps])


def _draw(msp, slabs, texts):
    for s in slabs:
        pts = s['points']
        for a, b in zip(pts, pts[1:] + pts[:1]):
            msp.add_line(a, b)
    for text, (x, y) in texts:
        msp.add_text(text, dxfattribs={'insert': (x, y), 'height': 10})


@pytest.fixture
def obra(tmp_path, monkeypatch):
    monkeypatch.setattr(g, '_floor_datum', lambda original, floor, anchors: (852.19, ['T1']))

    def build(slabs, texts, extra=lambda msp: None):
        crop_dir = tmp_path / 'Fase-2_Triagem' / 'recortes' / 'P'
        raw_dir = tmp_path / 'Fase-1_Ingestao' / 'Brutos'
        crop_dir.mkdir(parents=True)
        raw_dir.mkdir(parents=True)
        for path, more in ((crop_dir / 'torre_1.dxf', None), (raw_dir / 'P.dxf', extra)):
            doc = ezdxf.new()
            _draw(doc.modelspace(), slabs, texts)
            if more:
                more(doc.modelspace())  # o recorte descarta SOLID/letras como no 13_PAV
            doc.saveas(path)
        (crop_dir / 'crop_result.json').write_text(json.dumps({'dxf_bruto': 'C:\\obra\\P.dxf'}), encoding='utf-8')
        return crop_dir / 'torre_1.dxf'
    return build


BEAM = dict(beam_name='V1', segment_label='1', width='19', points=_square(0, 200, 400, 219))
# S1 ao sul da viga; N1 ao norte, sem cota; N2/N3 vizinhas de N1 através de viga.
S1, N1 = _slab('S1', (0, 0, 400, 200)), _slab('N1', (0, 219, 400, 419))
N2, N3 = _slab('N2', (419, 219, 819, 419)), _slab('N3', (-419, 219, -19, 419))


def _level(source, slabs, level='852.19', beam=BEAM):
    rows = [dict(beam, level=level)]
    return next(c for c in g.measure_beams(source, {'collections': {'fundo': rows}}, slabs, '13_PAV')['contacts']
                if c['aspect'] == 'nível')


def _zone(s1='852,12', n=('852,19', '852,19')):
    return [(s1, (100, 100)), (n[0], (600, 300)), (n[1], (-200, 300))]


def test_standard_level_needs_absence_and_agreeing_neighbours(obra):
    source = obra([S1, N1, N2, N3], _zone())
    rec = _level(source, [S1, N1, N2, N3])
    assert rec['status'] == 'measured' and not rec['errors']
    assert 'padrão do pavimento' in rec['level_basis']
    wrong = _level(source, [S1, N1, N2, N3], level='852.12')
    assert 'niveis' in wrong['errors']


def test_region_fill_only_in_original_blocks_standard(obra):
    source = obra([S1, N1, N2, N3], _zone(),
                  lambda msp: msp.add_solid([(100, 250), (200, 250), (100, 350), (200, 350)]))
    rec = _level(source, [S1, N1, N2, N3])
    assert rec['status'] == 'uncertain' and 'preenchimento' in rec['reason']


def test_arrow_sized_fill_is_not_a_region_exception(obra):
    source = obra([S1, N1, N2, N3], _zone(),
                  lambda msp: msp.add_solid([(100, 250), (130, 250), (100, 262), (130, 262)]))
    assert _level(source, [S1, N1, N2, N3])['status'] == 'measured'


def test_cut_marks_crossing_the_slab_block_standard(obra):
    def letters(msp):
        msp.add_text('A', dxfattribs={'insert': (50, 300), 'height': 10})
        msp.add_text('A', dxfattribs={'insert': (350, 300), 'height': 10})
    rec = _level(obra([S1, N1, N2, N3], _zone(), letters), [S1, N1, N2, N3])
    assert rec['status'] == 'uncertain' and 'corte A-A' in rec['reason']


def _section(msp, *, level='852,19', title=True, labels=True, step=False):
    """Elevação fora do recorte alinhada à marca A-A (x 100–300)."""
    y_cut = 350 if step else 300
    msp.add_text('A', dxfattribs={'insert': (100, y_cut), 'height': 8})
    msp.add_text('A', dxfattribs={'insert': (300, y_cut), 'height': 8})
    if title:
        msp.add_text('CORTE A-A', dxfattribs={'insert': (2100, 1500), 'height': 12})
    if labels:
        msp.add_text('V301', dxfattribs={'insert': (150, y_cut), 'height': 8})
        msp.add_text('V301', dxfattribs={'insert': (2050, 1500), 'height': 8})
    if step:
        msp.add_line((2000, 1482), (2100, 1482))
        msp.add_line((2000, 1470), (2100, 1470))
        msp.add_line((2100, 1460), (2200, 1460))
        msp.add_line((2100, 1448), (2200, 1448))
    else:
        for y in (1482, 1470, 1400):
            msp.add_line((2000, y), (2200, y))
    msp.add_text(level, dxfattribs={'insert': (2100, 1497), 'height': 8})


def test_flat_section_at_datum_lets_the_standard_through(obra):
    source = obra([S1, N1, N2, N3], _zone(), lambda msp: _section(msp))
    rec = _level(source, [S1, N1, N2, N3])
    assert rec['status'] == 'measured' and not rec['errors']
    assert 'padrão do pavimento' in rec['level_basis']


def test_drawn_step_in_the_section_stays_uncertain(obra):
    stepped = _slab('N1', (0, 219, 400, 419), steps=[('BD1', (200, 300, 400, 419))])
    source = obra([S1, stepped, N2, N3], _zone(), lambda msp: _section(msp, step=True))
    rec = _level(source, [S1, stepped, N2, N3])
    assert rec['status'] == 'uncertain' and 'degrau' in rec['reason']


def test_section_level_different_from_datum_stays_uncertain(obra):
    source = obra([S1, N1, N2, N3], _zone(), lambda msp: _section(msp, level='852,16'))
    rec = _level(source, [S1, N1, N2, N3])
    assert rec['status'] == 'uncertain' and 'corte A-A' in rec['reason']


def test_section_without_title_stays_uncertain(obra):
    rec = _level(obra([S1, N1, N2, N3], _zone(), lambda msp: _section(msp, title=False)),
                 [S1, N1, N2, N3])
    assert rec['status'] == 'uncertain' and 'título' in rec['reason']


def test_symmetric_section_without_labels_stays_uncertain(obra):
    rec = _level(obra([S1, N1, N2, N3], _zone(), lambda msp: _section(msp, labels=False)),
                 [S1, N1, N2, N3])
    assert rec['status'] == 'uncertain' and 'sentido' in rec['reason']


def test_mixed_zone_slab_is_only_an_upper_bound(obra):
    lower = _zone(s1='852,19', n=('852,12', '852,12'))
    source = obra([S1, N1, N2, N3], lower)
    rec = _level(source, [S1, N1, N2, N3])
    assert rec['status'] == 'measured' and any('<= padrão' in b for b in rec['level_basis'])


def test_bound_above_every_written_level_never_certifies(obra):
    source = obra([S1, N1, N2, N3], _zone(s1='852,12', n=('852,12', '852,12')))
    rec = _level(source, [S1, N1, N2, N3])
    assert rec['status'] == 'uncertain'


STEP_SLAB = _slab('S1', (0, 0, 400, 200), steps=[('BD1', (0, 150, 100, 200))])
STEP_BEAM = dict(BEAM, points=_square(0, 200, 90, 219))


@pytest.mark.parametrize('step_text, status', [('852,16', 'measured'), ('852,25', 'uncertain'), (None, 'uncertain')])
def test_step_region_touched_uses_its_own_written_level(obra, step_text, status):
    texts = [('852,19', (300, 100))] + ([(step_text, (50, 175))] if step_text else [])
    rec = _level(obra([STEP_SLAB], texts), [STEP_SLAB], beam=STEP_BEAM)
    assert rec['status'] == status and not rec['errors']
    if status == 'measured':
        assert any('painel de topo' in b for b in rec['level_basis'])


def test_slab_measurement_is_cached(obra, monkeypatch):
    source = obra([S1, N1, N2, N3], _zone())
    _level(source, [S1, N1, N2, N3])
    monkeypatch.setattr(g, '_measure_slabs', lambda *a: pytest.fail('lajes medidas de novo'))
    _level(source, [S1, N1, N2, N3])
