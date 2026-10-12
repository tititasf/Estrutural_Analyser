from pathlib import Path
import json
import ezdxf
import pytest
from src.core.lv_nova_sa_adapter import generate_ab
from src.core.n5_lateral_frames import assemble_lateral_frames, read_units

ROOT = Path(__file__).resolve().parents[1]/'scripts/arete/relatorios/20261002_nova_design'


def test_n5_units_align_by_sa_datum_instead_of_text_bbox(tmp_path):
    manifests=[]
    for side,height,base in [('A',75,99.25),('B',90,99.10)]:
        sa=dict(beam_name='V9',side=side,assembly_variant='gradeadas',
            panels=[dict(width=244,height1=height,height2=height,body_height_cm=height-15,
                         structural_segment_index=1)],
            structural_segments=[dict(segment_index=1,section_contract=dict(
                base_level_m=base,top_level_m=100,mounting={side:dict(panel_base_cm=0)}))])
        generate_ab(sa,tmp_path/f'{side}.dxf')
        manifests.append(tmp_path/f'{side}.units/manifest.json')
    dst=ezdxf.new('R2018')
    result=assemble_lateral_frames(dst,manifests,assembly='gradeadas',behavior='PARA',
        frame_path=ROOT/'moldura_NOVA_aprovada.dxf',index_path=ROOT/'INDICE_NOVA_original.dxf')
    assert len({u['sheet'] for u in result['lateral_units']})==1
    face_labels=[e for e in dst.modelspace().query('TEXT') if e.dxf.text in ('V9.A', 'V9.B')]
    assert {e.dxf.text for e in face_labels} == {'V9.A', 'V9.B'}
    labels=[e.dxf.insert.y for e in face_labels]
    assert len(labels)==2 and labels[0]==pytest.approx(labels[1])


@pytest.mark.parametrize('assembly', ['gradeadas', 'sarrafeadas'])
def test_units_pack_without_changing_source_and_remain_native(tmp_path, assembly):
    manifests = []
    for side in 'AB':
        source = dict(beam_name='V301', side=side, assembly_variant=assembly,
            panels=[dict(width=640, height1=75, height2=75, body_height_cm=60,
                         structural_segment_index=1)])
        generate_ab(source, tmp_path/f'{side}.dxf')
        manifests.append(tmp_path/f'{side}.units/manifest.json')
    original = [(p, p.read_bytes()) for m in manifests for p in m.parent.glob('*.dxf')]
    dst = ezdxf.new('R2018')
    result = assemble_lateral_frames(dst, manifests, assembly=assembly, behavior='PARA',
        frame_path=ROOT/'moldura_NOVA_aprovada.dxf', index_path=ROOT/'INDICE_NOVA_original.dxf',
        obra='Obra teste', cliente='Cliente real', pavimento='13_PAV')
    assert {u['unit']['side'] for u in result['lateral_units']}=={'A','B'}
    assert not dst.modelspace().query('INSERT DIMENSION IMAGE PDFUNDERLAY')
    assert not dst.audit().has_errors
    assert all(p.read_bytes() == before for p, before in original)
    assert all(p['scale'] == 1 for p in result['placements'])
    assert [p['page'] for p in result['pages']] == list(range(1, len(result['pages'])+1))
    # Every source line is present after the declared sheet translation.
    from src.core.n5_pillar_frames import position
    lines = list(dst.modelspace().query('LINE'))
    for unit in result['lateral_units']:
        doc = ezdxf.readfile(unit['source'])
        from ezdxf import bbox
        b = bbox.extents(doc.modelspace())
        ox, oy = position(unit['sheet']+2)
        window=unit['source_window_cm']
        dx,dy=unit['translation_cm'];dx+=ox;dy+=oy
        for line in doc.modelspace().query('LINE'):
            from shapely.geometry import LineString,box
            geometry=LineString([line.dxf.start.xy,line.dxf.end.xy])
            if window:
                if window[0] and abs(line.dxf.start.x-window[0])<1e-6 and abs(line.dxf.end.x-window[0])<1e-6:
                    continue
                geometry=geometry.intersection(box(window[0],-1e6,window[1],1e6))
            if geometry.geom_type=='LineString' and geometry.length>1e-6:
                start,end=geometry.coords[0],geometry.coords[-1]
                assert any(e.dxf.start.isclose((start[0]+dx,start[1]+dy,0)) and e.dxf.end.isclose((end[0]+dx,end[1]+dy,0)) for e in lines), (window,line.dxf.layer,start,end,dx,dy)


def test_inventory_rejects_other_variant_and_changed_source(tmp_path):
    generate_ab(dict(beam_name='V1', side='A', assembly_variant='sarrafeadas',
        panels=[dict(width=122, height1=75, height2=75, body_height_cm=60)]),tmp_path/'A.dxf')
    manifest=tmp_path/'A.units/manifest.json'
    with pytest.raises(ValueError,match='mistura'):
        read_units([manifest], 'gradeadas', 'PARA')
    data=json.loads(manifest.read_text(encoding='utf8'))
    (manifest.parent/data['units'][0]['file']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='alterada'):
        read_units([manifest], 'sarrafeadas', 'PARA')


def test_partitioned_structural_segment_keeps_every_mounting_unit(tmp_path):
    source = dict(beam_name='V314', side='A', assembly_variant='gradeadas',
        panels=[dict(width=131, height1=124, height2=124, body_height_cm=110,
                     structural_segment_index=1, physical_segment_index=1),
                dict(width=19, height1=124, height2=124, body_height_cm=103,
                     structural_segment_index=1, physical_segment_index=2),
                dict(width=131, height1=124, height2=124, body_height_cm=110,
                     structural_segment_index=1, physical_segment_index=3)])
    generate_ab(source, tmp_path/'A.dxf')
    manifest = tmp_path/'A.units/manifest.json'
    units = read_units([manifest], 'gradeadas', 'PARA')
    assert len(units) == 1
    assert [u['segments'] for u, _ in units] == [[1, 1, 1]]
    assert [s['body_cm'] for u,_ in units for s in u['contract']['segments']] == [110,103,110]
    assert sum(s['length'] for u, _ in units for s in u['contract']['segments']) == 281
    with pytest.raises(ValueError, match='duplicada'):
        read_units([manifest, manifest], 'gradeadas', 'PARA')


def test_lateral_index_tracks_selected_template_and_own_titles(tmp_path):
    from hashlib import sha256
    titles = ['CAPA', 'INDICE', 'LEGENDA LV', 'AB GRADEADO',
              'AB SARRAFEADO', 'CORTES LV']
    generate_ab(dict(beam_name='V1', side='A', assembly_variant='gradeadas',
        panels=[dict(width=122, height1=75, height2=75, body_height_cm=60)]),
        tmp_path/'A.dxf')
    template = tmp_path/'indice_lv.dxf'
    index = ezdxf.readfile(ROOT/'INDICE_NOVA_original.dxf')
    index.header['$PROJECTNAME'] = 'LATERAIS'
    index.saveas(template)
    result = assemble_lateral_frames(ezdxf.new('R2018'),
        [tmp_path/'A.units/manifest.json'], assembly='gradeadas', behavior='PARA',
        frame_path=ROOT/'moldura_NOVA_aprovada.dxf', index_path=template,
        index_titles=titles)
    assert [p['title'] for p in result['pages'][:6]] == titles
    assert result['index_sha256'] == sha256(template.read_bytes()).hexdigest()


def test_latest_contract_inventory_does_not_fall_back_to_old_previews(tmp_path):
    from src.core.n5_lateral_frames import published_manifests
    for name in ('001','002'):
        run=tmp_path/'Fase-6_Execucao_CAD/production_sa/13_PAV'/name
        (run/'n3/dxf').mkdir(parents=True)
        (run/'production_manifest.json').write_text('{"visual_mode":"NOVA"}')
        contracts=run/'n3/contracts_lv/LV-PARA/gradeadas'
        contracts.mkdir(parents=True)
        for s in 'AB': (contracts/f'V301_{s}.json').write_text('{}')
        if name=='001':
            for view in ('VIEW_A','VIEW_B','CORTE'):
                path=run/'n3/dxf/gradeadas'/f'LV_preview_V301_Para_{view}.dxf'
                path.parent.mkdir(exist_ok=True);path.write_text('old')
                path.with_suffix('.units').mkdir()
                (path.with_suffix('.units')/'manifest.json').write_text('{}')
    with pytest.raises(ValueError,match='atual incompleto'):
        published_manifests(tmp_path,'13_PAV','gradeadas','PARA')


def test_pending_sa_unit_cannot_disappear_from_fabrication_inventory(tmp_path):
    from src.core.n5_lateral_frames import published_manifests
    run=tmp_path/'Fase-6_Execucao_CAD/production_sa/13_PAV/001'
    (run/'n3/dxf').mkdir(parents=True)
    (run/'production_manifest.json').write_text('{"visual_mode":"NOVA"}')
    inventory=run/'n3/contracts_lv/LV-PARA'
    inventory.mkdir(parents=True)
    (inventory/'V302_A.json').write_text('{"vertical_pending":"altura ausente"}')
    with pytest.raises(ValueError,match='V302'):
        published_manifests(tmp_path,'13_PAV','gradeadas','PARA')


def test_n5_uses_regenerated_manual_panels_and_rejects_unsaved_artifact(tmp_path, monkeypatch):
    from portal.app.lv_n3_operations import load_ficha, save_ficha
    from portal.app.lv_n3_panels import resolve
    from src.core.n5_lateral_frames import published_manifests
    test_normal_n5_uses_complete_variant_inventory(tmp_path, monkeypatch, 'PARA', 'gradeadas')
    draft = load_ficha(tmp_path, '13_PAV', 'para', 'V301', 'gradeadas', mode='NOVA')
    draft['sides']['A']['panels'][0]['height1'] += 1
    draft['sides']['A']['panels'][0]['height2'] += 1
    save_ficha(tmp_path, '13_PAV', 'para', 'V301', draft, 'gradeadas', mode='NOVA')
    with pytest.raises(ValueError, match='atual incompleto'):
        published_manifests(tmp_path, '13_PAV', 'gradeadas', 'PARA')
    paths = [Path(resolve(tmp_path, '13_PAV', 'para', 'V301', side,
                          mode='NOVA', assembly='gradeadas', render=False)['path']) for side in 'AB']
    beams, manifests = published_manifests(tmp_path, '13_PAV', 'gradeadas', 'PARA')
    assert beams == ['V301']
    assert manifests[:2] == [p.with_suffix('.units') / 'manifest.json' for p in paths]
    units = read_units(manifests, 'gradeadas', 'PARA')
    assert units
    draft = load_ficha(tmp_path, '13_PAV', 'para', 'V301', 'gradeadas', mode='NOVA')
    draft['sides']['A']['panels'][0]['height1'] += 1
    draft['sides']['A']['panels'][0]['height2'] += 1
    save_ficha(tmp_path, '13_PAV', 'para', 'V301', draft, 'gradeadas', mode='NOVA')
    with pytest.raises(ValueError, match='atual incompleto'):
        published_manifests(tmp_path, '13_PAV', 'gradeadas', 'PARA')


def test_n5_rejects_stale_cut_when_sa_profile_changes(tmp_path,monkeypatch):
    from portal.app import lv_ficha
    from src.core.n5_lateral_frames import published_manifests
    test_normal_n5_uses_complete_variant_inventory(tmp_path,monkeypatch,'PARA','gradeadas')
    cuts=lv_ficha.montar_ficha_lv()['cut_views']
    cuts[0]['beam_height_cm']=65
    # The aggregate production preview still exists, but is not current proof.
    with pytest.raises(ValueError,match='CORTE/x/gradeadas'):
        published_manifests(tmp_path,'13_PAV','gradeadas','PARA')


def test_n5_rejects_partial_run_even_when_all_its_artifacts_exist(tmp_path,monkeypatch):
    from portal.app import ficha_reader
    from src.core.n5_lateral_frames import published_manifests
    test_normal_n5_uses_complete_variant_inventory(tmp_path,monkeypatch,'PASSA','gradeadas')
    monkeypatch.setattr(ficha_reader,'listar_itens_n1',lambda *args:
                        [{'beam_name':'V301'},{'beam_name':'V302'}])
    with pytest.raises(ValueError,match="ausentes=\\['V302'\\]"):
        published_manifests(tmp_path,'13_PAV','gradeadas','PASSA')


@pytest.mark.parametrize('behavior', ['PARA','PASSA'])
@pytest.mark.parametrize('assembly', ['gradeadas','sarrafeadas'])
def test_normal_n5_uses_complete_variant_inventory(tmp_path, monkeypatch, behavior, assembly):
    from src.core.n5_assembler import assemble_n5
    from src.core import n5_pillar_frames
    from src.core.lv_n3_cut_contract import build_cut_contract
    from scripts.arete.lv_n3_cut_draw import generate_local_sections
    run=tmp_path/'Fase-6_Execucao_CAD/production_sa/13_PAV/001'
    output=run/'n3/dxf'/assembly
    output.mkdir(parents=True)
    (run/'production_manifest.json').write_text('{"visual_mode":"NOVA"}')
    inventory=run/'n3/contracts_lv'/f'LV-{behavior}'
    contracts=inventory/assembly
    contracts.mkdir(parents=True)
    raw_cut=dict(kind='calculated',id='x',beam='V301',width_cm=19,
        beam_height_cm=55,profiles={s:dict(level=852.19,slabs=[]) for s in 'AB'},pairs=[])
    cut=build_cut_contract(raw_cut)
    sources={}
    for side in 'AB':
        source=dict(beam_name='V301',side=side,assembly_variant=assembly,
            behavior=behavior.title(),total_width=305.5,total_height=59,h_section=0,
            structural_segments=[dict(segment_index=1,section_contract=cut)],
            panels=[dict(width=305.5,height1=59,height2=59,body_height_cm=59,
                         structural_segment_index=1)])
        sources[side]=source
        for folder in (inventory,contracts):
            (folder/f'V301_{side}.json').write_text(json.dumps(source))
        generate_ab(source,output/f'LV_preview_V301_{behavior.title()}_VIEW_{side}.dxf',behavior)
    generate_local_sections(sources,output/f'LV_preview_V301_{behavior.title()}_CORTE.dxf','NOVA',behavior)
    from portal.app import ficha_reader, lv_ficha, lv_n3_panels, lv_n3_cuts
    monkeypatch.setattr(ficha_reader,'ler_estado_pavimento',lambda *args: {'current':True})
    monkeypatch.setattr(ficha_reader,'listar_itens_n1',lambda *args: [{'beam_name':'V301'}])
    monkeypatch.setattr(lv_ficha,'montar_ficha_lv',lambda *args,**kwargs: {'cut_views':[raw_cut]})
    for side in 'AB':
        lv_n3_panels.resolve(tmp_path,'13_PAV',behavior.lower(),'V301',side,
                             mode='NOVA',assembly=assembly,render=False)
    lv_n3_cuts.resolve(tmp_path,'13_PAV',behavior.lower(),raw_cut,
                       mode='NOVA',assembly=assembly,render=False)
    calls=[]
    def template(collection,classe):
        calls.append((collection,classe))
        return ROOT/('moldura_NOVA_aprovada.dxf' if collection=='drawing_frames' else 'INDICE_NOVA_original.dxf')
    monkeypatch.setattr(n5_pillar_frames,'uploaded_template',template)
    result=assemble_n5(tmp_path,'LV',pavimento='13_PAV',visual_mode='NOVA',
        lateral_assembly=assembly,lateral_behavior=behavior)
    manifest=json.loads(result.manifest_path.read_text(encoding='utf8'))
    assert result.ok_count==1 and result.missing_count==0
    assert calls==[('drawing_frames',f'LV_{behavior}'),('drawing_legends',f'LV_{behavior}')]
    assert result.output_path.name==f'N5_LV_13_PAV_NOVA_{behavior}_{assembly}.dxf'
    assert len(manifest['frame_layout']['lateral_units'])==3
    assert all('n3_panel_inventory' in u['source'] or 'n3_cut_inventory' in u['source']
               for u in manifest['frame_layout']['lateral_units'])
    assert not ezdxf.readfile(result.output_path).modelspace().query('INSERT DIMENSION IMAGE')



def test_cuts_appear_once_at_2x_ab_remains_1x_on_continuation_sheets(tmp_path):
    from hashlib import sha256
    manifests=[]
    for i in range(1,5):
        path=tmp_path/f'AB{i}.dxf'
        generate_ab(dict(beam_name='V301',side='A',assembly_variant='gradeadas',
            panels=[dict(width=900,height1=180,height2=180,body_height_cm=165,
                         structural_segment_index=i)]),path)
        manifests.append(path.with_suffix('.units')/'manifest.json')
    cuts=tmp_path/'cuts';cuts.mkdir()
    doc=ezdxf.new('R2018');doc.modelspace().add_line((0,0),(100,100));doc.saveas(cuts/'cut.dxf')
    (cuts/'manifest.json').write_text(json.dumps(dict(mode='NOVA',assembly_variant='gradeadas',
        behavior='PARA',units=[dict(file='cut.dxf',kind='CORTE',beam='V301',
        contract=dict(pairs=[dict(a_index=i) for i in range(1,5)]),
        sha256=sha256((cuts/'cut.dxf').read_bytes()).hexdigest())])))
    manifests.append(cuts/'manifest.json')
    dst=ezdxf.new('R2018');pages=tmp_path/'pages'
    result=assemble_lateral_frames(dst,manifests,assembly='gradeadas',behavior='PARA',
        frame_path=ROOT/'moldura_NOVA_aprovada.dxf',index_path=ROOT/'INDICE_NOVA_original.dxf',pages_dir=pages)
    units=result['lateral_units'];ab=[u for u in units if u['unit']['kind']=='AB']
    cuts=[u for u in units if u['unit']['kind']=='CORTE']
    assert len({u['source'] for u in ab})==4 and len(cuts)==1
    assert all(u['scale']==1 for u in ab) and all(u['scale']==2 for u in cuts)
    for sheet in {u['sheet'] for u in ab}:
        row=[u for u in cuts if u['sheet']==sheet]
        assert len(row)<=1
        if row:
            assert all(u['bounds'][3]<row[0]['bounds'][1] for u in ab if u['sheet']==sheet)
    assert not any(u['repeated_context'] for u in cuts)
    assert [p['title'] for p in result['pages'][:2]]==['CAPA','ÍNDICE']
    assert result['pages'][2]['page']==3
    for page in sorted(pages.glob('*.dxf'))[2:]:
        texts=[e.dxf.text for e in ezdxf.readfile(page).modelspace().query('TEXT')]
        assert not any(t.startswith('Laterais:') or t.startswith('V301.A S') and len(t)>30 for t in texts)


def test_frame_blocks_do_not_collide_with_uploaded_template_names():
    from src.core.n5_pillar_frames import SheetBuilder
    dst=ezdxf.new('R2018');builder=SheetBuilder(dst,ezdxf.readfile(ROOT/'moldura_NOVA_aprovada.dxf'))
    source=ezdxf.new('R2018');source.blocks.new('N5_FRAME_PART_1')
    line=source.modelspace().add_line((0,0),(1,1))
    builder.block(source,[line])
    assert 'N5_FRAME_PART_2' in source.blocks


def test_identical_cuts_from_different_beams_stay_separate(tmp_path):
    from hashlib import sha256
    manifests=[]
    originals=[]
    for beam in ('V301','V304'):
        folder=tmp_path/beam;folder.mkdir()
        generate_ab(dict(beam_name=beam,side='A',assembly_variant='gradeadas',
            panels=[dict(width=244,height1=75,height2=75,body_height_cm=60,
                         structural_segment_index=1)]),folder/'AB.dxf')
        manifests.append(folder/'AB.units/manifest.json')
        doc=ezdxf.new('R2018')
        doc.modelspace().add_line((0,0),(19,55))
        doc.modelspace().add_text(beam,dxfattribs={'insert':(0,60),'height':6.5})
        path=folder/'cut.dxf';doc.saveas(path);originals.append((path,path.read_bytes()))
        manifest=folder/'manifest.json'
        manifest.write_text(json.dumps(dict(mode='NOVA',assembly_variant='gradeadas',
            behavior='PARA',units=[dict(file='cut.dxf',kind='CORTE',beam=beam,
                contract=dict(pairs=[dict(a_index=1)]),sha256=sha256(path.read_bytes()).hexdigest())])))
        manifests.append(manifest)
    dst=ezdxf.new('R2018')
    result=assemble_lateral_frames(dst,manifests,assembly='gradeadas',behavior='PARA',
        frame_path=ROOT/'moldura_NOVA_aprovada.dxf',index_path=ROOT/'INDICE_NOVA_original.dxf')
    cuts=[u for u in result['lateral_units'] if u['unit']['kind']=='CORTE']
    assert len(cuts)==2
    assert cuts[0]['sheet']==cuts[1]['sheet']
    assert dst.modelspace().query('LINE[layer=="N5_SEPARACAO_VIGAS"]')
    assert [{a['unit']['beam'] for a in c['represented_cuts']} for c in cuts]==[{'V301'},{'V304'}]
    assert 'V301 / V304' not in [e.dxf.text for e in dst.modelspace().query('TEXT')]
    assert all(p.read_bytes()==data for p,data in originals)
    assert not any(c['repeated_context'] for c in cuts)


def test_cut_identity_preserves_dimensional_and_annotation_differences():
    from src.core.n5_lateral_frames import cut_design_key
    def cut(height,annotation):
        d=ezdxf.new('R2018');d.modelspace().add_line((0,0),(19,height))
        d.modelspace().add_text('V1');d.modelspace().add_text(annotation)
        return cut_design_key(d,'V1')
    assert cut(55,'L1')!=cut(55,'L2')
    assert cut(55,'L1')!=cut(56,'L1')


def test_pending_cuts_fill_first_rows_without_waiting_for_matching_ab(tmp_path):
    from hashlib import sha256
    manifests=[]
    for i in range(4):
        folder=tmp_path/str(i);folder.mkdir()
        generate_ab(dict(beam_name='V301',side='A',assembly_variant='gradeadas',
            panels=[dict(width=1000,height1=400,height2=400,body_height_cm=385,
                         structural_segment_index=i+1)]),folder/'AB.dxf')
        manifests.append(folder/'AB.units/manifest.json')
    folder=tmp_path/'cuts';folder.mkdir()
    units=[]
    for i in range(3):
        d=ezdxf.new('R2018');d.modelspace().add_line((0,0),(300,100+i))
        p=folder/f'{i}.dxf';d.saveas(p)
        units.append(dict(file=p.name,kind='CORTE',beam='V301',
            contract=dict(pairs=[dict(a_index=4)]),sha256=sha256(p.read_bytes()).hexdigest()))
    m=folder/'manifest.json'
    m.write_text(json.dumps(dict(mode='NOVA',assembly_variant='gradeadas',behavior='PARA',units=units)))
    manifests.append(m)
    result=assemble_lateral_frames(ezdxf.new('R2018'),manifests,assembly='gradeadas',behavior='PARA',
        frame_path=ROOT/'moldura_NOVA_aprovada.dxf',index_path=ROOT/'INDICE_NOVA_original.dxf')
    cuts=[u for u in result['lateral_units'] if u['unit']['kind']=='CORTE']
    first=min(c['sheet'] for c in cuts)
    assert sum(c['sheet']==first for c in cuts)==2
    assert sum(c['sheet']==first+1 for c in cuts)==1
    assert len(cuts)==3 and not any(c['repeated_context'] for c in cuts)
