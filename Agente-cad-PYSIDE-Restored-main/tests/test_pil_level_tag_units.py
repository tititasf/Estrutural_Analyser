import pytest
from scripts.arete.pil_agentic_highlight_draw import _fmt_nivel, _row_bits


@pytest.mark.parametrize('value', [852.19, '852,19', '852.19m', '852.19cm'])
def test_absolute_sa_level_tag_uses_meters_even_legacy_suffix(value):
    assert _fmt_nivel(value)=='852,2m'


def test_tag_keeps_section_dimensions_and_level_separate():
    tag=_row_bits({'nome':'V1','dim':'19/55','nivel':'852.19cm'},'chega',fid='B')
    assert '19/55' in tag and '852,2m' in tag and '852.19cm' not in tag


@pytest.mark.parametrize('value,expected', [('147.98','148,0m'),('147.88','147,9m'),('147.95','148,0m')])
def test_absolute_level_display_rounds_half_up(value,expected):
    assert _fmt_nivel(value)==expected


@pytest.mark.parametrize('face', list('ABCD'))
def test_midface_mark_is_preserved_instead_of_discarded(face):
    assert _row_bits({'nome':'L1','canto':face+face},'lajes',fid=face).splitlines()[0] == 'laje '+face+face
