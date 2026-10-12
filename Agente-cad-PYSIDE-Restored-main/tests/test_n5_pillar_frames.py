import ezdxf
import pytest
from src.core.n5_pillar_frames import SheetBuilder, INDEX_ORIGINS, INDEX_TITLES, primitives, position


def test_lateral_index_titles_keep_overflow_order_without_changing_pillar_defaults():
    from src.core.n5_pillar_frames import index_sheet_order
    titles = ['CAPA', 'ÍNDICE', 'LEGENDA LV', 'AB GRADEADO', 'AB SARRAFEADO', 'CORTE LV']
    assert index_sheet_order(1, titles) == [(0, titles[0]), (1, titles[1]),
        (1, 'ÍNDICE — CONTINUAÇÃO'), *list(enumerate(titles[2:], start=2))]
    assert [title for _, title in index_sheet_order(0)] == INDEX_TITLES
    with pytest.raises(ValueError, match='seis folhas'):
        index_sheet_order(0, titles[:5])


def test_nested_frame_labels_use_actual_obra_and_pavimento_without_mutating_template():
    source=ezdxf.new('R2018')
    source.modelspace().add_text('06',dxfattribs={'layer':'CARIMBO'})
    block=source.blocks.new('CARIMBO_VALUES')
    for i,text in enumerate(('PARAISO','1º PAVIMENTO','LATERAL DE VIGAS')):
        block.add_text(text,dxfattribs={'insert':(0,i*10)})
    source.modelspace().add_blockref(block.name,(0,0))
    builder=SheetBuilder(ezdxf.new('R2018'),source,'Obra_TREINO_1','13_PAV')
    assert {e.dxf.text for e in builder.frame_entities}=={'Obra_TREINO_1','13_PAV','PILARES'}
    assert {e.dxf.text for e in block}=={'PARAISO','1º PAVIMENTO','LATERAL DE VIGAS'}


def test_level_headers_format_absolute_metres_and_height_centimetres():
    source=ezdxf.new('R2018')
    source.modelspace().add_text('06',dxfattribs={'layer':'CARIMBO'})
    builder=SheetBuilder(ezdxf.new('R2018'),source)
    sheet=builder.sheet('P1')
    builder.levels(sheet,280,{'nivel_chegada_abs':852,'nivel_saida_abs':848.98})
    assert {e.dxf.text for e in sheet.modelspace().query('TEXT')}=={
        'NÍVEL DE CHEGADA: 852,00','NÍVEL DE SAÍDA: 848,98','PÉ-DIREITO: 280 cm'}


def test_cima_sizes_grow_down_from_the_same_upper_anchor():
    from src.core.n5_pillar_frames import UX, UY, UW, UH
    frame=ezdxf.new('R2018')
    frame.modelspace().add_text('06',dxfattribs={'layer':'CARIMBO'})
    builder=SheetBuilder(ezdxf.new('R2018'),frame)
    for height in (100,200):
        source=ezdxf.new('R2018')
        source.modelspace().add_line((0,0),(100,height))
        sheet=builder.sheet('P1 — Cima')
        builder.top_aligned(sheet,source,list(source.modelspace()),(UX+30,UY+30,UW-60,UH-54))
        builder.level_headers(sheet,321,{'nivel_chegada_abs':852.19,'nivel_saida_abs':848.98})
        assert builder.placements[-1]['bounds'][3]==pytest.approx(UY+UH-24)
        assert builder.placements[-1]['bounds'][1]==pytest.approx(UY+UH-24-height)
        headers=list(sheet.modelspace().query('TEXT'))
        assert [e.dxf.insert.y for e in headers]==pytest.approx([UY+UH-24-i*16 for i in range(3)])
        assert all(e.dxf.insert.x==UX+16 for e in headers)
        assert builder.sheets[-1]['level_headers'] is True


@pytest.mark.parametrize('drawing_count,overflow', [(0,0),(25,1),(50,2)])
def test_index_overflow_pushes_template_sheets_and_updates_printed_numbers(tmp_path,drawing_count,overflow):
    frame=ezdxf.new('R2018')
    frame.layers.new('CARIMBO')
    frame.modelspace().add_text('06',dxfattribs={'layer':'CARIMBO',
        'insert':(2017.803539105+1349.553261834,1429.188948938+76)})
    index=ezdxf.new('R2018')
    index.layers.new('TEXTO')
    for i,(x,y) in enumerate(INDEX_ORIGINS):
        index.modelspace().add_text(INDEX_TITLES[i],dxfattribs={'insert':(x+100,y+950)})
        if i:
            index.modelspace().add_text(f'{i+1:02d}',dxfattribs={'insert':(x+1349.553261834,y+76)})
    original_numbers=[e.dxf.text for e in index.modelspace()]
    builder=SheetBuilder(ezdxf.new('R2018'),frame)
    for i in range(drawing_count):
        builder.sheet(f'P{i+1} — Cima + ABCD')
    builder.sheet('Grades individuais',False)
    result=builder.finish(index,tmp_path)
    expected=INDEX_TITLES[:2]+['ÍNDICE — CONTINUAÇÃO']*overflow+INDEX_TITLES[2:]
    counted=[p for p in result['pages'] if p['counted']]
    assert [p['title'] for p in counted[:6+overflow]]==expected
    assert [p['page'] for p in counted]==list(range(1,len(counted)+1))
    assert [(p['page'],p['title']) for p in counted]==result['index_rows']
    assert all(p['origin']==position(p['page']) for p in counted)
    assert result['pages'][-1]['page'] is None
    for i in range(6+overflow):
        page=ezdxf.readfile(tmp_path/f'page_{i:03d}.dxf')
        numbers=[e.dxf.text for e in primitives(page.modelspace())
            if e.dxftype()=='TEXT' and abs(e.dxf.insert.y-76)<.001]
        assert numbers==[f'{i+1:02d}']
    assert [e.dxf.text for e in index.modelspace()][:len(original_numbers)]==original_numbers

@pytest.mark.parametrize('width,required',[(39.9,False),(40,False),(40.1,True),(50,True)])
def test_end_face_grade_threshold_is_strictly_above_40(width,required):
    from src.core.n5_pillar_frames import grade_requirements
    for shape in ('T','U','L','RETANGULAR'):
        rules=grade_requirements({'subtipo_pil':shape,'larg1_C':width,'larg1_D':width,'larg1_H':width})
        assert rules['C']['required']==required
        assert rules['D']['required']==required
        assert rules['H']['required']==(required if shape=='T' else True)


def test_required_grade_missing_fails_and_narrow_grade_is_excluded():
    from src.core.n5_pillar_frames import eligible_grade_groups
    groups=[{'names':['P1.A']},{'names':['P1.C']}]
    kept,audit=eligible_grade_groups(groups,{'larg1_A':100,'larg1_C':40},'P1','Para')
    assert kept==groups[:1]
    assert audit['faces'][1]['source_parts']==1
    assert audit['faces'][1]['unified_parts']==0
    with pytest.raises(ValueError,match='faltam grades.*B'):
        eligible_grade_groups(groups,{'larg1_A':100,'larg1_B':100,'larg1_C':40},'P1')

@pytest.mark.parametrize('client,expected',[(None,'NÃO INFORMADO'),('  ','NÃO INFORMADO'),('Cliente Atual','Cliente Atual')])
def test_stamp_client_and_cover_values_use_current_project(client,expected):
    frame=ezdxf.new('R2018')
    frame.modelspace().add_text('06',dxfattribs={'layer':'CARIMBO'})
    block=frame.blocks.new('STAMP')
    for text in ('ALIMONTI','PARAISO','1° PAVIMENTO'):
        block.add_text(text)
    frame.modelspace().add_blockref('STAMP',(0,0))
    builder=SheetBuilder(ezdxf.new('R2018'),frame,'Obra Atual','13_PAV',cliente=client)
    assert {e.dxf.text for e in builder.frame_entities}=={expected,'Obra Atual','13_PAV'}
    cover=ezdxf.new('R2018')
    for text in ('CAPREM','RESIDENCIAL DIAMOND',' 1° SUB - PERIFERIA - TORRE 1 - S01A','PILAR','00'):
        cover.modelspace().add_text(text)
    copies=builder.fill_stamp([e.copy() for e in cover.modelspace()])
    assert [e.dxf.text for e in copies]==[expected,'Obra Atual','13_PAV','PILARES','00']
    assert next(iter(cover.modelspace())).dxf.text=='CAPREM'


def test_index_grid_stops_before_project_stamp():
    doc=ezdxf.new('R2018')
    doc.layers.new('TEXTO')
    bottom=INDEX_ORIGINS[1][1]+256.4021360859192
    ms=doc.modelspace()
    ms.add_line((5239.43,bottom-60),(5859.41,bottom-60))
    ms.add_line((5239.43,bottom-60),(5239.43,bottom+300))
    ms.add_line((5239.43,bottom),(5859.41,bottom))
    result=SheetBuilder.index_body(doc,[e.copy() for e in ms],[('02','ÍNDICE')])
    lines=[e for e in result if e.dxftype()=='LINE']
    assert len(lines)==2
    assert all(min(e.dxf.start.y,e.dxf.end.y)>=bottom for e in lines)
    assert next(iter(ms)).dxf.start.y==bottom-60
