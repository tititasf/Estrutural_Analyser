import io
import hashlib
import ezdxf
import pytest
from portal.app import drawing_frame, example_crops
from portal.tests.test_portal_admin_visibility import _app_cliente, _login


def uploaded(tmp_path, monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG', str(tmp_path / 'drawing.json'))
    doc = ezdxf.new()
    doc.layers.new('CUSTOM', dxfattribs={'color': 3, 'linetype': 'DASHED'})
    doc.blocks.new('EMPTY')
    doc.modelspace().add_blockref('EMPTY', (0, 0))
    block = doc.blocks.new('REFERENCE')
    block.add_circle((0, 0), 5)
    doc.modelspace().add_blockref('REFERENCE', (20, 20), dxfattribs={'layer': 'CUSTOM'})
    doc.modelspace().add_line((80, 80), (100, 100))
    text = io.StringIO(); doc.write(text)
    item = drawing_frame.add_example('NOVA', 'PL', 'original.dxf', text.getvalue().encode())[0]
    return item


def rectangle(mapping, bounds):
    x0,y0,x1,y1 = mapping['bbox_dxf']
    a,b,c,d = bounds
    return [(a-x0)/(x1-x0), (y1-d)/(y1-y0), (c-x0)/(x1-x0), (y1-b)/(y1-y0)]


def test_crop_preserves_blocks_style_source_and_isolation(tmp_path, monkeypatch):
    item = uploaded(tmp_path, monkeypatch)
    root = example_crops.root_for('NOVA', 'PL', item['id'])
    original = root.parent / (item['id'] + '.dxf')
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    mapping = example_crops.source('NOVA', 'PL', item['id'])
    area = rectangle(mapping, (10,10,30,30))
    crop = example_crops.create('NOVA', 'PL', item['id'], 'CIMA', 'Cima teste', [area])
    result = ezdxf.readfile(root / (crop['id'] + '.dxf'))
    assert len(result.modelspace()) == 1
    assert result.modelspace()[0].dxftype() == 'INSERT'
    assert result.blocks.get('REFERENCE') is not None
    assert result.layers.get('CUSTOM').dxf.color == 3
    assert result.layers.get('CUSTOM').dxf.linetype == 'DASHED'
    assert hashlib.sha256(original.read_bytes()).hexdigest() == digest
    assert example_crops.crop_path('NOVA', 'PL', item['id'], crop['id']).exists()
    with pytest.raises(ValueError): example_crops.listing('INI', 'PL', item['id'])
    with pytest.raises(ValueError): example_crops.create('NOVA', 'PL', item['id'], 'FUNDOS', '', [area])
    with pytest.raises(ValueError): example_crops.create('NOVA', 'PL', item['id'], 'CIMA', '', [[0,0,float('nan'),1]])
    assert example_crops.remove('NOVA', 'PL', item['id'], crop['id']) == []
    assert original.exists()


@pytest.mark.asyncio
async def test_crop_api_auth_types_persistence(settings, tmp_path, monkeypatch):
    item = uploaded(tmp_path, monkeypatch)
    url = '/app/configuracao-modos/NOVA/PL/exemplos/' + item['id'] + '/recortes'
    async with _app_cliente(settings) as (_, client):
        assert (await client.get(url)).status_code == 401
        await _login(client, 'ana', 'segredo123')
        assert (await client.get(url)).json()['types'] == example_crops.TYPES['PL']
        body = {'kind':'ABCD', 'name':'Painéis', 'rectangles':[[0,0,1,1]]}
        assert (await client.post(url, json=body)).status_code == 403
        await _login(client, 'chefe', 'segredosuper')
        response = await client.post(url, json=body)
        assert response.status_code == 200, response.text
        token = response.json()['crop']['id']
        assert len((await client.get(url)).json()['crops']) == 1
        assert '<svg' in (await client.get(url+'/'+token+'/preview')).text
        assert (await client.post(url, json={**body,'kind':'INVALID'})).status_code == 422
        assert (await client.delete(url+'/'+token)).json()['crops'] == []
        assert (await client.get(url+'/'+token+'/preview')).status_code == 422
