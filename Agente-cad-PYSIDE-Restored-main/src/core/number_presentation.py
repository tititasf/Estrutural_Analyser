"""One decimal presentation policy; geometry and machine values stay exact."""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

POLICY_VERSION = 'one-decimal-levels-v6'
_DECIMAL = re.compile(r'(?<![\w.,-])-?\d+[.,]\d+(?:[eE][+-]?\d+)?(?![\d.]|,\d)(?=$|[^A-Za-z_]|(?:cm|mm|m2|m|pt|px)\b)', re.I)
_PROTECTED = re.compile(r'(https?://\S+|[A-Za-z]:[\\/]\S+|\b[\w.-]+\.(?:dxf|dwg|json|svg|png|pdf)\b|\\[A-Za-z][^;\\{}]*;)', re.I)
_NUMBER = re.compile(r'^\s*[+-]?\d+(?:[.,]\d+)?\s*$')


def _symbol_level_handles(layout):
    """Recognize altitude conventions by topology, not numeric magnitude.

    A circle must have both diameters and a horizontal label leader. A section
    triangle must be closed and have a midpoint stem plus a label leader.
    Isolated circles, dimension arrows and nearby numbers are not sufficient.
    Only horizontal TEXT labels above the actual leader are selected.
    """
    import math
    lines = []
    adjacency = {}
    def key(point):
        return (round(point[0], 3), round(point[1], 3))
    for entity in layout.query('LINE'):
        a, b = tuple(entity.dxf.start)[:2], tuple(entity.dxf.end)[:2]
        lines.append((a, b))
        adjacency.setdefault(key(a), []).append(b)
        adjacency.setdefault(key(b), []).append(a)
    def connected(a, b, tolerance):
        return any(math.dist(p, b) <= tolerance for p in adjacency.get(key(a), []))
    leaders = []
    for circle in layout.query('CIRCLE'):
        x, y = tuple(circle.dxf.center)[:2]
        r = circle.dxf.radius
        if r <= 0:
            continue
        tolerance = max(0.001, r * 0.0001)
        if not (connected((x, y-r), (x, y+r), tolerance)
                and connected((x-r, y), (x+r, y), tolerance)):
            continue
        for end in ((x-r, y), (x+r, y)):
            for other in adjacency.get(key(end), []):
                if abs(other[1]-y) <= tolerance and abs(other[0]-end[0]) > r*2:
                    leaders.append((end, other, r))
    for a, b in lines:
        width = abs(a[0]-b[0])
        if width <= 0 or abs(a[1]-b[1]) > max(0.001, width*0.0001):
            continue
        tolerance = max(0.001, width*0.0001)
        midpoint = ((a[0]+b[0])/2, (a[1]+b[1])/2)
        for tip in adjacency.get(key(a), []):
            depth = a[1]-tip[1]
            if not (width*.25 <= depth <= width*2
                    and abs(tip[0]-midpoint[0]) <= tolerance
                    and connected(b, tip, tolerance)):
                continue
            for stem in adjacency.get(key(midpoint), []):
                if not (abs(stem[0]-midpoint[0]) <= tolerance
                        and width*.1 <= stem[1]-midpoint[1] <= width):
                    continue
                for end in adjacency.get(key(stem), []):
                    if abs(end[1]-stem[1]) <= tolerance and abs(end[0]-stem[0]) > width*2:
                        leaders.append((stem, end, width))
    handles = set()
    for text in layout.query('TEXT'):
        if not _NUMBER.fullmatch(text.dxf.text) or abs(text.dxf.get('rotation', 0)) > .001:
            continue
        x, y = tuple(text.dxf.insert)[:2]
        height = text.dxf.height
        for a, b, size in leaders:
            if (size*.2 <= height <= size*2
                    and min(a[0], b[0]) <= x <= max(a[0], b[0])
                    and 0 <= y-a[1] <= height*1.5):
                handles.add(text.dxf.handle)
                break
    return handles


def display_number(value):
    if value is None or value == '':
        return '—'
    try:
        number = Decimal(str(value).replace(',', '.'))
        if not number.is_finite():
            return str(value)
        rounded = number.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
        if rounded == 0:
            rounded = abs(rounded)
        return format(rounded, '.1f').removesuffix('.0').replace('.', ',')
    except (InvalidOperation, ValueError):
        return str(value)


def display_level(value):
    """Absolute level already in metres; never infer unit from magnitude."""
    if value is None or value == '':
        return '—'
    try:
        number = Decimal(str(value).replace(',', '.'))
        if not number.is_finite():
            return str(value)
        rounded = number.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return format(abs(rounded) if rounded == 0 else rounded, '.2f').replace('.', ',')
    except (InvalidOperation, ValueError):
        return str(value)


_LEVEL_TEXT = re.compile(r'((?:n[ií]ve(?:l|is)(?:\s+(?:de\s+)?(?:chegada|sa[ií]da|do elemento|da laje|da viga|do trecho|superior|inferior))?|element_level|pillar_top_level|nivel_chegada|nivel_saida|laje_nivel)\s*["\']?\s*[:=]?\s*\(?\s*)([+-]?\d+(?:[.,]\d+)?)(?![\d.,]|\s*(?:cm|mm)\b)', re.I)


def _display_part(part):
    levels = []
    def protect(match):
        levels.append(match[1] + display_level(match[2]))
        return '\ue000' + str(len(levels) - 1) + '\ue001'
    part = _LEVEL_TEXT.sub(protect, part)
    part = _DECIMAL.sub(lambda match: display_number(match.group()), part)
    return re.sub(r'\ue000(\d+)\ue001', lambda match: levels[int(match[1])], part)


def display_text(value):
    """Decimal quantities only: IDs, paths, dates and counts are not measures."""
    parts = _PROTECTED.split(str(value))
    return ''.join(part if index % 2 else _display_part(part) for index, part in enumerate(parts))


def apply_dxf_number_presentation(doc):
    """Format existing labels in-place, without moving/rebuilding any geometry.

    Works on a freshly generated document or an in-memory preview copy. Never
    call saveas on a historical/source document after this operation.
    Dimension blocks can be shared; process each label exactly once.
    """
    dimension_blocks = set()
    dimensions = list(doc.entitydb.values())
    count = 0
    for entity in dimensions:
        if entity.is_alive and entity.dxftype() == 'DIMENSION':
            entity.override().update({'dimdec': 1, 'dimdsep': 44, 'dimzin': 8, 'dimrnd': 0.1})
            name = entity.dxf.get('geometry')
            if name:
                dimension_blocks.add(name)
            # Explicit dimension text must follow the same display policy.
            raw = entity.dxf.get('text', '')
            if raw and raw not in ('<>', ' '):
                entity.dxf.text = display_number(raw) if _NUMBER.fullmatch(raw) else display_text(raw)
            count += 1
    for layout in [doc.modelspace(), *doc.blocks]:
        is_dimension = layout.name in dimension_blocks
        level_handles = set() if is_dimension else _symbol_level_handles(layout)
        for entity in layout.query('TEXT MTEXT ATTRIB ATTDEF'):
            raw = entity.dxf.text if entity.dxftype() != 'MTEXT' else entity.text
            level_layer = re.search(r'(?:^|[_ -])(?:NIVEL|NÍVEL|LEVELS?)(?:$|[_ -])', entity.dxf.layer, re.I)
            formatted = (display_level(raw) if (level_layer or entity.dxf.handle in level_handles) and _NUMBER.fullmatch(raw)
                         else display_number(raw) if is_dimension and _NUMBER.fullmatch(raw) else display_text(raw))
            if formatted != raw:
                if entity.dxftype() == 'MTEXT':
                    entity.text = formatted
                else:
                    entity.dxf.text = formatted
    return count


def format_generated_dxf(path: str | Path):
    """Only for newly generated N3/N5, never original DXFs or N2/N4."""
    import ezdxf
    doc = ezdxf.readfile(path)
    count = apply_dxf_number_presentation(doc)
    doc.saveas(path)
    return count
