#!/usr/bin/env python3
"""
gerar_vigas_laterais_via_scr.py
Gera DXF de laterais de viga (LV) usando pipeline SCR:
  JSON Fase-4 → SCR (robot-compatible) → DXF (via ezdxf)

Mantém o mesmo layout de grid e carimbo do estilo visual ALIMONTI.

Uso:
  python scripts/gerar_vigas_laterais_via_scr.py
  python scripts/gerar_vigas_laterais_via_scr.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1 --cols 4
"""
import sys
import argparse
import json
import io
from pathlib import Path

import ezdxf
from ezdxf.enums import TextEntityAlignment

# Import das funções do pipeline SCR
_SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(_SCRIPTS))
from json_to_scr_lv import json_to_dados, gerar_scr_lv, soma_altura
from scr_to_dxf import scr_to_dxf_doc, _copy_entity_with_offset, read_scr, tokenize

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---------------------------------------------------------------------------
# CONSTANTES (cm)
# ---------------------------------------------------------------------------
MARGIN_X     = 15.0
MARGIN_Y     = 5.0
CARIMBO_H    = 40.0
HEADER_H     = 25.0
DIM_SPACE    = 30.0
COTA_RIGHT   = 45.0   # espaço à direita para cotas verticais
GRID_GAP_X   = 20.0
GRID_GAP_Y   = 20.0
COLS_DEFAULT = 4

LAYERS = [
    ('Painéis',       200),
    ('SARR_2.2x7',     40),
    ('SARR_2.2x3.5',   40),
    ('SARR_2.2x5',     40),
    ('SARR_3.5x7',     81),
    ('NOMENCLATURA',    7),
    ('COTA',          241),
    ('Texto Seção',     7),
    ('texto',           7),
    ('5',               5),
    ('CARIMBO',         9),
    ('BORDA_CELULA',    9),
    ('Nível',         160),
    ('Hachura',       251),
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
        ds.dxf.dimtxt   = 3.5
        ds.dxf.dimasz   = 2.5
        ds.dxf.dimexo   = 1.0
        ds.dxf.dimexe   = 2.0
        ds.dxf.dimgap   = 0.9
        ds.dxf.dimdec   = 0
        ds.dxf.dimrnd   = 1.0
        ds.dxf.dimscale = 1.0
        ds.dxf.dimclrd  = 4
        ds.dxf.dimclre  = 4
        ds.dxf.dimclrt  = 4
    return doc, msp


def draw_closed_poly(msp, pts, layer, color=None):
    attribs = {'layer': layer}
    if color is not None:
        attribs['color'] = color
    return msp.add_lwpolyline(pts, close=True, dxfattribs=attribs)


def scr_text_to_doc(scr_text: str):
    """
    Converte texto SCR (string) para documento ezdxf temporário.
    Usa a mesma lógica do scr_to_dxf.scr_to_dxf_doc mas recebe string.
    """
    lines = tokenize(scr_text)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    if 'HIDDEN' not in doc.linetypes:
        doc.linetypes.add('HIDDEN', pattern=[0.375, 0.25, -0.125])

    LAYER_COLORS = {
        'Painéis': 200, 'SARR_2.2x7': 40, 'SARR_2.2x3.5': 40, 'SARR_2.2x5': 40,
        'SARR_3.5x7': 81, 'NOMENCLATURA': 7, 'COTA': 241, 'texto': 7,
        '5': 5, 'Nível': 160, 'Hachura': 251, '0': 7,
    }

    def ensure_layer(name):
        if not name or name == '0':
            return
        if name not in doc.layers:
            color = LAYER_COLORS.get(name, 7)
            doc.layers.add(name, color=color)

    for nm, col in LAYER_COLORS.items():
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

    def is_coord(s):
        return parse_xy(s) is not None

    current_layer = '0'
    current_linetype = 'Continuous'
    i = 0
    n = len(lines)

    while i < n:
        ln = lines[i].upper().strip()
        raw_ln = lines[i].strip()

        if raw_ln.startswith(';') or raw_ln == '':
            i += 1
            continue

        if ln in ('ZOOM', '_ZOOM'):
            i += 1
            while i < n and not lines[i].strip().startswith(';') and \
                  lines[i].strip().upper() not in ('', '_ZOOM', 'ZOOM') and \
                  not lines[i].strip().upper().startswith('_') and \
                  not lines[i].strip().upper().startswith('-') and \
                  not lines[i].strip().upper().startswith('LAYER') and \
                  not lines[i].strip().upper().startswith('PLINE') and \
                  not lines[i].strip().upper().startswith('LINE') and \
                  not lines[i].strip().upper().startswith('TEXT') and \
                  not lines[i].strip().upper().startswith('DIM'):
                i += 1
            continue

        if ln in ('LAYER', '-LAYER', 'LAYER\n'):
            i += 1
            if i < n:
                next_tok = lines[i].strip()
                next_up = next_tok.upper()
                if next_up.startswith('S '):
                    current_layer = next_tok[2:].strip()
                    i += 1
                elif next_up == 'S':
                    i += 1
                    if i < n:
                        current_layer = lines[i].strip()
                        i += 1
                ensure_layer(current_layer)
            continue

        if ln in ('-LINETYPE', 'LINETYPE'):
            i += 1
            if i < n:
                next_tok = lines[i].strip()
                if next_tok.upper().startswith('S '):
                    current_linetype = next_tok[2:].strip()
                    i += 1
                elif next_tok.upper() == 'S':
                    i += 1
                    current_linetype = lines[i].strip() if i < n else ''
                    if i < n: i += 1
            continue

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

        if ln in ('_PLINE', 'PLINE'):
            i += 1
            pts = []
            close = False
            while i < n:
                raw = lines[i].strip()
                if raw.upper() == 'C':
                    close = True; i += 1; break
                if raw == '':
                    i += 1; break
                if raw.upper().startswith(';') or raw.upper().startswith('-') or \
                   raw.upper().startswith('_') or raw.upper() in ('ZOOM', 'LAYER'):
                    break
                p = parse_xy(raw)
                if p is not None:
                    pts.append(p)
                i += 1
            if len(pts) >= 2:
                attribs = {'layer': current_layer}
                if current_linetype and current_linetype.lower() not in ('continuous', ''):
                    attribs['linetype'] = current_linetype
                msp.add_lwpolyline(pts, close=close, dxfattribs=attribs)
            continue

        if ln in ('_LINE', 'LINE'):
            i += 1
            pts = []
            while i < n:
                raw = lines[i].strip()
                if raw == '' or raw.upper().startswith(';') or \
                   raw.upper().startswith('-') or raw.upper().startswith('_') or \
                   raw.upper() in ('ZOOM', 'LAYER'):
                    break
                p = parse_xy(raw)
                if p is not None:
                    pts.append(p)
                else:
                    i += 1; break
                i += 1
            if len(pts) >= 2:
                attribs = {'layer': current_layer}
                if current_linetype and current_linetype.lower() not in ('continuous', ''):
                    attribs['linetype'] = current_linetype
                for j in range(0, len(pts) - 1, 2):
                    msp.add_line(pts[j], pts[j+1], dxfattribs=attribs)
            continue

        if ln in ('_TEXT', '-TEXT', 'TEXT'):
            i += 1
            insert = None
            height = 7.5
            rotation = 0.0
            text_str = ''
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

        if ln in ('_DIMLINEAR', 'DIMLINEAR'):
            # Pular 3 linhas de coordenadas (será adicionado ao msp final com offset correto)
            i += 1
            for _ in range(3):
                if i < n:
                    raw = lines[i].strip()
                    if not raw.startswith(';') and raw != '':
                        i += 1
            continue

        # RECTANGLE — retângulo fechado (obstáculos, aberturas)
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

        # HHHH — marcador de centroide: desenha um X pequeno
        if raw_ln.upper().startswith('HHHH'):
            coord_part = raw_ln[4:].strip()
            p = parse_xy(coord_part) if coord_part else None
            if p is None and i + 1 < n:
                i += 1
                p = parse_xy(lines[i].strip()) if i < n else None
            if p:
                s = 4.0
                msp.add_line((p[0]-s, p[1]-s), (p[0]+s, p[1]+s), dxfattribs={'layer': current_layer})
                msp.add_line((p[0]+s, p[1]-s), (p[0]-s, p[1]+s), dxfattribs={'layer': current_layer})
            i += 1
            continue

        if ln in ('EX2', 'BEXTEND', 'I', 'EX', 'EXTEND'):
            i += 1
            for _ in range(2):
                if i < n and (is_coord(lines[i]) or lines[i].strip() == ''):
                    i += 1
            continue

        i += 1

    return doc, msp


def get_entities_bbox(msp):
    """Calcula bounding box das entidades (LWPOLYLINE + LINE + TEXT)."""
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
    return 0, 0, 100, 100


def add_dimlinears_from_scr(msp, scr_text: str, dx: float, dy: float, layer: str = 'COTA'):
    """Extrai DIMLINEAR do SCR, aplica offset e renderiza no msp."""
    lines = tokenize(scr_text)
    n = len(lines)

    def parse_xy(s):
        s = s.strip().replace(' ', ',')
        parts = [p for p in s.split(',') if p]
        if len(parts) >= 2:
            try: return float(parts[0]), float(parts[1])
            except ValueError: pass
        return None

    i = 0
    while i < n:
        ln = lines[i].strip().upper()
        if ln in ('_DIMLINEAR', 'DIMLINEAR'):
            i += 1
            pt1 = None; pt2 = None; dim_pos = None
            for _ in range(3):
                if i >= n: break
                raw = lines[i].strip()
                if raw.startswith(';') or raw == '': break
                p = parse_xy(raw)
                if p:
                    if pt1 is None:   pt1 = p
                    elif pt2 is None: pt2 = p
                    else:             dim_pos = p
                    i += 1
                else:
                    break
            if pt1 and pt2 and dim_pos:
                p1o  = (pt1[0] + dx,     pt1[1] + dy)
                p2o  = (pt2[0] + dx,     pt2[1] + dy)
                dpo  = (dim_pos[0] + dx, dim_pos[1] + dy)
                ddx  = abs(pt2[0] - pt1[0])
                angle = 90.0 if ddx < 0.1 else 0.0
                try:
                    dim = msp.add_linear_dim(base=dpo, p1=p1o, p2=p2o,
                                             angle=angle, dimstyle='COTA',
                                             dxfattribs={'layer': layer})
                    dim.render()
                except Exception:
                    pass
        else:
            i += 1


def calc_cell_size(data):
    """Calcula tamanho da célula com base nos dados JSON."""
    total_w = sum(float(p['width']) for p in data['panels'])
    total_h = float(soma_altura(str(data.get('total_height', 120))))
    cell_w = MARGIN_X * 2 + total_w + COTA_RIGHT + 10
    cell_h = CARIMBO_H + MARGIN_Y + total_h + DIM_SPACE + HEADER_H + 30
    return cell_w, cell_h


def draw_carimbo(msp, cell_ox, cell_oy, cell_w, obra, pav, num, name):
    cx, cy = cell_ox, cell_oy
    draw_closed_poly(msp, [(cx, cy), (cx + cell_w, cy),
                           (cx + cell_w, cy + CARIMBO_H), (cx, cy + CARIMBO_H)],
                     'BORDA_CELULA')
    rows = [('CLIENTE', obra), ('PAVIMENTO', pav), ('ELEMENTO', name)]
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


def draw_face_via_scr(msp, name, data, cell_ox, cell_oy, pav, max_cell_h=None):
    """Desenha face LV usando pipeline SCR (geometria idêntica ao robô)."""
    total_w = sum(float(p['width']) for p in data['panels'])
    total_h = float(soma_altura(str(data.get('total_height', 120))))

    # Posição de ancoragem (parte superior da célula, acima do carimbo)
    used_h = max_cell_h if max_cell_h is not None else (
        CARIMBO_H + MARGIN_Y + total_h + DIM_SPACE + HEADER_H + 30
    )

    # Gerar SCR a partir do JSON
    dados = json_to_dados(data)
    scr_text = gerar_scr_lv(dados)

    # Converter SCR para entidades ezdxf (temp doc)
    tmp_doc, tmp_msp = scr_text_to_doc(scr_text)

    # Calcular bbox da geometria gerada (sem DIMENSION/TEXT fora do painel)
    bbox = get_entities_bbox(tmp_msp)
    geom_w = bbox[2] - bbox[0]  # largura real
    geom_h = bbox[3] - bbox[1]  # altura real (y_max-y_min)

    # Target: face começa em MARGIN_X da esquerda, e é posicionada acima do carimbo+margin
    # A face deve estar a DIM_SPACE acima do fundo da célula + CARIMBO_H
    target_x = cell_ox + MARGIN_X
    target_y = cell_oy + used_h - HEADER_H - 5.0 - geom_h

    # Offset para mover geometria gerada ao target
    dx = target_x - bbox[0]
    dy = target_y - bbox[1]

    # Header
    msp.add_text(
        f'{name} -- {pav}',
        dxfattribs={'layer': 'NOMENCLATURA', 'color': 256, 'height': 5.0,
                    'insert': (cell_ox + MARGIN_X, cell_oy + used_h - HEADER_H / 2)}
    )

    # Copiar entidades com offset
    for e in tmp_msp:
        _copy_entity_with_offset(msp, e, dx, dy)

    # Adicionar DIMLINEAR com offset aplicado
    add_dimlinears_from_scr(msp, scr_text, dx, dy, layer='COTA')

    # Cota total_width label
    msp.add_text(
        f'TOTAL={total_w:.0f}cm',
        dxfattribs={'layer': 'COTA', 'color': 256, 'height': 3.0,
                    'insert': (cell_ox + MARGIN_X, cell_oy + used_h - HEADER_H - 5.0 + geom_h + 3)}
    )


def build_grid(json_dir, out_path, obra_name, pav, cols):
    files = sorted(json_dir.glob('*.json'),
                   key=lambda p: (p.stem.split('_')[0], p.stem))
    if not files:
        print(f'ERRO: Nenhum JSON em {json_dir}')
        return

    print(f'  {len(files)} laterais de viga encontradas')

    doc, msp = setup_doc()

    cell_sizes = []
    for jpath in files:
        data = json.loads(jpath.read_text(encoding='utf-8', errors='replace'))
        cw, ch = calc_cell_size(data)
        cell_sizes.append((cw, ch))

    max_cell_w = max(cw for cw, ch in cell_sizes)
    n = len(files)
    row_heights = []
    for r in range(0, n, cols):
        row_hs = [cell_sizes[j][1] for j in range(r, min(r + cols, n))]
        row_heights.append(max(row_hs) + GRID_GAP_Y)

    row_y_starts = []
    y = 0
    for rh in row_heights:
        y -= rh
        row_y_starts.append(y)

    cell_w = max_cell_w + GRID_GAP_X

    for i, jpath in enumerate(files):
        name = jpath.stem
        data = json.loads(jpath.read_text(encoding='utf-8', errors='replace'))
        face_pav = data.get('floor', pav)

        r = i // cols
        col = i % cols
        row_h = row_heights[r]
        row_cell_h = row_h - GRID_GAP_Y

        cell_ox = col * cell_w
        cell_oy = row_y_starts[r]

        draw_closed_poly(msp, [
            (cell_ox, cell_oy), (cell_ox + max_cell_w, cell_oy),
            (cell_ox + max_cell_w, cell_oy + row_cell_h), (cell_ox, cell_oy + row_cell_h),
        ], 'BORDA_CELULA')

        try:
            draw_face_via_scr(msp, name, data, cell_ox, cell_oy, face_pav, max_cell_h=row_cell_h)
            draw_carimbo(msp, cell_ox, cell_oy, max_cell_w, obra_name, face_pav, i + 1, name)
            total_w = sum(float(p['width']) for p in data['panels'])
            total_h = float(soma_altura(str(data.get('total_height', 120))))
            print(f'  {name}: w={total_w:.0f}cm h={total_h:.0f}cm [{col},{r}]')
        except Exception as e:
            import traceback
            print(f'  ERRO {name}: {e}')
            traceback.print_exc()

    total_rows = len(row_heights)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_path))
    print(f'\n  Salvo: {out_path}')
    print(f'  Grid: {len(files)} laterais — {cols} cols x {total_rows} linhas')


def main():
    parser = argparse.ArgumentParser(description='Gera DXF de laterais de viga via pipeline SCR')
    parser.add_argument('--obra', default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    parser.add_argument('--pav', default='TERREO')
    parser.add_argument('--cols', type=int, default=COLS_DEFAULT)
    parser.add_argument('--out', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    obra_name = obra_path.name
    json_dir  = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Laterais'

    if not json_dir.exists():
        print(f'ERRO: {json_dir} nao existe')
        return

    out_path = Path(args.out) if args.out else \
        obra_path / 'Fase-5_Geracao_Scripts' / 'DXF_Vigas' / f'vigas_laterais_{obra_name}.dxf'

    print(f'\n=== GERAR DXF VIGAS LATERAIS (via SCR) ===')
    print(f'  Obra  : {obra_name}')
    print(f'  JSON  : {json_dir}')
    print(f'  Output: {out_path}')
    print(f'  Cols  : {args.cols}\n')

    build_grid(json_dir, out_path, obra_name, args.pav, args.cols)


if __name__ == '__main__':
    main()
