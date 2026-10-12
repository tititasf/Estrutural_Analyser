"""Assemble independent N5 variants in isolated processes.

Registration, approval and SQLite writes stay with the portal caller.
"""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path


def assemble_task(task):
    label, obra_dir, classe, kwargs = task
    from src.core.n5_assembler import assemble_n5
    return label, assemble_n5(obra_dir, classe, **kwargs)


def run_assembly_tasks(tasks, max_workers=3):
    if not tasks:
        return []
    # Every worker owns its output DXF and manifest. Reject collisions before
    # starting any assembly rather than letting two workers overwrite a sheet.
    identities = set()
    from src.core.n5_assembler import _safe_name
    from scripts.visual_modes import normalize_visual_mode
    for _, obra_dir, classe, kwargs in tasks:
        cls = classe.strip().upper()
        mode = normalize_visual_mode(kwargs.get('visual_mode', 'NOVA'))
        group = str(kwargs.get('pillar_group') or '').upper()
        if cls == 'LV' and mode in ('INI', 'NOVA', 'MOLDE_1') and kwargs.get('lateral_assembly'):
            group = f"{kwargs.get('lateral_behavior')}_{kwargs['lateral_assembly']}"
        identity = (str(Path(obra_dir).resolve()), cls,
                    _safe_name(kwargs.get('pavimento') or 'GERAL'), mode, group)
        if identity in identities:
            raise ValueError('Variantes N5 com o mesmo destino')
        identities.add(identity)
    from src.core.cad_render_cache import render_worker_limit
    workers = render_worker_limit(max_workers, len(tasks))
    try:
        values = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
        available = int(values['MemAvailable'].split()[0]) * 1024
        # Unification holds imported drawings plus pagination copies. Peak RSS
        # measured on 13_PAV (2026-10-12): PL 1.5 GB, one LV variant 0.77 GB.
        budget = 1 if all(t[2].strip().upper() == 'LV' for t in tasks) else 2
        workers = min(workers, max(1, (available - 512 * 1024**2) // (budget * 1024**3)))
    except (OSError, KeyError, ValueError):
        pass
    with ProcessPoolExecutor(max_workers=workers,
                             mp_context=multiprocessing.get_context('spawn')) as pool:
        if workers == 1:
            # One child runs the batch: its variants share one read of the
            # effective SA state, and the PL peak (1.9 GB on 13_PAV) leaves
            # with the child instead of staying in the caller's heap.
            return pool.submit(assemble_serial, tasks).result()
        return list(pool.map(assemble_task, tasks, chunksize=1))


def assemble_serial(tasks):
    try:
        from portal.app.ficha_reader import estado_compartilhado
    except ImportError:
        from contextlib import nullcontext as estado_compartilhado
    with estado_compartilhado():
        return [assemble_task(task) for task in tasks]
