from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from threading import Barrier, Event, Lock

import pytest

from portal.app.effective_soffits import _singleflight
from portal.app import effective_soffits, item_geometry


def test_cold_geometry_requests_share_one_calculation():
    start = Barrier(8)
    entered = Event()
    release = Event()
    calls = []

    @_singleflight
    @lru_cache(maxsize=2)
    def compute(*revision):
        calls.append(revision)
        entered.set()
        assert release.wait(5)
        return {'geometry': revision}

    def request():
        start.wait(5)
        return compute('floor', 'source', 'database', 'state', 'edits')

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(request) for _ in range(8)]
        assert entered.wait(5)
        release.set()
        results = [f.result(5) for f in futures]
    assert len(calls) == 1
    assert all(result is results[0] for result in results)
    assert compute.cache_info().hits == 7


def test_different_revisions_do_not_block_each_other():
    inside = Barrier(2)

    @_singleflight
    @lru_cache(maxsize=2)
    def compute(revision):
        inside.wait(5)
        return revision

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(compute, revision) for revision in ('old', 'new')]
        assert [f.result(5) for f in futures] == ['old', 'new']


def test_failure_releases_waiters_and_is_not_cached():
    calls = 0
    guard = Lock()

    @_singleflight
    @lru_cache(maxsize=2)
    def compute(revision):
        nonlocal calls
        with guard:
            calls += 1
            if calls == 1:
                raise ValueError('temporary failure')
        return revision

    with pytest.raises(ValueError, match='temporary'):
        compute('same')
    assert compute('same') == 'same'
    assert compute('same') == 'same'
    assert calls == 2
    compute.cache_clear()
    assert compute('same') == 'same'
    assert calls == 3


def test_apply_state_preserves_revision_invalidation_and_copy_isolation(tmp_path, monkeypatch):
    source = tmp_path / 'source.dxf'
    source.write_text('original')
    database = tmp_path / 'database.sqlite'
    database.write_text('original')
    custom = {'edits': {}, 'created': {}}
    monkeypatch.setattr(item_geometry, 'load', lambda *args: custom)
    calls = []

    @_singleflight
    @lru_cache(maxsize=2)
    def compute(*args):
        calls.append(args)
        return {'geometry': [1, 2]}

    monkeypatch.setattr(effective_soffits, '_effective', compute)
    state = {'db_path': str(database), 'segmentos': {'fundo': [{'uid': 'one'}]}}
    def load():
        return effective_soffits.apply_state(state, tmp_path, '13_PAV', source)

    load()['geometry'].append(99)
    assert load()['geometry'] == [1, 2]
    assert len(calls) == 1
    source.write_text('modified source')
    load()
    database.write_text('modified database')
    load()
    state['segmentos']['fundo'].append({'uid': 'two'})
    load()
    custom['edits']['fundo'] = {'one': {}}
    load()
    assert len(calls) == 5
