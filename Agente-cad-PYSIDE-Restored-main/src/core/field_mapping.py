"""
src/core/field_mapping.py — CAD-10.1
Mapeamento canônico entre campos Fase-4 JSON e field IDs do DetailCard.

Uso:
    from src.core.field_mapping import map_pilar, map_viga_lateral, map_viga_fundo, map_laje, FASE4_TO_DETAIL

Retorno de cada map_*():
    {
        'flat':       {field_id: value}        — campos rasos (item_data[field_id])
        'sides_data': {face: {key: value}}     — para pilares (sides_data[face][key])
        'links':      {field_id: slots_dict}   — para lajes/vigas (links[field_id])
        'meta':       {field_id: confidence}   — confidence por campo
    }
"""
from __future__ import annotations
from typing import Any


# ─── Constantes de faces ──────────────────────────────────────────────────────

FACES_PILAR = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
SIDES_VIGA  = ['a', 'b', 'fundo']

# Confidence por fonte
CONF_FASE4    = 0.75   # motor_fase4.py (geométrico)
CONF_GT       = 0.90   # engenharia_reversa_dxf (ground truth)
CONF_VALIDATED = 1.00  # manual validado pelo usuário


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _link_slot(value: Any, slot: str = 'slot_1') -> dict:
    """Empacota valor no formato de links do DetailCard."""
    return {slot: [{'text': str(value), 'type': 'text', 'source': 'fase4_import'}]}


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _dim_str(comp: Any, larg: Any) -> str:
    c, l = _safe_float(comp), _safe_float(larg)
    ci = int(c) if c == int(c) else c
    li = int(l) if l == int(l) else l
    return f"{ci}x{li}"


# ─── PILAR ────────────────────────────────────────────────────────────────────

def map_pilar(pilar_json: dict) -> dict:
    """
    Mapeia JSON_Pilares/P{n}.json → estrutura para DB.

    Campos Fase-4 mapeados:
    ┌─ IDENTIFICAÇÃO ─────────────────────────────────────────────────────────┐
    │  nome/numero             → flat 'name', 'id_item'                       │
    │  comprimento × largura   → flat 'dim'  (ex: "88x19")                   │
    ├─ DIMENSIONAL GLOBAL ────────────────────────────────────────────────────┤
    │  altura                  → flat 'altura'                                │
    │  nivel_chegada/saida     → flat 'nivel_chegada', 'nivel_saida'          │
    │  pavimento               → flat 'pavimento'                             │
    │  modo_distribuicao       → flat 'modo_distribuicao'                     │
    ├─ ASSEMBLY (GRADES/PARAFUSOS) ───────────────────────────────────────────┤
    │  grade_1/2/3             → flat 'grade_1', 'grade_2', 'grade_3'        │
    │  distancia_1/2           → flat 'distancia_1', 'distancia_2'           │
    │  par_1_2 .. par_8_9      → flat 'par_1_2' .. 'par_8_9'                 │
    ├─ POR FACE (A–H) ────────────────────────────────────────────────────────┤
    │  h1..h5_{face}  (chapa)  → flat 'p_s{face}_c_h1' .. 'p_s{face}_c_h5'  │
    │  larg1..3_{face}(chapa)  → flat 'p_s{face}_c_larg1'..'p_s{face}_c_larg3'│
    │  laje_{face}    (laje adj)→ sides_data[face]['l1_h'] = p_s{face}_l1_h  │
    │  posicao_laje_{face}     → sides_data[face]['l1_p'] = p_s{face}_l1_p   │
    └─────────────────────────────────────────────────────────────────────────┘

    NOTA: h1..h5 são alturas das CHAPAS DA FORMA (seções de concreto por face),
    diferentes de l1_h que é a altura da LAJE ADJACENTE à face.
    """
    flat: dict       = {}
    sides: dict      = {}
    meta: dict       = {}
    conf = CONF_FASE4

    # ── Identificação ──
    nome = pilar_json.get('nome') or pilar_json.get('name', '')
    flat['name']    = nome
    flat['id_item'] = nome
    flat['dim']     = _dim_str(pilar_json.get('comprimento'), pilar_json.get('largura'))

    # ── Dimensional global ──
    flat['altura']          = _safe_float(pilar_json.get('altura'))
    flat['pavimento']       = pilar_json.get('pavimento', '')
    flat['nivel_chegada']   = _safe_float(pilar_json.get('nivel_chegada'))
    flat['nivel_saida']     = _safe_float(pilar_json.get('nivel_saida'))
    flat['modo_distribuicao'] = pilar_json.get('modo_distribuicao', 'NOVA')
    meta.update({'dim': conf, 'altura': conf, 'nivel_chegada': conf,
                 'nivel_saida': conf, 'modo_distribuicao': conf})

    # ── Assembly global (grades, distâncias, parafusos) ──
    for key in ('grade_1', 'grade_2', 'grade_3',
                'distancia_1', 'distancia_2',
                'par_1_2', 'par_2_3', 'par_3_4', 'par_4_5',
                'par_5_6', 'par_6_7', 'par_7_8', 'par_8_9'):
        v = pilar_json.get(key)
        if v is not None:
            flat[key] = _safe_float(v)
            meta[key] = conf

    # ── Por face (A–H) ──
    for face in FACES_PILAR:
        sd: dict = {}

        # Alturas das chapas de forma (h1=superior, h2=principal, h3=inferior, h4/h5=extras)
        # → DetailCard: p_s{face}_c_h1 .. p_s{face}_c_h5  (c = chapa)
        for hi in range(1, 6):
            v = pilar_json.get(f'h{hi}_{face}')
            if v is not None:
                fid = f'p_s{face}_c_h{hi}'
                flat[fid] = _safe_float(v)
                meta[fid] = conf

        # Larguras das chapas de forma
        # → DetailCard: p_s{face}_c_larg1 .. p_s{face}_c_larg3
        for li in range(1, 4):
            v = pilar_json.get(f'larg{li}_{face}')
            if v is not None:
                fid = f'p_s{face}_c_larg{li}'
                flat[fid] = _safe_float(v)
                meta[fid] = conf

        # Laje adjacente à face → sides_data usado pelo DetailCard para p_s{face}_l1_h
        laje_h = _safe_float(pilar_json.get(f'laje_{face}'))
        laje_p = _safe_float(pilar_json.get(f'posicao_laje_{face}'))
        if laje_h:
            sd['l1_h'] = laje_h
            meta[f'p_s{face}_l1_h'] = conf
        if laje_p:
            sd['l1_p'] = laje_p
            meta[f'p_s{face}_l1_p'] = conf

        if sd:
            sides[face] = sd

    return {'flat': flat, 'sides_data': sides, 'links': {}, 'meta': meta}


# ─── VIGA LATERAL (LV — lados A e B) ─────────────────────────────────────────

def map_viga_lateral(viga_json: dict, side: str = 'A') -> dict:
    """
    Mapeia JSON_Vigas_Laterais/V{n}_{A|B}.json → estrutura para DB.

    Campos mapeados:
        total_width, total_height → flat 'dim', 'total_width', 'total_height'
        panels[i]                 → viga_{a|b}_seg_{i+1}_h1/h2/dim/comprimento_total
        holes[i] (active=True)    → viga_{a|b}_seg_{i+1}_abert_*
        pillar_left/right         → flat keys
    """
    flat: dict  = {}
    meta: dict  = {}
    conf = CONF_FASE4

    side_l = side.lower()  # 'a' ou 'b'
    prefix = f'viga_{side_l}'

    nome = viga_json.get('name', '')
    flat['name']    = nome
    flat['id_item'] = nome
    flat['dim']     = _dim_str(
        viga_json.get('total_width'),
        _safe_float(str(viga_json.get('total_height', 0)))
    )
    flat['total_width']  = _safe_float(viga_json.get('total_width'))
    flat['total_height'] = _safe_float(str(viga_json.get('total_height', 0)))
    flat['floor']        = viga_json.get('floor', '')
    flat['side']         = viga_json.get('side', side)

    # ── Painéis como segmentos ──
    panels = viga_json.get('panels') or []
    for i, panel in enumerate(panels, start=1):
        seg = f'{prefix}_seg_{i}'
        w  = _safe_float(panel.get('width'))
        h1 = _safe_float(panel.get('height1'))
        h2 = _safe_float(panel.get('height2'))

        if w > 0:
            flat[f'{seg}_comprimento_total'] = w
            meta[f'{seg}_comprimento_total'] = conf
        flat[f'{seg}_h1']  = h1
        flat[f'{seg}_h2']  = h2
        flat[f'{seg}_dim'] = _dim_str(viga_json.get('total_width'), h1 or h2)
        flat[f'{seg}_exists'] = True

        # Grade horizontal
        gh1 = panel.get('grade_h1', '0')
        gh2 = panel.get('grade_h2', '0')
        if gh1 and str(gh1) != '0':
            flat[f'{seg}_mode_h1_grade'] = gh1
        if gh2 and str(gh2) != '0':
            flat[f'{seg}_mode_h2_grade'] = gh2

        meta[f'{seg}_h1'] = conf
        meta[f'{seg}_h2'] = conf

    # ── Aberturas ──
    holes = viga_json.get('holes') or []
    for i, hole in enumerate(holes):
        if hole.get('active'):
            seg = f'{prefix}_seg_{i + 1}'
            flat[f'{seg}_has_hole']       = True
            flat[f'{seg}_hole_width']     = _safe_float(hole.get('width'))
            flat[f'{seg}_hole_height']    = _safe_float(hole.get('height'))
            flat[f'{seg}_hole_position']  = _safe_float(hole.get('position'))

    # ── Pilares de extremidade ──
    pl = viga_json.get('pillar_left', {})
    pr = viga_json.get('pillar_right', {})
    if pl.get('active'):
        flat[f'{prefix}_pilar_esq_width']  = _safe_float(pl.get('width'))
        flat[f'{prefix}_pilar_esq_length'] = _safe_float(pl.get('length'))
    if pr.get('active'):
        flat[f'{prefix}_pilar_dir_width']  = _safe_float(pr.get('width'))
        flat[f'{prefix}_pilar_dir_length'] = _safe_float(pr.get('length'))

    meta['dim'] = conf

    return {'flat': flat, 'sides_data': {}, 'links': {}, 'meta': meta}


# ─── VIGA FUNDO (FV) ──────────────────────────────────────────────────────────

def map_viga_fundo(viga_json: dict) -> dict:
    """
    Mapeia JSON_Vigas_Fundo/V{n}_fundo.json → estrutura para DB.

    Campos mapeados:
        total_width               → viga_fundo_seg_1_largura
        sum(panels[i].width)      → viga_fundo_seg_1_comprimento
        panels[i]                 → viga_fundo_seg_{i+1}_*
    """
    flat: dict  = {}
    meta: dict  = {}
    conf = CONF_FASE4
    prefix = 'viga_fundo'

    nome = viga_json.get('name', '')
    flat['name']    = nome
    flat['id_item'] = nome
    flat['floor']   = viga_json.get('floor', '')

    panels = viga_json.get('panels') or []
    total_comp = sum(_safe_float(p.get('width')) for p in panels)

    flat[f'{prefix}_seg_1_largura']     = _safe_float(viga_json.get('total_width'))
    flat[f'{prefix}_seg_1_comprimento'] = total_comp
    flat[f'{prefix}_seg_1_exists']      = True
    meta[f'{prefix}_seg_1_largura']     = conf
    meta[f'{prefix}_seg_1_comprimento'] = conf

    for i, panel in enumerate(panels, start=1):
        seg = f'{prefix}_seg_{i}'
        w  = _safe_float(panel.get('width'))
        h1 = _safe_float(panel.get('height1'))
        h2 = _safe_float(panel.get('height2'))
        flat[f'{seg}_painel_w']  = w
        flat[f'{seg}_painel_h1'] = h1
        flat[f'{seg}_painel_h2'] = h2

    flat['total_width']  = _safe_float(viga_json.get('total_width'))
    flat['total_height'] = _safe_float(str(viga_json.get('total_height', 0)))
    flat['dim']          = _dim_str(viga_json.get('total_width'),
                                    str(viga_json.get('total_height', 0)))
    meta['dim'] = conf

    return {'flat': flat, 'sides_data': {}, 'links': {}, 'meta': meta}


# ─── LAJE (LJ) ────────────────────────────────────────────────────────────────

def map_laje(laje_json: dict) -> dict:
    """
    Mapeia JSON_Lajes/L{n}.json → estrutura para DB.

    Campos mapeados:
        comprimento, largura       → links['laje_dim']
        area_cm2                   → flat 'area'
        coordenadas                → flat 'points' (para âncoras)
        linhas_verticais           → flat 'laje_linhas_v' (lista de valores)
        linhas_horizontais         → flat 'laje_linhas_h'
        pontaletes                 → flat 'pontaletes' (dict)
    """
    flat: dict  = {}
    links: dict = {}
    meta: dict  = {}
    conf = CONF_FASE4

    nome = laje_json.get('nome', '')
    flat['name']    = nome
    flat['id_item'] = nome
    flat['type']    = 'Laje'

    comp = _safe_float(laje_json.get('comprimento'))
    larg = _safe_float(laje_json.get('largura'))
    area = _safe_float(laje_json.get('area_cm2')) / 10000  # → m²
    flat['area'] = area

    # laje_dim via links (para que _get_initial_value o leia)
    dim_str = _dim_str(comp, larg)
    links['laje_dim'] = _link_slot(dim_str)
    meta['laje_dim'] = conf

    # Pavimento / nível
    if laje_json.get('pavimento'):
        links['laje_nivel'] = _link_slot(laje_json['pavimento'])
        meta['laje_nivel'] = conf

    # Linhas de pontaletes: blob + contagem visível
    lvs = laje_json.get('linhas_verticais') or []
    lhs = laje_json.get('linhas_horizontais') or []
    flat['laje_linhas_v_count'] = str(len(lvs))
    flat['laje_linhas_h_count'] = str(len(lhs))
    meta['laje_linhas_v_count'] = conf
    meta['laje_linhas_h_count'] = conf
    if lvs:
        flat['laje_linhas_v'] = [v['value'] for v in lvs if isinstance(v, dict)]
    if lhs:
        flat['laje_linhas_h'] = [v['value'] for v in lhs if isinstance(v, dict)]

    # Modo de cálculo, flags e observações
    flat['modo_selecionado']  = str(laje_json.get('modo_selecionado', '0'))
    flat['unioes_nos_bordes'] = 'sim' if laje_json.get('unioes_nos_bordes') else 'nao'
    flat['observacoes']       = laje_json.get('observacoes', '')
    meta['modo_selecionado'] = conf

    # Pontaletes — campos individuais visíveis na Ficha
    pont = laje_json.get('pontaletes') or {}
    if pont:
        flat['pontaletes']      = pont   # blob completo (compatibilidade)
        flat['pont_total']      = str(pont.get('total', 0))
        flat['pont_meio']       = str(pont.get('meio_pontalete', 0))
        flat['pont_linhas']     = str(pont.get('linhas', 0))
        flat['pont_colunas']    = str(pont.get('colunas', 0))
        flat['pont_tipo']       = pont.get('tipo', 'PONTALETE')
        flat['pont_altura_pav'] = str(pont.get('altura_pav_cm', 0))
        flat['pont_comp_cm']    = str(pont.get('comprimento_cm', comp))
        flat['pont_larg_cm']    = str(pont.get('largura_cm', larg))
        for k in ('pont_total', 'pont_meio', 'pont_linhas', 'pont_colunas',
                  'pont_tipo', 'pont_altura_pav', 'pont_comp_cm', 'pont_larg_cm'):
            meta[k] = conf

    # Coordenadas como pontos de âncora
    coords = laje_json.get('coordenadas') or []
    if coords:
        flat['points'] = [[c[0], c[1]] for c in coords if len(c) >= 2]

    # Obstáculos como ilhas
    obs = laje_json.get('obstaculos') or []
    if obs:
        flat['laje_obstaculos'] = obs

    return {'flat': flat, 'sides_data': {}, 'links': links, 'meta': meta}


# ─── MAPEAMENTO INVERSO ───────────────────────────────────────────────────────

# ─── Mapeamento inverso: field_id do DetailCard → (json_key_fase4, transformação)
# Transformações suportadas: 'float', 'str'
_INVERSE_PILAR: dict[str, tuple] = {
    # ── Identificação ──
    'dim':              ('comprimento_largura', 'str'),   # composto — só leitura
    # ── Dimensional global ──
    'altura':           ('altura',           'float'),
    'nivel_chegada':    ('nivel_chegada',     'float'),
    'nivel_saida':      ('nivel_saida',       'float'),
    'pavimento':        ('pavimento',         'str'),
    'modo_distribuicao':('modo_distribuicao', 'str'),
    # ── Assembly ──
    'grade_1':          ('grade_1',           'float'),
    'grade_2':          ('grade_2',           'float'),
    'grade_3':          ('grade_3',           'float'),
    'distancia_1':      ('distancia_1',       'float'),
    'distancia_2':      ('distancia_2',       'float'),
    'par_1_2':          ('par_1_2',           'float'),
    'par_2_3':          ('par_2_3',           'float'),
    'par_3_4':          ('par_3_4',           'float'),
    'par_4_5':          ('par_4_5',           'float'),
    'par_5_6':          ('par_5_6',           'float'),
    'par_6_7':          ('par_6_7',           'float'),
    'par_7_8':          ('par_7_8',           'float'),
    'par_8_9':          ('par_8_9',           'float'),
}

# ── Per-face: chapas de forma (c_h = chapa altura, c_larg = chapa largura) ──
for _face in FACES_PILAR:
    # Alturas das chapas → h1_{face} .. h5_{face}
    for _hi in range(1, 6):
        _INVERSE_PILAR[f'p_s{_face}_c_h{_hi}'] = (f'h{_hi}_{_face}', 'float')
    # Larguras das chapas → larg1_{face} .. larg3_{face}
    for _li in range(1, 4):
        _INVERSE_PILAR[f'p_s{_face}_c_larg{_li}'] = (f'larg{_li}_{_face}', 'float')
    # Laje adjacente → laje_{face} e posicao_laje_{face}
    _INVERSE_PILAR[f'p_s{_face}_l1_h'] = (f'laje_{_face}',         'float')
    _INVERSE_PILAR[f'p_s{_face}_l1_p'] = (f'posicao_laje_{_face}', 'float')


def map_detail_to_fase4(field_id: str, value: Any) -> tuple | None:
    """
    Mapeamento inverso: field_id do DetailCard → (json_key_fase4, valor_transformado)
    Retorna None se não houver mapeamento.
    """
    if field_id not in _INVERSE_PILAR:
        return None
    json_key, transform = _INVERSE_PILAR[field_id]
    try:
        if transform == 'float':
            return (json_key, _safe_float(value))
        elif transform == 'str':
            return (json_key, str(value))
        elif transform == 'dim_str':
            return (json_key, str(value))
    except Exception:
        pass
    return None


# ─── TABELA SUMÁRIA DE COBERTURA ──────────────────────────────────────────────

def coverage_report(pilar_json: dict, viga_json: dict, laje_json: dict) -> dict:
    """Retorna % de campos Fase-4 que têm mapeamento no DetailCard."""
    p_result = map_pilar(pilar_json)
    v_result = map_viga_lateral(viga_json)
    l_result = map_laje(laje_json)

    def _count(r: dict) -> tuple[int, int]:
        populated = sum(1 for v in r['flat'].values() if v not in (None, '', 0.0, {}, []))
        populated += sum(1 for v in r['links'].values() if v)
        total = len(r['flat']) + len(r['links'])
        return populated, total

    pp, pt = _count(p_result)
    vp, vt = _count(v_result)
    lp, lt = _count(l_result)

    return {
        'pilar':  {'populated': pp, 'total': pt, 'pct': round(100 * pp / pt, 1) if pt else 0},
        'viga':   {'populated': vp, 'total': vt, 'pct': round(100 * vp / vt, 1) if vt else 0},
        'laje':   {'populated': lp, 'total': lt, 'pct': round(100 * lp / lt, 1) if lt else 0},
    }
