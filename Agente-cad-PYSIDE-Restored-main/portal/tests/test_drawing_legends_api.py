"""Aba "Índices e Legendas": mesmo comportamento da Moldura, guardada à parte (dono 2026-10-03)."""
import io

import ezdxf
import pytest

from portal.tests.test_portal_admin_visibility import _app_cliente, _login


def _dxf():
    doc = ezdxf.new()
    doc.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 70), (0, 70)], close=True)
    text = io.StringIO()
    doc.write(text)
    return text.getvalue().encode('utf8')


@pytest.mark.asyncio
async def test_indices_legendas_isolado_da_moldura(settings, tmp_path, monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG', str(tmp_path / 'drawing.json'))
    base = '/app/configuracao-modos/NOVA/PL'
    url = base + '/indices-legendas'
    async with _app_cliente(settings) as (_, client):
        assert (await client.get(url)).status_code == 401
        await _login(client, 'ana', 'segredo123')
        assert (await client.post(url, files={'arquivo': ('leg.dxf', _dxf())})).status_code == 403
        await _login(client, 'chefe', 'segredosuper')
        assert (await client.get(url)).json()['frame'] is None
        saved = await client.post(url, files={'arquivo': ('leg.dxf', _dxf())})
        assert saved.status_code == 200, saved.text
        doc = saved.json()['frame']
        preview = await client.get(url + '/' + doc['id'] + '/preview')
        assert preview.status_code == 200 and '<svg' in preview.text
        # coleção própria: não vira moldura, nem vaza para outro modo/classe
        assert (await client.get(base + '/moldura')).json()['frame'] is None
        assert (await client.get(base + '/moldura/' + doc['id'] + '/preview')).status_code == 404
        assert (await client.get(url.replace('NOVA', 'INI'))).json()['frame'] is None
        assert (await client.get(url.replace('/PL/', '/LJ/'))).json()['frame'] is None
        removed = await client.delete(url + '/' + doc['id'])
        assert removed.status_code == 200 and removed.json()['frame'] is None
        assert (await client.get(url)).json()['frame'] is None
