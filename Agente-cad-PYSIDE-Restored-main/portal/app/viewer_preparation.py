"""Prepare private visual derivatives ahead of navigation, never CAD inputs."""
from __future__ import annotations

import hashlib
import gzip
import logging
import os
from pathlib import Path
import queue
import tempfile
import threading
import time

from . import dxf_preview, viewer_package

log = logging.getLogger(__name__)
_locks = [threading.Lock() for _ in range(32)]


def compressed_viewer(viewer: Path) -> bytes:
    """Cache lossless HTTP compression of a revision-specific visual derivative."""
    viewer = Path(viewer)
    target = viewer.with_suffix(viewer.suffix + '.gz')
    lock = _locks[int(hashlib.sha256(str(viewer.resolve()).encode()).hexdigest()[:8], 16) % len(_locks)]
    with lock:
        if target.is_file() and target.stat().st_mtime_ns >= viewer.stat().st_mtime_ns:
            return target.read_bytes()
        content = gzip.compress(viewer.read_bytes(), compresslevel=3, mtime=0)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=viewer.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(content)
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return content


def prepare(source: Path, cache_dir: Path, *, regional: bool = True) -> dict:
    """Same revision and renderer as HTTP; concurrent requests share the work."""
    source, cache_dir = Path(source).resolve(), Path(cache_dir).resolve()
    revision = dxf_preview.etag_preview_completo(source)
    lock = _locks[int(hashlib.sha256(str(source).encode()).hexdigest()[:8], 16) % len(_locks)]
    with lock:
        # A queued crop may have been replaced before the worker starts.
        revision = dxf_preview.etag_preview_completo(source)
        viewer = cache_dir / (revision.strip('"') + '.viewer.svg')
        result = {"revision": revision, "viewer": str(viewer), "regional": None}
        original = None

        def load_original():
            nonlocal original
            if original is None:
                original = dxf_preview.renderizar_dxf_completo_cacheado(source, cache_dir)
            return original

        if not viewer.is_file():
            content = dxf_preview.svg_viewer_compactar_tracos(load_original())
            if dxf_preview.etag_preview_completo(source) != revision:
                raise ValueError("source changed during viewer preparation")
            cache_dir.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=cache_dir, delete=False) as output:
                    temporary = Path(output.name)
                    output.write(content)
                os.replace(temporary, viewer)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        if regional:
            try:
                result["regional"] = str(viewer_package.ensure_cached(
                    revision, cache_dir, load_original,
                    lambda: dxf_preview.etag_preview_completo(source)))
            except viewer_package.UnsupportedSVG as exc:
                # Complete SVG already prepared. Unsupported geometry is not removed.
                result["fallback"] = str(exc)
        if dxf_preview.etag_preview_completo(source) != revision:
            raise ValueError("source changed before viewer delivery")
        return result


class PreparationQueue:
    """One lazy worker, bounded queue, coalesced by source and renderer revision."""
    def __init__(self, capacity=32, prepare_fn=prepare):
        self.queue = queue.Queue(maxsize=capacity)
        self.prepare = prepare_fn
        self.guard = threading.Lock()
        self.pending = set()
        self.worker = None

    def submit(self, source: Path, cache_dir: Path) -> bool:
        try:
            source, cache_dir = Path(source).resolve(), Path(cache_dir).resolve()
            key = (source, cache_dir, dxf_preview.etag_preview_completo(source))
            with self.guard:
                if key in self.pending:
                    return True
                try:
                    self.queue.put_nowait(key)
                except queue.Full:
                    log.warning("viewer preparation queue full: %s; HTTP fallback retained", source)
                    return False
                self.pending.add(key)
                if self.worker is None or not self.worker.is_alive():
                    self.worker = threading.Thread(target=self._run, name="viewer-preparation", daemon=True)
                    self.worker.start()
            return True
        except Exception:
            log.exception("could not schedule viewer preparation: %s", source)
            return False

    def _run(self):
        while True:
            key = self.queue.get()
            started = time.perf_counter()
            try:
                result = self.prepare(key[0], key[1])
                log.info("viewer prepared: source=%s regional=%s elapsed=%.3fs", key[0],
                         bool(result.get("regional")), time.perf_counter() - started)
            except Exception:
                # A preview failure must never fail crop/SA production.
                log.exception("viewer preparation failed: %s; HTTP retry retained", key[0])
            finally:
                with self.guard:
                    self.pending.discard(key)
                self.queue.task_done()


_queue = PreparationQueue()


def schedule(source: Path, cache_dir: Path) -> bool:
    return _queue.submit(source, cache_dir)
