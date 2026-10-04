"""Stored DXF references for mode/class frames; never consumed by N3 yet."""
import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path

from scripts import drawing_mode_config as profiles
from .dxf_preview import obter_bbox_dxf, renderizar_dxf_svg

MAX_BYTES = 20 * 1024 * 1024
FRAMES = 'drawing_frames'
LEGENDS = 'drawing_legends'  # "Índices e Legendas": mesmo comportamento da moldura, coleção própria


def directory(mode, cls, collection='drawing_frames'):
    mode = profiles.check_mode(mode)
    cls = profiles.key_for(cls)
    return profiles.storage_path().parent / collection / mode / cls


def metadata(mode, cls, collection=FRAMES):
    root = directory(mode, cls, collection)
    path = root / 'current.json'
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else None


def documents(mode, cls, collection=FRAMES):
    """Keep existing single uploads visible without requiring a migration."""
    path = directory(mode, cls, collection) / 'index.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf8'))
    current = metadata(mode, cls, collection)
    return [current] if current else []


def store(mode, cls, filename, content, collection='drawing_frames'):
    root = directory(mode, cls, collection)
    with profiles.file_lock(root / 'current.json'):
        items = documents(mode, cls, collection) if collection in (FRAMES, LEGENDS) else None
        result = _store(mode, cls, filename, content, collection)
        if items is not None:
            _write_examples(root, items + [result])
        return result


def _store(mode, cls, filename, content, collection):
    if not filename or Path(filename).suffix.lower() != '.dxf':
        raise ValueError('Selecione um documento DXF.')
    if not content or len(content) > MAX_BYTES:
        raise ValueError('O DXF deve ter conteúdo e no máximo 20 MB.')
    root = directory(mode, cls, collection)
    root.mkdir(parents=True, exist_ok=True)
    # Validate and render before changing the current reference. Originals are immutable.
    with tempfile.TemporaryDirectory(dir=root) as temp:
        source = Path(temp) / 'source.dxf'
        source.write_bytes(content)
        try:
            bbox = obter_bbox_dxf(source)
            if bbox is None:
                raise ValueError('O DXF não contém geometria visível no Model Space.')
            svg = renderizar_dxf_svg(source, bbox=bbox, largura_px=1200, altura_px=700)
        except Exception as exc:
            raise ValueError('Não foi possível abrir o DXF. Verifique a geometria no Model Space.') from exc
        token = uuid.uuid4().hex
        source.replace(root / (token + '.dxf'))
        (root / (token + '.svg')).write_bytes(svg)
        result = {'id': token, 'filename': filename.replace('\\', '/').split('/')[-1],
                  'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
        pending = root / (token + '.json')
        pending.write_text(json.dumps(result, ensure_ascii=False), encoding='utf8')
        os.replace(pending, root / 'current.json')
    return result


def preview(mode, cls, token, collection='drawing_frames'):
    if len(token) != 32 or any(char not in '0123456789abcdef' for char in token):
        raise ValueError('Moldura inválida.')
    path = directory(mode, cls, collection) / (token + '.svg')
    return path


def examples(mode, cls):
    path = directory(mode, cls, 'drawing_examples') / 'index.json'
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else []


def _write_examples(root, items):
    pending = root / (uuid.uuid4().hex + '.json')
    pending.write_text(json.dumps(items, ensure_ascii=False), encoding='utf8')
    os.replace(pending, root / 'index.json')


def add_example(mode, cls, filename, content):
    root = directory(mode, cls, 'drawing_examples')
    with profiles.file_lock(root / 'index.json'):
        items = examples(mode, cls)
        if len(items) >= 10:
            raise ValueError('Limite de 10 exemplos por modo e classe. Remova um exemplo antes de enviar outro.')
        result = store(mode, cls, filename, content, 'drawing_examples')
        items.append(result)
        _write_examples(root, items)
    return items


def remove_example(mode, cls, token):
    preview(mode, cls, token, 'drawing_examples')  # validates token
    root = directory(mode, cls, 'drawing_examples')
    with profiles.file_lock(root / 'index.json'):
        items = examples(mode, cls)
        _write_examples(root, [item for item in items if item['id'] != token])
    # Source documents remain immutable; only the displayed list changes.
    return examples(mode, cls)


def remove_frame(mode, cls, token, collection=FRAMES):
    preview(mode, cls, token, collection)  # validates token before touching metadata
    root = directory(mode, cls, collection)
    with profiles.file_lock(root / 'current.json'):
        current = metadata(mode, cls, collection)
        items = documents(mode, cls, collection)
        if not any(item['id'] == token for item in items):
            raise RuntimeError('Documento não encontrado. Atualize a lista antes de remover.')
        remaining = [item for item in items if item['id'] != token]
        _write_examples(root, remaining)
        if current and current['id'] == token:
            if remaining:
                pending = root / (uuid.uuid4().hex + '.json')
                pending.write_text(json.dumps(remaining[-1], ensure_ascii=False), encoding='utf8')
                os.replace(pending, root / 'current.json')
            else:
                (root / 'current.json').unlink(missing_ok=True)
    # Keep uploaded originals intact; remove only the selected listed reference.
    return metadata(mode, cls, collection)


def compact_preview(path, gzip_enabled=False):
    """Derived immutable cache; uploaded SVG/DXF are never replaced."""
    import gzip
    from .svg_compact import compact_svg, VERSION
    cache = path.with_name(path.stem + '.' + VERSION + '.svg')
    zipped = cache.with_suffix('.svg.gz')
    with profiles.file_lock(cache):
        if not cache.exists() or cache.stat().st_mtime_ns < path.stat().st_mtime_ns:
            content = compact_svg(path.read_bytes())
            for target, payload in ((cache,content),(zipped,gzip.compress(content,compresslevel=6))):
                fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.preview-')
                try:
                    with os.fdopen(fd,'wb') as stream: stream.write(payload)
                    os.replace(temp,target)
                finally:
                    Path(temp).unlink(missing_ok=True)
        if gzip_enabled and zipped.exists(): return zipped
    return cache
