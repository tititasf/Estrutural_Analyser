"""Independent, conservative measurements from the immutable original CAD.

PIL: only axis-aligned rectangular pillars and unambiguous straight wall pairs.
LAJ: only label/h=/level texts written inside the slab's own contour (E1).
Unresolved measurements never become an automatic approval.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

EPS = .05  # extraction tolerance in CAD cm, not an engineering acceptance rate
_CACHE = {}


def _cached(kind, path, build, extra=''):
    """Memoiza leituras do mesmo arquivo (mesmo mtime/tamanho) entre vigas do pavimento."""
    path = Path(path)
    stat = path.stat()
    key = (kind, str(path.resolve()), stat.st_mtime_ns, stat.st_size, extra)
    if key not in _CACHE:
        if len(_CACHE) > 256:
            _CACHE.clear()
        _CACHE[key] = build()
    return _CACHE[key]


def _readfile(path):
    import ezdxf
    return _cached('doc', path, lambda: ezdxf.readfile(Path(path)))


def _sha256(path):
    return _cached('sha', path, lambda: hashlib.sha256(Path(path).read_bytes()).hexdigest())


def number(value):
    match = re.fullmatch(r'\s*([-+]?\d+(?:[.,]\d+)?)\s*(?:cm)?\s*', str(value))
    return float(match[1].replace(',', '.')) if match else None


def measure(source, snapshot):
    source = Path(source)
    doc = _readfile(source)
    walls, labels, contours = [], [], []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        segments = []
        if kind == 'LINE':
            segments = [(entity.dxf.start, entity.dxf.end)]
        elif kind == 'LWPOLYLINE':
            pts = list(entity.get_points('xyb'))
            repeated_end = len(pts) > 3 and abs(pts[0][0]-pts[-1][0]) < EPS and abs(pts[0][1]-pts[-1][1]) < EPS
            if (entity.closed or repeated_end) and not any(p[2] for p in pts):
                contours.append((entity.dxf.handle, {(float(p[0]), float(p[1])) for p in pts}))
            pairs = list(zip(pts, pts[1:] + (pts[:1] if entity.closed else [])))
            segments = [(a, b) for a, b in pairs if not a[2]]
        elif kind == 'TEXT':
            labels.append(dict(text=entity.dxf.text.strip(), x=float(entity.dxf.insert.x),
                               y=float(entity.dxf.insert.y), handle=entity.dxf.handle,
                               margin=max(float(entity.dxf.height)*2, EPS)))
        for a, b in segments:
            if abs(a[1]-b[1]) < EPS:
                walls.append(dict(axis='x', pos=float(a[1]), lo=min(a[0], b[0]),
                                  hi=max(a[0], b[0]), handle=entity.dxf.handle))
            elif abs(a[0]-b[0]) < EPS:
                walls.append(dict(axis='y', pos=float(a[0]), lo=min(a[1], b[1]),
                                  hi=max(a[1], b[1]), handle=entity.dxf.handle))
    contacts = []
    for index, pillar in enumerate(snapshot.get('collections', {}).get('pilares', [])):
        points = pillar.get('points') or []
        faces = (pillar.get('interpretacao_abcd') or {}).get('faces', {})
        for face, data in faces.items():
            for link in data.get('chega') or []:
                if str(link.get('nome') or '').strip().lower() in {'', 'nenhuma', 'nenhum', '—', '-'}:
                    continue
                record = dict(unit_path=f'/collections/pilares/{index}', face=face,
                              beam=link.get('nome'), status='uncertain', errors={})
                contacts.append(record)
                try:
                    xs, ys = [float(p[0]) for p in points], [float(p[1]) for p in points]
                    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
                    if (face not in 'ABCD' or len(set((x, y) for x, y in zip(xs, ys))) != 4 or
                            not all(math.isfinite(v) for v in xs+ys) or
                            not all(abs(x-xmin)<EPS or abs(x-xmax)<EPS for x in xs) or
                            not all(abs(y-ymin)<EPS or abs(y-ymax)<EPS for y in ys)):
                        raise ValueError('contorno não retangular/alinhado; medir no CAD manualmente')
                    own = set(zip(xs, ys))
                    matching = [handle for handle, vertices in contours if len(vertices) == len(own) and
                                all(any(abs(x-a)<EPS and abs(y-b)<EPS for a,b in vertices) for x,y in own)]
                    if len(matching) != 1:
                        raise ValueError('contorno candidato não corresponde a um único contorno fechado original')
                    record['pillar_handle'] = matching[0]
                    axis = 'x' if face in 'AB' else 'y'
                    anchor = {'A':xmin, 'B':xmax, 'C':ymax, 'D':ymin}[face]
                    low, high = (ymin, ymax) if axis == 'x' else (xmin, xmax)
                    direction = 1 if face in 'BC' else -1
                    candidates = [w for w in walls if w['axis'] == axis and
                                  low-EPS <= w['pos'] <= high+EPS and
                                  abs((w['lo'] if direction > 0 else w['hi'])-anchor) < EPS and
                                  w['hi']-w['lo'] > EPS]
                    pairs = []
                    for i, a in enumerate(candidates):
                        for b in candidates[i+1:]:
                            if (abs(a['lo']-b['lo']) > EPS or abs(a['hi']-b['hi']) > EPS or
                                    abs(a['pos']-b['pos']) <= EPS):
                                continue
                            bottom, top = sorted((a['pos'], b['pos']))
                            near = [t for t in labels if
                                    a['lo']-EPS <= t[axis] <= a['hi']+EPS and
                                    bottom-t['margin'] <= t['y' if axis == 'x' else 'x'] <= top+t['margin']]
                            if not any(t['text'] == record['beam'] for t in near):
                                continue
                            sections = [t for t in near if re.fullmatch(r'\d+(?:[.,]\d+)?/\d+(?:[.,]\d+)?', t['text']) and
                                        abs(float(t['text'].split('/')[0].replace(',', '.'))-(top-bottom)) <= EPS]
                            if len({t['text'] for t in sections}) != 1:
                                continue
                            pairs.append((a, b, bottom, top, sections))
                    if len(pairs) != 1:
                        raise ValueError('par de paredes/rótulo original ausente ou ambíguo; não aprovar por proximidade')
                    a, b, bottom, top, sections = pairs[0]
                    distances = sorted((bottom-low, high-top))
                    section = sections[0]['text']
                    record.update(status='measured', wall_handles=[a['handle'], b['handle']],
                                  section_handles=[t['handle'] for t in sections], section=section,
                                  width_cm=top-bottom, distances_cm=distances,
                                  face_length_cm=high-low)
                    actual = [number(link.get('dist_esq')), number(link.get('dist_dir'))]
                    if None in actual or any(abs(v-e) > EPS for v, e in zip(sorted(actual), distances)):
                        record['errors']['distancias_cantos'] = 'distâncias da ligação divergem das paredes originais; conferir distances_cm e handles'
                    # Every repeated reference to this beam must use the proven section.
                    def visit(value):
                        if isinstance(value, dict):
                            name = value.get('nome', value.get('name'))
                            if name == record['beam'] and 'dim' in value:
                                parts = str(value['dim']).replace(',', '.').split('/')
                                expected = section.replace(',', '.').split('/')
                                try:
                                    agrees = len(parts) == 2 and all(abs(float(v)-float(e)) <= EPS for v,e in zip(parts,expected))
                                except ValueError:
                                    agrees = False
                                if not agrees:
                                    record['errors']['dimensoes'] = 'seção da viga diverge do rótulo e das paredes originais; corrigir todas as referências desta viga'
                            for child in value.values():
                                visit(child)
                        elif isinstance(value, list):
                            for child in value:
                                visit(child)
                    visit(pillar)
                except (ValueError, TypeError, KeyError, IndexError) as exc:
                    record['reason'] = str(exc)
    return dict(schema='cad.qa_original_contacts/v1', source_sha256=_sha256(source),
                tolerance_cm=EPS, contacts=contacts, measured_accuracy=False)


LEVEL_TEXT = re.compile(r'[-+]?\d{3,4}[.,]\d{2}')
HEIGHT_TEXT = re.compile(r'h\s*=\s*(\d+(?:[.,]\d+)?)', re.I)
SLAB_LABEL = re.compile(r'L\d+[A-Z]?')
LAJ_GUARDS = ['identidade_contorno', 'dimensoes_espessura', 'niveis']


def _texts(doc):
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind not in {'TEXT', 'MTEXT'}:
            continue
        text = entity.dxf.text if kind == 'TEXT' else entity.plain_text()
        yield dict(text=' '.join(text.split()), x=float(entity.dxf.insert.x), y=float(entity.dxf.insert.y),
                   handle=entity.dxf.handle)


def measure_slabs(source, snapshot):
    """Rótulo, h= e cota escritos DENTRO do contorno da própria laje (E1).

    Só valor único contido mede; ausência/ambiguidade bloqueia PASS do critério
    (exige incerto) sem bloquear adoção humana: falta de cota não é erro do candidato.
    Consenso de vizinhas não é medido aqui (proibido como prova isolada).
    """
    source = Path(source)
    digest = hashlib.sha256(json.dumps(snapshot.get('collections', {}).get('lajes', []), sort_keys=True,
                                       default=str).encode()).hexdigest()
    return copy.deepcopy(_cached('slabs', source, lambda: _measure_slabs(source, snapshot), digest))


def _measure_slabs(source, snapshot):
    from shapely.geometry import Point, Polygon
    texts = _cached('texts', source, lambda: list(_texts(_readfile(source))))
    contacts = []
    for index, slab in enumerate(snapshot.get('collections', {}).get('lajes', [])):
        unit = f'/collections/lajes/{index}'
        name = str(slab.get('name') or '')
        points = []
        for p in slab.get('points') or []:
            point = (float(p[0]), float(p[1]))
            if not points or abs(point[0]-points[-1][0]) > EPS or abs(point[1]-points[-1][1]) > EPS:
                points.append(point)
        if len(points) > 1 and abs(points[0][0]-points[-1][0]) <= EPS and abs(points[0][1]-points[-1][1]) <= EPS:
            points.pop()
        polygon = Polygon(points) if len(points) >= 3 else None
        if polygon is None or not polygon.is_valid or polygon.area <= EPS:
            contacts.append(dict(unit_path=unit, aspect='contorno', item=name, status='uncertain', errors={},
                                 guards=LAJ_GUARDS, blocks_promotion=False,
                                 reason='contorno degenerado/inválido; medir no CAD manualmente'))
            continue
        inside = [t for t in texts if polygon.contains(Point(t['x'], t['y']))]

        def record(aspect, guard, found, compare):
            values = sorted({v for v, _ in found})
            handles = [h for _, h in found]
            rec = dict(unit_path=unit, aspect=aspect, item=name, status='uncertain', errors={}, guards=[guard],
                       blocks_promotion=False, handles=handles, values=values)
            if len(values) != 1:
                rec['reason'] = (f'{aspect}: nenhum valor escrito dentro do contorno (E1 ausente)' +
                                 ('; padrão do pavimento (NIV-PADRAO-EXCECAO-20261003) só vale sem hachura/corte de exceção, '
                                  'o que este gate não certifica' if aspect.startswith('nível') else '') +
                                 '; exige incerto ou validação humana'
                                 if not values else f'{aspect}: valores distintos dentro do contorno {values}; regiões não certificadas por este gate')
            else:
                rec['status'] = 'measured'
                problem = compare(values[0])
                if problem:
                    rec['errors'][guard] = problem
            contacts.append(rec)

        labels = [(t['text'], t['handle']) for t in inside if SLAB_LABEL.fullmatch(t['text'])]
        record('rótulo', 'identidade_contorno', labels,
               lambda v: None if v == name else f'rótulo contido {v} difere da laje {name}; contorno pode pertencer a outra laje')
        # Degraus: cada região contida é medida contra o próprio degrau; o resto contra a laje.
        regions = []
        for step in slab.get('slab_steps') or []:
            shape = Polygon([(float(p[0]), float(p[1])) for p in step.get('points') or []]) \
                if len(step.get('points') or []) >= 3 else None
            if shape is None or not shape.is_valid or shape.difference(polygon).area > .005 * shape.area:  # ruído de traço, não região fora
                contacts.append(dict(unit_path=unit, aspect='degrau', item=name, status='uncertain', errors={},
                                     guards=['dimensoes_espessura', 'niveis'], blocks_promotion=False,
                                     reason=f"degrau {step.get('uid')} sem região válida contida na laje"))
                regions = None
                break
            regions.append((f"degrau {str(step.get('uid', '')).rsplit(':', 1)[-1]}", shape,
                            number(step.get('height_cm')), number(step.get('level_m'))))
        if regions is None:
            continue
        principal = [t for t in inside if not any(shape.contains(Point(t['x'], t['y'])) for _, shape, _, _ in regions)]
        for label, region, declared_h, declared_n in [('', None, number(slab.get('height')), number(slab.get('nivel')))] + regions:
            pool = principal if region is None else [t for t in inside if region.contains(Point(t['x'], t['y']))]
            suffix = f' ({label})' if label else ''
            heights = [(number(m[1]), t['handle']) for t in pool for m in [HEIGHT_TEXT.fullmatch(t['text'])] if m]
            record('espessura'+suffix, 'dimensoes_espessura', heights,
                   lambda v, h=declared_h, s=suffix: None if h is not None and abs(v-h) <= EPS else
                   f'h={_fmt(v)} escrito{s} difere da espessura declarada {_fmt(h) if h is not None else "ausente"}')
            levels = [(number(t['text'].lstrip('+')), t['handle']) for t in pool if LEVEL_TEXT.fullmatch(t['text'])]
            record('nível'+suffix, 'niveis', levels,
                   lambda v, n=declared_n, s=suffix: None if n is not None and abs(v-n) <= .005 else
                   f'cota {v:.2f}{s} difere do nível declarado {"%.2f" % n if n is not None else "ausente"}'.replace('.', ','))
    return dict(schema='cad.qa_original_slabs/v1', source_sha256=_sha256(source),
                tolerance_cm=EPS, contacts=contacts, guards=LAJ_GUARDS, measured_accuracy=False)


SECTION_TEXT = re.compile(r'(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)')
BEAM_LABEL = re.compile(r'V[A-Z]?\d+[A-Z]?')
FV_GUARDS = ['identidade_contorno', 'dimensoes', 'apoios_limites', 'inventario_segmentos', 'niveis']


def _straight_walls(doc):
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == 'LINE':
            segments = [(entity.dxf.start, entity.dxf.end)]
        elif kind == 'LWPOLYLINE':
            pts = list(entity.get_points('xyb'))
            segments = [(a, b) for a, b in zip(pts, pts[1:] + (pts[:1] if entity.closed else [])) if not a[2]]
        else:
            continue
        for a, b in segments:
            if abs(a[1]-b[1]) < EPS and abs(a[0]-b[0]) > EPS:
                yield dict(axis='x', pos=float(a[1]), lo=min(a[0], b[0]), hi=max(a[0], b[0]), handle=entity.dxf.handle)
            elif abs(a[0]-b[0]) < EPS and abs(a[1]-b[1]) > EPS:
                yield dict(axis='y', pos=float(a[0]), lo=min(a[1], b[1]), hi=max(a[1], b[1]), handle=entity.dxf.handle)


def _dash_patterns(doc, source=None):
    """Tipos de linha tracejados (padrão com ≥1 elemento e comprimento > 0), por nome em maiúsculas.

    O recorte pode citar o tipo de linha sem trazer a definição (13_PAV: ESTILO_TQS_0004
    ausente da tabela LTYPE do recorte); nesse caso a definição vem do DXF original Fase-1.
    """
    def table(d):
        out = {}
        for lt in d.linetypes:
            tags = {t.code: t.value for t in lt.pattern_tags.tags} if lt.pattern_tags else {}
            out[lt.dxf.name.upper()] = int(tags.get(73, 0) or 0) > 0 and float(tags.get(40, 0) or 0) > 0
        return out
    patterns = table(doc)
    if source is not None:
        try:
            original = _original_dxf(source)[0]
            patterns = {**table(_readfile(original)), **{k: v for k, v in patterns.items() if v}}
        except (ValueError, OSError, KeyError, json.JSONDecodeError):
            pass
    return patterns


def _dashed(doc, entity, patterns):
    """Traço tracejado pela definição de tipo de linha (padrão com comprimento), não pelo nome."""
    name = entity.dxf.get('linetype', 'BYLAYER')
    if name.upper() == 'BYLAYER':
        layer = doc.layers.get(entity.dxf.get('layer', '0'))
        name = layer.dxf.get('linetype', 'Continuous') if layer is not None else 'Continuous'
    return bool(patterns.get(name.upper(), False))


def _strokes(doc, source=None):
    """Trechos retos originais (LINE/LWPOLYLINE) e caixas de outras entidades gráficas, com handle."""
    from ezdxf import bbox
    out, patterns = [], _dash_patterns(doc, source)
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == 'LINE':
            pieces = [((entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y))]
        elif kind == 'LWPOLYLINE':
            pts = [p[:2] for p in entity.get_points('xy')]
            pieces = list(zip(pts, pts[1:] + (pts[:1] if entity.closed else [])))
        elif kind in {'CIRCLE', 'ARC', 'ELLIPSE', 'SPLINE', 'HATCH', 'SOLID', 'INSERT', 'POLYLINE'}:
            try:
                box = bbox.extents([entity])
            except Exception:
                continue
            if box.has_data:
                out.append(dict(handle=entity.dxf.handle, kind=kind, box=(box.extmin.x, box.extmin.y, box.extmax.x, box.extmax.y)))
            continue
        else:
            continue
        dashed = _dashed(doc, entity, patterns)
        out += [dict(handle=entity.dxf.handle, kind=kind, a=a, b=b, dashed=dashed) for a, b in pieces
                if math.hypot(b[0]-a[0], b[1]-a[1]) > EPS]
    return out


def _nasce_outlines(source):
    """Contornos fechados reconhecidos como NASCE pela convenção de pilares do pavimento (D-65).

    O símbolo vem do recorte `convencao_pilares_*.dxf` vizinho (no 13_PAV: X); polilinha
    aberta nunca é pilar. Sem convenção única, nenhum contorno é NASCE.
    """
    from shapely.geometry import Polygon
    from portal.app.item_semantics import pillar_source
    from src.core.pillar_convention_recognition import recognize
    data, convention = pillar_source(source)
    if not convention:
        return []
    out = []
    for entity in _readfile(source).modelspace().query('LWPOLYLINE'):
        pts = [tuple(p[:2]) for p in entity.get_points('xy')]
        if len(pts) < 4 or not (entity.closed or math.dist(pts[0], pts[-1]) <= EPS):
            continue
        try:
            poly = Polygon(pts)
        except (ValueError, TypeError):
            continue
        if poly.is_valid and poly.area > 0 and recognize(pts, data, convention)[0] == 'NASCE':
            out.append(dict(handle=entity.dxf.handle, polygon=poly))
    return out


def _interior_marks(strokes, box):
    """Classifica o que o DXF original desenha no interior do fundo (borda excluída).

    Anotação: risco de cota (≤ 15 cm a 45°), linha de cota de uma aresta à outra com
    riscos nas duas pontas, traço tracejado (eixo/projeção). Todo o resto é elemento
    dentro do fundo (pilar, parede, abertura, símbolo) e impede provar ausência de exceção.
    """
    from shapely.geometry import LineString, Point, box as sbox
    xmin, xmax, ymin, ymax = box
    inner = sbox(xmin, ymin, xmax, ymax).buffer(-.5)
    if inner.is_empty:
        return [], []
    near = [s for s in strokes if 'a' in s and LineString([s['a'], s['b']]).distance(inner) <= 5]

    def tick(s):
        dx, dy = abs(s['b'][0]-s['a'][0]), abs(s['b'][1]-s['a'][1])
        return math.hypot(dx, dy) <= 15 and min(dx, dy) >= .6*max(dx, dy)
    ticks = [s for s in near if tick(s)]
    notes, elements = [], []
    for s in strokes:
        if 'box' in s:
            if sbox(*s['box']).intersects(inner):
                elements.append(dict(handle=s['handle'], kind=s['kind']))
            continue
        line = LineString([s['a'], s['b']])
        if not line.intersects(inner):
            continue
        if tick(s):
            notes.append(dict(handle=s['handle'], kind='risco de cota'))
        elif s['dashed'] and not any(sbox(xmin, ymin, xmax, ymax).contains(Point(p)) for p in (s['a'], s['b'])):
            # Eixo/linha de referência atravessa o fundo; figura tracejada dentro dele é elemento projetado.
            notes.append(dict(handle=s['handle'], kind='traço tracejado passante'))
        elif all(any(LineString([t['a'], t['b']]).distance(sbox(*p, *p)) <= 1 for t in ticks if t is not s)
                 for p in (s['a'], s['b'])):
            notes.append(dict(handle=s['handle'], kind='linha de cota'))
        else:
            elements.append(dict(handle=s['handle'], kind=s['kind']))
    return notes, elements


def _covered(intervals, lo, hi):
    total, cursor = 0.0, lo
    for a, b in sorted(intervals):
        a, b = max(a, cursor), min(b, hi)
        if b > a:
            total, cursor = total + b - a, b
    return total


TOUCH_CM = .2  # contorno de laje desenhado na face da viga, com ruído de traço


FILL_MIN_CM = 25    # lado curto do preenchimento dentro da laje; intrusões de seta/pilar <= 14 cm no 13_PAV
NEIGHBOR_CM = 30    # vizinha através de uma viga (bw até 25 cm)
FLOOR_DIR = 'Fase-1_Ingestao'


def _original_dxf(source):
    """Bruto Fase-1 do qual o recorte foi copiado, com a geometria do recorte conferida nele.

    O recorte descarta entidades (no 13_PAV, todos os SOLID); ausência de
    preenchimento só se prova no original.
    """
    source = Path(source)
    crop = json.loads((source.parent / 'crop_result.json').read_text(encoding='utf-8'))
    name = re.split(r'[\\/]', str(crop.get('dxf_bruto') or ''))[-1]
    obra = next((p.parent for p in source.parents if p.name == 'Fase-2_Triagem'), None)
    found = sorted((obra / FLOOR_DIR).rglob(name)) if obra and name else []
    if len(found) != 1:
        raise ValueError(f'DXF original do recorte ({name or "?"}) não localizado de forma única')

    def lines(path):
        return {tuple(round(v, 3) for v in (e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y))
                for e in _readfile(path).modelspace() if e.dxftype() == 'LINE'}
    crop_lines = _cached('lines', source, lambda: lines(source))
    if not crop_lines or not crop_lines <= _cached('lines', found[0], lambda: lines(found[0])):
        raise ValueError('recorte não coincide geometricamente com o DXF original')
    xs = [v for line in crop_lines for v in (line[0], line[2])]
    ys = [v for line in crop_lines for v in (line[1], line[3])]
    return found[0], (min(xs), min(ys), max(xs), max(ys))


def _short_side(geom):
    corners = list(geom.minimum_rotated_rectangle.exterior.coords)
    return min(math.dist(corners[0], corners[1]), math.dist(corners[1], corners[2])) if len(corners) > 2 else 0


def _exception_marks(original, extent):
    """Indicações explícitas de exceção de nível no DXF original (sem nome de layer).

    hatch: HATCH/MPOLYGON e blocos que os contenham (bbox, conservador); fill: componentes
    de SOLID/TRACE (o teste de região é feito na laje); cut: segmento entre duas letras
    maiúsculas isoladas iguais dentro da extensão do recorte (marca de corte; todos os pares).
    """
    from ezdxf import bbox
    from shapely.geometry import LineString, Polygon, box
    from shapely.ops import unary_union
    doc = _readfile(original)
    filled = {b.name for b in doc.blocks if any(e.dxftype() in {'HATCH', 'MPOLYGON', 'SOLID', 'TRACE'} for e in b)}
    hatches, solids, letters = [], [], {}
    for e in doc.modelspace():
        kind = e.dxftype()
        if kind in {'HATCH', 'MPOLYGON'} or (kind == 'INSERT' and e.dxf.name in filled):
            ext = bbox.extents([e])
            if ext.has_data:
                hatches.append((e.dxf.handle, box(ext.extmin.x, ext.extmin.y, ext.extmax.x, ext.extmax.y)))
        elif kind in {'SOLID', 'TRACE'}:
            shape = Polygon([(v.x, v.y) for v in e.wcs_vertices()]).convex_hull
            if shape.area > 0:
                solids.append((e.dxf.handle, shape))
        elif kind in {'TEXT', 'MTEXT'}:
            text = (e.dxf.text if kind == 'TEXT' else e.plain_text()).strip()
            x, y = float(e.dxf.insert.x), float(e.dxf.insert.y)
            if len(text) == 1 and text.isupper() and extent[0] <= x <= extent[2] and extent[1] <= y <= extent[3]:
                letters.setdefault(text, []).append((e.dxf.handle, (float(e.dxf.insert.x), float(e.dxf.insert.y))))
    merged = unary_union([shape.buffer(EPS) for _, shape in solids]) if solids else None
    fills = [([h for h, shape in solids if shape.intersects(part)], part)
             for part in getattr(merged, 'geoms', [merged] if merged is not None else [])]
    cuts = [(f'{k}-{k}', [h1, h2], LineString([p1, p2])) for k, marks in letters.items()
            for i, (h1, p1) in enumerate(marks) for h2, p2 in marks[i+1:]]  # todos os pares: conservador
    return dict(hatches=hatches, fills=fills, cuts=cuts)


def _section_level(original, extent, cut, regions):
    """Leitura do desenho do corte: o nível único que a elevação mostra ao longo da marca.

    Exige, sem nome de layer: título 'CORTE k' único fora do recorte; elevação localizada
    por votos (pontas de segmentos horizontais coincidindo com as fronteiras de laje ao longo
    da marca, s -> ±s + d, >= 6 votos e 5x a 2ª hipótese); cada vão de laje coberto por uma
    linha contínua de topo com a linha da espessura (5–40) abaixo; TODOS os topos na mesma
    altura; exatamente um valor de nível escrito logo acima (<= 40). Retorna
    ((valor, handles), None) ou (None, motivo). O corte pode não resolver centímetros (13_PAV:
    degraus 852,16 desenhados planos), então a leitura só serve para dizer se o corte
    INDICA nível diferente — nunca para atribuir nível a uma laje.
    """
    from collections import Counter
    key, _, line = cut
    doc = _readfile(original)
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    length = math.hypot(x1-x0, y1-y0)
    ux, uy = (x1-x0)/length, (y1-y0)/length

    def along(x, y):
        return (x-x0)*ux + (y-y0)*uy

    def outside(x, y):
        return not (extent[0] <= x <= extent[2] and extent[1] <= y <= extent[3])

    titles, levels, segs, labels = [], [], [], []
    for e in doc.modelspace():
        kind = e.dxftype()
        if kind in {'TEXT', 'MTEXT'}:
            text = ' '.join((e.dxf.text if kind == 'TEXT' else e.plain_text()).split()).upper()
            x, y = float(e.dxf.insert.x), float(e.dxf.insert.y)
            if re.fullmatch(r'[VPL]\d{2,3}[A-Z]?', text):
                labels.append((x, y, text, not outside(x, y)))
            if text == f'CORTE {key}' and outside(x, y):
                titles.append((x, y))
            elif re.fullmatch(r'\d{3}[.,]\d{2}', text) and outside(x, y):
                levels.append((float(text.replace(',', '.')), x, y, e.dxf.handle))
        elif kind in {'LINE', 'LWPOLYLINE'}:
            pts = ([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)] if kind == 'LINE'
                   else [(p[0], p[1]) for p in e.get_points()])
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                if abs(ay-by) < 1e-6 and abs(ax-bx) > 1 and outside(ax, ay) and outside(bx, by):
                    segs.append((round(ay, 2), min(ax, bx), max(ax, bx), e.dxf.handle))
    if len(titles) != 1:
        return None, f'corte {key}: título "CORTE {key}" encontrado {len(titles)} vezes fora do recorte'
    ty = titles[0][1]
    segs = [s for s in segs if abs(s[0]-ty) <= length/2]
    spans = []
    for name, slab in regions.items():
        for part, shape in slab['parts']:
            inter = line.intersection(shape)
            for piece in getattr(inter, 'geoms', [inter]):
                if not piece.is_empty and piece.length > 1:
                    s = sorted(along(*p) for p in piece.coords)
                    spans.append((s[0], s[-1], name, part))
    bounds = {round(v, 1) for a, b, *_ in spans for v in (a, b)}
    votes = Counter()
    for _, a, b, _ in segs:
        for end in (a, b):
            for s in bounds:
                for sign in (1, -1):
                    votes[sign, round(end - sign*s, 1)] += 1
    # Vãos regulares tornam espelho/translação quase empatados nos votos: desempate pelos
    # rótulos únicos (V/P/L) presentes na planta e na elevação, mapeados pela hipótese.
    best = max(votes.values(), default=0)
    hypotheses = [h for h, v in votes.items() if v >= .8*best]
    if best < 6:
        return None, f'corte {key}: elevação não alinhada às lajes da marca ({votes.most_common(2)})'
    names = {}
    for x, y, text, inside in labels:
        if not inside and abs(y-ty) > length/2:
            continue
        names.setdefault(text, {True: [], False: []})[inside].append(along(x, y) if inside else x)
    pairs = [(v[True][0], v[False][0]) for v in names.values() if len(v[True]) == 1 and len(v[False]) == 1]

    def misfit(h):
        sign, offset = h
        off = sorted(abs(sign*s + offset - x) for s, x in pairs)
        return off[len(off)//2] if off else math.inf
    scored = sorted((misfit(h), h) for h in hypotheses)
    if not scored or scored[0][0] > 100 or (len(scored) > 1 and scored[1][0] < 3*scored[0][0]):
        return None, (f'corte {key}: sentido da elevação não decidido por rótulos '
                      f'({[(round(m, 1), h) for m, h in scored[:2]]}, {len(pairs)} rótulos)')
    sign, offset = scored[0][1]
    common, used = None, {}
    for a, b, name, part in spans:
        lo, hi = sorted((sign*a + offset, sign*b + offset))
        covering = {}
        for y in {s[0] for s in segs}:
            pieces = [(s[1], s[2], s[3]) for s in segs if s[0] == y and s[2] > lo and s[1] < hi]
            if hi - lo > 2 and _covered([(p, q) for p, q, _ in pieces], lo + 1, hi - 1) >= hi - lo - 2 - EPS:
                covering[y] = [h for *_, h in pieces]
        paired = {y for y in covering if any(5 <= y-z <= 40 for z in covering)}
        if not paired:
            return None, f'corte {key}: {name}{"/"+part if part else ""} sem topo e espessura desenhados na elevação'
        common = paired if common is None else common & paired
        for y in paired:
            used.setdefault(y, []).extend(covering[y])
    # Outro desenho com os mesmos vãos (ex. corte de outro pavimento) também empareia: vale o
    # topo junto do título, com a 2ª hipótese ao menos 2x mais longe.
    near = sorted(common or [], key=lambda y: abs(y-ty))
    if not near or (len(near) > 1 and abs(near[1]-ty) < 2*abs(near[0]-ty)):
        return None, f'corte {key}: sem topo comum a todas as lajes da marca (degrau desenhado?) {near}'
    top = near[0]
    used = sorted(set(used[top]))
    lo, hi = sorted(sign*v + offset for v in (0, length))
    written = [(v, h) for v, x, y, h in levels if lo <= x <= hi and 0 < y-top <= 40]
    if len({v for v, _ in written}) != 1:
        return None, f'corte {key}: valores de nível acima do topo {sorted({v for v, _ in written})}'
    return (written[0][0], used + [h for _, h in written]), None


def _floor_datum(original, floor, anchors):
    """Nível de saída do pavimento lido na tabela de níveis do bruto (NIV-PADRAO-EXCECAO)."""
    from .preprocessamento.adapters.level_crossing import _floor_reference
    ref = _floor_reference(Path(original), str(floor), None, anchors)
    if ref.get('status') != 'direct_local_reference' or ref.get('unit') != 'm' or ref.get('top') is None:
        raise ValueError(f"nível do pavimento não lido diretamente na tabela do original ({ref.get('status')})")
    return float(ref['top']), ref.get('evidence_handles') or []


def _slab_regions(slabs):
    """Região principal (contorno menos degraus) e degraus de cada laje, com os rótulos de measure_slabs."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    regions = {}
    for s in slabs:
        try:
            shape = Polygon([(float(p[0]), float(p[1])) for p in s.get('points') or []]).buffer(0)
            steps = [(f"degrau {str(st.get('uid', '')).rsplit(':', 1)[-1]}",
                      Polygon([(float(p[0]), float(p[1])) for p in st.get('points') or []]).buffer(0))
                     for st in s.get('slab_steps') or []]
        except (TypeError, ValueError):
            continue
        if not shape.is_empty:
            main = shape.difference(unary_union([sh for _, sh in steps])) if steps else shape
            regions[str(s.get('name'))] = dict(shape=shape, parts=[('', main)] + steps)
    return regions


def _standard_level(name, regions, written, marks, datum, sections=None):
    """Padrão do pavimento na região principal de laje sem cota escrita, só com ausência provada.

    Exige: datum lido na tabela do original; nenhum HATCH, preenchimento de região ou marca
    de corte na laje; e nenhuma regra concorrente discordando (vizinhas com cota escrita
    através de viga: maioria estrita, >= 2, igual ao datum). A vizinhança é guarda contra
    zona de exceção, nunca prova do valor. Sem indicação de exceção e com todas as vizinhas
    escritas <= datum, a laje vale como LIMITE superior (<= datum): o padrão a põe no datum
    e só indicação explícita a poria acima.
    Retorna (valor_exato | None, motivo | None, limite | None).
    """
    if isinstance(datum, str):
        return None, f'{name} sem cota escrita; {datum}', None
    value, handles = datum
    slab = regions[name]
    core = slab['parts'][0][1].buffer(-1)
    found = [f'HATCH {h}' for h, shape in marks['hatches'] if shape.intersects(core)]
    # Preenchimento DA região (lado curto dentro da laje >= FILL_MIN_CM); seta/pilar no canto não é região.
    found += [f'preenchimento {"/".join(hs)}' for hs, shape in marks['fills']
              for part in getattr(shape.intersection(core), 'geoms', [shape.intersection(core)])
              if not part.is_empty and part.area > .01 and _short_side(part) >= FILL_MIN_CM]
    # Corte cujo desenho foi lido (_section_level) e mostra só o datum não indica exceção.
    read = {k: r for k, r in (sections or {}).items() if r[0] and abs(r[0][0]-value) <= .005}
    cuts = [(k, hs) for k, hs, line in marks['cuts'] if line.intersects(slab['shape'])]
    found += [f'corte {k} ({"/".join(hs)})' + (f': {sections[k][1]}' if k in (sections or {}) and sections[k][1] else '')
              for k, hs in cuts if k not in read]
    if found:
        return None, f'{name} sem cota escrita com indicação de exceção no original: {found[:4]}', None
    votes = [written[(n, '')][0] for n, other in regions.items()
             if n != name and (n, '') in written and other['shape'].distance(slab['shape']) <= NEIGHBOR_CM]
    agree = sum(abs(v-value) <= .005 for v in votes)
    if agree < 2 or agree * 2 <= len(votes):
        bound = (value, handles) if votes and max(votes) <= value + .005 else None
        return None, (f'{name} sem cota escrita: vizinhas com cota {sorted(set(votes))} não confirmam o padrão '
                      f'{value:.2f} (zona de exceção possível)').replace('.', ','), bound
    return (value, handles + [h for k, hs in cuts for h in hs + read[k][0][1]]), None, None


def _beam_levels(source, rows, slabs, floor=None):
    """Nível do fundo = maior nível entre as REGIÕES de laje que tocam o segmento.

    Região principal com cota escrita: a cota. Região principal sem cota: padrão do
    pavimento (NIV-PADRAO-EXCECAO) somente com ausência de HATCH/preenchimento/corte
    provada no DXF original. Degrau tocado: precisa da própria cota escrita e, abaixo da
    principal da mesma laje, a viga segue a principal (NIV-VIGA-LAJE-PAINEL: o painel de
    topo fecha a diferença); degrau acima, sem cota ou principal desconhecida = não certifica.
    """
    written = {}
    for c in measure_slabs(source, {'collections': {'lajes': slabs}})['contacts']:
        if c['aspect'].startswith('nível') and c['status'] == 'measured':
            label = c['aspect'][len('nível ('):-1] if c['aspect'] != 'nível' else ''
            written[(c['item'], label)] = (c['values'][0], c['handles'])
    regions = _slab_regions(slabs)
    try:
        original, extent = _original_dxf(source)
        marks = _cached('marks', original, lambda: _exception_marks(original, extent), str(extent))
        sections = {}
        for cut in marks['cuts']:
            if cut[0] not in sections or not sections[cut[0]][0]:
                try:
                    sections[cut[0]] = _cached('section', original, lambda: _section_level(original, extent, cut, regions),
                                               f'{extent}|{cut[0]}|{cut[2].wkt}|{sorted(regions)}')
                except Exception as exc:  # leitura do corte falhou: o corte segue como exceção possível
                    sections[cut[0]] = (None, f'corte {cut[0]}: leitura falhou ({exc})')
        anchors = sorted({v for v, _ in written.values()})
        datum = _cached('datum', original, lambda: _floor_datum(original, floor, anchors), f'{floor}|{anchors}') \
            if floor else 'pavimento não informado; padrão não aplicável'
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        marks, sections, datum = None, {}, f'padrão do pavimento não verificável: {exc}'
    standard = {}

    def principal(name):
        if (name, '') in written:
            return written[(name, '')][0], 'escrita', written[(name, '')][1], None, None
        if marks is None:
            return None, None, [], f'{name} sem cota escrita; {datum}', None
        if name not in standard:
            standard[name] = _standard_level(name, regions, written, marks, datum, sections)
        found, reason, bound = standard[name]
        return (found[0], 'padrão do pavimento', found[1], None, None) if found else (None, None, [], reason, bound)

    from shapely.geometry import Polygon
    contacts = []
    for index, row in enumerate(rows):
        label = f"{row.get('beam_name')} seg {row.get('segment_label', index+1)}"
        rec = dict(unit_path=f'/collections/fundo/{index}', item=label, aspect='nível', status='uncertain',
                   errors={}, guards=['niveis'], blocks_promotion=False)
        contacts.append(rec)
        try:
            segment = Polygon([(float(p[0]), float(p[1])) for p in row.get('points') or []]).buffer(0)
        except (TypeError, ValueError):
            rec['reason'] = 'contorno inválido'
            continue
        sources, reasons, bounds = [], [], []
        for name, slab in regions.items():
            if segment.distance(slab['shape']) > TOUCH_CM:
                continue
            for part, shape in slab['parts']:
                if shape.is_empty or segment.distance(shape) > TOUCH_CM:
                    continue
                value, basis, handles, why, bound = principal(name)
                region = f'{name}/{part}' if part else name
                if not part and bound:
                    bounds.append(dict(region=region, upper=bound[0], handles=bound[1], reason=why))
                    continue
                if part:
                    step = written.get((name, part))
                    if step is None:
                        why = f'{region} sem cota escrita própria'
                    elif value is None:
                        why = why or f'{region}: principal sem nível'
                    elif step[0] > value + .005:
                        why = f'{region} {step[0]:.2f} acima da principal {value:.2f}: mudaria a viga'.replace('.', ',')
                    else:
                        basis = f'principal ({basis}) sobre {region} {step[0]:.2f}, painel de topo'.replace('.', ',')
                        handles = handles + step[1]
                if why:
                    reasons.append(why)
                else:
                    sources.append(dict(region=region, value=value, basis=basis, handles=handles))
        rec.update(sources=sources, bounds=[dict(region=b['region'], upper=b['upper']) for b in bounds],
                   handles=sorted({h for s in sources+bounds for h in s['handles']}))
        top = max((s['value'] for s in sources), default=None)
        if not sources and not reasons and not bounds:
            rec['reason'] = 'nenhuma laje toca o segmento; nível por convenção não certificado'
        elif reasons or top is None or any(b['upper'] > top + .005 for b in bounds):
            reasons += [b['reason'] for b in bounds if top is None or b['upper'] > top + .005]
            rec['reason'] = '; '.join(dict.fromkeys(reasons)) + '; nível não certificado'
        else:
            expected = top
            declared = number(row.get('level'))
            rec.update(status='measured', level_basis=sorted({s['basis'] for s in sources
                                                              if abs(s['value']-expected) <= .005} |
                                                             {f"{b['region']} <= padrão (sem indicação de exceção)" for b in bounds}))
            if declared is None or abs(declared-expected) > .005:
                rec['errors']['niveis'] = (f'maior nível das regiões de laje que tocam {expected:.2f} difere do nível '
                                           f'declarado {"%.2f" % declared if declared is not None else "ausente"}').replace('.', ',')
            # level_slabs do SA = lajes que tocam com a maior cota (fundo_segment_levels).
            top_slabs = sorted({s['region'].split('/')[0] for s in sources if abs(s['value']-expected) <= .005})
            lajes = dict(unit_path=rec['unit_path'], item=label, aspect='lajes', status='measured', errors={},
                         guards=['lajes_aberturas'], blocks_promotion=False, expected_slabs=top_slabs,
                         handles=rec['handles'])
            if sorted(row.get('level_slabs') or []) != top_slabs and bounds:
                lajes.update(status='uncertain', reason='laje só com limite superior pode empatar na maior cota')
            elif sorted(row.get('level_slabs') or []) != top_slabs:
                lajes['errors']['lajes_aberturas'] = (f'lajes do nível {sorted(row.get("level_slabs") or [])} ≠ '
                                                      f'lajes que tocam com a maior cota {top_slabs}')
            contacts.append(lajes)
    return contacts


def _beam_texts(doc):
    texts = []
    for entity in doc.modelspace():
        if entity.dxftype() not in {'TEXT', 'MTEXT'}:
            continue
        text = entity.dxf.text if entity.dxftype() == 'TEXT' else entity.plain_text()
        rotation = float(getattr(entity.dxf, 'rotation', 0) or 0) % 180
        texts.append(dict(text=' '.join(text.split()), x=float(entity.dxf.insert.x), y=float(entity.dxf.insert.y),
                          handle=entity.dxf.handle, axis='x' if min(rotation, 180-rotation) < 1 else
                          'y' if abs(rotation-90) < 1 else None,
                          margin=max(float(getattr(entity.dxf, 'height', 0) or getattr(entity.dxf, 'char_height', 0) or 0)*2, EPS)))
    return texts


def measure_beams(source, snapshot, slabs=None, floor=None):
    """Fundo de viga FV: arestas longas sobre paredes originais + seção bw/h na faixa.

    identidade_contorno: as duas arestas longas do retângulo do segmento precisam
    coincidir com traços originais colineares (aresta sem traço algum = polígono
    deslocado, caso V304). dimensoes: um único bw escrito na faixa da própria viga
    (texto alinhado ao eixo, com o nome da viga na mesma faixa) comparado à largura
    declarada. Comprimento e nível não são certificados aqui.
    """
    from shapely.geometry import LineString, box as sbox
    source = Path(source)
    walls = _cached('walls', source, lambda: list(_straight_walls(_readfile(source))))
    texts = _cached('beam_texts', source, lambda: _beam_texts(_readfile(source)))
    strokes = _cached('strokes', source, lambda: _strokes(_readfile(source), source))
    try:
        nasce_outlines = _cached('nasce', source, lambda: _nasce_outlines(source))
    except (ImportError, OSError, ValueError):
        nasce_outlines = []
    # Preenchimentos (HATCH/SOLID) só existem com certeza no original: o recorte descarta SOLID.
    try:
        original, extent = _original_dxf(source)
        marks = _cached('marks', original, lambda: _exception_marks(original, extent), str(extent))
        original_fills = [(h, shape) for h, shape in marks['hatches']] +                          [(handles[0] if handles else '?', part) for handles, part in marks['fills']]
        fills_error = None
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        original_fills, fills_error = [], str(exc)
    rows = snapshot.get('collections', {}).get('fundo', [])
    boxes = []
    for p in rows:
        try:
            xs, ys = [float(v[0]) for v in p.get('points') or []], [float(v[1]) for v in p.get('points') or []]
            box = (min(xs), max(xs), min(ys), max(ys))
            if not all(abs(x-box[0]) < EPS or abs(x-box[1]) < EPS for x in xs) or \
                    not all(abs(y-box[2]) < EPS or abs(y-box[3]) < EPS for y in ys) or \
                    box[1]-box[0] <= EPS or box[3]-box[2] <= EPS:
                raise ValueError
            boxes.append(box)
        except ValueError:
            boxes.append(None)
    contacts = []
    for index, row in enumerate(rows):
        unit = f'/collections/fundo/{index}'
        name = str(row.get('beam_name') or '')
        label = f"{name} seg {row.get('segment_label', index+1)}"
        box = boxes[index]
        if box is None:
            contacts.append(dict(unit_path=unit, item=label, aspect='contorno', status='uncertain', errors={},
                                 guards=FV_GUARDS, blocks_promotion=False,
                                 reason='contorno não retangular/alinhado aos eixos; medir no CAD manualmente'))
            continue
        xmin, xmax, ymin, ymax = box
        axis = 'x' if xmax-xmin >= ymax-ymin else 'y'
        lo, hi, edges = (xmin, xmax, (ymin, ymax)) if axis == 'x' else (ymin, ymax, (xmin, xmax))
        length = hi - lo
        edge = dict(unit_path=unit, item=label, aspect='arestas', status='uncertain', errors={},
                    guards=['identidade_contorno'], blocks_promotion=False)
        coverage, handles = [], []
        for pos in edges:
            hits = [w for w in walls if w['axis'] == axis and abs(w['pos']-pos) < EPS and w['hi'] > lo and w['lo'] < hi]
            coverage.append(_covered([(w['lo'], w['hi']) for w in hits], lo, hi) / length)
            handles.append(sorted({w['handle'] for w in hits}))
        edge.update(coverage=[round(c, 3) for c in coverage], wall_handles=handles)
        if min(coverage) <= 0:
            edge['status'] = 'measured'
            edge['errors']['identidade_contorno'] = ('aresta longa sem traço original colinear; retângulo do fundo '
                                                      'pode estar deslocado da viga desenhada')
        elif min(coverage) >= .5:
            edge['status'] = 'measured'
        else:
            edge['reason'] = f'arestas cobertas só em {min(coverage):.0%} por traços originais; conferir no CAD'
        contacts.append(edge)
        # Extremos: traço original perpendicular ao eixo cobrindo a faixa (parede de viga
        # que cruza, face de pilar sólido, fim da viga). Corte por rótulo não deixa traço.
        cross_axis = 'y' if axis == 'x' else 'x'
        band = edges[1] - edges[0]

        def closing(pos):
            at = [w for w in walls if w['axis'] == cross_axis and abs(w['pos']-pos) < EPS]
            hits = [w for w in at if w['hi'] > edges[0]+EPS and w['lo'] < edges[1]-EPS]
            share = _covered([(w['lo'], w['hi']) for w in hits], edges[0], edges[1]) / band
            # Parede de viga que cruza desenhada interrompida: chega às duas arestas por fora.
            sides = sorted({s for w in at for s, ok in
                            (('abaixo', abs(w['hi']-edges[0]) < EPS), ('acima', abs(w['lo']-edges[1]) < EPS)) if ok})
            kind = ('traço fecha a faixa' if share >= 1 - EPS / band else
                    'paredes perpendiculares chegam às duas arestas' if sides == ['abaixo', 'acima'] else None)
            return kind, at, share, sides
        # Faixa = segmentos colineares desta viga com as mesmas arestas.
        chain = [b for i, b in enumerate(boxes) if b and str(rows[i].get('beam_name') or '') == name and
                 ((axis == 'x' and abs(b[2]-ymin) < EPS and abs(b[3]-ymax) < EPS) or
                  (axis == 'y' and abs(b[0]-xmin) < EPS and abs(b[1]-xmax) < EPS))]
        c_lo = min(b[0] if axis == 'x' else b[2] for b in chain)
        c_hi = max(b[1] if axis == 'x' else b[3] for b in chain)
        across = 'y' if axis == 'x' else 'x'

        def in_band(t, a, b):
            return (t['axis'] == axis and a-EPS <= t[axis] <= b+EPS and
                    edges[0]-t['margin'] <= t[across] <= edges[1]+t['margin'])

        def depths(found):
            return sorted({number(SECTION_TEXT.fullmatch(t['text'])[2]) for t in found})
        own_depth = depths([t for t in texts if in_band(t, lo, hi) and SECTION_TEXT.fullmatch(t['text'])]) or \
            depths([t for t in texts if in_band(t, c_lo, c_hi) and SECTION_TEXT.fullmatch(t['text'])])

        def lateral(end, end_name, side):
            """Viga chegando de um lado só (T): par de paredes perpendiculares encostadas por fora
            na mesma aresta, aresta oposta contínua, vizinho da mesma viga emendado ou após o vão.
            Regra: alturas iguais → a que chega atravessa (D-90/FV); diferentes → a mais funda
            cruza (FV.md §4). Retorna (limite, erro, fatos) ou None se não medido."""
            near, far = (edges[1], edges[0]) if side == 'acima' else (edges[0], edges[1])
            def touches(w):
                return abs((w['lo'] if side == 'acima' else w['hi']) - near) < EPS
            spans = [(b[0], b[1]) if axis == 'x' else (b[2], b[3]) for b in chain if b != box]
            for partner in sorted({round(w['pos'], 4) for w in walls if w['axis'] == cross_axis and touches(w) and
                                   10-EPS <= abs(w['pos']-end) <= 40+EPS}, key=lambda p: abs(p-end)):
                a, b = sorted((end, partner))
                if _covered([(w['lo'], w['hi']) for w in walls if w['axis'] == axis and abs(w['pos']-far) < EPS],
                            a, b) < b-a-EPS:
                    continue
                outward = partner > end if end_name == 'fim' else partner < end
                joint = [s for s in spans if abs((s[0] if end_name == 'fim' else s[1]) - end) < EPS]
                gap = [s for s in spans if outward and abs((s[0] if end_name == 'fim' else s[1]) - partner) < EPS]
                if not joint and not gap:
                    continue
                reach = (near, near+600) if side == 'acima' else (near-600, near)
                arriving = depths([t for t in texts if t['axis'] == cross_axis and SECTION_TEXT.fullmatch(t['text']) and
                                   a-t['margin'] <= t[axis] <= b+t['margin'] and
                                   reach[0]-EPS <= t[across] <= reach[1]+EPS])
                facts = dict(arriving_walls=[_fmt(a), _fmt(b)], arriving_depth=arriving, own_depth=own_depth,
                             continuation='emendado' if joint else 'após o vão da viga que chega')
                if len(arriving) != 1 or len(own_depth) != 1:
                    return None, None, facts
                own, other = own_depth[0], arriving[0]
                if joint:
                    if own > other:
                        return 'chegada lateral: viga mais funda passa, troca de painel (FV.md §4)', None, facts
                    if own < other:
                        return None, (f'viga que chega (h={_fmt(other)}) é mais funda e deveria cruzar; fundo '
                                      f'h={_fmt(own)} segue emendado (FV.md §4)'), facts
                    return None, None, facts  # mesma altura emendada: D-90 depende do toco; não medido
                if own > other:
                    return None, (f'fundo h={_fmt(own)} interrompido por viga mais rasa h={_fmt(other)}; '
                                  'a mais funda cruza (FV.md §4)'), facts
                return ('chegada lateral: viga que chega atravessa (D-90/FV)' if own == other else
                        'chegada lateral: viga mais funda cruza (FV.md §4)'), None, facts
            return None

        for end_name, end in (('início', lo), ('fim', hi)):
            kind, at_end, share, sides = closing(end)
            rec = dict(unit_path=unit, item=label, aspect=f'extremo {end_name}', status='uncertain', errors={},
                       guards=['apoios_limites', 'dimensoes'], blocks_promotion=False, coverage=round(share, 3),
                       touching_sides=sides, wall_handles=sorted({w['handle'] for w in at_end}))
            # Extremo além do limite: entre o extremo e um limite interno a ≤ 40 cm nenhuma aresta longa
            # tem traço (faixa da viga/pilar que cruza ficou dentro do fundo).
            inner = [w['pos'] for w in walls if w['axis'] == cross_axis and 10-EPS <= abs(w['pos']-end) <= 40+EPS and
                     lo-EPS <= w['pos'] <= hi+EPS and w['hi'] >= edges[0]-EPS and w['lo'] <= edges[1]+EPS]
            overrun = next((p for p in sorted(set(inner), key=lambda p: abs(p-end)) if closing(p)[0] and not any(
                _covered([(w['lo'], w['hi']) for w in walls if w['axis'] == axis and abs(w['pos']-e) < EPS],
                         min(p, end), max(p, end)) > EPS for e in edges)), None)
            # Elemento atravessado na ponta: paredes no limite interno e no extremo passam da faixa
            # (pilar maior que a viga ou viga que cruza com contorno colinear às arestas).
            def beyond(pos):
                return any(abs(w['pos']-pos) < EPS and w['hi'] >= edges[0]-EPS and w['lo'] <= edges[1]+EPS and
                           (w['lo'] < edges[0]-EPS or w['hi'] > edges[1]+EPS) for w in walls if w['axis'] == cross_axis)
            tip = None if overrun is not None or not kind or not beyond(end) else next(
                (p for p in sorted(set(inner), key=lambda p: abs(p-end)) if closing(p)[0] and beyond(p)), None)
            tip_depth = [] if tip is None else depths(
                [t for t in texts if t['axis'] == cross_axis and SECTION_TEXT.fullmatch(t['text']) and
                 min(tip, end)-t['margin'] <= t[axis] <= max(tip, end)+t['margin'] and
                 edges[0]-600 <= t[across] <= edges[1]+600])
            if kind and overrun is not None:
                message = (f'extremo {end_name} avança {_fmt(abs(overrun-end))} cm sobre a faixa sem paredes '
                           'da viga/pilar que cruza; limite desenhado antes dela')
                rec.update(status='measured', limit=kind, nearest_limit=overrun,
                           errors={'apoios_limites': message, 'dimensoes': message})
            elif tip is not None:
                # Só a viga mais funda avança até lá (FV.md §4), mas a seção na faixa atravessada não prova
                # que o elemento é viga e não pilar (mutação ±bw passou com essa exceção): não certifica.
                rec.update(nearest_limit=tip, crossing_depth=tip_depth,
                           reason=(f'extremo na face distante de elemento atravessado ({_fmt(abs(tip-end))} cm); '
                                   'atravessar exige provar viga mais funda (FV.md §4)'))
            elif kind:
                rec.update(status='measured', limit=kind)
            elif not at_end:
                # Sem traço algum no extremo: procura o limite original mais próximo na faixa.
                near = sorted({round(w['pos'], 4) for w in walls if w['axis'] == cross_axis and
                               0 < abs(w['pos']-end) <= 2*band and w['hi'] >= edges[0]-EPS and w['lo'] <= edges[1]+EPS},
                              key=lambda p: abs(p-end))
                found = next((p for p in near if closing(p)[0]), None)
                if found is None:
                    rec['reason'] = 'nenhum traço original perpendicular no extremo nem limite próximo; conferir no CAD'
                else:
                    rec.update(status='measured', nearest_limit=found)
                    message = (f'extremo {end_name} sem traço original; limite desenhado mais próximo a '
                               f'{_fmt(abs(found-end))} cm (corte por rótulo/linha interrompida?)')
                    rec['errors'] = {'apoios_limites': message, 'dimensoes': message}
            else:
                found = lateral(end, end_name, sides[0]) if len(sides) == 1 else None
                if found and (found[0] or found[1]):
                    rec.update(status='measured', limit=found[0] or 'chegada lateral', lateral=found[2])
                    if found[1]:
                        rec['errors'] = {'apoios_limites': found[1]}
                else:
                    if found:
                        rec['lateral'] = found[2]
                    rec['reason'] = (f'traço perpendicular só de um lado {sides} / {share:.0%} da faixa; '
                                     'natureza do limite não medida')
            contacts.append(rec)
        overlaps = [rows[i].get('segment_label', i+1) for i, b in enumerate(boxes) if i != index and b in chain and
                    min(hi, b[1] if axis == 'x' else b[3]) - max(lo, b[0] if axis == 'x' else b[2]) > EPS]
        contacts.append(dict(unit_path=unit, item=label, aspect='sobreposição', status='measured',
                             guards=['inventario_segmentos'], blocks_promotion=False, overlaps=overlaps,
                             errors={'inventario_segmentos': f'segmento sobreposto a {overlaps} da mesma viga'}
                             if overlaps else {}))
        names = {t['text'] for t in texts if in_band(t, c_lo, c_hi) and BEAM_LABEL.fullmatch(t['text'])}
        sections = [t for t in texts if in_band(t, lo, hi) and SECTION_TEXT.fullmatch(t['text'])] or \
                   [t for t in texts if in_band(t, c_lo, c_hi) and SECTION_TEXT.fullmatch(t['text'])]
        widths = sorted({number(SECTION_TEXT.fullmatch(t['text'])[1]) for t in sections})
        dim = dict(unit_path=unit, item=label, aspect='seção', status='uncertain', errors={}, guards=['dimensoes'],
                   blocks_promotion=False, names=sorted(names), sections=sorted({t['text'] for t in sections}),
                   section_handles=[t['handle'] for t in sections], band_width_cm=edges[1]-edges[0])
        if not names and len(widths) == 1:
            # Rótulo da viga fora da faixa (ex.: V306): a seção vale se nenhum outro rótulo disputa a faixa.
            dim['basis'] = 'única seção escrita na faixa, sem rótulo de outra viga'
        if names and names != {name}:
            dim['reason'] = (f'rótulos na faixa {sorted(names)} não identificam só {name}; seção não atribuída')
        elif len(widths) != 1:
            dim['reason'] = ('nenhuma seção bw/h escrita na faixa' if not widths else
                             f'larguras distintas na faixa {widths}') + '; conferir no CAD'
        else:
            dim['status'] = 'measured'
            declared = number(row.get('width'))
            if declared is None or abs(declared-widths[0]) > EPS:
                dim['errors']['dimensoes'] = (f'bw={_fmt(widths[0])} escrito na faixa difere da largura declarada '
                                              f'{_fmt(declared) if declared is not None else "ausente"}')
            if abs(widths[0]-(edges[1]-edges[0])) > EPS:
                dim['errors']['identidade_contorno'] = (f'largura do retângulo {_fmt(edges[1]-edges[0])} difere do '
                                                        f'bw={_fmt(widths[0])} escrito na viga')
        contacts.append(dim)
        # Exceções (furo/recorte/abertura/pilar dentro do fundo): o SA não declara nenhuma no fundo;
        # ausência só se prova quando o interior original tem apenas anotação.
        notes, elements = _interior_marks(strokes, box)
        inner_box = sbox(box[0], box[2], box[1], box[3]).buffer(-.5)
        elements += [dict(handle=h, kind='preenchimento no DXF original') for h, shape in original_fills
                     if shape.intersects(inner_box)]
        # Pilar que nasce (D-65) não é sólido aqui: contorno e X dele são anotação para o fundo.
        nasce = [n for n in nasce_outlines if n['polygon'].intersects(sbox(box[0], box[2], box[1], box[3]))]
        if nasce:
            by_handle = {s['handle']: s for s in strokes}
            def in_nasce(e):
                s = by_handle.get(e['handle'])
                return any(n['handle'] == e['handle'] or (s and 'a' in s and n['polygon'].buffer(.5).covers(
                    LineString([s['a'], s['b']]))) for n in nasce)
            notes += [dict(e, kind='pilar que nasce (D-65)') for e in elements if in_nasce(e)]
            elements = [e for e in elements if not in_nasce(e)]
        contacts.append(dict(unit_path=unit, item=label, aspect='aberturas', guards=['lajes_aberturas'],
                             blocks_promotion=False, errors={}, annotations=len(notes),
                             status='uncertain' if elements or fills_error else 'measured',
                             element_handles=sorted({e['handle'] for e in elements}),
                             **({'reason': f'{len(elements)} traço(s)/preenchimento(s) não-anotação dentro do fundo '
                                           f'(pilar sólido, seção preenchida ou abertura?); exceção não medida'}
                                if elements else {'reason': f'preenchimentos do DXF original não conferidos: {fills_error}'}
                                if fills_error else
                                {'basis': 'interior só com anotação (cota/tracejado/pilar que nasce) ou vazio, '
                                          'sem preenchimento no DXF original'})))
        # Coerência interna dos campos do SA (consistencia_alertas): comprimento/largura do
        # contorno, nível presente quando válido, lajes do nível coerentes com a origem.
        problems = []
        declared_length, declared_width = number(row.get('length')), number(row.get('width'))
        if declared_length is None or abs(declared_length-length) > EPS:
            problems.append(f'length {row.get("length")} ≠ extensão do contorno {_fmt(length)}')
        if declared_width is None or abs(declared_width-(edges[1]-edges[0])) > EPS:
            problems.append(f'width {row.get("width")} ≠ largura do contorno {_fmt(edges[1]-edges[0])}')
        if row.get('status') == 'valid' and number(row.get('level')) is None:
            problems.append('status valid sem nível')
        source_kind = row.get('level_source')
        if (source_kind == 'highest_touching_slab') != bool(row.get('level_slabs')):
            problems.append(f'level_source {source_kind} incoerente com level_slabs {row.get("level_slabs")}')
        contacts.append(dict(unit_path=unit, item=label, aspect='coerência', guards=['consistencia_alertas'],
                             blocks_promotion=False, status='measured',
                             errors={'consistencia_alertas': '; '.join(problems)} if problems else {}))
    if slabs is not None:
        contacts += _beam_levels(source, rows, slabs, floor)
    return dict(schema='cad.qa_original_beams/v1', source_sha256=_sha256(source),
                tolerance_cm=EPS, contacts=contacts, guards=FV_GUARDS, measured_accuracy=False)


_SVG_TEXT = re.compile(r'<text ([^>]*)transform="rotate\((-?[\d.]+) (-?[\d.]+) (-?[\d.]+)\)"[^>]*>([^<]*)</text>')
_SVG_LINE = re.compile(r'd="M (-?[\d.]+) (-?[\d.]+)\s+L (-?[\d.]+) (-?[\d.]+)\s*"')
_SVG_MARK = re.compile(r'<use [^>]*x="(-?[\d.]+)" y="(-?[\d.]+)"')


def _svg_frame(svg, source):
    """Transformação DXF→SVG do desenho matplotlib (aspecto igual), medida no próprio SVG.

    x: textos do DXF original de conteúdo único, horizontais e centrados (x exato no SVG);
    y: linhas horizontais do DXF reencontradas no SVG pelo x já ajustado (votação).
    Devolve (a, b, c) com svg_x = a·X + b e svg_y = c − a·Y, ou motivo de falha.
    """
    import html
    from collections import Counter, defaultdict
    doc = _readfile(source)
    by_text = defaultdict(list)
    for t in _cached('beam_texts', source, lambda: _beam_texts(doc)):
        by_text[t['text']].append(t)
    pairs = []
    for attrs, rot, x, _, text in _SVG_TEXT.findall(svg):
        text = ' '.join(html.unescape(text).split())
        if abs(float(rot)) < 1 and 'text-anchor: middle' in attrs and len(by_text.get(text, [])) == 1:
            pairs.append((by_text[text][0]['x'], float(x)))
    if len(pairs) < 3:
        return None, f'{len(pairs)} textos do DXF reconhecidos no SVG (mínimo 3)'
    mx = sum(p[0] for p in pairs)/len(pairs)
    my = sum(p[1] for p in pairs)/len(pairs)
    var = sum((p[0]-mx)**2 for p in pairs)
    if var <= 0:
        return None, 'textos reconhecidos sem dispersão em x'
    a = sum((p[0]-mx)*(p[1]-my) for p in pairs)/var
    b = my - a*mx
    residual = max(abs(a*p[0]+b-p[1]) for p in pairs)
    if a <= 0 or residual > .01:
        return None, f'textos do DXF não alinham com o SVG (resíduo {residual:.3f} px)'
    spans = defaultdict(list)
    for x1, y1, x2, y2 in (tuple(map(float, m)) for m in _SVG_LINE.findall(svg)):
        if abs(y1-y2) < 1e-6:
            spans[(round(min(x1, x2), 2), round(max(x1, x2), 2))].append(y1)
    votes = Counter()
    for e in doc.modelspace().query('LINE'):
        s0, s1 = e.dxf.start, e.dxf.end
        if abs(s0.y-s1.y) < 1e-6 and abs(s0.x-s1.x) > EPS:
            for y in spans.get((round(a*min(s0.x, s1.x)+b, 2), round(a*max(s0.x, s1.x)+b, 2)), []):
                votes[round(y + a*s0.y, 2)] += 1
    ranked = votes.most_common(2)
    if not ranked or ranked[0][1] < 6 or (len(ranked) > 1 and ranked[0][1] < 5*ranked[1][1]):
        return None, f'eixo y do SVG não determinado pelas linhas do DXF ({ranked})'
    return (a, b, ranked[0][0]), None


def measure_fv_tags(source, snapshot, svg):
    """tags_lideres FV no SVG SA real: cada tag S# aponta (marcador do líder) para dentro do próprio segmento.

    O SVG da camada SA vem de render pré-gerado; tag velha, faltante, duplicada ou apontando
    para outro segmento é FAIL. Sem transformação DXF→SVG medida, nada é certificado.
    """
    from shapely.geometry import Point, Polygon
    rows = (snapshot or {}).get('collections', {}).get('fundo', [])
    units = [(f'/collections/fundo/{i}', f"{r.get('beam_name')} seg {r.get('segment_label', i+1)}",
              str(r.get('segment_label', i+1)), r) for i, r in enumerate(rows)]
    contacts = []
    frame, why = _svg_frame(svg or '', Path(source)) if svg and '<svg' in svg else (None, 'SVG SA ausente')
    if frame is None:
        for unit, item, _, _ in units:
            contacts.append(dict(unit_path=unit, item=item, aspect='tag', guards=['tags_lideres'], status='uncertain',
                                 errors={}, blocks_promotion=False, reason=why))
        return contacts
    a, b, c = frame
    import html
    marks = [(float(x), float(y)) for x, y in _SVG_MARK.findall(svg)]
    tags = []
    for attrs, rot, x, y, text in _SVG_TEXT.findall(svg):
        text = html.unescape(text).strip()
        if re.fullmatch(r'S\S+', text) and abs(float(rot)) < 1 and 'font-weight: 700' in attrs:
            tags.append(dict(label=text[1:], x=float(x), y=float(y), vertical='text-anchor: end' in attrs))
    from src.ui.widgets.fv_hifi_n1_render import _normalize_segments
    polys = {lab: Polygon(r['points']) for _, _, lab, r in units}
    # Âncora do líder = a mesma que o renderer calcula do polígono; marcador fora dela = render de outro SA.
    anchors = {str(seg['label']): seg['c'] for seg in _normalize_segments(
        [dict(points=r['points'], label=lab) for _, _, lab, r in units])}
    def owner(m):
        point = Point((m[0]-b)/a, (c-m[1])/a)
        exact = [lab for lab, xy in anchors.items() if math.dist(xy, (point.x, point.y)) <= .5]
        if exact:
            return exact[0]
        inside = [lab for lab, poly in polys.items() if poly.covers(point)]
        return f'{inside[0]} (fora da âncora: render de outro SA)' if len(inside) == 1 else None
    paired = {}
    for t in tags:
        if t['vertical']:
            cands = [m for m in marks if m[0] > t['x'] and abs(m[1]-t['y']) <= 6]
            key = lambda m: m[0]-t['x']
        else:
            cands = [m for m in marks if abs(m[0]-t['x']) <= .01 and m[1] > t['y']]
            key = lambda m: m[1]-t['y']
        m = min(cands, key=key) if cands else None
        paired.setdefault(t['label'], []).append(owner(m) if m else 'sem marcador')
    stray = sorted(set(paired) - set(polys))
    for unit, item, lab, _ in units:
        rec = dict(unit_path=unit, item=item, aspect='tag', guards=['tags_lideres'], status='measured', errors={},
                   blocks_promotion=False)
        got = paired.get(lab, [])
        problems = []
        if len(got) != 1:
            problems.append(f'{len(got)} tags S{lab} no SVG SA (esperado 1)')
        elif got[0] != lab:
            problems.append(f'líder da tag S{lab} aponta para {"o segmento "+got[0] if got[0] and got[0] != "sem marcador" else got[0] or "fora de qualquer segmento"}')
        if stray:
            problems.append(f'tags sem segmento no SA: {", ".join("S"+s for s in stray)} (render velho?)')
        if problems:
            rec['errors'] = {'tags_lideres': '; '.join(problems)}
        else:
            rec['basis'] = 'tag única S# com líder dentro do próprio contorno (transformação DXF→SVG medida)'
        contacts.append(rec)
    return contacts


def _fmt(value):
    return f'{value:.1f}'.rstrip('0').rstrip('.').replace('.', ',')


def for_snapshot(obra_dir, pavimento, snapshot):
    measurer = {'PIL': measure, 'LAJ': measure_slabs, 'FV': measure_beams}.get((snapshot or {}).get('classe'))
    if not measurer:
        return None
    from . import ficha_reader
    try:
        source = ficha_reader._fonte_estrutural_producao(Path(obra_dir), pavimento)
        if not source:
            raise ValueError('DXF original indisponível')
        if snapshot.get('classe') == 'FV':
            from . import qa_interpretation
            state = ficha_reader.ler_estado_pavimento(Path(obra_dir), pavimento)
            slabs = [row for item in ficha_reader.listar_itens_n1(state, 'lajes')
                     for row in qa_interpretation.snapshot(state, 'LAJ', item['item_id'])['collections']['lajes']]
            return measure_beams(source, snapshot, slabs, pavimento)
        return measurer(source, snapshot)
    except Exception as exc:
        guards = {'LAJ': LAJ_GUARDS, 'FV': FV_GUARDS}.get(snapshot.get('classe'))
        return dict(schema='cad.qa_original_contacts/v1', contacts=[], error=str(exc), measured_accuracy=False,
                    **({'guards': guards} if guards else {}))


def errors(report, checks=None):
    if not report:
        return []
    approved = None if checks is None else {c['id'] for c in checks if c.get('status') == 'pass'}
    result = []
    if report.get('error'):
        guards = set(report.get('guards') or {'dimensoes', 'distancias_cantos'})
        return ['CAD original: '+report['error']] if approved is None or approved & guards else []
    for c in report.get('contacts', []):
        where = f"face {c['face']} {c['beam']}" if 'face' in c else f"{c.get('item')} {c.get('aspect')}"
        prefix = f"CAD original {c['unit_path']} {where}: "
        if c['status'] != 'measured':
            guards = set(c.get('guards') or {'dimensoes', 'distancias_cantos'})
            if approved is None and not c.get('blocks_promotion', True):
                continue
            if approved is None or approved & guards:
                result.append(prefix+c['reason'])
        else:
            result.extend(prefix+message for criterion,message in c['errors'].items()
                          if approved is None or criterion in approved)
    return result
