import sqlite3

from scripts.arete.dev_sa_cycle import protected_files, runtime_source_hashes, sha, snapshot_database


def test_runtime_code_guard_detects_concurrent_changes_without_mtime_assumption(tmp_path):
    import os
    core = tmp_path / 'src/core'
    core.mkdir(parents=True)
    qa = tmp_path / 'portal/app'
    qa.mkdir(parents=True)
    scripts = tmp_path / 'scripts/arete'
    scripts.mkdir(parents=True)
    source = core / 'engine.py'
    source.write_text('version = 1')
    removed = qa / 'qa.py'
    removed.write_text('gate = 1')
    (scripts / 'dev_sa_cycle.py').write_text('cycle = 1')
    reports = scripts / 'relatorios'
    reports.mkdir()
    report = reports / 'probe.py'
    report.write_text('diagnostic = 1')
    before = runtime_source_hashes(tmp_path)
    stamp = source.stat()
    source.write_text('version = 2')
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    removed.unlink()
    (qa / 'new_reader.py').write_text('reader = 1')
    report.write_text('diagnostic = 2')
    after = runtime_source_hashes(tmp_path)
    changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
    assert changed == {'src/core/engine.py', 'portal/app/qa.py', 'portal/app/new_reader.py'}


def test_sqlite_snapshot_includes_committed_wal_without_mutating_source(tmp_path):
    source = tmp_path / 'source.sqlite3'
    conn = sqlite3.connect(source)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('CREATE TABLE evidence(value INTEGER)')
    conn.execute('INSERT INTO evidence VALUES(55)')
    conn.commit()
    before = sha(source)
    destination = tmp_path / 'isolated.sqlite3'
    snapshot_database(source, destination)
    assert sha(source) == before
    with sqlite3.connect(destination) as snapshot:
        assert snapshot.execute('SELECT value FROM evidence').fetchone() == (55,)
        snapshot.execute('UPDATE evidence SET value=60')
    assert conn.execute('SELECT value FROM evidence').fetchone() == (55,)
    conn.close()


def test_guard_observes_created_deleted_and_changed_published_files(tmp_path):
    obra = tmp_path / 'work'
    folder = obra / 'Fase-6_Execucao_CAD/production_sa/14_PAV/current'
    folder.mkdir(parents=True)
    state = folder / 'state.json'
    state.write_text('initial')
    database = tmp_path / 'source.sqlite3'
    database.write_bytes(b'database')
    before = protected_files(obra, database)
    state.write_text('changed state')
    new = folder / 'unexpected.svg'
    new.write_text('render')
    after = protected_files(obra, database)
    assert before[str(state)] != after[str(state)]
    assert str(new) not in before and str(new) in after
    state.unlink()
    assert str(state) not in protected_files(obra, database)
