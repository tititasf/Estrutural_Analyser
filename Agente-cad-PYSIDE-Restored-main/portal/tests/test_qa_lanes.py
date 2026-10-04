import threading
import time
from types import SimpleNamespace

from portal.app import qa_jobs


def _p(name):
    return SimpleNamespace(config=SimpleNamespace(name=name))


def test_lanes_follow_env_and_keep_others_as_fallback(monkeypatch):
    gem, grok, codex = _p('antigravity'), _p('grok'), _p('codex')
    monkeypatch.delenv('CAD_QA_LANES', raising=False)
    assert qa_jobs._lanes([gem, grok, codex]) == [[gem, grok, codex]]
    monkeypatch.setenv('CAD_QA_LANES', 'antigravity,grok')
    assert qa_jobs._lanes([gem, grok, codex]) == [[gem, grok, codex], [grok, gem, codex]]
    monkeypatch.setenv('CAD_QA_LANES', 'grok,desconhecida')
    assert qa_jobs._lanes([gem, grok]) == [[gem, grok]]


def test_each_item_reviewed_once_in_parallel_and_pause_stops_lanes(tmp_path, monkeypatch):
    settings = SimpleNamespace(db_path=tmp_path / 'portal_data.db')
    lanes = [[_p('antigravity')], [_p('grok')]]
    seen, active, peak, lock = [], [0], [0], threading.Lock()

    def revisar(row, providers, conn):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            seen.append((row['item_id'], providers[0].config.name))
        time.sleep(0.05)
        with lock:
            active[0] -= 1
        return None

    rows = [{'item_id': f'P{i}'} for i in range(6)]
    assert qa_jobs._run_lanes(settings, rows, lanes, revisar) is None
    assert sorted(i for i, _ in seen) == sorted(r['item_id'] for r in rows)
    assert peak[0] == 2

    done = []

    def pausa(row, providers, conn):
        done.append(row['item_id'])
        return 'paused'

    assert qa_jobs._run_lanes(settings, rows, lanes, pausa) == 'paused'
    assert len(done) <= 2
