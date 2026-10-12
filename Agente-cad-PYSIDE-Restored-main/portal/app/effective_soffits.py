"""Revision-scoped derived FV geometry; source SA artifacts are never changed."""
import json
from copy import deepcopy
from functools import lru_cache, wraps
from pathlib import Path
from threading import Lock


def _singleflight(cached):
    """Share a cold calculation, while allowing unrelated revisions to run.

    lru_cache alone permits concurrent misses to compute the same geometry.
    Keep each lock until its last waiter exits; failures remain retryable.
    """
    guard = Lock()
    pending = {}

    @wraps(cached)
    def shared(*args):
        with guard:
            entry = pending.setdefault(args, [Lock(), 0])
            entry[1] += 1
        try:
            with entry[0]:
                return cached(*args)
        finally:
            with guard:
                entry[1] -= 1
                if entry[1] == 0:
                    del pending[args]

    shared.cache_clear = cached.cache_clear
    shared.cache_info = cached.cache_info
    return shared


@_singleflight
@lru_cache(maxsize=2)
def _effective(root, floor, source, revision, database_revision, serialized, protected_uids):
    from .structural_cut_overlay import collect_sections
    from src.core.fv_inverted_crossings import reconcile_state, structural_lines_from_dxf
    from src.core.lv_inverted_crossings import reconcile_state as reconcile_laterals
    state=json.loads(serialized)
    lines=structural_lines_from_dxf(source,revision)
    from src.core.lv_section_dividers import reconcile_section_dividers
    state=reconcile_section_dividers(state,lines,protected_uids)
    inventory=collect_sections(Path(root),floor,state)
    result=reconcile_state(state,inventory,lines,protected_uids)
    result=reconcile_laterals(result,inventory,lines,protected_uids)
    result['_current_beam_sections']=inventory
    return result


def apply_state(state, root, floor, source):
    if not (state.get('segmentos') or {}).get('fundo'):
        return state
    source=Path(source)
    stat=source.stat()
    database=Path(str(state.get('db_path') or ''))
    database_revision=(database.stat().st_mtime_ns,database.stat().st_size) if database.is_file() else None
    from .item_geometry import load
    custom=load(Path(root),floor)
    protected=tuple(sorted({uid for kind in ('edits','created')
        for group,items in (custom.get(kind) or {}).items()
        if group=='fundo' or group.startswith('lateral') for uid in items}))
    return deepcopy(_effective(str(root),floor,str(source),(stat.st_mtime_ns,stat.st_size),
                               database_revision,json.dumps(state,sort_keys=True,ensure_ascii=False),protected))
