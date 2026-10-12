import threading
from pathlib import Path

import pytest

from portal.app import viewer_preparation as vp
from portal.app.viewer_package import build
from portal.tests.test_viewer_package import svg


def test_lossless_compression_cached_without_recomputing(tmp_path, monkeypatch):
    import gzip
    drawing=tmp_path/'revision.viewer.svg'
    original=b'<svg>'+b'M 1.123456789 2 L 3 4 '*10000+b'</svg>'
    drawing.write_bytes(original)
    compressed=vp.compressed_viewer(drawing)
    assert gzip.decompress(compressed)==original
    assert drawing.read_bytes()==original
    monkeypatch.setattr(vp.gzip,'compress',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('warm HTTP must not recompress')))
    assert vp.compressed_viewer(drawing)==compressed


def setup_renderer(monkeypatch, tmp_path):
    source = tmp_path / 'source.dxf'
    source.write_bytes(b'input')
    drawing = svg('<path d="M 1.123456789 2 L 3 4" style="fill:none;stroke:red"/>')
    calls = []
    monkeypatch.setattr(vp.dxf_preview, 'renderizar_dxf_completo_cacheado',
                        lambda *_: calls.append(1) or drawing)
    monkeypatch.setattr(vp.dxf_preview, 'svg_viewer_compactar_tracos', lambda raw: raw)
    return source, drawing, calls


def test_warm_cache_complete_geometry_and_invalidation(monkeypatch, tmp_path):
    source, drawing, calls = setup_renderer(monkeypatch, tmp_path)
    cache = tmp_path / 'cache'
    result = vp.prepare(source, cache)
    assert Path(result['viewer']).read_bytes() == drawing
    assert build(drawing, result['revision']).reconstruct() == drawing
    assert vp.prepare(source, cache) == result
    assert len(calls) == 1
    source.write_bytes(b'changed source input')
    updated = vp.prepare(source, cache)
    assert updated['revision'] != result['revision']
    assert updated['viewer'] != result['viewer']
    assert len(calls) == 2


def test_request_shares_inflight_preparation(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    source, drawing, calls = setup_renderer(monkeypatch, tmp_path)
    entered, release = threading.Event(), threading.Event()
    def render(*_):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return drawing
    monkeypatch.setattr(vp.dxf_preview, 'renderizar_dxf_completo_cacheado', render)
    with ThreadPoolExecutor(max_workers=2) as pool:
        warm = pool.submit(vp.prepare, source, tmp_path / 'cache')
        assert entered.wait(5)
        request = pool.submit(vp.prepare, source, tmp_path / 'cache')
        release.set()
        assert request.result() == warm.result()
    assert len(calls) == 1


def test_unsupported_keeps_full_svg_and_source_race_rejects(monkeypatch, tmp_path):
    source, drawing, _ = setup_renderer(monkeypatch, tmp_path)
    unsupported = drawing.replace(b'data-cad-thin-strokes="1"', b'')
    monkeypatch.setattr(vp.dxf_preview, 'renderizar_dxf_completo_cacheado', lambda *_: unsupported)
    result = vp.prepare(source, tmp_path / 'cache')
    assert result['regional'] is None
    assert Path(result['viewer']).read_bytes() == unsupported
    source.write_bytes(b'new input')
    def change(*_):
        source.write_bytes(b'changed while rendering')
        return drawing
    monkeypatch.setattr(vp.dxf_preview, 'renderizar_dxf_completo_cacheado', change)
    with pytest.raises(ValueError, match='source changed'):
        vp.prepare(source, tmp_path / 'cache')


def test_queue_bounded_coalesced_failure_does_not_stop_next(monkeypatch, tmp_path):
    source, _, _ = setup_renderer(monkeypatch, tmp_path)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def work(path, cache):
        calls.append(path)
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
            raise ValueError('bad preview')
        return {'regional': 'ready'}
    queue = vp.PreparationQueue(capacity=1, prepare_fn=work)
    assert queue.submit(source, tmp_path / 'cache')
    assert entered.wait(5)
    assert queue.submit(source, tmp_path / 'cache')
    second = tmp_path / 'second.dxf'
    second.write_bytes(b'second')
    assert queue.submit(second, tmp_path / 'cache')
    third = tmp_path / 'third.dxf'
    third.write_bytes(b'third')
    assert not queue.submit(third, tmp_path / 'cache')
    release.set()
    queue.queue.join()
    assert calls == [source.resolve(), second.resolve()]
    assert not queue.pending


def test_crop_schedule_is_source_specific(monkeypatch, tmp_path):
    from portal.app import torre_crop
    out = tmp_path / 'crops'
    out.mkdir()
    for name in ['torre_1.dxf', 'detalhes.dxf', 'validado.json']:
        (out / name).write_bytes(b'file')
    calls = []
    monkeypatch.setattr(vp, 'schedule', lambda *args: calls.append(args))
    torre_crop._preparar_viewers(tmp_path, out)
    assert {p.name for p, _ in calls} == {'torre_1.dxf', 'detalhes.dxf'}
    assert all(cache == tmp_path / '.previews' for _, cache in calls)
