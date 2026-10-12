"""Initial iNi pillar anatomy from SA, with its own reference palette."""
from .formascia_design import wrap_draw as anatomy
from .lv_formascia_design import normalize_resources
import functools
import inspect


def _initial_wrap_draw(function, zone):
    # Existing iNi grid distribution already consumes the iNi configuration.
    if zone != 'cima':
        return function if zone == 'grades' else anatomy(function, zone)
    fallback = anatomy(function, zone)
    signature = inspect.signature(function)

    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        from .pillar_nova_design import special_payload, apply_zone
        bound = signature.bind(*args, **kwargs)
        pj = bound.arguments['pj']
        if special_payload(pj) is None:
            return fallback(*args, **kwargs)
        m = bound.arguments['msp']
        before = {e.dxf.handle for e in m}
        result = function(*args, **kwargs)
        # The legacy setup_doc DASHED record contains only a gap. This path
        # bypasses Formascia's resource repair, so retain it locally for iNi.
        if 'DASHED' in m.doc.linetypes:
            m.doc.linetypes.get('DASHED').setup_pattern([5.0, 3.0, -2.0])
        # Same contour, corner clearances, rod stations and metal contacts as
        # Nova. The iNi palette is applied later, without changing geometry.
        apply_zone(m, pj, zone, [e for e in m if e.dxf.handle not in before])
        return result

    wrapped._formascia_wrapped = True
    return wrapped


def _initial_finish(doc):
    for _, style in doc.mline_styles:
        if style.dxf.name.startswith('FORMASCIA-PL-SARRAFO'):
            style.dxf.fill_color = 256
            elements = list(style.elements)
            style.elements.elements.clear()
            for element in elements:
                style.elements.append(element.offset, 256, element.linetype)
    colors = {'FORMASCIA-SARRAFOS': 24, 'FORMASCIA-REFORCOS': 12,
              'FORMASCIA-VAZIOS': 251, 'FORMASCIA-PARAFUSOS': 1,
              'NUMERACAO_PAINEIS': 7, 'Texto Nível': 1}
    colors['Parafuso'] = 1
    for name, color in colors.items():
        if name in doc.layers:
            doc.layers.get(name).dxf.color = color
    m = doc.modelspace()
    for e in list(m):
        name = e.dxf.layer.casefold()
        if e.dxftype() == 'TEXT' and e.dxf.text.startswith(('CENARIOS', 'NIVEL DE')):
            m.delete_entity(e)
        elif name == 'numeracao_paineis':
            e.dxf.color = 1 if e.dxftype() == 'CIRCLE' else 7
        elif name == 'formascia-vazios':
            e.set_pattern_fill('AR-CONC', scale=.1, angle=0, color=251)
        elif name == 'formascia-sarrafos':
            e.dxf.color = 7 if e.dxf.style_name == 'SAR15' else 24
        elif name == 'formascia-parafusos':
            e.dxf.color = 1
    normalize_resources(doc)


def _transfer(source, target):
    """Copy native MLINE resources as well as the reviewed entities."""
    from .n5_ini_frames import clone
    from .n5_formascia_frames import transfer
    from ezdxf.addons import Importer
    source = clone(source)
    resources = Importer(source, target)
    resources.import_tables(['layers', 'linetypes'], replace=False)
    resources.import_tables(['styles', 'dimstyles'], replace=True)
    # AutoCAD requires layer 0 to remain the first table record. Update
    # palette attributes in place instead of replacing layer records.
    for original in source.layers:
        if original.dxf.name in target.layers:
            layer = target.layers.get(original.dxf.name)
            layer.dxf.color = original.dxf.color
            if original.dxf.hasattr('true_color'): layer.dxf.true_color = original.dxf.true_color
            else: layer.dxf.discard('true_color')
    resources.finalize()
    if 'DASHED' in target.linetypes:
        target.linetypes.get('DASHED').setup_pattern([5., 3., -2.])
    # Replacing Standard can invalidate the unused default MLEADER style.
    for _, style in target.mleader_styles:
        if target.entitydb.get(style.dxf.text_style_handle) is None:
            style.dxf.text_style_handle = target.styles.get('Standard').dxf.handle
    for block in list(source.blocks):
        if block.name.startswith('INI_APPROVED_') and block.name in target.blocks:
            target.blocks.delete_block(block.name, safe=False)
    for _, original in source.mline_styles:
        name = original.dxf.name
        if not name.startswith('INI'): continue
        st = target.mline_styles.get(name) if name in target.mline_styles else target.mline_styles.new(name)
        for attr in ('flags', 'fill_color', 'start_angle', 'end_angle'):
            st.dxf.set(attr, original.dxf.get(attr))
        st.elements.elements.clear()
        for el in original.elements: st.elements.append(el.offset, el.color, el.linetype)
    # Importer intentionally omits entity XDATA. Preserve semantic drilling
    # metadata and regenerate dimension overrides after the resource transfer.
    dimensions = [e.override().get_dstyle_dict() for e in source.modelspace().query('DIMENSION')]
    records = {}
    for e in source.modelspace():
        data = {name: list(e.get_xdata(name)) for name in ('PL_PANEL_DRILLING', 'DRAWING_ROLE') if e.has_xdata(name)}
        records.setdefault(e.dxftype(), []).append(data)
    before = {e.dxf.handle for e in target.modelspace()}
    count = transfer(source, target, native_mlines=True)
    indices = {}; di = 0
    for e in target.modelspace():
        if e.dxf.handle in before: continue
        kind = e.dxftype(); i = indices.get(kind, 0); indices[kind] = i+1
        for name, data in records.get(kind, [])[i].items():
            if name not in target.appids: target.appids.new(name)
            e.set_xdata(name, data)
        if kind == 'HATCH' and e.dxf.layer == 'CONCRETO' and e.has_pattern_fill:
            e.set_pattern_fill('AR-CONC', scale=.1, angle=0, color=251)
        if kind == 'DIMENSION':
            override = e.override(); override.update(dimensions[di]); override.render(); di += 1
    return count


def _namespace_blocks(doc):
    # Reference symbols belong to iNi. Shared legacy names must not reuse a
    # symbol that the generic palette has already transformed in another zone.
    for name in ('PT', 'MEIOPT', 'A$C51C4441F', 'NIVEL'):
        if name not in doc.blocks: continue
        new = 'INI_APPROVED_' + name
        doc.blocks.rename_block(name, new)
        for entity in list(doc.entitydb.values()):
            if entity.is_alive and entity.dxftype() == 'INSERT' and entity.dxf.name == name:
                entity.dxf.name = new


def wrap_draw(function, zone):
    import copy
    import ezdxf
    from .n5_ini_frames import clone, normalize_resources
    signature = inspect.signature(function)
    fallback = anatomy(function, zone) if zone in ('abcd', 'efgh') else function

    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        layout = bound.arguments['msp']; target = layout.doc
        pj = copy.deepcopy(bound.arguments['pj'])
        namespace = inspect.unwrap(function).__globals__
        if zone == 'cima':
            from .ini_pillar_top import top
            source = top(pj, namespace)
            for entity in source.modelspace():
                entity.translate(bound.arguments['ox'], bound.arguments['oy'], 0)
        else:
            source = namespace['setup_doc']()
            source._drawing_mode_config_store = getattr(target, '_drawing_mode_config_store', None)
            bound.arguments['msp'] = source.modelspace()
            grade_origin = (bound.arguments.get('base_x', 0), bound.arguments.get('base_y', 0))
            if zone == 'grades':
                bound.arguments['base_x'] = 0
                bound.arguments['base_y'] = 0
                bound.arguments['visual_mode'] = 'NOVA'
            result = fallback(*bound.args, **bound.kwargs)
            if result < 0: return result
            source._ini_building = True
            from scripts.visual_modes import apply_visual_mode
            if zone in ('abcd', 'efgh'):
                apply_visual_mode(source, 'INI', 'PL')
                from .ini_pillar_elevation import add_drilling, native_annotations, refine
                # Generic optional drilling may have run outside this hook;
                # the native iNi holes are generated from the actual CIMA axes.
                add_drilling(source, pj, namespace)
                native_annotations(source)
                refine(source, pj)
                for e in source.modelspace():
                    if e.dxf.layer == 'NUMERACAO_PAINEIS': e.dxf.color = 5
            else:
                from .ini_pillar_grades import refine_grades
                refine_grades(source, pj, namespace)
                for entity in source.modelspace(): entity.translate(*grade_origin, 0)
        _namespace_blocks(source)
        normalize_resources(source)
        before = {e.dxf.handle for e in layout}
        _transfer(source, target)
        handles = {e.dxf.handle for e in layout if e.dxf.handle not in before}
        if not hasattr(target, '_ini_approved_zones'): target._ini_approved_zones = []
        target._ini_approved_zones.append((handles, clone(source)))
        target.ezdxf_metadata()['INI_DESIGN_REVISION'] = 'approved_20261007_v1'
        return len(handles)
    wrapped._formascia_wrapped = True
    wrapped._native_panel_drilling = zone in ('abcd', 'efgh')
    return wrapped


def finish(doc):
    _initial_finish(doc)
    if getattr(doc, '_ini_building', False): return
    # Generic style application precedes this hook. Reinstall the native iNi
    # geometry/palette at the final boundary instead of recoloring it twice.
    for handles, source in getattr(doc, '_ini_approved_zones', []):
        for entity in list(doc.modelspace()):
            if entity.dxf.handle in handles: doc.modelspace().delete_entity(entity)
        _transfer(source, doc)
    doc._ini_approved_zones = []
    from .n5_ini_frames import normalize_resources
    normalize_resources(doc)
