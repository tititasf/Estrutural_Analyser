"""Adoção humana de camada QA vira apontamento comparativo, sem duplicar nem perder."""
import copy
import json

import pytest

from portal.app import auth, ficha_reader, qa_adoption_notes as notes, qa_interpretation as q, qa_versions as versions
from portal.db import connection, repository as repo

from .test_qa_interpretation import SVG, state_for

OLD_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="20"/></svg>'


def _cairo():
    try:
        import cairosvg  # noqa: F401
        return True
    except OSError:
        return False


def test_comparison_png_side_by_side():
    if not _cairo():
        pytest.skip('cairo nativo indisponível')
    png = notes.comparison_png(OLD_SVG, SVG, 'L1')
    assert png[:4] == b'\x89PNG'
    assert int.from_bytes(png[16:20], 'big') == 1800  # dois painéis de 900


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    conn = connection.init_db(tmp_path / 'portal.db')
    member = repo.criar_membro(conn, login='dono', nome='Dono', senha_hash=auth.hash_senha('segredo123'),
                               drive_folder_id='f')
    member_id = member if isinstance(member, str) else repo.obter_membro_por_login(conn, 'dono')['id']
    obra_id = repo.criar_obra(conn, membro_id=member_id, nome='Obra QA', pasta_drive_id='f', estado='pronta')
    state, item = state_for('LV')
    row = state['segmentos']['lateral_a_para'][0]
    row.update(level='852.195', height=12.04)
    original = q.snapshot(state, 'LV', item)
    candidate = copy.deepcopy(original)
    candidate['collections']['lateral_a_para'][0].update(level='852.12', height=13)
    token = q.fingerprint({'interpretation': candidate, 'svg': versions.digest(SVG)})
    record = dict(round_id='r1', svg=SVG, promotion_ready=True, candidate_sha256=token, provider='gemini', model='m',
                  verdict='invalidou', confidence_percent=98.04,
                  checks=[{'status': 'pass'}, {'status': 'fail'}, {'status': 'uncertain'}],
                  field_corrections=[{'field_path': '/collections/lateral_a_para/0/level', 'before': '852.195',
                                      'after': '852.12', 'evidence': [{'finding': 'cota no DXF'}]}],
                  candidate_interpretation=candidate, base_snapshot_sha256=q.fingerprint(original),
                  post_review={'assessment': 'pass', 'checks': [{'status': 'pass'}]})
    monkeypatch.setattr(versions, 'read', lambda *a: {'L1': record})
    monkeypatch.setattr(ficha_reader, 'ler_estado_pavimento', lambda *a, **kw: copy.deepcopy(state))
    yield dict(conn=conn, member_id=member_id, obra_id=obra_id, obra_dir=tmp_path, item=item, token=token)
    conn.close()


def _promote(env, **kw):
    return q.promote(env['obra_dir'], '13_PAV', 'LV', env['item'], 'para', 'L1', 'r1', env['token'],
                     env['member_id'], previous_svg=OLD_SVG, **kw)


def _publish(env):
    return notes.publish_pending(env['conn'], obra_id=env['obra_id'], obra_dir=env['obra_dir'],
                                 pavimento='13_PAV', base_url='https://portal.test/')


def _sessions(env):
    return env['conn'].execute('SELECT * FROM portal_apontamento_sessoes ORDER BY created_at,rowid').fetchall()


def test_adoption_creates_one_comparative_note(ambiente):
    env = ambiente
    event_id = _promote(env)['event_id']
    assert _publish(env) == {'criados': 1, 'pendentes': 0}
    assert _publish(env) == {'criados': 0, 'pendentes': 0}
    [session] = _sessions(env)
    assert session['origem_evento'] == event_id and session['membro_id'] == env['member_id']
    assert session['titulo'] == 'QA L1 adotada — LV V301 para (13_PAV)'
    point = env['conn'].execute('SELECT * FROM portal_apontamentos_ui WHERE sessao_id=?', (session['id'],)).fetchone()
    text = point['texto']
    assert '852,20 → 852,12' in text and '12 → 13' in text  # nível 2 casas; medida sem ruído
    assert '1 PASS / 1 FAIL / 1 incertos' in text and 'DECLARADA' in text and '98%' in text
    if _cairo():
        assert point['captura_mime'] == 'image/png' and point['captura_blob'][:4] == b'\x89PNG'
    else:  # sem cairo nativo: apontamento sai sem captura, SVGs seguem anexos
        assert point['captura_blob'] is None
    assert 'classe=laterais_para' in point['pagina_url'] and 'subvista=L1' in point['pagina_url']
    names = [a['nome'] for a in repo.listar_anexos_apontamento_ui(env['conn'], point['id'])]
    assert names == ['LV-V301-SA-anterior.svg', 'LV-V301-L1-adotada.svg', 'LV-V301-evidencias.json']
    blob = env['conn'].execute("SELECT blob FROM portal_apontamento_anexos WHERE nome LIKE '%evidencias.json'").fetchone()[0]
    evidence = json.loads(blob)
    assert evidence['sa_anterior']['collections']['lateral_a_para'][0]['level'] == '852.195'
    assert evidence['camada_adotada']['collections']['lateral_a_para'][0]['level'] == '852.12'
    assert q.load_manifest(env['obra_dir'], '13_PAV')['history'][-1]['apontamento'] == 'criado'


def test_db_failure_keeps_pending_then_retries_without_duplicate(ambiente, monkeypatch):
    env = ambiente
    _promote(env)
    original = repo.inserir_sessao_apontamento_ui
    monkeypatch.setattr(repo, 'inserir_sessao_apontamento_ui', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('db')))
    assert _publish(env) == {'criados': 0, 'pendentes': 1}
    assert q.load_manifest(env['obra_dir'], '13_PAV')['history'][-1]['apontamento'] == 'pendente'
    assert q.load_manifest(env['obra_dir'], '13_PAV')['items']  # adoção não depende do apontamento
    monkeypatch.setattr(repo, 'inserir_sessao_apontamento_ui', original)
    assert _publish(env)['criados'] == 1
    assert len(_sessions(env)) == 1


def test_crash_after_insert_before_mark_does_not_duplicate(ambiente, monkeypatch):
    env = ambiente
    _promote(env)
    monkeypatch.setattr(notes, '_mark', lambda *a: (_ for _ in ()).throw(OSError('disco')))
    _publish(env)
    monkeypatch.undo()
    _publish(env)
    assert len(_sessions(env)) == 1
    assert q.load_manifest(env['obra_dir'], '13_PAV')['history'][-1]['apontamento'] == 'criado'


def test_rollback_adds_note_and_keeps_adoption_note(ambiente):
    env = ambiente
    _promote(env)
    _publish(env)
    q.rollback(env['obra_dir'], '13_PAV', 'LV', env['item'], 'para', 'r1', env['member_id'])
    _publish(env)
    titles = [s['titulo'] for s in _sessions(env)]
    assert titles == ['QA L1 adotada — LV V301 para (13_PAV)', 'QA L1 desfeita — LV V301 para (13_PAV)']


def test_failed_promotion_creates_nothing(ambiente):
    env = ambiente
    with pytest.raises(ValueError):
        q.promote(env['obra_dir'], '13_PAV', 'LV', env['item'], 'para', 'L1', 'r1', 'errado', env['member_id'])
    assert _publish(env) == {'criados': 0, 'pendentes': 0}
    assert not _sessions(env)
    assert not (env['obra_dir'] / '.portal_overrides' / 'qa_adoptions').exists()


def test_missing_previous_viewer_is_stated_not_faked(ambiente):
    env = ambiente
    q.promote(env['obra_dir'], '13_PAV', 'LV', env['item'], 'para', 'L1', 'r1', env['token'], env['member_id'])
    _publish(env)
    point = env['conn'].execute('SELECT texto,id FROM portal_apontamentos_ui').fetchone()
    assert 'Viewer SA anterior indisponível' in point['texto']
    names = [a['nome'] for a in repo.listar_anexos_apontamento_ui(env['conn'], point['id'])]
    assert 'LV-V301-SA-anterior.svg' not in names
