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
from src.ui.widgets.svg_embed_utils import (
    strip_fixed_size as _svg_strip_fixed_size,
    embed_visual as _embed_visual,
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


_SEGMENT_DETAIL_SEPARATOR = "────────────────────────"


def _pillar_sides_text(side_values: dict[str, str], sides: str) -> str:
    """Agrupa lados do pilar em blocos ordenados na mesma célula."""
    sections = []
    for side in sides:
        value = str(side_values.get(side) or "nulo")
        sections.append(f"LADO {side}\n{value}")
    return f"\n{_SEGMENT_DETAIL_SEPARATOR}\n".join(sections)


def _pillar_abcd_text(side_values: dict[str, str]) -> str:
    return _pillar_sides_text(side_values, "ABCD")


def _pillar_abcdefgh_text(side_values: dict[str, str]) -> str:
    return _pillar_sides_text(side_values, "ABCDEFGH")


def _pillar_identity_text(
    name: str,
    classification: str,
    shape: str,
    confidence: int | float,
) -> str:
    """Organiza a identificação completa do pilar na primeira célula."""
    sections = [
        f"NOME\n{name or '—'}",
        f"CLASSIFICAÇÃO SA\n{classification or '—'}",
        f"FORMATO\n{shape or '—'}",
        f"CONFIANÇA\n{confidence:g}%",
    ]
    return f"\n{_SEGMENT_DETAIL_SEPARATOR}\n".join(sections)


def _cut_compact_width(original_width: int) -> int:
    """Reduz em 40% uma coluna informacional da Visão de Cortes."""
    return round(original_width * 0.60)


def _slab_details_text(
    slab: dict,
    *,
    height: str = "",
    level: str = "",
) -> str:
    """Resume dados técnicos existentes da laje sem criar novas inferências."""
    fields = slab.get("fields") or {}
    links = slab.get("links") or {}
    raw_height = height or fields.get("laje_dim") or slab.get("laje_dim") or "—"
    raw_level = level or fields.get("laje_nivel") or slab.get("laje_nivel") or "—"
    points = _slab_outline_points(slab)
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]

    area = slab.get("area")
    try:
        area_text = f"{float(area):.1f} u²"
    except (TypeError, ValueError):
        area_text = "—"

    supports: list[str] = []
    support_links = (links.get("laje_pilares_apoio") or {}).get("pillar_geom") or []
    for support in support_links:
        name = (
            (support.get("ficha") or {}).get("pillar_name")
            if isinstance(support, dict)
            else ""
        )
        if name and name not in supports:
            supports.append(str(name))

    neighbor_lines = []
    direction_names = {
        "neighbor_north": "Norte",
        "neighbor_east": "Leste",
        "neighbor_south": "Sul",
        "neighbor_west": "Oeste",
    }
    neighbors = links.get("laje_vizinhas_niveis") or {}
    for key, label in direction_names.items():
        names: list[str] = []
        for record in neighbors.get(key) or []:
            if not isinstance(record, dict):
                continue
            candidate = record.get("source_slab")
            if not candidate:
                text = str(record.get("text") or "")
                candidate = (
                    text
                    if re.fullmatch(r"L\d+[A-Z]?", text, re.IGNORECASE)
                    else ""
                )
            if candidate and candidate not in names:
                names.append(str(candidate))
        neighbor_lines.append(f"{label}: {', '.join(names) or '—'}")

    cuts = (links.get("laje_visao_corte") or {}).get("cut_view_geom") or []
    confidence = slab.get("confidence_score")
    if confidence is None:
        confidence = (slab.get("trace_diagnostics") or {}).get("confidence_score")
    try:
        confidence_value = float(confidence)
        if confidence_value <= 1:
            confidence_value *= 100
        confidence_text = f"{confidence_value:.0f}%"
    except (TypeError, ValueError):
        confidence_text = "—"

    sections = [
        [
            "DIMENSÕES E NÍVEL",
            f"Altura: {raw_height}",
            f"Nível: {raw_level}",
            f"Área geométrica: {area_text}",
            f"Vértices do contorno: {len(points) or '—'}",
        ],
        ["APOIOS", f"Pilares: {', '.join(supports) or '—'}"],
        ["VIZINHANÇA", *neighbor_lines],
        [
            "ANÁLISE",
            f"Origem: {slab.get('origin') or '—'}",
            f"Método: {slab.get('method') or '—'}",
            f"Confiança: {confidence_text}",
            f"Cortes vinculados: {len(cuts)}",
            f"Validada: {'Sim' if slab.get('is_validated') else 'Não'}",
        ],
    ]
    return f"\n{_SEGMENT_DETAIL_SEPARATOR}\n".join(
        "\n".join(section) for section in sections
    )


def _slab_outline_points(slab: dict) -> list:
    """Obtém o contorno autoritativo da laje, com fallback para o vínculo SA."""
    points = slab.get("points") or []
    if points:
        return list(points)
    contours = (
        ((slab.get("links") or {}).get("laje_outline_segs") or {}).get("contour")
        or []
    )
    for contour in contours:
        if isinstance(contour, dict) and contour.get("points"):
            return list(contour["points"])
    return []


def _segment_identity_text(segment: dict, is_fundo: bool = False) -> str:
    """Compacta a identificação segmentar em uma única célula ordenada."""
    lines = [
        f"Nome: {segment.get('beam_name') or '—'}",
        f"Segmento: {segment.get('segment_label') or '—'}",
    ]
    if not is_fundo:
        lines.extend([
            f"Lado: {segment.get('side') or '—'}",
            f"Comportamento: {segment.get('behavior') or '—'}",
        ])
    return "\n".join(lines)


def _segment_details_text(segment: dict, is_fundo: bool = False) -> str:
    """Organiza dimensões e classes técnicas com separadores visuais."""
    dimension_lines = [
        "DIMENSÕES",
        f"Comprimento: {float(segment.get('length') or 0.0):.1f}",
    ]
    if is_fundo:
        dimension_lines.append(f"Largura: {segment.get('width') or '—'}")
        return "\n".join(dimension_lines)

    dimension_lines.append(f"Altura: {segment.get('height') or '—'}")
    details = segment.get('details') or {}

    def support_line(label: str, support: dict | None) -> str:
        support = support or {}
        return (
            f"{label}: {support.get('name') or '—'} | "
            f"Dim.: {support.get('dimension') or '—'} | "
            f"Nível: {support.get('level') or '—'}"
        )

    sections = [
        dimension_lines,
        [
            "APOIOS",
            f"Vínculo: {segment.get('tag') or '—'}",
            support_line("Inicial", details.get('support_start')),
            support_line("Final", details.get('support_end')),
            f"Nível da viga: {details.get('beam_level') or '—'}",
        ],
    ]

    slabs = list(details.get('slabs') or [])[:3]
    slab_lines = ["LAJES"]
    for slab_index in range(3):
        slab = slabs[slab_index] if slab_index < len(slabs) else {}
        slab_lines.append(
            f"Laje {slab_index + 1}: {slab.get('name') or '—'} | "
            f"Nível: {slab.get('level') or '—'} | "
            f"Altura: {slab.get('height') or '—'}"
        )
    sections.append(slab_lines)

    adjustment = details.get('adjustment') or {}
    sections.extend([
        [
            "CONTINUIDADE E AJUSTE",
            f"Continuidade: {details.get('continuity') or 'A preencher'}",
            "Ajuste comprimento: "
            f"{adjustment.get('initial') or 'A preencher'} + "
            f"{adjustment.get('final') or 'A preencher'} = "
            f"{adjustment.get('total') or 'A preencher'}",
        ],
        [
            "INTERFERÊNCIAS",
            "Pilares que passam: "
            f"{', '.join(details.get('passing_pillars') or []) or '—'}",
            "Aberturas de viga: "
            f"{', '.join(details.get('beam_openings') or []) or '—'}",
        ],
    ])
    return f"\n{_SEGMENT_DETAIL_SEPARATOR}\n".join(
        "\n".join(section) for section in sections
    )


# ── Mini viewer vetorial ───────────────────────────────────────────────────────

def _segment_geometry_metrics(points: list | tuple | None) -> dict:
    """Resume o contorno SA sem alterar ou simplificar seus vértices."""
    clean: list[tuple[float, float]] = []
    for point in points or []:
        try:
            clean.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    if not clean:
        return {
            "vertex_count": 0,
            "unique_vertex_count": 0,
            "bbox": None,
            "centroid": None,
            "span_x": 0.0,
            "span_y": 0.0,
            "orientation": "indeterminada",
            "area": 0.0,
            "closed": False,
        }

    xs = [point[0] for point in clean]
    ys = [point[1] for point in clean]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    span_x = bbox[2] - bbox[0]
    span_y = bbox[3] - bbox[1]
    orientation = (
        "horizontal" if span_x > span_y
        else "vertical" if span_y > span_x
        else "quadrada"
    )
    closed = len(clean) > 2 and clean[0] == clean[-1]
    polygon = clean[:-1] if closed else clean
    area = 0.0
    if len(polygon) >= 3:
        area = abs(sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1])
        )) / 2.0
    return {
        "vertex_count": len(clean),
        "unique_vertex_count": len(set(clean)),
        "bbox": bbox,
        "centroid": ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0),
        "span_x": span_x,
        "span_y": span_y,
        "orientation": orientation,
        "area": area,
        "closed": closed,
    }


def _error_marker_block_pil(dialog, nome: str) -> str:
    """Checkbox + nota de erro para a ficha granular de pilar, salvos em
    localStorage (mesma origem file:// compartilhada por todas as fichas) —
    mesmo padrão de `_error_marker_block` em preficha_laje_html.py /
    preficha_fundo_html.py, adaptado ao prefixo `aten_erro_pil_`."""
    key = f"aten_erro_pil_{dialog._obra}_{dialog._pavimento}_{nome}".replace(" ", "_")
    key_js = json.dumps(key)
    return (
        '<div class="sec" style="margin-top:16px;border-color:#5a2020">'
        '<div class="sec-title" style="color:#e17055">'
        "Marcação de erro (revisão humana)</div>"
        '<div class="sec-body">'
        '<label style="display:flex;align-items:center;gap:8px;cursor:pointer;'
        'color:#e17055;font-weight:bold">'
        '<input type="checkbox" id="erro_check" style="width:16px;height:16px">'
        "Marcar esta ficha como ERRADA</label>"
        '<textarea id="erro_nota" placeholder='
        '"Descreva o que está errado (N1, N2, N3 ou N4)..." '
        'style="width:100%;min-height:70px;margin-top:8px;background:#1a1a1a;'
        "color:#f0b840;border:1px solid #554400;border-radius:3px;padding:6px;"
        'font-family:monospace;font-size:11px;box-sizing:border-box"></textarea>'
        "</div></div>"
        "<script>(function(){"
        f"var key={key_js};"
        "function save(){"
        '  var chk=document.getElementById("erro_check");'
        '  var txt=document.getElementById("erro_nota");'
        "  if(chk.checked||txt.value.trim()){"
        "    localStorage.setItem(key, JSON.stringify("
        "{erro:chk.checked, nota:txt.value}));"
        "  } else { localStorage.removeItem(key); }"
        "}"
        "function load(){"
        "  var stored=localStorage.getItem(key);"
        "  if(!stored)return;"
        "  try{"
        "    var obj=JSON.parse(stored);"
        '    document.getElementById("erro_check").checked=!!obj.erro;'
        '    document.getElementById("erro_nota").value=obj.nota||"";'
        "  }catch(e){}"
        "}"
        'document.addEventListener("DOMContentLoaded", function(){'
        "  load();"
        '  document.getElementById("erro_check")'
        '    .addEventListener("change", save);'
        '  document.getElementById("erro_nota")'
        '    .addEventListener("input", save);'
        "});"
        "})();</script>"
    )


def _sidebar_error_flags_script_pil(dialog) -> str:
    """Marca com ⚠️ os itens da sidebar de pilares já revisados como errados —
    mesmo padrão de `_sidebar_error_flags_script` em preficha_fundo_html.py,
    adaptado ao seletor `[data-pilar]` e ao prefixo `aten_erro_pil_`."""
    obra_js = json.dumps(dialog._obra)
    pav_js = json.dumps(dialog._pavimento)
    return (
        "<script>(function(){"
        f"var obra={obra_js}, pav={pav_js};"
        'document.querySelectorAll(".sidebar li[data-pilar]").forEach('
        "function(li){"
        '  var nome=li.getAttribute("data-pilar");'
        '  var key=("aten_erro_pil_"+obra+"_"+pav+"_"+nome).replace(/ /g,"_");'
        "  var stored=localStorage.getItem(key);"
        "  if(!stored)return;"
        "  try{"
        "    var obj=JSON.parse(stored);"
        "    if(obj.erro||((obj.nota||'').trim())){"
        '      var flag=li.querySelector(".erro-flag");'
        '      if(flag)flag.style.display="inline";'
        "    }"
        "  }catch(e){}"
        "});"
        "})();</script>"
    )


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
        highlight_closed: bool = False,
        mute_context: bool = False,
        parent=None,
    ):
        super().__init__(scene, parent)
        self.setFixedSize(thumb_w, thumb_h)
        self._highlight_pts = highlight_pts or []
        self._highlight_closed = bool(highlight_closed)
        self._mute_context = bool(mute_context)
        
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
        """Destaca somente a geometria vinculada, sem alterar a cena compartilhada."""
        if len(self._highlight_pts) < 2:
            return
        try:
            points = [QPointF(float(p[0]), float(p[1]))
                      for p in self._highlight_pts]
        except Exception:
            return
        painter.save()
        if self._mute_context:
            veil = QColor(Colors.BG_PRIMARY)
            veil.setAlpha(150)
            painter.fillRect(rect, veil)

        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        if self._highlight_closed:
            path.closeSubpath()
            fill = QColor(Accent.PRIMARY)
            fill.setAlpha(75)
            painter.setBrush(QBrush(fill))
        else:
            painter.setBrush(Qt.NoBrush)
        pen = QPen(QColor(Accent.BRAND))
        pen.setCosmetic(True)
        pen.setWidth(4)
        painter.setPen(pen)
        painter.drawPath(path)
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
        self._segment_data: dict[str, list[dict]] = collect_preficha_segments(
            self._beams,
            slabs=self._slabs,
            pillar_report=self._pillar_report,
            nivel_report=self._nivel_report,
        )
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
            self._active_tab_index = max(0, min(10, int(ui_state.get('active_tab', 0))))
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

        Regras estruturais (Casos 1–5 do doc INTERPRETACAO-PILARES-ABCD):
          Todos os lados: VIGA (wall alinhado) > LAJE (área) > NULO
          C/D dentro de polígono de laje sem viga → LAJE (Caso 3)
          Detecção de VIGA por wall requer _beam_poly_map (TODO: implementar)

        Estratégias em ordem de prioridade:
        1. Links diretos do SA (pillar['lajes']) → bloco Laje/Altura/Nível
        2. Pontos da aresta DENTRO de polígono de laje → LAJE (A/B/C/D)
        3. Aresta colínear com borda do polígono → LAJE (A/B/C/D)
        4. Projeção perpendicular para FORA da aresta com validação direcional de eixo:
             norte/sul → exige sobreposição em X da laje com a face
             leste/oeste → exige sobreposição em Y da laje com a face
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
        # Caso 3: face embutida na área da laje sem wall de viga alinhado → LAJE
        for sn, poly_pts in self._slab_poly_map.items():
            for px, py in samples:
                if self._point_in_polygon(px, py, poly_pts):
                    return _laje_block(sn)

        # ── Estratégia 3: aresta colínear com borda do polígono ───────────────
        # Laje termina exatamente na face → LAJE para ambos os casos (A/B/C/D)
        for sn, poly_pts in self._slab_poly_map.items():
            if self._edge_overlaps_poly_boundary((ex0, ey0), (ex1, ey1), poly_pts):
                return _laje_block(sn)

        # ── Estratégia 4: projeção perpendicular para fora da aresta ──────────
        # Encontra laje adjacente exterior com validação direcional de eixo.
        # Projeção norte/sul: laje deve ter sobreposição em X com a face.
        # Projeção leste/oeste: laje deve ter sobreposição em Y com a face.
        # Evita falsos positivos onde a laje está no quadrante errado mas o polígono
        # é grande o suficiente para entrar no caminho da projeção.
        horiz = (orientation or '').lower() != 'vertical'
        outward_dirs = {
            True:  {'A': (0.0, -1.0), 'B': (0.0, 1.0), 'C': (-1.0, 0.0), 'D': (1.0, 0.0)},
            False: {'A': (-1.0, 0.0), 'B': (1.0, 0.0), 'C': (0.0, 1.0), 'D': (0.0, -1.0)},
        }
        dx, dy = outward_dirs[horiz].get(side, (0.0, 0.0))
        face_xmin = min(ex0, ex1)
        face_xmax = max(ex0, ex1)
        face_ymin = min(ey0, ey1)
        face_ymax = max(ey0, ey1)
        # Cobertura mínima: laje deve cobrir >= 50% do comprimento da face
        # no eixo perpendicular à projeção. Evita que lajes adjacentes em diagonal
        # (tocando apenas o canto do pilar) sejam detectadas como laje da face.
        _MIN_COVERAGE = 0.5
        for delta in (4.0, 12.0, 25.0):
            for px, py in samples:
                for sn, poly_pts in self._slab_poly_map.items():
                    if not self._point_in_polygon(px + dx * delta, py + dy * delta, poly_pts):
                        continue
                    # Validação direcional por cobertura do eixo perpendicular
                    if dy != 0.0:  # projeção norte/sul → checar cobertura em X
                        poly_xs = [float(p[0]) for p in poly_pts]
                        face_len = face_xmax - face_xmin
                        overlap  = min(max(poly_xs), face_xmax) - max(min(poly_xs), face_xmin)
                        if face_len > 0 and overlap < face_len * _MIN_COVERAGE:
                            continue  # laje cobre menos de 50% da face — falso positivo
                    elif dx != 0.0:  # projeção leste/oeste → checar cobertura em Y
                        poly_ys = [float(p[1]) for p in poly_pts]
                        face_len = face_ymax - face_ymin
                        overlap  = min(max(poly_ys), face_ymax) - max(min(poly_ys), face_ymin)
                        if face_len > 0 and overlap < face_len * _MIN_COVERAGE:
                            continue  # laje cobre menos de 50% da face — falso positivo
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
        highlight_closed: bool = False,
        mute_context: bool = False,
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
                highlight_closed=highlight_closed,
                mute_context=mute_context,
            )

        # Fallback geométrico se não houver cena
        pix = self._render_polygon_geometric(
            pts, thumb_w, thumb_h, fallback_line, fallback_fill,
            closed=highlight_closed,
        )
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
                                   fill_color: str = Surface.RAISED,
                                   closed: bool = True) -> QPixmap | None:
        """
        Fallback: desenha o polígono geometricamente (sem canvas disponível).
        Respeita dimensões retangulares thumb_w × thumb_h.
        """
        if not pts or len(pts) < 2:
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
        painter.setBrush(QBrush(QColor(fill_color)) if closed else Qt.NoBrush)

        polygon = QPolygonF()
        for x, y in zip(xs, ys):
            polygon.append(QPointF(
                off_x + (x - minx) * scale,
                thumb_h - off_y - (y - miny) * scale,  # flip Y
            ))
        if closed:
            painter.drawPolygon(polygon)
        else:
            painter.drawPolyline(polygon)
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
            highlight_closed=True,
        )

    def _make_cut_viewer(self, pts: list) -> QWidget | None:
        """Mini viewer vetorial centrado no corte de viga — margem um pouco maior para contexto."""
        return self._make_mini_viewer(
            pts,
            thumb_w=self._CUT_THUMB_W, thumb_h=self._CUT_THUMB_H,
            margin_factor=3.0, min_margin_dxf=130.0,
            fallback_line=Semantic.SUCCESS, fallback_fill=Semantic.SUCCESS_BG_DARK,
        )

    def _make_segment_viewer(self, pts: list, closed: bool = False) -> QWidget | None:
        """Enquadra de perto e realça exclusivamente o vínculo FV/LV selecionado."""
        return self._make_mini_viewer(
            pts,
            thumb_w=self._SEG_THUMB_W, thumb_h=self._SEG_THUMB_H,
            margin_factor=0.12, min_margin_dxf=8.0,
            fallback_line=Accent.BRAND, fallback_fill=Surface.RAISED,
            highlight_closed=closed,
            mute_context=True,
        )

    def _make_slab_viewer(self, pts: list) -> QWidget | None:
        """Enquadra e destaca exclusivamente o contorno da laje selecionada."""
        return self._make_mini_viewer(
            pts,
            thumb_w=self._SLAB_THUMB_W, thumb_h=self._SLAB_THUMB_H,
            margin_factor=0.08, min_margin_dxf=8.0,
            fallback_line=Accent.BRAND, fallback_fill=Surface.RAISED,
            highlight_closed=True,
            mute_context=True,
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
            ('lajes', getattr(self, '_slab_table', None)),
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
            "  Lajes  ",
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
            10: self._build_slabs_tab,
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
        # Lajes
        if getattr(self, '_slab_table', None) and self._slab_table.isVisible():
            self._update_dynamic_viewers(
                self._slab_table,
                getattr(self, '_slab_viewer_data', {}),
                self._SLAB_COL_FOTO,
                'slab',
            )
        # Segmentos de vigas: cada aba mantem apenas os viewers das linhas visiveis.
        for kind, table in self._segment_tables.items():
            if table.isVisible():
                self._update_dynamic_viewers(
                    table,
                    self._segment_viewer_data.get(kind, {}),
                    table.property('viewer_column'),
                    'segment',
                )

    def _dynamic_viewer_tables(self):
        pillar_table = getattr(self, '_pillar_table', None)
        if pillar_table is not None:
            yield pillar_table, getattr(self, '_pillar_viewer_data', {}), self._PIL_COL_FOTO
        cut_table = getattr(self, '_cut_table', None)
        if cut_table is not None:
            yield cut_table, getattr(self, '_cut_viewer_data', {}), self._CUT_COL_FOTO
        slab_table = getattr(self, '_slab_table', None)
        if slab_table is not None:
            yield slab_table, getattr(self, '_slab_viewer_data', {}), self._SLAB_COL_FOTO
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
    _PIL_COL_NOME      = 0
    _PIL_COL_OVERRIDE  = 1
    _PIL_COL_NIVEL     = 2
    _PIL_COL_LADOS     = 3
    _PIL_COL_ATENCAO   = 4   # nota livre para feedback / gabarito
    _PIL_COL_FOTO      = 5

    # Índice das colunas da tabela de pilares especiais (A-H)
    _ESP_COL_NOME      = 0
    _ESP_COL_OVERRIDE  = 1
    _ESP_COL_NIVEL     = 2
    _ESP_COL_LADOS     = 3
    _ESP_COL_ATENCAO   = 4
    _ESP_COL_FOTO      = 5

    # Dimensões do mini viewer de pilar
    _PIL_THUMB_W  = 880
    _PIL_THUMB_H  = 420
    _PIL_COL_FOTO_W = 890
    _PIL_ROW_H    = 430

    def _build_pillar_table(self) -> QTableWidget:
        cols = [
            "Nome / Classificação / Formato / Confiança",
            "Classif. Override", "Nível",
            "Lados ABCD", "⚑ Atenção / Feedback (editável)", "Foto",
        ]
        tbl = QTableWidget(0, len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Fixed)
        hdr.setStretchLastSection(False)
        tbl.setColumnWidth(self._PIL_COL_NOME, 170)
        tbl.setColumnWidth(self._PIL_COL_OVERRIDE, 135)
        tbl.setColumnWidth(self._PIL_COL_NIVEL, 55)
        tbl.setColumnWidth(self._PIL_COL_LADOS, 250)
        tbl.setColumnWidth(self._PIL_COL_ATENCAO, 115)
        tbl.setColumnWidth(self._PIL_COL_FOTO, self._PIL_COL_FOTO_W)
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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
            if col in skip:
                continue
            it = tbl.item(row, col)
            if it:
                if bg:
                    it.setBackground(QBrush(bg))
                else:
                    it.setBackground(QBrush())
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

            # ── Nome: fonte maior + negrito ──────────────────────────────────
            if geo_is_alt:
                nome_display = f'↺ {name} (candidato alt.)'
            elif geo_foi_rejeitada:
                nome_display = f'⚠ {name}'
            else:
                nome_display = name
            nome_item = _make_item(nome_display, bold=True)
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
            # Classif. SA com sufixo do tipo físico (sólido / visual)
            if phys == 'visual_only':
                classif_sa_display = f'{classif}  ·  visual'
            elif phys == 'solid':
                classif_sa_display = f'{classif}  ·  sólido'
            else:
                classif_sa_display = classif
            identity_text = _pillar_identity_text(
                nome_display,
                classif_sa_display,
                PILLAR_FORMATO_LABELS.get(formato, formato),
                conf_pct,
            )
            contextual_tooltip = nome_item.toolTip()
            nome_item.setText(identity_text)
            nome_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            nome_item.setData(Qt.UserRole, key)   # guarda key para lookup dinâmico
            nome_item.setData(Qt.UserRole + 1, {
                'name': nome_display,
                'classification': classif_sa_display,
                'shape': PILLAR_FORMATO_LABELS.get(formato, formato),
                'confidence': conf_pct,
            })
            nome_item.setToolTip(
                identity_text
                + (f"\n\n{contextual_tooltip}" if contextual_tooltip else "")
            )
            tbl.setItem(row, self._PIL_COL_NOME, nome_item)
            tbl.setItem(row, self._PIL_COL_NIVEL,
                        _make_item(nivel_str, Qt.AlignCenter))

            # ── Célula única Lados ABCD ──────────────────────────────────────
            # Se classificação inválida (não é pilar / geometria errada) → "Não se aplica"
            invalid_geom = classif.upper() in _NAO_SE_APLICA_CLASSIFS
            if invalid_geom:
                side_values = {side: 'Não se aplica' for side in 'ABCD'}
            else:
                side_values = {
                    side: self._get_side_cell(pillar, side)
                    for side in 'ABCD'
                }
            abcd_text = _pillar_abcd_text(side_values)
            item = _make_item(abcd_text)
            item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            item.setToolTip(abcd_text)
            if invalid_geom or all(value == 'nulo' for value in side_values.values()):
                item.setForeground(QBrush(QColor(Colors.TEXT_MUTED)))
            elif any('⚠ suspeito' in value for value in side_values.values()):
                item.setForeground(QBrush(QColor(Semantic.DANGER)))
                item.setToolTip(
                    abcd_text
                    + '\n\n⚠ Nível suspeito de alucinação — revisar vinculação de nível no DXF.'
                )
            tbl.setItem(row, self._PIL_COL_LADOS, item)

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

    def _update_dynamic_viewers(self, tbl: QTableWidget, data_dict: dict, col_idx: int, viewer_mode):
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
                payload = data_dict[row]
                if isinstance(payload, dict):
                    pts = payload.get('points') or []
                    closed = bool(payload.get('closed'))
                else:
                    pts = payload
                    closed = False
                current_widget = tbl.cellWidget(row, col_idx)
                if current_widget and isinstance(current_widget, _MiniDXFView):
                    continue

                if viewer_mode == 'segment':
                    viewer = self._make_segment_viewer(pts, closed=closed)
                elif viewer_mode == 'slab':
                    viewer = self._make_slab_viewer(pts)
                elif viewer_mode:
                    viewer = self._make_cut_viewer(pts)
                else:
                    viewer = self._make_pillar_viewer(pts)
                if viewer:
                    tbl.setCellWidget(row, col_idx, viewer)
                else:
                    tbl.setItem(row, col_idx, _make_item('—', Qt.AlignCenter, color=QColor(Colors.TEXT_MUTED)))
                    del data_dict[row]
                    
        # Unload invisíveis para salvar memória e rendering
        for row in list(data_dict):
            if row < start_row or row > end_row:
                current_widget = tbl.cellWidget(row, col_idx)
                if current_widget and isinstance(current_widget, _MiniDXFView):
                    lbl = QLabel("⏳ Rolar para carregar")
                    lbl.setAlignment(Qt.AlignCenter)
                    lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 10px;")
                    tbl.setCellWidget(row, col_idx, lbl)

    def _refresh_side_cells(self, row: int, key: str, classif: str):
        """
        Atualiza a célula consolidada Lados ABCD da linha.

        Se classif estiver em _NAO_SE_APLICA_CLASSIFS (não é pilar ou geometria
        errada), preenche os quatro blocos com "Não se aplica" (cinza).
        Caso contrário, recalcula via _get_side_cell.
        """
        tbl = self._pillar_table
        pillar = self._pillar_report.get(key, {})
        invalid = classif.upper() in _NAO_SE_APLICA_CLASSIFS

        side_values = (
            {side: 'Não se aplica' for side in 'ABCD'}
            if invalid
            else {side: self._get_side_cell(pillar, side) for side in 'ABCD'}
        )
        abcd_text = _pillar_abcd_text(side_values)
        item = _make_item(abcd_text)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
        item.setToolTip(abcd_text)
        if invalid or all(value == 'nulo' for value in side_values.values()):
            item.setForeground(QBrush(QColor(Colors.TEXT_MUTED)))
        elif any('⚠ suspeito' in value for value in side_values.values()):
            item.setForeground(QBrush(QColor(Semantic.DANGER)))
        tbl.setItem(row, self._PIL_COL_LADOS, item)

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
        """Atualiza o bloco Classificação SA dentro da célula Nome."""
        tbl = self._pillar_table
        phys = self._term_type_map.get(term, 'unknown')
        for row in range(tbl.rowCount()):
            identity_item = tbl.item(row, self._PIL_COL_NOME)
            if not identity_item:
                continue
            metadata = identity_item.data(Qt.UserRole + 1) or {}
            base = str(metadata.get('classification') or '').split('  ·  ')[0].strip()
            if base.upper() != term.upper():
                continue
            if phys == 'visual_only':
                new_text = f'{term}  ·  visual'
            elif phys == 'solid':
                new_text = f'{term}  ·  sólido'
            else:
                new_text = term
            metadata['classification'] = new_text
            identity_item.setData(Qt.UserRole + 1, metadata)
            identity_text = _pillar_identity_text(
                metadata.get('name', '—'),
                new_text,
                metadata.get('shape', '—'),
                metadata.get('confidence', 0),
            )
            identity_item.setText(identity_text)
            identity_item.setToolTip(identity_text)

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
    _CUT_COL_DIM    = 1   # H × W da viga
    _CUT_COL_LAJE1  = 2   # Laje 1 (multilinhas: nome, dir, H, classif, dist)
    _CUT_COL_LAJE2  = 3   # Laje 2 (idem, ou "Parede")
    _CUT_COL_STATUS = 4   # Combobox: válido / não é VC / errada
    _CUT_COL_ATENCAO = 5  # feedback humano editável
    _CUT_COL_FOTO   = 6   # Mini viewer

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
        cols = ["Viga Assoc.", "Detalhes sobre o Segmento de Viga",
                "Lajes LADO A", "Lajes LADO B", "Status",
                "⚑ Atenção / Feedback (editável)", "Foto"]
        tbl = QTableWidget(0, len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Fixed)
        hdr.setStretchLastSection(False)
        tbl.setColumnWidth(self._CUT_COL_VIGA, _cut_compact_width(210))
        tbl.setColumnWidth(self._CUT_COL_DIM, _cut_compact_width(230))
        for col in (self._CUT_COL_LAJE1, self._CUT_COL_LAJE2):
            tbl.setColumnWidth(col, _cut_compact_width(self._CUT_LAJE_COL_W))
        tbl.setColumnWidth(self._CUT_COL_STATUS, _cut_compact_width(220))
        tbl.setColumnWidth(self._CUT_COL_ATENCAO, _cut_compact_width(300))
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
        uid = item.data(Qt.UserRole)
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
            attention_item.setData(Qt.UserRole, uid)
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
        columns = [
            "Viga", "Detalhes do Segmento", "Status",
            "⚑ Feedback deste segmento (editável)", "Foto",
        ]
        col = {
            'beam': 0, 'details': 1, 'status': 2, 'attention': 3, 'photo': 4,
        }

        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setProperty('viewer_column', col['photo'])
        table.setProperty('attention_column', col['attention'])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setStretchLastSection(False)
        table.setColumnWidth(col['beam'], 120)
        table.setColumnWidth(col['details'], 285)
        table.setColumnWidth(col['status'], 165)
        table.setColumnWidth(col['attention'], 155)
        header.setSectionResizeMode(col['photo'], QHeaderView.Fixed)
        table.setColumnWidth(col['photo'], self._SEG_THUMB_W + 10)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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
                self._update_dynamic_viewers(t, d, c, 'segment')
        )
        table.itemChanged.connect(
            lambda item, t=table: self._on_segment_attention_changed(t, item)
        )

        table.setUpdatesEnabled(False)
        for segment in self._segment_data.get(kind, []):
            row = table.rowCount()
            table.insertRow(row)
            table.setRowHeight(row, self._SEG_ROW_H)
            identity_text = _segment_identity_text(segment, is_fundo)
            beam_item = _make_item(identity_text, bold=True)
            beam_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            beam_item.setToolTip(identity_text)
            beam_item.setData(Qt.UserRole, segment['uid'])
            table.setItem(row, col['beam'], beam_item)
            details_text = _segment_details_text(segment, is_fundo)
            detail_label = QLabel(details_text)
            detail_label.setTextFormat(Qt.PlainText)
            detail_label.setWordWrap(True)
            detail_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            detail_label.setToolTip(details_text)
            detail_label.setStyleSheet(
                f"color:{Colors.TEXT_SECONDARY}; padding:5px; background:transparent;"
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
            attention_item.setToolTip(
                "Feedback exclusivo deste segmento na pré-ficha. "
                "Não altera a Atenção Geral da viga no SA."
            )
            table.setItem(row, col['attention'], attention_item)

            points = segment.get('points') or []
            if points:
                viewer_data[row] = {'points': points, 'closed': is_fundo}
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
                self._update_dynamic_viewers(t, d, c, 'segment'),
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

    # ── Aba Lajes ───────────────────────────────────────────────────────────────

    _SLAB_COL_NOME = 0
    _SLAB_COL_DETALHES = 1
    _SLAB_COL_VH = 2
    _SLAB_COL_FOTO = 3
    _SLAB_THUMB_W = 880
    _SLAB_THUMB_H = 420
    _SLAB_ROW_H = 430

    def _build_slabs_tab(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        info = QLabel(
            f"Lajes — {len(self._slabs)} item(ns). "
            "O viewer enquadra e destaca exclusivamente o contorno vinculado da laje. "
            "Verticais/Horizontais permanece reservado e sem preenchimento."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"font-size:9px; color:{Colors.TEXT_MUTED};")
        layout.addWidget(info)
        layout.addWidget(self._build_slab_table(), 1)
        return root

    def _build_slab_table(self) -> QTableWidget:
        columns = [
            "Nome",
            "Detalhes da Laje",
            "Verticais / Horizontais",
            "Foto",
        ]
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setStretchLastSection(False)
        table.setColumnWidth(self._SLAB_COL_NOME, 100)
        table.setColumnWidth(self._SLAB_COL_DETALHES, 380)
        table.setColumnWidth(self._SLAB_COL_VH, 235)
        table.setColumnWidth(self._SLAB_COL_FOTO, self._SLAB_THUMB_W + 10)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.setStyleSheet("QTableWidget { font-size:9px; }")
        table.setMinimumHeight(0)

        self._slab_table = table
        self._slab_viewer_data: dict[int, list] = {}
        table.verticalScrollBar().valueChanged.connect(
            lambda _: self._update_dynamic_viewers(
                self._slab_table,
                self._slab_viewer_data,
                self._SLAB_COL_FOTO,
                'slab',
            )
        )

        table.setUpdatesEnabled(False)
        slabs = sorted(
            self._slabs,
            key=lambda slab: self._natural_sort_key(
                str(slab.get('name') or slab.get('laje_name') or '')
            ),
        )
        for slab in slabs:
            row = table.rowCount()
            table.insertRow(row)
            table.setRowHeight(row, self._SLAB_ROW_H)

            name = str(
                slab.get('name')
                or slab.get('laje_name')
                or (slab.get('fields') or {}).get('nome')
                or '—'
            )
            name_item = _make_item(name, bold=True)
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            name_item.setToolTip(name)
            table.setItem(row, self._SLAB_COL_NOME, name_item)

            details_text = _slab_details_text(
                slab,
                height=self._slab_height_map.get(name, ''),
                level=self._slab_nivel_map.get(name, ''),
            )
            details_label = QLabel(details_text)
            details_label.setTextFormat(Qt.PlainText)
            details_label.setWordWrap(True)
            details_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            details_label.setToolTip(details_text)
            details_label.setStyleSheet(
                f"color:{Colors.TEXT_SECONDARY}; padding:5px; background:transparent;"
            )
            table.setCellWidget(row, self._SLAB_COL_DETALHES, details_label)

            # Reserva explícita: não preencher até o motor V/H ser definido.
            vh_item = _make_item("")
            vh_item.setToolTip(
                "Coluna reservada para Verticais/Horizontais; sem preenchimento nesta etapa."
            )
            table.setItem(row, self._SLAB_COL_VH, vh_item)

            points = _slab_outline_points(slab)
            if points:
                self._slab_viewer_data[row] = points
                loading = QLabel("⏳ Carregando...")
                loading.setAlignment(Qt.AlignCenter)
                loading.setStyleSheet(
                    f"color:{Colors.TEXT_MUTED}; font-size:10px;"
                )
                table.setCellWidget(row, self._SLAB_COL_FOTO, loading)
            else:
                table.setItem(
                    row,
                    self._SLAB_COL_FOTO,
                    _make_item('—', Qt.AlignCenter, color=QColor(Colors.TEXT_MUTED)),
                )

        table.setUpdatesEnabled(True)
        QTimer.singleShot(
            150,
            lambda: self._update_dynamic_viewers(
                table,
                self._slab_viewer_data,
                self._SLAB_COL_FOTO,
                'slab',
            ),
        )
        self._restore_table_scroll(table, 'lajes')
        return table

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
            "Nome / Classificação / Formato / Confiança",
            "Classif. Override", "Nível", "Lados ABCDEFGH",
            "⚑ Atenção / Feedback (editável)", "Foto",
        ]
        tbl = QTableWidget(0, len(cols))
        tbl.setHorizontalHeaderLabels(cols)
        hdr = tbl.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Fixed)
        hdr.setStretchLastSection(False)
        tbl.setColumnWidth(self._ESP_COL_NOME, 170)
        tbl.setColumnWidth(self._ESP_COL_OVERRIDE, 135)
        tbl.setColumnWidth(self._ESP_COL_NIVEL, 55)
        tbl.setColumnWidth(self._ESP_COL_LADOS, 250)
        tbl.setColumnWidth(self._ESP_COL_ATENCAO, 115)
        tbl.setColumnWidth(self._ESP_COL_FOTO, self._PIL_COL_FOTO_W)
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setEditTriggers(
            QAbstractItemView.CurrentChanged
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.DoubleClicked
        )
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
        tbl.itemChanged.connect(self._on_especial_attention_changed)
        self._populate_especiais_table()
        return tbl

    def _on_especial_attention_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != self._ESP_COL_ATENCAO:
            return
        nome_item = self._especiais_table.item(item.row(), self._ESP_COL_NOME)
        key = nome_item.data(Qt.UserRole) if nome_item else None
        if key:
            self._atencao_notes[str(key)] = item.text().strip()

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
            if hist_pil and hist_pil.get('attention'):
                self._atencao_notes[key] = str(hist_pil['attention'])

            phys = self._physical_type_for(classif)
            conf_pct = 0 if classif == 'INDETERMINADO' else 95
            if classif in (_NAO_PILAR_SOLIDO, _NAO_PILAR_VISUAL):
                conf_pct = 100

            p_nr = nr_pilares.get(key, {})
            nivel_str = p_nr.get('level_str') or '—'

            # Identificação consolidada
            if phys == 'visual_only':
                classif_sa_display = f'{classif}  ·  visual'
            elif phys == 'solid':
                classif_sa_display = f'{classif}  ·  sólido'
            else:
                classif_sa_display = classif
            shape_display = PILLAR_FORMATO_LABELS.get(formato, formato)
            identity_text = _pillar_identity_text(
                name, classif_sa_display, shape_display, conf_pct
            )
            nome_item = _make_item(identity_text, bold=True)
            nome_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            nome_item.setToolTip(identity_text)
            nome_item.setData(Qt.UserRole, key)
            nome_item.setData(Qt.UserRole + 1, {
                'name': name,
                'classification': classif_sa_display,
                'shape': shape_display,
                'confidence': conf_pct,
            })
            tbl.setItem(row, self._ESP_COL_NOME, nome_item)
            tbl.setItem(row, self._ESP_COL_NIVEL,
                        _make_item(nivel_str, Qt.AlignCenter))

            # Célula única Lados A-H
            invalid_geom = classif.upper() in _NAO_SE_APLICA_CLASSIFS
            if invalid_geom:
                side_values = {side: 'Não se aplica' for side in 'ABCDEFGH'}
            else:
                side_values = {
                    **{side: self._get_side_cell(pillar, side) for side in 'ABCD'},
                    **{side: '—' for side in 'EFGH'},
                }
            sides_text = _pillar_abcdefgh_text(side_values)
            sides_item = _make_item(sides_text)
            sides_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            sides_item.setToolTip(sides_text)
            if invalid_geom or all(
                value in {'nulo', '—'} for value in side_values.values()
            ):
                sides_item.setForeground(QBrush(QColor(Colors.TEXT_MUTED)))
            elif any('⚠ suspeito' in value for value in side_values.values()):
                sides_item.setForeground(QBrush(QColor(Semantic.DANGER)))
            tbl.setItem(row, self._ESP_COL_LADOS, sides_item)

            # Atenção editável, compartilhada com histórico e HTML
            attention_item = QTableWidgetItem(self._atencao_notes.get(key, ''))
            attention_item.setForeground(QBrush(QColor(Contextual.GOLD)))
            attention_item.setToolTip(
                'Clique para digitar uma nota de atenção — será salva no HTML.'
            )
            tbl.setItem(row, self._ESP_COL_ATENCAO, attention_item)

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
                lambda _, k=key, c=combo: self._on_especial_classif_changed(k, c))
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
            skip = {
                self._ESP_COL_OVERRIDE,
                self._ESP_COL_ATENCAO,
                self._ESP_COL_FOTO,
            }
            for col in range(tbl.columnCount()):
                if col in skip: continue
                it = tbl.item(row, col)
                if it:
                    if bg: it.setBackground(QBrush(bg))
                    else:  it.setBackground(QBrush())

        tbl.setUpdatesEnabled(True)
        QTimer.singleShot(150, lambda: self._update_dynamic_viewers(
            tbl, self._especiais_viewer_data, self._ESP_COL_FOTO, False))

    def _on_especial_classif_changed(self, key: str, combo: QComboBox) -> None:
        self._on_pillar_classif_changed(key, combo)
        row = getattr(self, '_especiais_rows', {}).get(key)
        if row is None:
            return
        classif = combo.currentText()
        pillar = self._pillar_report.get(key, {})
        invalid = classif.upper() in _NAO_SE_APLICA_CLASSIFS
        side_values = (
            {side: 'Não se aplica' for side in 'ABCDEFGH'}
            if invalid
            else {
                **{side: self._get_side_cell(pillar, side) for side in 'ABCD'},
                **{side: '—' for side in 'EFGH'},
            }
        )
        text = _pillar_abcdefgh_text(side_values)
        item = _make_item(text)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
        item.setToolTip(text)
        if invalid or all(value in {'nulo', '—'} for value in side_values.values()):
            item.setForeground(QBrush(QColor(Colors.TEXT_MUTED)))
        self._especiais_table.setItem(row, self._ESP_COL_LADOS, item)

        bg = self._row_bg_for_classif(classif)
        skip = {
            self._ESP_COL_OVERRIDE,
            self._ESP_COL_ATENCAO,
            self._ESP_COL_FOTO,
        }
        for col in range(self._especiais_table.columnCount()):
            if col in skip:
                continue
            row_item = self._especiais_table.item(row, col)
            if row_item:
                row_item.setBackground(QBrush(bg) if bg else QBrush())

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
                    # Geometria bruta (antes ausente do snapshot) — necessária para o
                    # diagnóstico numérico headless N1×N2 comparar bbox sem depender de
                    # self.slabs_found (só existe com UI aberta). Aditivo: nenhum
                    # consumidor existente do estado JSON lia essas chaves antes.
                    'points': s.get('points') or [],
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

    def _render_ezdxf_b64(self, dxf_path: str, width: int = 900, height: int = 600,
                           fmt: str = 'png') -> str:
        """Renderiza qualquer DXF com ezdxf+matplotlib (fundo branco).

        fmt='png' (default): retorna base64 PNG, para embutir em <img src="data:...">.
        fmt='svg': retorna markup SVG cru (texto preservado como <text> real do DOM,
        ver `_svg_strip_fixed_size`) para embutir inline no HTML — permite ao Playwright
        ler rótulos/cotas via DOM/accessibility tree sem gastar visão (ARETE-LOOP-
        PROCEDIMENTO-GERAL.md §5.1).
        """
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
            rc = {'svg.fonttype': 'none'} if fmt == 'svg' else {}
            with matplotlib.rc_context(rc):
                fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
                ax = fig.add_axes([0, 0, 1, 1])
                ctx = RenderContext(doc)
                out = MatplotlibBackend(ax)
                Frontend(ctx, out).draw_layout(msp)
                buf = io.BytesIO()
                fig.savefig(buf, format=fmt, dpi=dpi, facecolor='white', bbox_inches='tight')
                plt.close(fig)
            buf.seek(0)
            if fmt == 'svg':
                return _svg_strip_fixed_size(buf.read().decode('utf-8'))
            return base64.b64encode(buf.read()).decode('ascii')
        except Exception as exc:
            print(f'[HTML] _render_ezdxf_b64 falhou ({dxf_path}): {exc}', flush=True)
            return ''

    def _find_pilar_dxf(self, view_type: str, item_name: str, n4: bool = False) -> str:
        """Retorna path do DXF da vista solicitada.
        n4=True  → split CIMA/ABCD/GRADES em /n4/ (gerado pelo CE via N2 com governance fix)
                   fallback para raiz Fase-6 (gerado pelo CE antes do governance).
        n4=False → split CIMA/ABCD/GRADES em raiz Fase-6 (N3, gerado via Fase-4/N1).
        """
        if not self._obra:
            return ''
        base = os.path.join('D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra, 'Fase-6_Execucao_CAD')
        if view_type == 'CIMA':
            split_name = f'PL_CIMA_preview_{item_name}.dxf'
        elif view_type == 'ABCD':
            split_name = f'PL_ABCD_preview_{item_name}.dxf'
        elif view_type == 'GRADES':
            split_name = f'PL_GRADES_preview_{item_name}.dxf'
        else:
            split_name = f'PL_preview_{item_name}.dxf'

        if n4:
            # N4: /n4/ subpasta primeiro (após governance fix), depois raiz como fallback
            candidates = [
                os.path.join(base, 'n4', split_name),
                os.path.join(base, split_name),
            ]
        else:
            # N3: raiz Fase-6 (gerado via Fase-4/N1)
            candidates = [os.path.join(base, split_name)]

        for p in candidates:
            if os.path.exists(p):
                return p
        return ''

    def _find_beam_dxf(self, class_prefix: str, item_name: str, n4: bool = False) -> str:
        """Localiza o artefato DXF N3/N4 de uma viga ou laje sem misturar os níveis."""
        if not self._obra:
            return ''
        prefix = str(class_prefix or '').upper()
        if prefix not in {'FV', 'LV', 'LJ'}:
            return ''
        base = os.path.join(
            'D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra,
            'Fase-6_Execucao_CAD',
        )
        isolated_n3_dir = str(getattr(self, '_n3_preview_dir', '') or '')
        if not n4 and isolated_n3_dir and prefix in {'FV', 'LV', 'LJ'}:
            # Exportações comparativas podem fornecer candidatos NOVA isolados.
            # Quando o diretório foi definido, nunca cair no preview compartilhado
            # da Fase-6, que pode ter sido sobrescrito pelo modo INI.
            search_dir = isolated_n3_dir
        else:
            search_dir = os.path.join(base, 'n4') if n4 else base
        candidates = [
            os.path.join(search_dir, f'{prefix}_preview_{item_name}.dxf'),
            os.path.join(search_dir, f'{prefix}_preview_{item_name}_fundo.dxf'),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path

        # Fichas de vigas equivalentes podem compartilhar um único artefato,
        # por exemplo V313-V315-V317. A associação é por token estrutural
        # completo; V31 nunca casa acidentalmente com V313.
        import glob as _glob
        import re as _re
        wanted = str(item_name or '').upper()
        grouped = sorted(_glob.glob(
            os.path.join(search_dir, f'{prefix}_preview_*.dxf')
        ))
        for path in grouped:
            suffix = os.path.splitext(os.path.basename(path))[0]
            tokens = {
                token.upper()
                for token in _re.findall(r'VF?\d+[A-Z]?', suffix, _re.IGNORECASE)
            }
            normalized = {
                _re.sub(r'(?<=\d)[A-Z]$', '', token) for token in tokens
            }
            if wanted in tokens or wanted in normalized:
                return path
        return ''

    def _find_n2_recorte_dxf(self, class_prefix: str, item_name: str) -> str:
        """Localiza o recorte N2 validado por humano (status='aprovado' na
        tabela reverse_eng_recortes — mesma convenção usada em
        diagnostic_reverse_hub.py). A tabela é a fonte de verdade; um glob
        por nome de arquivo pode pegar qualquer tentativa automática do
        motor (status 'auto_aprovado'/'motor'), não a que um humano validou,
        já que a ordenação alfabética de pastas não reflete aprovação."""
        if not self._obra:
            return ''
        prefix = str(class_prefix or '').upper()

        db_path = self._db_path or 'D:/Agente-cad-PYSIDE/project_data.vision'
        if db_path and os.path.isfile(db_path):
            try:
                import sqlite3 as _sql
                conn = _sql.connect(db_path)
                row = conn.execute(
                    "SELECT recorte_path FROM reverse_eng_recortes "
                    "WHERE obra_name=? AND classe=? AND elemento_id=? "
                    "AND status='aprovado' ORDER BY created_at DESC LIMIT 1",
                    (self._obra, prefix, item_name),
                ).fetchone()
                if not row:
                    # Nenhum recorte aprovado ainda — melhor mostrar o
                    # candidato mais recente do motor do que nada, mas
                    # nunca preferir isso a um 'aprovado' existente.
                    row = conn.execute(
                        "SELECT recorte_path FROM reverse_eng_recortes "
                        "WHERE obra_name=? AND classe=? AND elemento_id=? "
                        "ORDER BY created_at DESC LIMIT 1",
                        (self._obra, prefix, item_name),
                    ).fetchone()
                conn.close()
                if row and row[0] and os.path.isfile(row[0]):
                    return row[0]
            except Exception:
                pass

        import glob as _glob
        recortes_base = os.path.join(
            'D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra,
            'Fase-2_Triagem', 'recortes_reversos',
        )
        pattern = os.path.join(
            recortes_base, '**', f'{prefix}_{item_name}_motor_*.dxf',
        )
        matches = sorted(_glob.glob(pattern, recursive=True), reverse=True)
        if matches:
            return matches[0]

        import re as _re
        wanted = str(item_name or '').upper()
        all_matches = sorted(_glob.glob(
            os.path.join(recortes_base, '**', f'{prefix}_*_motor_*.dxf'),
            recursive=True,
        ), reverse=True)
        for path in all_matches:
            filename = os.path.basename(path).split('_motor_', 1)[0]
            tokens = {
                token.upper()
                for token in _re.findall(r'VF?\d+[A-Z]?', filename, _re.IGNORECASE)
            }
            normalized = {
                _re.sub(r'(?<=\d)[A-Z]$', '', token) for token in tokens
            }
            if wanted in tokens or wanted in normalized:
                return path
        return ''

    def _n3_ficha_html_beam(self, class_prefix: str, item_name: str) -> str:
        """Expõe todos os campos do JSON Fase-4 usado para gerar o N3."""
        import html as _hl
        import json as _json
        if not self._obra:
            return '<span style="color:#555">sem obra</span>'
        prefix = str(class_prefix or '').upper()
        folder_name = 'JSON_Vigas_Fundo' if prefix == 'FV' else 'JSON_Vigas_Laterais'
        candidates = []
        isolated_contract_dir = str(
            getattr(self, '_n3_contract_dir', '') or ''
        )
        if prefix == 'FV' and isolated_contract_dir:
            candidates.append(os.path.join(
                isolated_contract_dir, f'{item_name}_fundo.json'
            ))
        candidates.extend([
            os.path.join(
                'D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra,
                'Fase-4_Sincronizacao', folder_name,
                f'{item_name}_fundo.json' if prefix == 'FV' else f'{item_name}.json',
            )
        ])
        if prefix == 'LV':
            candidates.extend([
                os.path.join(
                    'D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra,
                    'Fase-4_Sincronizacao', folder_name, f'{item_name}_A.json',
                ),
                os.path.join(
                    'D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra,
                    'Fase-4_Sincronizacao', folder_name, f'{item_name}_B.json',
                ),
            ])
        json_path = next((path for path in candidates if os.path.exists(path)), '')
        if not json_path:
            return '<span style="color:#555">sem JSON N3</span>'
        try:
            with open(json_path, encoding='utf-8') as file:
                data = _json.load(file)
            rows = []
            for key, value in data.items():
                if value in (None, '', [], {}):
                    continue
                rendered = _json.dumps(value, ensure_ascii=False, indent=2)
                rows.append(
                    '<tr>'
                    f'<td style="color:#4fc3a1;padding:2px 5px;white-space:nowrap;'
                    f'vertical-align:top">{_hl.escape(str(key))}</td>'
                    f'<td style="padding:2px 5px;white-space:pre-wrap">'
                    f'{_hl.escape(rendered)}</td></tr>'
                )
            return (
                '<table style="font-size:9px;border-collapse:collapse">'
                f'{"".join(rows)}</table>'
            )
        except Exception as exc:
            return f'<span style="color:#555">erro: {_hl.escape(str(exc))}</span>'

    def _render_n2_recorte_b64(self, item_name: str, width: int = 700, height: int = 500,
                                fmt: str = 'png') -> str:
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
        return self._render_ezdxf_b64(matches[0], width=width, height=height, fmt=fmt)

    def _n1_ficha_html_pilar(self, pilar_key: str) -> str:
        """Retorna HTML completo com TODOS os campos SA do pilar (Ficha N1 SA)."""
        import html as _hl
        pillar = self._pillar_report.get(pilar_key, {})
        if not pillar:
            return '<span style="color:#555">—</span>'
        nr_entry = (self._nivel_report or {}).get('pilares', {}).get(pilar_key, {})

        FACE_COLORS = {'A': '#ff9f43', 'B': '#4fc3a1', 'C': '#e17055', 'D': '#74b9ff'}
        CT_COLORS = {'laje': '#4fc3a1', 'viga': '#7eb8f7', 'both': '#e6b400'}

        def _row(label: str, val, color: str = '#7eb8f7', mono: bool = False) -> str:
            vstyle = 'font-family:monospace;white-space:pre-wrap' if mono else 'white-space:pre-wrap'
            return (f'<tr><td style="color:{color};padding:1px 5px;white-space:nowrap;'
                    f'font-weight:600;vertical-align:top">{_hl.escape(str(label))}</td>'
                    f'<td style="padding:1px 5px;{vstyle}">{_hl.escape(str(val))}</td></tr>')

        def _sep(label: str) -> str:
            return (f'<tr><td colspan="2" style="padding:4px 5px 1px;color:#4fc3a1;'
                    f'font-weight:700;border-top:1px solid #333;font-size:10px">'
                    f'{_hl.escape(label)}</td></tr>')

        rows = []

        # ── IDENTIDADE ────────────────────────────────────────────────────────
        rows.append(_sep('IDENTIDADE'))
        rows.append(_row('Nome', pillar.get('name', pilar_key)))
        rows.append(_row('Classificação', pillar.get('classification', '—'),
                         color='#e6b400' if pillar.get('classification') == 'INDETERMINADO' else '#4fc3a1'))
        rows.append(_row('Shape', pillar.get('shape_type', '—')))
        rows.append(_row('Orientação', pillar.get('orientation', '—')))
        rows.append(_row('Ignora vigas?', 'Sim' if pillar.get('ignore_in_beams') else 'Não'))
        rows.append(_row('Geo. fonte', pillar.get('geometry_source', '—')))
        if pillar.get('needs_geometry'):
            rows.append(_row('Geometria', 'NAO RESOLVIDA', color='#e17055'))
        npos = len(pillar.get('name_positions') or [])
        if npos:
            rows.append(_row('Posições texto', str(npos)))

        # ── GEOMETRIA ─────────────────────────────────────────────────────────
        rows.append(_sep('GEOMETRIA'))
        pts = pillar.get('points') or []
        if pts:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            w, h_ = max(xs) - min(xs), max(ys) - min(ys)
            rows.append(_row('Comprimento', f'{max(w, h_):.1f}'))
            rows.append(_row('Largura',     f'{min(w, h_):.1f}'))
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            rows.append(_row('Centro DXF',  f'({cx:.1f}, {cy:.1f})'))
        bbox = pillar.get('bbox')
        if bbox:
            rows.append(_row('BBox', f'({bbox[0]:.1f},{bbox[1]:.1f}) → ({bbox[2]:.1f},{bbox[3]:.1f})'))

        # ── NÍVEL (nivel_report) ───────────────────────────────────────────────
        rows.append(_sep('NÍVEL'))
        if nr_entry:
            for k, v in nr_entry.items():
                if v not in (None, '', 0, 0.0):
                    rows.append(_row(k, v, color='#c8e6c9'))
        nivel_str_pilar = pillar.get('nivel_str', '')
        if nivel_str_pilar:
            rows.append(_row('nivel_str', nivel_str_pilar, color='#c8e6c9'))

        # ── FACES A/B/C/D (output primário do SA) ────────────────────────────
        rows.append(_sep('FACES A / B / C / D  (SA)'))
        for face_id in ('A', 'B', 'C', 'D'):
            try:
                cell_text = self._get_side_cell(pillar, face_id)
            except Exception:
                cell_text = '—'
            col = FACE_COLORS.get(face_id, '#aaa')
            rows.append(_row(f'Lado {face_id}', cell_text or 'nulo', color=col, mono=True))

        # ── LAJES ADJACENTES DETALHADAS ───────────────────────────────────────
        rows.append(_sep('LAJES ADJACENTES (raw SA)'))
        lajes = pillar.get('lajes') or []
        if lajes:
            for lj in lajes:
                nome_lj    = lj.get('laje') or '(sem laje)'
                side       = lj.get('side', '?')
                face       = lj.get('face', '')
                src        = lj.get('side_source', lj.get('source', ''))
                dist       = lj.get('dist', '')
                ct         = lj.get('content_type', '')
                viga_info  = lj.get('viga') or {}
                # Altura e nível vêm dos mapas de slab (não ficam no laje entry)
                alt  = self._slab_height_map.get(nome_lj, '') if nome_lj != '(sem laje)' else ''
                niv  = self._slab_nivel_map.get(nome_lj, '')  if nome_lj != '(sem laje)' else ''

                parts = [f'Side={side}']
                if face and face not in ('AUTO', ''):
                    parts.append(f'Face={face}')
                if ct:
                    parts.append(f'tipo={ct}')
                if alt:
                    parts.append(f'Alt={alt}cm')
                if niv:
                    parts.append(f'Nív={niv}')
                if dist:
                    try:
                        parts.append(f'dist={float(dist):.0f}')
                    except Exception:
                        parts.append(f'dist={dist}')
                if src:
                    parts.append(f'[{src}]')
                if viga_info:
                    v_name = viga_info.get('name', '?')
                    v_dim  = viga_info.get('dim', '')
                    parts.append(f'VIGA={v_name}' + (f'({v_dim})' if v_dim else ''))

                detail = '  '.join(parts)
                col = FACE_COLORS.get(side, '#aaa')
                if ct:
                    col = CT_COLORS.get(ct, col)
                rows.append(_row(nome_lj, detail, color=col))
        else:
            rows.append(_row('—', 'sem lajes vinculadas', color='#e17055'))

        # ── CAMPOS EXTRAS (tudo que sobrou no dict) ───────────────────────────
        skip = {
            'name', 'classification', 'shape_type', 'orientation', 'ignore_in_beams',
            'geometry_source', 'points', 'lajes', 'beams', 'bbox', 'nivel_str',
            'lajes_adjacentes', 'preficha_reviewed', 'confidence_map', 'links',
            'issues', 'needs_geometry', 'alt_for_original_key', 'geometry_alt_candidate',
            'name_positions',
        }
        extras = {k: v for k, v in pillar.items()
                  if k not in skip and v not in (None, '', 0, 0.0, [], {})}
        if extras:
            rows.append(_sep('OUTROS CAMPOS'))
            for k, v in sorted(extras.items()):
                rows.append(_row(k, str(v)[:200]))

        return (f'<table style="font-size:9px;border-collapse:collapse;'
                f'background:#181818;min-width:340px">{"".join(rows)}</table>')

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

    def _render_pilar_dxf_context_b64(
        self,
        pilar_pts: list,
        width: int = 910,
        height: int = 650,
        focus_mode: str = 'pillar',
        fmt: str = 'png',
    ) -> str:
        """
        Renderiza o contexto DXF ao redor do pilar com as cores reais do DXF (ACI/RGB),
        exatamente como o mini-viewer do SA. Pilar destacado em teal.

        fmt='png' (default): base64 PNG. fmt='svg': markup SVG cru com texto/cota
        preservado como <text> real do DOM (ver `_render_ezdxf_b64` para o racional).
        """
        if not pilar_pts or not self._dxf_data:
            return ''
        try:
            import io, base64
            import matplotlib
            matplotlib.use('Agg')
            if fmt == 'svg':
                # Sem efeito no backend PNG/Agg — só muda como o backend SVG
                # embute texto (mantém <text> real em vez de converter p/ path).
                matplotlib.rcParams['svg.fonttype'] = 'none'
            import matplotlib.pyplot as plt
            from matplotlib.patches import Polygon as MplPolygon

            xs = [float(p[0]) for p in pilar_pts]
            ys = [float(p[1]) for p in pilar_pts]
            pw, ph = max(xs) - min(xs), max(ys) - min(ys)
            if focus_mode == 'segment':
                long_span = max(pw, ph, 1.0)
                short_span = max(min(pw, ph), 1.0)
                pad_long = max(60.0, long_span * 0.20)
                pad_short = max(90.0, short_span * 5.0)
                if pw >= ph:
                    vx0, vx1 = min(xs) - pad_long, max(xs) + pad_long
                    vy0, vy1 = min(ys) - pad_short, max(ys) + pad_short
                else:
                    vx0, vx1 = min(xs) - pad_short, max(xs) + pad_short
                    vy0, vy1 = min(ys) - pad_long, max(ys) + pad_long
            elif focus_mode == 'slab':
                # Lajes são áreas (não pontos como pilar nem linhas como
                # segmento de viga) — margem proporcional ao próprio
                # tamanho é suficiente para mostrar vizinhança/apoios sem
                # zoom fora a ponto de virar o mapa inteiro do pavimento.
                pad_x = max(40.0, pw * 0.35)
                pad_y = max(40.0, ph * 0.35)
                vx0, vx1 = min(xs) - pad_x, max(xs) + pad_x
                vy0, vy1 = min(ys) - pad_y, max(ys) + pad_y
            else:
                margin = (max(pw, ph) * 3.0 + 60) * 1.3
                vx0, vx1 = min(xs) - margin, max(xs) + margin
                vy0, vy1 = min(ys) - margin, max(ys) + margin
            view_w = max(vx1 - vx0, 1.0)

            BG = '#0d0d0d'
            dpi = 150
            fig, ax = plt.subplots(figsize=(width / dpi, height / dpi), dpi=dpi)
            ax.set_facecolor(BG)
            fig.patch.set_facecolor(BG)
            ax.set_aspect('equal')
            ax.set_xlim(vx0, vx1)
            ax.set_ylim(vy0, vy1)
            ax.axis('off')

            def _rgb(ent: dict) -> tuple:
                """Normaliza color (0-255 tuple) do dxf_data para matplotlib (0-1)."""
                c = ent.get('color')
                if isinstance(c, (list, tuple)) and len(c) == 3:
                    r, g, b = c
                    # ACI 7 (white) armazenado como preto (0,0,0) → forçar branco
                    if r == 0 and g == 0 and b == 0:
                        return (0.9, 0.9, 0.9)
                    return (r / 255.0, g / 255.0, b / 255.0)
                return (0.55, 0.65, 0.80)   # fallback azul-acinzentado

            # ── Linhas ────────────────────────────────────────────────────────
            for line in self._dxf_data.get('lines', []):
                s, e = line.get('start'), line.get('end')
                if not s or not e:
                    continue
                if (min(s[0], e[0]) > vx1 or max(s[0], e[0]) < vx0 or
                        min(s[1], e[1]) > vy1 or max(s[1], e[1]) < vy0):
                    continue
                lw = max(0.4, min(1.5, (line.get('lineweight') or 25) / 40.0))
                ax.plot([s[0], e[0]], [s[1], e[1]],
                        color=_rgb(line), lw=lw, solid_capstyle='round')

            # ── Polilinhas ────────────────────────────────────────────────────
            for poly in self._dxf_data.get('polylines', []):
                pts_p = poly.get('points', [])
                if not pts_p:
                    continue
                pxs_p = [p[0] for p in pts_p]
                pys_p = [p[1] for p in pts_p]
                if (min(pxs_p) > vx1 or max(pxs_p) < vx0 or
                        min(pys_p) > vy1 or max(pys_p) < vy0):
                    continue
                lw = max(0.4, min(1.5, (poly.get('lineweight') or 25) / 40.0))
                ax.plot(pxs_p, pys_p, color=_rgb(poly), lw=lw)

            # ── Textos com cores reais + tamanho proporcional ─────────────────
            px_per_unit = width / view_w
            for txt in self._dxf_data.get('texts', []):
                tx, ty = txt.get('pos', [0, 0])
                if not (vx0 <= float(tx) <= vx1 and vy0 <= float(ty) <= vy1):
                    continue
                t = str(txt.get('text', '')).strip()
                if not t:
                    continue
                h_dxf = float(txt.get('height') or 10)
                # Converter altura DXF → pt matplotlib: 1pt = dpi/72 px
                fsz = max(5, min(12, h_dxf * px_per_unit / (dpi / 72)))
                ax.text(float(tx), float(ty), t,
                        color=_rgb(txt), fontsize=fsz,
                        ha='center', va='center', clip_on=True,
                        fontfamily='monospace')

            # ── Pilar destacado (facecolor semi-transparente + borda teal) ────
            poly_patch = MplPolygon(
                [(float(p[0]), float(p[1])) for p in pilar_pts],
                closed=True, fill=True,
                facecolor='#ff9800' if focus_mode == 'segment' else '#1e3a5f',
                edgecolor='#ff3d00' if focus_mode == 'segment' else '#4fc3a1',
                lw=3.5 if focus_mode == 'segment' else 2.0,
                alpha=0.42 if focus_mode == 'segment' else 0.85,
                zorder=10,
            )
            ax.add_patch(poly_patch)
            if focus_mode == 'segment':
                ax.scatter(
                    xs, ys, s=18, c='#fff176', edgecolors='#ff3d00',
                    linewidths=0.8, zorder=11,
                )
                ax.text(
                    min(xs), max(ys) + max(short_span * 0.35, 8.0),
                    'SEGMENTO FV', color='#ffcc80', fontsize=8,
                    ha='left', va='bottom', zorder=12,
                    bbox={
                        'facecolor': BG, 'edgecolor': '#ff3d00',
                        'alpha': 0.85,
                    },
                )

            buf = io.BytesIO()
            fig.savefig(buf, format=fmt, facecolor=BG, dpi=dpi)
            plt.close(fig)
            buf.seek(0)
            if fmt == 'svg':
                return _svg_strip_fixed_size(buf.read().decode('utf-8'))
            return base64.b64encode(buf.read()).decode('ascii')
        except Exception as exc:
            print(f'[HTML] _render_pilar_dxf_context_b64 falhou: {exc}', flush=True)
            return ''

    def materialize_pl_n3_variants(self) -> tuple[list[str], list[str]]:
        """N3 de pilares: **sempre** PARA e PASSA (sem escolha manual).

        Publica contratos + DXF em
        ``DADOS-OBRAS/<obra>/Fase-6_Execucao_CAD/n3_variants/{para|passa}/``.
        Usado pelo headless e por qualquer caller que precise das duas
        listas iguais ao Comparison Engine.

        Returns:
            (generated_labels, failed_labels) ex.: ``['P1_para', 'P1_passa']``
        """
        # Reset flag para forçar batch neste call (mesmo se export anterior
        # na mesma instância já tiver materializado).
        self._pl_n3_materialized_once = False
        self._pl_n3_cache = {}
        self._last_pl_n3_materialize = {'generated': [], 'failed': []}
        try:
            self._export_html_snapshot(sections={'pilares'})
        except Exception as exc:
            print(f'[HTML] materialize_pl_n3_variants falhou: {exc}', flush=True)
        stats = getattr(self, '_last_pl_n3_materialize', None) or {}
        return (
            list(stats.get('generated') or []),
            list(stats.get('failed') or []),
        )

    def _export_html_snapshot(self, sections: set[str] | None = None) -> str | None:
        """Gera uma ficha HTML independente para cada aba de dados.

        `sections`: `None` (default) gera tudo, comportamento idêntico ao
        anterior. Um subconjunto de `{'pilares', 'lajes', 'fundos_viga'}`
        pula a montagem e a escrita das seções fora do conjunto (perf —
        ver STORY-EXEC-02-FLAG-SECAO.md). `pilares_especiais` segue
        `pilares`; `visao_cortes` e as laterais (`laterais_viga`, não
        selecionável por este flag) só são geradas quando `sections` é
        `None`.

        Retorna o output_dir gerado (ou None em caso de erro)."""
        import html
        _include = lambda name: sections is None or name in sections  # noqa: E731
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
        _pillar_items = (
            sorted(self._pillar_report.items(), key=lambda kv: self._natural_sort_key(kv[0]))
            if _include('pilares') else []
        )
        for key, pillar in _pillar_items:
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
                '_key': key,
            }
            (pillar_rows if row['Formato'] == 'Retangular' else special_rows).append(row)

        pillar_headers = ['Nome', 'Classificação', 'Formato', 'Nível', 'Lado A', 'Lado B', 'Lado C', 'Lado D', 'Atenção']
        _pil_extra_th = (
            '<th>Foto N1 (SA)</th>'
            '<th>N3 Cima</th><th>N3 ABCD</th><th>N3 Grades</th>'
            '<th>Atenção N3</th>'
            '<th>N4 Cima</th><th>N4 ABCD</th><th>N4 Grades</th>'
            '<th>Atenção N4</th>'
            '<th>Foto N2</th>'
            '<th>Ficha N1 SA</th><th>Ficha N2</th><th>Ficha N3 (JSON)</th>'
        )

        def _pil_extra_td(row: dict) -> str:
            nome = row['_nome']
            pts  = row.get('_points') or []

            # ── Foto N1: contexto DXF estrutural + pilar destacado ────────────
            geo = self._render_pilar_dxf_context_b64(pts, width=910, height=650) if pts else ''
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

            # ── Atenção N3 (editável, persiste em localStorage) ───────────────
            _n3_at_key = f'aten_n3_{self._obra}_{self._pavimento}_{nome}'.replace(' ', '_')
            n3_aten_cell = (
                f'<td class="atencao-cell" contenteditable="true" '
                f'data-atkey="{_n3_at_key}" '
                f'onblur="saveAten(this)" '
                f'title="Anotação N3 — {nome}"></td>'
            )

            # ── N4: 3 vistas DXF N4 (CE via N2 — /n4/ subpasta, fallback raiz) ──
            def _n4_view_cell(view_type: str) -> str:
                p = self._find_pilar_dxf(view_type, nome, n4=True)
                b64 = self._render_ezdxf_b64(p, width=750, height=550) if p else ''
                return (_img_cell(b64, 'img-n4') if b64
                        else f'<td><span class="muted">sem N4 {view_type}</span></td>')

            n4_cima   = _n4_view_cell('CIMA')
            n4_abcd   = _n4_view_cell('ABCD')
            n4_grades = _n4_view_cell('GRADES')

            # ── Atenção N4 (editável, persiste em localStorage) ───────────────
            _n4_at_key = f'aten_n4_{self._obra}_{self._pavimento}_{nome}'.replace(' ', '_')
            n4_aten_cell = (
                f'<td class="atencao-cell" contenteditable="true" '
                f'data-atkey="{_n4_at_key}" '
                f'onblur="saveAten(this)" '
                f'title="Anotação N4 — {nome}"></td>'
            )

            # ── Foto N2: recorte DXF Fase-2 renderizado ───────────────────────
            n2b64 = self._render_n2_recorte_b64(nome)
            n2_foto_cell = (_img_cell(n2b64, 'img-n2') if n2b64
                            else '<td><span class="muted">sem recorte N2</span></td>')

            # ── Fichas informacionais ─────────────────────────────────────────
            n1_ficha = self._n1_ficha_html_pilar(nome)
            n2_ficha = self._n2_ficha_html('PIL', nome)
            n3_ficha = self._n3_ficha_html_pilar(nome)

            return (n1_cell
                    + n3_cima + n3_abcd + n3_grades + n3_aten_cell
                    + n4_cima + n4_abcd + n4_grades + n4_aten_cell
                    + n2_foto_cell
                    + f'<td class="ficha-cell">{n1_ficha}</td>'
                    + f'<td class="ficha-cell">{n2_ficha}</td>'
                    + f'<td class="ficha-cell">{n3_ficha}</td>')

        reports.append(('pilares', 'Pré-ficha — Pilares', pillar_headers, pillar_rows, _pil_extra_th, _pil_extra_td))
        reports.append(('pilares_especiais', 'Pré-ficha — Pilares Especiais', pillar_headers, special_rows, _pil_extra_th, _pil_extra_td))

        # ── Report: Visão de Cortes ──────────────────────────────────────────
        # Não é uma seção selecionável por `--secao`: só entra quando a rodada
        # é completa (sections is None), igual às laterais mais abaixo.
        cut_rows = []
        for cut in (self._cut_view_data if sections is None else []):
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

        # ── Report: Lajes ─────────────────────────────────────────────────────
        slab_rows: list[dict] = []
        _slab_items = (
            sorted(
                self._slabs or [],
                key=lambda s: self._natural_sort_key(
                    str(s.get('name') or s.get('laje_name') or '')
                ),
            )
            if _include('lajes') else []
        )
        for slab in _slab_items:
            nome_lj = str(
                slab.get('name')
                or slab.get('laje_name')
                or (slab.get('fields') or {}).get('nome')
                or '—'
            )
            pts_lj = _slab_outline_points(slab)
            slab_rows.append({
                'Nome':      nome_lj,
                'Nível':     self._slab_nivel_map.get(nome_lj) or '—',
                'Espessura': self._slab_height_map.get(nome_lj) or '—',
                'Atenção':   self._atencao_notes.get(nome_lj, ''),
                'Detalhes':  _slab_details_text(
                    slab,
                    height=self._slab_height_map.get(nome_lj, ''),
                    level=self._slab_nivel_map.get(nome_lj, ''),
                ),
                '_points':   pts_lj,
                '_slab':     slab,
                '_name':     nome_lj,
            })
        reports.append((
            'lajes', 'Pré-ficha — Lajes',
            ['Nome', 'Nível', 'Espessura', 'Atenção'],
            slab_rows, '', None,
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
            # 'fundo' -> seção 'fundos_viga' (selecionável); as 4 laterais não
            # são selecionáveis por --secao, só entram na rodada completa.
            if kind == 'fundo':
                if not _include('fundos_viga'):
                    continue
            elif sections is not None and not _include('laterais_viga'):
                continue
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
                    '_segment': segment,
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
            '.img-geo{width:910px;height:650px;object-fit:contain;background:#111}'
            '.img-n3{width:900px;height:600px;object-fit:contain;background:#fff}'
            '.img-n4{width:750px;height:550px;object-fit:contain;background:#fff}'
            '.img-n2{width:600px;height:400px;object-fit:contain;background:#111}'
            '.ficha-cell{max-width:380px;overflow:auto}'
            'tr:hover td{background:#222}'
            '.atencao-cell{'
            '  min-width:220px;max-width:320px;min-height:50px;'
            '  background:#1e1b00;color:#f0b840;cursor:text;'
            '  border-left:2px solid #5a4400;white-space:pre-wrap;'
            '  font-size:10px;padding:4px 6px'
            '}'
            '.atencao-cell:focus{'
            '  outline:1px solid #f0b840;background:#252300'
            '}'
            '.atencao-cell:empty::before{'
            '  content:attr(title);color:#554400;font-style:italic'
            '}'
        )

        js = (
            '<script>'
            'function saveAten(el){'
            '  var key=el.dataset.atkey;if(!key)return;'
            '  var val=el.innerText.trim();'
            '  if(val){localStorage.setItem(key,val);}else{localStorage.removeItem(key);}'
            '}'
            'function loadAllAten(){'
            '  document.querySelectorAll("[data-atkey]").forEach(function(el){'
            '    var stored=localStorage.getItem(el.dataset.atkey);'
            '    if(stored!==null&&stored!=="")el.innerText=stored;'
            '  });'
            '}'
            'document.addEventListener("DOMContentLoaded",loadAllAten);'
            # Exporta todas as anotações como JSON para Playwright/Claude ler
            'function exportAnotacoes(){'
            '  var r={};'
            '  for(var i=0;i<localStorage.length;i++){'
            '    var k=localStorage.key(i);'
            '    if(k&&(k.startsWith("aten_")||k.startsWith("val_")))r[k]=localStorage.getItem(k);'
            '  }'
            '  var el=document.getElementById("_aten_export");'
            '  if(el)el.textContent=JSON.stringify(r,null,2);'
            '}'
            'function toggleValidacao(cb){'
            '  var row=cb.closest(".valid-row")||cb.closest(".mode-row");'
            '  if(!row)return;'
            '  var lbl=row.querySelector(".valid-lbl");'
            '  if(cb.checked){row.classList.add("approved");if(lbl)lbl.textContent="Aprovado ✓";}'
            '  else{row.classList.remove("approved");if(lbl)lbl.textContent="Aprovado";}'
            '  if(cb.dataset.cbkey)localStorage.setItem(cb.dataset.cbkey,cb.checked?"1":"0");'
            '}'
            'function loadAllValidacoes(){'
            '  document.querySelectorAll(".validacao-cb[data-cbkey]").forEach(function(cb){'
            '    if(localStorage.getItem(cb.dataset.cbkey)==="1"){'
            '      cb.checked=true;toggleValidacao(cb);'
            '    }'
            '  });'
            '}'
            'document.addEventListener("DOMContentLoaded",loadAllValidacoes);'
            '</script>'
        )

        def _render_td(h: str, row: dict, slug: str) -> str:
            val = str(row.get(h, ''))
            if h == 'Atenção':
                row_key = (row.get('_nome') or str(row.get('Nome') or
                           row.get('Viga') or row.get('Segmento') or '')).replace(' ', '_')
                at_key  = f'aten_{slug}_{row_key}'
                return (
                    f'<td class="atencao-cell" contenteditable="true" '
                    f'data-atkey="{html.escape(at_key)}" '
                    f'data-sa="{html.escape(val)}" '
                    f'onblur="saveAten(this)" '
                    f'title="Anotação — clique para editar">'
                    f'{html.escape(val)}</td>'
                )
            return f'<td>{html.escape(val)}</td>'

        # ── CSS adicional para layout sidebar (páginas individuais de pilar) ──
        import re as _re

        _layout_css = (
            'body{display:flex;flex-direction:row;margin:0;overflow:hidden;height:100vh}'
            '.sidebar{width:170px;min-width:130px;overflow-y:auto;background:#111;'
            '  border-right:1px solid #2a2a2a;padding:6px 0;flex-shrink:0;height:100vh}'
            '.sidebar h3{color:#4fc3a1;font-size:10px;padding:4px 8px;margin:0 0 4px;'
            '  border-bottom:1px solid #222}'
            '.sidebar ul{list-style:none;padding:0;margin:0}'
            '.sidebar li a{display:block;padding:3px 8px;color:#888;text-decoration:none;'
            '  font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
            '.sidebar li.active a{color:#f0b840;background:#1e1b00;font-weight:bold}'
            '.sidebar li a:hover{background:#1a1a1a;color:#ccc}'
            '.sidebar .grp{font-size:8px;color:#4fc3a1;padding:8px 6px 2px;'
            '  border-top:1px solid #222;text-transform:uppercase;letter-spacing:1px}'
            '.main-wrap{flex:1;overflow:auto;height:100vh}'
            '.main-content{padding:12px 16px;min-width:800px}'
            '.nav-bar{display:flex;align-items:center;gap:10px;margin-bottom:10px;'
            '  background:#1e1e1e;padding:5px 10px;border-radius:4px;'
            '  position:sticky;top:0;z-index:5}'
            '.nav-arrow{color:#7eb8f7;text-decoration:none;font-size:10px;padding:2px 8px;'
            '  border:1px solid #335;border-radius:3px;white-space:nowrap}'
            '.nav-arrow:hover{background:#1a2030}'
            '.nav-pos{color:#aaa;font-size:10px;flex:1;text-align:center}'
            '.sec{margin:8px 0;border:1px solid #2a2a2a;border-radius:4px}'
            '.sec-title{background:#1e1e1e;color:#4fc3a1;padding:3px 8px;'
            '  font-size:10px;font-weight:bold;border-radius:4px 4px 0 0}'
            '.sec-body{padding:8px}'
            '.face-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:6px}'
            '.face-card{border-radius:3px;padding:5px 7px;font-size:10px}'
            '.face-A{background:#122012;border-left:3px solid #4fc3a1}'
            '.face-B{background:#12122a;border-left:3px solid #7eb8f7}'
            '.face-C{background:#2a1228;border-left:3px solid #c47ef7}'
            '.face-D{background:#2a1e10;border-left:3px solid #f0b840}'
            '.face-label{color:#666;font-size:9px;margin-bottom:2px}'
            '.valid-grid{display:grid;grid-template-columns:repeat(2,minmax(260px,1fr));gap:8px}'
            '.valid-card{background:#101010;border:1px solid #292929;border-radius:4px;overflow:hidden}'
            '.valid-card-title{padding:5px 8px;font-weight:bold;font-size:10px;background:#171717}'
            '.valid-card-title.face-A{color:#4fc3a1}.valid-card-title.face-B{color:#7eb8f7}'
            '.valid-card-title.face-C{color:#c47ef7}.valid-card-title.face-D{color:#f0b840}'
            '.valid-row,.mode-row{display:flex;align-items:flex-start;gap:7px;padding:6px 8px;'
            '  border-top:1px solid #1d1d1d;background:#0d0d0d}'
            '.valid-row.approved,.mode-row.approved{background:#0b180b}'
            '.validacao-cb{width:14px;height:14px;margin-top:2px;accent-color:#4fc3a1;cursor:pointer;flex-shrink:0}'
            '.valid-lbl{font-size:9px;color:#4a4a4a;min-width:28px;margin-top:2px;flex-shrink:0}'
            '.approved .valid-lbl{color:#4fc3a1}'
            '.valid-badge{display:inline-block;padding:2px 7px;border-radius:2px;font-size:10px;'
            '  font-weight:bold;border-left:2px solid;white-space:nowrap;flex-shrink:0}'
            '.vb-sa{background:#102010;color:#4fc3a1;border-color:#4fc3a1}'
            '.vb-passa{background:#0e1828;color:#7eb8f7;border-color:#7eb8f7}'
            '.vb-para{background:#20140a;color:#f0b840;border-color:#f0b840}'
            '.vb-grade{background:#1a0a20;color:#d47ef7;border-color:#d47ef7}'
            '.vb-cima{background:#1b1b1b;color:#aaa;border-color:#777}'
            '.valid-detail{font-size:10px;color:#888;line-height:1.55;white-space:pre-wrap;flex:1}'
            '.valid-detail .muted{color:#4d4d4d}.valid-detail b{color:#ccc}'
            '.mode-grid{display:grid;grid-template-columns:repeat(2,minmax(320px,1fr));gap:8px}'
            '.mode-card{background:#101010;border:1px solid #2a2a2a;border-radius:4px;overflow:hidden}'
            '.mode-title{padding:5px 8px;font-size:10px;font-weight:bold;background:#171717;color:#7eb8f7}'
            '.mode-title.para{color:#f0b840}.mode-title.passa{color:#7eb8f7}.mode-title.cima{color:#aaa}'
            '.mode-note{font-size:10px;color:#666;padding:5px 8px;border-top:1px solid #1d1d1d;line-height:1.5}'
            '.field-table{width:100%;border-collapse:collapse;font-size:9px;margin-top:5px}'
            '.field-table td{border-top:1px solid #1a1a1a;padding:2px 5px;vertical-align:top}'
            '.field-table td:first-child{color:#666;white-space:nowrap;width:86px}'
            '.od-wrap{margin:6px 0 10px 0;display:flex;flex-direction:column;align-items:center;gap:0px;font-size:9px;font-family:monospace}'
            '.od-row{display:flex;align-items:center;justify-content:center;gap:0}'
            '.od-box{border:2px solid #555;background:#1e1e1e;color:#ddd;padding:6px 18px;'
            '  text-align:center;font-size:9px;font-weight:bold;min-width:70px;'
            '  border-radius:2px}'
            '.od-top{color:#c47ef7;font-weight:bold;padding:2px 0;text-align:center}'
            '.od-bot{color:#f0b840;font-weight:bold;padding:2px 0;text-align:center}'
            '.od-side-A{color:#4fc3a1;font-weight:bold;padding:4px 6px}'
            '.od-side-B{color:#7eb8f7;font-weight:bold;padding:4px 6px}'
            '.od-side-C{color:#c47ef7;font-weight:bold;padding:4px 6px}'
            '.od-side-D{color:#f0b840;font-weight:bold;padding:4px 6px}'
            '.od-hint{color:#555;font-size:8px;text-align:center;margin-top:2px}'
            '.face-val{white-space:pre-wrap;color:#ccc}'
            '.img-wrap{text-align:center;background:#0d0d0d;padding:6px;border-radius:3px}'
            '.views-row{display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start}'
            '.view-block{text-align:center}'
            '.view-label{font-size:9px;color:#666;margin-bottom:3px}'
            '.fichas-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}'
            '.ficha-col-title{color:#7eb8f7;font-size:10px;margin-bottom:4px;font-weight:bold}'
            '.evidence-grid{display:grid;grid-template-columns:1fr;gap:18px}'
            '.evidence-card{background:#101010;border:1px solid #292929;border-radius:3px;padding:6px}'
            '.evidence-card img,.evidence-card svg{display:block;width:100%;height:auto;max-height:none;object-fit:contain;background:#111}'
            '.img-wrap img,.img-wrap svg{display:block;width:100%;height:auto;max-height:none;object-fit:contain}'
            '.views-row{display:flex;flex-direction:column;gap:18px;align-items:stretch}'
            '.view-block{width:100%;text-align:center}'
            '.view-block img{display:block;width:100%;height:auto;max-height:none;object-fit:contain}'
            '.evidence-title{display:flex;justify-content:space-between;color:#aaa;font-size:9px;margin-bottom:4px}'
            '.artifact-path{color:#555;font-size:8px;word-break:break-all;margin-top:4px}'
            '.pipeline-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}'
            '.pipeline-stage{background:#111;border:1px solid #292929;border-radius:3px;padding:7px}'
            '.pipeline-stage.ok{border-left:3px solid #4fc3a1}'
            '.pipeline-stage.missing{border-left:3px solid #e17055}'
            '.stage-name{color:#7eb8f7;font-weight:bold;font-size:10px}'
            '.stage-state{font-size:9px;color:#888;margin:2px 0 5px}'
            '.vertex-table{max-height:260px;overflow:auto}'
            '.vertex-table table{font-size:9px}'
            '.tag{display:inline-block;background:#282828;color:#888;'
            '  font-size:8px;padding:1px 5px;border-radius:3px;margin-left:5px}'
        )
        _page_css = css + _layout_css

        def _classif_slug(c: str) -> str:
            return _re.sub(r'[^A-Za-z0-9]', '_', (c or 'OUTROS').strip().upper()) or 'OUTROS'

        def _write_pilar_pages(slug: str, title: str, rows: list) -> tuple:
            """Gera uma página HTML por pilar com sidebar + prev/next."""
            # nav_entries: [(nome, classif, classif_slug, abs_path)]
            nav_entries = []
            for row in rows:
                nome    = row['_nome']
                classif = row.get('Classificação') or 'INDETERMINADO'
                cs      = _classif_slug(classif)
                abs_p   = os.path.join(output_dir, slug, cs, f'{nome}.html')
                nav_entries.append((nome, classif, cs, abs_p))

            for _, _, _, abs_p in nav_entries:
                os.makedirs(os.path.dirname(abs_p), exist_ok=True)

            FACE_CLSS = {'A': 'face-A', 'B': 'face-B', 'C': 'face-C', 'D': 'face-D'}

            # Labels e diagrama ASCII por orientação
            _VERT_LBLS = {
                'A': 'A — esquerda (oeste) · face longa',
                'B': 'B — direita (leste) · face longa',
                'C': 'C — topo (norte) · face curta',
                'D': 'D — base (sul) · face curta',
            }
            _HORIZ_LBLS = {
                'A': 'A — base (sul) · face longa',
                'B': 'B — topo (norte) · face longa',
                'C': 'C — esquerda (oeste) · face curta',
                'D': 'D — direita (leste) · face curta',
            }

            def _orient_diagram(pts: list, nome: str, fmt: str) -> str:
                """Diagrama HTML mostrando posição de A/B/C/D para este pilar."""
                # Detectar orientação pela bbox
                is_vert = True
                if pts:
                    try:
                        xs = [float(p[0]) for p in pts]
                        ys = [float(p[1]) for p in pts]
                        pw = max(xs) - min(xs)
                        ph = max(ys) - min(ys)
                        is_vert = ph > pw
                    except Exception:
                        pass
                if is_vert:
                    # VERTICAL: C=norte, D=sul, A=oeste, B=leste
                    return (
                        '<div class="od-wrap">'
                        '<div class="od-top">C — topo / norte</div>'
                        '<div class="od-row">'
                        '<span class="od-side-A">A — oeste</span>'
                        f'<div class="od-box">{html.escape(nome)}</div>'
                        '<span class="od-side-B">B — leste</span>'
                        '</div>'
                        '<div class="od-bot">D — base / sul</div>'
                        '<div class="od-hint">VERTICAL · C e D = faces curtas · A e B = faces longas</div>'
                        '</div>'
                    )
                else:
                    # HORIZONTAL: B=norte, A=sul, C=oeste, D=leste
                    return (
                        '<div class="od-wrap">'
                        '<div class="od-top">B — topo / norte</div>'
                        '<div class="od-row">'
                        '<span class="od-side-C">C — oeste</span>'
                        f'<div class="od-box">{html.escape(nome)}</div>'
                        '<span class="od-side-D">D — leste</span>'
                        '</div>'
                        '<div class="od-bot">A — base / sul</div>'
                        '<div class="od-hint">HORIZONTAL · A e B = faces longas · C e D = faces curtas</div>'
                        '</div>'
                    )

            def _fmt_num(v) -> str:
                try:
                    fv = float(v)
                    return str(int(fv)) if abs(fv - int(fv)) < 1e-6 else f'{fv:.1f}'
                except Exception:
                    return str(v) if v not in (None, '') else '—'

            def _pillar_dims(pts: list) -> tuple[float, float]:
                if not pts:
                    return 0.0, 0.0
                try:
                    xs = [float(p[0]) for p in pts]
                    ys = [float(p[1]) for p in pts]
                    w, h = max(xs) - min(xs), max(ys) - min(ys)
                    return max(w, h), min(w, h)
                except Exception:
                    return 0.0, 0.0

            def _face_len(face_id: str, comp: float, larg: float) -> float:
                return comp if face_id in ('A', 'B') else larg

            def _face_kind(cell_text: str) -> str:
                t = (cell_text or '').strip().lower()
                if not t or t == 'nulo':
                    return 'NULO'
                if 'viga:' in t:
                    return 'VIGA'
                if 'laje:' in t:
                    return 'LAJE'
                return 'MISTO'

            def _entries_for_side(pillar: dict, side: str) -> list[dict]:
                return [e for e in (pillar.get('lajes') or []) if e.get('side') == side]

            def _entry_laje_detail(e: dict) -> str:
                ln = e.get('laje') or '?'
                h = self._slab_height_map.get(ln) or ''
                nv = self._slab_nivel_map.get(ln) or ''
                bits = [f'Laje: {ln}']
                if h:
                    bits.append(f'esp: {h}cm')
                if nv:
                    bits.append(f'N: {nv}')
                src = e.get('side_source') or e.get('source') or ''
                if src:
                    bits.append(f'fonte: {src}')
                return '  ·  '.join(bits)

            def _entry_viga_detail(e: dict) -> str:
                vg = e.get('viga') or {}
                if not vg:
                    return ''
                bits = [f'Viga: {vg.get("name", "?")}']
                if vg.get('dim'):
                    bits.append(f'dim: {vg.get("dim")}')
                if vg.get('nivel') or vg.get('n'):
                    bits.append(f'N: {vg.get("nivel") or vg.get("n")}')
                src = e.get('side_source') or e.get('source') or ''
                if src:
                    bits.append(f'fonte: {src}')
                return '  ·  '.join(bits)

            def _interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
                return max(0.0, min(max(a0, a1), max(b0, b1)) - max(min(a0, a1), min(b0, b1)))

            def _interval_gap(a0: float, a1: float, b0: float, b1: float) -> float:
                if max(a0, a1) < min(b0, b1):
                    return min(b0, b1) - max(a0, a1)
                if max(b0, b1) < min(a0, a1):
                    return min(a0, a1) - max(b0, b1)
                return 0.0

            def _as_point(obj) -> tuple[float, float] | None:
                if isinstance(obj, (list, tuple)) and len(obj) >= 2:
                    try:
                        return float(obj[0]), float(obj[1])
                    except Exception:
                        return None
                return None

            def _segment_bbox(points: list) -> tuple[float, float, float, float] | None:
                pts = [_as_point(p) for p in (points or [])]
                pts = [p for p in pts if p is not None]
                if len(pts) < 2:
                    return None
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                if max(x1 - x0, y1 - y0) < 5.0:
                    return None
                return x0, y0, x1, y1

            def _beam_segment_bboxes(beam: dict) -> list[tuple[str, tuple[float, float, float, float]]]:
                out: list[tuple[str, tuple[float, float, float, float]]] = []

                def _scan(label: str, obj, depth: int = 0) -> None:
                    if depth > 4:
                        return
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k in ('texts', 'dimension_texts', 'links', 'fields'):
                                continue
                            if k.startswith('seg') or 'seg_' in k or k in ('classified', 'geometry'):
                                _scan(k, v, depth + 1)
                        return
                    if not isinstance(obj, list):
                        return
                    bb = _segment_bbox(obj)
                    if bb:
                        out.append((label, bb))
                        return
                    for item in obj:
                        _scan(label, item, depth + 1)

                _scan('geometry', (beam.get('geometry') or {}).get('classified') or {})
                for key in ('seg_a', 'seg_b', 'seg_c', 'seg_bottom'):
                    if key in beam:
                        _scan(key, beam.get(key))

                dedup: list[tuple[str, tuple[float, float, float, float]]] = []
                seen: set[tuple] = set()
                for label, bb in out:
                    sig = (label,) + tuple(round(v, 2) for v in bb)
                    if sig in seen:
                        continue
                    seen.add(sig)
                    dedup.append((label, bb))
                return dedup

            def _beam_dim_near(beam: dict, bb: tuple[float, float, float, float] | None = None) -> str:
                if beam.get('lv_dimension_override'):
                    return str(beam.get('lv_dimension_override'))
                candidates: list[tuple[float, str]] = []
                cx = cy = None
                if bb:
                    cx = (bb[0] + bb[2]) / 2.0
                    cy = (bb[1] + bb[3]) / 2.0
                for txt in (beam.get('texts') or []):
                    raw = str(txt.get('text') or '').strip()
                    if not re.match(r'^\d+(?:[.,]\d+)?\s*/\s*\d+(?:[.,]\d+)?$', raw):
                        continue
                    pos = txt.get('pos') or []
                    dist = 0.0
                    if cx is not None and len(pos) >= 2:
                        try:
                            dist = math.hypot(float(pos[0]) - cx, float(pos[1]) - cy)
                        except Exception:
                            dist = 0.0
                    candidates.append((dist, raw.replace(' ', '')))
                if candidates:
                    return sorted(candidates, key=lambda x: x[0])[0][1]
                dim_txt = ((beam.get('geometry') or {}).get('lv_dimension_text') or {}).get('text')
                return str(dim_txt or '')

            def _beam_local_name(beam: dict, bb: tuple[float, float, float, float] | None) -> str:
                if not bb:
                    return ''
                cx = (bb[0] + bb[2]) / 2.0
                cy = (bb[1] + bb[3]) / 2.0
                candidates: list[tuple[float, str]] = []
                beam_name_re = re.compile(r'^(?:V|VF|F\.|LV|L\.)\s*[A-Z]?\d+', re.IGNORECASE)

                def _norm(raw: str) -> str:
                    s = raw.strip().replace(' ', '')
                    m = re.match(r'^F\.(.+?)(?:\.C)?(?:-\d+)?$', s, re.IGNORECASE)
                    if m:
                        return 'VF' + re.sub(r'[^A-Za-z0-9]', '', m.group(1))
                    m = re.match(r'^L\.(.+?)(?:\.[AB])?(?:-\d+)?$', s, re.IGNORECASE)
                    if m:
                        return 'LV' + re.sub(r'[^A-Za-z0-9]', '', m.group(1))
                    return s.upper()

                for txt in list(self._beam_texts or []) + list(beam.get('texts') or []):
                    raw = str(txt.get('text') or '').strip()
                    if not beam_name_re.match(raw):
                        continue
                    pos = txt.get('pos') or []
                    if len(pos) < 2:
                        continue
                    try:
                        dist = math.hypot(float(pos[0]) - cx, float(pos[1]) - cy)
                    except Exception:
                        continue
                    if dist <= 220.0:
                        candidates.append((dist, _norm(raw)))
                if not candidates:
                    return ''
                return sorted(candidates, key=lambda x: x[0])[0][1]

            def _beam_detail(beam: dict, bb: tuple[float, float, float, float] | None, note: str) -> str:
                local_name = _beam_local_name(beam, bb)
                if not local_name:
                    return ''
                # Sufixos A/B de lateral são identificadores internos do trecho,
                # não outra viga estrutural (V309A -> V309; VF301B -> VF301).
                local_name = re.sub(r'(?<=\d)[AB]$', '', local_name, flags=re.IGNORECASE)
                bits = [f'Viga: {local_name}']
                dim = _beam_dim_near(beam, bb)
                if dim:
                    bits.append(f'dim: {dim}')
                bits.append(note)
                return '  ·  '.join(bits)

            def _dynamic_face_interpretation(row: dict, pillar: dict) -> dict[str, dict[str, list[str]]]:
                pts = row.get('_points') or pillar.get('points') or []
                if not pts:
                    return {
                        fid: {'lajes': [], 'passa': [], 'chega': [], 'interior': []}
                        for fid in ('A', 'B', 'C', 'D')
                    }
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                px0, px1 = min(xs), max(xs)
                py0, py1 = min(ys), max(ys)
                pw, ph = px1 - px0, py1 - py0
                vertical_pillar = ph > pw
                face_len = {'A': ph, 'B': ph, 'C': pw, 'D': pw} if vertical_pillar else {'A': pw, 'B': pw, 'C': ph, 'D': ph}
                tol = max(6.0, min(max(pw, ph) * 0.12, 18.0))
                influence = max(160.0, max(pw, ph) * 2.2)
                result = {
                    fid: {'lajes': [], 'passa': [], 'chega': [], 'interior': []}
                    for fid in ('A', 'B', 'C', 'D')
                }

                for fid in ('A', 'B', 'C', 'D'):
                    entries = _entries_for_side(pillar, fid)
                    lajes = [
                        _entry_laje_detail(e) for e in entries
                        if (e.get('content_type') or 'laje') in ('laje', 'both') and e.get('laje')
                    ]
                    result[fid]['lajes'].extend(lajes)

                def _add(fid: str, kind: str, text: str) -> None:
                    if not text:
                        return
                    m = re.match(r'^Viga:\s*([^·]+)', text)
                    if m:
                        name = m.group(1).strip()
                        if any(existing.startswith(f'Viga: {name}  ') or existing == f'Viga: {name}' for existing in result[fid][kind]):
                            return
                    if text not in result[fid][kind]:
                        result[fid][kind].append(text)

                def _seg_bbox(seg: dict) -> tuple[float, float, float, float] | None:
                    pts = [_as_point(p) for p in (seg.get('points') or [])]
                    pts = [p for p in pts if p is not None]
                    if len(pts) < 2:
                        return None
                    xs_ = [p[0] for p in pts]
                    ys_ = [p[1] for p in pts]
                    return min(xs_), min(ys_), max(xs_), max(ys_)

                def _seg_width_completa(seg: dict) -> str:
                    """Retorna a seção do trecho lateral, nunca só a espessura do fundo.

                    O fundo de uma viga costuma guardar somente a largura (ex.: 19),
                    enquanto os segmentos laterais do mesmo trecho carregam a seção
                    completa (19/120). A ficha deve exibir esta última.
                    """
                    width = str(seg.get('width') or '').strip()
                    if '/' in width:
                        return width
                    beam_name = str(seg.get('beam_name') or '').strip()
                    own_bb = _seg_bbox(seg)
                    if not beam_name or not own_bb:
                        return width
                    ox0, oy0, ox1, oy1 = own_bb
                    alternatives = []
                    for sibling_group in (getattr(self, '_segment_data', {}) or {}).values():
                        for sibling in sibling_group or []:
                            if str(sibling.get('beam_name') or '').strip() != beam_name:
                                continue
                            sibling_width = str(sibling.get('width') or '').strip()
                            if '/' not in sibling_width:
                                continue
                            sibling_bb = _seg_bbox(sibling)
                            if not sibling_bb:
                                continue
                            sx0, sy0, sx1, sy1 = sibling_bb
                            # O menor afastamento entre as caixas identifica o lateral
                            # correspondente ao mesmo fundo, inclusive quando a lateral
                            # é uma linha (largura/altura zero).
                            distance = (
                                _interval_gap(ox0, ox1, sx0, sx1) +
                                _interval_gap(oy0, oy1, sy0, sy1)
                            )
                            alternatives.append((distance, sibling_width))
                    return min(alternatives)[1] if alternatives else width

                def _seg_detail(seg: dict, note: str) -> str:
                    name = str(seg.get('beam_name') or '').strip()
                    if not name:
                        name = 'SEM_NOME'
                    name = re.sub(r'(?<=\d)[AB]$', '', name, flags=re.IGNORECASE)
                    bits = [f'Viga: {name}']
                    width = _seg_width_completa(seg)
                    if width:
                        bits.append(f'dim: {width}')
                    bits.append(note)
                    return '  ·  '.join(bits)

                # Fonte preferencial para nome de viga: segmentos já consolidados
                # para FV/LV. Eles carregam beam_name por trecho; texto próximo fica
                # apenas como fallback bruto mais abaixo.
                segment_groups = getattr(self, '_segment_data', {}) or {}
                for group_name in (
                    'lateral_a_passa', 'lateral_b_passa',
                    'fundo',
                ):
                    for seg in segment_groups.get(group_name, []) or []:
                        bb = _seg_bbox(seg)
                        if not bb:
                            continue
                        bx0, by0, bx1, by1 = bb
                        bw, bh = bx1 - bx0, by1 - by0
                        is_vert_seg = bh >= max(10.0, bw * 3.0)
                        is_horiz_seg = bw >= max(10.0, bh * 3.0)

                        if vertical_pillar:
                            if is_vert_seg:
                                gap_y = _interval_gap(by0, by1, py0, py1)
                                if gap_y <= tol:
                                    touches_a = min(abs(bx0 - px0), abs(bx1 - px0)) <= tol or (bx0 <= px0 <= bx1)
                                    touches_b = min(abs(bx0 - px1), abs(bx1 - px1)) <= tol or (bx0 <= px1 <= bx1)
                                    overlaps_width = _interval_overlap(bx0, bx1, px0, px1) >= max(1.0, min(pw * 0.45, tol))
                                    if touches_a:
                                        _add('A', 'passa', _seg_detail(seg, 'corre ao longo da face A'))
                                    if touches_b:
                                        _add('B', 'passa', _seg_detail(seg, 'corre ao longo da face B'))
                                    # Se o mesmo trecho vertical toca o pilar e continua
                                    # para fora pelo eixo, a face curta vira interior.
                                    if (touches_a or touches_b or overlaps_width) and by1 >= py1 + tol:
                                        _add('C', 'interior', _seg_detail(seg, 'face C é limite interno; viga continua no eixo do pilar'))
                                    if (touches_a or touches_b or overlaps_width) and by0 <= py0 - tol:
                                        _add('D', 'interior', _seg_detail(seg, 'face D é limite interno; viga continua no eixo do pilar'))
                            if is_horiz_seg:
                                gap_x = _interval_gap(bx0, bx1, px0, px1)
                                if gap_x <= tol:
                                    if min(abs(by0 - py1), abs(by1 - py1)) <= tol or (by0 <= py1 <= by1):
                                        _add('C', 'passa', _seg_detail(seg, 'corre ao longo da face C'))
                                    if min(abs(by0 - py0), abs(by1 - py0)) <= tol or (by0 <= py0 <= by1):
                                        _add('D', 'passa', _seg_detail(seg, 'corre ao longo da face D'))
                                # Viga perpendicular chegando/atravessando a faixa do
                                # pilar: para faces longas A/B, registrar chegada sem
                                # inventar nome por texto local.
                                gap_y = _interval_gap(by0, by1, py0, py1)
                                if gap_y <= influence and _interval_overlap(bx0, bx1, px0, px1) > 0:
                                    _add('A', 'chega', _seg_detail(seg, 'chega perpendicularmente na face A'))
                                    _add('B', 'chega', _seg_detail(seg, 'chega perpendicularmente na face B'))
                                elif gap_y <= influence:
                                    if min(abs(bx0 - px0), abs(bx1 - px0)) <= tol and min(bx0, bx1) < px0 - tol:
                                        _add('A', 'chega', _seg_detail(seg, 'chega perpendicularmente na face A'))
                                    if min(abs(bx0 - px1), abs(bx1 - px1)) <= tol and max(bx0, bx1) > px1 + tol:
                                        _add('B', 'chega', _seg_detail(seg, 'chega perpendicularmente na face B'))
                        else:
                            if is_horiz_seg:
                                gap_x = _interval_gap(bx0, bx1, px0, px1)
                                if gap_x <= tol:
                                    touches_a = min(abs(by0 - py0), abs(by1 - py0)) <= tol or (by0 <= py0 <= by1)
                                    touches_b = min(abs(by0 - py1), abs(by1 - py1)) <= tol or (by0 <= py1 <= by1)
                                    overlaps_height = _interval_overlap(by0, by1, py0, py1) >= max(1.0, min(ph * 0.45, tol))
                                    if touches_a:
                                        _add('A', 'passa', _seg_detail(seg, 'corre ao longo da face A'))
                                    if touches_b:
                                        _add('B', 'passa', _seg_detail(seg, 'corre ao longo da face B'))
                                    if (touches_a or touches_b or overlaps_height) and bx0 <= px0 - tol:
                                        _add('C', 'interior', _seg_detail(seg, 'face C é limite interno; viga continua no eixo do pilar'))
                                    if (touches_a or touches_b or overlaps_height) and bx1 >= px1 + tol:
                                        _add('D', 'interior', _seg_detail(seg, 'face D é limite interno; viga continua no eixo do pilar'))
                            if is_vert_seg:
                                gap_y = _interval_gap(by0, by1, py0, py1)
                                if gap_y <= tol:
                                    if min(abs(bx0 - px0), abs(bx1 - px0)) <= tol or (bx0 <= px0 <= bx1):
                                        _add('C', 'passa', _seg_detail(seg, 'corre ao longo da face C'))
                                    if min(abs(bx0 - px1), abs(bx1 - px1)) <= tol or (bx0 <= px1 <= bx1):
                                        _add('D', 'passa', _seg_detail(seg, 'corre ao longo da face D'))

                def _retag_viga_detail(text: str, note: str) -> str:
                    m = re.match(r'^Viga:\s*([^·]+?)(?:\s*·\s*dim:\s*([^·]+?))?(?:\s*·|$)', text)
                    if not m:
                        return text
                    bits = [f'Viga: {m.group(1).strip()}']
                    if m.group(2):
                        bits.append(f'dim: {m.group(2).strip()}')
                    bits.append(note)
                    return '  ·  '.join(bits)

                def _viga_name_from_detail(text: str) -> str:
                    """Nome normalizado da viga exibida na ficha.

                    A mesma viga pode ter trechos de fundo e laterais na coleta de
                    segmentos. Para as duas faces longas, só é uma continuação do
                    pilar quando o vínculo aparece coerentemente nos dois lados.
                    """
                    if not text.startswith('Viga:'):
                        return ''
                    return re.sub(
                        r'(?<=\d)[AB]$', '', text[5:].split('  ·', 1)[0].strip(), flags=re.IGNORECASE
                    )

                # Um fundo de viga pode produzir laterais auxiliares encostadas em A
                # e C/D. Não são duas vigas que "passam" pela face A. Quando há
                # candidatos concorrentes nas faces longas, preservar somente a
                # continuidade que a própria geometria confirma também na face oposta.
                # A regra é geométrica e vale para qualquer pilar, não para P1.
                shared_long_faces: set[str] = set()
                shared_long_arrivals: set[str] = set()
                if vertical_pillar:
                    a_names = {_viga_name_from_detail(x) for x in result['A']['passa']}
                    b_names = {_viga_name_from_detail(x) for x in result['B']['passa']}
                    shared_long_faces = (a_names & b_names) - {''}
                    if shared_long_faces:
                        if len(result['A']['passa']) > 1:
                            result['A']['passa'] = [
                                x for x in result['A']['passa']
                                if _viga_name_from_detail(x) in shared_long_faces
                            ]
                        if len(result['B']['passa']) > 1:
                            result['B']['passa'] = [
                                x for x in result['B']['passa']
                                if _viga_name_from_detail(x) in shared_long_faces
                            ]
                        # Interior não é uma lista de todas as laterais que tocam a
                        # face curta: representa a viga que efetivamente continua no
                        # eixo do pilar. Mantém o mesmo vínculo A↔B quando há excesso.
                        for face_id in ('C', 'D'):
                            if len(result[face_id]['interior']) > 1:
                                result[face_id]['interior'] = [
                                    x for x in result[face_id]['interior']
                                    if _viga_name_from_detail(x) in shared_long_faces
                                ]
                    a_arrivals = {_viga_name_from_detail(x) for x in result['A']['chega']}
                    b_arrivals = {_viga_name_from_detail(x) for x in result['B']['chega']}
                    shared_long_arrivals = (a_arrivals & b_arrivals) - {''}

                # Em pilares verticais seriados (P2/P3...), a face C pode depender
                # dos vínculos SIMÉTRICOS de A↔B: uma viga passa no eixo do pilar e
                # outra cruza perpendicularmente. Não usar uma chegada isolada de
                # A ou B; ela não prova que exista uma segunda viga em C (caso P1).
                if vertical_pillar and not result['C']['passa']:
                    seen_c_sources: set[str] = set()
                    for source in result['A']['passa'] + result['A']['chega']:
                        source_name = _viga_name_from_detail(source)
                        if (
                            source_name in (shared_long_faces | shared_long_arrivals)
                            and source_name not in seen_c_sources
                        ):
                            seen_c_sources.add(source_name)
                            _add(
                                'C',
                                'passa',
                                _retag_viga_detail(source, 'vínculo simétrico A↔B para validação da face C'),
                            )

                for beam in self._beams:
                    bname = str(beam.get('name') or '')
                    if not bname or bname.upper().startswith('LV-'):
                        continue
                    segments = _beam_segment_bboxes(beam)
                    if not segments:
                        continue

                    # Linhas paralelas ao eixo maior do pilar, encostadas nas faces longas.
                    # Um mesmo beam do SA pode carregar ocorrencias vizinhas. Para nao
                    # contaminar a ficha, guardamos so o segmento local de menor gap.
                    left_cand = right_cand = bottom_cand = top_cand = None

                    def _prefer_segment(current, score: tuple[float, float], bb):
                        if current is None or score < current[0]:
                            return score, bb
                        return current
                    for _label, bb in segments:
                        bx0, by0, bx1, by1 = bb
                        bw, bh = bx1 - bx0, by1 - by0
                        is_vert_seg = bh >= max(10.0, bw * 3.0)
                        is_horiz_seg = bw >= max(10.0, bh * 3.0)

                        if vertical_pillar:
                            if is_vert_seg:
                                gap_y = _interval_gap(by0, by1, py0, py1)
                                if gap_y <= tol:
                                    score = (gap_y, abs(((by0 + by1) / 2.0) - ((py0 + py1) / 2.0)))
                                    if min(abs(bx0 - px0), abs(bx1 - px0)) <= tol:
                                        left_cand = _prefer_segment(left_cand, score, bb)
                                    if min(abs(bx0 - px1), abs(bx1 - px1)) <= tol:
                                        right_cand = _prefer_segment(right_cand, score, bb)
                            if is_horiz_seg and py0 - influence <= (by0 + by1) / 2.0 <= py1 + influence:
                                touches_a = min(abs(bx0 - px0), abs(bx1 - px0)) <= tol
                                touches_b = min(abs(bx0 - px1), abs(bx1 - px1)) <= tol
                                if touches_a and min(bx0, bx1) < px0 - tol:
                                    _add('A', 'chega', _beam_detail(beam, bb, 'chega perpendicularmente na face A'))
                                if touches_b and max(bx0, bx1) > px1 + tol:
                                    _add('B', 'chega', _beam_detail(beam, bb, 'chega perpendicularmente na face B'))
                        else:
                            if is_horiz_seg:
                                gap_x = _interval_gap(bx0, bx1, px0, px1)
                                if gap_x <= tol:
                                    score = (gap_x, abs(((bx0 + bx1) / 2.0) - ((px0 + px1) / 2.0)))
                                    if min(abs(by0 - py0), abs(by1 - py0)) <= tol:
                                        bottom_cand = _prefer_segment(bottom_cand, score, bb)
                                    if min(abs(by0 - py1), abs(by1 - py1)) <= tol:
                                        top_cand = _prefer_segment(top_cand, score, bb)
                            if is_vert_seg and px0 - influence <= (bx0 + bx1) / 2.0 <= px1 + influence:
                                touches_c = min(abs(by0 - py0), abs(by1 - py0)) <= tol
                                touches_d = min(abs(by0 - py1), abs(by1 - py1)) <= tol
                                if touches_c and min(by0, by1) < py0 - tol:
                                    _add('C', 'chega', _beam_detail(beam, bb, 'chega perpendicularmente na face C'))
                                if touches_d and max(by0, by1) > py1 + tol:
                                    _add('D', 'chega', _beam_detail(beam, bb, 'chega perpendicularmente na face D'))

                    if vertical_pillar:
                        left_bb = left_cand[1] if left_cand else None
                        right_bb = right_cand[1] if right_cand else None
                        if left_bb and not result['A']['passa']:
                            _add('A', 'passa', _beam_detail(beam, left_bb, 'corre ao longo da face A'))
                        if right_bb and not result['B']['passa']:
                            _add('B', 'passa', _beam_detail(beam, right_bb, 'corre ao longo da face B'))
                        if left_bb and right_bb and not (result['C']['interior'] or result['D']['interior']):
                            # Mesma seção do pilar seguindo no eixo N-S: face curta vira limite interno.
                            sel_y0 = min(left_bb[1], right_bb[1])
                            sel_y1 = max(left_bb[3], right_bb[3])
                            ref_bb = left_bb or right_bb
                            if sel_y1 >= py1 + tol:
                                _add('C', 'interior', _beam_detail(beam, ref_bb, 'face C é limite interno; viga continua no eixo do pilar'))
                            if sel_y0 <= py0 - tol:
                                _add('D', 'interior', _beam_detail(beam, ref_bb, 'face D é limite interno; viga continua no eixo do pilar'))
                    else:
                        bottom_bb = bottom_cand[1] if bottom_cand else None
                        top_bb = top_cand[1] if top_cand else None
                        if bottom_bb and not result['A']['passa']:
                            _add('A', 'passa', _beam_detail(beam, bottom_bb, 'corre ao longo da face A'))
                        if top_bb and not result['B']['passa']:
                            _add('B', 'passa', _beam_detail(beam, top_bb, 'corre ao longo da face B'))
                        if bottom_bb and top_bb and not (result['C']['interior'] or result['D']['interior']):
                            sel_x0 = min(bottom_bb[0], top_bb[0])
                            sel_x1 = max(bottom_bb[2], top_bb[2])
                            ref_bb = bottom_bb or top_bb
                            if sel_x0 <= px0 - tol:
                                _add('C', 'interior', _beam_detail(beam, ref_bb, 'face C é limite interno; viga continua no eixo do pilar'))
                            if sel_x1 >= px1 + tol:
                                _add('D', 'interior', _beam_detail(beam, ref_bb, 'face D é limite interno; viga continua no eixo do pilar'))

                def _norm_beam_label(raw: str) -> str:
                    value = raw.strip().replace(' ', '').upper()
                    match = re.match(r'^F\.(.+?)(?:\.C)?(?:-\d+)?$', value)
                    if match:
                        return 'VF' + re.sub(r'[^A-Z0-9]', '', match.group(1))
                    return value

                def _corner_label_override(face_id: str) -> tuple[str, tuple[float, float]] | None:
                    """Nome ancorado no canto do pilar vence nome de trecho distante.

                    Segmentos de fundo podem herdar o nome da viga horizontal mais
                    próxima. Uma etiqueta de viga encostada no próprio canto é uma
                    evidência geométrica mais forte para a chegada naquela face.
                    """
                    if vertical_pillar:
                        corner = (px0 if face_id == 'A' else px1, py1)
                    else:
                        corner = (px1, py0 if face_id == 'A' else py1)
                    candidates: list[tuple[float, str, tuple[float, float]]] = []
                    # O headless entrega beam_texts filtrado em algumas rotas; o
                    # texto bruto do DXF é o fallback canônico para a âncora.
                    for text_item in list(self._beam_texts or []) + list((self._dxf_data or {}).get('texts', []) or []):
                        raw = str(text_item.get('text') or '').strip()
                        name = _norm_beam_label(raw)
                        if not re.fullmatch(r'(?:V|VF)\d+', name):
                            continue
                        pos = text_item.get('pos') or []
                        if len(pos) < 2:
                            continue
                        try:
                            point = (float(pos[0]), float(pos[1]))
                        except (TypeError, ValueError):
                            continue
                        distance = math.hypot(point[0] - corner[0], point[1] - corner[1])
                        if distance <= max(35.0, tol * 2.5):
                            candidates.append((distance, name, point))
                    if not candidates:
                        return None
                    _, name, point = min(candidates, key=lambda item: item[0])
                    return name, point

                def _corner_label_width(label_pos: tuple[float, float], fallback: str) -> str:
                    """Largura cotada na linha da etiqueta; profundidade vem do trecho."""
                    candidates: list[tuple[float, str]] = []
                    for text_item in list(self._beam_texts or []) + list((self._dxf_data or {}).get('texts', []) or []):
                        raw = str(text_item.get('text') or '').strip().replace(',', '.')
                        if not re.fullmatch(r'\d+(?:\.\d+)?', raw):
                            continue
                        pos = text_item.get('pos') or []
                        if len(pos) < 2:
                            continue
                        try:
                            dx = float(pos[0]) - label_pos[0]
                            dy = float(pos[1]) - label_pos[1]
                        except (TypeError, ValueError):
                            continue
                        # Cota de largura costuma estar na mesma faixa horizontal
                        # do nome; não aceitar número distante de outra viga.
                        if abs(dy) <= 25.0 and math.hypot(dx, dy) <= 160.0:
                            candidates.append((math.hypot(dx, dy), raw))
                    return min(candidates, key=lambda item: item[0])[1] if candidates else fallback

                # Substituição conservadora: somente uma chegada detectada e uma
                # etiqueta de outra viga encostada no canto correspondente. Assim,
                # não se apaga uma lista real de chegadas múltiplas.
                for _face_id in ('A', 'B'):
                    _arrivals = result[_face_id]['chega']
                    _override = _corner_label_override(_face_id)
                    if len(_arrivals) != 1 or not _override:
                        continue
                    _old_name = _viga_name_from_detail(_arrivals[0])
                    _new_name, _label_pos = _override
                    if not _old_name or _old_name == _new_name:
                        continue
                    _dim_match = re.search(r'dim:\s*([^·\s]+)', _arrivals[0])
                    _old_dim = _dim_match.group(1).strip() if _dim_match else ''
                    if '/' in _old_dim:
                        _old_width, _depth = _old_dim.split('/', 1)
                        _width = _corner_label_width(_label_pos, _old_width)
                        _new_dim = f'{_width}/{_depth}'
                    else:
                        _new_dim = _old_dim
                    _detail = f'Viga: {_new_name}'
                    if _new_dim:
                        _detail += f'  ·  dim: {_new_dim}'
                    _detail += f'  ·  chega perpendicularmente na face {_face_id} (nome ancorado no canto do pilar)'
                    result[_face_id]['chega'] = [_detail]

                return result

            def _none_msg(text: str) -> str:
                return f'<span class="muted">— {html.escape(text)}</span>'

            def _laje_answer_detail(laje_detail: str, has_laje: bool) -> str:
                return laje_detail

            def _passa_answer_detail(viga_detail: str, has_viga: bool, fid: str) -> str:
                return viga_detail

            def _chega_answer_detail(viga_detail: str, has_viga: bool, fid: str) -> str:
                return viga_detail

            def _interior_answer_detail(viga_detail: str, has_viga: bool, fid: str) -> str:
                return viga_detail if has_viga else _none_msg('nenhuma')

            def _valid_row(base_key: str, suffix: str, badge: str, cls: str, detail: str) -> str:
                cb_key = f'val_{base_key}_{suffix}'.replace(' ', '_')
                return (
                    '<label class="valid-row">'
                    f'<input type="checkbox" class="validacao-cb" '
                    f'data-cbkey="{html.escape(cb_key)}" onchange="toggleValidacao(this)">'
                    '<span class="valid-lbl">Aprovado</span>'
                    f'<span class="valid-badge {cls}">{html.escape(badge)}</span>'
                    f'<div class="valid-detail">{detail}</div>'
                    '</label>'
                )

            def _mode_row(base_key: str, suffix: str, badge: str, cls: str, detail: str) -> str:
                cb_key = f'val_{base_key}_{suffix}'.replace(' ', '_')
                return (
                    '<label class="mode-row">'
                    f'<input type="checkbox" class="validacao-cb" '
                    f'data-cbkey="{html.escape(cb_key)}" onchange="toggleValidacao(this)">'
                    '<span class="valid-lbl">Aprovado</span>'
                    f'<span class="valid-badge {cls}">{html.escape(badge)}</span>'
                    f'<div class="valid-detail">{detail}</div>'
                    '</label>'
                )

            def _field_table(rows_: list[tuple[str, str]]) -> str:
                return '<table class="field-table">' + ''.join(
                    f'<tr><td>{html.escape(k)}</td><td>{v}</td></tr>' for k, v in rows_
                ) + '</table>'

            def _face_validation_section(row: dict, pillar: dict, lbls: dict, base_key: str) -> str:
                comp, larg = _pillar_dims(row.get('_points') or [])
                cards = []
                for fid in ('A', 'B', 'C', 'D'):
                    cell = (row.get(f'Lado {fid}') or 'nulo').strip() or 'nulo'
                    entries = _entries_for_side(pillar, fid)
                    lajes = [
                        _entry_laje_detail(e) for e in entries
                        if (e.get('content_type') or 'laje') in ('laje', 'both') and e.get('laje')
                    ]
                    vigas = [
                        _entry_viga_detail(e) for e in entries
                        if (e.get('content_type') or '') in ('viga', 'both') and e.get('viga')
                    ]
                    laje_detail = (
                        '<br>'.join(html.escape(x) for x in lajes)
                        if lajes else '<span class="muted">— nenhuma</span>'
                    )
                    viga_detail = (
                        '<br>'.join(html.escape(x) for x in vigas)
                        if vigas else '<span class="muted">— nenhuma</span>'
                    )
                    has_laje = bool(lajes)
                    has_viga = bool(vigas)
                    interior_row = (
                        _valid_row(
                            base_key, f'{fid}_dentro_interior', 'Dentro do interior', 'vb-grade',
                            _interior_answer_detail(viga_detail, has_viga, fid)
                        )
                        if has_viga else ''
                    )
                    cards.append(
                        f'<div class="valid-card">'
                        f'<div class="valid-card-title {FACE_CLSS[fid]}">{html.escape(lbls[fid])}</div>'
                        + _valid_row(
                            base_key, f'{fid}_lajes', 'Lajes', 'vb-sa',
                            _laje_answer_detail(laje_detail, has_laje)
                        )
                        + _valid_row(
                            base_key, f'{fid}_vigas_passa', 'Vigas que passam', 'vb-passa',
                            _passa_answer_detail(viga_detail, has_viga, fid)
                        )
                        + _valid_row(
                            base_key, f'{fid}_vigas_para', 'Vigas que chegam', 'vb-para',
                            _chega_answer_detail(viga_detail, has_viga, fid)
                        )
                        + interior_row
                        + f'</div>'
                    )
                return (
                    '<div class="sec"><div class="sec-title">Validação N1 — Interpretação ABCD por face</div>'
                    '<div class="sec-body">'
                    '<div style="font-size:10px;color:#777;margin-bottom:7px">'
                    'Checklist humano no formato do guia interpretacao_abcd.html: cada checkbox aprova diretamente a resposta da categoria abaixo.</div>'
                    f'<div class="valid-grid">{"".join(cards)}</div></div></div>'
                )

            def _cima_section(row: dict, base_key: str) -> str:
                comp, larg = _pillar_dims(row.get('_points') or [])
                detail = _field_table([
                    ('comprimento', html.escape(_fmt_num(comp)) + ' cm'),
                    ('largura', html.escape(_fmt_num(larg)) + ' cm'),
                    ('formato', html.escape(str(row.get('Formato') or '—'))),
                    ('fonte', 'bbox/pontos SA + Foto N1'),
                ])
                return (
                    '<div class="sec"><div class="sec-title">CIMA — validação única</div>'
                    '<div class="sec-body"><div class="mode-card">'
                    '<div class="mode-title cima">Visão CIMA não separa PARA/PASSA</div>'
                    + _mode_row(base_key, 'cima_unico', 'CIMA', 'vb-cima', detail)
                    + '<div class="mode-note">Use esta validação única para o topo do pilar. '
                    'A separação em dois modos começa em ABCD e GRADES.</div>'
                    '</div></div></div>'
                )

            def _modes_section(row: dict, base_key: str) -> str:
                comp, larg = _pillar_dims(row.get('_points') or [])
                face_rows = []
                for fid in ('A', 'B', 'C', 'D'):
                    cell = (row.get(f'Lado {fid}') or 'nulo').strip() or 'nulo'
                    face_rows.append((
                        f'Lado {fid}',
                        f'{html.escape(_face_kind(cell))} · '
                        f'{html.escape("longa" if fid in ("A", "B") else "curta")} · '
                        f'{html.escape(_fmt_num(_face_len(fid, comp, larg)))}cm<br>'
                        f'<span class="muted">{html.escape(cell).replace(chr(10), "<br>")}</span>'
                    ))
                common = _field_table(face_rows)
                para_detail = (
                    common
                    + '<div class="mode-note">Modo PARA: usar quando a lista/comparison engine classificar '
                        'a viga como chegada/terminando no pilar. ABCD deve representar abertura/recorte de chegada '
                        'ou “Para no canto” em Modo Ini/Nova; '
                    'GRADES segue a mesma interpretação de painéis, com alturas locais.</div>'
                )
                passa_detail = (
                    common
                    + '<div class="mode-note">Modo PASSA: usar quando a viga passa ao longo da face/parede lateral, '
                    'ou quando a interpretação for continuidade/engolimento (“Dentro do interior”). '
                    'ABCD deve preservar essa continuidade; GRADES acompanha os painéis resultantes '
                    'sem mudar a visão CIMA.</div>'
                )
                grade_base = _field_table([
                    ('A/B', 'gerar grade normalmente nas faces longas quando houver painel'),
                    ('C/D', 'gerar somente se a largura da face curta for superior a 50cm'),
                    ('topo', 'sarrafos verticais terminam 15cm abaixo do topo local do painel'),
                    ('largura', 'cada grade usa a largura do respectivo painel/trecho'),
                    ('extremos', 'sarrafos externos 7cm; internos/encontros/distâncias 3,5cm'),
                ])
                grades_para = grade_base + '<div class="mode-note">GRADES PARA: compatibilizar com o ABCD modo PARA; se a viga cria abertura/recorte, cada vertical recebe altura isolada.</div>'
                grades_passa = grade_base + '<div class="mode-note">GRADES PASSA: compatibilizar com o ABCD modo PASSA; preservar continuidade/engolimento e separar grades por trecho real do painel.</div>'
                return (
                    '<div class="sec"><div class="sec-title">Saídas N3 por modo — ABCD e GRADES</div>'
                    '<div class="sec-body"><div class="mode-grid">'
                    '<div class="mode-card"><div class="mode-title para">ABCD — caso a viga PARE</div>'
                    + _mode_row(base_key, 'abcd_para', 'ABCD PARA', 'vb-para', para_detail)
                    + '</div>'
                    '<div class="mode-card"><div class="mode-title passa">ABCD — caso a viga PASSE</div>'
                    + _mode_row(base_key, 'abcd_passa', 'ABCD PASSA', 'vb-passa', passa_detail)
                    + '</div>'
                    '<div class="mode-card"><div class="mode-title para">GRADES — caso a viga PARE</div>'
                    + _mode_row(base_key, 'grades_para', 'GRADES PARA', 'vb-grade', grades_para)
                    + '</div>'
                    '<div class="mode-card"><div class="mode-title passa">GRADES — caso a viga PASSE</div>'
                    + _mode_row(base_key, 'grades_passa', 'GRADES PASSA', 'vb-grade', grades_passa)
                    + '</div>'
                    '</div></div></div>'
                )

            def _load_n3_pilar_json(item_name: str) -> dict:
                if not self._obra:
                    return {}
                try:
                    import json as _json
                    json_path = os.path.join(
                        'D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra,
                        'Fase-4_Sincronizacao', 'JSON_Pilares', f'{item_name}.json'
                    )
                    if not os.path.exists(json_path):
                        return {}
                    with open(json_path, encoding='utf-8') as f:
                        return _json.load(f) or {}
                except Exception:
                    return {}

            def _mode_beam_parts(detail: str) -> dict:
                """Converte uma resposta humana da ficha N1 em dado rastreavel."""
                match = re.search(
                    r'^Viga:\s*([^·]+)(?:\s*·\s*dim:\s*'
                    r'([0-9]+(?:[.,][0-9]+)?)\s*/\s*([0-9]+(?:[.,][0-9]+)?))?',
                    str(detail or ''),
                )
                if not match:
                    return {'nome': 'SEM_NOME', 'largura': None, 'profundidade': None,
                            'evidencia': str(detail or '')}
                try:
                    width = float(match.group(2).replace(',', '.')) if match.group(2) else None
                    depth = float(match.group(3).replace(',', '.')) if match.group(3) else None
                except (AttributeError, ValueError):
                    width = depth = None
                return {
                    'nome': re.sub(r'(?<=\d)[AB]$', '', match.group(1).strip(), flags=re.I),
                    'largura': width,
                    'profundidade': depth,
                    'evidencia': str(detail or ''),
                }

            def _mode_slot(row: dict, pillar: dict, fid: str, beam_name: str,
                           arrival: bool) -> str | None:
                """Resolve AC/AD/AA e BC/BD/BB pela geometria consolidada do SA."""
                pts = row.get('_points') or pillar.get('points') or []
                if not pts:
                    return None
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                px0, px1, py0, py1 = min(xs), max(xs), min(ys), max(ys)
                vertical = (py1 - py0) > (px1 - px0)
                tol = max(6.0, min(max(px1 - px0, py1 - py0) * 0.12, 18.0))
                normalized = re.sub(r'(?<=\d)[AB]$', '', str(beam_name), flags=re.I)
                candidates: list[tuple[float, str]] = []
                for group in (getattr(self, '_segment_data', {}) or {}).values():
                    for seg in group or []:
                        seg_name = re.sub(
                            r'(?<=\d)[AB]$', '', str(seg.get('beam_name') or ''), flags=re.I,
                        )
                        if seg_name != normalized:
                            continue
                        seg_pts = [_as_point(p) for p in (seg.get('points') or [])]
                        seg_pts = [p for p in seg_pts if p is not None]
                        if len(seg_pts) < 2:
                            continue
                        bx0 = min(p[0] for p in seg_pts)
                        bx1 = max(p[0] for p in seg_pts)
                        by0 = min(p[1] for p in seg_pts)
                        by1 = max(p[1] for p in seg_pts)
                        bw, bh = bx1 - bx0, by1 - by0
                        is_vertical = bh >= max(10.0, bw * 3.0)
                        is_horizontal = bw >= max(10.0, bh * 3.0)
                        if vertical and fid in ('A', 'B'):
                            face_x = px0 if fid == 'A' else px1
                            if not (bx0 - tol <= face_x <= bx1 + tol):
                                continue
                            if is_vertical:
                                if abs(by0 - py1) <= tol:
                                    candidates.append((abs(by0 - py1), 'C'))
                                if abs(by1 - py0) <= tol:
                                    candidates.append((abs(by1 - py0), 'D'))
                            elif arrival and is_horizontal:
                                mid = (by0 + by1) / 2.0
                                if mid < py0:
                                    candidates.append((py0 - mid, 'C'))
                                elif mid > py1:
                                    candidates.append((mid - py1, 'D'))
                                else:
                                    candidates.append((0.0, 'central'))
                        elif (not vertical) and fid in ('A', 'B'):
                            face_y = py0 if fid == 'A' else py1
                            if not (by0 - tol <= face_y <= by1 + tol):
                                continue
                            if is_horizontal:
                                if abs(bx0 - px1) <= tol:
                                    candidates.append((abs(bx0 - px1), 'C'))
                                if abs(bx1 - px0) <= tol:
                                    candidates.append((abs(bx1 - px0), 'D'))
                            elif arrival and is_vertical:
                                mid = (bx0 + bx1) / 2.0
                                if px0 <= mid <= px1:
                                    candidates.append((0.0, 'central'))
                return min(candidates)[1] if candidates else None

            def _mode_slab_depth(data: dict) -> tuple[float | None, str | None]:
                ranked = []
                for detail in data.get('lajes') or []:
                    match = re.search(r'esp:\s*([0-9]+(?:[.,][0-9]+)?)', detail)
                    if match:
                        ranked.append((float(match.group(1).replace(',', '.')), detail))
                return max(ranked, default=(None, None), key=lambda item: item[0] or 0)

            def _build_n3_mode_contract(row: dict, pillar: dict, mode: str) -> dict:
                """Fonte unica das fichas/artefatos N3 PARA e PASSA.

                O contrato e derivado; o JSON canonico da Fase-4 nunca e alterado.
                Cada campo conserva a resposta N1 que o originou para auditoria humana.
                """
                mode = str(mode or '').lower()
                face_interp = _dynamic_face_interpretation(row, pillar)
                faces: dict[str, dict] = {}
                visual_mode = str(
                    _load_n3_pilar_json(str(row.get('_nome') or '')).get(
                        'modo_distribuicao', 'NOVA'
                    ) or 'NOVA'
                ).upper()
                # Nível do pilar = maior nível de laje em contato (topo de referência)
                _pillar_top_level_abs = None
                _pillar_bot_level_abs = None
                try:
                    from pl_abcd_visual_nova import parse_slab_level_and_esp as _parse_sl
                except Exception:
                    try:
                        import sys as _sys
                        _scripts = os.path.normpath(os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            '..', '..', '..', 'scripts',
                        ))
                        if _scripts not in _sys.path:
                            _sys.path.insert(0, _scripts)
                        from pl_abcd_visual_nova import parse_slab_level_and_esp as _parse_sl
                    except Exception:
                        _parse_sl = None
                if _parse_sl is not None:
                    for _fid0 in ('A', 'B', 'C', 'D'):
                        for _raw in (face_interp.get(_fid0) or {}).get('lajes') or []:
                            _lv, _ = _parse_sl(str(_raw))
                            if _lv is None:
                                continue
                            if _pillar_top_level_abs is None or _lv > _pillar_top_level_abs:
                                _pillar_top_level_abs = _lv
                    for _k in ('nivel_saida', 'nivel', 'level'):
                        _v = row.get(_k)
                        if _v is None:
                            continue
                        try:
                            _vf = float(str(_v).replace(',', '.'))
                            if _vf > 20:
                                if _pillar_top_level_abs is None or _vf > _pillar_top_level_abs:
                                    _pillar_top_level_abs = _vf
                        except Exception:
                            pass
                for fid in ('A', 'B', 'C', 'D'):
                    data = face_interp.get(fid, {})
                    passes = [_mode_beam_parts(item) for item in data.get('passa') or []]
                    interiors = [_mode_beam_parts(item) for item in data.get('interior') or []]
                    arrivals = [_mode_beam_parts(item) for item in data.get('chega') or []]
                    slab_depth, slab_evidence = _mode_slab_depth(data)
                    top_candidates = interiors[:]
                    if mode == 'passa' or fid in ('C', 'D'):
                        top_candidates += passes
                    top_candidates = [item for item in top_candidates
                                      if item.get('profundidade') is not None]
                    reference = max(
                        [item for item in passes + interiors
                         if item.get('profundidade') is not None],
                        default=None,
                        key=lambda item: item['profundidade'],
                    )
                    if top_candidates:
                        top = max(top_candidates, key=lambda item: item['profundidade'])
                        top_void = float(top['profundidade'])
                        top_source = 'dentro_do_interior' if top in interiors else 'viga_que_passa'
                        top_evidence = top['evidencia']
                    elif slab_depth is not None:
                        top_void = float(slab_depth) + 2.0
                        top_source = 'laje_espessura_mais_2'
                        top_evidence = slab_evidence
                    else:
                        top_void, top_source, top_evidence = 0.0, 'nulo', 'nenhuma fonte aplicavel'

                    stop_openings = []
                    if mode == 'para' and fid in ('A', 'B'):
                        for beam in passes:
                            pos = _mode_slot(row, pillar, fid, beam['nome'], False)
                            if pos not in ('C', 'D'):
                                continue
                            slot = f'{fid}{pos}'
                            stop_openings.append({
                                **beam, 'slot': slot, 'estado': 'ativa',
                                'largura_ini': 7.5,
                                'largura_nova': 11.0,
                                'altura': ((beam.get('profundidade') or 0.0) + 4.0),
                                'regra': 'Ini=7,5; Nova=11; profundidade=viga+4',
                            })

                    arrival_openings = []
                    for beam in arrivals:
                        pos = _mode_slot(row, pillar, fid, beam['nome'], True)
                        pos = pos if pos in ('C', 'D', 'central') else 'central'
                        slot = (f'{fid}{fid}' if pos == 'central' else f'{fid}{pos}')
                        ref_depth = reference.get('profundidade') if reference else None
                        neutralized = (
                            mode == 'passa' and ref_depth is not None and
                            beam.get('profundidade') is not None and
                            beam['profundidade'] <= ref_depth
                        )
                        corner = pos in ('C', 'D')
                        final_width = ((beam.get('largura') or 0.0) + (15.0 if corner else 8.0))
                        arrival_openings.append({
                            **beam, 'slot': slot,
                            'estado': 'neutralizada' if neutralized else 'ativa',
                            'largura_abertura': final_width,
                            'altura': ((beam.get('profundidade') or 0.0) + 4.0),
                            'regra': ('largura+11+4; profundidade+4' if corner
                                      else 'largura+4+4; profundidade+4'),
                            'motivo_neutralizacao': (
                                f'chegada {beam.get("profundidade")} <= passante {ref_depth}'
                                if neutralized else ''
                            ),
                        })
                    # Laje: rebaixo = Δnível (pilar topo − laje); vazio = esp+2
                    try:
                        from pl_abcd_visual_nova import face_laje_metrics
                    except Exception:
                        try:
                            import sys as _sys
                            _scripts = os.path.normpath(os.path.join(
                                os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', '..', 'scripts',
                            ))
                            if _scripts not in _sys.path:
                                _sys.path.insert(0, _scripts)
                            from pl_abcd_visual_nova import face_laje_metrics
                        except Exception:
                            face_laje_metrics = None
                    laje_m = {}
                    if face_laje_metrics is not None:
                        # topo do pilar: maior nível de laje/viga em contato no item
                        # (fallback: nivel_saida da ficha se absoluto)
                        laje_m = face_laje_metrics(
                            {'fontes_n1': data},
                            pillar_top_level=_pillar_top_level_abs,
                        )
                        # Se há laje e não há passante dominante em A/B, o vazio de
                        # topo não engole o rebaixo: rebaixo é faixa sólida separada.
                        if mode == 'para' and fid in ('A', 'B') and laje_m.get('vazio_laje_cm'):
                            # top_void para A/B com laje: NÃO usa esp+2 como único topo
                            # (aberturas de viga já definem o recorte; rebaixo/vazio laje
                            # vão em campos dedicados).
                            if top_source == 'laje_espessura_mais_2':
                                top_void = 0.0
                                top_source = 'laje_rebaixo_e_vazio_separados'
                                top_evidence = laje_m.get('evidencia_laje') or top_evidence
                    faces[fid] = {
                        'vazio_topo': {
                            'valor_cm': round(top_void, 4), 'fonte': top_source,
                            'evidencia': top_evidence, 'confianca': 'alta' if top_evidence else 'baixa',
                        },
                        'viga_passante_referencia': reference,
                        'aberturas_vigas_que_param': stop_openings,
                        'aberturas_vigas_que_chegam': arrival_openings,
                        'fontes_n1': data,
                        'rebaixo_laje_cm': laje_m.get('rebaixo_laje_cm', 0.0) if laje_m else 0.0,
                        'vazio_laje_cm': laje_m.get('vazio_laje_cm', 0.0) if laje_m else 0.0,
                        'nivel_laje': laje_m.get('nivel_laje') if laje_m else None,
                        'espessura_laje': laje_m.get('espessura_laje') if laje_m else None,
                    }
                base = _load_n3_pilar_json(str(row.get('_nome') or ''))
                return {
                    'schema': 'pil.n3_mode_contract.v2',
                    'item': str(row.get('_nome') or ''),
                    'modo_semantico': mode.upper(),
                    'modo_visual': visual_mode,
                    'fonte': 'SA/N1 + segmentos FV/LV consolidados + lajes vinculadas',
                    'altura_pilar': {
                        'nivel_saida': base.get('nivel_saida'),
                        'nivel_chegada': base.get('nivel_chegada'),
                        'altura': base.get('altura'),
                        'nivel_saida_abs': _pillar_top_level_abs,
                        'nivel_chegada_abs': _pillar_bot_level_abs,
                    },
                    'faces': faces,
                }

            def _variant_payload(contract: dict) -> dict:
                """Projeta o contrato semantico no schema que o gerador ABCD/GRADES le.

                Aberturas e lajes vêm do contrato SA (PARA vs PASSA). A malha
                de painéis (122+sobra), rebaixo, y_rel e sanidade são do
                motor NOVA ``enrich_payload_for_abcd_nova`` — não se injeta
                junta de abertura na malha (abertura = recorte, não módulo).
                """
                base = json.loads(json.dumps(
                    _load_n3_pilar_json(str(contract.get('item') or ''))
                ))
                if not base:
                    return {}
                mode = str(contract.get('modo_semantico') or '').lower()
                visual_mode = str(contract.get('modo_visual') or 'NOVA').upper()
                height = float(
                    base.get('pd_pavimento_cm')
                    or base.get('altura')
                    or 280.0
                )
                for fid, face in (contract.get('faces') or {}).items():
                    # Limpa somente campos derivados; o payload canonico permanece intacto.
                    for key in list(base):
                        if key == f'abertura_{fid}' or key.startswith(f'abertura_{fid}_'):
                            base.pop(key, None)
                    # Limpa malha legada (h2=244 etc.) — o enrich NOVA recalcula.
                    base.pop(f'paineis_intervals_{fid}', None)
                    h1 = float(base.get(f'h1_geom_{fid}', base.get(f'h1_{fid}', 2.0)) or 0.0)
                    top_void = float((face.get('vazio_topo') or {}).get('valor_cm') or 0.0)
                    panel_height = max(h1, height - top_void)
                    try:
                        rebaixo = float(face.get('rebaixo_laje_cm') or 0.0)
                    except (TypeError, ValueError):
                        rebaixo = 0.0
                    # Sanity: rebaixo de laje é faixa de cm, não PD/nível *100
                    if rebaixo > 40.0:
                        rebaixo = 0.0
                    try:
                        vazio_laje = float(face.get('vazio_laje_cm') or 0.0)
                    except (TypeError, ValueError):
                        vazio_laje = 0.0
                    base[f'rebaixo_laje_{fid}'] = rebaixo
                    base[f'vazio_laje_{fid}'] = vazio_laje
                    if face.get('nivel_laje') is not None:
                        base[f'nivel_laje_{fid}'] = face.get('nivel_laje')
                    # Conteúdo útil do painel sob o rebaixo (rebaixo é faixa sólida no topo)
                    content_cap = max(h1, panel_height - rebaixo)
                    openings = []
                    if mode == 'para':
                        for opening in face.get('aberturas_vigas_que_param') or []:
                            if opening.get('estado') != 'ativa' or not opening.get('altura'):
                                continue
                            pos = str(opening.get('slot') or '')[-1:]
                            side = ('esquerdo' if (fid == 'A' and pos == 'C') or
                                    (fid == 'B' and pos == 'D') else 'direito')
                            width = (opening.get('largura_ini') if visual_mode == 'INI'
                                     else opening.get('largura_nova'))
                            oh = float(opening['altura'])
                            # y_rel preliminar; enrich dual+vazio cola no topo se preciso
                            y_rel = max(0.0, content_cap - h1 - oh)
                            openings.append({
                                'lado': side, 'largura': width,
                                'altura': oh,
                                'y_rel': y_rel,
                                '_origem': opening.get('slot'), '_viga': opening.get('nome'),
                            })
                    for opening in face.get('aberturas_vigas_que_chegam') or []:
                        if opening.get('estado') != 'ativa' or not opening.get('altura'):
                            continue
                        slot = str(opening.get('slot') or '')
                        pos = slot[-1:] if len(slot) >= 2 else 'central'
                        if pos not in ('C', 'D'):
                            side = 'meio'
                        else:
                            side = ('esquerdo' if (fid == 'A' and pos == 'C') or
                                    (fid == 'B' and pos == 'D') else 'direito')
                        oh = float(opening['altura'])
                        _cap = max(h1, float(panel_height) - rebaixo)
                        entry = {
                            'lado': side, 'largura': opening.get('largura_abertura') or 0.0,
                            'altura': oh,
                            'y_rel': max(0.0, _cap - h1 - oh),
                            '_origem': slot, '_viga': opening.get('nome'),
                        }
                        if side == 'meio':
                            panel_width = float(base.get(f'larg1_{fid}') or 0.0)
                            entry['x_offset'] = max(0.0, (panel_width - float(entry['largura'])) / 2.0)
                        openings.append(entry)

                    # NÃO injetar fundo/topo de abertura na malha de painéis:
                    # NOVA trata abertura como recorte (malha = 122+sobra).
                    for index, opening in enumerate(openings, 1):
                        base[f'abertura_{fid}_{index}'] = opening
                # Níveis absolutos para header do DXF
                alt = contract.get('altura_pilar') or {}
                if alt.get('nivel_saida_abs') is not None:
                    base['nivel_saida_abs'] = alt['nivel_saida_abs']
                if alt.get('nivel_chegada_abs') is not None:
                    base['nivel_chegada_abs'] = alt['nivel_chegada_abs']
                # PD: se temos abs, recalcula
                try:
                    if alt.get('nivel_saida_abs') is not None and alt.get('nivel_chegada_abs') is not None:
                        ns = float(alt['nivel_saida_abs'])
                        nc = float(alt['nivel_chegada_abs'])
                        # metros → cm de PD
                        if ns > 20 and nc > 20:
                            base['pd_pavimento_cm'] = abs(ns - nc) * 100.0
                            base['altura'] = base['pd_pavimento_cm']
                        else:
                            base['pd_pavimento_cm'] = abs(ns - nc)
                    elif alt.get('nivel_saida_abs') is not None:
                        # só topo de laje: chegada = topo − altura relativa
                        ns = float(alt['nivel_saida_abs'])
                        h = float(base.get('altura') or height or 280.0)
                        if ns > 20:
                            base['nivel_saida_abs'] = ns
                            base['nivel_chegada_abs'] = ns - (h / 100.0)
                except Exception:
                    pass
                base['_sa_mode_contract'] = contract
                base['_sa_mode_variant'] = contract.get('modo_semantico')
                base['modo_distribuicao'] = 'NOVA'
                # Motor NOVA universal: malha 122, rebaixo dual, y_rel, clamp
                try:
                    import sys as _sys
                    scripts_dir = os.path.normpath(os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        '..', '..', '..', 'scripts',
                    ))
                    if scripts_dir not in _sys.path:
                        _sys.path.insert(0, scripts_dir)
                    from pl_abcd_visual_nova import enrich_payload_for_abcd_nova
                    base.pop('_pl_nova_enriched', None)
                    base = enrich_payload_for_abcd_nova(base)
                except Exception as exc:
                    print(
                        f'[HTML] enrich NOVA {contract.get("item")}/'
                        f'{contract.get("modo_semantico")} falhou: {exc}',
                        flush=True,
                    )
                return base

            def _materialize_n3_variant(row: dict, pillar: dict, mode: str) -> dict:
                """Persiste JSON + DXF isolados do run; nunca sobrescreve Fase-4/Fase-6.

                JSON publicado já vem enriquecido (motor NOVA). DXF usa o mesmo
                payload via generate_pilar_zone (re-enrich idempotente).
                """
                contract = _build_n3_mode_contract(row, pillar, mode)
                payload = _variant_payload(contract)
                result = {'contract': contract, 'payload': payload, 'paths': {}}
                if not payload:
                    return result
                item = str(contract.get('item') or 'P?')
                mode_slug = str(mode).lower()
                variant_dir = os.path.join(output_dir, 'pilares', 'n3_variants', mode_slug)
                os.makedirs(variant_dir, exist_ok=True)
                json_path = os.path.join(variant_dir, f'{item}.json')
                with open(json_path, 'w', encoding='utf-8') as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
                result['paths']['json'] = json_path
                try:
                    # O gerador historico importa visual_modes/pl_grade_visual_config
                    # como modulos irmaos. Quando consumido como biblioteca pelo SA,
                    # a pasta scripts precisa estar explicitamente no sys.path.
                    import sys as _sys
                    scripts_dir = os.path.normpath(os.path.join(
                        os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'scripts'
                    ))
                    if scripts_dir not in _sys.path:
                        _sys.path.insert(0, scripts_dir)
                    from gerar_pl_dxf_stog import setup_doc, generate_pilar_zone
                    from visual_modes import apply_visual_mode, normalize_visual_mode
                    visual_mode = normalize_visual_mode(
                        contract.get('modo_visual') or 'NOVA'
                    )
                    for zone in ('abcd', 'grades'):
                        # Cópia: generate_pilar_zone muta o pj in-place
                        zone_pj = json.loads(json.dumps(payload))
                        doc = setup_doc()
                        count = generate_pilar_zone(
                            doc.modelspace(), zone_pj, zone,
                            visual_mode=visual_mode,
                        )
                        if count < 0:
                            continue
                        # Perfil final: INI → MLINE; NOVA → preserva LINE.
                        apply_visual_mode(doc, visual_mode, 'PL')
                        path = os.path.join(
                            variant_dir, f'PL_{zone.upper()}_preview_{item}.dxf'
                        )
                        doc.saveas(path)
                        result['paths'][zone] = path
                except Exception as exc:
                    print(f'[HTML] variante N3 {item}/{mode_slug} falhou: {exc}', flush=True)
                # Publicação estável para o Comparison Engine. O pack HTML é
                # imutável por rodada; o CE precisa de uma fonte atual e
                # explícita sem substituir o N3 canônico da Fase-6.
                try:
                    import shutil
                    stable_dir = os.path.join(
                        'D:/Agente-cad-PYSIDE/DADOS-OBRAS', self._obra,
                        'Fase-6_Execucao_CAD', 'n3_variants', mode_slug,
                    )
                    os.makedirs(stable_dir, exist_ok=True)
                    shutil.copy2(json_path, os.path.join(stable_dir, f'{item}.json'))
                    for zone, path in (result.get('paths') or {}).items():
                        if zone in ('abcd', 'grades') and path and os.path.exists(path):
                            shutil.copy2(path, os.path.join(stable_dir, os.path.basename(path)))
                except Exception as exc:
                    print(f'[HTML] publicação CE N3 {item}/{mode_slug} falhou: {exc}', flush=True)
                return result

            # ── N3 PL: sempre PARA + PASSA (nunca escolha manual) ──────────
            # Batch antes das páginas HTML: publica n3_variants p/ CE/headless.
            # Cache por (nome, modo) evita regenerar em _views_sec e no 2º
            # grupo (especiais). Itens ainda não cacheados são gerados.
            _pl_n3_cache: dict = getattr(self, '_pl_n3_cache', None) or {}
            stats0 = getattr(self, '_last_pl_n3_materialize', None) or {}
            _pl_n3_generated: list[str] = list(stats0.get('generated') or [])
            _pl_n3_failed: list[str] = list(stats0.get('failed') or [])
            _batch_new = 0
            for row in rows:
                nome_m = str(row.get('_nome') or '')
                if not nome_m:
                    continue
                pkey_m = row.get('_key') or nome_m
                pillar_m = (
                    self._pillar_report.get(pkey_m)
                    or self._pillar_report.get(nome_m)
                    or {}
                )
                for mode in ('para', 'passa'):
                    label = f'{nome_m}_{mode}'
                    if (nome_m, mode) in _pl_n3_cache:
                        continue
                    try:
                        result = _materialize_n3_variant(row, pillar_m, mode)
                        _pl_n3_cache[(nome_m, mode)] = result
                        _batch_new += 1
                        paths = result.get('paths') or {}
                        if paths.get('json') and (
                            paths.get('abcd') or paths.get('grades')
                        ):
                            if label not in _pl_n3_generated:
                                _pl_n3_generated.append(label)
                        else:
                            if label not in _pl_n3_failed:
                                _pl_n3_failed.append(label)
                    except Exception as exc:
                        if label not in _pl_n3_failed:
                            _pl_n3_failed.append(label)
                        print(
                            f'[HTML] N3 PL {label} falhou: {exc}',
                            flush=True,
                        )
            self._pl_n3_cache = _pl_n3_cache
            self._pl_n3_materialized_once = True
            self._last_pl_n3_materialize = {
                'generated': list(_pl_n3_generated),
                'failed': list(_pl_n3_failed),
            }
            if _batch_new:
                print(
                    f'[HTML] N3 PL PARA+PASSA (+{_batch_new}): '
                    f'{len(_pl_n3_generated)} ok, {len(_pl_n3_failed)} falha(s)',
                    flush=True,
                )

            def _segments_label(values: list) -> str:
                vals = [_fmt_num(v) for v in (values or [])]
                return ' | '.join(vals) if vals else '—'

            def _whole_and_fraction_local(value, tolerance=1e-6):
                value = max(0.0, float(value))
                nearest = round(value)
                if abs(value - nearest) <= tolerance:
                    return int(nearest), 0.0
                whole = math.floor(value)
                return whole, round(value - whole, 6)

            def _balanced_segments_local(total, count):
                if count <= 0:
                    return []
                whole, fraction = _whole_and_fraction_local(total)
                base, remainder = divmod(whole, count)
                parts = [float(base)] * count
                for index in range(count - remainder, count):
                    if 0 <= index < count:
                        parts[index] += 1.0
                if fraction:
                    parts[-1] += fraction
                return parts

            def _integer_segments_local(total_w, offsets, preferred=None, count=4, tol=3.0, max_shift=20.0):
                total_w = float(total_w)
                if total_w <= 0 or count <= 0:
                    return []
                whole, fraction = _whole_and_fraction_local(total_w)
                if whole < count:
                    return _balanced_segments_local(total_w, count)
                ideal = total_w / count
                low = max(1, int(math.floor(ideal - max_shift)))
                high = max(low, int(math.ceil(ideal + max_shift)))
                preferred = [float(v) for v in (preferred or []) if float(v) > 0]
                if len(preferred) != count or abs(sum(preferred) - total_w) > 0.5:
                    preferred = []
                offsets = [float(value) for value in (offsets or [])]
                best = None
                fraction_indexes = [count - 1] if not fraction else list(range(count))
                for first in range(low, high + 1):
                    for second in range(low, high + 1):
                        for third in range(low, high + 1):
                            integers = [first, second, third]
                            last = whole - sum(integers)
                            if last < low or last > high:
                                continue
                            integers.append(last)
                            for fraction_index in fraction_indexes:
                                segments = [float(value) for value in integers]
                                if fraction:
                                    segments[fraction_index] += fraction
                                boundaries = []
                                cumulative = 0.0
                                for segment in segments[:-1]:
                                    cumulative += segment
                                    boundaries.append(cumulative)
                                penetrations = [
                                    tol - abs(boundary - offset)
                                    for boundary in boundaries
                                    for offset in offsets
                                    if abs(boundary - offset) <= tol
                                ]
                                conflict_count = len(penetrations)
                                conflict_depth = round(sum(value + 1e-6 for value in penetrations), 6)
                                balance = round(sum((value - ideal) ** 2 for value in segments), 6)
                                preferred_delta = (
                                    round(sum(abs(a - b) for a, b in zip(segments, preferred)), 6)
                                    if preferred else balance
                                )
                                fraction_rank = 0 if fraction_index == count - 1 else 1
                                score = (
                                    conflict_count,
                                    conflict_depth,
                                    preferred_delta,
                                    balance,
                                    fraction_rank,
                                    tuple(segments),
                                )
                                if best is None or score < best[0]:
                                    best = (score, segments)
                if best:
                    return best[1]
                return _balanced_segments_local(total_w, count)

            def _bolt_offsets_from_pj_local(pj: dict, grade_w: float) -> list:
                bolt_xs = []
                bx = -1.0
                limit = float(grade_w) + 1.0
                for i in range(1, 9):
                    sp = float(pj.get(f'par_{i}_{i+1}') or 0)
                    if sp <= 0:
                        break
                    bx += sp
                    if bx >= limit - 1.0:
                        break
                    bolt_xs.append(bx)
                return bolt_xs

            def _cima_info_card(row: dict, base_key: str) -> str:
                pj = _load_n3_pilar_json(row.get('_nome') or '')
                comp_geo, larg_geo = _pillar_dims(row.get('_points') or [])
                comp = float(pj.get('comprimento') or comp_geo or 0)
                larg = float(pj.get('largura') or larg_geo or 0)
                fallback_total = comp + 22.0
                grade_widths = [
                    float(pj.get(f'grade_{i}') or 0)
                    for i in range(1, 4)
                    if float(pj.get(f'grade_{i}') or 0) > 0
                ]
                if not grade_widths:
                    grade_widths = [fallback_total]
                gaps = [
                    float(pj.get(f'distancia_{i}') or 0)
                    for i in range(1, len(grade_widths))
                    if float(pj.get(f'distancia_{i}') or 0) > 0
                ]
                total_externo = sum(grade_widths) + sum(gaps)
                bolt_offsets = _bolt_offsets_from_pj_local(pj, total_externo)
                divs = []
                cursor = 0.0
                for index, grade_w in enumerate(grade_widths):
                    local_bolts = [
                        offset - cursor
                        for offset in bolt_offsets
                        if cursor - 3.0 <= offset <= cursor + grade_w + 3.0
                    ]
                    preferred = pj.get(f'grade_{index + 1}_div_a') or []
                    divs.append(_integer_segments_local(grade_w, local_bolts, preferred=preferred))
                    if index < len(gaps):
                        cursor += grade_w + gaps[index]
                bolt_chain = [0.0] + [float(x) for x in bolt_offsets] + [total_externo]
                bolt_spans = [b - a for a, b in zip(bolt_chain[:-1], bolt_chain[1:])]
                divs_a = divs or [[]]
                divs_b = [list(reversed(d)) for d in reversed(divs_a)]
                grade_label = ' + '.join(_fmt_num(w) for w in grade_widths)
                rows_cima = [
                    ('comprimento interno', f'{html.escape(_fmt_num(comp))} cm'),
                    ('largura interna', f'{html.escape(_fmt_num(larg))} cm'),
                    ('comprimento +22', f'{html.escape(_fmt_num(comp))} + 22 = <b>{html.escape(_fmt_num(total_externo))} cm</b>'),
                    ('parafusos', f'offsets: {html.escape(_segments_label(bolt_offsets))} cm'),
                    ('cotas parafusos', f'{html.escape(_segments_label(bolt_spans))} cm'),
                    ('layout grades', f'{len(grade_widths)} grade(s): {html.escape(grade_label)} cm; gaps {html.escape(_segments_label(gaps))}'),
                    ('quadradinhos A', html.escape(' ; '.join(f'G{i+1}: {_segments_label(d)}' for i, d in enumerate(divs_a)))),
                    ('quadradinhos B', html.escape(' ; '.join(f'G{i+1}: {_segments_label(d)}' for i, d in enumerate(divs_b))) + ' <span class="muted">(espelhado do A)</span>'),
                ]
                detail = _field_table(rows_cima)
                return (
                    '<div class="mode-card">'
                    '<div class="mode-title cima">CIMA — parafusos + grades em planta</div>'
                    + _mode_row(base_key, 'cima_unico', 'CIMA', 'vb-cima', detail)
                    + '<div class="mode-note">Valida o desenho em planta: comprimento externo (+22), '
                    'cadeia de parafusos e espaçamentos dos sarrafos verticais das grades. '
                    'Em pilares especiais esta mesma lógica será aberta por face A/B/C/D/E/F/G/H.</div>'
                    '</div>'
                )

            def _face_mode_rows(row: dict, mode: str) -> str:
                comp, larg = _pillar_dims(row.get('_points') or [])
                face_rows = []
                for fid in ('A', 'B', 'C', 'D'):
                    cell = (row.get(f'Lado {fid}') or 'nulo').strip() or 'nulo'
                    mode_hint = (
                        'chegada/recorte · guia: Vigas que chegam/Para no canto'
                        if mode == 'para'
                        else 'passagem/continuidade · guia: Vigas que passam/Dentro do interior'
                    )
                    face_rows.append((
                        f'Lado {fid}',
                        f'{html.escape(_face_kind(cell))} · '
                        f'{html.escape("longa" if fid in ("A", "B") else "curta")} · '
                        f'{html.escape(_fmt_num(_face_len(fid, comp, larg)))}cm · {mode_hint}<br>'
                        f'<span class="muted">{html.escape(cell).replace(chr(10), "<br>")}</span>'
                    ))
                return _field_table(face_rows)

            def _abcd_info_card(row: dict, base_key: str, mode: str) -> str:
                is_para = mode == 'para'
                title = 'ABCD — caso a viga PARE' if is_para else 'ABCD — caso a viga PASSE'
                badge = 'ABCD PARA' if is_para else 'ABCD PASSA'
                cls = 'vb-para' if is_para else 'vb-passa'
                note = (
                    'Modo PARA: validar aberturas/recortes quando a viga chega perpendicularmente e termina no pilar; '
                    'equivale às categorias “Vigas que chegam” e “Para no canto” (Modo Ini/Nova) do guia ABCD.'
                    if is_para else
                    'Modo PASSA: validar parede lateral/maior profundidade quando a viga passa ao longo da face, '
                    'e validar engolimento quando a face é “Dentro do interior” no guia ABCD.'
                )
                detail = _face_mode_rows(row, mode) + f'<div class="mode-note">{note}</div>'
                return (
                    f'<div class="mode-card"><div class="mode-title {"para" if is_para else "passa"}">{title}</div>'
                    + _mode_row(base_key, f'abcd_{mode}', badge, cls, detail)
                    + '</div>'
                )

            def _grades_info_card(row: dict, base_key: str, mode: str) -> str:
                comp, larg = _pillar_dims(row.get('_points') or [])
                is_para = mode == 'para'
                title = 'GRADES — caso a viga PARE' if is_para else 'GRADES — caso a viga PASSE'
                badge = 'GRADES PARA' if is_para else 'GRADES PASSA'
                face_rows = []
                for fid in ('A', 'B', 'C', 'D'):
                    width = _face_len(fid, comp, larg)
                    eligible = fid in ('A', 'B') or width > 50.0
                    face_rows.append((
                        f'Lado {fid}',
                        f'largura {_fmt_num(width)}cm · '
                        f'{"gera grade" if eligible else "não gera grade automática"} · '
                        f'{"face longa" if fid in ("A", "B") else "face curta >50cm exigida"}'
                    ))
                detail = _field_table(face_rows + [
                    ('topo local', 'cada sarrafo vertical termina 15cm abaixo do topo local do painel'),
                    ('largura grade', 'usa a largura do painel/trecho; se houver múltiplas grades, gaps são cotados'),
                    ('sarrafos', 'extremos isolados 7cm; centros/encontros/distância_1/distância_2 = 3,5cm'),
                    ('modo', 'abertura/recorte de chegada' if is_para else 'continuidade/engolimento preservado'),
                ])
                return (
                    f'<div class="mode-card"><div class="mode-title {"para" if is_para else "passa"}">{title}</div>'
                    + _mode_row(base_key, f'grades_{mode}', badge, 'vb-grade', detail)
                    + '</div>'
                )

            def _abcd_info_card(row: dict, pillar: dict, lbls: dict, base_key: str, mode: str) -> str:
                is_para = mode == 'para'
                title = 'ABCD — caso a viga PARE' if is_para else 'ABCD — caso a viga PASSE'
                cards = []
                for fid in ('A', 'B', 'C', 'D'):
                    entries = _entries_for_side(pillar, fid)
                    lajes = [
                        _entry_laje_detail(e) for e in entries
                        if (e.get('content_type') or 'laje') in ('laje', 'both') and e.get('laje')
                    ]
                    vigas = [
                        _entry_viga_detail(e) for e in entries
                        if (e.get('content_type') or '') in ('viga', 'both') and e.get('viga')
                    ]
                    laje_detail = (
                        '<br>'.join(html.escape(x) for x in lajes)
                        if lajes else '<span class="muted">— nenhuma</span>'
                    )
                    viga_detail = (
                        '<br>'.join(html.escape(x) for x in vigas)
                        if vigas else '<span class="muted">— nenhuma</span>'
                    )
                    interior_row = (
                        _valid_row(
                            base_key, f'abcd_{mode}_{fid}_dentro_interior',
                            'Dentro do interior', 'vb-grade', viga_detail
                        )
                        if vigas else ''
                    )
                    cards.append(
                        f'<div class="valid-card">'
                        f'<div class="valid-card-title {FACE_CLSS[fid]}">{html.escape(lbls[fid])}</div>'
                        + _valid_row(base_key, f'abcd_{mode}_{fid}_lajes', 'Lajes', 'vb-sa', laje_detail)
                        + _valid_row(base_key, f'abcd_{mode}_{fid}_vigas_passa', 'Vigas que passam', 'vb-passa', viga_detail)
                        + _valid_row(base_key, f'abcd_{mode}_{fid}_vigas_chegam', 'Vigas que chegam', 'vb-para', viga_detail)
                        + interior_row
                        + '</div>'
                    )
                return (
                    f'<div class="mode-card"><div class="mode-title {"para" if is_para else "passa"}">{title}</div>'
                    '<div class="mode-note">Formato igual ao guia ABCD: checkbox + categoria + texto interpretado.</div>'
                    f'<div class="valid-grid">{"".join(cards)}</div>'
                    '</div>'
                )

            def _grades_info_card(row: dict, base_key: str, mode: str) -> str:
                comp, larg = _pillar_dims(row.get('_points') or [])
                is_para = mode == 'para'
                title = 'GRADES — caso a viga PARE' if is_para else 'GRADES — caso a viga PASSE'
                badge = 'GRADES PARA' if is_para else 'GRADES PASSA'
                rows_html = ''
                for fid in ('A', 'B', 'C', 'D'):
                    width = _face_len(fid, comp, larg)
                    eligible = fid in ('A', 'B') or width > 50.0
                    detail = (
                        f'Lado {fid}: largura {_fmt_num(width)}cm  ·  '
                        f'{"gera grade" if eligible else "não gera grade automática"}  ·  '
                        f'{"face longa" if fid in ("A", "B") else "face curta: exige largura superior a 50cm"}'
                    )
                    rows_html += _mode_row(
                        base_key, f'grades_{mode}_{fid}', f'Lado {fid}', 'vb-grade',
                        html.escape(detail)
                    )
                rows_html += _mode_row(
                    base_key, f'grades_{mode}_topo', 'Topo local', 'vb-grade',
                    'cada sarrafo vertical termina 15cm abaixo do topo local do painel'
                )
                rows_html += _mode_row(
                    base_key, f'grades_{mode}_largura', 'Largura da grade', 'vb-grade',
                    'cada grade usa a largura do respectivo painel/trecho; quando houver múltiplas grades, as distâncias entre grades também são cotadas'
                )
                rows_html += _mode_row(
                    base_key, f'grades_{mode}_sarrafos', 'Sarrafos', 'vb-grade',
                    'extremos isolados = 7cm; centros, encontros, distância_1 e distância_2 = 3,5cm'
                )
                rows_html += _mode_row(
                    base_key, f'grades_{mode}_modo', 'Modo', 'vb-grade',
                    'abertura/recorte de chegada' if is_para else 'continuidade/engolimento preservado'
                )
                return (
                    f'<div class="mode-card"><div class="mode-title {"para" if is_para else "passa"}">{title}</div>'
                    f'<div class="mode-note">{badge}: checkbox + item de regra + texto interpretado.</div>'
                    f'{rows_html}</div>'
                )

            def _face_card_grid(row: dict, pillar: dict, lbls: dict, base_key: str, prefix: str = '') -> str:
                face_interp = _dynamic_face_interpretation(row, pillar)
                cards = []
                for fid in ('A', 'B', 'C', 'D'):
                    data = face_interp.get(fid, {})
                    lajes = data.get('lajes') or []
                    passa = data.get('passa') or []
                    chega = data.get('chega') or []
                    interior = data.get('interior') or []
                    laje_detail = (
                        '<br>'.join(html.escape(x) for x in lajes)
                        if lajes else '<span class="muted">— nenhuma</span>'
                    )
                    passa_detail = (
                        '<br>'.join(html.escape(x) for x in passa)
                        if passa else '<span class="muted">— nenhuma</span>'
                    )
                    chega_detail = (
                        '<br>'.join(html.escape(x) for x in chega)
                        if chega else '<span class="muted">— nenhuma</span>'
                    )
                    interior_detail = (
                        '<br>'.join(html.escape(x) for x in interior)
                        if interior else '<span class="muted">— nenhuma</span>'
                    )
                    key_prefix = f'{prefix}_{fid}' if prefix else fid
                    interior_row = (
                        _valid_row(
                            base_key, f'{key_prefix}_dentro_interior',
                            'Dentro do interior', 'vb-grade', interior_detail
                        )
                        if interior else ''
                    )
                    cards.append(
                        f'<div class="valid-card">'
                        f'<div class="valid-card-title {FACE_CLSS[fid]}">{html.escape(lbls[fid])}</div>'
                        + _valid_row(base_key, f'{key_prefix}_lajes', 'Lajes', 'vb-sa', laje_detail)
                        + _valid_row(base_key, f'{key_prefix}_vigas_passa', 'Vigas que passam', 'vb-passa', passa_detail)
                        + _valid_row(base_key, f'{key_prefix}_vigas_chegam', 'Vigas que chegam', 'vb-para', chega_detail)
                        + interior_row
                        + '</div>'
                    )
                return f'<div class="valid-grid">{"".join(cards)}</div>'

            def _face_validation_section(row: dict, pillar: dict, lbls: dict, base_key: str) -> str:
                return (
                    '<div class="sec"><div class="sec-title">Validação N1 — Interpretação ABCD por face</div>'
                    '<div class="sec-body">'
                    '<div style="font-size:10px;color:#777;margin-bottom:7px">'
                    'Checklist humano no formato do guia interpretacao_abcd.html: viga tem prioridade sobre laje quando há parede/chegada geométrica.</div>'
                    f'{_face_card_grid(row, pillar, lbls, base_key)}</div></div>'
                )

            def _abcd_info_card(row: dict, pillar: dict, lbls: dict, base_key: str, mode: str) -> str:
                is_para = mode == 'para'
                title = 'ABCD — caso a viga PARE' if is_para else 'ABCD — caso a viga PASSE'
                if is_para:
                    # Modo PARA é uma ficha operacional, não uma cópia da leitura N1:
                    # cada face aprova o vazio de topo e as aberturas que alimentarão
                    # o N3. A/B têm cantos AC/AD ou BC/BD; C/D nunca param.
                    face_interp = _dynamic_face_interpretation(row, pillar)
                    pilar_n3 = _load_n3_pilar_json(str(row.get('_nome') or ''))

                    def _first_number(text: str, pattern: str) -> float | None:
                        found = re.search(pattern, text)
                        if not found:
                            return None
                        try:
                            return float(found.group(1).replace(',', '.'))
                        except (TypeError, ValueError):
                            return None

                    def _fmt_cm(value: float) -> str:
                        return f'{_fmt_num(value)}cm'

                    def _vazio_topo(fid: str, data: dict[str, list[str]]) -> str:
                        lajes = data.get('lajes') or []
                        passa = data.get('passa') or []
                        interior = data.get('interior') or []
                        # "Dentro do interior" também é viga física na face: ela
                        # define o vazio local antes de qualquer laje, em A/B/C/D.
                        # Nas curtas, Viga que passa continua tendo a mesma prioridade.
                        vigas_topo = interior or (passa if fid in ('C', 'D') else [])
                        if vigas_topo:
                            details = []
                            origem = 'Dentro do interior' if interior else 'Viga que passa'
                            for viga in vigas_topo:
                                depth = _first_number(viga, r'dim:\s*[^/·]+/\s*([0-9]+(?:[.,][0-9]+)?)')
                                if depth is not None:
                                    details.append(
                                        f'{origem}: {html.escape(viga)} → vazio topo = profundidade {_fmt_cm(depth)}'
                                    )
                                else:
                                    details.append(
                                        f'{origem}: {html.escape(viga)} → vazio topo = profundidade da viga (a confirmar no SA)'
                                    )
                            suffix = (
                                '<br><span class="muted">C/D permanecem VIGA PASSA neste modo.</span>'
                                if fid in ('C', 'D') else ''
                            )
                            return '<br>'.join(details) + suffix
                        if lajes:
                            details = []
                            for laje in lajes:
                                thickness = _first_number(laje, r'esp:\s*([0-9]+(?:[.,][0-9]+)?)\s*cm')
                                if thickness is not None:
                                    details.append(
                                        f'{html.escape(laje)} → vazio topo = {_fmt_cm(thickness)} + 2cm = <b>{_fmt_cm(thickness + 2)}</b>'
                                    )
                                else:
                                    details.append(f'{html.escape(laje)} → espessura não disponível; vazio topo a confirmar')
                            return '<br>'.join(details)
                        return 'nulo → vazio topo = <b>0cm</b>'

                    _pts = row.get('_points') or pillar.get('points') or []
                    _xs = [float(p[0]) for p in _pts] if _pts else []
                    _ys = [float(p[1]) for p in _pts] if _pts else []
                    _px0, _px1 = (min(_xs), max(_xs)) if _xs else (0.0, 0.0)
                    _py0, _py1 = (min(_ys), max(_ys)) if _ys else (0.0, 0.0)
                    _vertical = (_py1 - _py0) > (_px1 - _px0)
                    _corner_tol = max(6.0, min(max(_px1 - _px0, _py1 - _py0) * 0.12, 18.0))

                    def _beam_parts(detail: str) -> tuple[str, float | None, float | None]:
                        match = re.search(
                            r'^Viga:\s*([^·]+)(?:\s*·\s*dim:\s*'
                            r'([0-9]+(?:[.,][0-9]+)?)\s*/\s*([0-9]+(?:[.,][0-9]+)?))?',
                            detail,
                        )
                        if not match:
                            return 'SEM_NOME', None, None
                        name = match.group(1).strip()
                        try:
                            width = float(match.group(2).replace(',', '.')) if match.group(2) else None
                            depth = float(match.group(3).replace(',', '.')) if match.group(3) else None
                        except (AttributeError, ValueError):
                            width = depth = None
                        return name, width, depth

                    def _segment_bbox_for_opening(seg: dict) -> tuple[float, float, float, float] | None:
                        points = [_as_point(p) for p in (seg.get('points') or [])]
                        points = [p for p in points if p is not None]
                        if len(points) < 2:
                            return None
                        return (
                            min(p[0] for p in points), min(p[1] for p in points),
                            max(p[0] for p in points), max(p[1] for p in points),
                        )

                    def _slot_for_segment(fid: str, beam_name: str, arrival: bool) -> str | None:
                        """Localiza ponta/canto pelo trecho geométrico, não pelo texto próximo."""
                        candidate_slots: list[tuple[float, str]] = []
                        normalized_name = re.sub(
                            r'(?<=\d)[AB]$', '', str(beam_name or '').strip(), flags=re.I,
                        )
                        for group in (getattr(self, '_segment_data', {}) or {}).values():
                            for seg in group or []:
                                segment_name = re.sub(
                                    r'(?<=\d)[AB]$', '',
                                    str(seg.get('beam_name') or '').strip(), flags=re.I,
                                )
                                if segment_name != normalized_name:
                                    continue
                                bb = _segment_bbox_for_opening(seg)
                                if not bb:
                                    continue
                                bx0, by0, bx1, by1 = bb
                                bw, bh = bx1 - bx0, by1 - by0
                                is_vertical = bh >= max(10.0, bw * 3.0)
                                is_horizontal = bw >= max(10.0, bh * 3.0)
                                if _vertical:
                                    # A/B são laterais longas: passagem/chegada é
                                    # vinculada à face que o trecho toca.
                                    face_x = _px0 if fid == 'A' else _px1
                                    touches_face = bx0 - _corner_tol <= face_x <= bx1 + _corner_tol
                                    if not touches_face:
                                        continue
                                    # No desenho PIL, menor Y é o canto D e maior Y
                                    # é o canto C para a cadeia de abertura A/B.
                                    if is_vertical:
                                        if abs(by1 - _py0) <= _corner_tol:
                                            candidate_slots.append((abs(by1 - _py0), 'D'))
                                        if abs(by0 - _py1) <= _corner_tol:
                                            candidate_slots.append((abs(by0 - _py1), 'C'))
                                    elif arrival and is_horizontal:
                                        mid_y = (by0 + by1) / 2.0
                                        if abs(mid_y - _py0) <= _corner_tol:
                                            candidate_slots.append((abs(mid_y - _py0), 'D'))
                                        elif abs(mid_y - _py1) <= _corner_tol:
                                            candidate_slots.append((abs(mid_y - _py1), 'C'))
                                        elif mid_y < _py0:
                                            # Chegada fora do vão, imediatamente antes
                                            # da extremidade C: ainda é abertura de
                                            # canto, nunca uma AA central.
                                            candidate_slots.append((_py0 - mid_y, 'C'))
                                        elif mid_y > _py1:
                                            candidate_slots.append((mid_y - _py1, 'D'))
                                        elif _py0 <= mid_y <= _py1:
                                            candidate_slots.append((0.0, 'central'))
                                else:
                                    face_y = _py0 if fid == 'A' else _py1
                                    touches_face = by0 - _corner_tol <= face_y <= by1 + _corner_tol
                                    if not touches_face:
                                        continue
                                    if is_horizontal:
                                        if abs(bx0 - _px1) <= _corner_tol:
                                            candidate_slots.append((abs(bx0 - _px1), 'C'))
                                        if abs(bx1 - _px0) <= _corner_tol:
                                            candidate_slots.append((abs(bx1 - _px0), 'D'))
                                    elif arrival and is_vertical:
                                        mid_x = (bx0 + bx1) / 2.0
                                        if _px0 < mid_x < _px1:
                                            candidate_slots.append((0.0, 'central'))
                        return min(candidate_slots)[1] if candidate_slots else None

                    def _pass_opening(name: str, depth: float | None) -> str:
                        if depth is None:
                            return f'{name} <span class="muted">(profundidade indisponível no SA)</span>'
                        final_depth = depth + 4.0
                        return (
                            f'{name} (Ini: 7,5×({_fmt_num(depth)}+4) = 7,5×{_fmt_num(final_depth)} '
                            f'/ Nova: 11×({_fmt_num(depth)}+4) = 11×{_fmt_num(final_depth)})'
                        )

                    def _arrival_opening(name: str, width: float | None, depth: float | None, at_corner: bool) -> str:
                        if width is None or depth is None:
                            return f'{name} <span class="muted">(seção indisponível no SA)</span>'
                        side_add = 15.0 if at_corner else 8.0  # canto = 11 + parede 4; centro = 4 + 4
                        final_width = width + side_add
                        final_depth = depth + 4.0
                        rule = '+11 +4 (canto)' if at_corner else '+4 +4 (central)'
                        return (
                            f'{name} ({_fmt_num(width)}×{_fmt_num(depth)}) → '
                            f'{_fmt_num(width)} {rule} = <b>{_fmt_num(final_width)}×{_fmt_num(final_depth)}cm</b>'
                        )

                    def _corner_openings(fid: str, vigas: list[str], kind: str) -> str:
                        is_arrival = kind == 'chega'
                        if fid not in ('A', 'B'):
                            if not is_arrival:
                                return '<span class="muted">não se aplica: C/D sempre passam.</span>'
                            if not vigas:
                                return '<span class="muted">nenhuma viga chega nesta face curta.</span>'
                            lines = []
                            for viga in vigas:
                                name, width, depth = _beam_parts(viga)
                                lines.append('Chegada ' + html.escape(fid) + ': ' + _arrival_opening(html.escape(name), width, depth, False))
                            return '<br>'.join(lines)

                        c1, c2 = ('AC', 'AD') if fid == 'A' else ('BC', 'BD')
                        slots = {c1: [], c2: []}
                        if is_arrival:
                            slots[f'{fid}{fid}'] = []  # AA ou BB: chegada central
                        for viga in vigas:
                            name, width, depth = _beam_parts(viga)
                            position = _slot_for_segment(fid, name, is_arrival)
                            if position == 'C':
                                slot = c1
                            elif position == 'D':
                                slot = c2
                            elif is_arrival:
                                slot = f'{fid}{fid}'
                            else:
                                # Uma viga que passa, mas sem término no canto, não
                                # cria abertura no modo PARA.
                                continue
                            formula = (
                                _arrival_opening(html.escape(name), width, depth, position in ('C', 'D'))
                                if is_arrival else _pass_opening(html.escape(name), depth)
                            )
                            slots[slot].append(formula)
                        rows = []
                        for slot, values in slots.items():
                            value = '<br>'.join(values) if values else 'nulo'
                            rows.append(f'Abertura {slot}: {value}')
                        return '<br>'.join(rows)

                    def _pillar_height_detail() -> str:
                        saida = pilar_n3.get('nivel_saida')
                        chegada = pilar_n3.get('nivel_chegada')
                        altura = pilar_n3.get('altura')
                        if saida is None or chegada is None:
                            return (
                                f'Nível SA: {html.escape(str(row.get("Nível") or "—"))} · '
                                '<span class="muted">níveis de saída/chegada ainda não disponíveis no payload.</span>'
                            )
                        try:
                            calc_altura = abs(float(saida) - float(chegada))
                            altura_txt = _fmt_cm(float(altura)) if altura is not None else _fmt_cm(calc_altura)
                            return (
                                f'Nível de saída: <b>{_fmt_cm(float(saida))}</b> · '
                                f'Nível de chegada: <b>{_fmt_cm(float(chegada))}</b> · '
                                f'Altura: <b>{altura_txt}</b> '
                                f'<span class="muted">(saída − chegada = {_fmt_cm(calc_altura)}; conversão do SA)</span>'
                            )
                        except (TypeError, ValueError):
                            return '<span class="muted">níveis do pilar indisponíveis para cálculo.</span>'

                    cards = []
                    for fid in ('A', 'B', 'C', 'D'):
                        data = face_interp.get(fid, {})
                        passa = data.get('passa') or []
                        chega = data.get('chega') or []
                        cards.append(
                            f'<div class="valid-card">'
                            f'<div class="valid-card-title {FACE_CLSS[fid]}">{html.escape(lbls[fid])}</div>'
                            + _valid_row(base_key, f'abcd_para_{fid}_vazio_topo', 'Vazio topo', 'vb-sa', _vazio_topo(fid, data))
                            + _valid_row(base_key, f'abcd_para_{fid}_aberturas_param', 'Aberturas vigas que param', 'vb-para', _corner_openings(fid, passa, 'passa'))
                            + _valid_row(base_key, f'abcd_para_{fid}_aberturas_chegam', 'Aberturas vigas que chegam', 'vb-para', _corner_openings(fid, chega, 'chega'))
                            + '</div>'
                        )
                    return (
                        f'<div class="mode-card"><div class="mode-title para">{title}</div>'
                        '<div class="mode-note">A/B: vazio de topo pela laje (nulo = 0; laje = espessura + 2). '
                        'C/D: a viga que passa tem prioridade sobre laje e nunca para.</div>'
                        + _valid_row(base_key, 'abcd_para_altura_pilar', 'Altura do pilar', 'vb-sa', _pillar_height_detail())
                        + f'<div class="valid-grid">{"".join(cards)}</div></div>'
                    )
                # PASSA: ficha operacional distinta de PARA.
                if not is_para:
                    face_interp = _dynamic_face_interpretation(row, pillar)
                    pilar_n3 = _load_n3_pilar_json(str(row.get('_nome') or ''))

                    def _dim(detail: str) -> tuple[float | None, float | None]:
                        match = re.search(r'dim:\s*([0-9.,]+)\s*/\s*([0-9.,]+)', detail)
                        if not match:
                            return None, None
                        return float(match.group(1).replace(',', '.')), float(match.group(2).replace(',', '.'))

                    def _topo_passa(data: dict[str, list[str]]) -> tuple[str, float | None, list[str]]:
                        passes = (data.get('passa') or []) + (data.get('interior') or [])
                        ranked = [(_dim(item)[1], item) for item in passes]
                        ranked = [(depth, item) for depth, item in ranked if depth is not None]
                        if ranked:
                            depth, item = max(ranked, key=lambda pair: pair[0])
                            return f'Viga que passa mais profunda: {html.escape(item)} → vazio topo = <b>{_fmt_num(depth)}cm</b>', depth, passes
                        lajes = data.get('lajes') or []
                        if lajes:
                            return f'Laje: {"<br>".join(html.escape(item) for item in lajes)} → vazio topo pela laje', None, passes
                        return 'nulo → vazio topo = <b>0cm</b>', None, passes

                    def _chegadas_passa(data: dict[str, list[str]], ref_depth: float | None) -> str:
                        arrivals = data.get('chega') or []
                        if not arrivals:
                            return '<span class="muted">nenhuma viga chega nesta face.</span>'
                        answers = []
                        for arrival in arrivals:
                            width, depth = _dim(arrival)
                            if ref_depth is not None and depth is not None and depth <= ref_depth:
                                answers.append(
                                    f'{html.escape(arrival)}<br><b>Neutralizada:</b> profundidade da chegada '
                                    f'({_fmt_num(depth)}cm) ≤ viga que passa ({_fmt_num(ref_depth)}cm); não cria abertura.'
                                )
                            elif width is not None and depth is not None:
                                answers.append(
                                    f'{html.escape(arrival)}<br><b>Abertura ativa:</b> regra PARA por canto '
                                    f'(largura {_fmt_num(width)} +11 +4 no canto, ou +4 +4 central; profundidade {_fmt_num(depth)} +4).'
                                )
                            else:
                                answers.append(f'{html.escape(arrival)}<br><span class="muted">seção indisponível para a regra condicional.</span>')
                        return '<br>'.join(answers)

                    def _altura_passa() -> str:
                        try:
                            saida = float(pilar_n3.get('nivel_saida'))
                            chegada = float(pilar_n3.get('nivel_chegada'))
                            return f'Nível de saída: <b>{_fmt_num(saida)}cm</b> · Nível de chegada: <b>{_fmt_num(chegada)}cm</b> · Altura: <b>{_fmt_num(abs(saida-chegada))}cm</b>'
                        except (TypeError, ValueError):
                            return f'Nível SA: {html.escape(str(row.get("Nível") or "—"))}'

                    cards = []
                    for fid in ('A', 'B', 'C', 'D'):
                        vazio, ref_depth, passes = _topo_passa(face_interp.get(fid, {}))
                        ref_detail = '<br>'.join(html.escape(item) for item in passes) or '<span class="muted">— nenhuma</span>'
                        cards.append(
                            f'<div class="valid-card"><div class="valid-card-title {FACE_CLSS[fid]}">{html.escape(lbls[fid])}</div>'
                            + _valid_row(base_key, f'abcd_passa_{fid}_vazio_topo', 'Vazio topo', 'vb-passa', vazio)
                            + _valid_row(base_key, f'abcd_passa_{fid}_referencia', 'Viga que passa — referência', 'vb-passa', ref_detail)
                            + _valid_row(base_key, f'abcd_passa_{fid}_chegadas', 'Vigas que chegam', 'vb-para', _chegadas_passa(face_interp.get(fid, {}), ref_depth))
                            + '</div>'
                        )
                    return (
                        f'<div class="mode-card"><div class="mode-title passa">{title}</div>'
                        '<div class="mode-note">Vazio topo: maior profundidade de viga que passa → laje → nulo. Não há viga que para. Chegada menor ou igual à viga passante é neutralizada.</div>'
                        + _valid_row(base_key, 'abcd_passa_altura_pilar', 'Altura do pilar', 'vb-sa', _altura_passa())
                        + f'<div class="valid-grid">{"".join(cards)}</div></div>'
                    )

                return (
                    f'<div class="mode-card"><div class="mode-title {"para" if is_para else "passa"}">{title}</div>'
                    '<div class="mode-note">Mesmo motor dinâmico da ficha N1: separa lajes, vigas que passam, vigas que chegam e dentro do interior.</div>'
                    f'{_face_card_grid(row, pillar, lbls, base_key, f"abcd_{mode}")}'
                    '</div>'
                )

            def _page(row: dict, idx: int) -> str:
                nome    = row['_nome']
                classif = row.get('Classificação') or 'INDETERMINADO'
                fmt     = row.get('Formato', '—')
                nivel   = row.get('Nível', '—')
                aten    = row.get('Atenção', '')
                pts     = row.get('_points') or []
                pkey    = row.get('_key') or nome
                pillar  = self._pillar_report.get(pkey) or self._pillar_report.get(nome, {})
                cur_dir = os.path.dirname(nav_entries[idx][3])

                # Sidebar
                cur_grp = None
                sb_items = []
                for j, (jnome, jclassif, jcs, jabs) in enumerate(nav_entries):
                    if jclassif != cur_grp:
                        sb_items.append(
                            f'<li><div class="grp">{html.escape(jclassif)}</div></li>')
                        cur_grp = jclassif
                    try:
                        rp = os.path.relpath(jabs, cur_dir).replace('\\', '/')
                    except ValueError:
                        rp = f'../../{jcs}/{jnome}.html'
                    act = ' class="active"' if j == idx else ''
                    sb_items.append(
                        f'<li{act} data-pilar="{html.escape(jnome)}">'
                        f'<a href="{html.escape(rp)}">'
                        f'<span class="erro-flag" style="display:none">⚠️ </span>'
                        f'{html.escape(jnome)}</a></li>')
                sidebar = (
                    f'<aside class="sidebar"><h3>Pilares ({len(rows)})</h3>'
                    f'<ul>{"".join(sb_items)}</ul></aside>'
                    + _sidebar_error_flags_script_pil(self)
                )

                # Nav bar
                def _nav_lnk(j: int, label: str) -> str:
                    if j < 0 or j >= len(nav_entries):
                        return ''
                    _, _, jcs, jabs = nav_entries[j]
                    try:
                        rp = os.path.relpath(jabs, cur_dir).replace('\\', '/')
                    except ValueError:
                        rp = f'../../{jcs}/{nav_entries[j][0]}.html'
                    return f'<a class="nav-arrow" href="{html.escape(rp)}">{html.escape(label)}</a>'

                prev_lnk = _nav_lnk(idx - 1, f'← {nav_entries[idx-1][0]}') if idx > 0 else ''
                next_lnk = _nav_lnk(idx + 1, f'{nav_entries[idx+1][0]} →') if idx < len(nav_entries)-1 else ''
                nav_bar = (
                    f'<div class="nav-bar">{prev_lnk}'
                    f'<span class="nav-pos"><b>{html.escape(nome)}</b>'
                    f' ({idx+1}/{len(rows)})'
                    f'<span class="tag">{html.escape(classif)}</span>'
                    f'<span class="tag">{html.escape(fmt)}</span>'
                    f'<span class="tag">{html.escape(nivel)}</span>'
                    f'</span>{next_lnk}</div>'
                )

                # Identidade
                at_key = f'aten_{slug}_{nome}'.replace(' ', '_')
                ident_section = (
                    '<div class="sec"><div class="sec-title">Identidade</div>'
                    '<div class="sec-body"><table>'
                    f'<tr><td style="color:#666;width:90px">Nome</td>'
                    f'<td><b>{html.escape(nome)}</b></td></tr>'
                    f'<tr><td style="color:#666">Classificação</td>'
                    f'<td>{html.escape(classif)}</td></tr>'
                    f'<tr><td style="color:#666">Formato</td>'
                    f'<td>{html.escape(fmt)}</td></tr>'
                    f'<tr><td style="color:#666">Nível</td>'
                    f'<td>{html.escape(nivel)}</td></tr>'
                    f'<tr><td style="color:#666;vertical-align:top">Atenção</td>'
                    f'<td><div class="atencao-cell" contenteditable="true" '
                    f'data-atkey="{html.escape(at_key)}" data-sa="{html.escape(aten)}" '
                    f'onblur="saveAten(this)" title="Atenção — clique para editar">'
                    f'{html.escape(aten)}</div></td></tr>'
                    '</table></div></div>'
                )

                # Faces ABCD — labels e diagrama adaptados à orientação
                _is_vert_row = True
                if pts:
                    try:
                        _xs = [float(p[0]) for p in pts]
                        _ys = [float(p[1]) for p in pts]
                        _is_vert_row = (max(_ys) - min(_ys)) > (max(_xs) - min(_xs))
                    except Exception:
                        pass
                _lbls = _VERT_LBLS if _is_vert_row else _HORIZ_LBLS
                face_cards = ''.join(
                    f'<div class="face-card {FACE_CLSS[fid]}">'
                    f'<div class="face-label">{html.escape(_lbls[fid])}</div>'
                    f'<div class="face-val">'
                    f'{html.escape((row.get(f"Lado {fid}") or "nulo").strip()).replace(chr(10), "<br>")}'
                    f'</div></div>'
                    for fid in ('A', 'B', 'C', 'D')
                )
                orient_diag = _orient_diagram(pts, nome, fmt)
                faces_section = (
                    '<div class="sec"><div class="sec-title">Faces ABCD</div>'
                    f'<div class="sec-body">{orient_diag}'
                    f'<div class="face-grid">{face_cards}</div></div></div>'
                )
                valid_base_key = f'{self._obra}_{self._pavimento}_{slug}_{nome}'.replace(' ', '_')
                face_validation_section = _face_validation_section(row, pillar, _lbls, valid_base_key)

                # Foto N1
                geo_b64 = self._render_pilar_dxf_context_b64(
                    pts, width=1820, height=1300, fmt='svg'
                ) if pts else ''
                geo_fmt = 'svg'
                if not geo_b64:
                    geo_b64 = _photo(pts)
                    geo_fmt = 'png'
                foto_n1 = (
                    '<div class="sec"><div class="sec-title">Foto N1 (SA) — Contexto DXF</div>'
                    f'<div class="sec-body"><div class="img-wrap">'
                    f'{_embed_visual(geo_b64, geo_fmt, "img-geo", "N1")}'
                    f'</div></div></div>'
                ) if geo_b64 else ''

                # N3 / N4
                def _views_sec(n4: bool) -> str:
                    tag      = 'N4' if n4 else 'N3'
                    subtitle = 'Robô via N2 (CE DXF)' if n4 else 'Robô via N1 (Fase-4→DXF)'
                    img_cls  = 'img-n4' if n4 else 'img-n3'
                    at_k     = (f'aten_{"n4" if n4 else "n3"}_{self._obra}_{self._pavimento}_{nome}'
                                ).replace(' ', '_')
                    views_html = ''
                    variant_results = (
                        {
                            mode: (
                                _pl_n3_cache.get((nome, mode))
                                or _materialize_n3_variant(row, pillar, mode)
                            )
                            for mode in ('para', 'passa')
                        }
                        if not n4 else {}
                    )
                    view_specs = (
                        [
                            ('CIMA', 'CIMA', _cima_info_card(row, valid_base_key), None),
                            ('ABCD', 'ABCD — modo PARA', _abcd_info_card(row, pillar, _lbls, valid_base_key, 'para'), 'para'),
                            ('ABCD', 'ABCD — modo PASSA', _abcd_info_card(row, pillar, _lbls, valid_base_key, 'passa'), 'passa'),
                            ('GRADES', 'GRADES — modo PARA', _grades_info_card(row, valid_base_key, 'para'), 'para'),
                            ('GRADES', 'GRADES — modo PASSA', _grades_info_card(row, valid_base_key, 'passa'), 'passa'),
                        ]
                        if not n4 else
                        [(vt, vt, '', None) for vt in ('CIMA', 'ABCD', 'GRADES')]
                    )
                    for vt, view_label, prefix_html, mode in view_specs:
                        variant = variant_results.get(mode, {}) if mode else {}
                        variant_path = (variant.get('paths') or {}).get(vt.lower())
                        p = variant_path or self._find_pilar_dxf(vt, nome, n4=n4)
                        artifact_html = ''
                        if mode:
                            contract = variant.get('contract') or {}
                            json_path = (variant.get('paths') or {}).get('json')
                            artifact_html = (
                                '<div class="mode-note">'
                                f'Contrato derivado: <b>{html.escape(str(contract.get("schema") or "ausente"))}</b> · '
                                f'modo <b>{html.escape(str(contract.get("modo_semantico") or mode).upper())}</b> · '
                                f'artefato isolado: <b>{"sim" if variant_path else "não"}</b>'
                                + (f' · JSON: {html.escape(os.path.basename(json_path))}' if json_path else '')
                                + '</div>'
                            )
                        b64v = self._render_ezdxf_b64(
                            p, width=1500, height=1100, fmt='svg'
                        ) if p else ''
                        if b64v:
                            views_html += (
                                f'<div class="view-block">'
                                f'{prefix_html}'
                                f'{artifact_html}'
                                f'<div class="view-label">{html.escape(view_label)}</div>'
                                f'{_embed_visual(b64v, "svg", img_cls, vt)}'
                                f'</div>'
                            )
                        else:
                            views_html += (f'<div class="view-block">'
                                           f'{prefix_html}'
                                           f'{artifact_html}'
                                           f'<div class="view-label" style="color:#444">sem {html.escape(view_label)}</div>'
                                           f'</div>')
                    aten_v = (
                        f'<div style="margin-top:8px">'
                        f'<div style="font-size:9px;color:#666;margin-bottom:2px">Atenção {tag}</div>'
                        f'<div class="atencao-cell" contenteditable="true" '
                        f'data-atkey="{html.escape(at_k)}" onblur="saveAten(this)" '
                        f'title="Anotação {tag} — {html.escape(nome)}"></div></div>'
                    )
                    return (
                        f'<div class="sec"><div class="sec-title">{tag} — {subtitle}</div>'
                        f'<div class="sec-body">'
                        f'<div class="views-row">{views_html}</div>'
                        f'{aten_v}</div></div>'
                    )

                n3_section = _views_sec(n4=False)
                n4_section = _views_sec(n4=True)

                # Foto N2
                n2b64 = self._render_n2_recorte_b64(
                    nome, width=1400, height=1000, fmt='svg'
                )
                foto_n2 = (
                    '<div class="sec"><div class="sec-title">Foto N2 — Recorte STOG</div>'
                    f'<div class="sec-body"><div class="img-wrap">'
                    f'{_embed_visual(n2b64, "svg", "img-n2", "N2")}'
                    f'</div></div></div>'
                ) if n2b64 else ''

                # Fichas
                n1f = self._n1_ficha_html_pilar(nome)
                n2f = self._n2_ficha_html('PIL', nome)
                n3f = self._n3_ficha_html_pilar(nome)
                fichas = (
                    '<div class="sec"><div class="sec-title">Fichas N1 / N2 / N3</div>'
                    '<div class="sec-body"><div class="fichas-grid">'
                    f'<div><div class="ficha-col-title">Ficha N1 (SA)</div>'
                    f'<div class="ficha-cell">{n1f}</div></div>'
                    f'<div><div class="ficha-col-title">Ficha N2</div>'
                    f'<div class="ficha-cell">{n2f}</div></div>'
                    f'<div><div class="ficha-col-title">Ficha N3 (JSON)</div>'
                    f'<div class="ficha-cell">{n3f}</div></div>'
                    '</div></div></div>'
                )

                main = (nav_bar + ident_section + faces_section +
                        face_validation_section +
                        foto_n1 + n3_section + n4_section + foto_n2 + fichas +
                        '<pre id="_aten_export" style="display:none"></pre>'
                        '<button onclick="exportAnotacoes()" style="margin:12px 0;'
                        'background:#2a2a00;color:#f0b840;border:1px solid #554400;'
                        'padding:3px 10px;cursor:pointer;font-size:10px">Exportar Anotações</button>'
                        + _error_marker_block_pil(self, nome))

                return (
                    f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
                    f'<title>{html.escape(nome)} — {html.escape(title)}</title>'
                    f'<style>{_page_css}</style>{js}</head>'
                    f'<body>{sidebar}'
                    f'<div class="main-wrap"><div class="main-content">'
                    f'<h2 style="font-size:13px;color:#7eb8f7;margin:0 0 8px">'
                    f'{html.escape(nome)}'
                    f'<span class="tag">{html.escape(classif)}</span>'
                    f'<span class="tag">{html.escape(fmt)}</span>'
                    f'</h2>{main}</div></div></body></html>'
                )

            # Gerar todas as páginas
            for idx, row in enumerate(rows):
                nome_r = row['_nome']
                _, _, _, abs_p = nav_entries[idx]
                with open(abs_p, 'w', encoding='utf-8') as f:
                    f.write(_page(row, idx))
                print(f'[HTML] {slug} {idx+1}/{len(rows)}: {nome_r}', flush=True)

            # index.html do grupo (pilares agrupados por classificação)
            seen_grp: dict[str, list] = {}
            for row in rows:
                c = row.get('Classificação') or 'INDETERMINADO'
                seen_grp.setdefault(c, []).append(row)
            groups_html = ''
            for grp_c, grp_rows in seen_grp.items():
                cs = _classif_slug(grp_c)
                items_li = ''.join(
                    f'<li><a href="{html.escape(cs)}/{html.escape(r["_nome"])}.html">'
                    f'{html.escape(r["_nome"])}</a>'
                    f' <span style="color:#555;font-size:10px">'
                    f'{html.escape(r.get("Formato",""))} | {html.escape(r.get("Nível",""))}'
                    f'</span></li>'
                    for r in grp_rows
                )
                groups_html += (
                    f'<h2 style="color:#4fc3a1;font-size:12px;margin:12px 0 4px">'
                    f'{html.escape(grp_c)} ({len(grp_rows)})</h2>'
                    f'<ul style="line-height:1.9">{items_li}</ul>'
                )
            idx_doc = (
                '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
                f'<title>Índice — {html.escape(title)}</title>'
                '<style>body{background:#1a1a1a;color:#c8c8c8;font:12px monospace;margin:16px}'
                'a{color:#7eb8f7}li{margin:2px 0}</style></head>'
                f'<body><h1 style="color:#7eb8f7;font-size:14px">Índice — {html.escape(title)}</h1>'
                f'<p style="color:#777;font-size:10px">Obra: {html.escape(self._obra)} | '
                f'Pavimento: {html.escape(self._pavimento)} | {len(rows)} itens</p>'
                f'{groups_html}</body></html>'
            )
            idx_path = os.path.join(output_dir, slug, 'index.html')
            with open(idx_path, 'w', encoding='utf-8') as f:
                f.write(idx_doc)

            return (f'{slug}/index.html', title, len(rows))

        generated: list[tuple[str, str, int]] = []
        try:
            # Laterais LV: consolidadas ANTES do loop genérico — as 4 combinações
            # lado×comportamento (lateral_a_para/b_para/a_passa/b_passa) viram
            # seções "Lado A"/"Lado B" de UMA página por viga, não 4 relatórios
            # tabulares separados (ver write_lateral_pages e ARETE-LOOP-
            # PROCEDIMENTO-GERAL.md §5.2).
            _lateral_kinds = (
                'lateral_a_para', 'lateral_b_para',
                'lateral_a_passa', 'lateral_b_passa',
            )
            _lateral_rows_by_kind = {
                slug: rows
                for slug, _title, _headers, rows, _extra_th, _extra_td_fn in reports
                if slug in _lateral_kinds
            }
            if _include('laterais_viga') and any(_lateral_rows_by_kind.get(k) for k in _lateral_kinds):
                from src.ui.widgets.preficha_lateral_html import write_lateral_pages
                generated.append(write_lateral_pages(
                    dialog=self,
                    title='Laterais de Viga',
                    rows_by_kind=_lateral_rows_by_kind,
                    output_dir=output_dir,
                    page_css=_page_css,
                    javascript=js,
                    photo_fn=_photo,
                    metrics_fn=_segment_geometry_metrics,
                ))

            for slug, title, headers, rows, extra_th, extra_td_fn in reports:
                if slug in _lateral_kinds:
                    continue
                # Pilares: gera página individual por item
                if slug in ('pilares', 'pilares_especiais'):
                    if rows:
                        generated.append(_write_pilar_pages(slug, title, rows))
                    continue
                if slug == 'fundo':
                    if rows:
                        from src.ui.widgets.preficha_fundo_html import write_fundo_pages
                        generated.append(write_fundo_pages(
                            dialog=self,
                            title=title,
                            rows=rows,
                            output_dir=output_dir,
                            page_css=_page_css,
                            javascript=js,
                            photo_fn=_photo,
                            metrics_fn=_segment_geometry_metrics,
                        ))
                    continue
                if slug == 'lajes':
                    if rows:
                        from src.ui.widgets.preficha_laje_html import write_laje_pages
                        generated.append(write_laje_pages(
                            dialog=self,
                            title=title,
                            rows=rows,
                            output_dir=output_dir,
                            page_css=_page_css,
                            javascript=js,
                            photo_fn=_photo,
                            metrics_fn=_segment_geometry_metrics,
                        ))
                    continue
                if slug == 'visao_cortes' and sections is not None:
                    # Não selecionável por --secao; cai aqui no bloco genérico
                    # (sem guarda de `rows`, ao contrário de pilares/lajes/fundo),
                    # então precisa de exclusão explícita para não sobrar um
                    # preficha_visao_cortes.html vazio numa rodada filtrada.
                    continue

                body_parts = []
                for row in rows:
                    cells = ''.join(_render_td(h, row, slug) for h in headers)
                    extra = extra_td_fn(row) if extra_td_fn else ''
                    body_parts.append(f"<tr>{cells}{extra}</tr>")
                th_row = ''.join(f'<th>{html.escape(h)}</th>' for h in headers) + (extra_th or '')
                document = (
                    f'<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">'
                    f'<title>{html.escape(title)}</title><style>{css}</style>{js}</head>'
                    f'<body><h1>{html.escape(title)}</h1>'
                    f'<div class="meta">Obra: <b>{html.escape(self._obra)}</b> | '
                    f'Pavimento: <b>{html.escape(self._pavimento)}</b> | '
                    f'Gerado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | '
                    f'Registros: {len(rows)} | '
                    f'<button onclick="exportAnotacoes()" style="background:#2a2a00;color:#f0b840;border:1px solid #554400;padding:2px 8px;cursor:pointer">Exportar Anotações</button>'
                    f'</div>'
                    f'<pre id="_aten_export" style="display:none"></pre>'
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
