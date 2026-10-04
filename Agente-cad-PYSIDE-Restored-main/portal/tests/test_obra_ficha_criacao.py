"""Ficha completa na criação, edição, validação e atualização de bancos antigos."""
import pytest

from portal.db import connection, repository as repo
from portal.tests.test_portal_http_flow import _app_cliente


@pytest.mark.asyncio
async def test_criar_editar_e_reabrir_ficha_completa(settings):
    async with _app_cliente(settings) as (_, client):
        await client.post('/login', json={'login': 'ana', 'senha': 'segredo123'})
        fields = dict(cliente='Cliente teste', data_solicitacao='2026-10-01',
                      data_entrega='2026-10-15', criterios_cliente='Critério separado',
                      observacoes='Nota interna', comportamento='passa',
                      comportamento_laterais_vigas='gradeadas', fundos_vigas_possui_garfos='nao')
        r = await client.post('/obras/criar', json=dict(nome='Obra completa', **fields))
        assert r.status_code == 200, r.text
        obra_id = r.json()['obra_id']
        r = await client.get(f'/obras/{obra_id}')
        assert all(r.json()['obra'][k] == v for k, v in fields.items())
        html = (await client.get(f'/app/obras/{obra_id}')).text
        assert 'name="comportamento_laterais_vigas"' not in html
        assert 'name="fundos_vigas_possui_garfos"' not in html
        r = await client.post(f'/obras/{obra_id}/cabecalho', json={
            'comportamento_laterais_vigas': 'sarrafeadas', 'fundos_vigas_possui_garfos': 'sim'})
        assert r.status_code == 200
        assert r.json()['cliente'] == fields['cliente']
        assert r.json()['comportamento_laterais_vigas'] == 'sarrafeadas'
        assert r.json()['fundos_vigas_possui_garfos'] == 'sim'
        r = await client.post(f'/obras/{obra_id}/cabecalho', json={
            'comportamento_laterais_vigas': '', 'fundos_vigas_possui_garfos': '', 'cliente': ''})
        assert r.status_code == 200
        r = await client.get(f'/obras/{obra_id}')
        assert r.json()['obra']['fundos_vigas_possui_garfos'] == 'nao'
        assert r.json()['obra']['comportamento_laterais_vigas'] == 'sarrafeadas'
        assert r.json()['obra']['cliente'] == ''
        for endpoint in ['/obras/criar', f'/obras/{obra_id}/cabecalho']:
            r = await client.post(endpoint, json={'nome': 'Inválida', 'fundos_vigas_possui_garfos': 'talvez'})
            assert r.status_code == 422
        r = await client.post('/obras/criar', json={'nome': 'Legada'})
        obra = (await client.get('/obras/' + r.json()['obra_id'])).json()['obra']
        assert obra['comportamento_laterais_vigas'] == 'sarrafeadas'
        assert obra['fundos_vigas_possui_garfos'] == 'nao'


def test_migracao_preserva_obra_existente_e_e_idempotente(tmp_path):
    import shutil
    old = tmp_path / 'migrations'
    old.mkdir()
    for path in connection.MIGRATIONS_DIR.glob('*.sql'):
        if int(path.name.split('_')[0]) < 19:
            shutil.copyfile(path, old / path.name)
    conn = connection.get_connection(tmp_path / 'portal_data.db')
    connection.migrate(conn, old)
    membro = repo.criar_membro(conn, login='teste', nome='Teste', senha_hash='hash')
    obra_id = repo.criar_obra(conn, membro_id=membro, nome='Preservar', pasta_drive_id='pasta')
    conn.execute('UPDATE portal_obras SET cliente=?, observacoes=? WHERE id=?',
                 ('Cliente antigo', 'Preservar nota', obra_id))
    conn.commit()
    assert connection.migrate(conn) == 21
    assert connection.migrate(conn) == 21
    obra = repo.obter_obra(conn, obra_id)
    assert obra['cliente'] == 'Cliente antigo' and obra['observacoes'] == 'Preservar nota'
    assert obra['comportamento_laterais_vigas'] == 'sarrafeadas'
    assert obra['fundos_vigas_possui_garfos'] == 'nao'
    conn.close()


def test_defaults_normalizam_vazios_e_preservam_escolhas(tmp_path):
    import shutil
    old = tmp_path / 'migrations19'
    old.mkdir()
    for path in connection.MIGRATIONS_DIR.glob('*.sql'):
        if int(path.name.split('_')[0]) <= 19:
            shutil.copyfile(path, old / path.name)
    conn = connection.get_connection(tmp_path / 'defaults.db')
    connection.migrate(conn, old)
    membro = repo.criar_membro(conn, login='teste', nome='Teste', senha_hash='hash')
    vazio = repo.criar_obra(conn, membro_id=membro, nome='Vazio', pasta_drive_id='pasta1')
    escolhido = repo.criar_obra(conn, membro_id=membro, nome='Escolhido', pasta_drive_id='pasta2')
    repo.atualizar_cabecalho_obra(conn, vazio, comportamento_laterais_vigas='', fundos_vigas_possui_garfos='')
    repo.atualizar_cabecalho_obra(conn, escolhido, comportamento_laterais_vigas='gradeadas', fundos_vigas_possui_garfos='sim')
    connection.migrate(conn)
    assert repo.obter_obra(conn, vazio)['comportamento_laterais_vigas'] == 'sarrafeadas'
    assert repo.obter_obra(conn, vazio)['fundos_vigas_possui_garfos'] == 'nao'
    assert repo.obter_obra(conn, escolhido)['comportamento_laterais_vigas'] == 'gradeadas'
    assert repo.obter_obra(conn, escolhido)['fundos_vigas_possui_garfos'] == 'sim'
    novo = repo.criar_obra(conn, membro_id=membro, nome='Ingestão', pasta_drive_id='pasta3')
    assert repo.obter_obra(conn, novo)['comportamento_laterais_vigas'] == 'sarrafeadas'
    assert repo.obter_obra(conn, novo)['fundos_vigas_possui_garfos'] == 'nao'
    conn.execute('UPDATE portal_obras SET comportamento_laterais_vigas=NULL, fundos_vigas_possui_garfos=? WHERE id=?', ('', escolhido))
    conn.commit()
    assert repo.obter_obra(conn, escolhido)['comportamento_laterais_vigas'] == 'sarrafeadas'
    assert repo.obter_obra(conn, escolhido)['fundos_vigas_possui_garfos'] == 'nao'
    conn.close()
