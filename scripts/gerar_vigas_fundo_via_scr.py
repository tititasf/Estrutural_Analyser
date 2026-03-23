#!/usr/bin/env python3
"""
gerar_vigas_fundo_via_scr.py
Gera DXF de fundos de viga (FV) usando pipeline SCR:
  JSON Fase-4 → SCR (robot-compatible) → DXF grid (via ezdxf)

O SCR é gerado pela mesma lógica do Robo_fundos_TASF_limpo_copy_22.py,
garantindo geometria idêntica ao robô ALIMONTI.

Uso:
  python scripts/gerar_vigas_fundo_via_scr.py
  python scripts/gerar_vigas_fundo_via_scr.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1 --cols 4
"""
import sys
import argparse
import json
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

_SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS))
from json_to_scr_fv import json_to_dados_fv, gerar_scr_fv
from scr_to_dxf import _copy_entity_with_offset, tokenize

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---------------------------------------------------------------------------
# CONSTANTES (cm)
# ---------------------------------------------------------------------------
MARGIN_X        = 15.0
MARGIN_Y        = 5.0
CARIMBO_H       = 40.0
HEADER_H        = 25.0
GRID_GAP_X      = 20.0
GRID_GAP_Y      = 20.0
COLS_DEFAULT    = 4
PAD_BOTTOM_COTA = 50.0   # espaço abaixo do bbox para cotas (y=-45 no SCR)
PAD_COTA_RIGHT  = 40.0   # espaço à direita para cota de espessura (x+30 no SCR)
PAD_TOP_GEOM    = 10.0   # margem acima do topo do bbox

LAYERS = [
    ('Painéis',       200),
    ('SARR_2.2x7',     40),
    ('SARR_2.2x5',     40),
    ('NOMENCLATURA',    7),
    ('COTA',          241),
    ('5',               5),
    ('CARIMBO',         9),
    ('BORDA_CELULA',    9),
]


def setup_doc():
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    if 'HIDDEN' not in doc.linetypes:
        doc.linetypes.add('HIDDEN', pattern=[0.375, 0.25, -0.125])
    for name, color in LAYERS:
        if name not in doc.layers:
            doc.layers.add(name, color=color)
    # Dimstyle COTA — replica visual do BASE_DWG_PARA_COMANDOS_SCRIPTS
    if 'COTA' not in doc.dimstyles:
        ds = doc.dimstyles.new('COTA')
        ds.dxf.dimtxt   = 3.5    # altura do texto (cm)
        ds.dxf.dimasz   = 2.5    # tamanho das setas
        ds.dxf.dimexo   = 1.0    # offset da linha de extensão
        ds.dxf.dimexe   = 2.0    # extensão da linha além da cota
        ds.dxf.dimgap   = 0.9    # espaço entre linha de cota e texto
        ds.dxf.dimdec   = 0      # casas decimais
        ds.dxf.dimrnd   = 1.0    # arredondamento para 1 unidade
        ds.dxf.dimscale = 1.0    # escala geral
        ds.dxf.dimclrd  = 4      # cor linha cota (cyan)
        ds.dxf.dimclre  = 4      # cor linhas extensão
        ds.dxf.dimclrt  = 4      # cor texto
    return doc, msp


def draw_closed_poly(msp, pts, layer, color=None):
    attribs = {'layer': layer}
    if color is not None:
        attribs['color'] = color
    return msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)


# ---------------------------------------------------------------------------
# Inline SCR parser
# ---------------------------------------------------------------------------

def scr_text_to_doc(scr_text: str):
    """Converte texto SCR (string) para documento ezdxf temporário."""
    lines = tokenize(scr_text)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    if 'HIDDEN' not in doc.linetypes:
        doc.linetypes.add('HIDDEN', pattern=[0.375, 0.25, -0.125])

    LAYER_COLORS = {
        'Painéis': 200, 'SARR_2.2x7': 40, 'SARR_2.2x5': 40,
        'NOMENCLATURA': 7, 'COTA': 241, '5': 5, '0': 7,
    }

    def ensure_layer(name):
        if not name or name == '0':
            return
        if name not in doc.layers:
            doc.layers.add(name, color=LAYER_COLORS.get(name, 7))

    for nm in LAYER_COLORS:
        ensure_layer(nm)

    def parse_xy(s):
        s = s.strip().replace(' ', ',')
        parts = [p for p in s.split(',') if p]
        if len(parts) >= 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass
        return None

    current_layer    = '0'
    current_linetype = 'Continuous'
    i = 0
    n = len(lines)

    while i < n:
        ln     = lines[i].upper().strip()
        raw_ln = lines[i].strip()

        if raw_ln.startswith(';') or raw_ln == '':
            i += 1; continue

        # ZOOM — ignorar
        if ln in ('ZOOM', '_ZOOM'):
            i += 1
            while i < n:
                nxt = lines[i].strip().upper()
                if nxt.startswith(';') or nxt.startswith('_') or nxt.startswith('-') or \
                   nxt.startswith('LAYER') or nxt.startswith('PLINE') or \
                   nxt.startswith('TEXT') or nxt.startswith('DIM'):
                    break
                i += 1
            continue

        # LAYER
        if ln in ('LAYER', '-LAYER'):
            i += 1
            if i < n:
                tok    = lines[i].strip()
                tok_up = tok.upper()
                if tok_up.startswith('S '):
                    current_layer = tok[2:].strip(); i += 1
                elif tok_up == 'S':
                    i += 1
                    if i < n:
                        current_layer = lines[i].strip(); i += 1
                ensure_layer(current_layer)
            continue

        # LINETYPE
        if ln in ('-LINETYPE', 'LINETYPE'):
            i += 1
            if i < n:
                tok = lines[i].strip()
                if tok.upper().startswith('S '):
                    current_linetype = tok[2:].strip(); i += 1
                elif tok.upper() == 'S':
                    i += 1
                    if i < n:
                        current_linetype = lines[i].strip(); i += 1
            continue

        # STYLE / commands to skip
        if ln.startswith('-STYLE') or ln.startswith('-DIMSTYLE') or \
           ln.startswith('-INSERT') or ln.startswith('INSERT'):
            i += 1
            while i < n:
                nxt = lines[i].strip()
                if nxt.startswith(';') or nxt == '' or \
                   nxt.upper().startswith('_') or nxt.upper().startswith('-') or \
                   nxt.upper().startswith('LAYER') or nxt.upper().startswith('ZOOM'):
                    break
                i += 1
            continue

        # PLINE
        if ln in ('_PLINE', 'PLINE'):
            i += 1
            pts   = []
            close = False
            while i < n:
                raw = lines[i].strip()
                if raw.upper() == 'C':
                    close = True; i += 1; break
                if raw == '':
                    i += 1; break
                if raw.startswith(';') or raw.startswith('-') or raw.startswith('_') or \
                   raw.upper() in ('ZOOM', 'LAYER'):
                    break
                p = parse_xy(raw)
                if p:
                    pts.append(p)
                i += 1
            if len(pts) >= 2:
                attribs = {'layer': current_layer}
                if current_linetype and current_linetype.lower() not in ('continuous', ''):
                    attribs['linetype'] = current_linetype
                msp.add_lwpolyline(pts, close=close, dxfattribs=attribs)
            continue

        # LINE
        if ln in ('_LINE', 'LINE'):
            i += 1
            pts = []
            while i < n:
                raw = lines[i].strip()
                if raw == '' or raw.startswith(';') or raw.startswith('-') or \
                   raw.startswith('_') or raw.upper() in ('ZOOM', 'LAYER'):
                    break
                p = parse_xy(raw)
                if p:
                    pts.append(p)
                else:
                    i += 1; break
                i += 1
            if len(pts) >= 2:
                attribs = {'layer': current_layer}
                for j in range(0, len(pts) - 1, 2):
                    msp.add_line(pts[j], pts[j+1], dxfattribs=attribs)
            continue

        # TEXT
        if ln in ('_TEXT', '-TEXT', 'TEXT'):
            i += 1
            insert = None; height = 7.5; rotation = 0.0; text_str = ''
            if i < n:
                p = parse_xy(lines[i].strip())
                if p: insert = p; i += 1
            if i < n:
                try: height = float(lines[i].strip()); i += 1
                except ValueError: pass
            if i < n:
                try: rotation = float(lines[i].strip()); i += 1
                except ValueError: pass
            if i < n:
                text_str = lines[i].strip(); i += 1
            if insert and text_str:
                msp.add_text(text_str, dxfattribs={
                    'layer': current_layer, 'height': max(height, 1.0),
                    'rotation': rotation, 'insert': insert, 'color': 256,
                })
            continue

        # DIMLINEAR — pular (será adicionado diretamente no msp final com offset correto)
        if ln in ('_DIMLINEAR', 'DIMLINEAR'):
            i += 1
            for _ in range(3):
                if i < n:
                    raw = lines[i].strip()
                    if not raw.startswith(';') and raw != '':
                        i += 1
            continue

        # RECTANGLE — desenhar retângulo fechado (usado para obstáculos e aberturas)
        if ln in ('_RECTANGLE', 'RECTANGLE', 'RECTANG', '_RECTANG'):
            i += 1
            pt1 = None; pt2 = None
            for _ in range(2):
                if i < n:
                    raw = lines[i].strip()
                    if not raw.startswith(';') and raw != '':
                        p = parse_xy(raw)
                        if p:
                            if pt1 is None: pt1 = p
                            else:           pt2 = p
                        i += 1
            if pt1 and pt2:
                pts = [pt1, (pt2[0], pt1[1]), pt2, (pt1[0], pt2[1])]
                msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': current_layer})
            continue

        # HHHH — marcador de centroide (laje/obstáculo): desenha um X pequeno
        if ln.startswith('HHHH'):
            coord_part = raw_ln[4:].strip()
            p = parse_xy(coord_part) if coord_part else None
            if p is None and i + 1 < n:
                i += 1
                p = parse_xy(lines[i].strip())
            if p:
                s = 3.0   # tamanho do X
                msp.add_line((p[0]-s, p[1]-s), (p[0]+s, p[1]+s), dxfattribs={'layer': current_layer})
                msp.add_line((p[0]+s, p[1]-s), (p[0]-s, p[1]+s), dxfattribs={'layer': current_layer})
            i += 1
            continue

        # EX2 / BEXTEND / I — comandos LISP do robot
        if ln in ('EX2', 'BEXTEND', 'I', 'EX', 'EXTEND', 'F'):
            i += 1
            for _ in range(2):
                if i < n and (parse_xy(lines[i]) or lines[i].strip() == ''):
                    i += 1
            continue

        i += 1

    return doc, msp


def add_dimlinears_from_scr(msp, scr_text: str, dx: float, dy: float, layer: str = 'COTA'):
    """
    Extrai blocos DIMLINEAR do texto SCR, aplica offset (dx, dy)
    e renderiza como entidades DIMENSION no msp.
    """
    lines = tokenize(scr_text)
    n = len(lines)

    def parse_xy(s):
        s = s.strip().replace(' ', ',')
        parts = [p for p in s.split(',') if p]
        if len(parts) >= 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                pass
        return None

    i = 0
    while i < n:
        ln = lines[i].strip().upper()
        if ln in ('_DIMLINEAR', 'DIMLINEAR'):
            i += 1
            pt1 = None; pt2 = None; dim_pos = None
            for _ in range(3):
                if i >= n:
                    break
                raw = lines[i].strip()
                if raw.startswith(';') or raw == '':
                    break
                p = parse_xy(raw)
                if p:
                    if pt1 is None:   pt1 = p
                    elif pt2 is None: pt2 = p
                    else:             dim_pos = p
                    i += 1
                else:
                    break
            if pt1 and pt2 and dim_pos:
                p1o  = (pt1[0]     + dx, pt1[1]     + dy)
                p2o  = (pt2[0]     + dx, pt2[1]     + dy)
                dpo  = (dim_pos[0] + dx, dim_pos[1] + dy)
                ddx  = abs(pt2[0] - pt1[0])
                angle = 90.0 if ddx < 0.1 else 0.0
                try:
                    dim = msp.add_linear_dim(
                        base=dpo, p1=p1o, p2=p2o,
                        angle=angle,
                        dimstyle='COTA',
                        dxfattribs={'layer': layer}
                    )
                    dim.render()
                except Exception:
                    pass
        else:
            i += 1


def get_entities_bbox(msp):
    """Calcula bounding box das entidades geométricas."""
    xs, ys = [], []
    for e in msp:
        if e.dxftype() == 'LINE':
            xs += [e.dxf.start.x, e.dxf.end.x]
            ys += [e.dxf.start.y, e.dxf.end.y]
        elif e.dxftype() == 'LWPOLYLINE':
            for p in e.get_points():
                xs.append(p[0]); ys.append(p[1])
        elif e.dxftype() == 'TEXT':
            xs.append(e.dxf.insert.x); ys.append(e.dxf.insert.y)
    if xs and ys:
        return min(xs), min(ys), max(xs), max(ys)
    return 0.0, 0.0, 200.0, 80.0   # fallback


def draw_carimbo(msp, cell_ox, cell_oy, cell_w, obra, pav, num, name):
    cx, cy = cell_ox, cell_oy
    draw_closed_poly(msp, [(cx, cy), (cx + cell_w, cy),
                            (cx + cell_w, cy + CARIMBO_H), (cx, cy + CARIMBO_H)],
                     'BORDA_CELULA')
    rows = [('CLIENTE', obra),
            ('PAVIMENTO', pav),
            ('ELEMENTO', name)]
    row_h = CARIMBO_H / len(rows)
    for i, (label, val) in enumerate(rows):
        ry = cy + CARIMBO_H - (i + 1) * row_h
        msp.add_line((cx, ry), (cx + cell_w, ry), dxfattribs={'layer': 'CARIMBO'})
        msp.add_text(label + ':', dxfattribs={'layer': 'CARIMBO', 'height': 3.5, 'color': 9,
                                               'insert': (cx + 3, ry + row_h / 2)})
        msp.add_text(val, dxfattribs={'layer': 'CARIMBO', 'height': 4.0, 'color': 2,
                                      'insert': (cx + 35, ry + row_h / 2)})
    msp.add_text(f'{num:02d}', dxfattribs={'layer': 'CARIMBO', 'color': 3, 'height': 7.0,
                                            'insert': (cx + cell_w - 15, cy + 5)})


def draw_fundo_face_via_scr(msp, name, jdata, cell_ox, cell_oy, pav, cell_h=None):
    """Desenha face FV usando pipeline SCR."""
    beam_w  = float(jdata.get('total_width', 15.0))
    total_w = sum(float(p['width']) for p in jdata.get('panels', []))

    # Gerar SCR
    dados = json_to_dados_fv(jdata)
    scr_text = gerar_scr_fv(dados)

    # Converter SCR -> doc temporário (sem DIMLINEAR)
    tmp_doc, tmp_msp = scr_text_to_doc(scr_text)
    bbox = get_entities_bbox(tmp_msp)
    geom_h = bbox[3] - bbox[1]

    # ---- Posicionamento: ancoramos o FUNDO do bbox ----
    # target_y = onde bbox[1] (y_min do bbox) vai parar no output
    # Reservamos PAD_BOTTOM_COTA abaixo do bbox para as cotas (y=-45 no SCR)
    target_x = cell_ox + MARGIN_X
    target_y = cell_oy + CARIMBO_H + MARGIN_Y + PAD_BOTTOM_COTA

    dx = target_x - bbox[0]
    dy = target_y - bbox[1]

    # Header: label acima da geometria (nome completo do JSON + pav)
    header_y = target_y + geom_h + 5.0
    full_name = jdata.get('name', name)
    msp.add_text(
        f'{full_name} [FUNDO] -- {pav}',
        dxfattribs={'layer': 'NOMENCLATURA', 'color': 256, 'height': 5.0,
                    'insert': (cell_ox + MARGIN_X, header_y)}
    )

    # Copiar entidades geométricas com offset
    # Pular TEXT do layer NOMENCLATURA (robot coloca nome da viga; usamos nosso header acima)
    for e in tmp_msp:
        if e.dxftype() == 'TEXT' and e.dxf.layer == 'NOMENCLATURA':
            continue
        _copy_entity_with_offset(msp, e, dx, dy)

    # Adicionar DIMLINEAR diretamente no msp final com offset aplicado
    add_dimlinears_from_scr(msp, scr_text, dx, dy, layer='COTA')

    # Info esp no header (sem sobreposição com cotas)
    msp.add_text(
        f'esp={beam_w:.0f}cm',
        dxfattribs={'layer': 'COTA', 'color': 256, 'height': 3.5,
                    'insert': (cell_ox + MARGIN_X + total_w * 0.6, header_y)}
    )


def build_grid(json_dir, out_path, obra_name, pav, cols):
    files = sorted(json_dir.glob('V*_fundo.json'),
                   key=lambda p: int(''.join(filter(str.isdigit, p.stem.split('_')[0]))))
    if not files:
        print(f'ERRO: Nenhum V*_fundo.json em {json_dir}')
        sys.exit(1)

    print(f'  {len(files)} fundos de viga encontrados')
    doc, msp = setup_doc()

    # ---- Primeira passagem: bbox real + tamanho de célula ----
    all_jdata  = []
    cell_sizes = []
    for jpath in files:
        jdata = json.loads(jpath.read_text(encoding='utf-8', errors='replace'))
        all_jdata.append(jdata)

        dados    = json_to_dados_fv(jdata)
        scr_text = gerar_scr_fv(dados)
        _, tmp_msp = scr_text_to_doc(scr_text)
        bbox = get_entities_bbox(tmp_msp)

        geom_w = bbox[2] - bbox[0]
        geom_h = bbox[3] - bbox[1]

        # Largura: geometria + margem esq + pad cota direita (cota esp a x+30)
        cw = MARGIN_X * 2 + geom_w + PAD_COTA_RIGHT
        # Altura: carimbo + margem + espaço cotas + geometria + área header (15cm)
        ch = CARIMBO_H + MARGIN_Y + PAD_BOTTOM_COTA + geom_h + 15.0
        cell_sizes.append((cw, ch))

    max_cell_w = max(cw for cw, _ in cell_sizes)
    n = len(files)

    # Alturas de linha (máximo da linha + gap)
    row_heights = []
    for r in range(0, n, cols):
        row_hs = [cell_sizes[j][1] for j in range(r, min(r + cols, n))]
        row_heights.append(max(row_hs) + GRID_GAP_Y)

    # Posições Y de início de cada linha (crescendo para baixo = Y negativo)
    row_y_starts = []
    y = 0.0
    for rh in row_heights:
        y -= rh
        row_y_starts.append(y)

    cell_w_grid = max_cell_w + GRID_GAP_X

    # ---- Segunda passagem: renderizar ----
    for i, jpath in enumerate(files):
        name     = jpath.stem.replace('_fundo', '')
        jdata    = all_jdata[i]
        face_pav = jdata.get('floor', pav)

        r      = i // cols
        col    = i % cols
        row_h  = row_heights[r]
        cell_h = row_h - GRID_GAP_Y

        cell_ox = col * cell_w_grid
        cell_oy = row_y_starts[r]

        # Borda da célula
        draw_closed_poly(msp, [
            (cell_ox, cell_oy), (cell_ox + max_cell_w, cell_oy),
            (cell_ox + max_cell_w, cell_oy + cell_h), (cell_ox, cell_oy + cell_h),
        ], 'BORDA_CELULA')

        try:
            draw_fundo_face_via_scr(msp, name, jdata, cell_ox, cell_oy, face_pav, cell_h=cell_h)
            draw_carimbo(msp, cell_ox, cell_oy, max_cell_w, obra_name, face_pav, i + 1, name)
            total_w = sum(float(p['width']) for p in jdata.get('panels', []))
            beam_w  = float(jdata.get('total_width', 15.0))
            print(f'  {name}: total_w={total_w:.0f}cm esp={beam_w:.0f}cm  [{col},{r}]')
        except Exception as e:
            print(f'  ERRO {name}: {e}')
            import traceback; traceback.print_exc()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_path))
    print(f'\n  Salvo: {out_path}')
    print(f'  Grid: {len(files)} fundos — {cols} cols x {len(row_heights)} linhas')


def main():
    parser = argparse.ArgumentParser(description='Gera DXF de fundos de vigas via SCR')
    parser.add_argument('--obra', default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    parser.add_argument('--pav',  default='TÉRREO')
    parser.add_argument('--cols', type=int, default=COLS_DEFAULT)
    parser.add_argument('--out',  default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    obra_name = obra_path.name
    json_dir  = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Fundo'

    if not json_dir.exists():
        print(f'ERRO: {json_dir} não existe')
        sys.exit(1)

    out_path = Path(args.out) if args.out else \
        obra_path / 'Fase-5_Geracao_Scripts' / 'DXF_Vigas' / f'vigas_fundo_{obra_name}.dxf'

    print(f'\n=== GERAR DXF VIGAS FUNDO (via SCR) ===')
    print(f'  Obra  : {obra_name}')
    print(f'  JSON  : {json_dir}')
    print(f'  Output: {out_path}')
    print(f'  Cols  : {args.cols}\n')

    build_grid(json_dir, out_path, obra_name, args.pav, args.cols)


if __name__ == '__main__':
    main()
