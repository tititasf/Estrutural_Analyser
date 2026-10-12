"""Reuse complete N1 packs only when every input and output is unchanged."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import sqlite3
from pathlib import Path

MANIFEST = '.n1_tag_cache.json'
_RANDOM_ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')


def _without_random_ids(value):
    # The SA stamps every link entry with a fresh uuid4 on each run; the
    # exporter never reads it and the pack does not embed it.
    if isinstance(value, dict):
        return {k: _without_random_ids(v) for k, v in value.items()
                if not (k == 'id' and isinstance(v, str) and _RANDOM_ID.fullmatch(v))}
    if isinstance(value, list):
        return [_without_random_ids(v) for v in value]
    return value


def _canonical_cell(cell):
    if isinstance(cell, str) and cell[:1] in '{[':
        try:
            return _without_random_ids(json.loads(cell))
        except ValueError:
            return cell
    return cell


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(settings, obra_dir, obra_name, project_id, pavimento, names):
    """Fail open to regeneration when inputs cannot be fully fingerprinted.

    Database inputs are read in one snapshot, scoped to this project. Renderer
    source, package versions, local convention, published state and approved
    assets are included. No inferred level becomes authority through caching.
    """
    try:
        from src.core.niveis_extractor import get_pavimento_niveis_abs
        repo, root = Path(settings.repo_root), Path(obra_dir)
        db = Path(settings.sa_db_path)
        with sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True) as conn:
            conn.execute('BEGIN')
            project = conn.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchall()
            dxf = conn.execute('SELECT dxf_path FROM projects WHERE id=?', (project_id,)).fetchone()
            if not project or not dxf or not dxf[0]:
                return None
            rows = {'projects': project}
            for table in ('pillars', 'slabs', 'beams'):
                rows[table] = sorted(
                    ([_canonical_cell(cell) for cell in row] for row in conn.execute(
                        f'SELECT * FROM {table} WHERE project_id=?', (project_id,))), key=repr)
        code = {}
        for relative in ('src', 'scripts/arete', 'portal/app'):
            for path in sorted((repo / relative).rglob('*.py')):
                code[path.relative_to(repo).as_posix()] = file_hash(path)
        if not code:
            return None
        approved = root / 'arete_approved'
        assets = {}
        candidates = [approved / f'pilares_tags_{pavimento}.json']
        candidates += sorted((approved / f'pilares_tags_{pavimento}').rglob('*'))
        for path in candidates:
            if path.is_file():
                assets[path.relative_to(root).as_posix()] = file_hash(path)
        snapshot = json.loads((root / f'estado_{pavimento}.json').read_text(encoding='utf-8'))
        # The exporter reads the inventory, not the snapshot creation clock.
        # Keep every other field, including provenance and manual overrides.
        snapshot.pop('gerado_em', None)
        value = dict(version=2, obra_root=str(root.resolve()), obra_name=obra_name,
                     project_id=project_id, pavimento=pavimento, names=sorted(names),
                     snapshot=_without_random_ids(snapshot),
                     dxf=file_hash(dxf[0]), database=rows, code=code, approved=assets,
                     levels=get_pavimento_niveis_abs(obra_name, pavimento) or {},
                     packages={name: importlib.metadata.version(name)
                               for name in ('ezdxf', 'matplotlib', 'numpy')})
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                       default=str).encode()).hexdigest()
    except (OSError, ValueError, sqlite3.Error, importlib.metadata.PackageNotFoundError):
        return None


def _artifacts(pack):
    return {p.relative_to(pack).as_posix(): file_hash(p)
            for p in sorted(pack.rglob('*')) if p.is_file()
            and p.name not in (MANIFEST, MANIFEST + '.tmp')}


def find_pack(output_root, pavimento, key, names):
    if key is None:
        return None
    for pack in sorted(Path(output_root).glob(f'{pavimento}_*_pilares_abcd'), reverse=True):
        try:
            data = json.loads((pack / MANIFEST).read_text(encoding='utf-8'))
            if not isinstance(data, dict) or not isinstance(data.get('stats'), dict):
                continue
            if data.get('key') != key or data.get('names') != sorted(names):
                continue
            if not data.get('artifacts') or data['artifacts'] != _artifacts(pack):
                continue
            return pack, data['stats']
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def record_pack(pack, key, names, stats):
    if key is None:
        return
    pack = Path(pack)
    data = dict(key=key, names=sorted(names), stats=stats, artifacts=_artifacts(pack))
    temporary = pack / (MANIFEST + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding='utf-8')
    temporary.replace(pack / MANIFEST)
