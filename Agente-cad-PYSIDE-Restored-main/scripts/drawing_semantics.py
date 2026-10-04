"""Drawing roles recorded at entity creation, before visual conversion.

The proxy delegates geometry unchanged. Roles come from the generating view,
face and annotation; no coordinates or individual item names are assumed.
"""
import inspect
import re
import sys
from types import SimpleNamespace

APPID = 'DRAWING_ROLE'
DIM_DETAIL = 'DRAWING_DIM_DETAIL'
VIEWS = {
    'PL': {'cima': 'Visão cima', 'abefgh': 'Faces A, B, E, F, G, H', 'cd': 'Faces C, D', 'grades': 'Grades'},
    'LV': {'corte': 'Visão corte', 'ab': 'Painéis A, B'},
    'FV': {'fundo': 'Fundos'}, 'LJ': {'planta': 'Planta da laje'},
}
TEXTS = {
    'PL': {'nome': 'Texto do nome', 'faces_cima': 'Referência das faces na visão cima', 'niveis': 'Níveis e pé-direito', 'sarrafos': 'Sarrafos necessários ao lado dos painéis', 'moldura': 'Preenchimento da moldura', 'faces': 'Identificação das faces', 'medidas': 'Medidas e referências'},
    'LV': {'nome': 'Nome da lateral', 'extremos': 'Ponto inicial e ponto final', 'paineis': 'Identificação dos painéis', 'sarrafos': 'Sarrafos e meio-pontaletes', 'referencias': 'Referências do corte e observações', 'moldura': 'Preenchimento da moldura'},
    'FV': {'nome': 'Nome do fundo', 'extremos': 'Ponto inicial e ponto final / apoios', 'paineis': 'Identificação e multiplicadores dos painéis', 'referencias': 'Referências e observações', 'moldura': 'Preenchimento da moldura'},
    'LJ': {'nome': 'Nome da laje', 'reaproveitamento': 'Reaproveitamento dos painéis', 'referencias': 'Pilares e obstáculos', 'medidas': 'Medidas auxiliares', 'moldura': 'Preenchimento da moldura'},
}
HATCHES = {
    'PL': {'lajes': 'Lajes / concreto', 'grades': 'Blocos das grades', 'reuso1': 'Reutilização completa 1', 'reuso2': 'Reutilização recortada 2', 'aberturas': 'Aberturas', 'paineis': 'Chapas e painéis'},
    'LV': {'lajes': 'Lajes / concreto', 'reuso1': 'Reutilização completa 1', 'reuso2': 'Reutilização recortada 2', 'aberturas': 'Aberturas', 'paineis': 'Chapas e painéis'},
    'FV': {'reuso1': 'Reutilização completa 1', 'reuso2': 'Reutilização recortada 2', 'paineis': 'Chapas e painéis'},
    'LJ': {'reuso1': 'Reutilização completa 1', 'reuso2': 'Reutilização recortada 2', 'escoramento': 'Tira de escoramento / união', 'pilares': 'Pilares / HLAZ'},
}

def schema(cls):
    cls = cls.split('_')[0]
    return {'views': VIEWS[cls], 'texts': TEXTS[cls], 'hatches': HATCHES[cls],
            'dimensions': {key: 'Cotas — ' + label for key, label in VIEWS[cls].items()}}

def roles(entity):
    if not entity.has_xdata(APPID):
        return None
    return tuple(tag.value for tag in entity.get_xdata(APPID) if tag.code == 1000)

def copy_role(source, target):
    if source.has_xdata(APPID):
        target.set_xdata(APPID, source.get_xdata(APPID))

def classify(cls, entity, frames):
    names = [f.function for f in frames]
    scope = ' '.join(names + [f.frame.f_code.co_filename for f in frames]).lower()
    values = {}
    # Closest frame takes precedence (individual face and reuse panel).
    for frame in reversed(frames):
        values.update(frame.frame.f_locals)
    view = next(iter(VIEWS[cls]))
    if cls == 'PL':
        if 'grade' in scope: view = 'grades'
        elif 'cima' in scope: view = 'cima'
        else: view = 'cd' if str(values.get('fid', values.get('face', ''))).upper() in {'C','D'} else 'abefgh'
    elif cls == 'LV': view = 'corte' if any(s in scope for s in ('section','corte','cut')) else 'ab'
    elif cls == 'FV': view = 'fundo'
    elif cls == 'LJ': view = 'planta'
    kind, layer = entity.dxftype(), str(entity.dxf.get('layer','')).casefold()
    role = ''
    family = 'geometry'
    if kind == 'DIMENSION' or 'plain_dim' in scope or '_dim_text' in scope:
        family, role = 'dimensions', view
    elif kind in {'TEXT','MTEXT','ATTRIB'}:
        family = 'texts'
        text = str(entity.plain_text() if kind == 'MTEXT' else entity.dxf.get('text','')).casefold()
        role = 'referencias'
        if 'carimbo' in layer or 'card' in scope or 'moldura' in scope: role = 'moldura'
        elif cls == 'PL':
            if 'nivel' in text or 'pd:' in text: role = 'niveis'
            elif 'sarr' in text: role = 'sarrafos'
            elif view == 'cima' and re.fullmatch(r'[a-h]',text.strip()): role = 'faces_cima'
            elif re.search(r'\.[a-h](?:\b|$)',text): role = 'faces'
            elif text.startswith('p') and not text.startswith('pd'): role = 'nome'
            else: role = 'medidas'
        elif cls in {'LV','FV'}:
            if 'endpoint' in scope or any(k in values and str(values[k]).casefold() == text for k in ('endpoint_start_label','endpoint_end_label','text_left','text_right','right_text','next_left')): role = 'extremos'
            elif 'sarr' in text or 'pont' in text: role = 'sarrafos' if cls == 'LV' else 'referencias'
            elif 'nom' in layer or text.startswith('v'): role = 'nome'
            elif layer in {'5','divisao','painéis','paineis'}: role = 'paineis'
        elif cls == 'LJ':
            if 'reap' in text or 'reuse' in scope or 'reap' in layer: role = 'reaproveitamento'
            elif layer in {'4','nomenclatura'}: role = 'nome'
            elif layer in {'painéis','paineis'}: role = 'medidas'
    elif kind == 'HATCH' or (cls == 'LJ' and 'pilar_hatch' in scope):
        family = 'hatches'
        if 'reuse' in scope or 'reap' in layer or 'reap' in scope or values.get('is_reuse'):
            role = 'reuso2' if any(s in scope for s in ('narrow','recort')) or values.get('reuse_cut') or values.get('recortado') else 'reuso1'
        elif cls == 'LJ': role = 'pilares' if 'pilar' in scope or 'hlaz' in scope else 'escoramento'
        elif 'grade' in scope: role = 'grades'
        elif any(s in scope for s in ('abert','opening','vazio','void')): role = 'aberturas'
        elif 'laj' in layer or 'concreto' in layer or 'laje' in scope or (values.get('pattern',entity.dxf.get('pattern_name','')) == 'AR-CONC' and cls != 'FV'): role = 'lajes'
        else: role = 'paineis'
    return view, family, role

class LayoutProxy:
    def __init__(self, layout, cls):
        self.layout, self.cls = layout, cls.split('_')[0]
        if APPID not in layout.doc.appids: layout.doc.appids.new(APPID)
        if DIM_DETAIL not in layout.doc.appids: layout.doc.appids.new(DIM_DETAIL)
    def __iter__(self): return iter(self.layout)
    def __len__(self): return len(self.layout)
    def __getattr__(self, name):
        original = getattr(self.layout, name)
        if not name.startswith('add_') or not callable(original): return original
        def create(*args, **kwargs):
            result = original(*args, **kwargs)
            entity = getattr(result, 'dimension', result)
            if hasattr(entity, 'set_xdata'):
                frames = []
                frame = sys._getframe(1)
                for _ in range(17):
                    if frame is None: break
                    frames.append(SimpleNamespace(function=frame.f_code.co_name,frame=frame))
                    frame = frame.f_back
                try:
                    entity.set_xdata(APPID, [(1000,s) for s in classify(self.cls,entity,frames)])
                    plain = next((f for f in frames if f.function in {'add_plain_dim_h','add_plain_dim_v'}),None)
                    if plain and entity.dxftype() == 'LINE':
                        difference = entity.dxf.end-entity.dxf.start
                        if difference.x and difference.y:
                            entity.set_xdata(DIM_DETAIL,[(1000,'tick')])
                    elif plain and entity.dxftype() == 'TEXT':
                        vertical = plain.function.endswith('_v')
                        vals = plain.frame.f_locals
                        if ('x' if vertical else 'y') in vals:
                            gap = entity.dxf.insert.x-vals['x'] if vertical else vals['y']-entity.dxf.insert.y
                            entity.set_xdata(DIM_DETAIL,[(1000,'vertical' if vertical else 'horizontal'),(1040,gap)])
                finally: del frames, frame
            return result
        return create

def instrument(namespace, cls):
    """Wrap drawing entry points once, without changing generator algorithms."""
    import functools
    for name, function in list(namespace.items()):
        if not inspect.isfunction(function) or function.__module__ != namespace.get('__name__') or getattr(function,'_drawing_roles',False): continue
        signature = inspect.signature(function)
        if 'msp' not in signature.parameters: continue
        @functools.wraps(function)
        def wrapper(*args, __f=function, __sig=signature, **kwargs):
            bound = __sig.bind(*args,**kwargs)
            if not isinstance(bound.arguments.get('msp'), LayoutProxy):
                bound.arguments['msp'] = LayoutProxy(bound.arguments['msp'],cls)
            return __f(*bound.args,**bound.kwargs)
        wrapper._drawing_roles = True
        namespace[name] = wrapper
