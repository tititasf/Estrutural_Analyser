"""Independent CAD object evidence used across structural classes.

Source layer semantics plus closed piece topology identify section glyphs.
Leader callouts own their annotations; text location alone is not ownership.
These rules never learn a floor/item coordinate or trust a derived slab.
"""
import re
import unicodedata
from shapely.geometry import Point, LineString


def section_layer(layer):
    norm = ''.join(c for c in unicodedata.normalize('NFKD', str(layer or '').upper())
                   if not unicodedata.combining(c))
    return ('SECTION' in norm or 'CORTE' in norm or 'CUT' in norm
            or 'SECAO' in norm or 'LINHA-SE' in norm)


def section_piece_keys(items, texts):
    """Actual source pieces, not bounding boxes of inferred objects."""
    from src.core.composite_cut_contours import partition_cut_contours
    records = partition_cut_contours(
        [p for p in items if p.get('points') and section_layer(p.get('layer'))], texts)
    keys = {tuple(sorted(set(tuple(p[:2]) for p in points)))
            for record in records for points in record['source_piece_keys']}
    return keys, records


def thickness_references(texts, items):
    """Resolve explicit arrow callouts, retaining independent provenance.

    The exploded leader has a shaft followed by two short arrow legs which
    repeat the tip. A nearby explicit BL label scopes a block annotation.
    Ambiguous/unproven leaders leave the original text position unchanged.
    """
    leaders = []
    for item in items:
        pts = item.get('points') or []
        if len(pts) != 6 or tuple(pts[2][:2]) != tuple(pts[4][:2]):
            continue
        a, b, tip, wing1, _, wing2 = [Point(p[:2]) for p in pts]
        shaft = b.distance(tip)
        if not shaft or min(tip.distance(wing1), tip.distance(wing2)) <= 0:
            continue
        if max(tip.distance(wing1), tip.distance(wing2)) >= shaft:
            continue
        leaders.append((a, b, tip, item))
    refs = []
    blocks = [t for t in texts if re.fullmatch(r'BL[.\-_ ]?\d+[A-Z]*',
              str(t.get('text', '')).strip(), re.I) and t.get('pos')]
    for text in texts:
        match = re.fullmatch(r'h\s*=\s*(\d+(?:[.,]\d+)?)\s*(?:cm)?',
                            str(text.get('text', '')).strip(), re.I)
        if not match or not text.get('pos'):
            continue
        value = float(match[1].replace(',', '.'))
        if value <= 0:
            continue
        row = dict(text)
        point = Point(text['pos'][:2])
        reach = 3 * float(text.get('height') or 10)
        hits = [leader for leader in leaders if leader[0].distance(point) <= reach]
        if len(hits) == 1:
            a, b, tip, item = hits[0]
            dx, dy = tip.x-b.x, tip.y-b.y
            length = b.distance(tip)
            row.update(pos=[tip.x+.01*dx/length, tip.y+.01*dy/length],
                       source_position=list(text['pos']),
                       annotation_reference='explicit_arrow_leader',
                       leader_points=item['points'])
            labels = [t for t in blocks if Point(t['pos'][:2]).distance(point) <= reach]
            if len(labels) == 1:
                row.update(target_class='foundation_block', target_label=labels[0]['text'])
        refs.append((row, value))
    return refs
