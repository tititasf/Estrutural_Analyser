import json
import hashlib
from pathlib import Path

import ezdxf
import pytest

from src.core.n5_beam_frames import segment_entities, assemble_beam_frames
from src.core.n5_assembler import _production_fv_ids, n3_mode_readiness


def source(tmp_path, name, widths):
    path=tmp_path/'n3'/'dxf'/f'FV_preview_{name}.dxf'
    path.parent.mkdir(parents=True,exist_ok=True)
    contract=path.parent.parent/'contracts'/f'{name}_fundo.json'
    contract.parent.mkdir(exist_ok=True)
    doc=ezdxf.new('R2018');x=0;panels=[]
    for n,w in enumerate(widths):
        doc.modelspace().add_lwpolyline([(x,0),(x+w,0),(x+w,-20),(x,-20)],close=True)
        dim=doc.modelspace().add_linear_dim(base=(x,-40),p1=(x,0),p2=(x+w,0));dim.render()
        panels.append(dict(total_width=w,texto_esq=f'P{n}',texto_dir=f'P{n+1}'))
        x+=w+15
    doc.saveas(path)
    contract.write_text(json.dumps(dict(name=name,side='C',panels=panels)))
    return name,path


def test_partition_preserves_every_geometry_entity_and_uses_rendered_width(tmp_path):
    _,p=source(tmp_path,'V1',[300,200])
    contract=json.loads((p.parent.parent/'contracts/V1_fundo.json').read_text())
    contract['panels'][0]['comprimento_total_fundo']=280
    doc=ezdxf.readfile(p)
    groups,excluded=segment_entities(doc,contract)
    assert [span for _,span,_ in groups]==[(0,300),(315,515)]
    assert sum(len(e) for _,_,e in groups)==len(doc.modelspace())
    assert not excluded


def test_missing_dimension_fails_instead_of_clipping(tmp_path):
    _,p=source(tmp_path,'V1',[300])
    contract={'name':'V1','panels':[{'total_width':400}]}
    with pytest.raises(ValueError,match='sem cota'):
        segment_entities(ezdxf.readfile(p),contract)


def test_fv_inventory_keeps_contract_without_preview_and_separates_modes(tmp_path):
    obra=tmp_path/'obra'
    run=obra/'Fase-6_Execucao_CAD/production_sa/13_PAV/run'
    source(run,'V1',[300])
    (run/'n3/contracts/V2_fundo.json').write_text('{}')
    (run/'production_manifest.json').write_text('{"visual_mode":"NOVA"}')
    assert _production_fv_ids(obra,'13_PAV','NOVA')==['V1','V2']
    assert _production_fv_ids(obra,'13_PAV','INI')==[]
    assert n3_mode_readiness(obra,'FV','13_PAV','NOVA')['missing']==['V2']


def test_wrap_repeats_endpoints_continuation_and_allows_new_beam_on_same_row(tmp_path):
    root=Path(__file__).resolve().parents[1]/'scripts/arete/relatorios/20261002_nova_design'
    frame=root/'moldura_NOVA_aprovada.dxf';index=root/'INDICE_NOVA_original.dxf'
    assert frame.is_file() and index.is_file()
    sources=[source(tmp_path,'V1',[900,900,100]),source(tmp_path,'V2',[100])]
    hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for _,p in sources]
    result=assemble_beam_frames(ezdxf.new('R2018'),sources,frame_path=frame,index_path=index)
    a,b,c,d=result['segments']
    assert a['row']<b['row']==c['row']==d['row']
    assert b['name']=='Cont. V1.C' and d['name']=='V2.C'
    assert a['final']==b['initial']=='P1'
    assert all(v['scale']==1 for v in result['placements'])
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for _,p in sources]==hashes
    assert [p['page'] for p in result['pages']]==list(range(1,len(result['pages'])+1))


def test_wrap_preserves_native_endpoint_color_height_and_relative_y(tmp_path):
    from ezdxf.enums import TextEntityAlignment
    root=Path(__file__).resolve().parents[1]/'scripts/arete/relatorios/20261002_nova_design'
    item,path=source(tmp_path,'V300',[900,900])
    doc=ezdxf.readfile(path);doc.layers.new('5',dxfattribs={'color':5})
    doc.layers.new('NOMENCLATURA',dxfattribs={'color':7})
    doc.modelspace().add_text('V300.C',dxfattribs={'height':12,'layer':'NOMENCLATURA'}).set_placement((3,9))
    doc.modelspace().add_text('P0',dxfattribs={'height':12,'layer':'5'}).set_placement((-10,-89),align=TextEntityAlignment.RIGHT)
    for x,label in [(905,'P1'),(1820,'P2')]:
        doc.modelspace().add_text(label,dxfattribs={'height':12,'layer':'5'}).set_placement((x,-89))
    doc.saveas(path);dst=ezdxf.new('R2018')
    result=assemble_beam_frames(dst,[(item,path)],frame_path=root/'moldura_NOVA_aprovada.dxf',index_path=root/'INDICE_NOVA_original.dxf')
    assert result['segments'][1]['name']=='Cont. V300.C'
    endpoints=[e for e in dst.modelspace().query('TEXT') if e.dxf.layer=='5']
    assert sorted(e.dxf.text for e in endpoints)==['P0','P1','P1','P2']
    assert all(e.dxf.height==12 and e.dxf.color==256 for e in endpoints)
    assert dst.layers.get('5').dxf.color==5
    assert not dst.modelspace().query('INSERT')
