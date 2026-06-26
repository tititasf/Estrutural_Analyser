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
    QListWidget, QListWidgetItem, QApplication, QLineEdit, QDialog,
)
from PySide6.QtCore import Qt, QProcess, Signal, QRect, QRectF, QPointF, QThread, QObject, QTimer, QEvent
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPainterPath, QPixmap, QTransform

from src.ui.components.organisms import DualCanvasManager

from src.ui.theme import Colors

# ── Helpers LV (acesso por todas as classes do módulo) ─────────────────────
import re as _lv_re

def _lv_strip_pp(item_id: str) -> str:
    """'V301_A_Para' → 'V301_A'"""
    return _lv_re.sub(r'_(Para|Passa)$', '', str(item_id), flags=_lv_re.IGNORECASE)

def _lv_elem_id(item_id: str) -> str:
    """'V301_A_Para' → 'V301' (sem face, sem pp)"""
    clean = _lv_re.sub(r'_(Para|Passa)$', '', str(item_id), flags=_lv_re.IGNORECASE)
    return _lv_re.sub(r'[_\.][AB]$', '', clean)

def _lv_pp_from_id(item_id: str) -> str:
    """'V301_A_Para' → 'para'"""
    m = _lv_re.search(r'_(Para|Passa)$', str(item_id), _lv_re.IGNORECASE)
    return m.group(1).lower() if m else ""

def _lv_stem_to_display(stem: str, para_passa: str = "") -> str:
    """'V10_A' → 'LV-V10.A';  com para_passa='para' → 'LV-V10.A-Para'"""
    m = _lv_re.match(r'^(V\d+[A-Z]?)_([AB])$', stem, _lv_re.IGNORECASE)
    if m:
        display = f"LV-{m.group(1).upper()}.{m.group(2).upper()}"
    else:
        display = f"LV-{stem}" if not stem.startswith("LV-") else stem
    if para_passa in ("para", "passa"):
        display = f"{display}-{para_passa.capitalize()}"
    return display

def _lv_base_from_stem(stem: str) -> str:
    """'V10_A' → 'V10'"""
    m = _lv_re.match(r'^(V\d+[A-Z]?)_[AB]$', stem, _lv_re.IGNORECASE)
    return m.group(1).upper() if m else stem

# ───────────────────────────────────────────────────────────────────────────

class DXFVectorView(QWidget):
    ready = Signal()
    def __init__(self, bg: str = Colors.BG_DEEP, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.canvas = CADCanvas()
        
        # Oculta a toolbar padrão do CADCanvas para ficar igual ao viewer antigo
        if hasattr(self.canvas, 'toolbar_layout'):
            # This is tricky, CADCanvas doesn't expose toolbar easily, but we can just use the canvas.
            pass
            
        self.layout.addWidget(self.canvas)
        self._dxf_bbox = None
        self._bg = bg
        self._highlight_bbox = None
        self._highlight_points = None
        self._is_loaded = False
        
        # Configuração de fundo
        self.canvas.setStyleSheet(f"background: {bg}; border: none;")

    def load_dxf(self, dxf_path, bbox=None):
        if not dxf_path:
            self.clear_image("Sem DXF")
            self.ready.emit()
            return
            
        try:
            # Em comparison engine, geralmente queremos destacar a cor original
            self.canvas.add_dxf_entities({}, source_dxf_path=dxf_path, color_override=None)
            self._is_loaded = True
            
            # Tentar fazer zoom se bbox foi fornecida
            if bbox:
                self.zoom_to_bbox(bbox)
        except Exception as e:
            print(f"Error loading DXF in DXFVectorView wrapper: {e}")
            
        self.ready.emit()

    def zoom_to_bbox(self, bbox):
        if not bbox or not self._is_loaded: return
        self._dxf_bbox = bbox
        
        x0, y0, x1, y1 = bbox
        # O CADCanvas gerencia QGraphicsScene, o sistema de coordenadas é (x, -y)
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        from PySide6.QtCore import QRectF
        rect = QRectF(x0, -y1, w, h)
        
        # Margem de 10%
        margin_x = w * 0.1
        margin_y = h * 0.1
        rect.adjust(-margin_x, -margin_y, margin_x, margin_y)
        
        from PySide6.QtCore import Qt
        self.canvas.fitInView(rect, Qt.KeepAspectRatio)

    def set_highlight_bbox(self, bbox):
        self._highlight_bbox = bbox
        if not bbox: return
        # Remove old highlight
        if hasattr(self, '_h_rect'):
            self.canvas.scene.removeItem(self._h_rect)
            
        x0, y0, x1, y1 = bbox
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        from PySide6.QtCore import QRectF
        rect = QRectF(x0, -y1, w, h)
        
        from PySide6.QtWidgets import QGraphicsRectItem
        from PySide6.QtGui import QPen, QColor
        self._h_rect = QGraphicsRectItem(rect)
        self._h_rect.setPen(QPen(QColor(0, 255, 255, 200), 2)) # Cyan
        self.canvas.scene.addItem(self._h_rect)

    def set_highlight_geometry(self, points):
        self._highlight_points = points
        if not points: return
        
        # Remove old highlight
        if hasattr(self, '_h_path'):
            self.canvas.scene.removeItem(self._h_path)
            
        from PySide6.QtGui import QPainterPath, QPen, QColor
        from PySide6.QtCore import QPointF
        from PySide6.QtWidgets import QGraphicsPathItem
        
        path = QPainterPath()
        if len(points) > 0:
            path.moveTo(points[0][0], -points[0][1])
            for pt in points[1:]:
                path.lineTo(pt[0], -pt[1])
                
        self._h_path = QGraphicsPathItem(path)
        self._h_path.setPen(QPen(QColor(0, 255, 255, 200), 2))
        self.canvas.scene.addItem(self._h_path)

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def clear_image(self, msg: str = "sem DXF"):
        self.canvas.scene.clear()
        self._is_loaded = False
        if hasattr(self, '_h_rect'): del self._h_rect
        if hasattr(self, '_h_path'): del self._h_path

    def cancel_load(self, msg: str = "cancelado"):
        self.clear_image(msg)

from src.ui.theme import Colors, Fonts, Radius, Semantic
from src.core.item_attention_store import (
    has_attention, load_attention, save_attention, save_human_validation, is_human_validated,
    save_para_passa, load_para_passa,
)

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
    ("N5", "Montagem e unificacao dos N3", "#263238", "#00bcd4", "N5 - consolida previews N3\n1 DXF final por classe suportada", 'dxf'),
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
_MAX_PATH_OPS   = 999999   # paths/lines
_MAX_FILL_OPS   = 999999    # HATCH fills — muito pesados
_MAX_TEXT_OPS   = 999999    # textos
_MAX_INSERT_OPS = 999999    # blocos expandidos

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
        """Cancela: sinaliza flag. O loop de polling no run() detecta e mata o
        subprocess imediatamente — sem race condition pois kill ocorre na mesma
        thread que chama poll() (worker thread), não na main thread."""
        self._cancelled[0] = True

    def _emit_ops_temp(self, ops):
        import os, pickle, tempfile
        fd, tmp_path = tempfile.mkstemp(suffix='.dxfops.pkl', prefix='ce_')
        os.close(fd)
        with open(tmp_path, 'wb') as f:
            pickle.dump(ops, f, protocol=4)
        self.loaded.emit(tmp_path)

    def run(self):
        import subprocess, json, pickle, time as _time, tempfile as _tempfile

        if self._cancelled[0]:
            return

        # Guard de tamanho rápido — sem subprocess para arquivos >_MAX_DXF_MB
        try:
            size_mb = self._dxf_path.stat().st_size / 1024 / 1024
            if size_mb > _MAX_DXF_MB:
                self._emit_ops_temp([('too_large', None, size_mb)])
                return
        except Exception:
            pass

        if self._cancelled[0]:
            return

        # Executar ezdxf em subprocess isolado — sem PySide6, sem GC conflict
        bbox_arg = json.dumps(list(self._bbox)) if self._bbox else 'null'
        _deadline = _time.monotonic() + 120
        stdout_file = None
        stderr_file = None
        try:
            # stdout=PIPE deadlocka quando o pickle do helper passa do buffer
            # do pipe. Arquivo temporario deixa o filho terminar normalmente.
            stdout_file = _tempfile.TemporaryFile()
            stderr_file = _tempfile.TemporaryFile()
            self._proc = subprocess.Popen(
                [sys.executable, str(self._HELPER),
                 str(self._dxf_path), bbox_arg],
                stdout=stdout_file,
                stderr=stderr_file,
            )
            # Polling loop: verifica _cancelled a cada 50ms — permite kill imediato
            # ao mudar de item, sem acumular subprocessos zumbis na memória.
            while True:
                rc_poll = self._proc.poll()
                if rc_poll is not None:
                    break
                if self._cancelled[0]:
                    try:
                        self._proc.kill()
                        self._proc.wait(timeout=2)
                    except Exception:
                        pass
                    self._proc = None
                    return
                if _time.monotonic() > _deadline:
                    try:
                        self._proc.kill()
                        self._proc.wait(timeout=2)
                    except Exception:
                        pass
                    self._proc = None
                    if not self._cancelled[0]:
                        self.failed.emit('Timeout ao carregar DXF (>120s)')
                    return
                _time.sleep(0.05)
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read()
            stderr = stderr_file.read()
            rc = self._proc.returncode
            self._proc = None
        except Exception as e:
            self._proc = None
            if not self._cancelled[0]:
                self.failed.emit(f'Subprocess error: {e}')
            return
        finally:
            try:
                if stdout_file:
                    stdout_file.close()
            except Exception:
                pass
            try:
                if stderr_file:
                    stderr_file.close()
            except Exception:
                pass

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
            try:
                self._emit_ops_temp(ops)
            except Exception as e:
                self.failed.emit(f'Serialização temp falhou: {e}')



from src.ui.canvas import CADCanvas

class _OldDXFVectorView(QWidget):

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
        self._highlight_bbox = None
        self._highlight_points = None

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

    def set_highlight_bbox(self, bbox):
        self._highlight_bbox = bbox
        self._highlight_points = None
        self.update()

    def set_highlight_geometry(self, points):
        self._highlight_points = points or None
        self._highlight_bbox = None
        self.update()

    @property
    def is_loaded(self) -> bool:
        """True se há DXF carregado (ops ou pixmap disponíveis)."""
        return bool(self._ops or self._pixmap)

    def clear_image(self, msg: str = "— sem DXF —"):
        self._ops      = []
        self._pixmap   = None
        self._dxf_bbox = None
        self._highlight_bbox = None
        self._highlight_points = None
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

        # Extrair fit_bbox computada pelo subprocess (bbox real do conteúdo filtrado)
        if op0 == 'bbox':
            computed_bbox = ops[0][1]
            raw_ops = ops[1:]
            if computed_bbox:
                # Sempre atualizar: worker retorna fit_bbox com Y real do conteúdo
                # (corrige zoom minúsculo quando bbox explícito tem Y=-9999..9999)
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
        s = min(ww / dw, wh / dh) * 0.88
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
        if self.width() <= 0 or self.height() <= 0:
            return
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

        if self._highlight_bbox:
            x0, y0, x1, y1 = self._highlight_bbox
            pen = QPen(QColor(Semantic.WARNING), 0)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(float(x0), float(y0), float(x1) - float(x0), float(y1) - float(y0)))
        elif self._highlight_points:
            try:
                from PySide6.QtGui import QPolygonF
                pts = [
                    QPointF(float(pt[0]), float(pt[1]))
                    for pt in self._highlight_points
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2
                ]
                if len(pts) >= 3:
                    pen = QPen(QColor(Semantic.WARNING), 0)
                    pen.setCosmetic(True)
                    fill = QColor(Semantic.WARNING)
                    fill.setAlpha(45)
                    p.setPen(pen)
                    p.setBrush(fill)
                    p.drawPolygon(QPolygonF(pts))
            except Exception:
                pass

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
        if self.width() <= 0 or self.height() <= 0:
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
        self._auto_select_initial_obra = False
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
            QPushButton#certify:hover {{ background: rgba(67, 160, 71, 1); }}
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
        """Lista todas as obras do banco (mesma lista harmoniosa do SA e dos robôs)."""
        self.cmb_obra.blockSignals(True)
        self.cmb_obra.clear()

        try:
            import sqlite3 as _sql
            _conn = _sql.connect("D:/Agente-cad-PYSIDE/project_data.vision")
            works = [r[0] for r in _conn.execute(
                "SELECT name FROM works ORDER BY name ASC"
            ).fetchall() if r[0]]
            _conn.close()
        except Exception as _e:
            _ce_log(f"[CE] _populate_obras erro ao carregar obras: {_e}")
            works = []

        for o in works:
            self.cmb_obra.addItem(f"📁 {o}", o)
        self.cmb_obra.blockSignals(False)

        if works:
            # Preferir a primeira obra que tenha pavimentos reais no banco
            try:
                import sqlite3 as _sql2
                _c2 = _sql2.connect("D:/Agente-cad-PYSIDE/project_data.vision")
                _obras_com_pav = {r[0] for r in _c2.execute(
                    "SELECT DISTINCT work_name FROM projects "
                    "WHERE pavement_name IS NOT NULL AND pavement_name != ''"
                ).fetchall()}
                _c2.close()
            except Exception:
                _obras_com_pav = set()

            _target = 0
            for _i in range(self.cmb_obra.count()):
                if self.cmb_obra.itemData(_i) in _obras_com_pav:
                    _target = _i
                    break
            self.cmb_obra.setCurrentIndex(_target)
        else:
            self.cmb_obra.setCurrentIndex(-1)

    @staticmethod
    def _pav_display_label(pav_key: str) -> str:
        """Formata nome do pavimento para exibição — suporta '13_PAV', '13PAV' e filenames DXF."""
        import re as _re
        k = pav_key.strip()
        up = k.upper()
        # Nome curto: remove sufixo _R20XX_ASCII_ODA e extensão .DXF/.DWG (igual ao SA)
        short = _re.sub(r'_R\d{4}_ASCII_ODA.*$', '', k, flags=_re.I)
        short = _re.sub(r'\.(DXF|DWG)$', '', short, flags=_re.I).strip()
        # 1) código N_PAV ou NPAV no início
        m = _re.match(r'^(\d{1,2})_?PAV', up)
        if m: return f"[{m.group(1)}º PAV]  {short}"
        # 2) padrão filename: -13P- ou -1PV- ou -13PAV-
        m = _re.search(r'[-_ ](\d{1,2})P(?:AV?|V)?(?:[-_ ]|$)', up)
        if m: return f"[{m.group(1)}º PAV]  {short}"
        if _re.search(r'TER|TÉRREO|TERREO', up): return f"[TÉRREO]  {short}"
        if _re.search(r'FUN|FUNDA', up): return f"[FUNDAÇÃO]  {short}"
        if _re.search(r'TIP|TIPO', up): return f"[TIPO]  {short}"
        if _re.search(r'COB|COBER|DECK|BARR', up): return f"[COBERTURA]  {short}"
        if _re.search(r'ATC|ATICO|ÁTICO', up): return f"[ÁTICO]  {short}"
        if _re.search(r'SUB|SUBSOLO', up): return f"[SUBSOLO]  {short}"
        return short

    def _on_obra_changed(self, obra_name: str):
        """Atualiza combo de pavimentos a partir da tabela projects (mesmos 'limpos' que o SA)."""
        obra_name = self.cmb_obra.currentData() or obra_name
        self.cmb_pav.blockSignals(True)
        self.cmb_pav.clear()
        if not obra_name:
            self.cmb_pav.blockSignals(False)
            return

        try:
            import sqlite3
            conn = sqlite3.connect("D:/Agente-cad-PYSIDE/project_data.vision")
            pavs = [row[0] for row in conn.execute(
                "SELECT DISTINCT pavement_name FROM projects "
                "WHERE work_name=? AND pavement_name IS NOT NULL AND pavement_name != '' "
                "ORDER BY pavement_name",
                (obra_name,)
            ).fetchall() if row[0]]
            conn.close()

            self.cmb_pav.addItem("TODOS", "TODOS")
            for p in pavs:
                self.cmb_pav.addItem(self._pav_display_label(p), p)

        except Exception as e:
            print(f"[CE] _on_obra_changed erro ao carregar pavimentos: {e}")

        # Fallback: se só tem TODOS, tenta pasta Fase-1
        if self.cmb_pav.count() == 1:
            fase1 = DADOS_OBRAS_ROOT / obra_name / "Fase-1_Ingestao"
            if fase1.exists():
                self.cmb_pav.addItem("1PV", "1PV")

        # Auto-seleciona primeiro pav real (índice 1 pula "TODOS")
        # Se só existe "TODOS", mantém -1 para não disparar load sem pav válido
        self.cmb_pav.blockSignals(False)
        if self.cmb_pav.count() > 1:
            self.cmb_pav.setCurrentIndex(1)
        else:
            self.cmb_pav.setCurrentIndex(-1)

        self._load_scores_for_obra(obra_name)
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
        obra = (self.cmb_obra.currentData() or self.cmb_obra.currentText())
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
        obra = (self.cmb_obra.currentData() or self.cmb_obra.currentText())
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
        obra = (self.cmb_obra.currentData() or self.cmb_obra.currentText())
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
            "background: rgba(0, 0, 0, 76); border-radius: 3px;"
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
                gridline-color: rgba(255, 255, 255, 18);
            }}
            QHeaderView::section {{
                background: rgba(20, 40, 40, 1); color: {Colors.TEXT_BRIGHT};
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
            f"background: rgba(0, 60, 80, 1); color: {Colors.ACCENT_TEAL};"
            "border: 1px solid #006666; border-radius: 3px; font-size: 10px;"  # hardcoded-ok
        )
        btn_load_all.clicked.connect(self._on_comp_load_all_scores)

        self._btn_export_audit = QPushButton("⬇ Exportar Auditoria")
        self._btn_export_audit.setFixedHeight(24)
        self._btn_export_audit.setStyleSheet(
            f"background: rgba(60, 40, 0, 1); color: {Colors.ACCENT_WARNING};"
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
        obra_name = (self.cmb_obra.currentData() or self.cmb_obra.currentText())
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
        idx = self.cmb_obra.findData(obra_name)
        if idx >= 0:
            self.cmb_obra.setCurrentIndex(idx)
        if pav:
            pav_idx = self.cmb_pav.findData(pav)
            if pav_idx < 0:
                pav_idx = self.cmb_pav.findText(pav)  # fallback texto direto
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
        if self.width() <= 0 or self.height() <= 0:
            return
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
    'N5': [
        "Ordenar itens N3 da classe",
        "Montar documento consolidado",
        "Gerar DXF N5",
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


# ── LV ficha helpers (reutilizados em N2 e N4) ───────────────────────────────

def _lv_section_widget(er_ficha: dict, accent: str = "#4caf50") -> "QWidget":
    """Widget de seções transversais numeradas para LV.
    Mostra cada section_view como um card; se vazia, usa campos globais."""
    from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QHBoxLayout, QWidget as _QW, QLabel as _QL, QFrame as _QF
    outer = _QW()
    outer.setStyleSheet(f"background: {Colors.BG_DEEP};")
    vlay = QVBoxLayout(outer)
    vlay.setContentsMargins(0, 0, 0, 0)
    vlay.setSpacing(3)

    views = er_ficha.get('section_views') or []
    if not views:
        # Fallback: montar 1 card com campos globais
        views = [{
            'h_A':        er_ficha.get('h_cm', 0),
            'h_B':        er_ficha.get('h_B_cm', 0),
            'b':          er_ficha.get('b_cm', 0),
            'tipo_viga':  er_ficha.get('tipo_viga', '—'),
            'h_section':  er_ficha.get('h_section_cm', 0),
            'laje_sup_A': er_ficha.get('laje_sup_cm', 0),
            'laje_inf_A': er_ficha.get('laje_inf_cm', 0),
            'laje_sup_B': er_ficha.get('laje_sup_B_cm', 0),
            'laje_inf_B': er_ficha.get('laje_inf_B_cm', 0),
        }]

    n = len(views)
    for idx, sv in enumerate(views, 1):
        card = _QF()
        card.setStyleSheet(
            f"QFrame {{ background: {Colors.BG_PANEL}; border: 1px solid {accent}55; "
            f"border-radius: 4px; margin: 1px; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(6, 4, 6, 4)
        cl.setSpacing(2)

        # cabeçalho do card
        hdr = _QL(f"  Corte {idx} / {n}")
        hdr.setStyleSheet(
            f"color: {accent}; font-weight: bold; font-size: 10px; "
            f"background: {accent}22; border-radius: 3px; padding: 2px 4px;"
        )
        cl.addWidget(hdr)

        def _row(label, val, layout=cl):
            if val is None or val == 0 or val == 0.0:
                return
            row_w = _QW()
            rh = QHBoxLayout(row_w)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(4)
            lbl = _QL(label)
            lbl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 10px; min-width: 72px;")
            val_lbl = _QL(str(val))
            val_lbl.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 10px; font-weight: bold;")
            rh.addWidget(lbl)
            rh.addWidget(val_lbl, 1)
            layout.addWidget(row_w)

        h_A = sv.get('h_A') or sv.get('h_cm') or er_ficha.get('h_cm')
        h_B = sv.get('h_B') or sv.get('h_B_cm') or er_ficha.get('h_B_cm')
        b   = sv.get('b')   or sv.get('b_cm')   or er_ficha.get('b_cm')

        _row("H face A",   f"{h_A:.0f} cm" if h_A else None)
        if h_B and h_B != h_A:
            _row("H face B",   f"{h_B:.0f} cm")
        body_A = sv.get('h_body_A')
        body_B = sv.get('h_body_B')
        _row("Corpo A", f"{body_A:.0f} cm" if body_A else None)
        _row("Corpo B", f"{body_B:.0f} cm" if body_B else None)
        _row("b",          f"{b:.0f} cm"   if b   else None)
        _row("Tipo",       sv.get('tipo_viga') or er_ficha.get('tipo_viga'))
        hs = sv.get('h_section') or sv.get('h_section_cm') or er_ficha.get('h_section_cm')
        _row("H seção",    f"{hs:.0f} cm"  if hs  else None)

        ls_A = sv.get('laje_sup_A') or sv.get('laje_sup') or er_ficha.get('laje_sup_cm')
        li_A = sv.get('laje_inf_A') or sv.get('laje_inf') or er_ficha.get('laje_inf_cm')
        ls_B = sv.get('laje_sup_B') or er_ficha.get('laje_sup_B_cm')
        li_B = sv.get('laje_inf_B') or er_ficha.get('laje_inf_B_cm')

        _row("Laje sup A", f"{ls_A:.0f} cm" if ls_A else None)
        _row("Laje inf A", f"{li_A:.0f} cm" if li_A else None)
        if ls_B and ls_B != ls_A:
            _row("Laje sup B", f"{ls_B:.0f} cm")
        if li_B and li_B != li_A:
            _row("Laje inf B", f"{li_B:.0f} cm")
        cont = er_ficha.get('continuation', '')
        if cont:
            _row("Continuação", cont)
        tl = er_ficha.get('text_left', ''); tr = er_ficha.get('text_right', '')
        if tl: _row("← Referência", tl)
        if tr: _row("→ Referência", tr)

        vlay.addWidget(card)

    vlay.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(outer)
    scroll.setStyleSheet(
        f"QScrollArea {{ border: none; background: {Colors.BG_DEEP}; }}"
        f"QScrollBar:vertical {{ width: 6px; background: {Colors.BG_PANEL}; }}"
        f"QScrollBar::handle:vertical {{ background: {accent}66; border-radius: 3px; }}"
    )
    return scroll


def _lv_segs_table_legacy(er_ficha: dict, accent: str = "#4caf50",
                          tbl_style: str = "") -> "QTableWidget":
    """Tabela de segmentos por face (A+B) com 7 colunas: # Larg Tipo H1 L↑ L↓ ⚑."""
    COLS = ["#", "Larg", "Tipo", "H1", "L↑", "L↓", "⚑"]
    tbl = QTableWidget(0, len(COLS))
    tbl.setHorizontalHeaderLabels(COLS)
    hh = tbl.horizontalHeader()
    for i, mode in enumerate([
        QHeaderView.ResizeToContents,  # #
        QHeaderView.ResizeToContents,  # Larg
        QHeaderView.Stretch,           # Tipo
        QHeaderView.ResizeToContents,  # H1
        QHeaderView.ResizeToContents,  # L↑
        QHeaderView.ResizeToContents,  # L↓
        QHeaderView.ResizeToContents,  # ⚑
    ]):
        hh.setSectionResizeMode(i, mode)
    tbl.verticalHeader().setVisible(False)
    tbl.setEditTriggers(QTableWidget.NoEditTriggers)
    tbl.setAlternatingRowColors(True)
    tbl.setShowGrid(False)
    if tbl_style:
        tbl.setStyleSheet(tbl_style)
    else:
        tbl.setStyleSheet(f"""
            QTableWidget {{
                background: transparent; 
                color: {Colors.TEXT_PRIMARY};
                font-size: 11px; 
                border: 1px solid rgba(255, 255, 255, 10);
                border-radius: 6px;
            }}
            QTableWidget::item {{
                border-bottom: 1px solid rgba(255, 255, 255, 5);
                padding: 4px 6px;
            }}
            QTableWidget::item:alternate {{
                background: rgba(255, 255, 255, 3);
            }}
            QTableWidget::item:hover {{
                background: rgba(180, 80, 200, 15);
            }}
            QHeaderView::section {{
                background: {Colors.BG_DEEP}; 
                color: {accent};
                border: none; 
                border-bottom: 2px solid {accent};
                font-size: 10px; 
                font-weight: bold;
                padding: 4px 6px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
        """)

    _face_bg   = QColor(Colors.BG_DEEP)
    _face_fg   = QColor(accent)
    _alt_bg    = QColor(Colors.BG_PANEL)
    _alt2_bg   = QColor("#1a2a1a")

    _TYPE_SHORT = {'Sarrafeado': 'Sarf.', 'Grade': 'Grade', 'Misto': 'Misto',
                   'gradeada': 'Grade', 'sarrafeada': 'Sarf.', 'invertida': 'Inv.'}

    def _add_face(face_label: str, segs: list, face_idx: int):
        # Linha de cabeçalho de face
        r = tbl.rowCount()
        tbl.insertRow(r)
        tbl.setRowHeight(r, 18)
        hdr_item = QTableWidgetItem(f"  {face_label}  —  {len(segs)} segmento{'s' if len(segs) != 1 else ''}")
        hdr_item.setBackground(QBrush(_face_bg))
        hdr_item.setForeground(QBrush(_face_fg))
        hdr_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        hdr_item.setFlags(hdr_item.flags() & ~Qt.ItemIsEditable)
        f = hdr_item.font(); f.setBold(True); f.setPointSize(9); hdr_item.setFont(f)
        tbl.setItem(r, 0, hdr_item)
        tbl.setSpan(r, 0, 1, len(COLS))

        for i, seg in enumerate(segs, 1):
            r = tbl.rowCount()
            tbl.insertRow(r)
            tbl.setRowHeight(r, 16)
            bg = _alt_bg if i % 2 == 1 else _alt2_bg

            larg = float(seg.get('largura_cm') or seg.get('width') or 0)
            ptype = seg.get('panel_type') or 'Sarrafeado'
            h1   = float(seg.get('height1') or seg.get('h1') or 0)
            l_up = float(seg.get('slab_top') or seg.get('laje_sup_local') or 0)
            l_dn = float(seg.get('slab_bottom') or seg.get('laje_inf_local') or 0)
            gh1  = float(seg.get('grade_h1') or 0)

            # Flags compactas
            flags = []
            if seg.get('is_first'): flags.append('P')
            if seg.get('is_last'):  flags.append('U')
            if seg.get('reuse'):    flags.append('R')
            if gh1 > 0:             flags.append('G')

            pshort = _TYPE_SHORT.get(ptype, ptype[:5])
            vals = [
                str(i),
                f"{larg:.0f}" if larg else "—",
                pshort,
                f"{h1:.0f}" if h1 else "—",
                f"{l_up:.0f}" if l_up else "—",
                f"{l_dn:.0f}" if l_dn else "—",
                " ".join(flags) if flags else "",
            ]
            for c, txt in enumerate(vals):
                it = QTableWidgetItem(txt)
                it.setTextAlignment(Qt.AlignCenter)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setBackground(QBrush(bg))
                tbl.setItem(r, c, it)

    face_units = er_ficha.get('face_units') or []
    if face_units:
        for unit_idx, unit in enumerate(face_units):
            segs = unit.get('segments') or unit.get('panels') or []
            if not segs:
                continue
            label = unit.get('label') or f"Face {unit.get('side', '?')}"
            _add_face(label, segs, unit_idx)
    else:
        segs_A = er_ficha.get('segmentos',   []) or []
        segs_B = er_ficha.get('segmentos_B', []) or []
        if segs_A:
            _add_face("Face A", segs_A, 0)
        if segs_B:
            _add_face("Face B", segs_B, 1)

    return tbl


def _lv_segs_table(er_ficha: dict, accent: str = "#4caf50",
                   tbl_style: str = "") -> "QWidget":
    """Cards de segmentos LV agrupados exclusivamente pelo lado A/B."""
    import re as _re
    from PySide6.QtWidgets import (
        QScrollArea, QVBoxLayout, QHBoxLayout,
        QWidget as _QW, QLabel as _QL, QFrame as _QF,
    )
    accent_color = QColor(accent)
    accent_soft = (
        f"rgba({accent_color.red()}, {accent_color.green()}, "
        f"{accent_color.blue()}, 34)"
    )
    accent_border = (
        f"rgba({accent_color.red()}, {accent_color.green()}, "
        f"{accent_color.blue()}, 85)"
    )
    accent_handle = (
        f"rgba({accent_color.red()}, {accent_color.green()}, "
        f"{accent_color.blue()}, 102)"
    )

    def _unit_side(unit: dict) -> str:
        side = str(unit.get('side') or '').strip().upper()
        if side in ('A', 'B'):
            return side
        label = str(unit.get('label') or '').strip().upper()
        match = _re.search(r'\.([AB])$', label)
        return match.group(1) if match else ''

    grouped = {'A': [], 'B': []}
    face_units = er_ficha.get('face_units') or []
    for unit in face_units:
        side = _unit_side(unit)
        if side in grouped:
            grouped[side].append(unit)

    # Compatibilidade com fichas antigas sem face_units.
    if not face_units:
        for side, key in (('A', 'segmentos'), ('B', 'segmentos_B')):
            panels = er_ficha.get(key) or []
            if panels:
                grouped[side].append({
                    'side': side,
                    'label': f'Face {side}',
                    'panels': panels,
                    'h_body': er_ficha.get(
                        'h_cm' if side == 'A' else 'h_B_cm', 0),
                    'laje_sup': er_ficha.get(
                        'laje_sup_cm' if side == 'A' else 'laje_sup_B_cm', 0),
                    'laje_inf': er_ficha.get(
                        'laje_inf_cm' if side == 'A' else 'laje_inf_B_cm', 0),
                })

    outer = _QW()
    outer.setStyleSheet(f"background: {Colors.BG_DEEP};")
    vlay = QVBoxLayout(outer)
    vlay.setContentsMargins(0, 0, 0, 0)
    vlay.setSpacing(3)

    summary = _QL(
        f"Segmentos A: {len(grouped['A'])}    |    "
        f"Segmentos B: {len(grouped['B'])}"
    )
    summary.setStyleSheet(
        f"color: {accent}; font-weight: bold; font-size: 10px; "
        f"background: {accent_soft}; border: 1px solid {accent_border}; "
        "border-radius: 4px; padding: 4px 7px;"
    )
    vlay.addWidget(summary)

    def _row(layout, label: str, value):
        if value is None or value == '' or value == 0 or value == 0.0:
            return
        row_w = _QW()
        rh = QHBoxLayout(row_w)
        rh.setContentsMargins(0, 0, 0, 0)
        rh.setSpacing(4)
        lbl = _QL(label)
        lbl.setStyleSheet(
            f"color: {Colors.TEXT_DIM}; font-size: 10px; min-width: 76px;")
        val = _QL(str(value))
        val.setWordWrap(True)
        val.setStyleSheet(
            f"color: {Colors.TEXT_PRIMARY}; font-size: 10px; "
            "font-weight: bold;"
        )
        rh.addWidget(lbl)
        rh.addWidget(val, 1)
        layout.addWidget(row_w)

    for side in ('A', 'B'):
        total = len(grouped[side])
        for idx, unit in enumerate(grouped[side], 1):
            panels = unit.get('segments') or unit.get('panels') or []
            widths = [
                float(p.get('largura_cm', p.get('width', 0)) or 0)
                for p in panels
            ]
            types = sorted({
                str(p.get('panel_type') or 'Sarrafeado') for p in panels
            })
            reuse_count = sum(bool(p.get('reuse')) for p in panels)
            holes_count = sum(len(p.get('holes') or []) for p in panels)
            h_body = float(
                unit.get('h_body', unit.get('h_total', 0)) or 0)

            card = _QF()
            card.setStyleSheet(
                f"QFrame {{ background: {Colors.BG_PANEL}; "
                f"border: 1px solid {accent_border}; border-radius: 4px; "
                "margin: 1px; }}"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(6, 4, 6, 4)
            cl.setSpacing(2)

            hdr = _QL(f"  Segmento {side} {idx} / {total}")
            hdr.setStyleSheet(
                f"color: {accent}; font-weight: bold; font-size: 10px; "
                f"background: {accent_soft}; border-radius: 3px; "
                "padding: 2px 4px;"
            )
            cl.addWidget(hdr)

            _row(cl, "Refer\u00eancia", unit.get('label') or f'Face {side}')
            _row(cl, "Pain\u00e9is", len(panels))
            _row(cl, "Largura",
                 f"{sum(widths):.0f} cm" if widths else None)
            _row(cl, "Composi\u00e7\u00e3o",
                 " + ".join(f"{w:.0f}" for w in widths) if widths else None)
            _row(cl, "Altura", f"{h_body:.0f} cm" if h_body else None)
            _row(cl, "Tipo", " / ".join(types) if types else None)
            laje_sup = float(unit.get('laje_sup', 0) or 0)
            laje_inf = float(unit.get('laje_inf', 0) or 0)
            _row(cl, "Laje sup.", f"{laje_sup:.0f} cm" if laje_sup else None)
            _row(cl, "Laje inf.", f"{laje_inf:.0f} cm" if laje_inf else None)
            _row(cl, "Reaprov.", reuse_count if reuse_count else None)
            _row(cl, "Aberturas", holes_count if holes_count else None)
            vlay.addWidget(card)

    if not grouped['A'] and not grouped['B']:
        empty = _QL("Nenhum segmento A/B identificado")
        empty.setAlignment(Qt.AlignCenter)
        empty.setStyleSheet(
            f"color: {Colors.TEXT_DIM}; font-size: 10px; padding: 12px;")
        vlay.addWidget(empty)

    vlay.addStretch(1)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(outer)
    scroll.setStyleSheet(
        f"QScrollArea {{ border: none; background: {Colors.BG_DEEP}; }}"
        f"QScrollBar:vertical {{ width: 6px; background: {Colors.BG_PANEL}; }}"
        f"QScrollBar::handle:vertical {{ background: {accent_handle}; "
        "border-radius: 3px; }}"
    )
    return scroll


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

        # ── Header compacto: [badge+título+desc+atenção] | [pipeline inline] ──
        # Altura fixa: 50px sem atenção, 100px com atenção (3 linhas nota)
        _HDR_H_NORMAL  = 50
        _HDR_H_ATT     = 100
        _HDR_H_ATT_PP  = 120    # +20px para linha Para/Passa
        hdr = QFrame()
        hdr.setFixedHeight(_HDR_H_NORMAL)
        hdr.setStyleSheet(f"background: {bg_color}; border-radius: 4px;")
        self._hdr = hdr
        self._hdr_h_normal = _HDR_H_NORMAL
        self._hdr_h_att    = _HDR_H_ATT
        self._hdr_h_att_pp = _HDR_H_ATT_PP
        hdr_main = QHBoxLayout(hdr)
        hdr_main.setContentsMargins(10, 5, 10, 5)
        hdr_main.setSpacing(8)

        # Esquerda: badge + título + desc + [atenção oculta]
        left_lay = QVBoxLayout()
        left_lay.setSpacing(2)
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
        self._badge_row = badge_row
        left_lay.addLayout(badge_row)

        lbl_desc = QLabel(descricao.replace('\n', ' · '))
        lbl_desc.setStyleSheet(
            "color: rgba(255, 255, 255, 110); font-size: 8px; background: transparent;"
        )
        left_lay.addWidget(lbl_desc)

        # ── Bloco de atenção inline (oculto por padrão) ───────────────
        self._attention_loading = False
        self._attention_callback = None
        self._human_validation_callback = None
        self._attention_dirty = False
        self._attention_save_timer = QTimer(self)
        self._attention_save_timer.setSingleShot(True)
        self._attention_save_timer.setInterval(550)
        self._attention_save_timer.timeout.connect(self._flush_attention_pending)
        self._attention_inline = QWidget()
        self._attention_inline.setVisible(False)
        self._attention_inline.setStyleSheet("background: transparent;")
        att_inline_lay = QVBoxLayout(self._attention_inline)
        att_inline_lay.setContentsMargins(0, 2, 0, 0)
        att_inline_lay.setSpacing(3)

        # Linha 1: score + checkbox ⚠
        att_top = QHBoxLayout()
        att_top.setSpacing(5)
        att_top.setContentsMargins(0, 0, 0, 0)
        self._score_label = QLabel("")
        self._score_label.setStyleSheet(
            f"color: {accent}; font-size: 9px; font-weight: bold; background: transparent;"
        )
        self._score_label.setWordWrap(False)
        self._attention_check = QCheckBox("⚠ Atenção")
        self._attention_check.setToolTip("Marcar item para revisão")
        self._attention_check.setStyleSheet(
            f"color: {accent}; font-size: 9px; background: transparent;"
        )
        self._human_validation_check = QCheckBox("Validado Humano")
        self._human_validation_check.setToolTip("Marcar resultado como conferido e aprovado manualmente")
        self._human_validation_check.setStyleSheet(
            f"color: {Colors.ACCENT_SUCCESS}; font-size: 9px; background: transparent;"
        )
        att_top.addWidget(self._score_label, 1)
        att_top.addWidget(self._human_validation_check, 0)
        att_top.addWidget(self._attention_check, 0)
        att_inline_lay.addLayout(att_top)

        # Linha 2: campo de nota compacto (3 linhas, scroll, max 3000 chars)
        self._attention_text = QTextEdit()
        self._attention_text.setFixedHeight(46)   # ~3 linhas de 9px
        self._attention_text.setPlaceholderText("Nota (max 3000 chars)...")
        self._attention_text.document().setMaximumBlockCount(0)
        self._attention_text.setStyleSheet(
            f"QTextEdit {{ background: rgba(0,0,0,0.35); color: {Colors.TEXT_PRIMARY}; "
            f"border: 1px solid {accent}55; border-radius: 3px; font-size: 9px; "
            f"padding: 2px 4px; }}"
            f"QScrollBar:vertical {{ background: transparent; width: 5px; }}"
            f"QScrollBar::handle:vertical {{ background: {accent}55; border-radius: 2px; }}"
        )
        att_inline_lay.addWidget(self._attention_text)

        # Linha 3: Para/Passa (exibido apenas para PIL e LAJ em N2)
        self._para_passa_row = QWidget()
        self._para_passa_row.setVisible(False)
        self._para_passa_row.setStyleSheet("background: transparent;")
        pp_lay = QHBoxLayout(self._para_passa_row)
        pp_lay.setContentsMargins(0, 0, 0, 0)
        pp_lay.setSpacing(4)
        pp_lbl = QLabel("Viga:")
        pp_lbl.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 9px; background: transparent;")
        self._para_btn = QPushButton("Para")
        self._passa_btn = QPushButton("Passa")
        self._para_passa_callback = None
        for _btn, _tipo in ((self._para_btn, "para"), (self._passa_btn, "passa")):
            _btn.setCheckable(True)
            _btn.setFixedHeight(16)
            _btn.setStyleSheet(
                f"QPushButton {{ background: {Colors.BG_DEEP}; color: {Colors.TEXT_SECONDARY}; "
                f"border: 1px solid {accent}55; border-radius: 3px; font-size: 9px; padding: 1px 6px; }}"
                f"QPushButton:checked {{ background: {accent}; color: #000; font-weight: bold; }}"
                f"QPushButton:hover {{ background: {accent}33; }}"
            )
            _btn.clicked.connect(lambda checked, t=_tipo: self._on_para_passa_clicked(t))
        pp_lay.addWidget(pp_lbl)
        pp_lay.addWidget(self._para_btn)
        pp_lay.addWidget(self._passa_btn)
        pp_lay.addStretch()
        att_inline_lay.addWidget(self._para_passa_row)

        self._attention_check.stateChanged.connect(self._emit_attention_changed)
        self._human_validation_check.stateChanged.connect(self._emit_human_validation_changed)
        self._attention_text.textChanged.connect(self._on_note_changed)
        left_lay.addWidget(self._attention_inline)

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

        # ── Splitter vertical: viewer (cima) + ficha (baixo) ─────────
        splitter_vf = QSplitter(Qt.Vertical)
        splitter_vf.setHandleWidth(4)
        splitter_vf.setStyleSheet(
            f"QSplitter::handle {{ background: {Colors.BORDER_DEFAULT}; }}"
            f"QSplitter::handle:hover {{ background: {accent}66; }}"
        )

        # ── Viewer (DXF vetorial ou PNG raster) ──────────────────────
        border_style = f"border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 2px;"
        if mode == 'dxf':
            self.img_widget: DXFVectorView | ZoomableImageLabel = DXFVectorView(bg=Colors.BG_DEEP)
        else:
            self.img_widget = ZoomableImageLabel(bg=Colors.BG_DEEP)
        self.img_widget.setMinimumHeight(160)
        self.img_widget.setStyleSheet(border_style)
        splitter_vf.addWidget(self.img_widget)

        # ── Painel inferior: progresso + ficha ────────────────────────
        bottom_w = QWidget()
        bottom_w.setStyleSheet("background: transparent;")
        bottom_lay = QVBoxLayout(bottom_w)
        bottom_lay.setContentsMargins(0, 0, 0, 0)
        bottom_lay.setSpacing(2)

        # Barra de progresso
        self.prog = QProgressBar()
        self.prog.setRange(0, 0)
        self.prog.setFixedHeight(4)
        self.prog.setVisible(False)
        self.prog.setStyleSheet(
            f"QProgressBar {{ border: none; background: {Colors.BG_DEEP}; }}"
            f"QProgressBar::chunk {{ background: {accent}; }}"
        )
        bottom_lay.addWidget(self.prog)

        # Ficha
        self.lbl_ficha = QLabel(f"Ficha {nivel_id}")
        self.lbl_ficha.setStyleSheet(
            f"color: {accent}; font-size: 10px; font-weight: bold; padding: 2px 4px;"
            f"background: {Colors.BG_CARD}; border-bottom: 1px solid {accent}44;"
        )
        self.lbl_ficha.setFixedHeight(18)
        bottom_lay.addWidget(self.lbl_ficha)

        # _attention_inline está no header (criado acima) — não precisa de panel no bottom

        # Ficha SA-style: scroll area com campos por seção
        self._ficha_accent = accent
        ficha_scroll = QScrollArea()
        ficha_scroll.setWidgetResizable(True)
        ficha_scroll.setMinimumHeight(80)
        ficha_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        ficha_scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{ background:{Colors.BG_DEEP}; width:5px; }}
            QScrollBar::handle:vertical {{ background:{Colors.BORDER_DEFAULT}; border-radius:2px; }}
        """)
        self._ficha_inner = QWidget()
        self._ficha_inner.setStyleSheet("background: transparent;")
        self._ficha_vlay = QVBoxLayout(self._ficha_inner)
        self._ficha_vlay.setContentsMargins(0, 0, 0, 0)
        self._ficha_vlay.setSpacing(0)
        self._ficha_vlay.addStretch()
        ficha_scroll.setWidget(self._ficha_inner)
        self._ficha_scroll = ficha_scroll
        bottom_lay.addWidget(ficha_scroll, 1)

        splitter_vf.addWidget(bottom_w)
        splitter_vf.setSizes([700, 300])  # 70% viewer / 30% ficha
        splitter_vf.setStretchFactor(0, 7)
        splitter_vf.setStretchFactor(1, 3)
        self._splitter_vf = splitter_vf
        self._last_loaded_dxf: str = ""   # rastreia último DXF carregado na coluna
        lay.addWidget(splitter_vf, 1)

        # Compat: manter ficha_table como objeto oculto para não quebrar código existente
        self.ficha_table = QTableWidget(0, 2)
        self.ficha_table.setVisible(False)
        self.ficha_table.setParent(self)  # filho mas fora do layout

    def set_attention_context(self, score_text: str, attention: bool, note: str, callback=None,
                              human_validated: bool = False, human_callback=None):
        self._flush_attention_pending()
        self._attention_callback = callback
        self._human_validation_callback = human_callback
        self._attention_loading = True
        self._attention_dirty = False
        try:
            self._score_label.setText(score_text or "")
            self._attention_check.setChecked(bool(attention))
            self._human_validation_check.setChecked(bool(human_validated))
            self._attention_text.setPlainText((note or "")[:3000])
            self._attention_inline.setVisible(True)
            pp_visible = self._para_passa_row.isVisible()
            self._hdr.setFixedHeight(self._hdr_h_att_pp if pp_visible else self._hdr_h_att)
        finally:
            self._attention_loading = False

    def clear_attention_context(self):
        self._flush_attention_pending()
        self._attention_callback = None
        self._human_validation_callback = None
        self._attention_dirty = False
        self._attention_save_timer.stop()
        self._para_passa_row.setVisible(False)
        self._attention_inline.setVisible(False)
        self._hdr.setFixedHeight(self._hdr_h_normal)

    def set_para_passa(self, tipo: str, callback=None):
        """Mostra e configura a linha Para/Passa no header.
        tipo: 'para', 'passa', ou '' (nenhum selecionado).
        """
        self._para_passa_callback = callback
        self._attention_loading = True
        try:
            self._para_btn.setChecked(tipo == "para")
            self._passa_btn.setChecked(tipo == "passa")
        finally:
            self._attention_loading = False
        self._para_passa_row.setVisible(True)
        # Expande header: garante que _attention_inline esteja visível para mostrar o widget
        if not self._attention_inline.isVisible():
            self._score_label.setText("")
            self._attention_inline.setVisible(True)
        self._hdr.setFixedHeight(self._hdr_h_att_pp)

    def clear_para_passa(self):
        """Oculta a linha Para/Passa e contrai o header se necessário."""
        self._para_passa_callback = None
        self._para_passa_row.setVisible(False)
        if self._attention_inline.isVisible():
            # Se attention_inline só estava visível por causa do para_passa, ocultá-lo também
            if not self._score_label.text() and not self._attention_check.isChecked() \
                    and not self._attention_text.toPlainText():
                self._attention_inline.setVisible(False)
                self._hdr.setFixedHeight(self._hdr_h_normal)
            else:
                self._hdr.setFixedHeight(self._hdr_h_att)
        else:
            self._hdr.setFixedHeight(self._hdr_h_normal)

    def _on_para_passa_clicked(self, tipo: str):
        if self._attention_loading:
            return
        # Após click o botão já está no novo estado. Determina tipo ativo:
        # se o botão clicado ficou checked → seleciona; se ficou unchecked → limpa.
        is_now_checked = (tipo == "para" and self._para_btn.isChecked()) or \
                         (tipo == "passa" and self._passa_btn.isChecked())
        new_tipo = tipo if is_now_checked else ""
        self._attention_loading = True
        try:
            self._para_btn.setChecked(new_tipo == "para")
            self._passa_btn.setChecked(new_tipo == "passa")
        finally:
            self._attention_loading = False
        if self._para_passa_callback:
            self._para_passa_callback(new_tipo)

    def _on_note_changed(self):
        if self._attention_loading or not self._attention_callback:
            return
        txt = self._attention_text.toPlainText()
        if len(txt) > 3000:
            self._attention_loading = True
            cursor = self._attention_text.textCursor()
            self._attention_text.setPlainText(txt[:3000])
            cursor.setPosition(min(cursor.position(), 3000))
            self._attention_text.setTextCursor(cursor)
            self._attention_loading = False
            self._attention_dirty = True
            self._attention_save_timer.start()
            return
        self._attention_dirty = True
        self._attention_save_timer.start()

    def _emit_attention_changed(self, *args):
        if self._attention_loading or not self._attention_callback:
            return
        self._attention_save_timer.stop()
        self._attention_dirty = False
        self._attention_callback(
            bool(self._attention_check.isChecked()),
            self._attention_text.toPlainText(),
        )

    def _emit_human_validation_changed(self, *args):
        if self._attention_loading or not self._human_validation_callback:
            return
        self._human_validation_callback(bool(self._human_validation_check.isChecked()))

    def _flush_attention_pending(self):
        if self._attention_loading or not self._attention_callback or not self._attention_dirty:
            return
        self._attention_save_timer.stop()
        self._attention_dirty = False
        self._attention_callback(
            bool(self._attention_check.isChecked()),
            self._attention_text.toPlainText(),
        )

    # ── Conteúdo ─────────────────────────────────────────────────────

    def load_content(self, path, bbox=None):
        """
        Carrega conteúdo de acordo com o mode da coluna.
        mode='dxf': chama load_dxf(path, bbox) no DXFVectorView.
        mode='png': carrega QPixmap no ZoomableImageLabel.
        """
        if path:
            self._last_loaded_dxf = str(path)
        if self._mode == 'dxf':
            self.img_widget.load_dxf(path, bbox)
        else:
            if path and Path(path).exists():
                self.img_widget.set_pixmap(QPixmap(str(path)))
            else:
                self.img_widget.clear_image()

    def _clear_ficha_vlay(self):
        """Remove todos os widgets filhos do layout da ficha dinâmica."""
        while self._ficha_vlay.count() > 0:
            item = self._ficha_vlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_ficha(self, rows: list):
        """rows = [(label, value), ...] — renderiza ficha SA-style com seções e campos.
        Marcadores especiais:
          label == '=='  → header de seção (value = título)
          label == '---' → separador fino
          label == '⚠ ...' → aviso laranja
        """
        self._restore_lv_ficha()
        self._clear_ficha_vlay()

        accent = self._ficha_accent
        _ODD  = "background: rgba(255,255,255,4);"
        _EVEN = "background: transparent;"
        _FIELD_H = 22
        _SECTION_SS = (f"background: rgba(30,60,100,0.7); color: {accent}; "
                       f"font-size: 10px; font-weight: bold; padding: 3px 8px; "
                       f"border-left: 3px solid {accent}; letter-spacing: 0.5px;")
        _LBL_SS = (f"color: {Colors.TEXT_SECONDARY}; font-size: 11px; "
                   f"padding: 0 8px; min-width: 140px; max-width: 180px;")
        _VAL_SS = (f"color: {Colors.TEXT_PRIMARY}; font-size: 11px; "
                   f"padding: 0 6px; border: none; background: transparent;")
        _WARN_SS = (f"color: #f59e0b; font-size: 10px; padding: 2px 8px; "
                    f"background: rgba(245,158,11,0.08);")

        row_idx = 0
        for label, value in rows:
            label = str(label)
            value = str(value) if value is not None else "—"

            if label == "==":
                # Seção com título
                sec = QLabel(value.upper())
                sec.setStyleSheet(_SECTION_SS)
                sec.setFixedHeight(20)
                self._ficha_vlay.addWidget(sec)
                row_idx = 0
                continue

            if label == "---":
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: rgba(255,255,255,8); border:none;")
                self._ficha_vlay.addWidget(sep)
                continue

            # Campo normal: row com label + valor
            row_w = QWidget()
            row_w.setFixedHeight(_FIELD_H)
            row_w.setStyleSheet(_ODD if row_idx % 2 else _EVEN)
            rh = QHBoxLayout(row_w)
            rh.setContentsMargins(0, 0, 0, 0)
            rh.setSpacing(0)

            lbl_w = QLabel(label)
            lbl_w.setStyleSheet(_LBL_SS)
            lbl_w.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            if label.startswith("⚠"):
                lbl_w.setStyleSheet(_WARN_SS)
                val_w = QLabel(value)
                val_w.setStyleSheet(_WARN_SS)
            else:
                val_w = QLabel(value)
                val_w.setStyleSheet(_VAL_SS)
                val_w.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            rh.addWidget(lbl_w)
            rh.addWidget(val_w, 1)
            self._ficha_vlay.addWidget(row_w)
            row_idx += 1

        self._ficha_vlay.addStretch()

    def set_lv_ficha(self, er_ficha: dict, accent: str = "#4caf50"):
        """Layout estruturado LV (seções + segmentos) na área de ficha (30% inferior).
        Mantém viewer DXF visível no topo (70%) — NÃO esconde _splitter_vf.
          - Esquerda: seções transversais numeradas (scroll cards)
          - Direita: segmentos por face (tabela rica 7 colunas)
        """
        self._restore_lv_ficha()   # limpa anterior se houver
        self._clear_ficha_vlay()   # limpa ficha genérica anterior

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {Colors.BORDER_DEFAULT}; }}"
        )

        sect_w = _lv_section_widget(er_ficha, accent)
        segs_t = _lv_segs_table(er_ficha, accent)
        segs_t.setMinimumHeight(100)

        splitter.addWidget(sect_w)
        splitter.addWidget(segs_t)
        splitter.setSizes([200, 340])

        # Inserir na área de ficha (dentro do _ficha_vlay, abaixo do viewer)
        self._ficha_vlay.addWidget(splitter, 1)
        self._lv_ficha_splitter = splitter

    def _restore_lv_ficha(self):
        """Remove widget LV estruturado da área de ficha."""
        w = getattr(self, '_lv_ficha_splitter', None)
        if w is not None:
            w.setParent(None)
            w.deleteLater()
            self._lv_ficha_splitter = None
        self._splitter_vf.setVisible(True)  # garante visibilidade (idempotente)

    def set_processing(self, active: bool):
        self.prog.setVisible(active)
        if active:
            self.img_widget.clear_image("Processando...")

    # ── PIL 3-panel mode ─────────────────────────────────────────────

    def switch_to_pil_zones(self, zone_paths: dict, er_ficha: dict,
                             zone_fichas: "dict | None" = None,
                             accent: str = "#a855f7"):
        """Replace viewer+ficha with 3-or-4-panel layout for PIL.

        zone_paths:  {'ABCD': Path|None, 'CIMA': Path|None, 'GRADES': Path|None[, 'EFGH': Path|None]}
        er_ficha:    full ficha dict (fallback when zone_fichas absent)
        zone_fichas: {'ABCD': dict, 'CIMA': dict, 'GRADES': dict[, 'EFGH': dict]} from motor zones
        EFGH panel added when zone_paths contains 'EFGH' key (subtipo U).
        """
        lay = self.layout()

        # Determine zones to show (always CIMA|ABCD|GRADES; EFGH only if present)
        show_efgh = 'EFGH' in zone_paths
        active_zones = ['CIMA', 'ABCD', 'GRADES'] + (['EFGH'] if show_efgh else [])

        if not getattr(self, '_pil_mode', False):
            self._splitter_vf.setVisible(False)

            splitter = QSplitter(Qt.Horizontal)
            self._zone_views: dict = {}
            self._zone_tables: dict = {}

            for zone in active_zones:
                panel = QWidget()
                pv = QVBoxLayout(panel)
                pv.setContentsMargins(2, 2, 2, 2)
                pv.setSpacing(2)

                zone_hdr = QLabel(zone)
                zone_hdr.setAlignment(Qt.AlignCenter)
                zone_hdr.setFixedHeight(20)
                zone_hdr.setStyleSheet(
                    f"color: {accent}; font-weight: bold; font-size: 11px; "
                    f"background: {Colors.BG_DEEP}; border-radius: 3px;"
                )
                pv.addWidget(zone_hdr)

                view = DXFVectorView(bg=Colors.BG_DEEP)
                view.setMinimumHeight(180)
                pv.addWidget(view, 1)

                tbl = QTableWidget(0, 2)
                tbl.setHorizontalHeaderLabels(["Campo", "Valor"])
                tbl.horizontalHeader().setSectionResizeMode(
                    0, QHeaderView.ResizeToContents)
                tbl.horizontalHeader().setSectionResizeMode(
                    1, QHeaderView.Stretch)
                tbl.verticalHeader().setVisible(False)
                tbl.setEditTriggers(QTableWidget.NoEditTriggers)
                tbl.setFixedHeight(120)
                tbl.setStyleSheet(self.ficha_table.styleSheet())
                pv.addWidget(tbl)

                self._zone_views[zone] = view
                self._zone_tables[zone] = tbl
                splitter.addWidget(panel)

            # Inserir splitter PIL após o header (index 1)
            lay.insertWidget(1, splitter)
            self._pil_splitter = splitter
            self._pil_mode = True

        # Load DXFs into viewers
        from pathlib import Path as _Path
        for zone, view in self._zone_views.items():
            p = zone_paths.get(zone)
            if p and _Path(p).exists():
                view.load_dxf(str(p), None)
            else:
                view.clear_image(f"Sem ficha {zone}")

        self._update_pil_zone_fichas(er_ficha, zone_fichas)

    def _update_pil_zone_fichas(self, er_ficha: dict, zone_fichas: "dict | None" = None):
        """Populate each zone's mini-ficha table.
        Uses zone_fichas[zone] if provided, else slices er_ficha via PIL_ZONE_FIELDS."""
        try:
            import sys as _sys, os as _os
            _sys.path.insert(0, str(_os.path.join(
                _os.path.dirname(__file__), '..', '..', '..')))
            from src.core.services.dxf_generator import PIL_ZONE_FIELDS
        except Exception:
            PIL_ZONE_FIELDS = {
                'ABCD':   ['nome', 'comprimento', 'largura', 'altura', 'pd_pavimento_cm'],
                'CIMA':   ['nome', 'comprimento', 'largura', 'grade_1'],
                'GRADES': ['nome', 'comprimento', 'largura', 'altura', 'grade_1', 'grade_2'],
                'EFGH':   ['nome', 'larg1_E', 'larg1_F', 'h1_E', 'h2_E', 'h3_E', 'h1_F', 'h2_F', 'h3_F'],
            }
        for zone, tbl in self._zone_tables.items():
            fields = PIL_ZONE_FIELDS.get(zone, [])
            ficha_src = (zone_fichas or {}).get(zone) or er_ficha
            tbl.setRowCount(0)
            for field in fields:
                val = ficha_src.get(field, ficha_src.get(field.replace('_', ''), None))
                r = tbl.rowCount()
                tbl.insertRow(r)
                tbl.setRowHeight(r, 18)
                fi = QTableWidgetItem(field)
                vi = QTableWidgetItem(str(val) if val is not None else '—')
                fi.setFlags(fi.flags() & ~Qt.ItemIsEditable)
                vi.setFlags(vi.flags() & ~Qt.ItemIsEditable)
                tbl.setItem(r, 0, fi)
                tbl.setItem(r, 1, vi)

    def switch_to_lv_zones(self, zone_paths: dict, er_ficha: dict,
                            zone_fichas: "dict | None" = None):
        """Replace viewer+ficha with 2-panel layout for LV.

        zone_paths: {'Visão Corte': (dxf_path, bbox_or_None),
                     'Lateral A-B': (dxf_path, bbox_or_None)}
        er_ficha:   full LV ficha dict (campos: h_cm, h_B_cm, b_cm, tipo_viga,
                    segmentos, segmentos_B, laje_sup_cm, laje_inf_cm, ...)
        """
        ACCENT = "#4caf50"
        ZONES = ['Visão Corte', 'Lateral A-B']
        lay = self.layout()
        from pathlib import Path as _Path

        if not getattr(self, '_pil_mode', False):
            self._splitter_vf.setVisible(False)

            splitter = QSplitter(Qt.Horizontal)
            self._zone_views:  dict = {}
            self._zone_tables: dict = {}   # legado
            self._zone_fichas: dict = {}   # novos widgets de ficha LV

            for zone in ZONES:
                panel = QWidget()
                pv = QVBoxLayout(panel)
                pv.setContentsMargins(2, 2, 2, 2)
                pv.setSpacing(2)

                zone_hdr = QLabel(zone)
                zone_hdr.setAlignment(Qt.AlignCenter)
                zone_hdr.setFixedHeight(20)
                zone_hdr.setStyleSheet(
                    f"color: {ACCENT}; font-weight: bold; font-size: 11px; "
                    f"background: {Colors.BG_DEEP}; border-radius: 3px;"
                )
                pv.addWidget(zone_hdr)

                view = DXFVectorView(bg=Colors.BG_DEEP)
                view.setMinimumHeight(180)
                pv.addWidget(view, 1)

                # Ficha estruturada (substituem as antigas tabelas simples)
                if zone == 'Lateral A-B':
                    ficha_w = _lv_segs_table(er_ficha or {}, ACCENT)
                    ficha_w.setFixedHeight(160)
                else:
                    ficha_w = _lv_section_widget(er_ficha or {}, ACCENT)
                    ficha_w.setFixedHeight(160)
                pv.addWidget(ficha_w)

                self._zone_views[zone]  = view
                self._zone_fichas[zone] = ficha_w
                splitter.addWidget(panel)

            # Visão Corte ~26%, Lateral A-B ~74%
            splitter.setSizes([264, 736])
            lay.insertWidget(1, splitter)
            self._pil_splitter = splitter
            self._pil_mode = True

        else:
            # Já em modo LV — atualizar fichas sem recriar o layout
            if 'Lateral A-B' in self._zone_fichas:
                old = self._zone_fichas['Lateral A-B']
                new = _lv_segs_table(er_ficha or {}, ACCENT)
                new.setFixedHeight(160)
                old.parent().layout().replaceWidget(old, new)
                old.setParent(None); old.deleteLater()
                self._zone_fichas['Lateral A-B'] = new
            if 'Visão Corte' in self._zone_fichas:
                old = self._zone_fichas['Visão Corte']
                new = _lv_section_widget(er_ficha or {}, ACCENT)
                new.setFixedHeight(160)
                old.parent().layout().replaceWidget(old, new)
                old.setParent(None); old.deleteLater()
                self._zone_fichas['Visão Corte'] = new

        # ── Carregar DXFs (mesmo arquivo, bboxes diferentes → culling por X) ──
        for zone, view in self._zone_views.items():
            entry = zone_paths.get(zone)
            if entry:
                path, bbox = entry if isinstance(entry, tuple) else (entry, None)
                if path and _Path(str(path)).exists():
                    if not self._last_loaded_dxf:
                        self._last_loaded_dxf = str(path)
                    view.load_dxf(str(path), bbox)
                else:
                    view.clear_image(f"Sem DXF — {zone}")
            else:
                view.clear_image(f"Sem DXF — {zone}")

    def show_n2_above(self, recorte_path, *, title: str | None = None, bbox=None,
                      highlight_points=None, cull_to_bbox: bool = True):
        """Insere viewer N2 (recorte) ACIMA do conteúdo N4 existente, sem ficha.
        Toggle: chamar novamente atualiza o DXF; chamar hide_n2_above() remove."""
        from pathlib import Path as _Path
        if hasattr(self, '_n2_above') and self._n2_above is not None:
            if recorte_path and _Path(str(recorte_path)).exists():
                if hasattr(self, '_n2_above_hdr') and title:
                    self._n2_above_hdr.setText(title)
                if highlight_points:
                    self._n2_above_view.set_highlight_geometry(highlight_points)
                elif bbox:
                    self._n2_above_view.set_highlight_bbox(bbox)
                else:
                    self._n2_above_view.set_highlight_geometry(None)
                self._n2_above_view.load_dxf(str(recorte_path), bbox if cull_to_bbox else None)
                self._n2_above.setVisible(True)
                self._apply_compare_viewer_y_ratio()
            else:
                self.hide_n2_above()
            return
        if not recorte_path or not _Path(str(recorte_path)).exists():
            return
        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(2, 2, 2, 2)
        pv.setSpacing(2)
        hdr = QLabel("DXF N2 — Recorte")
        hdr.setAlignment(Qt.AlignCenter)
        hdr.setFixedHeight(18)
        hdr.setStyleSheet(
            "color: #4acf7a; font-weight: bold; font-size: 11px; "
            f"background: {Colors.BG_DEEP}; border-radius: 3px;"
        )
        pv.addWidget(hdr)
        n2_view = DXFVectorView(bg=Colors.BG_DEEP)
        n2_view.setMinimumHeight(self.img_widget.minimumHeight())
        n2_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pv.addWidget(n2_view, 1)
        if highlight_points:
            n2_view.set_highlight_geometry(highlight_points)
        elif bbox:
            n2_view.set_highlight_bbox(bbox)
        n2_view.load_dxf(str(recorte_path), bbox if cull_to_bbox else None)
        self._n2_above = panel
        self._n2_above_hdr = hdr
        self._n2_above_view = n2_view
        self.layout().insertWidget(1, panel, 2)
        self._apply_compare_viewer_y_ratio()

    def _apply_compare_viewer_y_ratio(self):
        """Keep compare:viewer:ficha at 7:7:3, matching the column viewer Y ratio."""
        try:
            lay = self.layout()
            compare = getattr(self, '_n2_above', None)
            if compare is None:
                return
            compare_idx = lay.indexOf(compare)
            splitter_idx = lay.indexOf(self._splitter_vf)
            if compare_idx >= 0:
                lay.setStretch(compare_idx, 7)
            if splitter_idx >= 0:
                lay.setStretch(splitter_idx, 10)
            self._splitter_vf.setSizes([700, 300])
            self._splitter_vf.setStretchFactor(0, 7)
            self._splitter_vf.setStretchFactor(1, 3)
        except Exception:
            pass

    def hide_n2_above(self):
        """Remove o viewer N2 inserido acima do N4."""
        if getattr(self, '_n2_above', None) is not None:
            self._n2_above.setParent(None)
            self._n2_above.deleteLater()
            self._n2_above = None
            self._n2_above_view = None
            try:
                splitter_idx = self.layout().indexOf(self._splitter_vf)
                if splitter_idx >= 0:
                    self.layout().setStretch(splitter_idx, 1)
                self._splitter_vf.setSizes([700, 300])
            except Exception:
                pass

    def restore_single_view(self):
        """Restore N4 column to single-viewer layout (called on item/classe change)."""
        if not getattr(self, '_pil_mode', False):
            return
        self._pil_splitter.setVisible(False)
        self._splitter_vf.setVisible(True)
        self._pil_mode = False


class DxfVisualConfigDialog(QDialog):
    """Inspeciona configuracoes visuais dos robos e do motor DXF atual."""

    _ROBOT_ROOTS = {
        "PL": SCRIPTS_DIR.parent / "_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25",
        "LV": SCRIPTS_DIR.parent / "_ROBOS_ABAS/Robo_Laterais_de_Vigas",
        "FV": SCRIPTS_DIR.parent / "_ROBOS_ABAS/Robo_Fundos_de_Vigas/compactador-producao",
        "LJ": SCRIPTS_DIR.parent / "_ROBOS_ABAS/Robo_Lajes",
    }
    _COMMON_TEMPLATE_FILE = SCRIPTS_DIR.parent / "config" / "dxf_visual_templates.json"

    def __init__(self, classe: str, script_path: Path, robot_widget=None, parent=None):
        super().__init__(parent)
        self.classe = str(classe or "").upper()
        self.script_path = Path(script_path)
        self.robot_widget = robot_widget
        self.setWindowTitle(f"Configuracao Visual DXF - {self.classe}")
        self.resize(980, 720)
        self.setStyleSheet(f"""
            QDialog {{ background:{Colors.BG_PRIMARY}; color:{Colors.TEXT_PRIMARY}; }}
            QTabWidget::pane {{ border:1px solid {Colors.BORDER_DEFAULT}; }}
            QTableWidget {{ background:{Colors.BG_DEEP}; color:{Colors.TEXT_PRIMARY}; gridline-color:{Colors.BORDER_DEFAULT}; }}
            QHeaderView::section {{ background:{Colors.BG_CARD}; color:{Colors.TEXT_SECONDARY}; padding:4px; border:none; }}
            QTextEdit {{ background:{Colors.BG_DEEP}; color:{Colors.TEXT_PRIMARY}; border:1px solid {Colors.BORDER_DEFAULT}; }}
        """)

        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(8)

        hdr = QLabel(f"{self.classe} - templates do robo + template do motor DXF atual")
        hdr.setStyleSheet(f"color:{Colors.ACCENT_BLUE}; font-weight:bold; font-size:13px;")
        main.addWidget(hdr)

        self.tabs = QTabWidget()
        main.addWidget(self.tabs, 1)

        self.current_template = self._extract_current_motor_template()
        self._persist_current_template_if_supported()
        self._add_native_config_tab()
        self._add_current_template_tab()
        self._add_robot_templates_tab()
        self._add_robot_config_tab()
        self._add_extra_params_tab()
        self._add_source_tab()

        row = QHBoxLayout()
        row.addStretch()
        native_actions = self._native_config_actions()
        if native_actions:
            for label, callback in native_actions:
                btn_native = QPushButton(label)
                btn_native.clicked.connect(callback)
                row.addWidget(btn_native)
        else:
            btn_native = QPushButton("Abrir Config Nativa do Robo")
            btn_native.clicked.connect(self._open_native_config)
            btn_native.setEnabled(self._has_native_config())
            row.addWidget(btn_native)
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.accept)
        row.addWidget(btn_close)
        main.addLayout(row)

    def _safe_literal(self, node):
        import ast
        try:
            return ast.literal_eval(node)
        except Exception:
            return None

    def _safe_dict_literal(self, node, known_names: dict):
        import ast
        if not isinstance(node, ast.Dict):
            return None
        out = {}
        for key_node, val_node in zip(node.keys, node.values):
            if isinstance(key_node, ast.Name) and key_node.id in known_names:
                key = known_names[key_node.id]
            else:
                key = self._safe_literal(key_node)
            val = self._safe_literal(val_node)
            if key is not None and val is not None:
                out[key] = val
        return out

    def _extract_current_motor_template(self) -> dict:
        import ast
        template = {
            "classe": self.classe,
            "script": str(self.script_path),
            "origem": "motor_dxf_atual",
            "constantes": {},
            "layers": {},
            "dimstyles": [],
            "blocks": [],
            "funcoes_setup": [],
        }
        try:
            source = self.script_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except Exception as exc:
            template["erro"] = str(exc)
            return template

        for node in tree.body:
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if not names:
                    continue
                name = names[0]
                value = self._safe_literal(node.value)
                if name == "LAYERS":
                    layers = value if isinstance(value, dict) else self._safe_dict_literal(node.value, template["constantes"])
                    if isinstance(layers, dict):
                        template["layers"] = layers
                elif name.isupper() and value is not None and isinstance(value, (str, int, float, bool, list, tuple, dict)):
                    template["constantes"][name] = value
            elif isinstance(node, ast.FunctionDef):
                if node.name.startswith("setup") or node.name.startswith("_define"):
                    template["funcoes_setup"].append(node.name)

        for key, value in template.get("constantes", {}).items():
            if "DIMSTYLE" in key or key.endswith("_STYLE"):
                template["dimstyles"].append({key: value})
            if "BLOCK" in key:
                template["blocks"].append({key: value})
        return template

    def _robot_config_manager(self):
        cm = getattr(self.robot_widget, "config_manager", None)
        if cm is None and hasattr(self.robot_widget, "vm"):
            cm = getattr(self.robot_widget.vm, "config_manager", None)
        return cm

    def _persist_current_template_if_supported(self):
        try:
            self._COMMON_TEMPLATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            all_templates = {}
            if self._COMMON_TEMPLATE_FILE.exists():
                all_templates = json.loads(self._COMMON_TEMPLATE_FILE.read_text(encoding="utf-8", errors="replace"))
                if not isinstance(all_templates, dict):
                    all_templates = {}
            all_templates[f"DXF_ATUAL_{self.classe}"] = self.current_template
            self._COMMON_TEMPLATE_FILE.write_text(
                json.dumps(all_templates, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass
        cm = self._robot_config_manager()
        if cm is None or not hasattr(cm, "save_template"):
            return
        try:
            cm.save_template(f"DXF_ATUAL_{self.classe}", self.current_template)
        except Exception:
            pass

    def _has_native_config(self) -> bool:
        return bool(self._native_config_actions())

    def _native_config_actions(self) -> list[tuple[str, object]]:
        rw = self.robot_widget
        if rw is None:
            return []

        actions = []

        def add(label, fn):
            if callable(fn):
                actions.append((label, lambda _=False, f=fn: self._run_native_config(f)))

        if self.classe == "PL":
            vm = getattr(rw, "vm", None)
            add("Abrir Config Robo - CIMA", getattr(vm, "open_config_cima", None))
            add("Abrir Config Robo - ABCD", getattr(vm, "open_config_abcd", None))
            add("Abrir Config Robo - GRADES", getattr(vm, "open_config_grades", None))
            return actions

        if self.classe == "LV":
            if hasattr(rw, "show_settings"):
                actions.append(("Abrir Config Robo - A-B", lambda _=False: self._run_native_config(lambda: rw.show_settings(initial_tab=1))))
                actions.append(("Abrir Config Robo - Visao Corte", lambda _=False: self._run_native_config(lambda: rw.show_settings(initial_tab=2))))
            return actions

        if self.classe == "FV":
            add("Abrir Config Robo - Fundo", getattr(rw, "open_config", None))
            return actions

        if self.classe == "LJ":
            laje_tab = getattr(rw, "laje_tab", None)
            add("Abrir Config Robo - Laje", getattr(laje_tab, "abrir_configuracoes", None))
            return actions

        if hasattr(rw, "open_config"):
            add("Abrir Config Nativa do Robo", getattr(rw, "open_config", None))
        return actions

    def _run_native_config(self, callback):
        try:
            callback()
        except TypeError:
            try:
                callback(False)
            except Exception as exc:
                QMessageBox.warning(self, "Configuracao Visual", f"Nao foi possivel abrir config nativa: {exc}")
        except Exception as exc:
            QMessageBox.warning(self, "Configuracao Visual", f"Nao foi possivel abrir config nativa: {exc}")

    def _open_native_config(self):
        actions = self._native_config_actions()
        if actions:
            actions[0][1]()
            return
        if self.robot_widget is None:
            return
        try:
            if hasattr(self.robot_widget, "open_config"):
                self.robot_widget.open_config()
                return
            for btn in self.robot_widget.findChildren(QPushButton):
                if "config" in (btn.text() or "").lower():
                    btn.click()
                    return
        except Exception as exc:
            QMessageBox.warning(self, "Configuracao Visual", f"Nao foi possivel abrir config nativa: {exc}")

    def _add_dict_table_tab(self, title: str, data: dict):
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Grupo", "Parametro", "Valor"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)

        def add_row(group, key, value):
            r = table.rowCount()
            table.insertRow(r)
            values = (
                str(group),
                str(key),
                json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list, tuple)) else str(value),
            )
            for c, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(r, c, item)

        def walk(group, obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, dict):
                        walk(str(key), value)
                    else:
                        add_row(group, str(key), value)
            else:
                add_row(title, "valor", obj)

        walk(title, data or {})
        self.tabs.addTab(table, title)
        return table

    def _add_current_template_tab(self):
        self._add_dict_table_tab("Template Atual", self.current_template)

    def _add_native_config_tab(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)
        lbl = QLabel("Abrir configuracoes originais do robo integrado.")
        lbl.setStyleSheet(f"color:{Colors.TEXT_SECONDARY}; font-size:12px;")
        lay.addWidget(lbl)
        actions = self._native_config_actions()
        if actions:
            for label, callback in actions:
                btn = QPushButton(label)
                btn.setFixedHeight(30)
                btn.clicked.connect(callback)
                lay.addWidget(btn)
        else:
            empty = QLabel("Nenhuma configuracao nativa encontrada para esta classe.")
            empty.setStyleSheet(f"color:{Colors.TEXT_DIM};")
            lay.addWidget(empty)
        lay.addStretch()
        self.tabs.addTab(tab, "Configs Nativas")

    def _load_robot_templates(self) -> dict:
        templates = {}
        cm = self._robot_config_manager()
        if cm is not None and hasattr(cm, "load_templates"):
            try:
                loaded = cm.load_templates()
                if isinstance(loaded, dict):
                    templates.update(loaded)
            except Exception:
                pass
        root = self._ROBOT_ROOTS.get(self.classe)
        if root and root.exists():
            for path in list(root.rglob("templates*.json"))[:20]:
                try:
                    templates[path.name] = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    templates[path.name] = str(path)
        return templates

    def _add_robot_templates_tab(self):
        templates = self._load_robot_templates()
        templates.setdefault(f"DXF_ATUAL_{self.classe}", self.current_template)
        self._add_dict_table_tab("Templates Robo", templates)

    def _load_robot_config(self) -> dict:
        cfg = {}
        cm = self._robot_config_manager()
        if cm is not None and isinstance(getattr(cm, "config", None), dict):
            cfg["config_manager"] = cm.config
        root = self._ROBOT_ROOTS.get(self.classe)
        if root and root.exists():
            files = []
            for pattern in ("config*.json", "*config*.json", "settings*.json"):
                files.extend(root.rglob(pattern))
            for path in sorted(set(files))[:35]:
                try:
                    cfg[path.name] = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    cfg[path.name] = str(path)
        return cfg

    def _add_robot_config_tab(self):
        self._add_dict_table_tab("Configs Robo", self._load_robot_config())

    def _add_extra_params_tab(self):
        robot_cfg_text = json.dumps(self._load_robot_config(), ensure_ascii=False).lower()
        extras = {}
        for key, value in self.current_template.get("constantes", {}).items():
            if str(key).lower() not in robot_cfg_text:
                extras[key] = value
        for lname, color in self.current_template.get("layers", {}).items():
            if str(lname).lower() not in robot_cfg_text:
                extras[f"LAYER::{lname}"] = color
        self._add_dict_table_tab("Parametros Extras Motor DXF", extras)

    def _add_source_tab(self):
        text = QTextEdit()
        text.setReadOnly(True)
        payload = {
            "classe": self.classe,
            "script": str(self.script_path),
            "template_atual": self.current_template,
            "templates_robo": self._load_robot_templates(),
            "configs_robo": self._load_robot_config(),
        }
        text.setPlainText(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        self.tabs.addTab(text, "JSON Completo")


class NavSidebar(QFrame):
    """Sidebar: mini-tabs PL/LV/FV/LJ + lista scrollável de itens + ações."""

    item_selected       = Signal(str, str)
    process_requested   = Signal(str, str)   # N3 (legado)
    gerar_n1_requested  = Signal(str, str)   # classe, item_id
    gerar_n2_requested  = Signal(str, str)
    gerar_n3_requested  = Signal(str, str)
    gerar_n4_requested  = Signal(str, str)
    gerar_n5_requested  = Signal(str, list)
    analise_requested   = Signal()
    fase4_requested     = Signal()
    classe_changed      = Signal(str)        # emitido ao trocar aba de classe

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
        self._selected_source  = "estrutural"
        self._selected_recorte_path = ""  # recorte_path do item ER selecionado (Qt.UserRole+1)
        self._tab_btns: dict  = {}
        self._lj_filter: "set[str] | None" = None  # stems LJ válidos do DXF atual
        self._lv_subtab: str = ""  # "Para" | "Passa" | "" (nenhuma selecionada)

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
        self._btn_flow_estru.setVisible(False)
        self._btn_flow_rev.setVisible(False)

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

        # ── Sub-abas LV: Vigas Para / Vigas Passam ────────────────────
        self._lv_subtab_widget = QWidget()
        _lv_sub_lay = QHBoxLayout(self._lv_subtab_widget)
        _lv_sub_lay.setContentsMargins(0, 0, 0, 0)
        _lv_sub_lay.setSpacing(2)
        self._lv_ss_para_act  = ("QPushButton{background:#1B5E20;color:#fff;border-radius:3px;"
                                 "font-size:10px;font-weight:bold;border-bottom:2px solid #4caf50;}")
        self._lv_ss_para_inac = (f"QPushButton{{background:{Colors.BG_CARD};color:{Colors.TEXT_SECONDARY};"
                                 f"border-radius:3px;font-size:10px;border:1px solid {Colors.BORDER_DEFAULT};}}"
                                 f"QPushButton:hover{{background:{Colors.BG_PANEL};}}")
        self._lv_ss_pass_act  = ("QPushButton{background:#4A148C;color:#fff;border-radius:3px;"
                                 "font-size:10px;font-weight:bold;border-bottom:2px solid #9c27b0;}")
        self._lv_ss_pass_inac = (f"QPushButton{{background:{Colors.BG_CARD};color:{Colors.TEXT_SECONDARY};"
                                 f"border-radius:3px;font-size:10px;border:1px solid {Colors.BORDER_DEFAULT};}}"
                                 f"QPushButton:hover{{background:{Colors.BG_PANEL};}}")
        self._btn_lv_para = QPushButton("Vigas Para")
        self._btn_lv_para.setFixedHeight(20)
        self._btn_lv_para.setCheckable(True)
        self._btn_lv_para.setStyleSheet(self._lv_ss_para_inac)
        self._btn_lv_para.clicked.connect(lambda: self._select_lv_subtab("Para"))
        self._btn_lv_passa = QPushButton("Vigas Passam")
        self._btn_lv_passa.setFixedHeight(20)
        self._btn_lv_passa.setCheckable(True)
        self._btn_lv_passa.setStyleSheet(self._lv_ss_pass_inac)
        self._btn_lv_passa.clicked.connect(lambda: self._select_lv_subtab("Passa"))
        _lv_sub_lay.addWidget(self._btn_lv_para)
        _lv_sub_lay.addWidget(self._btn_lv_passa)
        self._lv_subtab_widget.setVisible(False)
        lay.addWidget(self._lv_subtab_widget)

        # ── Lista de itens (scrollável) ──────────────────────────────
        self.tbl_items = QTableWidget(0, 2)
        self.tbl_items.setHorizontalHeaderLabels(["N1/N3 Estrutural", "N2/N4 Eng. Reversa"])
        self.tbl_items.verticalHeader().setVisible(False)
        self.tbl_items.setShowGrid(False)
        self.tbl_items.setAlternatingRowColors(True)
        self.tbl_items.setSelectionBehavior(QTableWidget.SelectItems)
        self.tbl_items.setSelectionMode(QTableWidget.SingleSelection)
        self.tbl_items.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tbl_items.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_items.setStyleSheet(f"""
            QTableWidget {{
                background: {Colors.BG_DEEP}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; font-size: 11px;
                alternate-background-color: {Colors.BG_PANEL};
            }}
            QTableWidget::item {{ padding: 2px 4px; border-bottom: 1px solid {Colors.BORDER_DEFAULT}; }}
            QTableWidget::item:selected {{
                background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT};
            }}
            QTableWidget::item:hover {{ background: {Colors.BG_CARD}; }}
            QHeaderView::section {{
                background: {Colors.BG_CARD}; color: {Colors.TEXT_SECONDARY};
                border: none; border-right: 1px solid {Colors.BORDER_DEFAULT};
                padding: 3px 4px; font-size: 9px; font-weight: bold;
            }}
        """)
        self.tbl_items.currentItemChanged.connect(
            lambda cur, _prev: self._on_item_clicked(cur) if cur is not None else None
        )
        lay.addWidget(self.tbl_items, 1)

        self.lst = QListWidget()
        self.lst.setVisible(False)
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
        self.btn_gerar_n1.setVisible(False)   # dinâmico — funcionalidade mantida
        self.btn_gerar_n1.setToolTip("Gerar N1+N3: estrutural + robot SA (lista 1)")
        self.btn_gerar_n1.clicked.connect(self._on_gerar_n1_clicked)
        n_row1.addWidget(self.btn_gerar_n1)

        self.btn_gerar_n2 = _mbtn("▶ N2", "#1a4a2a", "#2a7a4a")
        self.btn_gerar_n2.setEnabled(False)
        self.btn_gerar_n2.setVisible(False)   # dinâmico — funcionalidade mantida
        self.btn_gerar_n2.setToolTip("Gerar N2+N4: recorte ER + robot ER (lista 2)")
        self.btn_gerar_n2.clicked.connect(self._on_gerar_n2_clicked)
        n_row1.addWidget(self.btn_gerar_n2)

        self.btn_gerar_n3 = _mbtn("▶ N3", "#4a2a1a", "#8a4a2a")
        self.btn_gerar_n3.setEnabled(False)
        self.btn_gerar_n3.setVisible(False)   # dinâmico — funcionalidade mantida
        self.btn_gerar_n3.setToolTip("Gerar N3: robot DXF via ficha SA")
        self.btn_gerar_n3.clicked.connect(self._on_gerar_n3_clicked)
        n_row1.addWidget(self.btn_gerar_n3)

        self.btn_gerar_n4 = _mbtn("▶ N4", "#2d1a47", "#5a2a8a")
        self.btn_gerar_n4.setEnabled(False)
        self.btn_gerar_n4.setVisible(False)   # dinâmico — funcionalidade mantida
        self.btn_gerar_n4.setToolTip("Gerar N4: robot DXF via ficha ER (lista 2)")
        self.btn_gerar_n4.clicked.connect(self._on_gerar_n4_clicked)
        n_row1.addWidget(self.btn_gerar_n4)
        lay.addLayout(n_row1)

        self.btn_gerar_n5 = _mbtn("▶ N5 Montagem", "#263238", "#006978")
        self.btn_gerar_n5.setToolTip("N5: montar 1 DXF consolidado dos N3 da classe atual (LJ/FV)")
        self.btn_gerar_n5.clicked.connect(self._on_gerar_n5_clicked)
        self.btn_gerar_n5.setVisible(False)   # N5 auto-dispara ao selecionar a aba N5
        lay.addWidget(self.btn_gerar_n5)

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
        self.btn_process_all.setVisible(False)   # funcionalidade mantida, botão oculto
        crop_row.addWidget(self.btn_process_all)
        lay.addLayout(crop_row)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {Colors.BORDER_DEFAULT};")
        lay.addWidget(sep)

        self.btn_analise = _mbtn("▶ Análise Geral", Colors.ACCENT_SUCCESS, "rgba(67, 160, 71, 1)")
        self.btn_analise.setToolTip("Processa o DXF estrutural N1 e preenche a lista de itens")
        self.btn_analise.clicked.connect(lambda: self.analise_requested.emit())
        lay.addWidget(self.btn_analise)

        self.btn_fase4 = _mbtn("⚙ Fase 4 — Sync", Colors.ACCENT_WARNING, "rgba(245, 124, 0, 1)")
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
        self.btn_gerar_n5.setEnabled(cls in ("LJ", "FV"))
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
        # Sub-abas LV: mostrar apenas quando LV ativo
        self._lv_subtab_widget.setVisible(cls == "LV")
        if cls == "LV":
            # Resetar sub-aba e mostrar placeholder — não carregar ainda
            self._lv_subtab = ""
            self._btn_lv_para.setChecked(False)
            self._btn_lv_passa.setChecked(False)
            self._btn_lv_para.setStyleSheet(self._lv_ss_para_inac)
            self._btn_lv_passa.setStyleSheet(self._lv_ss_pass_inac)
            self.tbl_items.blockSignals(True)
            self.tbl_items.clearSelection()
            self.tbl_items.setRowCount(1)
            _ph = QTableWidgetItem("↑ Selecione Vigas Para ou Vigas Passam")
            _ph.setFlags(_ph.flags() & ~Qt.ItemIsSelectable)
            _ph.setForeground(QColor(Colors.TEXT_DIM))
            _ph2 = QTableWidgetItem("")
            _ph2.setFlags(_ph2.flags() & ~Qt.ItemIsSelectable)
            self.tbl_items.setItem(0, 0, _ph)
            self.tbl_items.setItem(0, 1, _ph2)
            self.tbl_items.blockSignals(False)
            self._disable_all_btns()
            self.classe_changed.emit(cls)
            return
        self._populate_list(cls)
        self.classe_changed.emit(cls)   # emit APÓS populate — garante ids disponíveis

    # ── Sub-aba LV selecionada (Para / Passa) ────────────────────────
    def _select_lv_subtab(self, pp: str):
        self._lv_subtab = pp
        is_para = (pp == "Para")
        self._btn_lv_para.setChecked(is_para)
        self._btn_lv_passa.setChecked(not is_para)
        self._btn_lv_para.setStyleSheet(self._lv_ss_para_act if is_para else self._lv_ss_para_inac)
        self._btn_lv_passa.setStyleSheet(self._lv_ss_pass_inac if is_para else self._lv_ss_pass_act)
        self._populate_list("LV")

    # ── Popula lista a partir do JSON dir da obra ─────────────────────
    def _populate_list(self, cls: str):
        # LV requer que uma sub-aba esteja selecionada antes de popular
        if cls == "LV" and not self._lv_subtab:
            return
        self._populate_aligned_items(cls)
        return

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
                    it = QListWidgetItem(str(elem_id))
                    it.setData(Qt.UserRole, (cls, elem_id))
                    it.setData(Qt.UserRole + 1, recorte_path)
                    it.setForeground(QColor(Colors.TEXT_PRIMARY))
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

        if cls == "LJ" and hasattr(self, "_refresh_lj_n1_latest"):
            self._refresh_lj_n1_latest()

        json_dir  = self._current_obra_dir / self._JSON_DIRS[cls]
        prev_dir  = self._current_obra_dir / self._PREVIEW_DIRS[cls]
        prefix    = self._PREVIEW_PFX[cls]

        item_ids: list[str] = []
        db_names = self._db_item_names_for_pav(cls)
        if cls == "FV" and db_names:
            item_ids = db_names
        if cls == "LJ" and db_names:
            # Lajes N1 vêm do Structural Analyzer/Analise Geral. Não depender de
            # JSON da Fase 4, pois eles podem ainda não existir ou estar defasados.
            item_ids = db_names
        if json_dir.exists():
            all_stems = sorted(
                f.stem for f in json_dir.glob("*.json")
                if not f.stem.startswith("_") and not f.stem.startswith("vigas")
                   and not f.stem.startswith("fichas")
            )
            if db_names is not None and cls not in ("LJ", "FV"):
                db_set = set(db_names)
                if cls == "PL":
                    # Pilar: stem do JSON = nome no DB (ex: 'P18' == 'P18.json')
                    item_ids = [s for s in all_stems if s in db_set]
                elif cls == "LV":
                    # Viga: stem começa com nome no DB (ex: 'V302_A' começa com 'V302')
                    item_ids = [s for s in all_stems if any(s == n or s.startswith(n + "_") for n in db_set)]
            elif cls == "LJ" and not item_ids and self._lj_filter is not None:
                # Laje: filtrar pelos labels do DXF ativo (populado após scan async)
                item_ids = [s for s in all_stems if s in self._lj_filter]
            elif not item_ids:
                item_ids = all_stems
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
        obra_name = self._current_obra_dir.name if self._current_obra_dir is not None else ""
        pav_key   = self._current_pav or ""

        for iid in item_ids:
            n3_ok = (prev_dir / f"{prefix}{iid}.dxf").exists()
            if cls == "LV":
                base = _lv_base_from_stem(str(iid))
                pp = load_para_passa(obra_name, pav_key, "LV", base)
                display = _lv_stem_to_display(str(iid), pp)
            else:
                display = str(iid)
            it = QListWidgetItem(display)
            it.setData(Qt.UserRole, (cls, iid))
            it.setForeground(QColor(Colors.TEXT_PRIMARY))
            self.lst.addItem(it)

    @staticmethod
    def _item_sort_key(value: str):
        import re as _re
        text = str(value or "")
        parts = _re.split(r"(\d+)", text.upper())
        out = []
        for part in parts:
            out.append(int(part) if part.isdigit() else part)
        return out

    @staticmethod
    def _match_aliases(cls: str, item_id: str) -> list[str]:
        """Aliases usados para alinhar N1/N3 com N2/N4 sem exigir nome literal."""
        import re as _re
        raw = str(item_id or "").upper().strip()
        raw = _re.sub(r"\s+", "", raw)
        raw = _re.sub(r"_FUNDO$", "", raw)
        aliases: list[str] = []

        def add(value: str):
            value = _re.sub(r"\s+", "", str(value or "").upper())
            value = _re.sub(r"_FUNDO$", "", value)
            value = _re.sub(r"(?:\.C)+$", ".C", value)
            value = _re.sub(r"^([VP]\d+)V$", r"\1", value)
            if value and value not in aliases:
                aliases.append(value)

        add(raw)
        add(raw.replace(".C", ""))
        if cls == "LV":
            # Strip prefixes/suffixes: "LV-V10.A-Para", "V10_A_Para" → core aliases
            clean = _re.sub(r"^LV-", "", raw)                           # "V10.A-PARA" / "V10_A_PARA"
            clean = _re.sub(r"-(PARA|PASSA)$", "", clean)               # strip -PARA/-PASSA
            clean = _re.sub(r"_(PARA|PASSA)$", "", clean)               # strip _Para/_Passa
            add(clean)
            add(clean.replace(".", "_"))                                  # "V10_A"
            add(clean.replace("_", "."))                                  # "V10.A"
            base_no_face = _re.sub(r"[_\.][AB]$", "", clean)            # "V10"
            add(base_no_face)
            add(_re.sub(r"_[AB]$", "", raw))
            # Aliases Para/Passa para correspondência com recortes futuros
            for sfx in ("-PARA", "-PASSA", "_PARA", "_PASSA"):
                add(base_no_face + sfx)
        if cls == "FV":
            add(_re.sub(r"(?:\.C)+$", "", raw))
            add(raw if raw.endswith(".C") else f"{raw}.C")
        for token in _re.findall(r"[VP]\d+[A-Z]?(?:\.C)?", raw):
            add(token)
            add(token.replace(".C", ""))
            if cls == "FV" and not token.endswith(".C"):
                add(f"{token}.C")
        return aliases or [raw]

    def _structural_item_rows(self, cls: str) -> dict[str, dict]:
        if self._current_obra_dir is None:
            return {}
        if cls == "LJ":
            try:
                parent = self.parent()
                while parent is not None and not hasattr(parent, "tri_level"):
                    parent = parent.parent()
                if parent is not None and hasattr(parent, "tri_level"):
                    parent.tri_level._refresh_lj_n1_from_latest_sa()
            except Exception:
                pass

        json_dir = self._current_obra_dir / self._JSON_DIRS[cls]
        prev_dir = self._current_obra_dir / self._PREVIEW_DIRS[cls]
        prefix = self._PREVIEW_PFX[cls]

        item_ids: list[str] = []
        db_names = self._db_item_names_for_pav(cls)
        if cls in ("FV", "LJ") and db_names:
            item_ids = db_names
        if json_dir.exists():
            all_stems = sorted(
                f.stem for f in json_dir.glob("*.json")
                if not f.stem.startswith("_") and not f.stem.startswith("vigas")
                   and not f.stem.startswith("fichas")
            )
            if db_names is not None and cls not in ("LJ", "FV"):
                db_set = set(db_names)
                if cls == "PL":
                    item_ids = [s for s in all_stems if s in db_set]
                elif cls == "LV":
                    item_ids = [s for s in all_stems if any(s == n or s.startswith(n + "_") for n in db_set)]
            elif cls == "LJ" and not item_ids and self._lj_filter is not None:
                item_ids = [s for s in all_stems if s in self._lj_filter]
            elif not item_ids:
                item_ids = all_stems
        if not item_ids and cls == "LV":
            item_ids = VIGAS_LV_LIST

        import re as _re
        obra_name = self._current_obra_dir.name if self._current_obra_dir is not None else ""
        pav_key = self._current_pav or ""
        rows: dict[str, dict] = {}
        for iid in item_ids:
            # verifica DXF N3 existente (sem face e sem Para/Passa no nome)
            base_stem = _re.sub(r'[_\.][AB]$', '', str(iid))
            n3_ok = ((prev_dir / f"{prefix}{iid}.dxf").exists() or
                     (prev_dir / f"{prefix}{base_stem}.dxf").exists())
            if cls == "LV":
                # Cada face LV gera DUAS instâncias independentes: Para e Passa
                for pp in ("para", "passa"):
                    virt_id = f"{iid}_{pp.capitalize()}"
                    display_text = _lv_stem_to_display(str(iid), pp)
                    rows[virt_id] = {
                        "id": virt_id,
                        "text": display_text,
                        "source": "estrutural",
                        "recorte_path": "",
                        "ok": n3_ok,
                        "base_stem": str(iid),
                    }
            else:
                display_text = str(iid)
                rows[str(iid)] = {
                    "id": str(iid),
                    "text": display_text,
                    "source": "estrutural",
                    "recorte_path": "",
                    "ok": n3_ok,
                }
        return rows

    def _reverse_item_rows(self, cls: str) -> dict[str, dict]:
        obra_name = self._current_obra_dir.name if self._current_obra_dir is not None else ""
        pav_key   = self._current_pav or ""
        rows = self._load_reverse_items(obra_name, cls, pav_key)
        out: dict[str, dict] = {}
        for elem_id, conf, status, recorte_path in rows:
            if cls == "LV":
                # reverse_eng_recortes guarda só o ID base (sem face); exibe como "LV-V10"
                pp = load_para_passa(obra_name, pav_key, "LV", str(elem_id).upper())
                pp_suffix = f"-{pp.capitalize()}" if pp else ""
                disp = f"LV-{elem_id}{pp_suffix}"
            else:
                disp = str(elem_id)
                pp = ""
            out[str(elem_id)] = {
                "id": str(elem_id),
                "text": disp,
                "source": "reverso",
                "recorte_path": recorte_path or "",
                "status": status or "",
                "conf": float(conf or 0.0),
                "pp": (pp or "").lower(),  # "para" | "passa" | ""
            }
        return out

    def _row_has_attention(self, cls: str, row_data: dict | None) -> bool:
        if not row_data:
            return False
        try:
            obra = self._current_obra_dir.name if self._current_obra_dir is not None else ""
            pav = self._current_pav or ""
            scope = "N4" if row_data.get("source") == "reverso" else "N3"
            return has_attention(obra, pav, cls, row_data.get("id", ""), scope)
        except Exception:
            return False

    def _row_human_validated(self, cls: str, row_data: dict | None) -> bool:
        if not row_data:
            return False
        try:
            obra = self._current_obra_dir.name if self._current_obra_dir is not None else ""
            pav = self._current_pav or ""
            scope = "N4" if row_data.get("source") == "reverso" else "N3"
            return is_human_validated(obra, pav, cls, row_data.get("id", ""), scope)
        except Exception:
            return False

    def _make_item_cell(self, cls: str, row_data: dict | None) -> QTableWidgetItem:
        if not row_data:
            item = QTableWidgetItem("")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QColor(Colors.TEXT_DIM))
            return item
        text = row_data.get("text") or row_data.get("id") or ""
        if self._row_human_validated(cls, row_data) and "✓" not in text:
            text = f"{text} ✓"
        if self._row_has_attention(cls, row_data) and "⚠" not in text:
            text = f"{text} ⚠"
        item = QTableWidgetItem(text)
        item.setData(Qt.UserRole, (cls, row_data.get("id", ""), row_data.get("source", "estrutural")))
        item.setData(Qt.UserRole + 1, row_data.get("recorte_path", ""))
        item.setForeground(QColor(Colors.TEXT_PRIMARY))
        if row_data.get("source") == "reverso":
            status = row_data.get("status", "")
            item.setToolTip(f"N2/N4: {row_data.get('id')}\nStatus: {status}\nRecorte: {row_data.get('recorte_path', '')}")
        else:
            item.setToolTip(f"N1/N3: {row_data.get('id')}")
        return item

    def _populate_aligned_items(self, cls: str):
        prev_item = self._selected_item
        prev_source = self._selected_source
        self.tbl_items.blockSignals(True)
        try:
            self.tbl_items.clearSelection()
            self.tbl_items.setCurrentCell(-1, -1)
            self.tbl_items.setRowCount(0)
            self.lst.clear()

            structural = self._structural_item_rows(cls)
            reverse = self._reverse_item_rows(cls)

            # Filtrar por sub-aba Para/Passa quando LV está ativo
            if cls == "LV" and self._lv_subtab:
                pp_lower = self._lv_subtab.lower()
                structural = {k: v for k, v in structural.items()
                              if k.lower().endswith(f"_{pp_lower}")}
                reverse = {k: v for k, v in reverse.items()
                           if not v.get("pp") or v.get("pp") == pp_lower}

            reverse_by_alias: dict[str, dict] = {}
            for rev_id, rev_data in reverse.items():
                for alias in self._match_aliases(cls, rev_id):
                    reverse_by_alias.setdefault(alias, rev_data)

            row_pairs: list[tuple[str, dict | None, dict | None]] = []
            used_reverse_ids: set[str] = set()
            for struct_id in sorted(structural, key=self._item_sort_key):
                rev_data = None
                for alias in self._match_aliases(cls, struct_id):
                    rev_data = reverse_by_alias.get(alias)
                    if rev_data:
                        break
                if rev_data:
                    used_reverse_ids.add(str(rev_data.get("id", "")))
                row_pairs.append((struct_id, structural.get(struct_id), rev_data))

            for rev_id in sorted(reverse, key=self._item_sort_key):
                if rev_id not in used_reverse_ids:
                    row_pairs.append((rev_id, None, reverse.get(rev_id)))

            if not row_pairs:
                self.tbl_items.setRowCount(1)
                empty = QTableWidgetItem("sem itens")
                empty.setFlags(empty.flags() & ~Qt.ItemIsSelectable)
                empty.setForeground(QColor(Colors.TEXT_DIM))
                blank = QTableWidgetItem("")
                blank.setFlags(blank.flags() & ~Qt.ItemIsSelectable)
                self.tbl_items.setItem(0, 0, empty)
                self.tbl_items.setItem(0, 1, blank)
                self._disable_all_btns()
                return

            self.tbl_items.setRowCount(len(row_pairs))
            for row, (key, struct_data, rev_data) in enumerate(row_pairs):
                self.tbl_items.setItem(row, 0, self._make_item_cell(cls, struct_data))
                self.tbl_items.setItem(row, 1, self._make_item_cell(cls, rev_data))

                legacy_source = struct_data or rev_data
                if legacy_source:
                    legacy = QListWidgetItem(legacy_source.get("id", key))
                    legacy.setData(Qt.UserRole, (cls, legacy_source.get("id", key)))
                    legacy.setData(Qt.UserRole + 1, legacy_source.get("recorte_path", ""))
                    self.lst.addItem(legacy)

            self.tbl_items.resizeRowsToContents()
            self.btn_process_all.setEnabled(True)
            self.btn_gerar_n5.setEnabled(cls in ("LJ", "FV"))
            self._restore_table_selection(prev_item, prev_source, emit=False)
        finally:
            self.tbl_items.blockSignals(False)
        self._restore_table_selection(prev_item, prev_source, emit=False)

    def _restore_table_selection(self, item_id: str | None = None, source: str | None = None,
                                 emit: bool = False) -> bool:
        item_id = item_id or self._selected_item
        source = source or self._selected_source
        if not item_id:
            return False
        for row in range(self.tbl_items.rowCount()):
            for col in range(self.tbl_items.columnCount()):
                item = self.tbl_items.item(row, col)
                data = item.data(Qt.UserRole) if item else None
                if not data or len(data) < 2:
                    continue
                if str(data[1]) != str(item_id):
                    continue
                if source and len(data) >= 3 and data[2] != source:
                    continue
                self.tbl_items.setCurrentCell(row, col)
                self.tbl_items.scrollToItem(item)
                if emit:
                    self._on_item_clicked(item)
                return True
        return False

    def _project_id_for_current_pav(self, conn):
        """Resolve o projeto atual por obra+pavimento, aceitando chave curta ou nome completo."""
        if not self._current_pav or self._current_obra_dir is None:
            return None
        import re as _re

        obra_name = self._current_obra_dir.name
        row = conn.execute(
            "SELECT id FROM projects WHERE work_name=? AND pavement_name=? LIMIT 1",
            (obra_name, self._current_pav)
        ).fetchone()
        if row:
            return row[0]

        pav_digits = "".join(_re.findall(r"\d+", str(self._current_pav)))
        if pav_digits:
            row = conn.execute(
                "SELECT id FROM projects WHERE work_name=? AND pavement_name LIKE ? "
                "ORDER BY updated_at DESC LIMIT 1",
                (obra_name, f"%{pav_digits}%")
            ).fetchone()
            if row:
                return row[0]

        return None

    def _db_item_names_for_pav(self, cls: str) -> "list[str] | None":
        """Retorna prefixos de JSON para filtrar itens do pavimento atual via DB.

        Para PL: pillars.name é idêntico ao stem do JSON ('P18' → 'P18.json').
        Para LV/FV: beams.name pode ser 'V302' ou 'F.V303.C-1' — extrai prefixo
            V\\d+[A-Z]? para filtrar stems ('V302_A', 'V302_fundo').
        Para LJ: retorna diretamente as lajes salvas pelo Structural Analyzer.
        Retorna None se pavimento não selecionado ou DB inacessível.
        """
        import re as _re
        if not self._current_pav or self._current_obra_dir is None:
            return None
        try:
            import sqlite3 as _sql
            conn = _sql.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            project_id = self._project_id_for_current_pav(conn)
            if not project_id:
                conn.close()
                return None
            if cls == "PL":
                rows = conn.execute(
                    "SELECT DISTINCT name FROM pillars WHERE project_id=? ORDER BY name",
                    (project_id,)
                ).fetchall()
                names = [r[0] for r in rows if r[0]]
            elif cls == "FV":
                rows = conn.execute(
                    "SELECT DISTINCT viga_nome FROM beam_elements "
                    "WHERE project_id=? AND classe='FV' "
                    "AND (campos_json LIKE '%n_paineis_logicos%' OR campos_json LIKE '%dim_text%') "
                    "ORDER BY viga_nome",
                    (project_id,)
                ).fetchall()
                prefixes: set[str] = set()
                for (n,) in rows:
                    if not n:
                        continue
                    m = _re.search(r'(V\d+[A-Z]?)', str(n).upper())
                    if m:
                        prefixes.add(m.group(1))
                names = sorted(prefixes)
            elif cls == "LV":
                rows = conn.execute(
                    "SELECT DISTINCT name FROM beams WHERE project_id=? ORDER BY name",
                    (project_id,)
                ).fetchall()
                # Normaliza nomes para prefixo de viga: 'F.V303.C-1' → 'V303', 'V302' → 'V302'
                prefixes: set[str] = set()
                for (n,) in rows:
                    if not n:
                        continue
                    m = _re.search(r'(V\d+[A-Z]?)', n.upper())
                    if m:
                        prefixes.add(m.group(1))
                names = sorted(prefixes)
            elif cls == 'LJ':
                rows = conn.execute(
                    "SELECT DISTINCT laje_nome FROM slab_elements "
                    "WHERE project_id=? AND classe='LAJ' ORDER BY "
                    "CAST(REPLACE(UPPER(laje_nome), 'L', '') AS INTEGER), laje_nome",
                    (project_id,)
                ).fetchall()
                names = []
                seen = set()
                for (name,) in rows:
                    if name and name not in seen:
                        seen.add(name)
                        names.append(name)
                if not names:
                    rows = conn.execute(
                        "SELECT name, id_item FROM slabs WHERE project_id=? ORDER BY "
                        "CAST(COALESCE(NULLIF(id_item, ''), '999999') AS INTEGER), name",
                        (project_id,)
                    ).fetchall()
                    for name, _id_item in rows:
                        if name and name not in seen:
                            seen.add(name)
                            names.append(name)
            else:
                names = None
            conn.close()
            return names if names else None
        except Exception as e:
            print(f"[CE] _db_item_names_for_pav error: {e}")
            return None

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
        """Converte pav_key para o formato de pavimento do DB (reverse_eng_fichas.pavimento).

        Suporta:
          '13PAV', '13_PAV'                      → '13_PAV'
          'TIPO - 3 AO 12PAV'                    → '12_PAV'
          'TMC-EST-PE-6000-13P-R03_R2018_...'   → '13_PAV'  (DXF filename do projects)
          'TMC-EST-EX-3000-1PV-R00_R2018_...'   → '1_PAV'
          'PARAISO - COBERTURA...'               → 'COBERTURA'
          'TËRREO' / 'TERREO' / '-TER-'         → 'TERREO'
        """
        import re as _re, unicodedata as _ucd
        s = _ucd.normalize('NFKD', pav_key)
        s = ''.join(c for c in s if not _ucd.combining(c)).upper().strip()

        if 'TERREO' in s or 'TRREO' in s or _re.search(r'[-_ ]TER[-_ ]', s):
            return 'TERREO'
        if 'COB' in s:
            return 'COBERTURA'
        # Número seguido de PAV: "13PAV", "13_PAV", "TIPO - 3 AO 12PAV"
        matches = _re.findall(r'(\d+)\s*PAV', s)
        if matches:
            return f"{matches[-1]}_PAV"
        # DXF filename style: -13P- ou -1PV- (número + P ou PV entre separadores)
        matches = _re.findall(r'[-_ ](\d{1,2})P(?:V)?(?:[-_ ]|$)', s)
        if matches:
            return f"{matches[-1]}_PAV"
        if 'TIPO' in s or _re.search(r'[-_ ]TIP[-_ ]', s):
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
                "WHERE (obra_name=? OR obra_name='') AND classe=? "
                "ORDER BY elemento_id, CASE WHEN obra_name=? THEN 0 ELSE 1 END, created_at DESC",
                (obra_name, db_cls, obra_name)
            )
            all_rows = cur.fetchall()
            conn.close()

            db_pav = self._pav_key_to_db_pav(pav_key) if pav_key else ""

            _priority = {'aprovado': 0, 'manual_sel': 1, 'manual': 2,
                          'auto_aprovado': 3, 'motor': 4}
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
    def _refresh_lj_n1_latest(self):
        try:
            parent = self.parent()
            while parent is not None and not hasattr(parent, "tri_level"):
                parent = parent.parent()
            if parent is not None and hasattr(parent, "tri_level"):
                parent.tri_level._refresh_lj_n1_from_latest_sa()
        except Exception:
            pass

    def set_obra(self, obra_dir_str: str):
        from pathlib import Path as _P
        self._current_obra_dir = _P(obra_dir_str) if obra_dir_str else None
        self._lj_filter = None  # resetar filtro LJ ao mudar obra
        self._populate_list(self._current_classe)

    def set_lj_filter(self, est_labels: dict):
        """Chamado quando scan do DXF conclui — filtra lista LJ pelos labels do DXF ativo."""
        self._lj_filter = {k for k in est_labels if k.startswith('L') and k[1:].isdigit()}
        if self._current_classe == 'LJ':
            self._populate_list('LJ')

    # ── Set pav (chamado quando troca pavimento no combo) ─────────────
    def set_pav(self, pav_key: str):
        """Atualiza o pavimento atual e repopula a lista."""
        self._current_pav = pav_key
        self._lj_filter = None  # resetar filtro LJ ao mudar pavimento (scan novo será iniciado)
        self._populate_list(self._current_classe)

    # ── Click item ────────────────────────────────────────────────────
    def _on_item_clicked(self, item):
        data = item.data(Qt.UserRole)
        if not data:
            return
        if len(data) >= 3:
            classe, item_id, source = data
        else:
            classe, item_id = data
            source = self._current_flow
        self._selected_classe = classe
        self._selected_item   = item_id
        self._selected_source = source
        self._current_flow = source
        # Captura o recorte_path já salvo no item (estado atual do DB, sem re-consulta)
        self._selected_recorte_path = item.data(Qt.UserRole + 1) or ""
        for btn in (self.btn_process, self.btn_gerar_n1,
                    self.btn_gerar_n2, self.btn_gerar_n3, self.btn_gerar_n4):
            btn.setEnabled(True)
        self.btn_gerar_n5.setEnabled(self._current_classe in ("LJ", "FV"))
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

    def _on_gerar_n5_clicked(self):
        cls = self._current_classe
        if cls not in ("LJ", "FV"):
            self.set_status("N5 suporta apenas Lajes e Fundos de Viga neste ciclo", Colors.TEXT_DIM)
            return
        self._disable_all_btns()
        self.gerar_n5_requested.emit(cls, self.current_item_ids())

    def current_item_ids(self) -> list:
        ids = []
        for row in range(self.tbl_items.rowCount()):
            item = self.tbl_items.item(row, 0)
            data = item.data(Qt.UserRole) if item else None
            if not data:
                continue
            cls, item_id = data[0], data[1]
            if cls == self._current_classe and item_id:
                ids.append(item_id)
        return ids

    def _disable_all_btns(self):
        for btn in (self.btn_process, self.btn_gerar_n1,
                    self.btn_gerar_n2, self.btn_gerar_n3, self.btn_gerar_n4,
                    self.btn_gerar_n5, self.btn_process_all):
            btn.setEnabled(False)

    def _enable_item_btns(self):
        if self._selected_item:
            for btn in (self.btn_process, self.btn_gerar_n1,
                        self.btn_gerar_n2, self.btn_gerar_n3, self.btn_gerar_n4):
                btn.setEnabled(True)
        self.btn_gerar_n5.setEnabled(self._current_classe in ("LJ", "FV"))
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
        count = self.tbl_items.rowCount()
        if count == 0:
            return
        cur = self.tbl_items.currentRow()
        if cur < 0 and self._selected_item:
            self._restore_table_selection(emit=False)
            cur = self.tbl_items.currentRow()
        if cur < 0:
            new_row = 0 if delta > 0 else count - 1
        else:
            new_row = max(0, min(count - 1, cur + delta))
        if new_row != cur:
            col = self.tbl_items.currentColumn()
            if col < 0:
                col = 0 if self._selected_source != "reverso" else 1
            target = self.tbl_items.item(new_row, col)
            if target is None or not target.data(Qt.UserRole):
                alt_col = 1 - col if self.tbl_items.columnCount() > 1 else col
                alt = self.tbl_items.item(new_row, alt_col)
                if alt is not None and alt.data(Qt.UserRole):
                    col = alt_col
            self.tbl_items.setCurrentCell(new_row, col)
            # currentItemChanged dispara → _on_item_clicked → item_selected signal


class TriLevelArea(QWidget):
    """Área central: 3 colunas com scroll horizontal + fichas de dados."""

    scan_done = Signal(dict)   # emitido quando scan do DXF estrutural conclui; payload = est_labels

    def __init__(self):
        super().__init__()
        self._current_obra: str = OBRA_TREINO_16.name
        self._current_pav:  str = ""
        self._discovery:    dict = {}
        self._scan_worker: "DXFScanWorker | None" = None
        self._retiring_scan_workers: list = []   # mantém refs até QThread terminar (evita crash ao destruir thread ativa)
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
            ("#00bcd4", "#263238"),   # N5 ciano
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
        db_lajes = self._load_n1_lajes_from_db(obra_dir.name)
        if db_lajes:
            if not isinstance(self._lajes_fase3, dict):
                self._lajes_fase3 = {}
            self._lajes_fase3.update(db_lajes)

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

    def _project_id_for_obra_pav(self, obra_name: str):
        """Resolve project_id por obra+pavimento atual, incluindo pavimento abreviado."""
        if not obra_name or not self._current_pav:
            return None
        import re as _re
        import sqlite3 as _sqlite3

        try:
            conn = _sqlite3.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            row = conn.execute(
                "SELECT id FROM projects WHERE work_name=? AND pavement_name=? LIMIT 1",
                (obra_name, self._current_pav)
            ).fetchone()
            if row:
                conn.close()
                return row[0]

            pav_digits = "".join(_re.findall(r"\d+", str(self._current_pav)))
            if pav_digits:
                row = conn.execute(
                    "SELECT id FROM projects WHERE work_name=? AND pavement_name LIKE ? "
                    "ORDER BY updated_at DESC LIMIT 1",
                    (obra_name, f"%{pav_digits}%")
                ).fetchone()
                if row:
                    conn.close()
                    return row[0]
            conn.close()
        except Exception as exc:
            _ce_log("N1 project lookup error", obra_name, self._current_pav, exc)
        return None

    def _load_n1_lajes_from_db(self, obra_name: str) -> dict:
        """Carrega lajes N1 salvas pelo Structural Analyzer para a obra/pav atual."""
        project_id = self._project_id_for_obra_pav(obra_name)
        if not project_id:
            return {}
        import json as _json
        import sqlite3 as _sqlite3

        try:
            conn = _sqlite3.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            conn.row_factory = _sqlite3.Row
            rows_el = conn.execute(
                "SELECT laje_nome, campos_json, is_validated, updated_at FROM slab_elements "
                "WHERE project_id=? AND classe='LAJ' "
                "ORDER BY updated_at DESC",
                (project_id,)
            ).fetchall()
            lajes = {}
            for row in rows_el:
                try:
                    data = _json.loads(row["campos_json"] or "{}")
                except Exception:
                    data = {}
                if not isinstance(data, dict):
                    continue
                name = data.get("nome") or row["laje_nome"]
                if not name:
                    continue
                data.setdefault("nome", name)
                data.setdefault("name", name)
                data["_ce_n1_source"] = "slab_elements"
                data["_ce_n1_updated_at"] = row["updated_at"]
                if row["is_validated"] is not None:
                    data.setdefault("is_validated", bool(row["is_validated"]))
                lajes[str(name)] = data
            if lajes:
                conn.close()
                return lajes

            rows = conn.execute(
                "SELECT * FROM slabs WHERE project_id=? ORDER BY "
                "CAST(COALESCE(NULLIF(id_item, ''), '999999') AS INTEGER), name",
                (project_id,)
            ).fetchall()
            conn.close()
        except Exception as exc:
            _ce_log("N1 lajes db load error", obra_name, self._current_pav, exc)
            return {}

        lajes = {}
        for row in rows:
            s = dict(row)
            try:
                extra = _json.loads(s.get("extra_data_json") or "{}")
                if isinstance(extra, dict):
                    s.update(extra)
            except Exception:
                pass
            try:
                s["points"] = _json.loads(s.get("points_json") or "[]")
            except Exception:
                s["points"] = []
            name = s.get("name")
            if not name:
                continue
            s.setdefault("nome", name)
            if "area_cm2" not in s and s.get("area") is not None:
                s["area_cm2"] = s.get("area")
            if "coordenadas" not in s and s.get("points"):
                s["coordenadas"] = s["points"]
            s["_ce_n1_source"] = "slabs"
            lajes[name] = s
        return lajes

    def _refresh_lj_n1_from_latest_sa(self) -> None:
        """Recarrega LAJ N1 da fonte persistida mais recente do Structural Analyzer."""
        if not self._current_obra:
            return
        db_lajes = self._load_n1_lajes_from_db(self._current_obra)
        if db_lajes:
            if not isinstance(self._lajes_fase3, dict):
                self._lajes_fase3 = {}
            self._lajes_fase3.update(db_lajes)

    @staticmethod
    def _points_bbox(points: list, pad: float = 35.0):
        pts = [
            (float(p[0]), float(p[1]))
            for p in (points or [])
            if isinstance(p, (list, tuple)) and len(p) >= 2
        ]
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

    def _get_lj_n1_data(self, item_id: str) -> dict:
        if not isinstance(self._lajes_fase3, dict):
            return {}
        data = self._lajes_fase3.get(item_id, {})
        return data if isinstance(data, dict) else {}

    def _get_lj_n1_points(self, item_id: str) -> list:
        lj = self._get_lj_n1_data(item_id)
        points = lj.get("coordenadas") or lj.get("points") or []
        if not points:
            links = (lj.get("links") or {}).get("laje_outline_segs", {})
            if isinstance(links, dict):
                for link in links.get("contour", []) or []:
                    pts = link.get("points") if isinstance(link, dict) else None
                    if pts and len(pts) >= 3:
                        points = pts
                        break
        return points or []

    def _start_async_scan(self, obra_dir: Path):
        """Inicia scan do DXF estrutural em QThread background — sem bloquear UI.
        Cancela scan anterior se ainda em andamento."""
        # Retirement seguro: não destruir QThread em execução (causa STATUS_ACCESS_VIOLATION
        # no Python 3.14/Windows). Manter ref Python viva até o thread terminar sozinho,
        # igual ao padrão do AnaliseGeralWorker com _retiring_analise_workers.
        if hasattr(self, '_scan_worker') and self._scan_worker is not None:
            old_sw = self._scan_worker
            try:
                old_sw.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            if not hasattr(self, '_retiring_scan_workers'):
                self._retiring_scan_workers = []
            self._retiring_scan_workers.append(old_sw)
            def _retire_sw(w=old_sw, lst=self._retiring_scan_workers):
                try:
                    lst.remove(w)
                except ValueError:
                    pass
                try:
                    w.deleteLater()
                except RuntimeError:
                    pass
            try:
                old_sw.finished.connect(_retire_sw)
            except (RuntimeError, TypeError):
                _retire_sw()
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
            self.scan_done.emit(self._est_labels)
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

    @staticmethod
    def _find_n1_project_dxf(obra_name: str, pav_name: str) -> "Path | None":
        """Busca dxf_path gravado em projects — o mesmo DXF que o SA carregou para análise."""
        if not obra_name or not pav_name:
            return None
        try:
            import sqlite3
            from pathlib import Path as _P
            conn = sqlite3.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            cur = conn.execute(
                "SELECT dxf_path FROM projects WHERE work_name=? AND pavement_name=? LIMIT 1",
                (obra_name, pav_name))
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                p = _P(row[0])
                if p.exists():
                    return p
        except Exception as e:
            print(f"[CE] _find_n1_project_dxf error: {e}")
        return None

    def _find_n1_dxf(self, obra_dir: Path) -> "Path | None":
        """Retorna DXF do pavimento atual — usa projects.dxf_path (mesmo que o SA).
        Fallback: Estruturais_Pavimentos_Limpos → Fase-1 bruto."""
        p = self._find_n1_project_dxf(self._current_obra, self._current_pav or "")
        if p:
            return p
        return self._find_n1_clean_dxf(obra_dir, self._current_pav or "")

    def _find_n1_clean_dxf(self, obra_dir: Path, pav: str) -> "Path | None":
        """Busca DXF limpo em Fase-2_Triagem/Estruturais_Pavimentos_Limpos/ para o pavimento dado.
        Estratégia de matching por tokens derivados do nome do pavimento classificado.
        Fallback para DXF bruto se não encontrado."""
        import re as _re

        clean_folder = obra_dir / "Fase-2_Triagem" / "Estruturais_Pavimentos_Limpos"
        pav_up = pav.upper().strip()

        # Tokens de busca derivados do nome do pavimento (ex: "13PAV" → ["PAVIMENTO_13", ...])
        def _pav_tokens(name: str) -> list[str]:
            name_up = name.upper()
            tokens: list[str] = []
            # Prioriza número de padrão DXF-style: -13P- ou -1PV- (antes do primeiro número genérico)
            m_dxf = _re.search(r'[-_ ](\d{1,2})P(?:AV?|V)?[-_ ]', name_up)
            if m_dxf:
                n = m_dxf.group(1)
            else:
                nums = _re.findall(r'\d+', name_up)
                n = nums[0] if nums else None
            if n:
                tokens += [f"PAVIMENTO_{n}", f"PAVIMENTO-{n}", f"PAVIMENTO {n}",
                           f"{n}-PAV", f"{n}_PAV", f"{n}PAV",
                           f"{n}-PAVIMENTO", f"{n}_PAVIMENTO"]
            # Keywords especiais — chaves curtas para cobrir abreviações DXF (-TER-, -TIP-, -COB-)
            kw_map = {
                "TER":  ["TERREO", "TÉRREO"],
                "TIP":  ["TIPO", "PAVIMENTO-TIPO", "PAVIMENTO_TIPO"],
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
            self._refresh_lj_n1_from_latest_sa()
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
        # Para LV/FV: strip Para/Passa virtual suffix e depois face
        if classe in ("LV", "FV"):
            import re
            clean = re.sub(r'_(Para|Passa)$', '', item_id)   # "V301_A_Para" → "V301_A"
            stem = re.sub(r'[_\.]([AB])$', '', clean)         # "V301_A" → "V301"
            for cand in (clean, stem):
                p2 = fase6 / f"{pfx}{cand}.dxf"
                if p2.exists():
                    return p2
        return None

    def _get_n1_bbox_for(self, item_id: str, classe: str = "", R: int = 134):
        """Retorna bbox do item no DXF estrutural usando labels escaneados.
        R=134 (era 267/2) e pad=34 (era 67/2) → zoom 6x mais perto que original.
        Normaliza sufixos de face: V301_A/V301_fundo → V301."""
        import re as _re
        if str(classe).upper() == "LJ":
            lj_bbox = self._points_bbox(self._get_lj_n1_points(item_id), pad=20.0)
            if lj_bbox:
                return lj_bbox
        label_id = _re.sub(r'[_.]([A-Da-d]|fundo)$', '', item_id, flags=_re.I)
        fv_bbox = self._get_n1_fv_bbox_from_db(label_id) if str(classe).upper() == "FV" else None
        if fv_bbox:
            return fv_bbox
        pos = self._est_labels.get(label_id) or self._est_labels.get(item_id)
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

    def _get_n1_fv_bbox_from_db(self, item_id: str):
        """BBox do fundo N1 salvo pela Analise Geral em beam_elements."""
        data = self._get_n1_fv_data_from_db(item_id)
        if not data:
            return None
        import re as _re

        name = _re.sub(r'\.C$', '', str(item_id).strip(), flags=_re.I)
        pos = self._est_labels.get(name) or self._est_labels.get(f"{name}.C") or self._est_labels.get(item_id)
        if not pos:
            return None
        xs, ys = [], []
        dim_width = float(data.get("h_n1") or data.get("h_espessura") or 0) or 20.0
        is_horizontal = bool(data.get("is_horizontal", True))
        for seg in data.get("segmentos_fundo", []) or []:
            if not isinstance(seg, dict) or not seg.get("coord"):
                continue
            try:
                c0 = float(seg["coord"][0])
                c1 = float(seg["coord"][1])
                ficha = seg.get("ficha") if isinstance(seg.get("ficha"), dict) else {}
                w = float(ficha.get("largura_total_fundo") or seg.get("dim_width") or dim_width or 20.0)
                half = max(w / 2.0, 4.0)
                if is_horizontal:
                    xs.extend([c0, c1])
                    ys.extend([float(pos[1]) - half, float(pos[1]) + half])
                else:
                    xs.extend([float(pos[0]) - half, float(pos[0]) + half])
                    ys.extend([c0, c1])
            except Exception:
                continue
        if not xs or not ys:
            return None
        pad = 35.0
        return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)

    def _get_n1_fv_data_from_db(self, item_id: str) -> dict:
        if not self._current_obra or not self._current_pav or not item_id:
            return {}
        import json as _json
        import re as _re
        import sqlite3 as _sqlite3

        name = str(item_id).strip()
        name = _re.sub(r'_fundo$', '', name, flags=_re.I)
        name = _re.sub(r'\.C$', '', name, flags=_re.I)
        candidates = [name, f"{name}.C", f"{name}_fundo"]
        pav_digits = "".join(_re.findall(r"\d+", str(self._current_pav)))
        try:
            conn = _sqlite3.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            conn.row_factory = _sqlite3.Row
            if pav_digits:
                proj = conn.execute(
                    "SELECT id FROM projects WHERE work_name=? AND pavement_name LIKE ? LIMIT 1",
                    (self._current_obra, f"%{pav_digits}%"),
                ).fetchone()
            else:
                proj = conn.execute(
                    "SELECT id FROM projects WHERE work_name=? LIMIT 1",
                    (self._current_obra,),
                ).fetchone()
            if not proj:
                conn.close()
                return {}
            marks = ",".join("?" for _ in candidates)
            row = conn.execute(
                f"SELECT campos_json FROM beam_elements "
                f"WHERE project_id=? AND classe='FV' AND viga_nome IN ({marks}) "
                f"ORDER BY CASE WHEN campos_json LIKE '%n_paineis_logicos%' THEN 0 "
                f"WHEN campos_json LIKE '%dim_text%' THEN 1 ELSE 2 END, updated_at DESC LIMIT 1",
                [proj["id"], *candidates],
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT campos_json FROM beam_elements "
                    "WHERE project_id=? AND classe='FV' AND viga_nome LIKE ? "
                    "ORDER BY CASE WHEN campos_json LIKE '%n_paineis_logicos%' THEN 0 "
                    "WHEN campos_json LIKE '%dim_text%' THEN 1 ELSE 2 END, updated_at DESC LIMIT 1",
                    (proj["id"], f"%{name}%"),
                ).fetchone()
            conn.close()
            if not row:
                return {}
            data = _json.loads(row["campos_json"] or "{}")
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            _ce_log("N1 FV data db error", item_id, exc)
            return {}

    def _get_n2_bbox_for(self, item_id: str, classe: str = 'LV'):
        """Retorna bbox do item no DXF STOG real.
        - LV: busca NOMENCLATURA no KB (ents do DXF de eng. reversa)
        - PL: usa _est_labels (posição no DXF estrutural) — N2 é crop do DXF estrutural
        - LJ: usa motor reverso no recorte _sel_ para enquadrar a área interna
        - FV: retorna None (auto-bbox = view completa)
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

        if classe == 'LJ':
            return self._get_lj_content_bbox_for(item_id)

        if classe == 'FV':
            return None  # auto-bbox

        # LV: usa KB (NOMENCLATURA labels)
        if not self._kb_ents:
            return None
        # IDs virtuais: strip Para/Passa antes de buscar no KB
        lv_stem = _lv_strip_pp(item_id)   # "V301_A_Para" → "V301_A"
        # KB usa ponto (V4.A), NavSidebar usa underscore (V4_A) — normalizar
        kb_id = lv_stem.replace('_', '.')
        cx = cy = None
        for e in self._kb_ents:
            if e.get('type') not in ('MTEXT', 'TEXT'):
                continue
            c = (e.get('content', '') or '').replace('\\P', '\n').split('\n')[0].strip()
            if c in (lv_stem, kb_id) and e.get('layer', '') == 'NOMENCLATURA':
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

    def _get_lj_content_bbox_for(self, item_id: str, pad: float = 45.0):
        """BBox da área interna LAJ em coordenadas STOG, com folga para cotas."""
        try:
            import re as _re
            import sys as _sys

            recortes_dir = (DADOS_OBRAS_ROOT / self._current_obra /
                            "Fase-2_Triagem" / "recortes_reversos")
            if not recortes_dir.exists():
                return None

            pat_sel = _re.compile(rf"^LAJ_{_re.escape(item_id)}_sel_\d+\.dxf$", _re.I)
            pat_motor = _re.compile(rf"^LAJ_{_re.escape(item_id)}_motor_\d+\.dxf$", _re.I)
            sel_candidates: list[Path] = []
            motor_candidates: list[Path] = []
            def _suffix_rank(path: Path) -> tuple[int, float]:
                m = _re.search(r"_(?:motor|sel)_(\d+)$", path.stem, _re.I)
                num = int(m.group(1)) if m else 0
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    mtime = 0.0
                return (num, mtime)
            for dxf in recortes_dir.rglob("*.dxf"):
                name = dxf.name
                if pat_sel.match(name):
                    sel_candidates.append(dxf)
                elif pat_motor.match(name):
                    motor_candidates.append(dxf)
            dxf_path = (
                max(sel_candidates, key=_suffix_rank) if sel_candidates else
                max(motor_candidates, key=_suffix_rank) if motor_candidates else
                None
            )
            if not dxf_path:
                return None

            scripts_dir = str(SCRIPTS_DIR)
            if scripts_dir not in _sys.path:
                _sys.path.insert(0, scripts_dir)
            from motor_reverso_laj import extrair_ficha_laje

            ficha = extrair_ficha_laje(str(dxf_path), item_id, self._current_obra)
            coords = ficha.get("coordenadas") or []
            if len(coords) < 3:
                return None

            xs = [float(c[0]) for c in coords]
            ys = [float(c[1]) for c in coords]
            raw_x0, raw_y0 = min(xs), min(ys)
            pose = ficha.get("_stog_pose") or {}
            off_x = float(pose.get("x", 0.0)) if pose and abs(raw_x0) <= 0.5 else 0.0
            off_y = float(pose.get("y", 0.0)) if pose and abs(raw_y0) <= 0.5 else 0.0
            abs_xs = [x + off_x for x in xs]
            abs_ys = [y + off_y for y in ys]
            return (min(abs_xs) - pad, min(abs_ys) - pad,
                    max(abs_xs) + pad, max(abs_ys) + pad)
        except Exception:
            return None

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

        n1_bbox = self._get_n1_bbox_for(item_id, classe)
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

    _NIVEL_IDX = {'N1': 0, 'N2': 1, 'N3': 2, 'N4': 3, 'N5': 4}

    def set_pipeline_step(self, nivel: str, step_idx: int, status: str, msg: str = ''):
        """Atualiza um step do pipeline visual de uma coluna específica."""
        idx = self._NIVEL_IDX.get(nivel, -1)
        if 0 <= idx < len(self._columns):
            self._columns[idx].pipeline.set_step(step_idx, status, msg)

    def reset_all_pipelines(self):
        """Reseta todos os steps de todos os níveis para 'pending'."""
        for col in self._columns:
            col.pipeline.reset()
        # Restaura N4 para single-viewer caso esteja em modo PIL 3-panel
        self._columns[3].restore_single_view()

    # ── Fichas ──────────────────────────────────────────────────────

    def _ficha_n1(self, vn: str) -> list:
        """Ficha N1 para LV (Vigas Laterais) — dados Fase-3 estrutural."""
        return self._ficha_n1_for('LV', vn)

    def _ficha_n1_for(self, classe: str, item_id: str) -> list:
        """Ficha N1 class-aware — lê Fase-3 / Fase-4 para qualquer classe.
        Retorna lista de tuplas (label, value) com marcadores:
          ('==', 'TÍTULO')  → seção
          ('---', '')       → separador
          ('⚠ aviso', msg) → warning
        """
        import re as _re, json as _json

        def _fmt(v, default="—"):
            if v is None: return default
            if isinstance(v, float) and v == int(v): return str(int(v))
            return str(v) if str(v).strip() else default

        def _pct(v): return f"{v*100:.1f}%" if v else "—"
        def _bool(v): return "Sim" if v else "Não"
        def _linhas(lst):
            if not isinstance(lst, list) or not lst: return "—"
            vals = [f"{l.get('value', l) if isinstance(l, dict) else l:.0f}" for l in lst[:4]]
            extra = f" +{len(lst)-4}" if len(lst) > 4 else ""
            return f"{len(lst)}× [{', '.join(vals)}{extra}] cm"
        def _anc(v):
            if isinstance(v, (list, tuple)) and len(v) >= 2:
                return f"({v[0]:.0f}, {v[1]:.0f})"
            return _fmt(v)

        # Normaliza chave: V301_A/V301_fundo → V301
        viga_key = _re.sub(r'[_.]([A-Da-d]|fundo)$', '', item_id, flags=_re.I)
        rows: list = []

        # ── Header: Nome / Item
        rows += [
            ("==", f"{classe}  ·  {item_id}"),
            ("Nº Item", _fmt(item_id)),
            ("Classe", classe),
        ]

        if classe == 'LV':
            vd  = self._vigas_fase3.get(viga_key) or self._vigas_fase3.get(item_id, {})
            fr  = self._fichas_rev.get(viga_key) or self._fichas_rev.get(item_id, {})
            _anc_raw = self._ancoras.get(viga_key) or self._ancoras.get(item_id)
            # ancoras_vigas.json: valores podem ser dict {'A':..,'B':..} ou list [x,y]
            if isinstance(_anc_raw, dict):
                anc_a, anc_b = _anc_raw.get("A"), _anc_raw.get("B")
            elif isinstance(_anc_raw, (list, tuple)) and len(_anc_raw) >= 2:
                anc_a, anc_b = _anc_raw[0], _anc_raw[1]
            else:
                anc_a, anc_b = None, None
            if not isinstance(vd, dict): vd = {}
            if not isinstance(fr, dict): fr = {}
            rows += [
                ("==", "CONFIGURAÇÃO DA VIGA"),
                ("b estrutural (cm)", _fmt(vd.get("b"))),
                ("h estrutural (cm)", _fmt(vd.get("h"))),
                ("Comprimento bruto (cm)", _fmt(vd.get("comprimento_original"))),
                ("Comprimento (cm)", _fmt(vd.get("comprimento"))),
                ("Status comprimento", _fmt(vd.get("comprimento_enrich_status"))),
                ("Faces", ", ".join(vd.get("sides", [])) or "—"),
                ("has_lv", _bool(fr.get("has_lv"))),
                ("has_fv", _bool(fr.get("has_fv"))),
                ("==", "DADOS GERAIS - VIGA LATERAL"),
                ("Altura estrutural (cm)", _fmt(fr.get("altura_cm"))),
                ("Pavimentos", ", ".join(fr.get("pavimentos", [])) if isinstance(fr.get("pavimentos"), list) else "—"),
                ("Âncora A", _anc(anc_a)),
                ("Âncora B", _anc(anc_b)),
                ("Confidence", _pct(vd.get("confidence"))),
                ("Source", _fmt(vd.get("source"))),
            ]

        elif classe == 'PL':
            pd_ = self._pilares_fase3.get(item_id, {})
            pa  = self._pilares_assembly.get(item_id, {})
            pos = self._est_labels.get(item_id)
            rows += [
                ("==", "DIMENSIONAMENTO"),
                ("b (cm)", _fmt(pd_.get("b"))),
                ("h (cm)", _fmt(pd_.get("h"))),
                ("Altura (cm)", _fmt(pd_.get("altura"))),
                ("Nível saída", _fmt(pd_.get("nivel_saida"))),
                ("Nível chegada", _fmt(pd_.get("nivel_chegada"))),
                ("==", "DADOS GERAIS - PILAR"),
                ("grade_1", _fmt(pa.get("grade_1"))),
                ("grade_2", _fmt(pa.get("grade_2"))),
                ("distancia_1", _fmt(pa.get("distancia_1"))),
                ("Pos. estrutural (x,y)", f"({pos[0]:.0f}, {pos[1]:.0f})" if pos else "—"),
                ("Confidence", _pct(pd_.get("confidence"))),
                ("Source", _fmt(pd_.get("source"))),
            ]

        elif classe == 'FV':
            fv = self._vigas_fundo_fase3.get(viga_key) or self._vigas_fundo_fase3.get(item_id, {})
            fv_db = self._get_n1_fv_data_from_db(viga_key) or {}
            if fv_db:
                segs = fv_db.get("segmentos_fundo", []) or []
                comp = fv_db.get("comprimento_fundo") or fv_db.get("comprimento_total_fundo")
                rows += [
                    ("==", "N1 STRUCTURAL ANALYZER - FUNDO"),
                    ("Qtd. segmentos", _fmt(fv_db.get("panels_n1") or len(segs))),
                    ("Comprimento total (cm)", _fmt(comp)),
                    ("Dimensao texto", _fmt(fv_db.get("dim_text"))),
                    ("Largura/h extraida (cm)", _fmt(fv_db.get("h_n1"))),
                ]
                for seg in segs[:6]:
                    if not isinstance(seg, dict):
                        continue
                    ficha = seg.get("ficha") if isinstance(seg.get("ficha"), dict) else {}
                    rows.append((
                        f"Seg {seg.get('seg_index', '?')}",
                        f"comp={_fmt(ficha.get('comprimento_total_fundo') or seg.get('length'))} "
                        f"larg={_fmt(ficha.get('largura_total_fundo') or seg.get('dim_width'))} "
                        f"dim={_fmt(seg.get('dim_text'))}"
                    ))
            rows += [
                ("==", "CONFIGURAÇÃO DO FUNDO DE VIGA"),
                ("b (cm)", _fmt(fv.get("b"))),
                ("h (cm)", _fmt(fv.get("h"))),
                ("Comprimento (cm)", _fmt(fv.get("comprimento"))),
                ("==", "DADOS GERAIS"),
                ("Confidence", _pct(fv.get("confidence"))),
                ("Source", _fmt(fv.get("source"))),
            ]

        elif classe == 'LJ':
            self._refresh_lj_n1_from_latest_sa()
            lj = self._lajes_fase3.get(item_id, {})
            pont = self._lajes_pontaletes.get(item_id, {})
            # Fallback Fase-4: schema Fase-3 diferente (comprimento_cm ≠ comprimento)
            if self._current_obra and 'comprimento' not in lj:
                _f4p = (DADOS_OBRAS_ROOT / self._current_obra
                        / "Fase-4_Sincronizacao" / "JSON_Lajes" / f"{item_id}.json")
                if _f4p.exists():
                    try:
                        lj = _json.loads(_f4p.read_text(encoding='utf-8'))
                        if isinstance(lj.get('pontaletes'), dict):
                            pont = lj['pontaletes']
                    except Exception:
                        lj = {}
            # Formatar área
            area = lj.get("area_cm2")
            area_str = f"{area:.0f} cm²  ({area/10000:.2f} m²)" if area else "—"
            # Formatar modo
            modo = lj.get("modo_selecionado")
            modo_str = {0: "Normal (0)", 1: "Espelho (1)"}.get(modo, _fmt(modo))
            fields = lj.get("fields") if isinstance(lj.get("fields"), dict) else {}
            links = lj.get("links") if isinstance(lj.get("links"), dict) else {}
            val_fields = lj.get("validated_fields") or []
            val_links = lj.get("validated_link_classes") or {}

            def _count_slot(field_id: str, slot_id: str | None = None) -> int:
                data = links.get(field_id, {})
                if not isinstance(data, dict):
                    return 0
                if slot_id:
                    return len(data.get(slot_id) or [])
                return sum(len(v or []) for v in data.values() if isinstance(v, list))

            def _brief(v):
                if isinstance(v, list):
                    return f"[{len(v)} itens]"
                if isinstance(v, dict):
                    return f"{{{len(v)} chaves}}"
                return _fmt(v)

            coords = lj.get("coordenadas") or lj.get("points") or []
            bbox = self._points_bbox(coords, pad=0.0)
            bbox_str = (
                f"({bbox[0]:.1f}, {bbox[1]:.1f}) → ({bbox[2]:.1f}, {bbox[3]:.1f})"
                if bbox else "—"
            )
            rows += [
                ("==", "CÁLCULO / MÉTRICAS DA LAJE"),
                ("Área Total (calculada)", area_str),
                ("Modo de Cálculo", modo_str),
                ("Lin. Verticais de Pont.", _linhas(lj.get("linhas_verticais"))),
                ("Lin. Horizontais de Pont.", _linhas(lj.get("linhas_horizontais"))),
                ("Uniões nos Bordos", _bool(lj.get("unioes_nos_bordes"))),
                ("Observações / Notas", _fmt(lj.get("observacoes")) or "—"),
                ("==", "DADOS GERAIS - LAJE"),
                ("Nome", _fmt(lj.get("nome") or item_id)),
                ("Comprimento C (cm)", _fmt(lj.get("comprimento"))),
                ("Largura L (cm)", _fmt(lj.get("largura"))),
                ("Dimensão C×L [laje_dim]", _fmt(fields.get("laje_dim") or lj.get("laje_dim"))),
                ("Visão de Corte", f"{_count_slot('laje_visao_corte')} vínculo(s)"),
                ("Níveis / Vizinhas", f"{_count_slot('laje_vizinhas_niveis')} vínculo(s)"),
                ("Pilares de Apoio", f"{_count_slot('laje_pilares_apoio')} vínculo(s)"),
                ("Nível / Pavimento", _fmt(fields.get("laje_nivel") or lj.get("laje_nivel"))),
                ("Segmentos da Área", f"{_count_slot('laje_outline_segs', 'contour')} contorno(s)"),
                ("Acréscimos de Borda", f"{_count_slot('laje_outline_segs', 'acrescimo_borda')} extensão(ões)"),
                ("Ilhas / Obstáculos", f"{_count_slot('laje_islands')} vínculo(s)"),
                ("Pontos geometria", len(coords) if isinstance(coords, list) else 0),
                ("BBox geometria", bbox_str),
                ("Pontaletes total", _fmt(pont.get("total")) if isinstance(pont, dict) else "—"),
                ("==", "VALIDAÇÃO SA"),
                ("Campos validados", ", ".join(val_fields) if val_fields else "—"),
                ("Vínculos validados", _brief(val_links)),
            ]
            if fields:
                rows.append(("==", "CAMPOS SA - TODOS"))
                for k in sorted(fields):
                    if k in {"laje_dim", "laje_nivel"}:
                        continue
                    rows.append((k, _brief(fields.get(k))))
            extra_keys = [
                "id_item", "name", "type", "area", "area_cm2", "modo_selecionado",
                "laje_linhas_v_count", "laje_linhas_h_count", "unioes_nos_bordes",
                "observacoes", "pont_total", "pont_meio", "pont_linhas", "pont_colunas",
                "pont_tipo", "pont_altura_pav", "pont_comp_cm", "pont_larg_cm",
            ]
            rows.append(("==", "CHAVES SA DIRETAS"))
            for k in extra_keys:
                if k in lj:
                    rows.append((k, _brief(lj.get(k))))

        # Checar se todos valores são "—" (ficha vazia)
        data_rows = [v for (k, v) in rows if k not in ("==", "---", "Classe") and k not in (f"{classe}  ·  {item_id}", "Nº Item")]
        if all(v == "—" for v in data_rows):
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
            import re as _re2
            base_item_id = _re2.sub(r'_(Para|Passa)$', '', item_id)  # strip sufixo virtual
            # LV usa fichas_lv_v2 (estrutura especializada)
            entries = [f for f in self._fichas_lv_v2 if f.get('viga') == base_item_id]
            if not entries:
                # Fallback para JSON individual em Fase-4
                return self._ficha_fase4_json('LV', base_item_id, fase4 / "JSON_Vigas_Laterais")
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
            rows = self._ficha_n1_for('FV', item_id)
            rows += [("---", ""), ("==", "N3 ROBO FUNDO / FASE 4")]
            rows += self._ficha_fase4_json('FV', f"{item_id}_fundo", fase4 / "JSON_Vigas_Fundo")
            return rows

        elif classe == 'LJ':
            rows = [
                ("==", "N1 STRUCTURAL ANALYZER"),
                *self._ficha_n1_for("LJ", item_id),
                ("==", "FICHA N3 / ROBO LAJE"),
            ]
            rows.extend(self._ficha_fase4_json('LJ', item_id, fase4 / "JSON_Lajes"))
            return rows

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
        self.nav_sidebar.gerar_n5_requested.connect(self._on_gerar_n5)
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
        # Quando scan do DXF conclui → filtrar lista LJ pelos labels do DXF ativo
        self.tri_level.scan_done.connect(self.nav_sidebar.set_lj_filter)
        # Disparar carga inicial após construção (500ms delay para event loop estabilizar)
        QTimer.singleShot(500, self._on_obra_pav_changed)

        def _hdr_btn(text, accent, checkable=False):
            b = QPushButton(text)
            b.setFixedHeight(18)
            b.setCheckable(checkable)
            b.setStyleSheet(
                f"QPushButton {{ background: rgba(0,0,0,0.3); color: {accent}; border-radius: 3px; "
                f"padding: 1px 8px; font-size: 10px; font-weight: bold; border: 1px solid {accent}55; }}"
                f"QPushButton:hover {{ background: {accent}33; color: #fff; }}"
                f"QPushButton:checked {{ background: {accent}; color: #000; }}"
            )
            return b

        # N3 header: Comparar com N1 | Abrir DXF
        _btn_cmp_n1 = _hdr_btn("Comparar com N1", "#cf8a4a", checkable=True)
        _btn_cmp_n1.clicked.connect(self._on_comparar_n1_toggled)
        self._btn_comparar_n1 = _btn_cmp_n1
        self.tri_level._columns[2]._badge_row.addWidget(_btn_cmp_n1)
        _btn_cmp_n4_on_n3 = _hdr_btn("Comparar com N4", "#cf8a4a", checkable=True)
        _btn_cmp_n4_on_n3.clicked.connect(self._on_comparar_n4_on_n3_toggled)
        self._btn_comparar_n4_on_n3 = _btn_cmp_n4_on_n3
        self.tri_level._columns[2]._badge_row.addWidget(_btn_cmp_n4_on_n3)
        _btn_open_n3 = _hdr_btn("Abrir DXF", "#cf8a4a")
        _btn_open_n3.clicked.connect(lambda: self._on_abrir_dxf(2))
        self.tri_level._columns[2]._badge_row.addWidget(_btn_open_n3)
        _btn_pdf_n3 = _hdr_btn("Criar Ficha PDF", "#cf8a4a")
        _btn_pdf_n3.clicked.connect(self._on_criar_ficha_pdf)
        self.tri_level._columns[2]._badge_row.addWidget(_btn_pdf_n3)
        _btn_cfg_n3 = _hdr_btn("Configuracao Visual", "#cf8a4a")
        _btn_cfg_n3.clicked.connect(lambda: self._on_configuracao_visual(2))
        self.tri_level._columns[2]._badge_row.addWidget(_btn_cfg_n3)

        # N4 header: Comparar com N2 | Abrir DXF
        _btn_cmp_n2 = _hdr_btn("Comparar com N2", "#a855f7", checkable=True)
        _btn_cmp_n2.clicked.connect(self._on_comparar_n2_toggled)
        self._btn_comparar_n2 = _btn_cmp_n2
        self.tri_level._columns[3]._badge_row.addWidget(_btn_cmp_n2)
        _btn_open_n4 = _hdr_btn("Abrir DXF", "#a855f7")
        _btn_open_n4.clicked.connect(lambda: self._on_abrir_dxf(3))
        self.tri_level._columns[3]._badge_row.addWidget(_btn_open_n4)
        _btn_cfg_n4 = _hdr_btn("Configuracao Visual", "#a855f7")
        _btn_cfg_n4.clicked.connect(lambda: self._on_configuracao_visual(3))
        self.tri_level._columns[3]._badge_row.addWidget(_btn_cfg_n4)

        # N5 header: Comparar Eng. Reversa Humana | Abrir DXF
        _btn_cmp_n5 = _hdr_btn("Comparar Eng. Rev. Humana", "#00bcd4", checkable=True)
        _btn_cmp_n5.clicked.connect(self._on_comparar_er_humana_toggled)
        self._btn_comparar_n5 = _btn_cmp_n5
        self.tri_level._columns[4]._badge_row.addWidget(_btn_cmp_n5)
        _btn_open_n5 = _hdr_btn("Abrir DXF", "#00bcd4")
        _btn_open_n5.clicked.connect(lambda: self._on_abrir_dxf(4))
        self.tri_level._columns[4]._badge_row.addWidget(_btn_open_n5)
        _btn_cfg_n5 = _hdr_btn("Configuracao Visual", "#00bcd4")
        _btn_cfg_n5.clicked.connect(lambda: self._on_configuracao_visual(4))
        self.tri_level._columns[4]._badge_row.addWidget(_btn_cfg_n5)

        # Troca de classe → N5 auto-gera | seleção de item → N3 ou N4 auto-exibe
        self.nav_sidebar.classe_changed.connect(self._on_classe_changed)

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

    def _on_comparar_n1_toggled(self, checked: bool):
        """Toggle: mostra/esconde DXF N1 (estrutural) acima do viewer N3."""
        col_n3 = self.tri_level._columns[2]
        if checked:
            btn_n4 = getattr(self, "_btn_comparar_n4_on_n3", None)
            if btn_n4 and btn_n4.isChecked():
                btn_n4.setChecked(False)
            if not self._refresh_n3_compare_if_active():
                self.nav_sidebar.set_status("N1 nÃ£o carregado", Colors.TEXT_DIM)
                self._btn_comparar_n1.setChecked(False)
            return
            n1_path = self.tri_level._columns[0]._last_loaded_dxf or ""
            if n1_path and Path(n1_path).exists():
                classe = getattr(self.nav_sidebar, "_selected_classe", "")
                item_id = getattr(self.nav_sidebar, "_selected_item", "")
                bbox = self.tri_level._get_n1_bbox_for(item_id, classe) if item_id else None
                points = self.tri_level._get_lj_n1_points(item_id) if classe == "LJ" and item_id else None
                col_n3.show_n2_above(
                    n1_path,
                    title=f"DXF N1 - {item_id}" if item_id else "DXF N1",
                    bbox=bbox,
                    highlight_points=points,
                )
                if hasattr(col_n3, "_n2_above_hdr"):
                    col_n3._n2_above_hdr.setText(f"DXF N1 - {item_id}" if item_id else "DXF N1")
            else:
                self.nav_sidebar.set_status("N1 não carregado", Colors.TEXT_DIM)
                self._btn_comparar_n1.setChecked(False)
        else:
            col_n3.hide_n2_above()

    def _on_comparar_n4_on_n3_toggled(self, checked: bool):
        """Toggle: mostra/esconde DXF N4 acima do viewer N3."""
        col_n3 = self.tri_level._columns[2]
        if checked:
            btn_n1 = getattr(self, "_btn_comparar_n1", None)
            if btn_n1 and btn_n1.isChecked():
                btn_n1.setChecked(False)
            if not self._refresh_n3_compare_n4_if_active():
                self.nav_sidebar.set_status("N4 nao encontrado para este item", Colors.TEXT_DIM)
                self._btn_comparar_n4_on_n3.setChecked(False)
            return
        else:
            col_n3.hide_n2_above()

    def _on_comparar_n2_toggled(self, checked: bool):
        """Toggle: mostra/esconde DXF N2 (recorte) acima do viewer N4."""
        col = self.tri_level._columns[3]
        if checked:
            recorte = getattr(self.nav_sidebar, '_selected_recorte_path', "") or ""
            if not recorte or not self._refresh_n4_compare_if_active(recorte, cull_to_bbox=False):
                self.nav_sidebar.set_status("Sem recorte N2 para este item", Colors.TEXT_DIM)
                self._btn_comparar_n2.setChecked(False)
            return
            recorte = getattr(self.nav_sidebar, '_selected_recorte_path', "") or ""
            if recorte and Path(recorte).exists():
                col.show_n2_above(recorte)
            else:
                self.nav_sidebar.set_status("Sem recorte N2 para este item", Colors.TEXT_DIM)
                self._btn_comparar_n2.setChecked(False)
        else:
            col.hide_n2_above()

    def _refresh_n3_compare_if_active(self, classe: str | None = None, item_id: str | None = None) -> bool:
        """Atualiza o viewer comparativo N1 aberto acima do N3 para o item atual."""
        btn = getattr(self, "_btn_comparar_n1", None)
        if not btn or not btn.isChecked():
            return True
        n1_path = self.tri_level._columns[0]._last_loaded_dxf or ""
        if not n1_path or not Path(n1_path).exists():
            return False
        classe = classe or getattr(self.nav_sidebar, "_selected_classe", "")
        item_id = item_id or getattr(self.nav_sidebar, "_selected_item", "")
        bbox = self.tri_level._get_n1_bbox_for(item_id, classe) if item_id else None
        points = self.tri_level._get_lj_n1_points(item_id) if classe == "LJ" and item_id else None
        self.tri_level._columns[2].show_n2_above(
            n1_path,
            title=f"DXF N1 - {item_id}" if item_id else "DXF N1",
            bbox=bbox,
            highlight_points=points,
        )
        return True

    def _refresh_n3_compare_n4_if_active(self, classe: str | None = None,
                                         item_id: str | None = None) -> bool:
        """Atualiza o viewer comparativo N4 aberto acima do N3 para o item atual."""
        btn = getattr(self, "_btn_comparar_n4_on_n3", None)
        if not btn or not btn.isChecked():
            return True
        classe = classe or getattr(self.nav_sidebar, "_selected_classe", "")
        item_id = item_id or getattr(self.nav_sidebar, "_selected_item", "")
        if not classe or not item_id:
            return False
        obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
        obra_dir = DADOS_OBRAS_ROOT / obra
        n4_path = self._find_n4_dxf_strict(obra_dir, classe, item_id)
        if not n4_path or not n4_path.exists():
            return False
        self.tri_level._columns[2].show_n2_above(
            n4_path,
            title=f"DXF N4 - {item_id}",
            bbox=None,
        )
        return True

    def _refresh_n4_compare_if_active(self, n2_path=None, classe: str | None = None,
                                      item_id: str | None = None, bbox=None,
                                      cull_to_bbox: bool = True) -> bool:
        """Atualiza o viewer comparativo N2 aberto acima do N4 para o item atual."""
        btn = getattr(self, "_btn_comparar_n2", None)
        if not btn or not btn.isChecked():
            return True
        path = n2_path or getattr(self.nav_sidebar, '_selected_recorte_path', "") or ""
        if not path:
            path = self.tri_level._columns[1]._last_loaded_dxf or ""
        if not path or not Path(str(path)).exists():
            return False
        classe = classe or getattr(self.nav_sidebar, "_selected_classe", "")
        item_id = item_id or getattr(self.nav_sidebar, "_selected_item", "")
        if bbox is None and item_id:
            bbox = self.tri_level._get_n2_bbox_for(item_id, classe)
        self.tri_level._columns[3].show_n2_above(
            path,
            title=f"DXF N2 - {item_id}" if item_id else "DXF N2",
            bbox=bbox,
            cull_to_bbox=cull_to_bbox,
        )
        return True

    def _load_recorte_full_with_optional_zoom(self, col, dxf_path, bbox=None):
        """Carrega recorte individual inteiro; bbox serve apenas para destacar/zoomar."""
        if bbox:
            def _after_ready():
                try:
                    col.img_widget.ready.disconnect(_after_ready)
                except (RuntimeError, TypeError):
                    pass
                try:
                    col.img_widget.set_highlight_bbox(bbox)
                    col.img_widget.zoom_to_bbox(bbox)
                except Exception:
                    pass
            try:
                col.img_widget.ready.connect(_after_ready)
            except (RuntimeError, TypeError):
                pass
        col.load_content(str(dxf_path), None)
        if bbox and hasattr(col.img_widget, "set_highlight_bbox"):
            col.img_widget.set_highlight_bbox(bbox)

    def _on_comparar_er_humana_toggled(self, checked: bool):
        """Toggle: mostra/esconde DXF Eng. Reversa Humana (obra_triagem) acima do viewer N5."""
        col_n5 = self.tri_level._columns[4]
        if not checked:
            col_n5.hide_n2_above()
            return
        try:
            import sqlite3 as _sql
            DB_PATH = Path("D:/Agente-cad-PYSIDE/project_data.vision")
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            cls  = self.nav_sidebar._current_classe  # "LV","FV","LJ","PL"
            _CLS_ACCEPT = {
                "LV": {"LV", "VIGAS_LATERAIS", "LATERAL"},
                "FV": {"FV", "VIGAS_FUNDO", "FUNDO"},
                "LJ": {"LJ", "LAJ", "LAJES"},
                "PL": {"PL", "PIL", "PILARES"},
            }
            accepted = _CLS_ACCEPT.get(cls, {cls})
            with _sql.connect(str(DB_PATH)) as con:
                rows = con.execute(
                    "SELECT file_name, file_path, notes FROM obra_triagem "
                    "WHERE obra_name=? AND status='approved' "
                    "AND (suggested_category LIKE '%Engenharia Reversa%' "
                    "     OR suggested_category LIKE '%Projetos Finalizados%') "
                    "ORDER BY suggested_order ASC, file_name ASC",
                    (obra,)
                ).fetchall()
            import json as _json
            match = None
            for fname, fpath, notes_text in rows:
                er_class = ""
                if notes_text:
                    try:
                        er_class = _json.loads(notes_text).get("er_class", "")
                    except Exception:
                        pass
                if not er_class:
                    # inferência por nome
                    fn_up = (fname or "").upper()
                    for tag in accepted:
                        if tag in fn_up:
                            er_class = cls
                            break
                if er_class.upper() in accepted or er_class == cls:
                    if fpath and Path(fpath).exists():
                        match = fpath
                        break
            if match:
                col_n5.show_n2_above(match)
            else:
                self.nav_sidebar.set_status(f"DXF Eng. Rev. Humana não encontrado para {cls}", Colors.TEXT_DIM)
                self._btn_comparar_n5.setChecked(False)
        except Exception as exc:
            self.nav_sidebar.set_status(f"Erro ER Humana: {exc}", Colors.ACCENT_DANGER)
            self._btn_comparar_n5.setChecked(False)

    def _on_abrir_dxf(self, col_index: int):
        """Abre o último DXF carregado na coluna col_index no aplicativo padrão do SO."""
        import os as _os
        path = self.tri_level._columns[col_index]._last_loaded_dxf or ""
        if path and Path(path).exists():
            try:
                _os.startfile(path)
            except Exception as exc:
                self.nav_sidebar.set_status(f"Erro ao abrir: {exc}", Colors.ACCENT_DANGER)
        else:
            self.nav_sidebar.set_status("Nenhum DXF carregado nesta aba", Colors.TEXT_DIM)

    def _on_criar_ficha_pdf(self):
        """Gera e abre a ficha PDF do item selecionado no CE (qualquer classe)."""
        from .ficha_pdf_generator import gerar_ficha_pdf, abrir_pdf
        from PySide6.QtWidgets import QMessageBox

        obra_dir = self._current_obra_dir
        classe   = (self._selected_classe or "").upper()
        item_id  = self._selected_item or ""

        if not obra_dir or not classe or not item_id:
            self.nav_sidebar.set_status(
                "Selecione um item antes de gerar a ficha PDF", Colors.TEXT_DIM)
            return

        obra = obra_dir.name if obra_dir else ""
        pav  = getattr(self, "_current_pav", "") or ""

        self.nav_sidebar.set_status("Gerando ficha PDF…", Colors.TEXT_DIM)

        try:
            ficha   = self._get_er_ficha_dict(obra, classe, item_id)
            dxf_p   = self._find_n3_dxf(obra_dir, classe, item_id)
            out_dir = obra_dir / "Fase-6_Execucao_CAD" / "fichas_pdf"

            pdf_path = gerar_ficha_pdf(
                ficha=ficha,
                classe=classe,
                item_id=item_id,
                obra=obra,
                pav=pav,
                out_dir=out_dir,
                dxf_path=dxf_p,
            )
            self.nav_sidebar.set_status(
                f"Ficha PDF gerada: {pdf_path.name}", Colors.ACCENT_SUCCESS)
            abrir_pdf(pdf_path)
        except Exception as exc:
            self.nav_sidebar.set_status(
                f"Erro ao gerar PDF: {str(exc)[:80]}", Colors.ACCENT_DANGER)
            QMessageBox.critical(self, "Erro — Ficha PDF",
                                 f"Não foi possível gerar a ficha PDF:\n\n{exc}")

    def _robot_widget_for_classe(self, classe: str):
        main = self.window()
        attr = {
            "PL": "robo_pilares",
            "LV": "robo_viga",
            "FV": "robo_fundo",
            "LJ": "robo_laje",
        }.get(str(classe or "").upper())
        return getattr(main, attr, None) if attr else None

    def _script_for_visual_config(self, classe: str, col_index: int) -> Path:
        classe = str(classe or "").upper()
        if col_index == 4:
            return Path(__file__).parent.parent.parent / "core" / "n5_assembler.py"
        return SCRIPTS_DIR / _N3_SCRIPTS.get(classe, "")

    def _on_configuracao_visual(self, col_index: int):
        """Abre painel de configuracao visual do DXF para N3/N4/N5."""
        try:
            classe = getattr(self.nav_sidebar, "_current_classe", "") or "FV"
            script = self._script_for_visual_config(classe, col_index)
            robot = self._robot_widget_for_classe(classe)
            if not script.exists():
                self.nav_sidebar.set_status(f"Script DXF nao encontrado: {script.name}", Colors.ACCENT_DANGER)
                return
            dlg = DxfVisualConfigDialog(classe, script, robot_widget=robot, parent=self)
            dlg.exec()
        except Exception as exc:
            self.nav_sidebar.set_status(f"Erro Config Visual: {str(exc)[:80]}", Colors.ACCENT_DANGER)
            print(f"[CE] _on_configuracao_visual error: {exc}")

    def _on_classe_changed(self, cls: str):
        """Ao trocar aba de classe, gera/exibe dinamicamente o N5 da classe."""
        try:
            self.tri_level._nivel_tabs.setCurrentIndex(4)
            if cls not in ("LJ", "FV"):
                col = self.tri_level._columns[4]
                col.img_widget.cancel_load(f"N5 nao disponivel para {cls}")
                return
            ids = self.nav_sidebar.current_item_ids()
            if ids:
                self._on_gerar_n5(cls, ids)
        except Exception:
            pass

    def eventFilter(self, obj, event) -> bool:
        """Intercepta ↑/↓ globalmente para navegar na lista de itens do NavSidebar."""
        if event.type() == QEvent.MouseButtonPress and self.isVisible():
            QTimer.singleShot(0, lambda: self.nav_sidebar._restore_table_selection(emit=False))
        if (
            event.type() == QEvent.KeyPress
            and self.isVisible()
            and event.key() in (Qt.Key_Return, Qt.Key_Enter)
        ):
            focused = QApplication.focusWidget()
            if not isinstance(focused, (QLineEdit, QComboBox)):
                return self._validate_current_tab_human()
        if (
            event.type() == QEvent.KeyPress
            and self.isVisible()
            and event.key() in (Qt.Key_Up, Qt.Key_Down)
        ):
            focused = QApplication.focusWidget()
            if not isinstance(focused, (QLineEdit, QComboBox)):
                delta = -1 if event.key() == Qt.Key_Up else 1
                self.nav_sidebar.navigate(delta)
                return True
        return super().eventFilter(obj, event)

    def _validate_current_tab_human(self) -> bool:
        try:
            tab_idx = self.tri_level._nivel_tabs.currentIndex()
            scope = "N3" if tab_idx == 2 else "N4" if tab_idx == 3 else ""
            if not scope:
                return False
            classe = getattr(self.nav_sidebar, "_selected_classe", "") or getattr(self.nav_sidebar, "_current_classe", "")
            item_id = getattr(self.nav_sidebar, "_selected_item", "")
            if not classe or not item_id:
                return False
            self.nav_sidebar._restore_table_selection(emit=False)
            self._save_level_human_validation(scope, classe, item_id, True)
            col = self.tri_level._columns[tab_idx]
            check = getattr(col, "_human_validation_check", None)
            if check is not None and not check.isChecked():
                old = getattr(col, "_attention_loading", False)
                col._attention_loading = True
                check.setChecked(True)
                col._attention_loading = old
            return True
        except Exception as exc:
            print(f"[CE] _validate_current_tab_human error: {exc}")
            return False

    def _on_obra_pav_changed(self, _text: str = ""):
        """Propaga mudança de obra/pav do Fase8Panel para o TriLevelArea e main.py.
        Carrega DXF limpo no N1 uma vez ao mudar pavimento (item click = só zoom).
        Também auto-dispara Análise Geral em background se não estiver em cache.
        Guard: ignora chamadas com pav vazio (durante populate do combo)."""
        try:
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            pav  = self.fase8_panel.current_pav_key
            _ce_log(f"[CE] _on_obra_pav_changed obra={obra!r} pav={pav!r}")
            # Guard: não processar enquanto combo está sendo populado (pav vazio = populate em andamento)
            if not obra or not pav:
                return
            # FIX: Cancela workers N2/N3/N4/N5 em andamento antes de mudar pav.
            # Sem isso, um DXF pesado (ex: LV STOG 6.9MB) completando após mudança de pav
            # dispara _on_loaded_file com dado stale, causando STATUS_STACK_BUFFER_OVERRUN
            # no Python 3.14 / Windows quando o resultado chega no meio da transição de estado.
            for _ci in (1, 2, 3, 4):
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
        """Carrega DXF do pavimento no N1 viewer — usa projects.dxf_path (mesmo que SA)."""
        # Prioridade: recorte gravado pelo SA em projects.dxf_path
        n1_dxf = self.tri_level._find_n1_project_dxf(obra, pav)
        if not n1_dxf:
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
                    if isinstance(lst, list):
                        lst.remove(w)
                except (ValueError, AttributeError):
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
                    self.nav_sidebar.refresh_tree()
            else:
                self.nav_sidebar.set_status(f"❌ Análise: {msg[:40]}", Colors.ACCENT_DANGER)
                self.tri_level.set_pipeline_step('N1', 0, 'error', msg[:30])
        except RuntimeError:
            pass  # Widget deletado — ignorar

    def _on_iniciar_analise(self):
        """CE-002: Botão Análise Geral manual — força re-processamento mesmo com cache."""
        obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
        pav  = self.fase8_panel.current_pav_key
        self.analise_geral_requested.emit(obra, pav)
        # Limpa cache e re-dispara
        self._analise_cache.clear()
        self._auto_analise_geral(obra, pav)

    # ── Handlers Gerar N1 / N2 / N3 ────────────────────────────────

    def _find_n2_recorte_for_item(self, obra: str, classe: str, item_id: str) -> Path | None:
        try:
            import sqlite3
            db_cls = {"PL": "PIL", "LJ": "LAJ"}.get(classe, classe)
            conn = sqlite3.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT recorte_path FROM reverse_eng_fichas "
                    "WHERE obra_name=? AND classe=? AND elemento_id=? "
                    "ORDER BY updated_at DESC, ROWID DESC LIMIT 1",
                    (obra, db_cls, item_id),
                )
            except Exception:
                cur.execute(
                    "SELECT recorte_path FROM reverse_eng_fichas "
                    "WHERE obra_name=? AND classe=? AND elemento_id=? "
                    "ORDER BY ROWID DESC LIMIT 1",
                    (obra, db_cls, item_id),
                )
            row = cur.fetchone()
            conn.close()
            if row and row[0] and Path(row[0]).exists():
                return Path(row[0])
        except Exception:
            pass
        try:
            return self.tri_level._find_disk_dxf_for_er(
                obra, {"PL": "PIL", "LJ": "LAJ"}.get(classe, classe), item_id
            )
        except Exception:
            return None

    def _visual_score_for_level(self, scope: str, classe: str, item_id: str) -> str:
        obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
        if not obra:
            return "Score visual pendente: obra nao selecionada."
        obra_dir = DADOS_OBRAS_ROOT / obra
        label = "Score visual N3 x N4" if scope == "N3" else "Score visual N4 x recorte N2"
        detail = "comparacao com N4" if scope == "N3" else "sobre o recorte N2"
        try:
            import sys as _sys
            scripts_dir = str(SCRIPTS_DIR)
            arete_dir = str(SCRIPTS_DIR / "arete")
            if scripts_dir not in _sys.path:
                _sys.path.insert(0, scripts_dir)
            if arete_dir not in _sys.path:
                _sys.path.insert(0, arete_dir)

            if scope == "N3":
                left = self.tri_level._find_n3_dxf(obra_dir, classe, item_id)
                right = self._find_n4_dxf_strict(obra_dir, classe, item_id)
            else:
                left = self._find_n2_recorte_for_item(obra, classe, item_id)
                right = self._find_n4_dxf_strict(obra_dir, classe, item_id)

            if not left or not right or not Path(left).exists() or not Path(right).exists():
                return f"{label}: pendente ({detail}; DXF ausente)."

            if classe == "LJ":
                from scripts.arete_lj_canonico import canonical, diff
                diffs = diff(canonical(Path(left)), canonical(Path(right))).get("diffs", {})
                weights = {
                    "outline": 50,
                    "linhas_verticais": 20,
                    "linhas_horizontais": 20,
                    "hlaz": 5,
                    "obstaculos": 5,
                }
                lost = sum(weight for field, weight in weights.items() if field in diffs)
                pct = max(0, 100 - lost)
                fails = [field for field in weights if field in diffs]
                suffix = "OK" if not fails else "diverge: " + ", ".join(fails)
                return f"{label}: {pct:.0f}% ({detail}; marco/linhas LAJ; {suffix})."

            from paridade_visual import paridade_item
            score_cls = "PIL" if classe == "PL" else classe
            r = paridade_item(str(left), str(right), verbose=False, classe=score_cls)
            sc = r.get("scores", {})
            cats = {
                "entidades": sc.get("entidades_ok"),
                "geometria": sc.get("geometria_ok"),
                "textos": sc.get("textos_ok"),
                "hatches": sc.get("hatches_ok"),
            }
            n_ok = sum(1 for v in cats.values() if v is True)
            fails = [k for k, v in cats.items() if v is False]
            pct = 100 * n_ok / max(len(cats), 1)
            status = "OK" if r.get("resultado") == "PASS" else f"falhou: {', '.join(fails) if fails else 'ver diffs'}"
            return f"{label}: {pct:.0f}% ({detail}; {classe}; {status})."

            if classe == "PIL":
                from partes_pil import comparar_pil_canonico
                resultados = comparar_pil_canonico(str(recorte), str(n4), verbose=False)
                partes_pass = [p for p, r in resultados.items() if r.get("resultado") == "PASS"]
                partes_fail = [p for p, r in resultados.items() if r.get("resultado") == "FAIL"]
                n_diffs = sum(len(r.get("diffs", [])) for r in resultados.values())
                if not partes_fail:
                    return f"Score G2 PIL: PASS — {len(partes_pass)} partes OK, 0 diffs."
                return (f"Score G2 PIL: FAIL — {len(partes_fail)} parte(s) FAIL "
                        f"({', '.join(partes_fail)}); {n_diffs} diffs.")
            else:
                from paridade_visual import paridade_item
                r = paridade_item(str(recorte), str(n4), verbose=False, classe=classe)
                sc = r.get("scores", {})
                cats = {"ent": sc.get("entidades_ok"), "geom": sc.get("geometria_ok"),
                        "txt": sc.get("textos_ok"), "hatch": sc.get("hatches_ok")}
                n_ok = sum(1 for v in cats.values() if v)
                fails = [k for k, v in cats.items() if v is False]
                pct = 100 * n_ok // max(len(cats), 1)
                if r.get("resultado") == "PASS":
                    return f"Score G2 {classe}: PASS — {pct}% ({n_ok}/4 cats OK)."
                return (f"Score G2 {classe}: FAIL — {pct}% "
                        f"(falhou: {', '.join(fails) if fails else 'ver diffs'}).")
        except Exception as exc:
            return f"{label}: erro ({exc})."

    def _configure_level_attention(self, scope: str, classe: str, item_id: str):
        try:
            idx = 2 if scope == "N3" else 3 if scope == "N4" else None
            if idx is None:
                return
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            pav = self.fase8_panel.current_pav_key
            meta = load_attention(obra, pav, classe, item_id, scope)
            score_text = self._visual_score_for_level(scope, classe, item_id)
            col = self.tri_level._columns[idx]
            col.set_attention_context(
                score_text,
                meta.get("attention", False),
                meta.get("note", ""),
                lambda att, note, s=scope, c=classe, iid=item_id: self._save_level_attention(s, c, iid, att, note),
                meta.get("human_validated", False),
                lambda ok, s=scope, c=classe, iid=item_id: self._save_level_human_validation(s, c, iid, ok),
            )
            # Para LV: exibe Para/Passa em N3 e N4 sincronizado com N2
            if classe == "LV":
                tipo = _lv_pp_from_id(item_id) or load_para_passa(
                    obra, pav, "LV", _lv_elem_id(item_id))
                viga_base = _lv_elem_id(item_id)
                col.set_para_passa(
                    tipo,
                    lambda t, b=viga_base: self._save_lv_para_passa_and_sync(b, t),
                )
            elif col._para_passa_row.isVisible():
                # limpa apenas se estava visível (evita ocultar attention_inline por engano)
                col.clear_para_passa()
        except Exception as exc:
            print(f"[CE] _configure_level_attention error: {exc}")

    def _save_level_attention(self, scope: str, classe: str, item_id: str, attention: bool, note: str):
        try:
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            pav = self.fase8_panel.current_pav_key
            save_attention(obra, pav, classe, item_id, scope, attention, note)
            self.nav_sidebar.refresh_tree()
        except Exception as exc:
            print(f"[CE] _save_level_attention error: {exc}")

    def _save_level_human_validation(self, scope: str, classe: str, item_id: str, human_validated: bool):
        try:
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            pav = self.fase8_panel.current_pav_key
            save_human_validation(obra, pav, classe, item_id, scope, human_validated)
            self.nav_sidebar.set_status(
                f"{scope} {'validado humano' if human_validated else 'validacao humana removida'} - {item_id}",
                Colors.ACCENT_SUCCESS if human_validated else Colors.TEXT_DIM,
            )
            self.nav_sidebar.refresh_tree()
        except Exception as exc:
            print(f"[CE] _save_level_human_validation error: {exc}")

    def _configure_para_passa_n2(self, classe: str, item_id: str):
        """Configura widget Para/Passa na coluna N2 para PIL, LAJ e LV."""
        try:
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            pav = self.fase8_panel.current_pav_key
            col = self.tri_level._columns[1]
            if classe in ("PL", "LJ"):
                db_cls = "PIL" if classe == "PL" else "LAJ"
                tipo = load_para_passa(obra, pav, db_cls, item_id)
                col.set_para_passa(
                    tipo,
                    lambda t, s=db_cls, iid=item_id: self._save_para_passa_n2(s, iid, t),
                )
            elif classe == "LV":
                # Para IDs virtuais "V301_A_Para", extrai pp do ID e viga_base sem face/pp
                tipo = _lv_pp_from_id(item_id) or load_para_passa(
                    obra, pav, "LV", _lv_elem_id(item_id))
                viga_base = _lv_elem_id(item_id)
                col.set_para_passa(
                    tipo,
                    lambda t, b=viga_base: self._save_lv_para_passa_and_sync(b, t),
                )
            else:
                col.clear_para_passa()
        except Exception as exc:
            print(f"[CE] _configure_para_passa_n2 error: {exc}")

    def _save_para_passa_n2(self, db_cls: str, item_id: str, tipo: str):
        try:
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            pav = self.fase8_panel.current_pav_key
            save_para_passa(obra, pav, db_cls, item_id, tipo)
            suffix = f"-{tipo.capitalize()}" if tipo else ""
            self.nav_sidebar.set_status(
                f"{db_cls} {item_id}{suffix} classificado", Colors.ACCENT_SUCCESS
            )
            self.nav_sidebar.refresh_tree()
        except Exception as exc:
            print(f"[CE] _save_para_passa_n2 error: {exc}")

    def _save_lv_para_passa_and_sync(self, viga_base: str, tipo: str):
        """Salva Para/Passa para LV e sincroniza todos os headers simultaneamente."""
        try:
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            pav = self.fase8_panel.current_pav_key
            save_para_passa(obra, pav, "LV", viga_base, tipo)
            # sincroniza botões em todos os headers que mostram Para/Passa
            for col in self.tri_level._columns:
                if col._para_passa_row.isVisible():
                    col._attention_loading = True
                    try:
                        col._para_btn.setChecked(tipo == "para")
                        col._passa_btn.setChecked(tipo == "passa")
                    finally:
                        col._attention_loading = False
            suffix = f"-{tipo.capitalize()}" if tipo else ""
            self.nav_sidebar.set_status(
                f"LV-{viga_base}{suffix} classificado", Colors.ACCENT_SUCCESS
            )
            # atualiza display da lista (sufixos Para/Passa nos nomes)
            self._populate_list(self._current_classe)
            self.nav_sidebar.refresh_tree()
        except Exception as exc:
            print(f"[CE] _save_lv_para_passa_and_sync error: {exc}")

    def _on_item_selected(self, classe: str, item_id: str):
        """Auto-dispara N1 → N2 → N3 em sequência ao selecionar item.
        Troca de aba automaticamente: lista esquerda → N3 | lista direita → N4.
        Incrementa _seq_id para cancelar sequências anteriores pendentes nos timers.
        """
        try:
            flow = getattr(self.nav_sidebar, '_current_flow', 'estrutural')
            _ce_log(f"ITEM_SELECTED classe={classe} id={item_id} flow={flow}")
            if classe == "LJ":
                self.tri_level._refresh_lj_n1_from_latest_sa()
            self._seq_id += 1
            seq = self._seq_id
            for _ci in (1, 2, 3):
                try:
                    self.tri_level._columns[_ci].img_widget.cancel_load("— aguardando seleção —")
                except Exception:
                    pass
            self.tri_level._lbl_item.setText(f"{classe} / {item_id}")
            self.tri_level.reset_all_pipelines()
            # Auto-switch: esquerda (estrutural) → N3 | direita (reverso) → N4
            if flow == "reverso":
                self.tri_level._nivel_tabs.setCurrentIndex(3)
            else:
                self.tri_level._nivel_tabs.setCurrentIndex(2)
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

            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            pav  = self.fase8_panel.current_pav_key
            if not obra or not item_id:
                self.nav_sidebar._enable_item_btns()
                return

            # Fluxo ER: N1 estrutural não se aplica — propaga para N2
            if classe == "LJ":
                self.tri_level._refresh_lj_n1_from_latest_sa()
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
            n1_bbox = self.tri_level._get_n1_bbox_for(item_id, classe)

            if col.img_widget.is_loaded:
                # DXF já carregado — só reposiciona viewport
                if n1_bbox:
                    if classe == "LJ" and hasattr(col.img_widget, "set_highlight_geometry"):
                        col.img_widget.set_highlight_geometry(self.tri_level._get_lj_n1_points(item_id))
                    elif hasattr(col.img_widget, "set_highlight_bbox"):
                        col.img_widget.set_highlight_bbox(n1_bbox)
                    col.img_widget.zoom_to_bbox(n1_bbox)
                    col.pipeline.set_step(1, 'ok', item_id)
                else:
                    # Item sem posição no DXF (scan async ainda pendente ou sem labels)
                    col.pipeline.set_step(1, 'ok', f'{item_id} (pav completo)')
            else:
                # DXF não carregado (primeira vez ou após reset) — carrega e faz zoom
                n1_dxf = self.tri_level._find_n1_project_dxf(obra, pav)
                if not n1_dxf:
                    obra_dir = DADOS_OBRAS_ROOT / obra
                    n1_dxf = self.tri_level._find_n1_clean_dxf(obra_dir, pav)
                if n1_dxf and n1_dxf.exists():
                    col.load_content(str(n1_dxf), n1_bbox)
                    if classe == "LJ" and hasattr(col.img_widget, "set_highlight_geometry"):
                        col.img_widget.set_highlight_geometry(self.tri_level._get_lj_n1_points(item_id))
                    elif hasattr(col.img_widget, "set_highlight_bbox"):
                        col.img_widget.set_highlight_bbox(n1_bbox)
                    col.pipeline.set_step(1, 'ok', item_id)
                    self._n1_loaded_pav = f"{obra}/{pav}"
                else:
                    col.pipeline.set_step(1, 'error', 'DXF limpo não encontrado')

            # Step 3: ficha N1 — class-aware (campos do Structural Analyzer)
            col.pipeline.set_step(2, 'running', '')
            col.set_ficha(self.tri_level._ficha_n1_for(classe, item_id))
            col.pipeline.set_step(2, 'ok', '')

            self.nav_sidebar.set_status(f"✅ N1 — {item_id}", Colors.ACCENT_SUCCESS)
            self._refresh_n3_compare_if_active(classe, item_id)

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
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
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
                # Passa pav para filtrar recorte pelo pavimento correto (evita cruzar COBERTURA/TIPO)
                n2_dxf = self._get_recorte_dxf_for_er(obra, classe, item_id, pav=pav)
                n2_bbox = self.tri_level._get_n2_bbox_for(item_id, classe) if classe == "LJ" else None
                _ce_log(f"N2 recorte_path={n2_dxf}")
            else:
                n2_dxf  = self.tri_level._find_n2_dxf(obra, pav, classe)
                n2_bbox = self.tri_level._get_n2_bbox_for(item_id, classe)

            if n2_dxf and n2_dxf.exists():
                _ce_log(f"N2 loading DXF size={n2_dxf.stat().st_size//1024}KB")
                if is_er_flow:
                    self._load_recorte_full_with_optional_zoom(col, n2_dxf, n2_bbox)
                else:
                    col.load_content(str(n2_dxf), n2_bbox)
                self._refresh_n4_compare_if_active(
                    n2_dxf, classe, item_id, n2_bbox, cull_to_bbox=not is_er_flow
                )
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
                if classe == 'LV':
                    er_ficha_lv = self._get_er_ficha_dict(obra, classe, item_id)
                    if er_ficha_lv:
                        col.set_lv_ficha(er_ficha_lv)
            else:
                col.set_ficha(self.tri_level._ficha_n2_for(classe, item_id))
            col.pipeline.set_step(2, 'ok', '')
            self._configure_para_passa_n2(classe, item_id)

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
                "WHERE (obra_name=? OR obra_name='') AND classe=? AND elemento_id=? "
                "ORDER BY CASE WHEN obra_name=? THEN 0 ELSE 1 END, created_at DESC",
                (obra, db_cls, item_id, obra)
            )
            rows = cur.fetchall()
            conn.close()

            _priority = {'aprovado': 0, 'manual_sel': 1, 'manual': 2,
                          'auto_aprovado': 3, 'motor': 4}
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

    def _get_recorte_dxf_for_er(self, obra: str, classe: str, item_id: str,
                                pav: str = "") -> "Path | None":
        """Retorna o recorte DXF individual para o fluxo ER.

        Prioridade:
        1. reverse_eng_fichas filtrado por pavimento (pav passado ou derivado da ficha mais recente)
           — evita cruzar pavimentos (ex: TIPO/12_PAV vs 13_PAV vs COBERTURA)
        2. reverse_eng_fichas ORDER BY id DESC (mais recente = pavimento correto na prática)
        3. reverse_eng_recortes (sem coluna pavimento — pode pegar pavimento errado)
        4. disco direto
        """
        # LV: IDs virtuais "V301_A_Para" → elem_id no DB é "V301"
        if classe == "LV":
            item_id = _lv_elem_id(item_id)
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)

        import sqlite3 as _sqlite3
        db_path = r"D:/Agente-cad-PYSIDE/project_data.vision"

        # Tentativa 1: fichas filtradas por pavimento
        # — se pav não fornecido, deriva do pavimento da ficha mais recente (ORDER BY id DESC)
        try:
            conn = _sqlite3.connect(db_path)
            cur = conn.cursor()
            if pav:
                cur.execute(
                    "SELECT recorte_path FROM reverse_eng_fichas "
                    "WHERE obra_name=? AND classe=? AND elemento_id=? AND pavimento=? "
                    "ORDER BY id DESC LIMIT 1",
                    (obra, db_cls, item_id, pav)
                )
            else:
                # Deriva pavimento da ficha mais recente, depois filtra recorte pelo mesmo pav
                cur.execute(
                    "SELECT pavimento FROM reverse_eng_fichas "
                    "WHERE obra_name=? AND classe=? AND elemento_id=? ORDER BY id DESC LIMIT 1",
                    (obra, db_cls, item_id)
                )
                pav_row = cur.fetchone()
                derived_pav = pav_row[0] if pav_row else None
                if derived_pav:
                    cur.execute(
                        "SELECT recorte_path FROM reverse_eng_fichas "
                        "WHERE obra_name=? AND classe=? AND elemento_id=? AND pavimento=? "
                        "ORDER BY id DESC LIMIT 1",
                        (obra, db_cls, item_id, derived_pav)
                    )
                else:
                    cur.execute(
                        "SELECT recorte_path FROM reverse_eng_fichas "
                        "WHERE obra_name=? AND classe=? AND elemento_id=? ORDER BY id DESC LIMIT 1",
                        (obra, db_cls, item_id)
                    )
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                p = Path(row[0])
                if p.exists():
                    _ce_log(f"N2 recorte via fichas pav={pav}: {p.name}")
                    return p
        except Exception as exc:
            print(f"[CE] _get_recorte_dxf_for_er fichas error: {exc}")

        # Tentativa 2: fichas ORDER BY id DESC (pavimento mais recente)
        try:
            conn = _sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT recorte_path FROM reverse_eng_fichas "
                "WHERE obra_name=? AND classe=? AND elemento_id=? ORDER BY id DESC LIMIT 1",
                (obra, db_cls, item_id)
            )
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                p = Path(row[0])
                if p.exists():
                    _ce_log(f"N2 recorte via fichas recente: {p.name}")
                    return p
        except Exception as exc:
            print(f"[CE] _get_recorte_dxf_for_er fichas-recente error: {exc}")

        # Tentativa 3: reverse_eng_recortes (sem filtro pavimento — pode pegar errado)
        record = self._get_recorte_record(obra, db_cls, item_id)
        if record:
            p = Path(record[0])
            if p.exists():
                _ce_log(f"N2 recorte via recortes: {p.name}")
                return p

        # Tentativa 3: disco direto
        return self._find_disk_dxf_for_er(obra, db_cls, item_id)

    def _ficha_n2_er(self, obra: str, classe: str, item_id: str) -> list:
        """Ficha N2 para fluxo ER — mostra APENAS dados já salvos no DB.
        Nunca roda motor on-demand (processamento pertence ao Diagnostic Reverse Hub).
        Prioridade: reverse_eng_fichas cacheada (qualquer recorte_path) →
        info básica de reverse_eng_recortes → mensagem orientativa."""
        import json as _json
        # LV: IDs virtuais "V301_A_Para" → elem_id no DB é "V301"
        if classe == "LV":
            item_id = _lv_elem_id(item_id)
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)

        if db_cls == "LAJ":
            dxf_path = self._get_recorte_dxf_for_er(obra, classe, item_id)
            if dxf_path:
                try:
                    campos, conf = self._extrair_ficha_motor(db_cls, item_id, str(dxf_path), obra)
                    return self._format_ficha_rows(
                        item_id, db_cls, campos, conf or 0.0,
                        "extraido", "motor reverso LAJ"
                    )
                except Exception as exc:
                    print(f"[CE] _ficha_n2_er LAJ motor error: {exc}")

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
                    "WHERE (obra_name=? OR obra_name='') AND classe=? AND elemento_id=? "
                    "ORDER BY CASE WHEN obra_name=? THEN 0 ELSE 1 END, ROWID DESC LIMIT 1",
                    (obra, db_cls, item_id, obra)
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
                "WHERE (obra_name=? OR obra_name='') AND classe=? AND elemento_id=? "
                "ORDER BY CASE WHEN obra_name=? THEN 0 ELSE 1 END, ROWID DESC LIMIT 1",
                (obra, db_cls, item_id, obra)
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

            def _suffix_rank(path: Path) -> tuple[int, float]:
                m = _re.search(r'_(?:motor|sel)_(\d+)$', path.stem, _re.I)
                num = int(m.group(1)) if m else 0
                try:
                    mtime = path.stat().st_mtime
                except OSError:
                    mtime = 0.0
                return (num, mtime)

            sel_candidates: list[Path] = []
            motor_candidates: list[Path] = []
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
                        sel_candidates.append(dxf)
                    else:
                        motor_candidates.append(dxf)
            if sel_candidates:
                return max(sel_candidates, key=_suffix_rank)
            if motor_candidates:
                return max(motor_candidates, key=_suffix_rank)
            return None
        except Exception:
            return None

    def _materialize_lj_n3_json_from_n1(self, obra: str, item_id: str) -> "Path | None":
        """Escreve JSON_Lajes/{item}.json usando a ficha N1/SA carregada."""
        if not obra or not item_id:
            return None
        try:
            import json as _json
            from src.core.laje_n1_to_robot_ficha import n1_laje_to_robot_ficha

            self.tri_level._refresh_lj_n1_from_latest_sa()
            n1_laje = self.tri_level._get_lj_n1_data(item_id)
            if not n1_laje:
                return None
            ficha = n1_laje_to_robot_ficha(n1_laje)
            if not ficha.get("nome"):
                return None
            ficha["_sa_meta"] = {
                "source": "comparison_engine_n1",
                "item_id": item_id,
                "fields": n1_laje.get("fields", {}),
                "validated_fields": n1_laje.get("validated_fields", []),
                "validated_link_classes": n1_laje.get("validated_link_classes", {}),
            }
            try:
                from src.core.laj_n3_learning import apply_learning_to_ficha, normalize_ficha_pose_coords
                ficha = apply_learning_to_ficha(ficha, teacher=None, record_teacher=False)
                ficha = normalize_ficha_pose_coords(ficha)
            except Exception:
                pass
            ficha["_sa_meta"]["n3_source"] = "comparison_engine_n1"
            ficha["_sa_meta"]["n3_teacher"] = None
            out_dir = DADOS_OBRAS_ROOT / obra / "Fase-4_Sincronizacao" / "JSON_Lajes"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{ficha['nome']}.json"
            out_path.write_text(
                _json.dumps(ficha, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return out_path
        except Exception as exc:
            print(f"[CE] _materialize_lj_n3_json_from_n1 error: {exc}")
            return None

    def _on_gerar_n3(self, classe: str, item_id: str, auto_chain: bool = False, seq: int = -1):
        """Gerar N3: step 1=conversão, step 2=ficha, step 3=gerar DXF + carregar."""
        try:
            if seq >= 0 and seq != self._seq_id:
                return
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
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
            if classe == "LJ":
                self._materialize_lj_n3_json_from_n1(obra, item_id)
            n3_dxf   = self.tri_level._find_n3_dxf(obra_dir, classe, item_id)
            if classe == "LJ":
                n3_dxf = None
            col.set_ficha(self.tri_level._ficha_n3_for(classe, item_id))
            self._configure_level_attention("N3", classe, item_id)
            col.pipeline.set_step(1, 'ok', '')

            col.pipeline.set_step(2, 'running', 'Gerando DXF...')
            if n3_dxf and n3_dxf.exists():
                col.load_content(str(n3_dxf), None)
                col.pipeline.set_step(2, 'ok', 'DXF existente')
                self.nav_sidebar.set_status(f"✅ N3 ok — {item_id}", Colors.ACCENT_SUCCESS)
                self._refresh_n3_compare_n4_if_active(classe, item_id)
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
        if self._process is not None:
            if self._process.state() == QProcess.Running:
                try:
                    self._process.finished.disconnect()
                except (RuntimeError, TypeError):
                    pass
                self._process.kill()
                self._process.waitForFinished(500)
            try:
                self._process.deleteLater()
            except RuntimeError:
                pass
            self._process = None

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

        obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
        obra_dir = str(DADOS_OBRAS_ROOT / obra)
        # LV: script espera stem real (ex: "V301_A"), não ID virtual "V301_A_Para"
        script_item_id = _lv_strip_pp(item_id) if classe == "LV" else item_id

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_proc_out)
        self._process.finished.connect(
            lambda code, _: self._on_n3_gen_done(code, col, classe, item_id)
        )
        args = [str(script), "--obra", obra_dir, "--item", script_item_id]
        self._process.start(sys.executable, args)

    def _on_n3_gen_done(self, code: int, col, classe: str, item_id: str):
        try:
            obra_dir = DADOS_OBRAS_ROOT / (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
        except RuntimeError:
            # Widget C++ já deletado (usuário navegou para outra aba durante geração)
            return
        try:
            n3_dxf = self.tri_level._find_n3_dxf(obra_dir, classe, item_id)
            if code == 0 and n3_dxf and n3_dxf.exists():
                col.load_content(str(n3_dxf), None)
                col.pipeline.set_step(2, 'ok', '')
                col.set_ficha(self.tri_level._ficha_n3_for(classe, item_id))
                self._configure_level_attention("N3", classe, item_id)
                self.nav_sidebar.set_status(f"✅ N3 gerado — {item_id}", Colors.ACCENT_SUCCESS)
                self._refresh_n3_compare_n4_if_active(classe, item_id)
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
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            if not obra or not item_id:
                self.nav_sidebar._enable_item_btns()
                return
        except Exception as exc:
            print(f"[CE] _on_gerar_n4 early error: {exc}")
            return

        try:
            _ce_log(f"N4 start classe={classe} id={item_id}")
            col = self.tri_level._columns[3]
            col.pipeline.reset()

            # Step 1: obter ficha ER completa do motor reverso
            col.pipeline.set_step(0, 'running', 'Lendo ficha ER...')
            _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
            db_cls = _cls_map.get(classe, classe)
            _ce_log(f"N4 get_er_ficha classe={classe} id={item_id}")
            er_ficha = self._get_er_ficha_dict(obra, classe, item_id)
            _ce_log(f"N4 set_ficha classe={classe} id={item_id} er_keys={len(er_ficha or {})}")
            col.set_ficha(self._ficha_rows_from_dict(er_ficha, item_id, db_cls))
            self._configure_level_attention("N4", classe, item_id)
            self._configure_level_attention("N3", classe, item_id)
            col.pipeline.set_step(0, 'ok', '')
            _ce_log(f"N4 step0 ok")

            # ── PIL: 3-panel view (CIMA | ABCD | GRADES) ────────────────────────
            if classe == 'PL':
                col.pipeline.set_step(1, 'running', 'Gerando zonas N4...')
                obra_dir_pil = DADOS_OBRAS_ROOT / obra
                # N4 PIL: gera das fichas N2 (er_ficha) com pd_pavimento_cm injetado
                # em subdir n4/ (sempre fresh — não usa cache N3 de Fase-4/N1).
                zone_paths = self._generate_pil_zones_n4(obra_dir_pil, obra, item_id, er_ficha)
                n_found = sum(1 for p in zone_paths.values() if p and p.exists())
                n_total = len(zone_paths)
                zone_fichas = self._get_pil_zone_fichas(obra, item_id, er_ficha)
                col.switch_to_pil_zones(zone_paths, er_ficha, zone_fichas)
                zones_label = '·'.join(z for z in ('CIMA', 'ABCD', 'GRADES', 'EFGH') if z in zone_paths)
                col.pipeline.set_step(1, 'ok', zones_label)
                col.pipeline.set_step(2, 'ok', f'{item_id} ({n_found}/{n_total} zonas)')
                self.nav_sidebar.set_status(
                    f"✅ N4 PIL {n_total}-panel — {item_id}", Colors.ACCENT_SUCCESS)
                self.nav_sidebar._enable_item_btns()
                return

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
            # LV also regenerates: the selected recorte is extracted with the
            # current motor, so an older cached DXF must not win.
            force_regen = classe in ("LJ", "FV", "LV")
            _ce_log(f"N4 dxf_check n4_dxf={n4_dxf} force_regen={force_regen}")
            if n4_dxf and n4_dxf.exists() and not force_regen:
                if classe == 'LV':
                    # 2-panel view: Visão Corte | Lateral A-B
                    # sect_total = max(SECT_W+SECT_GAP, b+178) = max(190, b+178)
                    # Face A começa em x = sect_total — corte 15cm antes para não incluir painéis
                    vc_bbox, lat_bbox = self._lv_n4_zone_bboxes(er_ficha or {})
                    lv_zones = {
                        'Visão Corte': (str(n4_dxf), vc_bbox),
                        'Lateral A-B': (str(n4_dxf), lat_bbox),
                    }
                    col.switch_to_lv_zones(lv_zones, er_ficha or {})
                    col.pipeline.set_step(2, 'ok', Path(n4_dxf).name[:25])
                    self.nav_sidebar.set_status(f"✅ N4 LV — {item_id}", Colors.ACCENT_SUCCESS)
                    self._refresh_n3_compare_n4_if_active(classe, item_id)
                    self.nav_sidebar._enable_item_btns()
                else:
                    n4_bbox = self.tri_level._get_n2_bbox_for(item_id, classe) if classe == "LJ" else None
                    col.load_content(str(n4_dxf), n4_bbox)
                    col.pipeline.set_step(2, 'ok', Path(n4_dxf).name[:25])
                    self.nav_sidebar.set_status(f"✅ N4 ok — {item_id}", Colors.ACCENT_SUCCESS)
                    self._refresh_n3_compare_n4_if_active(classe, item_id)
                    self.nav_sidebar._enable_item_btns()
            else:
                # Gera DXF via temp JSON (Option B)
                col.pipeline.set_step(2, 'running', 'Gerando via robô...')
                _ce_log(f"N4 generate classe={classe} id={item_id} via={'lv_gen' if classe=='LV' else 'robot'}")
                if classe == 'LV':
                    self._start_n4_lv_generation(item_id, er_ficha, obra_dir, col)
                else:
                    self._start_n4_generation(classe, item_id, er_ficha, obra_dir, script, col)
                _ce_log(f"N4 generate launched")

        except Exception as exc:
            print(f"[CE] _on_gerar_n4 error: {exc}")
            try:
                self.nav_sidebar._enable_item_btns()
            except Exception:
                pass

    def _on_gerar_n5(self, classe: str, item_ids: list):
        """N5: monta 1 DXF consolidado da classe a partir dos previews N3."""
        try:
            obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
            pav = self.fase8_panel.current_pav_key
            if not obra:
                self.nav_sidebar._enable_item_btns()
                return

            col = self.tri_level._columns[4]
            col.pipeline.reset()
            col.pipeline.set_step(0, 'running', f'{classe} ({len(item_ids)})')
            if classe not in ("LJ", "FV"):
                col.pipeline.set_step(0, 'error', 'classe sem N5')
                self.nav_sidebar.set_status("N5 suporta apenas LJ e FV neste ciclo", Colors.TEXT_DIM)
                self.nav_sidebar._enable_item_btns()
                return

            obra_dir = DADOS_OBRAS_ROOT / obra
            from src.core.n5_assembler import assemble_n5

            col.pipeline.set_step(0, 'ok', f'{len(item_ids)} itens')
            col.pipeline.set_step(1, 'running', 'Consolidando...')
            result = assemble_n5(obra_dir, classe, item_ids=item_ids, pavimento=pav)
            col.pipeline.set_step(1, 'ok', f'{result.ok_count}/{len(result.items)} ok')

            col.pipeline.set_step(2, 'running', 'Carregando DXF...')
            rows = [
                ("Classe", result.classe),
                ("Obra", result.obra),
                ("Pavimento", result.pavimento or "GERAL"),
                ("DXF N5", str(result.output_path)),
                ("Manifest", str(result.manifest_path)),
                ("Itens OK", str(result.ok_count)),
                ("Itens ausentes/erro", str(result.missing_count)),
                ("Regra", "LJ: coordenadas nativas; FV: grade de folhas ordenada"),
            ]
            for n5_item in result.items[:80]:
                status = n5_item.status.upper()
                msg = n5_item.message or (Path(n5_item.source).name if n5_item.source else "")
                rows.append((f"{n5_item.item_id} [{status}]", msg))
            if len(result.items) > 80:
                rows.append(("Itens omitidos", str(len(result.items) - 80)))

            col.set_ficha(rows)
            col.load_content(str(result.output_path), None)
            col.pipeline.set_step(2, 'ok', result.output_path.name)
            self.tri_level._nivel_tabs.setCurrentIndex(4)
            self.nav_sidebar.set_status(
                f"✅ N5 {classe}: {result.ok_count}/{len(result.items)} itens",
                Colors.ACCENT_SUCCESS if result.missing_count == 0 else Colors.ACCENT_WARNING,
            )
        except Exception as exc:
            try:
                self.tri_level._columns[4].pipeline.set_step(2, 'error', str(exc)[:30])
            except Exception:
                pass
            self.nav_sidebar.set_status(f"❌ N5 erro: {str(exc)[:60]}", Colors.ACCENT_DANGER)
            print(f"[CE] _on_gerar_n5 error: {exc}")
        finally:
            try:
                self.nav_sidebar._enable_item_btns()
            except Exception:
                pass

    def _get_er_ficha_dict(self, obra: str, classe: str, item_id: str) -> dict:
        """Retorna a ficha ER como dicionário (para passar ao script robô).
        Tenta DB primeiro, depois motor on-demand no DXF do disco."""
        import json as _json, re as _re
        # LV: IDs virtuais "V301_A_Para" → elem_id no DB/motor é "V301"
        if classe == "LV":
            item_id = _lv_elem_id(item_id)
        _cls_map = {"PL": "PIL", "LV": "LV", "FV": "FV", "LJ": "LAJ"}
        db_cls = _cls_map.get(classe, classe)

        # LV: fichas não estão no DB — ler de fichas_lv_v2.json (pré-gerado pelo motor)
        if db_cls == "LV":
            try:
                import sys as _sys
                scripts_dir = str(
                    Path(__file__).parent.parent.parent.parent / "scripts")
                if scripts_dir not in _sys.path:
                    _sys.path.insert(0, scripts_dir)
                dxf_path = self._get_recorte_dxf_for_er(
                    obra, classe, item_id,
                    pav=self.fase8_panel.current_pav_key,
                )
                if dxf_path:
                    from motor_reverso_lv import extrair_ficha_lateral_viga
                    ficha = extrair_ficha_lateral_viga(
                        str(dxf_path),
                        item_id,
                        obra_name=obra,
                        obra_root=DADOS_OBRAS_ROOT / obra,
                    )
                    if ficha:
                        _ce_log(
                            f"LV ficha live {item_id}: "
                            f"face_units={len(ficha.get('face_units') or [])} "
                            f"sections={len(ficha.get('section_views') or [])}"
                        )
                        return ficha
            except Exception as exc:
                _ce_log(f"LV ficha live falhou {item_id}: {exc}")

        # FV: motor live no recorte (igual ao LV) — garante fixes de tier e _multiplier
        if db_cls == "FV":
            try:
                import sys as _sys
                scripts_dir = str(Path(__file__).parent.parent.parent.parent / "scripts")
                if scripts_dir not in _sys.path:
                    _sys.path.insert(0, scripts_dir)
                dxf_path = self._get_recorte_dxf_for_er(
                    obra, classe, item_id,
                    pav=self.fase8_panel.current_pav_key,
                )
                if dxf_path:
                    from motor_reverso_fv import extrair_ficha_fundo_viga
                    ficha = extrair_ficha_fundo_viga(
                        str(dxf_path),
                        item_id,
                        obra_name=obra,
                        obra_root=DADOS_OBRAS_ROOT / obra,
                    )
                    if ficha:
                        _ce_log(
                            f"FV ficha live {item_id}: "
                            f"segments={len(ficha.get('segments_rich') or [])}"
                        )
                        return ficha
            except Exception as exc:
                _ce_log(f"FV ficha live falhou {item_id}: {exc}")

        if db_cls == "LAJ":
            try:
                import sys as _sys
                scripts_dir = str(Path(__file__).parent.parent.parent.parent / "scripts")
                if scripts_dir not in _sys.path:
                    _sys.path.insert(0, scripts_dir)
                dxf_path = self._get_recorte_dxf_for_er(obra, classe, item_id)
                if dxf_path:
                    from motor_reverso_laj import extrair_ficha_laje
                    return extrair_ficha_laje(str(dxf_path), item_id, obra)
            except Exception:
                pass
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

    def _find_or_generate_pil_zones(self, obra_dir: Path, item_id: str) -> dict:
        """Find (or generate if missing) zone DXFs for a PIL item.
        Returns {'ABCD': Path|None, 'CIMA': Path|None, 'GRADES': Path|None,
                 'EFGH': Path|None}  — EFGH only when subtipo_pil == 'U'.
        Generation uses the static Fase-4 JSON (fast, <1s per zone).
        """
        import subprocess as _sp, json as _json
        out_dir = obra_dir / "Fase-6_Execucao_CAD"
        out_dir.mkdir(parents=True, exist_ok=True)
        script = SCRIPTS_DIR / "gerar_pl_dxf_stog.py"

        # Detect subtipo from Fase-4 JSON
        pj_path = obra_dir / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item_id}.json"
        subtipo = 'RETANGULAR'
        if pj_path.exists():
            try:
                subtipo = _json.loads(pj_path.read_text('utf-8')).get('subtipo_pil', 'RETANGULAR')
            except Exception:
                pass

        zones = ["ABCD", "CIMA", "GRADES"]
        if subtipo == 'U':
            zones.append("EFGH")

        results = {}
        for zone in zones:
            expected = out_dir / f"PL_{zone}_preview_{item_id}.dxf"
            if not expected.exists() and script.exists():
                try:
                    _sp.run(
                        [sys.executable, str(script),
                         "--obra", str(obra_dir),
                         "--item", item_id,
                         "--zone", zone.lower()],
                        capture_output=True, timeout=30,
                    )
                except Exception as _e:
                    print(f"[CE] PIL zone {zone} gen error: {_e}")
            results[zone] = expected if expected.exists() else None
        return results

    def _extract_pd_from_n2_dxf(self, dxf_path: "Path") -> "float | None":
        """Extrai pd_pavimento_cm do DXF N2 medindo a maior cota vertical do ABCD.

        O pd real de cada pilar está codificado como a cota total à esquerda do
        bloco ABCD (ex: 321 para P10 13_PAV). Pode variar por pilar mesmo dentro
        do mesmo pavimento.

        Estratégia (ordem de prioridade):
        1. DIMENSION entities → abs(defpoint2.y - defpoint3.y) — leitura direta das cotas
        2. TEXT/MTEXT com valor numérico no intervalo plausível [150, 700]
        3. Bounding-box geométrico (max_y - min_y de LINE/LWPOLYLINE)
        Em todos os casos: retorna o MAIOR valor encontrado (pd é sempre o maior).
        """
        try:
            import ezdxf as _ez
            doc = _ez.readfile(str(dxf_path))
            msp = doc.modelspace()
            candidates: list[float] = []

            for e in msp:
                t = e.dxftype()
                if t == "DIMENSION":
                    try:
                        val = abs(e.dxf.defpoint2.y - e.dxf.defpoint3.y)
                        if 150.0 <= val <= 700.0:
                            candidates.append(val)
                    except Exception:
                        pass
                elif t in ("TEXT", "MTEXT"):
                    try:
                        raw = e.dxf.text if t == "TEXT" else e.text
                        # Strip MTEXT escape sequences  {\f...;value}
                        import re as _re
                        raw = _re.sub(r'\{[^}]*\}', '', raw).strip()
                        raw = raw.replace(",", ".")
                        val = float(raw)
                        if 150.0 <= val <= 700.0:
                            candidates.append(val)
                    except Exception:
                        pass

            if candidates:
                pd = round(max(candidates), 1)
                _ce_log(f"pd extraido do DXF N2: {pd} (de {len(candidates)} candidatos)")
                return pd

            # Fallback geométrico
            ys: list[float] = []
            for e in msp:
                t = e.dxftype()
                if t == "LINE":
                    ys += [e.dxf.start.y, e.dxf.end.y]
                elif t == "LWPOLYLINE":
                    ys += [p[1] for p in e.get_points()]
            if ys:
                span = round(max(ys) - min(ys), 1)
                if 150.0 <= span <= 700.0:
                    _ce_log(f"pd extraido do DXF N2 (bbox): {span}")
                    return span
        except Exception as _e:
            print(f"[CE] _extract_pd_from_n2_dxf: {_e}")
        return None

    def _extract_laje_per_face_from_n2_dxf(
        self, dxf_path: "Path", pd_val: "float | None" = None
    ) -> "dict[str, float]":
        """Extrai laje_{face} e posicao_laje_{face} do DXF N2 por face ABCD.

        Algoritmo:
        1. Encontra x-posição dos labels "P{n}.{face}" (layer NOMENCLATURA).
        2. Para cada face, coleta COTAs (TEXT, layer COTA, valor >10) no intervalo
           x-label → x-próximo-label.
        3. Se sum(cotas_face) < pd: zona vazia = posicao_laje; maior cota do topo = laje.

        Retorna dict com chaves laje_A, posicao_laje_A, laje_B, etc. (0.0 = sem sub-painel).
        """
        import re as _re2
        result: dict[str, float] = {}
        try:
            import ezdxf as _ez2
            doc = _ez2.readfile(str(dxf_path))
            msp = doc.modelspace()

            # Face label x-positions
            face_label_xs: dict[str, float] = {}
            face_label_ys: list[float] = []
            for e in msp:
                if e.dxftype() == 'TEXT':
                    m = _re2.match(r'^[A-Z]\d+\.([ABCDEFGH])$', e.dxf.text.strip())
                    if m:
                        face_label_xs[m.group(1)] = e.dxf.insert.x
                        face_label_ys.append(e.dxf.insert.y)
            # y_face_base: exclui cotas de largura (comprimento=82) abaixo da base
            y_face_base = (min(face_label_ys) - 20.0) if face_label_ys else -1e9

            if len(face_label_xs) < 2:
                # Fallback geométrico: DXFs sem labels de texto (ex: TIPO/12_PAV)
                # SARR_2.2x7 span = (h_low - h1) + h_par = 122 + h_par
                _sarr_ys_fb: list[float] = []
                for _e_fb in msp:
                    if _e_fb.dxf.layer == 'SARR_2.2x7':
                        if _e_fb.dxftype() == 'LINE':
                            _sarr_ys_fb += [_e_fb.dxf.start.y, _e_fb.dxf.end.y]
                        elif _e_fb.dxftype() == 'LWPOLYLINE':
                            _sarr_ys_fb += [p[1] for p in _e_fb.get_points()]
                if _sarr_ys_fb:
                    _h_par_fb = round(max(_sarr_ys_fb) - min(_sarr_ys_fb) - 122.0, 1)
                    if 50.0 <= _h_par_fb <= 150.0:
                        for _face_fb in ('A', 'B'):
                            result[f'h_par_{_face_fb}'] = _h_par_fb
                        _ce_log(f"N2 DXF geometric h_par={_h_par_fb:.0f} (sem labels)")
                return result

            # pd: maior cota plausível (DIMENSION ou TEXT)
            if pd_val is None:
                pd_cands: list[float] = []
                for e in msp:
                    t = e.dxftype()
                    if t == 'DIMENSION':
                        try:
                            v = abs(e.dxf.defpoint2.y - e.dxf.defpoint3.y)
                            if 150.0 <= v <= 700.0:
                                pd_cands.append(v)
                        except Exception:
                            pass
                    elif t in ('TEXT', 'MTEXT'):
                        try:
                            raw = e.dxf.text if t == 'TEXT' else e.text
                            raw = _re2.sub(r'\{[^}]*\}', '', raw).strip().replace(',', '.')
                            v = float(raw)
                            if 150.0 <= v <= 700.0:
                                pd_cands.append(v)
                        except Exception:
                            pass
                pd_val = round(max(pd_cands), 1) if pd_cands else None

            if pd_val is None:
                return result

            # COTA texts com posição x
            # y >= y_face_base: exclui cotas de largura (ex: "82") abaixo da base
            cota_xy: list[tuple[float, float, float]] = []
            for e in msp:
                if e.dxftype() == 'TEXT' and 'COTA' in e.dxf.layer.upper():
                    try:
                        v = float(e.dxf.text.strip().replace(',', '.'))
                        if 2.0 <= v <= 700.0 and e.dxf.insert.y >= y_face_base:
                            cota_xy.append((e.dxf.insert.x, e.dxf.insert.y, v))
                    except Exception:
                        pass

            faces_sorted = sorted(face_label_xs.items(), key=lambda kv: kv[1])
            for i, (face, x_face) in enumerate(faces_sorted):
                if face not in ('A', 'B', 'C', 'D'):
                    continue
                x_next = (faces_sorted[i + 1][1]
                          if i + 1 < len(faces_sorted)
                          else x_face + 600.0)

                # Limites de x por face: midpoints entre labels adjacentes evitam
                # contaminação cruzada (ex: linhas de face C vazando para face B).
                x_mid_left  = ((faces_sorted[i - 1][1] + x_face) / 2
                                if i > 0 else x_face - 600.0)
                x_mid_right = ((x_face + x_next) / 2)

                # ── Painéis intervals (geometria real do N2) ──────────────────
                # Linhas horizontais da layer Painéis dentro desta face.
                # Representam TODAS as divisões de painel (incluindo sub-painéis
                # complexos como P28/P30 com 5+ segmentos).
                _p_hs = sorted(set(
                    round(_ep.dxf.start.y, 1)
                    for _ep in msp
                    if _ep.dxftype() == 'LINE'
                    and 'PAIN' in _ep.dxf.layer.upper()
                    and abs(_ep.dxf.start.y - _ep.dxf.end.y) < 0.5
                    and x_mid_left <= (_ep.dxf.start.x + _ep.dxf.end.x) / 2 <= x_mid_right
                    and _ep.dxf.start.y >= y_face_base
                ))
                if len(_p_hs) >= 2:
                    _ivs = [round(_p_hs[_j + 1] - _p_hs[_j], 1)
                            for _j in range(len(_p_hs) - 1)]
                    # Normalizar: se o primeiro intervalo = h1 (~2cm), remover.
                    # Alguns DXFs têm linha Painéis em y_bot (P18); outros em y_bot+h1.
                    # draw_abcd sempre trata h1 separadamente.
                    if _ivs and abs(_ivs[0] - 2.0) < 0.5:
                        _ivs = _ivs[1:]
                    if len(_ivs) >= 1:
                        result[f'paineis_intervals_{face}'] = _ivs
                        _ce_log(f"N2 DXF face {face}: paineis_intervals={_ivs}")

                    # ── Abertura: verticais Painéis dentro dos limites x da face ──
                    _y_h0_ce = _p_hs[0]
                    _face_th_ce = _p_hs[-1] - _p_hs[0]
                    _hx_ce = []
                    for _ehx_ce in msp:
                        if _ehx_ce.dxftype() != 'LINE': continue
                        if 'PAIN' not in _ehx_ce.dxf.layer.upper(): continue
                        if abs(_ehx_ce.dxf.start.y - _ehx_ce.dxf.end.y) > 0.5: continue
                        _xc_ce = (_ehx_ce.dxf.start.x + _ehx_ce.dxf.end.x) / 2
                        if (x_mid_left <= _xc_ce <= x_mid_right
                                and _ehx_ce.dxf.start.y >= y_face_base):
                            _hx_ce.extend([_ehx_ce.dxf.start.x, _ehx_ce.dxf.end.x])
                    if _hx_ce and _face_th_ce > 0:
                        _xl_ce = min(_hx_ce)
                        _xr_ce = max(_hx_ce)
                        # menor H por y → endpoints
                        _mep_ce: dict = {}
                        for _ehx2c in msp:
                            if _ehx2c.dxftype() != 'LINE': continue
                            if 'PAIN' not in _ehx2c.dxf.layer.upper(): continue
                            if abs(_ehx2c.dxf.start.y - _ehx2c.dxf.end.y) > 0.5: continue
                            _xc2c = (_ehx2c.dxf.start.x + _ehx2c.dxf.end.x) / 2
                            if not (x_mid_left <= _xc2c <= x_mid_right
                                    and _ehx2c.dxf.start.y >= y_face_base): continue
                            _epy2c = round(_ehx2c.dxf.start.y, 1)
                            _epw2c = abs(_ehx2c.dxf.start.x - _ehx2c.dxf.end.x)
                            _ex1c  = round(min(_ehx2c.dxf.start.x, _ehx2c.dxf.end.x), 1)
                            _ex2c  = round(max(_ehx2c.dxf.start.x, _ehx2c.dxf.end.x), 1)
                            if _epy2c not in _mep_ce or _epw2c < _mep_ce[_epy2c][2]:
                                _mep_ce[_epy2c] = (_ex1c, _ex2c, _epw2c)
                        # coleta inner verts individuais
                        _ivraw_ce = []
                        for _ev_ce in msp:
                            if _ev_ce.dxftype() != 'LINE': continue
                            if 'PAIN' not in _ev_ce.dxf.layer.upper(): continue
                            _xs_ce, _xe_ce = _ev_ce.dxf.start.x, _ev_ce.dxf.end.x
                            _ys_ce, _ye_ce = _ev_ce.dxf.start.y, _ev_ce.dxf.end.y
                            if abs(_xs_ce - _xe_ce) > 0.5: continue
                            _xv_ce = (_xs_ce + _xe_ce) / 2
                            if _xv_ce <= _xl_ce + 2.0 or _xv_ce >= _xr_ce - 2.0: continue
                            if _xv_ce < x_mid_left or _xv_ce > x_mid_right: continue
                            if abs(_ys_ce - _ye_ce) < 5.0: continue
                            if max(_ys_ce, _ye_ce) < y_face_base: continue
                            _ivraw_ce.append({
                                'x':     round(_xv_ce, 1),
                                'y_bot': round(min(_ys_ce, _ye_ce), 1),
                                'y_top': round(max(_ys_ce, _ye_ce), 1),
                            })
                        # agrupa por x (±3cm), guarda segs individuais
                        _grps_ce: list = []
                        for _vv_ce in sorted(_ivraw_ce, key=lambda v: v['x']):
                            _placed_ce = False
                            for _g_ce in _grps_ce:
                                if abs(_vv_ce['x'] - _g_ce['x']) <= 3.0:
                                    _g_ce['y_bot'] = min(_g_ce['y_bot'], _vv_ce['y_bot'])
                                    _g_ce['y_top'] = max(_g_ce['y_top'], _vv_ce['y_top'])
                                    _g_ce['segs'].append({'y_bot': _vv_ce['y_bot'], 'y_top': _vv_ce['y_top']})
                                    _placed_ce = True; break
                            if not _placed_ce:
                                _grps_ce.append({
                                    'x': _vv_ce['x'], 'y_bot': _vv_ce['y_bot'], 'y_top': _vv_ce['y_top'],
                                    'segs': [{'y_bot': _vv_ce['y_bot'], 'y_top': _vv_ce['y_top']}],
                                })
                        # filtro ratio
                        _rok_ce = [_g for _g in _grps_ce
                                   if (_g['y_top'] - _g['y_bot']) / _face_th_ce < 0.45]
                        if _rok_ce:
                            def _ep_ce(_xv, _y):
                                _ep = _mep_ce.get(_y)
                                return _ep and min(abs(_xv - _ep[0]), abs(_xv - _ep[1])) <= 2.5
                            if len(_rok_ce) >= 3:
                                _ov_ce = []
                                for _g_ce in _rok_ce:
                                    for _sg_ce in sorted(_g_ce['segs'], key=lambda s: s['y_bot']):
                                        if _ep_ce(_g_ce['x'], _sg_ce['y_bot']) or _ep_ce(_g_ce['x'], _sg_ce['y_top']):
                                            _g_ce['y_bot_u'] = _sg_ce['y_bot']
                                            _g_ce['y_top_u'] = _sg_ce['y_top']
                                            _ov_ce.append(_g_ce); break
                            else:
                                for _g_ce in _rok_ce:
                                    _g_ce['y_bot_u'] = _g_ce['y_bot']
                                    _g_ce['y_top_u'] = _g_ce['y_top']
                                _ov_ce = _rok_ce
                            _ab_ce: dict | None = None
                            if len(_ov_ce) == 1:
                                _vce = _ov_ce[0]
                                _dl_ce = _vce['x'] - _xl_ce; _dr_ce = _xr_ce - _vce['x']
                                _ab_ce = {
                                    'lado':    'esquerdo' if _dl_ce <= _dr_ce else 'direito',
                                    'largura': round(_dl_ce if _dl_ce <= _dr_ce else _dr_ce, 1),
                                    'y_rel':   round(_vce['y_bot_u'] - _y_h0_ce, 1),
                                    'altura':  round(_vce['y_top_u'] - _vce['y_bot_u'], 1),
                                }
                            elif len(_ov_ce) == 2:
                                _v1c, _v2c = _ov_ce
                                _ab_ce = {
                                    'lado':     'meio',
                                    'largura':  round(_v2c['x'] - _v1c['x'], 1),
                                    'x_offset': round(_v1c['x'] - _xl_ce, 1),
                                    'y_rel':    round(min(_v1c['y_bot_u'], _v2c['y_bot_u']) - _y_h0_ce, 1),
                                    'altura':   round(max(_v1c['y_top_u'], _v2c['y_top_u'])
                                                     - min(_v1c['y_bot_u'], _v2c['y_bot_u']), 1),
                                }
                            if _ab_ce is not None:
                                result[f'abertura_{face}'] = _ab_ce
                                _ce_log(f"N2 DXF face {face}: abertura={_ab_ce}")

                # Cotas desta face: valores >10 (excluem h1=2, larguras=7/19)
                face_cotas_y = sorted(
                    [(fy, v) for fx, fy, v in cota_xy
                     if x_face <= fx <= x_next and v > 10.0],
                    reverse=True,  # y decrescente = topo → base
                )
                face_vals = [v for _, v in face_cotas_y]
                face_vals_asc = list(reversed(face_vals))  # base → topo

                # h_par: 2ª cota da base = zona parafuso (varia por pilar).
                # Para pilares com intervals, h_par é intervals[1] (mais confiável).
                _ivs_face = result.get(f'paineis_intervals_{face}')
                if _ivs_face and len(_ivs_face) >= 2:
                    result[f'h_par_{face}'] = float(_ivs_face[1])
                    _ce_log(f"N2 DXF face {face}: h_par={_ivs_face[1]:.0f} (via intervals)")
                elif len(face_vals_asc) >= 2:
                    result[f'h_par_{face}'] = float(face_vals_asc[1])
                    _ce_log(f"N2 DXF face {face}: h_par={face_vals_asc[1]:.0f} (via COTA)")

                # Laje detectada: requer >= 3 cotas (h_low + H_PAR + laje_panel).
                # 2 cotas = H_PAR não-padrão (ex: P1.A=[97,124]) — sem sub-painel.
                # Não usar quando intervals já incluem o sub-painel (evita duplicação).
                if not _ivs_face and len(face_vals) >= 3:
                    gap = round(pd_val - sum(face_vals), 1)
                    if gap > 5.0:
                        result[f'laje_{face}']         = float(face_vals[0])
                        result[f'posicao_laje_{face}'] = gap
                        _ce_log(
                            f"N2 DXF face {face}: laje={face_vals[0]:.0f} "
                            f"posicao={gap:.0f} (pd={pd_val}, sum={sum(face_vals):.0f})"
                        )

        except Exception as _e:
            print(f"[CE] _extract_laje_per_face_from_n2_dxf: {_e}")
        return result

    def _get_pd_pavimento_cm(self, obra: str, item_id: str,
                              obra_dir: "Path | None" = None) -> "float | None":
        """Fallback de pd quando nao foi possivel extrair do DXF N2.

        Prioridade:
        1. Fase-4 JSON real (N1) — tem o campo explícito, valor preciso.
        2. DB pavimento → arete_config.PD_PAVIMENTO_CM (constante por pavimento).
        Usar apenas como último recurso — prefira _extract_pd_from_n2_dxf().
        """
        # 1. Fase-4 N1 JSON (mais confiável — tem pd_pavimento_cm explícito)
        if obra_dir is not None:
            pj = obra_dir / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item_id}.json"
            if pj.exists():
                try:
                    import json as _j
                    val = _j.loads(pj.read_text('utf-8')).get('pd_pavimento_cm')
                    if val:
                        return float(val)
                except Exception:
                    pass
        # 2. DB pavimento → PD_PAVIMENTO_CM (ORDER BY id DESC = ficha mais recente)
        try:
            import sqlite3 as _sq
            conn = _sq.connect(r"D:/Agente-cad-PYSIDE/project_data.vision")
            cur = conn.cursor()
            cur.execute(
                "SELECT pavimento FROM reverse_eng_fichas "
                "WHERE obra_name=? AND elemento_id=? ORDER BY id DESC LIMIT 1",
                (obra, item_id),
            )
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                import sys as _sys
                arete_dir = str(Path(__file__).parent.parent.parent.parent / "scripts" / "arete")
                if arete_dir not in _sys.path:
                    _sys.path.insert(0, arete_dir)
                from arete_config import PD_PAVIMENTO_CM
                return PD_PAVIMENTO_CM.get(row[0])
        except Exception as _e:
            print(f"[CE] _get_pd_pavimento_cm: {_e}")
        return None

    def _generate_pil_zones_n4(self, obra_dir: Path, obra: str,
                                item_id: str, er_ficha: dict) -> dict:
        """Gera zonas PIL N4 a partir da ficha N2 (er_ficha).

        - Usa er_ficha (N2) com pd_pavimento_cm injetado (não usa Fase-4/N1).
        - Escreve em Fase-6_Execucao_CAD/n4/ (subdir separado do N3).
        - Sempre regenera (sem cache — ficha pode ter mudado).
        """
        import subprocess as _sp, json as _json, tempfile as _tmp

        # 1. Preparar ficha N2 com pd_pavimento_cm
        campos = {k: v for k, v in er_ficha.items() if not k.startswith('_')}

        # Fonte primária: extrair pd da cota total do DXF N2 (varia por pilar,
        # mesmo dentro do mesmo pavimento — nao usar constante por pav).
        try:
            pav = self.fase8_panel.current_pav_key
        except Exception:
            pav = ""
        n2_dxf_path = self._get_recorte_dxf_for_er(obra, 'PL', item_id, pav=pav)
        pd_from_dxf = self._extract_pd_from_n2_dxf(n2_dxf_path) if n2_dxf_path else None

        if pd_from_dxf is not None:
            campos['pd_pavimento_cm'] = pd_from_dxf
            _ce_log(f"N4 PIL {item_id}: pd_pavimento_cm={pd_from_dxf} (DXF N2 geometry)")
        elif 'pd_pavimento_cm' not in campos:
            # Fallback: Fase-4 N1 JSON ou constante por pavimento
            pd_cm = self._get_pd_pavimento_cm(obra, item_id, obra_dir=obra_dir)
            if pd_cm is not None:
                campos['pd_pavimento_cm'] = pd_cm
                _ce_log(f"N4 PIL {item_id}: pd_pavimento_cm={pd_cm} (fallback N1/constante)")

        # Per-face laje: extrair do DXF N2 e sobrescrever campos da ficha
        # (fichas antigas no DB têm laje_B=0; a geometria N2 é fonte de verdade)
        if n2_dxf_path:
            _laje_fields = self._extract_laje_per_face_from_n2_dxf(
                n2_dxf_path, pd_val=campos.get('pd_pavimento_cm')
            )
            if _laje_fields:
                campos.update(_laje_fields)
                _ce_log(f"N4 PIL {item_id}: per-face laje injetado: {_laje_fields}")

        # subtipo_pil: da ficha N2 ou da Fase-4 N1 (para decidir zonas)
        subtipo = campos.get('subtipo_pil', 'RETANGULAR')
        if subtipo == 'RETANGULAR':
            pj_n1 = obra_dir / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{item_id}.json"
            if pj_n1.exists():
                try:
                    subtipo = _json.loads(pj_n1.read_text('utf-8')).get('subtipo_pil', 'RETANGULAR')
                except Exception:
                    pass

        # 2. Escrever JSON N2 em temp dir com layout Fase-4
        tmp_dir = Path(_tmp.gettempdir()) / f"ce_n4_PIL_{item_id}"
        json_subdir = tmp_dir / "Fase-4_Sincronizacao" / "JSON_Pilares"
        json_subdir.mkdir(parents=True, exist_ok=True)
        out_dir_n4 = tmp_dir / "Fase-6_Execucao_CAD"
        out_dir_n4.mkdir(parents=True, exist_ok=True)
        (tmp_dir / "Fase-6_Execucao_CAD" / "n4").mkdir(parents=True, exist_ok=True)
        json_path = json_subdir / f"{item_id}.json"
        json_path.write_text(
            _json.dumps(campos, indent=2, ensure_ascii=False), encoding='utf-8'
        )

        # 3. Gerar zonas N4 em out_dir_n4
        script = SCRIPTS_DIR / "gerar_pl_dxf_stog.py"
        zones = ["ABCD", "CIMA", "GRADES"]
        if subtipo == 'U':
            zones.append("EFGH")

        results: dict = {}
        for zone in zones:
            expected = out_dir_n4 / f"PL_{zone}_preview_{item_id}.dxf"
            if script.exists():
                try:
                    _sp.run(
                        [sys.executable, str(script),
                         "--obra", str(tmp_dir),
                         "--item", item_id,
                         "--zone", zone.lower()],
                        capture_output=True, timeout=30,
                    )
                except Exception as _e:
                    print(f"[CE] PIL N4 zone {zone} gen error: {_e}")
            results[zone] = expected if expected.exists() else None
        return results

    def _get_pil_zone_fichas(self, obra: str, item_id: str,
                              er_ficha: dict) -> "dict | None":
        """
        Extrai fichas N2 por zona PIL usando motor_reverso_pil_zones.
        Retorna {'ABCD': dict, 'CIMA': dict, 'GRADES': dict} ou None se falhar.
        """
        try:
            import sys as _sys
            scripts_dir = str(Path(__file__).parent.parent.parent.parent / "scripts")
            if scripts_dir not in _sys.path:
                _sys.path.insert(0, scripts_dir)
            from motor_reverso_pil_zones import extrair_fichas_pil_zones

            recorte = self._find_disk_dxf_for_er(obra, "PIL", item_id)
            if recorte is None:
                return None

            obra_root = DADOS_OBRAS_ROOT / obra
            pavimento = er_ficha.get("pavimento")
            return extrair_fichas_pil_zones(str(recorte), item_id,
                                            str(obra_root), pavimento)
        except Exception as _e:
            print(f"[CE] _get_pil_zone_fichas error: {_e}")
            return None

    def _find_n4_dxf_strict(self, obra_dir: Path, classe: str, item_id: str) -> "Path | None":
        """Procura APENAS em Fase-6/n4/ — sem fallback para N3."""
        prefixes = {"PL": "PL_preview_", "LV": "LV_preview_",
                    "FV": "FV_preview_", "LJ": "LJ_preview_"}
        pfx = prefixes.get(classe, f"{classe}_preview_")
        n4_dir = obra_dir / "Fase-6_Execucao_CAD" / "n4"
        base_id = item_id.split('_')[0] if '_' in item_id else item_id
        # LV: gerar_lv_n4_fichas.py grava com sufixo _A (ex: LV_preview_V301_A.dxf)
        cands = [f"{item_id}_A", f"{base_id}_A", item_id, base_id] if classe == 'LV' \
                else [item_id, base_id]
        for cand in cands:
            p = n4_dir / f"{pfx}{cand}.dxf"
            if p.exists():
                return p
        return None

    def _lv_n4_zone_bboxes(self, er_ficha: dict) -> tuple:
        """Bboxes de visualizacao LV N4: corte com zoom finito e lateral separada."""
        er_ficha = er_ficha or {}
        b_cm = float(er_ficha.get('b_cm', er_ficha.get('b_geom', 19)) or 19)
        sect_total = max(190, int(b_cm) + 178, 1800)
        section_views = er_ficha.get('section_views') or []

        y_section = -150.0
        x_points: list[float] = []
        y_points: list[float] = []
        for sv in section_views:
            try:
                h_sec = float(
                    sv.get('h_section', sv.get('h_section_cm', 0)) or 0
                )
            except Exception:
                h_sec = 0.0
            h_sec = max(h_sec, 55.0)
            y_center = y_section + h_sec / 2.0
            primitives = (
                (sv.get('raw') or {}).get('visual_primitives')
                or sv.get('visual_primitives')
                or []
            )

            def _add_point(pt):
                try:
                    x_points.append(95.0 + float(pt[0]))
                    y_points.append(y_center + float(pt[1]))
                except Exception:
                    pass

            for prim in primitives:
                kind = prim.get('kind')
                if kind in ('line', 'polyline'):
                    for pt in prim.get('points') or []:
                        _add_point(pt)
                elif kind == 'text':
                    _add_point(prim.get('insert') or [0.0, 0.0])
                elif kind == 'hatch':
                    for path in prim.get('paths') or []:
                        for pt in path:
                            _add_point(pt)

            if not primitives:
                x_points.extend([25.0, min(sect_total - 25.0, 165.0)])
                y_points.extend([y_center - h_sec / 2.0 - 45.0,
                                 y_center + h_sec / 2.0 + 45.0])
            y_section -= max(h_sec + 90.0, 180.0)

        if x_points and y_points:
            vc_bbox = (
                max(-80.0, min(x_points) - 35.0),
                min(y_points) - 35.0,
                min(float(sect_total - 15), max(x_points) + 35.0),
                max(y_points) + 35.0,
            )
            y_min_section = vc_bbox[1]
            y_max_section = vc_bbox[3]
        else:
            vc_bbox = (-60.0, -250.0, float(sect_total - 15), 80.0)
            y_min_section, y_max_section = vc_bbox[1], vc_bbox[3]

        lat_bbox = (sect_total - 5, y_min_section - 120, 99999, y_max_section + 120)
        return vc_bbox, lat_bbox

    def _start_n4_lv_generation(self, item_id: str, er_ficha: dict,
                                obra_dir: Path, col):
        """Gera N4 LV via gerar_lv_n4_fichas.py (bypass DB — LV não está no DB)."""
        if self._process is not None:
            if self._process.state() == QProcess.Running:
                try:
                    self._process.finished.disconnect()
                except (RuntimeError, TypeError):
                    pass
                self._process.kill()
                self._process.waitForFinished(500)
            try:
                self._process.deleteLater()
            except RuntimeError:
                pass
            self._process = None

        import re as _re, tempfile as _tempfile, uuid as _uuid
        # LV: strip sufixo virtual Para/Passa antes de extrair base (sem face)
        _clean_id = _re.sub(r'_(Para|Passa)$', '', item_id, flags=_re.IGNORECASE)
        base_id = _re.sub(r'[_\.]([AB])$', '', _clean_id, flags=_re.IGNORECASE)
        n4_script = SCRIPTS_DIR / "arete" / "gerar_lv_n4_fichas.py"
        out_dir    = obra_dir / "Fase-6_Execucao_CAD" / "n4"
        out_dir.mkdir(parents=True, exist_ok=True)
        entry_path = Path(_tempfile.gettempdir()) / (
            f"ce_lv_{base_id}_{_uuid.uuid4().hex}.json")
        entry_path.write_text(
            json.dumps(er_ficha, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_proc_out)

        def _on_done(code, _sig,
                     _base_id=base_id, _item_id=item_id,
                     _out_dir=out_dir, _col=col, _er_ficha=er_ficha,
                     _entry_path=entry_path):
            try:
                # DXF gerado: LV_preview_{base_id}_A.dxf
                dxf_path = _out_dir / f"LV_preview_{_base_id}_A.dxf"
                if code == 0 and dxf_path.exists():
                    vc_bbox, lat_bbox = self._lv_n4_zone_bboxes(_er_ficha or {})
                    lv_zones = {
                        'Visão Corte': (str(dxf_path), vc_bbox),
                        'Lateral A-B': (str(dxf_path), lat_bbox),
                    }
                    _col.switch_to_lv_zones(lv_zones, _er_ficha or {})
                    _col.pipeline.set_step(2, 'ok', dxf_path.name[:25])
                    self._configure_level_attention("N4", "LV", _item_id)
                    self._configure_level_attention("N3", "LV", _item_id)
                    self.nav_sidebar.set_status(f"✅ N4 LV gerado — {_item_id}", Colors.ACCENT_SUCCESS)
                    self._refresh_n3_compare_n4_if_active("LV", _item_id)
                else:
                    _col.pipeline.set_step(2, 'error', f'código {code}')
                    self.nav_sidebar.set_status(f"❌ N4 LV falhou — {_item_id}", Colors.ACCENT_ERROR)
            except Exception as _e:
                print(f"[CE] _on_done LV n4: {_e}")
            finally:
                try:
                    _entry_path.unlink(missing_ok=True)
                except Exception:
                    pass
                self.nav_sidebar._enable_item_btns()

        self._process.finished.connect(_on_done)
        self._process.start(
            sys.executable,
            [
                str(n4_script), base_id,
                "--out", str(out_dir),
                "--obra", str(obra_dir),
                "--entry-json", str(entry_path),
            ],
        )

    def _start_n4_generation(self, classe: str, item_id: str, er_ficha: dict,
                              obra_dir: Path, script: Path, col):
        """Option B: escreve ficha ER como temp JSON em Fase-4, roda script robô,
        move output para Fase-6/n4/, carrega no viewer N4."""
        # Cancela processo anterior se ainda rodando — desconecta sinais para evitar
        # que o _on_done antigo chame col.load_content depois de item/classe mudarem.
        # CRÍTICO: não destruir o QProcess com GC enquanto ainda roda (crash C-level).
        if self._process is not None:
            if self._process.state() == QProcess.Running:
                try:
                    self._process.finished.disconnect()
                except (RuntimeError, TypeError):
                    pass
                self._process.kill()
                self._process.waitForFinished(500)
            try:
                self._process.deleteLater()
            except RuntimeError:
                pass
            self._process = None

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
        ficha_clean = {
            k: v for k, v in er_ficha.items()
            if not k.startswith('_') or (
                classe == "LJ"
                and k in {"_hlaz", "_stog_pose"}
            )
        }
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
                     _item_id=item_id, _classe=classe, _col=col,
                     _er_ficha=er_ficha):
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
                    if _classe == 'LV':
                        vc_bbox, lat_bbox = self._lv_n4_zone_bboxes(_er_ficha or {})
                        lv_zones = {
                            'Visão Corte': (str(canon), vc_bbox),
                            'Lateral A-B': (str(canon), lat_bbox),
                        }
                        _col.switch_to_lv_zones(lv_zones, _er_ficha or {})
                    else:
                        n4_bbox = self.tri_level._get_n2_bbox_for(_item_id, _classe) if _classe == "LJ" else None
                        _col.load_content(str(canon), n4_bbox)
                    _col.pipeline.set_step(2, 'ok', canon.name[:25])
                    self._configure_level_attention("N4", _classe, _item_id)
                    self._configure_level_attention("N3", _classe, _item_id)
                    self.nav_sidebar.set_status(f"✅ N4 gerado — {_item_id}", Colors.ACCENT_SUCCESS)
                    self._refresh_n3_compare_n4_if_active(_classe, _item_id)
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
        obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
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
            n1_bbox = self.tri_level._get_n1_bbox_for(item_id, classe)
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

        obra = (self.fase8_panel.cmb_obra.currentData() or self.fase8_panel.cmb_obra.currentText())
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
