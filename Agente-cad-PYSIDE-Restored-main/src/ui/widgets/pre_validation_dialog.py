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
    QMessageBox,
)
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer, QSize, QThread, Signal
from PySide6.QtGui import (QColor, QFont, QBrush, QPixmap, QPainter,
                            QPen, QPolygonF, QPainterPath)

try:
    from src.ui.theme import Colors, Semantic, Accent, Text, Surface, Border, Contextual
except ImportError:
    class Surface:
        BASE = "#1a1a2e"; RAISED = "#16213e"; DEEP = "#121212"; CARD = "#252525"; ELEVATED = "#2a2a3e"
    class Border:
        DEFAULT = "#333333"; STRONG = "#444444"; SUBTLE = "#2a2a2a"
    class Contextual:
        DANGER_DARK = "#332222"; FOREST = "rgba(26, 74, 26, 1)"; PURPLE = "#a070ff"; GOLD = "#e6b400"
    class Colors:
        BG_PRIMARY        = Surface.BASE
        BG_SECONDARY      = Surface.RAISED
        BG_PANEL          = Surface.BASE
        ACCENT_MINT       = "#4caf50"   # = Semantic.SUCCESS
        ACCENT_WARNING_ALT = "#ff9800"  # = Semantic.WARNING
        BORDER_DEFAULT    = Border.DEFAULT
        BORDER_INPUT      = Border.STRONG
        TEXT_PRIMARY      = "#e0e0e0"
        TEXT_MUTED        = "#666666"
    class Semantic:
        SUCCESS = "#4caf50"; WARNING = "#ff9800"; DANGER = "#f44336"
        SUCCESS_BG_DARK = "#1a3320"; WARNING_BG_DARK = "#332900"; DANGER_BG_DARK = "#330d00"
    class Accent:
        PRIMARY = "#00d4ff"; BRAND = "#00E5FF"; INTERACTIVE = "#0078d4"
    class Text:
        PRIMARY = "#e0e0e0"; SECONDARY = "#9a9aa6"; MUTED = "#666666"; BRIGHT = "#ffffff"

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
        """Extrai nivel (level_str) de cada laje via nivel_report."""
        lajes_nr = (self._nivel_report or {}).get('lajes', {})
        return {name: (entry.get('level_str') or '') for name, entry in lajes_nr.items()}

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
        lines.append(f'Nivel: {nivel}' if nivel else 'Nivel:')
        return '\n'.join(lines)

    _VIGA_CELL_TEXT = 'Viga:\nLargura:\nAltura:\nNivel:'

    def _get_side_cell(self, pillar: dict, side: str) -> str:
        """
        Retorna o texto para a célula do lado (A/B/C/D) de um pilar.

        Estratégias em ordem de prioridade:
        1. Lajes entries vindas do analisador → bloco multi-linha "Laje:/Altura:/Nivel:"
        2. Amostragem múltipla ao longo da aresta (25 / 50 / 75 %) dentro de
           qualquer polígono de laje → bloco VIGA
        3. Aresta colínear com borda do polígono de laje (overlap ≥ 5 u) → bloco VIGA
           (cobre aresta coincidente com fronteira, onde ray-casting é não-det.)
        4. Projeção perpendicular para FORA da aresta → bloco VIGA
           (detecta lajes adjacentes nos lados C/D cujo limite coincide com a borda)
        5. Nada encontrado → "nulo"
        """
        lajes_entries = [e for e in (pillar.get('lajes') or []) if e.get('side') == side]
        if lajes_entries:
            parts: list[str] = []
            for e in lajes_entries:
                ln = e.get('laje') or '?'
                h     = self._slab_height_map.get(ln) or ''
                nivel = self._slab_nivel_map.get(ln) or ''
                parts.append(self._side_cell_laje_block(ln, h, nivel))
            return '\n\n'.join(parts)

        bbox = pillar.get('bbox')
        orientation = pillar.get('orientation') or 'horizontal'
        edge = self._side_edge(bbox, orientation, side)
        if not edge:
            return 'nulo'

        (ex0, ey0), (ex1, ey1) = edge

        # ── Estratégia 2: amostragem múltipla (3 pontos) ──────────────────────
        samples = [
            (ex0 * 0.75 + ex1 * 0.25,  ey0 * 0.75 + ey1 * 0.25),
            ((ex0 + ex1) / 2.0,         (ey0 + ey1) / 2.0),
            (ex0 * 0.25 + ex1 * 0.75,  ey0 * 0.25 + ey1 * 0.75),
        ]
        for slab_name, poly_pts in self._slab_poly_map.items():
            for px, py in samples:
                if self._point_in_polygon(px, py, poly_pts):
                    return self._VIGA_CELL_TEXT

        # ── Estratégia 3: sobreposição colínear com borda do polígono ─────────
        for slab_name, poly_pts in self._slab_poly_map.items():
            if self._edge_overlaps_poly_boundary((ex0, ey0), (ex1, ey1), poly_pts):
                return self._VIGA_CELL_TEXT

        # ── Estratégia 4: projeção perpendicular para fora da aresta ──────────
        # Para lados C/D onde a borda do pilar coincide com a borda do polígono
        # de laje adjacente — ray-casting on-boundary é não-determinístico.
        horiz = (orientation or '').lower() != 'vertical'
        outward_dirs = {
            True:  {'A': (0.0, -1.0), 'B': (0.0, 1.0), 'C': (-1.0, 0.0), 'D': (1.0, 0.0)},
            False: {'A': (-1.0, 0.0), 'B': (1.0, 0.0), 'C': (0.0, 1.0), 'D': (0.0, -1.0)},
        }
        dx, dy = outward_dirs[horiz].get(side, (0.0, 0.0))
        for delta in (4.0, 12.0, 25.0):
            for px, py in samples:
                for poly_pts in self._slab_poly_map.values():
                    if self._point_in_polygon(px + dx * delta, py + dy * delta, poly_pts):
                        return self._VIGA_CELL_TEXT

        return 'nulo'

    def _make_mini_viewer(
        self, pts: list,
        thumb_w: int, thumb_h: int,
        margin_factor: float = 3.0,
        min_margin_dxf: float = 120.0,
        fallback_line: str = Colors.ACCENT_MINT,
        fallback_fill: str = Surface.RAISED,
    ) -> QWidget | None:
        """
        Cria um _MiniDXFView que compartilha a cena DXF do canvas principal,
        centralizado na bbox dos pontos + margem de contexto.

        Renderização vetorial: nenhum grab, nenhuma pixelação — Qt desenha
        diretamente na geometria DXF em qualquer zoom.

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

            # 0ª — Tenta pegar o recorte da convencao de pilares
            try:
                cur.execute(
                    "SELECT output_path FROM obra_recortes "
                    "WHERE obra_name=? AND pavimento_name=? AND recorte_type='convencao_pilares' AND status IN ('approved', 'manual') "
                    "ORDER BY recorte_index DESC LIMIT 1",
                    (self._obra, self._pavimento)
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

        def _on_doc_loaded(doc):
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
                
                viewer = _MiniDXFView(scene, x0, y0, x1, y1,
                                      thumb_w=800, thumb_h=250,
                                      highlight_pts=[])
                viewer.setMaximumWidth(16777215)
                viewer.setMinimumWidth(300)
                viewer.setMinimumHeight(200)
                viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                vbox.addWidget(viewer)
            except Exception as e:
                err_lbl = QLabel(f"Falha ao renderizar gabarito: {e}")
                err_lbl.setAlignment(Qt.AlignCenter)
                vbox.addWidget(err_lbl)
            finally:
                # Mantém uma referência para a thread não morrer prematuramente
                self._dxf_thread = None

        # Carrega o DXF em thread separada para não travar a GUI
        self._dxf_thread = _DXFReaderThread(dxf_path)
        self._dxf_thread.finished.connect(_on_doc_loaded)
        self._dxf_thread.start()

        return grp

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
            return {'pilares': {}, 'cut_views': {}}
        try:
            with open(self._history_path, encoding='utf-8') as f:
                data = json.load(f)
            return {
                'pilares':   data.get('pilares', {}),
                'cut_views': data.get('cut_views', {}),
            }
        except Exception:
            return {'pilares': {}, 'cut_views': {}}

    def _save_pf_history(self) -> None:
        """Persiste estado atual dos combos de pilar e corte, keyed por geometria."""
        if not self._history_path:
            return
        pilares: dict = dict(self._pf_history.get('pilares', {}))
        cut_views: dict = dict(self._pf_history.get('cut_views', {}))
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

        data = {
            'version':   2,
            'obra':      self._obra,
            'pavimento': self._pavimento,
            'saved_at':  now,
            'pilares':   pilares,
            'cut_views': cut_views,
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
        """
        best: float | None = None
        for laje_name, dist_top_str in (
            (cut.get('own_laje', ''), cut.get('own_dist_top', '—')),
            (cut.get('neigh_laje', ''), cut.get('neigh_dist_top', '—')),
        ):
            if not laje_name or laje_name in ('—', 'nulo', 'NULO', ''):
                continue
            nivel_str = self._slab_nivel_map.get(laje_name, '')
            if not nivel_str:
                continue
            try:
                nivel = float(nivel_str)
                dt = float(dist_top_str) if dist_top_str not in ('—', None, '') else 0.0
                val = nivel + dt
                if best is None or val > best:
                    best = val
            except (ValueError, TypeError):
                pass
        return f"{best:.2f}" if best is not None else '—'

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

        sep = f"<hr style='border:none; border-top:1px solid {Border.DEFAULT}; margin:2px 0;'>"
        html = (
            "<div style='font-size:9px; line-height:1.45; padding:3px;'>"
            f"{_kv('Nome:', beam_name_f, CG, bold=True)}<br>"
            f"{_kv('Segmento:', '—', CL)}<br>"
            f"{_kv('Largura:', str(bw))} cm"
            f"&nbsp;&nbsp;<span style='color:{CL}'>{tipo}</span><br>"
            f"{_kv('Altura:', str(bh))} cm<br>"
            f"{_kv('Nível viga:', nivel_viga, CM)}"
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
        self._tab_loaded: dict[int, bool] = {0: False, 1: False, 2: False}

        # Placeholders leves (QWidget vazio com loading label)
        for idx, title in enumerate([
            "  Convenção de Pilares  ",
            "  Pilares  ",
            "  Visão de Cortes  ",
        ]):
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

        # Carrega tab 0 (Convenção) via QTimer para que o dialog apareça instantaneamente
        QTimer.singleShot(50, lambda: self._on_tab_changed(0))

    def _on_tab_changed(self, index: int) -> None:
        """Lazy-load: constrói o conteúdo da aba apenas na primeira vez que é selecionada."""
        if self._tab_loaded.get(index, True):
            return  # já carregada
        self._tab_loaded[index] = True

        builders = {
            0: self._build_convention_tab,
            1: self._build_pillars_tab,
            2: self._build_cut_views_tab,
        }
        builder = builders.get(index)
        if not builder:
            return

        old_widget = self._tabs.widget(index)
        tab_text = self._tabs.tabText(index)
        
        # Show a loading placeholder instantly
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import QTimer, Qt
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
                new_widget = builder()
                self._tabs.blockSignals(True)
                self._tabs.removeTab(index)
                self._tabs.insertTab(index, new_widget, tab_text)
                self._tabs.setCurrentIndex(index)
                
                # Trigger lazy loader after a short delay so layout is done
                QTimer.singleShot(100, self._trigger_dynamic_viewers_for_visible_tab)
            except Exception as e:
                import traceback
                traceback.print_exc()
                from PySide6.QtWidgets import QLabel
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
        # Dispara o recarregamento dos miniviewers (5 por vez baseados no scroll)
        # Pilares
        if getattr(self, '_pillar_table', None) and self._pillar_table.isVisible():
            self._update_dynamic_viewers(self._pillar_table, getattr(self, '_pillar_viewer_data', {}), self._PIL_COL_FOTO, False)
        # Visão de Corte
        if getattr(self, '_cut_table', None) and self._cut_table.isVisible():
            self._update_dynamic_viewers(self._cut_table, getattr(self, '_cut_viewer_data', {}), self._CUT_COL_FOTO, True)


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
        n_hall = nr_sum.get('hallucination_suspects', 0)

        def _chip(text: str, color: str) -> QLabel:
            lb = QLabel(text)
            lb.setStyleSheet(f"color:{color}; font-size:10px; font-weight:bold; padding:2px 8px;")
            return lb

        lay.addWidget(_chip(f"{n_lajes} lajes", Semantic.SUCCESS))
        lay.addWidget(_chip(f"{n_conf} níveis confirmados / {n_inf} inferidos", Semantic.SUCCESS))
        if n_hall:
            lay.addWidget(_chip(f"{n_hall} suspeitos de alucinação", Semantic.DANGER))
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

        btn_confirm = QPushButton("  Confirmar e Prosseguir  ▶")
        btn_confirm.setStyleSheet(
            f"QPushButton {{ background:{Accent.PRIMARY}; color:{Surface.DEEP}; font-weight:bold; "
            f"  border:none; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:{Accent.BRAND}; }}"
        )
        btn_confirm.clicked.connect(self._confirm_and_save)

        lay.addWidget(btn_cancel)
        lay.addWidget(btn_save)
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
        gabarito = self._build_detail_reference_viewer()
        if gabarito:
            lay.addWidget(gabarito)
            sep = QFrame(); sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet(f"color:{Colors.BORDER_DEFAULT};")
            lay.addWidget(sep)

        # Lista de termos + mini viewers por classe
        lay.addWidget(self._build_convention_panel())
        lay.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_pillars_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)
        lay.addWidget(self._build_pillar_table(), 1)
        return w

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

            ref_viewer = self._make_conv_viewer_for_term(term, w=190, h=85)

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

    # Índice das colunas da tabela de pilares
    # Classif.SA e Classif.Override ficam lado a lado (cols 1 e 2)
    _PIL_COL_NOME      = 0
    _PIL_COL_CLASSIF   = 1
    _PIL_COL_OVERRIDE  = 2   # ao lado da classificação SA
    _PIL_COL_PHYS      = 3
    _PIL_COL_CONF      = 4
    _PIL_COL_NIVEL     = 5
    _PIL_COL_LADO_A    = 6
    _PIL_COL_LADO_B    = 7
    _PIL_COL_LADO_C    = 8
    _PIL_COL_LADO_D    = 9
    _PIL_COL_FOTO      = 10

    # Dimensões do mini viewer de pilar
    _PIL_THUMB_W  = 440
    _PIL_THUMB_H  = 210
    _PIL_COL_FOTO_W = 450
    _PIL_ROW_H    = 220

    # Largura das colunas Lado-A/B/C/D (−20% de 130)
    _PIL_LADO_COL_W = 104

    def _build_pillar_table(self) -> QTableWidget:
        cols = [
            "Nome", "Classif. SA", "Classif. Override",
            "Tipo Físico", "Conf %", "Nível",
            "Lado-A", "Lado-B", "Lado-C", "Lado-D", "Foto",
        ]
        tbl = QTableWidget(0, len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        # Nome: metade do tamanho — o espaço economizado sai do total (não vai p/ outras colunas)
        hdr.setSectionResizeMode(self._PIL_COL_NOME, QHeaderView.Fixed)
        tbl.setColumnWidth(self._PIL_COL_NOME, 75)
        for col in (self._PIL_COL_LADO_A, self._PIL_COL_LADO_B,
                    self._PIL_COL_LADO_C, self._PIL_COL_LADO_D):
            hdr.setSectionResizeMode(col, QHeaderView.Interactive)
            tbl.setColumnWidth(col, self._PIL_LADO_COL_W)
        hdr.setSectionResizeMode(self._PIL_COL_OVERRIDE, QHeaderView.Interactive)
        tbl.setColumnWidth(self._PIL_COL_OVERRIDE, 180)
        hdr.setSectionResizeMode(self._PIL_COL_FOTO, QHeaderView.Fixed)
        tbl.setColumnWidth(self._PIL_COL_FOTO, self._PIL_COL_FOTO_W)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setStyleSheet("QTableWidget { font-size:9px; }")
        tbl.setMinimumHeight(0)  # não trava o layout; footer permanece visível
        self._pillar_table = tbl
        self._pillar_viewer_data = {}
        tbl.verticalScrollBar().valueChanged.connect(
            lambda _: self._update_dynamic_viewers(self._pillar_table, self._pillar_viewer_data, self._PIL_COL_FOTO, False)
        )
        self._populate_pillar_table()
        return tbl

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
        skip = {self._PIL_COL_OVERRIDE, self._PIL_COL_FOTO}
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
            phys = self._physical_type_for(classif)
            ignore = PHYS_IGNORE.get(phys, False)
            txt = Text.SECONDARY if ignore else Semantic.DANGER
            bg_css = bg.name() if bg else 'transparent'
            lbl.setStyleSheet(
                f"color:{txt}; font-size:9px; padding:3px; background:{bg_css};"
            )

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

            phys = self._physical_type_for(classif)
            ignore = PHYS_IGNORE.get(phys, False)

            conf_pct = 0 if classif == 'INDETERMINADO' else 95
            if classif in (_NAO_PILAR_SOLIDO, _NAO_PILAR_VISUAL):
                conf_pct = 100

            p_nr = nr_pilares.get(key, {})
            nivel_str = p_nr.get('level_str') or '—'
            phys_label_text = PHYS_LABEL.get(phys, phys)
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

            tbl.setItem(row, self._PIL_COL_CLASSIF, _make_item(classif))
            tbl.setItem(row, self._PIL_COL_CONF,
                        _make_item(f"{conf_pct}%", Qt.AlignCenter, color=conf_color))
            tbl.setItem(row, self._PIL_COL_NIVEL,
                        _make_item(nivel_str, Qt.AlignCenter))

            # ── Tipo Físico: QLabel com word wrap ────────────────────────────
            txt_color = Text.SECONDARY if ignore else Semantic.DANGER
            phys_lbl = QLabel(phys_label_text)
            phys_lbl.setWordWrap(True)
            phys_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            phys_lbl.setStyleSheet(
                f"color:{txt_color}; font-size:9px; padding:3px; background:transparent;"
            )
            self._phys_labels[key] = phys_lbl
            tbl.setCellWidget(row, self._PIL_COL_PHYS, phys_lbl)

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
                    if cell_text.startswith('Viga:'):
                        item.setForeground(QBrush(QColor(Colors.ACCENT_WARNING_ALT)))
                    elif cell_text == 'nulo':
                        item.setForeground(QBrush(QColor(Colors.TEXT_MUTED)))
                tbl.setItem(row, col, item)

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
        bottom_row = tbl.rowAt(vp_height)
        
        if top_row == -1:
            top_row = 0
        if bottom_row == -1:
            bottom_row = tbl.rowCount() - 1
            
        start_row = max(0, top_row - 1)
        end_row = min(tbl.rowCount() - 1, bottom_row + 1)
        
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
            if row < start_row - 2 or row > end_row + 2:
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
        """Atualiza coluna Tipo Físico (QLabel) para todos os pilares com esse termo."""
        tbl = self._pillar_table
        for row in range(tbl.rowCount()):
            classif_item = tbl.item(row, self._PIL_COL_CLASSIF)
            if not classif_item or classif_item.text().upper() != term.upper():
                continue
            phys = self._term_type_map.get(term, 'unknown')
            ignore = PHYS_IGNORE.get(phys, False)
            phys_label_text = PHYS_LABEL.get(phys, phys)
            # Obtém key pelo UserRole do item Nome
            nome_item = tbl.item(row, self._PIL_COL_NOME)
            key = nome_item.data(Qt.UserRole) if nome_item else None
            if key and key in self._phys_labels:
                lbl = self._phys_labels[key]
                lbl.setText(phys_label_text)
                bg = self._row_bg_for_classif(classif_item.text())
                bg_css = bg.name() if bg else 'transparent'
                txt = Text.SECONDARY if ignore else Semantic.DANGER
                lbl.setStyleSheet(
                    f"color:{txt}; font-size:9px; padding:3px; background:{bg_css};"
                )

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
    _CUT_COL_FOTO   = 6   # Mini viewer

    # Opções de status do corte
    _CUT_ST_OK     = '— Válido (é visão de corte) —'
    _CUT_ST_VISUAL = 'NÃO É VISÃO CORTE — Errada Apenas Visual'
    _CUT_ST_SOLIDA = 'NÃO É VISÃO CORTE — Errada Sólida'
    _CUT_ST_PILAR  = 'NÃO É VISÃO CORTE — É Pilar'

    # Opção "nenhuma viga identificada"
    _CUT_NENHUMA   = '— Nenhuma (não identificada) —'

    _CUT_THUMB_W  = 440
    _CUT_THUMB_H  = 210
    _CUT_COL_FOTO_W = 450
    _CUT_ROW_H    = 310
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

    def _build_cut_view_table(self) -> QTableWidget:
        cols = ["Viga Assoc.", "Conf %",
                "Detalhes sobre o Segmento de Viga",
                "Lajes LADO A", "Lajes LADO B", "Status", "Foto"]
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
        hdr.setSectionResizeMode(self._CUT_COL_FOTO, QHeaderView.Fixed)
        tbl.setColumnWidth(self._CUT_COL_FOTO, self._CUT_COL_FOTO_W)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.setStyleSheet("QTableWidget { font-size:9px; }")
        tbl.setMinimumHeight(0)  # não trava o layout; footer permanece visível
        self._cut_table = tbl
        self._cut_viewer_data = {}
        tbl.verticalScrollBar().valueChanged.connect(
            lambda _: self._update_dynamic_viewers(self._cut_table, self._cut_viewer_data, self._CUT_COL_FOTO, True)
        )
        self._populate_cut_view_table()
        return tbl

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

            own_text = self._laje_info_text(
                cut['own_laje'], laje1_dir,
                cut['own_pos'], cut['own_dist_top'], cut['own_dist_bot'],
                own_lado, slab_h_cut=cut.get('own_slab_h', ''),
            )
            neigh_text = self._laje_info_text(
                cut['neigh_laje'], laje2_dir,
                cut['neigh_pos'], cut['neigh_dist_top'], cut['neigh_dist_bot'],
                neigh_lado, slab_h_cut=cut.get('neigh_slab_h', ''),
            )

            def _make_laje_lbl(text, is_wall, is_own):
                lbl = QLabel(text)
                lbl.setWordWrap(True)
                lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                if is_own:
                    color = Colors.ACCENT_MINT
                elif is_wall:
                    color = Colors.TEXT_MUTED
                else:
                    color = Accent.INTERACTIVE
                lbl.setStyleSheet(
                    f"color:{color}; font-size:9px; padding:4px; background:transparent;"
                )
                return lbl

            # own_lado == 'A' → own vai para col A, neigh para col B; caso contrário, inverte
            if own_lado != 'B':
                tbl.setCellWidget(row, self._CUT_COL_LAJE1, _make_laje_lbl(own_text,  False, True))
                tbl.setCellWidget(row, self._CUT_COL_LAJE2, _make_laje_lbl(neigh_text, wall, False))
            else:
                tbl.setCellWidget(row, self._CUT_COL_LAJE1, _make_laje_lbl(neigh_text, wall, False))
                tbl.setCellWidget(row, self._CUT_COL_LAJE2, _make_laje_lbl(own_text,  False, True))

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

    def _confirm_and_save(self) -> None:
        """Salva histórico de pré-ficha (geometria → override) e aceita o diálogo."""
        self._save_pf_history()
        self.accept()

    # ── Resultado ─────────────────────────────────────────────────────────────

    def get_result(self) -> dict:
        """
        Retorna as decisões do usuário:
          {
            'term_type_map':        {term: phys_type},
            'pillar_overrides':     {key: {classification, physical_type, ignore_in_beams}},
            'cut_view_assignments': {uid: {beam_name, confidence, status, is_invalid}},
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

        # Pilares
        pillar_overrides: dict[str, dict] = {}
        invalid_pillar_keys: set[str] = set()
        for key, combo in self._pillar_combos.items():
            classif = combo.currentText()
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
            }

        return {
            'term_type_map':        term_map,
            'pillar_overrides':     pillar_overrides,
            'cut_view_assignments': cut_assignments,
            'invalid_pillar_keys':  invalid_pillar_keys,
            'invalid_cut_uids':     invalid_cut_uids,
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
        """Constrói o conteúdo pesado (gabarito + painel de termos) de forma diferida."""
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
        old = self._conv_scroll.widget()
        self._conv_scroll.setWidget(inner)
        if old:
            old.deleteLater()


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
