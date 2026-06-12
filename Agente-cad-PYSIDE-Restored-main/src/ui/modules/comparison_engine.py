"""
Comparison Engine — Tab 2
Fase-8: Validação Visual (NVIDIA NIM) + Certificação de Obras.
Layout: [DualCanvas | Painel Fase-8]
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# ── Crash diagnostics: log nativo no ce_crash.log e faulthandler ──────────
import faulthandler as _fh
_CE_LOG = Path("D:/Agente-cad-PYSIDE/ce_debug.log")
try:
    _CE_LOG.parent.mkdir(parents=True, exist_ok=True)
    _fh.enable(file=open(str(_CE_LOG), 'a'), all_threads=True)
except Exception:
    pass

def _ce_log(*args):
    """Escreve mensagem de diagnóstico no ce_debug.log (flush imediato)."""
    try:
        msg = " ".join(str(a) for a in args)
        ts  = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(str(_CE_LOG), 'a', encoding='utf-8') as _f:
            _f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel,
    QPushButton, QComboBox, QCheckBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QScrollArea, QSplitter, QGroupBox, QTextEdit, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QSizePolicy,
    QListWidget, QListWidgetItem, QApplication, QLineEdit,
)
from PySide6.QtCore import Qt, QProcess, Signal, QRect, QRectF, QPointF, QThread, QObject, QTimer, QEvent
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPainterPath, QPixmap, QTransform

from src.ui.components.organisms import DualCanvasManager
from src.ui.theme import Colors, Fonts, Radius

try:
    from src.core.services.comparison_service import ComparisonService, FieldStatus
    from src.core.services.audit_exporter import AuditExporter
    _COMP_AVAILABLE = True
except ImportError:
    _COMP_AVAILABLE = False

DADOS_OBRAS_ROOT  = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
VALIDACAO_DIR     = Path("D:/Agente-cad-PYSIDE/validacao_visual")
SCRIPTS_DIR       = Path(__file__).parent.parent.parent.parent / "scripts"

# ── 3-Level comparison paths ─────────────────────────────────────────────────
OBRA_TREINO_16  = DADOS_OBRAS_ROOT / "Obra_TREINO_16"
CROPS_DIR_3N    = Path("C:/Users/Thierry/Desktop/lv_3niveis_crops")
LV_RENDERS_DIR  = Path("C:/Users/Thierry/Desktop/lv_pag_renders")
GEN_SCRIPT_3N   = Path("C:/Users/Thierry/Desktop/gen_3niveis_html.py")
VIGAS_LV_LIST   = ["V4", "V5", "V6", "V7"]

# Mapeamento classe → script gerador N3 (todos em scripts/)
_N3_SCRIPTS = {
    'PL': 'gerar_pl_dxf_stog.py',
    'LV': 'gerar_lv_dxf_stog.py',
    'FV': 'gerar_fv_dxf_stog.py',
    'LJ': 'gerar_lj_dxf_stog.py',
}

NIVEL_DEFS = [
    # (id,  titulo,                    bg_color,   accent,     descricao,                                                       mode)
    ("N1", "Estrutura Real",           "#1b3a6b",  "#4a9eff",  "DXF Estrutural · Fase 1\nPosição e dimensões reais do elemento", 'dxf'),
    ("N2", "STOG Real DXF",            "#1a4a2a",  "#4acf7a",  "Eng. Reversa · Fase 1\nForms, seções e sarrafos STOG",           'dxf'),
    ("N3", "Robot via Ficha SA",       "#4a2a1a",  "#cf8a4a",  "Robot N3 · Fase 4→6\nDXF gerado via ficha do Structural Analyzer", 'dxf'),
    ("N4", "Robot via Ficha ER",       "#2d1a47",  "#a855f7",  "Robot N4 · Fase 2→6\nDXF gerado via Ficha Eng. Reversa (STOG real)", 'dxf'),
]

TIPOS = ["PL", "LV", "FV", "LJ"]

# ── ACI Color map (AutoCAD Color Index → QColor) ─────────────────────────────
_ACI: dict[int, str] = {
    0: '#cccccc', 1: '#ff0000', 2: '#ffff00', 3: '#00ff00',
    4: '#00ffff', 5: '#0000ff', 6: '#ff00ff', 7: '#ffffff',
    8: '#414141', 9: '#808080', 10: '#ff4040', 11: '#ffff80',
    12: '#80ff80', 13: '#80ffff', 14: '#8080ff', 15: '#ff80ff',
    20: '#ff6600', 30: '#ff7f00', 40: '#bfbf00', 50: '#80ff00',
    60: '#00bf80', 70: '#0080ff', 80: '#4000ff', 90: '#8000ff',
    100: '#ff0080', 110: '#ff00ff', 120: '#ff40ff', 130: '#ff80ff',
    140: '#ffaaaa', 150: '#aaffaa', 160: '#aaaaff', 170: '#aaffff',
    180: '#ffaaff', 190: '#ffffaa', 200: '#c0c0c0', 210: '#808080',
    250: '#333333', 251: '#555555', 252: '#777777', 253: '#999999',
    254: '#bbbbbb', 255: '#dddddd', 256: '#cccccc',
}


def _entity_color(entity, doc=None) -> str:
    """Resolve uma cor hex '#rrggbb' para uma entidade DXF (sem Qt objects — thread-safe).
    Chamada no worker thread; QColor é criado depois no main thread."""
    try:
        tc = entity.rgb
        if tc is not None:
            return '#{:02x}{:02x}{:02x}'.format(int(tc[0]), int(tc[1]), int(tc[2]))
    except Exception:
        pass
    try:
        aci = entity.dxf.color
        if aci == 256 and doc:        # BYLAYER
            try:
                lyr = doc.layers.get(entity.dxf.layer)
                aci = abs(lyr.dxf.color)
            except Exception:
                aci = 7
        return _ACI.get(aci, '#cccccc')
    except Exception:
        return '#cccccc'


def _ep_to_cmds(ep) -> list:
    """Converte ezdxf Path em lista de comandos puros Python (sem Qt — thread-safe).
    Formato: [('M', x, y), ('L', x, y), ('Q', cx,cy,ex,ey), ('C', c1x,c1y,c2x,c2y,ex,ey)]
    """
    cmds = [('M', ep.start.x, ep.start.y)]
    for cmd in ep:
        ct = cmd.type
        end = cmd.end
        if ct.value == 4:    # MOVE_TO
            cmds.append(('M', end.x, end.y))
        elif ct.value == 1:  # LINE_TO
            cmds.append(('L', end.x, end.y))
        elif ct.value == 2:  # CURVE3_TO (quadratic)
            ctrl = cmd.ctrl
            cmds.append(('Q', ctrl.x, ctrl.y, end.x, end.y))
        elif ct.value == 3:  # CURVE4_TO (cubic)
            c1, c2 = cmd.ctrl1, cmd.ctrl2
            cmds.append(('C', c1.x, c1.y, c2.x, c2.y, end.x, end.y))
    return cmds


def _cmds_to_qpath(cmds: list) -> QPainterPath:
    """Converte lista de comandos Python → QPainterPath. Chamar APENAS no main thread."""
    qp = QPainterPath()
    for cmd in cmds:
        t = cmd[0]
        if t == 'M':
            qp.moveTo(cmd[1], cmd[2])
        elif t == 'L':
            qp.lineTo(cmd[1], cmd[2])
        elif t == 'Q':
            qp.quadTo(cmd[1], cmd[2], cmd[3], cmd[4])
        elif t == 'C':
            qp.cubicTo(cmd[1], cmd[2], cmd[3], cmd[4], cmd[5], cmd[6])
    return qp


def _raw_ops_to_qt(raw_ops: list) -> list:
    """Converte ops raw (str + list) → ops Qt (QColor + QPainterPath).
    DEVE ser chamada no main thread — cria objetos Qt.

    Formatos suportados (novos do ezdxf backend + legado):
      ('path',    color_hex, lw, cmds_list)
      ('fill',    color_hex, lw, cmds_list)
      ('polygon', color_hex, lw, [(x,y),...])   → fill fechado
      ('line',    color_hex, lw, (x0,y0), (x1,y1))
      ('point',   color_hex, lw, (x, y))
      ('text',    color_hex, (dx, dy, txt, h))  ← legado sem lw
    """
    result = []
    for op in raw_ops:
        kind = op[0]
        try:
            if kind in ('path', 'fill'):
                if len(op) == 4:
                    # novo formato: (kind, color, lw, cmds)
                    _, color_str, lw, cmds = op
                else:
                    # legado: (kind, color, cmds)
                    _, color_str, cmds = op
                    lw = 0.25
                qp = _cmds_to_qpath(cmds)
                if not qp.isEmpty():
                    result.append((kind, QColor(color_str), lw, qp))

            elif kind == 'polygon':
                _, color_str, lw, pts = op
                if pts:
                    qp = QPainterPath()
                    qp.moveTo(pts[0][0], pts[0][1])
                    for x, y in pts[1:]:
                        qp.lineTo(x, y)
                    qp.closeSubpath()
                    result.append(('fill', QColor(color_str), lw, qp))

            elif kind == 'lines':
                # Batch de segmentos [(x0,y0,x1,y1),...] — uma QPainterPath por cor/lw
                _, color_str, lw, segs = op
                qp = QPainterPath()
                for x0, y0, x1, y1 in segs:
                    qp.moveTo(x0, y0)
                    qp.lineTo(x1, y1)
                if not qp.isEmpty():
                    result.append(('path', QColor(color_str), lw, qp))

            elif kind == 'line':
                _, color_str, lw, p0, p1 = op
                qp = QPainterPath()
                qp.moveTo(p0[0], p0[1])
                qp.lineTo(p1[0], p1[1])
                result.append(('path', QColor(color_str), lw, qp))

            elif kind == 'point':
                _, color_str, lw, pos = op
                qp = QPainterPath()
                qp.addEllipse(pos[0] - 1, pos[1] - 1, 2, 2)
                result.append(('fill', QColor(color_str), lw, qp))

            elif kind == 'text':
                _, color_str, data = op
                result.append(('text', QColor(color_str), 0.25, data))

        except Exception:
            pass   # op malformado — ignorar silenciosamente
    return result


# Caps conservadores — priorizamos segurança de memória sobre completude visual
_MAX_PATH_OPS   = 600   # paths/lines
_MAX_FILL_OPS   = 20    # HATCH fills — muito pesados
_MAX_TEXT_OPS   = 60    # textos
_MAX_INSERT_OPS = 15    # blocos expandidos

# DXFs maiores que este limite não são renderizados inline (evita OOM)
_MAX_DXF_MB = 30.0


def _collect_dxf_ops(dxf_path: Path, bbox: tuple, cancelled_flag=None) -> list:
    """
    Carrega um DXF e extrai draw-ops dentro da bbox.
    Retorna ops RAW (sem Qt objects — apenas str e listas Python) para
    ser convertido no main thread via _raw_ops_to_qt().
    - Arquivos > _MAX_DXF_MB retornam lista especial [('too_large', None, size_mb)]
    - cancelled_flag: lista [bool] — se [True], interrompe loop e retorna ops parciais
    """
    import ezdxf
    from ezdxf import path as ezpath
    import gc, math

    try:
        size_mb = dxf_path.stat().st_size / 1024 / 1024
        if size_mb > _MAX_DXF_MB:
            return [('too_large', None, size_mb)]
    except Exception:
        pass

    ops: list = []
    path_count = fill_count = text_count = insert_count = 0

    x0, y0, x1, y1 = bbox
    bw = x1 - x0; bh = y1 - y0
    pad = max(bw, bh) * 0.08
    bx0, by0, bx1, by1 = x0-pad, y0-pad, x1+pad, y1+pad

    def in_range(x, y):
        return bx0 <= x <= bx1 and by0 <= y <= by1

    def try_cmds(entity):
        """Retorna lista de comandos Python (sem QPainterPath) ou None."""
        try:
            ep = ezpath.make_path(entity)
            pts = list(ep.control_vertices())
            if not pts:
                return None
            step = max(1, len(pts) // 6)
            if not any(in_range(p.x, p.y) for p in pts[::step]):
                return None
            return _ep_to_cmds(ep) or None
        except Exception:
            return None

    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception:
        return ops

    for entity in msp:
        if cancelled_flag and cancelled_flag[0]:
            break
        t = entity.dxftype()
        color = _entity_color(entity, doc)   # retorna str hex
        try:
            if t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE'):
                if path_count >= _MAX_PATH_OPS:
                    continue
                cmds = try_cmds(entity)
                if cmds:
                    ops.append(('path', color, cmds)); path_count += 1

            elif t == 'HATCH':
                if fill_count >= _MAX_FILL_OPS:
                    continue
                try:
                    for sub in ezpath.from_hatch(entity):
                        if fill_count >= _MAX_FILL_OPS:
                            break
                        pts = list(sub.control_vertices())
                        if not pts:
                            continue
                        step = max(1, len(pts) // 6)
                        if not any(in_range(p.x, p.y) for p in pts[::step]):
                            continue
                        cmds = _ep_to_cmds(sub)
                        if cmds:
                            ops.append(('fill', color, cmds)); fill_count += 1
                except Exception:
                    pass

            elif t in ('TEXT', 'MTEXT'):
                if text_count >= _MAX_TEXT_OPS:
                    continue
                try:
                    ins = entity.dxf.insert
                    txt = (entity.dxf.text if t == 'TEXT'
                           else (entity.plain_text() if hasattr(entity, 'plain_text') else '')).strip()
                    h = entity.dxf.get('height' if t == 'TEXT' else 'char_height', 10)
                    if txt and in_range(ins.x, ins.y):
                        ops.append(('text', color, (ins.x, ins.y, txt[:30], h))); text_count += 1
                except Exception:
                    pass

            elif t == 'INSERT':
                if insert_count >= _MAX_INSERT_OPS:
                    continue
                try:
                    block_name = entity.dxf.name
                    blk = doc.blocks.get(block_name)
                    ins_x, ins_y = entity.dxf.insert.x, entity.dxf.insert.y
                    if not in_range(ins_x, ins_y):
                        continue
                    sx = entity.dxf.get('xscale', 1.0)
                    sy = entity.dxf.get('yscale', 1.0)
                    rot = math.radians(entity.dxf.get('rotation', 0.0))
                    cos_r, sin_r = math.cos(rot), math.sin(rot)
                    blk_added = 0
                    for blk_ent in blk:
                        if blk_added >= 10:
                            break
                        if blk_ent.dxftype() not in ('LINE', 'LWPOLYLINE', 'CIRCLE', 'ARC'):
                            continue
                        sub_cmds = try_cmds(blk_ent)
                        if sub_cmds is None:
                            continue
                        # Aplicar transform (scale + rotate + translate) nos comandos
                        t_cmds = []
                        for cmd in sub_cmds:
                            if cmd[0] == 'M':
                                lx = cmd[1]*sx*cos_r - cmd[2]*sy*sin_r + ins_x
                                ly = cmd[1]*sx*sin_r + cmd[2]*sy*cos_r + ins_y
                                t_cmds.append(('M', lx, ly))
                            elif cmd[0] == 'L':
                                lx = cmd[1]*sx*cos_r - cmd[2]*sy*sin_r + ins_x
                                ly = cmd[1]*sx*sin_r + cmd[2]*sy*cos_r + ins_y
                                t_cmds.append(('L', lx, ly))
                        if t_cmds:
                            blk_color = _entity_color(blk_ent, doc)
                            ops.append(('path', blk_color, t_cmds)); blk_added += 1
                    insert_count += 1
                except Exception:
                    pass
        except Exception:
            pass

    try:
        del doc
    except Exception:
        pass
    # NÃO chamar gc.collect() no worker thread — Python 3.14 + ezdxf crasha
    # durante finalização de objetos DXF quando gc.collect() é explicitamente chamado.
    return ops


def _load_dxf_single_pass(dxf_path: Path, bbox, cancelled_flag=None) -> list:
    """
    Lê o DXF UMA SÓ VEZ e retorna draw-ops.
    Se bbox=None, calcula bbox automaticamente na mesma leitura.
    Evita o double-readfile de _auto_bbox + _collect_dxf_ops.
    """
    import ezdxf
    from ezdxf import path as ezpath
    import gc

    SENTINEL_X = -5000

    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = list(doc.modelspace())   # materializa uma vez
    except Exception:
        return []

    # Passo 1: se bbox não fornecido, calcular a partir das entidades
    if bbox is None:
        xs, ys = [], []
        for e in msp:
            t = e.dxftype()
            try:
                if t == 'LWPOLYLINE':
                    for pt in e.vertices():
                        if pt[0] > SENTINEL_X:
                            xs.append(pt[0]); ys.append(pt[1])
                elif t == 'LINE':
                    sx2, ex2 = e.dxf.start.x, e.dxf.end.x
                    if sx2 > SENTINEL_X and ex2 > SENTINEL_X:
                        xs += [sx2, ex2]; ys += [e.dxf.start.y, e.dxf.end.y]
                elif t in ('TEXT', 'MTEXT', 'CIRCLE', 'ARC'):
                    if hasattr(e.dxf, 'insert'):
                        ix, iy = e.dxf.insert.x, e.dxf.insert.y
                        if ix > SENTINEL_X:
                            xs.append(ix); ys.append(iy)
                    elif t in ('CIRCLE', 'ARC') and hasattr(e.dxf, 'center'):
                        cx2, cy2 = e.dxf.center.x, e.dxf.center.y
                        if cx2 > SENTINEL_X:
                            xs.append(cx2); ys.append(cy2)
            except Exception:
                pass
        if not xs:
            try: del doc, msp
            except Exception: pass
            gc.collect()
            return []
        w2 = max(xs) - min(xs); h2 = max(ys) - min(ys)
        mx2 = max(w2 * 0.05, 10); my2 = max(h2 * 0.05, 10)
        bbox = (min(xs)-mx2, min(ys)-my2, max(xs)+mx2, max(ys)+my2)

    # Passo 2: coletar ops dentro da bbox
    x0, y0, x1, y1 = bbox
    bw = x1 - x0; bh = y1 - y0
    pad = max(bw, bh) * 0.08
    bx0, by0, bx1, by1 = x0-pad, y0-pad, x1+pad, y1+pad

    def in_range(x, y):
        return bx0 <= x <= bx1 and by0 <= y <= by1

    def try_cmds(entity):
        """Retorna lista de comandos Python (sem Qt objects) ou None."""
        try:
            ep = ezpath.make_path(entity)
            pts = list(ep.control_vertices())
            if not pts: return None
            step = max(1, len(pts) // 6)
            if not any(in_range(p.x, p.y) for p in pts[::step]): return None
            cmds = _ep_to_cmds(ep)
            return cmds if cmds else None
        except Exception:
            return None

    ops = []
    path_count = fill_count = text_count = insert_count = 0

    for entity in msp:
        if cancelled_flag and cancelled_flag[0]:
            break
        t = entity.dxftype()
        color = _entity_color(entity, doc)   # str hex — sem Qt
        try:
            if t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE'):
                if path_count >= _MAX_PATH_OPS: continue
                cmds = try_cmds(entity)
                if cmds:
                    ops.append(('path', color, cmds)); path_count += 1

            elif t == 'HATCH':
                if fill_count >= _MAX_FILL_OPS: continue
                try:
                    for sub in ezpath.from_hatch(entity):
                        if fill_count >= _MAX_FILL_OPS: break
                        pts2 = list(sub.control_vertices())
                        if not pts2: continue
                        step = max(1, len(pts2) // 6)
                        if not any(in_range(p.x, p.y) for p in pts2[::step]): continue
                        cmds = _ep_to_cmds(sub)
                        if cmds:
                            ops.append(('fill', color, cmds)); fill_count += 1
                except Exception: pass

            elif t in ('TEXT', 'MTEXT'):
                if text_count >= _MAX_TEXT_OPS: continue
                try:
                    ins = entity.dxf.insert
                    txt = (entity.dxf.text if t == 'TEXT'
                           else (entity.plain_text() if hasattr(entity, 'plain_text') else '')).strip()
                    h = entity.dxf.get('height' if t == 'TEXT' else 'char_height', 10)
                    if txt and in_range(ins.x, ins.y):
                        ops.append(('text', color, (ins.x, ins.y, txt[:30], h))); text_count += 1
                except Exception: pass

            elif t == 'INSERT':
                if insert_count >= _MAX_INSERT_OPS: continue
                try:
                    import math as _math
                    block_name = entity.dxf.name
                    blk = doc.blocks.get(block_name)
                    ins_x, ins_y = entity.dxf.insert.x, entity.dxf.insert.y
                    if not in_range(ins_x, ins_y): continue
                    sx = entity.dxf.get('xscale', 1.0); sy = entity.dxf.get('yscale', 1.0)
                    rot = _math.radians(entity.dxf.get('rotation', 0.0))
                    cos_r, sin_r = _math.cos(rot), _math.sin(rot)
                    blk_added = 0
                    for blk_ent in blk:
                        if blk_added >= 10: break
                        if blk_ent.dxftype() not in ('LINE', 'LWPOLYLINE', 'CIRCLE', 'ARC'): continue
                        sub_cmds = try_cmds(blk_ent)
                        if sub_cmds is None: continue
                        t_cmds = []
                        for cmd in sub_cmds:
                            if cmd[0] == 'M':
                                t_cmds.append(('M',
                                    cmd[1]*sx*cos_r - cmd[2]*sy*sin_r + ins_x,
                                    cmd[1]*sx*sin_r + cmd[2]*sy*cos_r + ins_y))
                            elif cmd[0] == 'L':
                                t_cmds.append(('L',
                                    cmd[1]*sx*cos_r - cmd[2]*sy*sin_r + ins_x,
                                    cmd[1]*sx*sin_r + cmd[2]*sy*cos_r + ins_y))
                        if t_cmds:
                            blk_color = _entity_color(blk_ent, doc)
                            ops.append(('path', blk_color, t_cmds)); blk_added += 1
                    insert_count += 1
                except Exception: pass
        except Exception: pass

    try: del doc, msp
    except Exception: pass
    # NÃO chamar gc.collect() aqui — Python 3.14 + ezdxf crasha durante GC explícito
    return ops


def _auto_bbox(dxf_path: Path):
    """Quick scan for DXF bounding box — used when caller doesn't know bbox.
    Filters sentinel lines at x < -5000 (robot-generated preview DXFs).
    Retorna None se arquivo > _MAX_DXF_MB (evita OOM)."""
    try:
        if dxf_path.stat().st_size / 1024 / 1024 > _MAX_DXF_MB:
            return None
    except Exception:
        pass
    try:
        import ezdxf as _ez
        doc = _ez.readfile(str(dxf_path))
        xs, ys = [], []
        SENTIN = -5000
        for e in doc.modelspace():
            t = e.dxftype()
            try:
                if t == 'LWPOLYLINE':
                    for pt in e.vertices():
                        if pt[0] > SENTIN:
                            xs.append(pt[0]); ys.append(pt[1])
                elif t == 'LINE':
                    sx, ex2 = e.dxf.start.x, e.dxf.end.x
                    if sx > SENTIN and ex2 > SENTIN:
                        xs += [sx, ex2]; ys += [e.dxf.start.y, e.dxf.end.y]
                elif t in ('TEXT', 'MTEXT'):
                    if hasattr(e.dxf, 'insert'):
                        ix, iy = e.dxf.insert.x, e.dxf.insert.y
                        if ix > SENTIN:
                            xs.append(ix); ys.append(iy)
                elif t == 'CIRCLE':
                    cx2, cy2 = e.dxf.center.x, e.dxf.center.y
                    if cx2 > SENTIN:
                        xs.append(cx2); ys.append(cy2)
            except Exception:
                pass
        if not xs:
            return None
        w = max(xs) - min(xs); h = max(ys) - min(ys)
        mx = max(w * 0.05, 10); my = max(h * 0.05, 10)
        return (min(xs)-mx, min(ys)-my, max(xs)+mx, max(ys)+my)
    except Exception:
        return None


class DXFLoadWorker(QThread):
    """Carrega DXF em subprocess isolado (sem PySide6, sem GC conflict).
    Python 3.14 + ezdxf causava access violation quando GC rodava durante
    ezdxf.readfile() no worker thread. Subprocess resolve completamente.

    FIX Python 3.14: passar listas grandes (>33MB pickle) via Signal(list)
    causa STATUS_STACK_BUFFER_OVERRUN (0xC0000409) no Windows. Solução: o
    worker salva o pickle num arquivo temporário e emite apenas o caminho
    (string curta). O main thread lê o arquivo e apaga-o.
    """

    loaded = Signal(str)    # emite caminho do arquivo temp com ops pickled
    failed = Signal(str)    # emite mensagem de erro

    # Caminho do script helper (mesmo diretório deste módulo)
    _HELPER = Path(__file__).parent / 'dxf_loader_worker.py'

    def __init__(self, dxf_path: Path, bbox):
        super().__init__()
        self._dxf_path  = dxf_path
        self._bbox      = bbox       # pode ser None → auto-compute no subprocess
        self._cancelled = [False]
        self._proc      = None       # subprocess.Popen

    def cancel(self):
        """Cancela: sinaliza flag. NÃO mata o subprocess — evita race condition
        entre kill() na main thread e communicate() no worker thread no Windows.
        O subprocess termina sozinho; resultado descartado pelo flag _cancelled."""
        self._cancelled[0] = True

    def run(self):
        import subprocess, json, pickle

        if self._cancelled[0]:
            return

        # Guard de tamanho rápido — sem subprocess para arquivos >_MAX_DXF_MB
        try:
            size_mb = self._dxf_path.stat().st_size / 1024 / 1024
            if size_mb > _MAX_DXF_MB:
                self.loaded.emit([('too_large', None, size_mb)])
                return
        except Exception:
            pass

        if self._cancelled[0]:
            return

        # Executar ezdxf em subprocess isolado — sem PySide6, sem GC conflict
        bbox_arg = json.dumps(list(self._bbox)) if self._bbox else 'null'
        try:
            self._proc = subprocess.Popen(
                [sys.executable, str(self._HELPER),
                 str(self._dxf_path), bbox_arg],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = self._proc.communicate(timeout=120)
            rc = self._proc.returncode
            self._proc = None
        except subprocess.TimeoutExpired:
            try: self._proc.kill()
            except Exception: pass
            self._proc = None
            if not self._cancelled[0]:
                self.failed.emit('Timeout ao carregar DXF (>120s)')
            return
        except Exception as e:
            self._proc = None
            if not self._cancelled[0]:
                self.failed.emit(f'Subprocess error: {e}')
            return

        if self._cancelled[0]:
            return

        if rc != 0 and not stdout:
            err = stderr.decode('utf-8', errors='replace')[:200] if stderr else f'rc={rc}'
            self.failed.emit(f'DXF loader falhou: {err}')
            return

        # Protocolo: pickle de lista de ops vetoriais
        try:
            ops = pickle.loads(stdout)
        except Exception as e:
            self.failed.emit(f'Desserialização falhou: {e}')
            return

        if not self._cancelled[0]:
            # Salva ops em arquivo temp para evitar crash STATUS_STACK_BUFFER_OVERRUN
            # ao passar lista grande (>33MB) via Signal(list) cross-thread no Python 3.14.
            import tempfile, os
            try:
                fd, tmp_path = tempfile.mkstemp(suffix='.dxfops.pkl', prefix='ce_')
                os.close(fd)
                with open(tmp_path, 'wb') as f:
                    pickle.dump(ops, f, protocol=4)
                self.loaded.emit(tmp_path)
            except Exception as e:
                self.failed.emit(f'Serialização temp falhou: {e}')


class DXFVectorView(QWidget):
    """
    Renderiza entidades DXF como vetores via QPainter (sem bitmap).
    Zoom e pan sem perda de qualidade — igual a um viewer DXF real.
    Emite `ready` quando o carregamento termina (sucesso ou falha).
    """

    ready = Signal()   # emitido ao terminar load (usado para loading sequencial)

    def __init__(self, bg: str = Colors.BG_DEEP, parent=None):
        super().__init__(parent)
        self._ops: list = []
        self._pixmap     = None   # QPixmap quando carregado via PNG subprocess
        self._scale     = 1.0
        self._offset    = QPointF(0.0, 0.0)
        self._drag_start  = None
        self._drag_origin = None
        self._status_text = "— sem DXF —"
        self._bg     = bg
        self._loading = False
        self._worker: DXFLoadWorker | None = None
        self._retiring_workers: list = []  # mantém refs Python vivas até QThread terminar
        self._dxf_bbox = None   # (x0, y0, x1, y1)

        self.setMinimumSize(200, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

    def showEvent(self, event):
        """Re-fit quando o widget fica visível — pode ter sido dimensionado
        DEPOIS do carregamento do DXF (tab oculta durante _on_loaded)."""
        super().showEvent(event)
        if self._dxf_bbox and (self._ops or self._pixmap):
            self._fit()
            self.update()

    # ── Public API ──────────────────────────────────────────────────

    def load_dxf(self, dxf_path, bbox=None):
        """Inicia carregamento DXF em thread separado. Cancela worker anterior.
        Se bbox=None, auto-computa a partir das entidades do DXF.
        Arquivos > _MAX_DXF_MB mostram mensagem sem tentar ler."""
        if dxf_path is None:
            self.clear_image("— DXF não disponível —")
            self.ready.emit()
            return
        # Guard de tamanho na UI thread — evita OOM antes mesmo de criar worker
        try:
            size_mb = Path(dxf_path).stat().st_size / 1024 / 1024
            if size_mb > _MAX_DXF_MB:
                self.clear_image(f"— DXF muito grande ({size_mb:.0f} MB) —")
                self.ready.emit()
                return
        except Exception:
            pass

        # Cancelar worker anterior — sinaliza flag e desconecta sinais
        if self._worker is not None:
            old = self._worker
            old.cancel()
            try:
                old.loaded.disconnect()
                old.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
            # Manter ref Python viva até o QThread terminar de verdade (evita crash
            # no Python 3.14 quando GC destrói o wrapper enquanto C++ ainda roda)
            self._retiring_workers.append(old)
            def _retire(w=old, lst=self._retiring_workers):
                try:
                    lst.remove(w)
                except ValueError:
                    pass
                try:
                    w.deleteLater()
                except RuntimeError:
                    pass
            try:
                old.finished.connect(_retire)
            except (RuntimeError, TypeError):
                _retire()  # thread já terminou, limpa agora
            self._worker = None

        self._ops = []
        self._dxf_bbox = bbox
        self._loading  = True
        self._status_text = "Carregando DXF..."
        self.update()

        self._worker = DXFLoadWorker(Path(dxf_path), bbox)
        self._worker.loaded.connect(self._on_loaded_file)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def zoom_to_bbox(self, bbox):
        """Reposiciona o viewport para a bbox dada SEM recarregar o DXF.
        Usa _fit() com a nova bbox. Se o DXF ainda não foi carregado, não faz nada."""
        if not (self._ops or self._pixmap):
            return
        if bbox:
            self._dxf_bbox = bbox
        self._fit()
        self.update()

    @property
    def is_loaded(self) -> bool:
        """True se há DXF carregado (ops ou pixmap disponíveis)."""
        return bool(self._ops or self._pixmap)

    def clear_image(self, msg: str = "— sem DXF —"):
        self._ops      = []
        self._pixmap   = None
        self._dxf_bbox = None
        self._loading  = False
        self._status_text = msg
        self.update()

    def cancel_load(self, msg: str = "— cancelado —"):
        """Cancela carregamento em andamento e limpa o widget.
        Diferente de load_dxf(None): cancela worker existente antes de limpar.
        Usar quando muda pavimento/obra para evitar resultado stale."""
        if self._worker is not None:
            old = self._worker
            old.cancel()
            try:
                old.loaded.disconnect()
                old.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
            # Mantém ref Python viva até QThread terminar (evita destruição de running thread)
            self._retiring_workers.append(old)
            def _retire(w=old, lst=self._retiring_workers):
                try:
                    lst.remove(w)
                except ValueError:
                    pass
                try:
                    w.deleteLater()
                except RuntimeError:
                    pass
            try:
                old.finished.connect(_retire)
            except (RuntimeError, TypeError):
                _retire()
            self._worker = None
        self._loading = False
        self.clear_image(msg)

    # ── Slots ────────────────────────────────────────────────────────

    def _on_loaded_file(self, tmp_path: str):
        """Lê ops do arquivo temporário gerado pelo worker e deleta o arquivo."""
        import os, pickle as _pickle
        try:
            with open(tmp_path, 'rb') as f:
                ops = _pickle.load(f)
        except Exception as e:
            self._worker = None
            self._loading = False
            self._status_text = f"Erro ao ler ops temp: {e}"
            self.update()
            self.ready.emit()
            return
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        self._on_loaded(ops)

    def _on_loaded(self, ops: list):
        self._worker  = None   # libera referência → GC pode limpar o thread
        self._loading = False

        if not ops:
            self._status_text = "— vazio —"
            self.update()
            self.ready.emit()
            return

        op0 = ops[0][0]

        # Caso especial: erro ou arquivo muito grande
        if op0 == 'too_large':
            size_mb = ops[0][2]
            self._ops = []
            self._pixmap = None
            self._status_text = f"— DXF muito grande ({size_mb:.0f} MB) —\nUse viewer externo"
            self.update()
            self.ready.emit()
            return

        if op0 == 'error':
            self._status_text = f"Erro: {str(ops[0][1])[:80]}"
            self.update()
            self.ready.emit()
            return

        # Extrair bbox computada pelo subprocess (primeiro op)
        if op0 == 'bbox':
            computed_bbox = ops[0][1]
            raw_ops = ops[1:]
            if computed_bbox and not self._dxf_bbox:
                self._dxf_bbox = computed_bbox
        else:
            raw_ops = ops

        # Converter ops vetoriais raw → Qt objects (no main thread, thread-safe)
        self._pixmap = None
        self._ops = _raw_ops_to_qt(raw_ops)
        self._status_text = f"{len(self._ops)} entidades" if self._ops else "— vazio —"
        # Fit imediato (pode falhar se widget ainda tem tamanho 0)
        self._fit()
        self.update()
        # Fit diferido: garante fit correto após o event loop processar o layout
        QTimer.singleShot(50, self._deferred_fit)
        self.ready.emit()

    def _on_failed(self, msg: str):
        self._worker  = None
        self._loading = False
        self._status_text = f"Erro: {msg[:60]}"
        self.update()
        self.ready.emit()

    # ── Fit ──────────────────────────────────────────────────────────

    def _deferred_fit(self):
        """Fit diferido — chamado via QTimer após o event loop processar o layout."""
        if self._dxf_bbox and (self._ops or self._pixmap):
            self._fit()
            self.update()

    def _fit(self):
        """Ajusta scale/offset para que a bbox DXF caiba no widget (com Y-flip)."""
        if not self._dxf_bbox:
            return
        x0, y0, x1, y1 = self._dxf_bbox
        dw, dh = x1 - x0, y1 - y0
        ww, wh = self.width(), self.height()
        if ww <= 0 or wh <= 0 or dw <= 0 or dh <= 0:
            return
        s = min(ww / dw, wh / dh) * 0.92
        cx_dxf = (x0 + x1) / 2
        cy_dxf = (y0 + y1) / 2
        # Y-flip: widget_y = oy - dxf_y * s → oy = wh/2 + cy_dxf * s
        ox = ww / 2 - cx_dxf * s
        oy = wh / 2 + cy_dxf * s
        self._scale  = s
        self._offset = QPointF(ox, oy)

    def _fit_pixmap(self):
        """Ajusta scale/offset para que o pixmap caiba centralizado no widget."""
        pm = self._pixmap
        if not pm or pm.isNull():
            return
        ww, wh = self.width(), self.height()
        pw, ph = pm.width(), pm.height()
        if ww <= 0 or wh <= 0 or pw <= 0 or ph <= 0:
            return
        s = min(ww / pw, wh / ph) * 0.97
        self._scale  = s
        self._offset = QPointF((ww - pw * s) / 2, (wh - ph * s) / 2)

    # ── Paint — puro vetorial com viewport culling ───────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(self._bg))

        # Modo PNG (ezdxf Frontend rendering)
        if self._pixmap and not self._pixmap.isNull():
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            ox = self._offset.x()
            oy = self._offset.y()
            s  = self._scale
            pw = self._pixmap.width()  * s
            ph = self._pixmap.height() * s
            p.drawPixmap(QRectF(ox, oy, pw, ph),
                         self._pixmap,
                         QRectF(self._pixmap.rect()))
            p.setPen(QColor(Colors.TEXT_DIM))
            p.setFont(QFont("Arial", 9))
            p.drawText(self.rect().adjusted(0, 0, -6, -4),
                       Qt.AlignRight | Qt.AlignBottom,
                       f"{s*100:.0f}%")
            p.end()
            return

        if not self._ops:
            p.setPen(QColor(Colors.TEXT_DIM))
            p.setFont(QFont("Arial", 11))
            p.drawText(self.rect(), Qt.AlignCenter, self._status_text)
            p.end()
            return

        ox = self._offset.x()
        oy = self._offset.y()
        s  = self._scale

        # Aplica transform DXF→widget com Y-flip
        p.translate(ox, oy)
        p.scale(s, -s)

        # Pen cache para evitar recriação por objeto
        _pen_cache: dict = {}

        for op in self._ops:
            op_type = op[0]
            color   = op[1]
            lw      = op[2]   # lineweight (float, mm)
            data    = op[3]

            if op_type == 'path':
                cache_key = color.rgb()
                pen = _pen_cache.get(cache_key)
                if pen is None:
                    pen = QPen(color, 0)   # cosmetic pen (largura 1px em pixels de tela)
                    pen.setCosmetic(True)
                    _pen_cache[cache_key] = pen
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawPath(data)

            elif op_type == 'fill':
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
                p.drawPath(data)

            elif op_type == 'text':
                dx, dy, txt, h = data
                wx = ox + dx * s
                wy = oy - dy * s
                p.resetTransform()
                px_h = max(6, min(int(h * s * 0.75), 48))
                p.setFont(QFont("Arial", px_h))
                p.setPen(color)
                p.drawText(QPointF(wx, wy), txt)
                p.translate(ox, oy)
                p.scale(s, -s)

        p.resetTransform()

        # Badge zoom
        p.setFont(QFont("Arial", 9))
        p.setPen(QColor(Colors.TEXT_DIM))
        p.drawText(self.rect().adjusted(0, 0, -6, -4),
                   Qt.AlignRight | Qt.AlignBottom,
                   f"{s*100:.0f}%  {len(self._ops)}")
        p.end()

    # ── Zoom centrado no cursor ──────────────────────────────────────

    def wheelEvent(self, event):
        has_content = bool(self._ops) or (self._pixmap and not self._pixmap.isNull())
        if not has_content:
            return
        factor = 1.18 if event.angleDelta().y() > 0 else 1.0 / 1.18
        cur = event.position()
        ox, oy = self._offset.x(), self._offset.y()
        s = self._scale
        new_s = max(0.001, min(s * factor, 2000.0))

        if self._pixmap and not self._pixmap.isNull():
            # Modo pixmap: sem Y-flip
            img_x = (cur.x() - ox) / s
            img_y = (cur.y() - oy) / s
            new_ox = cur.x() - img_x * new_s
            new_oy = cur.y() - img_y * new_s
        else:
            # Modo vetorial: com Y-flip
            dxf_x = (cur.x() - ox) / s
            dxf_y = (oy - cur.y()) / s
            new_ox = cur.x() - dxf_x * new_s
            new_oy = cur.y() + dxf_y * new_s

        self._scale  = new_s
        self._offset = QPointF(new_ox, new_oy)
        self.update()
        event.accept()

    # ── Pan ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        has_content = bool(self._ops) or (self._pixmap and not self._pixmap.isNull())
        if event.button() == Qt.LeftButton and has_content:
            self._drag_start  = event.position()
            self._drag_origin = QPointF(self._offset)
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            self._offset = self._drag_origin + (event.position() - self._drag_start)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.CrossCursor)

    def mouseDoubleClickEvent(self, event):
        """Double-click → fit."""
        if self._pixmap and not self._pixmap.isNull():
            self._fit_pixmap()
        else:
            self._fit()
        self.update()

    def resizeEvent(self, event):
        if self._pixmap and not self._pixmap.isNull():
            self._fit_pixmap()
        elif self._ops:
            self._fit()
        super().resizeEvent(event)
        self.update()


SCORE_COLORS = {
    "arete":  (Colors.ACCENT_GOLD,    "ARETE ≥85%"),
    "ok":     (Colors.ACCENT_SUCCESS,  "OK ≥75%"),
    "improve":(Colors.ACCENT_WARNING,  "MELHORAR ≥60%"),
    "bad":    (Colors.ACCENT_DANGER,   "INVESTIGAR <60%"),
}


def _score_category(score):
    if score is None:
        return None
    if score >= 85:
        return "arete"
    if score >= 75:
        return "ok"
    if score >= 60:
        return "improve"
    return "bad"


def _score_badge(score):
    if score is None:
        return "—"
    cat = _score_category(score)
    label = SCORE_COLORS[cat][1]
    return f"{score:.1f}%"


class ScoreLabel(QLabel):
    """Label de score com cor automática."""
    def set_score(self, score):
        if score is None:
            self.setText("—")
            self.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 20px; font-weight: bold;")
            return
        cat = _score_category(score)
        color = SCORE_COLORS[cat][0]
        self.setText(f"{score:.1f}%")
        self.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")


class ScoreSparkline(QWidget):
    """
    Mini-gráfico de linha para evolução de scores ao longo do tempo.
    Exibe os últimos N eventos de uma obra específica.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)
        self._points = []   # list of (x_norm, score)  0..1 each
        self._colors = {
            "PL": QColor("#7ab3e0"),  # hardcoded-ok: cor de série de gráfico, sem token equivalente
            "LV": QColor(Colors.ACCENT_SUCCESS),
            "FV": QColor(Colors.ACCENT_WARNING),
            "LJ": QColor("#e91e63"),  # hardcoded-ok: cor de série de gráfico, sem token equivalente
        }
        self._series = {}   # tipo → list of (x_norm, score)

    def set_events(self, events: list):
        """Recebe lista de dicts {scores, timestamp} e monta séries."""
        self._series = {t: [] for t in TIPOS}
        n = len(events)
        if n == 0:
            self.update()
            return
        for i, ev in enumerate(events):
            x = i / max(n - 1, 1)
            for tipo in TIPOS:
                sc = ev.get("scores", {}).get(tipo)
                if sc is not None:
                    self._series[tipo].append((x, sc))
        self.update()

    def paintEvent(self, event):
        if not any(self._series.values()):
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pad = 12

        # Fundo
        p.fillRect(0, 0, w, h, QColor(Colors.BG_DEEP))

        # Linhas de referência 60% e 75% e 85%
        for thr, label in [(60, "60"), (75, "75"), (85, "85")]:
            y = h - pad - (thr / 100) * (h - 2 * pad)
            pen = QPen(QColor(Colors.BG_CARD))
            pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawLine(pad, int(y), w - pad, int(y))
            p.setPen(QColor(Colors.TEXT_MUTED))
            p.setFont(QFont("Arial", 8))
            p.drawText(2, int(y) + 4, label)

        # Séries
        for tipo, pts in self._series.items():
            if len(pts) < 1:
                continue
            color = self._colors.get(tipo, QColor(Colors.TEXT_SECONDARY))
            pen = QPen(color, 2)
            p.setPen(pen)
            path = QPainterPath()
            first = True
            for x_norm, score in pts:
                px = pad + x_norm * (w - 2 * pad)
                py = h - pad - (score / 100) * (h - 2 * pad)
                if first:
                    path.moveTo(px, py)
                    first = False
                else:
                    path.lineTo(px, py)
            p.drawPath(path)
            # Dot no último ponto
            if pts:
                lx, ls = pts[-1]
                px = pad + lx * (w - 2 * pad)
                py = h - pad - (ls / 100) * (h - 2 * pad)
                p.setBrush(QBrush(color))
                p.drawEllipse(QPointF(px, py), 3, 3)

        p.end()


class Fase8Panel(QFrame):
    """
    Painel lateral de Fase-8: seleção de obra/tipo, execução de validação,
    exibição de scores e botão de certificação.
    """
    validation_requested = Signal(str, str, list)   # obra, pav, tipos[]

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_SECONDARY};
                border-right: 1px solid {Colors.ACCENT_BLUE};
            }}
            QLabel  {{ color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_MD}; }}
            QGroupBox {{
                color: {Colors.ACCENT_PRIMARY}; font-weight: bold; font-size: {Fonts.SIZE_MD};
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: {Radius.MD}; margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}
            QPushButton {{
                background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT};
                border-radius: {Radius.MD}; padding: 5px 12px;
                font-weight: bold; font-size: {Fonts.SIZE_MD};
            }}
            QPushButton:hover  {{ background: {Colors.ACCENT_BLUE_HOVER}; }}
            QPushButton:disabled {{ background: {Colors.BORDER_DEFAULT}; color: {Colors.TEXT_DIM}; }}
            QPushButton#certify {{
                background: {Colors.ACCENT_SUCCESS}; font-size: {Fonts.SIZE_LG}; padding: 7px 12px;
            }}
            QPushButton#certify:hover {{ background: rgba(67,160,71,1); }}
            QComboBox {{
                background: {Colors.BG_CARD}; color: {Colors.TEXT_PRIMARY}; border: 1px solid {Colors.BORDER_INPUT};
                border-radius: {Radius.SM}; padding: 3px 6px; font-size: {Fonts.SIZE_MD};
            }}
            QProgressBar {{
                border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: {Radius.SM};
                background: {Colors.BG_PANEL}; height: 8px;
            }}
            QProgressBar::chunk {{ background: {Colors.ACCENT_BLUE}; border-radius: {Radius.SM}; }}
            QCheckBox {{ color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_MD}; spacing: 5px; }}
            QTableWidget {{
                background: {Colors.BG_PANEL}; color: {Colors.TEXT_PRIMARY}; font-size: {Fonts.SIZE_SM};
                border: none; gridline-color: {Colors.BORDER_SUBTLE};
            }}
            QHeaderView::section {{
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM};
                border: none; padding: 3px;
            }}
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(5)

        # ── Título compacto ──────────────────────────────
        lbl = QLabel("Fase-8: Validação & Certificação")
        lbl.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-size: 11px; font-weight: bold; padding-bottom: 2px;")
        outer.addWidget(lbl)

        # ── Seleção Obra / Pav (compacto, sem GroupBox pesado) ──────────
        grp_sel = QGroupBox("Obra & Tipo")
        sel_lay = QVBoxLayout(grp_sel)
        sel_lay.setContentsMargins(5, 4, 5, 4)
        sel_lay.setSpacing(3)

        row_obra = QHBoxLayout()
        row_obra.addWidget(QLabel("Obra:"))
        self.cmb_obra = QComboBox()
        self.cmb_obra.setMinimumHeight(24)
        self.cmb_obra.setMaximumHeight(24)
        self.cmb_obra.currentTextChanged.connect(self._on_obra_changed)
        row_obra.addWidget(self.cmb_obra, 1)
        sel_lay.addLayout(row_obra)

        row_pav = QHBoxLayout()
        row_pav.addWidget(QLabel("Pav:"))
        self.cmb_pav = QComboBox()
        self.cmb_pav.setMinimumHeight(24)
        self.cmb_pav.setMaximumHeight(24)
        row_pav.addWidget(self.cmb_pav, 1)
        sel_lay.addLayout(row_pav)

        # _chk_tipos mantido para lógica interna (btn_validate oculto na UI)
        self._chk_tipos = {}
        for t in TIPOS:
            cb = QCheckBox(t)
            cb.setChecked(True)
            self._chk_tipos[t] = cb

        self.chk_sem_api = QCheckBox("Só estrutural (sem API)")
        self.chk_sem_api.setChecked(True)

        outer.addWidget(grp_sel)

        # ── Botão Validar (oculto — acionado via pipeline externo) ──────
        self.btn_validate = QPushButton("▶ Validar")
        self.btn_validate.clicked.connect(self._on_validate_clicked)
        self.btn_validate.setVisible(False)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        outer.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM};")
        outer.addWidget(self.lbl_status)

        # ── Status de Processamento N1/N2/N3 ────
        grp_proc = QGroupBox("Status de Processamento")
        proc_lay = QVBoxLayout(grp_proc)
        proc_lay.setContentsMargins(6, 4, 6, 4)
        proc_lay.setSpacing(3)

        _PROC_LEVELS = [
            ("N1", "Estrutura Real",   "DXF Fase-1"),
            ("N2", "Fichas Fase-3",    "Interpretação"),
            ("N3", "Robot via Ficha SA", "Fase-4"),
        ]
        self._proc_status_labels: dict[str, QLabel] = {}
        for nid, ntitle, ndesc in _PROC_LEVELS:
            row = QHBoxLayout()
            row.setSpacing(4)

            dot = QLabel("●")
            dot.setFixedWidth(12)
            dot.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 10px;")
            dot.setObjectName(f"proc_dot_{nid}")
            row.addWidget(dot)

            lbl_name = QLabel(f"<b>{nid}</b> {ntitle}")
            lbl_name.setStyleSheet(f"font-size: 9px; color: {Colors.TEXT_SECONDARY};")
            lbl_name.setFixedWidth(105)
            row.addWidget(lbl_name)

            lbl_val = QLabel("—")
            lbl_val.setStyleSheet(f"font-size: 9px; color: {Colors.TEXT_DIM};")
            lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(lbl_val, 1)

            self._proc_status_labels[nid] = lbl_val
            proc_lay.addLayout(row)

            # store dot ref for color update
            setattr(self, f"_proc_dot_{nid}", dot)

        outer.addWidget(grp_proc)

        # ── Scores ──────────────────────────────
        grp_scores = QGroupBox("Scores")
        sc_lay = QVBoxLayout(grp_scores)
        sc_lay.setSpacing(4)

        score_grid = QHBoxLayout()
        score_grid.setSpacing(3)
        self._score_labels = {}
        for t in TIPOS:
            col = QVBoxLayout()
            col.setSpacing(1)
            lbl_t = QLabel(t, alignment=Qt.AlignCenter)
            lbl_t.setStyleSheet(f"font-size: 9px; color: {Colors.TEXT_SECONDARY};")
            col.addWidget(lbl_t)
            sl = ScoreLabel("—")
            sl.setAlignment(Qt.AlignCenter)
            sl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 13px; font-weight: bold;")
            self._score_labels[t] = sl
            col.addWidget(sl)
            score_grid.addLayout(col)
        sc_lay.addLayout(score_grid)

        row_avg = QHBoxLayout()
        row_avg.addWidget(QLabel("Média:", styleSheet=f"font-size:10px;"))
        self.lbl_avg = ScoreLabel("—")
        self.lbl_avg.setStyleSheet(f"font-size:12px; font-weight:bold; color:{Colors.TEXT_DIM};")
        row_avg.addWidget(self.lbl_avg)
        row_avg.addStretch()
        sc_lay.addLayout(row_avg)

        outer.addWidget(grp_scores)

        # ── Certificar ──────────────────────────
        self.btn_certify = QPushButton("✅ Certificar Obra")
        self.btn_certify.setObjectName("certify")
        self.btn_certify.setEnabled(False)
        self.btn_certify.clicked.connect(self._on_certify)
        outer.addWidget(self.btn_certify)

        self.lbl_cert_status = QLabel("")
        outer.addWidget(self.lbl_cert_status)

        # Histórico/Tendência/Comparação — criados mas ocultos (lógica preservada)
        self.tbl_history = QTableWidget(0, 5)
        self.tbl_history.setHorizontalHeaderLabels(["Obra", "PL", "LV", "FV", "LJ"])
        self.tbl_history.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 5):
            self.tbl_history.setColumnWidth(col, 45)
        self._sparkline = ScoreSparkline()
        self._lbl_trend_info = QLabel("")
        self._comp_tab_widget = self._build_comparacao_tab()
        self._tabs_hist = None
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        self._process = None
        self._current_obra = None
        self._current_pav  = None
        self._last_result  = None
        self._db           = None     # CAD-10.5: injetado via set_database
        self._project_id   = ''

        # Preencher obras
        self._populate_obras()

    # ─────────────────────────────────────────────
    # Population
    # ─────────────────────────────────────────────

    def _populate_obras(self):
        """Lista obras disponíveis ordenando TREINO primeiro, depois outras."""
        self.cmb_obra.blockSignals(True)
        self.cmb_obra.clear()
        if not DADOS_OBRAS_ROOT.exists():
            self.cmb_obra.blockSignals(False)
            return

        all_obras = [d.name for d in DADOS_OBRAS_ROOT.iterdir()
                     if d.is_dir() and d.name.startswith("Obra_")]
        # TREINO primeiro (ordenadas numericamente), depois outras alfabeticamente
        treino = sorted([o for o in all_obras if "TREINO" in o],
                        key=lambda x: int(x.split("_")[-1]) if x.split("_")[-1].isdigit() else 999)
        outros = sorted([o for o in all_obras if "TREINO" not in o])
        obras = treino + outros

        for o in obras:
            self.cmb_obra.addItem(o)
        self.cmb_obra.blockSignals(False)

        # Seleciona primeira obra com validação existente (score real)
        primeira_com_score = next(
            (o for o in treino
             if (VALIDACAO_DIR / f"consolidado_{o}.json").exists()),
            obras[0] if obras else None
        )
        if primeira_com_score:
            idx = self.cmb_obra.findText(primeira_com_score)
            if idx >= 0:
                self.cmb_obra.setCurrentIndex(idx)
            self._on_obra_changed(primeira_com_score)

    @staticmethod
    def _pav_display_label(pav_key: str) -> str:
        """Formata nome do pavimento classificado para exibição no combo.
        Ex: '13PAV' → '[13PAV] 13º Pavimento' | 'TIPO - 3 AO 12PAV' → '[TIPO] Pavimento Tipo 3-12'"""
        import re as _re
        k = pav_key.strip()
        # Detecta número(s) no início (ex: "13PAV", "14PAV", "1PAV", "2PAV")
        m = _re.match(r'^(\d+)\s*PAV', k, _re.I)
        if m:
            n = m.group(1)
            return f"[{k}]  {n}º Pavimento"
        # TIPO
        if _re.search(r'TIPO', k, _re.I):
            return f"[TIPO]  Pavimento Tipo"
        # Terreo
        if _re.search(r'TER|TÉRREO|TERREO', k, _re.I):
            return f"[TER]  Térreo"
        # Cobertura / Deck
        if _re.search(r'COB|DECK|BARR', k, _re.I):
            return f"[COB]  Cobertura / Deck"
        # Ático
        if _re.search(r'ATC|ÁTIC|ATIC', k, _re.I):
            return f"[ATC]  Ático"
        # Fundação
        if _re.search(r'FUN|FUND', k, _re.I):
            return f"[FUN]  Fundação"
        # Subsolo
        if _re.search(r'SUB', k, _re.I):
            return f"[SUB]  Subsolo"
        # fallback: exibir como está
        return f"[—]  {k}"

    def _on_obra_changed(self, obra_name: str):
        """Atualiza combo de pavimentos ao trocar de obra.
        Bloqueia signals do cmb_pav durante populate para evitar múltiplos
        disparos de _on_obra_pav_changed → _load_n1_dxf_for_pav → QThread crash."""
        self.cmb_pav.blockSignals(True)
        self.cmb_pav.clear()
        if not obra_name:
            self.cmb_pav.blockSignals(False)
            return
        disc_path = DADOS_OBRAS_ROOT / "dxf_discovery.json"
        if disc_path.exists():
            disc = json.loads(disc_path.read_text(encoding='utf-8', errors='replace'))
            pavs = sorted(disc.get(obra_name, {}).keys())
            for p in pavs:
                label = self._pav_display_label(p)
                self.cmb_pav.addItem(label, p)   # userData = chave real para lookup
        # Fallback: Fase-1
        if self.cmb_pav.count() == 0:
            fase1 = DADOS_OBRAS_ROOT / obra_name / "Fase-1_Ingestao"
            if fase1.exists():
                self.cmb_pav.addItem("1PV")
        self.cmb_pav.blockSignals(False)

        # Carregar scores existentes
        self._load_scores_for_obra(obra_name)
        # Atualizar status N1/N2/N3
        self._refresh_processing_status(obra_name)

    def _refresh_processing_status(self, obra_name: str):
        """Verifica existência de dados em cada nível e atualiza o painel de status."""
        if not obra_name:
            return
        obra_dir = DADOS_OBRAS_ROOT / obra_name

        def _set(nid: str, ok: bool, partial: bool, text: str):
            lbl = self._proc_status_labels.get(nid)
            dot = getattr(self, f"_proc_dot_{nid}", None)
            if lbl:
                lbl.setText(text)
            if dot:
                if ok:
                    color = "#4acf7a"   # green
                elif partial:
                    color = "#cfb84a"   # amber
                else:
                    color = "#555566"   # dim gray
                dot.setStyleSheet(f"color: {color}; font-size: 10px;")

        # N1 — DXFs limpos de Fase-2_Triagem (preferencial) ou brutos de Fase-1
        clean_dir = obra_dir / "Fase-2_Triagem" / "Estruturais_Pavimentos_Limpos"
        bruto_dir = obra_dir / "Fase-1_Ingestao" / "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
        n1_clean = len(list(clean_dir.glob("*.dxf"))) if clean_dir.exists() else 0
        n1_bruto = len(list(bruto_dir.glob("*.dxf"))) if bruto_dir.exists() else 0
        n1_count = n1_clean or n1_bruto
        n1_label = f"{n1_clean} limpos" if n1_clean > 0 else (f"{n1_bruto} brutos" if n1_bruto > 0 else "sem dados")
        _set("N1",
             ok=(n1_clean > 0),
             partial=(n1_clean == 0 and n1_bruto > 0),
             text=n1_label)

        # N2 — Fichas from Fase-3_Interpretacao_Extracao
        fase3_dir = obra_dir / "Fase-3_Interpretacao_Extracao"
        n2_count = 0
        if fase3_dir.exists():
            for sub in ("Pilares", "Vigas", "Lajes"):
                sub_dir = fase3_dir / sub
                if sub_dir.exists():
                    n2_count += len(list(sub_dir.glob("*.json")))
        _set("N2",
             ok=(n2_count > 0),
             partial=False,
             text=f"{n2_count} fichas" if n2_count > 0 else "sem dados")

        # N3 — JSON_Pilares/Vigas from Fase-4_Sincronizacao
        fase4_dir = obra_dir / "Fase-4_Sincronizacao"
        n3_count = 0
        if fase4_dir.exists():
            for sub in ("JSON_Pilares", "JSON_Vigas_Fundo", "JSON_Vigas_Laterais", "JSON_Lajes"):
                sub_dir = fase4_dir / sub
                if sub_dir.exists():
                    n3_count += len(list(sub_dir.glob("*.json")))
        _set("N3",
             ok=(n3_count > 0),
             partial=False,
             text=f"{n3_count} itens" if n3_count > 0 else "sem dados")

    def _load_scores_for_obra(self, obra_name: str):
        """Carrega scores do JSON consolidado se existir."""
        json_path = VALIDACAO_DIR / f"consolidado_{obra_name}.json"
        if not json_path.exists():
            for lbl in self._score_labels.values():
                lbl.set_score(None)
            self.lbl_avg.set_score(None)
            self.btn_certify.setEnabled(False)
            return

        try:
            data = json.loads(json_path.read_text(encoding='utf-8', errors='replace'))
            # data = { pav: { obra, pavimento, resultados: { PL: {score_final: X}, ... } } }
            # Pegar primeiro pav com resultados
            scores = {}
            for pav_key, pav_data in data.items():
                resultados = pav_data.get("resultados", {})
                for tipo, res in resultados.items():
                    if tipo in TIPOS:
                        scores[tipo] = res.get("score_final")
                break  # first pav only for now

            for tipo in TIPOS:
                self._score_labels[tipo].set_score(scores.get(tipo))

            valid = [v for v in scores.values() if v is not None]
            avg = sum(valid) / len(valid) if valid else None
            self.lbl_avg.set_score(avg)
            self.btn_certify.setEnabled(avg is not None)
            self._last_result = data
        except Exception as e:
            self._log(f"Erro ao carregar scores: {e}")

    @property
    def current_pav_key(self) -> str:
        """Retorna a chave real do pavimento (userData se disponível, senão currentText)."""
        data = self.cmb_pav.currentData()
        return data if data else self.cmb_pav.currentText()

    # ─────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────

    def _on_validate_clicked(self):
        obra = self.cmb_obra.currentText()
        pav  = self.current_pav_key
        tipos = [t for t, cb in self._chk_tipos.items() if cb.isChecked()]

        if not obra or not tipos:
            QMessageBox.warning(self, "Fase-8", "Selecione uma obra e pelo menos um tipo.")
            return

        script = SCRIPTS_DIR / "validar_visual_dxf.py"
        if not script.exists():
            QMessageBox.critical(self, "Fase-8", f"Script não encontrado:\n{script}")
            return

        self.btn_validate.setEnabled(False)
        self.btn_certify.setEnabled(False)
        self.progress.setVisible(True)
        self._lbl_status("Iniciando validação...")
        self.log_box.clear()

        self._current_obra = obra
        self._current_pav  = pav

        args = [str(script), "--obra", obra]
        if pav:
            args += ["--pav", pav]
        for t in tipos:
            args += ["--tipo", t]
        if self.chk_sem_api.isChecked():
            args.append("--sem-api")

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_proc_output)
        self._process.finished.connect(self._on_proc_finished)
        self._process.start(sys.executable, args)

        self._log(f"Validando {obra}/{pav} tipos={tipos}")

    def _lbl_status(self, text: str):
        self.lbl_status.setText(text[:60])

    def _on_proc_output(self):
        raw = bytes(self._process.readAllStandardOutput())
        text = raw.decode('utf-8', errors='replace')
        for line in text.splitlines():
            if line.strip():
                self._log(line)
                self._lbl_status(line[:60])

    def _on_proc_finished(self, code, _):
        self.progress.setVisible(False)
        self.btn_validate.setEnabled(True)

        if code != 0:
            self._lbl_status(f"❌ Erro (código {code})")
            return

        self._lbl_status("✓ Validação concluída")
        self._load_scores_for_obra(self._current_obra or "")
        self.load_history()
        self._save_learning_event()
        # S4 — log estruturado de scores por tipo
        scores_log = {}
        if self._last_result or True:
            json_path = VALIDACAO_DIR / f"consolidado_{self._current_obra}.json"
            if json_path.exists():
                try:
                    _data = json.loads(json_path.read_text(encoding='utf-8', errors='replace'))
                    for _pav, _pd in _data.items():
                        for _t, _r in _pd.get("resultados", {}).items():
                            _s = _r.get("score_final")
                            if _s is not None:
                                scores_log[_t] = f"{_s:.1f}%"
                        break
                except Exception:
                    pass
        if scores_log:
            parts = " ".join(f"{t}:{v}" for t, v in scores_log.items())
            print(f"[VALIDAR] {self._current_obra}/{self._current_pav} — {parts}", flush=True)

    # ─────────────────────────────────────────────
    # Certification
    # ─────────────────────────────────────────────

    def _on_certify(self):
        obra = self.cmb_obra.currentText()
        pav  = self.current_pav_key
        if not self._last_result:
            QMessageBox.warning(self, "Certificar", "Valide a obra primeiro.")
            return

        scores = {}
        for pav_key, pav_data in self._last_result.items():
            for tipo, res in pav_data.get("resultados", {}).items():
                if tipo in TIPOS:
                    scores[tipo] = res.get("score_final")
            break

        valid = [v for v in scores.values() if v is not None]
        avg   = sum(valid) / len(valid) if valid else 0.0

        if avg >= 75:
            status = "APROVADO"
        elif avg >= 60:
            status = "CONDICIONAL"
        else:
            status = "REPROVADO"

        cert = {
            "obra": obra,
            "pavimento": pav,
            "tipos_validados": list(scores.keys()),
            "scores": scores,
            "media_geral": round(avg, 1),
            "status": status,
            "data_cert": datetime.now().isoformat(),
            "versao": "v4.0",
        }

        out_dir = DADOS_OBRAS_ROOT / obra / "Fase-8_Revisao_Entrega"
        out_dir.mkdir(parents=True, exist_ok=True)
        cert_path = out_dir / "CERTIFICADO.json"
        cert_path.write_text(json.dumps(cert, indent=2, ensure_ascii=False), encoding='utf-8')

        color = Colors.ACCENT_SUCCESS if status == "APROVADO" else Colors.ACCENT_WARNING if status == "CONDICIONAL" else Colors.ACCENT_DANGER
        self.lbl_cert_status.setText(f"<b style='color:{color}'>{status}</b> — Média {avg:.1f}%")
        self._log(f"Certificado gravado: {cert_path}")
        QMessageBox.information(
            self, "Certificação",
            f"Obra: {obra}\nMédia: {avg:.1f}%\nStatus: {status}\n\nSalvo em: {cert_path}"
        )

    # ─────────────────────────────────────────────
    # History Table
    # ─────────────────────────────────────────────

    def load_history(self):
        """Popula tabela de histórico com todos os consolidados existentes."""
        self.tbl_history.setRowCount(0)
        if not VALIDACAO_DIR.exists():
            return

        for json_path in sorted(VALIDACAO_DIR.glob("consolidado_Obra_TREINO_*.json")):
            try:
                data = json.loads(json_path.read_text(encoding='utf-8', errors='replace'))
                obra_name = json_path.stem.replace("consolidado_", "")
                scores = {}
                for pav_data in data.values():
                    for tipo, res in pav_data.get("resultados", {}).items():
                        if tipo in TIPOS:
                            scores[tipo] = res.get("score_final")
                    break

                row = self.tbl_history.rowCount()
                self.tbl_history.insertRow(row)

                name_item = QTableWidgetItem(obra_name.replace("Obra_", ""))
                self.tbl_history.setItem(row, 0, name_item)

                for col_idx, tipo in enumerate(TIPOS, 1):
                    sc = scores.get(tipo)
                    item = QTableWidgetItem(_score_badge(sc))
                    if sc is not None:
                        cat = _score_category(sc)
                        item.setForeground(QColor(SCORE_COLORS[cat][0]))
                    self.tbl_history.setItem(row, col_idx, item)

            except Exception:
                continue

    # ─────────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────────

    # ─────────────────────────────────────────────
    # Trend Dashboard (CAD-UI-2.2)
    # ─────────────────────────────────────────────

    def _load_trend(self):
        """Carrega eventos de treinamento da obra selecionada e atualiza sparkline."""
        obra = self.cmb_obra.currentText()
        events_path = VALIDACAO_DIR / "training_events.json"
        if not events_path.exists():
            self._lbl_trend_info.setText("Nenhum evento ainda — valide obras primeiro.")
            return
        try:
            all_events = json.loads(events_path.read_text(encoding='utf-8', errors='replace'))
            obra_events = [e for e in all_events if e.get('obra') == obra]
            # Últimos 20 eventos
            obra_events = obra_events[-20:]
            self._sparkline.set_events(obra_events)
            n = len(obra_events)
            if n == 0:
                self._lbl_trend_info.setText(f"Nenhum evento para {obra}.")
            else:
                medias = [e.get('media') for e in obra_events if e.get('media') is not None]
                trend = ""
                if len(medias) >= 2:
                    delta = medias[-1] - medias[0]
                    trend = f" (Δ {delta:+.1f}pp)"
                self._lbl_trend_info.setText(f"{n} validações para {obra}{trend}")
        except Exception as e:
            self._lbl_trend_info.setText(f"Erro: {e}")

    # ─────────────────────────────────────────────
    # Learning Events (CAD-UI-2.4)
    # ─────────────────────────────────────────────

    def _save_learning_event(self):
        """Salva evento de aprendizagem em training_events.json."""
        if not self._last_result:
            return
        events_path = VALIDACAO_DIR / "training_events.json"
        try:
            events = []
            if events_path.exists():
                events = json.loads(events_path.read_text(encoding='utf-8', errors='replace'))

            scores = {}
            for pav_data in self._last_result.values():
                for tipo, res in pav_data.get("resultados", {}).items():
                    if tipo in TIPOS:
                        scores[tipo] = res.get("score_final")
                break

            valid = [v for v in scores.values() if v is not None]
            avg   = round(sum(valid) / len(valid), 1) if valid else None

            event = {
                "obra":       self._current_obra,
                "pavimento":  self._current_pav,
                "scores":     scores,
                "media":      avg,
                "timestamp":  datetime.now().isoformat(),
                "tipos":      list(scores.keys()),
            }
            events.append(event)
            # Manter apenas os últimos 500 eventos
            events = events[-500:]
            events_path.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding='utf-8')
            self._log(f"📚 Evento de aprendizagem salvo (média={avg}%)")
        except Exception as e:
            self._log(f"Aviso: não foi possível salvar evento de aprendizagem: {e}")

    def _log(self, text: str):
        self.log_box.append(text)
        sb = self.log_box.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_database(self, db, project_id: str = ''):
        """Injeta DB e project_id para as funções de comparação (CAD-10.5)."""
        self._db         = db
        self._project_id = project_id

    # ─────────────────────────────────────────────
    # CAD-10.5: Tab Comparação Tri-Fonte
    # ─────────────────────────────────────────────

    def _build_comparacao_tab(self) -> QWidget:
        """Constrói aba de comparação tri-fonte GT/F4/DB."""
        tab = QWidget()
        vlay = QVBoxLayout(tab)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        if not _COMP_AVAILABLE:
            vlay.addWidget(QLabel("⚠ Módulo de comparação não disponível."))
            return tab

        # ── Seletores tipo + item ─────────────────────────────────────────
        sel_row = QHBoxLayout()
        sel_row.setSpacing(4)

        self._cmb_comp_tipo = QComboBox()
        self._cmb_comp_tipo.addItems(["Pilares", "Vigas Laterais", "Vigas Fundo", "Lajes"])
        self._cmb_comp_tipo.setFixedHeight(24)
        self._cmb_comp_tipo.currentTextChanged.connect(self._on_comp_tipo_changed)
        sel_row.addWidget(QLabel("Tipo:"))
        sel_row.addWidget(self._cmb_comp_tipo, 1)
        vlay.addLayout(sel_row)

        item_row = QHBoxLayout()
        item_row.setSpacing(4)
        self._cmb_comp_item = QComboBox()
        self._cmb_comp_item.setFixedHeight(24)
        self._cmb_comp_item.currentTextChanged.connect(self._on_comp_item_changed)
        item_row.addWidget(QLabel("Item:"))
        item_row.addWidget(self._cmb_comp_item, 1)
        vlay.addLayout(item_row)

        # ── Score bar ────────────────────────────────────────────────────
        self._comp_score_label = QLabel("—")
        self._comp_score_label.setStyleSheet(
            f"color: {Colors.ACCENT_MINT}; font-size: 10px; padding: 2px 4px;"
            "background: rgba(0,0,0,76); border-radius: 3px;"
        )
        vlay.addWidget(self._comp_score_label)

        # ── Tabela tri-fonte ──────────────────────────────────────────────
        self._comp_table = QTableWidget(0, 5)
        self._comp_table.setHorizontalHeaderLabels(
            ["Campo", "GT", "Fase-4", "DB", "Status"]
        )
        self._comp_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._comp_table.verticalHeader().setVisible(False)
        self._comp_table.setAlternatingRowColors(False)
        self._comp_table.setStyleSheet(f"""
            QTableWidget {{
                background: {Colors.BG_CARD}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; font-size: 10px;
                gridline-color: rgba(255,255,255,18);
            }}
            QHeaderView::section {{
                background: rgba(20,40,40,1); color: {Colors.TEXT_BRIGHT};
                border: 1px solid {Colors.BORDER_DEFAULT}; padding: 2px;
                font-size: 9px; font-weight: bold;
            }}
        """)
        hdr = self._comp_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, w in enumerate([0, 60, 70, 70, 50], start=0):
            if col > 0:
                self._comp_table.setColumnWidth(col, w)
        vlay.addWidget(self._comp_table, 1)

        # ── Score de todos os itens ───────────────────────────────────────
        self._score_summary_table = QTableWidget(0, 3)
        self._score_summary_table.setHorizontalHeaderLabels(
            ["Item", "Completude", "Match"]
        )
        self._score_summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._score_summary_table.verticalHeader().setVisible(False)
        self._score_summary_table.setMaximumHeight(120)
        self._score_summary_table.setStyleSheet(self._comp_table.styleSheet())
        ss_hdr = self._score_summary_table.horizontalHeader()
        ss_hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        self._score_summary_table.setColumnWidth(1, 70)
        self._score_summary_table.setColumnWidth(2, 60)
        self._score_summary_table.itemClicked.connect(self._on_summary_item_clicked)
        vlay.addWidget(self._score_summary_table)

        # ── Botões ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        btn_load_all = QPushButton("📊 Calcular Todos")
        btn_load_all.setFixedHeight(24)
        btn_load_all.setStyleSheet(
            f"background: rgba(0,60,80,1); color: {Colors.ACCENT_TEAL};"
            "border: 1px solid #006666; border-radius: 3px; font-size: 10px;"  # hardcoded-ok
        )
        btn_load_all.clicked.connect(self._on_comp_load_all_scores)

        self._btn_export_audit = QPushButton("⬇ Exportar Auditoria")
        self._btn_export_audit.setFixedHeight(24)
        self._btn_export_audit.setStyleSheet(
            f"background: rgba(60,40,0,1); color: {Colors.ACCENT_WARNING};"
            "border: 1px solid #aa6600; border-radius: 3px; font-size: 10px;"  # hardcoded-ok
        )
        self._btn_export_audit.clicked.connect(self._on_export_audit)

        btn_row.addWidget(btn_load_all)
        btn_row.addWidget(self._btn_export_audit)
        vlay.addLayout(btn_row)

        # Estado interno
        self._comp_items_cache: dict = {}  # tipo → list[item_data]
        return tab

    def _comp_obra_path(self) -> str | None:
        obra_name = self.cmb_obra.currentText()
        if not obra_name:
            return None
        return str(DADOS_OBRAS_ROOT / obra_name)

    def _on_comp_tipo_changed(self, tipo_label: str):
        """Recarrega lista de items ao mudar tipo."""
        self._cmb_comp_item.blockSignals(True)
        self._cmb_comp_item.clear()

        if not self._db or not self._project_id:
            self._cmb_comp_item.blockSignals(False)
            return

        items = self._load_comp_items(tipo_label)
        for item in items:
            self._cmb_comp_item.addItem(item.get('id_item', '?'))

        self._cmb_comp_item.blockSignals(False)
        if self._cmb_comp_item.count() > 0:
            self._on_comp_item_changed(self._cmb_comp_item.currentText())

    def _load_comp_items(self, tipo_label: str) -> list:
        """Carrega itens do DB pelo tipo selecionado."""
        if not self._db or not self._project_id:
            return []
        try:
            tl = tipo_label.lower()
            if 'pilar' in tl:
                items = self._db.load_pillars(self._project_id) or []
            elif 'viga fundo' in tl or 'fundo' in tl:
                items = [b for b in (self._db.load_beams(self._project_id) or [])
                         if 'fundo' in str(b.get('id_item', '')).lower()]
            elif 'viga' in tl:
                items = [b for b in (self._db.load_beams(self._project_id) or [])
                         if 'fundo' not in str(b.get('id_item', '')).lower()]
            elif 'laje' in tl:
                items = self._db.load_slabs(self._project_id) or []
            else:
                items = []
            tipo_key = tipo_label
            self._comp_items_cache[tipo_key] = items
            return items
        except Exception as e:
            self._log(f"[Comparação] Erro ao carregar itens: {e}")
            return []

    def _get_current_comp_item_data(self) -> dict | None:
        tipo_label = self._cmb_comp_tipo.currentText()
        item_id    = self._cmb_comp_item.currentText()
        items      = self._comp_items_cache.get(tipo_label, [])
        return next((i for i in items if i.get('id_item') == item_id), None)

    def _on_comp_item_changed(self, item_id: str):
        """Renderiza tabela tri-fonte para o item selecionado."""
        if not item_id:
            return
        item_data = self._get_current_comp_item_data()
        if item_data is None:
            return
        self._render_comp_table(item_data)

    def _render_comp_table(self, item_data: dict):
        """Preenche _comp_table com os dados tri-fonte do item."""
        obra_path = self._comp_obra_path()
        if not obra_path:
            return

        svc = ComparisonService(item_data, obra_path)
        if not svc.has_fase4:
            self._comp_score_label.setText(
                f"⚠ Fase-4 não disponível para {item_data.get('id_item','?')}"
            )
            self._comp_table.setRowCount(0)
            return

        rows = svc.build_rows()
        sc   = svc.score()

        self._comp_score_label.setText(
            f"{item_data.get('id_item','?')} — "
            f"Completude: {sc['completude_pct']}% | Match F4-DB: {sc['match_pct']}%"
        )

        _STATUS_COLOR = {
            FieldStatus.IGUAL:      ('#1a3320', '#4caf50'),  # hardcoded-ok
            FieldStatus.DIFERENTE:  ('#332900', '#ffc107'),  # hardcoded-ok
            FieldStatus.AUSENTE_GT: ('#1a1a1a', '#9e9e9e'),  # hardcoded-ok
            FieldStatus.AUSENTE_F4: ('#1a1a1a', '#9e9e9e'),  # hardcoded-ok
            FieldStatus.CONFLITO:   ('#330d00', '#f44336'),  # hardcoded-ok
        }
        _STATUS_ICON = {
            FieldStatus.IGUAL: '✓', FieldStatus.DIFERENTE: '≠',
            FieldStatus.AUSENTE_GT: '—', FieldStatus.AUSENTE_F4: '∅',
            FieldStatus.CONFLITO: '!',
        }

        self._comp_table.setRowCount(0)
        for row_idx, row in enumerate(rows):
            self._comp_table.insertRow(row_idx)
            self._comp_table.setRowHeight(row_idx, 22)
            bg, fg = _STATUS_COLOR.get(row.status, ('#1a1a1a', '#9e9e9e'))  # hardcoded-ok

            def _cell(text, tfg=Colors.TEXT_PRIMARY, tbg=None):
                it = QTableWidgetItem(str(text) if text else '—')
                from PySide6.QtGui import QColor, QBrush
                it.setForeground(QBrush(QColor(tfg)))
                if tbg:
                    it.setBackground(QBrush(QColor(tbg)))
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                return it

            self._comp_table.setItem(row_idx, 0, _cell(row.label))
            gt_str = str(int(row.gt_value)) if isinstance(row.gt_value, float) and row.gt_value == int(row.gt_value) else (str(row.gt_value) if row.gt_value is not None else '')
            f4_str = str(int(row.f4_value)) if isinstance(row.f4_value, float) and row.f4_value == int(row.f4_value) else (str(row.f4_value) if row.f4_value is not None else '')
            db_str = str(int(row.db_value)) if isinstance(row.db_value, float) and row.db_value == int(row.db_value) else (str(row.db_value) if row.db_value is not None else '')
            self._comp_table.setItem(row_idx, 1, _cell(gt_str, tfg=Colors.TEXT_SECONDARY))
            self._comp_table.setItem(row_idx, 2, _cell(f4_str, tfg=fg))
            self._comp_table.setItem(row_idx, 3, _cell(db_str, tfg=Colors.TEXT_BRIGHT if db_str else Colors.TEXT_SECONDARY))
            st_cell = _cell(f"{_STATUS_ICON.get(row.status,'?')} {row.status.value}", tfg=fg, tbg=bg)
            st_cell.setTextAlignment(Qt.AlignCenter)
            self._comp_table.setItem(row_idx, 4, st_cell)

    def _on_comp_load_all_scores(self):
        """Calcula score de todos os itens do tipo selecionado e preenche tabela resumo."""
        tipo_label = self._cmb_comp_tipo.currentText()
        obra_path  = self._comp_obra_path()
        if not obra_path:
            return

        items = self._load_comp_items(tipo_label)
        if not items:
            self._log("[Comparação] Sem itens para calcular.")
            return

        self._score_summary_table.setRowCount(0)
        for i, item_data in enumerate(items):
            svc = ComparisonService(item_data, obra_path)
            sc  = svc.score() if svc.has_fase4 else None

            self._score_summary_table.insertRow(i)
            self._score_summary_table.setRowHeight(i, 20)

            def _cell(text, fg=Colors.TEXT_PRIMARY):
                it = QTableWidgetItem(str(text))
                from PySide6.QtGui import QColor, QBrush
                it.setForeground(QBrush(QColor(fg)))
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                return it

            id_item = item_data.get('id_item', '?')
            self._score_summary_table.setItem(i, 0, _cell(id_item))

            if sc:
                c_pct = sc['completude_pct']
                m_pct = sc['match_pct']
                c_fg = Colors.ACCENT_SUCCESS if c_pct >= 75 else (Colors.ACCENT_WARNING if c_pct >= 50 else Colors.ACCENT_DANGER)
                m_fg = Colors.ACCENT_SUCCESS if m_pct >= 75 else (Colors.ACCENT_WARNING if m_pct >= 50 else Colors.ACCENT_DANGER)
                self._score_summary_table.setItem(i, 1, _cell(f"{c_pct}%", fg=c_fg))
                self._score_summary_table.setItem(i, 2, _cell(f"{m_pct}%", fg=m_fg))
            else:
                self._score_summary_table.setItem(i, 1, _cell("—", fg=Colors.TEXT_DIM))
                self._score_summary_table.setItem(i, 2, _cell("—", fg=Colors.TEXT_DIM))

        self._log(f"[Comparação] {len(items)} {tipo_label} calculados.")

    def _on_summary_item_clicked(self, item):
        """Clique na tabela resumo → selecionar item no combo."""
        row = item.row()
        id_item = self._score_summary_table.item(row, 0)
        if not id_item:
            return
        idx = self._cmb_comp_item.findText(id_item.text())
        if idx >= 0:
            self._cmb_comp_item.setCurrentIndex(idx)

    def _on_export_audit(self):
        """Exporta relatório de auditoria JSON + Markdown."""
        obra_path = self._comp_obra_path()
        if not obra_path or not self._db or not self._project_id:
            QMessageBox.warning(self, "Exportar",
                                "Selecione uma obra e verifique se o DB está disponível.")
            return
        try:
            exporter = AuditExporter(obra_path, self._project_id, self._db)
            report   = exporter.build_report()
            json_path = exporter.save(report)
            QMessageBox.information(self, "Exportar",
                                    f"Auditoria exportada:\n{json_path}")
            self._log(f"[Auditoria] Exportado: {json_path}")
        except Exception as e:
            QMessageBox.critical(self, "Exportar", f"Erro: {e}")

    def set_obra(self, obra_name: str, pav: str = ""):
        """Seleciona obra e pav programaticamente (chamado do main.py)."""
        idx = self.cmb_obra.findText(obra_name)
        if idx >= 0:
            self.cmb_obra.setCurrentIndex(idx)
        if pav:
            pav_idx = self.cmb_pav.findText(pav)
            if pav_idx >= 0:
                self.cmb_pav.setCurrentIndex(pav_idx)


# ──────────────────────────────────────────────────────
# 3-Level Comparison: ZoomableImageLabel, LevelColumn, NavSidebar, TriLevelArea
# ──────────────────────────────────────────────────────

class ZoomableImageLabel(QWidget):
    """Widget de imagem PNG com zoom (scroll do mouse) e pan (drag)."""

    def __init__(self, bg: str = Colors.BG_DEEP, parent=None):
        super().__init__(parent)
        self._pixmap     = None
        self._scale      = 1.0
        self._offset     = QPointF(0.0, 0.0)
        self._drag_start  = None
        self._drag_origin = None
        self._status_text = "— sem imagem —"
        self._bg = bg

        self.setMinimumSize(200, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

    # ── Public API ──────────────────────────────────────────────────

    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._status_text = ""
        self._fit()
        self.update()

    def clear_image(self, msg: str = "— sem imagem —"):
        self._pixmap = None
        self._status_text = msg
        self.update()

    # ── Fit ─────────────────────────────────────────────────────────

    def _fit(self):
        src = self._pixmap
        if not src:
            return
        w, h   = self.width(), self.height()
        pw, ph = src.width(), src.height()
        if w <= 0 or h <= 0 or pw <= 0 or ph <= 0:
            return
        self._scale  = min(w / pw, h / ph)
        self._offset = QPointF(
            (w - pw * self._scale) / 2.0,
            (h - ph * self._scale) / 2.0,
        )

    # ── Paint ────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(self._bg))

        if not self._pixmap:
            p.setPen(QColor(Colors.TEXT_DIM))
            p.setFont(QFont("Arial", 11))
            p.drawText(self.rect(), Qt.AlignCenter, self._status_text)
            p.end()
            return

        t = QTransform()
        t.translate(self._offset.x(), self._offset.y())
        t.scale(self._scale, self._scale)
        p.setTransform(t)
        p.drawPixmap(0, 0, self._pixmap)
        p.resetTransform()

        p.setFont(QFont("Arial", 9))
        p.setPen(QColor(Colors.TEXT_DIM))
        p.drawText(self.rect().adjusted(0, 0, -6, -4),
                   Qt.AlignRight | Qt.AlignBottom,
                   f"{self._scale*100:.0f}%")
        p.end()

    # ── Zoom ────────────────────────────────────────────────────────

    def wheelEvent(self, event):
        if not self._pixmap:
            return
        factor = 1.18 if event.angleDelta().y() > 0 else 1.0 / 1.18
        cur    = event.position()
        img_x  = (cur.x() - self._offset.x()) / self._scale
        img_y  = (cur.y() - self._offset.y()) / self._scale
        new_sc = max(0.05, min(self._scale * factor, 30.0))
        self._offset = QPointF(
            cur.x() - img_x * new_sc,
            cur.y() - img_y * new_sc,
        )
        self._scale = new_sc
        self.update()
        event.accept()

    # ── Pan ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._pixmap:
            self._drag_start  = event.position()
            self._drag_origin = QPointF(self._offset)
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_start is not None:
            self._offset = self._drag_origin + (event.position() - self._drag_start)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.CrossCursor)

    def mouseDoubleClickEvent(self, event):
        self._fit()
        self.update()

    def resizeEvent(self, event):
        self._fit()
        super().resizeEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Steps Widget — exibido entre o viewer e a ficha em cada coluna
# ─────────────────────────────────────────────────────────────────────────────

_STEP_ICONS = {
    'pending':  ('⏳', Colors.TEXT_SECONDARY),
    'running':  ('🔄', Colors.ACCENT_WARNING),
    'ok':       ('✅', Colors.ACCENT_SUCCESS_ALT),
    'error':    ('❌', Colors.ACCENT_DANGER),
}

_PIPELINE_STEPS = {
    'N1': [
        "Interpretar fichas (Fase 3)",
        "Recorte centralizado N1",
        "Ficha Comparison N1",
    ],
    'N2': [
        "Recorte centralizado N2",
        "Extração eng. reversa",
        "Ficha eng. reversa",
    ],
    'N3': [
        "Conversão ficha → Robot DXF",
        "Preenchimento ficha N3",
        "Gerar DXF + carregar N3",
    ],
    'N4': [
        "Ficha Eng. Reversa N2",
        "Conversão ficha → Robot",
        "Gerar DXF N4",
    ],
}


class PipelineStepsWidget(QFrame):
    """Mini-painel compacto com steps — usado inline no header do LevelColumn."""

    def __init__(self, nivel_id: str, accent: str, bg_color: str):
        super().__init__()
        self._nivel_id = nivel_id
        self._accent   = accent
        steps = _PIPELINE_STEPS.get(nivel_id, [])

        # Transparente — vai ficar dentro do header colorido
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(1)

        self._rows: list[tuple] = []   # (lbl_icon, lbl_text, lbl_msg)
        for step_label in steps:
            row = QHBoxLayout()
            row.setSpacing(3)
            row.setContentsMargins(0, 0, 0, 0)

            icon = QLabel("⏳")
            icon.setFixedWidth(14)
            icon.setStyleSheet("background: transparent; font-size: 9px;")

            txt = QLabel(step_label)
            txt.setStyleSheet(
                f"color: {Colors.TEXT_DIM}; font-size: 8px; background: transparent;"
            )

            msg = QLabel("")
            msg.setStyleSheet(
                f"color: {Colors.TEXT_DIM}; font-size: 7px; background: transparent;"
            )
            msg.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            row.addWidget(icon)
            row.addWidget(txt, 1)
            row.addWidget(msg)
            lay.addLayout(row)
            self._rows.append((icon, txt, msg))

    def reset(self):
        """Volta todos os steps para 'pending'."""
        for i in range(len(self._rows)):
            self.set_step(i, 'pending', '')

    def set_step(self, idx: int, status: str, message: str = ''):
        """Atualiza o status visual de um step.
        status: 'pending' | 'running' | 'ok' | 'error'
        """
        if idx < 0 or idx >= len(self._rows):
            return
        icon_lbl, txt_lbl, msg_lbl = self._rows[idx]
        sym, color = _STEP_ICONS.get(status, ('⏳', Colors.TEXT_SECONDARY))
        icon_lbl.setText(sym)
        txt_lbl.setStyleSheet(
            f"color: {color}; font-size: 9px; font-weight: bold; background: transparent;"
            if status in ('ok', 'error', 'running')
            else f"color: {Colors.TEXT_SECONDARY}; font-size: 9px; background: transparent;"
        )
        msg_lbl.setText(message[:30] if message else '')
        msg_lbl.setStyleSheet(
            f"color: {Colors.ACCENT_DANGER if status == 'error' else Colors.TEXT_DIM};"
            "font-size: 8px; background: transparent;"
        )


class LevelColumn(QFrame):
    """Coluna de nível (N1/N2/N3): badge + header, viewer, pipeline steps, ficha."""

    COL_W = 540   # largura fixa da coluna (pixels)

    def __init__(self, nivel_id: str, titulo: str, bg_color: str,
                 accent: str, descricao: str, mode: str = 'png'):
        super().__init__()
        self.nivel_id = nivel_id
        self._mode    = mode   # 'dxf' ou 'png'
        self.setFixedWidth(self.COL_W)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_SECONDARY};
                border-right: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(4)

        # ── Header compacto: [badge+título+desc] | [pipeline inline] ──
        hdr = QFrame()
        hdr.setFixedHeight(50)
        hdr.setStyleSheet(f"background: {bg_color}; border-radius: 4px;")
        hdr_main = QHBoxLayout(hdr)
        hdr_main.setContentsMargins(10, 5, 10, 5)
        hdr_main.setSpacing(8)

        # Esquerda: badge + título + desc em uma linha
        left_lay = QVBoxLayout()
        left_lay.setSpacing(1)
        left_lay.setContentsMargins(0, 0, 0, 0)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(6)
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge = QLabel(nivel_id)
        badge.setFixedWidth(34)
        badge.setFixedHeight(20)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background: {accent}; color: #000; font-weight: bold;"
            "font-size: 12px; padding: 1px 4px; border-radius: 3px;"
        )
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            f"color: {accent}; font-weight: bold; font-size: 12px; background: transparent;"
        )
        badge_row.addWidget(badge)
        badge_row.addWidget(lbl_titulo)
        badge_row.addStretch()
        left_lay.addLayout(badge_row)

        lbl_desc = QLabel(descricao.replace('\n', ' · '))
        lbl_desc.setStyleSheet(
            "color: rgba(255,255,255,110); font-size: 8px; background: transparent;"
        )
        left_lay.addWidget(lbl_desc)

        hdr_main.addLayout(left_lay, 2)

        # Separador vertical
        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.VLine)
        sep_line.setFixedWidth(1)
        sep_line.setStyleSheet(f"background: {accent}44; border: none;")
        hdr_main.addWidget(sep_line)

        # Direita: pipeline steps inline
        self.pipeline = PipelineStepsWidget(nivel_id, accent, bg_color)
        self.pipeline.setFixedWidth(210)
        hdr_main.addWidget(self.pipeline, 0)

        lay.addWidget(hdr)

        # ── Viewer (DXF vetorial ou PNG raster) — 1.7x maior em Y ────
        border_style = f"border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 2px;"
        if mode == 'dxf':
            self.img_widget: DXFVectorView | ZoomableImageLabel = DXFVectorView(bg=Colors.BG_DEEP)
        else:
            self.img_widget = ZoomableImageLabel(bg=Colors.BG_DEEP)
        self.img_widget.setMinimumHeight(440)
        self.img_widget.setStyleSheet(border_style)
        lay.addWidget(self.img_widget, 1)

        # ── Barra de progresso ───────────────────────────────────────
        self.prog = QProgressBar()
        self.prog.setRange(0, 0)
        self.prog.setFixedHeight(4)
        self.prog.setVisible(False)
        self.prog.setStyleSheet(
            f"QProgressBar {{ border: none; background: {Colors.BG_DEEP}; }}"
            f"QProgressBar::chunk {{ background: {accent}; }}"
        )
        lay.addWidget(self.prog)

        # ── Ficha ────────────────────────────────────────────────────
        lbl_ficha = QLabel(f"Ficha {nivel_id}")
        lbl_ficha.setStyleSheet(
            f"color: {accent}; font-size: 10px; font-weight: bold; padding-top: 2px;"
        )
        lay.addWidget(lbl_ficha)

        self.ficha_table = QTableWidget(0, 2)
        self.ficha_table.setHorizontalHeaderLabels(["Campo", "Valor"])
        self.ficha_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ficha_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ficha_table.verticalHeader().setVisible(False)
        self.ficha_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ficha_table.setAlternatingRowColors(True)
        self.ficha_table.setFixedHeight(240)
        self.ficha_table.setStyleSheet(f"""
            QTableWidget {{
                background: {Colors.BG_PANEL}; color: {Colors.TEXT_PRIMARY};
                font-size: 10px; border: 1px solid {Colors.BORDER_DEFAULT};
                gridline-color: {Colors.BORDER_SUBTLE};
            }}
            QTableWidget::item:alternate {{ background: {Colors.BG_CARD}; }}
            QHeaderView::section {{
                background: {bg_color}; color: {accent};
                border: none; padding: 3px; font-size: 10px; font-weight: bold;
            }}
        """)
        lay.addWidget(self.ficha_table)

    # ── Conteúdo ─────────────────────────────────────────────────────

    def load_content(self, path, bbox=None):
        """
        Carrega conteúdo de acordo com o mode da coluna.
        mode='dxf': chama load_dxf(path, bbox) no DXFVectorView.
        mode='png': carrega QPixmap no ZoomableImageLabel.
        """
        if self._mode == 'dxf':
            self.img_widget.load_dxf(path, bbox)
        else:
            if path and Path(path).exists():
                self.img_widget.set_pixmap(QPixmap(str(path)))
            else:
                self.img_widget.clear_image()

    def set_ficha(self, rows: list):
        """rows = [(label, value), ...] """
        self.ficha_table.setRowCount(0)
        for label, value in rows:
            r = self.ficha_table.rowCount()
            self.ficha_table.insertRow(r)
            self.ficha_table.setRowHeight(r, 20)
            lbl_item = QTableWidgetItem(str(label))
            val_item = QTableWidgetItem(str(value))
            lbl_item.setFlags(lbl_item.flags() & ~Qt.ItemIsEditable)
            val_item.setFlags(val_item.flags() & ~Qt.ItemIsEditable)
            if str(label) == "---":
                sep_color = QColor(Colors.BORDER_DEFAULT)
                lbl_item.setBackground(QBrush(sep_color))
                val_item.setBackground(QBrush(sep_color))
                lbl_item.setText("")
            self.ficha_table.setItem(r, 0, lbl_item)
            self.ficha_table.setItem(r, 1, val_item)

    def set_processing(self, active: bool):
        self.prog.setVisible(active)
        if active:
            self.img_widget.clear_image("Processando...")


class NavSidebar(QFrame):
    """Sidebar: mini-tabs PL/LV/FV/LJ + lista scrollável de itens + ações."""

    item_selected       = Signal(str, str)
    process_requested   = Signal(str, str)   # N3 (legado)
    gerar_n1_requested  = Signal(str, str)   # classe, item_id
    gerar_n2_requested  = Signal(str, str)
    gerar_n3_requested  = Signal(str, str)
    gerar_n4_requested  = Signal(str, str)
    analise_requested   = Signal()
    fase4_requested     = Signal()

    _CLASSES = [("PL", "Pilares"), ("LV", "L.Viga"), ("FV", "F.Viga"), ("LJ", "Lajes")]
    _CLS_COLORS = {
        "PL": "#7ab3e0", "LV": "#4caf50", "FV": "#ff9800", "LJ": "#e91e63"
    }
    _JSON_DIRS = {
        "PL": "Fase-4_Sincronizacao/JSON_Pilares",
        "LV": "Fase-4_Sincronizacao/JSON_Vigas_Laterais",
        "FV": "Fase-4_Sincronizacao/JSON_Vigas_Fundo",
        "LJ": "Fase-4_Sincronizacao/JSON_Lajes",
    }
    _PREVIEW_DIRS = {
        "PL": "Fase-6_Execucao_CAD", "LV": "Fase-6_Execucao_CAD",
        "FV": "Fase-6_Execucao_CAD", "LJ": "Fase-6_Execucao_CAD",
    }
    _PREVIEW_PFX  = {"PL": "PL_preview_", "LV": "LV_preview_",
                     "FV": "FV_preview_", "LJ": "LJ_preview_"}

    def __init__(self):
        super().__init__()
        self._current_obra_dir: "Path | None" = None
        self._current_classe = "LV"
        self._current_pav: str = ""       # pav key do discovery.json (ex: "13PAV")
        self._selected_classe = ""
        self._selected_item   = ""
        self._selected_recorte_path = ""  # recorte_path do item ER selecionado (Qt.UserRole+1)
        self._tab_btns: dict  = {}

        self.setStyleSheet(f"background: {Colors.BG_PANEL}; border-top: 1px solid {Colors.BORDER_DEFAULT};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(5, 5, 5, 5)
        lay.setSpacing(4)

        # ── Título ───────────────────────────────────────────────────
        title = QLabel("Classes / Itens")
        title.setStyleSheet(
            f"color:{Colors.ACCENT_PRIMARY}; font-weight:bold; font-size:11px; background:transparent;"
        )
        lay.addWidget(title)

        # ── Flow Switcher: Estrutural N1/N3  ←→  Eng. Reversa N2/N4 ──
        self._current_flow = "estrutural"   # "estrutural" | "reverso"
        flow_row = QHBoxLayout()
        flow_row.setSpacing(1)
        flow_row.setContentsMargins(0, 0, 0, 0)

        _FLOW_SS_ACTIVE = (
            f"QPushButton {{ background:#1b3a6b; color:#fff; border-radius:3px; "
            f"font-size:9px; font-weight:bold; border-bottom:2px solid {Colors.ACCENT_BLUE}; }}"
        )
        _FLOW_SS_INACTIVE = (
            f"QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_SECONDARY}; "
            f"border-radius:3px; font-size:9px; border:1px solid {Colors.BORDER_DEFAULT}; }} "
            f"QPushButton:hover {{ background:{Colors.BG_PANEL}; }}"
        )

        self._btn_flow_estru = QPushButton("Itens Estrutural N1/N3")
        self._btn_flow_estru.setFixedHeight(20)
        self._btn_flow_estru.setCheckable(True)
        self._btn_flow_estru.setChecked(True)
        self._btn_flow_estru.setStyleSheet(_FLOW_SS_ACTIVE)
        self._btn_flow_estru.clicked.connect(lambda: self._select_flow("estrutural"))

        self._btn_flow_rev = QPushButton("Itens Eng. Reversa N2/N4")
        self._btn_flow_rev.setFixedHeight(20)
        self._btn_flow_rev.setCheckable(True)
        self._btn_flow_rev.setChecked(False)
        self._btn_flow_rev.setStyleSheet(_FLOW_SS_INACTIVE)
        self._btn_flow_rev.clicked.connect(lambda: self._select_flow("reverso"))

        self._flow_ss_active   = _FLOW_SS_ACTIVE
        self._flow_ss_inactive = _FLOW_SS_INACTIVE

        flow_row.addWidget(self._btn_flow_estru)
        flow_row.addWidget(self._btn_flow_rev)
        lay.addLayout(flow_row)

        # ── Mini-tabs PL / LV / FV / LJ ──────────────────────────────
        tab_row = QHBoxLayout()
        tab_row.setSpacing(2)
        tab_row.setContentsMargins(0, 0, 0, 0)
        for cls, label in self._CLASSES:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setCheckable(True)
            btn.setProperty("ce_cls", cls)
            btn.clicked.connect(lambda checked, c=cls: self._select_class(c))
            self._tab_btns[cls] = btn
            tab_row.addWidget(btn)
        lay.addLayout(tab_row)

        # ── Lista de itens (scrollável) ──────────────────────────────
        self.lst = QListWidget()
        self.lst.setStyleSheet(f"""
            QListWidget {{
                background: {Colors.BG_DEEP}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; font-size: 11px;
            }}
            QListWidget::item {{ padding: 2px 4px; }}
            QListWidget::item:selected {{
                background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT};
            }}
            QListWidget::item:hover {{ background: {Colors.BG_CARD}; }}
        """)
        # currentItemChanged: setas do teclado também disparam seleção
        self.lst.currentItemChanged.connect(
            lambda cur, _prev: self._on_item_clicked(cur) if cur is not None else None
        )
        lay.addWidget(self.lst, 1)

        # ── Botões compactos ─────────────────────────────────────────
        def _mbtn(text, bg, hover):
            b = QPushButton(text)
            b.setFixedHeight(24)
            b.setStyleSheet(f"""
                QPushButton {{
                    background:{bg}; color:{Colors.TEXT_BRIGHT};
                    border-radius:3px; padding:2px 6px;
                    font-weight:bold; font-size:11px;
                }}
                QPushButton:hover {{ background:{hover}; }}
                QPushButton:disabled {{ background:{Colors.BORDER_DEFAULT}; color:{Colors.TEXT_DIM}; }}
            """)
            return b

        # ── Botões individuais N1 / N2 / N3 / N4 ────────────────────
        n_row1 = QHBoxLayout()
        n_row1.setSpacing(3)
        self.btn_gerar_n1 = _mbtn("▶ N1", "#1b3a6b", "#2a5ab0")
        self.btn_gerar_n1.setEnabled(False)
        self.btn_gerar_n1.setToolTip("Gerar N1+N3: estrutural + robot SA (lista 1)")
        self.btn_gerar_n1.clicked.connect(self._on_gerar_n1_clicked)
        n_row1.addWidget(self.btn_gerar_n1)

        self.btn_gerar_n2 = _mbtn("▶ N2", "#1a4a2a", "#2a7a4a")
        self.btn_gerar_n2.setEnabled(False)
        self.btn_gerar_n2.setToolTip("Gerar N2+N4: recorte ER + robot ER (lista 2)")
        self.btn_gerar_n2.clicked.connect(self._on_gerar_n2_clicked)
        n_row1.addWidget(self.btn_gerar_n2)

        self.btn_gerar_n3 = _mbtn("▶ N3", "#4a2a1a", "#8a4a2a")
        self.btn_gerar_n3.setEnabled(False)
        self.btn_gerar_n3.setToolTip("Gerar N3: robot DXF via ficha SA")
        self.btn_gerar_n3.clicked.connect(self._on_gerar_n3_clicked)
        n_row1.addWidget(self.btn_gerar_n3)

        self.btn_gerar_n4 = _mbtn("▶ N4", "#2d1a47", "#5a2a8a")
        self.btn_gerar_n4.setEnabled(False)
        self.btn_gerar_n4.setToolTip("Gerar N4: robot DXF via ficha ER (lista 2)")
        self.btn_gerar_n4.clicked.connect(self._on_gerar_n4_clicked)
        n_row1.addWidget(self.btn_gerar_n4)
        lay.addLayout(n_row1)

        crop_row = QHBoxLayout()
        crop_row.setSpacing(3)
        self.btn_process = _mbtn("▶ Gerar N3", Colors.ACCENT_BLUE, Colors.ACCENT_BLUE_HOVER)
        self.btn_process.setEnabled(False)
        self.btn_process.setVisible(False)   # mantido por compatibilidade mas oculto
        self.btn_process.clicked.connect(self._on_process_clicked)
        crop_row.addWidget(self.btn_process)

        self.btn_process_all = _mbtn("⚡ Gerar todos N1,2,3", "#4a2a7a", "#6a3a9a")
        self.btn_process_all.setToolTip("Processa N1 → N2 → N3 para o item selecionado")
        self.btn_process_all.clicked.connect(self._on_process_all_clicked)
        crop_row.addWidget(self.btn_process_all)
        lay.addLayout(crop_row)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {Colors.BORDER_DEFAULT};")
        lay.addWidget(sep)

        self.btn_analise = _mbtn("▶ Análise Geral", Colors.ACCENT_SUCCESS, "rgba(67,160,71,1)")
        self.btn_analise.setToolTip("Processa o DXF estrutural N1 e preenche a lista de itens")
        self.btn_analise.clicked.connect(lambda: self.analise_requested.emit())
        lay.addWidget(self.btn_analise)

        self.btn_fase4 = _mbtn("⚙ Fase 4 — Sync", Colors.ACCENT_WARNING, "rgba(245,124,0,1)")
        self.btn_fase4.setToolTip("Executa motor_fase4.py para o pavimento selecionado")
        self.btn_fase4.clicked.connect(lambda: self.fase4_requested.emit())
        lay.addWidget(self.btn_fase4)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(
            f"color:{Colors.TEXT_DIM}; font-size:9px; background:transparent;"
        )
        self.lbl_status.setWordWrap(True)
        lay.addWidget(self.lbl_status)

        # Selecionar LV por padrão
        self._select_class("LV")

    # ── Classe selecionada ───────────────────────────────────────────
    def _select_class(self, cls: str):
        self._current_classe = cls
        color = self._CLS_COLORS.get(cls, Colors.ACCENT_BLUE)
        for c, btn in self._tab_btns.items():
            active = (c == cls)
            btn.setChecked(active)
            if active:
                btn.setStyleSheet(f"""
                    QPushButton {{ background:{color}; color:#fff;
                        border-radius:3px; font-size:10px; font-weight:bold;
                        border-bottom: 2px solid white; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_SECONDARY};
                        border-radius:3px; font-size:10px; border:1px solid {Colors.BORDER_DEFAULT}; }}
                    QPushButton:hover {{ background:{Colors.BG_PANEL}; }}
                """)
        self._populate_list(cls)

    # ── Popula lista a partir do JSON dir da obra ─────────────────────
    def _populate_list(self, cls: str):
        self.lst.clear()

        # ── Fluxo Eng. Reversa N2/N4 ─────────────────────────────────
        if self._current_flow == "reverso":
            obra_name = ""
            if self._current_obra_dir is not None:
                obra_name = self._current_obra_dir.name
            rows = self._load_reverse_items(obra_name, cls, self._current_pav)
            if not rows:
                db_pav = self._pav_key_to_db_pav(self._current_pav) if self._current_pav else "?"
                msg = (f"— Sem itens ER para {db_pav} —"
                       if self._current_pav else "— Execute o Motor de Engenharia Reversa —")
                ph = QListWidgetItem(msg)
                ph.setForeground(QColor(Colors.TEXT_DIM))
                ph.setFlags(ph.flags() & ~Qt.ItemIsSelectable)
                self.lst.addItem(ph)
            else:
                color_aprovado = QColor(self._CLS_COLORS.get(cls, Colors.ACCENT_SUCCESS))
                color_auto     = QColor(Colors.ACCENT_WARNING)
                color_dim      = QColor(Colors.TEXT_PRIMARY)
                _badges = {
                    'aprovado':      (" [✓ aprovado]", color_aprovado),
                    'approved':      (" [✓ aprovado]", color_aprovado),
                    'auto_aprovado': (" [⚡ auto]",      color_auto),
                    'manual_sel':    (" [manual]",      color_dim),
                    'manual':        (" [manual]",      color_dim),
                    'motor':         (" [N2]",          color_dim),
                }
                for (elem_id, conf, status, recorte_path) in rows:
                    badge, color = _badges.get(status, (" [N2]", color_dim))
                    it = QListWidgetItem(f"{elem_id}{badge}")
                    it.setData(Qt.UserRole, (cls, elem_id))
                    it.setData(Qt.UserRole + 1, recorte_path)
                    it.setForeground(color)
                    it.setToolTip(
                        f"Confiança: {conf:.0%} | Status: {status}\nRecorte: {recorte_path}"
                    )
                    self.lst.addItem(it)
            return

        # ── Fluxo Estrutural N1/N3 (comportamento original) ───────────
        if self._current_obra_dir is None:
            ph = QListWidgetItem("— selecione uma obra —")
            ph.setForeground(QColor(Colors.TEXT_DIM))
            ph.setFlags(ph.flags() & ~Qt.ItemIsSelectable)
            self.lst.addItem(ph)
            return

        json_dir  = self._current_obra_dir / self._JSON_DIRS[cls]
        prev_dir  = self._current_obra_dir / self._PREVIEW_DIRS[cls]
        prefix    = self._PREVIEW_PFX[cls]

        item_ids: list[str] = []
        if json_dir.exists():
            item_ids = sorted(
                f.stem for f in json_dir.glob("*.json")
                if not f.stem.startswith("_") and not f.stem.startswith("vigas")
                   and not f.stem.startswith("fichas")
            )
        # fallback LV estático
        if not item_ids and cls == "LV":
            item_ids = VIGAS_LV_LIST

        if not item_ids:
            ph = QListWidgetItem("— sem itens —")
            ph.setForeground(QColor(Colors.TEXT_DIM))
            ph.setFlags(ph.flags() & ~Qt.ItemIsSelectable)
            self.lst.addItem(ph)
            return

        color_ok  = QColor(self._CLS_COLORS.get(cls, Colors.ACCENT_SUCCESS))
        color_dim = QColor(Colors.TEXT_PRIMARY)

        for iid in item_ids:
            n3_ok = (prev_dir / f"{prefix}{iid}.dxf").exists()
            badge = " [N3]" if n3_ok else ""
            it = QListWidgetItem(f"{iid}{badge}")
            it.setData(Qt.UserRole, (cls, iid))
            it.setForeground(color_ok if n3_ok else color_dim)
            self.lst.addItem(it)

    # ── Flow switcher: Estrutural N1/N3 ←→ Eng. Reversa N2/N4 ──────────
    def _select_flow(self, flow: str):
        """Alterna entre fluxo estrutural (N1/N3) e engenharia reversa (N2/N4)."""
        self._current_flow = flow
        is_rev = (flow == "reverso")
        self._btn_flow_estru.setChecked(not is_rev)
        self._btn_flow_rev.setChecked(is_rev)
        self._btn_flow_estru.setStyleSheet(
            self._flow_ss_active if not is_rev else self._flow_ss_inactive
        )
        self._btn_flow_rev.setStyleSheet(
            self._flow_ss_active if is_rev else self._flow_ss_inactive
        )
        self._populate_list(self._current_classe)

    @staticmethod
    def _pav_key_to_db_pav(pav_key: str) -> str:
        """Converte pav_key do dxf_discovery.json para o formato de pavimento do DB.

        Exemplos:
          '13PAV'                    → '13_PAV'
          'TIPO - 3 AO 12PAV'       → '12_PAV'
          'PARAISO - COBERTURA...'  → 'COBERTURA'
          'TËRREO' / 'TERREO'       → 'TERREO'
          '1PAV'                    → '1_PAV'
        """
        import re as _re, unicodedata as _ucd
        # Normalizar unicode (remove acentos: Ë→E, º→o etc.)
        s = _ucd.normalize('NFKD', pav_key)
        s = ''.join(c for c in s if not _ucd.combining(c)).upper().strip()

        if 'TERREO' in s or 'TRREO' in s:
            return 'TERREO'
        if 'COB' in s:
            return 'COBERTURA'
        # Número antes de PAV: "13PAV" → ['13'], "TIPO - 3 AO 12PAV" → ['3','12']
        matches = _re.findall(r'(\d+)\s*PAV', s)
        if matches:
            return f"{matches[-1]}_PAV"   # último número (ex: 12 de "3 AO 12PAV")
        if 'TIPO' in s:
            return 'TIPO'
        return pav_key.strip()

    @staticmethod
    def _folder_name_to_db_pav(folder_name: str) -> str:
        """Aplica a mesma lógica de _pav_key_to_db_pav a um nome de pasta de recortes_reversos
        (ex: 'ALIMONTI - PARAISO - 13° PAV.- LV - R00' → '13_PAV')."""
        import re as _re, unicodedata as _ucd
        n = _ucd.normalize('NFKD', folder_name)
        n = ''.join(c for c in n if not _ucd.combining(c)).upper()
        if 'TERREO' in n or 'TRREO' in n:
            return 'TERREO'
        if 'COB' in n:
            return 'COBERTURA'
        nums = _re.findall(r'(\d+)\s*(?:PAV|°)', n)
        if nums:
            return f"{nums[-1]}_PAV"
        return folder_name.upper()

    def _load_reverse_items(self, obra_name: str, classe: str, pav_key: str = "") -> list:
        """Busca recortes do SQLite (reverse_eng_recortes) filtrados por obra + pavimento + classe,
        refletindo o estado REAL salvo no Diagnostic Reverse Hub (aprovação humana 'aprovado',
        auto-aprovação >=90% 'auto_aprovado', ou demais status).
        Quando há múltiplos recortes para o mesmo elemento_id, prioriza o de status mais
        autoritativo ('aprovado' > 'auto_aprovado' > 'manual_sel' > 'manual' > 'motor').
        Fallback: quando não há registros no DB para o pav, varre o disco em recortes_reversos.
        Retorna lista de (elemento_id, confianca, status, recorte_path)."""
        try:
            import sqlite3
            from pathlib import Path as _P
            db_path = r"D:/Agente-cad-PYSIDE/project_data.vision"
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
            db_cls = _cls_map.get(classe, classe)

            cur.execute(
                "SELECT elemento_id, confidence, status, recorte_path "
                "FROM reverse_eng_recortes "
                "WHERE obra_name=? AND classe=? ORDER BY elemento_id, created_at DESC",
                (obra_name, db_cls)
            )
            all_rows = cur.fetchall()
            conn.close()

            db_pav = self._pav_key_to_db_pav(pav_key) if pav_key else ""

            _priority = {'aprovado': 0, 'auto_aprovado': 1, 'manual_sel': 2,
                          'manual': 3, 'motor': 4}
            best: dict = {}
            for elem_id, conf, status, recorte_path in all_rows:
                if not recorte_path:
                    continue
                p = _P(recorte_path)
                if not p.exists():
                    continue
                if db_pav:
                    folder_pav = self._folder_name_to_db_pav(p.parent.name)
                    if folder_pav != db_pav:
                        continue
                rank = _priority.get(status, 5)
                prev = best.get(elem_id)
                if prev is None or rank < prev[3]:
                    best[elem_id] = (elem_id, conf or 0.0, status, rank, recorte_path)

            rows = [(e, c, s, rp) for (e, c, s, _r, rp) in best.values()]
            rows.sort(key=lambda r: r[0])

            # Fallback: nada no DB para esse pav → varre recortes_reversos no disco
            if not rows and pav_key:
                rows = self._scan_disk_recortes(obra_name, classe, pav_key)

            return rows
        except Exception:
            return []   # tabela ainda não existe ou obra não tem recortes — OK

    def _scan_disk_recortes(self, obra_name: str, classe: str, pav_key: str) -> list:
        """Fallback: varre Fase-2_Triagem/recortes_reversos/ no disco quando o DB não tem
        registros (reverse_eng_recortes) para esse pav.
        Identifica pasta pelo padrão pav+classe, extrai elemento_id do nome do arquivo.
        Retorna lista de (elemento_id, 0.0, status, recorte_path)."""
        import re as _re, unicodedata as _ucd
        from pathlib import Path as _P

        # Mapeamento classe CE → sufixo de pasta DXF
        _cls_folder = {"PL": "PL", "LV": "LV", "FV": "FV", "LJ": "LJ",
                       "PIL": "PL", "LAJ": "LJ"}
        folder_cls = _cls_folder.get(classe, classe)

        # Prefixo de arquivo: PIL_P*, LV_V*, FV_V*, LAJ_L*
        _cls_prefix = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ",
                       "PIL": "PIL", "LAJ": "LAJ"}
        file_prefix = _cls_prefix.get(classe, classe)

        db_pav = self._pav_key_to_db_pav(pav_key)

        try:
            recortes_dir = (DADOS_OBRAS_ROOT / obra_name /
                            "Fase-2_Triagem" / "recortes_reversos")
            if not recortes_dir.exists():
                return []

            def _norm(s: str) -> str:
                t = _ucd.normalize('NFKD', s)
                return ''.join(c for c in t if not _ucd.combining(c)).upper()

            # Coletar elemento_ids únicos de pastas que batem com db_pav + classe
            elem_ids: dict = {}  # elem_id → (tag, dxf_path)
            for folder in recortes_dir.iterdir():
                if not folder.is_dir():
                    continue
                # Filtrar pela classe (sufixo '- PL -', '- LV -', etc.)
                fn_norm = _norm(folder.name)
                if f'- {folder_cls} -' not in fn_norm and f'- {folder_cls}.' not in fn_norm:
                    continue
                # Filtrar pelo pavimento
                if self._folder_name_to_db_pav(folder.name) != db_pav:
                    continue
                # Varrer DXFs e extrair elemento_id
                for dxf in folder.glob("*.dxf"):
                    stem = dxf.stem  # ex: PIL_P1_motor_178..., LV_V1_A_sel_178...
                    # Padrão: {PREFIX}_{elemid}_(motor|sel)_{timestamp}
                    m = _re.match(
                        rf'^{_re.escape(file_prefix)}_(.+?)_(motor|sel)_\d+$',
                        stem, _re.IGNORECASE
                    )
                    if not m:
                        continue
                    eid = m.group(1)
                    tag = m.group(2)  # 'motor' ou 'sel'
                    # Prioridade: sel > motor
                    prev = elem_ids.get(eid)
                    if prev is None:
                        elem_ids[eid] = (tag, dxf)
                    else:
                        prev_tag, _prev_dxf = prev
                        if tag == 'sel' or prev_tag == 'motor':
                            elem_ids[eid] = (tag, dxf)

            # Construir resultado (elemento_id, confianca, status, recorte_path)
            result = []
            for eid in sorted(elem_ids):
                tag, dxf_path = elem_ids[eid]
                status = 'auto_aprovado' if tag == 'motor' else 'aprovado'
                result.append((eid, 0.0, status, str(dxf_path)))
            return result

        except Exception:
            return []

    # ── Set obra (chamado quando troca obra no combo) ─────────────────
    def set_obra(self, obra_dir_str: str):
        from pathlib import Path as _P
        self._current_obra_dir = _P(obra_dir_str) if obra_dir_str else None
        self._populate_list(self._current_classe)

    # ── Set pav (chamado quando troca pavimento no combo) ─────────────
    def set_pav(self, pav_key: str):
        """Atualiza o pavimento atual e repopula a lista se no fluxo ER."""
        self._current_pav = pav_key
        if self._current_flow == "reverso":
            self._populate_list(self._current_classe)

    # ── Click item ────────────────────────────────────────────────────
    def _on_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        classe, item_id = data
        self._selected_classe = classe
        self._selected_item   = item_id
        # Captura o recorte_path já salvo no item (estado atual do DB, sem re-consulta)
        self._selected_recorte_path = item.data(Qt.UserRole + 1) or ""
        for btn in (self.btn_process, self.btn_gerar_n1,
                    self.btn_gerar_n2, self.btn_gerar_n3, self.btn_gerar_n4):
            btn.setEnabled(True)
        self.item_selected.emit(classe, item_id)

    def _on_process_clicked(self):
        if self._selected_item:
            self.btn_process.setEnabled(False)
            self.btn_process_all.setEnabled(False)
            self.process_requested.emit(self._selected_classe, self._selected_item)

    def _on_process_all_clicked(self):
        self._disable_all_btns()
        if self._selected_item:
            self.process_requested.emit(self._selected_classe, self._selected_item)
        else:
            self.process_requested.emit("ALL", "ALL")

    def _on_gerar_n1_clicked(self):
        if self._selected_item:
            self._disable_all_btns()
            self.gerar_n1_requested.emit(self._selected_classe, self._selected_item)

    def _on_gerar_n2_clicked(self):
        if self._selected_item:
            self._disable_all_btns()
            self.gerar_n2_requested.emit(self._selected_classe, self._selected_item)

    def _on_gerar_n3_clicked(self):
        if self._selected_item:
            self._disable_all_btns()
            self.gerar_n3_requested.emit(self._selected_classe, self._selected_item)

    def _on_gerar_n4_clicked(self):
        if self._selected_item:
            self._disable_all_btns()
            self.gerar_n4_requested.emit(self._selected_classe, self._selected_item)

    def _disable_all_btns(self):
        for btn in (self.btn_process, self.btn_gerar_n1,
                    self.btn_gerar_n2, self.btn_gerar_n3, self.btn_gerar_n4,
                    self.btn_process_all):
            btn.setEnabled(False)

    def _enable_item_btns(self):
        if self._selected_item:
            for btn in (self.btn_process, self.btn_gerar_n1,
                        self.btn_gerar_n2, self.btn_gerar_n3, self.btn_gerar_n4):
                btn.setEnabled(True)
        self.btn_process_all.setEnabled(True)

    def set_status(self, text: str, color: str = ""):
        self.lbl_status.setText(text)
        c = color or Colors.TEXT_DIM
        self.lbl_status.setStyleSheet(
            f"color:{c}; font-size:9px; background:transparent;"
        )

    def refresh_tree(self):
        """Re-escaneia previews e atualiza indicadores."""
        self._populate_list(self._current_classe)

    def navigate(self, delta: int):
        """Avança (+1) ou retrocede (-1) na lista de itens."""
        count = self.lst.count()
        if count == 0:
            return
        cur = self.lst.currentRow()
        if cur < 0:
            new_row = 0 if delta > 0 else count - 1
        else:
            new_row = max(0, min(count - 1, cur + delta))
        if new_row != cur:
            self.lst.setCurrentRow(new_row)
            # currentItemChanged dispara → _on_item_clicked → item_selected signal


class TriLevelArea(QWidget):
    """Área central: 3 colunas com scroll horizontal + fichas de dados."""

    def __init__(self):
        super().__init__()
        self._current_obra: str = OBRA_TREINO_16.name
        self._current_pav:  str = ""
        self._discovery:    dict = {}
        self._scan_worker: "DXFScanWorker | None" = None
        self._load_data(OBRA_TREINO_16)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Título ──────────────────────────────────────────────────
        title_bar = QFrame()
        title_bar.setFixedHeight(34)
        title_bar.setStyleSheet(
            f"background: {Colors.BG_CARD}; border-bottom: 1px solid {Colors.BORDER_DEFAULT};"
        )
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(12, 0, 12, 0)
        lbl_t = QLabel("Comparison Engine — N1 / N2 / N3 (Robot SA) / N4 (Robot Eng. Rev.)")
        lbl_t.setStyleSheet(
            f"color: {Colors.ACCENT_PRIMARY}; font-weight: bold; font-size: 13px;"
        )
        self._lbl_item = QLabel("Nenhum item selecionado")
        self._lbl_item.setStyleSheet(
            f"color: {Colors.TEXT_SECONDARY}; font-size: 11px;"
        )
        tb.addWidget(lbl_t)
        tb.addStretch()
        tb.addWidget(self._lbl_item)
        lay.addWidget(title_bar)

        # ── QTabWidget N1 / N2 / N3 / N4 (tela cheia) ───────────────
        self._nivel_tabs = QTabWidget()
        self._nivel_tabs.setDocumentMode(True)
        self._nivel_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: {Colors.BG_SECONDARY};
            }}
            QTabBar::tab {{
                background: {Colors.BG_DEEP};
                color: {Colors.TEXT_SECONDARY};
                padding: 6px 20px;
                font-size: 11px;
                font-weight: bold;
                border: none;
                border-right: 1px solid {Colors.BORDER_DEFAULT};
                min-width: 80px;
            }}
            QTabBar::tab:selected {{
                color: #000;
                border-bottom: none;
            }}
            QTabBar::tab:hover {{
                color: {Colors.TEXT_PRIMARY};
            }}
        """)

        # Criar LevelColumns (mantém self._columns para compatibilidade total)
        self._columns = []
        _tab_colors = [
            ("#4a9eff", "#1b3a6b"),   # N1 azul
            ("#4acf7a", "#1a4a2a"),   # N2 verde
            ("#cf8a4a", "#4a2a1a"),   # N3 laranja
            ("#a855f7", "#2d1a47"),   # N4 roxo
        ]
        for i, (nivel_id, titulo, bg, accent, desc, mode) in enumerate(NIVEL_DEFS):
            col = LevelColumn(nivel_id, titulo, bg, accent, desc, mode)
            col.setFixedWidth(16777215)   # remove largura fixa — ocupa tela cheia
            col.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._columns.append(col)
            tab_accent, _ = _tab_colors[i]
            tab_label = f"  {nivel_id}  "
            tab_idx = self._nivel_tabs.addTab(col, tab_label)
            self._nivel_tabs.tabBar().setTabTextColor(tab_idx, QColor(tab_accent))

        lay.addWidget(self._nivel_tabs, 1)

    def _find_n4_dxf(self, obra_dir: Path, classe: str, item_id: str) -> "Path | None":
        """Retorna N4 DXF: procura em Fase-6/n4/ (gerado via ER ficha),
        cai back para N3 DXF se N4 ainda não foi gerado para este item."""
        prefixes = {"PL": "PL_preview_", "LV": "LV_preview_",
                    "FV": "FV_preview_", "LJ": "LJ_preview_"}
        pfx = prefixes.get(classe, f"{classe}_preview_")
        n4_dir = obra_dir / "Fase-6_Execucao_CAD" / "n4"
        for cand in [item_id, item_id.split('_')[0] if '_' in item_id else item_id]:
            p = n4_dir / f"{pfx}{cand}.dxf"
            if p.exists():
                return p
        # Fallback: N3 DXF (mesmo robô, mesmo output por enquanto)
        return self._find_n3_dxf(obra_dir, classe, item_id)

    # ── Carregamento de dados ────────────────────────────────────────

    def _load_data(self, obra_dir: Path):
        """Carrega dados da obra para todas as classes (PL/LV/FV/LJ).
        obra_dir = DADOS_OBRAS_ROOT / obra_name."""
        def _j(p, default=None):
            try:
                return json.loads(Path(p).read_text(encoding='utf-8', errors='replace'))
            except Exception:
                return default if default is not None else {}

        def _j_try(*paths, default=None):
            """Tenta múltiplos caminhos, retorna o primeiro que existe."""
            for p in paths:
                try:
                    t = Path(p).read_text(encoding='utf-8', errors='replace')
                    return json.loads(t)
                except Exception:
                    continue
            return default if default is not None else {}

        fase3 = obra_dir / "Fase-3_Interpretacao_Extracao"
        fase4 = obra_dir / "Fase-4_Sincronizacao"
        fase6 = obra_dir / "Fase-6_Execucao_CAD"
        kb_lv = obra_dir / "Fase-0_STOG_KB/LV"

        # ── LV (Vigas Laterais) ──────────────────────────────────────
        self._vigas_fase3  = _j_try(
            fase3 / "Vigas/vigas.json",
            fase3 / "vigas_dim.json",
            fase3 / "Vigas/vigas_enriquecida.json",
        )
        self._fichas_rev   = _j_try(
            fase3 / "Vigas/fichas_reverso_VIG_ALL.json",
            fase3 / "fichas_rev.json",
        )
        self._ancoras      = _j_try(
            fase3 / "ancoras_vigas.json",
            fase3 / "Vigas/ancoras_vigas.json",
        )
        lv2 = _j_try(
            fase6 / "granular/fichas/fichas_lv_v2.json",
            fase3 / "Vigas/fichas_lv_v2.json",
            default=[],
        )
        self._fichas_lv_v2 = lv2 if isinstance(lv2, list) else []

        # ── PL (Pilares) ─────────────────────────────────────────────
        self._pilares_fase3 = _j_try(
            fase3 / "Pilares/pilares_bh.json",
            fase3 / "pilares_bh.json",
            fase3 / "Pilares/pilares.json",
        )
        self._pilares_assembly = _j_try(
            fase3 / "Pilares/pilares_assembly.json",
            fase3 / "pilares_assembly.json",
        )

        # ── FV (Vigas Fundo) ─────────────────────────────────────────
        self._vigas_fundo_fase3 = _j_try(
            fase3 / "Vigas/vigas_fundo.json",
            fase3 / "vigas_fundo.json",
        )

        # ── LJ (Lajes) ───────────────────────────────────────────────
        self._lajes_fase3 = _j_try(
            fase3 / "Lajes/lajes_data.json",
            fase3 / "lajes_data.json",
            fase3 / "Lajes/lajes.json",
        )
        self._lajes_pontaletes = _j_try(
            fase3 / "Lajes/lajes_meioPont.json",
            fase3 / "lajes_meioPont.json",
        )

        # ── KB (Knowledge Base — STOG N2) ───────────────────────────
        self._kb_ents = []
        if kb_lv.exists():
            kb_files = sorted(kb_lv.glob("*.json"))
            if kb_files:
                kb_data = _j(kb_files[0])
                self._kb_ents = kb_data.get("entities", [])

        # ── Escanear DXF estrutural (labels + entities) — ASYNC ─────────
        self._est_labels: dict = {}   # {item_id: (cx, cy)}
        self._est_ents_raw: list = [] # [(type, x, y, layer)]
        self._start_async_scan(obra_dir)

    def _start_async_scan(self, obra_dir: Path):
        """Inicia scan do DXF estrutural em QThread background — sem bloquear UI.
        Cancela scan anterior se ainda em andamento."""
        # Cancela worker anterior
        if hasattr(self, '_scan_worker') and self._scan_worker is not None:
            try:
                self._scan_worker.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._scan_worker = None

        dxf_path = self._find_n1_dxf(obra_dir)
        if dxf_path is None or not dxf_path.exists():
            return

        self._scan_worker = DXFScanWorker(dxf_path)
        self._scan_worker.finished.connect(self._on_scan_done)
        self._scan_worker.start()

    def _on_scan_done(self, tmp_path: str):
        """Recebe caminho do arquivo temp com resultado do scan — lê e apaga."""
        self._scan_worker = None
        if not tmp_path:
            return
        import os, pickle as _pickle
        try:
            with open(tmp_path, 'rb') as f:
                data = _pickle.load(f)
            self._est_labels   = data.get('labels', {})
            self._est_ents_raw = data.get('ents', [])
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    # ── CE-004: helpers dinâmicos ────────────────────────────────────

    def _load_discovery(self) -> dict:
        """Carrega (e cacheia) dxf_discovery.json."""
        if not self._discovery:
            disc_path = DADOS_OBRAS_ROOT / "dxf_discovery.json"
            if disc_path.exists():
                try:
                    self._discovery = json.loads(
                        disc_path.read_text(encoding='utf-8', errors='replace')
                    )
                except Exception:
                    self._discovery = {}
        return self._discovery

    def _find_n1_dxf(self, obra_dir: Path) -> "Path | None":
        """Retorna DXF limpo do pavimento atual de Fase-2_Triagem/Estruturais_Pavimentos_Limpos/.
        Usa tokens derivados do nome do pavimento classificado na triagem.
        Fallback: DXF bruto de Fase-1_Ingestao se limpo não encontrado."""
        return self._find_n1_clean_dxf(obra_dir, self._current_pav or "")

    def _find_n1_clean_dxf(self, obra_dir: Path, pav: str) -> "Path | None":
        """Busca DXF limpo em Fase-2_Triagem/Estruturais_Pavimentos_Limpos/ para o pavimento dado.
        Estratégia de matching por tokens derivados do nome do pavimento classificado.
        Fallback para DXF bruto se não encontrado."""
        import re as _re

        clean_folder = obra_dir / "Fase-2_Triagem" / "Estruturais_Pavimentos_Limpos"
        pav_up = pav.upper().strip()

        # Tokens de busca derivados do nome do pavimento (ex: "13PAV" → ["13", "PAVIMENTO_13", "PAVIMENTO-13"])
        def _pav_tokens(name: str) -> list[str]:
            name_up = name.upper()
            tokens: list[str] = []
            # Número principal (ex: "13PAV" → "13")
            nums = _re.findall(r'\d+', name_up)
            if nums:
                n = nums[0]
                tokens += [f"PAVIMENTO_{n}", f"PAVIMENTO-{n}", f"PAVIMENTO {n}",
                           f"{n}-PAV", f"{n}_PAV", f"{n}PAV",
                           f"{n}-PAVIMENTO", f"{n}_PAVIMENTO"]
            # Keywords especiais
            kw_map = {
                "TERR": ["TERREO", "TÉRREO", "TERREO"],
                "TIPO": ["TIPO", "PAVIMENTO-TIPO", "PAVIMENTO_TIPO"],
                "COB":  ["COBERTURA", "COB"],
                "ATC":  ["ATICO", "ÁTICO", "ATTICO"],
                "FUN":  ["FUNDACAO", "FUNDAÇÃO"],
                "SUB":  ["SUBSOLO"],
                "DEC":  ["DECK"],
                "BAR":  ["BARRILETE", "CAIXA"],
            }
            for kw, expansions in kw_map.items():
                if kw in name_up:
                    tokens += expansions
            return tokens

        if clean_folder.exists():
            dxfs = sorted(clean_folder.glob("*.dxf"))
            if dxfs:
                tokens = _pav_tokens(pav_up)
                # Match: nome do arquivo contém algum token
                for tok in tokens:
                    candidates = [p for p in dxfs if tok.upper() in p.name.upper()]
                    if candidates:
                        return candidates[0]
                # Fallback: primeiro DXF disponível na pasta limpa
                return dxfs[0]

        # Fallback final: DXF bruto de Fase-1
        bruto_folder = obra_dir / "Fase-1_Ingestao" / "Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
        if not bruto_folder.exists():
            return None
        dxfs = sorted(bruto_folder.glob("*.dxf"))
        if not dxfs:
            return None

        pav_tokens = _pav_tokens(pav_up)

        def format_rank(p: Path) -> int:
            n = p.name.upper()
            if "R2018" in n and "ASCII" in n: return 0
            if "R2013" in n and "ASCII" in n: return 1
            if "ASCII" in n:                  return 3
            return 4

        if pav_tokens:
            candidates = [p for p in dxfs
                          if any(t.upper() in p.name.upper() for t in pav_tokens)]
            if candidates:
                return sorted(candidates, key=format_rank)[0]

        non_loc = [p for p in dxfs if "LOC" not in p.name.upper()]
        pool = non_loc if non_loc else dxfs
        return sorted(pool, key=format_rank)[0]

    def _find_n2_dxf(self, obra: str, pav: str, tipo: str) -> "Path | None":
        """Retorna DXF de eng. reversa para obra/pav/tipo via dxf_discovery.json."""
        disc = self._load_discovery()
        rel = disc.get(obra, {}).get(pav, {}).get(tipo)
        if rel:
            p = Path(rel)
            if p.is_absolute() and p.exists():
                return p
            # tentativa com raiz DADOS_OBRAS_ROOT
            p2 = DADOS_OBRAS_ROOT / rel
            if p2.exists():
                return p2
        # fallback: scan pasta eng. reversa
        folder = DADOS_OBRAS_ROOT / obra / "Fase-1_Ingestao" / "Projetos_Finalizados_para_Engenharia_Reversa"
        if folder.exists():
            pattern = f"*{tipo}*.dxf"
            matches = sorted(folder.glob(pattern))
            if matches:
                return matches[0]
        return None

    def set_obra_pav(self, obra: str, pav: str):
        """Recarrega dados quando obra ou pavimento muda no Fase8Panel."""
        if obra == self._current_obra and pav == self._current_pav:
            return
        self._current_obra = obra
        self._current_pav  = pav
        obra_dir = DADOS_OBRAS_ROOT / obra
        if obra_dir.exists():
            self._est_labels   = {}
            self._est_ents_raw = []
            self._load_data(obra_dir)

    def _find_n3_dxf(self, obra_dir: Path, classe: str, item_id: str) -> "Path | None":
        """Retorna preview DXF gerado pelo robô em Fase-6.
        Para LV/FV, o arquivo usa apenas o ID da viga sem sufixo de face (_A/_B).
        Ex: item_id='V4_A' → 'LV_preview_V4.dxf'
        """
        prefixes = {"PL": "PL_preview_", "LV": "LV_preview_",
                    "FV": "FV_preview_", "LJ": "LJ_preview_"}
        pfx = prefixes.get(classe, f"{classe}_preview_")
        fase6 = obra_dir / "Fase-6_Execucao_CAD"
        # Tenta exatamente primeiro
        p = fase6 / f"{pfx}{item_id}.dxf"
        if p.exists():
            return p
        # Para LV/FV: strip sufixo de face (_A, _B, .A, .B)
        if classe in ("LV", "FV"):
            import re
            stem = re.sub(r'[_\.]([AB])$', '', item_id)
            p2 = fase6 / f"{pfx}{stem}.dxf"
            if p2.exists():
                return p2
        return None

    def _get_n1_bbox_for(self, item_id: str, R: int = 134):
        """Retorna bbox do item no DXF estrutural usando labels escaneados.
        R=134 (era 267/2) e pad=34 (era 67/2) → zoom 6x mais perto que original."""
        pos = self._est_labels.get(item_id)
        if not pos:
            return None
        cx, cy = pos
        xs = [ex for (_, ex, ey, _) in self._est_ents_raw
              if abs(ex - cx) < R and abs(ey - cy) < R]
        ys = [ey for (_, ex, ey, _) in self._est_ents_raw
              if abs(ex - cx) < R and abs(ey - cy) < R]
        if not xs:
            return (cx - R, cy - R, cx + R, cy + R)
        pad = 34
        return (min(xs)-pad, min(ys)-pad, max(xs)+pad, max(ys)+pad)

    def _get_n2_bbox_for(self, item_id: str, classe: str = 'LV'):
        """Retorna bbox do item no DXF STOG real.
        - LV: busca NOMENCLATURA no KB (ents do DXF de eng. reversa)
        - PL: usa _est_labels (posição no DXF estrutural) — N2 é crop do DXF estrutural
        - FV/LJ: retorna None (auto-bbox = view completa)
        """
        if classe == 'PL':
            pos = self._est_labels.get(item_id)
            if not pos:
                return None
            cx, cy = pos
            R = 700
            xs = [ex for (_, ex, ey, _) in self._est_ents_raw if abs(ex-cx) < R and abs(ey-cy) < R]
            ys = [ey for (_, ex, ey, _) in self._est_ents_raw if abs(ex-cx) < R and abs(ey-cy) < R]
            if not xs:
                return (cx - R, cy - R, cx + R, cy + R)
            pad = 150
            return (min(xs)-pad, min(ys)-pad, max(xs)+pad, max(ys)+pad)

        if classe in ('FV', 'LJ'):
            return None  # auto-bbox

        # LV: usa KB (NOMENCLATURA labels)
        if not self._kb_ents:
            return None
        # KB usa ponto (V4.A), NavSidebar usa underscore (V4_A) — normalizar
        kb_id = item_id.replace('_', '.')
        cx = cy = None
        for e in self._kb_ents:
            if e.get('type') not in ('MTEXT', 'TEXT'):
                continue
            c = (e.get('content', '') or '').replace('\\P', '\n').split('\n')[0].strip()
            if c in (item_id, kb_id) and e.get('layer', '') == 'NOMENCLATURA':
                ins = e.get('insert', [0, 0])
                cx, cy = ins[0], ins[1]
                break
        if cx is None:
            return None
        R = 500
        all_xs, all_ys = [], []
        for e in self._kb_ents:
            t = e.get('type', '')
            if t in ('MTEXT', 'TEXT'):
                ins = e.get('insert', [0, 0]); ex, ey = ins[0], ins[1]
            elif t == 'LINE':
                s = e.get('start', [0, 0]); en = e.get('end', [0, 0])
                ex = (s[0]+en[0])/2; ey = (s[1]+en[1])/2
            elif t == 'LWPOLYLINE':
                pts2 = e.get('vertices', [])
                if not pts2:
                    continue
                for pp in pts2:
                    if abs(pp[0]-cx) < R and abs(pp[1]-cy) < R:
                        all_xs.append(pp[0]); all_ys.append(pp[1])
                continue
            elif t == 'DIMENSION':
                ins = e.get('insert', [0, 0]); ex, ey = ins[0], ins[1]
            else:
                continue
            if abs(ex-cx) < R and abs(ey-cy) < R:
                all_xs.append(ex); all_ys.append(ey)
        if not all_xs:
            return (cx-R, cy-R, cx+R, cy+R)
        pad = 80
        return (min(all_xs)-pad, min(all_ys)-pad,
                max(all_xs)+pad, min(cy+180, max(all_ys)+pad))

    def _ficha_generic(self, classe: str, item_id: str) -> list:
        """Lê JSON de Fase-4_Sincronizacao para qualquer classe."""
        dirs = {"PL": "JSON_Pilares", "LV": "JSON_Vigas_Laterais",
                "FV": "JSON_Vigas_Fundo", "LJ": "JSON_Lajes"}
        sub = dirs.get(classe, f"JSON_{classe}")
        json_path = (DADOS_OBRAS_ROOT / self._current_obra
                     / "Fase-4_Sincronizacao" / sub / f"{item_id}.json")
        if not json_path.exists():
            return [("JSON Fase-4", f"não encontrado para {classe}/{item_id}")]
        try:
            data = json.loads(json_path.read_text(encoding='utf-8', errors='replace'))
        except Exception as exc:
            return [("Erro leitura", str(exc)[:60])]
        rows = []
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                rows.append((k, json.dumps(v, ensure_ascii=False)[:80]))
            else:
                rows.append((k, str(v)))
        return rows or [("(vazio)", "")]

    def _disconnect_chain(self):
        """Desconecta callbacks de loading sequencial anteriores."""
        for attr, col_idx in (('_n1_ready_cb', 0), ('_n2_ready_cb', 1)):
            cb = getattr(self, attr, None)
            if cb is not None:
                try:
                    self._columns[col_idx].img_widget.ready.disconnect(cb)
                except (RuntimeError, TypeError):
                    pass
                setattr(self, attr, None)

    def load_item(self, classe: str, item_id: str):
        """
        Carrega as 3 colunas para o item selecionado (todas as classes: PL/LV/FV/LJ).
        Loading sequencial 3 estágios: N1 pronto → N2 pronto → N3.
        """
        self._lbl_item.setText(f"{classe} / {item_id}")
        self._disconnect_chain()

        obra_dir = DADOS_OBRAS_ROOT / self._current_obra
        n1_dxf = self._find_n1_dxf(obra_dir)
        n2_dxf = self._find_n2_dxf(self._current_obra, self._current_pav, classe)
        n3_dxf = self._find_n3_dxf(obra_dir, classe, item_id)

        n1_bbox = self._get_n1_bbox_for(item_id)
        n2_bbox = self._get_n2_bbox_for(item_id, classe)

        # Fichas (instantâneas) — class-aware para todas as classes
        self._columns[0].set_ficha(self._ficha_n1_for(classe, item_id))
        self._columns[1].set_ficha(self._ficha_n2_for(classe, item_id))
        self._columns[2].set_ficha(self._ficha_n3_for(classe, item_id))

        # Mostrar placeholder nas colunas enquanto carregam
        for col in self._columns:
            col.img_widget.clear_image("Aguardando...")

        # Loading sequencial 3 estágios: N1 → N2 → N3

        def _on_n2_ready():
            self._n2_ready_cb = None
            try:
                self._columns[1].img_widget.ready.disconnect(_on_n2_ready)
            except (RuntimeError, TypeError):
                pass
            self._columns[2].load_content(n3_dxf, None)  # auto-bbox

        def _on_n1_ready():
            self._n1_ready_cb = None
            try:
                self._columns[0].img_widget.ready.disconnect(_on_n1_ready)
            except (RuntimeError, TypeError):
                pass
            self._n2_ready_cb = _on_n2_ready
            self._columns[1].img_widget.ready.connect(_on_n2_ready)
            n2_path = n2_dxf if (n2_dxf and n2_dxf.exists()) else None
            self._columns[1].load_content(n2_path, n2_bbox)

        self._n1_ready_cb = _on_n1_ready
        self._columns[0].img_widget.ready.connect(_on_n1_ready)
        n1_path = n1_dxf if (n1_dxf and n1_dxf.exists()) else None
        self._columns[0].load_content(n1_path, n1_bbox)

    def set_processing(self, active: bool):
        for col in self._columns:
            col.set_processing(active)

    # ── Pipeline helpers ─────────────────────────────────────────────

    _NIVEL_IDX = {'N1': 0, 'N2': 1, 'N3': 2, 'N4': 3}

    def set_pipeline_step(self, nivel: str, step_idx: int, status: str, msg: str = ''):
        """Atualiza um step do pipeline visual de uma coluna específica."""
        idx = self._NIVEL_IDX.get(nivel, -1)
        if 0 <= idx < len(self._columns):
            self._columns[idx].pipeline.set_step(step_idx, status, msg)

    def reset_all_pipelines(self):
        """Reseta todos os steps de todos os níveis para 'pending'."""
        for col in self._columns:
            col.pipeline.reset()

    # ── Fichas ──────────────────────────────────────────────────────

    def _ficha_n1(self, vn: str) -> list:
        """Ficha N1 para LV (Vigas Laterais) — dados Fase-3 estrutural."""
        return self._ficha_n1_for('LV', vn)

    def _ficha_n1_for(self, classe: str, item_id: str) -> list:
        """Ficha N1 class-aware — lê Fase-3 para qualquer classe."""
        rows = [("Nome", item_id), ("Classe", classe)]

        if classe == 'LV':
            vd  = self._vigas_fase3.get(item_id, {})
            fr  = self._fichas_rev.get(item_id, {})
            anc = self._ancoras.get(item_id, {})
            rows += [
                ("---", ""),
                ("b estrutural (cm)", vd.get("b", "—")),
                ("h estrutural (cm)", vd.get("h", "—")),
                ("Compr. bruto (cm)", vd.get("comprimento_original", "—")),
                ("Compr. enriquecido (cm)", vd.get("comprimento", "—")),
                ("Status enriquecimento", vd.get("comprimento_enrich_status", "—")),
                ("Confidence", f"{vd.get('confidence',0)*100:.1f}%" if vd.get('confidence') else "—"),
                ("Source", vd.get("source", "—")),
                ("Faces", ", ".join(vd.get("sides", []))),
                ("has_lv", str(fr.get("has_lv", "—"))),
                ("has_fv", str(fr.get("has_fv", "—"))),
                ("Pavimentos", ", ".join(fr.get("pavimentos", []))),
                ("Altura estrutural (cm)", fr.get("altura_cm", "—")),
                ("Âncora A (x, y)", str(anc.get("A", "—"))),
                ("Âncora B (x, y)", str(anc.get("B", "—"))),
            ]

        elif classe == 'PL':
            pd_ = self._pilares_fase3.get(item_id, {})
            pa  = self._pilares_assembly.get(item_id, {})
            pos = self._est_labels.get(item_id)
            rows += [
                ("---", ""),
                ("b (cm)", pd_.get("b", "—")),
                ("h (cm)", pd_.get("h", "—")),
                ("Altura (cm)", pd_.get("altura", "—")),
                ("Confidence", f"{pd_.get('confidence',0)*100:.1f}%" if pd_.get('confidence') else "—"),
                ("Source", pd_.get("source", "—")),
                ("---", ""),
                ("grade_1", pa.get("grade_1", "—")),
                ("grade_2", pa.get("grade_2", "—")),
                ("distancia_1", pa.get("distancia_1", "—")),
                ("Pos. estrutural (x,y)", f"({pos[0]:.0f}, {pos[1]:.0f})" if pos else "—"),
            ]

        elif classe == 'FV':
            fv = self._vigas_fundo_fase3.get(item_id, {})
            rows += [
                ("---", ""),
                ("b (cm)", fv.get("b", "—")),
                ("h (cm)", fv.get("h", "—")),
                ("Comprimento (cm)", fv.get("comprimento", "—")),
                ("Confidence", f"{fv.get('confidence',0)*100:.1f}%" if fv.get('confidence') else "—"),
                ("Source", fv.get("source", "—")),
            ]

        elif classe == 'LJ':
            lj = self._lajes_fase3.get(item_id, {})
            pont = self._lajes_pontaletes.get(item_id, {})
            rows += [
                ("---", ""),
                ("Comprimento (cm)", lj.get("comprimento", "—")),
                ("Largura (cm)", lj.get("largura", "—")),
                ("Área (cm²)", lj.get("area_cm2", "—")),
                ("Modo selecionado", lj.get("modo_selecionado", "—")),
                ("Pontaletes total", pont.get("total", "—") if isinstance(pont, dict) else "—"),
            ]

        if all(v == "—" for k, v in rows[2:] if k != "---"):
            rows.append(("⚠ Fase-3", "Rode Análise Geral para popular esta ficha"))
        return rows

    def _ficha_n2(self, vn: str) -> list:
        if not self._kb_ents:
            return [("KB", "não disponível")]

        # Encontrar sentinel principal
        main_sentinel = None
        for e in self._kb_ents:
            if e.get('type') not in ('MTEXT', 'TEXT'):
                continue
            c = (e.get('content', '') or '').replace('\\P', '\n').split('\n')[0].strip()
            if c == vn and e.get('layer', '') == 'NOMENCLATURA':
                ins = e.get('insert', [0, 0])
                main_sentinel = (ins[0], ins[1])
                break

        if not main_sentinel:
            return [("N2 sentinel", f"'{vn}' não encontrado em NOMENCLATURA")]

        cx, cy = main_sentinel
        R = 500
        layers, sarr_counts = set(), {}
        panels_by_y, dim_values, mtext_content = [], [], []
        n_ents, face_y = 0, {}

        for e in self._kb_ents:
            t = e.get('type', '')
            layer = e.get('layer', '')
            ex = ey = None

            if t in ('MTEXT', 'TEXT'):
                ins = e.get('insert', [0, 0])
                ex, ey = ins[0], ins[1]
            elif t == 'LINE':
                s = e.get('start', [0, 0]); en = e.get('end', [0, 0])
                ex = (s[0]+en[0])/2; ey = (s[1]+en[1])/2
            elif t == 'LWPOLYLINE':
                pts = e.get('vertices', [])
                if not pts:
                    continue
                ex = sum(p[0] for p in pts)/len(pts)
                ey = sum(p[1] for p in pts)/len(pts)
                if abs(ex - cx) < R and abs(ey - cy) < R:
                    xs  = [p[0] for p in pts]; ysp = [p[1] for p in pts]
                    w   = round(max(xs) - min(xs), 1)
                    if w > 5 and ('Pain' in layer or 'Painel' in layer):
                        panels_by_y.append((sum(ysp)/len(ysp), w))
                    n_ents += 1
                    layers.add(layer)
                continue
            elif t == 'DIMENSION':
                ins = e.get('insert', [0, 0])
                ex, ey = ins[0], ins[1]
            else:
                continue

            if ex is not None and abs(ex - cx) < R and abs(ey - cy) < R:
                n_ents += 1
                layers.add(layer)
                if 'SARR' in layer:
                    sarr_counts[layer] = sarr_counts.get(layer, 0) + 1
                if t in ('MTEXT', 'TEXT') and layer == 'NOMENCLATURA':
                    c = (e.get('content','') or '').replace('\\P','\n').split('\n')[0].strip()
                    if c == f'{vn}.A' and 'A' not in face_y:
                        face_y['A'] = ey
                    elif c == f'{vn}.B' and 'B' not in face_y:
                        face_y['B'] = ey
                if t == 'MTEXT':
                    c = (e.get('content','') or '').replace('\\P','\n').strip()
                    if c and len(c) < 60:
                        mtext_content.append(c.split('\n')[0])
                if t == 'DIMENSION':
                    m = e.get('measurement')
                    if m:
                        dim_values.append(round(m, 1))

        panels_A, panels_B = [], []
        if 'A' in face_y and 'B' in face_y:
            y_sep = (face_y['A'] + face_y['B']) / 2
            for (py, pw) in panels_by_y:
                (panels_A if py > y_sep else panels_B).append(pw)
        else:
            panels_A = [pw for (_, pw) in panels_by_y]
        panels_A = sorted(panels_A, reverse=True)
        panels_B = sorted(panels_B, reverse=True)

        return [
            ("Entidades na região KB", n_ents),
            ("Layers presentes", ", ".join(sorted(layers)) or "—"),
            ("Painéis A (larguras cm)", str(panels_A) if panels_A else "—"),
            ("Painéis B (larguras cm)", str(panels_B) if panels_B else "—"),
            ("Sarrafos (tipo: count)", str(sarr_counts) or "—"),
            ("MTEXT/labels", " | ".join(mtext_content[:8]) or "—"),
            ("COTAs (amostra)", str(sorted(set(dim_values))[:10]) or "—"),
            ("Face sep y (A/B)", f"A={face_y.get('A',0):.0f} B={face_y.get('B',0):.0f}" if face_y else "—"),
            ("Sentinel (x, y)", f"({cx:.0f}, {cy:.0f})"),
        ]

    def _ficha_n2_for(self, classe: str, item_id: str) -> list:
        """Ficha N2 class-aware — engenharia reversa para qualquer classe."""
        if classe == 'LV':
            return self._ficha_n2(item_id)
        elif classe == 'PL':
            # N2 para pilar: mostra coords no DXF estrutural + vizinhos
            pos = self._est_labels.get(item_id)
            if not pos:
                return [("N2 Pilar", f"'{item_id}' não encontrado no DXF estrutural"),
                        ("Dica", "Rode Análise Geral para escanear o DXF")]
            cx, cy = pos
            R = 600
            nearby = [(t, ex, ey, layer)
                      for (t, ex, ey, layer) in self._est_ents_raw
                      if abs(ex - cx) < R and abs(ey - cy) < R]
            layers = sorted({e[3] for e in nearby})
            return [
                ("Item", item_id),
                ("Posição estrutural (x)", f"{cx:.0f}"),
                ("Posição estrutural (y)", f"{cy:.0f}"),
                ("Entidades vizinhas", len(nearby)),
                ("Layers vizinhos", ", ".join(layers[:6]) or "—"),
            ]
        elif classe == 'FV':
            fv = self._vigas_fundo_fase3.get(item_id, {})
            if not fv:
                return [("N2 FV", "Dados de fundo viga não encontrados na Fase-3")]
            return [
                ("Nome", item_id),
                ("b (cm)", fv.get("b", "—")),
                ("h (cm)", fv.get("h", "—")),
                ("Comprimento (cm)", fv.get("comprimento", "—")),
                ("Confidence", f"{fv.get('confidence',0)*100:.1f}%" if fv.get('confidence') else "—"),
            ]
        elif classe == 'LJ':
            lj = self._lajes_fase3.get(item_id, {})
            if not lj:
                return [("N2 Laje", "Dados de laje não encontrados na Fase-3")]
            linhas_v = lj.get("linhas_verticais", [])
            return [
                ("Nome", item_id),
                ("Comprimento (cm)", lj.get("comprimento", "—")),
                ("Largura (cm)", lj.get("largura", "—")),
                ("Linhas verticais", len(linhas_v)),
                ("Obstáculos", len(lj.get("obstaculos", []))),
                ("Coordenadas", f"{len(lj.get('coordenadas',[]))} pts"),
            ]
        return [("N2", f"Classe '{classe}' sem ficha N2 implementada")]

    def _ficha_n3(self, vn: str) -> list:
        """Ficha N3 para LV (fichas_lv_v2.json)."""
        return self._ficha_n3_for('LV', vn)

    def _ficha_n3_for(self, classe: str, item_id: str) -> list:
        """Ficha N3 class-aware — lê Fase-4 JSON formatado para cada classe."""
        obra_dir = DADOS_OBRAS_ROOT / self._current_obra
        fase4 = obra_dir / "Fase-4_Sincronizacao"

        if classe == 'LV':
            # LV usa fichas_lv_v2 (estrutura especializada)
            entries = [f for f in self._fichas_lv_v2 if f.get('viga') == item_id]
            if not entries:
                # Fallback para JSON individual em Fase-4
                return self._ficha_fase4_json('LV', item_id, fase4 / "JSON_Vigas_Laterais")
            rows = []
            for e in entries:
                face = e.get('face', '?')
                segs = e.get('segmentos', [])
                widths = [s.get('largura_cm', '?') for s in segs]
                codes  = ['/'.join(s.get('codigos_forma', [])) for s in segs]
                rows += [
                    (f"[{face}] h_cm", e.get('h_cm', '—')),
                    (f"[{face}] b_cm", e.get('b_cm', '—')),
                    (f"[{face}] laje_sup_cm", e.get('laje_sup_cm', '—')),
                    (f"[{face}] laje_inf_cm", e.get('laje_inf_cm', '—')),
                    (f"[{face}] comprimento_cm", e.get('comprimento_cm', '—')),
                    (f"[{face}] painéis (cm)", str(widths)),
                    (f"[{face}] códigos forma", str(codes)),
                    (f"[{face}] sarrafos",
                     f"{e.get('total_sarrafos','—')} ({e.get('sarr_por_tipo',{})})"),
                    (f"[{face}] nota_face", e.get('nota_face', '—')),
                    ("---", ""),
                ]
            return rows or [("Ficha LV v2", "vazia")]

        elif classe == 'PL':
            return self._ficha_fase4_json('PL', item_id, fase4 / "JSON_Pilares")

        elif classe == 'FV':
            return self._ficha_fase4_json('FV', item_id, fase4 / "JSON_Vigas_Fundo")

        elif classe == 'LJ':
            return self._ficha_fase4_json('LJ', item_id, fase4 / "JSON_Lajes")

        return self._ficha_generic(classe, item_id)

    def _ficha_fase4_json(self, classe: str, item_id: str, json_dir: Path) -> list:
        """Lê JSON Fase-4 e formata para exibição com agrupamento semântico."""
        json_path = json_dir / f"{item_id}.json"
        if not json_path.exists():
            return [(f"JSON Fase-4 {classe}", f"não encontrado: {item_id}")]
        try:
            data = json.loads(json_path.read_text(encoding='utf-8', errors='replace'))
        except Exception as exc:
            return [("Erro leitura", str(exc)[:60])]

        meta = data.pop('_sa_meta', {})
        rows = []

        # Campos de identificação sempre primeiro
        for k in ('nome', 'numero', 'name', 'number', 'pavimento', 'floor', 'side'):
            if k in data:
                rows.append((k, str(data.pop(k))))

        # Dimensões
        rows.append(("---", ""))
        for k in ('comprimento', 'largura', 'altura', 'total_width', 'total_height',
                  'b', 'h', 'area_cm2'):
            if k in data:
                rows.append((k, str(data.pop(k))))

        # Painéis (LV/FV)
        if 'panels' in data:
            panels = data.pop('panels')
            rows.append(("---", ""))
            rows.append(("Painéis (n)", len(panels)))
            for i, p in enumerate(panels[:8]):
                w = p.get('width', '?')
                h1 = p.get('height1', '?')
                rows.append((f"Painel {i+1}", f"L={w} H={h1}"))

        # Grades
        rows.append(("---", ""))
        for k in sorted(k for k in data if k.startswith('grade_')):
            if data[k]:
                rows.append((k, str(data.pop(k))))

        # Par (parafusos)
        pars = {k: v for k, v in data.items() if k.startswith('par_') and v}
        if pars:
            rows.append(("---", ""))
            for k, v in sorted(pars.items()):
                rows.append((k, str(v)))
                data.pop(k)

        # Completude meta
        if meta:
            rows.append(("---", ""))
            rows.append(("Completude", f"{meta.get('completude_pct', '?'):.1f}%"
                         if isinstance(meta.get('completude_pct'), (int, float)) else "?"))
            rows.append(("Campos extraídos", str(len(meta.get('campos_extraidos', [])))))
            rows.append(("Campos defaulted", str(len(meta.get('campos_defaulted', [])))))

        # Resto (campos não mapeados)
        remaining = {k: v for k, v in data.items()
                     if v not in (0, 0.0, '', None, [], {})
                     and not k.startswith('h1_') and not k.startswith('larg1_')}
        if remaining:
            rows.append(("---", ""))
            for k, v in list(remaining.items())[:12]:
                rows.append((k, str(v)[:40]))

        return rows or [("(vazio)", "")]


# ──────────────────────────────────────────────────────
# Cache de sessão para Análise Geral (por obra+pavimento)
# ──────────────────────────────────────────────────────

class AnaliseGeralCache:
    """Cache em memória da Análise Geral por (obra, pavimento).
    Se o pavimento muda, o cache do pavimento anterior não é reutilizado.
    """
    def __init__(self):
        self._data: dict = {}   # (obra, pav) → qualquer dado da análise

    def has(self, obra: str, pav: str) -> bool:
        return (obra, pav) in self._data

    def get(self, obra: str, pav: str):
        return self._data.get((obra, pav))

    def set(self, obra: str, pav: str, data):
        self._data[(obra, pav)] = data

    def clear(self):
        self._data.clear()


# ──────────────────────────────────────────────────────
# Worker de Análise Geral em background
# ──────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────
# Worker de scan de labels do DXF estrutural (background)
# ──────────────────────────────────────────────────────

class DXFScanWorker(QThread):
    """Escaneia labels e entidades do DXF estrutural em background.
    Não bloqueia o main thread — substitui _scan_structural_dxf síncrono.
    Emite finished(tmp_path) com caminho para arquivo pickle temporário
    (evita STATUS_STACK_BUFFER_OVERRUN ao passar dict/list via signal no Python 3.14)."""
    finished = Signal(str)   # caminho do arquivo temp pickle, ou "" em caso de erro

    def __init__(self, dxf_path: Path):
        super().__init__()
        self._dxf_path = dxf_path

    def run(self):
        import subprocess, json, tempfile, os, pickle as _pickle
        helper = Path(__file__).parent / 'dxf_scan_worker.py'
        if not helper.exists() or not self._dxf_path.exists():
            self.finished.emit("")
            return
        try:
            result = subprocess.run(
                [sys.executable, str(helper), str(self._dxf_path)],
                capture_output=True, timeout=30
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout.decode('utf-8', errors='replace'))
                labels = {k: tuple(v) for k, v in data.get('labels', {}).items()}
                ents   = [tuple(e) for e in data.get('ents', [])]
                fd, tmp = tempfile.mkstemp(suffix='.scan.pkl', prefix='ce_')
                os.close(fd)
                with open(tmp, 'wb') as f:
                    _pickle.dump({'labels': labels, 'ents': ents}, f, protocol=4)
                self.finished.emit(tmp)
            else:
                self.finished.emit("")
        except Exception:
            self.finished.emit("")


class AnaliseGeralWorker(QThread):
    """Roda motor_fase3 / scan do DXF estrutural em background sem bloquear UI.
    Emite `finished(obra, pav, success, msg)` ao terminar.
    """
    finished = Signal(str, str, bool, str)

    def __init__(self, obra: str, pav: str, obra_dir: Path):
        super().__init__()
        self._obra    = obra
        self._pav     = pav
        self._obra_dir = obra_dir

    def run(self):
        try:
            fase3 = self._obra_dir / "Fase-3_Interpretacao_Extracao"
            # Script real de Fase-3: engenharia_reversa_dxf.py
            script = Path(__file__).parent.parent.parent.parent / "scripts" / "engenharia_reversa_dxf.py"

            if not script.exists():
                # Sem script: verifica se JSONs já existem (análise prévia)
                has_data = fase3.exists() and any(fase3.rglob("*.json"))
                if has_data:
                    self.finished.emit(self._obra, self._pav, True,
                                       "Fase-3 existente (cache de disco)")
                else:
                    self.finished.emit(self._obra, self._pav, False,
                                       "engenharia_reversa_dxf.py não encontrado")
                return

            import subprocess
            obra_path = str(self._obra_dir)
            args = [sys.executable, str(script), "--obra", obra_path]
            if self._pav:
                args += ["--pavimento", self._pav]
            result = subprocess.run(args, capture_output=True, timeout=300)
            ok  = result.returncode == 0
            if ok:
                msg = "Análise Geral (Fase-3) concluída"
            else:
                err = (result.stderr or result.stdout or b"").decode('utf-8', errors='replace')
                msg = err.strip()[-80:] or f"código {result.returncode}"
            self.finished.emit(self._obra, self._pav, ok, msg)
        except Exception as exc:
            self.finished.emit(self._obra, self._pav, False, str(exc)[:80])


# ──────────────────────────────────────────────────────
# Module principal (Tab 2)
# ──────────────────────────────────────────────────────

class ComparisonEngineModule(QWidget):
    """
    Tab 2 — Comparison Engine / Fase-8 Validação Visual.
    Layout: [Left 270px: Fase8Panel(obra/pav/scores) + NavSidebar(tree/botões)] | [TriLevelArea flex]
    CE-004: N2 DXF resolvido dinamicamente via dxf_discovery.json por obra/pav/tipo.
    """
    # CE-002/CE-005: signals propagados para main.py
    analise_geral_requested = Signal(str, str)   # obra, pav
    fase4_sync_requested    = Signal(str, str)   # obra, pav
    obra_pav_changed        = Signal(str, str)   # obra, pav — CE-005 sync bidirecional

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Painel esquerdo: Fase8 + NavSidebar dentro de QScrollArea ──
        # Conteúdo interno (sem largura fixa — deixa o scroll controlar)
        left_inner = QFrame()
        left_inner.setStyleSheet(f"background: {Colors.BG_SECONDARY};")
        left_inner.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        left_inner_lay = QVBoxLayout(left_inner)
        left_inner_lay.setContentsMargins(0, 0, 0, 0)
        left_inner_lay.setSpacing(0)

        # 1. Fase-8: seleção obra/pav + scores
        self.fase8_panel = Fase8Panel()
        self.fase8_panel.load_history()
        self.fase8_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        left_inner_lay.addWidget(self.fase8_panel)

        # 2. NavSidebar: mini-tabs + lista + botões (ocupa resto disponível)
        self.nav_sidebar = NavSidebar()
        self.nav_sidebar.item_selected.connect(self._on_item_selected)
        self.nav_sidebar.process_requested.connect(self._on_process_requested)
        self.nav_sidebar.gerar_n1_requested.connect(self._on_gerar_n1)
        self.nav_sidebar.gerar_n2_requested.connect(self._on_gerar_n2)
        self.nav_sidebar.gerar_n3_requested.connect(self._on_gerar_n3)
        self.nav_sidebar.gerar_n4_requested.connect(self._on_gerar_n4)
        self.nav_sidebar.analise_requested.connect(self._on_iniciar_analise)
        self.nav_sidebar.fase4_requested.connect(self._on_fase4_sync)
        self.nav_sidebar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_inner_lay.addWidget(self.nav_sidebar, 1)

        # Scroll vertical para o painel esquerdo completo
        left_scroll = QScrollArea()
        left_scroll.setWidget(left_inner)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFixedWidth(340)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {Colors.BG_SECONDARY};
                border: none;
                border-right: 1px solid {Colors.ACCENT_BLUE};
            }}
            QScrollBar:vertical {{
                background: {Colors.BG_DEEP}; width: 6px;
            }}
            QScrollBar::handle:vertical {{
                background: {Colors.BORDER_DEFAULT}; border-radius: 3px; min-height: 20px;
            }}
        """)

        layout.addWidget(left_scroll)

        # 3. Área central 3 níveis (flex)
        self.tri_level = TriLevelArea()
        layout.addWidget(self.tri_level, 1)

        # Conectar obra/pav da Fase8 ao TriLevelArea (CE-004)
        self.fase8_panel.cmb_obra.currentTextChanged.connect(self._on_obra_pav_changed)
        self.fase8_panel.cmb_pav.currentTextChanged.connect(self._on_obra_pav_changed)
        # Disparar carga inicial após construção (500ms delay para event loop estabilizar)
        QTimer.singleShot(500, self._on_obra_pav_changed)

        self._process        = None
        self._pending_classe = ""
        self._pending_item   = ""
        self._analise_cache  = AnaliseGeralCache()
        self._analise_worker: "AnaliseGeralWorker | None" = None
        self._retiring_analise_workers: list = []   # mantém refs até QThread terminar
        self._n1_loaded_pav  = ""   # controle: evita reload N1 quando só item muda
        self._seq_id         = 0    # sequence guard: cancela sequências N1→N2→N3 antigas

        # Setas do teclado navegam na lista mesmo com foco em outro widget
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        """Intercepta ↑/↓ globalmente para navegar na lista de itens do NavSidebar."""
        if (
            event.type() == QEvent.KeyPress
            and self.isVisible()
            and event.key() in (Qt.Key_Up, Qt.Key_Down)
        ):
            focused = QApplication.focusWidget()
            if not isinstance(focused, (QLineEdit, QTextEdit)):
                delta = -1 if event.key() == Qt.Key_Up else 1
                self.nav_sidebar.navigate(delta)
                return True
        return super().eventFilter(obj, event)

    def _on_obra_pav_changed(self, _text: str = ""):
        """Propaga mudança de obra/pav do Fase8Panel para o TriLevelArea e main.py.
        Carrega DXF limpo no N1 uma vez ao mudar pavimento (item click = só zoom).
        Também auto-dispara Análise Geral em background se não estiver em cache.
        Guard: ignora chamadas com pav vazio (durante populate do combo)."""
        try:
            obra = self.fase8_panel.cmb_obra.currentText()
            pav  = self.fase8_panel.current_pav_key
            # Guard: não processar enquanto combo está sendo populado (pav vazio = populate em andamento)
            if not obra or not pav:
                return
            # FIX: Cancela workers N2/N3 em andamento antes de mudar pav.
            # Sem isso, um DXF pesado (ex: LV STOG 6.9MB) completando após mudança de pav
            # dispara _on_loaded_file com dado stale, causando STATUS_STACK_BUFFER_OVERRUN
            # no Python 3.14 / Windows quando o resultado chega no meio da transição de estado.
            for _ci in (1, 2):
                try:
                    self.tri_level._columns[_ci].img_widget.cancel_load("— aguardando seleção —")
                except Exception:
                    pass
            self.tri_level.set_obra_pav(obra, pav)
            self.obra_pav_changed.emit(obra, pav)
            obra_dir = str(DADOS_OBRAS_ROOT / obra)
            self.nav_sidebar.set_obra(obra_dir)
            self.nav_sidebar.set_pav(pav)   # filtra lista ER pelo pavimento selecionado
            # Cancela sequência anterior de item (novo pav = novo contexto)
            self._seq_id += 1
            # Carrega DXF limpo no N1 apenas quando muda obra ou pavimento
            pav_key = f"{obra}/{pav}"
            if pav_key != self._n1_loaded_pav:
                self._n1_loaded_pav = pav_key
                # Usa QTimer para desacoplar do event loop do combo — evita race condition com workers
                QTimer.singleShot(50, lambda: self._load_n1_dxf_for_pav(obra, pav))
            # Auto-dispara análise geral se não estiver em cache
            self._auto_analise_geral(obra, pav)
        except Exception as exc:
            print(f"[CE] _on_obra_pav_changed error: {exc}")

    def _load_n1_dxf_for_pav(self, obra: str, pav: str):
        """Carrega DXF limpo do pavimento no N1 viewer (visão completa, sem bbox de item)."""
        obra_dir = DADOS_OBRAS_ROOT / obra
        n1_dxf = self.tri_level._find_n1_clean_dxf(obra_dir, pav)
        col = self.tri_level._columns[0]
        col.pipeline.reset()
        if n1_dxf and n1_dxf.exists():
            col.load_content(str(n1_dxf), None)   # None = visão completa do pavimento
            col.pipeline.set_step(0, 'ok', pav or 'pavimento')
            self.nav_sidebar.set_status(f"N1 carregado — {pav}", Colors.ACCENT_SUCCESS)
        else:
            col.img_widget.clear_image("— DXF limpo não encontrado —")
            col.pipeline.set_step(0, 'error', 'DXF limpo ausente')

    # ── Análise Geral — cache + auto-trigger ────────────────────────

    def _auto_analise_geral(self, obra: str, pav: str):
        """Dispara Análise Geral em background se (obra, pav) não estiver em cache."""
        if not obra:
            return
        if self._analise_cache.has(obra, pav):
            self.nav_sidebar.set_status(
                f"Análise Geral: cache ({pav or 'geral'})", Colors.ACCENT_SUCCESS
            )
            return
        # Descarta worker anterior sem bloquear a UI — subprocess continua em background
        # mas ignoramos o resultado (signal desconectado antes do novo worker ser criado).
        # FIX: manter ref Python viva até QThread terminar — destruir running QThread
        # no Python 3.14/Windows causa STATUS_STACK_BUFFER_OVERRUN (0xC0000409).
        if self._analise_worker and self._analise_worker.isRunning():
            old_aw = self._analise_worker
            try:
                old_aw.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            # Retirement: mesma estratégia do DXFLoadWorker
            self._retiring_analise_workers.append(old_aw)
            def _retire_aw(w=old_aw, lst=self._retiring_analise_workers):
                try:
                    lst.remove(w)
                except ValueError:
                    pass
                try:
                    w.deleteLater()
                except RuntimeError:
                    pass
            try:
                old_aw.finished.connect(_retire_aw)
            except (RuntimeError, TypeError):
                _retire_aw()
            self._analise_worker = None

        obra_dir = DADOS_OBRAS_ROOT / obra
        self.nav_sidebar.set_status("⏳ Análise Geral em andamento...", Colors.ACCENT_WARNING)
        # Sinaliza step 1 de N1 como rodando
        self.tri_level.set_pipeline_step('N1', 0, 'running', 'Processando...')

        self._analise_worker = AnaliseGeralWorker(obra, pav, obra_dir)
        self._analise_worker.finished.connect(self._on_analise_geral_done)
        self._analise_worker.start()

    def _on_analise_geral_done(self, obra: str, pav: str, success: bool, msg: str):
        self._analise_worker = None
        try:
            if success:
                self._analise_cache.set(obra, pav, {'done': True, 'msg': msg})
                self.nav_sidebar.set_status(f"✅ {msg[:40]}", Colors.ACCENT_SUCCESS)
                self.tri_level.set_pipeline_step('N1', 0, 'ok', '')
                obra_dir = DADOS_OBRAS_ROOT / obra
                if obra_dir.exists():
                    self.tri_level._load_data(obra_dir)
            else:
                self.nav_sidebar.set_status(f"❌ Análise: {msg[:40]}", Colors.ACCENT_DANGER)
                self.tri_level.set_pipeline_step('N1', 0, 'error', msg[:30])
        except RuntimeError:
            pass  # Widget deletado — ignorar

    def _on_iniciar_analise(self):
        """CE-002: Botão Análise Geral manual — força re-processamento mesmo com cache."""
        obra = self.fase8_panel.cmb_obra.currentText()
        pav  = self.fase8_panel.current_pav_key
        self.analise_geral_requested.emit(obra, pav)
        # Limpa cache e re-dispara
        self._analise_cache.clear()
        self._auto_analise_geral(obra, pav)

    # ── Handlers Gerar N1 / N2 / N3 ────────────────────────────────

    def _on_item_selected(self, classe: str, item_id: str):
        """Auto-dispara N1 → N2 → N3 em sequência ao selecionar item.
        Incrementa _seq_id para cancelar sequências anteriores pendentes nos timers.
        """
        try:
            flow = getattr(self.nav_sidebar, '_current_flow', 'estrutural')
            _ce_log(f"ITEM_SELECTED classe={classe} id={item_id} flow={flow}")
            self._seq_id += 1
            seq = self._seq_id
            self.tri_level._lbl_item.setText(f"{classe} / {item_id}")
            self.tri_level.reset_all_pipelines()
            self._run_n1_n2_n3_sequence(classe, item_id, seq)
        except Exception as exc:
            print(f"[CE] _on_item_selected error: {exc}")

    def _run_n1_n2_n3_sequence(self, classe: str, item_id: str, seq: int):
        """Roda N1 → N2 → N3 em sequência para o item selecionado.
        seq é o sequence guard — callbacks abortam se seq != self._seq_id."""
        self._on_gerar_n1(classe, item_id, auto_chain=True, seq=seq)

    def _on_gerar_n1(self, classe: str, item_id: str, auto_chain: bool = False, seq: int = -1):
        """Gerar N1: zoom no item já carregado (DXF carregado uma vez ao mudar pavimento).
        Se o DXF não estiver carregado ainda, carrega e depois dá zoom.
        seq=-1 significa chamada manual (botão), sem guard de sequência.
        Fluxo ER: N1 é N/A — propaga diretamente para N2 sem bloquear.
        """
        try:
            # Guard de sequência: aborta se outro item foi selecionado entre o timer e a execução
            if seq >= 0 and seq != self._seq_id:
                return

            obra = self.fase8_panel.cmb_obra.currentText()
            pav  = self.fase8_panel.current_pav_key
            if not obra or not item_id:
                self.nav_sidebar._enable_item_btns()
                return

            # Fluxo ER: N1 estrutural não se aplica — propaga para N2
            _flow_n1 = getattr(self.nav_sidebar, '_current_flow', 'estrutural')
            _ce_log(f"N1 flow={_flow_n1} classe={classe} id={item_id} auto_chain={auto_chain}")
            if _flow_n1 == "reverso":
                col = self.tri_level._columns[0]
                col.pipeline.reset()
                col.pipeline.set_step(0, 'ok', 'ER (N/A)')
                col.pipeline.set_step(1, 'ok', 'N/A')
                col.pipeline.set_step(2, 'ok', '')
                _ce_log(f"N1 ER shortcircuit → chaining N2")
                if auto_chain:
                    _seq = seq
                    QTimer.singleShot(50, lambda: self._on_gerar_n2(classe, item_id, auto_chain=True, seq=_seq))
                else:
                    self.nav_sidebar._enable_item_btns()
                return

            col = self.tri_level._columns[0]
            col.pipeline.reset()

            # Step 1: verifica se análise Fase 3 existe (ou está em cache)
            col.pipeline.set_step(0, 'running', 'Verificando Fase 3...')
            has_analise = self._analise_cache.has(obra, pav)
            if not has_analise:
                fase3 = DADOS_OBRAS_ROOT / obra / "Fase-3_Interpretacao_Extracao"
                has_analise = fase3.exists() and (
                    (fase3 / "Vigas" / "vigas.json").exists() or
                    any(True for _ in fase3.glob("*.json")) or
                    any(True for _ in fase3.rglob("*.json"))
                )
            if has_analise:
                col.pipeline.set_step(0, 'ok', '')
            else:
                col.pipeline.set_step(0, 'error', 'Fase 3 não encontrada')
                self.nav_sidebar.set_status("❌ N1: rode Análise Geral primeiro", Colors.ACCENT_DANGER)
                self.nav_sidebar._enable_item_btns()
                return

            # Step 2: zoom no item — sem recarregar DXF se já está carregado
            col.pipeline.set_step(1, 'running', 'Zoom no item...')
            n1_bbox = self.tri_level._get_n1_bbox_for(item_id)

            if col.img_widget.is_loaded:
                # DXF já carregado — só reposiciona viewport
                if n1_bbox:
                    col.img_widget.zoom_to_bbox(n1_bbox)
                    col.pipeline.set_step(1, 'ok', item_id)
                else:
                    # Item sem posição no DXF (scan async ainda pendente ou sem labels)
                    col.pipeline.set_step(1, 'ok', f'{item_id} (pav completo)')
            else:
                # DXF não carregado (primeira vez ou após reset) — carrega e faz zoom
                obra_dir = DADOS_OBRAS_ROOT / obra
                n1_dxf = self.tri_level._find_n1_clean_dxf(obra_dir, pav)
                if n1_dxf and n1_dxf.exists():
                    col.load_content(str(n1_dxf), n1_bbox)
                    col.pipeline.set_step(1, 'ok', item_id)
                    self._n1_loaded_pav = f"{obra}/{pav}"
                else:
                    col.pipeline.set_step(1, 'error', 'DXF limpo não encontrado')

            # Step 3: ficha N1 — class-aware (campos do Structural Analyzer)
            col.pipeline.set_step(2, 'running', '')
            col.set_ficha(self.tri_level._ficha_n1_for(classe, item_id))
            col.pipeline.set_step(2, 'ok', '')

            self.nav_sidebar.set_status(f"✅ N1 — {item_id}", Colors.ACCENT_SUCCESS)

            # Lista 1 (estrutural): N1 → N3 diretamente (N2 só responde à lista 2 / fluxo ER)
            if auto_chain:
                _seq = seq
                QTimer.singleShot(100, lambda: self._on_gerar_n3(classe, item_id, auto_chain=False, seq=_seq))
            else:
                self.nav_sidebar._enable_item_btns()

        except Exception as exc:
            print(f"[CE] _on_gerar_n1 error: {exc}")
            try:
                self.nav_sidebar._enable_item_btns()
            except Exception:
                pass

    def _on_gerar_n2(self, classe: str, item_id: str, auto_chain: bool = False, seq: int = -1):
        """Gerar N2: step 1=recorte, step 2=eng reversa, step 3=ficha.
        Fluxo reverso: usa recorte DXF individual do DB (pequeno, sem crash).
        Fluxo estrutural: usa DXF STOG completo do pavimento (comportamento original).
        """
        try:
            if seq >= 0 and seq != self._seq_id:
                return
            obra = self.fase8_panel.cmb_obra.currentText()
            pav  = self.fase8_panel.current_pav_key
            if not obra or not item_id:
                self.nav_sidebar._enable_item_btns()
                return
        except Exception as exc:
            print(f"[CE] _on_gerar_n2 early error: {exc}")
            return

        try:
            col = self.tri_level._columns[1]
            col.pipeline.reset()

            is_er_flow = (getattr(self.nav_sidebar, '_current_flow', 'estrutural') == "reverso")
            _ce_log(f"N2 is_er_flow={is_er_flow} obra={obra} classe={classe} id={item_id}")

            # Step 1: recorte N2
            col.pipeline.set_step(0, 'running', 'Localizando...')
            if is_er_flow:
                # Sempre re-consulta o DB para garantir o recorte mais recente (pós-edição)
                n2_dxf = self._get_recorte_dxf_for_er(obra, classe, item_id)
                n2_bbox = None  # vista completa do recorte
                _ce_log(f"N2 recorte_path={n2_dxf}")
            else:
                n2_dxf  = self.tri_level._find_n2_dxf(obra, pav, classe)
                n2_bbox = self.tri_level._get_n2_bbox_for(item_id, classe)

            if n2_dxf and n2_dxf.exists():
                _ce_log(f"N2 loading DXF size={n2_dxf.stat().st_size//1024}KB")
                col.load_content(str(n2_dxf), n2_bbox)
                col.pipeline.set_step(0, 'ok', Path(n2_dxf).name[:30] if n2_dxf else '')
            else:
                _ce_log(f"N2 DXF not found: {n2_dxf}")
                col.pipeline.set_step(0, 'error', 'DXF recorte não encontrado')
                if not auto_chain:
                    self.nav_sidebar._enable_item_btns()
                    return

            # Step 2: extração eng. reversa
            col.pipeline.set_step(1, 'running', 'Extraindo...')
            if is_er_flow:
                col.pipeline.set_step(1, 'ok', 'Motor ER')
            elif classe == 'LV':
                has_kb = bool(self.tri_level._kb_ents)
                col.pipeline.set_step(1, 'ok' if has_kb else 'error',
                                      f'{len(self.tri_level._kb_ents)} ents KB' if has_kb else 'KB LV vazio')
            else:
                col.pipeline.set_step(1, 'ok', f'Fase-3 ({classe})')

            # Step 3: ficha eng. reversa — class-aware
            col.pipeline.set_step(2, 'running', '')
            if is_er_flow:
                col.set_ficha(self._ficha_n2_er(obra, classe, item_id))
            else:
                col.set_ficha(self.tri_level._ficha_n2_for(classe, item_id))
            col.pipeline.set_step(2, 'ok', '')

            _ce_log(f"N2 done ok. is_er={is_er_flow} auto_chain={auto_chain}")
            self.nav_sidebar.set_status(f"✅ N2 ok — {item_id}", Colors.ACCENT_SUCCESS)

            # Fluxo ER: propaga para N4 (Robot via Ficha ER)
            if is_er_flow:
                _seq = seq
                QTimer.singleShot(50, lambda c=classe, i=item_id, s=_seq: self._on_gerar_n4(c, i, seq=s))
            elif auto_chain:
                _seq = seq
                QTimer.singleShot(100, lambda: self._on_gerar_n3(classe, item_id, auto_chain=False, seq=_seq))
            else:
                self.nav_sidebar._enable_item_btns()

        except Exception as exc:
            _ce_log(f"N2 EXCEPTION: {exc}")
            print(f"[CE] _on_gerar_n2 error: {exc}")
            try:
                self.nav_sidebar._enable_item_btns()
            except Exception:
                pass

    def _get_recorte_record(self, obra: str, db_cls: str, item_id: str) -> "tuple | None":
        """Busca o recorte mais autoritativo em reverse_eng_recortes para
        (obra, db_cls, item_id) — reflete o estado REAL salvo no Diagnostic Reverse Hub
        (pós edição/aprovação). Prioridade: 'aprovado' > 'auto_aprovado' > 'manual_sel'
        > 'manual' > 'motor'. Retorna (recorte_path, status, confidence) ou None."""
        try:
            import sqlite3
            db_path = r"D:/Agente-cad-PYSIDE/project_data.vision"
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT recorte_path, status, confidence FROM reverse_eng_recortes "
                "WHERE obra_name=? AND classe=? AND elemento_id=? ORDER BY created_at DESC",
                (obra, db_cls, item_id)
            )
            rows = cur.fetchall()
            conn.close()

            _priority = {'aprovado': 0, 'auto_aprovado': 1, 'manual_sel': 2,
                          'manual': 3, 'motor': 4}
            best = None
            for recorte_path, status, confidence in rows:
                if not recorte_path or not Path(recorte_path).exists():
                    continue
                rank = _priority.get(status, 5)
                if best is None or rank < best[3]:
                    best = (recorte_path, status, confidence, rank)
            if best is None:
                return None
            return (best[0], best[1], best[2])
        except Exception as exc:
            print(f"[CE] _get_recorte_record DB error: {exc}")
            return None

    def _extrair_ficha_motor(self, db_cls: str, item_id: str, dxf_path: str,
                              obra: str) -> "tuple[dict, float]":
        """Executa o motor reverso correto (PIL/LV/FV/LAJ) sobre o recorte DXF informado.
        Retorna (campos, confianca)."""
        import sys as _sys
        scripts_dir = str(Path(__file__).parent.parent.parent.parent / "scripts")
        if scripts_dir not in _sys.path:
            _sys.path.insert(0, scripts_dir)

        campos: dict = {}
        if db_cls == "PIL":
            from motor_reverso_pil import extrair_ficha_pilar
            campos = extrair_ficha_pilar(str(dxf_path), item_id, obra)
        elif db_cls == "LV":
            from motor_reverso_lv import extrair_ficha_lateral_viga
            campos = extrair_ficha_lateral_viga(str(dxf_path), item_id, obra)
        elif db_cls == "FV":
            from motor_reverso_fv import extrair_ficha_fundo_viga
            campos = extrair_ficha_fundo_viga(str(dxf_path), item_id, obra)
        elif db_cls == "LAJ":
            from motor_reverso_laj import extrair_ficha_laje
            campos = extrair_ficha_laje(str(dxf_path), item_id, obra)

        conf = float(campos.pop("_confianca", 0.0))
        campos.pop("_er_meta", None)
        return campos, conf

    def _format_ficha_rows(self, item_id: str, db_cls: str, campos: dict, conf: float,
                            rec_status: str, source: str) -> list:
        """Monta as linhas padrão da ficha N2 ER: Elemento/Classe/Status ER/Confiança/Origem
        + campos extraídos."""
        result = [
            ("Elemento", item_id),
            ("Classe", db_cls),
            ("Status ER", rec_status or "—"),
            ("Confiança", f"{(conf or 0)*100:.0f}%"),
            ("Origem", source),
        ]
        for k, v in campos.items():
            if k.startswith("_"):
                continue
            if isinstance(v, list):
                result.append((k, f"[{len(v)} itens]"))
            elif isinstance(v, dict):
                result.append((k, str(v)[:60]))
            else:
                result.append((k, str(v)))
        return result

    def _get_recorte_dxf_for_er(self, obra: str, classe: str, item_id: str) -> "Path | None":
        """Retorna o recorte DXF individual para o fluxo ER, refletindo o estado ATUAL
        (pós edição/aprovação) salvo no Diagnostic Reverse Hub.
        Tentativa 1: reverse_eng_recortes (mais autoritativo — recorte atual aprovado/edição).
        Tentativa 2: legado reverse_eng_fichas. Tentativa 3: disco.
        Estes são arquivos pequenos (<1MB) — seguros para carregar sem crash.
        """
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)

        # Tentativa 1: reverse_eng_recortes (recorte atual)
        record = self._get_recorte_record(obra, db_cls, item_id)
        if record:
            p = Path(record[0])
            if p.exists():
                return p

        # Tentativa 2: legado reverse_eng_fichas
        try:
            import sqlite3
            db_path = r"D:/Agente-cad-PYSIDE/project_data.vision"
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT recorte_path FROM reverse_eng_fichas "
                "WHERE obra_name=? AND classe=? AND elemento_id=?",
                (obra, db_cls, item_id)
            )
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                p = Path(row[0])
                if p.exists():
                    return p
        except Exception as exc:
            print(f"[CE] _get_recorte_dxf_for_er DB error: {exc}")

        # Tentativa 3: disco direto
        return self._find_disk_dxf_for_er(obra, db_cls, item_id)

    def _ficha_n2_er(self, obra: str, classe: str, item_id: str) -> list:
        """Ficha N2 para fluxo ER — mostra APENAS dados já salvos no DB.
        Nunca roda motor on-demand (processamento pertence ao Diagnostic Reverse Hub).
        Prioridade: reverse_eng_fichas cacheada (qualquer recorte_path) →
        info básica de reverse_eng_recortes → mensagem orientativa."""
        import json as _json
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)

        # ── Tentativa 1: recorte atual (reverse_eng_recortes) ─────────────────
        record = self._get_recorte_record(obra, db_cls, item_id)
        if record:
            recorte_path, rec_status, rec_conf = record

            # 1a: ficha cacheada em reverse_eng_fichas (aceita qualquer recorte_path salvo)
            try:
                import sqlite3
                db_path = r"D:/Agente-cad-PYSIDE/project_data.vision"
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute(
                    "SELECT campos_json, confianca, recorte_path FROM reverse_eng_fichas "
                    "WHERE obra_name=? AND classe=? AND elemento_id=? "
                    "ORDER BY ROWID DESC LIMIT 1",
                    (obra, db_cls, item_id)
                )
                row = cur.fetchone()
                conn.close()
                if row and row[0]:
                    campos_raw, conf, cached_path = row
                    campos = _json.loads(campos_raw) if campos_raw else {}
                    source = "ficha salva" if (cached_path and Path(cached_path) == Path(recorte_path)) \
                             else "ficha salva (recorte anterior)"
                    return self._format_ficha_rows(
                        item_id, db_cls, campos, conf or 0.0, rec_status, source
                    )
            except Exception as exc:
                print(f"[CE] _ficha_n2_er cache error: {exc}")

            # 1b: sem ficha processada — mostra info básica do recorte salvo (sem motor)
            return self._format_ficha_rows(
                item_id, db_cls, {}, rec_conf or 0.0,
                rec_status,
                f"recorte salvo · processe no Diagnostic Hub para gerar ficha"
            )

        # ── Tentativa 2: legado — reverse_eng_fichas por elemento_id ──────────
        try:
            import sqlite3
            db_path = r"D:/Agente-cad-PYSIDE/project_data.vision"
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT campos_json, confianca, status FROM reverse_eng_fichas "
                "WHERE obra_name=? AND classe=? AND elemento_id=?",
                (obra, db_cls, item_id)
            )
            row = cur.fetchone()
            conn.close()
            if row:
                campos_raw, conf, status = row
                campos = _json.loads(campos_raw) if campos_raw else {}
                return self._format_ficha_rows(
                    item_id, db_cls, campos, conf or 0.0,
                    status, "ficha cacheada (legado)"
                )
        except Exception as exc:
            print(f"[CE] _ficha_n2_er DB error: {exc}")

        # Não há registro no DB — não roda motor on-demand (processamento é do Diagnostic Hub)
        return [
            ("Elemento", item_id),
            ("Classe",   db_cls),
            ("Status",   "—"),
            ("Info",     "Sem ficha salva — processe no Diagnostic Hub"),
        ]

    def _find_disk_dxf_for_er(self, obra_name: str, classe: str, elem_id: str) -> "Path | None":
        """Encontra o melhor DXF no disco para (obra, classe, elem_id).
        Prefere arquivo _sel_ sobre _motor_. Retorna None se não encontrar."""
        import re as _re, unicodedata as _ucd
        _cls_folder = {"PIL": "PL", "LV": "LV", "FV": "FV", "LAJ": "LJ"}
        folder_cls = _cls_folder.get(classe, classe)

        try:
            recortes_dir = (DADOS_OBRAS_ROOT / obra_name /
                            "Fase-2_Triagem" / "recortes_reversos")
            if not recortes_dir.exists():
                return None

            def _norm(s: str) -> str:
                t = _ucd.normalize('NFKD', s)
                return ''.join(c for c in t if not _ucd.combining(c)).upper()

            best_sel: "Path | None" = None
            best_motor: "Path | None" = None
            pattern = _re.compile(
                rf'^{_re.escape(classe)}_{_re.escape(elem_id)}_(motor|sel)_\d+$',
                _re.IGNORECASE
            )
            for folder in recortes_dir.iterdir():
                if not folder.is_dir():
                    continue
                fn_norm = _norm(folder.name)
                if f'- {folder_cls} -' not in fn_norm and f'- {folder_cls}.' not in fn_norm:
                    continue
                for dxf in folder.glob("*.dxf"):
                    m = pattern.match(dxf.stem)
                    if not m:
                        continue
                    tag = m.group(1).lower()
                    if tag == 'sel':
                        best_sel = dxf
                    elif best_motor is None:
                        best_motor = dxf
            return best_sel or best_motor
        except Exception:
            return None

    def _on_gerar_n3(self, classe: str, item_id: str, auto_chain: bool = False, seq: int = -1):
        """Gerar N3: step 1=conversão, step 2=ficha, step 3=gerar DXF + carregar."""
        try:
            if seq >= 0 and seq != self._seq_id:
                return
            obra = self.fase8_panel.cmb_obra.currentText()
            if not obra or not item_id:
                self.nav_sidebar._enable_item_btns()
                return
        except Exception as exc:
            print(f"[CE] _on_gerar_n3 early error: {exc}")
            return

        try:
            col = self.tri_level._columns[2]
            col.pipeline.reset()
            col.pipeline.set_step(0, 'running', 'Convertendo...')

            self._pending_classe = classe
            self._pending_item   = item_id
            col.pipeline.set_step(0, 'ok', '')

            col.pipeline.set_step(1, 'running', 'Preenchendo ficha...')
            obra_dir = DADOS_OBRAS_ROOT / obra
            n3_dxf   = self.tri_level._find_n3_dxf(obra_dir, classe, item_id)
            col.set_ficha(self.tri_level._ficha_n3_for(classe, item_id))
            col.pipeline.set_step(1, 'ok', '')

            col.pipeline.set_step(2, 'running', 'Gerando DXF...')
            if n3_dxf and n3_dxf.exists():
                col.load_content(str(n3_dxf), None)
                col.pipeline.set_step(2, 'ok', 'DXF existente')
                self.nav_sidebar.set_status(f"✅ N3 ok — {item_id}", Colors.ACCENT_SUCCESS)
                self.nav_sidebar._enable_item_btns()
            else:
                self._start_n3_generation(classe, item_id, col)

        except Exception as exc:
            print(f"[CE] _on_gerar_n3 error: {exc}")
            try:
                self.nav_sidebar._enable_item_btns()
            except Exception:
                pass

    def _start_n3_generation(self, classe: str, item_id: str, col):
        """Executa o script gerador N3 correto por classe via QProcess."""
        if self._process and self._process.state() == QProcess.Running:
            self.nav_sidebar.set_status("Já processando N3...", Colors.ACCENT_WARNING)
            self.nav_sidebar._enable_item_btns()
            return

        script_name = _N3_SCRIPTS.get(classe)
        if not script_name:
            col.pipeline.set_step(2, 'error', f'Sem script para {classe}')
            self.nav_sidebar.set_status(f"❌ Sem script N3 para classe {classe}", Colors.ACCENT_DANGER)
            self.nav_sidebar._enable_item_btns()
            return

        script = SCRIPTS_DIR / script_name
        if not script.exists():
            col.pipeline.set_step(2, 'error', 'Script não encontrado')
            self.nav_sidebar.set_status(f"❌ {script_name} não encontrado", Colors.ACCENT_DANGER)
            self.nav_sidebar._enable_item_btns()
            return

        obra = self.fase8_panel.cmb_obra.currentText()
        obra_dir = str(DADOS_OBRAS_ROOT / obra)

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_proc_out)
        self._process.finished.connect(
            lambda code, _: self._on_n3_gen_done(code, col, classe, item_id)
        )
        args = [str(script), "--obra", obra_dir, "--item", item_id]
        self._process.start(sys.executable, args)

    def _on_n3_gen_done(self, code: int, col, classe: str, item_id: str):
        try:
            obra_dir = DADOS_OBRAS_ROOT / self.fase8_panel.cmb_obra.currentText()
        except RuntimeError:
            # Widget C++ já deletado (usuário navegou para outra aba durante geração)
            return
        try:
            n3_dxf = self.tri_level._find_n3_dxf(obra_dir, classe, item_id)
            if code == 0 and n3_dxf and n3_dxf.exists():
                col.load_content(str(n3_dxf), None)
                col.pipeline.set_step(2, 'ok', '')
                col.set_ficha(self.tri_level._ficha_n3_for(classe, item_id))
                self.nav_sidebar.set_status(f"✅ N3 gerado — {item_id}", Colors.ACCENT_SUCCESS)
            else:
                col.pipeline.set_step(2, 'error', f'código {code}')
                self.nav_sidebar.set_status(f"❌ N3 erro código {code}", Colors.ACCENT_DANGER)
            self.tri_level.set_processing(False)
            self.nav_sidebar.refresh_tree()
            self.nav_sidebar._enable_item_btns()
        except RuntimeError:
            pass  # Widget deletado — ignorar silenciosamente

    def _on_gerar_n4(self, classe: str, item_id: str, seq: int = -1):
        """Gerar N4: ficha ER → temp JSON → script robô → DXF em Fase-6/n4/.
        Option B: DXF independente do N3, gerado com dados da ficha ER (motor reverso N2).
        Chamado automaticamente após N2 no fluxo ER, ou manualmente via botão ▶ N4."""
        try:
            if seq >= 0 and seq != self._seq_id:
                return
            obra = self.fase8_panel.cmb_obra.currentText()
            if not obra or not item_id:
                self.nav_sidebar._enable_item_btns()
                return
        except Exception as exc:
            print(f"[CE] _on_gerar_n4 early error: {exc}")
            return

        try:
            col = self.tri_level._columns[3]
            col.pipeline.reset()

            # Step 1: obter ficha ER completa do motor reverso
            col.pipeline.set_step(0, 'running', 'Lendo ficha ER...')
            _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
            db_cls = _cls_map.get(classe, classe)
            er_ficha = self._get_er_ficha_dict(obra, classe, item_id)
            col.set_ficha(self._ficha_rows_from_dict(er_ficha, item_id, db_cls))
            col.pipeline.set_step(0, 'ok', '')

            # Step 2: verificar script robô
            col.pipeline.set_step(1, 'running', 'Verificando script...')
            script_name = _N3_SCRIPTS.get(classe)
            if not script_name:
                col.pipeline.set_step(1, 'error', f'Sem script para {classe}')
                self.nav_sidebar._enable_item_btns()
                return
            script = SCRIPTS_DIR / script_name
            if not script.exists():
                col.pipeline.set_step(1, 'error', 'Script não encontrado')
                self.nav_sidebar._enable_item_btns()
                return
            col.pipeline.set_step(1, 'ok', script_name[:20])

            # Step 3: DXF existente ou gerar via temp JSON
            col.pipeline.set_step(2, 'running', 'Procurando DXF...')
            obra_dir = DADOS_OBRAS_ROOT / obra
            n4_dxf = self._find_n4_dxf_strict(obra_dir, classe, item_id)
            if n4_dxf and n4_dxf.exists():
                col.load_content(str(n4_dxf), None)
                col.pipeline.set_step(2, 'ok', Path(n4_dxf).name[:25])
                self.nav_sidebar.set_status(f"✅ N4 ok — {item_id}", Colors.ACCENT_SUCCESS)
                self.nav_sidebar._enable_item_btns()
            else:
                # Gera DXF via temp JSON (Option B)
                col.pipeline.set_step(2, 'running', 'Gerando via robô...')
                self._start_n4_generation(classe, item_id, er_ficha, obra_dir, script, col)

        except Exception as exc:
            print(f"[CE] _on_gerar_n4 error: {exc}")
            try:
                self.nav_sidebar._enable_item_btns()
            except Exception:
                pass

    def _get_er_ficha_dict(self, obra: str, classe: str, item_id: str) -> dict:
        """Retorna a ficha ER como dicionário (para passar ao script robô).
        Tenta DB primeiro, depois motor on-demand no DXF do disco."""
        import json as _json
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)
        # Tentativa 1: DB
        try:
            import sqlite3
            conn = sqlite3.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            cur = conn.cursor()
            cur.execute(
                "SELECT campos_json FROM reverse_eng_fichas "
                "WHERE obra_name=? AND classe=? AND elemento_id=?",
                (obra, db_cls, item_id)
            )
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                return _json.loads(row[0])
        except Exception:
            pass
        # Tentativa 2: motor on-demand
        try:
            import sys as _sys
            scripts_dir = str(Path(__file__).parent.parent.parent.parent / "scripts")
            if scripts_dir not in _sys.path:
                _sys.path.insert(0, scripts_dir)
            dxf_path = self._find_disk_dxf_for_er(obra, db_cls, item_id)
            if dxf_path:
                if db_cls == "PIL":
                    from motor_reverso_pil import extrair_ficha_pilar
                    return extrair_ficha_pilar(str(dxf_path), item_id, obra)
                elif db_cls == "LV":
                    from motor_reverso_lv import extrair_ficha_lateral_viga
                    return extrair_ficha_lateral_viga(str(dxf_path), item_id, obra)
                elif db_cls == "FV":
                    from motor_reverso_fv import extrair_ficha_fundo_viga
                    return extrair_ficha_fundo_viga(str(dxf_path), item_id, obra)
                elif db_cls == "LAJ":
                    from motor_reverso_laj import extrair_ficha_laje
                    return extrair_ficha_laje(str(dxf_path), item_id, obra)
        except Exception:
            pass
        return {}

    def _ficha_rows_from_dict(self, campos: dict, item_id: str, db_cls: str) -> list:
        """Converte dict da ficha ER em lista de tuplas para set_ficha()."""
        conf = float(campos.get("_confianca", 0.0))
        result = [
            ("Elemento", item_id),
            ("Classe", db_cls),
            ("Status ER", campos.get("_er_meta", {}).get("source", "—") if isinstance(campos.get("_er_meta"), dict) else "—"),
            ("Confiança", f"{conf*100:.0f}%"),
        ]
        for k, v in campos.items():
            if k.startswith("_"):
                continue
            if isinstance(v, list):
                result.append((k, f"[{len(v)} itens]"))
            elif isinstance(v, dict):
                result.append((k, str(v)[:60]))
            else:
                result.append((k, str(v)))
        return result

    def _find_n4_dxf_strict(self, obra_dir: Path, classe: str, item_id: str) -> "Path | None":
        """Procura APENAS em Fase-6/n4/ — sem fallback para N3."""
        prefixes = {"PL": "PL_preview_", "LV": "LV_preview_",
                    "FV": "FV_preview_", "LJ": "LJ_preview_"}
        pfx = prefixes.get(classe, f"{classe}_preview_")
        n4_dir = obra_dir / "Fase-6_Execucao_CAD" / "n4"
        for cand in [item_id, item_id.split('_')[0] if '_' in item_id else item_id]:
            p = n4_dir / f"{pfx}{cand}.dxf"
            if p.exists():
                return p
        return None

    def _start_n4_generation(self, classe: str, item_id: str, er_ficha: dict,
                              obra_dir: Path, script: Path, col):
        """Option B: escreve ficha ER como temp JSON em Fase-4, roda script robô,
        move output para Fase-6/n4/, carrega no viewer N4."""
        if self._process and self._process.state() == QProcess.Running:
            self.nav_sidebar.set_status("Já processando...", Colors.ACCENT_WARNING)
            self.nav_sidebar._enable_item_btns()
            return

        import json as _json, time as _time
        _cls_json_dirs = {
            "PL": ("Fase-4_Sincronizacao", "JSON_Pilares"),
            "LV": ("Fase-4_Sincronizacao", "JSON_Vigas_Laterais"),
            "FV": ("Fase-4_Sincronizacao", "JSON_Vigas_Fundo"),
            "LJ": ("Fase-4_Sincronizacao", "JSON_Lajes"),
        }
        _prefixes = {"PL": "PL_preview_", "LV": "LV_preview_",
                     "FV": "FV_preview_", "LJ": "LJ_preview_"}
        _cls_id_pfx = {"PL": "P", "LV": "V", "FV": "V", "LJ": "L"}

        fase_parts = _cls_json_dirs.get(classe)
        if not fase_parts:
            col.pipeline.set_step(2, 'error', f'Classe {classe} sem mapeamento')
            self.nav_sidebar._enable_item_btns()
            return

        json_dir = obra_dir / fase_parts[0] / fase_parts[1]
        json_dir.mkdir(parents=True, exist_ok=True)

        # Nome temporário único: ex V1_n4er_A.json (para LV) ou P1_n4er.json (para PL)
        ts_tag  = f"n4er"
        pfx     = _cls_id_pfx.get(classe, "X")

        # Normaliza item_id base (sem sufixo _A/_B)
        import re as _re
        base_id = _re.sub(r'[_\.]([AB])$', '', item_id, flags=_re.IGNORECASE)
        temp_item = f"{base_id}_{ts_tag}"

        # Prepara dados para o JSON: remove campos internos, garante campos obrigatórios
        ficha_clean = {k: v for k, v in er_ficha.items() if not k.startswith('_')}
        ficha_clean.setdefault('name',     item_id)
        ficha_clean.setdefault('floor',    'Pavimento')
        ficha_clean.setdefault('panels',   [])
        ficha_clean.setdefault('holes',    [])
        ficha_clean.setdefault('pillar_left',  {'active': False, 'width': 0.0, 'length': 0.0})
        ficha_clean.setdefault('pillar_right', {'active': False, 'width': 0.0, 'length': 0.0})
        ficha_clean.setdefault('sarrafo_left_id',  0)
        ficha_clean.setdefault('sarrafo_right_id', 0)

        # Para LV: escreve _A.json e _B.json (script lê apenas *_A.json)
        temp_files: list[Path] = []
        if classe == "LV":
            for face in ("A", "B"):
                fc = {**ficha_clean, 'side': face}
                p  = json_dir / f"{temp_item}_{face}.json"
                p.write_text(_json.dumps(fc, ensure_ascii=False, indent=2), encoding='utf-8')
                temp_files.append(p)
        elif classe == "FV":
            # FV: {elem_id}_fundo.json
            p = json_dir / f"{temp_item}_fundo.json"
            p.write_text(_json.dumps(ficha_clean, ensure_ascii=False, indent=2), encoding='utf-8')
            temp_files.append(p)
        else:
            # PL, LJ: {item_id}.json
            p = json_dir / f"{temp_item}.json"
            p.write_text(_json.dumps(ficha_clean, ensure_ascii=False, indent=2), encoding='utf-8')
            temp_files.append(p)

        # Diretório de output exclusivo N4
        out_dir = obra_dir / "Fase-6_Execucao_CAD" / "n4"
        out_dir.mkdir(parents=True, exist_ok=True)

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_proc_out)

        pfx_out = _prefixes.get(classe, f"{classe}_preview_")

        def _on_done(code, _sig,
                     _temp_files=temp_files, _out_dir=out_dir,
                     _pfx_out=pfx_out, _temp_item=temp_item,
                     _item_id=item_id, _classe=classe, _col=col):
            # Remove JSONs temporários
            for tf in _temp_files:
                try:
                    tf.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                # Procura DXF gerado (nome: {PFX}{temp_item}.dxf ou variante)
                fase6 = obra_dir / "Fase-6_Execucao_CAD"
                generated = None
                for cand in [f"{_pfx_out}{_temp_item}.dxf",
                              f"{_pfx_out}{_temp_item}_A.dxf"]:
                    p = fase6 / cand
                    if p.exists():
                        generated = p
                        break
                if generated is None:
                    # Fallback: qualquer DXF recém-criado com temp_item no nome
                    for p in fase6.glob(f"*{_temp_item}*.dxf"):
                        generated = p
                        break

                if code == 0 and generated and generated.exists():
                    # Move para pasta n4 com nome canônico
                    canon = _out_dir / f"{_pfx_out}{_item_id}.dxf"
                    generated.replace(canon)
                    _col.load_content(str(canon), None)
                    _col.pipeline.set_step(2, 'ok', canon.name[:25])
                    self.nav_sidebar.set_status(f"✅ N4 gerado — {_item_id}", Colors.ACCENT_SUCCESS)
                else:
                    _col.pipeline.set_step(2, 'error', f'código {code}')
                    self.nav_sidebar.set_status(f"❌ N4 erro — {_item_id}", Colors.ACCENT_DANGER)

                self.tri_level.set_processing(False)
                self.nav_sidebar._enable_item_btns()
            except RuntimeError:
                pass

        self._process.finished.connect(_on_done)
        args = [str(script), "--obra", str(obra_dir), "--item", temp_item]
        self._process.start(sys.executable, args)
        self.nav_sidebar.set_status(f"⏳ N4 gerando via robô — {item_id}...", Colors.ACCENT_WARNING)

    def _on_fase4_sync(self):
        """CE-002: Dispara motor_fase4.py (N3) para obra/pavimento atual.
        Após conclusão: carrega N1 (DXF estrutural do pavimento) automaticamente.
        Se há item selecionado no NavSidebar: zoom centrado no item.
        Se não: exibe DXF completo do pavimento em N1."""
        obra = self.fase8_panel.cmb_obra.currentText()
        pav  = self.fase8_panel.current_pav_key
        if not obra:
            return
        self.nav_sidebar.set_status("⏳ Fase 4 — sincronizando...", Colors.ACCENT_WARNING)
        script = Path(__file__).parent.parent.parent.parent / "scripts" / "motor_fase4.py"
        if not script.exists():
            self.nav_sidebar.set_status(f"motor_fase4.py não encontrado", Colors.ACCENT_DANGER)
            return
        self.fase4_sync_requested.emit(obra, pav)
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.MergedChannels)
        args = [str(script), "--obra", obra]
        if pav:
            args += ["--pavimento", pav]

        def _on_fase4_finished(code, _):
            try:
                if code == 0:
                    self.nav_sidebar.set_status("✅ Fase 4 concluída — carregando N1...", Colors.ACCENT_SUCCESS)
                    self._load_n1_after_fase4(obra)
                else:
                    self.nav_sidebar.set_status(f"❌ Fase 4 erro (código {code})", Colors.ACCENT_DANGER)
            except RuntimeError:
                pass

        proc.finished.connect(_on_fase4_finished)
        proc.start(sys.executable, args)

    def _load_n1_after_fase4(self, obra: str):
        """Carrega DXF estrutural (N1) após Fase 4 concluir.
        - Se item selecionado: zoom centrado no item (bbox).
        - Se não: DXF completo do pavimento."""
        obra_dir = DADOS_OBRAS_ROOT / obra
        n1_dxf = self.tri_level._find_n1_dxf(obra_dir)
        if not n1_dxf or not n1_dxf.exists():
            self.nav_sidebar.set_status("N1: DXF estrutural não encontrado", Colors.TEXT_DIM)
            return

        col = self.tri_level._columns[0]
        col.pipeline.reset()

        classe  = self.nav_sidebar._selected_classe
        item_id = self.nav_sidebar._selected_item

        if item_id:
            # Zoom centrado no item selecionado
            n1_bbox = self.tri_level._get_n1_bbox_for(item_id)
            col.load_content(str(n1_dxf), n1_bbox)
            col.pipeline.set_step(0, 'ok', '')
            col.pipeline.set_step(1, 'ok', item_id)
            col.set_ficha(self.tri_level._ficha_n1_for(classe, item_id))
            col.pipeline.set_step(2, 'ok', '')
            self.nav_sidebar.set_status(f"N1 ✅ {item_id} — DXF estrutural", Colors.ACCENT_SUCCESS)
        else:
            # Sem item selecionado: exibe pavimento completo
            col.load_content(str(n1_dxf), None)
            col.pipeline.set_step(0, 'ok', '')
            col.pipeline.set_step(1, 'ok', 'pavimento completo')
            self.nav_sidebar.set_status("N1 ✅ DXF estrutural carregado", Colors.ACCENT_SUCCESS)

    def _on_process_requested(self, classe: str, item_id: str):
        """'Gerar todos N1,2,3' — gera DXFs para toda a classe de uma obra."""
        if self._process and self._process.state() == QProcess.Running:
            self.nav_sidebar.set_status("Já processando...", Colors.ACCENT_WARNING)
            return

        script_name = _N3_SCRIPTS.get(classe)
        if not script_name:
            self.nav_sidebar.set_status(f"Sem script N3 para classe {classe}", Colors.ACCENT_DANGER)
            self.nav_sidebar.btn_process.setEnabled(True)
            self.nav_sidebar.btn_process_all.setEnabled(True)
            return

        script = SCRIPTS_DIR / script_name
        if not script.exists():
            self.nav_sidebar.set_status(f"Script não encontrado: {script_name}", Colors.ACCENT_DANGER)
            self.nav_sidebar.btn_process.setEnabled(True)
            self.nav_sidebar.btn_process_all.setEnabled(True)
            return

        obra = self.fase8_panel.cmb_obra.currentText()
        obra_dir = str(DADOS_OBRAS_ROOT / obra)
        self._pending_classe = classe
        self._pending_item   = item_id

        self.nav_sidebar.set_status(f"Gerando {classe} N3...", Colors.ACCENT_WARNING)
        self.tri_level.set_processing(True)

        args = [str(script), "--obra", obra_dir]
        if item_id and item_id != "ALL":
            args += ["--item", item_id]

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_proc_out)
        self._process.finished.connect(self._on_proc_done)
        self._process.start(sys.executable, args)

    def _on_proc_out(self):
        try:
            raw  = bytes(self._process.readAllStandardOutput())
            text = raw.decode('utf-8', errors='replace').strip()
            if text:
                last = text.splitlines()[-1]
                self.nav_sidebar.set_status(last[:50], Colors.TEXT_SECONDARY)
        except RuntimeError:
            pass

    def _on_proc_done(self, code, _):
        try:
            self.tri_level.set_processing(False)
            self.nav_sidebar.btn_process.setEnabled(True)
            self.nav_sidebar.btn_process_all.setEnabled(True)
            self.nav_sidebar.refresh_tree()
            if code == 0:
                self.nav_sidebar.set_status("Processado com sucesso!", Colors.ACCENT_SUCCESS)
                pending = self._pending_item
                classe  = self._pending_classe
                if pending and pending != "ALL":
                    # Usa sequência nova para carregar o item processado
                    self._on_item_selected(classe, pending)
                elif pending == "ALL" and VIGAS_LV_LIST:
                    self._on_item_selected("LV", VIGAS_LV_LIST[0])
            else:
                self.nav_sidebar.set_status(f"Erro (código {code})", Colors.ACCENT_DANGER)
        except Exception as exc:
            print(f"[CE] _on_proc_done error: {exc}")

    def set_database(self, db, project_id: str = ''):
        self.fase8_panel.set_database(db, project_id)
