"""Revision-scoped derived FV geometry; source SA artifacts are never changed."""
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=2)
def _effective(root, floor, source, revision, database_revision, serialized, protected_uids):
    from .structural_cut_overlay import collect_sections
    from src.core.fv_inverted_crossings import reconcile_state, structural_lines_from_dxf
    state=json.loads(serialized)
    inventory=collect_sections(Path(root),floor,state)
    result=reconcile_state(state,inventory,structural_lines_from_dxf(source,revision),protected_uids)
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
    protected=tuple(sorted(set((custom.get('edits') or {}).get('fundo') or {}) |
                           set((custom.get('created') or {}).get('fundo') or {})))
    return deepcopy(_effective(str(root),floor,str(source),(stat.st_mtime_ns,stat.st_size),
                               database_revision,json.dumps(state,sort_keys=True,ensure_ascii=False),protected))
