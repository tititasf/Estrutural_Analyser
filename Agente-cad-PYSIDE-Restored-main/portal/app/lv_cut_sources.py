"""Fontes de corte limitadas ao projeto/tower do snapshot, somente leitura."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from functools import lru_cache

from src.core.lv_cut_inventory import collect_explicit_cuts


@lru_cache(maxsize=4)
def _red_strokes(path, revision):
    import ezdxf
    document = ezdxf.readfile(path)
    rows = []
    for entity in document.modelspace().query('LINE'):
        color = entity.dxf.color
        if color == 256:
            color = document.layers.get(entity.dxf.layer).dxf.color
        if abs(color) == 1:
            rows.append(dict(start=list(entity.dxf.start)[:2],end=list(entity.dxf.end)[:2],
                             aci=1,handle=entity.dxf.handle))
    return rows


@lru_cache(maxsize=4)
def _dimension_labels(path, revision):
    import re
    import ezdxf
    document = ezdxf.readfile(path)
    result = []
    for entity in document.modelspace().query('TEXT MTEXT'):
        value = entity.dxf.text if entity.dxftype() == 'TEXT' else entity.plain_text()
        if re.fullmatch(r'\s*\d+(?:[.,]\d+)?\s*/\s*\d+(?:[.,]\d+)?\s*', value):
            result.append(dict(text=value,pos=list(entity.dxf.insert)[:2],handle=entity.dxf.handle))
    return result


def load_sources(obra_dir, floor, state, records):
    slabs = state.get('slabs') or []
    project_ids = {r.get('project_id') for r in records.values() if r.get('project_id')}
    db_path = Path(str(state.get('db_path') or ''))
    source_dxf = None
    if db_path.is_file() and len(project_ids) == 1:
        with sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro', uri=True) as db:
            pid = next(iter(project_ids))
            columns = {r[1] for r in db.execute('PRAGMA table_info(slabs)')}
            if {'name','project_id','links_json','extra_data_json','points_json'} <= columns:
                snapshot = {s['name']: s for s in slabs}
                full = []
                for name, links, extra, points in db.execute(
                    'SELECT name,links_json,extra_data_json,points_json FROM slabs WHERE project_id=?', (pid,)):
                    base = {**json.loads(extra or '{}'), 'name':name, 'points':json.loads(points or '[]'),
                            'links':json.loads(links or '{}')}
                    base.update({k:v for k,v in snapshot.get(name,{}).items() if v not in (None,'',[],{})})
                    full.append(base)
                slabs = full or slabs
            columns = {r[1] for r in db.execute('PRAGMA table_info(projects)')}
            if {'id','dxf_path'} <= columns:
                row = db.execute('SELECT dxf_path FROM projects WHERE id=?',(pid,)).fetchone()
                source_dxf = Path(row[0]).resolve() if row and row[0] else None
    preprocessing = []
    receipt = {'status':'absent', 'items':0}
    if source_dxf:
        from .preprocessamento.service import read_floor, read_tower
        from .preprocessamento.freshness import changed_sources
        floor_data = read_floor(Path(obra_dir).resolve(), floor)
        if floor_data:
            matching = [s for s in floor_data['sources'] if s['kind']=='tower'
                        and (Path(obra_dir)/s['relative_path']).resolve()==source_dxf]
            if len(matching)==1:
                package = read_tower(obra_dir, floor_data, matching[0]['source_id'])
                receipt = {'status':'stale' if changed_sources(Path(obra_dir), package['sources']) else package['status'],
                           'run_id':package['run_id'], 'source_id':matching[0]['source_id'], 'items':0}
                if receipt['status'] in {'partial','complete'}:
                    preprocessing = (package.get('cuts') or {}).get('items') or []
                    receipt['items']=len(preprocessing)
    cuts = collect_explicit_cuts(state.get('cortes') or [], slabs, preprocessing)
    lines = []
    if source_dxf and source_dxf.is_file():
        stat = source_dxf.stat()
        lines = _red_strokes(str(source_dxf), (stat.st_mtime_ns,stat.st_size))
        receipt['dimension_labels'] = _dimension_labels(str(source_dxf), (stat.st_mtime_ns,stat.st_size))
    from src.core.beam_vertical_context import enrich_originals
    cuts = enrich_originals(cuts, lines)
    return slabs, cuts, receipt
