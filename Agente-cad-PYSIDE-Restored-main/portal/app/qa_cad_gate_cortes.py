"""Gate CAD da Visão Corte (D-92): níveis e dimensões de cada corte de viga e degrau de laje.

Mede no DXF original, sem nome de layer e sem reler o SA:

- **corte original de viga** (o T/L desenhado em planta): bw, h e, por braço de
  laje, espessura e desnível até o topo, comparados com o que o SA leu (ficha);
- **corte interpretado** (calculado pelo SA): o desnível de cada laje até o topo
  da viga e a espessura, contra as cotas e ``h=`` escritas dentro das lajes;
- **degrau de laje**: o corte original do degrau (duas espessuras e o desnível)
  contra a região rebaixada declarada; degrau sem corte original fica incerto;
- **segmento de viga sem corte**: incerto (nada a conferir).

Os lados A/B do desenho dependem da orientação do símbolo; o gate compara o
conjunto de braços e diz qual atribuição explica o desenho, sem certificar A/B.
"""
from __future__ import annotations

import math
from collections import defaultdict

from . import qa_cad_gate as gate

TOL_CM = .5          # desenho do corte: medidas inteiras em cm, traço com ruído
ARM_MIN_CM = 3.      # braço de laje real sai >= 20 cm da alma; espora de 1 cm é ruído de traço
LEVEL_TOL_CM = .5    # cotas com duas casas (1 cm) -> meia unidade
VC_GUARDS = ['dimensoes', 'niveis', 'degraus', 'inventario_segmentos']


def _num(value):
    return gate.number(value)


def _fmt(value):
    return gate._fmt(value)


def _lvl(value):
    return f'{value:.2f}'.replace('.', ',')


# --------------------------------------------------------------------------
# Geometria do símbolo de corte
# --------------------------------------------------------------------------

def _closed_polygons(source):
    """Polígonos fechados do DXF (qualquer layer), em cache por arquivo."""
    def build():
        from shapely.geometry import Polygon
        doc = gate._readfile(source)
        result = []
        for entity in doc.modelspace().query('LWPOLYLINE POLYLINE'):
            try:
                if entity.dxftype() == 'LWPOLYLINE':
                    pts = [tuple(p[:2]) for p in entity.get_points()]
                    closed = entity.closed
                else:
                    pts = [tuple(v.dxf.location)[:2] for v in entity.vertices]
                    closed = entity.is_closed
            except Exception:
                continue
            if len(pts) >= 3 and (closed or math.dist(pts[0], pts[-1]) <= gate.EPS):
                poly = Polygon(pts)
                if poly.is_valid and poly.area > 1:
                    result.append((poly, entity.dxf.handle))
        return result
    return gate._cached('vc_closed', source, build)


def _source_shape(source, points):
    """União das peças fechadas do DXF que formam o símbolo apontado pelo SA."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    hint = Polygon(points).buffer(.5)
    if not hint.is_valid or hint.area <= 1:
        return None, []
    parts = [(p, h) for p, h in _closed_polygons(source)
             if p.intersects(hint) and p.intersection(hint).area >= .9*p.area]
    if not parts:
        return None, []
    return unary_union([p for p, _ in parts]), [h for _, h in parts]


def _slices(shape, axis, sign):
    """Faixas ao longo do eixo da altura: [(u0, u1, [(v0, v1), ...])], topo em u=0."""
    from shapely.geometry import LineString
    x0, y0, x1, y1 = shape.bounds
    if axis == 'y':
        top = y1 if sign < 0 else y0
        to_u = (lambda y: (top-y)) if sign < 0 else (lambda y: (y-top))
        length = y1-y0
    else:
        top = x1 if sign < 0 else x0
        to_u = (lambda x: (top-x)) if sign < 0 else (lambda x: (x-top))
        length = x1-x0
    coords = [c for g in getattr(shape, 'geoms', [shape]) for c in g.exterior.coords]
    breaks = sorted({round(to_u(c[1] if axis == 'y' else c[0]), 4) for c in coords})
    bands = []
    for u0, u1 in zip(breaks, breaks[1:]):
        if u1-u0 < .05:
            continue
        um = (u0+u1)/2
        w = top-um if sign < 0 else top+um
        line = (LineString([(x0-1, w), (x1+1, w)]) if axis == 'y' else LineString([(w, y0-1), (w, y1+1)]))
        cut = shape.intersection(line)
        segs = [g for g in getattr(cut, 'geoms', [cut]) if g.geom_type == 'LineString' and g.length > .05]
        ivs = sorted((min(c[0 if axis == 'y' else 1] for c in s.coords), max(c[0 if axis == 'y' else 1] for c in s.coords))
                     for s in segs)
        bands.append((u0, u1, ivs))
    return bands, length


def profile(shape, axis, sign):
    """Perfil do T/L numa orientação: bw, h, braços por lado (desnível, espessura).

    A alma é o intervalo transversal que ocupa o maior comprimento ao longo da
    altura (faixas de quebra inclinada são curtas e não a estreitam).
    ``broken`` marca alma interrompida (símbolo de quebra): h não é medível.
    """
    bands, length = _slices(shape, axis, sign)
    if not bands:
        return None
    weight = defaultdict(float)
    for u0, u1, ivs in bands:
        for a, b in ivs:
            weight[(round(a, 1), round(b, 1))] += u1-u0
    if not weight:
        return None
    stem = max(weight, key=lambda iv: (weight[iv], -(iv[1]-iv[0])))
    if stem[1]-stem[0] < 5:
        return None
    covered = [u1-u0 for u0, u1, ivs in bands if any(a <= stem[0]+.05 and b >= stem[1]-.05 for a, b in ivs)]
    broken = sum(covered) < length-.1
    arms = {'-': [], '+': []}
    for u0, u1, ivs in bands:
        for a, b in ivs:
            if not (a <= stem[0]+.05 and b >= stem[1]-.05):
                continue
            for side, reach in (('-', stem[0]-a), ('+', b-stem[1])):
                if reach <= ARM_MIN_CM:
                    continue
                run = arms[side]
                if run and abs(run[-1][1]-u0) <= .05:
                    run[-1] = (run[-1][0], u1, max(run[-1][2], reach))
                else:
                    run.append((u0, u1, reach))
    return dict(bw=round(stem[1]-stem[0], 2), h=round(length, 2), broken=broken,
                arms={s: [dict(drop=round(u0, 2), thick=round(u1-u0, 2)) for u0, u1, _ in r] for s, r in arms.items()})


def orientations(shape):
    result = []
    for axis in ('x', 'y'):
        for sign in (1, -1):
            p = profile(shape, axis, sign)
            if p:
                result.append(dict(p, axis=axis, sign=sign))
    return result


# --------------------------------------------------------------------------
# Corte original x leitura do SA (ficha)
# --------------------------------------------------------------------------

def _declared_original(source_cut):
    """O que o SA leu do corte: bw, h e lajes por lado {A,B}: (nome, espessura, desnível)."""
    f = source_cut.get('ficha') or {}
    bw = _num(source_cut.get('beam_w')) or _num(f.get('beam_bottom_dim'))
    h = _num(source_cut.get('beam_h')) or _num(f.get('beam_height'))
    direction = str(f.get('direction') or '').strip().casefold()
    own_side = {'norte': 'A', 'leste': 'A', 'east': 'A', 'north': 'A',
                'sul': 'B', 'oeste': 'B', 'south': 'B', 'west': 'B'}.get(direction)
    own = source_cut.get('own_laje')
    if not own_side:
        own_side = 'A' if own == f.get('side_a_laje_name') else 'B' if own == f.get('side_b_laje_name') else None
    slabs = {'A': [], 'B': []}
    if own_side:
        other = 'B' if own_side == 'A' else 'A'
        for prefix, thick_key, side in (('own', 'own_slab_height', own_side), ('neighbor', 'neigh_slab_height', other)):
            name = f.get(f'side_{side.lower()}_laje_name')
            if str(f.get(f'beam_lajes_side_{side.lower()}')) == '0' or not name or str(name).casefold() in ('nulo', 'null', 'none'):
                continue
            slabs[side].append(dict(name=name, thick=_num(f.get(thick_key)), drop=_num(f.get(f'{prefix}_dist_top'))))
    return dict(bw=bw, h=h, slabs=slabs, own_side=own_side)


def _arm_errors(measured, declared, plan_h=lambda name: None):
    """Compara braços medidos {-,+} com lajes declaradas {A,B}; devolve (erros, atribuição, notas).

    Espessura: o símbolo de corte costuma ser esquemático; se o valor declarado
    é o h= escrito na planta, a diferença é nota (vale a planta), não erro.
    """
    best = None
    for mapping in (({'-': 'A', '+': 'B'}), ({'-': 'B', '+': 'A'})):
        errs, notes = [], []
        for side_m, side_d in mapping.items():
            got = measured['arms'][side_m]
            want = declared['slabs'][side_d]
            if len(got) != len(want):
                errs.append(f'lado {side_d}: {len(want)} laje(s) declarada(s), {len(got)} braço(s) no desenho'
                            + (f" ({', '.join(f'{_fmt(a['thick'])} cm a {_fmt(a['drop'])} cm do topo' for a in got)})" if got else ''))
                continue
            for a, s in zip(sorted(got, key=lambda a: a['drop']), sorted(want, key=lambda s: s['drop'] or 0)):
                if s['thick'] is None or abs(a['thick']-s['thick']) > TOL_CM:
                    plan = plan_h(s['name'])
                    if s['thick'] is not None and plan is not None and abs(plan-s['thick']) <= TOL_CM:
                        notes.append(f"lado {side_d} {s['name']}: símbolo desenha {_fmt(a['thick'])} cm, planta h={_fmt(plan)} (vale a planta)")
                    else:
                        errs.append(f"lado {side_d} {s['name']}: espessura declarada {_fmt(s['thick']) if s['thick'] is not None else 'ausente'}, desenho {_fmt(a['thick'])} cm"
                                    + (f', planta h={_fmt(plan)}' if plan is not None else ''))
                drop = a['drop']
                if measured['broken'] and s['drop'] is not None and declared['h'] and s['thick'] is not None                         and a['drop'] > measured['h']/2:
                    # Alma quebrada encurta o desenho: braço na metade de baixo
                    # (viga invertida) se mede a partir do fundo da viga.
                    drop = declared['h'] - (measured['h'] - a['drop'] - a['thick']) - s['thick']
                if s['drop'] is None or abs(drop-s['drop']) > TOL_CM:
                    errs.append(f"lado {side_d} {s['name']}: desnível declarado {_fmt(s['drop']) if s['drop'] is not None else 'ausente'}, desenho {_fmt(drop)} cm do topo")
        if best is None or len(errs) < len(best[0]):
            best = (errs, mapping, notes)
    return best


def plan_sections(source, state):
    """{viga: [(caixa do fundo, {(bw, h)})]} escritos em planta na faixa de cada segmento, sem rótulo de outra viga.

    É o vínculo exigido por NIV-ALTURA-NUMERICA-VINCULADA: a altura escrita na viga
    prevalece sobre a medida no corte desenhado. Faixa disputada não vincula nada.
    """
    from pathlib import Path
    source = Path(source)
    walls = gate._cached('walls', source, lambda: list(gate._straight_walls(gate._readfile(source))))
    texts = gate._cached('beam_texts', source, lambda: gate._beam_texts(gate._readfile(source)))
    pillar_sections = gate._cached('proved_pillar_sections', source,
                                   lambda: gate._proved_pillar_section_handles(gate._readfile(source), texts))
    texts = [t for t in texts if t['handle'] not in pillar_sections]
    found = defaultdict(list)
    for row in (state.get('segmentos') or {}).get('fundo', []):
        name = str(row.get('beam_name') or '')
        box = gate._exact_axis_rectangle(row.get('points'))
        if not name or box is None:
            continue
        axis = gate._fv_rectangle_axis(box, walls)
        across = 'y' if axis == 'x' else 'x'
        lo, hi, edges = (box[0], box[1], box[2:4]) if axis == 'x' else (box[2], box[3], box[0:2])
        band = [t for t in texts if t['axis'] == axis and lo - gate.EPS <= t[axis] <= hi + gate.EPS
                and edges[0] - t['margin'] <= t[across] <= edges[1] + t['margin']]
        if {t['text'] for t in band if gate.BEAM_LABEL.fullmatch(t['text'])} - {name}:
            continue
        found[name].append((box, {gate._section(t['text']) for t in band if gate.SECTION_TEXT.fullmatch(t['text'])}))
    return dict(found)


def _plan_at(plan, pts):
    """Seções escritas no segmento de fundo mais próximo do símbolo do corte (V408: 14/55 × 19/55)."""
    if not plan or not pts:
        return None
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    gap = lambda b: math.hypot(max(b[0] - cx, 0, cx - b[1]), max(b[2] - cy, 0, cy - b[3]))
    nearest = min(gap(box) for box, _ in plan)
    return set().union(*(values for box, values in plan if gap(box) <= nearest + gate.EPS))


def measure_original(source, source_cut, beam, unit, written=None, plan=None):
    """Contatos de um corte original: dimensões e braços de laje contra a ficha do SA."""
    pts = source_cut.get('points') or source_cut.get('pts') or []
    base = dict(unit_path=unit, item=beam, guards=['dimensoes', 'niveis'], blocks_promotion=True, errors={})
    if len(pts) < 3:
        return [dict(base, aspect='corte original', status='uncertain', reason='SA sem polígono do corte original')]
    shape, handles = _source_shape(source, pts)
    if shape is None:
        return [dict(base, aspect='corte original', status='uncertain', reason='peças fechadas do corte não encontradas no DXF')]
    declared = _declared_original(source_cut)
    if not (source_cut.get('ficha') or {}).get('direction') and not declared['own_side']:
        return [dict(base, aspect='corte original', status='uncertain', handles=handles,
                     reason='SA não leu a ficha deste corte (sem direção nem lajes)')]
    where = f'corte original ({_fmt(declared["bw"]) if declared["bw"] else "?"}/{_fmt(declared["h"]) if declared["h"] else "?"})'
    cands = orientations(shape)
    if not cands:
        return [dict(base, aspect=where, status='uncertain', handles=handles,
                     reason='símbolo sem alma contínua; não é um T/L legível')]
    scored = []
    for c in cands:
        errs = []
        if declared['bw'] is None or abs(c['bw']-declared['bw']) > TOL_CM:
            errs.append(f"bw declarado {_fmt(declared['bw']) if declared['bw'] else 'ausente'}, desenho {_fmt(c['bw'])} cm")
        if not c['broken'] and (declared['h'] is None or abs(c['h']-declared['h']) > TOL_CM):
            errs.append(f"h declarado {_fmt(declared['h']) if declared['h'] else 'ausente'}, desenho {_fmt(c['h'])} cm")
        plan_h = lambda name: ((written or {}).get((str(name), 'principal')) or {}).get('h')
        arm_errs, mapping, notes = _arm_errors(c, declared, plan_h) if declared['own_side'] else (
            ['orientação da laje ausente na ficha (direção)'], None, [])
        bw_off = abs(c['bw']-declared['bw']) if declared['bw'] else 99
        scored.append((len(errs)+len(arm_errs), bw_off, errs+arm_errs, c, mapping, notes))
    scored.sort(key=lambda s: (s[0], s[1]))
    _, _, errs, c, mapping, notes = scored[0]
    linked = None
    if declared['bw'] is not None and declared['h'] is not None and _plan_at(plan, pts) == {(declared['bw'], declared['h'])}:
        linked = [e for e in errs if e.startswith('h declarado ')]
        errs = [e for e in errs if not e.startswith('h declarado ')]
    contacts = [dict(base, aspect=where, status='measured', handles=handles,
                     measured=dict(bw=c['bw'], h=None if c['broken'] else c['h'], arms=c['arms'],
                                   lados={k: v for k, v in (mapping or {}).items()}),
                     errors={'dimensoes': '; '.join(errs)} if errs else {})]
    if linked:
        # NIV-ALTURA-NUMERICA-VINCULADA: o número vinculado vence; a discrepância fica como evidência.
        contacts[0]['basis'] = (f"{_fmt(declared['bw'])}/{_fmt(declared['h'])} escrito na faixa da viga prevalece "
                                f"sobre o desenho do corte ({'; '.join(linked)})")
    if notes:
        contacts.append(dict(base, aspect=where + ' espessura', status='uncertain', blocks_promotion=False,
                             handles=handles, reason='; '.join(notes)))
    if c['broken']:
        contacts.append(dict(base, aspect=where + ' altura', status='uncertain', blocks_promotion=False,
                             handles=handles, reason='alma interrompida (símbolo de quebra): h não medível no desenho'))
    return contacts


# --------------------------------------------------------------------------
# Corte interpretado x cotas e h= das lajes (planta)
# --------------------------------------------------------------------------

def slab_values(source, slabs):
    """{(laje, região): {'nivel': cota, 'h': espessura}} escritos dentro do contorno (E1)."""
    report = gate.measure_slabs(source, {'collections': {'lajes': slabs}})
    values = defaultdict(dict)
    for c in report.get('contacts', []):
        if c.get('status') != 'measured' or len(c.get('values') or []) != 1:
            continue
        aspect = c.get('aspect') or ''
        region = 'principal'
        if '(' in aspect:
            region = aspect[aspect.index('(')+1:aspect.rindex(')')].replace('degrau ', '')
        key = (str(c.get('item')), region)
        if aspect.startswith('nível'):
            values[key]['nivel'] = c['values'][0]
        elif aspect.startswith('espessura'):
            values[key]['h'] = c['values'][0]
    return values


def _region(slab):
    rid = str(slab.get('region_id') or 'principal')
    return 'principal' if rid == 'principal' else rid.rsplit(':', 1)[-1]


def measure_calculated(entry, written, unit, label):
    """Desnível e espessura de cada laje do corte calculado contra a planta."""
    contract = entry.get('section_contract') or {}
    beam = entry['beam']
    top = _num(contract.get('top_level_m'))
    base = dict(unit_path=unit, item=beam, guards=['niveis', 'dimensoes'], errors={})
    # Corte agrupado (D-87): vários pares A/B com a mesma seção; a região de
    # cada laje vem do par em que ela aparece, não só do primeiro.
    pairs = entry.get('pairs') or []
    contacts = []
    seen = []
    for side in ('A', 'B'):
        declared = contract.get('slabs', {}).get(side) or []
        regions = defaultdict(list)
        for p in pairs:
            for s in ((p.get('profiles') or {}).get(side) or {}).get('slabs') or []:
                if _region(s) not in regions[str(s.get('name'))]:
                    regions[str(s.get('name'))].append(_region(s))
        for slab in declared:
            names = [n.strip() for n in str(slab.get('name') or '').split(',') if n.strip()]
            for name in names:
                cands = regions.get(name) or ['principal']
                region = next((r for r in cands if (written.get((name, r)) or {}).get('h') is not None
                               and abs(written[(name, r)]['h']-_num(slab['height_cm'])) <= TOL_CM), cands[0])
                got = written.get((name, region)) or {}
                where = f'{label} lado {side} {name}' + (f' (degrau {region})' if region != 'principal' else '')
                errs = []
                if got.get('h') is not None and abs(got['h']-_num(slab['height_cm'])) > TOL_CM:
                    errs.append(f"espessura do corte {_fmt(_num(slab['height_cm']))} cm, planta h={_fmt(got['h'])}")
                if got.get('nivel') is not None and top is not None:
                    expected = round((top-got['nivel'])*100, 2)
                    if abs(expected-_num(slab['drop_cm'])) > LEVEL_TOL_CM:
                        errs.append(f"desnível do corte {_fmt(_num(slab['drop_cm']))} cm; planta: cota {_lvl(got['nivel'])} "
                                    f"fica {_fmt(expected)} cm abaixo do topo {_lvl(top)}")
                if got.get('nivel') is not None:
                    seen.append((side, name, got['nivel'], _num(slab['drop_cm'])))
                if not got:
                    contacts.append(dict(base, aspect=where, status='uncertain', blocks_promotion=False,
                                         reason='laje sem cota/h= escritos dentro do contorno'))
                    continue
                contacts.append(dict(base, aspect=where, status='measured',
                                     errors={'niveis': '; '.join(errs)} if errs else {}))
    # Corte relativo (sem topo absoluto): o desnível ENTRE os lados ainda se confere.
    if top is None and len({s for s, *_ in seen}) == 2:
        a = next(x for x in seen if x[0] == 'A')
        b = next(x for x in seen if x[0] == 'B')
        expected = round((a[2]-b[2])*100, 2)
        if a[3] is not None and b[3] is not None:
            got = round(b[3]-a[3], 2)
            contacts.append(dict(base, aspect=f'{label} degrau entre lados', status='measured',
                                 errors={} if abs(expected-got) <= LEVEL_TOL_CM else
                                 {'niveis': f'corte põe {b[1]} {_fmt(got)} cm abaixo de {a[1]}; planta: '
                                            f'{_lvl(a[2])} e {_lvl(b[2])} ({_fmt(expected)} cm)'}))
    return contacts


# --------------------------------------------------------------------------
# Degrau de laje
# --------------------------------------------------------------------------

def measure_slab_step(source, slab, step, section, unit, written=None):
    """Corte original do degrau: duas espessuras e os dois desníveis (topo e fundo)."""
    label = f"degrau {str(step.get('uid', '')).rsplit(':', 1)[-1]}"
    base = dict(unit_path=unit, item=str(slab.get('name')), guards=['degraus', 'niveis', 'dimensoes'], errors={})
    pts = section.get('points') or []
    shape, handles = _source_shape(source, pts) if len(pts) >= 3 else (None, [])
    if shape is None:
        return dict(base, aspect=f'{label} corte original', status='uncertain', blocks_promotion=True,
                    reason='peças do corte do degrau não encontradas no DXF')
    from shapely.geometry import LineString
    x0, y0, x1, y1 = shape.bounds
    vertical = y1-y0 > x1-x0
    lo, hi = (y0, y1) if vertical else (x0, x1)
    widths = {}
    for k in range(1, 40):
        w = lo+(hi-lo)*k/40
        line = LineString([(x0-1, w), (x1+1, w)] if vertical else [(w, y0-1), (w, y1+1)])
        cut = shape.intersection(line)
        if cut.geom_type != 'LineString' or cut.length <= .05:
            continue
        cs = [c[0] if vertical else c[1] for c in cut.coords]
        widths.setdefault(round(cut.length, 1), (min(cs), max(cs)))
    if len(widths) != 2:
        return dict(base, aspect=f'{label} corte original', status='uncertain', blocks_promotion=True, handles=handles,
                    reason=f'corte do degrau com {len(widths)} espessura(s) no desenho; esperado 2')
    (t1, (a1, b1)), (t2, (a2, b2)) = sorted(widths.items())
    offsets = sorted([round(abs(a1-a2), 2), round(abs(b1-b2), 2)])
    want_t = sorted([_num(step.get('height_cm')), _num(step.get('owner_height_cm'))])
    level_d = abs(round(((_num(step.get('owner_level_m')) or 0)-(_num(step.get('level_m')) or 0))*100, 2))
    bottom_d = abs(round(((_num(step.get('owner_bottom_m')) or 0)-(_num(step.get('bottom_m')) or 0))*100, 2))
    errs, notes = [], []
    if None in want_t or abs(t1-want_t[0]) > TOL_CM or abs(t2-want_t[1]) > TOL_CM:
        name = str(slab.get('name'))
        uid = str(step.get('uid', '')).rsplit(':', 1)[-1]
        plan = sorted(v.get('h') for v in ((written or {}).get((name, 'principal')) or {},
                                           (written or {}).get((name, uid)) or {}) if v.get('h') is not None)
        msg = f'espessuras declaradas {"/".join(_fmt(t) if t is not None else "?" for t in want_t)} cm, desenho {_fmt(t1)}/{_fmt(t2)}'
        principal = ((written or {}).get((name, 'principal')) or {}).get('h')
        if None not in want_t and len(plan) == 2 and all(abs(a-b) <= TOL_CM for a, b in zip(plan, want_t)):
            notes.append(msg + f', planta h={"/".join(_fmt(v) for v in plan)} (vale a planta)')
        elif (None not in want_t and step.get('method') == 'flat_bottom_section_written_step'
              and principal is not None and abs(principal-_num(step.get('owner_height_cm'))) <= TOL_CM
              and abs((t2-t1)-(want_t[1]-want_t[0])) <= TOL_CM):
            # Região sem h= próprio (L406/96B): símbolo genérico; vale o h= da
            # planta no principal e o degrau desenhado = degrau escrito.
            notes.append(msg + f', planta h={_fmt(principal)} e degrau desenhado {_fmt(t2-t1)} cm '
                         '= escrito (vale o número)')
        else:
            errs.append(msg + (f', planta h={"/".join(_fmt(v) for v in plan)}' if plan else ''))
    if any(abs(g-w) > TOL_CM for g, w in zip(offsets, sorted([level_d, bottom_d]))):
        errs.append(f'desníveis declarados topo {_fmt(level_d)} / fundo {_fmt(bottom_d)} cm, desenho {_fmt(offsets[0])}/{_fmt(offsets[1])}')
    return dict(base, aspect=f'{label} corte original', status='measured', blocks_promotion=True, handles=handles,
                measured=dict(espessuras=[t1, t2], desniveis=offsets),
                errors={'degraus': '; '.join(errs)} if errs else {}, notes=notes)


# --------------------------------------------------------------------------
# Pavimento
# --------------------------------------------------------------------------

def measure_pavimento(source, state, inventory, slabs, item_names=None):
    """{item: report} da Visão Corte: vigas (cortes) e lajes (degraus)."""
    reports = defaultdict(lambda: dict(schema='cad.qa_original_cortes/v1', contacts=[], guards=VC_GUARDS, inputs=[]))
    wanted = (lambda n: n in item_names) if item_names else (lambda n: True)
    labels = {s['uid']: str(s.get('segment_label') or '') for s in (state.get('segmentos') or {}).get('fundo', [])}

    written = slab_values(source, slabs)
    try:
        plan = plan_sections(source, state)
    except (OSError, ValueError, KeyError):
        plan = {}
    # 1. Cortes originais que o SA leu (um por polígono, mesmo repetido em Para/Passa).
    # Dono do corte = a mesma associação geométrica que a ficha LV consome
    # (lv_ficha._cut_views), não o rótulo bruto do SA (14_PAV: L419_3154_2078 é da V408).
    from . import corte_references
    references = corte_references.preparar_segmentos(state)
    done = set()
    for row in inventory.get('relative_originals') or []:
        sc = row.get('source_cut') or {}
        key = str(row.get('id') or sc.get('uid'))
        beam = str(corte_references.associar_referencias(sc, references).get('nome_sugerido')
                   or row.get('beam') or '')
        if key in done or not beam or not wanted(beam):
            continue
        done.add(key)
        reports[beam]['inputs'].append(sc)
        reports[beam]['contacts'] += measure_original(source, sc, beam, f'/cortes/original/{key}', written,
                                                      plan.get(beam))

    # 2. Cortes interpretados (calculados) contra cotas/h= das lajes.
    for index, entry in enumerate(inventory.get('entries') or []):
        if entry.get('kind') == 'identified' or not wanted(entry['beam']):
            continue
        seg = labels.get(entry.get('fundo_id'), '?')
        reports[entry['beam']]['inputs'].append(entry.get('section_contract'))
        reports[entry['beam']]['contacts'] += measure_calculated(
            entry, written, f'/cortes/interpretado/{index}', f'corte seg {seg}')

    # 3. Segmento de fundo sem nenhum corte e cortes que o SA não fechou.
    for row in inventory.get('soffit_coverage') or []:
        beam = str(row.get('beam') or '')
        if row.get('status') == 'pending' and beam and wanted(beam):
            reports[beam]['inputs'].append(row)
            reports[beam]['contacts'].append(dict(
                unit_path=f"/cortes/cobertura/{row['fundo_id']}", item=beam, aspect=f"seg {row.get('segment')}",
                guards=['inventario_segmentos'], status='uncertain', blocks_promotion=True, errors={},
                reason='segmento sem corte (' + (row.get('reason') or 'sem par A/B') + ')'))
    for row in inventory.get('blocked') or []:
        beam = str(row.get('beam') or '')
        if beam and wanted(beam):
            reports[beam]['inputs'].append(row)
            reports[beam]['contacts'].append(dict(
                unit_path=f"/cortes/bloqueado/{beam}/{row.get('behavior')}/{row.get('cut_index')}", item=beam,
                aspect=f"corte {row.get('behavior')} {row.get('cut_index')}", guards=['dimensoes'],
                status='uncertain', blocks_promotion=True, errors={},
                reason=f"SA não montou o corte: {row.get('reason')}"))

    # 4. Degraus de laje: corte original medido; sem corte original fica incerto.
    for slab in state.get('slabs') or []:
        name = str(slab.get('name') or '')
        if not wanted(name):
            continue
        for step in slab.get('slab_steps') or []:
            sections = step.get('sections') or []
            unit = f"/cortes/degrau/{step.get('uid')}"
            reports[name]['inputs'].append(step)
            if not sections:
                reports[name]['contacts'].append(dict(
                    unit_path=unit, item=name, aspect=f"degrau {str(step.get('uid', '')).rsplit(':', 1)[-1]}",
                    guards=['degraus'], status='uncertain', blocks_promotion=False, errors={},
                    reason='degrau sem corte original no DXF (corte interpretado pelo SA)'))
            for section in sections:
                reports[name]['contacts'].append(measure_slab_step(source, slab, step, section, unit, written))
    return dict(reports)


def inputs_fingerprint(report):
    """Impressão digital do que o SA declarou para o item (selo "desatualizado")."""
    import hashlib
    import json
    return hashlib.sha256(json.dumps(report.get('inputs') or [], ensure_ascii=False, sort_keys=True,
                                     default=str).encode()).hexdigest()


def measure_obra(obra_dir, pav, source, state, slabs, item_names=None):
    """Inventário de cortes do SA (``structural_cut_overlay``) medido no DXF original."""
    from . import structural_cut_overlay
    inventory = structural_cut_overlay.collect_sections(obra_dir, pav, state)
    return measure_pavimento(source, state, inventory, slabs, item_names=item_names)
