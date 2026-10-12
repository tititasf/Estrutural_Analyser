"""Run independent N3 drawings in isolated processes, preserving motor contracts."""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
import time


def generate_local_task(task):
    name, sides, path, view, mode, behavior = task
    started = time.monotonic()
    try:
        from scripts.arete.lv_n3_cut_draw import generate_local_panels, generate_local_sections
        if view == 'CORTE':
            generate_local_sections(sides, path, mode, behavior)
        else:
            generate_local_panels(sides, path, view, mode, behavior)
        if not Path(path).is_file():
            raise RuntimeError('gerador terminou sem publicar DXF')
        return name, True, '', time.monotonic() - started
    except Exception as exc:
        return name, False, str(exc), time.monotonic() - started


def run_local_tasks(tasks, max_workers=1):
    if not tasks:
        return []
    from src.core.cad_render_cache import render_worker_limit
    # Peak RSS of one spawned N3 worker on 13_PAV (2026-10-12): 106-138 MB.
    workers = render_worker_limit(max_workers, len(tasks), worker_bytes=384 * 1024**2)
    if workers == 1:
        return [generate_local_task(task) for task in tasks]
    # Spawn avoids inheriting Qt, SQLite connections or mutable CAD documents.
    with ProcessPoolExecutor(max_workers=workers,
                             mp_context=multiprocessing.get_context('spawn')) as pool:
        return list(pool.map(generate_local_task, tasks, chunksize=1))


def resolve_cut_task(task):
    from portal.app.lv_n3_cuts import resolve
    started = time.monotonic()
    try:
        result = resolve(*task)
        if not result.get('available') or '<svg' not in (result.get('svg') or ''):
            raise RuntimeError(result.get('reason') or 'SVG indisponivel')
        return True, result['fingerprint'], '', time.monotonic()-started
    except Exception as exc:
        return False, None, str(exc), time.monotonic()-started


def run_cut_tasks(tasks, max_workers=1):
    from src.core.cad_render_cache import render_worker_limit
    if not tasks:
        return []
    workers = render_worker_limit(max_workers, len(tasks))
    if workers == 1:
        return [resolve_cut_task(task) for task in tasks]
    with ProcessPoolExecutor(max_workers=workers,
                             mp_context=multiprocessing.get_context('spawn')) as pool:
        return list(pool.map(resolve_cut_task, tasks, chunksize=1))


def resolve_panel_task(task):
    from portal.app.lv_n3_panels import resolve
    obra, floor, behavior, beam, side, mode, assembly = task
    started = time.monotonic()
    try:
        result = resolve(obra, floor, behavior, beam, side, mode=mode,
                         assembly=assembly, render=False)
        if not result.get('available') or not Path(result['path']).is_file():
            raise RuntimeError('painel N3 indisponivel')
        return True, result['path'], result['fingerprint'], '', time.monotonic()-started
    except Exception as exc:
        return False, None, None, str(exc), time.monotonic()-started


def run_panel_tasks(tasks, max_workers=1):
    from src.core.cad_render_cache import render_worker_limit
    if not tasks:
        return []
    workers = render_worker_limit(max_workers, len(tasks))
    if workers == 1:
        return [resolve_panel_task(task) for task in tasks]
    with ProcessPoolExecutor(max_workers=workers,
                             mp_context=multiprocessing.get_context('spawn')) as pool:
        return list(pool.map(resolve_panel_task, tasks, chunksize=1))
