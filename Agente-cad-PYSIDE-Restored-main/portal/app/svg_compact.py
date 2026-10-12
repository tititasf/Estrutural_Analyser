"""Compact matplotlib previews without changing source DXFs or path geometry."""
from __future__ import annotations
import re
import xml.etree.ElementTree as ET

SVG = 'http://www.w3.org/2000/svg'
XLINK = 'http://www.w3.org/1999/xlink'
ET.register_namespace('', SVG)
ET.register_namespace('xlink', XLINK)
VERSION = 'compact-v1'
BATCH = 128

_PATH_TOKEN = re.compile(r'[MmZzLlHhVvCcSsQqTtAa]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?')

def compact_svg_serialization(source: bytes) -> bytes:
    """Lossless lexical compaction: no rounding, merging or style inheritance.

    Keep each numeric lexeme and command unchanged. Text, comments, IDs and
    custom attributes remain available to tags, navigation and editing.
    """
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(source, parser=parser)
    for style_node in root.iter(f'{{{SVG}}}style'):
        css = re.sub(r'/\*.*?\*/', '', ''.join(style_node.itertext()), flags=re.S)
        if any(s.strip() != '*' for s in re.findall(r'([^{}]+)\{', css)):
            return source
    containers = {f'{{{SVG}}}{name}' for name in ('svg', 'g', 'defs', 'clipPath')}
    for node in root.iter():
        if node.tag == f'{{{SVG}}}path' and 'd' in node.attrib:
            value = node.get('d')
            tokens = _PATH_TOKEN.findall(value)
            # Unsupported syntax fails open to the original path representation.
            if tokens and not re.sub(r'[\s,]', '', _PATH_TOKEN.sub('', value)):
                node.set('d', ''.join(
                    token if i == 0 or token.isalpha() or tokens[i-1].isalpha()
                    else ' ' + token for i, token in enumerate(tokens)))
        style = node.get('style')
        if style and re.fullmatch(r'[a-zA-Z0-9_:#.;%+\-\s]+', style):
            node.set('style', re.sub(r'\s*([:;])\s*', r'\1', style.strip()))
        if node.tag in containers:
            if node.text and not node.text.strip():
                node.text = None
            for child in node:
                if child.tail and not child.tail.strip():
                    child.tail = None
    result = ET.tostring(root, encoding='utf-8', xml_declaration=True)
    return result if len(result) < len(source) else source

def compact_svg_structure(source: bytes) -> bytes:
    """Remove only redundant groups; retain separate paint operations and comments.

    Joining strokes can change antialiasing at overlaps. This conservative path
    preserves path data, marker uses, draw order and every rendering attribute.
    """
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(source, parser=parser)
    # Unknown CSS can depend on group IDs or ancestry. Matplotlib's universal
    # stroke rule does not; leave other stylesheets untouched.
    for style in root.iter(f'{{{SVG}}}style'):
        css = re.sub(r'/\*.*?\*/', '', ''.join(style.itertext()), flags=re.S)
        if any(selector.strip() != '*' for selector in re.findall(r'([^{}]+)\{', css)):
            return source
    references = set()
    for node in root.iter():
        for key, value in node.attrib.items():
            if key.endswith('href'):
                references.add(value.lstrip('#'))
            references.update(re.findall(r'url\(\s*[\"\']?#([^\s)\"\']+)', value))
    def walk(parent, protected=False):
        protected = protected or parent.tag in (f'{{{SVG}}}defs', f'{{{SVG}}}style')
        children = []
        for child in list(parent):
            walk(child, protected)
            if (not protected and child.tag == f'{{{SVG}}}g'
                    and set(child.attrib) <= {'id'}
                    and child.get('id') not in references):
                children.extend(list(child))
            else:
                children.append(child)
        parent[:] = children
    walk(root)
    root.set('data-cad-compact', 'structure-v1')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)

def _relative_marker(d):
    # Matplotlib scatter markers consist of absolute M/C and close only.
    tokens = re.findall(r'[A-Za-z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?', d)
    if not tokens or tokens[0] != 'M': return None
    i, x, y, out = 0, 0., 0., []
    while i < len(tokens):
        command = tokens[i]; i += 1
        if command in ('z','Z'): out.append('z'); continue
        count = {'M':2,'C':6}.get(command)
        if count is None or i+count > len(tokens): return None
        try: values = list(map(float,tokens[i:i+count]))
        except ValueError: return None
        i += count
        if command == 'M':
            if out: return None
            start = values
        else:
            out.append('c'+' '.join(format(v-(x if j%2==0 else y),'.9g') for j,v in enumerate(values)))
        x,y=values[-2:]
    return start, ' '.join(out)

def compact_svg(source: bytes) -> bytes:
    root = ET.fromstring(source)
    references = {v.lstrip('#') for n in root.iter() for k,v in n.attrib.items() if k.endswith('href')}
    markers = {n.get('id'): (_relative_marker(n.get('d','')),n.attrib) for n in root.iter(f'{{{SVG}}}path') if n.get('id')}
    def walk(parent, in_defs=False):
        in_defs = in_defs or parent.tag == f'{{{SVG}}}defs'
        children=[]
        for child in list(parent):
            walk(child,in_defs)
            # Unreferenced id-only groups do not affect geometry, style or clipping.
            if not in_defs and child.tag==f'{{{SVG}}}g' and set(child.attrib)<= {'id'} and child.get('id') not in references:
                children.extend(list(child))
            else: children.append(child)
        if in_defs: return
        result=[]; batch=[]; key=None; attrs=None
        def flush():
            nonlocal batch
            if batch:
                result.append(ET.Element(f'{{{SVG}}}path',dict(attrs,d=' '.join(batch), **({'data-cad-batch':str(len(batch))} if len(batch)>1 else {}))))
                batch=[]
        for child in children:
            candidate=None; shape=None
            if child.tag==f'{{{SVG}}}path' and not child.get('data-cad-batch') and not child.get('id') and 'fill: none' in child.get('style','') and not any(k in child.attrib for k in ('transform','opacity','filter','mask')) and 'opacity' not in child.get('style',''):
                candidate={k:v for k,v in child.attrib.items() if k!='d'}; shape=child.get('d','')
            elif child.tag==f'{{{SVG}}}use' and set(child.attrib)<= {f'{{{XLINK}}}href','href','x','y','style'}:
                marker=markers.get((child.get(f'{{{XLINK}}}href') or child.get('href','')).lstrip('#'))
                if marker and marker[0] and set(marker[1]) <= {'id','d','style'} and 'opacity' not in child.get('style',''):
                    start,relative=marker[0]
                    x=float(child.get('x',0))+start[0]; y=float(child.get('y',0))+start[1]
                    candidate={'style':marker[1].get('style','')+';'+child.get('style','')}
                    shape=f'M{x:.9f} {y:.9f} {relative}'
            newkey=tuple(sorted(candidate.items())) if candidate is not None else None
            if candidate is None or newkey!=key or len(batch)>=BATCH:
                flush();key=newkey;attrs=candidate
            if candidate is None:result.append(child)
            else:batch.append(shape)
        flush();parent[:]=result
    walk(root)
    root.set('data-cad-compact',VERSION)
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)
