import json
import sqlite3
from types import SimpleNamespace

import pytest

from portal.app import pillar_tag_cache as cache


def test_pack_integrity_and_scope(tmp_path):
    pack = tmp_path / 'TIPO_20261010_pilares_abcd'
    pack.mkdir()
    svg = pack / 'P1.svg'
    svg.write_text('<svg>complete drawing</svg>')
    cache.record_pack(pack, 'key', ['P1'], {'gerados': 1})
    assert cache.find_pack(tmp_path, 'TIPO', 'key', ['P1'])[0] == pack
    assert cache.find_pack(tmp_path, 'OTHER', 'key', ['P1']) is None
    assert cache.find_pack(tmp_path, 'TIPO', 'key', ['P2']) is None
    assert cache.find_pack(tmp_path, 'TIPO', 'changed', ['P1']) is None
    svg.write_text('<svg>missing geometry</svg>')
    assert cache.find_pack(tmp_path, 'TIPO', 'key', ['P1']) is None


@pytest.mark.parametrize('mutation', ['remove', 'extra'])
def test_pack_missing_or_extra_artifact_rejected(tmp_path, mutation):
    pack = tmp_path / 'TIPO_1_pilares_abcd'
    pack.mkdir()
    (pack / 'drawing.svg').write_text('full')
    cache.record_pack(pack, 'key', ['P1'], {})
    if mutation == 'remove':
        (pack / 'drawing.svg').unlink()
    else:
        (pack / 'extra.svg').write_text('extra')
    assert cache.find_pack(tmp_path, 'TIPO', 'key', ['P1']) is None


@pytest.mark.parametrize('manifest', ['[]', '{"key":"key","names":["P1"],"stats":null}'])
def test_corrupt_cache_metadata_falls_back_to_generation(tmp_path, manifest):
    pack = tmp_path / 'TIPO_1_pilares_abcd'
    pack.mkdir()
    (pack / cache.MANIFEST).write_text(manifest)
    assert cache.find_pack(tmp_path, 'TIPO', 'key', ['P1']) is None


def test_fingerprint_scopes_db_and_invalidates_changed_sources(tmp_path, monkeypatch):
    from src.core import niveis_extractor
    monkeypatch.setattr(niveis_extractor, 'get_pavimento_niveis_abs', lambda *a: {'top': 100})
    monkeypatch.setattr(cache.importlib.metadata, 'version', lambda *a: 'test')
    repo = tmp_path / 'repo'
    source = repo / 'src/core/nested/render.py'
    source.parent.mkdir(parents=True)
    source.write_text('# renderer')
    root = tmp_path / 'obra'
    root.mkdir()
    snapshot = root / 'estado_TIPO.json'
    snapshot.write_text('{}')
    dxf = root / 'tower.dxf'
    dxf.write_text('geometry')
    db = tmp_path / 'state.db'
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE projects (id TEXT, dxf_path TEXT)')
        conn.execute('INSERT INTO projects VALUES (?,?)', ('p', str(dxf)))
        for table in ('pillars', 'slabs', 'beams'):
            conn.execute(f'CREATE TABLE {table} (project_id TEXT, value TEXT)')
            conn.execute(f'INSERT INTO {table} VALUES (?,?)', ('p', 'original'))
            conn.execute(f'INSERT INTO {table} VALUES (?,?)', ('foreign', 'original'))
    settings = SimpleNamespace(repo_root=repo, sa_db_path=db)
    def key():
        return cache.fingerprint(settings, root, 'obra', 'p', 'TIPO', ['P1'])
    initial = key()
    assert initial is not None
    snapshot.write_text(json.dumps({'gerado_em': 'new run clock'}))
    assert key() == initial
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE pillars SET value='changed' WHERE project_id='foreign'")
    assert key() == initial
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE slabs SET value='changed' WHERE project_id='p'")
    current = key()
    assert current != initial
    source.write_text('# changed nested renderer')
    assert key() != current
    current = key()
    dxf.write_text('changed geometry')
    assert key() != current
    current = key()
    snapshot.write_text(json.dumps({'level': 2}))
    assert key() != current
    current = key()
    approved = root / 'arete_approved/pilares_tags_TIPO.json'
    approved.parent.mkdir()
    approved.write_text('{"items":{}}')
    assert key() != current

