import ezdxf
from portal.app.crop_islands import classify_island, ensure_detail_islands


def test_shoring_levels_are_not_floor_altitudes():
    texts=[{'text':f'NIVEL {n} - COMPLETO','pos':[0,n*100],'height':10} for n in range(5)]
    assert classify_island(texts)[0]=='outros'


def test_floor_elevation_and_pillar_legend_are_distinct():
    texts=[]
    for n in range(1,4):
        texts.extend([{'text':f'{n}º PAVIMENTO','pos':[0,n*100],'height':10},
                      {'text':f'{n*3},00','pos':[100,n*100],'height':10}])
    assert classify_island(texts)[0]=='convencao_niveis'
    assert classify_island([{'text':t,'pos':[0,0]} for t in ('PILAR NASCE','PILAR CONTINUA')])[0]=='convencao_pilares'


def test_island_backfill_preserves_source_existing_tower_and_idempotency(tmp_path):
    source=tmp_path/'raw.dxf'; doc=ezdxf.new()
    for n in range(1,4):
        doc.modelspace().add_text(f'{n} PAVIMENTO',dxfattribs={'insert':(10,n*100),'height':10})
        doc.modelspace().add_text(f'{n*3},00',dxfattribs={'insert':(100,n*100),'height':10})
    doc.saveas(source); original=source.read_bytes()
    out=tmp_path/'crops';out.mkdir(); tower=out/'torre_1.dxf';tower.write_bytes(b'manual')
    regions={'detalhes':[{'bbox':[0,0,200,400]}]}
    result=ensure_detail_islands(source,out,regions)
    assert len(result['islands'])==1
    assert result['islands'][0]['kind']=='convencao_niveis'
    cropped=out/result['islands'][0]['file']; preserved=cropped.read_bytes()
    assert ensure_detail_islands(source,out,regions)==result
    assert cropped.read_bytes()==preserved and tower.read_bytes()==b'manual'
    assert source.read_bytes()==original


def test_partial_manifest_retries_missing_island(tmp_path):
    import json
    import hashlib
    source=tmp_path/'raw.dxf'; doc=ezdxf.new(); doc.modelspace().add_line((0,0),(100,0)); doc.saveas(source)
    out=tmp_path/'crops';out.mkdir()
    (out/'islands.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'islands':[], 'errors':[{'reason':'interrupted'}]}))
    result=ensure_detail_islands(source,out,{'detalhes':[{'bbox':[0,-1,101,1]}]})
    assert len(result['islands'])==1 and not result['errors']
