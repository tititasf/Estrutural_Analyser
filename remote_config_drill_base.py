"""Persistent drawing profiles. No Qt, no source DXF or Fase-4 mutation.

Only overrides are applied: opening/saving unchanged settings preserves the
existing generator. Legacy fields without a headless equivalent are read-only.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import functools
import inspect
from contextvars import ContextVar

ROOT = Path(__file__).resolve().parents[1]
CLASSES = {'PL': 'Pilares', 'LV_PARA': 'Laterais Para', 'LV_PASSA': 'Laterais Passa', 'FV': 'Fundos de viga', 'LJ': 'Lajes'}
MODES = ('INI', 'NOVA', 'MOLDE_1', 'MOLDE_2', 'MOLDE_3')
MODE_LABELS = {'INI': 'Modo iNI', 'NOVA': 'Modo Nova', 'MOLDE_1': 'Modo Molde 1', 'MOLDE_2': 'Modo Molde 2', 'MOLDE_3': 'Modo Molde 3'}
LOCK = threading.RLock()
GENERATION_STORE = ContextVar('drawing_generation_store', default=None)
CATALOG_CURRENT = ContextVar('drawing_catalog_current', default=None)
MOTOR_CONSTANTS = {
    'PL': ('FACE_SPACING', 'ZONE_ABCD_X', 'ZONE_CIMA_X', 'ZONE_GRADES_X'),
    'LV': ('NOM_H', 'NOM_ABOVE', 'PID_H', 'DIM_BELOW', 'DIM_TOTAL_BELOW', 'DIM_H_RIGHT', 'GAP_ROW_LV', 'GAP_AB', 'LV_UNIT_GAP', 'LV_SARR_INSET', 'SARR_INSET_H', 'SECT_GAP', 'DRAW_HATCHES_LAJE', 'DRAW_HATCHES_PAINEL'),
    'FV': ('NOM_ABOVE', 'NOM_H', 'LABEL_ABOVE', 'LABEL_H', 'DIM_BELOW', 'DIM_TOTAL_BELOW', 'TIER_STEP', 'DIM_B_RIGHT', 'PID_H', 'GAP_VIGAS', 'GAP_ROW', 'SARR_RECUO', 'SARR_MAX_GAP', 'SARR_MAX_LEN'),
    'LJ': ('DIM_HORIZONTAL_OFFSET_CM', 'DIM_VERTICAL_OFFSET_CM', 'GAP_X', 'GAP_Y', 'PAD', 'TITULO_H', 'CARIMBO_H', 'SARRAFO_GAP', 'PILAR_HATCH_STEP'),
}
COMPONENTS = {'paineis': 'Painéis', 'sarrafos': 'Sarrafos', 'cotas': 'Cotas', 'textos': 'Textos e nomes', 'hachuras': 'Hachuras', 'metal': 'Perfis e gravatas', 'carimbo': 'Folhas e carimbo'}


def storage_path():
    return Path(os.environ.get('ARETE_DRAWING_MODE_CONFIG', str(ROOT / 'portal_runtime/drawing_mode_settings.json')))


def key_for(robot_class, behavior=None):
    cls = str(robot_class).upper()
    if cls == 'LV':
        if behavior is None:
            return 'LV_PARA'
        b = str(behavior).upper()
        if b not in {'PARA', 'PASSA'}:
            raise ValueError('Comportamento de lateral inválido')
        return 'LV_' + b
    if cls not in CLASSES:
        raise ValueError('Classe inválida')
    return cls


def check_mode(mode):
    value = str(mode).upper()
    if value not in MODES:
        raise ValueError('Modo inválido')
    return value


def read_store():
    path = storage_path()
    value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'schema_version': 1, 'revision': 0, 'profiles': {}}
    if value.get('schema_version') != 1 or not isinstance(value.get('profiles'), dict):
        raise ValueError('Arquivo de configuração de modos inválido')
    for mode in MODES[2:]:
        value['profiles'].setdefault(mode, deepcopy(value['profiles'].get('NOVA', {})))
    return value


def overrides(mode, cls):
    store = GENERATION_STORE.get() or read_store()
    return deepcopy(store['profiles'].get(check_mode(mode), {}).get(key_for(cls), {}))


@functools.lru_cache(maxsize=8)
def _motor_tree(source):
    return ast.parse(source)


def motor_literals(cls):
    cls = cls.split('_')[0]
    path = ROOT / 'scripts' / f'gerar_{cls.lower()}_dxf_stog.py'
    tree = _motor_tree(path.read_text(encoding='utf-8-sig'))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    layers = next(node.value for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'LAYERS' for t in node.targets))
    result = {}
    for k, v in zip(layers.keys, layers.values):
        name = values[k.id] if isinstance(k, ast.Name) else ast.literal_eval(k)
        result[name] = ast.literal_eval(v)
    return result, {k: values[k] for k in MOTOR_CONSTANTS[cls] if k in values}


def motor_blocks(cls):
    source = (ROOT / 'scripts' / f'gerar_{cls.split("_")[0].lower()}_dxf_stog.py').read_text(encoding='utf-8-sig')
    tree = _motor_tree(source)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'add_blockref' and node.args:
            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                names.add(node.args[0].value)
    return {name: True for name in sorted(names)}


def current_catalog():
    """Observed output of current generators; never substitute legacy presets."""
    snapshot = CATALOG_CURRENT.get()
    if snapshot is not None:
        return deepcopy(snapshot)
    path = ROOT / 'config/drawing_mode_current_catalog.json'
    data = json.loads(path.read_text(encoding='utf8')) if path.exists() else {'modes': {}, 'sources': {}, 'contracts': []}
    data['verified'] = bool(data['sources']) and all(
        (ROOT/name).exists() and hashlib.sha256((ROOT/name).read_text(encoding='utf8').encode()).hexdigest() == digest
        for name, digest in data['sources'].items())
    return data


def populate_current(value, mode, cls):
    catalog = current_catalog()
    measured = catalog.get('modes', {}).get(mode, {}).get(cls, {}) if catalog['verified'] else {}
    for group in ('texts', 'hatches', 'dimensions'):
        for role, options in value[group].items():
            actual = measured.get(group, {}).get(role, {})
            for key in options:
                # scale/arrow_scale are relative multipliers, not DXF values.
                observations = actual.get(key, [])
                if len(observations) == 1 and key not in {'scale', 'arrow_scale', 'enabled'}:
                    options[key] = observations[0]
    for name, observations in measured.get('layers',{}).items():
        if name not in value['layers']: continue
        colors=observations.get('color',[])
        if len(colors)==1 and 1 <= colors[0] <= 255: value['layers'][name]['color']=colors[0]
        for field, key in [('linetype','entity_linetype'),('hatch_pattern','hatch_pattern')]:
            values=observations.get(key,[])
            allowed={'CONTINUOUS','DASHED','HIDDEN','CENTER'} if field=='linetype' else {'SOLID','ANSI31','ANSI32','AR-CONC'}
            if len(values)==1 and values[0] in allowed: value['layer_styles'][name][field]=values[0]
    return value


def defaults(mode, cls):
    mode = check_mode(mode)
    cls = key_for(cls)
    layers, constants = motor_literals(cls)
    # Settings describe the final profile, after the existing Ini conversion.
    from scripts.visual_modes import _INI_LAYER_MAP, _LEGACY_COLORS
    mapping = _INI_LAYER_MAP.get(cls.split('_')[0], {}) if mode == 'INI' else {}
    final_layers = {}
    for name, color in layers.items():
        target = mapping.get(name.casefold(), name)
        final_layers.setdefault(target, {'name': target, 'color': _LEGACY_COLORS.get(target, color) if mode == 'INI' else color, 'enabled': True})
    value = {
        'components': {key: True for key in COMPONENTS},
        'layers': final_layers,
        'layout': constants,
        'appearance': {'text_scale': 1.0, 'dimension_scale': 1.0, 'hatch_scale': 1.0, 'hatch_angle': 45.0},
        'blocks': motor_blocks(cls),
        'layer_styles': {name: {'linetype': 'PRESERVAR', 'hatch_pattern': 'PRESERVAR'} for name in final_layers},
    }
    from scripts.drawing_semantics import schema
    roles = schema(cls)
    value['view_components'] = {view: {key: True for key in COMPONENTS} for view in roles['views']}
    value['texts'] = {key: {'enabled': True, 'scale': 1.0, 'color': 0, 'style': 'PRESERVAR', 'rotation': 999.0} for key in roles['texts']}
    value['hatches'] = {key: {'enabled': True, 'scale': 1.0, 'color': 0, 'pattern': 'PRESERVAR', 'angle': 999.0} for key in roles['hatches']}
    value['dimensions'] = {key: {'enabled': True, 'scale': 1.0, 'arrow_scale': 1.0, 'color': 0, 'style': 'PRESERVAR', 'precision': -1, 'gap': -1.0} for key in roles['dimensions']}
    for options in value['texts'].values(): options['height'] = -1.0
    for options in value['hatches'].values(): options['pattern_scale'] = -1.0
    for options in value['dimensions'].values(): options.update(text_height=-1.0, arrow_size=-1.0)
    value['special'] = {'sarrafo_representation': 'PADRAO', 'bylayer': 'PADRAO'}
    value['human_notes'] = ''
    if cls == 'PL':
        from scripts.pl_grade_visual_config import positions_for_mode
        value['grade_positions_cm'] = positions_for_mode('NOVA' if mode.startswith('MOLDE_') else mode)
    return populate_current(value, mode, cls)


def merge(base, updates):
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge(base[key], value)
        else:
            base[key] = deepcopy(value)
    return base


def effective(mode, cls):
    return merge(defaults(mode, cls), overrides(mode, cls))


def leaf_diff(base, value):
    result = {}
    for key, current in value.items():
        if isinstance(current, dict):
            child = leaf_diff(base[key], current)
            if child:
                result[key] = child
        elif current != base[key]:
            result[key] = current
    return result


def validate(mode, cls, value):
    base = defaults(mode, cls)
    if not isinstance(value, dict) or set(value) != set(base):
        raise ValueError('Campos de configuração ausentes ou desconhecidos')
    for group in ('components', 'layers', 'layout', 'appearance', 'blocks', 'layer_styles'):
        if not isinstance(value[group], dict) or set(value[group]) != set(base[group]):
            raise ValueError(f'Campos inválidos: {group}')
    for group in ('view_components','texts','hatches','dimensions','special'):
        if not isinstance(value[group],dict) or set(value[group]) != set(base[group]):
            raise ValueError(f'Campos inválidos: {group}')
    for view, components in value['view_components'].items():
        if set(components) != set(COMPONENTS) or any(type(v) is not bool for v in components.values()): raise ValueError('Componentes por vista inválidos')
    for group in ('texts','hatches','dimensions'):
        for role, options in value[group].items():
            if not isinstance(options,dict) or set(options) != set(base[group][role]): raise ValueError(f'Campos inválidos: {role}')
            for key, item in options.items():
                if key == 'enabled':
                    if type(item) is not bool: raise ValueError('Inclusão inválida')
                elif key in {'scale','arrow_scale'}:
                    if type(item) not in (int,float) or not math.isfinite(item) or not .05 <= item <= 20: raise ValueError('Escala deve estar entre 0,05 e 20')
                elif key == 'color':
                    if type(item) is not int or not 0 <= item <= 256: raise ValueError('Cor deve ser ACI 0 (preservar) a 256 (ByLayer)')
                elif key == 'pattern':
                    if not isinstance(item,str) or not item.strip() or len(item)>120 or any(c in item for c in '<>/\\":;?*|=\n\r'): raise ValueError('Hachura inválida')
                elif key == 'style':
                    if not isinstance(item,str) or not item.strip() or len(item)>120 or any(c in item for c in '<>/\\":;?*|=\n\r'): raise ValueError('Estilo inválido')
                elif type(item) not in (int,float) or not math.isfinite(item) or abs(item)>1000: raise ValueError('Valor numérico inválido')
                elif key in {'height','pattern_scale','text_height','arrow_size'} and item != -1 and item <= 0: raise ValueError('Use um valor positivo ou -1 para manter a variação atual')
            if group == 'dimensions' and (type(options['precision']) is not int or not -1 <= options['precision'] <= 8 or not -1 <= options['gap'] <= 100): raise ValueError('Precisão/afastamento de cota inválido')
    if value['special']['sarrafo_representation'] not in {'PADRAO','LINE','MLINE'} or value['special']['bylayer'] not in {'PADRAO','SIM','NAO'}: raise ValueError('Detalhe especial inválido')
    if not isinstance(value['human_notes'],str) or len(value['human_notes'])>20000: raise ValueError('Anotações: limite de 20.000 caracteres')
    for name, enabled in value['components'].items():
        if type(enabled) is not bool:
            raise ValueError(f'{name}: esperado sim/não')
    for name, enabled in value['blocks'].items():
        if type(enabled) is not bool:
            raise ValueError(f'Bloco {name}: esperado sim/não')
    for name, style in value['layer_styles'].items():
        if not isinstance(style, dict) or set(style) != {'linetype', 'hatch_pattern'}:
            raise ValueError(f'Estilo inválido: {name}')
        if style['linetype'] not in {'PRESERVAR', 'CONTINUOUS', 'DASHED', 'HIDDEN', 'CENTER'}:
            raise ValueError(f'Tipo de linha inválido: {name}')
        if style['hatch_pattern'] not in {'PRESERVAR', 'SOLID', 'ANSI31', 'ANSI32', 'AR-CONC'}:
            raise ValueError(f'Hachura inválida: {name}')
    for source, layer in value['layers'].items():
        if not isinstance(layer, dict) or set(layer) != {'name', 'color', 'enabled'}:
            raise ValueError(f'Layer inválido: {source}')
        if not isinstance(layer['name'], str) or not layer['name'].strip() or len(layer['name']) > 120 or any(c in layer['name'] for c in '<>/\\":;?*|=\n\r'):
            raise ValueError(f'Nome de layer inválido: {source}')
        if type(layer['color']) is not int or not 1 <= layer['color'] <= 255 or type(layer['enabled']) is not bool:
            raise ValueError(f'Cor/visibilidade inválida: {source}')
    # Renaming to another source layer makes subsequent profile semantics ambiguous.
    names = [layer['name'].casefold() for layer in value['layers'].values()]
    if len(set(names)) != len(names):
        raise ValueError('Cada layer deve ter um nome distinto')
    for group in ('layout', 'appearance'):
        for key, number in value[group].items():
            if group == 'layout' and type(base[group][key]) is bool:
                if type(number) is not bool:
                    raise ValueError(f'{key}: esperado sim/não')
                continue
            if type(number) not in (int, float) or not math.isfinite(number) or abs(number) > 50000:
                raise ValueError(f'Valor numérico inválido: {key}')
            if group == 'appearance' and key.endswith('_scale') and not 0.05 <= number <= 20:
                raise ValueError(f'{key}: use um fator entre 0,05 e 20')
            if group == 'layout' and not key.startswith('ZONE_') and number <= 0:
                raise ValueError(f'{key}: valor deve ser positivo')
    if 'grade_positions_cm' in value:
        from scripts.pl_grade_visual_config import validate_positions
        value['grade_positions_cm'] = validate_positions(value['grade_positions_cm'])
    return leaf_diff(base, value)


@contextmanager
def file_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with LOCK, open(str(path) + '.lock', 'a+b') as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def save(mode, cls, value, expected_revision, actor):
    mode, cls = check_mode(mode), key_for(cls)
    delta = validate(mode, cls, value)
    path = storage_path()
    with file_lock(path):
        store = read_store()
        if type(expected_revision) is not int or store['revision'] != expected_revision:
            raise RuntimeError('Configuração alterada por outro usuário. Reabra antes de salvar.')
        store['profiles'].setdefault(mode, {})[cls] = delta
        store['revision'] += 1
        from datetime import datetime, timezone
        store['updated_at'] = datetime.now(timezone.utc).isoformat()
        store['updated_by'] = str(actor)
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.drawing-', suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(store, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)
    return store['revision']


def catalog():
    legacy = json.loads((ROOT / 'config/drawing_mode_legacy_catalog.json').read_text(encoding='utf-8'))
    # Snapshot clones once: later Nova edits never leak into the three Moldes.
    with file_lock(storage_path()):
        store = read_store()
        raw = json.loads(storage_path().read_text(encoding='utf8')) if storage_path().exists() else {}
        if any(mode not in raw.get('profiles',{}) for mode in MODES[2:]):
            fd, temp = tempfile.mkstemp(dir=storage_path().parent, prefix='.modes-', suffix='.json')
            with os.fdopen(fd,'w',encoding='utf8') as out: json.dump(store,out,ensure_ascii=False,indent=2)
            os.replace(temp,storage_path())
    from scripts.drawing_semantics import schema
    measured = current_catalog()
    token = CATALOG_CURRENT.set(measured)
    store_token = GENERATION_STORE.set(store)
    try:
        return {
            'revision': store['revision'], 'scope': 'global', 'classes': CLASSES,
            'components': COMPONENTS, 'legacy': legacy, 'mode_labels': MODE_LABELS,
            'roles': {cls: schema(cls) for cls in CLASSES},
            'current': measured,
            'modes': {mode: {cls: effective(mode, cls) for cls in CLASSES} for mode in MODES},
        }
    finally:
        CATALOG_CURRENT.reset(token)
        GENERATION_STORE.reset(store_token)


@contextmanager
def configured_motor(namespace, mode, cls):
    """Scoped constants for in-process PL; subprocess robots configure once."""
    from scripts.drawing_semantics import instrument
    instrument(namespace,cls)
    values = overrides(mode, cls).get('layout', {})
    with LOCK:
        old = {key: namespace[key] for key in values}
        namespace.update(values)
        try:
            yield
        finally:
            namespace.update(old)


def configure_subprocess(namespace, mode, cls):
    from scripts.drawing_semantics import instrument
    instrument(namespace,cls)
    GENERATION_STORE.set(read_store())
    namespace.update(overrides(mode, cls).get('layout', {}))


def configured_function(cls):
    def decorate(function):
        signature = inspect.signature(function)
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            mode = bound.arguments.get('visual_mode', 'NOVA')
            msp = bound.arguments.get('msp')
            doc = msp.doc if msp is not None else None
            snapshot = getattr(doc, '_drawing_mode_config_store', None) or GENERATION_STORE.get() or read_store()
            if doc is not None:
                doc._drawing_mode_config_store = snapshot
            token = GENERATION_STORE.set(snapshot)
            try:
                with configured_motor(function.__globals__, mode, cls):
                    return function(*args, **kwargs)
            finally:
                GENERATION_STORE.reset(token)
        return wrapped
    return decorate


def grade_positions(mode):
    return overrides(mode, 'PL').get('grade_positions_cm')


def category(entity):
    layer = str(entity.dxf.get('layer', '0')).casefold()
    kind = entity.dxftype()
    if kind == 'DIMENSION':
        return 'cotas'
    if layer in {'folhas', 'carimbo'}:
        return 'carimbo'
    if kind in {'TEXT', 'MTEXT', 'ATTRIB'}:
        return 'textos'
    if 'sarr' in layer or layer == 'madeira':
        return 'sarrafos'
    if kind == 'HATCH':
        return 'hachuras'
    if 'cota' in layer:
        return 'cotas'
    if any(word in layer for word in ('gravata', 'perfil', 'metal', 'tensor', 'presilha', 'forcador')):
        return 'metal'
    if any(word in layer for word in ('pain', 'chapa')):
        return 'paineis'
    return None


def apply_config(doc, mode, robot_class, behavior=None):
    cls = key_for(robot_class, behavior)
    store = getattr(doc, '_drawing_mode_config_store', None) or GENERATION_STORE.get() or read_store()
    delta = deepcopy(store['profiles'].get(check_mode(mode), {}).get(cls, {}))
    if not delta:
        return {'changed': 0, 'removed': 0}
    changed = removed = 0
    components = delta.get('components', {})
    layer_changes = delta.get('layers', {})
    appearance = delta.get('appearance', {})
    block_changes = delta.get('blocks', {})
    styles = delta.get('layer_styles', {})
    from scripts.drawing_semantics import roles
    for style in styles.values():
        name = style.get('linetype', 'PRESERVAR')
        if name not in {'PRESERVAR', 'CONTINUOUS'} and name not in doc.linetypes:
            patterns = {'DASHED': [1.0, .6, -.4], 'HIDDEN': [.5, .25, -.25], 'CENTER': [2.0, 1.2, -.3, .2, -.3]}
            doc.linetypes.add(name, pattern=patterns[name])
    # Copy each changed layer first; entities are mapped simultaneously (no cascade).
    for source, config in layer_changes.items():
        target = config.get('name', source)
        if target not in doc.layers:
            old = doc.layers.get(source) if source in doc.layers else None
            doc.layers.new(target, dxfattribs={'color': old.dxf.color if old else 7})
        if 'color' in config:
            doc.layers.get(target).dxf.color = config['color']
    layouts = [doc.modelspace()] + [block for block in doc.blocks if not block.name.startswith('*')]
    for layout in layouts:
        for entity in list(layout):
            source = str(entity.dxf.get('layer', '0'))
            layer = layer_changes.get(source, {})
            component = category(entity)
            role = roles(entity)
            view, family, name = role if role and len(role)==3 else ('','','')
            if family == 'dimensions':
                component = 'cotas'
            options = delta.get(family, {}).get(name, {})
            view_disabled = delta.get('view_components',{}).get(view,{}).get(component) is False
            block_disabled = entity.dxftype() == 'INSERT' and block_changes.get(entity.dxf.name) is False
            if components.get(component) is False or layer.get('enabled') is False or block_disabled or view_disabled or options.get('enabled') is False:
                layout.delete_entity(entity)
                removed += 1
                continue
            if 'name' in layer:
                entity.dxf.layer = layer['name']
                changed += 1
            if 'color' in layer:
                if entity.dxf.is_supported('color'):
                    entity.dxf.color = 256
                if entity.dxf.hasattr('true_color'):
                    entity.dxf.discard('true_color')
                changed += 1
            kind = entity.dxftype()
            bylayer = delta.get('special',{}).get('bylayer','PADRAO')
            if bylayer != 'PADRAO' and entity.dxf.is_supported('color'):
                entity.dxf.color = 256 if bylayer == 'SIM' else doc.layers.get(entity.dxf.layer).dxf.color
                entity.dxf.discard('true_color')
            if options.get('color',0):
                entity.dxf.color = options['color']
                entity.dxf.discard('true_color')
                changed += 1
            if family == 'texts':
                attr = 'char_height' if kind == 'MTEXT' else 'height'
                if options.get('height',-1)>0: setattr(entity.dxf,attr,options['height']); changed += 1
                if 'scale' in options: setattr(entity.dxf,attr,getattr(entity.dxf,attr)*options['scale']); changed += 1
                if options.get('rotation',999) != 999: entity.dxf.rotation = options['rotation']; changed += 1
                text_style = options.get('style','PRESERVAR')
                if text_style != 'PRESERVAR':
                    if text_style not in doc.styles: doc.styles.new(text_style,dxfattribs={'font':'txt'})
                    entity.dxf.style = text_style; changed += 1
            if family == 'hatches' and kind == 'HATCH':
                pattern = options.get('pattern','PRESERVAR')
                if pattern == 'SOLID': entity.set_solid_fill(color=entity.dxf.color)
                elif pattern != 'PRESERVAR': entity.set_pattern_fill(pattern,scale=entity.dxf.pattern_scale or 1,angle=entity.dxf.pattern_angle)
                if not entity.dxf.solid_fill:
                    if options.get('pattern_scale',-1)>0: entity.set_pattern_scale(options['pattern_scale'])
                    if 'scale' in options: entity.set_pattern_scale(entity.dxf.pattern_scale * options['scale'])
                    if options.get('angle',999) != 999: entity.set_pattern_angle(options['angle'])
                if options: changed += 1
            if family == 'dimensions':
                if kind == 'DIMENSION' and options:
                    style_name = options.get('style','PRESERVAR')
                    if style_name != 'PRESERVAR':
                        if style_name not in doc.dimstyles:
                            original_style = doc.dimstyles.get(entity.dxf.dimstyle)
                            doc.dimstyles.duplicate_entry(original_style.dxf.name,style_name)
                        entity.dxf.dimstyle = style_name
                    dim = entity.override()
                    updates = {}
                    for key, factor in [('dimtxt',options.get('scale')),('dimasz',options.get('arrow_scale'))]:
                        if factor is not None:
                            base = dim.get(key)
                            if base is None: base = doc.dimstyles.get(entity.dxf.dimstyle).dxf.get(key,2.5)
                            updates[key] = base * factor
                    for field, key in [('text_height','dimtxt'),('arrow_size','dimasz')]:
                        if options.get(field,-1)>0: updates[key] = options[field] * options.get('scale' if field=='text_height' else 'arrow_scale',1)
                    if options.get('precision',-1) >= 0: updates['dimdec'] = options['precision']
                    if options.get('gap',-1) >= 0: updates['dimgap'] = options['gap']
                    if options.get('color',0): updates.update({key:options['color'] for key in ('dimclrd','dimclre','dimclrt')})
                    dim.update(updates); dim.render(); changed += 1
                elif kind in {'TEXT','MTEXT'} and ('scale' in options or options.get('text_height',-1)>0):
                    attr = 'char_height' if kind == 'MTEXT' else 'height'
                    setattr(entity.dxf,attr,options.get('text_height') if options.get('text_height',-1)>0 else getattr(entity.dxf,attr))
                    setattr(entity.dxf,attr,getattr(entity.dxf,attr)*options.get('scale',1)); changed += 1
                if kind in {'TEXT','MTEXT'}:
                    text_style = options.get('style','PRESERVAR')
                    if text_style != 'PRESERVAR':
                        if text_style not in doc.styles: doc.styles.new(text_style,dxfattribs={'font':'txt'})
                        entity.dxf.style = text_style
                    if options.get('precision',-1) >= 0 and kind == 'TEXT':
                        try: entity.dxf.text = f"{float(entity.dxf.text):.{options['precision']}f}"
                        except ValueError: pass
                if kind == 'LINE' and entity.has_xdata('DRAWING_DIM_DETAIL'):
                    detail = entity.get_xdata('DRAWING_DIM_DETAIL')
                    if detail[0].value == 'tick' and ('arrow_scale' in options or options.get('arrow_size',-1)>0):
                        center = (entity.dxf.start + entity.dxf.end) / 2
                        factor = options.get('arrow_scale',1)
                        if options.get('arrow_size',-1)>0: factor *= options['arrow_size'] / (entity.dxf.end-entity.dxf.start).magnitude
                        entity.dxf.start = center + (entity.dxf.start-center)*factor
                        entity.dxf.end = center + (entity.dxf.end-center)*factor
                if kind == 'TEXT' and options.get('gap',-1) >= 0 and entity.has_xdata('DRAWING_DIM_DETAIL'):
                    detail = entity.get_xdata('DRAWING_DIM_DETAIL')
                    if detail[0].value in {'horizontal','vertical'}:
                        from ezdxf.math import Vec3
                        original_gap = detail[1].value
                        shift = options['gap'] - original_gap
                        offset = Vec3(0,-shift,0) if detail[0].value == 'horizontal' else Vec3(shift,0,0)
                        entity.dxf.insert += offset
                        if entity.dxf.hasattr('align_point'): entity.dxf.align_point += offset
            style = styles.get(source, {})
            if style.get('linetype', 'PRESERVAR') != 'PRESERVAR' and kind not in {'HATCH', 'DIMENSION', 'TEXT', 'MTEXT', 'INSERT'} and entity.dxf.is_supported('linetype'):
                entity.dxf.linetype = style['linetype']
                changed += 1
            pattern = style.get('hatch_pattern', 'PRESERVAR')
            if kind == 'HATCH' and pattern != 'PRESERVAR':
                if pattern == 'SOLID':
                    entity.set_solid_fill(color=entity.dxf.color)
                else:
                    entity.set_pattern_fill(pattern, scale=entity.dxf.pattern_scale or 1.0, angle=entity.dxf.pattern_angle)
                changed += 1
            if 'text_scale' in appearance and kind in {'TEXT', 'MTEXT', 'ATTRIB'}:
                attr = 'char_height' if kind == 'MTEXT' else 'height'
                setattr(entity.dxf, attr, getattr(entity.dxf, attr) * appearance['text_scale'])
                changed += 1
            if kind == 'DIMENSION' and 'dimension_scale' in appearance:
                factor = appearance['dimension_scale']
                style = doc.dimstyles.get(entity.dxf.dimstyle)
                override = entity.override()
                override.update({'dimtxt': style.dxf.dimtxt * factor, 'dimasz': style.dxf.dimasz * factor})
                override.render()
                changed += 1
            if kind == 'HATCH' and not entity.dxf.solid_fill:
                if 'hatch_scale' in appearance:
                    entity.set_pattern_scale(entity.dxf.pattern_scale * appearance['hatch_scale'])
                    changed += 1
                if 'hatch_angle' in appearance:
                    entity.set_pattern_angle(appearance['hatch_angle'])
                    changed += 1
    digest = hashlib.sha256(json.dumps(delta, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    doc.header['$USERI1'] = store['revision']
    if 'DRAWING_MODE_CONFIG' not in doc.appids:
        doc.appids.new('DRAWING_MODE_CONFIG')
    # DXF-resident provenance survives download and permits diagnosing stale N3.
    for entity in doc.modelspace():
        entity.set_xdata('DRAWING_MODE_CONFIG', [(1000, f'{mode}/{cls}'), (1000, digest)])
        break
    return {'changed': changed, 'removed': removed, 'sha256': digest}
