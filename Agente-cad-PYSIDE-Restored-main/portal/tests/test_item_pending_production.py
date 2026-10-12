import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from src.core import n5_assembler
from portal.app import pipeline_runner, n5_release


def test_failed_current_item_never_reuses_old_preview(tmp_path):
    root=tmp_path/'Fase-6_Execucao_CAD'
    for run,failed in [('20260101',[]),('20260102',['P10_para'])]:
        folder=root/'production_sa'/'floor'/run
        (folder/'n3'/'dxf').mkdir(parents=True)
        (folder/'production_manifest.json').write_text(json.dumps(dict(visual_mode='INI',n3={'pl_failed':failed})))
    legacy=root/'n3_modes'/'INI'/'pilares'
    for path in n5_assembler._pillar_preview_paths(legacy,'P10'):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text('stale')
    assert n5_assembler._find_n3_previews(tmp_path,'PL','P10','floor','INI') == []
    assert not n5_assembler._current_n3_failure(tmp_path,'PL','P1','floor','INI')


@pytest.mark.parametrize('module,mode',[('lv_ini_packer','INI'),('lv_formascia_packer','MOLDE_1'),('n5_lateral_frames','NOVA')])
def test_missing_beam_is_isolated_and_does_not_use_old_round(tmp_path, monkeypatch,module,mode):
    import importlib
    packer=importlib.import_module('src.core.'+module)
    folder=tmp_path/'run'/'n3'/'dxf';folder.mkdir(parents=True)
    contracts=folder.parent/'contracts_lv'/'LV-PARA'/'gradeadas';contracts.mkdir(parents=True)
    (contracts.parent/'V1_A.json').write_text('{}')
    monkeypatch.setattr(n5_assembler,'_production_n3_dirs',lambda *args:[folder])
    from portal.app import ficha_reader
    monkeypatch.setattr(ficha_reader,'ler_estado_pavimento',lambda *args: {'beam':True})
    monkeypatch.setattr(ficha_reader,'listar_itens_n1',lambda *args:[{'beam_name':'V1'},{'beam_name':'V2'}])
    (contracts.parent/'V2_A.json').write_text('{}')
    for side in 'AB':(contracts/f'V2_{side}.json').write_text('{}')
    from portal.app import lv_n3_panels,lv_n3_cuts,lv_ficha
    def identity(*args,**kwargs):
        tag=args[4] if isinstance(args[3],str) else args[3]['id']
        path=tmp_path/f'valid_{tag}.dxf';path.write_text('test identity')
        units=path.with_suffix('.units');units.mkdir(exist_ok=True)
        (units/'manifest.json').write_text('{}')
        return None,path,None
    monkeypatch.setattr(lv_n3_panels,'artifact_identity',identity)
    monkeypatch.setattr(lv_n3_cuts,'artifact_identity',identity)
    monkeypatch.setattr(lv_ficha,'montar_ficha_lv',lambda *args,**kw:{'cut_views':[{'id':'cut_V2'}]})
    with pytest.raises(ValueError,match='contrato A'):
        packer.published_manifests(tmp_path,'floor','gradeadas','PARA')
    pending=[]
    beams,manifests=packer.published_manifests(tmp_path,'floor','gradeadas','PARA',pending=pending)
    assert beams==['V2'] and len(manifests)==3
    assert pending[0]['item_id']=='V1' and pending[0]['status']=='missing'


def test_n5_partial_keeps_valid_items_and_names_missing(tmp_path,monkeypatch):
    from src.core import n5_tasks
    monkeypatch.setattr(n5_assembler,'n3_mode_readiness',lambda *args:dict(ready=False,total=2,missing=['L2']))
    part=n5_assembler.N5AssemblyResult('LJ','obra','floor',tmp_path/'out.dxf',tmp_path/'out.json',[
        n5_assembler.N5ItemResult('L1','current','ok','valid'),n5_assembler.N5ItemResult('L2','','missing','nível ausente')])
    def assemble(tasks):
        assert tasks[0][3]['allow_partial']
        return [('base',part)]
    monkeypatch.setattr(n5_tasks,'run_assembly_tasks',assemble)
    result=pipeline_runner.executar_n5(SimpleNamespace(sa_db_path=tmp_path/'db'),dict(local_path=str(tmp_path),nome='obra'),classe='LJ',pavimento='floor',dry_run=False)
    assert result.ok and result.artefatos['partial']
    assert result.artefatos['item_pending'][0]['item_id']=='L2'


def test_no_valid_item_has_no_release_or_empty_dxf(monkeypatch):
    monkeypatch.setattr(pipeline_runner,'executar_n5',lambda *args,**kw:SimpleNamespace(ok=False,artefatos={'item_pending':[{'item_id':'L2','message':'nível ausente'}]}))
    def forbidden(*args,**kw):pytest.fail('Empty N5 must not be released')
    monkeypatch.setattr(n5_release.repo,'registrar_n5_release',forbidden)
    result=n5_release.liberar_n5(None,None,obra={},classe='LJ',pavimento='floor',membro_id='member')
    assert result['release_id'] is None and result['dxf_path'] is None and result['status']=='pendente'


def test_all_missing_keeps_previous_published_dxf_and_manifest(tmp_path):
    output=tmp_path/'Fase-6_Execucao_CAD'/'n5';output.mkdir(parents=True)
    previous=output/'N5_LJ_floor_NOVA.dxf';previous.write_bytes(b'previous valid publication')
    previous.with_suffix('.json').write_bytes(b'previous manifest')
    result=n5_assembler.assemble_n5(tmp_path,'LJ',item_ids=['missing'],pavimento='floor',visual_mode='NOVA',allow_partial=True)
    assert result.ok_count==0 and result.missing_count==1
    assert previous.read_bytes()==b'previous valid publication'
    assert previous.with_suffix('.json').read_bytes()==b'previous manifest'
    assert result.manifest_path.name.endswith('.pending.json')


def test_chain_pending_item_does_not_stop_classes_or_next_floor(conn,membro_id,settings,tmp_path,monkeypatch):
    from portal.app import obra_pipeline
    from portal.app.routers.jobs_routes import CadeiaObraIn
    from portal.db import repository as repo
    oid=repo.criar_obra(conn,membro_id=membro_id,nome='Universal',pasta_drive_id='folder')
    obra=repo.obter_obra(conn,oid)
    state=SimpleNamespace(settings=settings,db=conn,job_meta={})
    queued=obra_pipeline.enfileirar_cadeia(SimpleNamespace(app=SimpleNamespace(state=state)),conn,obra,{'id':membro_id},CadeiaObraIn(),['floor1','floor2'])
    job=repo.consumir_job(conn)
    monkeypatch.setattr(pipeline_runner,'executar_etapa',lambda *args,**kw:SimpleNamespace(ok=True,artefatos={'item_pending':['LV/V2: nível ausente']},log_tail=''))
    called=[]
    def release(*args,**kw):
        called.append((kw['pavimento'],kw['classe']))
        return dict(release_id=None,dxf_path=None,item_pending=[dict(item_id='V2',message='nível ausente')] if kw['classe']=='LV' else [])
    monkeypatch.setattr(n5_release,'liberar_n5',release)
    monkeypatch.setattr(obra_pipeline,'preprocessar_pavimento',lambda *a,**k:{'status':'complete'})
    meta=repo.obter_job_meta(conn,queued['job_id'])
    obra_pipeline.executar_cadeia(state,conn,settings,obra,job,meta,tmp_path/'job.log')
    assert len(called)==8 and called[-1]==('floor2','LJ')
    result=repo.obter_job_meta(conn,job['id'])['cadeia']
    assert result['parcial'] and result['concluidos']==12 and len(result['pendencias'])==4
