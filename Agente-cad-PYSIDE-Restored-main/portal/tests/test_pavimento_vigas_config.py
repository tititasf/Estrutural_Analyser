import json
from copy import deepcopy

import pytest

from portal.db import repository as repo
from portal.tests.test_portal_http_flow import _app_cliente, _obra_da_ana
from src.core.vigas_drawing_config import apply_lv_config, apply_fv_config


@pytest.mark.asyncio
async def test_opcoes_por_pavimento_snapshot_n3_e_motores(settings):
    async with _app_cliente(settings) as (app, client):
        obra_id = _obra_da_ana(settings)
        await client.post('/login', json={'login': 'ana', 'senha': 'segredo123'})
        base = f'/obras/{obra_id}/pavimentos/vigas-config'
        original = (await client.get(base, params={'pavimento': '13_PAV'})).json()
        assert original['comportamento_laterais_vigas'] == 'sarrafeadas'
        assert original['fundos_vigas_possui_garfos'] == 'nao'
        chosen = dict(comportamento_laterais_vigas='gradeadas', fundos_vigas_possui_garfos='sim')
        assert (await client.put(base, params={'pavimento':'13_PAV'}, json=chosen)).status_code == 200
        other = (await client.get(base, params={'pavimento':'14_PAV'})).json()
        assert other['comportamento_laterais_vigas'] == 'sarrafeadas'
        for endpoint, sections in [('n3',['laterais_viga'])]:
            response = await client.post(f'/obras/{obra_id}/{endpoint}', json={'pav':'13_PAV', 'secao':sections})
            assert response.status_code == 200, response.text
            assert response.json()['meta']['vigas_config'] == chosen
            frozen = response.json()['job_id']
        assert (await client.post(f'/obras/{obra_id}/n3', json={'pav':'13_PAV', 'secao':['fundos_viga']})).status_code == 422
        await client.put(base, params={'pavimento':'13_PAV'}, json={**chosen, 'fundos_vigas_possui_garfos':'nao'})
        assert app.state.job_meta[frozen]['vigas_config']['fundos_vigas_possui_garfos'] == 'sim'
        for endpoint, sections in [('n3',['fundos_viga']),('motores',[])]:
            result = await client.post(f'/obras/{obra_id}/{endpoint}', json={'pav':'13_PAV','secao':sections})
            assert result.status_code == 200, result.text
            assert result.json()['meta']['vigas_config'] == {**chosen,'fundos_vigas_possui_garfos':'nao'}
        assert (await client.put(base, params={'pavimento':'13_PAV'}, json={**chosen, 'fundos_vigas_possui_garfos':''})).status_code == 422
        assert (await client.get(base, params={'pavimento':''})).status_code == 422
        html = (await client.get(f'/app/obras/{obra_id}')).text
        assert 'name="comportamento_laterais_vigas"' not in html
        assert 'name="fundos_vigas_possui_garfos"' not in html


def test_converter_so_copia_contrato_e_envia_grade_e_garfos():
    original = {'panels':[{'height1':54.0,'height2':0,'panel_type':'Sarrafeado'}]}
    saved = deepcopy(original)
    config = dict(comportamento_laterais_vigas='gradeadas',fundos_vigas_possui_garfos='sim')
    grade = apply_lv_config(original, config)
    assert grade['panels'][0]['panel_type'] == 'Grade'
    assert grade['panels'][0]['grade_h1'] == 54.0
    assert grade['panels'][0]['grade_h2'] == 0.0
    assert apply_lv_config(grade)['panels'][0]['panel_type'] == 'Sarrafeado'
    assert apply_fv_config(original, config)['possui_garfos'] is True
    assert apply_fv_config(original)['possui_garfos'] is False
    assert original == saved


def test_comando_headless_recebe_snapshot(settings):
    from portal.app.pipeline_runner import montar_comando_headless
    config = dict(comportamento_laterais_vigas='gradeadas',fundos_vigas_possui_garfos='nao')
    cmd = montar_comando_headless(settings, {'nome':'Teste'}, pav='13_PAV', vigas_config=config)
    assert json.loads(cmd[cmd.index('--vigas-config-json')+1]) == config
    assert '--wait' in cmd


@pytest.mark.asyncio
async def test_cinco_modos_snapshot_para_todas_as_classes(settings):
    async with _app_cliente(settings) as (app, client):
        obra_id = _obra_da_ana(settings)
        await client.post('/login', json={'login':'ana','senha':'segredo123'})
        cases = [('pilares','pilares'),('lajes','lajes'),('fundo','fundos_viga'),
                 ('laterais_para','laterais_viga'),('laterais_passa','laterais_viga')]
        for mode in ('INI','NOVA','MOLDE_1','MOLDE_2','MOLDE_3'):
            for classe, section in cases:
                response = await client.post(f'/obras/{obra_id}/n3', json={
                    'pav':'13_PAV','secao':[section],'classe_ui':classe,'visual_mode':mode})
                assert response.status_code == 200, response.text
                assert response.json()['meta']['visual_mode'] == mode
                assert app.state.job_meta[response.json()['job_id']]['visual_mode'] == mode
            for endpoint in ('n3','motores'):
                response = await client.post(f'/obras/{obra_id}/{endpoint}',
                    json={'pav':'13_PAV','visual_mode':mode})
                assert response.status_code == 200, response.text
                assert response.json()['meta']['visual_mode'] == mode
        bad = await client.post(f'/obras/{obra_id}/n3',json={'pav':'13_PAV','visual_mode':'invalid'})
        assert bad.status_code == 422


@pytest.mark.asyncio
async def test_modo_desenho_persiste_por_pavimento_e_classe(settings):
    async with _app_cliente(settings) as (_app, client):
        obra_id = _obra_da_ana(settings)
        await client.post('/login', json={'login':'ana','senha':'segredo123'})
        base = f'/obras/{obra_id}/pavimentos/modo-desenho-config'
        params = {'pavimento': '13_PAV', 'classe_ui': 'laterais_para'}
        assert (await client.get(base, params=params)).json()['visual_mode'] == 'NOVA'
        saved = await client.put(base, params=params, json={'visual_mode': 'MOLDE_1'})
        assert saved.status_code == 200
        assert saved.json()['visual_mode'] == 'MOLDE_1'
        assert (await client.get(base, params=params)).json()['visual_mode'] == 'MOLDE_1'
        assert (await client.get(base, params={**params, 'classe_ui': 'laterais_passa'})).json()['visual_mode'] == 'NOVA'
        assert (await client.get(base, params={**params, 'pavimento': '14_PAV'})).json()['visual_mode'] == 'NOVA'
        assert (await client.get(base, params={**params, 'classe_ui': 'invalida'})).status_code == 422
