import copy
import pytest
from src.core.lv_n3_cut_contract import build_cut_contract, CutContractError
from scripts.arete.lv_n3_cut_draw import generate as generate_mode


def generate(contract, path, mode='INI'):
    # These tests protect the previous AQ/INI conventions. NOVA deliberately
    # has the approved hatch/hardware rules tested against its frozen DXFs.
    return generate_mode(contract, path, mode)


def test_original_cut_hardware_has_nested_geometry(tmp_path):
    from ezdxf import bbox
    doc=generate(build_cut_contract(calculated()),tmp_path/'original-hardware.dxf')
    # Authentic nut/plate geometry and inherited dependencies must survive
    # export/reload; the earlier shared blocks were only two crossing lines.
    import ezdxf
    loaded=ezdxf.readfile(tmp_path/'original-hardware.dxf')
    assert not loaded.audit().has_errors
    assert len(loaded.blocks['PAR_ESQ'].query('INSERT'))==2
    entity=loaded.modelspace().add_blockref('PAR_ESQ',(0,0))
    bounds=bbox.extents([entity])
    assert bounds.size.y==pytest.approx(12)
    assert bounds.size.x>5


def test_original_hardware_converts_legacy_double_scale(tmp_path):
    from scripts.arete.lv_n3_cut_draw import insert_original_fitting
    from ezdxf import bbox
    doc=generate(build_cut_contract(calculated()),tmp_path/'physical-hardware.dxf')
    insert=insert_original_fitting(doc.modelspace(),'PAR_ESQ',20,30)
    bounds=bbox.extents([insert])
    assert bounds.size.y==pytest.approx(6)
    assert insert.dxf.insert.x==20 and insert.dxf.insert.y==30
    with pytest.raises(ValueError,match='fora do escopo'):
        insert_original_fitting(doc.modelspace(),'PARAFUSO_PILAR',0,0)


@pytest.mark.parametrize('height',[14,25,55,120])
def test_lower_fixing_pair_is_present_at_all_section_heights(tmp_path,height):
    cut=calculated();cut['beam_height_cm']=height
    cut['profiles']['A']['slabs']=[];cut['profiles']['B']['slabs']=[]
    doc=generate(build_cut_contract(cut),tmp_path/f'bottom-{height}.dxf')
    inserts=list(doc.modelspace().query('INSERT'))
    bottoms=[e for e in inserts if e.dxf.name.startswith('PAR_FUNDO')]
    assert sorted(e.dxf.name for e in bottoms)==['PAR_FUNDO_DIR','PAR_FUNDO_ESQ']
    assert len({e.dxf.insert.y for e in bottoms})==1
    assert all(e.dxf.xscale==.5 for e in inserts)
    assert not doc.audit().has_errors


def test_cut_sarrafos_use_lateral_n3_rule_without_extra_edge_pieces(tmp_path):
    from scripts.arete.lv_n3_cut_draw import motor
    contract=build_cut_contract(calculated())
    doc=generate(contract,tmp_path/'slats.dxf')
    actual=[]
    for e in doc.modelspace().query('LWPOLYLINE'):
        if e.dxf.layer!='Madeira':continue
        pts=list(e.get_points('xy'))
        actual.append(round((min(y for x,y in pts)+max(y for x,y in pts))/2,6))
    expected=[]
    for side in ('A','B'):
        slab=contract['slabs'][side][0]
        panel_height=contract['height_cm']-slab['drop_cm']-slab['height_cm']-2+4
        _,_,positions=motor()._get_sarrafo_positions(panel_height)
        expected.extend(round(p-4,6) for p in positions)
    assert sorted(actual)==sorted(expected)


def calculated():
    return {'kind':'calculated','id':'test-cut','beam':'V1','width_cm':19,'beam_height_cm':55,
            'profiles':{'A':{'level':852.12,'slabs':[{'name':'L1','height_cm':10,'level':852.12}]},
                        'B':{'level':852.19,'slabs':[{'name':'L2','height_cm':12,'level':852.19}]}},'pairs':[]}


def test_inverted_cut_has_top_liso_cap_without_normal_soffit_hardware(tmp_path):
    cut=calculated();cut['beam_height_cm']=71
    cut['section_semantics']={'confirmed':True,'beam_type':'inverted'}
    for profile in cut['profiles'].values():
        profile['level']=852.12;profile['level_source']='lv_cell_slabs'
        profile['slabs']=[{'name':'L','height_cm':13,'level':852.12}]
    contract=build_cut_contract(cut)
    assert contract['top_level_m']==pytest.approx(852.70)
    assert contract['base_level_m']==pytest.approx(851.99)
    doc=generate(contract,tmp_path/'inverted.dxf')
    space=doc.modelspace()
    labels={e.dxf.text for e in space.query('TEXT')}
    assert {'LISO','VIGA INVERTIDA'}<=labels
    assert not list(space.query('INSERT'))
    cap=[]
    for e in space.query('LWPOLYLINE'):
        points=list(e.get_points('xy'))
        if e.dxf.layer=='Painéis' and min(p[1] for p in points)==71 and max(p[1] for p in points)==73:
            cap.append(e)
        if e.dxf.layer=='SARR_3.5x7':
            assert min(p[1] for p in points)>=0
    assert len(cap)==1
    assert not doc.audit().has_errors


def test_inverted_original_base_reference_preserves_opposite_lower_slab():
    cut=calculated();cut['beam_height_cm']=120
    cut['profiles']['A'].update(level_source='lv_cell_slabs',level=852.12,
        slabs=[{'name':'upper_neighbor','height_cm':13,'level':852.12}])
    cut['profiles']['B'].update(level_source='paired_touching_slabs',level=852.19,
        slabs=[{'name':'base_owner','height_cm':13,'level':852.19}])
    cut['section_semantics']={'confirmed':True,'beam_type':'inverted','height_cm':120,
        'reference_height_cm':120,'flanges':{'left':{'height_cm':10,'bottom_cm':0},
                                           'right':{'height_cm':13,'bottom_cm':0}}}
    contract=build_cut_contract(cut)
    assert contract['base_level_m']==pytest.approx(852.06)
    assert contract['top_level_m']==pytest.approx(853.26)
    assert contract['slabs']['A'][0]['drop_cm']==114
    assert contract['slabs']['B'][0]['drop_cm']==107
    # A changed 71 cm profile must use its own slab, not the 120 cm datum.
    cut['beam_height_cm']=71
    assert build_cut_contract(cut)['base_level_m']==pytest.approx(851.99)


def test_slab_step_keeps_beam_top_and_draws_upper_closure(tmp_path):
    cut=calculated()
    for side in ('A','B'):
        cut['profiles'][side]['level']=852.19
        cut['profiles'][side]['slabs']=[{'name':'L','height_cm':10,'level':852.16}]
    contract=build_cut_contract(cut)
    assert contract['slabs']['A'][0]['drop_cm']==pytest.approx(3)
    assert contract['height_cm']==55
    doc=generate(contract,tmp_path/'step-upper-closure.dxf')
    closures=[]
    for entity in doc.modelspace().query('LWPOLYLINE'):
        if entity.dxf.layer=='Painéis':
            ys=[p[1] for p in entity.get_points('xy')]
            if min(ys)==pytest.approx(52) and max(ys)==pytest.approx(57):
                closures.append(entity)
    assert len(closures)==2


@pytest.mark.parametrize('a,b,count',[(40,40,2),(40,80,2),(40.01,40.01,5),
                                     (90,90,5),(90,100,5),(90.01,90.01,8)])
def test_fixing_thresholds_use_both_local_h1_strictly(tmp_path,a,b,count):
    cut=calculated(); cut['beam_height_cm']=120
    for side,h1 in [('A',a),('B',b)]:
        cut['profiles'][side]['level']=852.19
        cut['profiles'][side]['slabs']=[{'name':side,'height_cm':122-h1,'level':852.19}]
    contract=build_cut_contract(cut)
    doc=generate(contract,tmp_path/'threshold.dxf')
    inserts=list(doc.modelspace().query('INSERT'))
    assert len(inserts)==count
    internal=[e.dxf.insert.y for e in inserts if e.dxf.name=='par_int_esq']
    assert internal==([] if count==2 else [21.] if count==5 else [21.,71.])
    assert not doc.audit().has_errors


@pytest.mark.parametrize('side',['A','B'])
def test_either_lower_slab_suppresses_all_fixings(tmp_path,side):
    cut=calculated();cut['beam_height_cm']=120
    for p in cut['profiles'].values():p['level']=852.19;p['slabs']=[]
    # Upper surface 10 cm above soffit; slab lower surface reaches soffit.
    cut['profiles'][side]['slabs']=[{'name':'LI','height_cm':10,'level':851.09}]
    contract=build_cut_contract(cut)
    assert contract['mounting'][side]['lower_slab']
    assert contract['mounting'][side]['panel_base_cm']==12
    doc=generate(contract,tmp_path/'lower-slab.dxf')
    assert not list(doc.modelspace().query('INSERT'))
    assert not [e for e in doc.modelspace() if e.dxf.layer=='BARRA_ANCORAGEM']
    assert not doc.audit().has_errors


def test_asymmetric_slab_drop_is_not_beam_conflict():
    contract=build_cut_contract(calculated())
    assert contract['slabs']['A'][0]['drop_cm']==7
    assert contract['slabs']['B'][0]['drop_cm']==0
    assert contract['source']=='N1'


def test_geometry_and_executive_dimensions_close(tmp_path):
    contract=build_cut_contract(calculated())
    doc=generate(contract,tmp_path/'cut.dxf')
    assert not doc.audit().has_errors
    core=next(e for e in doc.modelspace() if e.dxf.layer=='CONCRETO')
    pts=list(core.get_points('xy'))
    assert (-9.5,0) in pts and (9.5,0) in pts
    assert max(y for x,y in pts)==55
    # A at -7 with 10 cm slab: 38-2+4=40 cm body; B 43-2+4=45.
    panels=[e for e in doc.modelspace().query('LWPOLYLINE') if e.dxf.layer=='Painéis']
    heights=[max(p[1] for p in e.get_points())-min(p[1] for p in e.get_points()) for e in panels]
    assert 40 in heights and 45 in heights
    labels={e.dxf.text for e in doc.modelspace().query('TEXT')}
    assert {'19','55','7','10','12','40','45'} <= labels


def test_missing_slab_measure_fails_closed():
    cut=calculated();cut['profiles']['A']['slabs'][0]['height_cm']=None
    with pytest.raises(CutContractError,match='height_cm'):
        build_cut_contract(cut)


def test_slab_above_beam_reference_does_not_raise_beam():
    cut=calculated()
    for profile in cut['profiles'].values():
        profile['level']=852.12
    cut['profiles']['B']['slabs'][0]['level']=852.19
    with pytest.raises(CutContractError,match='laje fora da altura da viga'):
        build_cut_contract(cut)


def test_section_fingerprint_changes_when_slab_changes():
    cut=calculated(); before=build_cut_contract(cut)
    cut['profiles']['A']['slabs'][0]['height_cm']=11
    assert build_cut_contract(cut)['fingerprint']!=before['fingerprint']


def test_identified_neigh_field_and_explicit_absence():
    cut={'kind':'identified','beam':'V1','id':'c1','source_cut':{'beam_w':19,'beam_h':55,'own_laje':'L1','neigh_laje':'L2',
         'ficha':{'side_a_laje_name':'L1','side_b_laje_name':'L2','own_slab_height':12,'own_dist_top':0,'own_dist_bottom':43,
                  'neigh_slab_height':10,'neighbor_dist_top':7,'neighbor_dist_bottom':38}}}
    assert build_cut_contract(cut)['slabs']['B'][0]['height_cm']==10
    cut['source_cut']['ficha']['beam_lajes_side_b']='0'
    cut['source_cut']['ficha']['neigh_slab_height']='nulo'
    assert build_cut_contract(cut)['slabs']['B']==[]


def test_cut_keeps_ini_outline_and_nova_approved_hatches(tmp_path):
    contract=build_cut_contract(calculated())
    a=generate(contract,tmp_path/'a.dxf','NOVA');b=generate(contract,tmp_path/'b.dxf','INI')
    assert len(a.modelspace().query('HATCH'))>0
    assert len(b.modelspace().query('HATCH'))==0
    assert not list(a.modelspace().query('INSERT'))  # approved sarrafeadas: forks
    assert list(b.modelspace().query('INSERT'))
    assert not a.audit().has_errors and not b.audit().has_errors


def test_merged_other_owner_keeps_ficha_orientation():
    cut={'kind':'identified','beam':'V1','id':'merged','source_cut':{
        'beam_w':19,'beam_h':55,'own_laje':'L_south','neigh_laje':'L_north',
        'ficha':{'direction':'Sul','side_a_laje_name':'L_south','side_b_laje_name':'L_north',
                 'own_slab_height':12,'own_dist_top':0,'own_dist_bottom':43,
                 'neigh_slab_height':10,'neighbor_dist_top':7,'neighbor_dist_bottom':38}}}
    contract=build_cut_contract(cut)
    assert contract['slabs']['A']==[{'name':'L_south','height_cm':10,'drop_cm':7}]
    assert contract['slabs']['B']==[{'name':'L_north','height_cm':12,'drop_cm':0}]
    cut['source_cut']['own_laje']='L_north'
    cut['source_cut']['neigh_laje']='L_south'
    assert build_cut_contract(cut)['slabs']==contract['slabs']


def test_annotated_slab_precedes_symbol_and_recomputes_panel(tmp_path):
    cut={'kind':'identified','beam':'V1','id':'annotated','source_cut':{
        'beam_w':19,'beam_h':55,'own_laje':'L1','neigh_laje':'L2',
        'ficha':{'direction':'Sul','side_a_laje_name':'L1','side_b_laje_name':'L2',
                 'side_a_laje_height':'h=10','side_b_laje_height':'h=13',
                 'own_slab_height':12,'own_dist_top':0,'own_dist_bottom':43,
                 'neigh_slab_height':10,'neighbor_dist_top':7,'neighbor_dist_bottom':38}}}
    contract=build_cut_contract(cut)
    assert contract['slabs']['B'][0]['height_cm']==13
    doc=generate(contract,tmp_path/'annotated.dxf')
    labels={e.dxf.text for e in doc.modelspace().query('TEXT')}
    assert {'13','10','44','40','55','19'} <= labels
    assert any('símbolo mede 12 cm' in w for w in contract['warnings'])
