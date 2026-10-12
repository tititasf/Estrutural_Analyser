import pytest
from scripts.arete.pil_agentic_highlight_draw import _fmt_nivel, _row_bits


@pytest.mark.parametrize('levels,expected', [(None,''), ({},''), ({'chegada_abs':None},''),
                                          ({'chegada_abs':0},'0'), ({'chegada_abs':-2.35},'-2.35')])
def test_standalone_missing_reference_never_substitutes_other_floor_level(levels, expected):
    from scripts.arete.pil_agentic_highlight_draw import _default_beam_level
    assert _default_beam_level(levels) == expected


def test_project_reader_keeps_explicit_zero_over_stale_fallback(tmp_path):
    import sqlite3,json
    from scripts.arete.pil_agentic_highlight_draw import load_project
    db=tmp_path/'project.db'
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE projects (id TEXT, dxf_path TEXT)')
        c.execute('CREATE TABLE slabs (project_id TEXT, name TEXT, points_json TEXT, extra_data_json TEXT)')
        c.execute('CREATE TABLE beams (project_id TEXT, name TEXT, data_json TEXT)')
        c.execute('CREATE TABLE pillars (project_id TEXT, name TEXT, points_json TEXT, sides_data_json TEXT, extra_data_json TEXT, type TEXT)')
        c.execute('INSERT INTO slabs VALUES (?,?,?,?)',('p','L','[]',json.dumps({'fields':{'laje_nivel':0},'laje_nivel':9})))
    _,_,levels,_,_,_=load_project(db,'p','any','any')
    assert levels['L']=='0'


@pytest.mark.parametrize('value', [852.19, '852,19', '852.19m', '852.19cm'])
def test_absolute_sa_level_tag_uses_meters_even_legacy_suffix(value):
    assert _fmt_nivel(value)=='852,19m'


def test_tag_keeps_section_dimensions_and_level_separate():
    tag=_row_bits({'nome':'V1','dim':'19/55','nivel':'852.19cm'},'chega',fid='B')
    assert '19/55' in tag and '852,19m' in tag and '852.19cm' not in tag


@pytest.mark.parametrize('value,expected', [('147.985','147,99m'),('147.88','147,88m'),('147.95','147,95m')])
def test_absolute_level_display_rounds_half_up(value,expected):
    assert _fmt_nivel(value)==expected


@pytest.mark.parametrize('value,expected', [
    (0, '0,00m'), ('0cm', '0,00m'), (-2.35, '-2,35m'),
    ('-2,35m', '-2,35m'), ('+2.35cm', '2,35m'), (None, ''),
])
def test_absolute_level_preserves_zero_and_sign(value, expected):
    assert _fmt_nivel(value) == expected


@pytest.mark.parametrize('face', list('ABCD'))
def test_midface_mark_is_preserved_instead_of_discarded(face):
    assert _row_bits({'nome':'L1','canto':face+face},'lajes',fid=face).splitlines()[0] == 'laje '+face+face
