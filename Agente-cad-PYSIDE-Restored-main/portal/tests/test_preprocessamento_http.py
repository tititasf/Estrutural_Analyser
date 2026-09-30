import pytest

from portal.app.routers import preprocessamento_routes as routes
from portal.tests.test_portal_http_flow import _app_cliente, _obra_da_ana
from portal.app.preprocessamento.sources import SourceKind, SourceRecord


@pytest.mark.asyncio
async def test_http_autorizacao_flag_fila_e_estado(settings, monkeypatch):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)
        source = SourceRecord(
            source_id='pre-src-v1:' + 'a'*64, obra_id=obra_id, pavimento_id='14_PAV',
            bruto_id='A', item_id='torre_1', kind=SourceKind.TOWER, revision='b'*64,
            relative_path='Fase-2_Triagem/recortes/A/torre_1.dxf', validated=True)
        monkeypatch.setattr(routes, 'inventory_floor_sources', lambda **kwargs: (source,))
        url = f'/obras/{obra_id}/preprocessamento'
        assert (await client.get(url, params={'pavimento':'14_PAV'})).status_code in (401, 303)
        assert (await client.post('/login', json={'login':'ana','senha':'segredo123'})).status_code == 200
        response = await client.post(url + '/jobs', json={'pavimento':'14_PAV'})
        assert response.status_code == 409
        settings.preprocess_enabled = True
        first = await client.post(url + '/jobs', json={'pavimento':'14_PAV'})
        assert first.status_code == 202
        second = await client.post(url + '/jobs', json={'pavimento':'14_PAV'})
        assert second.status_code == 202
        assert first.json()['job_id'] == second.json()['job_id']
        status = await client.get(url, params={'pavimento':'14_PAV'})
        assert status.status_code == 200
        assert status.json()['job_id'] == first.json()['job_id']
        assert status.json()['enabled'] is True
        level_list = await client.get(url + '/niveis', params={'pavimento': '14_PAV'})
        assert level_list.status_code == 200
        assert level_list.json()['status'] == 'not_started'


@pytest.mark.asyncio
async def test_http_recorte_niveis_pendente_e_opcional(settings, monkeypatch):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)
        tower = SourceRecord(
            source_id='pre-src-v1:' + 'a'*64, obra_id=obra_id, pavimento_id='14_PAV',
            bruto_id='A', item_id='torre_1', kind=SourceKind.TOWER, revision='b'*64,
            relative_path='Fase-2_Triagem/recortes/A/torre_1.dxf', validated=True)
        level = SourceRecord(
            source_id='pre-src-v1:' + 'c'*64, obra_id=obra_id, pavimento_id='14_PAV',
            bruto_id='A', item_id='convencao_niveis', kind=SourceKind.LEVEL_CONVENTION,
            revision='d'*64, relative_path='Fase-2_Triagem/recortes/A/convencao_niveis.dxf',
            validated=False)
        monkeypatch.setattr(routes, 'inventory_floor_sources', lambda **kwargs: (tower, level))
        assert (await client.post('/login', json={'login':'ana','senha':'segredo123'})).status_code == 200
        settings.preprocess_enabled = True
        response = await client.post(f'/obras/{obra_id}/preprocessamento/jobs',
                                     json={'pavimento':'14_PAV'})
        assert response.status_code == 202
        assert response.json()['source_count'] == 2
