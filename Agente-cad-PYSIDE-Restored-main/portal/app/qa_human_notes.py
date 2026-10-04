"""Notas por versão; mantém os contratos existentes de lajes e fundos."""
import json
import os
import re
import tempfile
import threading
from pathlib import Path

from . import fv_operations, laje_operations

LAYERS = ('sa', 'c1', 'c2', 'c3', 'n3')
_LOCK = threading.RLock()


def _path(obra_dir, pavimento, classe, item, behavior):
    if classe not in {'PIL', 'LV'} or behavior not in {'para', 'passa'}:
        raise ValueError('classe ou comportamento inválido')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', value) or value in {'.', '..'}
           for value in (pavimento, item)):
        raise ValueError('identidade inválida')
    return Path(obra_dir) / '.portal_overrides' / 'qa_notes' / classe / pavimento / behavior / (item + '.json')


def load(obra_dir, pavimento, classe, item, behavior='para'):
    if classe == 'FV':
        return fv_operations.load_override(obra_dir, pavimento, item).get('notes') or {}
    if classe == 'LAJ':
        return laje_operations.load_override(obra_dir, pavimento, item).get('notes') or {}
    path = _path(obra_dir, pavimento, classe, item, behavior)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def save(obra_dir, pavimento, classe, item, notes, behavior='para'):
    clean = {key: str(notes.get(key) or '')[:8000] for key in LAYERS}
    if classe == 'FV':
        return fv_operations.save_notes(obra_dir, pavimento, item, clean)
    if classe == 'LAJ':
        return laje_operations.save_notes(obra_dir, pavimento, item, clean)
    path = _path(obra_dir, pavimento, classe, item, behavior)
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.notes-', suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(clean, stream, ensure_ascii=False)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return clean
