"""Place existing FV chips without changing CAD, labels or leader endpoints."""
import re
import xml.etree.ElementTree as ET

NS = 'http://www.w3.org/2000/svg'
NUMBER = r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?'


def separate_chips(svg, gap=2.0):
    root = ET.fromstring(svg)
    view = [float(n) for n in root.get('viewBox', '').split()]
    if len(view) != 4:
        return svg
    rows = {}
    for parent in root.iter():
        siblings = list(parent)
        for index, group in enumerate(siblings):
            text = group.find('{'+NS+'}text')
            paths = [p for p in group.iter('{'+NS+'}path') if p.get('data-fv-hl') == 'tag']
            if text is None or len(paths) != 1 or index == 0 or group.get('transform'):
                continue
            label = ''.join(text.itertext())
            if not re.fullmatch(r'S\d+', label):
                continue
            # The tagged Matplotlib chip uses only M/L/Q/z Cartesian pairs.
            d = paths[0].get('d', '')
            if re.search(r'[A-DF-KN-PR-WYac-hj-pr-wy]', re.sub(NUMBER, '', d)):
                continue
            coords = [float(v) for v in re.findall(NUMBER, d)]
            if len(coords) < 8 or len(coords) % 2:
                continue
            x, y = float(text.get('x')), float(text.get('y'))
            xs = coords[::2]
            arrow = list(siblings[index-1].iter('{'+NS+'}path'))
            if len(arrow) != 2:
                continue
            shaft = arrow[0]
            # Association is verified from the existing shaft, not sibling ID.
            points = [float(v) for v in re.findall(NUMBER, shaft.get('d', ''))]
            if len(points) != 6 or abs(points[0]-x) > .01 or abs(points[-2]-x) > .01:
                continue
            rows.setdefault(round(y, 3), []).append((x,min(xs),max(xs),group,shaft,points))
    changed = False
    for row in rows.values():
        row.sort(key=lambda item:item[0])
        placed, right = [], None
        for item in row:
            left, old_right = item[1:3]
            dx = max(0.0, right+gap-left) if right is not None else 0.0
            placed.append((item,dx))
            right = old_right+dx
        if not any(dx for _,dx in placed):
            continue
        shift = max(0.0, right-(view[0]+view[2]-gap))
        if placed[0][0][1]-shift < view[0]+gap:
            raise ValueError('espaço insuficiente para etiquetas FV legíveis')
        for (x,left,old_right,group,shaft,points),dx in placed:
            dx -= shift
            if abs(dx) < 1e-9:
                continue
            group.set('transform', f'translate({dx:.9f} 0)')
            # Keep original arrowhead and exact target; move only its start.
            shaft.set('d', f'M {x+dx:.9f} {points[1]} L {points[-2]} {points[-1]}')
            group.set('data-fv-chip-layout', 'separated-v1')
            changed = True
    return ET.tostring(root,encoding='unicode') if changed else svg
