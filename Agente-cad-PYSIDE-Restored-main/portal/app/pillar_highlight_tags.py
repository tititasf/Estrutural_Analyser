"""Reproject only the existing S1 interpretation layer onto the floor viewer."""
from __future__ import annotations

import hashlib
import copy
import re
import xml.etree.ElementTree as ET


def project_s1_tags(svg: str, points: list, transform) -> str | None:
    """Fail closed if the S1 pillar calibration polygon is missing.

    The red S1 polygon supplies the exact SVG/DXF calibration. Everything
    before it is the CAD background, not interpretation, and is discarded.
    Retain path glyphs and their definitions without regenerating any tags.
    """
    ns = 'http://www.w3.org/2000/svg'
    ET.register_namespace('', ns)
    root = ET.fromstring(svg, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))
    axes = root.find(f'.//{{{ns}}}g[@id="axes_1"]')
    if axes is None or not points:
        return None
    children = list(axes)
    calibration = None
    for index, child in enumerate(children):
        for path in child.iter(f'{{{ns}}}path'):
            if 'fill: #ff1744' in path.get('style', '') and 'opacity: 0.12' in path.get('style', ''):
                calibration = (index, path)
                break
        if calibration:
            break
    if calibration is None:
        return None
    index, path = calibration
    coords = re.findall(r'[ML]\s*([-+\d.eE]+)\s+([-+\d.eE]+)', path.get('d', ''))
    if len(coords) < 3:
        return None
    sxv, syv = zip(*[(float(x), float(y)) for x, y in coords])
    pixels = [transform.dxf_para_px(float(p[0]), float(p[1])) for p in points]
    px, py = zip(*pixels)
    if max(sxv) == min(sxv) or max(syv) == min(syv):
        return None
    sx = (max(px) - min(px)) / (max(sxv) - min(sxv))
    sy = (max(py) - min(py)) / (max(syv) - min(syv))
    if sx <= 0 or sy <= 0 or abs(sx / sy - 1) > .02:
        return None
    tx, ty = min(px) - sx * min(sxv), min(py) - sy * min(syv)
    outer = ET.Element(f'{{{ns}}}g', {'class': 'pillar-interpretive-tags'})
    # Root clip definitions and each tag's nested glyph definitions are needed.
    for child in root:
        if child.tag == f'{{{ns}}}defs':
            outer.append(child)
    layer = ET.SubElement(outer, f'{{{ns}}}g', {'transform': f'matrix({sx} 0 0 {sy} {tx} {ty})'})
    for child in children[index + 1:]:
        # Exclude the S1 banner, which belongs to the individual evidence page.
        if any(node.tag is ET.Comment and 'SA motor' in (node.text or '') for node in child.iter()):
            continue
        layer.append(child)
    source_ids = {node.get('id'): node for node in root.iter() if node.get('id')}
    definitions = ET.SubElement(outer, f'{{{ns}}}defs')
    # Matplotlib may reuse a glyph first defined in the discarded CAD layer.
    for _ in range(8):
        present = {node.get('id') for node in outer.iter() if node.get('id')}
        referenced = set()
        for node in outer.iter():
            for key, value in node.attrib.items():
                referenced.update(re.findall(r'url\(#([^)]+)\)', value))
                if key.endswith('href') and value.startswith('#'):
                    referenced.add(value[1:])
        missing = referenced - present
        if not missing:
            break
        if any(key not in source_ids for key in missing):
            return None
        for key in missing:
            definitions.append(copy.deepcopy(source_ids[key]))
    else:
        return None
    prefix = 'pil-tags-' + hashlib.sha256(svg.encode()).hexdigest()[:16] + '-'
    ids = {node.get('id'): prefix + node.get('id') for node in outer.iter() if node.get('id')}
    for node in outer.iter():
        if node.get('id'):
            node.set('id', ids[node.get('id')])
        for key, value in list(node.attrib.items()):
            value = re.sub(r'url\(#([^)]+)\)', lambda m: 'url(#' + ids.get(m[1], m[1]) + ')', value)
            if key.endswith('href') and value.startswith('#'):
                value = '#' + ids.get(value[1:], value[1:])
            node.set(key, value)
    return ET.tostring(outer, encoding='unicode')
