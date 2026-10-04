"""Mode/class/example scoped reference crops; original uploads stay immutable."""
import json
import math
import os
import uuid
from . import drawing_frame as frames
from .dxf_preview import obter_bbox_dxf, renderizar_dxf_svg_com_transform
from scripts import drawing_mode_config as profiles

TYPES = {
    'PL': {'CIMA': 'Cima', 'ABCD': 'ABCD', 'GRADES': 'Grades'},
    'LV': {'CORTE_SARRAFEADO': 'Visão corte sarrafeado', 'CORTE_GRADEADO': 'Visão corte gradeado',
           'CORTE_GARFO': 'Visão corte com garfo', 'AB_SARRAFEADO': 'AB sarrafeado', 'AB_GRADEADO': 'AB gradeado'},
    'FV': {'FUNDOS': 'Fundos', 'GARFOS': 'Garfos'},
}


def root_for(mode, cls, token):
    frames.preview(mode, cls, token, 'drawing_examples')
    if not any(item['id'] == token for item in frames.examples(mode, cls)):
        raise ValueError('Exemplo não encontrado na lista.')
    return frames.directory(mode, cls, 'drawing_examples') / (token + '_crops')


def listing(mode, cls, token):
    root = root_for(mode, cls, token)
    path = root / 'index.json'
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else []


def source(mode, cls, token):
    root = root_for(mode, cls, token)
    root.mkdir(parents=True, exist_ok=True)
    with profiles.file_lock(root / 'source.json'):
        path = root / 'source.json'
        if not path.exists():
            dxf = root.parent / (token + '.dxf')
            rendered = renderizar_dxf_svg_com_transform(dxf, bbox=obter_bbox_dxf(dxf), largura_px=1200, altura_px=700)
            (root / 'source.svg').write_bytes(rendered.svg)
            path.write_text(json.dumps(rendered.como_dict()), encoding='utf8')
        return json.loads(path.read_text(encoding='utf8'))


def save_index(root, items):
    pending = root / (uuid.uuid4().hex + '.json')
    pending.write_text(json.dumps(items, ensure_ascii=False), encoding='utf8')
    os.replace(pending, root / 'index.json')


def create(mode, cls, token, kind, name, rectangles):
    kinds = TYPES.get(profiles.key_for(cls).split('_')[0], {})
    if kind not in kinds:
        raise ValueError('Escolha um tipo de recorte válido para esta classe.')
    if not rectangles or len(rectangles) > 30:
        raise ValueError('Desenhe de 1 a 30 retângulos.')
    for box in rectangles:
        if len(box) != 4 or not all(math.isfinite(v) and 0 <= v <= 1 for v in box) or box[2] <= box[0] or box[3] <= box[1]:
            raise ValueError('Coordenadas de recorte inválidas.')
    root = root_for(mode, cls, token)
    mapping = source(mode, cls, token)
    x0, y0, x1, y1 = mapping['bbox_dxf']
    boxes = [(x0+a*(x1-x0), y1-d*(y1-y0), x0+c*(x1-x0), y1-b*(y1-y0)) for a,b,c,d in rectangles]
    # Same contained-entity rule as manual floor crops. Keep the document tables,
    # blocks, text styles and dimension styles intact for faithful reference design.
    import ezdxf
    from ezdxf import bbox
    doc = ezdxf.readfile(root.parent / (token + '.dxf'))
    layout = doc.modelspace()
    entities = list(layout)
    kept = 0
    for entity in entities:
        # multi_flat skips entities without geometry; never zip its output with
        # modelspace or a skipped entity would shift every following selection.
        ext = bbox.extents([entity], fast=True)
        inside = ext.has_data and any(ext.extmin.x >= a and ext.extmin.y >= b and ext.extmax.x <= c and ext.extmax.y <= d for a,b,c,d in boxes)
        if inside: kept += 1
        else: layout.delete_entity(entity)
    if not kept: raise ValueError('Nenhuma entidade ficou integralmente dentro do recorte.')
    crop_id = uuid.uuid4().hex
    target = root / (crop_id + '.dxf')
    doc.saveas(target)
    rendered = renderizar_dxf_svg_com_transform(target, bbox=obter_bbox_dxf(target), largura_px=1200, altura_px=700)
    (root / (crop_id + '.svg')).write_bytes(rendered.svg)
    result = {'id': crop_id, 'kind': kind, 'label': kinds[kind], 'name': (name.strip()[:120] or kinds[kind]), 'entities': kept, 'rectangles': rectangles}
    with profiles.file_lock(root / 'index.json'):
        items = listing(mode, cls, token)
        items.append(result)
        save_index(root, items)
    return result


def crop_path(mode, cls, token, crop_id):
    root = root_for(mode, cls, token)
    if not any(item['id'] == crop_id for item in listing(mode, cls, token)):
        raise ValueError('Recorte não encontrado.')
    return root / (crop_id + '.svg')


def remove(mode, cls, token, crop_id):
    root = root_for(mode, cls, token)
    with profiles.file_lock(root / 'index.json'):
        items = listing(mode, cls, token)
        save_index(root, [item for item in items if item['id'] != crop_id])
    return listing(mode, cls, token)
