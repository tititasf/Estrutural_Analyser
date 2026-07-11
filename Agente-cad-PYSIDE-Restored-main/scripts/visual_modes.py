"""Perfis visuais dos geradores DXF de Pilares e Vigas.

NOVA e o caminho de producao atual e, por contrato, nao altera o documento.
INI e a reproducao dos templates/SCR legados:

* sarrafos **sólidos** (aberturas, horizontais sob vazio de laje/viga passante,
  fustes C/D, grades) viram **MLINE** central (estilo SAR3, fundo solido);
* sarrafos **HIDDEN / DASHED** (ex. Sarrafo de Pressão) **permanecem LINE**
  — nao viram MLINE;
* a escala da MLINE corresponde a largura geometrica/nominal do sarrafo;
* entidades passam a usar cor BYLAYER;
* layers seguem os nomes e cores encontrados nos templates dos robos.

O perfil e aplicado somente ao final da geracao. Assim, refinamentos do INI
nao podem mudar geometria, layers ou cores do modo NOVA.
A geometria (malha, aberturas, rebaixo, seccionamento) e a mesma para PARA e
PASSA; so muda o perfil visual INI vs NOVA no final.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable


VISUAL_MODE_NOVA = "NOVA"
VISUAL_MODE_INI = "INI"
VISUAL_MODES = (VISUAL_MODE_NOVA, VISUAL_MODE_INI)

# Linetypes que ficam como LINE no INI (nunca MLINE).
_LINE_KEEP_LINETYPES = (
    "HIDDEN",
    "DASHED",
    "DASHDOT",
    "CENTER",
    "PHANTOM",
    "DIVIDE",
    "DOT",
    "BORDER",
    "ACAD_ISO02W100",
    "ACAD_ISO03W100",
    "ACAD_ISO04W100",
)


def normalize_visual_mode(value: object) -> str:
    mode = str(value or VISUAL_MODE_NOVA).strip().upper()
    if mode not in VISUAL_MODES:
        raise ValueError(f"Modo visual invalido: {value!r}")
    return mode


# Cores ACI observadas nos moldes/DXFs dos robos SCR.
_LEGACY_COLORS = {
    "0": 7,
    "Painéis": 255,
    "hachura-chapa": 7,
    "Hachura": 251,
    "barra_ancoragem": 224,
    "BARRA_ANCORAGEM": 224,
    "COTA": 241,
    "cota": 241,
    "cotaS": 241,
    "NOMENCLATURA": 7,
    "nomenclatura": 7,
    "DIVISAO": 142,
    "Nível": 3,
    "pedireito": 3,
    "CONCRETO": 251,
    "concreto": 251,
    "GRAVATA": 224,
    "perfil_metalico": 224,
    "Perfil Metálico": 224,
    "SARRAFO": 30,
    "SARRAFO_2_2X7": 30,
    "SARRAFO_2_2x7": 30,
    "SARRAFO_2_2x5": 91,
    "SARR_2.2x7": 30,
    "SARR_2.2x10": 60,
    "SARR_2.2x5": 91,
    "SARR_2.2x3.5": 71,
    "SARR_3.5x7": 7,
    "SARR_7x7": 100,
    "MEIOPONTALETE": 160,
    "SARRAFO_PRESSAO": 1,
    "SARRAFO DE PRESSAO": 1,
    "Sarrafo_de_pressao": 1,
}


_INI_LAYER_MAP = {
    "PL": {
        "paineis": "hachura-chapa",
        "painéis": "hachura-chapa",
        "sarrafo": "SARRAFO_2_2X7",
        "sarr_2.2x7": "SARRAFO_2_2X7",
        # GRADES usa classes fisicamente e visualmente distintas. Preservar
        # essas layers faz a MLINE herdar a cor correta por BYLAYER.
        "sarr_2.2x10": "SARR_2.2x10",
        "sarr_3.5x7": "SARR_3.5x7",
        "sarrafo de pressão": "Sarrafo_de_pressao",
        "sarrafo de pressao": "Sarrafo_de_pressao",
        "sarrafo_de_pressao": "Sarrafo_de_pressao",
        "sarrafo_pressao": "Sarrafo_de_pressao",
        "gravata": "perfil_metalico",
        "perfil metálico": "perfil_metalico",
        "hachura": "barra_ancoragem",
        "nível": "pedireito",
    },
    "LV": {
        "sarr_2.2x7": "SARRAFO_2_2X7",
        "sarr_2.2x10": "SARR_2.2x10",
        "sarr_2.2x5": "SARRAFO_2_2x5",
        "sarr_2.2x3.5": "SARR_2.2x3.5",
        "sarr_3.5x7": "SARR_3.5x7",
        "sarrafo_2_2x7": "SARRAFO_2_2X7",
        "meiopontalete": "MEIOPONTALETE",
        "5": "DIVISAO",
        "cota": "cota",
    },
    "FV": {
        "sarr_2.2x7": "SARRAFO_2_2X7",
        "sarr_2.2x10": "SARR_2.2x10",
        "sarr_2.2x5": "SARRAFO_2_2x5",
        "sarr_5cm": "SARRAFO_2_2x5",
        "sarr_contorno_10cm": "SARRAFO_2_2x5",
        "sarrafo de pressao": "Sarrafo_de_pressao",
        "nomenclatura": "0",
        "5": "DIVISAO",
        "cota": "cota",
    },
}


@dataclass
class VisualModeStats:
    mode: str
    robot_class: str
    remapped_entities: int = 0
    mlines_created: int = 0
    rectangles_collapsed: int = 0


def _ensure_layer(doc, name: str) -> None:
    color = _LEGACY_COLORS.get(name, 7)
    if name not in doc.layers:
        doc.layers.add(name, color=color)
    else:
        doc.layers.get(name).dxf.color = color


def _ensure_sar3_style(doc) -> None:
    if "SAR3" in doc.mline_styles:
        style = doc.mline_styles.get("SAR3")
    else:
        style = doc.mline_styles.new("SAR3")
    if len(style.elements.elements) != 2:
        style.elements.elements.clear()
        style.elements.append(-0.5, color=256, linetype="BYLAYER")
        style.elements.append(0.5, color=256, linetype="BYLAYER")
    style.dxf.flags = style.MITER | style.FILL
    style.dxf.fill_color = 256


def _polyline_vertices(entity) -> list[tuple[float, float]]:
    kind = entity.dxftype()
    if kind == "LINE":
        return [
            (float(entity.dxf.start.x), float(entity.dxf.start.y)),
            (float(entity.dxf.end.x), float(entity.dxf.end.y)),
        ]
    if kind == "LWPOLYLINE":
        return [(float(x), float(y)) for x, y, *_ in entity.get_points()]
    return []


def _is_sarrafo_layer(layer: str) -> bool:
    norm = str(layer or "").casefold()
    return "sarr" in norm or norm == "meiopontalete"


def _is_pressure_layer(layer: str) -> bool:
    return "press" in str(layer or "").casefold()


def _entity_effective_linetype(doc, entity) -> str:
    """Resolve linetype efetivo (entity ou BYLAYER → layer)."""
    lt = str(entity.dxf.get("linetype", "BYLAYER") or "BYLAYER").upper()
    if lt not in ("BYLAYER", "BYBLOCK", ""):
        return lt
    try:
        layer = doc.layers.get(entity.dxf.layer)
        return str(getattr(layer.dxf, "linetype", None) or "CONTINUOUS").upper()
    except Exception:
        return "CONTINUOUS"


def _is_hidden_or_dashed(doc, entity) -> bool:
    """Pressão / HIDDEN / DASHED permanecem LINE no INI (nao viram MLINE)."""
    if _is_pressure_layer(str(entity.dxf.get("layer", ""))):
        return True
    lt = _entity_effective_linetype(doc, entity)
    return any(token in lt for token in _LINE_KEEP_LINETYPES)


def _should_convert_to_mline(doc, entity, layer: str) -> bool:
    """MLINE só para sarrafo sólido (abertura, vazio laje, passante, C/D, grades)."""
    if not _is_sarrafo_layer(layer):
        return False
    if entity.dxftype() not in ("LINE", "LWPOLYLINE"):
        return False
    if _is_hidden_or_dashed(doc, entity):
        return False
    return True


def _is_lv_layer_sentinel(entity) -> bool:
    """Reconhece as linhas de presenca de layer emitidas fora do desenho."""
    if entity.dxftype() != "LINE":
        return False
    p0, p1 = _line_points(entity)
    return (
        max(p0[0], p1[0]) <= -8000.0
        and abs(p0[1]) <= 1e-6
        and abs(p1[1]) <= 1e-6
        and abs(abs(p1[0] - p0[0]) - 10.0) <= 1e-6
    )


def _axis_aligned_rectangle(vertices: list[tuple[float, float]],
                            tolerance: float = 1e-4):
    if len(vertices) < 4:
        return None
    points = vertices[:-1] if vertices[0] == vertices[-1] else vertices
    if len(points) != 4:
        return None
    xs = sorted({round(point[0], 4) for point in points})
    ys = sorted({round(point[1], 4) for point in points})
    if len(xs) != 2 or len(ys) != 2:
        return None
    corners = {(x, y) for x in xs for y in ys}
    actual = {(round(x, 4), round(y, 4)) for x, y in points}
    if corners != actual:
        return None
    width, height = xs[1] - xs[0], ys[1] - ys[0]
    if width <= tolerance or height <= tolerance:
        return None
    return xs[0], ys[0], xs[1], ys[1]


def _centerline_from_bbox(box):
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    if width >= height:
        cy = (y0 + y1) / 2.0
        return [(x0, cy), (x1, cy)], height
    cx = (x0 + x1) / 2.0
    return [(cx, y0), (cx, y1)], width


def _centerline_for_visual_class(box, layer: str, robot_class: str):
    """Resolve secoes cuja orientacao nao pode ser inferida pelo lado maior."""
    x0, y0, x1, y1 = box
    width, height = x1 - x0, y1 - y0
    layer_norm = str(layer or "").casefold()
    if (
        robot_class == "LV"
        and layer_norm == "sarrafo_2_2x7"
        and width > 0
        and height > 0
        and 0.75 <= width / height <= 1.25
    ):
        # Na Visao Corte o eixo atravessa os 4 cm do painel e o perfil
        # SAR3 abre 4.4 cm na vertical, conforme o SCR (_CMLSCALE 4.400).
        cy = (y0 + y1) / 2.0
        return [(x0, cy), (x1, cy)], height
    return _centerline_from_bbox(box)


def _line_points(entity):
    return (
        (float(entity.dxf.start.x), float(entity.dxf.start.y)),
        (float(entity.dxf.end.x), float(entity.dxf.end.y)),
    )


def _edge_key(p1, p2, precision: int = 4):
    a = (round(p1[0], precision), round(p1[1], precision))
    b = (round(p2[0], precision), round(p2[1], precision))
    return tuple(sorted((a, b)))


def _line_rectangles(lines: list) -> list[tuple[list, tuple]]:
    """Localiza retangulos formados por quatro LINEs no mesmo layer."""
    by_edge: dict[tuple[str, tuple], list] = {}
    horizontal: dict[tuple[str, float, float], list[tuple[float, object]]] = {}
    for entity in lines:
        p1, p2 = _line_points(entity)
        layer = str(entity.dxf.layer)
        by_edge.setdefault((layer, _edge_key(p1, p2)), []).append(entity)
        if abs(p1[1] - p2[1]) <= 1e-4 and abs(p1[0] - p2[0]) > 1e-4:
            x0, x1 = sorted((round(p1[0], 4), round(p2[0], 4)))
            horizontal.setdefault(
                (layer, x0, x1), []
            ).append((round(p1[1], 4), entity))

    used = set()
    found = []
    for (layer, x0, x1), entries in horizontal.items():
        for (y0, bottom), (y1, top) in sorted(
            combinations(sorted(entries), 2),
            key=lambda pair: abs(pair[1][0] - pair[0][0]),
        ):
            if y0 == y1 or id(bottom) in used or id(top) in used:
                continue
            y0, y1 = sorted((y0, y1))
            left_key = (layer, _edge_key((x0, y0), (x0, y1)))
            right_key = (layer, _edge_key((x1, y0), (x1, y1)))
            left = next(
                (e for e in by_edge.get(left_key, []) if id(e) not in used),
                None,
            )
            right = next(
                (e for e in by_edge.get(right_key, []) if id(e) not in used),
                None,
            )
            if left is None or right is None:
                continue
            group = [bottom, top, left, right]
            used.update(id(entity) for entity in group)
            found.append((group, (x0, y0, x1, y1)))
    return found


def _width_from_layer(
    layer: str, vertices, planar_width: bool = False
) -> float:
    """Fallback para linhas sem retangulo: seção nominal orientada pelo eixo."""
    if str(layer or "").casefold() == "meiopontalete":
        return 14.0
    match = __import__("re").search(
        r"(?:SARR(?:AFO)?[_ .-]*)(\d+(?:[._]\d+)?)X(\d+(?:[._]\d+)?)",
        str(layer).upper(),
    )
    if not match:
        return 2.2
    first = float(match.group(1).replace("_", "."))
    second = float(match.group(2).replace("_", "."))
    if planar_width:
        return second
    p0, p1 = vertices[0], vertices[-1]
    horizontal = abs(p1[0] - p0[0]) >= abs(p1[1] - p0[1])
    return first if horizontal else second


def _panel_boxes(entities: Iterable) -> list[tuple[float, float, float, float]]:
    """Bounding boxes dos paineis usados para alinhar sarrafos FV/PL."""
    boxes = []
    horizontal_groups: dict[tuple[float, float], list[float]] = {}
    for entity in entities:
        if "pain" not in str(entity.dxf.get("layer", "")).casefold():
            continue
        vertices = _polyline_vertices(entity)
        if len(vertices) < 2:
            continue
        xs = [point[0] for point in vertices]
        ys = [point[1] for point in vertices]
        if max(xs) > min(xs) and max(ys) > min(ys):
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
        elif (
            len(vertices) == 2
            and abs(vertices[0][1] - vertices[1][1]) <= 1e-4
            and abs(vertices[0][0] - vertices[1][0]) > 1e-4
        ):
            key = tuple(sorted((
                round(vertices[0][0], 4),
                round(vertices[1][0], 4),
            )))
            horizontal_groups.setdefault(key, []).append(vertices[0][1])
    for (x0, x1), ys in horizontal_groups.items():
        if len(ys) >= 2 and max(ys) > min(ys):
            boxes.append((x0, min(ys), x1, max(ys)))
    return boxes


def _pl_cima_madeira_layers(entities: Iterable) -> dict[int, str]:
    """Classifica as pecas fechadas da grade na vista CIMA.

    O motor desenha todas na layer ``Madeira``: bases/cantos 7x7 e
    divisores 3.5x7. A relacao entre as espessuras torna a deteccao
    independente da escala 2x usada pela vista.
    """
    rectangles = []
    for entity in entities:
        if (
            str(entity.dxf.get("layer", "")).casefold() != "madeira"
            or entity.dxftype() != "LWPOLYLINE"
            or not entity.closed
        ):
            continue
        box = _axis_aligned_rectangle(_polyline_vertices(entity))
        if box is None:
            continue
        x0, y0, x1, y1 = box
        short_side = min(x1 - x0, y1 - y0)
        rectangles.append((entity, short_side))
    if not rectangles:
        return {}

    full_section = max(short_side for _, short_side in rectangles)
    return {
        id(entity): (
            "SARR_3.5x7"
            if short_side < full_section * 0.75
            else "SARR_7x7"
        )
        for entity, short_side in rectangles
    }


def _panel_vertical_edges(panel_boxes) -> list[float]:
    """Xs das paredes verticais dos paineis (inclui paredes de abertura)."""
    edges: list[float] = []
    for box in panel_boxes or []:
        try:
            edges.append(float(box[0]))
            edges.append(float(box[2]))
        except (TypeError, ValueError, IndexError):
            continue
    return edges


def _wall_flush_center_x(
    mx: float, thickness: float, panel_boxes, edge_extra: float = 0.5
):
    """Se o eixo esta a ~1 face de sarrafo de uma parede, devolve o X central
    da MLINE para a face externa encostar na parede.

    Ex.: parede em 157, eixo LINE em 150 (offset 7), thickness=7 -> centro 153.5
    (faixa MLINE [150, 157] flush na parede). Sem isso, trechos no vao da
    abertura ficavam no eixo 150 e o trecho no painel solido ia para 153.5 —
    o L da abertura "quebrava" e nao alinhava na parede.
    """
    th = float(thickness)
    if th < 0.2:
        return None
    best = None  # (dist, target_x)
    for edge_x in _panel_vertical_edges(panel_boxes):
        dist = abs(float(mx) - edge_x)
        if dist <= 1e-6 or dist > th + float(edge_extra):
            continue
        # Centro da faixa: parede +/- th/2, do lado em que ja esta o eixo.
        if mx < edge_x:
            target = edge_x - th / 2.0
        else:
            target = edge_x + th / 2.0
        if best is None or dist < best[0]:
            best = (dist, target)
    return None if best is None else best[1]


def _align_panel_centerline(
    vertices, thickness: float, panel_boxes, edge_extra: float = 0.5
):
    """Centraliza a faixa MLINE para encostar na borda do painel/parede.

    Cobre:
    * borda externa do painel (comportamento original);
    * parede de abertura (eixo a ~thickness da parede) — inclusive trechos
      no vao, para o L e o fuste seccionados nao desalinharem.
    """
    if len(vertices) < 2 or not panel_boxes:
        return vertices

    th = float(thickness)
    extra = float(edge_extra)

    # Polilinha em L (3+ vertices): alinha a perna vertical na parede
    if len(vertices) >= 3:
        from collections import Counter

        xs = [float(p[0]) for p in vertices]
        ys = [float(p[1]) for p in vertices]
        wall_x = None
        for edge_x in _panel_vertical_edges(panel_boxes):
            for x in xs:
                if abs(x - edge_x) <= max(extra, 0.6):
                    wall_x = edge_x
                    break
            if wall_x is not None:
                break
        if wall_x is not None:
            other_xs = [x for x in xs if abs(x - wall_x) > max(extra, 0.6)]
            if other_xs:
                sarr_x = Counter(round(x, 3) for x in other_xs).most_common(1)[0][0]
                target = _wall_flush_center_x(sarr_x, th, panel_boxes, extra)
                if target is not None:
                    out = []
                    for x, y in zip(xs, ys):
                        if abs(x - wall_x) <= max(extra, 0.6):
                            out.append((wall_x, y))
                        elif abs(x - sarr_x) <= 1.0:
                            out.append((target, y))
                        else:
                            out.append((x, y))
                    return out
        return vertices

    p0, p1 = vertices[0], vertices[-1]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    horizontal = abs(dx) >= abs(dy) * 10
    vertical = abs(dy) >= abs(dx) * 10
    if not horizontal and not vertical:
        return vertices

    mx = (p0[0] + p1[0]) / 2.0
    my = (p0[1] + p1[1]) / 2.0

    # Vertical: flush na parede (solido OU vao seccionado)
    if vertical:
        target = _wall_flush_center_x(mx, th, panel_boxes, extra)
        if target is not None:
            return [(target, float(p0[1])), (target, float(p1[1]))]
        candidates = [
            box for box in panel_boxes
            if box[0] - 1 <= mx <= box[2] + 1
            and box[1] - 1 <= my <= box[3] + 1
        ]
        if not candidates:
            return vertices
        box = min(candidates, key=lambda value: (
            abs(mx - (value[0] + value[2]) / 2.0)
            + abs(my - (value[1] + value[3]) / 2.0)
        ))
        shift_x = 0.0
        low = abs(mx - box[0])
        high = abs(box[2] - mx)
        if low < high and low <= th + extra:
            shift_x = -th / 2.0
        elif high < low and high <= th + extra:
            shift_x = th / 2.0
        return [
            (float(p0[0]) + shift_x, float(p0[1])),
            (float(p1[0]) + shift_x, float(p1[1])),
        ]

    # Horizontal: braco L curto parede->eixo (~1 face) ou borda sup/inf
    for edge_x in _panel_vertical_edges(panel_boxes):
        d0 = abs(float(p0[0]) - edge_x)
        d1 = abs(float(p1[0]) - edge_x)
        if d0 <= max(extra, 0.6) and th * 0.35 <= d1 <= th + extra:
            free_target = (
                edge_x - th / 2.0 if p1[0] < edge_x else edge_x + th / 2.0
            )
            return [(edge_x, float(p0[1])), (free_target, float(p1[1]))]
        if d1 <= max(extra, 0.6) and th * 0.35 <= d0 <= th + extra:
            free_target = (
                edge_x - th / 2.0 if p0[0] < edge_x else edge_x + th / 2.0
            )
            return [(free_target, float(p0[1])), (edge_x, float(p1[1]))]

    candidates = [
        box for box in panel_boxes
        if box[0] - 1 <= mx <= box[2] + 1
        and box[1] - 1 <= my <= box[3] + 1
    ]
    if not candidates:
        return vertices
    box = min(candidates, key=lambda value: (
        abs(mx - (value[0] + value[2]) / 2.0)
        + abs(my - (value[1] + value[3]) / 2.0)
    ))
    shift_y = 0.0
    low = abs(my - box[1])
    high = abs(box[3] - my)
    if low < high and low <= th + extra:
        shift_y = -th / 2.0
    elif high < low and high <= th + extra:
        shift_y = th / 2.0
    return [
        (float(point[0]), float(point[1]) + shift_y)
        for point in vertices
    ]


def _add_solid_mline(msp, vertices, layer: str, thickness: float) -> None:
    msp.add_mline(
        vertices,
        close=False,
        dxfattribs={
            "layer": layer,
            "style_name": "SAR3",
            "scale_factor": max(float(thickness), 0.1),
            "justification": 1,  # Zero/centro: preserva o envelope do retangulo.
            "color": 256,
        },
    )


def _iter_modelspace_entities(doc) -> Iterable:
    # Os motores atuais geram a geometria editavel no modelspace. Nao
    # reescrevemos definicoes de blocos, pois elas sao compartilhadas.
    return list(doc.modelspace())


def apply_visual_mode(doc, mode: object = VISUAL_MODE_NOVA,
                      robot_class: str = "") -> VisualModeStats:
    """Aplica o perfil solicitado a um documento ezdxf.

    NOVA retorna imediatamente e preserva byte/semantica do motor atual.
    """
    normalized = normalize_visual_mode(mode)
    cls = str(robot_class or "").strip().upper()
    stats = VisualModeStats(normalized, cls)
    if normalized == VISUAL_MODE_NOVA:
        return stats

    layer_map = _INI_LAYER_MAP.get(cls, {})
    _ensure_sar3_style(doc)

    msp = doc.modelspace()
    original_entities = _iter_modelspace_entities(doc)
    pl_cima_madeira = (
        _pl_cima_madeira_layers(original_entities)
        if cls == "PL"
        else {}
    )
    panel_boxes = (
        _panel_boxes(original_entities)
        if cls in ("FV", "PL")
        else []
    )
    sarrafo_entities = []
    for entity in original_entities:
        old_layer = str(entity.dxf.get("layer", "0"))
        new_layer = pl_cima_madeira.get(
            id(entity),
            layer_map.get(old_layer.casefold(), old_layer),
        )
        _ensure_layer(doc, new_layer)

        if new_layer != old_layer:
            entity.dxf.layer = new_layer
            stats.remapped_entities += 1

        # INI historico usa a paleta do layer, nao cores individuais.
        if entity.dxf.is_supported("color"):
            entity.dxf.color = 256

        if (
            _should_convert_to_mline(doc, entity, new_layer)
            and not (cls == "LV" and _is_lv_layer_sentinel(entity))
        ):
            sarrafo_entities.append(entity)

    consumed = set()

    # Retangulos LWPOLYLINE fechados viram uma unica linha central MLINE.
    for entity in sarrafo_entities:
        if entity.dxftype() != "LWPOLYLINE" or not entity.closed:
            continue
        vertices = _polyline_vertices(entity)
        box = _axis_aligned_rectangle(vertices)
        if box is None:
            continue
        centerline, thickness = _centerline_for_visual_class(
            box, entity.dxf.layer, cls
        )
        _add_solid_mline(msp, centerline, entity.dxf.layer, thickness)
        consumed.add(id(entity))
        stats.mlines_created += 1
        stats.rectangles_collapsed += 1

    # Os motores também constroem retângulos como quatro LINEs independentes.
    line_entities = [
        entity for entity in sarrafo_entities
        if entity.dxftype() == "LINE" and id(entity) not in consumed
    ]
    for group, box in _line_rectangles(line_entities):
        centerline, thickness = _centerline_for_visual_class(
            box, group[0].dxf.layer, cls
        )
        _add_solid_mline(msp, centerline, group[0].dxf.layer, thickness)
        consumed.update(id(entity) for entity in group)
        stats.mlines_created += 1
        stats.rectangles_collapsed += 1

    # Linhas que já eram eixos permanecem uma linha, com escala pela seção.
    for entity in sarrafo_entities:
        if id(entity) in consumed:
            continue
        vertices = _polyline_vertices(entity)
        if len(vertices) < 2:
            continue
        if entity.dxftype() == "LWPOLYLINE" and entity.closed:
            # Forma fechada não retangular: não há eixo confiável.
            continue
        thickness = _width_from_layer(
            entity.dxf.layer,
            vertices,
            planar_width=(cls in ("FV", "PL", "LV")),
        )
        if cls in ("FV", "PL"):
            vertices = _align_panel_centerline(
                vertices,
                thickness,
                panel_boxes,
                edge_extra=2.5 if cls == "PL" else 0.5,
            )
        _add_solid_mline(msp, vertices, entity.dxf.layer, thickness)
        consumed.add(id(entity))
        stats.mlines_created += 1

    for entity in sarrafo_entities:
        if id(entity) in consumed:
            msp.delete_entity(entity)

    # Atualiza inclusive layers presentes no desenho mas sem entidades.
    for layer in list(doc.layers):
        name = str(layer.dxf.name)
        mapped = layer_map.get(name.casefold(), name)
        _ensure_layer(doc, mapped)
        if name in _LEGACY_COLORS:
            layer.dxf.color = _LEGACY_COLORS[name]

    return stats
