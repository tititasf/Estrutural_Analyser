"""Draw immutable SA pillar payloads in isolated processes, without Qt or DB."""
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
from pathlib import Path
import shutil
import sys
import time


ZONES = ('cima', 'abcd', 'grades')


def draw_pillar_task(task):
    label, payload, variant_dir, visual_mode, destinations = task
    started = time.monotonic()
    paths = {}
    try:
        scripts = str(Path(__file__).resolve().parents[2] / 'scripts')
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from gerar_pl_dxf_stog import setup_doc, generate_pilar_zone
        # Register drawing instrumentation before creating the first document.
        # Otherwise setup_doc() depends on whether this process drew a previous
        # pillar (the generator wraps its helpers on its first drawing call).
        import gerar_pl_dxf_stog
        from scripts.drawing_semantics import instrument, LayoutProxy
        instrument(vars(gerar_pl_dxf_stog), 'PL')
        generate_pilar_zone = gerar_pl_dxf_stog.generate_pilar_zone
        from visual_modes import apply_visual_mode, normalize_visual_mode
        mode = normalize_visual_mode(visual_mode)
        variant_dir = Path(variant_dir)
        item = label.rsplit('_', 1)[0]
        for zone in ZONES:
            # The generator mutates its payload. Each zone receives the same
            # independent JSON copy used by the original sequential caller.
            zone_payload = json.loads(json.dumps(payload))
            doc = setup_doc()
            LayoutProxy(doc.modelspace(), 'PL')
            count = generate_pilar_zone(doc.modelspace(), zone_payload, zone, visual_mode=mode)
            if count < 0:
                raise RuntimeError(f'zona {zone} indisponivel')
            # A complete task must not silently fall back to four faces when
            # the immutable input contains a physical eight-face U contour.
            from src.core.pillar_u_nova_contract import u_nova_payload, n3_u_faces
            if u_nova_payload(zone_payload):
                expected = {row['id'] for row in n3_u_faces(zone_payload, grades_only=zone == 'grades')}
                texts = {e.dxf.text for e in doc.modelspace().query('TEXT')}
                required = expected if zone == 'cima' else {f'{zone_payload.get("nome") or "?"}.{face}' for face in expected}
                if not required <= texts:
                    raise RuntimeError(f'U {zone}: missing required faces {sorted(required-texts)}')
            apply_visual_mode(doc, mode, 'PL')
            path = variant_dir / f'PL_{zone.upper()}_preview_{item}.dxf'
            doc.saveas(path)
            paths[zone] = str(path)
        # Publish only complete variants; workers never share a DXF document.
        for destination in destinations:
            destination = Path(destination)
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(variant_dir / f'{item}.json', destination / f'{item}.json')
            for path in paths.values():
                shutil.copy2(path, destination / Path(path).name)
        return label, paths, '', time.monotonic() - started
    except Exception as exc:
        return label, {}, str(exc), time.monotonic() - started


def run_pillar_tasks(tasks, max_workers=1):
    if not tasks:
        return []
    from src.core.cad_render_cache import render_worker_limit
    # Peak RSS of one spawned N3 worker on 13_PAV (2026-10-12): 106-138 MB.
    workers = render_worker_limit(max_workers, len(tasks), worker_bytes=384 * 1024**2)
    if workers == 1:
        return [draw_pillar_task(task) for task in tasks]
    with ProcessPoolExecutor(max_workers=workers,
                             mp_context=multiprocessing.get_context('spawn')) as pool:
        return list(pool.map(draw_pillar_task, tasks, chunksize=1))
