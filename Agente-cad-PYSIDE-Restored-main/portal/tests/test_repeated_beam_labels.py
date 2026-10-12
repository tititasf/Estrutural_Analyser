from copy import deepcopy
from portal.app.preprocessamento.repeated_beam_labels import parcel_receivers
from portal.app.preprocessamento.sa_levels import merge_sa_levels


def test_requires_one_original_label_handle_in_proof(tmp_path):
    source = tmp_path / 'original.dxf'
    source.write_text('fixture')
    items = [dict(item_id=k,item_class='beam',display_name='V1',source_entity_handles=[h])
             for k,h in [('first','A'),('second','B')]]
    seg = {'uid':'s2','points':[]}
    def proof(handles):
        return lambda *args: dict(section_source='original_aligned_name_section_wall_pair',source_entity_handles=handles)
    assert parcel_receivers(items,{'V1':[('fundo',seg)]},source,measure=proof(['B','wall']))[0] == {'s2':'second'}
    for handles in ([],['wall'],['A','B']):
        assert parcel_receivers(items,{'V1':[('fundo',seg)]},source,measure=proof(handles))[0] == {}
    assert parcel_receivers(items,{'V1':[('lateral_a_para',seg)]},source,measure=proof(['B']))[0] == {}
    ambiguous = lambda *args: dict(section_source='original_aligned_name_section_wall_pair',
        source_entity_handles=['B','wall'],source_name_candidates=['A','B'])
    assert parcel_receivers(items,{'V1':[('fundo',seg)]},source,measure=ambiguous)[0] == {}


def test_merge_partitions_fund_without_transferring_primary_laterals(monkeypatch):
    from portal.tests.test_preprocessamento_sa_levels import fixture
    import portal.app.preprocessamento.repeated_beam_labels as labels
    tower, context = fixture()
    first = tower['items'][1]
    second = deepcopy(first)
    second['item_id'] = 'own-second-label'
    tower['items'].append(second)
    monkeypatch.setattr(labels,'parcel_receivers',lambda *args: (
        {'V1|2':'own-second-label'}, {'V1|2':{'source_entity_handles':['own-label','wall-a','wall-b']}}))
    result = merge_sa_levels(tower,context)
    a = next(i for i in result['items'] if i['item_id']=='V1')
    b = next(i for i in result['items'] if i['item_id']=='own-second-label')
    assert [s['uid'] for s in a['segments']] == ['V1|1']
    assert [s['uid'] for s in b['segments']] == ['V1|2']
    assert b['segments'][0]['original_label_parcel_proof']['source_entity_handles'][0] == 'own-label'
    assert b['levels'][0]['status'] == 'estimated'
    assert b['levels'][0]['value'] == 852.12


def test_unbound_repeated_label_retains_unknown_history():
    from portal.tests.test_preprocessamento_sa_levels import fixture
    tower, context = fixture()
    second = deepcopy(tower['items'][1])
    second.update(item_id='unproved',levels=[dict(field='beam_top',value=None,status='unknown')])
    tower['items'].append(second)
    result = merge_sa_levels(tower,context)
    b = next(i for i in result['items'] if i['item_id']=='unproved')
    assert b['segments'] == []
    assert b['pre_sa_levels'][0]['status'] == 'unknown'


def test_lateral_follows_its_proved_fund_not_the_remote_first_label(tmp_path):
    source = tmp_path / 'original.dxf'
    source.write_text('fixture')
    items = [dict(item_id=k,item_class='beam',display_name='V1',source_entity_handles=[h])
             for k,h in [('first','A'),('second','B')]]
    fund = dict(uid='near',points=[[0,0],[100,100],[110,90],[10,-10],[0,0]])
    far = dict(uid='far',points=[[500,0],[600,0],[600,14],[500,14],[500,0]])
    side = dict(uid='side',points=[[0,0],[100,100]])
    measure = lambda points,*args: dict(section_source='original_aligned_name_section_wall_pair',
        source_entity_handles=['B' if points == fund['points'] else 'A','wall-a','wall-b'])
    owners, proofs = parcel_receivers(items,{'V1':[('fundo',far),('fundo',fund),
        ('lateral_a_para',side),('lateral_a_passa',dict(side,uid='pass'))]},source,measure=measure)
    assert owners == dict(far='first',near='second',side='second',**{'pass':'second'})
    assert proofs['side']['source_fv_segments'] == ['near']
    assert proofs['side']['spatial_coverage'] == 1


def test_lateral_cannot_cross_owners_or_use_partial_or_interior_contact(tmp_path):
    source = tmp_path / 'original.dxf'
    source.write_text('fixture')
    items = [dict(item_id=k,item_class='beam',display_name='V1',source_entity_handles=[k])
             for k in ('A','B')]
    a = dict(uid='a',points=[[0,0],[50,0],[50,14],[0,14],[0,0]])
    b = dict(uid='b',points=[[50,0],[100,0],[100,14],[50,14],[50,0]])
    measure = lambda points,*args: dict(section_source='original_aligned_name_section_wall_pair',
        source_entity_handles=['A' if points == a['points'] else 'B'])
    for points in ([[0,0],[100,0]], [[0,0],[200,0]], [[0,7],[50,7]], [[25,-20],[25,30]]):
        owners,_ = parcel_receivers(items,{'V1':[('fundo',a),('fundo',b),
            ('lateral_a_para',dict(uid='side',points=points))]},source,measure=measure)
        assert 'side' not in owners


def test_merge_resolves_lateral_from_its_own_parcel_level(tmp_path,monkeypatch):
    from portal.tests.test_segment_level_correspondence import fixture
    import portal.app.preprocessamento.oriented_beam_section as section
    tower, context, fund, side = fixture()
    source=tmp_path/'original.dxf'
    import ezdxf
    ezdxf.new().saveas(source)
    context['tower_path']=source
    first=tower['items'][0]
    first['source_entity_handles']=['A']
    second=deepcopy(first)
    second.update(item_id='own-near-label',source_entity_handles=['B'])
    tower['items'].append(second)
    context['state']['segmentos']['lateral_b_para']=[
        side(1,0,50,level=999,slab=None)]
    context['state']['segmentos']['lateral_b_para'][0]['level_source']='lv_cell_estimado'
    monkeypatch.setattr(section,'source_section',lambda points,*args: dict(
        section_source='original_aligned_name_section_wall_pair',
        source_entity_handles=['B' if max(p[0] for p in points)<=50 else 'A']))
    result=merge_sa_levels(tower,context)
    own=next(i for i in result['items'] if i['item_id']=='own-near-label')
    remote=next(i for i in result['items'] if i['item_id']=='V1')
    lateral=next(s for s in own['segments'] if s['family']=='lateral_b_para')
    assert lateral['level']==100
    assert lateral['status']!='estimated'
    assert lateral['level_ranges'][0]['fv_segments']==[1]
    assert all(s['family']=='fundo' and s['level']==101 for s in remote['segments'])
