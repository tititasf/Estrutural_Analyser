from types import SimpleNamespace
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.templating import Jinja2Templates
from portal.app.routers import drawing_mode_config_routes as routes
from scripts import drawing_mode_config as profiles


def client(monkeypatch, signed=True):
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[routes.get_db_conn]=lambda: None
    app.state.templates=Jinja2Templates(directory=str(Path(routes.__file__).parents[1]/'templates'))
    app.state.static_versao='test'
    monkeypatch.setattr(routes,'_membro_da_sessao',lambda *args: {'id':'test','nome':'Teste','login':'test','papel':'dono'} if signed else None)
    return TestClient(app)


def test_page_and_context_return(monkeypatch):
    r=client(monkeypatch).get('/app/configuracao-modos/pagina',params={'retorno':'/app/obras/abc?pavimento=13_PAV'})
    assert r.status_code==200
    assert '<section id="drawing-mode-config-dialog"' in r.text
    assert '<dialog id="drawing-mode-config-dialog"' not in r.text
    assert 'id="portal-sidebar"' in r.text
    assert '/app/obras/abc?pavimento=13_PAV' in r.text


def test_return_cannot_redirect_outside_portal(monkeypatch):
    r=client(monkeypatch).get('/app/configuracao-modos/pagina',params={'retorno':'https://evil.example/'})
    assert 'evil.example' not in r.text


def test_page_requires_session(monkeypatch):
    r=client(monkeypatch,False).get('/app/configuracao-modos/pagina',follow_redirects=False)
    assert r.status_code==303 and r.headers['location']=='/login'


def test_catalog_shares_measurement_but_resets_after_request(tmp_path,monkeypatch):
    monkeypatch.setenv('ARETE_DRAWING_MODE_CONFIG',str(tmp_path/'settings.json'))
    original=profiles.current_catalog;calls=[]
    def measured():
        if profiles.CATALOG_CURRENT.get() is None: calls.append(1)
        return original()
    monkeypatch.setattr(profiles,'current_catalog',measured)
    a=profiles.catalog();b=profiles.catalog()
    assert a==b and len(calls)==2
    assert profiles.CATALOG_CURRENT.get() is None
    assert profiles.GENERATION_STORE.get() is None
    assert profiles._motor_tree('A=1') is not profiles._motor_tree('A=2')
