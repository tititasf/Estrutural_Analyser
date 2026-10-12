import sqlite3
import pytest
from scripts.arete import register_lv_nova_design_knowledge as knowledge


def test_rejects_desktop_stale_copy_when_workspace_db_exists(tmp_path, monkeypatch):
    repo = tmp_path/'repo'; repo.mkdir()
    monkeypatch.setattr(knowledge, '__file__', str(repo/'scripts/arete/register.py'))
    (tmp_path/'project_data.vision').touch()
    stale = repo/'project_data.vision'; stale.touch()
    with pytest.raises(ValueError, match='stale'):
        knowledge.register(stale, tmp_path/'unused.md', 'Thierry')


def test_registers_vps_canonical_repo_db_idempotently(tmp_path, monkeypatch):
    repo = tmp_path/'repo'; repo.mkdir()
    monkeypatch.setattr(knowledge, '__file__', str(repo/'scripts/arete/register.py'))
    db = repo/'project_data.vision'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE semantic_rag_kb (classe, regra_semantica, obra_contexto, confianca, tier, field_id, familia)')
    spec = repo/'approved.md'; spec.write_text('# Approved\n\n## AB\nApproved drawing rule.', encoding='utf8')
    assert knowledge.register(db, spec, 'Thierry')['inserted'] == 1
    assert knowledge.register(db, spec, 'Thierry')['already_registered']
    with sqlite3.connect(db) as con:
        assert con.execute('SELECT count(*) FROM semantic_rag_kb').fetchone()[0] == 1
