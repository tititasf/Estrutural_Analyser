from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from portal.app import auth
from portal.app.dbdep import get_db_conn
from portal.app.routers import recortes_routes as routes


@pytest.fixture
def client(tmp_path, monkeypatch):
    app=FastAPI()
    app.state.settings=SimpleNamespace(dados_obras_dir=tmp_path)
    app.include_router(routes.router)
    app.dependency_overrides[auth.exige_login]=lambda:{'id':'allowed'}
    app.dependency_overrides[get_db_conn]=lambda:None
    def access(conn, obra_id, membro):
        if membro['id']!='allowed':
            raise HTTPException(403)
        return {'local_path':str(tmp_path)}
    monkeypatch.setattr(routes,'_obra_do_membro',access)
    source=tmp_path/'test.dxf';source.write_bytes(b'immutable DXF fixture')
    monkeypatch.setattr(routes.torre_crop,'obter_recorte_bruto',lambda *args:{'path':str(source)})
    monkeypatch.setattr(routes.dxf_preview,'etag_preview_completo',lambda *args:'"one"')
    original=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" data-cad-thin-strokes="1"><style id="cad-thin-strokes">svg[data-cad-thin-strokes="1"] :is(path,line,polyline,polygon){vector-effect:non-scaling-stroke!important;stroke-width:0.55px!important;stroke-linecap:butt!important;stroke-linejoin:miter!important;}</style><g id="LineCollection_1"><path d="M 1 2 L 3 4"/></g></svg>'
    monkeypatch.setattr(routes.dxf_preview,'renderizar_dxf_completo_cacheado',lambda *args:original)
    return TestClient(app),app,tmp_path


BASE='/obras/test/recortes/brutos/bruto/torre_1/viewer-package/'


def test_assets_revision_checksums_and_private_cache(client):
    c,app,folder=client
    r=c.get(BASE+'manifest');assert r.status_code==200
    assert r.headers['cache-control']=='private, no-cache'
    manifest=r.json();revision=manifest['revision']
    assert c.get(BASE+'shell',params={'revision':revision}).status_code==200
    assert c.get(BASE+'segments',params={'revision':revision}).content
    assert c.get(BASE+'chunks',params={'revision':revision,'ids':'0'}).json()['fragments'][0]['svg']
    assert c.get(BASE+'chunks',params={'revision':revision,'ids':'../0'}).status_code==400
    assert c.get(BASE+'chunks',params={'revision':revision,'ids':'1'}).status_code==400
    assert c.get(BASE+'shell',params={'revision':'other'}).status_code==409
    package=next((folder/'.previews').glob('*.regional'))
    (package/'0.svgpart').write_bytes(b'corrupted')
    assert c.get(BASE+'chunks',params={'revision':revision,'ids':'0'}).status_code==503
    assert (folder/'test.dxf').read_bytes()==b'immutable DXF fixture'


def test_access_rechecked_for_cached_asset(client):
    c,app,folder=client
    revision=c.get(BASE+'manifest').json()['revision']
    app.dependency_overrides[auth.exige_login]=lambda:{'id':'denied'}
    for asset in ['manifest','shell','segments','chunks']:
        assert c.get(BASE+asset,params={'revision':revision,'ids':'0'}).status_code==403
    def unauthenticated():raise HTTPException(401)
    app.dependency_overrides[auth.exige_login]=unauthenticated
    assert c.get(BASE+'shell',params={'revision':revision}).status_code==401

RAW='/obras/test/recortes/brutos/bruto/viewer-package/'


def test_raw_package_uses_original_and_checks_access_revision(client, monkeypatch):
    c,app,folder=client
    entrada=folder/'entrada';entrada.mkdir()
    original=entrada/'bruto.DXF';original.write_bytes(b'original entities unchanged')
    monkeypatch.setattr(routes.torre_crop,'obter_recorte_bruto',lambda *args: (_ for _ in ()).throw(AssertionError('Raw must use original, not crop')))
    manifest=c.get(RAW+'manifest').json();revision=manifest['revision']
    for asset in ['shell','segments','chunks']:
        assert c.get(RAW+asset,params={'revision':revision,'ids':'0'}).status_code==200
    assert c.get(RAW+'shell',params={'revision':'stale'}).status_code==409
    assert c.get('/obras/test/recortes/brutos/missing/viewer-package/manifest').status_code==404
    app.dependency_overrides[auth.exige_login]=lambda:{'id':'denied'}
    for asset in ['manifest','shell','segments','chunks']:
        assert c.get(RAW+asset,params={'revision':revision,'ids':'0'}).status_code==403
    assert original.read_bytes()==b'original entities unchanged'


def test_raw_complete_preview_uses_compact_cache_and_304(client, monkeypatch):
    c,app,folder=client
    entrada=folder/'entrada';entrada.mkdir()
    (entrada/'bruto.dxf').write_bytes(b'original')
    url='/obras/test/recortes/brutos/bruto/foto'
    response=c.get(url);assert response.status_code==200
    assert response.headers['content-encoding']=='gzip'
    uncompressed=c.get(url,headers={'Accept-Encoding':'gzip;q=0, identity'})
    assert 'content-encoding' not in uncompressed.headers
    assert uncompressed.content==response.content
    assert response.headers['vary']=='Accept-Encoding'
    assert response.headers['cache-control']=='private, no-cache'
    assert list((folder/'.previews').glob('*.viewer.svg'))
    assert c.get(url,headers={'If-None-Match':'W/'+response.headers['etag']}).status_code==304
