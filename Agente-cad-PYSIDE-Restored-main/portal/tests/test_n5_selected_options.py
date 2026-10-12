from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from portal.app.routers import jobs_routes


@pytest.mark.parametrize('classe', ['FV', 'ALL'])
def test_unification_cannot_publish_without_selected_fork_geometry(monkeypatch, classe):
    monkeypatch.setattr(jobs_routes, '_obra_do_membro', lambda *args: {'id':'obra'})
    monkeypatch.setattr(jobs_routes.repo, 'obter_config_vigas_pavimento',
                        lambda *args: {'fundos_vigas_possui_garfos':'sim'})
    def publish(*args, **kwargs):
        pytest.fail('A selected unsupported configuration must not publish N5')
    monkeypatch.setattr(jobs_routes.n5_release, 'liberar_n5', publish)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=None)))
    body = jobs_routes.N5In(classe=classe,pavimento='PAV',visual_mode='INI')
    with pytest.raises(HTTPException) as error:
        jobs_routes.n5('obra',body,request,{'id':'owner'},None)
    assert error.value.status_code == 422
    assert 'garfos' in error.value.detail


@pytest.mark.parametrize('classe', ['PL', 'LV', 'FV', 'LJ', 'ALL'])
def test_unification_human_review_is_optional(monkeypatch, classe):
    monkeypatch.setattr(jobs_routes, '_obra_do_membro', lambda *args: {'id': 'obra'})
    monkeypatch.setattr(jobs_routes.repo, 'obter_config_vigas_pavimento', lambda *args: {})
    monkeypatch.setattr(jobs_routes.repo, 'obter_validacao_classe',
                        lambda *args: {'validado': False})
    monkeypatch.setattr(jobs_routes.pipeline_runner, 'engine_version', lambda *args: 'test')
    published = []
    def publish(*args, **kwargs):
        published.append(kwargs['classe'])
        return {'ok': True, 'classe': kwargs['classe']}
    monkeypatch.setattr(jobs_routes.n5_release, 'liberar_n5', publish)
    settings = SimpleNamespace(repo_root='unused')
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))
    body = jobs_routes.N5In(classe=classe, pavimento='PAV', visual_mode='INI')
    result = jobs_routes.n5('obra', body, request, {'id': 'member', 'papel': 'membro'}, None)
    assert published == (['PL', 'LV', 'FV', 'LJ'] if classe == 'ALL' else [classe])
    assert result['ok']


@pytest.mark.parametrize('classe', ['PL', 'ALL'])
def test_unification_incomplete_n3_still_blocks(monkeypatch, classe):
    monkeypatch.setattr(jobs_routes, '_obra_do_membro', lambda *args: {'id': 'obra'})
    monkeypatch.setattr(jobs_routes.repo, 'obter_config_vigas_pavimento', lambda *args: {})
    monkeypatch.setattr(jobs_routes.repo, 'obter_validacao_classe', lambda *args: {'validado': False})
    monkeypatch.setattr(jobs_routes.pipeline_runner, 'engine_version', lambda *args: 'test')
    def incomplete(*args, **kwargs):
        raise ValueError('N3 incompleto: item ausente')
    monkeypatch.setattr(jobs_routes.n5_release, 'liberar_n5', incomplete)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(repo_root='unused'))))
    with pytest.raises(HTTPException) as error:
        jobs_routes.n5('obra', jobs_routes.N5In(classe=classe, pavimento='PAV', visual_mode='INI'),
                       request, {'id': 'member'}, None)
    assert error.value.status_code == (409 if classe == 'ALL' else 422)
    assert 'N3' in str(error.value.detail)


def test_motor_sequence_generates_all_n5_without_human_review(conn, membro_id, settings, monkeypatch):
    from portal.app import jobs
    from portal.db import repository as repo
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome='Test', pasta_drive_id='folder')
    job_id = repo.enfileirar_job(conn, obra_id=obra_id)
    meta = {'etapa': 'motores', 'cascade_n5': True, 'pav': 'PAV', 'visual_mode': 'INI', 'membro_id': membro_id}
    repo.salvar_job_meta(conn, job_id, meta)
    job = repo.consumir_job(conn)
    state = SimpleNamespace(settings=settings, db=conn, job_meta={job_id: meta})
    monkeypatch.setattr(jobs.pipeline_runner, 'executar_etapa',
                        lambda *args, **kwargs: SimpleNamespace(ok=True, artefatos={}, log_tail=''))
    published = []
    monkeypatch.setattr(jobs.n5_release, 'liberar_n5', lambda *args, **kwargs: published.append(kwargs['classe']))
    jobs.processar_um_job(state, job)
    assert published == ['PL', 'LV', 'FV', 'LJ']
    assert conn.execute('SELECT status FROM portal_jobs WHERE id=?', (job_id,)).fetchone()[0] == 'concluido'
