from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from portal.app import obra_pipeline, jobs
from portal.app.routers.jobs_routes import CadeiaObraIn
from portal.db import repository as repo


@pytest.fixture(autouse=True)
def isolated_preprocessing(monkeypatch):
    monkeypatch.setattr(obra_pipeline, 'preprocessar_pavimento', lambda *a, **k: {'status': 'complete'})


def test_discovery_matches_current_documents_and_requires_clean_towers(tmp_path, monkeypatch):
    root = tmp_path / 'Obra'
    crops = root / 'Fase-2_Triagem' / 'recortes'
    for name in ['old', 'second_R2018_ASCII_ODA', 'ninth', 'nocrop']:
        (crops / name).mkdir(parents=True)
    monkeypatch.setattr(repo, 'listar_documentos_por_obra', lambda *args: [
        dict(arquivo_nome='second.dwg', pavimento_confirmado='2_PAV'),
        dict(arquivo_nome='ninth.dxf', pavimento_sugerido='9_PAV'),
        dict(arquivo_nome='nocrop.dxf', pavimento_sugerido='10_PAV')])
    monkeypatch.setattr(obra_pipeline.torre_crop, 'listar_recortes_bruto',
                        lambda root, name: [dict(item_id='detalhes' if name == 'nocrop' else 'torre_1')])
    assert obra_pipeline.descobrir_pavimentos(None, None, dict(id='obra', local_path=str(root))) == ['2_PAV', '9_PAV']


def setup(conn, membro_id, settings):
    oid = repo.criar_obra(conn, membro_id=membro_id, nome='Universal', pasta_drive_id='folder')
    state = SimpleNamespace(settings=settings, db=conn, job_meta={})
    return repo.obter_obra(conn, oid), state, SimpleNamespace(app=SimpleNamespace(state=state))


@pytest.mark.parametrize('mode', ['INI', 'NOVA', 'MOLDE_1'])
def test_queue_freezes_options_and_deduplicates(conn, membro_id, settings, mode):
    obra, state, request = setup(conn, membro_id, settings)
    body = CadeiaObraIn(visual_mode=mode, lateral_assembly='sarrafeadas')
    result = obra_pipeline.enfileirar_cadeia(request, conn, obra, {'id':membro_id}, body, ['2_PAV','9_PAV'])
    again = obra_pipeline.enfileirar_cadeia(request, conn, obra, {'id':membro_id}, body, ['2_PAV','9_PAV'])
    assert again['job_id'] == result['job_id'] and again['reutilizado']
    saved = repo.obter_job_meta(conn, result['job_id'])
    assert saved['pavimentos'] == ['2_PAV','9_PAV']
    assert saved['visual_mode'] == mode
    assert saved['vigas_config']['comportamento_laterais_vigas'] == 'sarrafeadas'


@pytest.mark.parametrize('floors,forks', [([], 'nao'), (['2_PAV'], 'sim')])
def test_preflight_never_queues_invalid_request(conn, membro_id, settings, floors, forks):
    obra, state, request = setup(conn, membro_id, settings)
    with pytest.raises(HTTPException) as error:
        obra_pipeline.enfileirar_cadeia(request, conn, obra, {'id':membro_id}, CadeiaObraIn(fundos_garfos=forks), floors)
    assert error.value.status_code == 422
    assert conn.execute('SELECT count(*) FROM portal_jobs').fetchone()[0] == 0


@pytest.mark.parametrize('fail', [None, 'n3', 'LV'])
@pytest.mark.parametrize('selected_floor', [None, '9_PAV'])
def test_worker_order_and_failure_boundaries(conn, membro_id, settings, monkeypatch, fail, selected_floor):
    obra, state, request = setup(conn, membro_id, settings)
    result = obra_pipeline.enfileirar_cadeia(request, conn, obra, {'id':membro_id}, CadeiaObraIn(pavimento=selected_floor), ['2_PAV','9_PAV'])
    floors = [selected_floor] if selected_floor else ['2_PAV','9_PAV']
    calls = []
    def preprocess(*args):
        calls.append((args[3], 'Pré-processamento'))
        return {'status': 'complete'}
    monkeypatch.setattr(obra_pipeline, 'preprocessar_pavimento', preprocess)
    def draw(*args, **kw):
        assert args[1] == 'n3'  # Must not route through --sa-only.
        assert kw['visual_mode'] == 'INI' and kw['vigas_config']['fundos_vigas_possui_garfos'] == 'nao'
        calls.append((kw['pav'], 'SA+N3'))
        return SimpleNamespace(ok=fail != 'n3', log_tail='drawing failed', artefatos={})
    def publish(*args, **kw):
        calls.append((kw['pavimento'], kw['classe']))
        assert kw['vigas_config']['comportamento_laterais_vigas'] == 'gradeadas'
        if fail == kw['classe']:
            raise ValueError('incomplete N3')
        return {'release_id':'real-test-release', 'dxf_path':'fixture.dxf'}
    monkeypatch.setattr(obra_pipeline.pipeline_runner, 'executar_etapa', draw)
    monkeypatch.setattr(obra_pipeline.n5_release, 'liberar_n5', publish)
    job = repo.consumir_job(conn)
    jobs.processar_um_job(state, job)
    status = conn.execute('SELECT status FROM portal_jobs WHERE id=?',(result['job_id'],)).fetchone()[0]
    assert status == ('falhou' if fail else 'concluido')
    if fail == 'n3':
        assert calls == [(floors[0],'Pré-processamento'), (floors[0],'SA+N3')]
    elif fail == 'LV':
        assert calls == [(floors[0],'Pré-processamento'), (floors[0],'SA+N3'), (floors[0],'PL'), (floors[0],'LV')]
    else:
        assert calls == [(p,s) for p in floors for s in ['Pré-processamento','SA+N3','PL','LV','FV','LJ']]
        assert repo.obter_job_meta(conn, job['id'])['cadeia']['concluidos'] == len(floors) * 6


@pytest.mark.parametrize('selected_floor', ['', 'unknown', ' 9_PAV '])
def test_invalid_floor_never_expands_to_all(conn, membro_id, settings, selected_floor):
    obra, state, request = setup(conn, membro_id, settings)
    with pytest.raises(HTTPException) as exc:
        obra_pipeline.enfileirar_cadeia(request, conn, obra, {'id':membro_id},
                                      CadeiaObraIn(pavimento=selected_floor), ['2_PAV','9_PAV'])
    assert exc.value.status_code == 422
    assert conn.execute('SELECT count(*) FROM portal_jobs').fetchone()[0] == 0


def test_floor_scope_is_frozen_and_deduplication_respects_selection(conn, membro_id, settings):
    obra, state, request = setup(conn, membro_id, settings)
    available = ['2_PAV', '9_PAV']
    def queue(floor):
        return obra_pipeline.enfileirar_cadeia(request, conn, obra, {'id':membro_id},
                                             CadeiaObraIn(pavimento=floor), available)
    first, second, all_floors = queue('2_PAV'), queue('9_PAV'), queue(None)
    assert len({first['job_id'], second['job_id'], all_floors['job_id']}) == 3
    assert queue('9_PAV')['job_id'] == second['job_id']
    available.append('10_PAV')
    assert repo.obter_job_meta(conn, first['job_id'])['pavimentos'] == ['2_PAV']
    assert repo.obter_job_meta(conn, all_floors['job_id'])['pavimentos'] == ['2_PAV', '9_PAV']


def test_absent_classes_require_current_run_evidence(conn, membro_id, settings, monkeypatch, tmp_path):
    import json
    obra, state, request = setup(conn, membro_id, settings)
    manifest = tmp_path/'receipt.json'
    manifest.write_text(json.dumps({'n1_counts': {'pillars':4,'beams':0,'slabs':0}}))
    obra_pipeline.enfileirar_cadeia(request, conn, obra, {'id':membro_id}, CadeiaObraIn(), ['9_PAV'])
    monkeypatch.setattr(obra_pipeline.pipeline_runner, 'executar_etapa', lambda *a,**k:
                        SimpleNamespace(ok=True, artefatos={'production_manifest':str(manifest)}, log_tail=''))
    calls=[]
    def publish(*a,**k):
        calls.append(k['classe'])
        return {'release_id':'fixture','dxf_path':'fixture.dxf'}
    monkeypatch.setattr(obra_pipeline.n5_release, 'liberar_n5', publish)
    job=repo.consumir_job(conn); jobs.processar_um_job(state, job)
    assert calls == ['PL']
    receipt=repo.obter_job_meta(conn, job['id'])['cadeia']
    assert receipt['concluidos']==6
    assert sum(x.get('status')=='sem_itens' for x in receipt['recibos'])==3


def test_triage_must_finish_before_queueing(conn, membro_id, settings):
    obra, state, request = setup(conn, membro_id, settings)
    pending=repo.enfileirar_job(conn, obra_id=obra['id'])
    repo.salvar_job_meta(conn,pending,{'etapa':'recortes'})
    with pytest.raises(HTTPException) as exc:
        obra_pipeline.enfileirar_cadeia(request,conn,obra,{'id':membro_id},CadeiaObraIn(),['9_PAV'])
    assert exc.value.status_code==409
    assert conn.execute('SELECT count(*) FROM portal_jobs').fetchone()[0]==1


def test_cancel_at_boundary_does_not_overwrite_cancellation(conn, membro_id, settings, monkeypatch):
    obra, state, request = setup(conn, membro_id, settings)
    result=obra_pipeline.enfileirar_cadeia(request,conn,obra,{'id':membro_id},CadeiaObraIn(),['9_PAV'])
    def draw(*a,**k):
        conn.execute("UPDATE portal_jobs SET status='cancelado' WHERE id=?",(result['job_id'],));conn.commit()
        return SimpleNamespace(ok=True,artefatos={},log_tail='')
    monkeypatch.setattr(obra_pipeline.pipeline_runner,'executar_etapa',draw)
    monkeypatch.setattr(obra_pipeline.n5_release,'liberar_n5',lambda *a,**k:pytest.fail('Do not publish after cancellation'))
    job=repo.consumir_job(conn);jobs.processar_um_job(state,job)
    assert conn.execute('SELECT status FROM portal_jobs WHERE id=?',(job['id'],)).fetchone()[0]=='cancelado'


def test_confirmed_new_document_still_requires_triage_and_existing_tower_is_not_repeated(tmp_path, monkeypatch):
    root=tmp_path/'obra'
    (root/'Fase-2_Triagem/recortes/existing_R2018_ASCII_ODA').mkdir(parents=True)
    monkeypatch.setattr(obra_pipeline.torre_crop,'listar_recortes_bruto',lambda *a:[{'item_id':'torre_1'}])
    docs=[dict(arquivo_nome=n+'.DXF',status='classificado',tipo_documento_confirmado='Bruto',pavimento_confirmado='CUSTOM')
          for n in ['existing','new']]
    docs.append(dict(arquivo_nome='notes.pdf',status='classificado',classe_confirmada='PDF'))
    result=obra_pipeline.documentos_para_triagem(None,{'local_path':str(root)},docs)
    assert result==[docs[1]]


def test_preprocess_failure_stops_before_drawing(conn, membro_id, settings, monkeypatch):
    obra,state,request=setup(conn,membro_id,settings)
    queued=obra_pipeline.enfileirar_cadeia(request,conn,obra,{'id':membro_id},CadeiaObraIn(),['new'])
    monkeypatch.setattr(obra_pipeline,'preprocessar_pavimento',lambda *a,**k:{'status':'failed'})
    monkeypatch.setattr(obra_pipeline.pipeline_runner,'executar_etapa',lambda *a,**k:pytest.fail('SA must wait for preprocessing'))
    job=repo.consumir_job(conn);jobs.processar_um_job(state,job)
    assert conn.execute('SELECT status FROM portal_jobs WHERE id=?',(queued['job_id'],)).fetchone()[0]=='falhou'
