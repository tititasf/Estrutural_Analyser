from copy import deepcopy
import io
import ezdxf
import pytest
from portal.tests.test_portal_admin_visibility import _app_cliente, _login


@pytest.mark.asyncio
async def test_auth_save_validation_and_concurrency(settings, tmp_path, monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG', str(tmp_path / 'drawing.json'))
    url = '/app/configuracao-modos'
    async with _app_cliente(settings) as (_, client):
        assert (await client.get(url)).status_code == 401
        await _login(client, 'ana', 'segredo123')
        member = await client.get(url)
        assert member.status_code == 200
        assert not member.json()['can_edit']
        settings_body = member.json()['modes']['NOVA']['LV_PARA']
        body = {'revision': 0, 'settings': settings_body}
        assert (await client.put(url + '/NOVA/LV_PARA', json=body)).status_code == 403
        await _login(client, 'chefe', 'segredosuper')
        settings_body['appearance']['text_scale'] = 1.5
        saved = await client.put(url + '/NOVA/LV_PARA', json=body)
        assert saved.status_code == 200, saved.text
        assert saved.json()['revision'] == 1
        assert (await client.put(url + '/NOVA/LV_PARA', json=body)).status_code == 409
        reread = (await client.get(url)).json()
        assert reread['modes']['NOVA']['LV_PARA']['appearance']['text_scale'] == 1.5
        assert reread['modes']['NOVA']['LV_PASSA']['appearance']['text_scale'] == 1
        body['revision'] = 1
        settings_body['appearance']['text_scale'] = -1
        assert (await client.put(url + '/NOVA/LV_PARA', json=body)).status_code == 422


@pytest.mark.asyncio
async def test_frame_upload_render_isolation_and_invalid_preserves_previous(settings, tmp_path, monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG', str(tmp_path / 'drawing.json'))
    doc = ezdxf.new()
    doc.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 70), (0, 70)], close=True)
    text = io.StringIO()
    doc.write(text)
    content = text.getvalue().encode('utf8')
    url = '/app/configuracao-modos/NOVA/LV_PARA/moldura'
    async with _app_cliente(settings) as (_, client):
        assert (await client.get(url)).status_code == 401
        await _login(client, 'ana', 'segredo123')
        assert (await client.post(url, files={'arquivo': ('frame.dxf', content)})).status_code == 403
        await _login(client, 'chefe', 'segredosuper')
        assert (await client.get(url)).json()['frame'] is None
        assert (await client.post(url, files={'arquivo': ('frame.txt', content)})).status_code == 422
        saved = await client.post(url, files={'arquivo': ('frame.dxf', content)})
        assert saved.status_code == 200, saved.text
        frame = saved.json()['frame']
        preview = await client.get(url + '/' + frame['id'] + '/preview')
        assert preview.status_code == 200 and '<svg' in preview.text
        assert (await client.get(url.replace('LV_PARA', 'LV_PASSA'))).json()['frame'] is None
        assert (await client.get(url.replace('NOVA', 'INI'))).json()['frame'] is None
        assert (await client.post(url, files={'arquivo': ('bad.dxf', b'invalid')})).status_code == 422
        assert (await client.get(url)).json()['frame'] == frame
        assert (await client.get(url.replace('NOVA', 'INVALID'))).status_code == 422
        monkeypatch.setattr('portal.app.drawing_frame.MAX_BYTES', 100)
        assert (await client.post(url, files={'arquivo': ('big.dxf', content)})).status_code == 422
        assert (await client.get('/app/configuracao-modos')).json()['revision'] == 0


@pytest.mark.asyncio
async def test_examples_limit_isolation_preview_and_removal(settings,tmp_path,monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG',str(tmp_path/'drawing.json'))
    doc=ezdxf.new();doc.modelspace().add_line((0,0),(10,20))
    stream=io.StringIO();doc.write(stream);content=stream.getvalue().encode()
    url='/app/configuracao-modos/MOLDE_1/PL/exemplos'
    async with _app_cliente(settings) as (_,client):
        assert (await client.get(url)).status_code==401
        await _login(client,'ana','segredo123')
        assert (await client.post(url,files={'arquivo':('a.dxf',content)})).status_code==403
        await _login(client,'chefe','segredosuper')
        for i in range(10):
            response=await client.post(url,files={'arquivo':(f'exemplo{i+1}.dxf',content)})
            assert response.status_code==200,response.text
        listing=response.json()['examples']
        assert len(listing)==10
        assert (await client.post(url,files={'arquivo':('overflow.dxf',content)})).status_code==422
        token=listing[0]['id']
        assert '<svg' in (await client.get(url+'/'+token+'/preview')).text
        assert not (await client.get(url.replace('MOLDE_1','MOLDE_2'))).json()['examples']
        assert not (await client.get(url.replace('/PL/','/FV/'))).json()['examples']
        assert len((await client.delete(url+'/'+token)).json()['examples'])==9
        assert (await client.post(url,files={'arquivo':('replacement.dxf',content)})).status_code==200

@pytest.mark.asyncio
@pytest.mark.parametrize('segment', ['moldura', 'indices-legendas'])
async def test_document_tabs_append_preview_and_selected_removal(settings,tmp_path,monkeypatch,segment):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG',str(tmp_path/'drawing.json'))
    doc=ezdxf.new();doc.modelspace().add_line((0,0),(10,20))
    stream=io.StringIO();doc.write(stream);content=stream.getvalue().encode()
    url='/app/configuracao-modos/MOLDE_1/PL/'+segment
    async with _app_cliente(settings) as (_,client):
        await _login(client,'chefe','segredosuper')
        a=(await client.post(url,files={'arquivo':('a.dxf',content)})).json()['frame']
        response=await client.post(url,files={'arquivo':('b.dxf',content)})
        assert response.status_code==200,response.text
        b=response.json()['frame']
        assert response.json()['documents']==[a,b]
        assert (await client.get(url)).json()['documents']==[a,b]
        for item in [a,b]:
            assert '<svg' in (await client.get(url+'/'+item['id']+'/preview')).text
        other='indices-legendas' if segment=='moldura' else 'moldura'
        assert (await client.get(url.rsplit('/',1)[0]+'/'+other)).json()['documents']==[]
        removed=await client.delete(url+'/'+a['id'])
        assert removed.json()=={'frame':b,'documents':[b]}
        assert (await client.delete(url+'/'+b['id'])).json()=={'frame':None,'documents':[]}
