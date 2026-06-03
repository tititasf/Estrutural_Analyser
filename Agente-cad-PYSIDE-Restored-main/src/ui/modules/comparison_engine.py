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

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel,
    QPushButton, QComboBox, QCheckBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QScrollArea, QSplitter, QGroupBox, QTextEdit, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QSizePolicy,
)
from PySide6.QtCore import Qt, QProcess, Signal, QRect, QRectF, QPointF, QThread, QObject
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

NIVEL_DEFS = [
    # (id,  titulo,           bg_color,   accent,     descricao,                                      mode)
    ("N1", "Estrutura Real",  "#1b3a6b",  "#4a9eff",  "DXF Estrutural · Fase 1\nPosição e dimensões da viga", 'dxf'),
    ("N2", "STOG Real DXF",   "#1a4a2a",  "#4acf7a",  "Eng. Reversa · Fase 1\nForms, seções e sarrafos STOG", 'dxf'),
    ("N3", "Robot Gerado",    "#4a2a1a",  "#cf8a4a",  "Robot LV · Fase 6\nPNG gerado automaticamente",        'png'),
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


def _entity_color(entity, doc=None) -> QColor:
    """Resolve a QColor for a DXF entity (true color → ACI → layer color)."""
    try:
        tc = entity.rgb
        if tc is not None:
            return QColor(int(tc[0]), int(tc[1]), int(tc[2]))
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
        return QColor(_ACI.get(aci, '#cccccc'))
    except Exception:
        return QColor('#cccccc')


def _ep_to_qpath(ep) -> QPainterPath:
    """Convert an ezdxf Path to QPainterPath (keeps DXF XY coords, Z ignored)."""
    qp = QPainterPath()
    qp.moveTo(ep.start.x, ep.start.y)
    for cmd in ep:
        ct = cmd.type
        end = cmd.end
        if ct.value == 4:   # MOVE_TO
            qp.moveTo(end.x, end.y)
        elif ct.value == 1:  # LINE_TO
            qp.lineTo(end.x, end.y)
        elif ct.value == 2:  # CURVE3_TO
            ctrl = cmd.ctrl
            qp.quadTo(ctrl.x, ctrl.y, end.x, end.y)
        elif ct.value == 3:  # CURVE4_TO
            c1, c2 = cmd.ctrl1, cmd.ctrl2
            qp.cubicTo(c1.x, c1.y, c2.x, c2.y, end.x, end.y)
    return qp


# Caps por tipo — geometria (paths) sem limite global para integridade visual
# Fills/texto/inserts são os pesados em memória → limitados
_MAX_PATH_OPS   = 3000  # safety net para paths/lines (3000 é muito difícil de atingir)
_MAX_FILL_OPS   = 80    # HATCH fills — complexos, limitados
_MAX_TEXT_OPS   = 120   # textos
_MAX_INSERT_OPS = 60    # blocos expandidos


def _collect_dxf_ops(dxf_path: Path, bbox: tuple) -> list:
    """
    Carrega um DXF e extrai draw-ops dentro da bbox.
    Retorna [(op_type, QColor, data), ...] onde op_type ∈ {'path','fill','text'}.
    Geometria (paths) é capturada integralmente até _MAX_PATH_OPS.
    Fills/texto/inserts têm caps menores (mais pesados em memória).
    Roda em thread separado — sem dependências PySide.
    """
    import ezdxf
    from ezdxf import path as ezpath

    ops: list = []
    path_count  = 0
    fill_count  = 0
    text_count  = 0
    insert_count = 0

    x0, y0, x1, y1 = bbox
    bw = x1 - x0; bh = y1 - y0
    pad = max(bw, bh) * 0.08
    bx0, by0, bx1, by1 = x0-pad, y0-pad, x1+pad, y1+pad

    def in_range(x, y):
        return bx0 <= x <= bx1 and by0 <= y <= by1

    def try_path(entity):
        try:
            ep = ezpath.make_path(entity)
            pts = list(ep.control_vertices())
            if not pts:
                return None
            step = max(1, len(pts) // 6)
            if not any(in_range(p.x, p.y) for p in pts[::step]):
                return None
            qp = _ep_to_qpath(ep)
            return qp if not qp.isEmpty() else None
        except Exception:
            return None

    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
    except Exception:
        return ops

    for entity in msp:
        t = entity.dxftype()
        color = _entity_color(entity, doc)

        try:
            if t in ('LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE'):
                # Geometria principal — sem cap exceto safety net
                if path_count >= _MAX_PATH_OPS:
                    continue
                qp = try_path(entity)
                if qp:
                    ops.append(('path', color, qp))
                    path_count += 1

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
                        qp = _ep_to_qpath(sub)
                        if not qp.isEmpty():
                            ops.append(('fill', color, qp))
                            fill_count += 1
                except Exception:
                    pass

            elif t in ('TEXT', 'MTEXT'):
                if text_count >= _MAX_TEXT_OPS:
                    continue
                try:
                    if t == 'TEXT':
                        ins = entity.dxf.insert
                        txt = entity.dxf.text or ''
                        h   = entity.dxf.get('height', 10)
                    else:
                        ins = entity.dxf.insert
                        txt = entity.plain_text() if hasattr(entity, 'plain_text') else ''
                        h   = entity.dxf.get('char_height', 10)
                    txt = txt.strip()
                    if txt and in_range(ins.x, ins.y):
                        ops.append(('text', color, (ins.x, ins.y, txt[:30], h)))
                        text_count += 1
                except Exception:
                    pass

            elif t == 'INSERT':
                if insert_count >= _MAX_INSERT_OPS:
                    continue
                try:
                    block_name = entity.dxf.name
                    blk = doc.blocks.get(block_name)
                    ins_x = entity.dxf.insert.x
                    ins_y = entity.dxf.insert.y
                    if not in_range(ins_x, ins_y):
                        continue
                    sx = entity.dxf.get('xscale', 1.0)
                    sy = entity.dxf.get('yscale', 1.0)
                    import math
                    rot = math.radians(entity.dxf.get('rotation', 0.0))
                    cos_r, sin_r = math.cos(rot), math.sin(rot)
                    blk_added = 0
                    for blk_ent in blk:
                        if blk_added >= 10:
                            break
                        if blk_ent.dxftype() not in ('LINE', 'LWPOLYLINE', 'CIRCLE', 'ARC'):
                            continue
                        ep = try_path(blk_ent)
                        if ep is None:
                            continue
                        t_qp = QPainterPath()
                        for i in range(ep.elementCount()):
                            el = ep.elementAt(i)
                            lx = el.x * sx * cos_r - el.y * sy * sin_r + ins_x
                            ly = el.x * sx * sin_r + el.y * sy * cos_r + ins_y
                            if el.type == 0:
                                t_qp.moveTo(lx, ly)
                            elif el.type == 1:
                                t_qp.lineTo(lx, ly)
                        if not t_qp.isEmpty():
                            blk_color = _entity_color(blk_ent, doc)
                            ops.append(('path', blk_color, t_qp))
                            blk_added += 1
                    insert_count += 1
                except Exception:
                    pass

        except Exception:
            pass

    return ops


class DXFLoadWorker(QThread):
    """Carrega e converte DXF em draw-ops num thread separado."""

    loaded = Signal(list)   # emite ops list
    failed = Signal(str)    # emite mensagem de erro

    def __init__(self, dxf_path: Path, bbox: tuple):
        super().__init__()
        self._dxf_path = dxf_path
        self._bbox     = bbox

    def run(self):
        try:
            ops = _collect_dxf_ops(self._dxf_path, self._bbox)
            self.loaded.emit(ops)
        except Exception as e:
            self.failed.emit(str(e))


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
        self._scale     = 1.0
        self._offset    = QPointF(0.0, 0.0)
        self._drag_start  = None
        self._drag_origin = None
        self._status_text = "— sem DXF —"
        self._bg     = bg
        self._loading = False
        self._worker: DXFLoadWorker | None = None
        self._dxf_bbox = None   # (x0, y0, x1, y1)

        self.setMinimumSize(200, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

    # ── Public API ──────────────────────────────────────────────────

    def load_dxf(self, dxf_path, bbox):
        """Inicia carregamento DXF em thread separado. Cancela worker anterior."""
        if dxf_path is None or bbox is None:
            self.clear_image("— DXF não disponível —")
            return

        # Cancelar worker anterior antes de iniciar novo (evita 2 leituras simultâneas)
        if self._worker is not None:
            # Desconectar sinais para ignorar resultado do worker anterior
            try:
                self._worker.loaded.disconnect()
                self._worker.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
            # quit() sinaliza encerramento; o thread termina sozinho sem bloquear main
            if self._worker.isRunning():
                self._worker.quit()
            self._worker = None

        self._ops = []
        self._dxf_bbox = bbox
        self._loading  = True
        self._status_text = "Carregando DXF..."
        self.update()

        self._worker = DXFLoadWorker(Path(dxf_path), bbox)
        self._worker.loaded.connect(self._on_loaded)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def clear_image(self, msg: str = "— sem DXF —"):
        self._ops = []
        self._dxf_bbox = None
        self._loading  = False
        self._status_text = msg
        self.update()

    # ── Slots ────────────────────────────────────────────────────────

    def _on_loaded(self, ops: list):
        self._ops     = ops
        self._loading = False
        self._status_text = f"{len(ops)} entidades" if ops else "— vazio —"
        self._fit()
        self.update()
        self.ready.emit()

    def _on_failed(self, msg: str):
        self._loading = False
        self._status_text = f"Erro: {msg[:60]}"
        self.update()
        self.ready.emit()

    # ── Fit ──────────────────────────────────────────────────────────

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

    # ── Paint — puro vetorial com viewport culling ───────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(self._bg))

        if not self._ops:
            p.setPen(QColor(Colors.TEXT_DIM))
            p.setFont(QFont("Arial", 11))
            p.drawText(self.rect(), Qt.AlignCenter, self._status_text)
            p.end()
            return

        ox = self._offset.x()
        oy = self._offset.y()
        s  = self._scale
        ww = float(self.width())
        wh = float(self.height())

        # Rect visível em coordenadas DXF (com Y-flip) para viewport culling
        # widget x → dxf_x = (wx - ox) / s
        # widget y → dxf_y = (oy - wy) / s  (Y-flip)
        vis_x0 = (0.0 - ox) / s
        vis_x1 = (ww  - ox) / s
        vis_y0 = (oy - wh) / s
        vis_y1 = oy / s
        vis = QRectF(vis_x0, vis_y0, vis_x1 - vis_x0, vis_y1 - vis_y0)

        # Aplica transform DXF→widget com Y-flip
        p.translate(ox, oy)
        p.scale(s, -s)

        drawn = 0
        for op in self._ops:
            op_type = op[0]
            color   = op[1]
            data    = op[2]

            if op_type == 'path':
                # Viewport culling — pula entidades fora da área visível
                if not vis.intersects(data.boundingRect()):
                    continue
                pen = QPen(color, 0)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawPath(data)
                drawn += 1

            elif op_type == 'fill':
                if not vis.intersects(data.boundingRect()):
                    continue
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
                p.drawPath(data)
                drawn += 1

            elif op_type == 'text':
                dx, dy, txt, h = data
                if not vis.contains(QPointF(dx, dy)):
                    continue
                # Texto em coordenadas widget (sem flip)
                wx = ox + dx * s
                wy = oy - dy * s
                p.resetTransform()
                px_h = max(6, min(int(h * s * 0.75), 48))
                p.setFont(QFont("Arial", px_h))
                p.setPen(color)
                p.drawText(QPointF(wx, wy), txt)
                p.translate(ox, oy)
                p.scale(s, -s)
                drawn += 1

        p.resetTransform()

        # Badge zoom + entidades desenhadas vs total
        p.setFont(QFont("Arial", 9))
        p.setPen(QColor(Colors.TEXT_DIM))
        p.drawText(self.rect().adjusted(0, 0, -6, -4),
                   Qt.AlignRight | Qt.AlignBottom,
                   f"{s*100:.0f}%  {drawn}/{len(self._ops)}")
        p.end()

    # ── Zoom centrado no cursor (com Y-flip) ─────────────────────────

    def wheelEvent(self, event):
        if not self._ops:
            return
        factor = 1.18 if event.angleDelta().y() > 0 else 1.0 / 1.18
        cur = event.position()
        ox, oy = self._offset.x(), self._offset.y()
        s = self._scale

        dxf_x = (cur.x() - ox) / s
        dxf_y = (oy - cur.y()) / s   # Y-flip invertido

        new_s = max(0.001, min(s * factor, 2000.0))

        new_ox = cur.x() - dxf_x * new_s
        new_oy = cur.y() + dxf_y * new_s   # Y-flip

        self._scale  = new_s
        self._offset = QPointF(new_ox, new_oy)
        self.update()
        event.accept()

    # ── Pan ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._ops:
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
        self._fit()
        self.update()

    def resizeEvent(self, event):
        if self._ops:
            self._fit()
        super().resizeEvent(event)


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
        self.setFixedWidth(320)
        self.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_SECONDARY};
                border-left: 1px solid {Colors.ACCENT_BLUE};
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
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # ── Título ──────────────────────────────
        lbl = QLabel("🔬 <b>Fase-8</b>: Validação Visual & Certificação")
        lbl.setStyleSheet(f"color: {Colors.ACCENT_PRIMARY}; font-size: {Fonts.SIZE_LG}; padding-bottom: 4px;")
        outer.addWidget(lbl)

        # ── Seleção Obra / Pav ───────────────────
        grp_sel = QGroupBox("Obra & Tipo")
        sel_lay = QVBoxLayout(grp_sel)
        sel_lay.setSpacing(5)

        sel_lay.addWidget(QLabel("Obra:"))
        self.cmb_obra = QComboBox()
        self.cmb_obra.currentTextChanged.connect(self._on_obra_changed)
        sel_lay.addWidget(self.cmb_obra)

        sel_lay.addWidget(QLabel("Pavimento:"))
        self.cmb_pav = QComboBox()
        sel_lay.addWidget(self.cmb_pav)

        sel_lay.addWidget(QLabel("Tipos:"))
        tipos_row = QHBoxLayout()
        self._chk_tipos = {}
        for t in TIPOS:
            cb = QCheckBox(t)
            cb.setChecked(True)
            self._chk_tipos[t] = cb
            tipos_row.addWidget(cb)
        sel_lay.addLayout(tipos_row)

        self.chk_sem_api = QCheckBox("Só estrutural (sem API)")
        self.chk_sem_api.setChecked(True)   # padrão: sem API (mais rápido, evita timeout)
        sel_lay.addWidget(self.chk_sem_api)

        outer.addWidget(grp_sel)

        # ── Botão Validar ────────────────────────
        self.btn_validate = QPushButton("▶ Validar")
        self.btn_validate.clicked.connect(self._on_validate_clicked)
        outer.addWidget(self.btn_validate)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        outer.addWidget(self.progress)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM};")
        outer.addWidget(self.lbl_status)

        # ── Scores ──────────────────────────────
        grp_scores = QGroupBox("Scores")
        sc_lay = QVBoxLayout(grp_scores)
        sc_lay.setSpacing(4)

        score_grid = QHBoxLayout()
        self._score_labels = {}
        for t in TIPOS:
            col = QVBoxLayout()
            col.addWidget(QLabel(t, alignment=Qt.AlignCenter))
            sl = ScoreLabel("—")
            sl.setAlignment(Qt.AlignCenter)
            sl.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 16px; font-weight: bold;")
            self._score_labels[t] = sl
            col.addWidget(sl)
            score_grid.addLayout(col)
        sc_lay.addLayout(score_grid)

        row_avg = QHBoxLayout()
        row_avg.addWidget(QLabel("Média:"))
        self.lbl_avg = ScoreLabel("—")
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

        # ── Histórico + Tendência em abas ────────
        tabs_hist = QTabWidget()
        tabs_hist.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {Colors.BORDER_DEFAULT}; background: {Colors.BG_PANEL}; }}
            QTabBar::tab {{ background: {Colors.BG_PANEL}; color: {Colors.TEXT_SECONDARY}; padding: 4px 8px; font-size: {Fonts.SIZE_SM}; }}
            QTabBar::tab:selected {{ background: {Colors.BG_CARD}; color: {Colors.TEXT_PRIMARY}; }}
        """)

        # Tab Histórico
        hist_tab = QWidget()
        hist_lay = QVBoxLayout(hist_tab)
        hist_lay.setContentsMargins(4, 4, 4, 4)
        hist_lay.setSpacing(4)

        self.tbl_history = QTableWidget(0, 5)
        self.tbl_history.setHorizontalHeaderLabels(["Obra", "PL", "LV", "FV", "LJ"])
        self.tbl_history.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 5):
            self.tbl_history.setColumnWidth(col, 45)
        self.tbl_history.setMaximumHeight(150)
        hist_lay.addWidget(self.tbl_history)

        btn_reload = QPushButton("🔄 Atualizar")
        btn_reload.setStyleSheet(f"font-size: {Fonts.SIZE_SM}; padding: 3px;")
        btn_reload.clicked.connect(self.load_history)
        hist_lay.addWidget(btn_reload)
        tabs_hist.addTab(hist_tab, "Histórico")

        # Tab Tendência — CAD-UI-2.2
        trend_tab = QWidget()
        trend_lay = QVBoxLayout(trend_tab)
        trend_lay.setContentsMargins(4, 4, 4, 4)
        trend_lay.setSpacing(4)

        trend_lay.addWidget(QLabel("Evolução de scores (últimas 20 validações):"))
        self._sparkline = ScoreSparkline()
        trend_lay.addWidget(self._sparkline)

        legend_row = QHBoxLayout()
        for tipo, color in [("PL","#7ab3e0"),("LV",Colors.ACCENT_SUCCESS),("FV",Colors.ACCENT_WARNING),("LJ","#e91e63")]:
            dot = QLabel(f"● {tipo}")
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            legend_row.addWidget(dot)
        legend_row.addStretch()
        trend_lay.addLayout(legend_row)

        btn_load_trend = QPushButton("🔄 Carregar tendência")
        btn_load_trend.setStyleSheet(f"font-size: {Fonts.SIZE_SM}; padding: 3px;")
        btn_load_trend.clicked.connect(self._load_trend)
        trend_lay.addWidget(btn_load_trend)

        self._lbl_trend_info = QLabel("Selecione uma obra e clique em Carregar.")
        self._lbl_trend_info.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: {Fonts.SIZE_SM};")
        trend_lay.addWidget(self._lbl_trend_info)
        tabs_hist.addTab(trend_tab, "Tendência")

        # ── Tab Comparação tri-fonte (CAD-10.5) ──────────────────────────────
        self._comp_tab_widget = self._build_comparacao_tab()
        tabs_hist.addTab(self._comp_tab_widget, "Comparação")
        self._tabs_hist = tabs_hist  # referência para scroll

        outer.addWidget(tabs_hist)
        outer.addStretch()

        # Log
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMaximumHeight(100)
        self.log_box.setStyleSheet(
            f"background: {Colors.BG_DEEP}; color: {Colors.TEXT_SECONDARY}; font-size: {Fonts.SIZE_SM};"
            f" font-family: monospace; border: 1px solid {Colors.BORDER_DEFAULT};"
        )
        outer.addWidget(self.log_box)

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

    def _on_obra_changed(self, obra_name: str):
        """Atualiza combo de pavimentos ao trocar de obra."""
        self.cmb_pav.clear()
        if not obra_name:
            return
        disc_path = DADOS_OBRAS_ROOT / "dxf_discovery.json"
        if disc_path.exists():
            disc = json.loads(disc_path.read_text(encoding='utf-8', errors='replace'))
            pavs = sorted(disc.get(obra_name, {}).keys())
            for p in pavs:
                self.cmb_pav.addItem(p)
        # Fallback: Fase-1
        if self.cmb_pav.count() == 0:
            fase1 = DADOS_OBRAS_ROOT / obra_name / "Fase-1_Ingestao"
            if fase1.exists():
                self.cmb_pav.addItem("1PV")

        # Carregar scores existentes
        self._load_scores_for_obra(obra_name)

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

    # ─────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────

    def _on_validate_clicked(self):
        obra = self.cmb_obra.currentText()
        pav  = self.cmb_pav.currentText()
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

    # ─────────────────────────────────────────────
    # Certification
    # ─────────────────────────────────────────────

    def _on_certify(self):
        obra = self.cmb_obra.currentText()
        pav  = self.cmb_pav.currentText()
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
            "background: rgba(0,0,0,0.3); border-radius: 3px;"
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
                gridline-color: rgba(255,255,255,0.07);
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
                c_fg = '#4caf50' if c_pct >= 75 else ('#ffc107' if c_pct >= 50 else '#f44336')
                m_fg = '#4caf50' if m_pct >= 75 else ('#ffc107' if m_pct >= 50 else '#f44336')
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


class LevelColumn(QFrame):
    """Coluna de nível (N1/N2/N3): badge + header, viewer, ficha."""

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
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # ── Header ──────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setFixedHeight(72)
        hdr.setStyleSheet(f"background: {bg_color}; border-radius: 4px;")
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(10, 7, 10, 7)
        hdr_lay.setSpacing(3)

        badge_row = QHBoxLayout()
        badge = QLabel(nivel_id)
        badge.setFixedWidth(36)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background: {accent}; color: #000; font-weight: bold;"
            "font-size: 13px; padding: 1px 6px; border-radius: 3px;"
        )
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            f"color: {accent}; font-weight: bold; font-size: 13px; background: transparent;"
        )
        badge_row.addWidget(badge)
        badge_row.addSpacing(6)
        badge_row.addWidget(lbl_titulo)
        badge_row.addStretch()
        hdr_lay.addLayout(badge_row)

        lbl_desc = QLabel(descricao)
        lbl_desc.setStyleSheet(
            "color: rgba(255,255,255,0.65); font-size: 10px; background: transparent;"
        )
        lbl_desc.setWordWrap(True)
        hdr_lay.addWidget(lbl_desc)
        lay.addWidget(hdr)

        # ── Viewer (DXF vetorial ou PNG raster) ──────────────────────
        border_style = f"border: 1px solid {Colors.BORDER_DEFAULT}; border-radius: 2px;"
        if mode == 'dxf':
            self.img_widget: DXFVectorView | ZoomableImageLabel = DXFVectorView(bg=Colors.BG_DEEP)
        else:
            self.img_widget = ZoomableImageLabel(bg=Colors.BG_DEEP)
        self.img_widget.setMinimumHeight(260)
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
            f"color: {accent}; font-size: 11px; font-weight: bold; padding-top: 4px;"
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
    """Sidebar esquerda: classes/itens + botão processar."""

    item_selected    = Signal(str, str)   # classe, item_id
    process_requested = Signal(str, str)  # classe, item_id

    def __init__(self):
        super().__init__()
        self.setFixedWidth(215)
        self.setStyleSheet(f"""
            QFrame {{
                background: {Colors.BG_PANEL};
                border-right: 1px solid {Colors.BORDER_DEFAULT};
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 8, 6, 8)
        lay.setSpacing(6)

        title = QLabel("Classes / Itens")
        title.setStyleSheet(
            f"color: {Colors.ACCENT_PRIMARY}; font-weight: bold; font-size: 13px;"
            "padding-bottom: 4px; background: transparent;"
        )
        lay.addWidget(title)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background: {Colors.BG_DEEP}; color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER_DEFAULT}; font-size: 12px;
            }}
            QTreeWidget::item {{ padding: 3px 2px; }}
            QTreeWidget::item:selected {{
                background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT};
            }}
            QTreeWidget::item:hover {{ background: {Colors.BG_CARD}; }}
        """)
        self.tree.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self.tree, 1)

        self._populate_tree()

        # ── Botões ───────────────────────────────────────────────────
        btn_style = f"""
            QPushButton {{
                background: {Colors.ACCENT_BLUE}; color: {Colors.TEXT_BRIGHT};
                border-radius: 4px; padding: 6px 10px;
                font-weight: bold; font-size: 12px;
            }}
            QPushButton:hover {{ background: {Colors.ACCENT_BLUE_HOVER}; }}
            QPushButton:disabled {{
                background: {Colors.BORDER_DEFAULT}; color: {Colors.TEXT_DIM};
            }}
        """

        self.btn_process = QPushButton("▶ Processar Item")
        self.btn_process.setEnabled(False)
        self.btn_process.setStyleSheet(btn_style)
        self.btn_process.clicked.connect(self._on_process_clicked)
        lay.addWidget(self.btn_process)

        self.btn_process_all = QPushButton("⚡ Processar Todas")
        self.btn_process_all.setStyleSheet(
            btn_style.replace(Colors.ACCENT_BLUE, "#4a2a7a")
                     .replace(Colors.ACCENT_BLUE_HOVER, "#6a3a9a")
        )
        self.btn_process_all.clicked.connect(self._on_process_all_clicked)
        lay.addWidget(self.btn_process_all)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(
            f"color: {Colors.TEXT_DIM}; font-size: 10px; background: transparent;"
        )
        self.lbl_status.setWordWrap(True)
        lay.addWidget(self.lbl_status)

        self._selected_classe = ""
        self._selected_item   = ""

    def _populate_tree(self):
        """Popula árvore com classes e itens; mostra quais já têm crops."""
        # LV — Laterais de Vigas
        lv_root = QTreeWidgetItem(self.tree, ["Laterais de Vigas (LV)"])
        lv_root.setData(0, Qt.UserRole, ("LV", None))
        lv_root.setExpanded(True)
        font_bold = QFont()
        font_bold.setBold(True)
        lv_root.setFont(0, font_bold)

        for vn in VIGAS_LV_LIST:
            n1_ok = (CROPS_DIR_3N / f"n1_{vn}.png").exists()
            n2_ok = (CROPS_DIR_3N / f"n2_{vn}.png").exists()
            n3_ok = (LV_RENDERS_DIR / f"{vn}_gerado.png").exists()
            avail = [n for n, ok in [("N1", n1_ok), ("N2", n2_ok), ("N3", n3_ok)] if ok]
            label = f"{vn}  [{'/'.join(avail)}]" if avail else vn
            child = QTreeWidgetItem(lv_root, [label])
            child.setData(0, Qt.UserRole, ("LV", vn))
            if avail:
                child.setForeground(0, QBrush(QColor(Colors.ACCENT_SUCCESS)))

        # Placeholder futuras classes
        for cls_label in ["Pilares (PL)", "Vigas Fundo (FV)", "Lajes (LJ)"]:
            root = QTreeWidgetItem(self.tree, [cls_label])
            root.setForeground(0, QBrush(QColor(Colors.TEXT_DIM)))
            root.setData(0, Qt.UserRole, (cls_label[:2], None))
            ph = QTreeWidgetItem(root, ["— em breve —"])
            ph.setForeground(0, QBrush(QColor(Colors.TEXT_DIM)))
            ph.setFlags(ph.flags() & ~Qt.ItemIsSelectable)

    def _on_item_clicked(self, item, col):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        classe, item_id = data
        if item_id is None:
            return
        self._selected_classe = classe
        self._selected_item   = item_id
        self.btn_process.setEnabled(True)
        self.item_selected.emit(classe, item_id)

    def _on_process_clicked(self):
        if self._selected_item:
            self.btn_process.setEnabled(False)
            self.btn_process_all.setEnabled(False)
            self.process_requested.emit(self._selected_classe, self._selected_item)

    def _on_process_all_clicked(self):
        self.btn_process.setEnabled(False)
        self.btn_process_all.setEnabled(False)
        self.process_requested.emit("ALL", "ALL")

    def set_status(self, text: str, color: str = ""):
        self.lbl_status.setText(text)
        c = color or Colors.TEXT_DIM
        self.lbl_status.setStyleSheet(
            f"color: {c}; font-size: 10px; background: transparent;"
        )

    def refresh_tree(self):
        """Re-escaneia crops e atualiza indicadores verdes."""
        root_lv = self.tree.topLevelItem(0)
        if not root_lv:
            return
        for i in range(root_lv.childCount()):
            child = root_lv.child(i)
            data  = child.data(0, Qt.UserRole)
            if not data:
                continue
            _, vn = data
            if not vn:
                continue
            n1_ok = (CROPS_DIR_3N / f"n1_{vn}.png").exists()
            n2_ok = (CROPS_DIR_3N / f"n2_{vn}.png").exists()
            n3_ok = (LV_RENDERS_DIR / f"{vn}_gerado.png").exists()
            avail = [n for n, ok in [("N1", n1_ok), ("N2", n2_ok), ("N3", n3_ok)] if ok]
            child.setText(0, f"{vn}  [{'/'.join(avail)}]" if avail else vn)
            child.setForeground(
                0, QBrush(QColor(Colors.ACCENT_SUCCESS if avail else Colors.TEXT_PRIMARY))
            )


class TriLevelArea(QWidget):
    """Área central: 3 colunas com scroll horizontal + fichas de dados."""

    def __init__(self):
        super().__init__()
        self._load_data()

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
        lbl_t = QLabel("Comparison Engine — 3 Níveis")
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

        # ── Scroll com 3 colunas ─────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: {Colors.BG_SECONDARY}; }}
            QScrollBar:horizontal {{
                background: {Colors.BG_DEEP}; height: 10px;
            }}
            QScrollBar::handle:horizontal {{
                background: {Colors.BORDER_DEFAULT}; border-radius: 5px; min-width: 30px;
            }}
        """)

        cols_widget = QWidget()
        cols_widget.setStyleSheet(f"background: {Colors.BG_SECONDARY};")
        cols_lay = QHBoxLayout(cols_widget)
        cols_lay.setContentsMargins(0, 0, 0, 0)
        cols_lay.setSpacing(0)

        self._columns = []
        for nivel_id, titulo, bg, accent, desc, mode in NIVEL_DEFS:
            col = LevelColumn(nivel_id, titulo, bg, accent, desc, mode)
            self._columns.append(col)
            cols_lay.addWidget(col)
        cols_lay.addStretch()

        scroll.setWidget(cols_widget)
        lay.addWidget(scroll, 1)

    # ── Carregamento de dados ────────────────────────────────────────

    def _load_data(self):
        def _j(p, default=None):
            try:
                return json.loads(Path(p).read_text(encoding='utf-8', errors='replace'))
            except Exception:
                return default if default is not None else {}

        fase3 = OBRA_TREINO_16 / "Fase-3_Interpretacao_Extracao"
        fase6 = OBRA_TREINO_16 / "Fase-6_Execucao_CAD"
        kb_lv = OBRA_TREINO_16 / "Fase-0_STOG_KB/LV"

        self._vigas_fase3  = _j(fase3 / "Vigas/vigas.json")
        self._fichas_rev   = _j(fase3 / "Vigas/fichas_reverso_VIG_ALL.json")
        self._ancoras      = _j(fase3 / "ancoras_vigas.json")
        lv2                = _j(fase6 / "granular/fichas/fichas_lv_v2.json", default=[])
        self._fichas_lv_v2 = lv2 if isinstance(lv2, list) else []

        self._kb_ents = []
        if kb_lv.exists():
            kb_files = sorted(kb_lv.glob("*.json"))
            if kb_files:
                kb_data = _j(kb_files[0])
                self._kb_ents = kb_data.get("entities", [])

        # Escanear DXF estrutural para obter coords reais das vigas
        self._est_labels: dict = {}   # {viga: (cx, cy)}  coords no DXF estrutural
        self._est_ents_raw: list = [] # [(type, x, y, layer)]
        self._scan_structural_dxf()

    def _scan_structural_dxf(self):
        """Carrega labels e entidades do DXF estrutural para bbox N1."""
        dxf_path = (OBRA_TREINO_16
                    / "Fase-1_Ingestao/Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
                    / "976-EST-PE-0004-1PV-R01_R2018_ASCII_ODA.dxf")
        if not dxf_path.exists():
            return
        try:
            import ezdxf
            doc  = ezdxf.readfile(str(dxf_path))
            msp  = doc.modelspace()
            targets = set(VIGAS_LV_LIST)
            for e in msp:
                t   = e.dxftype()
                lyr = e.dxf.layer if hasattr(e.dxf, 'layer') else ''
                ex = ey = None
                try:
                    if hasattr(e.dxf, 'insert'):
                        ex, ey = e.dxf.insert.x, e.dxf.insert.y
                    elif hasattr(e.dxf, 'start'):
                        ex = (e.dxf.start.x + e.dxf.end.x) / 2
                        ey = (e.dxf.start.y + e.dxf.end.y) / 2
                except Exception:
                    pass
                if ex is not None:
                    self._est_ents_raw.append((t, ex, ey, lyr))
                if t in ('MTEXT', 'TEXT') and ex is not None:
                    try:
                        txt = (e.plain_text() if hasattr(e, 'plain_text')
                               else e.dxf.text).strip()
                        if txt in targets and txt not in self._est_labels:
                            self._est_labels[txt] = (ex, ey)
                    except Exception:
                        pass
        except Exception:
            pass

    def load_item(self, classe: str, item_id: str):
        """
        Carrega as 3 colunas para o item selecionado.
        N1 e N2 são DXFs — loading sequencial (N1 termina → N2 inicia)
        para nunca ter dois ezdxf.readfile() simultâneos em memória.
        N3 (PNG) é carregado imediatamente.
        """
        self._lbl_item.setText(f"{classe} / {item_id}")

        if classe == "LV" and item_id in VIGAS_LV_LIST:
            vn = item_id

            n1_dxf  = (OBRA_TREINO_16
                       / "Fase-1_Ingestao/Estruturais_dos_Pavimentos_Estado_Bruto_DWG_DXF"
                       / "976-EST-PE-0004-1PV-R01_R2018_ASCII_ODA.dxf")
            n2_dxf  = (OBRA_TREINO_16
                       / "Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"
                       / "NOVA-TRISUL-VALDIR NIEMEYER-1PV-LV-R00_R2018_ASCII_ODA.dxf")
            n1_bbox = self._get_n1_bbox(vn)
            n2_bbox = self._get_n2_bbox(vn)

            # Fichas (instantâneas)
            self._columns[0].set_ficha(self._ficha_n1(vn))
            self._columns[1].set_ficha(self._ficha_n2(vn))
            self._columns[2].set_ficha(self._ficha_n3(vn))

            # N3: PNG — carrega imediatamente (sem DXF, sem memória extra)
            n3_path = LV_RENDERS_DIR / f"{vn}_gerado.png"
            self._columns[2].load_content(n3_path)

            # Desconectar chain anterior pelo nome (evita RuntimeWarning)
            prev = getattr(self, '_n1_ready_cb', None)
            if prev is not None:
                try:
                    self._columns[0].img_widget.ready.disconnect(prev)
                except (RuntimeError, TypeError):
                    pass

            # Loading sequencial: N1 termina → inicia N2
            def _on_n1_ready():
                self._n1_ready_cb = None
                try:
                    self._columns[0].img_widget.ready.disconnect(_on_n1_ready)
                except (RuntimeError, TypeError):
                    pass
                self._columns[1].load_content(
                    n2_dxf if n2_dxf.exists() else None, n2_bbox
                )

            self._n1_ready_cb = _on_n1_ready
            self._columns[0].img_widget.ready.connect(_on_n1_ready)
            self._columns[0].load_content(
                n1_dxf if n1_dxf.exists() else None, n1_bbox
            )

    def _get_n1_bbox(self, vn: str):
        """Retorna bbox do viga no DXF estrutural usando labels escaneados."""
        pos = self._est_labels.get(vn)
        if not pos:
            return None
        cx, cy = pos
        R = 800
        xs = [ex for (_, ex, ey, _) in self._est_ents_raw
              if abs(ex - cx) < R and abs(ey - cy) < R]
        ys = [ey for (_, ex, ey, _) in self._est_ents_raw
              if abs(ex - cx) < R and abs(ey - cy) < R]
        if not xs:
            return (cx - R, cy - R, cx + R, cy + R)
        pad = 200
        return (min(xs)-pad, min(ys)-pad, max(xs)+pad, max(ys)+pad)

    def _get_n2_bbox(self, vn: str):
        """Retorna bbox do viga no DXF STOG real a partir do KB."""
        if not self._kb_ents:
            return None
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
            return None
        cx, cy = main_sentinel
        R = 500
        all_xs, all_ys = [], []
        for e in self._kb_ents:
            t = e.get('type', '')
            if t in ('MTEXT', 'TEXT'):
                ins = e.get('insert', [0, 0]); ex, ey = ins[0], ins[1]
            elif t == 'LINE':
                s = e.get('start', [0,0]); en = e.get('end', [0,0])
                ex = (s[0]+en[0])/2; ey = (s[1]+en[1])/2
            elif t == 'LWPOLYLINE':
                pts2 = e.get('vertices', [])
                if not pts2: continue
                for pp in pts2:
                    if abs(pp[0]-cx)<R and abs(pp[1]-cy)<R:
                        all_xs.append(pp[0]); all_ys.append(pp[1])
                continue
            elif t == 'DIMENSION':
                ins = e.get('insert', [0,0]); ex, ey = ins[0], ins[1]
            else:
                continue
            if abs(ex-cx)<R and abs(ey-cy)<R:
                all_xs.append(ex); all_ys.append(ey)
        if not all_xs:
            return (cx-R, cy-R, cx+R, cy+R)
        pad = 80
        return (min(all_xs)-pad, min(all_ys)-pad,
                max(all_xs)+pad, min(cy+180, max(all_ys)+pad))

    def set_processing(self, active: bool):
        for col in self._columns:
            col.set_processing(active)

    # ── Fichas ──────────────────────────────────────────────────────

    def _ficha_n1(self, vn: str) -> list:
        vd  = self._vigas_fase3.get(vn, {})
        fr  = self._fichas_rev.get(vn, {})
        anc = self._ancoras.get(vn, {})
        return [
            ("Nome", vn),
            ("b estrutural (cm)", vd.get("b", "—")),
            ("h estrutural (cm)", vd.get("h", "—")),
            ("Comprimento bruto (cm)", vd.get("comprimento_original", "—")),
            ("Comprimento enriquecido (cm)", vd.get("comprimento", "—")),
            ("Status enriquecimento", vd.get("comprimento_enrich_status", "—")),
            ("Confidence", f"{vd.get('confidence', 0)*100:.1f}%" if vd.get('confidence') else "—"),
            ("Source", vd.get("source", "—")),
            ("Faces", ", ".join(vd.get("sides", []))),
            ("has_lv", str(fr.get("has_lv", "—"))),
            ("has_fv", str(fr.get("has_fv", "—"))),
            ("Pavimentos", ", ".join(fr.get("pavimentos", []))),
            ("Altura estrutural (cm)", fr.get("altura_cm", "—")),
            ("Âncora A (x, y)", str(anc.get("A", "—"))),
            ("Âncora B (x, y)", str(anc.get("B", "—"))),
        ]

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

    def _ficha_n3(self, vn: str) -> list:
        entries = [f for f in self._fichas_lv_v2 if f.get('viga') == vn]
        if not entries:
            return [("Ficha LV v2", "não encontrada")]
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
                (f"[{face}] sarrafos", f"{e.get('total_sarrafos','—')} ({e.get('sarr_por_tipo',{})})"),
                (f"[{face}] nota_face", e.get('nota_face', '—')),
                ("---", ""),
            ]
        return rows


# ──────────────────────────────────────────────────────
# Module principal (Tab 2)
# ──────────────────────────────────────────────────────

class ComparisonEngineModule(QWidget):
    """
    Tab 2 — Comparison Engine / Fase-8 Validação Visual.
    Layout: [NavSidebar (esquerda)] | [TriLevelArea (centro)] | [Fase8Panel (direita)]
    """

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Sidebar de navegação (esquerda)
        self.nav_sidebar = NavSidebar()
        self.nav_sidebar.item_selected.connect(self._on_item_selected)
        self.nav_sidebar.process_requested.connect(self._on_process_requested)
        layout.addWidget(self.nav_sidebar)

        # 2. Área central 3 níveis
        self.tri_level = TriLevelArea()
        layout.addWidget(self.tri_level, 1)

        # 3. Painel Fase-8 (direita)
        self.fase8_panel = Fase8Panel()
        self.fase8_panel.load_history()
        layout.addWidget(self.fase8_panel)

        self._process       = None
        self._pending_classe = ""
        self._pending_item   = ""

    def _on_item_selected(self, classe: str, item_id: str):
        self.tri_level.load_item(classe, item_id)

    def _on_process_requested(self, classe: str, item_id: str):
        if self._process and self._process.state() == QProcess.Running:
            self.nav_sidebar.set_status("Já processando...", Colors.ACCENT_WARNING)
            return
        if not GEN_SCRIPT_3N.exists():
            self.nav_sidebar.set_status(
                f"Script não encontrado:\n{GEN_SCRIPT_3N.name}", Colors.ACCENT_DANGER
            )
            self.nav_sidebar.btn_process.setEnabled(True)
            self.nav_sidebar.btn_process_all.setEnabled(True)
            return

        self._pending_classe = classe
        self._pending_item   = item_id

        self.nav_sidebar.set_status("Processando crops DXF...", Colors.ACCENT_WARNING)
        self.tri_level.set_processing(True)

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_proc_out)
        self._process.finished.connect(self._on_proc_done)
        self._process.start(sys.executable, [str(GEN_SCRIPT_3N)])

    def _on_proc_out(self):
        raw  = bytes(self._process.readAllStandardOutput())
        text = raw.decode('utf-8', errors='replace').strip()
        if text:
            last = text.splitlines()[-1]
            self.nav_sidebar.set_status(last[:50], Colors.TEXT_SECONDARY)

    def _on_proc_done(self, code, _):
        self.tri_level.set_processing(False)
        self.nav_sidebar.btn_process.setEnabled(True)
        self.nav_sidebar.btn_process_all.setEnabled(True)
        self.nav_sidebar.refresh_tree()

        if code == 0:
            self.nav_sidebar.set_status("Processado com sucesso!", Colors.ACCENT_SUCCESS)
            if self._pending_item and self._pending_item != "ALL":
                self.tri_level.load_item(self._pending_classe, self._pending_item)
            elif self._pending_item == "ALL" and VIGAS_LV_LIST:
                # Selecionar primeira viga após processar todas
                self.tri_level.load_item("LV", VIGAS_LV_LIST[0])
        else:
            self.nav_sidebar.set_status(f"Erro (código {code})", Colors.ACCENT_DANGER)

    def set_database(self, db, project_id: str = ''):
        self.fase8_panel.set_database(db, project_id)
