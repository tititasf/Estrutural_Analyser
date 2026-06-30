"""
PreValidationDialog — janela de confirmação pós-análise de lajes.

Abre ANTES de processar vigas/pilares e apresenta 2 abas:
  1. Pilares  — lista de pilares + classificação + tipo físico (editable)
               + painel de mapeamento de terminologia da obra
  2. Visão de Cortes — lista de cortes com score de associação ao nome da viga

Retorna via exec_() == QDialog.Accepted / Rejected.
Resultado acessível em dialog.get_result() → dict.
"""

from __future__ import annotations
import re
import math
import json
import os
from datetime import datetime
from typing import Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QComboBox, QGroupBox, QGridLayout, QAbstractItemView,
    QSizePolicy, QScrollArea, QSplitter, QGraphicsView, QGraphicsScene,
    QMessageBox, QTextEdit, QFileDialog,
)
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, QSize, QThread, Signal
from PySide6.QtGui import (QColor, QFont, QBrush, QPixmap, QPainter,
                            QPen, QPolygonF, QPainterPath)

from src.ui.theme import Colors, Semantic, Accent, Text, Surface, Border, Contextual
from src.core.preficha_segments import (
    SEGMENT_TAB_SPECS,
    collect_preficha_segments,
    serializable_segment,
)

# ── Logger de diagnóstico de freeze (TEMPORÁRIO) ────────────────────────────────
_DBG_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'freeze_dump.log'
)
def _dbg(msg: str) -> None:
    try:
        with open(_DBG_LOG, 'a', encoding='utf-8') as _f:
            _f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] PVD: {msg}\n")
            _f.flush()
    except Exception:
        pass

# ── Constantes de terminologia ─────────────────────────────────────────────────

PHYSICAL_TYPES: list[tuple[str, str]] = [
    ('solid',           'Objeto Sólido (pilar que bloqueia)'),
    ('visual_only',     'Somente Visual (pilar que ignora nas vigas)'),
    ('obstacle_solid',  'NÃO PILAR — porém Objeto Sólido (bloqueia)'),
    ('visual_noise',    'NÃO PILAR — Apenas Visual (não bloqueia)'),
    ('unknown',         'Indeterminado'),
]
PHYS_LABEL: dict[str, str] = {k: v for k, v in PHYSICAL_TYPES}
PHYS_IGNORE: dict[str, bool] = {
    'solid': False,
    'visual_only': True,
    'obstacle_solid': False,
    'visual_noise': True,
    'unknown': False,
}

# Formato geométrico do pilar (shape detection)
PILLAR_FORMATO_LABELS: dict[str, str] = {
    'Retangular':  'Retangular',
    'em L':        'em L',
    'em U':        'em U',
    'em T':        'em T',
    'Circular':    'Circular',
    'Especial':    'Especial',
}

PILLAR_FORMATO_COLORS: dict[str, str] = {
    'Retangular': '#4fc3a1',   # mint — padrão ok
    'em L':       '#e6b400',   # gold
    'em U':       '#e6b400',
    'em T':       '#e6b400',
    'Circular':   '#7eb8f7',   # azul info
    'Especial':   '#f07070',   # vermelho leve
}


def _pilar_formato(pts: list) -> str:
    """Detecta o formato geométrico do pilar a partir dos vértices da polilinha.

    Passos:
      1. Remove vértice de fechamento (se último == primeiro).
      2. Remove vértices colineares (3 consecutivos na mesma linha H/V).
      3. Classifica pelo número de vértices limpos:
           4  → Retangular
           6  → em L
           8  → em U
           ≥8 com perfil circular (CV de distâncias < 15%) → Circular
           outros → Especial
    """
    if not pts:
        return 'Especial'
    try:
        clean = list(pts)
        # 1. Remove vértice de fechamento
        if len(clean) > 1:
            if (abs(float(clean[0][0]) - float(clean[-1][0])) < 0.5
                    and abs(float(clean[0][1]) - float(clean[-1][1])) < 0.5):
                clean = clean[:-1]

        # 2. Remove vértices colineares iterativamente (H ou V)
        changed = True
        while changed and len(clean) > 3:
            changed = False
            new: list = []
            nc = len(clean)
            for i in range(nc):
                p0 = clean[(i - 1) % nc]
                p1 = clean[i]
                p2 = clean[(i + 1) % nc]
                vert  = (abs(float(p0[0]) - float(p1[0])) < 0.5
                         and abs(float(p1[0]) - float(p2[0])) < 0.5)
                horiz = (abs(float(p0[1]) - float(p1[1])) < 0.5
                         and abs(float(p1[1]) - float(p2[1])) < 0.5)
                if vert or horiz:
                    changed = True
                else:
                    new.append(p1)
            if new:
                clean = new

        n = len(clean)
        if n == 4:
            return 'Retangular'
        if n == 6:
            return 'em L'
        if n == 8:
            return 'em U'

        # 3. Circular: muitos segmentos e vértices equidistantes do centróide
        if n >= 8:
            import math as _math
            cx = sum(float(p[0]) for p in clean) / n
            cy = sum(float(p[1]) for p in clean) / n
            dists = [_math.sqrt((float(p[0]) - cx) ** 2 + (float(p[1]) - cy) ** 2)
                     for p in clean]
            md = sum(dists) / n
            if md > 0 and (max(dists) - min(dists)) / md < 0.15:
                return 'Circular'

        return 'Especial'
    except Exception:
        return 'Especial'


# Termos padrão → tipo físico
STANDARD_TERM_MAP: dict[str, str] = {
    'NASCE':    'visual_only',
    'MORRE':    'solid',
    'CONTINUA': 'solid',
    'SEGUE':    'solid',
    'PASSA':    'solid',
}

# Classificações disponíveis no combobox de pilar.
PILLAR_CLASSIFICATION_OPTIONS: list[str] = [
    'NASCE', 'MORRE', 'CONTINUA', 'SEGUE',
    'INDETERMINADO',
    '── Não é pilar ─────────────────────────',   # separador (não selecionável)
    'NÃO PILAR — OBJETO SÓLIDO',
    'NÃO PILAR — APENAS VISUAL',
    '── Geometria vinculada errada ───────────',  # separador (não selecionável)
    'GEOMETRIA ERRADA — ATUAL SÓLIDA',
    'GEOMETRIA ERRADA — ATUAL APENAS VISUAL',
]

# Chaves internas
_NAO_PILAR_SOLIDO   = 'NÃO PILAR — OBJETO SÓLIDO'
_NAO_PILAR_VISUAL   = 'NÃO PILAR — APENAS VISUAL'
_GEOM_ERRADA_SOLIDA = 'GEOMETRIA ERRADA — ATUAL SÓLIDA'
_GEOM_ERRADA_VISUAL = 'GEOMETRIA ERRADA — ATUAL APENAS VISUAL'
_SEPARADOR_ITEM     = '── Não é pilar ─────────────────────────'
_SEPARADOR_GEOM     = '── Geometria vinculada errada ───────────'

# Classificações que invalidam os lados A/B/C/D (geometria errada ou não é pilar)
_NAO_SE_APLICA_CLASSIFS: frozenset[str] = frozenset({
    _NAO_PILAR_SOLIDO.upper(),
    _NAO_PILAR_VISUAL.upper(),
    _GEOM_ERRADA_SOLIDA.upper(),
    _GEOM_ERRADA_VISUAL.upper(),
})

# Distância máxima para associação de corte → viga (unidades DXF, tipicamente cm)
MAX_ASSOC_DIST = 900.0

# Pattern de nome de viga
BEAM_NAME_RE = re.compile(r'^[Vv]\s*\d{2,}')


# ── Helpers visuais ────────────────────────────────────────────────────────────

def _confidence_color(pct: float) -> QColor:
    if pct >= 75:
        return QColor(Semantic.SUCCESS)
    if pct >= 50:
        return QColor(Semantic.WARNING)
    return QColor(Semantic.DANGER)


def _make_item(text: str, align=Qt.AlignLeft, bold: bool = False,
               color: QColor | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
    item.setTextAlignment(align | Qt.AlignVCenter)
    if bold:
        f = item.font(); f.setBold(True); item.setFont(f)
    if color:
        item.setForeground(QBrush(color))
    return item


# ── Mini viewer vetorial ───────────────────────────────────────────────────────

class _MiniDXFView(QGraphicsView):
    """
    Mini viewer vetorial embutido na célula da tabela usando QGraphicsView real.
    Carregamento lazy garante que poucas instâncias existam simultaneamente, evitando travamentos.
    """
    def __init__(
        self,
        scene,
        x0: float, y0: float, x1: float, y1: float,
        thumb_w: int, thumb_h: int,
        highlight_pts: list | None = None,
        parent=None,
    ):
        super().__init__(scene, parent)
        self.setFixedSize(thumb_w, thumb_h)
        self._highlight_pts = highlight_pts or []
        
        self.setStyleSheet(
            f"border:1px solid {Colors.BORDER_DEFAULT}; "
            f"background:{Colors.BG_PANEL};"
        )
        self.setRenderHint(QPainter.Antialiasing, False)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Invert Y to match DXF coordinates
        self.scale(1, -1)
        
        w = max(x1 - x0, 1.0)
        h = max(y1 - y0, 1.0)
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        
        dxf_rect = QRectF(cx - w/2, cy - h/2, w, h)
        self.fitInView(dxf_rect, Qt.KeepAspectRatio)
            
    def drawForeground(self, painter, rect):
        if len(self._highlight_pts) >= 2:
            poly = QPolygonF([QPointF(float(p[0]), float(p[1])) for p in self._highlight_pts])
            fill = QColor(Accent.PRIMARY)
            fill.setAlpha(40)
            painter.setBrush(QBrush(fill))
            pen = QPen(QColor(Accent.BRAND))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawPolygon(poly)

    def wheelEvent(self, event):
        # Zoom in and zoom out mantendo integridade da funcao de arraste
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale(zoom_factor, zoom_factor)
        event.accept()

    # ── Interação ─────────────────────────────────────────────────────────────

    def wheelEvent(self, event):
        """Zoom centrado na posição do cursor; não propaga para o widget pai."""
        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return
        factor = 1.20 if delta > 0 else 1.0 / 1.20
        # Ancora o zoom no ponto DXF sob o cursor
        anchor = event.position().toPoint()
        scene_before = self.mapToScene(anchor)
        self.scale(factor, factor)
        scene_after = self.mapToScene(anchor)
        diff = scene_after - scene_before
        self.translate(diff.x(), diff.y())
        event.accept()

    # ── Destaque do item ───────────────────────────────────────────────────────

    def drawForeground(self, painter: QPainter, rect):
        """Sobrepõe o contorno do polígono do item sem alterar a cena compartilhada."""
        if len(self._highlight_pts) < 2:
            return
        try:
            poly = QPolygonF([QPointF(float(p[0]), float(p[1]))
                              for p in self._highlight_pts])
        except Exception:
            return
        painter.save()
        # Fill translúcido para marcar a área
        fill = QColor(Accent.PRIMARY)
        fill.setAlpha(40)
        painter.setBrush(QBrush(fill))
        # Borda cosmética: largura fixa em pixels independente do zoom
        pen = QPen(QColor(Accent.BRAND))
        pen.setCosmetic(True)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawPolygon(poly)
        painter.restore()


class _DXFReaderThread(QThread):
    """Lê um DXF de forma assíncrona com ezdxf.readfile (seguro em background)."""
    finished = Signal(object)  # Emite o 'doc' lido ou None se falhar

    def __init__(self, dxf_path: str):
        super().__init__()
        self.dxf_path = dxf_path

    def run(self):
        try:
            import ezdxf
            doc = ezdxf.readfile(self.dxf_path)
            self.finished.emit(doc)
        except Exception as e:
            print(f"DXFReaderThread erro: {e}")
            self.finished.emit(None)

# ── Classe principal ───────────────────────────────────────────────────────────

class PreValidationDialog(QDialog):
    """Diálogo de pré-validação pós-lajes."""

    def __init__(
        self,
        pillar_report: dict,
        nivel_report: dict,
        slabs: list[dict],
        convention: dict,
        obra: str,
        pavimento: str,
        beam_texts: list[dict] | None = None,
        canvas=None,          # CADCanvas (QGraphicsView) para recortes reais
        convention_file: str | None = None,  # path p/ JSON de convenção salva
        db_path: str | None = None,           # SQLite project_data.vision
        dxf_data: dict | None = None,         # DXF bruto para re-detecção de geometrias
        beams: list[dict] | None = None,       # vigas SA ja segmentadas (mesmas refs do pos-preficha)
        parent=None,
    ):
        super().__init__(parent)
        # Qt.Dialog previne o deadlock de foco (soft-lock) no Windows ao usar modality com parent
        self.setWindowFlags(Qt.Dialog | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle(f"Pré-validação — {obra} / {pavimento}")
        self.setMinimumSize(1000, 600)
        self.setModal(True)
        self.setStyleSheet(
            f"QDialog {{ background:{Colors.BG_PRIMARY}; color:{Colors.TEXT_PRIMARY}; }}"
            f"QLabel {{ color:{Colors.TEXT_PRIMARY}; }}"
            f"QTableWidget {{ background:{Colors.BG_SECONDARY}; color:{Colors.TEXT_PRIMARY}; "
            f"  gridline-color:{Colors.BORDER_DEFAULT}; border:none; }}"
            f"QHeaderView::section {{ background:{Colors.BG_PANEL}; color:{Colors.ACCENT_MINT}; "
            f"  border:none; padding:4px; font-size:9px; }}"
            f"QGroupBox {{ color:{Colors.ACCENT_MINT}; font-size:10px; font-weight:bold; "
            f"  border:1px solid {Colors.BORDER_DEFAULT}; margin-top:6px; padding-top:8px; }}"
            f"QPushButton {{ background:{Colors.BG_PANEL}; color:{Colors.TEXT_PRIMARY}; "
            f"  border:1px solid {Colors.BORDER_DEFAULT}; border-radius:3px; padding:4px 10px; }}"
            f"QPushButton:hover {{ border-color:{Colors.ACCENT_MINT}; }}"
            f"QComboBox {{ background:{Colors.BG_PANEL}; color:{Colors.TEXT_PRIMARY}; "
            f"  border:1px solid {Colors.BORDER_INPUT}; }}"
            f"QTabWidget::pane {{ border:1px solid {Colors.BORDER_DEFAULT}; }}"
            f"QTabBar::tab {{ background:{Colors.BG_PANEL}; color:{Colors.TEXT_MUTED}; "
            f"  padding:5px 14px; font-size:10px; }}"
            f"QTabBar::tab:selected {{ background:{Colors.BG_SECONDARY}; color:{Colors.ACCENT_MINT}; }}"
        )

        self._pillar_report = pillar_report or {}
        self._nivel_report = nivel_report or {}
        self._slabs = slabs or []
        self._convention = convention or {}
        self._beam_texts = beam_texts or []
        self._obra = obra
        self._pavimento = pavimento
        self._canvas = canvas   # QGraphicsView — usado para mini viewers

        # Cena DXF compartilhada pelos mini viewers (sem grab, sem pixelação)
        self._dxf_scene = getattr(canvas, 'scene', None) if canvas is not None else None
        # DXF bruto (optional) — usado para re-detectar geometrias de pilares
        self._dxf_data = dxf_data or {}
        self._beams = beams or []
        self._segment_data: dict[str, list[dict]] = collect_preficha_segments(self._beams)
        self._segment_tables: dict[str, QTableWidget] = {}
        self._segment_viewer_data: dict[str, dict[int, list]] = {}
        self._segment_status_combos: dict[str, QComboBox] = {}
        self._segment_attention: dict[str, str] = {}
        self._atencao_notes: dict[str, str] = {}

        # Anti-freeze: suspende repaints do canvas principal enquanto este modal
        # (maximizado, que cobre o canvas) está aberto. Sem isso, os mini-viewers
        # vivos sobre a cena gigante fazem o canvas repintar em loop e travam.
        self._canvas_suppressed = False
        self.finished.connect(self._restore_canvas_updates)

        # Mapas de suporte (construídos antes dos dados)
        self._slab_height_map: dict[str, str] = self._build_slab_height_map()
        self._slab_nivel_map:  dict[str, str] = self._build_slab_nivel_map()
        self._slab_poly_map: dict[str, list] = self._build_slab_poly_map()

        # Estado editável
        self._term_type_map: dict[str, str] = self._build_initial_term_map()
        self._pillar_combos: dict[str, QComboBox] = {}   # key → classif combobox
        self._term_combos: dict[str, QComboBox] = {}     # term → phys_type combobox
        self._cut_combos: dict[str, QComboBox] = {}      # cut_uid → beam_name combobox
        self._pillar_rows: dict[str, int] = {}           # key → row index
        self._phys_labels: dict[str, QLabel] = {}        # key → QLabel de Tipo Físico
        self._cut_status_combos: dict[str, QComboBox] = {}  # uid → status combobox
        self._cut_attention: dict[str, str] = {}
        self._cut_tag_labels: dict[str, QLabel] = {}         # uid → tag QLabel
        self._cut_migrar_btns: dict[str, QPushButton] = {}   # uid → botão migrar pilar
        self._cut_row_meta: dict[str, dict] = {}             # uid → {'row', 'is_hist'}
        self._cut_view_data: list[dict] = self._collect_cut_views()

        self._convention_file: str | None = convention_file
        self._db_path: str | None = db_path
        self._saved_term_examples: dict[str, list | None] = {}
        self._btn_save_conv: QPushButton | None = None  # injetado em _build_footer

        # ── Histórico de pré-ficha (persistência por geometria) ───────────────
        self._history_path: str | None = self._resolve_history_path()
        self._pf_history: dict = self._load_pf_history()
        ui_state = self._pf_history.get('ui_state', {})
        try:
            self._active_tab_index = max(0, min(9, int(ui_state.get('active_tab', 0))))
        except (TypeError, ValueError):
            self._active_tab_index = 0
        self._saved_scroll_positions: dict[str, int] = dict(
            ui_state.get('scroll_positions', {}) or {}
        )
        segment_history = self._pf_history.get('beam_segments', {})
        for entries in self._segment_data.values():
            for segment in entries:
                saved = segment_history.get(segment['uid'], {})
                if saved:
                    segment['status'] = saved.get('status') or 'valid'
                    segment['attention'] = saved.get('attention') or ''

        # Sobrescreve _term_type_map com convenção salva (se existir) ANTES de _build_ui
        if convention_file and os.path.isfile(convention_file):
            self._load_saved_convention(convention_file)

        self._build_ui()
    def _build_slab_height_map(self) -> dict[str, str]:
        """Extrai espessura (H) de cada laje pelo campo laje_dim."""
        result: dict[str, str] = {}
        for slab in self._slabs:
            name = slab.get('name') or ''
            if not name:
                continue
            fields = slab.get('fields') or {}
            raw = fields.get('laje_dim') or slab.get('laje_dim') or ''
            # Pega o primeiro número (espessura H)
            m = re.search(r'\d+(?:[.,]\d+)?', str(raw))
            result[name] = m.group(0) if m else ''
        return result

    def _build_slab_nivel_map(self) -> dict[str, str]:
        """Extrai nivel (level_str) de cada laje via nivel_report.

        Lajes com warning de alucinação (após retries) recebem '⚠' em vez do
        valor suspeito — evita que niveis errados contaminem as colunas Lado-A/B/C/D.
        """
        lajes_nr = (self._nivel_report or {}).get('lajes', {})
        result: dict[str, str] = {}
        for name, entry in lajes_nr.items():
            is_suspect = any(
                'alucinacao' in w.lower() or 'diverge' in w.lower()
                for w in (entry.get('warnings') or [])
            )
            result[name] = '⚠' if is_suspect else (entry.get('level_str') or '')
        return result

    def _build_slab_poly_map(self) -> dict[str, list]:
        """Constrói mapa nome_laje → lista de pontos do polígono."""
        result: dict[str, list] = {}
        for slab in self._slabs:
            name = slab.get('name') or ''
            pts = slab.get('points') or []
            if name and len(pts) >= 3:
                result[name] = pts
        return result

    def _side_edge(self, bbox: tuple, orientation: str,
                  side: str) -> tuple[tuple, tuple] | None:
        """
        Retorna os dois extremos da aresta completa do pilar para o lado dado.

        Horizontal: A=baixo(y0) B=cima(y1) C=esq(x0) D=dir(x1)
        Vertical:   A=esq(x0)  B=dir(x1)  C=cima(y1) D=baixo(y0)
        """
        if not bbox:
            return None
        x0, y0, x1, y1 = bbox
        horiz = (orientation or '').lower() != 'vertical'
        table = {
            True:  {'A': ((x0, y0), (x1, y0)),
                    'B': ((x0, y1), (x1, y1)),
                    'C': ((x0, y0), (x0, y1)),
                    'D': ((x1, y0), (x1, y1))},
            False: {'A': ((x0, y0), (x0, y1)),
                    'B': ((x1, y0), (x1, y1)),
                    'C': ((x0, y1), (x1, y1)),
                    'D': ((x0, y0), (x1, y0))},
        }
        return table[horiz].get(side)

    def _side_midpoint(self, bbox: tuple, orientation: str,
                       side: str) -> tuple[float, float] | None:
        """Ponto médio da aresta (atalho para compatibilidade)."""
        edge = self._side_edge(bbox, orientation, side)
        if edge is None:
            return None
        (x1, y1), (x2, y2) = edge
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def _point_in_polygon(self, px: float, py: float, pts: list) -> bool:
        """Ray-casting para detectar se ponto está dentro do polígono."""
        n = len(pts)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = float(pts[i][0]), float(pts[i][1])
            xj, yj = float(pts[j][0]), float(pts[j][1])
            if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    def _edge_overlaps_poly_boundary(
        self,
        p1: tuple, p2: tuple,
        poly_pts: list,
        collinear_tol: float = 12.0,
        min_overlap: float = 5.0,
    ) -> bool:
        """
        Retorna True se o segmento p1→p2 for aproximadamente colínear E tiver
        sobreposição projetada ≥ min_overlap com qualquer aresta do polígono.

        Funciona apenas para segmentos axis-aligned (caso típico de plantas estruturais).

        Parâmetros
        ----------
        collinear_tol : distância perpendicular máxima entre as retas (~DXF units)
        min_overlap   : comprimento mínimo de sobreposição projetada
        """
        ax1, ay1 = float(p1[0]), float(p1[1])
        ax2, ay2 = float(p2[0]), float(p2[1])
        a_vert = abs(ax2 - ax1) < collinear_tol   # segmento A é vertical
        a_horiz = abs(ay2 - ay1) < collinear_tol  # segmento A é horizontal

        if not a_vert and not a_horiz:
            return False   # diagonal — ignora

        n = len(poly_pts)
        for i in range(n):
            bx1 = float(poly_pts[i][0])
            by1 = float(poly_pts[i][1])
            bx2 = float(poly_pts[(i + 1) % n][0])
            by2 = float(poly_pts[(i + 1) % n][1])

            b_vert  = abs(bx2 - bx1) < collinear_tol
            b_horiz = abs(by2 - by1) < collinear_tol

            if a_vert and b_vert:
                # Ambos verticais — verifica que X's são próximos e Y sobrepõe
                if abs(ax1 - bx1) > collinear_tol:
                    continue
                ov = min(max(ay1, ay2), max(by1, by2)) - max(min(ay1, ay2), min(by1, by2))
                if ov >= min_overlap:
                    return True

            elif a_horiz and b_horiz:
                # Ambos horizontais — verifica que Y's são próximos e X sobrepõe
                if abs(ay1 - by1) > collinear_tol:
                    continue
                ov = min(max(ax1, ax2), max(bx1, bx2)) - max(min(ax1, ax2), min(bx1, bx2))
                if ov >= min_overlap:
                    return True

        return False

    @staticmethod
    def _side_cell_laje_block(ln: str, h: str, nivel: str) -> str:
        """Formata um bloco multi-linha para uma laje em célula Lado-A/B/C/D."""
        is_beam = ln.upper().startswith('V') or ln.upper().startswith('FV') or ln.upper().startswith('LV')
        lines = []
        if is_beam:
            lines.append(f'Viga: {ln}')
            lines.append('Largura:')
        else:
            lines.append(f'Laje: {ln}')

        lines.append(f'Altura: {h}' if h else 'Altura:')
        # ⚠ marca nivel suspeito de alucinação (após retries falharam)
        nivel_disp = '⚠ suspeito' if nivel == '⚠' else nivel
        lines.append(f'Nivel: {nivel_disp}' if nivel_disp else 'Nivel:')
        return '\n'.join(lines)

    _VIGA_CELL_TEXT = 'Viga:\nLargura:\nAltura:\nNivel:'

    def _get_side_cell(self, pillar: dict, side: str) -> str:
        """
        Retorna o texto para a célula do lado (A/B/C/D) de um pilar.

        Regras estruturais:
          Lados A e B  → sempre LAJE (face principal: laje encosta direto no pilar)
          Lados C e D  → VIGA QUE PASSA quando a face está DENTRO do corpo da viga
                         (proxy: pontos da aresta dentro de polígono de laje);
                         LAJE quando a face encontra uma laje sem viga atravessando;
                         NULO se não há nada.

        Estratégias em ordem de prioridade:
        1. Links diretos do SA (pillar['lajes']) → bloco Laje/Altura/Nível
        2. Pontos da aresta DENTRO de polígono de laje:
             A/B → LAJE com nome; C/D → VIGA QUE PASSA (face embutida = viga atravessa)
        3. Aresta colínear com borda do polígono (slab boundary = pilar face):
             A/B → LAJE com nome; C/D → LAJE com nome (laje abuta a face sem viga)
        4. Projeção perpendicular para FORA da aresta (slab adjacente exterior):
             A/B → LAJE com nome; C/D → LAJE com nome (laje do lado, sem viga interna)
        5. Nada encontrado → "nulo"
        """
        lajes_entries = [e for e in (pillar.get('lajes') or []) if e.get('side') == side]
        if lajes_entries:
            parts: list[str] = []
            for e in lajes_entries:
                ln    = e.get('laje') or '?'
                h     = self._slab_height_map.get(ln) or ''
                nivel = self._slab_nivel_map.get(ln) or ''
                parts.append(self._side_cell_laje_block(ln, h, nivel))
            return '\n\n'.join(parts)

        bbox        = pillar.get('bbox')
        orientation = pillar.get('orientation') or 'horizontal'
        edge        = self._side_edge(bbox, orientation, side)
        if not edge:
            return 'nulo'

        (ex0, ey0), (ex1, ey1) = edge
        is_ab = side in ('A', 'B')

        samples = [
            (ex0 * 0.75 + ex1 * 0.25, ey0 * 0.75 + ey1 * 0.25),
            ((ex0 + ex1) / 2.0,        (ey0 + ey1) / 2.0),
            (ex0 * 0.25 + ex1 * 0.75, ey0 * 0.25 + ey1 * 0.75),
        ]

        def _laje_block(sn: str) -> str:
            return self._side_cell_laje_block(
                sn,
                self._slab_height_map.get(sn) or '',
                self._slab_nivel_map.get(sn) or '',
            )

        # ── Estratégia 2: pontos da aresta DENTRO de polígono de laje ─────────
        # A/B: face principal toca laje → LAJE
        # C/D: face embutida em polígono → proxy de viga que atravessa → VIGA template
        for sn, poly_pts in self._slab_poly_map.items():
            for px, py in samples:
                if self._point_in_polygon(px, py, poly_pts):
                    return _laje_block(sn) if is_ab else self._VIGA_CELL_TEXT

        # ── Estratégia 3: aresta colínear com borda do polígono ───────────────
        # Laje termina exatamente na face → LAJE para ambos os casos (A/B/C/D)
        for sn, poly_pts in self._slab_poly_map.items():
            if self._edge_overlaps_poly_boundary((ex0, ey0), (ex1, ey1), poly_pts):
                return _laje_block(sn)

        # ── Estratégia 4: projeção perpendicular para fora da aresta ──────────
        # Encontra laje adjacente exterior → LAJE para todos os lados
        horiz = (orientation or '').lower() != 'vertical'
        outward_dirs = {
            True:  {'A': (0.0, -1.0), 'B': (0.0, 1.0), 'C': (-1.0, 0.0), 'D': (1.0, 0.0)},
            False: {'A': (-1.0, 0.0), 'B': (1.0, 0.0), 'C': (0.0, 1.0), 'D': (0.0, -1.0)},
        }
        dx, dy = outward_dirs[horiz].get(side, (0.0, 0.0))
        for delta in (4.0, 12.0, 25.0):
            for px, py in samples:
                for sn, poly_pts in self._slab_poly_map.items():
                    if self._point_in_polygon(px + dx * delta, py + dy * delta, poly_pts):
                        return _laje_block(sn)

        return 'nulo'

    def _suppress_canvas_updates(self) -> None:
        """Desliga repaints do canvas principal enquanto o modal está aberto.

        O diálogo é maximizado e cobre o canvas, então isto é invisível ao
        usuário. Evita que os mini-viewers vivos (QGraphicsView sobre a mesma
        cena de dezenas de milhares de itens) disparem repaints em cascata do
        canvas full-screen — a causa do travamento ao abrir a janela.
        """
        c = getattr(self, '_canvas', None)
        if c is None or self._canvas_suppressed:
            return
        try:
            c.setUpdatesEnabled(False)
            self._canvas_suppressed = True
        except Exception:
            pass

    def _restore_canvas_updates(self, *args) -> None:
        """Reabilita os updates do canvas principal (ao fechar o diálogo)."""
        c = getattr(self, '_canvas', None)
        if c is None or not self._canvas_suppressed:
            return
        try:
            c.setUpdatesEnabled(True)
            vp = c.viewport() if hasattr(c, 'viewport') else None
            if vp is not None:
                vp.update()
        except Exception:
            pass
        self._canvas_suppressed = False

    def showEvent(self, event):
        super().showEvent(event)
        self._suppress_canvas_updates()

    def closeEvent(self, event):
        self._save_pf_history()
        self._restore_canvas_updates()
        super().closeEvent(event)

    def _make_mini_viewer(
        self, pts: list,
        thumb_w: int, thumb_h: int,
        margin_factor: float = 3.0,
        min_margin_dxf: float = 120.0,
        fallback_line: str = Colors.ACCENT_MINT,
        fallback_fill: str = Surface.RAISED,
    ) -> QWidget | None:
        """
        Cria um _MiniDXFView VIVO (vetorial, com zoom e arraste) que compartilha
        a cena DXF do canvas principal, centralizado na bbox dos pontos + margem.

        Performance/anti-freeze: enquanto este diálogo modal (maximizado) está
        aberto, os updates do canvas principal ficam SUSPENSOS — ver
        _suppress_canvas_updates(). Sem isso, múltiplas QGraphicsView sobre a
        mesma cena gigante (planta inteira) faziam o canvas repintar 25k+ itens
        em loop e travavam a GUI. As tabelas de pilares/cortes ainda carregam os
        viewers de forma lazy (apenas os visíveis) via _update_dynamic_viewers.

        Fallback: QLabel com polígono geométrico se a cena não estiver disponível.

        Fallback: QLabel com polígono geométrico se a cena não estiver disponível.
        """
        if not pts:
            return None
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
        except Exception:
            return None

        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        dxf_w = max(maxx - minx, 1.0)
        dxf_h = max(maxy - miny, 1.0)
        marg = max(max(dxf_w, dxf_h) * margin_factor, min_margin_dxf)

        if self._dxf_scene is not None:
            return _MiniDXFView(
                self._dxf_scene,
                minx - marg, miny - marg,
                maxx + marg, maxy + marg,
                thumb_w, thumb_h,
                highlight_pts=pts,
            )

        # Fallback geométrico se não houver cena
        pix = self._render_polygon_geometric(pts, thumb_w, thumb_h, fallback_line, fallback_fill)
        if pix is None:
            return None
        lbl = QLabel()
        lbl.setPixmap(pix)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background:transparent;")
        return lbl

    def _render_polygon_geometric(self, pts: list,
                                   thumb_w: int = 440, thumb_h: int = 210,
                                   line_color: str = Colors.ACCENT_MINT,
                                   fill_color: str = Surface.RAISED) -> QPixmap | None:
        """
        Fallback: desenha o polígono geometricamente (sem canvas disponível).
        Respeita dimensões retangulares thumb_w × thumb_h.
        """
        if not pts or len(pts) < 3:
            return None
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
        except Exception:
            return None

        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        margin = 10
        scale = min(
            (thumb_w - 2 * margin) / max(maxx - minx, 1.0),
            (thumb_h - 2 * margin) / max(maxy - miny, 1.0),
        )
        # Centra o polígono dentro do pixmap
        poly_w = (maxx - minx) * scale
        poly_h = (maxy - miny) * scale
        off_x = (thumb_w - poly_w) / 2.0
        off_y = (thumb_h - poly_h) / 2.0

        pixmap = QPixmap(thumb_w, thumb_h)
        pixmap.fill(QColor(Colors.BG_SECONDARY))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(line_color), 1))
        painter.setBrush(QBrush(QColor(fill_color)))

        polygon = QPolygonF()
        for x, y in zip(xs, ys):
            polygon.append(QPointF(
                off_x + (x - minx) * scale,
                thumb_h - off_y - (y - miny) * scale,  # flip Y
            ))
        painter.drawPolygon(polygon)
        # Borda
        painter.setPen(QPen(QColor(Colors.BORDER_DEFAULT), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, thumb_w - 1, thumb_h - 1)
        painter.end()
        return pixmap

    def _make_pillar_viewer(self, pts: list) -> QWidget | None:
        """Mini viewer vetorial centrado no pilar — margem ajustada para ver contexto imediato."""
        return self._make_mini_viewer(
            pts,
            thumb_w=self._PIL_THUMB_W, thumb_h=self._PIL_THUMB_H,
            margin_factor=2.5, min_margin_dxf=100.0,
            fallback_line=Colors.ACCENT_MINT, fallback_fill=Surface.RAISED,
        )

    def _make_cut_viewer(self, pts: list) -> QWidget | None:
        """Mini viewer vetorial centrado no corte de viga — margem um pouco maior para contexto."""
        return self._make_mini_viewer(
            pts,
            thumb_w=self._CUT_THUMB_W, thumb_h=self._CUT_THUMB_H,
            margin_factor=3.0, min_margin_dxf=130.0,
            fallback_line=Semantic.SUCCESS, fallback_fill=Semantic.SUCCESS_BG_DARK,
        )

    # ── Gabarito — recorte PIL do Motor Reverso ───────────────────────────────

    def _query_detail_recorte(self) -> tuple[str | None, str | None]:
        """
        Busca no DB o path do DXF recorte PIL para esta obra.
        O pavement_name dos projetos (nome do DXF) não coincide com o campo
        pavimento do reverse_eng, por isso a estratégia usa uma única conexão com
        3 tentativas ordenadas por especificidade.
        Retorna (dxf_path, elemento_id) ou (None, None).
        """
        if not self._db_path:
            return None, None
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 0ª — Tenta pegar o recorte da convencao de pilares (obra-wide: vale para todos os pavimentos)
            try:
                cur.execute(
                    "SELECT output_path FROM obra_recortes "
                    "WHERE obra_name=? AND recorte_type='convencao_pilares' AND status IN ('approved', 'manual') "
                    "ORDER BY recorte_index DESC LIMIT 1",
                    (self._obra,)
                )
                row = cur.fetchone()
                if row and row['output_path'] and os.path.isfile(row['output_path']):
                    conn.close()
                    return row['output_path'], "Convenção de Pilares"
            except Exception:
                pass

            # 0.5ª — Tenta pegar o recorte de detalhe aprovado no Diagnostic Pre Hub
            try:
                cur.execute(
                    "SELECT output_path FROM obra_recortes "
                    "WHERE obra_name=? AND pavimento_name=? AND recorte_type='detalhe' AND status IN ('approved', 'manual') "
                    "ORDER BY recorte_index LIMIT 1",
                    (self._obra, self._pavimento)
                )
                row = cur.fetchone()
                if row and row['output_path'] and os.path.isfile(row['output_path']):
                    conn.close()
                    return row['output_path'], "Detalhe"
            except Exception:
                pass

            def _first_valid(rows) -> tuple[str, str] | None:
                for r in rows:
                    p = r['recorte_path'] if 'recorte_path' in r.keys() else None
                    eid = r['elemento_id'] if 'elemento_id' in r.keys() else None
                    if p and eid and os.path.isfile(p):
                        return p, eid
                return None

            # 1ª — fichas com número do pavimento no path (ex: "- 13")
            pav_num = re.search(r'(\d+)', self._pavimento or '')
            if pav_num:
                pav_filter = f'%- {pav_num.group(1)}%'
                cur.execute("""
                    SELECT recorte_path, elemento_id FROM reverse_eng_fichas
                    WHERE obra_name = ? AND classe = 'PIL'
                      AND recorte_path IS NOT NULL
                      AND recorte_path LIKE ?
                      AND elemento_id NOT LIKE 'GRADES%'
                    ORDER BY elemento_id LIMIT 5
                """, (self._obra, pav_filter))
                hit = _first_valid(cur.fetchall())
                if hit:
                    conn.close(); return hit

                # 2ª — mesma busca em reverse_eng_recortes
                cur.execute("""
                    SELECT recorte_path, elemento_id FROM reverse_eng_recortes
                    WHERE obra_name = ? AND classe = 'PIL'
                      AND recorte_path LIKE ?
                      AND elemento_id NOT LIKE 'GRADES%'
                    ORDER BY elemento_id LIMIT 5
                """, (self._obra, pav_filter))
                hit = _first_valid(cur.fetchall())
                if hit:
                    conn.close(); return hit

            # 3ª — qualquer PIL aprovado da obra (outro pav. serve como referência visual)
            cur.execute("""
                SELECT recorte_path, elemento_id FROM reverse_eng_fichas
                WHERE obra_name = ? AND classe = 'PIL'
                  AND recorte_path IS NOT NULL
                  AND elemento_id NOT LIKE 'GRADES%'
                ORDER BY elemento_id LIMIT 10
            """, (self._obra,))
            hit = _first_valid(cur.fetchall())
            conn.close()
            if hit:
                return hit
        except Exception:
            pass
        return None, None

    def _load_dxf_to_scene(self, dxf_path: str) -> tuple['QGraphicsScene | None', tuple]:
        """
        Carrega DXF recorte em uma QGraphicsScene isolada usando ezdxf.addons.drawing.
        Retorna (scene, (x0, y0, x1, y1)) ou (None, ()).
        """
        try:
            import ezdxf
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            scene = QGraphicsScene()
            scene.setBackgroundBrush(QColor(Colors.BG_PANEL))
            
            try:
                from ezdxf.addons.drawing import RenderContext, Frontend
                from ezdxf.addons.drawing.pyqt import PyQtBackend
                from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy
                
                for layer in doc.layers:
                    layer.on()
                    layer.thaw()
                for ent in doc.entitydb.values():
                    if hasattr(ent, 'dxf') and hasattr(ent.dxf, 'invisible'):
                        ent.dxf.invisible = 0

                ctx = RenderContext(doc)
                out = PyQtBackend(scene)
                config = Configuration(
                    background_policy=BackgroundPolicy.CUSTOM,
                    custom_bg_color=Colors.BG_PANEL,
                    color_policy=ColorPolicy.COLOR,
                )
                Frontend(ctx, out, config=config).draw_layout(msp)
                
                rect = scene.itemsBoundingRect()
                if rect.isNull():
                    return None, ()
                return scene, (rect.left(), rect.top(), rect.right(), rect.bottom())
            except Exception as e:
                print(f"Fallback due to {e}")
                return None, ()
                
        except Exception as e:
            return None, ()

    def _build_detail_reference_viewer(self) -> 'QWidget | None':
        """
        Viewer central grande - recorte PIL do Motor Reverso como gabarito.
        Posicionado ACIMA da lista de termos na aba Convenção de Pilares.
        """
        dxf_path, elem_id = self._query_detail_recorte()
        if not dxf_path:
            if not self._db_path:
                return None  # silencia se DB não foi fornecido
            # Mostra aviso mas mantém espaço
            grp = QGroupBox("Gabarito - Recorte PIL (Motor Reverso)")
            lb = QLabel("Recorte não encontrado no DB para esta obra / pavimento.")
            lb.setAlignment(Qt.AlignCenter)
            lb.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:9px;")
            lb.setFixedHeight(60)
            QVBoxLayout(grp).addWidget(lb)
            return grp

        title = f"Gabarito  —  PIL '{elem_id}'  |  {self._obra} / {self._pavimento}"
        grp = QGroupBox(title)
        vbox = QVBoxLayout(grp)
        vbox.setContentsMargins(4, 8, 4, 4)
        
        loading_label = QLabel("Carregando recorte do DXF...\nIsso pode demorar alguns segundos.")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:12px; font-weight:bold;")
        vbox.addWidget(loading_label)

        # Guarda o contexto para o slot que roda na GUI thread.
        self._gab_vbox = vbox
        self._gab_loading = loading_label

        # Carrega o DXF em thread separada para não travar a GUI.
        # IMPORTANTE: o slot é um MÉTODO ligado a self (QObject que vive na GUI
        # thread). Assim o Qt resolve a conexão como QueuedConnection e executa
        # a criação de widgets SEMPRE na GUI thread. Conectar a uma função livre
        # (closure) faria o Qt usar DirectConnection -> o callback rodaria dentro
        # da worker thread, criando QWidget fora da GUI thread e travando a app.
        _dbg(f"_build_detail_reference_viewer: iniciando _DXFReaderThread para {dxf_path}")
        self._dxf_thread = _DXFReaderThread(dxf_path)
        self._dxf_thread.finished.connect(self._on_gabarito_doc_loaded)
        self._dxf_thread.start()

        return grp

    def _on_gabarito_doc_loaded(self, doc) -> None:
        """Renderiza o gabarito na GUI thread após a leitura assíncrona do DXF."""
        _dbg(f"_on_gabarito_doc_loaded INICIO doc={bool(doc)}")
        vbox = getattr(self, '_gab_vbox', None)
        loading_label = getattr(self, '_gab_loading', None)
        if vbox is None:
            self._dxf_thread = None
            return
        try:
            if loading_label is not None:
                loading_label.hide()
                vbox.removeWidget(loading_label)
            if not doc:
                err_lbl = QLabel("Falha ao ler o arquivo DXF.")
                err_lbl.setAlignment(Qt.AlignCenter)
                vbox.addWidget(err_lbl)
                return

            try:
                msp = doc.modelspace()
                scene = QGraphicsScene()
                scene.setBackgroundBrush(QColor(Colors.BG_PANEL))

                from ezdxf.addons.drawing import RenderContext, Frontend
                from ezdxf.addons.drawing.pyqt import PyQtBackend
                from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy

                for layer in doc.layers:
                    layer.on()
                    layer.thaw()
                for ent in doc.entitydb.values():
                    if hasattr(ent, 'dxf') and hasattr(ent.dxf, 'invisible'):
                        ent.dxf.invisible = 0

                ctx = RenderContext(doc)
                out = PyQtBackend(scene)
                config = Configuration(
                    background_policy=BackgroundPolicy.CUSTOM,
                    custom_bg_color=Colors.BG_PANEL,
                    color_policy=ColorPolicy.COLOR,
                )
                Frontend(ctx, out, config=config).draw_layout(msp)

                rect = scene.itemsBoundingRect()
                if rect.isNull():
                    raise ValueError("Scene is empty")

                x0, y0 = rect.left(), rect.top()
                x1, y1 = rect.right(), rect.bottom()
                _dbg("_on_gabarito_doc_loaded: criando _MiniDXFView do gabarito")
                viewer = _MiniDXFView(scene, x0, y0, x1, y1,
                                      thumb_w=800, thumb_h=250,
                                      highlight_pts=[])
                # Mantém a cena viva enquanto a view existir (evita GC da cena
                # local, que deixaria a QGraphicsView apontando para C++ morto).
                viewer._dxf_scene_ref = scene
                viewer.setMaximumWidth(16777215)
                viewer.setMinimumWidth(300)
                viewer.setMinimumHeight(200)
                viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                vbox.addWidget(viewer)
                _dbg("_on_gabarito_doc_loaded: gabarito adicionado OK")
            except Exception as e:
                err_lbl = QLabel(f"Falha ao renderizar gabarito: {e}")
                err_lbl.setAlignment(Qt.AlignCenter)
                vbox.addWidget(err_lbl)
        finally:
            # Libera o contexto e a referência da thread (já terminou).
            self._gab_vbox = None
            self._gab_loading = None
            self._dxf_thread = None

    # ── Convenção salva ────────────────────────────────────────────────────────

    def _find_term_example_pts(self, term: str) -> list | None:
        """Retorna pontos do primeiro pilar com essa classificação no relatório atual."""
        tu = term.upper()
        for data in self._pillar_report.values():
            if (data.get('classification') or '').upper() == tu:
                pts = data.get('points') or []
                if len(pts) >= 2:
                    return pts
        return None

    def _load_saved_convention(self, path: str) -> None:
        """Carrega convenção salva em JSON e aplica ao _term_type_map."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for term, phys in (data.get('term_map') or {}).items():
                if any(k == phys for k, _ in PHYSICAL_TYPES):
                    self._term_type_map[term.upper()] = phys
            self._saved_term_examples = {
                k.upper(): v
                for k, v in (data.get('term_examples') or {}).items()
            }
        except Exception:
            pass

    def _save_convention(self) -> None:
        """Persiste _term_type_map + exemplos de pts para cada termo no arquivo JSON."""
        if not self._convention_file:
            return
        term_examples: dict[str, list | None] = {}
        for term in self._term_type_map:
            term_examples[term] = self._find_term_example_pts(term)
        # Incorpora exemplos salvos de outros pavimentos que não estão no atual
        for term, pts in self._saved_term_examples.items():
            if term not in term_examples or not term_examples[term]:
                term_examples[term] = pts
        data = {
            'obra':          self._obra,
            'saved_at':      datetime.now().isoformat(timespec='seconds'),
            'term_map':      dict(self._term_type_map),
            'term_examples': term_examples,
        }
        try:
            os.makedirs(os.path.dirname(self._convention_file), exist_ok=True)
            with open(self._convention_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            if self._btn_save_conv:
                self._btn_save_conv.setText("  Convenção Salva ✓  ")
                self._btn_save_conv.setEnabled(False)
                def _restore_btn(b=self._btn_save_conv):
                    b.setText("  Salvar Convenção ↓  ")
                    b.setEnabled(True)
                QTimer.singleShot(2500, _restore_btn)
        except Exception as e:
            if self._btn_save_conv:
                self._btn_save_conv.setText(f"  Erro: {e}  ")

    # ── Histórico de pré-ficha (por geometria) ────────────────────────────────

    def _resolve_history_path(self) -> str | None:
        """Retorna path do JSON de histórico ao lado do convention_file (mesma pasta)."""
        base = None
        if self._convention_file:
            base = os.path.dirname(self._convention_file)
        elif self._db_path:
            base = os.path.dirname(self._db_path)
        if not base:
            return None
        pav_slug = re.sub(r'[^\w\-]', '_', self._pavimento)[:60]
        return os.path.join(base, f'preficha_history_{pav_slug}.json')

    @staticmethod
    def _pillar_geo_key(pillar: dict) -> str:
        """Chave geométrica de pilar: bbox arredondada a 1 decimal."""
        bbox = pillar.get('bbox') or []
        if len(bbox) < 4:
            return ''
        return ','.join(f'{round(float(v), 1)}' for v in bbox[:4])

    @staticmethod
    def _cv_geo_key(pts: list) -> str:
        """Chave geométrica de corte: centro do polígono arredondado a 0.5u."""
        if not pts:
            return ''
        cx = sum(float(p[0]) for p in pts) / len(pts)
        cy = sum(float(p[1]) for p in pts) / len(pts)
        return f'{round(cx * 2) / 2},{round(cy * 2) / 2}'

    def _load_pf_history(self) -> dict:
        """Carrega histórico salvo; retorna dict vazio se não existir."""
        if not self._history_path or not os.path.isfile(self._history_path):
            return {'pilares': {}, 'cut_views': {}, 'beam_segments': {}, 'ui_state': {}}
        try:
            with open(self._history_path, encoding='utf-8') as f:
                data = json.load(f)
            return {
                'pilares':   data.get('pilares', {}),
                'cut_views': data.get('cut_views', {}),
                'beam_segments': data.get('beam_segments', {}),
                'ui_state': data.get('ui_state', {}),
            }
        except Exception:
            return {'pilares': {}, 'cut_views': {}, 'beam_segments': {}, 'ui_state': {}}

    def _save_pf_history(self) -> None:
        """Persiste estado atual dos combos de pilar e corte, keyed por geometria."""
        if not self._history_path:
            return
        pilares: dict = dict(self._pf_history.get('pilares', {}))
        cut_views: dict = dict(self._pf_history.get('cut_views', {}))
        beam_segments: dict = dict(self._pf_history.get('beam_segments', {}))
        now = datetime.now().isoformat(timespec='seconds')

        # Pilares
        for key, pillar in self._pillar_report.items():
            geo = self._pillar_geo_key(pillar)
            if not geo:
                continue
            combo = self._pillar_combos.get(key)
            classif = combo.currentText() if combo else (pillar.get('classification') or '')
            pilares[geo] = {
                'geo_key':      geo,
                'last_name':    key,
                'classification': classif,
                'physical_type': self._physical_type_for(classif),
                'attention': self._atencao_notes.get(
                    key, (self._pf_history.get('pilares', {}).get(geo, {}) or {}).get('attention', '')
                ),
                'saved_at':     now,
            }

        # Cortes de viga
        for cut in self._cut_view_data:
            geo = self._cv_geo_key(cut.get('pts', []))
            if not geo:
                continue
            uid = cut['uid']
            beam_combo   = self._cut_combos.get(uid)
            status_combo = self._cut_status_combos.get(uid)
            beam_name = beam_combo.currentData() if beam_combo else ''
            beam_text = beam_combo.currentText() if beam_combo else ''
            status    = status_combo.currentData() if status_combo else 'ok'
            prev_entry = cut_views.get(geo, {})
            entry = {
                'geo_key':    geo,
                'beam_name':  beam_name or beam_text,
                'status':     status,
                'own_laje':   cut.get('own_laje', ''),
                'attention':  self._cut_attention.get(uid, (prev_entry or {}).get('attention', '')),
                'saved_at':   now,
            }
            # Preserva dados de migração pilar se já existiam (ou foram recém-gravados)
            in_mem = self._pf_history.get('cut_views', {}).get(geo, {})
            if in_mem.get('pillar_migrated'):
                entry['pillar_migrated'] = True
                entry['pillar_name']     = in_mem.get('pillar_name', '')
            elif prev_entry.get('pillar_migrated'):
                entry['pillar_migrated'] = True
                entry['pillar_name']     = prev_entry.get('pillar_name', '')
            cut_views[geo] = entry

        # Segmentos de vigas: UID semantico estavel (tipo|viga|indice|ocorrencia).
        for entries in self._segment_data.values():
            for segment in entries:
                uid = segment['uid']
                combo = self._segment_status_combos.get(uid)
                status = combo.currentData() if combo else segment.get('status', 'valid')
                attention = self._segment_attention.get(uid, segment.get('attention', ''))
                beam_segments[uid] = {
                    'status': status or 'valid',
                    'attention': attention,
                    'source_key': segment.get('source_key', ''),
                    'saved_at': now,
                }

        scroll_positions = dict(self._saved_scroll_positions)
        table_specs = [
            ('pilares', getattr(self, '_pillar_table', None)),
            ('visao_cortes', getattr(self, '_cut_table', None)),
        ]
        table_specs.extend((kind, table) for kind, table in self._segment_tables.items())
        for state_key, table in table_specs:
            if table is not None:
                scroll_positions[state_key] = table.verticalScrollBar().value()

        data = {
            'version':   3,
            'obra':      self._obra,
            'pavimento': self._pavimento,
            'saved_at':  now,
            'pilares':   pilares,
            'cut_views': cut_views,
            'beam_segments': beam_segments,
            'ui_state': {
                'active_tab': getattr(self, '_active_tab_index', 0),
                'scroll_positions': scroll_positions,
            },
        }
        try:
            os.makedirs(os.path.dirname(self._history_path), exist_ok=True)
            with open(self._history_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _make_conv_placeholder(self, w: int, h: int, text: str = "Sem exemplo") -> QLabel:
        lb = QLabel(text)
        lb.setAlignment(Qt.AlignCenter)
        lb.setFixedSize(w, h)
        lb.setWordWrap(True)
        lb.setStyleSheet(
            f"font-size:8px; color:{Colors.TEXT_MUTED}; "
            f"border:1px solid {Colors.BORDER_DEFAULT}; "
            f"background:{Colors.BG_PANEL};"
        )
        return lb

    def _make_conv_viewer_for_term(self, term: str, w: int = 190, h: int = 85) -> QWidget:
        """
        Mini viewer para o painel de convenção.
        Prioridade:
          1. Pilar do relatório atual → usa cena do canvas (coordenadas corretas)
          2. Exemplo salvo de outro pavimento → cena autônoma com só o polígono
          3. Fallback: placeholder de texto
        """
        # 1. Relatório atual
        pts = self._find_term_example_pts(term)
        if pts and self._dxf_scene:
            return self._make_mini_viewer(
                pts, thumb_w=w, thumb_h=h,
                margin_factor=2.0, min_margin_dxf=80.0,
                fallback_line=Colors.ACCENT_MINT, fallback_fill=Surface.RAISED,
            ) or self._make_conv_placeholder(w, h, "Sem canvas")

        # 2. Exemplo salvo (outro pavimento) — cena autônoma
        saved_pts = self._saved_term_examples.get(term.upper())
        if saved_pts and len(saved_pts) >= 2:
            try:
                xs = [float(p[0]) for p in saved_pts]
                ys = [float(p[1]) for p in saved_pts]
                bx0, bx1 = min(xs), max(xs)
                by0, by1 = min(ys), max(ys)
                margin = max(80.0, max(bx1 - bx0, by1 - by0) * 2.0)
                vx0, vx1 = bx0 - margin, bx1 + margin
                vy0, vy1 = by0 - margin, by1 + margin
                scene = QGraphicsScene()
                scene.setSceneRect(vx0, vy0, vx1 - vx0, vy1 - vy0)
                scene.setBackgroundBrush(QColor(Colors.BG_PANEL))
                viewer = _MiniDXFView(scene, vx0, vy0, vx1, vy1, w, h,
                                      highlight_pts=saved_pts)
                viewer.setToolTip("Referência salva de outro pavimento")
                return viewer
            except Exception:
                pass

        # 3. Placeholder
        if self._convention_file:
            return self._make_conv_placeholder(w, h, "Sem exemplo\nneste pav.")
        return self._make_conv_placeholder(w, h, "Sem exemplo")

    def _build_initial_term_map(self) -> dict[str, str]:
        """
        Constrói mapa termo→tipo_físico combinando:
        - termos padrão (STANDARD_TERM_MAP)
        - termos detectados na convenção da obra
        """
        result: dict[str, str] = dict(STANDARD_TERM_MAP)
        for term, info in self._convention.items():
            term_upper = str(term).upper()
            if term_upper not in result:
                # Tenta mapear por similaridade de assinatura geométrica
                sig = info.get('sig', '') if isinstance(info, dict) else ''
                if sig == 'EMPTY':
                    result[term_upper] = 'visual_only'    # sem hachura = nasce
                elif sig in ('CROSS', 'DIAG'):
                    result[term_upper] = 'solid'
                else:
                    result[term_upper] = 'unknown'
        return result

    # Direções opostas para calcular o lado da Laje 2
    _DIR_OPPOSITE: dict[str, str] = {
        'SUL': 'NORTE', 'NORTE': 'SUL',
        'LESTE': 'OESTE', 'OESTE': 'LESTE',
        'S': 'N', 'N': 'S', 'L': 'O', 'O': 'L',
        'E': 'W', 'W': 'E',
    }

    # Mapeamento direcao -> (own_lado, neigh_lado)
    # Viga Horizontal (corte N-S): Sul=A (baixo), Norte=B (cima)
    # Viga Vertical   (corte E-W): Oeste=A (esq), Leste=B (dir)
    _DIR_TO_LADO: dict[str, tuple[str, str]] = {
        'NORTE': ('A', 'B'),  # own=Sul(A), neigh=Norte(B)
        'SUL':   ('B', 'A'),  # own=Norte(B), neigh=Sul(A)
        'LESTE': ('A', 'B'),  # own=Oeste(A), neigh=Leste(B)
        'OESTE': ('B', 'A'),  # own=Leste(B), neigh=Oeste(A)
    }

    @staticmethod
    def _dir_beam_type(direction: str) -> str:
        """'H' para viga horizontal (corte N-S), 'V' para vertical (corte E-W)."""
        d = str(direction or '').upper()
        return 'H' if d in ('NORTE', 'SUL', 'N', 'S') else 'V'

    def _compute_nivel_viga(self, cut: dict) -> str:
        """
        Nível da viga = max(nivel_laje + dist_topo) considerando Lado A e Lado B.
        A laje que atingir o maior nível define o nível da viga.
        Retorna '⚠' quando ambas as lajes têm nivel suspeito (impossível calcular).
        """
        best: float | None = None
        has_suspect = False
        for laje_name, dist_top_str in (
            (cut.get('own_laje', ''), cut.get('own_dist_top', '—')),
            (cut.get('neigh_laje', ''), cut.get('neigh_dist_top', '—')),
        ):
            if not laje_name or laje_name in ('—', 'nulo', 'NULO', ''):
                continue
            nivel_str = self._slab_nivel_map.get(laje_name, '')
            if not nivel_str:
                continue
            if nivel_str == '⚠':
                has_suspect = True
                continue
            try:
                nivel = float(nivel_str)
                dt = float(dist_top_str) if dist_top_str not in ('—', None, '') else 0.0
                val = nivel + dt
                if best is None or val > best:
                    best = val
            except (ValueError, TypeError):
                pass
        if best is not None:
            return f"{best:.2f}"
        return '⚠' if has_suspect else '—'

    def _build_segmento_viga_widget(self, cut: dict) -> QLabel:
        """
        Fichinha 'Detalhes sobre o Segmento de Viga' exibida na col DIM da tabela.
        Inclui: nome, segmento (placeholder), largura, altura, nível, e blocos Lado A/B
        com painéis (H1 = dist_fundo−2+4, H2 = dist_topo) e posição da laje.
        """
        ficha = cut.get('ficha') or {}
        direction = cut.get('direction') or '—'

        # Resolve Lado A / Lado B
        own_lado = cut.get('own_lado', 'A')
        if own_lado != 'B':
            laje_a  = cut.get('own_laje', '—')
            laje_b  = cut.get('neigh_laje', '—')
            sh_a    = cut.get('own_slab_h', '—')
            dt_a    = cut.get('own_dist_top', '—')
            df_a    = cut.get('own_dist_bot', '—')
            df_cp_a = ficha.get('own_dist_bottom_c_painel', '—')
            scp_a   = ficha.get('own_slab_ref_c_painel', '—')
            sh_b    = cut.get('neigh_slab_h', '—')
            dt_b    = cut.get('neigh_dist_top', '—')
            df_b    = cut.get('neigh_dist_bot', '—')
            df_cp_b = ficha.get('neighbor_dist_bottom_c_painel', '—')
            scp_b   = ficha.get('neigh_slab_ref_c_painel', '—')
        else:
            laje_a  = cut.get('neigh_laje', '—')
            laje_b  = cut.get('own_laje', '—')
            sh_a    = cut.get('neigh_slab_h', '—')
            dt_a    = cut.get('neigh_dist_top', '—')
            df_a    = cut.get('neigh_dist_bot', '—')
            df_cp_a = ficha.get('neighbor_dist_bottom_c_painel', '—')
            scp_a   = ficha.get('neigh_slab_ref_c_painel', '—')
            sh_b    = cut.get('own_slab_h', '—')
            dt_b    = cut.get('own_dist_top', '—')
            df_b    = cut.get('own_dist_bot', '—')
            df_cp_b = ficha.get('own_dist_bottom_c_painel', '—')
            scp_b   = ficha.get('own_slab_ref_c_painel', '—')

        bh = cut.get('beam_h', '—')
        bw = cut.get('beam_w', '—')
        tipo = 'Horiz.' if self._dir_beam_type(direction) == 'H' else 'Vert.'
        beam_name_f = ficha.get('beam_name') or cut.get('beam_name') or '—'
        nivel_viga  = self._compute_nivel_viga(cut)

        CL = Text.SECONDARY   # muted
        CV = Text.PRIMARY     # valor padrão
        CM = Accent.PRIMARY   # mint — Lado A
        CB = Accent.INTERACTIVE  # azul — Lado B
        CG = Semantic.WARNING # dourado — nome da viga

        def _kv(k: str, v: str, vc: str = CV, bold: bool = False) -> str:
            b, eb = ('<b>', '</b>') if bold else ('', '')
            return (f"<span style='color:{CL}'>{k}</span>"
                    f"&nbsp;<span style='color:{vc}'>{b}{v}{eb}</span>")

        def _pos_lbl(dt_s, df_s) -> str:
            try:
                dt = float(dt_s) if dt_s not in ('—', None, '') else None
                df = float(df_s) if df_s not in ('—', None, '') else None
            except (ValueError, TypeError):
                return '—'
            if dt is None or df is None:
                return '—'
            if abs(dt) < 0.5:
                return 'Topo'
            if abs(df) < 0.5:
                return 'Fundo'
            return 'Central'

        def _laje_dim(pos: str, sh_s: str, scp_s: str) -> tuple[str, str]:
            """Retorna (valor, sufixo) para a dimensão da laje."""
            try:
                h = float(sh_s) if sh_s not in ('—', '', None, 'nulo') else None
            except (ValueError, TypeError):
                h = None
            if h is None:
                return '—', ''
            if pos == 'Fundo':
                return f"{h:.0f}", 'cm'
            val = scp_s if scp_s not in ('—', '', None) else f"{h + 2.0:.0f}"
            return val, 'cm (+2 painel)'

        def _side_html(lado: str, laje: str, sh: str, dt: str, df: str,
                       df_cp: str, scp: str, color: str) -> str:
            wall = not laje or laje in ('—', 'nulo', 'NULO', '')
            title = (f"<b style='color:{color}'>── LADO {lado}</b>"
                     f"&nbsp;<span style='color:{color}'>{laje if not wall else '(parede)'}</span>")
            if wall:
                return title
            pos = _pos_lbl(dt, df)
            lv, lsfx = _laje_dim(pos, sh, scp)
            h1 = df_cp if df_cp not in ('—', '', None) else '—'
            h2 = dt if dt not in ('—', '', None) else '—'
            return '<br>'.join([
                title,
                f"&nbsp;&nbsp;<b style='color:{color}'>Painéis</b>",
                f"&nbsp;&nbsp;&nbsp;{_kv('H1 (fundo−2+4):', str(h1))} cm",
                f"&nbsp;&nbsp;&nbsp;{_kv('H2 (topo):', str(h2))} cm",
                f"&nbsp;&nbsp;<b style='color:{color}'>Laje&nbsp;—&nbsp;{pos}</b>",
                f"&nbsp;&nbsp;&nbsp;{_kv(pos + ':', lv)} {lsfx}",
            ])

        nv_color = Semantic.DANGER if nivel_viga == '⚠' else CM
        nv_text  = '⚠ suspeito (laje c/ nivel inválido)' if nivel_viga == '⚠' else nivel_viga

        sep = f"<hr style='border:none; border-top:1px solid {Border.DEFAULT}; margin:2px 0;'>"
        html = (
            "<div style='font-size:9px; line-height:1.45; padding:3px;'>"
            f"{_kv('Nome:', beam_name_f, CG, bold=True)}<br>"
            f"{_kv('Segmento:', '—', CL)}<br>"
            f"{_kv('Largura:', str(bw))} cm"
            f"&nbsp;&nbsp;<span style='color:{CL}'>{tipo}</span><br>"
            f"{_kv('Altura:', str(bh))} cm<br>"
            f"{_kv('Nível viga:', nv_text, nv_color)}"
            f"{sep}"
            f"{_side_html('A', laje_a, sh_a, dt_a, df_a, df_cp_a, scp_a, CM)}"
            f"{sep}"
            f"{_side_html('B', laje_b, sh_b, dt_b, df_b, df_cp_b, scp_b, CB)}"
            "</div>"
        )
        lbl = QLabel(html)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        lbl.setStyleSheet('background:transparent;')
        lbl.setTextFormat(Qt.RichText)
        return lbl

    def _find_neighbor_laje(self, cx: float, cy: float,
                             own_laje: str, direction: str,
                             probe_dist: float = 150.0) -> str:
        """
        Fallback espacial: procura a laje vizinha sondando um ponto deslocado
        na direção OPOSTA à 'direction' (que indica de qual lado está a Laje 1).
        """
        _offsets: dict[str, tuple[float, float]] = {
            'SUL':   ( 0.0,  probe_dist),   # Laje 1 ao sul → vizinha ao norte (+Y)
            'NORTE': ( 0.0, -probe_dist),
            'LESTE': (-probe_dist,  0.0),
            'OESTE': ( probe_dist,  0.0),
            'S': ( 0.0,  probe_dist), 'N': ( 0.0, -probe_dist),
            'L': (-probe_dist,  0.0), 'O': ( probe_dist,  0.0),
            'E': (-probe_dist,  0.0), 'W': ( probe_dist,  0.0),
        }
        dx, dy = _offsets.get(direction.upper(), (0.0, 0.0))
        if dx == 0 and dy == 0:
            return '—'
        for scale in (1.0, 1.5, 2.0, 0.5, 3.0):
            px, py = cx + dx * scale, cy + dy * scale
            for name, poly in self._slab_poly_map.items():
                if name == own_laje:
                    continue
                if self._point_in_polygon(px, py, poly):
                    return name
        return '—'

    def _collect_cut_views(self) -> list[dict]:
        """
        Coleta cortes de viga de todas as lajes.

        Detecção da Laje Vizinha (em ordem de prioridade):
          1. ficha.get('side_a_laje_name')
          2. Mapa cruzado: mesmo corte aparece na lista de outra laje
          3. Sondagem espacial na direção oposta
        """
        # ── Passagem 1: mapa centro → lajes que o contêm ─────────────────────
        center_to_slabs: dict[str, list[str]] = {}
        for slab in self._slabs:
            sn = slab.get('name') or ''
            cut_links = (slab.get('links') or {}).get('laje_visao_corte', {})
            if not isinstance(cut_links, dict):
                continue
            for cut in cut_links.get('cut_view_geom', []) or []:
                pts = cut.get('points') or []
                try:
                    xs = [float(p[0]) for p in pts]
                    ys = [float(p[1]) for p in pts]
                    ck = f"{round((min(xs)+max(xs))/2.0, -1)}_{round((min(ys)+max(ys))/2.0, -1)}"
                except Exception:
                    continue
                if ck not in center_to_slabs:
                    center_to_slabs[ck] = []
                if sn and sn not in center_to_slabs[ck]:
                    center_to_slabs[ck].append(sn)

        # ── Passagem 2: constrói lista de cortes ──────────────────────────────
        cuts: list[dict] = []
        seen: set[str] = set()          # uid = slab_cx_cy (para assignment)
        pos_seen: set[str] = set()      # cx_cy apenas (dedup de geometria repetida em >1 laje)

        for slab in self._slabs:
            slab_name = slab.get('name') or '?'
            cut_links = (slab.get('links') or {}).get('laje_visao_corte', {})
            if not isinstance(cut_links, dict):
                continue
            for i, cut in enumerate(cut_links.get('cut_view_geom', []) or []):
                if not isinstance(cut, dict):
                    continue
                pts  = cut.get('points') or []
                ficha = cut.get('ficha') or {}
                try:
                    xs = [float(p[0]) for p in pts]
                    ys = [float(p[1]) for p in pts]
                    cx = (min(xs) + max(xs)) / 2.0
                    cy = (min(ys) + max(ys)) / 2.0
                    uid = f"{slab_name}_{round(cx)}_{round(cy)}"
                    ck  = f"{round(cx, -1)}_{round(cy, -1)}"
                    pos_key = f"{round(cx, 0)}_{round(cy, 0)}"
                except Exception:
                    cx = cy = 0.0
                    uid = f"{slab_name}_{i}"
                    ck  = uid
                    pos_key = uid

                if uid in seen:
                    continue
                seen.add(uid)

                # Mesmo polígono T pode estar em >1 laje — exibe apenas uma vez.
                # Prefere o que veio da laje cujo slab_name é Lado A (mais informativo).
                side_a_name = ficha.get('side_a_laje_name') or ''
                side_b_name = ficha.get('side_b_laje_name') or ''
                current_is_a = (slab_name == side_a_name)

                if pos_key in pos_seen:
                    # Já exibido — substitui apenas se este é o lado canônico (A).
                    if not current_is_a:
                        continue
                    # É Lado A: substitui o registro existente (removido ao final).
                    cuts = [c for c in cuts if c.get('_pos_key') != pos_key]
                pos_seen.add(pos_key)

                direction = ficha.get('direction') or '—'

                # own_laje é SEMPRE a laje sobre a qual estamos iterando.
                # neigh_laje é o outro lado.
                own_laje = slab_name
                if current_is_a:
                    neigh_laje = side_b_name or ''
                else:
                    neigh_laje = side_a_name or ''

                # Fallback espacial quando a ficha não tem o vizinho preenchido
                if not neigh_laje or neigh_laje in ('nulo', 'NULO', '—'):
                    others = [s for s in center_to_slabs.get(ck, []) if s != own_laje]
                    if others:
                        neigh_laje = others[0]
                if (not neigh_laje or neigh_laje in ('nulo', 'NULO', '—')) \
                        and direction not in ('—', ''):
                    neigh_laje = self._find_neighbor_laje(cx, cy, own_laje, direction)
                if not neigh_laje:
                    neigh_laje = '—'

                # Distâncias: topo e fundo para cada laje
                # own_dist_top  = dist laje_topo -> topo_viga (0 se nivelado no topo)
                # own_dist_bot  = dist fundo_viga -> fundo_laje
                beam_h_raw     = ficha.get('beam_height') or '—'
                own_dist_top   = ficha.get('own_dist_top') or '—'
                neigh_dist_top = ficha.get('neighbor_dist_top') or '—'
                # Lê diretamente da ficha (valores geometricos corretos)
                own_dist_bot   = ficha.get('own_dist_bottom') or '—'
                neigh_dist_bot = ficha.get('neighbor_dist_bottom') or '—'

                own_lado = self._DIR_TO_LADO.get(direction.upper(), ('A', 'B'))[0]
                beam_name, conf_pct, candidates = self._associate_beam_name(cx, cy, ficha)
                cuts.append({
                    '_pos_key':      pos_key,   # chave interna de dedup geométrico
                    'uid':           uid,
                    'slab_name':     slab_name,
                    'pts':           pts,
                    'center':        (cx, cy),
                    'ficha':         ficha,
                    'beam_name':     beam_name,
                    'conf_pct':      conf_pct,
                    'candidates':    candidates,
                    'direction':     direction,
                    'own_lado':      own_lado,
                    'beam_h':        beam_h_raw,
                    'beam_w':        ficha.get('beam_bottom_dim') or '—',
                    'scale_v':       ficha.get('scale_v') or '1.0',
                    'own_laje':      own_laje,
                    'neigh_laje':    neigh_laje,
                    'own_pos':       ficha.get('own_position') or '—',
                    'neigh_pos':     ficha.get('neighbor_position') or '—',
                    'own_dist_top':  own_dist_top,
                    'own_dist_bot':  own_dist_bot,
                    'neigh_dist_top': neigh_dist_top,
                    'neigh_dist_bot': neigh_dist_bot,
                    'own_slab_h':    ficha.get('own_slab_height') or '—',
                    'neigh_slab_h':  ficha.get('neigh_slab_height') or ficha.get('neighbor_slab_height') or '—',
                })
        return cuts

    def _associate_beam_name(self, cx: float, cy: float,
                              ficha: dict) -> tuple[str, int, list[dict]]:
        """
        Encontra o nome de viga mais provável para um corte em (cx, cy).
        Retorna (beam_name, confidence_pct, candidates_sorted_by_dist).
        """
        if not self._beam_texts:
            return '', 0, []

        scored: list[tuple[float, dict]] = []
        for bt in self._beam_texts:
            pos = bt.get('pos') or [0, 0]
            try:
                dx = float(pos[0]) - cx
                dy = float(pos[1]) - cy
                dist = math.sqrt(dx * dx + dy * dy)
            except Exception:
                continue
            if dist <= MAX_ASSOC_DIST:
                scored.append((dist, bt))

        scored.sort(key=lambda x: x[0])
        candidates = [
            {'text': bt.get('text', ''), 'dist': round(d, 1),
             'pos': bt.get('pos'), 'conf_pct': int(max(0, 1 - d / MAX_ASSOC_DIST) * 100)}
            for d, bt in scored[:8]
        ]

        if candidates:
            best = candidates[0]
            return best['text'], best['conf_pct'], candidates

        # Sem candidatos dentro do raio → retorna string vazia, confiança 0
        return '', 0, []

    # ── Construção UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Header
        root.addWidget(self._build_header())

        # Tabs — lazy loading: conteúdo só é construído ao selecionar a aba
        self._tabs = QTabWidget()
        tab_titles = [
            "  Convenção de Pilares  ",
            "  Pilares  ",
            "  Visão de Cortes  ",
            "  Segmentos Fundos  ",
            "  Segmentos Lateral A Para  ",
            "  Segmentos Lateral B Para  ",
            "  Segmentos Lateral A Passa  ",
            "  Segmentos Lateral B Passa  ",
            "  Convenção de Níveis  ",
            "  Pilares Especiais  ",
        ]
        self._tab_loaded: dict[int, bool] = {idx: False for idx in range(len(tab_titles))}

        # Placeholders leves (QWidget vazio com loading label)
        for idx, title in enumerate(tab_titles):
            placeholder = QWidget()
            placeholder_lay = QVBoxLayout(placeholder)
            placeholder_lay.setContentsMargins(0, 0, 0, 0)
            loading = QLabel("Carregando...")
            loading.setAlignment(Qt.AlignCenter)
            loading.setStyleSheet(
                f"color:{Colors.TEXT_MUTED}; font-size:14px; font-weight:bold; padding:40px;"
            )
            placeholder_lay.addWidget(loading)
            self._tabs.addTab(placeholder, title)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tabs, 1)

        # Footer
        root.addWidget(self._build_footer())

        # Restaura a última aba da sessão sem construir as demais.
        def _restore_active_tab():
            index = getattr(self, '_active_tab_index', 0)
            self._tabs.setCurrentIndex(index)
            self._on_tab_changed(index)  # necessário quando index == 0 (sem sinal Qt)
        QTimer.singleShot(50, _restore_active_tab)

    def _on_tab_changed(self, index: int) -> None:
        """Lazy-load: constrói o conteúdo da aba apenas na primeira vez que é selecionada."""
        self._active_tab_index = index
        # Aba oculta não mantém QGraphicsView vivo. O scroll/tabela permanecem.
        QTimer.singleShot(0, self._deactivate_hidden_viewers)
        if self._tab_loaded.get(index, True):
            QTimer.singleShot(0, self._trigger_dynamic_viewers_for_visible_tab)
            return  # já carregada; sessão e scroll foram preservados
        self._tab_loaded[index] = True

        builders = {
            0: self._build_convention_tab,
            1: self._build_pillars_tab,
            2: self._build_cut_views_tab,
            3: lambda: self._build_segment_tab('fundo'),
            4: lambda: self._build_segment_tab('lateral_a_para'),
            5: lambda: self._build_segment_tab('lateral_b_para'),
            6: lambda: self._build_segment_tab('lateral_a_passa'),
            7: lambda: self._build_segment_tab('lateral_b_passa'),
            8: self._build_niveis_tab,
            9: self._build_especiais_tab,
        }
        builder = builders.get(index)
        if not builder:
            return

        old_widget = self._tabs.widget(index)
        tab_text = self._tabs.tabText(index)
        
        # Show a loading placeholder instantly
        loading_lbl = QLabel("Montando elementos da tabela (isso pode levar alguns segundos)...")
        loading_lbl.setAlignment(Qt.AlignCenter)
        loading_lbl.setStyleSheet("font-size: 14px; color: gray;")
        
        self._tabs.blockSignals(True)
        self._tabs.removeTab(index)
        self._tabs.insertTab(index, loading_lbl, tab_text)
        self._tabs.setCurrentIndex(index)
        self._tabs.blockSignals(False)
        
        if old_widget:
            old_widget.deleteLater()

        def _do_build():
            try:
                _dbg(f"_do_build INICIO tab={index}")
                new_widget = builder()
                _dbg(f"_do_build builder() OK tab={index}")
                self._tabs.blockSignals(True)
                self._tabs.removeTab(index)
                self._tabs.insertTab(index, new_widget, tab_text)
                self._tabs.setCurrentIndex(index)
                _dbg(f"_do_build insertTab+setCurrentIndex OK tab={index}")

                # Trigger lazy loader after a short delay so layout is done
                QTimer.singleShot(100, self._trigger_dynamic_viewers_for_visible_tab)
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_lbl = QLabel(f"❌ Erro crítico ao montar aba:\n{e}\n\nO erro foi reportado no terminal.")
                error_lbl.setAlignment(Qt.AlignCenter)
                error_lbl.setStyleSheet("font-size: 14px; color: red;")
                self._tabs.blockSignals(True)
                self._tabs.removeTab(index)
                self._tabs.insertTab(index, error_lbl, tab_text)
                self._tabs.setCurrentIndex(index)
            finally:
                self._tabs.blockSignals(False)
                loading_lbl.deleteLater()

        # Defer construction so PySide6 renders the loading label first
        QTimer.singleShot(50, _do_build)

    def _trigger_dynamic_viewers_for_visible_tab(self):
        # Recarrega exclusivamente as linhas visíveis da aba atual.
        # Pilares
        if getattr(self, '_pillar_table', None) and self._pillar_table.isVisible():
            self._update_dynamic_viewers(self._pillar_table, getattr(self, '_pillar_viewer_data', {}), self._PIL_COL_FOTO, False)
        # Visão de Corte
        if getattr(self, '_cut_table', None) and self._cut_table.isVisible():
            self._update_dynamic_viewers(self._cut_table, getattr(self, '_cut_viewer_data', {}), self._CUT_COL_FOTO, True)
        # Segmentos de vigas: cada aba mantem apenas os viewers das linhas visiveis.
        for kind, table in self._segment_tables.items():
            if table.isVisible():
                self._update_dynamic_viewers(
                    table,
                    self._segment_viewer_data.get(kind, {}),
                    table.property('viewer_column'),
                    True,
                )

    def _dynamic_viewer_tables(self):
        pillar_table = getattr(self, '_pillar_table', None)
        if pillar_table is not None:
            yield pillar_table, getattr(self, '_pillar_viewer_data', {}), self._PIL_COL_FOTO
        cut_table = getattr(self, '_cut_table', None)
        if cut_table is not None:
            yield cut_table, getattr(self, '_cut_viewer_data', {}), self._CUT_COL_FOTO
        for kind, table in self._segment_tables.items():
            yield table, self._segment_viewer_data.get(kind, {}), int(table.property('viewer_column'))

    def _deactivate_hidden_viewers(self) -> None:
        """Destrói viewers de abas ocultas, mantendo dados, scroll e edições."""
        for table, data_dict, column in self._dynamic_viewer_tables():
            if table.isVisible():
                continue
            self._unload_dynamic_viewers(table, data_dict, column)

    def _unload_dynamic_viewers(self, table: QTableWidget, data_dict: dict, column: int) -> None:
        for row in data_dict:
            widget = table.cellWidget(row, column)
            if not isinstance(widget, _MiniDXFView):
                continue
            placeholder = QLabel("⏳ Rolar para carregar")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:10px;")
            table.setCellWidget(row, column, placeholder)

    def _restore_table_scroll(self, table: QTableWidget, state_key: str) -> None:
        value = int(self._saved_scroll_positions.get(state_key, 0) or 0)
        QTimer.singleShot(0, lambda: table.verticalScrollBar().setValue(value))


    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background:{Colors.BG_SECONDARY}; border-radius:4px; padding:4px; }}"
        )
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(8, 4, 8, 4)

        n_lajes = len(self._slabs)
        n_pilares = len(self._pillar_report)
        n_cuts = len(self._cut_view_data)
        nr_sum = (self._nivel_report or {}).get('summary', {})
        n_conf = nr_sum.get('confirmed', 0)
        n_inf = nr_sum.get('inferred', 0)

        # Coleta nomes reais das lajes suspeitas (com warning de alucinação)
        lajes_nr = (self._nivel_report or {}).get('lajes', {})
        suspect_names = sorted(
            name for name, entry in lajes_nr.items()
            if any('alucinacao' in w.lower() or 'diverge' in w.lower()
                   for w in (entry.get('warnings') or []))
        )
        n_hall = len(suspect_names)

        def _chip(text: str, color: str, tooltip: str = '') -> QLabel:
            lb = QLabel(text)
            lb.setStyleSheet(f"color:{color}; font-size:10px; font-weight:bold; padding:2px 8px;")
            if tooltip:
                lb.setToolTip(tooltip)
            return lb

        lay.addWidget(_chip(f"{n_lajes} lajes", Semantic.SUCCESS))
        lay.addWidget(_chip(f"{n_conf} níveis confirmados / {n_inf} inferidos", Semantic.SUCCESS))
        if n_hall:
            tip = "Lajes com nível suspeito de alucinação:\n" + "\n".join(
                f"  • {nm}: {lajes_nr[nm].get('level_str','?')}"
                for nm in suspect_names
            )
            lbl = _chip(f"⚠ {n_hall} suspeitos de nível: {', '.join(suspect_names)}", Semantic.DANGER, tip)
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        lay.addWidget(_chip(f"{n_pilares} pilares", Semantic.WARNING))
        lay.addWidget(_chip(f"{n_cuts} cortes de viga", Text.SECONDARY))
        lay.addStretch()
        return frame

    def _build_footer(self) -> QFrame:
        frame = QFrame()
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(
            f"QPushButton {{ color:{Semantic.DANGER}; border-color:{Semantic.DANGER}; }}"
            f"QPushButton:hover {{ background:{Contextual.DANGER_DARK}; }}"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("  Salvar Convenção ↓  ")
        btn_save.setToolTip("Salva o mapeamento de termos desta obra para usar em análises futuras")
        if not self._convention_file:
            btn_save.setEnabled(False)
            btn_save.setToolTip("convention_file não configurado — salvar indisponível")
        btn_save.setStyleSheet(
            f"QPushButton {{ color:{Semantic.WARNING}; "
            f"  border-color:{Semantic.WARNING}; padding:6px 14px; }}"
            f"QPushButton:hover {{ background:{Semantic.WARNING_BG_DARK}; }}"
            f"QPushButton:disabled {{ color:{Text.MUTED}; border-color:{Border.STRONG}; }}"
        )
        btn_save.clicked.connect(self._save_convention)
        self._btn_save_conv = btn_save

        btn_html = QPushButton("  Gerar todos HTMLs  ")
        btn_html.setToolTip("Gera uma ficha HTML separada por aba, com fotos e notas de atenção")
        btn_html.setStyleSheet(
            f"QPushButton {{ color:{Colors.ACCENT_MINT}; border-color:{Colors.ACCENT_MINT}; padding:6px 14px; }}"
            f"QPushButton:hover {{ background:{Semantic.SUCCESS_BG_DARK}; }}"
        )
        btn_html.clicked.connect(self._export_html_snapshot)

        btn_confirm = QPushButton("  Confirmar e Prosseguir  ▶")
        btn_confirm.setStyleSheet(
            f"QPushButton {{ background:{Accent.PRIMARY}; color:{Surface.DEEP}; font-weight:bold; "
            f"  border:none; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:{Accent.BRAND}; }}"
        )
        btn_confirm.clicked.connect(self._confirm_and_save)

        lay.addWidget(btn_cancel)
        lay.addWidget(btn_save)
        lay.addWidget(btn_html)
        lay.addWidget(btn_confirm)
        return frame

    # ── Aba Pilares ────────────────────────────────────────────────────────────

    def _build_convention_tab(self) -> QWidget:
        """
        Aba Convenção de Pilares.
        Layout:
          [Gabarito] — viewer grande com recorte PIL do Motor Reverso (fonte de verdade)
          ──────────────────────────────────────────────────────────────────────────
          [Lista de termos + mini viewers por classe]
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setMinimumHeight(0)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(6)

        # Viewer central do gabarito (Motor Reverso)
        _dbg("_build_convention_tab: antes do gabarito")
        gabarito = self._build_detail_reference_viewer()
        _dbg("_build_convention_tab: gabarito construido")
        if gabarito:
            lay.addWidget(gabarito)
            sep = QFrame(); sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet(f"color:{Colors.BORDER_DEFAULT};")
            lay.addWidget(sep)

        # Lista de termos + mini viewers por classe
        _dbg("_build_convention_tab: antes do convention_panel")
        lay.addWidget(self._build_convention_panel())
        _dbg("_build_convention_tab: convention_panel OK")
        lay.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_pillars_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # Barra de ações — só exibe se há DXF disponível para re-detecção
        if self._dxf_data:
            bar = QHBoxLayout()
            bar.setContentsMargins(0, 0, 0, 0)
            self._btn_rebuscar = QPushButton("🔍 Rebuscar Geometrias Erradas")
            self._btn_rebuscar.setToolTip(
                "Re-detecta polígonos de pilares para os itens classificados como\n"
                "'GEOMETRIA ERRADA'. Pilares corrigidos voltam para INDETERMINADO."
            )
            self._btn_rebuscar.setStyleSheet(
                f"QPushButton {{ color:{Semantic.WARNING}; border-color:{Semantic.WARNING}; font-size:10px; }}"
                f"QPushButton:hover {{ background:{Semantic.WARNING_BG_DARK}; }}"
            )
            self._btn_rebuscar.clicked.connect(self._rebuscar_geometrias_erradas)
            bar.addWidget(self._btn_rebuscar)
            bar.addStretch()
            lay.addLayout(bar)

        lay.addWidget(self._build_pillar_table(), 1)
        return w

    def _rebuscar_geometrias_erradas(self) -> None:
        """
        Re-detecta polígonos de pilar para todos os pilares classificados como
        'GEOMETRIA ERRADA'. Para cada um, busca uma geometria alternativa no DXF
        e — se encontrada — atualiza o pillar_report e a linha da tabela.
        """
        from src.core.analysis_helpers import detect_pilares_from_polylines

        geom_erradas = {
            key: pillar
            for key, pillar in self._pillar_report.items()
            if pillar.get('classification', '').upper() in _NAO_SE_APLICA_CLASSIFS
            and 'GEOMETRIA' in pillar.get('classification', '').upper()
        }
        if not geom_erradas:
            return

        polylines = self._dxf_data.get('polylines', [])
        texts     = self._dxf_data.get('texts', [])
        if not polylines:
            return

        # Polígonos já em uso pelos pilares OK (para tentar evitar re-usar os mesmos)
        used_geo_keys: set = set()
        for key, p in self._pillar_report.items():
            if key not in geom_erradas:
                gk = self._pillar_geo_key(p)
                if gk:
                    used_geo_keys.add(gk)

        # Re-detecta todos os pilares do DXF
        all_detected = detect_pilares_from_polylines(polylines, texts)
        detected_by_name: dict[str, list] = {}
        for p in all_detected:
            nm = (p.get('name') or p.get('fields', {}).get('nome') or '').strip().upper()
            if nm:
                detected_by_name.setdefault(nm, []).append(p)

        updated_count = 0
        for key, pillar in geom_erradas.items():
            pil_name = (pillar.get('name') or '').strip().upper()
            candidates = detected_by_name.get(pil_name, [])
            # Filtra candidatos com geometria diferente da atual
            current_gk = self._pillar_geo_key(pillar)
            alts = [c for c in candidates if self._pillar_geo_key(c) != current_gk
                    and self._pillar_geo_key(c) not in used_geo_keys]
            if not alts:
                continue

            best = alts[0]
            best_gk = self._pillar_geo_key(best)
            # Atualiza in-place: preserva nome/key, substitui geometria
            pillar['points']      = best.get('points', pillar.get('points', []))
            pillar['bbox']        = best.get('bbox', pillar.get('bbox'))
            pillar['orientation'] = best.get('orientation', pillar.get('orientation'))
            pillar['area_val']    = best.get('area_val', pillar.get('area_val'))
            pillar['classification'] = 'INDETERMINADO'
            pillar['physical_type']  = 'unknown'
            if best_gk:
                used_geo_keys.add(best_gk)

            # Atualiza combobox e linha na tabela
            combo = self._pillar_combos.get(key)
            if combo:
                idx = next((i for i, o in enumerate(list(PILLAR_CLASSIFICATION_OPTIONS))
                            if o == 'INDETERMINADO'), -1)
                # Bloqueia sinal para não disparar _on_pillar_classif_changed desnecessariamente
                combo.blockSignals(True)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                combo.blockSignals(False)
            row = self._pillar_rows.get(key)
            if row is not None:
                self._paint_row(row, 'INDETERMINADO')
                self._refresh_side_cells(row, key, 'INDETERMINADO')
                # Atualiza viewer vetorial com nova geometria
                pts = pillar.get('points', [])
                if pts:
                    self._pillar_viewer_data[row] = pts
                    viewer = self._make_pillar_viewer(pts)
                    if viewer:
                        self._pillar_table.setCellWidget(row, self._PIL_COL_FOTO, viewer)
            updated_count += 1

        if updated_count:
            self._btn_rebuscar.setText(
                f"🔍 Rebuscar Geometrias Erradas  ✔ {updated_count} atualizado(s)"
            )
            self._btn_rebuscar.setStyleSheet(
                f"QPushButton {{ color:{Semantic.SUCCESS}; border-color:{Semantic.SUCCESS}; font-size:10px; }}"
            )

    def _build_convention_panel(self) -> QGroupBox:
        grp = QGroupBox("Mapeamento de Terminologia da Obra → Tipo Físico")
        grid = QGridLayout(grp)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(2)
        grid.setContentsMargins(6, 8, 6, 4)

        headers = ["Termo (DXF)", "Padrão equivalente", "Tipo Físico", "Efeito nas vigas", "Ref. DXF"]
        for col, h in enumerate(headers):
            lb = QLabel(h)
            lb.setStyleSheet(f"color:{Colors.ACCENT_MINT}; font-size:9px; font-weight:bold;")
            grid.addWidget(lb, 0, col)
        grid.setColumnMinimumWidth(4, 195)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{Colors.BORDER_DEFAULT};")
        grid.addWidget(sep, 1, 0, 1, 5)

        # Termos padrão primeiro
        shown_terms: set[str] = set()
        all_terms: list[str] = []
        for t in STANDARD_TERM_MAP:
            all_terms.append(t)
            shown_terms.add(t)
        # Termos da obra não padrão
        for term in self._convention:
            tu = term.upper()
            if tu not in shown_terms:
                all_terms.append(tu)
                shown_terms.add(tu)

        for row_i, term in enumerate(all_terms):
            row = row_i + 2
            std_equiv = self._std_equivalent(term)
            current_phys = self._term_type_map.get(term, 'unknown')
            effect = "ignora como obstáculo" if PHYS_IGNORE.get(current_phys) else "conta como obstáculo"
            is_std = term in STANDARD_TERM_MAP

            term_lbl = QLabel(term)
            term_lbl.setStyleSheet(
                f"font-size:9px; font-weight:bold; color:{Text.SECONDARY if is_std else Semantic.WARNING};"
            )
            std_lbl = QLabel(std_equiv)
            std_lbl.setStyleSheet(f"font-size:9px; color:{Colors.TEXT_MUTED};")

            phys_combo = QComboBox()
            phys_combo.setStyleSheet("font-size:9px;")
            for key, label in PHYSICAL_TYPES:
                phys_combo.addItem(label, key)
            idx = next((i for i, (k, _) in enumerate(PHYSICAL_TYPES) if k == current_phys), 0)
            phys_combo.setCurrentIndex(idx)

            effect_lbl = QLabel(effect)
            effect_lbl.setStyleSheet(
                f"font-size:9px; color:{Text.SECONDARY if PHYS_IGNORE.get(current_phys) else Semantic.DANGER};"
            )

            def _make_on_change(t=term, eff_lb=effect_lbl):
                def _on(idx, lb=eff_lb, tm=t):
                    phys = PHYSICAL_TYPES[idx][0]
                    self._term_type_map[tm] = phys
                    ignore = PHYS_IGNORE.get(phys, False)
                    lb.setText("ignora como obstáculo" if ignore else "conta como obstáculo")
                    lb.setStyleSheet(
                        f"font-size:9px; color:{Text.SECONDARY if ignore else Semantic.DANGER};"
                    )
                    # Propaga para pilares com esse termo
                    self._refresh_pillar_table_row_for_term(tm)
                return _on

            phys_combo.currentIndexChanged.connect(_make_on_change())
            self._term_combos[term] = phys_combo

            _dbg(f"convention_panel: criando viewer termo '{term}'")
            ref_viewer = self._make_conv_viewer_for_term(term, w=190, h=85)
            _dbg(f"convention_panel: viewer termo '{term}' OK")

            grid.addWidget(term_lbl, row, 0)
            grid.addWidget(std_lbl, row, 1)
            grid.addWidget(phys_combo, row, 2)
            grid.addWidget(effect_lbl, row, 3)
            grid.addWidget(ref_viewer, row, 4, Qt.AlignCenter)
            grid.setRowMinimumHeight(row, 90)

        return grp

    def _std_equivalent(self, term: str) -> str:
        tu = term.upper()
        if tu in STANDARD_TERM_MAP:
            return tu
        for std, phys in STANDARD_TERM_MAP.items():
            if self._term_type_map.get(tu) == phys:
                return f"~ {std}"
        return "—"

    # Índice das colunas da tabela de pilares (retangulares)
    # Classif.SA e Classif.Override ficam lado a lado (cols 1 e 2)
    _PIL_COL_NOME      = 0
    _PIL_COL_CLASSIF   = 1
    _PIL_COL_OVERRIDE  = 2   # ao lado da classificação SA
    _PIL_COL_PHYS      = 3   # agora: "Formato Pilar" (shape geométrico)
    _PIL_COL_CONF      = 4
    _PIL_COL_NIVEL     = 5
    _PIL_COL_LADO_A    = 6
    _PIL_COL_LADO_B    = 7
    _PIL_COL_LADO_C    = 8
    _PIL_COL_LADO_D    = 9
    _PIL_COL_ATENCAO   = 10  # nota livre para feedback / gabarito
    _PIL_COL_FOTO      = 11

    # Índice das colunas da tabela de pilares especiais (A-H)
    _ESP_COL_NOME      = 0
    _ESP_COL_CLASSIF   = 1
    _ESP_COL_OVERRIDE  = 2
    _ESP_COL_FORMATO   = 3
    _ESP_COL_CONF      = 4
    _ESP_COL_NIVEL     = 5
    _ESP_COL_LADO_A    = 6
    _ESP_COL_LADO_B    = 7
    _ESP_COL_LADO_C    = 8
    _ESP_COL_LADO_D    = 9
    _ESP_COL_LADO_E    = 10
    _ESP_COL_LADO_F    = 11
    _ESP_COL_LADO_G    = 12
    _ESP_COL_LADO_H    = 13
    _ESP_COL_FOTO      = 14

    # Dimensões do mini viewer de pilar
    _PIL_THUMB_W  = 880
    _PIL_THUMB_H  = 420
    _PIL_COL_FOTO_W = 890
    _PIL_ROW_H    = 430

    # Largura das colunas Lado-A/B/C/D (−20% de 130)
    _PIL_LADO_COL_W = 104

    def _build_pillar_table(self) -> QTableWidget:
        cols = [
            "Nome", "Classif. SA", "Classif. Override",
            "Formato Pilar", "Conf %", "Nível",
            "Lado-A", "Lado-B", "Lado-C", "Lado-D", "⚑ Atenção / Feedback (editável)", "Foto",
        ]
        tbl = QTableWidget(0, len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self._PIL_COL_NOME, QHeaderView.Fixed)
        tbl.setColumnWidth(self._PIL_COL_NOME, 75)
        for col in (self._PIL_COL_LADO_A, self._PIL_COL_LADO_B,
                    self._PIL_COL_LADO_C, self._PIL_COL_LADO_D):
            hdr.setSectionResizeMode(col, QHeaderView.Interactive)
            tbl.setColumnWidth(col, self._PIL_LADO_COL_W)
        hdr.setSectionResizeMode(self._PIL_COL_OVERRIDE, QHeaderView.Interactive)
        tbl.setColumnWidth(self._PIL_COL_OVERRIDE, 180)
        hdr.setSectionResizeMode(self._PIL_COL_ATENCAO, QHeaderView.Interactive)
        tbl.setColumnWidth(self._PIL_COL_ATENCAO, 300)
        hdr.setSectionResizeMode(self._PIL_COL_FOTO, QHeaderView.Fixed)
        tbl.setColumnWidth(self._PIL_COL_FOTO, self._PIL_COL_FOTO_W)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        # Atenção é editável; demais colunas não
        tbl.setEditTriggers(
            QAbstractItemView.CurrentChanged
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.DoubleClicked
        )
        tbl.verticalHeader().setVisible(False)
        tbl.setStyleSheet("QTableWidget { font-size:9px; }")
        tbl.setMinimumHeight(0)
        self._pillar_table = tbl
        self._pillar_viewer_data = {}
        # Mantém notas existentes caso a exportação tenha ocorrido antes do lazy-load.
        tbl.verticalScrollBar().valueChanged.connect(
            lambda _: self._update_dynamic_viewers(self._pillar_table, self._pillar_viewer_data, self._PIL_COL_FOTO, False)
        )
        tbl.itemChanged.connect(self._on_atencao_changed)
        self._populate_pillar_table()
        self._restore_table_scroll(tbl, 'pilares')
        return tbl

    def _on_atencao_changed(self, item: QTableWidgetItem) -> None:
        """Persiste nota de atenção quando o usuário edita a célula."""
        if item.column() != self._PIL_COL_ATENCAO:
            return
        row = item.row()
        nome_item = self._pillar_table.item(row, self._PIL_COL_NOME)
        key = nome_item.data(Qt.UserRole) if nome_item else None
        if key:
            self._atencao_notes[key] = item.text().strip()

    def _row_bg_for_classif(self, classif: str) -> QColor | None:
        """
        Retorna a cor de fundo da linha baseada na classificação:
          INDETERMINADO          → Semantic.DANGER_BG_DARK
          visual_only (ex NASCE) → Semantic.SUCCESS_BG_DARK
          NÃO PILAR …            → Semantic.WARNING_BG_DARK
          GEOMETRIA ERRADA …     → Semantic.WARNING_BG_DARK
          outros (solid)         → None (padrão)
        """
        cu = (classif or '').upper()
        if cu == 'INDETERMINADO':
            return QColor(Semantic.DANGER_BG_DARK)
        if cu in (_NAO_PILAR_SOLIDO.upper(), _NAO_PILAR_VISUAL.upper()):
            return QColor(Semantic.WARNING_BG_DARK)
        if cu in (_GEOM_ERRADA_SOLIDA.upper(), _GEOM_ERRADA_VISUAL.upper()):
            return QColor(Semantic.WARNING_BG_DARK)
        phys = self._physical_type_for(classif)
        if phys == 'visual_only':
            return QColor(Semantic.SUCCESS_BG_DARK)
        return None

    def _paint_row(self, row: int, classif: str):
        """Aplica a cor de fundo da linha em todas as células (itens + label de Tipo Físico)."""
        tbl = self._pillar_table
        bg = self._row_bg_for_classif(classif)
        skip = {self._PIL_COL_OVERRIDE, self._PIL_COL_ATENCAO, self._PIL_COL_FOTO}
        for col in range(tbl.columnCount()):
            if col in skip or col == self._PIL_COL_PHYS:
                continue
            it = tbl.item(row, col)
            if it:
                if bg:
                    it.setBackground(QBrush(bg))
                else:
                    it.setBackground(QBrush())
        # Tipo Físico é QLabel → atualiza via stylesheet
        nome_item = tbl.item(row, self._PIL_COL_NOME)
        key = nome_item.data(Qt.UserRole) if nome_item else None
        if key and key in self._phys_labels:
            lbl = self._phys_labels[key]
            # Preserva a cor do formato; apenas atualiza o background
            bg_css = bg.name() if bg else 'transparent'
            cur_ss = lbl.styleSheet()
            # Substitui apenas a parte background mantendo color existente
            import re as _re
            new_ss = _re.sub(r'background:[^;]+;', f'background:{bg_css};', cur_ss)
            if 'background:' not in new_ss:
                new_ss += f' background:{bg_css};'
            lbl.setStyleSheet(new_ss)

    @staticmethod
    def _natural_sort_key(s: str):
        """Chave para ordenação alfanumérica natural: P1 P2 … P9 P10 P11 …"""
        return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

    def _populate_pillar_table(self):
        tbl = self._pillar_table
        tbl.setUpdatesEnabled(False)
        tbl.setRowCount(0)
        self._pillar_rows.clear()
        self._phys_labels.clear()
        nr_pilares = (self._nivel_report or {}).get('pilares', {})

        def _pil_sort_key(kv):
            k = kv[0]
            if k.endswith('__ALT'):
                return self._natural_sort_key(k[:-5]) + [1]
            return self._natural_sort_key(k) + [0]

        sorted_items = sorted(self._pillar_report.items(), key=_pil_sort_key)
        for i, (key, pillar) in enumerate(sorted_items):
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setRowHeight(row, self._PIL_ROW_H)
            self._pillar_rows[key] = row

            name = pillar.get('name') or key
            classif = pillar.get('classification') or 'INDETERMINADO'

            geo_is_alt      = bool(pillar.get('geometry_alt_candidate'))
            alt_original_key = pillar.get('alt_for_original_key', '')

            # ── Restaura override do histórico por geometria ─────────────────
            geo_key = self._pillar_geo_key(pillar)
            hist_pil = self._pf_history.get('pilares', {}).get(geo_key)
            geo_foi_rejeitada  = bool(pillar.get('geometry_previously_rejected'))
            geo_foi_substituida = bool(pillar.get('geometry_swapped'))
            if hist_pil and hist_pil.get('classification') and not geo_is_alt:
                classif = hist_pil['classification']
                if classif.upper() in _NAO_SE_APLICA_CLASSIFS:
                    geo_foi_rejeitada = True
            if hist_pil and hist_pil.get('attention'):
                self._atencao_notes[key] = str(hist_pil['attention'])

            phys = self._physical_type_for(classif)
            ignore = PHYS_IGNORE.get(phys, False)

            # Detecta formato geométrico; pilares não-retangulares vão p/ aba Especiais
            pts = pillar.get('points') or []
            formato = _pilar_formato(pts)
            if formato != 'Retangular':
                continue   # será renderizado na aba "Pilares Especiais"

            conf_pct = 0 if classif == 'INDETERMINADO' else 95
            if classif in (_NAO_PILAR_SOLIDO, _NAO_PILAR_VISUAL):
                conf_pct = 100

            p_nr = nr_pilares.get(key, {})
            nivel_str = p_nr.get('level_str') or '—'
            conf_color = _confidence_color(conf_pct)

            # ── Nome: fonte maior + negrito ──────────────────────────────────
            if geo_is_alt:
                nome_display = f'↺ {name} (candidato alt.)'
            elif geo_foi_rejeitada:
                nome_display = f'⚠ {name}'
            else:
                nome_display = name
            nome_item = _make_item(nome_display, bold=True)
            f = nome_item.font()
            f.setPixelSize(18)
            f.setBold(True)
            nome_item.setFont(f)
            if geo_is_alt:
                nome_item.setForeground(QBrush(QColor(Accent.BRAND)))
                nome_item.setToolTip(
                    f'↺ Candidato de geometria alternativa para "{alt_original_key}".\n'
                    f'A bbox original foi rejeitada — esta pode ser a geometria correta.\n'
                    f'Classifique conforme o tipo real do pilar.'
                )
            elif geo_foi_rejeitada:
                nome_item.setForeground(QBrush(QColor(Semantic.WARNING)))
                nome_item.setToolTip(
                    f'⚠ Geometria desta bbox foi rejeitada anteriormente para "{name}".\n'
                    f'Sem alternativa disponível nesta análise.'
                )
            nome_item.setData(Qt.UserRole, key)   # guarda key para lookup dinâmico
            tbl.setItem(row, self._PIL_COL_NOME, nome_item)

            # Classif. SA com sufixo do tipo físico (sólido / visual)
            if phys == 'visual_only':
                classif_sa_display = f'{classif}  ·  visual'
            elif phys == 'solid':
                classif_sa_display = f'{classif}  ·  sólido'
            else:
                classif_sa_display = classif
            tbl.setItem(row, self._PIL_COL_CLASSIF, _make_item(classif_sa_display))
            tbl.setItem(row, self._PIL_COL_CONF,
                        _make_item(f"{conf_pct}%", Qt.AlignCenter, color=conf_color))
            tbl.setItem(row, self._PIL_COL_NIVEL,
                        _make_item(nivel_str, Qt.AlignCenter))

            # ── Formato Pilar: QLabel colorido por shape ──────────────────────
            fmt_color = PILLAR_FORMATO_COLORS.get(formato, '#f07070')
            fmt_lbl = QLabel(PILLAR_FORMATO_LABELS.get(formato, formato))
            fmt_lbl.setWordWrap(True)
            fmt_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            fmt_lbl.setStyleSheet(
                f"color:{fmt_color}; font-size:9px; padding:3px; background:transparent;"
            )
            self._phys_labels[key] = fmt_lbl
            tbl.setCellWidget(row, self._PIL_COL_PHYS, fmt_lbl)

            # ── Colunas Lado-A … Lado-D ──────────────────────────────────────
            # Se classificação inválida (não é pilar / geometria errada) → "Não se aplica"
            invalid_geom = classif.upper() in _NAO_SE_APLICA_CLASSIFS
            for col, side in ((self._PIL_COL_LADO_A, 'A'), (self._PIL_COL_LADO_B, 'B'),
                              (self._PIL_COL_LADO_C, 'C'), (self._PIL_COL_LADO_D, 'D')):
                if invalid_geom:
                    item = _make_item('Não se aplica', color=QColor(Colors.TEXT_MUTED))
                    item.setToolTip('Geometria inválida ou objeto não é pilar')
                else:
                    cell_text = self._get_side_cell(pillar, side)
                    item = _make_item(cell_text)
                    item.setToolTip(cell_text)
                    if '⚠ suspeito' in cell_text:
                        item.setForeground(QBrush(QColor(Semantic.DANGER)))
                        item.setToolTip(cell_text + '\n\n⚠ Nível suspeito de alucinação — revisar vinculação de nivel no DXF.')
                    elif cell_text.startswith('Viga:'):
                        item.setForeground(QBrush(QColor(Colors.ACCENT_WARNING_ALT)))
                    elif cell_text == 'nulo':
                        item.setForeground(QBrush(QColor(Colors.TEXT_MUTED)))
                tbl.setItem(row, col, item)

            # ── Coluna Atenção (editável) ────────────────────────────────────
            nota = self._atencao_notes.get(key, '')
            atencao_item = QTableWidgetItem(nota)
            atencao_item.setForeground(QBrush(QColor('#f0b840')))
            atencao_item.setToolTip('Clique para digitar uma nota de atenção — será salva no HTML')
            tbl.setItem(row, self._PIL_COL_ATENCAO, atencao_item)

            # ── Combobox Override ────────────────────────────────────────────
            combo = QComboBox()
            combo.setStyleSheet("font-size:9px;")
            combo.view().setWordWrap(True)
            options = list(PILLAR_CLASSIFICATION_OPTIONS)
            # Insere termos da obra antes do primeiro separador
            sep_idx = options.index(_SEPARADOR_ITEM) if _SEPARADOR_ITEM in options else len(options)
            for term in self._term_type_map:
                if term not in options and term not in (_SEPARADOR_ITEM, _SEPARADOR_GEOM):
                    options.insert(sep_idx, term)
                    sep_idx += 1
            # Separadores não selecionáveis e cores especiais
            _SEPARADORES = {_SEPARADOR_ITEM, _SEPARADOR_GEOM}
            for j, opt in enumerate(options):
                combo.addItem(opt)
                mi = combo.model().item(j)
                if not mi:
                    continue
                if opt in _SEPARADORES:
                    mi.setEnabled(False)
                    mi.setForeground(QBrush(QColor(Colors.TEXT_MUTED)))
                elif opt in (_NAO_PILAR_SOLIDO, _NAO_PILAR_VISUAL):
                    mi.setForeground(QBrush(QColor(Contextual.GOLD)))   # amarelo
                elif opt in (_GEOM_ERRADA_SOLIDA, _GEOM_ERRADA_VISUAL):
                    mi.setForeground(QBrush(QColor(Semantic.WARNING)))   # laranja
            idx = next((i for i, o in enumerate(options) if o == classif), 0)
            combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(
                lambda _, k=key, c=combo: self._on_pillar_classif_changed(k, c))
            tbl.setCellWidget(row, self._PIL_COL_OVERRIDE, combo)
            self._pillar_combos[key] = combo

            # ── Mini viewer vetorial ─────────────────────────────────────────
            pts = pillar.get('points') or []
            if pts:
                self._pillar_viewer_data[row] = pts
                lbl = QLabel("⏳ Carregando...")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px;")
                tbl.setCellWidget(row, self._PIL_COL_FOTO, lbl)
            else:
                tbl.setItem(row, self._PIL_COL_FOTO,
                            _make_item('—', Qt.AlignCenter, color=QColor(Colors.TEXT_MUTED)))

            # ── Cor da linha baseada na classificação ────────────────────────
            self._paint_row(row, classif)
            
        tbl.setUpdatesEnabled(True)
        # Gatilho para carregar os viewers visíveis inicialmente
        QTimer.singleShot(150, lambda: self._update_dynamic_viewers(tbl, self._pillar_viewer_data, self._PIL_COL_FOTO, False))

    def _update_dynamic_viewers(self, tbl: QTableWidget, data_dict: dict, col_idx: int, is_cut: bool):
        if not tbl.isVisible():
            return
            
        vp_height = tbl.viewport().height()
        top_row = tbl.rowAt(0)
        bottom_row = tbl.rowAt(max(0, vp_height - 1))
        
        if top_row == -1:
            top_row = 0
        if bottom_row == -1:
            bottom_row = tbl.rowCount() - 1
            
        # Sem prefetch: viewers 2x maiores tornam suficiente manter apenas o
        # intervalo realmente visível no viewport atual.
        start_row = max(0, top_row)
        end_row = min(tbl.rowCount() - 1, bottom_row)
        
        # Load visíveis
        for row in range(start_row, end_row + 1):
            if row in data_dict:
                pts = data_dict[row]
                current_widget = tbl.cellWidget(row, col_idx)
                if current_widget and isinstance(current_widget, _MiniDXFView):
                    continue
                    
                viewer = self._make_cut_viewer(pts) if is_cut else self._make_pillar_viewer(pts)
                if viewer:
                    tbl.setCellWidget(row, col_idx, viewer)
                else:
                    tbl.setItem(row, col_idx, _make_item('—', Qt.AlignCenter, color=QColor(Colors.TEXT_MUTED)))
                    del data_dict[row]
                    
        # Unload invisíveis para salvar memória e rendering
        for row, pts in list(data_dict.items()):
            if row < start_row or row > end_row:
                current_widget = tbl.cellWidget(row, col_idx)
                if current_widget and isinstance(current_widget, _MiniDXFView):
                    lbl = QLabel("⏳ Rolar para carregar")
                    lbl.setAlignment(Qt.AlignCenter)
                    lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px;")
                    tbl.setCellWidget(row, col_idx, lbl)

    def _refresh_side_cells(self, row: int, key: str, classif: str):
        """
        Atualiza as 4 células Lado-A/B/C/D da linha.

        Se classif estiver em _NAO_SE_APLICA_CLASSIFS (não é pilar ou geometria
        errada), preenche todas com "Não se aplica" (cinza).
        Caso contrário, recalcula via _get_side_cell.
        """
        tbl = self._pillar_table
        pillar = self._pillar_report.get(key, {})
        invalid = classif.upper() in _NAO_SE_APLICA_CLASSIFS

        for col, side in ((self._PIL_COL_LADO_A, 'A'), (self._PIL_COL_LADO_B, 'B'),
                          (self._PIL_COL_LADO_C, 'C'), (self._PIL_COL_LADO_D, 'D')):
            if invalid:
                it = _make_item('Não se aplica', color=QColor(Colors.TEXT_MUTED))
                it.setToolTip('Geometria inválida ou objeto não é pilar')
            else:
                cell_text = self._get_side_cell(pillar, side)
                it = _make_item(cell_text)
                it.setToolTip(cell_text)
                if cell_text.startswith('Viga:'):
                    it.setForeground(QBrush(QColor(Colors.ACCENT_WARNING_ALT)))
                elif cell_text == 'nulo':
                    it.setForeground(QBrush(QColor(Colors.TEXT_MUTED)))
            tbl.setItem(row, col, it)

    def _on_pillar_classif_changed(self, key: str, combo: QComboBox):
        new_classif = combo.currentText()
        if new_classif in (_SEPARADOR_ITEM, _SEPARADOR_GEOM):
            return
        pillar = self._pillar_report.get(key, {})
        if key in self._pillar_report:
            phys = self._physical_type_for(new_classif)
            self._pillar_report[key]['classification'] = new_classif
            self._pillar_report[key]['physical_type'] = phys
            self._pillar_report[key]['ignore_in_beams'] = PHYS_IGNORE.get(phys, False)
        # Persiste imediatamente no histórico quando é uma rejeição de geometria
        if new_classif.upper() in _NAO_SE_APLICA_CLASSIFS:
            geo = self._pillar_geo_key(pillar)
            if geo:
                self._pf_history.setdefault('pilares', {})[geo] = {
                    'geo_key':        geo,
                    'last_name':      key,
                    'classification': new_classif,
                    'physical_type':  self._physical_type_for(new_classif),
                    'saved_at':       datetime.now().isoformat(timespec='seconds'),
                }
                self._save_pf_history()
        row = self._pillar_rows.get(key)
        if row is not None:
            self._paint_row(row, new_classif)
            self._refresh_side_cells(row, key, new_classif)

    def _physical_type_for(self, classif: str) -> str:
        cu = (classif or '').upper()
        if cu in self._term_type_map:
            return self._term_type_map[cu]
        if cu in (_NAO_PILAR_SOLIDO.upper(), _GEOM_ERRADA_SOLIDA.upper()):
            return 'obstacle_solid'
        if cu in (_NAO_PILAR_VISUAL.upper(), _GEOM_ERRADA_VISUAL.upper()):
            return 'visual_noise'
        return STANDARD_TERM_MAP.get(cu, 'unknown')

    def _refresh_pillar_table_row_for_term(self, term: str):
        """Atualiza sufixo de tipo físico na coluna Classif.SA para pilares com esse termo."""
        tbl = self._pillar_table
        phys = self._term_type_map.get(term, 'unknown')
        for row in range(tbl.rowCount()):
            classif_item = tbl.item(row, self._PIL_COL_CLASSIF)
            if not classif_item:
                continue
            # Compara sem sufixo (o texto pode ser "NASCE  ·  visual")
            base = classif_item.text().split('  ·  ')[0].strip()
            if base.upper() != term.upper():
                continue
            # Atualiza sufixo do tipo físico no item de Classif.SA
            if phys == 'visual_only':
                new_text = f'{term}  ·  visual'
            elif phys == 'solid':
                new_text = f'{term}  ·  sólido'
            else:
                new_text = term
            classif_item.setText(new_text)

    # ── Aba Visão de Cortes ────────────────────────────────────────────────────

    def _build_cut_views_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Legenda de score
        leg = QLabel(
            f"Score de associação: "
            f"<span style='color:{Semantic.SUCCESS}'>■ ≥75% confiante</span>  "
            f"<span style='color:{Semantic.WARNING}'>■ 50–74% moderado</span>  "
            f"<span style='color:{Semantic.DANGER}'>■ &lt;50% incerto — revisar</span>"
        )
        leg.setStyleSheet("font-size:9px;")
        lay.addWidget(leg)

        info = QLabel(
            "Combobox 'Viga Assoc.' lista candidatos próximos por distância. "
            "Selecione ou digite o nome correto. Múltiplas linhas do mesmo corte "
            "indicam que a mesma viga tem mais de um recorte de visão."
        )
        info.setStyleSheet(f"font-size:9px; color:{Colors.TEXT_MUTED};")
        info.setWordWrap(True)
        lay.addWidget(info)

        lay.addWidget(self._build_cut_view_table(), 1)
        return w

    # ── Colunas da tabela de cortes (layout simplificado) ─────────────────────
    _CUT_COL_VIGA   = 0   # Viga Assoc. (combobox editável)
    _CUT_COL_CONF   = 1   # Conf %
    _CUT_COL_DIM    = 2   # H × W da viga
    _CUT_COL_LAJE1  = 3   # Laje 1 (multilinhas: nome, dir, H, classif, dist)
    _CUT_COL_LAJE2  = 4   # Laje 2 (idem, ou "Parede")
    _CUT_COL_STATUS = 5   # Combobox: válido / não é VC / errada
    _CUT_COL_ATENCAO = 6  # feedback humano editável
    _CUT_COL_FOTO   = 7   # Mini viewer

    # Opções de status do corte
    _CUT_ST_OK     = '— Válido (é visão de corte) —'
    _CUT_ST_VISUAL = 'NÃO É VISÃO CORTE — Errada Apenas Visual'
    _CUT_ST_SOLIDA = 'NÃO É VISÃO CORTE — Errada Sólida'
    _CUT_ST_PILAR  = 'NÃO É VISÃO CORTE — É Pilar'

    # Opção "nenhuma viga identificada"
    _CUT_NENHUMA   = '— Nenhuma (não identificada) —'

    _CUT_THUMB_W  = 880
    _CUT_THUMB_H  = 420
    _CUT_COL_FOTO_W = 890
    _CUT_ROW_H    = 430
    _CUT_LAJE_COL_W = 276   # largura das colunas Laje A / Laje B (+20%)

    def _laje_info_text(self, laje_name: str, direction: str,
                        position: str, dist_top, dist_bot,
                        lado: str = '', slab_h_cut: str = '') -> str:
        """
        Formata o bloco de informacao de uma laje no corte.

        Formato:
          Nome: L311
          Altura: 12
          Espessura no corte: 12.0
          Distancia do topo da viga: 0
          Distancia do fundo da viga: 43
          Nivel da laje: 852.19
          Posicao da viga em relacao a laje: no Sul da laje
          Classificacao vertical: topo
        """
        if not laje_name or laje_name in ('—', 'nulo', 'NULO'):
            return 'Parede\n(sem laje vizinha)'

        h     = self._slab_height_map.get(laje_name, '')
        nivel = self._slab_nivel_map.get(laje_name, '')

        lines = []

        # Nome (+ Lado A/B)
        nome_line = f'Nome: {laje_name}'
        if lado:
            nome_line += f'  |  Lado {lado}'
        lines.append(nome_line)

        # Altura cadastrada
        lines.append(f'Altura: {h}' if h else 'Altura:')

        # Espessura detectada no corte (pode diferir do cadastro)
        slab_h_cut_clean = str(slab_h_cut) if slab_h_cut not in ('—', '', None) else ''
        if slab_h_cut_clean:
            lines.append(f'Espessura no corte: {slab_h_cut_clean}')

        # Distancias
        def _fmt_dist(v) -> str:
            return str(v) if v not in ('—', None, '') else ''

        dt = _fmt_dist(dist_top)
        df = _fmt_dist(dist_bot)
        lines.append(f'Distancia do topo da viga: {dt}' if dt else 'Distancia do topo da viga:')
        lines.append(f'Distancia do fundo da viga: {df}' if df else 'Distancia do fundo da viga:')

        # Nivel
        lines.append(f'Nivel da laje: {nivel}' if nivel else 'Nivel da laje:')

        # Posicao geografica (onde a viga esta em relacao a esta laje)
        if direction and direction not in ('—', ''):
            lines.append(f'Posicao da viga: no {direction} da laje')
        else:
            lines.append('Posicao da viga:')

        # Classificacao estrutural vertical (topo / centro / fundo)
        pos_clean = str(position or '').strip()
        if pos_clean and pos_clean not in ('—', 'nulo', ''):
            lines.append(f'Classificacao vertical: {pos_clean}')
        else:
            lines.append('Classificacao vertical:')

        return '\n'.join(lines)

    def _build_laje_lado_widget(self, laje_name: str, direction: str,
                                position: str, dist_top, dist_bot,
                                lado: str, slab_h_cut: str, color: str) -> QLabel:
        """
        Fichinha 'Lajes LADO A/B' — versão bonita (HTML rico), no mesmo padrão
        visual da coluna 'Detalhes sobre o Segmento de Viga'. Substitui o texto
        plano de _laje_info_text por rótulos/valores coloridos e título destacado.
        """
        CL = Text.SECONDARY   # rótulo muted
        CV = Text.PRIMARY     # valor padrão

        def _kv(k: str, v: str, sfx: str = '', vc: str = CV) -> str:
            tail = f"&nbsp;<span style='color:{CL}'>{sfx}</span>" if sfx else ''
            return (f"<span style='color:{CL}'>{k}</span>"
                    f"&nbsp;<span style='color:{vc}'>{v}</span>{tail}")

        wall = not laje_name or laje_name in ('—', 'nulo', 'NULO', '')
        if wall:
            html = (
                "<div style='font-size:9px; line-height:1.45; padding:4px;'>"
                f"<b style='color:{CL}'>── Parede</b><br>"
                f"&nbsp;&nbsp;<span style='color:{CL}'>(sem laje vizinha)</span>"
                "</div>"
            )
        else:
            h     = self._slab_height_map.get(laje_name, '')
            nivel = self._slab_nivel_map.get(laje_name, '')

            def _fmt(v) -> str:
                s = str(v).strip() if v is not None else ''
                return s if s.lower() not in ('—', '', 'nulo') else '—'

            def _unit(v) -> str:
                try:
                    float(str(v).replace(',', '.'))
                    return 'cm'
                except (ValueError, TypeError):
                    return ''

            sh_cut_raw = str(slab_h_cut).strip() if slab_h_cut not in ('—', '', None) else ''
            # Lado "nulo": a viga NÃO corta esta laje → altura cadastrada não se aplica
            side_is_nulo = sh_cut_raw.lower() == 'nulo'

            altura_disp = '—' if side_is_nulo else _fmt(h)
            dt = _fmt(dist_top)
            df = _fmt(dist_bot)
            pos_clean = str(position or '').strip()
            if pos_clean.lower() in ('—', 'nulo', ''):
                pos_clean = '—'
            dir_clean = direction if direction and direction not in ('—', '') else '—'

            title = f"<b style='color:{color}'>── {laje_name}</b>"
            if lado:
                title += f"&nbsp;<span style='color:{CL}'>|&nbsp;Lado {lado}</span>"

            rows = [title]
            rows.append(f"&nbsp;&nbsp;{_kv('Altura:', altura_disp, _unit(altura_disp))}")
            if sh_cut_raw:
                rows.append(f"&nbsp;&nbsp;{_kv('Espessura no corte:', sh_cut_raw, _unit(sh_cut_raw))}")
            rows.append(f"&nbsp;&nbsp;{_kv('Dist. topo da viga:', dt, _unit(dt))}")
            rows.append(f"&nbsp;&nbsp;{_kv('Dist. fundo da viga:', df, _unit(df))}")
            if nivel == '⚠':
                rows.append(
                    f"&nbsp;&nbsp;{_kv('Nível da laje:', '⚠ suspeito', vc=Semantic.DANGER)}"
                )
            else:
                rows.append(f"&nbsp;&nbsp;{_kv('Nível da laje:', _fmt(nivel))}")
            rows.append(f"&nbsp;&nbsp;{_kv('Posição da viga:', dir_clean, vc=color)}")
            rows.append(f"&nbsp;&nbsp;{_kv('Classif. vertical:', pos_clean, vc=color)}")

            html = (
                "<div style='font-size:9px; line-height:1.45; padding:4px;'>"
                + '<br>'.join(rows) +
                "</div>"
            )

        lbl = QLabel(html)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        lbl.setStyleSheet('background:transparent;')
        lbl.setTextFormat(Qt.RichText)
        return lbl

    def _build_cut_view_table(self) -> QTableWidget:
        cols = ["Viga Assoc.", "Conf %",
                "Detalhes sobre o Segmento de Viga",
                "Lajes LADO A", "Lajes LADO B", "Status",
                "⚑ Atenção / Feedback (editável)", "Foto"]
        tbl = QTableWidget(0, len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self._CUT_COL_VIGA, QHeaderView.Interactive)
        tbl.setColumnWidth(self._CUT_COL_VIGA, 210)
        hdr.setSectionResizeMode(self._CUT_COL_DIM, QHeaderView.Interactive)
        tbl.setColumnWidth(self._CUT_COL_DIM, 230)
        for col in (self._CUT_COL_LAJE1, self._CUT_COL_LAJE2):
            hdr.setSectionResizeMode(col, QHeaderView.Interactive)
            tbl.setColumnWidth(col, self._CUT_LAJE_COL_W)
        hdr.setSectionResizeMode(self._CUT_COL_STATUS, QHeaderView.Interactive)
        tbl.setColumnWidth(self._CUT_COL_STATUS, 220)
        hdr.setSectionResizeMode(self._CUT_COL_ATENCAO, QHeaderView.Interactive)
        tbl.setColumnWidth(self._CUT_COL_ATENCAO, 300)
        hdr.setSectionResizeMode(self._CUT_COL_FOTO, QHeaderView.Fixed)
        tbl.setColumnWidth(self._CUT_COL_FOTO, self._CUT_COL_FOTO_W)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setEditTriggers(
            QAbstractItemView.CurrentChanged
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.DoubleClicked
        )
        tbl.verticalHeader().setVisible(False)
        tbl.setStyleSheet("QTableWidget { font-size:9px; }")
        tbl.setMinimumHeight(0)  # não trava o layout; footer permanece visível
        self._cut_table = tbl
        self._cut_viewer_data = {}
        tbl.verticalScrollBar().valueChanged.connect(
            lambda _: self._update_dynamic_viewers(self._cut_table, self._cut_viewer_data, self._CUT_COL_FOTO, True)
        )
        tbl.itemChanged.connect(self._on_cut_attention_changed)
        self._populate_cut_view_table()
        self._restore_table_scroll(tbl, 'visao_cortes')
        return tbl

    def _on_cut_attention_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != self._CUT_COL_ATENCAO:
            return
        uid_item = self._cut_table.item(item.row(), self._CUT_COL_CONF)
        uid = uid_item.data(Qt.UserRole) if uid_item else None
        if uid:
            self._cut_attention[str(uid)] = item.text().strip()

    # Mapa de cor de fundo da linha por (status_data, is_hist)
    _CUT_ROW_BG: dict[tuple, str] = {
        ('ok',     False): Surface.RAISED,           # azul escuro — válido novo
        ('ok',     True):  Semantic.SUCCESS_BG_DARK, # verde escuro — válido histórico
        ('visual', False): Semantic.WARNING_BG_DARK, # laranja escuro — errata visual
        ('visual', True):  Semantic.WARNING_BG_DARK,
        ('solida', False): Semantic.DANGER_BG_DARK,  # vermelho escuro — errata sólida
        ('solida', True):  Semantic.DANGER_BG_DARK,
        ('pilar',  False): Surface.BASE,             # roxo-navy — é pilar
        ('pilar',  True):  Surface.BASE,
    }

    def _paint_cut_row(self, row: int, status: str, is_hist: bool) -> None:
        """Pinta fundo da linha com base no status + tag histórico/novo."""
        tbl = self._cut_table
        bg_hex = self._CUT_ROW_BG.get((status, is_hist), Surface.RAISED)
        bg = QColor(bg_hex)
        # Célula item (Conf %)
        it = tbl.item(row, self._CUT_COL_CONF)
        if it:
            it.setBackground(QBrush(bg))
        # Widgets com fundo dinâmico (Laje A/B e Segmento de Viga)
        for col in (self._CUT_COL_LAJE1, self._CUT_COL_LAJE2, self._CUT_COL_DIM):
            w = tbl.cellWidget(row, col)
            if isinstance(w, QLabel):
                ss = re.sub(r'background:[^;]+;', '', w.styleSheet())
                w.setStyleSheet(ss + f' background:{bg_hex};')

    def _on_cut_status_changed(self, uid: str) -> None:
        """Repinta a linha e controla visibilidade do botão migrar."""
        meta = self._cut_row_meta.get(uid, {})
        row  = meta.get('row', -1)
        is_hist = meta.get('is_hist', False)
        combo = self._cut_status_combos.get(uid)
        if combo and row >= 0:
            status = combo.currentData() or 'ok'
            self._paint_cut_row(row, status, is_hist)
            btn = self._cut_migrar_btns.get(uid)
            if btn:
                btn.setVisible(status == 'pilar')

    def _populate_cut_view_table(self):
        tbl = self._cut_table
        tbl.setUpdatesEnabled(False)
        tbl.setRowCount(0)
        self._cut_status_combos.clear()
        self._cut_tag_labels.clear()
        self._cut_migrar_btns.clear()
        self._cut_row_meta.clear()

        # ── Ordena por (status_order, is_hist) ──────────────────────────────
        _st_order = {'ok': 0, 'visual': 1, 'solida': 2}
        def _cut_sort_key(cut):
            geo = self._cv_geo_key(cut.get('pts', []))
            h = self._pf_history.get('cut_views', {}).get(geo, {})
            st = h.get('status', 'ok')
            return (_st_order.get(st, 0), 1 if h else 0)

        for i, cut in enumerate(sorted(self._cut_view_data, key=_cut_sort_key)):
            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setRowHeight(row, self._CUT_ROW_H)

            uid      = cut['uid']
            conf_pct = cut['conf_pct']

            # ── Histórico por geometria ──────────────────────────────────────
            cv_geo   = self._cv_geo_key(cut.get('pts', []))
            hist_cv  = self._pf_history.get('cut_views', {}).get(cv_geo, {})
            is_hist  = bool(hist_cv)   # True = dado carregado do histórico

            # ── Viga Assoc. (combobox editável) ─────────────────────────────
            beam_combo = QComboBox()
            beam_combo.setEditable(True)
            beam_combo.setStyleSheet("font-size:9px;")
            beam_combo.addItem(self._CUT_NENHUMA, '')   # índice 0 = nenhuma
            candidates = cut.get('candidates') or []
            for cand in candidates:
                beam_combo.addItem(
                    f"{cand['text']}  ({cand['dist']:.0f}u, {cand['conf_pct']}%)",
                    cand['text']
                )
            # Restaura do histórico (prioridade máxima); senão usa candidato automático
            hist_beam = hist_cv.get('beam_name', '')
            if hist_beam:
                # Tenta achar nos candidatos; senão insere manualmente
                found = False
                for j in range(beam_combo.count()):
                    if beam_combo.itemData(j) == hist_beam or beam_combo.itemText(j).startswith(hist_beam):
                        beam_combo.setCurrentIndex(j)
                        found = True
                        break
                if not found:
                    beam_combo.insertItem(1, f'{hist_beam}  [histórico]', hist_beam)
                    beam_combo.setCurrentIndex(1)
            elif cut['beam_name'] and candidates and conf_pct >= 40:
                beam_combo.setCurrentIndex(1)
            tbl.setCellWidget(row, self._CUT_COL_VIGA, beam_combo)
            self._cut_combos[uid] = beam_combo

            # ── Conf % ──────────────────────────────────────────────────────
            tbl.setItem(row, self._CUT_COL_CONF,
                        _make_item(f"{conf_pct}%", Qt.AlignCenter,
                                   color=_confidence_color(conf_pct)))
            tbl.item(row, self._CUT_COL_CONF).setData(Qt.UserRole, uid)

            # ── Detalhes sobre o Segmento de Viga ───────────────────────────
            seg_widget = self._build_segmento_viga_widget(cut)
            tbl.setCellWidget(row, self._CUT_COL_DIM, seg_widget)

            # ── Lados A/B da viga para cada laje ────────────────────────────
            laje1_dir = cut.get('direction') or '—'
            own_lado, neigh_lado = self._DIR_TO_LADO.get(
                laje1_dir.upper(), ('', ''))

            # Coluna Laje A recebe a laje que é Lado A; coluna Laje B recebe Lado B.
            # own_lado determina qual laje é A — a outra vai para B.
            laje2_dir = self._DIR_OPPOSITE.get(laje1_dir.upper(), '—') \
                        if laje1_dir not in ('—', '') else '—'
            wall = cut['neigh_laje'] in ('—', '', None, 'nulo', 'NULO')

            # Cores: coluna LADO A em mint, LADO B em azul (igual aos blocos A/B
            # da ficha de segmento de viga). Parede herda muted dentro do widget.
            CM = Accent.PRIMARY      # mint — coluna Lado A
            CB = Accent.INTERACTIVE  # azul — coluna Lado B

            own_widget = self._build_laje_lado_widget(
                cut['own_laje'], laje1_dir,
                cut['own_pos'], cut['own_dist_top'], cut['own_dist_bot'],
                own_lado, cut.get('own_slab_h', ''),
                CM if own_lado != 'B' else CB,
            )
            neigh_widget = self._build_laje_lado_widget(
                cut['neigh_laje'], laje2_dir,
                cut['neigh_pos'], cut['neigh_dist_top'], cut['neigh_dist_bot'],
                neigh_lado, cut.get('neigh_slab_h', ''),
                CB if own_lado != 'B' else CM,
            )

            # own_lado == 'A' → own vai para col A, neigh para col B; caso contrário, inverte
            if own_lado != 'B':
                tbl.setCellWidget(row, self._CUT_COL_LAJE1, own_widget)
                tbl.setCellWidget(row, self._CUT_COL_LAJE2, neigh_widget)
            else:
                tbl.setCellWidget(row, self._CUT_COL_LAJE1, neigh_widget)
                tbl.setCellWidget(row, self._CUT_COL_LAJE2, own_widget)

            # ── Status + TAG (container widget) ─────────────────────────────
            st_combo = QComboBox()
            st_combo.setStyleSheet("font-size:9px;")
            st_combo.view().setWordWrap(True)
            st_combo.addItem(self._CUT_ST_OK,     'ok')
            st_combo.addItem(self._CUT_ST_VISUAL,  'visual')
            st_combo.addItem(self._CUT_ST_SOLIDA,  'solida')
            st_combo.addItem(self._CUT_ST_PILAR,   'pilar')
            mi_v = st_combo.model().item(1)
            mi_s = st_combo.model().item(2)
            mi_p = st_combo.model().item(3)
            if mi_v: mi_v.setForeground(QBrush(QColor(Contextual.GOLD)))
            if mi_s: mi_s.setForeground(QBrush(QColor(Semantic.WARNING)))
            if mi_p: mi_p.setForeground(QBrush(QColor(Contextual.PURPLE)))

            # Restaura status do histórico
            hist_status = hist_cv.get('status', '')
            initial_status = 'ok'
            if hist_status:
                for j in range(st_combo.count()):
                    if st_combo.itemData(j) == hist_status:
                        st_combo.setCurrentIndex(j)
                        initial_status = hist_status
                        break

            # Tag visual (DADO-HISTORICO / DADO-NOVO / PILAR-MIGRADO)
            hist_pilar_migrated = hist_cv.get('pillar_migrated', False)
            hist_pilar_name     = hist_cv.get('pillar_name', '')
            if hist_pilar_migrated and hist_pilar_name:
                tag_text  = f'HISTÓRICO | PILAR:{hist_pilar_name}'
                tag_color = Contextual.PURPLE
            elif is_hist:
                tag_text  = 'DADO-HISTÓRICO'
                tag_color = Semantic.SUCCESS
            else:
                tag_text  = 'DADO-NOVO'
                tag_color = Accent.INTERACTIVE
            tag_lbl = QLabel(f'TAG:{tag_text}')
            tag_lbl.setStyleSheet(
                f'color:{tag_color}; font-size:7px; font-weight:bold;'
                f' padding:1px; background:transparent;'
            )

            # Botão "Migrar para Pilares" (visível só quando status == 'pilar')
            btn_migrar = QPushButton('Buscar pilar e migrar →')
            btn_migrar.setStyleSheet(
                f'font-size:8px; padding:2px 6px;'
                f' background:rgba(160, 112, 255, 0.18); color:{Contextual.PURPLE};'
                f' border:1px solid {Contextual.PURPLE}; border-radius:3px;'
            )
            btn_migrar.setVisible(initial_status == 'pilar')

            st_container = QWidget()
            st_container.setStyleSheet('background:transparent;')
            st_lay = QVBoxLayout(st_container)
            st_lay.setContentsMargins(2, 2, 2, 2)
            st_lay.setSpacing(1)
            st_lay.addWidget(st_combo)
            st_lay.addWidget(tag_lbl)
            st_lay.addWidget(btn_migrar)
            st_lay.addStretch()
            tbl.setCellWidget(row, self._CUT_COL_STATUS, st_container)
            self._cut_status_combos[uid] = st_combo
            self._cut_tag_labels[uid]    = tag_lbl
            self._cut_migrar_btns[uid]   = btn_migrar
            self._cut_row_meta[uid] = {'row': row, 'is_hist': is_hist}

            # Conecta repintura dinâmica + visibilidade botão
            _cut_ref = cut
            st_combo.currentIndexChanged.connect(
                lambda _, u=uid: self._on_cut_status_changed(u))
            btn_migrar.clicked.connect(
                lambda _, u=uid, c=_cut_ref: self._migrate_cut_to_pilar(u, c))

            attention = str(hist_cv.get('attention') or self._cut_attention.get(uid, ''))
            self._cut_attention[uid] = attention
            attention_item = QTableWidgetItem(attention)
            attention_item.setForeground(QBrush(QColor(Contextual.GOLD)))
            attention_item.setToolTip(
                'Clique e escreva sua interpretação; o feedback será salvo no histórico e no HTML.'
            )
            tbl.setItem(row, self._CUT_COL_ATENCAO, attention_item)

            # ── Mini viewer ──────────────────────────────────────────────────
            pts = cut.get('pts') or []
            if pts:
                self._cut_viewer_data[row] = pts
                lbl = QLabel("⏳ Carregando...")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px;")
                tbl.setCellWidget(row, self._CUT_COL_FOTO, lbl)
            else:
                tbl.setItem(row, self._CUT_COL_FOTO,
                            _make_item('—', Qt.AlignCenter,
                                       color=QColor(Colors.TEXT_MUTED)))

            # ── Cor de fundo da linha (status + tag) ────────────────────────
            self._paint_cut_row(row, initial_status, is_hist)
            
        tbl.setUpdatesEnabled(True)
        # Gatilho inicial para os cortes visíveis
        QTimer.singleShot(150, lambda: self._update_dynamic_viewers(tbl, self._cut_viewer_data, self._CUT_COL_FOTO, True))

    # ── Confirmar + persistir histórico ───────────────────────────────────────

    def _migrate_cut_to_pilar(self, uid: str, cut: dict) -> None:
        """
        Busca o pilar mais próximo da geometria do corte e registra a migração.
        Não altera vinculos de lajes — isso é feito em _apply_pre_validation_result
        ao processar invalid_cut_uids. A migração apenas associa nome+geo ao pilar.
        """
        cx, cy = cut.get('center', (0.0, 0.0))

        # Busca no pillar_report pelo centróide de bbox mais próximo
        best_key = None
        best_dist = float('inf')
        for key, pillar in self._pillar_report.items():
            bbox = pillar.get('bbox') or []
            if len(bbox) >= 4:
                px = (float(bbox[0]) + float(bbox[2])) / 2.0
                py = (float(bbox[1]) + float(bbox[3])) / 2.0
            else:
                pts_p = pillar.get('points') or []
                if not pts_p:
                    continue
                px = sum(float(p[0]) for p in pts_p) / len(pts_p)
                py = sum(float(p[1]) for p in pts_p) / len(pts_p)
            dist = math.sqrt((px - cx) ** 2 + (py - cy) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_key = key

        # Busca também em _beam_texts por labels do tipo P1, P2 …
        pilar_re = re.compile(r'^P\d+$', re.IGNORECASE)
        text_match = None
        text_best_dist = float('inf')
        for bt in self._beam_texts:
            if not pilar_re.match(bt.get('text', '')):
                continue
            pos = bt.get('pos') or [0, 0]
            try:
                d = math.sqrt((float(pos[0]) - cx) ** 2 + (float(pos[1]) - cy) ** 2)
            except Exception:
                continue
            if d < text_best_dist:
                text_best_dist = d
                text_match = bt.get('text', '')

        # Prioriza texto mais próximo se dentro de 400u; caso contrário usa report
        pilar_name = (text_match if text_match and text_best_dist < 400
                      else best_key)

        if not pilar_name:
            QMessageBox.warning(
                self, 'Migrar para Pilares',
                'Nenhum pilar encontrado próximo a esta geometria.\n'
                'Verifique manualmente na aba Pilares.'
            )
            return

        # Verifica se já existe na lista de pilares
        ja_existe = pilar_name in self._pillar_report

        # Verifica se já foi migrado antes
        geo = self._cv_geo_key(cut.get('pts', []))
        cv_hist = self._pf_history.setdefault('cut_views', {}).setdefault(geo, {})
        ja_migrado = cv_hist.get('pillar_migrated', False)

        if ja_migrado:
            prev_name = cv_hist.get('pillar_name', pilar_name)
            QMessageBox.information(
                self, 'Migrar para Pilares',
                f'Este corte já foi migrado anteriormente para o Pilar "{prev_name}".\n'
                f'Tag atualizada. Ao confirmar, será removido dos vínculos de laje.'
            )

        # Registra migração no histórico
        cv_hist['pillar_migrated'] = True
        cv_hist['pillar_name']     = pilar_name
        cv_hist['status']          = 'pilar'

        # Atualiza tag visual da linha
        tag_lbl = self._cut_tag_labels.get(uid)
        if tag_lbl:
            migrado_str = ' | PILAR-MIGRADO' if ja_migrado else ''
            tag_lbl.setText(f'TAG:HISTÓRICO | PILAR:{pilar_name}{migrado_str}')
            tag_lbl.setStyleSheet(
                f'color:{Contextual.PURPLE}; font-size:7px; font-weight:bold;'
                ' padding:1px; background:transparent;'
            )

        if ja_existe:
            QMessageBox.information(
                self, 'Migrar para Pilares',
                f'Pilar "{pilar_name}" encontrado na lista de pilares.\n'
                f'O corte será removido dos vínculos de laje ao confirmar.'
            )
        else:
            QMessageBox.warning(
                self, 'Migrar para Pilares',
                f'Pilar "{pilar_name}" identificado por texto, mas não está na lista\n'
                f'automática de pilares. Verifique na aba Pilares.\n'
                f'O corte será removido dos vínculos de laje ao confirmar.'
            )

    # ── Abas de segmentos de vigas ───────────────────────────────────────────

    _SEG_THUMB_W = 880
    _SEG_THUMB_H = 420
    _SEG_ROW_H = 430

    def _build_segment_tab(self, kind: str) -> QWidget:
        """Monta uma lista segmentar LV/FV sem recalcular geometrias do SA."""
        spec = SEGMENT_TAB_SPECS[kind]
        root = QWidget()
        lay = QVBoxLayout(root)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)
        entries = self._segment_data.get(kind, [])
        info = QLabel(
            f"{spec['title']} — {len(entries)} segmento(s). "
            "A foto usa exatamente a geometria vinculada pelo motor SA; "
            "marcar como ignorado remove esse mesmo vínculo após a confirmação."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"font-size:9px; color:{Colors.TEXT_MUTED};")
        lay.addWidget(info)
        lay.addWidget(self._build_segment_table(kind), 1)
        return root

    def _build_segment_table(self, kind: str) -> QTableWidget:
        is_fundo = kind == 'fundo'
        if is_fundo:
            columns = [
                "Viga", "Segmento", "Comprimento", "Largura", "Status",
                "⚑ Atenção / Feedback (editável)", "Foto",
            ]
            col = {
                'beam': 0, 'segment': 1, 'length': 2, 'width': 3,
                'status': 4, 'attention': 5, 'photo': 6,
            }
        else:
            columns = [
                "Viga", "Segmento", "Lado", "Comportamento", "Comprimento",
                "Detalhes do Segmento", "Status",
                "⚑ Atenção / Feedback (editável)", "Foto",
            ]
            col = {
                'beam': 0, 'segment': 1, 'side': 2, 'behavior': 3, 'length': 4,
                'details': 5, 'status': 6, 'attention': 7, 'photo': 8,
            }

        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setProperty('viewer_column', col['photo'])
        table.setProperty('attention_column', col['attention'])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(col['beam'], QHeaderView.Interactive)
        table.setColumnWidth(col['beam'], 150)
        header.setSectionResizeMode(col['attention'], QHeaderView.Interactive)
        table.setColumnWidth(col['attention'], 300)
        header.setSectionResizeMode(col['photo'], QHeaderView.Fixed)
        table.setColumnWidth(col['photo'], self._SEG_THUMB_W + 10)
        if not is_fundo:
            header.setSectionResizeMode(col['details'], QHeaderView.Interactive)
            table.setColumnWidth(col['details'], 240)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(
            QAbstractItemView.CurrentChanged
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.DoubleClicked
        )
        table.verticalHeader().setVisible(False)
        table.setStyleSheet("QTableWidget { font-size:9px; }")
        table.setMinimumHeight(0)

        viewer_data: dict[int, list] = {}
        self._segment_tables[kind] = table
        self._segment_viewer_data[kind] = viewer_data
        table.verticalScrollBar().valueChanged.connect(
            lambda _, t=table, d=viewer_data, c=col['photo']:
                self._update_dynamic_viewers(t, d, c, True)
        )
        table.itemChanged.connect(
            lambda item, t=table: self._on_segment_attention_changed(t, item)
        )

        table.setUpdatesEnabled(False)
        for segment in self._segment_data.get(kind, []):
            row = table.rowCount()
            table.insertRow(row)
            table.setRowHeight(row, self._SEG_ROW_H)
            beam_item = _make_item(segment['beam_name'], bold=True)
            beam_item.setData(Qt.UserRole, segment['uid'])
            table.setItem(row, col['beam'], beam_item)
            table.setItem(row, col['segment'], _make_item(segment['segment_label'], Qt.AlignCenter, bold=True))
            table.setItem(row, col['length'], _make_item(f"{segment['length']:.1f}", Qt.AlignCenter))
            if is_fundo:
                table.setItem(
                    row, col['width'],
                    _make_item(segment.get('width') or '—', Qt.AlignCenter),
                )

            if not is_fundo:
                table.setItem(row, col['side'], _make_item(segment['side'], Qt.AlignCenter, bold=True))
                table.setItem(row, col['behavior'], _make_item(segment['behavior'], Qt.AlignCenter))
                details = segment.get('ficha') or {}
                detail_lines = [f"Tag: {segment.get('tag') or '—'}"]
                for key in ('altura_total', 'largura_total_fundo', 'comprimento_total_fundo',
                            'apoio_inicial', 'apoio_final'):
                    value = details.get(key)
                    if value not in (None, ''):
                        detail_lines.append(f"{key.replace('_', ' ').title()}: {value}")
                detail_label = QLabel('<br>'.join(detail_lines))
                detail_label.setWordWrap(True)
                detail_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                detail_label.setStyleSheet(
                    f"color:{Colors.TEXT_SECONDARY}; padding:4px; background:transparent;"
                )
                table.setCellWidget(row, col['details'], detail_label)

            status_combo = QComboBox()
            status_combo.addItem("Válido — manter vínculo", "valid")
            status_combo.addItem("Ignorar — remover vínculo", "ignore")
            initial_status = segment.get('status') or 'valid'
            status_combo.setCurrentIndex(1 if initial_status == 'ignore' else 0)
            status_combo.currentIndexChanged.connect(
                lambda _, uid=segment['uid'], combo=status_combo:
                    self._on_segment_status_changed(uid, combo)
            )
            table.setCellWidget(row, col['status'], status_combo)
            self._segment_status_combos[segment['uid']] = status_combo

            attention = str(segment.get('attention') or '')
            self._segment_attention[segment['uid']] = attention
            attention_item = QTableWidgetItem(attention)
            attention_item.setForeground(QBrush(QColor(Contextual.GOLD)))
            attention_item.setToolTip("Clique para registrar uma observação desta geometria")
            table.setItem(row, col['attention'], attention_item)

            points = segment.get('points') or []
            if points:
                viewer_data[row] = points
                loading = QLabel("⏳ Carregando...")
                loading.setAlignment(Qt.AlignCenter)
                loading.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:10px;")
                table.setCellWidget(row, col['photo'], loading)
            else:
                table.setItem(row, col['photo'], _make_item('—', Qt.AlignCenter, color=QColor(Colors.TEXT_MUTED)))
            self._paint_segment_row(table, row, initial_status)

        table.setUpdatesEnabled(True)
        QTimer.singleShot(
            150,
            lambda t=table, d=viewer_data, c=col['photo']:
                self._update_dynamic_viewers(t, d, c, True),
        )
        self._restore_table_scroll(table, kind)
        return table

    def _on_segment_attention_changed(self, table: QTableWidget, item: QTableWidgetItem) -> None:
        if item.column() != int(table.property('attention_column')):
            return
        beam_item = table.item(item.row(), 0)
        uid = beam_item.data(Qt.UserRole) if beam_item else None
        if uid:
            self._segment_attention[str(uid)] = item.text().strip()

    def _on_segment_status_changed(self, uid: str, combo: QComboBox) -> None:
        for table in self._segment_tables.values():
            for row in range(table.rowCount()):
                beam_item = table.item(row, 0)
                if beam_item and beam_item.data(Qt.UserRole) == uid:
                    self._paint_segment_row(table, row, combo.currentData() or 'valid')
                    return

    @staticmethod
    def _paint_segment_row(table: QTableWidget, row: int, status: str) -> None:
        background = QColor(Semantic.WARNING_BG_DARK) if status == 'ignore' else QColor(Surface.RAISED)
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item:
                item.setBackground(QBrush(background))

    # ── Aba Convenção de Níveis ────────────────────────────────────────────────

    def _build_niveis_tab(self) -> QWidget:
        """
        Aba Convenção de Níveis.

        Colunas: Nome Doc | Nome Pav | Nível Chegada | Nível Saída | Altura |
                 Lajes (SA) | Pilares | Vigas

        Fonte primária: Elevação Típica (recorte convencao_niveis) — lista TODOS
        os pavimentos do projeto. Fonte secundária: pré-análise SA (laje_niveis).
        Pavimentos SA sem correspondência na Elevação Típica são adicionados ao fim.
        """
        from PySide6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
        )
        from PySide6.QtGui import QFont as _QFont, QColor as _QColor
        from pathlib import Path
        import re as _re

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)

        # ── Viewer do recorte convencao_niveis (se existir) ───────────────────
        niveis_recorte = self._query_niveis_recorte()
        if niveis_recorte:
            dxf_path, label = niveis_recorte
            grp = QGroupBox(f"Recorte Convenção de Níveis — {label}")
            grp_vbox = QVBoxLayout(grp)
            grp_vbox.setContentsMargins(4, 8, 4, 4)
            loading_lbl = QLabel("Carregando recorte…")
            loading_lbl.setAlignment(Qt.AlignCenter)
            loading_lbl.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:11px;")
            grp_vbox.addWidget(loading_lbl)
            self._niveis_gab_vbox    = grp_vbox
            self._niveis_gab_loading = loading_lbl
            self._niveis_dxf_thread  = _DXFReaderThread(dxf_path)
            self._niveis_dxf_thread.finished.connect(self._on_niveis_gabarito_loaded)
            self._niveis_dxf_thread.start()
            lay.addWidget(grp)

        # ── Extrai cotas da Elevação Típica ───────────────────────────────────
        from src.core.niveis_extractor import (
            extract_elevacao_tipica, pav_num_from_sa_name,
            lajes_by_nivel, derive_nome_pav, filter_laje_niveis,
        )
        elevacao_tipica: list = []
        if niveis_recorte:
            try:
                from src.core.dxf_loader import DXFLoader as _DXFLoader
                dxf_data = _DXFLoader.load_dxf(niveis_recorte[0])
                texts_rec = dxf_data.get('texts', []) if dxf_data else []
                elevacao_tipica = extract_elevacao_tipica(texts_rec)
            except Exception:
                pass

        all_pav_data = self._collect_all_pav_niveis()

        # ── Monta lookup SA por pav_num ───────────────────────────────────────
        sa_by_num: dict[int, dict] = {}
        tip_sa: 'dict | None' = None
        for entry_sa in all_pav_data:
            sa_nome = entry_sa['nome']
            num = pav_num_from_sa_name(sa_nome)
            if num is None:
                if _re.search(r'[-_]TIP[-_]', sa_nome, _re.IGNORECASE) and tip_sa is None:
                    tip_sa = entry_sa
            else:
                if num not in sa_by_num:
                    sa_by_num[num] = entry_sa

        # ── Monta linhas da tabela ────────────────────────────────────────────
        rows: list[dict] = []

        def _make_row(num, sa_entry, nome_pav, chegada, saida, altura):
            return {
                'pav_num':    num,
                'nome_doc':   sa_entry['nome']        if sa_entry else '—',
                'nome_pav':   nome_pav,
                'chegada':    chegada,
                'saida':      saida,
                'altura':     altura,
                'laje_list':  sa_entry['laje_niveis']  if sa_entry else [],
                'pilar_list': sa_entry['pilar_niveis'] if sa_entry else [],
                'viga_list':  sa_entry['viga_niveis']  if sa_entry else [],
                'fonte':      sa_entry['fonte']        if sa_entry else '—',
                'is_current': sa_entry is not None and sa_entry['nome'] == self._pavimento,
            }

        if elevacao_tipica:
            matched_nums: set[int] = set()
            for entry in elevacao_tipica:
                num = entry['pav_num']
                sa_info = sa_by_num.get(num)
                if sa_info is None and entry.get('is_tipo') and tip_sa:
                    sa_info = tip_sa
                if sa_info:
                    matched_nums.add(num)
                rows.append(_make_row(num, sa_info, entry['pav_raw'],
                                      entry['chegada'], entry['saida'], entry['altura']))
            for num, sa_entry in sa_by_num.items():
                if num not in matched_nums:
                    rows.append(_make_row(num, sa_entry, derive_nome_pav(num), '?', '?', '?'))
        else:
            for sa_entry in all_pav_data:
                num = pav_num_from_sa_name(sa_entry['nome'])
                rows.append(_make_row(
                    num if num is not None else 5000,
                    sa_entry, derive_nome_pav(num), '?', '?', '?'
                ))

        rows.sort(key=lambda r: r['pav_num'])

        # ── Infobar ───────────────────────────────────────────────────────────
        n_et  = len(elevacao_tipica)
        n_sa  = len(all_pav_data)
        src   = f"Elevação Típica: {n_et} pav.  +  SA: {n_sa} pav." if n_et else f"SA: {n_sa} pav. (sem recorte Conv. Nív.)"
        info_lbl = QLabel(
            f"Pavimento atual: <b>{self._pavimento}</b>  —  "
            f"Lajes detectadas pelo SA: {len(self._slabs)}<br>"
            f"{src}<br>"
            "Colunas Pilares e Vigas disponíveis em versão futura."
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(f"color:{Colors.TEXT_SECONDARY}; font-size:10px;")
        lay.addWidget(info_lbl)

        # ── Tabela: 8 colunas fixas ───────────────────────────────────────────
        # Nome Doc | Nome Pav | Nível Chegada | Nível Saída | Altura | Lajes | Pilares | Vigas
        tbl = QTableWidget(0, 8)
        tbl.setHorizontalHeaderLabels([
            "Nome Doc", "Nome Pav",
            "Nível\nChegada", "Nível\nSaída", "Altura",
            "Lajes (SA)", "Pilares", "Vigas",
        ])
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Stretch)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setAlternatingRowColors(True)
        tbl.setWordWrap(True)
        tbl.setStyleSheet(
            f"QTableWidget {{ background:{Colors.BG_SECONDARY};"
            f" color:{Colors.TEXT_PRIMARY}; gridline-color:{Colors.BORDER_DEFAULT};"
            f" border:none; font-size:10px; }}"
            f"QTableWidget::item:alternate {{ background:{Colors.BG_PANEL}; }}"
            f"QHeaderView::section {{ background:{Colors.BG_PANEL}; color:{Colors.ACCENT_MINT};"
            f" border:none; padding:4px; font-size:9px; font-weight:bold; }}"
        )

        for row in rows:
            ri = tbl.rowCount()
            tbl.insertRow(ri)

            # Col 0: Nome Doc
            item_doc = QTableWidgetItem(row['nome_doc'])
            if row['is_current']:
                f = _QFont(); f.setBold(True)
                item_doc.setFont(f)
                item_doc.setForeground(_QColor(Colors.ACCENT_MINT))
            else:
                item_doc.setForeground(_QColor(Colors.TEXT_SECONDARY))
            item_doc.setToolTip(row['nome_doc'])
            tbl.setItem(ri, 0, item_doc)

            # Col 1: Nome Pav
            item_np = QTableWidgetItem(row['nome_pav'])
            item_np.setForeground(_QColor(Colors.TEXT_PRIMARY))
            tbl.setItem(ri, 1, item_np)

            # Col 2: Nível Chegada
            item_ch = QTableWidgetItem(row['chegada'])
            if row['chegada'] != '?':
                item_ch.setForeground(_QColor(Contextual.GOLD))
            else:
                item_ch.setForeground(_QColor(Colors.TEXT_DIM))
            tbl.setItem(ri, 2, item_ch)

            # Col 3: Nível Saída
            item_sa = QTableWidgetItem(row['saida'])
            if row['saida'] != '?':
                item_sa.setForeground(_QColor(Contextual.GOLD))
            else:
                item_sa.setForeground(_QColor(Colors.TEXT_DIM))
            tbl.setItem(ri, 3, item_sa)

            # Col 4: Altura
            item_al = QTableWidgetItem(row['altura'])
            if row['altura'] != '?':
                item_al.setForeground(_QColor(Colors.ACCENT_MINT))
            else:
                item_al.setForeground(_QColor(Colors.TEXT_DIM))
            tbl.setItem(ri, 4, item_al)

            # Col 5: Lajes (agrupadas por nível, com anti-alucinação)
            if row['laje_list']:
                validas, suspeitas = filter_laje_niveis(
                    row['laje_list'], row['chegada'], row['saida']
                )
                laj_txt = lajes_by_nivel(validas) if validas else '—'
                if suspeitas:
                    laj_txt += f'\n⚠ {len(suspeitas)} suspeito(s) filtrado(s)'
            else:
                laj_txt = '—'
            item_laj = QTableWidgetItem(laj_txt)
            item_laj.setToolTip(f"[{row['fonte']}]")
            tbl.setItem(ri, 5, item_laj)

            # Col 6: Pilares (com anti-alucinação)
            if row.get('pilar_list'):
                vp, sp = filter_laje_niveis(row['pilar_list'], row['chegada'], row['saida'])
                pil_txt = lajes_by_nivel(vp) if vp else '—'
                if sp:
                    pil_txt += f'\n⚠ {len(sp)} suspeito(s) filtrado(s)'
            else:
                pil_txt = '—'
            item_pil = QTableWidgetItem(pil_txt)
            if pil_txt == '—':
                item_pil.setForeground(_QColor(Colors.TEXT_DIM))
            tbl.setItem(ri, 6, item_pil)

            # Col 7: Vigas (com anti-alucinação)
            if row.get('viga_list'):
                vv, sv = filter_laje_niveis(row['viga_list'], row['chegada'], row['saida'])
                vig_txt = lajes_by_nivel(vv) if vv else '—'
                if sv:
                    vig_txt += f'\n⚠ {len(sv)} suspeito(s) filtrado(s)'
            else:
                vig_txt = '—'
            item_vig = QTableWidgetItem(vig_txt)
            if vig_txt == '—':
                item_vig.setForeground(_QColor(Colors.TEXT_DIM))
            tbl.setItem(ri, 7, item_vig)

        tbl.resizeRowsToContents()
        lay.addWidget(tbl, 1)

        n_com_cota = sum(1 for r in rows if r['chegada'] != '?')
        footer = QLabel(
            f"{len(rows)} pavimento(s)  |  {n_com_cota} com cotas da Elevação Típica"
        )
        footer.setStyleSheet(f"color:{Colors.TEXT_DIM}; font-size:9px;")
        lay.addWidget(footer)

        lay.addStretch()
        scroll.setWidget(inner)
        return scroll

    # ── Aba Pilares Especiais ───────────────────────────────────────────────────

    def _build_especiais_tab(self) -> QWidget:
        """Aba para pilares com formato não-retangular (em L, em U, em T, Circular, Especial)."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        info = QLabel(
            "Pilares com geometria especial (em L, em U, em T, Circular, Especial). "
            "8 lados A–H para análise estendida."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{Colors.TEXT_MUTED}; font-size:9px; padding:3px;")
        lay.addWidget(info)

        lay.addWidget(self._build_especiais_table(), 1)
        return w

    def _build_especiais_table(self) -> QTableWidget:
        cols = [
            "Nome", "Classif. SA", "Classif. Override",
            "Formato Pilar", "Conf %", "Nível",
            "Lado-A", "Lado-B", "Lado-C", "Lado-D",
            "Lado-E", "Lado-F", "Lado-G", "Lado-H", "Foto",
        ]
        tbl = QTableWidget(0, len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(self._ESP_COL_NOME, QHeaderView.Fixed)
        tbl.setColumnWidth(self._ESP_COL_NOME, 75)
        for col in (self._ESP_COL_LADO_A, self._ESP_COL_LADO_B,
                    self._ESP_COL_LADO_C, self._ESP_COL_LADO_D,
                    self._ESP_COL_LADO_E, self._ESP_COL_LADO_F,
                    self._ESP_COL_LADO_G, self._ESP_COL_LADO_H):
            hdr.setSectionResizeMode(col, QHeaderView.Interactive)
            tbl.setColumnWidth(col, self._PIL_LADO_COL_W)
        hdr.setSectionResizeMode(self._ESP_COL_OVERRIDE, QHeaderView.Interactive)
        tbl.setColumnWidth(self._ESP_COL_OVERRIDE, 180)
        hdr.setSectionResizeMode(self._ESP_COL_FOTO, QHeaderView.Fixed)
        tbl.setColumnWidth(self._ESP_COL_FOTO, self._PIL_COL_FOTO_W)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setStyleSheet("QTableWidget { font-size:9px; }")
        self._especiais_table = tbl
        self._especiais_viewer_data: dict = {}
        self._especiais_rows: dict[str, int] = {}
        tbl.verticalScrollBar().valueChanged.connect(
            lambda _: self._update_dynamic_viewers(
                self._especiais_table, self._especiais_viewer_data,
                self._ESP_COL_FOTO, False)
        )
        self._populate_especiais_table()
        return tbl

    def _populate_especiais_table(self):
        if not hasattr(self, '_especiais_table'):
            return
        tbl = self._especiais_table
        tbl.setUpdatesEnabled(False)
        tbl.setRowCount(0)
        self._especiais_rows.clear()
        self._especiais_viewer_data.clear()
        nr_pilares = (self._nivel_report or {}).get('pilares', {})

        def _pil_sort_key(kv):
            k = kv[0]
            if k.endswith('__ALT'):
                return self._natural_sort_key(k[:-5]) + [1]
            return self._natural_sort_key(k) + [0]

        sorted_items = sorted(self._pillar_report.items(), key=_pil_sort_key)
        for key, pillar in sorted_items:
            pts = pillar.get('points') or []
            formato = _pilar_formato(pts)
            if formato == 'Retangular':
                continue   # retangulares ficam na aba Pilares

            row = tbl.rowCount()
            tbl.insertRow(row)
            tbl.setRowHeight(row, self._PIL_ROW_H)
            self._especiais_rows[key] = row

            name = pillar.get('name') or key
            classif = pillar.get('classification') or 'INDETERMINADO'

            # Restaura override do histórico
            geo_key = self._pillar_geo_key(pillar)
            hist_pil = self._pf_history.get('pilares', {}).get(geo_key)
            if hist_pil and hist_pil.get('classification'):
                classif = hist_pil['classification']

            phys = self._physical_type_for(classif)
            conf_pct = 0 if classif == 'INDETERMINADO' else 95
            if classif in (_NAO_PILAR_SOLIDO, _NAO_PILAR_VISUAL):
                conf_pct = 100

            p_nr = nr_pilares.get(key, {})
            nivel_str = p_nr.get('level_str') or '—'
            conf_color = _confidence_color(conf_pct)

            # Nome
            nome_item = _make_item(name, bold=True)
            f = nome_item.font(); f.setPixelSize(18); f.setBold(True)
            nome_item.setFont(f)
            nome_item.setData(Qt.UserRole, key)
            tbl.setItem(row, self._ESP_COL_NOME, nome_item)

            # Classif. SA com sufixo tipo físico
            if phys == 'visual_only':
                classif_sa_display = f'{classif}  ·  visual'
            elif phys == 'solid':
                classif_sa_display = f'{classif}  ·  sólido'
            else:
                classif_sa_display = classif
            tbl.setItem(row, self._ESP_COL_CLASSIF, _make_item(classif_sa_display))
            tbl.setItem(row, self._ESP_COL_CONF,
                        _make_item(f"{conf_pct}%", Qt.AlignCenter, color=conf_color))
            tbl.setItem(row, self._ESP_COL_NIVEL,
                        _make_item(nivel_str, Qt.AlignCenter))

            # Formato Pilar
            fmt_color = PILLAR_FORMATO_COLORS.get(formato, '#f07070')
            fmt_lbl = QLabel(PILLAR_FORMATO_LABELS.get(formato, formato))
            fmt_lbl.setWordWrap(True)
            fmt_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            fmt_lbl.setStyleSheet(
                f"color:{fmt_color}; font-size:9px; padding:3px; background:transparent;"
            )
            tbl.setCellWidget(row, self._ESP_COL_FORMATO, fmt_lbl)

            # Lados A-D (mesma lógica dos retangulares)
            invalid_geom = classif.upper() in _NAO_SE_APLICA_CLASSIFS
            for col, side in (
                (self._ESP_COL_LADO_A, 'A'), (self._ESP_COL_LADO_B, 'B'),
                (self._ESP_COL_LADO_C, 'C'), (self._ESP_COL_LADO_D, 'D'),
            ):
                if invalid_geom:
                    item = _make_item('Não se aplica', color=QColor(Colors.TEXT_MUTED))
                else:
                    cell_text = self._get_side_cell(pillar, side)
                    item = _make_item(cell_text)
                    item.setToolTip(cell_text)
                tbl.setItem(row, col, item)

            # Lados E-H (placeholder — conteúdo definido pelo usuário futuramente)
            for col in (self._ESP_COL_LADO_E, self._ESP_COL_LADO_F,
                        self._ESP_COL_LADO_G, self._ESP_COL_LADO_H):
                tbl.setItem(row, col, _make_item('—', Qt.AlignCenter,
                                                  color=QColor(Colors.TEXT_MUTED)))

            # Override combo
            combo = QComboBox()
            combo.setStyleSheet("font-size:9px;")
            options = list(PILLAR_CLASSIFICATION_OPTIONS)
            sep_idx = options.index(_SEPARADOR_ITEM) if _SEPARADOR_ITEM in options else len(options)
            for term in self._term_type_map:
                if term not in options and term not in (_SEPARADOR_ITEM, _SEPARADOR_GEOM):
                    options.insert(sep_idx, term); sep_idx += 1
            _SEPARADORES = {_SEPARADOR_ITEM, _SEPARADOR_GEOM}
            for j, opt in enumerate(options):
                combo.addItem(opt)
                mi = combo.model().item(j)
                if not mi: continue
                if opt in _SEPARADORES:
                    mi.setEnabled(False)
                    mi.setForeground(QBrush(QColor(Colors.TEXT_MUTED)))
                elif opt in (_NAO_PILAR_SOLIDO, _NAO_PILAR_VISUAL):
                    mi.setForeground(QBrush(QColor(Contextual.GOLD)))
                elif opt in (_GEOM_ERRADA_SOLIDA, _GEOM_ERRADA_VISUAL):
                    mi.setForeground(QBrush(QColor(Semantic.WARNING)))
            idx = next((i for i, o in enumerate(options) if o == classif), 0)
            combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(
                lambda _, k=key, c=combo: self._on_pillar_classif_changed(k, c))
            tbl.setCellWidget(row, self._ESP_COL_OVERRIDE, combo)
            self._pillar_combos[key] = combo   # registra p/ get_result() e _save_pf_history()

            # Mini viewer
            if pts:
                self._especiais_viewer_data[row] = pts
                lbl = QLabel("⏳ Carregando...")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px;")
                tbl.setCellWidget(row, self._ESP_COL_FOTO, lbl)
            else:
                tbl.setItem(row, self._ESP_COL_FOTO,
                            _make_item('—', Qt.AlignCenter, color=QColor(Colors.TEXT_MUTED)))

            # Cor de linha
            bg = self._row_bg_for_classif(classif)
            skip = {self._ESP_COL_OVERRIDE, self._ESP_COL_FOTO, self._ESP_COL_FORMATO}
            for col in range(tbl.columnCount()):
                if col in skip: continue
                it = tbl.item(row, col)
                if it:
                    if bg: it.setBackground(QBrush(bg))
                    else:  it.setBackground(QBrush())

        tbl.setUpdatesEnabled(True)
        QTimer.singleShot(150, lambda: self._update_dynamic_viewers(
            tbl, self._especiais_viewer_data, self._ESP_COL_FOTO, False))

    def _query_niveis_recorte(self) -> 'tuple[str, str] | None':
        """Busca recorte convencao_niveis aprovado para esta obra."""
        if not self._db_path:
            return None
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT output_path FROM obra_recortes "
                "WHERE obra_name=? AND recorte_type='convencao_niveis' AND status IN ('approved','manual') "
                "ORDER BY recorte_index DESC LIMIT 1",
                (self._obra,)
            ).fetchone()
            conn.close()
            if row and row['output_path'] and os.path.isfile(row['output_path']):
                return row['output_path'], "Convenção de Níveis"
        except Exception:
            pass
        return None

    def _collect_all_pav_niveis(self) -> 'list[dict]':
        """
        Coleta dados de níveis de todos os pavimentos.

        Retorna lista de dicts:
          nome        : str  — nome SA do pavimento
          laje_niveis : list[{name, nivel_str}]
          pilar_niveis: list[{name, nivel_str}]  (vazio se não disponível)
          viga_niveis : list[{name, nivel_str}]  (vazio se não disponível)
          fonte       : str  — 'SA atual' | 'estado JSON'

        Prioridade:
        1. Pavimento atual → self._slabs (SA) + self._nivel_report (pilares)
        2. Outros pavimentos → pre_processamento_estado.json
        """
        result: list = []
        seen_pavs: set = set()

        # 1. Pavimento atual — lajes do SA
        current_laje: list = []
        for slab in self._slabs:
            name = slab.get('name') or ''
            fields = slab.get('fields') or {}
            nivel_str = (
                fields.get('laje_nivel') or slab.get('nivel') or slab.get('level') or ''
            )
            if name:
                current_laje.append({'name': name, 'nivel_str': str(nivel_str).strip()})

        # 1b. Pilares do pav atual via nivel_report
        current_pilar: list = []
        for key, pdata in (self._nivel_report.get('pilares') or {}).items():
            pname = pdata.get('name') or key
            lv = pdata.get('level_str') or ''
            if pname and lv:
                current_pilar.append({'name': pname, 'nivel_str': lv})

        if self._pavimento:
            result.append({
                'nome':         self._pavimento,
                'laje_niveis':  current_laje,
                'pilar_niveis': current_pilar,
                'viga_niveis':  [],
                'fonte':        'SA atual',
            })
            seen_pavs.add(self._pavimento)

        # 2. Outros pavimentos → pre_processamento_estado.json
        try:
            from pathlib import Path as _P
            DADOS_OBRAS = _P("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
            estado_path = DADOS_OBRAS / self._obra / "pre_processamento_estado.json"
            if estado_path.exists():
                import json as _json
                estado = _json.loads(estado_path.read_text(encoding='utf-8'))
                pavs_json = estado.get('ficha', {}).get('pavimentos', [])
                for pav in pavs_json:
                    pav_nome = pav.get('nome', '')
                    if not pav_nome or pav_nome in seen_pavs:
                        continue
                    laje_niveis = pav.get('laje_niveis', [])
                    if not laje_niveis:
                        nc = pav.get('nivel_chegada', 0)
                        ns = pav.get('nivel_saida', 0)
                        laje_niveis = [{'name': '(chegada)', 'nivel_str': str(nc)}]
                        if ns != nc:
                            laje_niveis.append({'name': '(saída)', 'nivel_str': str(ns)})
                    result.append({
                        'nome':         pav_nome,
                        'laje_niveis':  laje_niveis,
                        'pilar_niveis': pav.get('pilar_niveis', []),
                        'viga_niveis':  pav.get('viga_niveis', []),
                        'fonte':        'estado JSON',
                    })
                    seen_pavs.add(pav_nome)
        except Exception:
            pass

        current_row = [r for r in result if r['nome'] == self._pavimento]
        others      = sorted([r for r in result if r['nome'] != self._pavimento],
                             key=lambda x: x['nome'])
        return current_row + others

    def _on_niveis_gabarito_loaded(self, doc) -> None:
        """Renderiza o recorte de Convenção de Níveis na GUI thread."""
        vbox = getattr(self, '_niveis_gab_vbox', None)
        loading_lbl = getattr(self, '_niveis_gab_loading', None)
        if vbox is None:
            self._niveis_dxf_thread = None
            return
        try:
            if loading_lbl:
                loading_lbl.hide()
                vbox.removeWidget(loading_lbl)
            if not doc:
                vbox.addWidget(QLabel("Falha ao carregar DXF do recorte."))
                return
            try:
                from ezdxf.addons.drawing import RenderContext, Frontend
                from ezdxf.addons.drawing.pyqt import PyQtBackend
                from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy, ColorPolicy
                from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

                msp = doc.modelspace()
                scene = QGraphicsScene()
                scene.setBackgroundBrush(QColor(Colors.BG_PANEL))
                for layer in doc.layers:
                    layer.on(); layer.thaw()
                for ent in doc.entitydb.values():
                    if hasattr(ent, 'dxf') and hasattr(ent.dxf, 'invisible'):
                        ent.dxf.invisible = 0
                ctx = RenderContext(doc)
                out = PyQtBackend(scene)
                cfg = Configuration(
                    background_policy=BackgroundPolicy.CUSTOM,
                    custom_bg_color=Colors.BG_PANEL,
                    color_policy=ColorPolicy.COLOR,
                )
                Frontend(ctx, out, config=cfg).draw_layout(msp)
                rect = scene.itemsBoundingRect()
                if rect.isNull():
                    raise ValueError("cena vazia")
                viewer = _MiniDXFView(
                    scene, rect.left(), rect.top(), rect.right(), rect.bottom(),
                    thumb_w=900, thumb_h=260, highlight_pts=[],
                )
                viewer._dxf_scene_ref = scene
                viewer.setMinimumHeight(200)
                viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                vbox.addWidget(viewer)
            except Exception as e:
                vbox.addWidget(QLabel(f"Falha ao renderizar: {e}"))
        finally:
            self._niveis_gab_vbox = None
            self._niveis_gab_loading = None
            self._niveis_dxf_thread = None

    def _confirm_and_save(self) -> None:
        """Salva histórico de pré-ficha (geometria → override) e aceita o diálogo."""
        self._save_pf_history()
        self.accept()

    # ── Estado de Análise (snapshot persistente p/ headless) ──────────────────

    def _analysis_state_path(self) -> str:
        """Caminho fixo do snapshot de estado: html_fichas/{obra}/estado_{pav}.json"""
        base = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', '..', 'scripts', 'arete', 'html_fichas', self._obra,
        ))
        pav_slug = re.sub(r'[^\w\-]', '_', self._pavimento)[:60]
        return os.path.join(base, f'estado_{pav_slug}.json')

    def _save_analysis_state(self) -> None:
        """Serializa o estado completo da análise para JSON headless-friendly."""
        try:
            state_path = self._analysis_state_path()
            os.makedirs(os.path.dirname(state_path), exist_ok=True)

            nr_pilares = (self._nivel_report or {}).get('pilares', {})

            # Pilares: geometria + classificação atual + lajes enriquecidas
            pilares_serial: list[dict] = []
            for key, pillar in sorted(
                self._pillar_report.items(),
                key=lambda kv: self._natural_sort_key(kv[0])
            ):
                combo = self._pillar_combos.get(key)
                classif = combo.currentText() if combo else pillar.get('classification', 'INDETERMINADO')
                pilares_serial.append({
                    'key':            key,
                    'name':           pillar.get('name') or key,
                    'classification': classif,
                    'orientation':    pillar.get('orientation') or 'vertical',
                    'points':         pillar.get('points') or [],
                    'bbox':           pillar.get('bbox') or [],
                    'lajes':          pillar.get('lajes') or [],
                    'nivel_str':      (nr_pilares.get(key) or {}).get('level_str') or '',
                    'lado_A':         self._get_side_cell(pillar, 'A'),
                    'lado_B':         self._get_side_cell(pillar, 'B'),
                    'lado_C':         self._get_side_cell(pillar, 'C'),
                    'lado_D':         self._get_side_cell(pillar, 'D'),
                    'atencao':        self._atencao_notes.get(key, ''),
                })

            # Slabs
            slabs_serial = [
                {
                    'name':   s.get('name') or '',
                    'nivel':  (s.get('fields') or {}).get('laje_nivel') or s.get('nivel') or '',
                    'height': (s.get('fields') or {}).get('laje_h') or s.get('height') or '',
                }
                for s in (self._slabs or [])
            ]

            # Cortes de viga
            cuts_serial = []
            for cut in self._cut_view_data:
                combo = self._cut_combos.get(cut['uid'])
                sc = self._cut_status_combos.get(cut['uid'])
                cuts_serial.append({
                    'uid':        cut['uid'],
                    'beam_name':  combo.currentText() if combo else cut.get('beam_name', ''),
                    'conf_pct':   cut.get('conf_pct', 0),
                    'own_laje':   cut.get('own_laje', ''),
                    'neigh_laje': cut.get('neigh_laje', ''),
                    'beam_h':     cut.get('beam_h', ''),
                    'status':     sc.currentText() if sc else 'Válido',
                    'atencao':    self._cut_attention.get(cut['uid'], ''),
                    'pts':        cut.get('pts') or [],
                })

            # Segmentos
            segs_serial: dict[str, list] = {}
            for kind in SEGMENT_TAB_SPECS:
                segs_serial[kind] = []
                for raw in self._segment_data.get(kind, []):
                    seg = serializable_segment(raw)
                    cb = self._segment_status_combos.get(seg['uid'])
                    segs_serial[kind].append({
                        'uid':           seg['uid'],
                        'beam_name':     seg['beam_name'],
                        'segment_label': seg['segment_label'],
                        'side':          seg['side'],
                        'behavior':      seg['behavior'],
                        'length':        seg['length'],
                        'width':         seg.get('width', ''),
                        'status':        cb.currentText() if cb else seg.get('status', 'valid'),
                        'atencao':       self._segment_attention.get(seg['uid'], seg.get('attention', '')),
                        'points':        seg.get('points') or [],
                    })

            state = {
                'gerado_em':  datetime.now().isoformat(timespec='seconds'),
                'obra':       self._obra,
                'pavimento':  self._pavimento,
                'db_path':    self._db_path or '',
                'pilares':    pilares_serial,
                'slabs':      slabs_serial,
                'cortes':     cuts_serial,
                'segmentos':  segs_serial,
            }
            with open(state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # snapshot é best-effort — nunca bloquear o usuário

    # ── Export HTML Snapshot ───────────────────────────────────────────────────

    def _widget_to_b64_png(self, widget) -> str:
        """Captura um QWidget como PNG base64."""
        try:
            from PySide6.QtGui import QPixmap
            px = widget.grab()
            if px.isNull():
                return ''
            from PySide6.QtCore import QBuffer, QByteArray, QIODevice
            buf = QBuffer()
            buf.open(QIODevice.WriteOnly)
            px.save(buf, 'PNG')
            import base64
            return base64.b64encode(buf.data().data()).decode('ascii')
        except Exception:
            return ''

    def _file_to_b64(self, path: str) -> str:
        """Lê um arquivo PNG do filesystem e retorna base64."""
        try:
            import base64
            with open(path, 'rb') as f:
                return base64.b64encode(f.read()).decode('ascii')
        except Exception:
            return ''

    def _find_n4_png(self, class_prefix: str, item_name: str) -> str:
        """Busca render N4 mais recente: relatorios/{ts}/png/{class_prefix}_{item_name}.png."""
        import glob as _glob
        base = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', '..', 'scripts', 'arete', 'relatorios'
        ))
        pattern = os.path.join(base, '*', 'png', f'{class_prefix}_{item_name}.png')
        matches = sorted(_glob.glob(pattern), reverse=True)
        return self._file_to_b64(matches[0]) if matches else ''

    def _render_ezdxf_b64(self, dxf_path: str, width: int = 900, height: int = 600) -> str:
        """Renderiza qualquer DXF com ezdxf+matplotlib (fundo branco). Retorna base64 PNG."""
        if not os.path.exists(dxf_path):
            return ''
        try:
            import io, base64
            import ezdxf
            from ezdxf.addons.drawing import RenderContext, Frontend
            from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            dpi = 150
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
            ax = fig.add_axes([0, 0, 1, 1])
            ctx = RenderContext(doc)
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(msp)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=dpi, facecolor='white', bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode('ascii')
        except Exception as exc:
            print(f'[HTML] _render_ezdxf_b64 falhou ({dxf_path}): {exc}', flush=True)
            return ''

    def _find_pilar_dxf(self, view_type: str, item_name: str, n4: bool = False) -> str:
        """Retorna path do DXF da vista solicitada.
        n4=True → /n4/PL_preview_{nome}.dxf (combined gerado pelo CE via N2).
        n4=False → root Fase-6 com split CIMA/ABCD/GRADES (N3, gerado via Fase-4/N1).
        """
        if not self._obra:
            return ''
        base = os.path.join('D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra, 'Fase-6_Execucao_CAD')
        if n4:
            # CE gera PL_preview_{nome}.dxf (combined) em /n4/ — não tem split views
            p = os.path.join(base, 'n4', f'PL_preview_{item_name}.dxf')
            return p if os.path.exists(p) else ''
        # N3: split views em root Fase-6
        if view_type == 'CIMA':
            filenames = [f'PL_CIMA_preview_{item_name}.dxf']
        elif view_type == 'ABCD':
            filenames = [f'PL_ABCD_preview_{item_name}.dxf']
        elif view_type == 'GRADES':
            filenames = [f'PL_GRADES_preview_{item_name}.dxf']
        else:
            filenames = [f'PL_preview_{item_name}.dxf']
        for fn in filenames:
            p = os.path.join(base, fn)
            if os.path.exists(p):
                return p
        return ''

    def _render_n2_recorte_b64(self, item_name: str, width: int = 700, height: int = 500) -> str:
        """Renderiza o DXF recorte N2 mais recente do pilar (Fase-2 triagem)."""
        if not self._obra:
            return ''
        import glob as _glob
        recortes_base = os.path.join(
            'D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra,
            'Fase-2_Triagem', 'recortes_reversos'
        )
        # Busca em subpastas PL/PIL do 13 PAV
        pattern = os.path.join(recortes_base, '**', f'PIL_{item_name}_motor_*.dxf')
        matches = sorted(_glob.glob(pattern, recursive=True), reverse=True)
        if not matches:
            return ''
        return self._render_ezdxf_b64(matches[0], width=width, height=height)

    def _n1_ficha_html_pilar(self, pilar_key: str) -> str:
        """Retorna HTML completo com TODOS os campos SA do pilar (Ficha N1 SA)."""
        import html as _hl
        pillar = self._pillar_report.get(pilar_key, {})
        if not pillar:
            return '<span style="color:#555">—</span>'
        nr_entry = (self._nivel_report or {}).get('pilares', {}).get(pilar_key, {})

        def _row(label: str, val, color: str = '#7eb8f7') -> str:
            return (f'<tr><td style="color:{color};padding:1px 5px;white-space:nowrap;'
                    f'font-weight:600">{_hl.escape(str(label))}</td>'
                    f'<td style="padding:1px 5px">{_hl.escape(str(val))}</td></tr>')

        def _sep(label: str) -> str:
            return (f'<tr><td colspan="2" style="padding:3px 5px 1px;color:#4fc3a1;'
                    f'font-weight:700;border-top:1px solid #333">{_hl.escape(label)}</td></tr>')

        rows = []
        # ── Identidade ────────────────────────────────────────────────────────
        rows.append(_sep('IDENTIDADE'))
        rows.append(_row('Nome', pillar.get('name', pilar_key)))
        rows.append(_row('Classificação', pillar.get('classification', '—')))
        rows.append(_row('Tipo físico', pillar.get('physical_type', '—')))
        rows.append(_row('Shape', pillar.get('shape_type', '—')))
        rows.append(_row('Orientação', pillar.get('orientation', '—')))
        rows.append(_row('Ignora vigas?', 'Sim' if pillar.get('ignore_in_beams') else 'Não'))
        rows.append(_row('Geo. fonte', pillar.get('geometry_source', '—')))

        # ── Geometria ─────────────────────────────────────────────────────────
        rows.append(_sep('GEOMETRIA'))
        pts = pillar.get('points') or []
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            w, h_ = max(xs) - min(xs), max(ys) - min(ys)
            rows.append(_row('Largura DXF', f'{w:.1f}'))
            rows.append(_row('Altura DXF', f'{h_:.1f}'))
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            rows.append(_row('Centro', f'({cx:.1f}, {cy:.1f})'))
        bbox = pillar.get('bbox')
        if bbox:
            rows.append(_row('BBox', f'{bbox[0]:.1f},{bbox[1]:.1f} → {bbox[2]:.1f},{bbox[3]:.1f}'))

        # ── Nível ─────────────────────────────────────────────────────────────
        rows.append(_sep('NÍVEL'))
        if nr_entry:
            for k, v in nr_entry.items():
                if v not in (None, '', 0, 0.0):
                    rows.append(_row(k, v))
        else:
            rows.append(_row('nivel_str', pillar.get('nivel_str', '—')))

        # ── Lajes adjacentes (ABCD) ──────────────────────────────────────────
        rows.append(_sep('LAJES ADJACENTES'))
        lajes = pillar.get('lajes') or []
        if lajes:
            for lj in lajes:
                nome_lj = lj.get('laje') or lj.get('laje_name') or '?'
                side = lj.get('side', '?')
                face = lj.get('face', '')
                src  = lj.get('side_source', lj.get('source', ''))
                dist = lj.get('dist', '')
                alt  = lj.get('altura', lj.get('alt', ''))
                niv  = lj.get('nivel_str', lj.get('nivel', ''))
                detail = f'Side={side}'
                if face and face not in ('AUTO', ''):
                    detail += f' Face={face}'
                if alt:
                    detail += f' Alt={alt}'
                if niv:
                    detail += f' Nív={niv}'
                if dist:
                    detail += f' dist={float(dist):.0f}'
                if src:
                    detail += f' [{src}]'
                col = {'A': '#ff9f43', 'B': '#4fc3a1', 'C': '#e17055', 'D': '#74b9ff'}.get(side, '#aaa')
                rows.append(_row(nome_lj, detail, color=col))
        else:
            rows.append(_row('—', 'sem lajes vinculadas'))

        # ── Vigas vinculadas ─────────────────────────────────────────────────
        beams = pillar.get('beams') or []
        if beams:
            rows.append(_sep('VIGAS'))
            for b in beams:
                bname = b.get('name') or b.get('beam_name', '?')
                bside = b.get('side', '')
                btyp  = b.get('type', b.get('behavior', ''))
                detail = f'lado={bside}' if bside else ''
                if btyp:
                    detail += f' tipo={btyp}'
                rows.append(_row(bname, detail or '—', color='#7eb8f7'))

        # ── Campos extras ────────────────────────────────────────────────────
        skip = {'name', 'classification', 'physical_type', 'shape_type', 'orientation',
                'ignore_in_beams', 'geometry_source', 'points', 'lajes', 'beams',
                'bbox', 'nivel_str', 'lajes_adjacentes', 'preficha_reviewed',
                'confidence_map', 'links', 'issues', 'needs_geometry',
                'alt_for_original_key', 'geometry_alt_candidate'}
        extras = {k: v for k, v in pillar.items() if k not in skip
                  and v not in (None, '', 0, 0.0, [], {})}
        if extras:
            rows.append(_sep('OUTROS'))
            for k, v in extras.items():
                rows.append(_row(k, str(v)[:120]))

        return (f'<table style="font-size:9px;border-collapse:collapse;'
                f'background:#181818">{"".join(rows)}</table>')

    def _n3_ficha_html_pilar(self, item_name: str) -> str:
        """Retorna HTML compacto com dados Fase-4 JSON do pilar (Ficha N3 informacional)."""
        import html as _hl, json as _json
        if not self._obra:
            return '<span style="color:#555">sem obra</span>'
        json_path = os.path.join(
            'D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra,
            'Fase-4_Sincronizacao', 'JSON_Pilares', f'{item_name}.json'
        )
        if not os.path.exists(json_path):
            return '<span style="color:#555">sem JSON N3</span>'
        try:
            with open(json_path, encoding='utf-8') as f:
                data = _json.load(f)
            skip = {'_sa_meta', 'numero', 'nome', 'pavimento', 'modo_distribuicao'}
            entries = []
            for k, v in data.items():
                if k in skip:
                    continue
                if v in (0, 0.0, '', None):
                    continue
                entries.append(
                    f'<tr><td style="color:#4fc3a1;padding:1px 4px;white-space:nowrap">'
                    f'{_hl.escape(str(k))}</td>'
                    f'<td style="padding:1px 4px">{_hl.escape(str(v))}</td></tr>'
                )
            if not entries:
                return '<span style="color:#555">sem dados</span>'
            return f'<table style="font-size:9px;border-collapse:collapse">{"".join(entries)}</table>'
        except Exception:
            return '<span style="color:#555">erro</span>'

    def _find_n2_png(self, obra: str, subfolder: str, item_name: str) -> str:
        """Busca render N2 em DADOS-OBRAS/{obra}/Fase-6_Execucao_CAD/{subfolder}/{item}_n2.png."""
        path = os.path.join(
            'D:/Agente-cad-PYSIDE/DADOS-OBRAS', obra,
            'Fase-6_Execucao_CAD', subfolder, f'{item_name}_n2.png'
        )
        return self._file_to_b64(path)

    def _n2_ficha_html(self, classe: str, elemento_id: str) -> str:
        """Retorna HTML compacto dos campos N2 (ficha informacional do DB)."""
        if not self._db_path:
            return '<span style="color:#555">sem DB</span>'
        try:
            import sqlite3, json as _json, html as _hl
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT campos_json FROM reverse_eng_fichas "
                "WHERE classe=? AND elemento_id=? AND obra_name=? "
                "ORDER BY id DESC LIMIT 1",
                (classe, elemento_id, self._obra),
            ).fetchone()
            conn.close()
            if not row:
                return '<span style="color:#555">—</span>'
            data = _json.loads(row[0])
            skip = {'_er_meta', 'modo_distribuicao', 'pavimento', 'numero', 'nome'}
            entries = []
            for k, v in data.items():
                if k in skip:
                    continue
                if v in (0, 0.0, '', None) or (isinstance(v, list) and not v):
                    continue
                entries.append(
                    f'<tr><td style="color:#7eb8f7;padding:1px 4px;white-space:nowrap">'
                    f'{_hl.escape(str(k))}</td>'
                    f'<td style="padding:1px 4px">{_hl.escape(str(v))}</td></tr>'
                )
            if not entries:
                return '<span style="color:#555">sem dados</span>'
            return f'<table style="font-size:9px;border-collapse:collapse">{"".join(entries)}</table>'
        except Exception:
            return '<span style="color:#555">erro</span>'

    def _render_pilar_dxf_context_b64(self, pilar_pts: list, width: int = 700, height: int = 500) -> str:
        """
        Renderiza o contexto DXF ao redor do pilar usando matplotlib (funciona headless).
        Mostra as linhas estruturais da area + pilar destacado em verde-agua.
        Retorna string base64 PNG.
        """
        if not pilar_pts or not self._dxf_data:
            return ''
        try:
            import io, base64
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from matplotlib.patches import Polygon as MplPolygon

            xs = [float(p[0]) for p in pilar_pts]
            ys = [float(p[1]) for p in pilar_pts]
            pw, ph = max(xs) - min(xs), max(ys) - min(ys)
            margin = max(pw, ph) * 3.0 + 60
            vx0, vx1 = min(xs) - margin, max(xs) + margin
            vy0, vy1 = min(ys) - margin, max(ys) + margin

            dpi = 150
            fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
            ax.set_facecolor('#111111')
            fig.patch.set_facecolor('#111111')
            ax.set_aspect('equal')
            ax.set_xlim(vx0, vx1)
            ax.set_ylim(vy0, vy1)
            ax.axis('off')

            # Linhas DXF na area de visualizacao
            for line in self._dxf_data.get('lines', []):
                s, e = line.get('start'), line.get('end')
                if not s or not e:
                    continue
                if (min(s[0], e[0]) <= vx1 and max(s[0], e[0]) >= vx0 and
                        min(s[1], e[1]) <= vy1 and max(s[1], e[1]) >= vy0):
                    ax.plot([s[0], e[0]], [s[1], e[1]], color='#3a5078', lw=0.6, solid_capstyle='round')

            # Polilinhas DXF na area
            for poly in self._dxf_data.get('polylines', []):
                pts = poly.get('points', [])
                if not pts:
                    continue
                pxs_p = [p[0] for p in pts]
                pys_p = [p[1] for p in pts]
                if (min(pxs_p) <= vx1 and max(pxs_p) >= vx0 and
                        min(pys_p) <= vy1 and max(pys_p) >= vy0):
                    ax.plot(pxs_p, pys_p, color='#3a5078', lw=0.6)

            # Todos os textos DXF na área de visualização
            import re as _re
            _pilar_pat = _re.compile(r'^P\d', re.IGNORECASE)
            _laje_pat  = _re.compile(r'^L\d', re.IGNORECASE)
            _viga_pat  = _re.compile(r'^V\d', re.IGNORECASE)
            for txt in self._dxf_data.get('texts', []):
                tx, ty = txt.get('pos', [0, 0])
                if vx0 <= float(tx) <= vx1 and vy0 <= float(ty) <= vy1:
                    t = str(txt.get('text', ''))
                    if not t.strip():
                        continue
                    if _pilar_pat.match(t):
                        col, fsz = '#ff9f43', 7      # pilar: laranja
                    elif _laje_pat.match(t):
                        col, fsz = '#4fc3a1', 6      # laje: verde-água
                    elif _viga_pat.match(t):
                        col, fsz = '#7eb8f7', 6      # viga: azul
                    else:
                        col, fsz = '#aaaaaa', 5      # demais: cinza
                    ax.text(float(tx), float(ty), t, color=col,
                            fontsize=fsz, ha='center', va='center', clip_on=True)

            # Pilar destacado
            poly_patch = MplPolygon(
                [(float(p[0]), float(p[1])) for p in pilar_pts],
                closed=True, fill=True,
                facecolor='#1e3a5f', edgecolor='#4fc3a1', lw=1.8, alpha=0.9, zorder=10
            )
            ax.add_patch(poly_patch)

            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.02,
                        facecolor='#111111', dpi=dpi)
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode('ascii')
        except Exception as exc:
            print(f'[HTML] _render_pilar_dxf_context_b64 falhou: {exc}', flush=True)
            return ''

    def _export_html_snapshot(self) -> str | None:
        """Gera uma ficha HTML independente para cada aba de dados.
        Retorna o output_dir gerado (ou None em caso de erro)."""
        import html
        self._save_analysis_state()   # snapshot JSON para modo headless
        # Pasta fixa por obra: scripts/arete/html_fichas/{obra}/{pavimento}_{ts}/
        # Acumula histórico de geração sem sobrescrever runs anteriores.
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        base = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', '..', 'scripts', 'arete', 'html_fichas',
            self._obra,
        ))
        output_dir = os.path.join(base, f'{self._pavimento}_{ts}')
        os.makedirs(output_dir, exist_ok=True)

        def _photo(points: list) -> str:
            pixmap = self._render_polygon_geometric(
                points, self._SEG_THUMB_W, self._SEG_THUMB_H,
                Colors.ACCENT_MINT, Surface.RAISED,
            )
            if pixmap is None:
                return ''
            label = QLabel()
            label.setPixmap(pixmap)
            label.setFixedSize(pixmap.size())
            return self._widget_to_b64_png(label)

        def _img_cell(b64: str, cls: str = 'img-n4') -> str:
            if b64:
                return f'<td><img class="{cls}" src="data:image/png;base64,{b64}" alt="render"></td>'
            return '<td><span class="muted">—</span></td>'

        def _html_cell(content: str) -> str:
            return f'<td style="max-width:340px;overflow:auto">{content}</td>'

        # ── Report: Pilares ──────────────────────────────────────────────────
        # Extra colunas por row: _n4_b64, _n2_html
        # tuple: (slug, title, data_headers, rows, extra_th_html, extra_td_fn)
        # ────────────────────────────────────────────────────────────────────
        reports: list[tuple] = []

        pillar_rows: list[dict] = []
        special_rows: list[dict] = []
        nr_pilares = (self._nivel_report or {}).get('pilares', {})
        for key, pillar in sorted(self._pillar_report.items(), key=lambda kv: self._natural_sort_key(kv[0])):
            combo = self._pillar_combos.get(key)
            classif = combo.currentText() if combo else pillar.get('classification', 'INDETERMINADO')
            nome = pillar.get('name') or key
            row = {
                'Nome': nome,
                'Classificação': classif,
                'Formato': _pilar_formato(pillar.get('points') or []),
                'Nível': (nr_pilares.get(key) or {}).get('level_str') or '—',
                'Lado A': self._get_side_cell(pillar, 'A'),
                'Lado B': self._get_side_cell(pillar, 'B'),
                'Lado C': self._get_side_cell(pillar, 'C'),
                'Lado D': self._get_side_cell(pillar, 'D'),
                'Atenção': self._atencao_notes.get(key, ''),
                '_points': pillar.get('points') or [],
                '_nome': nome,
            }
            (pillar_rows if row['Formato'] == 'Retangular' else special_rows).append(row)

        pillar_headers = ['Nome', 'Classificação', 'Formato', 'Nível', 'Lado A', 'Lado B', 'Lado C', 'Lado D', 'Atenção']
        _pil_extra_th = (
            '<th>Foto N1 (SA)</th>'
            '<th>N3 Cima</th><th>N3 ABCD</th><th>N3 Grades</th>'
            '<th>N4 Robot</th>'
            '<th>Foto N2</th>'
            '<th>Ficha N1 SA</th><th>Ficha N2</th><th>Ficha N3 (JSON)</th>'
        )

        def _pil_extra_td(row: dict) -> str:
            nome = row['_nome']
            pts  = row.get('_points') or []

            # ── Foto N1: contexto DXF estrutural + pilar destacado ────────────
            geo = self._render_pilar_dxf_context_b64(pts) if pts else ''
            if not geo:
                geo = _photo(pts)
            n1_cell = (f'<td><img class="img-geo" src="data:image/png;base64,{geo}" alt="N1"></td>'
                       if geo else '<td><span class="muted">sem N1</span></td>')

            # ── N3: 3 vistas DXF N3 (Fase-6 raiz = gerado via N1/Fase-4) ────
            def _n3_view_cell(view_type: str) -> str:
                p = self._find_pilar_dxf(view_type, nome, n4=False)
                b64 = self._render_ezdxf_b64(p, width=750, height=550) if p else ''
                return (_img_cell(b64, 'img-n3') if b64
                        else f'<td><span class="muted">sem N3 {view_type}</span></td>')

            n3_cima   = _n3_view_cell('CIMA')
            n3_abcd   = _n3_view_cell('ABCD')
            n3_grades = _n3_view_cell('GRADES')

            # ── N4: combined /n4/PL_preview_{nome}.dxf (CE via N2) ───────────
            n4_path = self._find_pilar_dxf('', nome, n4=True)
            n4_b64  = self._render_ezdxf_b64(n4_path, width=750, height=850) if n4_path else ''
            n4_cell = (_img_cell(n4_b64, 'img-n4') if n4_b64
                       else '<td><span class="muted">sem N4 (rode CE)</span></td>')

            # ── Foto N2: recorte DXF Fase-2 renderizado ───────────────────────
            n2b64 = self._render_n2_recorte_b64(nome)
            n2_foto_cell = (_img_cell(n2b64, 'img-n2') if n2b64
                            else '<td><span class="muted">sem recorte N2</span></td>')

            # ── Fichas informacionais ─────────────────────────────────────────
            n1_ficha = self._n1_ficha_html_pilar(nome)
            n2_ficha = self._n2_ficha_html('PIL', nome)
            n3_ficha = self._n3_ficha_html_pilar(nome)

            return (n1_cell
                    + n3_cima + n3_abcd + n3_grades
                    + n4_cell
                    + n2_foto_cell
                    + f'<td class="ficha-cell">{n1_ficha}</td>'
                    + f'<td class="ficha-cell">{n2_ficha}</td>'
                    + f'<td class="ficha-cell">{n3_ficha}</td>')

        reports.append(('pilares', 'Pré-ficha — Pilares', pillar_headers, pillar_rows, _pil_extra_th, _pil_extra_td))
        reports.append(('pilares_especiais', 'Pré-ficha — Pilares Especiais', pillar_headers, special_rows, _pil_extra_th, _pil_extra_td))

        # ── Report: Visão de Cortes ──────────────────────────────────────────
        cut_rows = []
        for cut in self._cut_view_data:
            combo = self._cut_combos.get(cut['uid'])
            status_combo = self._cut_status_combos.get(cut['uid'])
            cut_rows.append({
                'Viga': combo.currentText() if combo else cut.get('beam_name', ''),
                'Confiança': f"{cut.get('conf_pct', 0)}%",
                'Laje A': cut.get('own_laje', '—'),
                'Laje B': cut.get('neigh_laje', '—'),
                'Altura': cut.get('beam_h', '—'),
                'Status': status_combo.currentText() if status_combo else 'Válido',
                'Atenção': self._cut_attention.get(cut['uid'], ''),
                '_points': cut.get('pts') or [],
            })
        _cut_extra_th = '<th>Foto</th>'

        def _cut_extra_td(row: dict) -> str:
            geo = _photo(row.get('_points') or [])
            return (f'<td><img class="img-geo" src="data:image/png;base64,{geo}" alt="geo"></td>'
                    if geo else '<td><span class="muted">sem geo</span></td>')

        reports.append((
            'visao_cortes', 'Pré-ficha — Visão de Cortes',
            ['Viga', 'Confiança', 'Laje A', 'Laje B', 'Altura', 'Status', 'Atenção'],
            cut_rows, _cut_extra_th, _cut_extra_td,
        ))

        # ── Reports: Segmentos de Vigas ──────────────────────────────────────
        # fundo → FV, laterais → LV
        _seg_class = {
            'fundo': 'FV',
            'lateral_a_para': 'LV',
            'lateral_b_para': 'LV',
            'lateral_a_passa': 'LV',
            'lateral_b_passa': 'LV',
        }
        for kind, spec in SEGMENT_TAB_SPECS.items():
            seg_cls = _seg_class.get(kind, 'LV')
            segment_rows = []
            for raw in self._segment_data.get(kind, []):
                segment = serializable_segment(raw)
                combo = self._segment_status_combos.get(segment['uid'])
                seg_r: dict = {
                    'Viga': segment['beam_name'],
                    'Segmento': segment['segment_label'],
                    'Lado': segment['side'],
                    'Comportamento': segment['behavior'],
                    'Comprimento': f"{segment['length']:.1f}",
                    'Largura': segment.get('width') or '—',
                    'Status': combo.currentText() if combo else segment.get('status', 'valid'),
                    'Atenção': self._segment_attention.get(segment['uid'], segment.get('attention', '')),
                    '_points': segment.get('points') or [],
                    '_beam': segment['beam_name'],
                    '_cls': seg_cls,
                }
                segment_rows.append(seg_r)

            seg_headers = (
                ['Viga', 'Segmento', 'Comprimento', 'Largura', 'Status', 'Atenção']
                if kind == 'fundo' else
                ['Viga', 'Segmento', 'Lado', 'Comportamento', 'Comprimento', 'Status', 'Atenção']
            )
            _seg_extra_th = '<th>Foto N1</th><th>Foto N4</th><th>Foto N2</th>'

            def _make_seg_extra(cls: str):
                def _seg_extra_td(row: dict) -> str:
                    beam = row['_beam']
                    geo  = _photo(row.get('_points') or [])
                    n4   = self._find_n4_png(cls, beam)
                    n2   = self._find_n2_png(self._obra, f'comparacao_{cls.lower()}', beam)
                    if not n2:
                        n2 = self._find_n2_png(self._obra, 'comparacao_lv', beam)
                    geo_cell = (f'<td><img class="img-geo" src="data:image/png;base64,{geo}" alt="geo"></td>'
                                if geo else '<td><span class="muted">sem geo</span></td>')
                    return geo_cell + _img_cell(n4) + _img_cell(n2, 'img-n2')
                return _seg_extra_td

            reports.append((
                kind, f"Pré-ficha — {spec['title']}",
                seg_headers, segment_rows,
                _seg_extra_th, _make_seg_extra(seg_cls),
            ))

        # ── Render HTML ──────────────────────────────────────────────────────
        css = (
            'body{background:#1a1a1a;color:#c8c8c8;font:11px monospace;margin:16px}'
            'h1{color:#7eb8f7;font-size:16px} .meta,.muted{color:#777}'
            'table{border-collapse:collapse}'
            'th{position:sticky;top:0;background:#2a2a2a;color:#4fc3a1;padding:6px;white-space:nowrap}'
            'td{padding:5px 7px;border-bottom:1px solid #303030;vertical-align:top;white-space:pre-wrap}'
            '.img-geo{width:700px;height:500px;object-fit:contain;background:#111}'
            '.img-n3{width:900px;height:600px;object-fit:contain;background:#fff}'
            '.img-n4{width:900px;height:600px;object-fit:contain;background:#111}'
            '.img-n2{width:600px;height:400px;object-fit:contain;background:#111}'
            '.ficha-cell{max-width:380px;overflow:auto}'
            'tr:hover td{background:#222}'
        )

        generated: list[tuple[str, str, int]] = []
        try:
            for slug, title, headers, rows, extra_th, extra_td_fn in reports:
                body_parts = []
                for row in rows:
                    cells = ''.join(
                        f"<td>{html.escape(str(row.get(h, '')))}</td>"
                        for h in headers
                    )
                    extra = extra_td_fn(row) if extra_td_fn else ''
                    body_parts.append(f"<tr>{cells}{extra}</tr>")
                th_row = ''.join(f'<th>{html.escape(h)}</th>' for h in headers) + (extra_th or '')
                document = (
                    f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
                    f'<title>{html.escape(title)}</title><style>{css}</style></head>'
                    f'<body><h1>{html.escape(title)}</h1>'
                    f'<div class="meta">Obra: <b>{html.escape(self._obra)}</b> | '
                    f'Pavimento: <b>{html.escape(self._pavimento)}</b> | '
                    f'Gerado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | '
                    f'Registros: {len(rows)}</div>'
                    f'<table><thead><tr>{th_row}</tr></thead>'
                    f'<tbody>{"".join(body_parts)}</tbody></table></body></html>'
                )
                filename = f'preficha_{slug}.html'
                with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as file:
                    file.write(document)
                generated.append((filename, title, len(rows)))

            index_items = ''.join(
                f'<li><a href="{html.escape(f)}">{html.escape(t)}</a> — {c} registro(s)</li>'
                for f, t, c in generated
            )
            with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as file:
                file.write(
                    '<!DOCTYPE html><html lang="pt-BR"><meta charset="UTF-8">'
                    '<body style="background:#1a1a1a;color:#ccc;font:14px sans-serif">'
                    f'<h1>Pré-fichas — {html.escape(self._obra)} / {html.escape(self._pavimento)}</h1>'
                    f'<ul>{index_items}</ul></body></html>'
                )
            if self.isVisible():
                QMessageBox.information(
                    self, "HTMLs Gerados",
                    f"{len(generated)} fichas e índice salvos em:\n{output_dir}",
                )
            return output_dir
        except Exception as exc:
            if self.isVisible():
                QMessageBox.critical(self, "Erro ao Salvar", str(exc))
            else:
                import traceback
                print(f'[HTML] ERRO ao gerar HTMLs: {exc}', flush=True)
                traceback.print_exc()
        return None

    # ── Resultado ─────────────────────────────────────────────────────────────

    def get_result(self) -> dict:
        """
        Retorna as decisões do usuário:
          {
            'term_type_map':        {term: phys_type},
            'pillar_overrides':     {key: {classification, physical_type, ignore_in_beams}},
            'cut_view_assignments': {uid: {beam_name, confidence, status, is_invalid}},
            'segment_decisions':    {uid: {status, attention}},
            'invalid_pillar_keys':  set[str],   # pilares com classif "não é pilar"
            'invalid_cut_uids':     set[str],   # cortes marcados como "não é visão corte"
          }

        Quality gate: callers devem excluir invalid_pillar_keys e invalid_cut_uids
        ao propagar vínculos de volta às lajes.
        """
        # Termo → tipo físico: base = mapa inicializado (inclui defaults + arquivo salvo)
        # Se combos existem (aba Convenção visível), eles sobrescrevem.
        term_map: dict[str, str] = dict(self._term_type_map)
        for term, combo in self._term_combos.items():
            phys = PHYSICAL_TYPES[combo.currentIndex()][0]
            term_map[term] = phys

        # Pilares — cobre TODOS os pilares do report, mesmo os de abas não carregadas.
        # Combos registrados têm prioridade; pilares sem combo usam a classificação
        # original da análise (ou do histórico já restaurado em _populate_*).
        pillar_overrides: dict[str, dict] = {}
        invalid_pillar_keys: set[str] = set()
        all_keys = set(self._pillar_report.keys()) | set(self._pillar_combos.keys())
        for key in all_keys:
            combo = self._pillar_combos.get(key)
            if combo:
                classif = combo.currentText()
            else:
                # Aba não carregada — usa classificação do pillar_report (já com hist)
                pillar = self._pillar_report.get(key, {})
                classif = pillar.get('classification') or 'INDETERMINADO'
            if classif in (_SEPARADOR_ITEM, _SEPARADOR_GEOM):
                classif = 'INDETERMINADO'
            phys = self._physical_type_for(classif)
            is_invalid = classif.upper() in _NAO_SE_APLICA_CLASSIFS
            if is_invalid:
                invalid_pillar_keys.add(key)
            pillar_overrides[key] = {
                'classification':  classif,
                'physical_type':   phys,
                'ignore_in_beams': PHYS_IGNORE.get(phys, False),
                'is_invalid':      is_invalid,
            }

        # Cortes de viga
        cut_assignments: dict[str, dict] = {}
        invalid_cut_uids: set[str] = set()
        for cut in self._cut_view_data:
            uid      = cut['uid']
            beam_cb  = self._cut_combos.get(uid)
            status_cb = self._cut_status_combos.get(uid)
            if beam_cb is None:
                continue

            # Nome da viga: índice 0 = "nenhuma"
            idx = beam_cb.currentIndex()
            if idx > 0:
                beam_name = beam_cb.itemData(idx) or \
                            beam_cb.currentText().split('  ')[0].strip()
            else:
                # Pode ter sido digitado manualmente no campo editável
                typed = beam_cb.currentText().strip()
                beam_name = '' if (not typed or typed == self._CUT_NENHUMA) else typed

            status     = status_cb.itemData(status_cb.currentIndex()) \
                         if status_cb else 'ok'
            is_invalid = status != 'ok'
            if is_invalid:
                invalid_cut_uids.add(uid)

            conf = cut['conf_pct'] if beam_name else 0
            cut_assignments[uid] = {
                'beam_name':  beam_name,
                'confidence': conf / 100.0,
                'status':     status,
                'is_invalid': is_invalid,
                'attention':  self._cut_attention.get(uid, ''),
            }

        segment_decisions: dict[str, dict] = {}
        for entries in self._segment_data.values():
            for segment in entries:
                uid = segment['uid']
                combo = self._segment_status_combos.get(uid)
                status = combo.currentData() if combo else segment.get('status', 'valid')
                segment_decisions[uid] = {
                    'status': status or 'valid',
                    'attention': self._segment_attention.get(
                        uid, segment.get('attention', '')
                    ),
                    'source_key': segment.get('source_key', ''),
                }

        return {
            'term_type_map':        term_map,
            'pillar_overrides':     pillar_overrides,
            'cut_view_assignments': cut_assignments,
            'invalid_pillar_keys':  invalid_pillar_keys,
            'invalid_cut_uids':     invalid_cut_uids,
            'segment_decisions':    segment_decisions,
        }


# ── Diálogo standalone de Convenção de Pilares (exibido ANTES da análise) ─────

class ConvencaoPilaresDialog(PreValidationDialog):
    """
    Diálogo de Convenção de Pilares exibido ANTES da análise geral.
    Mostra o viewer de referência (recorte PIL do Motor Reverso) e o painel de
    mapeamento termo → tipo físico.  Não precisa de pillar_report nem slabs.
    """

    def __init__(
        self,
        obra: str,
        pavimento: str,
        convention: dict,
        convention_file: str | None = None,
        db_path: str | None = None,
        parent=None,
    ):
        super().__init__(
            pillar_report={},
            nivel_report={},
            slabs=[],
            convention=convention,
            obra=obra,
            pavimento=pavimento,
            beam_texts=[],
            canvas=None,
            convention_file=convention_file,
            db_path=db_path,
            parent=parent,
        )
        self.setWindowTitle(f"Convenção de Pilares — {obra} / {pavimento}")
        self.setMinimumSize(900, 600)
        self.showMaximized()

    # ── UI ──────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Mostra apenas o viewer de referência + painel de mapeamento de termos.
        Conteúdo pesado é diferido via QTimer para que a janela apareça instantaneamente."""
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Cabeçalho
        hdr = QFrame()
        hdr.setStyleSheet(
            f"QFrame {{ background:{Colors.BG_SECONDARY}; border-radius:4px; padding:4px; }}"
        )
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel(
            f"<b>Convenção de Pilares</b>  —  {self._obra} / {self._pavimento}"
            f"  <span style='color:{Text.SECONDARY}; font-size:9px;'>"
            f"Defina os tipos antes de iniciar a análise</span>"
        )
        lbl.setStyleSheet(f"color:{Colors.TEXT_PRIMARY}; font-size:11px;")
        hdr_lay.addWidget(lbl)
        root.addWidget(hdr)

        # Placeholder de carregamento
        self._conv_scroll = QScrollArea()
        self._conv_scroll.setWidgetResizable(True)
        self._conv_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._conv_scroll.setStyleSheet("QScrollArea { border: none; }")
        self._conv_scroll.setMinimumHeight(0)
        loading = QLabel("Carregando conteúdo...")
        loading.setAlignment(Qt.AlignCenter)
        loading.setStyleSheet(
            f"color:{Colors.TEXT_MUTED}; font-size:14px; font-weight:bold; padding:40px;"
        )
        self._conv_scroll.setWidget(loading)
        root.addWidget(self._conv_scroll, 1)

        root.addWidget(self._build_footer())

        # Defere construção pesada para o próximo ciclo de evento
        QTimer.singleShot(50, self._build_conv_content_deferred)

    def _build_conv_content_deferred(self) -> None:
        """Constrói o conteúdo pesado (gabarito + painel de termos) de forma diferida.

        Roda como slot de QTimer.singleShot: qualquer exceção que escapasse daqui
        poderia abortar/travar a app (dependendo da versão do PySide6), então todo
        o corpo é protegido por try/except.
        """
        try:
            inner = QWidget()
            lay = QVBoxLayout(inner)
            lay.setContentsMargins(6, 4, 6, 4)
            lay.setSpacing(6)

            gabarito = self._build_detail_reference_viewer()
            if gabarito:
                lay.addWidget(gabarito)
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet(f"color:{Colors.BORDER_DEFAULT};")
                lay.addWidget(sep)

            lay.addWidget(self._build_convention_panel())
            lay.addStretch()
            # takeWidget() remove o widget antigo SEM deletá-lo (devolve a posse);
            # setWidget() deletaria o antigo sozinho, então NÃO chamar deleteLater
            # sobre algo já destruído (causava RuntimeError dentro do slot).
            old = self._conv_scroll.takeWidget()
            self._conv_scroll.setWidget(inner)
            if old is not None:
                old.deleteLater()
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                err = QLabel(f"Falha ao montar a Convenção de Pilares:\n{e}")
                err.setAlignment(Qt.AlignCenter)
                err.setStyleSheet(f"color:{Colors.TEXT_MUTED}; padding:30px;")
                self._conv_scroll.setWidget(err)
            except Exception:
                pass


    # ── Overrides p/ modo pré-análise ───────────────────────────────────────────

    def _make_conv_viewer_for_term(self, term: str, w: int = 190, h: int = 85) -> QWidget:
        """Sem dados de pilar pré-análise: usa exemplos salvos ou placeholder."""
        saved_pts = self._saved_term_examples.get(term.upper())
        if saved_pts and len(saved_pts) >= 2:
            try:
                xs = [float(p[0]) for p in saved_pts]
                ys = [float(p[1]) for p in saved_pts]
                bx0, bx1 = min(xs), max(xs)
                by0, by1 = min(ys), max(ys)
                margin = max(80.0, max(bx1 - bx0, by1 - by0) * 2.0)
                vx0, vx1 = bx0 - margin, bx1 + margin
                vy0, vy1 = by0 - margin, by1 + margin
                scene = QGraphicsScene()
                scene.setSceneRect(vx0, vy0, vx1 - vx0, vy1 - vy0)
                scene.setBackgroundBrush(QColor(Colors.BG_PANEL))
                viewer = _MiniDXFView(scene, vx0, vy0, vx1, vy1, w, h,
                                      highlight_pts=saved_pts)
                viewer.setToolTip("Referência salva de outro pavimento")
                return viewer
            except Exception:
                pass
        return self._make_conv_placeholder(w, h, "Disponível\napós análise")

    def _refresh_pillar_table_row_for_term(self, term: str) -> None:
        """No-op: tabela de pilares não existe no modo pré-análise."""
