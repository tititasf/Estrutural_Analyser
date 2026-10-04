import pytest
from portal.app import qa_human_notes, fv_operations, laje_operations


@pytest.mark.parametrize('classe,item', [('PIL','P1'), ('LV','V301'), ('FV','V301'), ('LAJ','L301')])
def test_notes_roundtrip_all_versions(tmp_path, classe, item):
    notes = {layer: 'Observação ' + layer for layer in qa_human_notes.LAYERS}
    assert qa_human_notes.save(tmp_path, '13_PAV', classe, item, notes) == notes
    assert qa_human_notes.load(tmp_path, '13_PAV', classe, item) == notes
    if classe == 'FV':
        assert fv_operations.load_override(tmp_path, '13_PAV', item)['notes'] == notes
    if classe == 'LAJ':
        assert laje_operations.load_override(tmp_path, '13_PAV', item)['notes'] == notes


def test_notes_isolate_floor_item_and_lateral_behavior(tmp_path):
    qa_human_notes.save(tmp_path, '13_PAV', 'LV', 'V301', {'sa':'Para'})
    qa_human_notes.save(tmp_path, '13_PAV', 'LV', 'V301', {'sa':'Passa'}, 'passa')
    assert qa_human_notes.load(tmp_path, '13_PAV', 'LV', 'V301')['sa'] == 'Para'
    assert qa_human_notes.load(tmp_path, '13_PAV', 'LV', 'V301', 'passa')['sa'] == 'Passa'
    assert qa_human_notes.load(tmp_path, '14_PAV', 'LV', 'V301') == {}
    assert qa_human_notes.load(tmp_path, '13_PAV', 'LV', 'V302') == {}


def test_notes_reject_path_escape(tmp_path):
    with pytest.raises(ValueError):
        qa_human_notes.save(tmp_path, '..', 'PIL', 'P1', {'sa':'bad'})


def test_notes_keep_existing_fv_segments(tmp_path):
    fv_operations.save_notes(tmp_path, '13_PAV', 'V301', {'sa':'antes'})
    path = tmp_path / '.portal_overrides/fv/13_PAV/V301.json'
    import json
    payload = json.loads(path.read_text(encoding='utf-8'))
    payload['segments'] = {'1': {'validated':True}}
    path.write_text(json.dumps(payload), encoding='utf-8')
    qa_human_notes.save(tmp_path, '13_PAV', 'FV', 'V301', {'n3':'desenho'})
    assert fv_operations.load_override(tmp_path, '13_PAV', 'V301')['segments'] == payload['segments']


@pytest.mark.asyncio
async def test_notes_authenticated_roundtrip_and_qa_capabilities(settings):
    import json
    from portal.tests.test_portal_ui_feedback import _client, _obra
    async with _client(settings) as client:
        obra_id = _obra(settings)
        folder = settings.dados_obras_dir / 'Obra Feedback'
        folder.mkdir(parents=True)
        (folder / 'estado_13_PAV.json').write_text(json.dumps({'slabs':[], 'pillars':[]}), encoding='utf-8')
        path = f'/obras/{obra_id}/qa-notas/PIL/P1?pavimento=13_PAV'
        assert (await client.get(path)).status_code in {401, 303}
        await client.post('/login', json={'login':'ana','senha':'segredo123'})
        for classe, item in [('PIL','P1'), ('FV','V301'), ('LAJ','L301'), ('LV','V301')]:
            path = f'/obras/{obra_id}/qa-notas/{classe}/{item}?pavimento=13_PAV'
            response = await client.put(path, json={'notes':{'sa':'nota de revisão', 'n3':'ajustar desenho'}})
            assert response.status_code == 200, response.text
            response = await client.get(path)
            assert response.json()['notes']['n3'] == 'ajustar desenho'
            assert response.json()['qa_available'] is True
        assert (await client.put(f'/obras/{obra_id}/qa-notas/PIL/P1?pavimento=99_PAV', json={'notes':{}})).status_code == 404


def test_worker_receives_saved_pillar_notes(conn, settings, tmp_path, monkeypatch):
    from portal.app import qa_versions
    monkeypatch.setattr(qa_versions, "current_sa", lambda *args, **kwargs: ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"/>', {}))
    from portal.tests.test_portal_qa_agentico import _rodada, _Provider
    from portal.app import qa_jobs
    round_id, _ = _rodada(conn, tmp_path)
    settings.repo_root = tmp_path
    qa_human_notes.save(settings.dados_obras_dir / 'Obra_TREINO_1', '13_PAV', 'PIL', 'P9',
                        {'sa':'conferir face oeste', 'n3':'revisar altura do desenho'})
    provider = _Provider('codex', 'validou')
    assert qa_jobs.executar_qa_round(settings=settings, conn=conn, round_id=round_id,
                                   log_path=tmp_path / 'notes-review.json', providers=[provider]) == 'completed'
    assert 'conferir face oeste' in provider.calls[0]
    assert 'revisar altura do desenho' in provider.calls[0]
    assert 'conferir face oeste' not in provider.calls[1]
