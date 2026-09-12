# -*- coding: utf-8 -*-
"""HTML E2E multi-segmento V301 com RENDER DXF real (ezdxf), não wireframe.

Gabarito = recorte N2 original clipado por face_unit.
Candidato = N4 VIEW_A/B clipado na banda do label.

Uso:
  python scripts/arete/_build_segments_html_v301.py --open
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import webbrowser
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import ezdxf  # noqa: E402
import ezdxf.colors as ez_colors  # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext  # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend  # noqa: E402

ARETE = Path(__file__).resolve().parent
SCRIPTS = ARETE.parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO))

from arete.geometry_lv_units import (  # noqa: E402
    n2_anchor,
    n4_anchor,
    pair_units,
    split_n4_view,
    unit_label,
)
from arete.gerar_lv_n4_fichas import _entry_from_live_recorte  # noqa: E402
import gerar_lv_dxf_stog as lv_motor  # noqa: E402
from lv_n4_face_unit_selection import select_n4_face_units  # noqa: E402

# Item corrente. Passa a ser definido por `--item` (default V301, que foi o
# item de calibracao do motor). Mantidos como globais porque varias funcoes
# auxiliares ja liam GATE/PREV; `_set_item()` reaponta as duas.
ITEM = "V301"
GATE = ARETE / "relatorios" / "g2v" / f"{ITEM.lower()}_geometry_gate"
PREV = GATE / "previews_dxf"


def _set_item(item: str) -> None:
    """Reaponta o item corrente e os diretorios derivados dele."""
    global ITEM, GATE, PREV
    ITEM = str(item).strip().upper()
    GATE = ARETE / "relatorios" / "g2v" / f"{ITEM.lower()}_geometry_gate"
    PREV = GATE / "previews_dxf"
    PREV.mkdir(parents=True, exist_ok=True)
import os  # noqa: E402
# Idem run_geometry_gate_lv: LV_N4_DIR redireciona a leitura dos N4 para a
# pasta da rodada, deixando os N4 selados de producao intocados.
N4_DIR = Path(
    os.environ.get("LV_N4_DIR")
    or r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n4"
)
PREV.mkdir(parents=True, exist_ok=True)


def render_dxf_clip(
    dxf_path: Path,
    out_png: Path,
    *,
    clip: tuple[float, float, float, float] | None,
    title: str,
    width_px: int = 900,
    height_px: int = 520,
    dpi: int = 140,
) -> bool:
    """Render DXF real (cores/layers/cotas do ezdxf drawing). clip=(xmin,ymin,xmax,ymax) abs."""
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        fig_w, fig_h = width_px / dpi, height_px / dpi
        fig = plt.figure(figsize=(fig_w, fig_h), dpi=dpi)
        ax = fig.add_axes([0.02, 0.04, 0.96, 0.90])
        ax.set_facecolor("#ffffff")
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(msp, finalize=True)
        # O finalize do backend DXF pode redimensionar a figura conforme a
        # extensão global do desenho. Reponha o viewport contratado para que
        # N2 e N4 tenham exatamente o mesmo quadro em pixels.
        fig.set_size_inches(fig_w, fig_h, forward=True)
        ax.set_position([0.02, 0.04, 0.96, 0.90])
        if clip is not None:
            xmin, ymin, xmax, ymax = clip
            # Respiro visual: expande o recorte para cada direção. Reduzido
            # de 20% para 8% (achado 2026-08-31): ocorrências repetidas no
            # mesmo recorte ficam empilhadas a ~30cm uma da outra, e 20% de
            # respiro (ex. 28cm num clip de 140cm) já é o suficiente pra
            # "vazar" o título/label da ocorrência vizinha pro N2 preview,
            # fazendo o card mostrar um rótulo errado mesmo com a geometria
            # comparada corretamente por trás (revisor via "CONT. V301.A"
            # onde devia ver "UNIT.B#7"). 8% fica bem abaixo desse gap
            # típico e ainda dá respiro pra cotas na borda.
            dx = max(3.0, (xmax - xmin) * 0.08)
            dy = max(3.0, (ymax - ymin) * 0.08)
            ax.set_xlim(xmin - dx, xmax + dx)
            ax.set_ylim(ymin - dy, ymax + dy)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(title, fontsize=9, color="#0f172a", pad=4)
        ax.tick_params(labelsize=6)
        # O DXF pode conter textos/cotas com bounding boxes muito afastados do
        # recorte. ``bbox_inches='tight'`` tenta incluí-los e, no Windows, pode
        # produzir uma imagem de dimensão inválida (Errno 22). Os limites do
        # eixo acima já são o contrato visual do segmento; preserve o quadro
        # fixo e deixe o clipping do Matplotlib cuidar do restante.
        fig.savefig(out_png, dpi=dpi, facecolor="#f8fafc")
        plt.close(fig)
        return out_png.is_file()
    except Exception as ex:
        print("render fail", dxf_path.name, ex)
        try:
            plt.close("all")
        except Exception:
            pass
        return False


def _hex_from_aci(aci: int) -> str:
    try:
        rgb = ez_colors.aci2rgb(int(aci))
        return f"#{rgb.r:02x}{rgb.g:02x}{rgb.b:02x}"
    except Exception:
        return "#e5e7eb"


def _layer_color_map(doc) -> dict:
    out = {}
    for layer in doc.layers:
        aci = layer.dxf.color
        if aci is None or not (1 <= aci <= 255):
            aci = 7
        out[layer.dxf.name] = _hex_from_aci(aci)
    return out


def _entity_hex(e, layer_colors: dict, *, fallback_layer=None, fallback_color=None) -> str:
    color = getattr(e.dxf, "color", 256)
    layer = fallback_layer or e.dxf.layer
    if color in (0, 256) and fallback_color is not None:
        color = fallback_color
    if color not in (0, 256) and isinstance(color, int) and 1 <= color <= 255:
        return _hex_from_aci(color)
    return layer_colors.get(layer, "#e5e7eb")


def _all_geom_points(msp):
    """Pontos (x,y) de todas as LINE/LWPOLYLINE do modelspace — usado para
    delimitar a caixa real de uma instancia de corte (nao ha campo de bbox
    pronto, tem que medir a geometria)."""
    pts = []
    for e in msp:
        if e.dxftype() == "LINE":
            pts.append((e.dxf.start.x, e.dxf.start.y))
            pts.append((e.dxf.end.x, e.dxf.end.y))
        elif e.dxftype() == "LWPOLYLINE":
            for p in e.get_points():
                pts.append((p[0], p[1]))
    return pts


_BORDAS_PAINEL_CACHE: dict = {}


def _bordas_de_painel(path: Path) -> list[tuple]:
    """Horizontais da layer `Painéis` do recorte: (y, x_ini, x_fim)."""
    chave = str(path)
    if chave in _BORDAS_PAINEL_CACHE:
        return _BORDAS_PAINEL_CACHE[chave]
    bordas = []
    try:
        for e in ezdxf.readfile(str(path)).modelspace().query("LINE"):
            if e.dxf.layer != "Painéis":
                continue
            s, t = e.dxf.start, e.dxf.end
            if abs(s[1] - t[1]) > 0.6:
                continue
            bordas.append((float(s[1]), float(min(s[0], t[0])),
                           float(max(s[0], t[0]))))
    except Exception:
        bordas = []
    _BORDAS_PAINEL_CACHE[chave] = bordas
    return bordas


def _expandir_ate_borda_de_painel(path: Path, clip, alcance: float = 35.0):
    """Nao cortar a borda de um painel que esta' logo fora do recorte.

    O recorte N2 e' derivado da banda que a ficha declara. Quando a ficha erra
    a banda, o recorte decepa a borda que justamente define a altura do painel
    — na V13 a face A perdia 9.0cm do topo, e sem o topo nao da' para ler o
    tamanho real do painel (apontado pelo dono, 2026-09-11).

    Regra de EXIBICAO, independente da ficha: se existe borda horizontal de
    `Painéis` ate' `alcance` fora da janela, e ela cobre boa parte da largura
    mostrada, a janela cresce ate' inclui-la. Limitada a `alcance` para nao
    engolir a face vizinha.
    """
    x0, y0, x1, y1 = clip
    largura = max(x1 - x0, 1.0)
    novo_y0, novo_y1 = y0, y1
    for y, xa, xb in _bordas_de_painel(path):
        # so' bordas que pertencem ao que esta' sendo mostrado
        sobre = min(x1, xb) - max(x0, xa)
        if sobre < 0.5 * largura:
            continue
        if y1 < y <= y1 + alcance:
            novo_y1 = max(novo_y1, y + 6.0)
        elif y0 - alcance <= y < y0:
            novo_y0 = min(novo_y0, y - 6.0)
    return (x0, novo_y0, x1, novo_y1)


def find_n4_corte_instances(path: Path, section_views: list | None = None) -> list[dict]:
    """Particiona LV_preview_{item}_CORTE.dxf em uma instancia por secao.

    Reproduz o empilhamento do proprio gerador em vez de procurar texto de
    titulo: desde que o N4 passou a replicar a geometria real do N2 (decisao
    do dono, 2026-09-10), o titulo sintetico "NOME (LxA)" — que so o template
    procedural emitia — deixou de existir. Tambem nao da pra agrupar por vazio
    vertical: as primitivas do N2 vem em escala 2x e as cotas de uma secao
    chegam perto da vizinha, sem intervalo limpo.

    Regra (espelha ``draw_viga_lateral_face_units``): ``y_section`` comeca em
    ``y_top - 150`` e anda ``-max(h_sec + 90, 180)`` por secao; cada secao e'
    desenhada centrada em ``y_section + h_sec/2``. A extensao vertical real
    vem das proprias ``visual_primitives`` daquela secao (coords relativas ao
    centro), entao a faixa e' exata mesmo com o 2x.
    """
    try:
        doc = ezdxf.readfile(str(path))
    except Exception as ex:
        print("corte n4 read fail", path.name, ex)
        return []
    msp = doc.modelspace()
    pts = _all_geom_points(msp)
    if not pts or not section_views:
        return []

    # Centros de cada secao, pela mesma cascata do gerador.
    centers: list[tuple[int, float, float]] = []
    _y_sec = -150.0  # y_top = 0 na vista CORTE isolada
    for idx, sv in enumerate(section_views):
        _h = float(sv.get("h_section", 0) or 0)
        if _h > 0:
            centers.append((idx, _y_sec + _h / 2.0, _h))
        _y_sec -= max(_h + 90.0, 180.0)

    out = []
    for pos, (idx, center, h_sec) in enumerate(centers):
        sv = section_views[idx]
        rel_y = []
        for prim in (sv.get("visual_primitives") or []):
            for key in ("points", "insert", "align_point"):
                val = prim.get(key)
                if not val:
                    continue
                seq = val if isinstance(val[0], (list, tuple)) else [val]
                rel_y += [float(p[1]) for p in seq if len(p) >= 2]
            for sub in (prim.get("paths") or []):
                rel_y += [float(p[1]) for p in sub if len(p) >= 2]
        if rel_y:
            y_lo, y_hi = center + min(rel_y) - 8.0, center + max(rel_y) + 8.0
        else:
            y_lo, y_hi = center - h_sec, center + h_sec
        # As cotas de uma secao alcancam a vizinha (primitivas em 2x), entao
        # a faixa e' cortada no meio do caminho ate' o centro vizinho.
        if pos > 0:
            y_hi = min(y_hi, (center + centers[pos - 1][1]) / 2.0)
        if pos + 1 < len(centers):
            y_lo = max(y_lo, (center + centers[pos + 1][1]) / 2.0)
        band = [(px, py) for px, py in pts if y_lo <= py <= y_hi]
        if band:
            xs = [p[0] for p in band]
            bys = [p[1] for p in band]
            out.append({
                "label": str(sv.get("label") or f"Corte {idx + 1}"),
                "clip": (min(xs) - 5.0, min(bys) - 5.0,
                         max(xs) + 5.0, max(bys) + 5.0),
            })
    return out


def find_n2_corte_instances(
    path: Path, x_range: tuple[float, float], gap: float = 160.0,
) -> list[dict]:
    """Particiona o CORTE real do N2 em instancias via cluster dos rotulos
    'a'/'b'/'c' (marcam cada corte individual no desenho humano — nao ha
    titulo "NOME (LxA)" no N2, so' esses 3 rotulos curtos por instancia).
    """
    try:
        doc = ezdxf.readfile(str(path))
    except Exception as ex:
        print("corte n2 read fail", path.name, ex)
        return []
    msp = doc.modelspace()
    abc = []
    for e in msp.query("TEXT"):
        t = (e.dxf.text or "").strip()
        x = float(e.dxf.insert.x)
        if t in ("a", "b", "c") and x_range[0] <= x <= x_range[1]:
            abc.append(float(e.dxf.insert.y))
    if not abc:
        return []
    abc.sort(reverse=True)
    clusters: list[list[float]] = []
    cur = [abc[0]]
    for y in abc[1:]:
        if cur[-1] - y > gap:
            clusters.append(cur)
            cur = [y]
        else:
            cur.append(y)
    clusters.append(cur)
    pts = [
        (px, py) for px, py in _all_geom_points(msp)
        if x_range[0] - 20.0 <= px <= x_range[1] + 20.0
    ]
    out = []
    for cl in clusters:
        y_hi, y_lo = max(cl) + 90.0, min(cl) - 90.0
        band = [(px, py) for px, py in pts if y_lo <= py <= y_hi]
        if not band:
            continue
        xs = [p[0] for p in band]
        ys = [p[1] for p in band]
        out.append({"clip": (min(xs) - 5.0, min(ys) - 5.0, max(xs) + 5.0, max(ys) + 5.0)})
    return out


def render_dxf_clip_svg(
    dxf_path: Path,
    *,
    clip: tuple[float, float, float, float] | None,
    id_prefix: str,
    pad_frac: float = 0.08,
) -> str | None:
    """Renderiza um recorte do DXF como SVG inline, um elemento por entidade.

    Cada LINE/TEXT/HATCH/DIMENSION vira seu proprio <g data-layer=... data-
    type=... data-handle=...> no DOM — quando o dono aponta "essa linha
    aqui" no navegador, o clique carrega a entidade real (layer/tipo/handle/
    medida), fechando a ponte anotacao->codigo sem eu ter que recalcular
    coordenada de pixel/porcentagem (pedido do dono, 2026-08-31).
    """
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as ex:
        print("svg render fail (read)", dxf_path.name, ex)
        return None
    msp = doc.modelspace()
    layer_colors = _layer_color_map(doc)

    if clip is not None:
        xmin, ymin, xmax, ymax = clip
        dx = max(3.0, (xmax - xmin) * pad_frac)
        dy = max(3.0, (ymax - ymin) * pad_frac)
        xmin, xmax = xmin - dx, xmax + dx
        ymin, ymax = ymin - dy, ymax + dy
    else:
        ext_min = doc.header.get("$EXTMIN")
        ext_max = doc.header.get("$EXTMAX")
        xmin, ymin = (ext_min[0], ext_min[1]) if ext_min else (0.0, 0.0)
        xmax, ymax = (ext_max[0], ext_max[1]) if ext_max else (100.0, 100.0)

    def fy(y: float) -> float:
        return -y

    def in_window(x: float, y: float, pad: float = 0.0) -> bool:
        return (xmin - pad) <= x <= (xmax + pad) and (ymin - pad) <= y <= (ymax + pad)

    frags: list[str] = []
    counter = {"n": 0}
    pattern_defs: dict[str, tuple] = {}

    def _pattern_ref(name: str, color: str) -> str:
        # Hatch de padrao (ANSI31/AR-CONC/etc, nao solid_fill) preenchido
        # solido a 0.28 de opacidade virava um "bloco cinza" enganoso quando
        # duas faixas de padrao ficam lado a lado — o dono achou que a
        # posicao tinha piorado quando na verdade era so a minha
        # simplificacao de render empilhando dois blocos solidos (achado
        # 2026-08-31: reaproveitamento ANSI31 + laje AR-CONC, ambos color=7
        # no DXF real, ficavam indistinguiveis um do outro e do fundo).
        # Textura de verdade (linhas/pontos esparsos) preserva a leitura.
        key = f"{name}|{color}"
        if key not in pattern_defs:
            pid = f"pat-{id_prefix}-{len(pattern_defs)}"
            if (name or "").upper() == "AR-CONC":
                body = (
                    f'<pattern id="{pid}" width="7" height="7" '
                    f'patternUnits="userSpaceOnUse">'
                    f'<circle cx="1.8" cy="1.8" r="0.55" fill="{color}" fill-opacity="0.65"/>'
                    f'<circle cx="5.2" cy="4.8" r="0.4" fill="{color}" fill-opacity="0.55"/>'
                    f'</pattern>'
                )
            else:
                body = (
                    f'<pattern id="{pid}" width="6" height="6" '
                    f'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                    f'<line x1="0" y1="0" x2="0" y2="6" stroke="{color}" '
                    f'stroke-width="0.6" stroke-opacity="0.7"/>'
                    f'</pattern>'
                )
            pattern_defs[key] = (pid, body)
        return pattern_defs[key][0]

    def emit(tag_svg: str, *, dxftype: str, layer: str, handle: str, extra: str = "") -> None:
        counter["n"] += 1
        eid = f"{id_prefix}-{counter['n']}"
        frags.append(
            f'<g id="{html.escape(eid, quote=True)}" data-layer="{html.escape(layer, quote=True)}" '
            f'data-type="{html.escape(dxftype, quote=True)}" '
            f'data-handle="{html.escape(handle, quote=True)}"'
            f'{extra} class="dxf-el dxf-{html.escape(dxftype.lower())}">{tag_svg}</g>'
        )

    def handle_line(e, *, fallback_layer=None, fallback_color=None):
        s, e2 = e.dxf.start, e.dxf.end
        if not (in_window(s.x, s.y, 20) or in_window(e2.x, e2.y, 20)):
            return
        color = _entity_hex(e, layer_colors, fallback_layer=fallback_layer, fallback_color=fallback_color)
        layer = fallback_layer or e.dxf.layer
        length = round(((e2.x - s.x) ** 2 + (e2.y - s.y) ** 2) ** 0.5, 1)
        x1, y1, x2, y2 = f"{s.x:.2f}", f"{fy(s.y):.2f}", f"{e2.x:.2f}", f"{fy(e2.y):.2f}"
        # "Ima" de clique: linha invisivel bem mais grossa por baixo da
        # linha fina real, so' para hit-test (pointer-events:stroke) — sem
        # isso o dono tinha que acertar o pixel exato de uma stroke de
        # 0.6px pra selecionar (pedido do dono, 2026-08-31).
        svg = (
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="transparent" stroke-width="12" vector-effect="non-scaling-stroke" '
            f'style="pointer-events:stroke"/>'
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="0.6" vector-effect="non-scaling-stroke" '
            f'style="pointer-events:none"/>'
        )
        emit(
            svg, dxftype="LINE", layer=layer, handle=str(e.dxf.handle),
            extra=f' data-length-cm="{length}"',
        )

    def handle_lwpolyline(e, *, fallback_layer=None, fallback_color=None):
        pts = [(p[0], p[1]) for p in e.get_points()]
        if not pts or not any(in_window(px, py, 20) for px, py in pts):
            return
        color = _entity_hex(e, layer_colors, fallback_layer=fallback_layer, fallback_color=fallback_color)
        layer = fallback_layer or e.dxf.layer
        d = "M " + " L ".join(f"{px:.2f} {fy(py):.2f}" for px, py in pts)
        closed = bool(getattr(e, "closed", False))
        if closed:
            d += " Z"
        # Sem fill automatico so por estar "fechada": no DXF real uma
        # LWPOLYLINE (aberta ou fechada) e' so contorno — preenchimento so
        # existe se houver um HATCH separado referenciando o mesmo path.
        # Preencher toda closed=True a 25% criava caixas com "fundo solido"
        # enganoso (ex.: contorno de painel 75x7cm sem hachura nenhuma
        # associada, achado 2026-09-08 via ponto marcado pelo dono).
        hit_stroke = (
            f'<path d="{d}" stroke="transparent" stroke-width="12" fill="none" '
            f'vector-effect="non-scaling-stroke" style="pointer-events:stroke"/>'
        )
        svg = (
            f'{hit_stroke}'
            f'<path d="{d}" stroke="{color}" stroke-width="0.6" fill="none" '
            f'vector-effect="non-scaling-stroke" style="pointer-events:none"/>'
        )
        emit(svg, dxftype="LWPOLYLINE", layer=layer, handle=str(e.dxf.handle))

    def handle_hatch(e):
        color = _entity_hex(e, layer_colors)
        layer = e.dxf.layer
        is_solid = bool(getattr(e.dxf, "solid_fill", 0))
        pattern_name = str(getattr(e.dxf, "pattern_name", "") or "")
        paths_svg = []
        any_in = False
        for p in e.paths:
            pts = None
            if hasattr(p, "vertices"):
                pts = [(v[0], v[1]) for v in p.vertices]
            if not pts:
                continue
            if any(in_window(px, py, 20) for px, py in pts):
                any_in = True
            d = "M " + " L ".join(f"{px:.2f} {fy(py):.2f}" for px, py in pts) + " Z"
            paths_svg.append(d)
        if not any_in or not paths_svg:
            return
        d_all = " ".join(paths_svg)
        if is_solid:
            fill_attr = f'fill="{color}" fill-opacity="0.28"'
        else:
            pid = _pattern_ref(pattern_name, color)
            fill_attr = f'fill="url(#{pid})"'
        # Contorno da hachura de reaproveitamento (layer "Hachura") quase
        # sempre coincide com uma linha Painéis real já desenhada separada
        # (a borda do painel/degrau) — o stroke aqui virava "linha
        # duplicada" falsa na leitura visual (achado 2026-09-09, SEGMENTO
        # 3B: handle BDE parecia duplicado, mas era so o contorno do
        # hatch por cima dele). Outros hatches (concreto/vazio) mantêm o
        # contorno normal, pois neles a borda é a única indicação visual
        # do limite da região.
        stroke_attr = (
            "" if layer == "Hachura"
            else f'stroke="{color}" stroke-width="0.25" stroke-opacity="0.5" '
        )
        svg = (
            f'<path d="{d_all}" {fill_attr} '
            f'{stroke_attr}fill-rule="evenodd"/>'
        )
        emit(
            svg, dxftype="HATCH", layer=layer, handle=str(e.dxf.handle),
            extra=f' data-pattern="{html.escape(pattern_name, quote=True)}"',
        )

    def handle_text(e, *, dxftype="TEXT", fallback_layer=None, fallback_color=None):
        try:
            ins = e.dxf.insert
            txt = e.dxf.text if dxftype == "TEXT" else e.text
            h = float(getattr(e.dxf, "height", 8.0) or getattr(e.dxf, "char_height", 8.0) or 8.0)
        except Exception:
            return
        if not txt or not in_window(ins.x, ins.y, 30):
            return
        color = _entity_hex(e, layer_colors, fallback_layer=fallback_layer, fallback_color=fallback_color)
        layer = fallback_layer or e.dxf.layer
        txt_esc = html.escape(str(txt))[:80]
        svg = (
            f'<text x="{ins.x:.2f}" y="{fy(ins.y):.2f}" font-size="{max(h, 4):.1f}" '
            f'fill="{color}" font-family="monospace">{txt_esc}</text>'
        )
        emit(
            svg, dxftype=dxftype, layer=layer, handle=str(e.dxf.handle),
            extra=f' data-text="{html.escape(str(txt), quote=True)[:80]}"',
        )

    def handle_dimension(e):
        layer = e.dxf.layer
        color = getattr(e.dxf, "color", 256)
        fb_color = None if color in (0, 256) else color
        try:
            subs = list(e.virtual_entities())
        except Exception:
            subs = []
        for v in subs:
            vt = v.dxftype()
            if vt == "LINE":
                handle_line(v, fallback_layer=layer, fallback_color=fb_color)
            elif vt in ("TEXT", "MTEXT"):
                handle_text(v, dxftype=vt, fallback_layer=layer, fallback_color=fb_color)

    for e in msp:
        t = e.dxftype()
        try:
            if t == "LINE":
                handle_line(e)
            elif t == "LWPOLYLINE":
                handle_lwpolyline(e)
            elif t == "HATCH":
                handle_hatch(e)
            elif t == "TEXT":
                handle_text(e, dxftype="TEXT")
            elif t == "MTEXT":
                handle_text(e, dxftype="MTEXT")
            elif t == "DIMENSION":
                handle_dimension(e)
        except Exception as ex:
            print("svg entity skip", t, ex)
            continue

    width = xmax - xmin
    height = ymax - ymin
    if width <= 0 or height <= 0:
        return None
    view_box = f"{xmin:.2f} {fy(ymax):.2f} {width:.2f} {height:.2f}"
    defs = "".join(body for _, body in pattern_defs.values())
    return (
        f'<svg viewBox="{view_box}" xmlns="http://www.w3.org/2000/svg" '
        f'preserveAspectRatio="xMidYMid meet" class="dxf-svg" '
        f'style="width:100%;height:100%;display:block;background:#1e2531">'
        f'<defs>{defs}</defs>'
        f'<g>{"".join(frags)}</g></svg>'
    )


def _cls(v: str) -> str:
    if "PASS" in v:
        return "ok"
    if "FAIL" in v:
        return "fail"
    return "sus"


def build(item: str | None = None) -> Path:
    if item:
        _set_item(item)
    viga = ITEM
    data = json.loads((GATE / f"{viga}_GEOMETRY_GATE.json").read_text(encoding="utf-8"))
    results = list(data.get("results") or [])
    n2_path = Path(data["n2"])

    entry = _entry_from_live_recorte(viga)
    fus = select_n4_face_units(
        lv_motor, entry.get("face_units") or [], viga
    ) if entry else []
    n2_by_side: dict[str, list] = {"A": [], "B": []}
    for i, u in enumerate(fus):
        side = str(u.get("side") or "?").upper()
        if side in n2_by_side:
            uu = dict(u)
            uu["_idx"] = i
            n2_by_side[side].append(uu)

    # LV_preview_V301_VIEW_A/B.dxf sao renders de UMA ocorrencia so (uso
    # canonico: ficha focada). O combinado _A.dxf tem TODAS as ocorrencias
    # (A e B, absolutas) na mesma folha — fonte real p/ split multi-unidade
    # (split_n4_view ja filtra por sufixo .A/.B do label).
    _n4_combined = N4_DIR / f"LV_preview_{viga}_A.dxf"
    n4_paths = {
        "A": _n4_combined,
        "B": _n4_combined,
    }
    # Versiona as imagens pela revisão efetiva dos DXFs. Isso impede que o
    # navegador reutilize previews do motor anterior e evita sobrescrever PNGs
    # que estejam momentaneamente abertos pelo servidor no Windows.
    n2_tag = str(n2_path.stat().st_mtime_ns)
    n4_tag = str(max([p.stat().st_mtime_ns for p in n4_paths.values() if p.exists()] or [0]))
    preview_tag = f"{n2_tag}_{n4_tag}"

    n4_units = {
        s: split_n4_view(p, s) if p.exists() else [] for s, p in n4_paths.items()
    }

    # mapa label N2 -> unit dict for clip
    n2_by_label: dict[str, dict] = {}
    for side, units in n2_by_side.items():
        for u in units:
            n2_by_label[unit_label(u, u.get("_idx", 0))] = u

    # full face renders (qualidade DXF)
    # clip=None desenhava o arquivo INTEIRO, incluindo blocos de referencia
    # (PAR_ESQ/PAR_FUNDO_ESQ/par_int_esq/par_int_dir, perto de x=0-120,
    # marcadores fixos sem relacao com as ocorrencias reais) e a visao de
    # corte embutida no mesmo arquivo la' por x<0 — contaminando a leitura
    # visual de "N4 completo" com objetos que nao sao paineis A/B (achado
    # 2026-09-10, dono circulou os retangulos brancos e o icone de corte).
    # As ocorrencias reais do painel comecam por volta de x=1800; recorta
    # so' essa faixa.
    # Clip do panorama: bbox da geometria real (LINE/LWPOLYLINE). Exclui os
    # blocos PAR_* soltos perto da origem local, que nao pertencem a ocorrencia
    # desenhada e esticavam a imagem. Generalizado 2026-09-11 — antes era a
    # faixa fixa da V301 (1700..12420), que cortava as outras vigas.
    def _faixa_densa(vals: list[float]) -> tuple[float, float]:
        """Descarta cauda solta separada por um vazio grande.

        O combinado tem entidades perdidas longe do desenho (na V13 ha um ponto
        em x=-9000 enquanto o conteudo vive entre 119 e 3070). Sem isso o bbox
        fica 12070 de largura e a imagem vira uma faixa preta quase vazia
        (apontado pelo dono, 2026-09-11).
        """
        v = sorted(vals)
        if len(v) < 8:
            return v[0], v[-1]
        span = v[-1] - v[0]
        if span <= 0:
            return v[0], v[-1]
        lo, hi = 0, len(v) - 1
        for _ in range(4):  # pode haver cauda dos dois lados
            larguras = [(v[i + 1] - v[i], i) for i in range(lo, hi)]
            if not larguras:
                break
            gap, i = max(larguras)
            # Vazio tem que ser MUITO maior que o normal do desenho: as
            # ocorrencias de uma mesma face ficam a ~25% do span umas das
            # outras e nao podem ser cortadas. 40% separa cauda perdida de
            # espacamento legitimo. A cauda pode ter ate' 25% dos pontos —
            # na V13 o bloco solto em x=-9000 tem 28 de 276 (10.1%) e o
            # limiar anterior de 10% deixava passar raspando.
            if gap < 0.40 * (v[hi] - v[lo]):
                break
            n_esq, n_dir = (i + 1) - lo, hi - i
            if n_esq <= n_dir and n_esq <= 0.25 * len(v):
                lo = i + 1
            elif n_dir < n_esq and n_dir <= 0.25 * len(v):
                hi = i
            else:
                break
        return v[lo], v[hi]

    # Mobilia de prancha: nao e' o desenho da viga. Na V13 a moldura+carimbo
    # ocupam Y +200..+1250 enquanto a viga vive em Y -305..0 — incluir isso no
    # enquadramento quintuplica a altura e some com o desenho (apontado pelo
    # dono, 2026-09-11: "faixa preta gigante").
    _LAYERS_PRANCHA = {"Folhas", "CARIMBO"}

    def _clip_geom(caminho: Path):
        try:
            msp = ezdxf.readfile(str(caminho)).modelspace()
        except Exception:
            return None
        pts = []
        for e in msp:
            if str(getattr(e.dxf, "layer", "")) in _LAYERS_PRANCHA:
                continue
            t = e.dxftype()
            if t == "LINE":
                pts += [(e.dxf.start[0], e.dxf.start[1]),
                        (e.dxf.end[0], e.dxf.end[1])]
            elif t == "LWPOLYLINE":
                pts += [(p[0], p[1]) for p in e.get_points("xy")]
        if not pts:
            return None
        x0, x1 = _faixa_densa([q[0] for q in pts])
        y0, y1 = _faixa_densa([q[1] for q in pts])
        pad_x = max((x1 - x0) * 0.02, 10.0)
        pad_y = max((y1 - y0) * 0.08, 10.0)
        return (x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y)

    def _tela(clip, largura=1200, alt_min=230, alt_max=520):
        """Altura da imagem seguindo a proporcao do recorte (evita tarja)."""
        if not clip:
            return largura, 420
        dx, dy = clip[2] - clip[0], clip[3] - clip[1]
        if dx <= 0 or dy <= 0:
            return largura, 420
        return largura, int(min(max(largura * dy / dx, alt_min), alt_max))

    full_prev = {}
    for side, p in n4_paths.items():
        if p.exists():
            out = PREV / f"FULL_N4_VIEW_{side}_{n4_tag}.png"
            _cl = _clip_geom(p)
            _w, _h = _tela(_cl)
            ok = out.exists() or render_dxf_clip(
                p, out, clip=_cl,
                title=f"N4 VIEW_{side} completo (DXF real)",
                width_px=_w, height_px=_h,
            )
            full_prev[side] = f"previews_dxf/{out.name}" if ok else None

    # Visao CORTE — classe separada dos paineis A/B (pedido do dono,
    # 2026-09-10): overview completo + card granular por instancia de
    # corte (N2 real x N4 gerado), abaixo dos segmentos de painel.
    corte_path = N4_DIR / f"LV_preview_{viga}_CORTE.dxf"
    full_corte = None
    corte_pairs: list[dict] = []
    if corte_path.exists():
        out_corte = PREV / f"FULL_N4_CORTE_{n4_tag}.png"
        ok_corte = out_corte.exists() or render_dxf_clip(
            corte_path, out_corte, clip=None,
            title="N4 CORTE completo (DXF real)", width_px=900, height_px=520,
        )
        full_corte = f"previews_dxf/{out_corte.name}" if ok_corte else None
        n4_corte_insts = find_n4_corte_instances(
            corte_path, section_views=entry.get("section_views") or [],
        )
        # Faixa X do corte no recorte N2: vem do bbox que a propria ficha
        # registra por secao (generalizado 2026-09-11 — antes era a faixa fixa
        # da V301, x~5100-5500, que nao vale para as outras vigas).
        _xs = [
            (float(sv["bbox"]["x_left"]), float(sv["bbox"]["x_right"]))
            for sv in (entry.get("section_views") or [])
            if isinstance(sv.get("bbox"), dict)
            and sv["bbox"].get("x_left") is not None
        ]
        if _xs:
            _x_range = (min(a for a, _ in _xs) - 40.0,
                        max(b for _, b in _xs) + 40.0)
        else:
            _x_range = None
        n2_corte_insts = (
            find_n2_corte_instances(n2_path, x_range=_x_range) if _x_range else []
        )
        for idx in range(min(len(n4_corte_insts), len(n2_corte_insts))):
            corte_pairs.append({
                "idx": idx,
                "n4_label": n4_corte_insts[idx]["label"],
                "clip_n2": n2_corte_insts[idx]["clip"],
                "clip_n4": n4_corte_insts[idx]["clip"],
            })

    # N2 full (overview) — recorte inteiro
    out_n2 = PREV / f"FULL_N2_recorte_{n2_tag}.png"
    ok_n2 = out_n2.exists() or render_dxf_clip(
        n2_path, out_n2, clip=None, title="N2 recorte completo (DXF original)", width_px=1200, height_px=520
    )
    full_n2 = f"previews_dxf/{out_n2.name}" if ok_n2 else None

    # per-result previews: clip N2 bbox + clip N4 band
    pairs_by_side = {
        s: pair_units(n2_by_side[s], n4_units[s]) for s in ("A", "B")
    }
    # index by n2 label for n4 unit lookup from gate results
    n4_lookup = {}
    for side, pairs in pairs_by_side.items():
        for pr in pairs:
            if pr.get("status") != "paired":
                continue
            u2, u4 = pr["n2"], pr["n4"]
            lab = unit_label(u2, u2.get("_idx", 0))
            n4_lookup.setdefault((side, lab), []).append((u2, u4))

    lookup_occurrence = {}

    for i, r in enumerate(results):
        r["preview_n2_svg"] = None
        r["preview_n4_svg"] = None
        side = str(r.get("side") or "")
        lab = str(r.get("label") or "")
        if side not in ("A", "B"):
            continue
        key = (side, lab)
        if key not in n4_lookup:
            # try n4_label match
            for (s, l), pairs in n4_lookup.items():
                if s == side and (
                    l == lab
                    or any(p[1].get("label") == r.get("n4_label") for p in pairs)
                ):
                    key = (s, l)
                    break
        if key not in n4_lookup:
            continue
        occurrence = lookup_occurrence.get(key, 0)
        pairs = n4_lookup[key]
        u2, u4 = pairs[min(occurrence, len(pairs) - 1)]
        lookup_occurrence[key] = occurrence + 1
        a2 = n2_anchor(u2)
        a4 = n4_anchor(u4, widths_fallback=a2["panel_widths"])
        ox2, oy2 = a2["origin"]
        # clip N2 em coords absolutas do recorte
        c2 = a2["clip"]  # rel
        clip_n2 = (ox2 + c2[0], oy2 + c2[1], ox2 + c2[2], oy2 + c2[3])
        clip_n2 = _expandir_ate_borda_de_painel(n2_path, clip_n2)
        ox4, oy4 = a4["origin"]
        c4 = a4["clip"]
        clip_n4 = (ox4 + c4[0], oy4 + c4[1], ox4 + c4[2], oy4 + c4[3])

        # SVG por elemento (nao PNG raster): cada LINE/TEXT/HATCH/DIMENSION
        # do recorte vira seu proprio <g data-layer/data-type/data-handle>
        # no DOM, para o clique do dono mapear direto na entidade real —
        # sem eu ter que recalcular posicao por pixel/porcentagem cada vez
        # que ele aponta "essa linha aqui" (pedido do dono, 2026-08-31).
        sp2 = PREV / f"seg_{i:02d}_N2_{n2_tag}.svg"
        sp4 = PREV / f"seg_{i:02d}_N4_{n4_tag}.svg"
        if sp2.exists():
            r["preview_n2_svg"] = sp2.read_text(encoding="utf-8")
        else:
            svg2 = render_dxf_clip_svg(n2_path, clip=clip_n2, id_prefix=f"s{i}n2")
            if svg2:
                sp2.write_text(svg2, encoding="utf-8")
                r["preview_n2_svg"] = svg2
        n4p = n4_paths[side]
        if n4p.exists():
            if sp4.exists():
                r["preview_n4_svg"] = sp4.read_text(encoding="utf-8")
            else:
                svg4 = render_dxf_clip_svg(n4p, clip=clip_n4, id_prefix=f"s{i}n4")
                if svg4:
                    sp4.write_text(svg4, encoding="utf-8")
                    r["preview_n4_svg"] = svg4

    def sort_key(r):
        lab = str(r.get("label") or "")
        side = str(r.get("side") or "")
        primary = 0 if lab in (f"{viga}.A", f"{viga}.B") else (1 if "CONT" in lab else 2)
        return (side, primary, lab)

    ordered = sorted(
        enumerate(
            r for r in results
            if str(r.get("side") or "").upper() in {"A", "B"}
            and str(r.get("pair_status") or "") == "paired"
        ),
        key=lambda t: sort_key(t[1]),
    )
    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    prim = [r for r in results if r.get("label") in (f"{viga}.A", f"{viga}.B")]

    parts = [
        """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"/>
<title>V301 · Segmentos DXF real N2×N4</title>
<style>
body{font-family:system-ui,sans-serif;background:#0b1220;color:#e5e7eb;margin:0}
header{padding:16px 22px;background:#0f172a;border-bottom:1px solid #1f2937}
h1{margin:0 0 6px;font-size:1.25rem}.mut{color:#94a3b8;font-size:.9rem}
.ok{color:#34d399;font-weight:700}.fail{color:#f87171;font-weight:700}.sus{color:#fbbf24;font-weight:700}
main{padding:18px 22px 60px;max-width:1600px;margin:0 auto}
.card{background:#111827;border:1px solid #1f2937;border-radius:12px;padding:14px;margin:14px 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:1000px){.grid2{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th,td{border-bottom:1px solid #1f2937;padding:7px 8px;text-align:left;vertical-align:top}
th{color:#94a3b8}
.primary{outline:1px solid #34d39966;background:#052e1a44}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.75rem;font-weight:700}
.badge.ok{background:#064e3b;color:#6ee7b7}.badge.fail{background:#7f1d1d;color:#fca5a5}.badge.sus{background:#78350f;color:#fcd34d}
img.preview{width:100%;border-radius:8px;border:1px solid #334155;background:#fff}
code{color:#fde68a}.kpi{font-size:1.35rem;font-weight:800}
.warn{background:#422006;border:1px solid #b45309;color:#fde68a;padding:10px 12px;border-radius:8px;margin:10px 0}
.segment-head{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap}
.validated{width:18px;height:18px;vertical-align:middle}.validation{white-space:nowrap;font-weight:700}
.attention{display:block;margin-top:10px;font-weight:700}.note{display:block;box-sizing:border-box;width:100%;margin-top:4px;background:#0b1220;color:#e5e7eb;border:1px solid #475569;border-radius:6px;padding:8px;font:inherit}
.imgwrap{position:relative;cursor:grab;height:480px;overflow:hidden;border-radius:8px}
.imgwrap.dragging{cursor:grabbing}
.pz-reset{position:absolute;top:6px;right:6px;z-index:2;background:#1f2937cc;color:#e5e7eb;border:1px solid #475569;border-radius:6px;padding:3px 8px;font-size:11px;cursor:pointer}
.pz-reset:hover{background:#334155cc}
.click-dot{position:absolute;width:14px;height:14px;margin-left:-7px;margin-top:-7px;border-radius:50%;border:2px solid #fff;box-shadow:0 0 2px #000;pointer-events:none}
.click-label{position:absolute;margin-left:9px;margin-top:-16px;font-size:11px;font-weight:700;color:#fff;text-shadow:0 0 3px #000,0 0 3px #000;pointer-events:none;font-family:monospace}
.points-list-head{margin-top:8px}
.copy-all-points{background:#1f2937;color:#e5e7eb;border:1px solid #475569;border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer}
.copy-all-points:hover{background:#334155}
.copy-all-points[hidden]{display:none}
.points-list{margin-top:8px;display:flex;flex-direction:column;gap:6px}
.point-row{display:flex;gap:6px;align-items:center;font-size:12px}
.point-row input{flex:1;background:#0b1220;color:#e5e7eb;border:1px solid #475569;border-radius:6px;padding:4px 6px;font:inherit}
.point-row button{width:24px;background:#1f2937;color:#e5e7eb;border:1px solid #475569;border-radius:6px;cursor:pointer}
.point-row .elem-tag{font-family:monospace;font-size:10px;color:#93c5fd;background:#1e293b;border-radius:4px;padding:1px 5px;white-space:nowrap}
.point-row-removed{opacity:0.75}
.point-row-removed button{width:auto;padding:3px 8px;font-size:11px}
.dxf-svg{border:1px solid #334155}
.dxf-el{cursor:pointer}
.dxf-el:hover line,.dxf-el:hover path,.dxf-el:hover text{filter:drop-shadow(0 0 0.6px #0ea5e9) drop-shadow(0 0 1.5px #0ea5e9)}
.dxf-el.dxf-picked line,.dxf-el.dxf-picked path{stroke:#0ea5e9!important;stroke-width:1.6!important}
.dxf-el.dxf-picked text{fill:#0ea5e9!important}
.dxf-el.dxf-picked{cursor:default}
.dxf-el.dxf-picked *{pointer-events:none!important}
</style></head><body>
<header>
<h1>V301 · Segmentos com DXF real (ezdxf)</h1>
<p class="mut">N2 = recorte original clipado · N4 = VIEW gerada clipada · cores/layers/cotas via Frontend ezdxf (não wireframe de ledger).</p>
</header><main>
<div class="warn"><b>Transparência:</b> o HTML anterior usava só linhas do GeometryIndex (fidelidade baixa).
Este usa render do DXF. O gate numérico (R/G) continua no ledger; o visual abaixo é o desenho de verdade para você julgar se “parece N2”.</div>
"""
    ]

    # full overviews
    parts.append('<div class="card"><h2>Visão completa DXF</h2><div class="grid2">')
    if full_n2:
        parts.append(f'<div><div class="mut">N2 recorte</div><img class="preview" src="{html.escape(full_n2)}"/></div>')
    for side in ("A", "B"):
        if full_prev.get(side):
            parts.append(
                f'<div><div class="mut">N4 VIEW_{side}</div>'
                f'<img class="preview" src="{html.escape(full_prev[side])}"/></div>'
            )
    if full_corte:
        parts.append(
            f'<div><div class="mut">N4 CORTE (classe separada dos painéis A/B)</div>'
            f'<img class="preview" src="{html.escape(full_corte)}"/></div>'
        )
    parts.append("</div></div>")

    parts.append('<div class="card"><h2>Faces nominais A/B (métricas gate)</h2><div class="grid2">')
    for r in prim:
        m = r.get("metrics") or {}
        v = r["verdict"]
        parts.append(
            f"""<div class="primary" style="padding:12px;border-radius:10px">
<div><span class="badge {_cls(v)}">{html.escape(v)}</span>
 <b>{html.escape(str(r.get('label')))}</b> ↔ <code>{html.escape(str(r.get('n4_label')))}</code></div>
<div class="kpi">R {100*float(m.get('r_match') or 0):.0f}% · G {100*float(m.get('g_match') or 0):.0f}%</div>
<div class="mut">inventadas {html.escape(str(m.get('invented_r') or []))}</div>
</div>"""
        )
    parts.append("</div></div>")

    parts.append('<div class="card"><h2>Resumo multi-segmento</h2><ul>')
    for k in ("PASS E2E", "FAIL E2E", "SUSPEITO"):
        if counts.get(k):
            parts.append(f"<li class='{_cls(k)}'>{k}: <b>{counts[k]}</b></li>")
    parts.append(f"</ul><p class='mut'>Total: {len(results)} · {html.escape(str(data.get('schema')))}</p></div>")

    parts.append('<div class="card"><h2>Tabela</h2><table>')
    parts.append(
        "<tr><th>#</th><th>N2</th><th>N4</th><th>Side</th><th>Pair</th>"
        "<th>Veredito</th><th>R%</th><th>G%</th><th>Inv</th><th>Motivos</th></tr>"
    )
    for i, r in ordered:
        m = r.get("metrics") or {}
        v = r["verdict"]
        lab = str(r.get("label") or "")
        row = "primary" if lab in (f"{viga}.A", f"{viga}.B") else ""
        parts.append(
            f"<tr class='{row}'><td>{i}</td>"
            f"<td><code>{html.escape(lab)}</code></td>"
            f"<td><code>{html.escape(str(r.get('n4_label') or '—'))}</code></td>"
            f"<td>{html.escape(str(r.get('side')))}</td>"
            f"<td class='mut'>{html.escape(str(r.get('pair_status')))}</td>"
            f"<td class='{_cls(v)}'>{html.escape(v)}</td>"
            f"<td>{100*float(m.get('r_match') or 0):.0f}%</td>"
            f"<td>{100*float(m.get('g_match') or 0):.0f}%</td>"
            f"<td>{html.escape(str(m.get('invented_r') or [])[:40])}</td>"
            f"<td class='mut'>{html.escape(' · '.join(r.get('reasons') or [])[:140])}</td></tr>"
        )
    parts.append("</table></div>")

    parts.append('<div class="card"><h2>Revisão por segmento (N2 clip | N4 clip)</h2><p class="mut">Cada cartão tem obrigatoriamente seu par N2×N4. A nomenclatura é sequencial por lado: SEGMENTO 1A, 2A, …, 1B, 2B.</p>')
    segment_ordinals = {"A": 0, "B": 0}
    for i, r in ordered:
        m = r.get("metrics") or {}
        v = r["verdict"]
        lab = str(r.get("label") or "")
        side = str(r.get("side") or "").upper()
        segment_ordinals[side] += 1
        segment_name = f"SEGMENTO {segment_ordinals[side]}{side}"
        box = "primary" if lab in (f"{viga}.A", f"{viga}.B") else ""
        legacy_key = f"LV::13_PAV::{viga}::{r.get('side')}::{lab}::{r.get('n4_label') or 'ausente'}"
        review_key = f"LV::13_PAV::{viga}::{segment_name}::{i}::{lab}::{r.get('n4_label') or 'ausente'}"
        parts.append(
            f'<article class="card segment-card {box}" '
            f'data-key="{html.escape(review_key, quote=True)}" '
            f'data-legacy-key="{html.escape(legacy_key, quote=True)}" '
            'style="margin:10px 0">'
        )
        parts.append(
            f"<div class='segment-head'><div><span class='badge {_cls(v)}'>{html.escape(v)}</span> "
            f"<b>{segment_name}</b> <span class='mut'>#{i}</span> <code>{html.escape(lab)}</code> ↔ "
            f"<code>{html.escape(str(r.get('n4_label') or '—'))}</code> · "
            f"R {100*float(m.get('r_match') or 0):.0f}% · G {100*float(m.get('g_match') or 0):.0f}%</div>"
            "<label class='validation'><input class='validated' type='checkbox'> Validado</label></div>"
        )
        svg2, svg4 = r.get("preview_n2_svg"), r.get("preview_n4_svg")
        if svg2 or svg4:
            parts.append('<div class="grid2">')
            if svg2:
                parts.append(
                    '<div><div class="mut">N2 original (clip) · '
                    '<span class="mut">arraste p/ mover, roda p/ zoom, clique num elemento p/ marcar</span></div>'
                    f'<div class="imgwrap" data-side="n2">{svg2}'
                    '<button type="button" class="pz-reset" data-pz-reset>reset zoom</button></div></div>'
                )
            if svg4:
                parts.append(
                    '<div><div class="mut">N4 gerado (clip) · '
                    '<span class="mut">arraste p/ mover, roda p/ zoom, clique num elemento p/ marcar</span></div>'
                    f'<div class="imgwrap" data-side="n4">{svg4}'
                    '<button type="button" class="pz-reset" data-pz-reset>reset zoom</button></div></div>'
                )
            parts.append("</div>")
        else:
            parts.append("<p class='mut'>sem par clipável (n2_only / n4_only / CORTE)</p>")
        parts.append(
            f"<p class='mut'>{html.escape(' · '.join(r.get('reasons') or [])[:220])}</p>"
            "<div class='mut' style='margin-top:8px'>Clique na imagem N2 ou N4 acima para marcar um ponto de incoerência.</div>"
            "<div class='points-list-head'>"
            "<button type='button' class='copy-all-points' title='copiar referência de todos os pontos deste card'>📋 copiar todos os pontos</button>"
            "</div>"
            "<div class='points-list'></div>"
            "<label class='attention'>Atenção / observação geral"
            "<textarea class='note' rows='3' placeholder='Salva automaticamente neste navegador'></textarea>"
            "</label></article>"
        )

    # Cards granulares de VISAO CORTE — classe separada dos paineis A/B,
    # um card por instancia real de corte que a viga possui (N2 real x N4
    # gerado), abaixo dos segmentos de painel (pedido do dono, 2026-09-10).
    if corte_pairs:
        parts.append(
            '<div class="card"><h2>Revisão por visão de CORTE (N2 clip | N4 clip)</h2>'
            '<p class="mut">Classe separada dos painéis A/B — uma seção transversal '
            'por instância real que a viga possui.</p>'
        )
        for cp in corte_pairs:
            n4_label = cp["n4_label"]
            review_key = f"LV::13_PAV::{viga}::CORTE {cp['idx']+1}::{n4_label}"
            parts.append(
                f'<article class="card segment-card" data-key="{html.escape(review_key, quote=True)}" '
                'style="margin:10px 0">'
            )
            parts.append(
                f"<div class='segment-head'><div><b>CORTE {cp['idx']+1}</b> "
                f"<code>{html.escape(n4_label)}</code></div>"
                "<label class='validation'><input class='validated' type='checkbox'> Validado</label></div>"
            )
            svg2 = render_dxf_clip_svg(n2_path, clip=cp["clip_n2"], id_prefix=f"corte{cp['idx']}n2")
            svg4 = render_dxf_clip_svg(corte_path, clip=cp["clip_n4"], id_prefix=f"corte{cp['idx']}n4")
            if svg2 or svg4:
                parts.append('<div class="grid2">')
                if svg2:
                    parts.append(
                        '<div><div class="mut">N2 original (clip) · '
                        '<span class="mut">arraste p/ mover, roda p/ zoom, clique num elemento p/ marcar</span></div>'
                        f'<div class="imgwrap" data-side="n2">{svg2}'
                        '<button type="button" class="pz-reset" data-pz-reset>reset zoom</button></div></div>'
                    )
                if svg4:
                    parts.append(
                        '<div><div class="mut">N4 gerado (clip) · '
                        '<span class="mut">arraste p/ mover, roda p/ zoom, clique num elemento p/ marcar</span></div>'
                        f'<div class="imgwrap" data-side="n4">{svg4}'
                        '<button type="button" class="pz-reset" data-pz-reset>reset zoom</button></div></div>'
                    )
                parts.append("</div>")
            else:
                parts.append("<p class='mut'>sem clip renderizável</p>")
            parts.append(
                "<div class='mut' style='margin-top:8px'>Clique na imagem N2 ou N4 acima para marcar um ponto de incoerência.</div>"
                "<div class='points-list-head'>"
                "<button type='button' class='copy-all-points' title='copiar referência de todos os pontos deste card'>📋 copiar todos os pontos</button>"
                "</div>"
                "<div class='points-list'></div>"
                "<label class='attention'>Atenção / observação geral"
                "<textarea class='note' rows='3' placeholder='Salva automaticamente neste navegador'></textarea>"
                "</label></article>"
            )
        parts.append("</div>")

    parts.append("""</div></main><script>
const prefix='cad_analyzer_review_';
const cards=[...document.querySelectorAll('.segment-card')];
function cookieNameFor(key){return prefix+key.replace(/[^a-zA-Z0-9]/g,'_');}
function cookieName(card){return cookieNameFor(card.dataset.key);}
function readCookie(key){try{const name=cookieNameFor(key)+'=';const part=document.cookie.split('; ').find(row=>row.startsWith(name));return part?JSON.parse(decodeURIComponent(part.slice(name.length))):{};}catch(_){return {};}}
function read(card){const current=readCookie(card.dataset.key);if(current.validated||current.note)return current;return readCookie(card.dataset.legacyKey||'');}
function sync(key,data){fetch('/api/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({[key]:data})}).catch(()=>{});}
function save(card){const data={validated:card.querySelector('.validated').checked,note:card.querySelector('.note').value,points:(card._points||[]).filter(p=>!p._removed),updated_at:new Date().toISOString()};try{const value=encodeURIComponent(JSON.stringify(data));if(value.length>3500)throw Error('nota longa');document.cookie=`${cookieName(card)}=${value}; Max-Age=31536000; Path=/; SameSite=Lax`;sync(card.dataset.key,data);}catch(_){sync(card.dataset.key,data);}}
const pointColors=['#f87171','#60a5fa','#4ade80','#fbbf24','#c084fc','#f472b6','#2dd4bf','#fb923c'];
// Zoom/pan por viewBox (padrao do projeto, docs/PADRAO-SVG-WEB-PANZOOM-VIEWBOX.md).
// Arrastar move o desenho; roda do mouse aplica zoom centrado no cursor;
// duplo-clique ou o botao "reset zoom" volta ao home. O ponto marcado so
// existe se o clique realmente caiu num elemento DXF (.dxf-el) — pedido do
// dono, 2026-08-31: nao marcar ponto em fundo vazio.
function initSvgPanZoom(wrap){
  const svg=wrap.querySelector('svg.dxf-svg');
  if(!svg||wrap.dataset.pzInit==='1')return;
  wrap.dataset.pzInit='1';
  const base=svg.viewBox.baseVal;
  const home={x:base.x,y:base.y,w:base.width,h:base.height};
  if(!isFinite(home.w)||home.w<=0)return;
  const state={x:home.x,y:home.y,w:home.w,h:home.h};
  function apply(){svg.setAttribute('viewBox',`${state.x} ${state.y} ${state.w} ${state.h}`);renderDots(wrap.closest('.segment-card'));}
  function reset(){state.x=home.x;state.y=home.y;state.w=home.w;state.h=home.h;apply();}
  wrap._pzReset=reset;
  function clientToSvg(cx,cy){
    const pt=svg.createSVGPoint();pt.x=cx;pt.y=cy;
    const ctm=svg.getScreenCTM();
    if(!ctm)return{x:state.x+state.w/2,y:state.y+state.h/2};
    return pt.matrixTransform(ctm.inverse());
  }
  wrap.addEventListener('wheel',e=>{
    e.preventDefault();
    let factor=e.deltaY<0?0.88:1.14;
    let nextW=state.w*factor,nextH=state.h*factor;
    const minW=home.w*0.04,maxW=home.w*4;
    if(nextW<minW){factor=minW/state.w;nextW=minW;nextH=state.h*factor;}
    if(nextW>maxW){factor=maxW/state.w;nextW=maxW;nextH=state.h*factor;}
    const p=clientToSvg(e.clientX,e.clientY);
    state.x=p.x-(p.x-state.x)*(nextW/state.w);
    state.y=p.y-(p.y-state.y)*(nextH/state.h);
    state.w=nextW;state.h=nextH;apply();
  },{passive:false});
  let dragging=false,lx=0,ly=0;
  wrap._dragMoved=0;
  wrap.addEventListener('mousedown',e=>{
    if(e.button!==0)return;
    if(e.target&&e.target.closest&&e.target.closest('button'))return;
    dragging=true;lx=e.clientX;ly=e.clientY;wrap._dragMoved=0;
    wrap.classList.add('dragging');
  });
  window.addEventListener('mousemove',e=>{
    if(!dragging)return;
    const ctm=svg.getScreenCTM();if(!ctm)return;
    const inv=ctm.inverse();
    const p0=svg.createSVGPoint();p0.x=lx;p0.y=ly;
    const p1=svg.createSVGPoint();p1.x=e.clientX;p1.y=e.clientY;
    const a=p0.matrixTransform(inv),b=p1.matrixTransform(inv);
    state.x-=(b.x-a.x);state.y-=(b.y-a.y);
    wrap._dragMoved+=Math.abs(e.clientX-lx)+Math.abs(e.clientY-ly);
    lx=e.clientX;ly=e.clientY;apply();
  });
  window.addEventListener('mouseup',()=>{
    if(!dragging)return;dragging=false;wrap.classList.remove('dragging');
  });
  wrap.addEventListener('dblclick',e=>{
    if(e.target&&e.target.closest&&e.target.closest('button'))return;
    reset();
  });
  const btn=wrap.querySelector('[data-pz-reset]');
  if(btn)btn.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();reset();});
}
// Elemento ja marcado: trava (sem reclique) e manda pra tras no z-order
// (primeiro filho do <g> = pintado primeiro = fica atras de tudo que veio
// depois na ordem do DXF), pra nao atrapalhar a selecao de elementos
// vizinhos empilhados no mesmo lugar (pedido do dono, 2026-08-31).
function markPicked(target){
  if(!target||target.classList.contains('dxf-picked'))return;
  target.classList.add('dxf-picked');
  if(target.parentNode)target.parentNode.prepend(target);
}
// Ao excluir o ponto, o elemento associado destrava (fica selecionavel de
// novo) — sem isso, uma linha apagada da lista continuava presa pra
// sempre, mesmo sem nenhum ponto mais se referindo a ela (pedido do dono,
// 2026-09-08). Nao desfaz o reordenamento pro fundo (nao guardamos a
// posicao original), so remove a trava de clique/hover.
function unmarkPicked(card, elementId){
  if(!elementId)return;
  card.querySelectorAll('.imgwrap svg.dxf-svg').forEach(svg=>{
    const el=svg.querySelector('#'+CSS.escape(elementId));
    if(el)el.classList.remove('dxf-picked');
  });
}
function renderDots(card){
  card.querySelectorAll('.imgwrap').forEach(wrap=>{
    wrap.querySelectorAll('.click-dot,.click-label').forEach(el=>el.remove());
    const side=wrap.dataset.side;
    const wRect=wrap.getBoundingClientRect();
    let _vi=-1;
    (card._points||[]).forEach((p)=>{
      if(p._removed)return;
      _vi++;
      if(p.side!==side)return;
      const c=pointColors[_vi%pointColors.length];
      let x=p.x,y=p.y;
      // reancorra no elemento real (se ainda existir nesta geracao do SVG)
      // para o ponto acompanhar o desenho durante pan/zoom.
      const el=p.element&&p.element.id?wrap.querySelector('#'+CSS.escape(p.element.id)):null;
      if(el)markPicked(el);
      if(el&&wRect.width>0&&wRect.height>0){
        const r=el.getBoundingClientRect();
        x=(r.left+r.width/2-wRect.left)/wRect.width;
        y=(r.top+r.height/2-wRect.top)/wRect.height;
      }
      if(x<-0.05||x>1.05||y<-0.05||y>1.05)return;
      const dot=document.createElement('div');
      dot.className='click-dot';dot.style.left=(x*100)+'%';dot.style.top=(y*100)+'%';dot.style.background=c;
      wrap.appendChild(dot);
      const lb=document.createElement('div');
      lb.className='click-label';lb.style.left=(x*100)+'%';lb.style.top=(y*100)+'%';lb.style.color=c;lb.textContent=String(_vi+1);
      wrap.appendChild(lb);
    });
  });
}
// Referencia compacta de um ponto: cola no chat e o agente ja sabe qual
// card/elemento/nota sem precisar reler o revisoes_humanas.json inteiro
// (pedido do dono, 2026-09-08 — "economizar tokens" ao apontar um ponto).
function pointRefText(card, p, i){
  const parts=[card.dataset.key, `P${i+1} ${p.side}`];
  if(p.element){
    const el=p.element;
    let s=`${el.type}·${el.layer}`;
    if(el.pattern) s+=` pattern=${el.pattern}`;
    if(el.handle) s+=` handle=${el.handle}`;
    if(el.text) s+=` texto="${el.text}"`;
    if(el.length_cm) s+=` ${el.length_cm}cm`;
    if(el.coords){
      const c=el.coords;
      s+= (c.x2!==undefined)
        ? ` @(${c.x1.toFixed(1)},${c.y1.toFixed(1)})->(${c.x2.toFixed(1)},${c.y2.toFixed(1)})`
        : ` @(${c.x1.toFixed(1)},${c.y1.toFixed(1)})`;
    }
    parts.push(s);
  }
  if(p.note) parts.push(`nota: "${p.note}"`);
  return parts.join(' | ');
}
function renderPoints(card){
  const list=card.querySelector('.points-list');
  if(!list)return;
  list.innerHTML='';
  const copyAllBtn=card.querySelector('.copy-all-points');
  const activeCount=(card._points||[]).filter(p=>!p._removed).length;
  if(copyAllBtn){
    copyAllBtn.hidden=!activeCount;
  }
  let vi=-1;
  (card._points||[]).forEach((p,i)=>{
    // Exclusao "leve": o ponto some do render normal, dos dots e do que e
    // salvo no servidor, mas continua em card._points ate a pagina
    // recarregar — so assim um botao de desfazer no LUGAR onde ele estava
    // pode trazer ele de volta (pedido do dono, 2026-09-09: "me arrepender"
    // de uma exclusao sem precisar remarcar o ponto do zero). Some de vez
    // so quando a pagina for recarregada (save() ja filtra _removed).
    if(p._removed){
      const row=document.createElement('div');
      row.className='point-row point-row-removed';
      const lbl=document.createElement('span');
      lbl.style.cssText='flex:1;color:#94a3b8;font-style:italic;font-size:11px;';
      lbl.textContent='ponto removido';
      const undo=document.createElement('button');
      undo.type='button';undo.textContent='↺ desfazer';
      undo.style.cssText='white-space:nowrap;';
      undo.addEventListener('click',()=>{
        delete p._removed;
        if(p.element&&p.element.id){
          const wrap=card.querySelector(`.imgwrap[data-side="${p.side}"]`);
          const el=wrap&&wrap.querySelector('#'+CSS.escape(p.element.id));
          if(el)markPicked(el);
        }
        renderDots(card);renderPoints(card);save(card);
      });
      row.appendChild(lbl);row.appendChild(undo);
      list.appendChild(row);
      return;
    }
    vi++;
    const c=pointColors[vi%pointColors.length];
    const row=document.createElement('div');
    row.className='point-row';
    const lbl=document.createElement('span');
    lbl.style.cssText=`min-width:70px;color:${c};font-family:monospace;`;
    lbl.textContent=`P${vi+1} ${p.side.toUpperCase()}`;
    const inp=document.createElement('input');
    inp.type='text';inp.placeholder='nota sobre este ponto';inp.value=p.note||'';
    inp.addEventListener('input',()=>{p.note=inp.value;save(card);});
    const cp=document.createElement('button');
    cp.type='button';cp.textContent='📋';cp.title='copiar referência deste ponto';
    cp.addEventListener('click',()=>{
      const text=pointRefText(card,p,vi);
      const done=()=>{cp.textContent='✓';setTimeout(()=>{cp.textContent='📋';},1200);};
      if(navigator.clipboard&&navigator.clipboard.writeText){
        navigator.clipboard.writeText(text).then(done).catch(done);
      }else{
        const ta=document.createElement('textarea');
        ta.value=text;ta.style.position='fixed';ta.style.opacity='0';
        document.body.appendChild(ta);ta.select();
        try{document.execCommand('copy');}catch(_){}
        document.body.removeChild(ta);done();
      }
    });
    const rm=document.createElement('button');
    rm.type='button';rm.textContent='×';
    rm.addEventListener('click',()=>{
      unmarkPicked(card,p.element&&p.element.id);
      p._removed=true;renderDots(card);renderPoints(card);save(card);
    });
    row.appendChild(lbl);
    if(p.element){
      const tag=document.createElement('span');
      tag.className='elem-tag';
      tag.title=`handle=${p.element.handle}`+(p.element.pattern?` pattern=${p.element.pattern}`:'')+(p.element.text?` texto="${p.element.text}"`:'')+(p.element.length_cm?` ${p.element.length_cm}cm`:'');
      tag.textContent=`${p.element.type}·${p.element.layer}`;
      row.appendChild(tag);
    }
    row.appendChild(inp);row.appendChild(cp);row.appendChild(rm);
    list.appendChild(row);
  });
}
function applyState(state){
  cards.forEach(card=>{
    const saved=(state&&(state[card.dataset.key]||state[card.dataset.legacyKey||'']))||read(card)||{};
    card.querySelector('.validated').checked=!!saved.validated;
    card.querySelector('.note').value=saved.note||'';
    card._points=Array.isArray(saved.points)?saved.points:[];
    const copyAllBtn=card.querySelector('.copy-all-points');
    if(copyAllBtn){
      copyAllBtn.addEventListener('click',()=>{
        const text=(card._points||[]).filter(p=>!p._removed).map((p,i)=>pointRefText(card,p,i)).join('\\n');
        const done=()=>{copyAllBtn.textContent='✓ copiado';setTimeout(()=>{copyAllBtn.textContent='📋 copiar todos os pontos';},1200);};
        if(navigator.clipboard&&navigator.clipboard.writeText){
          navigator.clipboard.writeText(text).then(done).catch(done);
        }else{
          const ta=document.createElement('textarea');
          ta.value=text;ta.style.position='fixed';ta.style.opacity='0';
          document.body.appendChild(ta);ta.select();
          try{document.execCommand('copy');}catch(_){}
          document.body.removeChild(ta);done();
        }
      });
    }
    card.querySelector('.validated').addEventListener('change',()=>save(card));
    card.querySelector('.note').addEventListener('input',()=>save(card));
    card.querySelectorAll('.imgwrap').forEach(wrap=>{
      initSvgPanZoom(wrap);
      wrap.addEventListener('click',(e)=>{
        if(e.target&&e.target.closest&&e.target.closest('button'))return;
        // arrastar (pan) tambem dispara 'click' no mouseup — so conta como
        // marcacao de ponto se o mouse quase nao se moveu.
        if((wrap._dragMoved||0)>4)return;
        // so marca ponto se o clique caiu de fato num elemento DXF (LINE/
        // TEXT/HATCH/...), nunca no fundo vazio do SVG (pedido do dono).
        const target=e.target.closest('.dxf-el');
        if(!target)return;
        const rect=wrap.getBoundingClientRect();
        const tr=target.getBoundingClientRect();
        const x=(tr.left+tr.width/2-rect.left)/rect.width;
        const y=(tr.top+tr.height/2-rect.top)/rect.height;
        // elemento ja marcado antes: ignora o clique (nao gera ponto
        // duplicado) — o proprio markPicked ja tirou o pointer-events dele,
        // isso aqui e' so um fallback defensivo.
        if(target.classList.contains('dxf-picked'))return;
        card._points=card._points||[];
        markPicked(target);
        // Coordenadas reais do DXF (nao pixel/SVG) — o handle muda a cada
        // regeneracao, mas a posicao geometrica e' estavel; dono pediu pra
        // apontar o elemento geometricamente em vez de so' por handle
        // (2026-09-10). y guardado no SVG e' -y_dxf (fy() em Python), entao
        // desfaz o sinal aqui pra devolver a coordenada real.
        let coords=null;
        const lineEl=target.querySelector('line');
        if(lineEl){
          coords={
            x1:parseFloat(lineEl.getAttribute('x1')),
            y1:-parseFloat(lineEl.getAttribute('y1')),
            x2:parseFloat(lineEl.getAttribute('x2')),
            y2:-parseFloat(lineEl.getAttribute('y2')),
          };
        }else{
          const pathEl=target.querySelector('path');
          if(pathEl){
            const d=pathEl.getAttribute('d')||'';
            const nums=(d.match(/-?\d+\.?\d*/g)||[]).map(Number);
            if(nums.length>=2) coords={x1:nums[0],y1:-nums[1]};
          }
        }
        const point={
          side:wrap.dataset.side,x,y,note:'',
          element:{
            id:target.id,
            layer:target.dataset.layer||'',
            type:target.dataset.type||'',
            handle:target.dataset.handle||'',
            text:target.dataset.text||'',
            length_cm:target.dataset.lengthCm||'',
            pattern:target.dataset.pattern||'',
            coords,
          },
        };
        card._points.push(point);
        renderDots(card);renderPoints(card);save(card);
      });
    });
    renderDots(card);renderPoints(card);
  });
}
fetch('revisoes_humanas.json',{cache:'no-store'})
  .then(r=>r.ok?r.json():{})
  .then(applyState)
  .catch(()=>applyState({}));

let lastDxfVersion = '';
let dxfPollTimer = null;
async function checkDxfHotReload() {
  try {
    const res = await fetch('/api/dxf-version', { cache: 'no-store' });
    if (!res.ok) return;
    const data = await res.json();
    if (data.ok && data.version) {
      if (!lastDxfVersion) {
        lastDxfVersion = String(data.version);
      } else if (lastDxfVersion !== String(data.version)) {
        lastDxfVersion = String(data.version);
        location.reload();
      }
    }
  } catch (_) {}
}
function startDxfPolling() {
  if (dxfPollTimer) return;
  dxfPollTimer = setInterval(checkDxfHotReload, 800);
}
function stopDxfPolling() {
  if (dxfPollTimer) { clearInterval(dxfPollTimer); dxfPollTimer = null; }
}
// setInterval sozinho e' throttled/pausado pelo navegador quando a aba fica em
// background (Chrome pode cair pra ~1 tick/min ou menos). Isso faz o hot-reload
// "sumir" justamente quando o usuario troca de janela pra olhar o resultado de
// uma edicao e volta. Forcamos uma checagem imediata sempre que a aba volta a
// ficar visivel/focada, alem do polling normal em primeiro plano.
startDxfPolling();
checkDxfHotReload();
document.addEventListener('visibilitychange', () => {
  if (document.hidden) { stopDxfPolling(); }
  else { checkDxfHotReload(); startDxfPolling(); }
});
window.addEventListener('focus', () => { checkDxfHotReload(); startDxfPolling(); });
window.addEventListener('pageshow', () => { checkDxfHotReload(); startDxfPolling(); });
</script></body></html>""")

    # Estado da revisao humana mora em arquivo, ao lado da pagina (mesmo
    # mecanismo do painel LAJ). Sem semear, a pagina servida por
    # `servidor_revisao_pil.py` carrega vazia no primeiro acesso.
    _estado = GATE / "revisoes_humanas.json"
    if not _estado.exists():
        _estado.write_text("{}", encoding="utf-8")

    out = GATE / f"{viga}_SEGMENTS_E2E.html"
    # O cabecalho vem de um bloco triplo com CSS (chaves), entao nao pode ser
    # f-string: o nome da viga entra aqui, na escrita.
    html_out = "".join(parts).replace("V301 · Segmentos", f"{viga} · Segmentos")
    out.write_text(html_out, encoding="utf-8")
    print("previews in", PREV)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("item", nargs="?", default="V301",
                    help="Viga LV a montar (default V301, item de calibracao)")
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()
    path = build(args.item)
    print("HTML", path)
    if args.open:
        webbrowser.open(path.resolve().as_uri())


if __name__ == "__main__":
    main()
