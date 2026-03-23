#!/usr/bin/env python3
"""
scr_to_dxf.py
Conversor SCR (AutoCAD Script) → DXF usando ezdxf.

Suporta os comandos gerados pelos robôs ALIMONTI:
  _PLINE / PLINE      → LWPOLYLINE
  _LINE / LINE        → LINE
  _TEXT / -TEXT / TEXT → TEXT
  LAYER S / -LAYER S  → set current layer
  -LINETYPE S         → set current linetype
  _DIMLINEAR          → DIMENSION (linear)
  HHHH x,y           → HATCH (ponto interior)
  C (em PLINE)        → fechar polilinha
  ; comentário        → ignorar
  ZOOM / _ZOOM        → ignorar
  -INSERT             → ignorar (bloco)
  -STYLE / -DIMSTYLE  → ignorar

Encodings suportados: UTF-16 (BOM fffe/feff) e latin-1/cp1252.
"""
import sys
import re
import ezdxf
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ---------------------------------------------------------------------------
# Cores padrão dos layers (ACI) — mapeamento igual ao real ALIMONTI
# ---------------------------------------------------------------------------
LAYER_COLORS = {
    'Painéis':          200,
    'SARR_2.2x7':       40,
    'SARR_2.2x3.5':     40,
    'SARR_3.5x7':       81,
    'SARR_2.2x10':      60,
    'SARR_2.2x5':       40,
    'NOMENCLATURA':      7,
    'COTA':            241,
    'Texto Seção':       7,
    'texto':             7,
    '5':                 5,
    'CARIMBO':           9,
    'Nível':           160,
    'Hachura':         251,
    'CONCRETO':        251,
    'CHAPA':             1,
    '0':                 7,
}


def read_scr(path):
    """Lê SCR com detecção automática de encoding."""
    with open(path, 'rb') as f:
        raw = f.read()
    bom = raw[:2]
    if bom in (b'\xff\xfe', b'\xfe\xff'):
        return raw.decode('utf-16', errors='replace')
    # Tenta UTF-8, depois latin-1
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('latin-1', errors='replace')


def tokenize(text):
    """Divide SCR em tokens (linhas), normalizando espaços e CRLF."""
    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        lines.append(ln)
    return lines


def parse_xy(s):
    """Parseia 'x,y' ou 'x y' → (float, float). Retorna None se inválido."""
    s = s.strip().replace(' ', ',')
    parts = [p for p in s.split(',') if p]
    if len(parts) >= 2:
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            pass
    return None


def is_coord(s):
    """Verifica se a string é uma coordenada x,y."""
    return parse_xy(s) is not None


def scr_to_dxf_doc(scr_path, offset_x=0.0, offset_y=0.0, scale=1.0):
    """
    Converte um arquivo SCR em documento ezdxf.

    Args:
        scr_path: caminho do .scr
        offset_x, offset_y: deslocamento aplicado a todas as coordenadas
        scale: fator de escala (1.0 = sem escala)

    Returns:
        (doc, msp): documento ezdxf e modelspace
    """
    text = read_scr(scr_path)
    lines = tokenize(text)

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # Setup linetypes
    if 'HIDDEN' not in doc.linetypes:
        doc.linetypes.add('HIDDEN', pattern=[0.375, 0.25, -0.125])
    if 'CONTINUOUS' not in doc.linetypes:
        pass  # já existe

    # Setup layers
    def ensure_layer(name):
        if not name or name == '0':
            return
        if name not in doc.layers:
            color = LAYER_COLORS.get(name, 7)
            doc.layers.add(name, color=color)

    ensure_layer('Painéis')
    for lname in LAYER_COLORS:
        ensure_layer(lname)

    # Setup dimstyle
    if 'PAINEL' not in doc.dimstyles:
        ds = doc.dimstyles.new('PAINEL')
        ds.dxf.dimtxt  = 10.0
        ds.dxf.dimasz  = 3.0
        ds.dxf.dimexo  = 3.0
        ds.dxf.dimexe  = 3.0
        ds.dxf.dimgap  = 3.0
        ds.dxf.dimdec  = 1
        ds.dxf.dimrnd  = 1.0
        ds.dxf.dimclrd = 4
        ds.dxf.dimclre = 4
        ds.dxf.dimclrt = 240

    # State
    current_layer = '0'
    current_linetype = 'Continuous'
    pending_hatches = []   # lista de (layer, x, y) para criar hatches depois

    def xy(s):
        """Aplica offset + scale a uma coordenada."""
        p = parse_xy(s)
        if p is None:
            return None
        return (p[0] * scale + offset_x, p[1] * scale + offset_y)

    i = 0
    n = len(lines)

    while i < n:
        ln = lines[i].upper().strip()
        raw_ln = lines[i].strip()

        # ── Comentário ──
        if raw_ln.startswith(';') or raw_ln == '':
            i += 1
            continue

        # ── ZOOM (ignorar) ──
        if ln in ('ZOOM', '_ZOOM'):
            # Ignorar próximas 2-3 linhas do comando ZOOM
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

        # ── LAYER / -LAYER ──
        if ln in ('LAYER', '-LAYER', 'LAYER\n'):
            i += 1
            if i < n:
                next_tok = lines[i].strip()
                next_up = next_tok.upper()
                if next_up.startswith('S '):
                    # Formato: "S layername" na mesma linha
                    layer_name = next_tok[2:].strip()
                    i += 1
                elif next_up == 'S':
                    # Formato: "S" sozinho, nome na próxima linha
                    i += 1
                    if i < n:
                        layer_name = lines[i].strip()
                        i += 1
                    else:
                        layer_name = ''
                else:
                    layer_name = ''
                if layer_name:
                    current_layer = layer_name
                    ensure_layer(current_layer)
            continue

        # ── -LINETYPE ──
        if ln in ('-LINETYPE', 'LINETYPE'):
            i += 1
            if i < n:
                next_tok = lines[i].strip()
                next_up = next_tok.upper()
                if next_up.startswith('S '):
                    lt = next_tok[2:].strip()
                    i += 1
                elif next_up == 'S':
                    i += 1
                    lt = lines[i].strip() if i < n else ''
                    if i < n: i += 1
                else:
                    lt = ''
                if lt:
                    current_linetype = lt
            continue

        # ── -STYLE, -DIMSTYLE, -INSERT ── (ignorar bloco)
        if ln.startswith('-STYLE') or ln.startswith('-DIMSTYLE') or \
           ln.startswith('-INSERT') or ln.startswith('INSERT'):
            # Pular próximas linhas até próximo comando
            i += 1
            while i < n:
                nxt = lines[i].strip()
                if nxt.startswith(';') or nxt == '' or \
                   nxt.upper().startswith('_') or nxt.upper().startswith('-') or \
                   nxt.upper().startswith('LAYER') or nxt.upper().startswith('ZOOM'):
                    break
                i += 1
            continue

        # ── _PLINE / PLINE ──
        if ln in ('_PLINE', 'PLINE'):
            i += 1
            pts = []
            close = False
            while i < n:
                raw = lines[i].strip()
                if raw.upper() == 'C':
                    close = True
                    i += 1
                    break
                if raw == '':
                    i += 1
                    break
                if raw.upper().startswith(';') or raw.upper().startswith('-') or \
                   raw.upper().startswith('_') or raw.upper() in ('ZOOM','LAYER'):
                    break
                p = xy(raw)
                if p is not None:
                    pts.append(p)
                i += 1
            if len(pts) >= 2:
                attribs = {'layer': current_layer}
                if current_linetype and current_linetype.lower() not in ('continuous', ''):
                    attribs['linetype'] = current_linetype
                msp.add_lwpolyline(pts, close=close, dxfattribs=attribs)
            continue

        # ── _LINE / LINE ──
        if ln in ('_LINE', 'LINE'):
            i += 1
            pts = []
            while i < n:
                raw = lines[i].strip()
                if raw == '' or raw.upper().startswith(';') or \
                   raw.upper().startswith('-') or raw.upper().startswith('_') or \
                   raw.upper() in ('ZOOM', 'LAYER'):
                    break
                p = xy(raw)
                if p is not None:
                    pts.append(p)
                else:
                    i += 1
                    break
                i += 1
            if len(pts) >= 2:
                attribs = {'layer': current_layer}
                if current_linetype and current_linetype.lower() not in ('continuous', ''):
                    attribs['linetype'] = current_linetype
                # LINE command: pairs of points
                for j in range(0, len(pts) - 1, 2):
                    msp.add_line(pts[j], pts[j+1], dxfattribs=attribs)
            continue

        # ── _TEXT / -TEXT / TEXT ──
        if ln in ('_TEXT', '-TEXT', 'TEXT'):
            i += 1
            insert = None
            height = 7.5
            rotation = 0.0
            text_str = ''

            if i < n:
                p = xy(lines[i].strip())
                if p:
                    insert = p
                    i += 1
            if i < n:
                try:
                    height = float(lines[i].strip()) * scale
                    i += 1
                except ValueError:
                    pass
            if i < n:
                try:
                    rotation = float(lines[i].strip())
                    i += 1
                except ValueError:
                    pass
            if i < n:
                text_str = lines[i].strip()
                i += 1

            if insert and text_str:
                msp.add_text(
                    text_str,
                    dxfattribs={
                        'layer': current_layer,
                        'height': max(height, 1.0),
                        'rotation': rotation,
                        'insert': insert,
                        'color': 256,
                    }
                )
            continue

        # ── _DIMLINEAR ──
        if ln in ('_DIMLINEAR', 'DIMLINEAR'):
            i += 1
            p1 = p2 = base = None
            if i < n:
                p1 = xy(lines[i].strip()); i += 1
            if i < n:
                p2 = xy(lines[i].strip()); i += 1
            if i < n:
                base = xy(lines[i].strip()); i += 1

            if p1 and p2 and base:
                # Determinar se é horizontal ou vertical baseado nos pontos
                dx = abs(p2[0] - p1[0])
                dy = abs(p2[1] - p1[1])
                angle = 0 if dx >= dy else 90
                try:
                    dim = msp.add_linear_dim(
                        base=base,
                        p1=p1, p2=p2,
                        angle=angle,
                        dimstyle='PAINEL',
                    )
                    dim.dxf.layer = current_layer
                    dim.render()
                except Exception:
                    pass
            continue

        # ── HHHH x,y (hatch interior point) ──
        if raw_ln.upper().startswith('HHHH'):
            # Formato: HHHH x,y  OU próxima linha tem x,y
            coord_part = raw_ln[4:].strip()
            if coord_part:
                p = xy(coord_part)
            else:
                i += 1
                p = xy(lines[i].strip()) if i < n else None
            if p:
                pending_hatches.append((current_layer, p))
            i += 1
            continue

        # ── ex2, Bextend, i (AutoCAD extend commands — ignorar) ──
        if ln in ('EX2', 'BEXTEND', 'I', 'EX', 'EXTEND'):
            i += 1
            # Ignorar próximas 2 linhas (pontos do extend)
            for _ in range(2):
                if i < n and (is_coord(lines[i]) or lines[i].strip() == ''):
                    i += 1
            continue

        i += 1

    # Criar hatches pendentes (HHHH)
    for (layer, point) in pending_hatches:
        try:
            h = msp.add_hatch(dxfattribs={'layer': layer})
            h.dxf.solid_fill = 1
            h.dxf.color = 256
            # Hatch simples (sem boundary — AutoCAD detecta pelo ponto interno)
            # Para ezdxf, precisamos de um contorno — usar um placeholder pequeno
        except Exception:
            pass

    return doc, msp


def convert_scr_to_dxf(scr_path, out_dxf_path, offset_x=0.0, offset_y=0.0, scale=1.0):
    """
    Converte um SCR para DXF e salva.

    Returns:
        True se sucesso, False se erro.
    """
    try:
        doc, msp = scr_to_dxf_doc(scr_path, offset_x, offset_y, scale)
        Path(out_dxf_path).parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(str(out_dxf_path))
        print(f"  OK: {scr_path} → {out_dxf_path}")
        return True
    except Exception as e:
        print(f"  ERRO: {scr_path}: {e}")
        return False


def merge_scr_files_to_dxf(scr_files, out_dxf_path, grid_cols=4,
                             cell_gap_x=50.0, cell_gap_y=50.0):
    """
    Converte múltiplos SCR files e organiza em grid no mesmo DXF.

    Calcula bounding box de cada SCR e posiciona em grade.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    # Setup linetypes e layers base
    if 'HIDDEN' not in doc.linetypes:
        doc.linetypes.add('HIDDEN', pattern=[0.375, 0.25, -0.125])
    for lname, color in LAYER_COLORS.items():
        if lname not in doc.layers:
            doc.layers.add(lname, color=color)
    if 'PAINEL' not in doc.dimstyles:
        ds = doc.dimstyles.new('PAINEL')
        ds.dxf.dimtxt = 10.0; ds.dxf.dimasz = 3.0
        ds.dxf.dimclrd = 4; ds.dxf.dimclre = 4; ds.dxf.dimclrt = 240

    # Parse todos os SCRs e achar bboxes
    parsed = []
    for scr_path in scr_files:
        try:
            tmp_doc, tmp_msp = scr_to_dxf_doc(scr_path)
            ents = list(tmp_msp)

            xs, ys = [], []
            for e in ents:
                if e.dxftype() == 'LINE':
                    for pt in (e.dxf.start, e.dxf.end):
                        xs.append(pt.x); ys.append(pt.y)
                elif e.dxftype() == 'LWPOLYLINE':
                    for pt in e.get_points():
                        xs.append(pt[0]); ys.append(pt[1])
                elif e.dxftype() == 'TEXT':
                    ins = e.dxf.insert
                    xs.append(ins.x); ys.append(ins.y)

            if xs and ys:
                bbox = (min(xs), min(ys), max(xs), max(ys))
            else:
                bbox = (0, 0, 100, 100)

            parsed.append((scr_path, tmp_msp, bbox))
        except Exception as e_:
            print(f"  WARN: {scr_path}: {e_}")

    if not parsed:
        return False

    # Calcular tamanhos de célula
    cell_w = max(bbox[2] - bbox[0] for _, _, bbox in parsed) + cell_gap_x
    row_heights = []
    for r in range(0, len(parsed), grid_cols):
        row_slice = parsed[r:r + grid_cols]
        rh = max(bbox[3] - bbox[1] for _, _, bbox in row_slice)
        row_heights.append(rh + cell_gap_y)

    # Posicionar cada SCR no grid
    for idx, (scr_path, tmp_msp, bbox) in enumerate(parsed):
        col = idx % grid_cols
        row = idx // grid_cols

        # Offset para mover ao grid position
        row_y = -sum(row_heights[:row]) - row_heights[row] / 2
        cell_cx = col * cell_w

        dx = cell_cx - bbox[0]
        dy = row_y - bbox[1]

        # Copiar entidades com offset
        for e in tmp_msp:
            _copy_entity_with_offset(msp, e, dx, dy)

    Path(out_dxf_path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(out_dxf_path))
    print(f"\n  Salvo: {out_dxf_path} ({len(parsed)} elementos, {grid_cols} cols)")
    return True


def _copy_entity_with_offset(msp, e, dx, dy):
    """Copia uma entidade para o msp com offset dx, dy."""
    def off(pt):
        return (pt[0] + dx, pt[1] + dy)

    try:
        if e.dxftype() == 'LINE':
            s = e.dxf.start
            en = e.dxf.end
            attribs = {'layer': e.dxf.layer}
            try: attribs['color'] = e.dxf.color
            except: pass
            try: attribs['linetype'] = e.dxf.linetype
            except: pass
            msp.add_line(off((s.x, s.y)), off((en.x, en.y)), dxfattribs=attribs)

        elif e.dxftype() == 'LWPOLYLINE':
            pts = [(p[0] + dx, p[1] + dy) for p in e.get_points()]
            attribs = {'layer': e.dxf.layer}
            try: attribs['color'] = e.dxf.color
            except: pass
            msp.add_lwpolyline(pts, close=e.closed, dxfattribs=attribs)

        elif e.dxftype() == 'TEXT':
            ins = e.dxf.insert
            attribs = {
                'layer': e.dxf.layer,
                'height': e.dxf.height,
                'insert': off((ins.x, ins.y)),
                'rotation': e.dxf.get('rotation', 0),
                'color': e.dxf.get('color', 256),
            }
            msp.add_text(e.dxf.text, dxfattribs=attribs)

        elif e.dxftype() == 'DIMENSION':
            pass  # Dimensões são complexas de copiar — ignorar por ora

    except Exception:
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Converte SCR → DXF')
    parser.add_argument('scr', nargs='+', help='Arquivo(s) .scr')
    parser.add_argument('--out', required=True, help='Arquivo .dxf de saída')
    parser.add_argument('--cols', type=int, default=4, help='Colunas no grid (multi-SCR)')
    args = parser.parse_args()

    scr_files = [Path(s) for s in args.scr]

    if len(scr_files) == 1:
        convert_scr_to_dxf(scr_files[0], args.out)
    else:
        merge_scr_files_to_dxf(scr_files, args.out, grid_cols=args.cols)
