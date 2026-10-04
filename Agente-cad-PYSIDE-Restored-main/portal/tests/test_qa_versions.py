import pytest
from types import SimpleNamespace
from portal.app import qa_versions as qa

SVG='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M1 1H90"/></svg>'

def test_inline_glyph_references_survive_xml_prefixes_and_history(tmp_path):
    raw = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:ns4="http://www.w3.org/1999/xlink"><defs><path id="glyph" d="M0 0L2 2"/></defs><use ns4:href="#glyph"/><use ns4:href="https://external/file"/></svg>'
    cleaned = qa.safe_svg(raw)
    assert 'href="#glyph"' in cleaned and 'ns4:href' not in cleaned
    assert 'external' not in cleaned
    folder = qa.directory(tmp_path, '13_PAV', 'PIL', 'P1')
    folder.mkdir(parents=True)
    (folder/'r.svg').write_text(raw, encoding='utf-8')
    (folder/'L1.json').write_text('{"round_id":"r","viewer_generated":true}', encoding='utf-8')
    records, layers = qa.availability(tmp_path, '13_PAV', 'PIL', 'P1')
    assert 'href="#glyph"' in layers['c1']['svg']
    assert qa.read(tmp_path, '13_PAV', 'PIL', 'P1')['L1']['svg'] == raw
    assert (folder/'r.svg').read_text(encoding='utf-8') == raw
def result(verdict='validou', action='manter'):
    return SimpleNamespace(status='completed',item='V301',verdict=verdict,note='Observação',
        provider='test',model='unit',suggestion={'action':action,'confidence_percent':83,
        'checks':[{'criterion':'contorno','observation':'cota conferida','status':'pass' if verdict=='validou' else 'fail'}],
        'proposed':[] if action!='corrigir' else [{'points':[[1,1],[20,1],[20,20]]}]})
def row(layer='L1', round_id='round1'):
    return {'id':round_id,'pavimento':'13_PAV','classe':'FV','layer':layer}


@pytest.mark.parametrize('classe', ['PIL', 'LAJ', 'FV', 'LV'])
def test_complete_context_survives_layer_chain(tmp_path, monkeypatch, classe):
    fields = {'campos': {'altura': 12}, 'segments': [{'name': 'S1', 'points': [[1, 1], [20, 20]]}]}
    monkeypatch.setattr(qa, 'current_sa', lambda *a, **kw: (SVG, fields))
    request = row(); request['classe'] = classe
    qa.persist(tmp_path, request, result('invalidou', 'corrigir'), SVG, fields)
    svg, inherited = qa.source(tmp_path, '13_PAV', classe, 'V301', 'L2')
    assert inherited['source_interpretation'] == fields
    assert inherited['geometry_coordinate_space'] == 'svg_viewBox'
    assert inherited['field_corrections_applied'] is False
    assert inherited['geometry_proposals']
    inherited['source_interpretation']['campos']['altura'] = 999
    record = qa.read(tmp_path, '13_PAV', classe, 'V301')['L1']
    assert record['interpretation']['campos']['altura'] == 12
    assert record['authority'] == 'agentic'
    assert record['human_validated'] is False
    assert record['corrections_applied'] is False
    assert record['promotion_ready'] is False
    assert 'qa-correction' in svg


def test_field_change_invalidates_geometry_unchanged(tmp_path, monkeypatch):
    fields = {'campos': {'altura': 12}}
    qa.persist(tmp_path, row(), result('invalidou', 'corrigir'), SVG, fields)
    monkeypatch.setattr(qa, 'current_sa', lambda *a, **kw: (SVG, {'campos': {'altura': 13}}))
    with pytest.raises(ValueError, match='campos SA alterados'):
        qa.source(tmp_path, '13_PAV', 'FV', 'V301', 'L2')


def test_unit_review_ledger_is_archived_with_exact_round(tmp_path):
    item=result()
    item.suggestion.update(unit_reviews=[{'unit_path':'/collections/fundo/0','checks':{'niveis':{'status':'uncertain'}}}],
                           unit_coverage={'units':1,'pass':7,'fail':0,'uncertain':1,'measured_accuracy':False})
    qa.persist(tmp_path,row(),item,SVG)
    record=qa.read(tmp_path,'13_PAV','FV','V301')['L1']
    assert record['round_id']=='round1'
    assert record['unit_reviews']==item.suggestion['unit_reviews']
    assert record['unit_coverage']==item.suggestion['unit_coverage']


def test_interpretation_digest_ignores_reference_but_detects_fields():
    assert qa.interpretation_digest(SVG, {'x': 1, '_qa_reference_svg': SVG}) == qa.interpretation_digest(SVG, {'x': 1})
    assert qa.interpretation_digest(SVG, {'x': 1}) != qa.interpretation_digest(SVG, {'x': 2})
    with pytest.raises(ValueError):
        qa.interpretation_digest(SVG, {'x': float('nan')})


def test_historical_false_pass_units_block_promotion_without_rewriting(tmp_path):
    import json
    folder=qa.directory(tmp_path,'13_PAV','FV','V301');folder.mkdir(parents=True)
    record={'round_id':'historic','promotion_ready':True,'post_review':{
        'assessment':'pass','checks':[{'id':'niveis','status':'pass','observation':'Nível 852.19cm'}]}}
    path=folder/'L1.json';text=json.dumps(record);path.write_text(text)
    loaded=qa.read(tmp_path,'13_PAV','FV','V301')['L1']
    assert loaded['promotion_ready'] is False
    assert loaded['promotion_blockers']
    assert path.read_text()==text

@pytest.mark.parametrize('classe', ['PIL','FV','LAJ','LV'])
def test_approval_does_not_generate_and_blocks_next(tmp_path,classe):
    request=row();request['classe']=classe
    qa.persist(tmp_path,request,result(),SVG)
    assert not list(qa.directory(tmp_path,'13_PAV',classe,'V301').glob('*.svg'))
    with pytest.raises(ValueError,match='viewer populado'):
        qa.source(tmp_path,'13_PAV',classe,'V301','L2')

def test_proposal_chain_invalidated_when_previous_changes(tmp_path,monkeypatch):
    monkeypatch.setattr(qa,'current_sa',lambda *args,**kw:(SVG,{}))
    qa.persist(tmp_path,row(),result('invalidou','corrigir'),SVG)
    c1,_=qa.source(tmp_path,'13_PAV','FV','V301','L2')
    assert 'qa-correction' in c1
    qa.persist(tmp_path,row('L2','round2'),result('invalidou','corrigir'),c1)
    assert qa.source(tmp_path,'13_PAV','FV','V301','L3')[0]
    qa.persist(tmp_path,row('L1','round3'),result(),SVG)
    assert qa.read(tmp_path,'13_PAV','FV','V301')['L2']['stale']
    with pytest.raises(ValueError):qa.source(tmp_path,'13_PAV','FV','V301','L3')

def test_sa_edit_invalidates_proposal_as_source(tmp_path,monkeypatch):
    qa.persist(tmp_path,row(),result('invalidou','corrigir'),SVG)
    monkeypatch.setattr(qa,'current_sa',lambda *args,**kw:(SVG.replace('H90','H80'),{}))
    with pytest.raises(ValueError,match='SA alterado'):qa.source(tmp_path,'13_PAV','FV','V301','L2')

def test_missing_evidence_and_contradictory_approval_rejected():
    item=result();item.suggestion['checks']=[]
    with pytest.raises(ValueError):qa.validate_result(item)
    item=result();item.suggestion['checks'][0]['status']='uncertain'
    with pytest.raises(ValueError):qa.validate_result(item)

@pytest.mark.parametrize('points', [[[1,1],[1,1],[1,1]], [[0,0],[200,0],[0,20]], [[0,0],[True,2],[3,4]]])
def test_invalid_geometry_rejected(points):
    with pytest.raises(ValueError):qa.corrected_svg(SVG,[{'points':points}])

def test_svg_keeps_internal_uses_and_canonical_viewbox(tmp_path):
    import xml.etree.ElementTree as ET
    raw='<svg xmlns="http://www.w3.org/2000/svg" viewbox="0 0 100 100"><defs><path id="shape" d="M1 1H20V20Z"/></defs><use href="#shape"/><use/><use href="https://external/a"/></svg>'
    cleaned=qa.safe_svg(raw)
    root=ET.fromstring(cleaned)
    assert root.get('viewBox')=='0 0 100 100'
    assert len(list(root.iter('{http://www.w3.org/2000/svg}use')))==1
    assert 'href="#shape"' in cleaned
    path=tmp_path/'input.svg';path.write_text(cleaned)
    qa.render_png(path,tmp_path/'image.png')
    assert (tmp_path/'image.png').stat().st_size>100

def test_digest_ignores_renderer_ids_and_metadata_but_detects_geometry():
    a='<svg viewBox="0 0 100 100"><metadata>date1</metadata><defs><path id="p123" d="M1 1H20"/></defs><use href="#p123" clip-path="url(#p123)"/></svg>'
    b=a.replace('date1','date2').replace('p123','p987')
    assert qa.digest(a)==qa.digest(b)
    assert qa.digest(a)!=qa.digest(b.replace('H20','H21'))


def test_inline_href_fix_preserves_historical_version_hash():
    raw = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:ns4="http://www.w3.org/1999/xlink"><defs><path id="glyph" d="M0 0L2 2"/></defs><use ns4:href="#glyph"/></svg>'
    # Recorded using the sanitizer/hash implementation before the HTML display fix.
    assert qa.digest(raw) == '3c6e913fff0b8e2acab745b2d81f1853365ed18f87c84160e1718d26b7a45269'
    assert 'href="#glyph"' in qa.safe_svg(raw)
    assert qa.digest(raw) != qa.digest(raw.replace('L2 2', 'L3 2'))


@pytest.mark.parametrize('classe', ['PIL', 'LAJ', 'FV', 'LV'])
def test_candidate_nested_absolute_levels_reject_cm_without_conversion(classe):
    import copy
    candidate = {'classe': classe, 'collections': {'items': [{
        'level': 852.19, 'height': '55cm', 'distance': '3cm',
        'nested': {'nivel': '852,12cm'}, 'nivel_str': '852.19 m',
        'unknown': {'nivel': '—'},
    }]}}
    original = copy.deepcopy(candidate)
    errors = qa.candidate_level_unit_errors(candidate)
    assert len(errors) == 1
    assert '/collections/items/0/nested/nivel:' in errors[0]
    assert candidate == original
    if classe != 'PIL':
        assert qa.candidate_integrity_errors(candidate, SVG) == errors


def test_historical_candidate_unit_error_blocks_promotion_without_rewrite(tmp_path):
    import json
    folder = qa.directory(tmp_path, '13_PAV', 'LV', 'V301')
    folder.mkdir(parents=True)
    record = {'round_id': 'historic', 'promotion_ready': True,
              'candidate_interpretation': {'classe': 'LV', 'collections': {
                  'laterais': [{'lv_cell': {'level': '852.19 cm'}}]}}}
    path = folder / 'L1.json'
    original = json.dumps(record)
    path.write_text(original)
    loaded = qa.read(tmp_path, '13_PAV', 'LV', 'V301')['L1']
    assert loaded['promotion_ready'] is False
    assert any('lv_cell/level' in error for error in loaded['promotion_blockers'])
    assert path.read_text() == original

