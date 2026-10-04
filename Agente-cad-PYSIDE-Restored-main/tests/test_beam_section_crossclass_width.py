from copy import deepcopy
from src.core.pillar_face_beams import canonical_fundo_section_dim,reconcile_beam_fundo_facts

def beam():
    return dict(fields=dict(dimensao='19/66',viga_fundo_seg_1_dim='19/66'),links={
        'viga_segs':dict(seg_bottom=[dict(ficha=dict(largura_total_fundo='14'))]),
        'viga_fundo_seg_1_dim':dict(label=[dict(text='19/66')]),
        'viga_a_seg_1_dim':dict(label=[dict(text='14/55')]),
        'viga_b_seg_1_dim':dict(label=[dict(text='14/55')])})

def test_wrong_pillar_label_requires_own_bottom_width_crosscheck():
    b=beam()
    assert canonical_fundo_section_dim(b)=='14/55'
    reconcile_beam_fundo_facts([b])
    assert b['fields']['dimensao']=='14/55'
    assert b['fields']['viga_fundo_seg_1_dim']=='14/55'

def test_conflicting_sides_abstain_instead_of_majority_or_nearby_label():
    b=beam(); b['links']['viga_b_seg_1_dim']['label'][0]['text']='14/60'
    assert canonical_fundo_section_dim(b)==''
    assert reconcile_beam_fundo_facts([b])==0

def test_validated_dimension_survives_crossclass_reconciliation():
    b=beam(); b['validated_fields']=['dimensao','viga_fundo_seg_1_dim']
    reconcile_beam_fundo_facts([b])
    assert b['fields']['dimensao']=='19/66'
    assert b['fields']['viga_fundo_seg_1_dim']=='19/66'
