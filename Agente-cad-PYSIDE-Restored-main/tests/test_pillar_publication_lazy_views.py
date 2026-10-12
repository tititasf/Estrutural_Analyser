from scripts.arete.export_pilares_abcd_fichas import build_pillar_page
from src.core.pil_qa_notes_chrome import wrap_n1_panzoom,js_pil_qa

def test_secondary_pillar_views_reuse_full_svg_assets():
    page=build_pillar_page('P1','Retangular',{},obra='test',pav='floor',niveis={},idx=1,total=1,nav_links='',n1_near='<svg id="active"/>',n1_near_plain='<svg id="plain"/>',n1_far='<svg id="far"/>',l1_svg='<svg id="l1"/>',n1_far_src='../propostas/P1_sa_far.svg')
    assert '<svg id="active"/>' not in page
    for inactive in ('plain','far','l1'):
        assert f'<svg id="{inactive}"/>' not in page
    for asset in ('sa_motor','sa_plain','sa_far','qa_L1'):
        assert f'../propostas/P1_{asset}.svg' in page
    assert 'window.loadPilView(p)' in page
    assert 'viewBox' in page

def test_standalone_inline_panzoom_remains_compatible():
    assert '<svg id="inline"/>' in wrap_n1_panzoom('<svg id="inline"/>',viewer_id='v')
    lazy=wrap_n1_panzoom('<svg/>',viewer_id='v',svg_src='full.svg')
    assert 'data-proposal-src="full.svg"' in lazy and '<svg/>' not in lazy
    assert 'window.loadPilView' in js_pil_qa()def test_plain_fallback_loads_existing_plain_asset():    page = build_pillar_page('P1','Retangular',{},obra='test',pav='floor',        niveis={},idx=1,total=1,nav_links='',n1_near='<svg/>',n1_near_plain='<svg/>')    assert 'P1_sa_motor.svg' not in page    assert 'P1_sa_plain.svg' in page


def test_unknown_convention_does_not_invent_levels_or_height():
    page = build_pillar_page('P1', '', {}, obra='unknown', pav='unknown',
        niveis={}, idx=1, total=1, nav_links='')
    assert '852.19' not in page and '848.98' not in page
    assert 'Nonecm' not in page
    assert '<td>Nível chegada</td><td><b>—</b>' in page


def test_absolute_convention_is_metres_height_is_centimetres():
    page = build_pillar_page('P1', '', {}, obra='test', pav='floor',
        niveis={'chegada_abs': 0, 'saida_abs': -3.21, 'altura_cm': 321},
        idx=1, total=1, nav_links='')
    assert '<b>0,00 m</b>' in page
    assert '<b>-3,21 m</b>' in page
    assert '<b>321 cm</b>' in page
