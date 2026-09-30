# -*- coding: utf-8 -*-
"""Viewer unico de depuracao das laterais: SA x N3 x N4, por viga e segmento.

Um so' HTML, com quatro niveis de aba:

    VIGA  ->  CAMADA  ->  LADO A|B  ->  SEGMENTOS daquele lado

A ficha (os numeros) aparece logo ABAIXO do desenho e troca junto com a aba,
para que o dono case segmento a segmento sem abrir tres paginas.

As tres camadas, e de onde cada uma vem:

    SA   o recorte do DXF ESTRUTURAL em volta do segmento, que e' o que o
         interpretador leu. E' a unica das tres que nao e' desenho de forma.
    N3   `LV_preview_{viga}_{Para|Passa}_VIEW_{A|B}.dxf`, gerado do N1 pelo
         mesmo caminho do headless (`_generate_lv_n3_nova_previews`).
    N4   `LV_preview_{viga}_VIEW_{A|B}.dxf` da rodada aprovada pelo dono —
         a REFERENCIA.

Uso:
    python scripts/arete/build_lv_debug_viewer.py \
        --n3 <dir com os DXF N3> --n4 <dir com os DXF N4> --out <arquivo.html>
"""
from __future__ import annotations

import argparse
import base64
import html as _html
import io
import json
import re
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt          # noqa: E402
import ezdxf                              # noqa: E402
from ezdxf.addons.drawing import Frontend, RenderContext          # noqa: E402
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend     # noqa: E402

ARETE = Path(__file__).resolve().parent
SCRIPTS = ARETE.parent
REPO = SCRIPTS.parent
for _p in (REPO, SCRIPTS, ARETE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.core.lv_generation_contract import (  # noqa: E402
    build_lv_generation_contracts,
)
from arete.geometry_lv_units import (  # noqa: E402
    split_n4_view, _n4_widths_in_band,
)

DB_PADRAO = 'D:/Agente-cad-PYSIDE/project_data.vision'
PROJETO = 'dd238e47-1dc6-4f63-a760-4e7ce19a7386'
VIGAS = ('V301', 'V302', 'V303', 'V304')
N4_APROVADO = (
    ARETE / 'relatorios' / 'g2v' / 'lv_13pav_rodada_20260911' / 'n4_AQ'
)
DXF_ESTRUTURAL = (
    'D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes/'
    'TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA/torre_1.dxf'
)


# ───────────────────────────── render ─────────────────────────────

_CACHE_DOC: dict = {}


def _doc(caminho: str):
    if caminho not in _CACHE_DOC:
        _CACHE_DOC[caminho] = ezdxf.readfile(caminho)
    return _CACHE_DOC[caminho]


def _svg(caminho: str, janela=None, largura=11.0, altura=4.2,
         tags: list | None = None) -> str:
    """PNG embutido (data URI) do DXF, opcionalmente recortado na janela.

    PNG, nao SVG, de proposito. O recorte do DXF ESTRUTURAL em volta de um
    segmento mostra uma janela pequena, mas o SVG sai com TODAS as entidades da
    prancha — a primeira versao desta pagina deu 211 MB. Em PNG a mesma pagina
    cabe em poucos MB, e para casar segmento com desenho a resolucao basta.
    """
    try:
        doc = _doc(str(caminho))
    except Exception:
        return ''
    fig = plt.figure(figsize=(largura, altura), dpi=104)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor('#0d0d0d')
    try:
        # finalize=True e' o que enquadra o desenho. Com False o eixo fica
        # no default 0..1 e a geometria LV (milhares de cm) cai fora da
        # janela: PNG solido #0d0d0d. O recorte SA passa `janela` e por isso
        # aparecia; N3/N4 nao passam e saiam pretos.
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(
            doc.modelspace(), finalize=True,
        )
        fig.set_size_inches(largura, altura, forward=True)
        ax.set_position([0, 0, 1, 1])
        if janela:
            x0, y0, x1, y1 = janela
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
            ax.set_aspect('auto')
        ax.set_axis_off()
        ax.set_facecolor('#0d0d0d')
        for tag in (tags or []):
            lab, x, y = tag[0], float(tag[1]), float(tag[2])
            hot = bool(tag[3]) if len(tag) > 3 else False
            pts = list(tag[4] or []) if len(tag) > 4 else []
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            if len(xs) >= 2:
                ax.plot(xs, ys, color='#8fe0c4' if hot else '#3d7a6a',
                        lw=1.6 if hot else 0.9, zorder=20, solid_capstyle='round')
            is_v = False
            if len(xs) >= 2:
                is_v = abs(max(ys) - min(ys)) >= abs(max(xs) - min(xs)) * 1.15
            if is_v:
                tx, ty, ha, va = x - 55.0, y, 'right', 'center'
            else:
                tx, ty, ha, va = x, y + 55.0, 'center', 'bottom'
            ax.annotate(
                lab, xy=(x, y), xytext=(tx, ty),
                color='#ffffff', fontsize=8, fontweight='bold',
                ha=ha, va=va, zorder=22,
                bbox=dict(boxstyle='round,pad=0.25',
                          facecolor='#2a6a3a' if hot else '#17392f',
                          edgecolor='#c4e88f' if hot else '#8fe0c4',
                          linewidth=1.1 if hot else 0.8, alpha=0.95),
                arrowprops=dict(arrowstyle='-|>',
                                color='#c4e88f' if hot else '#8fe0c4',
                                lw=0.7, mutation_scale=8),
            )
        buf = io.BytesIO()
        fig.savefig(buf, format='png', facecolor='#0d0d0d')
        return ('data:image/png;base64,'
                + base64.b64encode(buf.getvalue()).decode('ascii'))
    except Exception as exc:
        print('render fail', caminho, type(exc).__name__, exc)
        return ''
    finally:
        plt.close(fig)


def _svg_tag(svg: str) -> str:
    if not svg:
        return ('<div class="vazio">artefato ausente — '
                'nao ha desenho para esta combinacao</div>')
    return f'<img loading="lazy" src="{svg}" alt="">'


# ───────────────────────────── dados ─────────────────────────────

def _coletar(db: str, n3_dir: Path, n4_dir: Path) -> list[dict]:
    conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    bboxes = {}
    for nome, pts in conn.execute(
            'SELECT name, points_json FROM pillars WHERE project_id=?',
            (PROJETO,)):
        try:
            p = json.loads(pts or '[]')
            xs = [float(q[0]) for q in p]
            ys = [float(q[1]) for q in p]
            if xs:
                bboxes[str(nome)] = (min(xs), min(ys), max(xs), max(ys))
        except Exception:
            continue

    from arete.gerar_lv_n4_fichas import _entry_from_live_recorte

    out = []
    for viga in VIGAS:
        row = conn.execute(
            'SELECT data_json FROM beams WHERE project_id=? AND name=?',
            (PROJETO, viga)).fetchone()
        if not row:
            continue
        beam = json.loads(row[0] or '{}')
        contratos = build_lv_generation_contracts(
            beam, beam_name=viga, floor='13_PAV', pillar_bboxes=bboxes)
        try:
            n4 = _entry_from_live_recorte(viga)
        except Exception:
            n4 = {}
        out.append({
            'viga': viga,
            'rotulo_dim': (beam.get('fields') or {}).get('dimensao'),
            'contratos': contratos,
            'n4': n4,
            'n3_dir': n3_dir,
            'n4_dir': n4_dir,
        })
    return out


def _janela_do_segmento(pontos, folga=90.0):
    if not pontos or len(pontos) < 2:
        return None
    xs = [float(p[0]) for p in pontos]
    ys = [float(p[1]) for p in pontos]
    x0, x1 = min(xs) - folga, max(xs) + folga
    y0, y1 = min(ys) - folga, max(ys) + folga + 70.0
    if x1 - x0 < 260:
        m = (x0 + x1) / 2
        x0, x1 = m - 130, m + 130
    if y1 - y0 < 200:
        m = (y0 + y1) / 2
        y0, y1 = m - 100, m + 100
    return (x0, y0, x1, y1)


def _janela_todos(segmentos, folga=120.0):
    pts = []
    for seg in segmentos or []:
        pts.extend(seg.get('points') or [])
    return _janela_do_segmento(pts, folga=folga)


def _tags_sa(segmentos, destaque: int | None = None) -> list:
    tags = []
    for i, seg in enumerate(segmentos or [], 1):
        pts = seg.get('points') or []
        if len(pts) < 2:
            continue
        cx = (float(pts[0][0]) + float(pts[-1][0])) / 2.0
        cy = (float(pts[0][1]) + float(pts[-1][1])) / 2.0
        tags.append(('S%d' % i, cx, cy, destaque in (None, i), pts))
    return tags


def _n4_tag_anchor(unit: dict) -> tuple[float, float, list]:
    ox, yb = unit.get('origin') or (0.0, 0.0)
    end = float(unit.get('body_end_x') or ox)
    h = float(unit.get('h_body') or 100)
    cx = (float(ox) + end) / 2.0
    cy = float(yb) + h / 2.0
    return cx, cy, [(float(ox), float(yb)), (end, float(yb))]


def _n4_height_class(h: float) -> int:
    """Altura medida arredondada — nao 59/124 fixos."""
    return int(round(float(h or 0)))


def _tags_n4(units: list, destaque: int | None = None) -> list:
    tags = []
    for j, unit in enumerate(units or [], 1):
        cx, cy, pts = _n4_tag_anchor(unit)
        hc = unit.get('h_class') or _n4_height_class(unit.get('h_body') or 0)
        lab = '%d·%s' % (j, hc)
        tags.append((lab, cx, cy, destaque in (None, j), pts))
    return tags


def _split_n4_degrau(msp, unit: dict) -> list[dict]:
    """Parte uma ocorrencia N4 se as horizontais de Painéis divergirem em Y."""
    ox, yb = unit.get('origin') or (0.0, 0.0)
    ox, yb = float(ox), float(yb)
    end = float(unit.get('body_end_x') or ox)
    h = float(unit.get('h_body') or 100)
    base = dict(unit)
    base['h_class'] = _n4_height_class(h)
    if h < 80:
        return [base]
    by_y: dict[float, list[tuple[float, float]]] = {}
    for e in msp:
        if e.dxftype() != 'LINE' or e.dxf.layer not in ('Painéis', 'Paineis'):
            continue
        s, e2 = e.dxf.start, e.dxf.end
        if abs(s.y - e2.y) > 0.4:
            continue
        y = round(float(s.y), 1)
        xa, xb = sorted((float(s.x), float(e2.x)))
        w = xb - xa
        if w < 15:
            continue
        mx = 0.5 * (xa + xb)
        if not (ox - 8 <= mx <= end + 8):
            continue
        if y < yb - 3 or y > yb + h + 8:
            continue
        by_y.setdefault(y, []).append((xa, xb))
    ys = sorted(by_y)
    if len(ys) < 3:
        return [base]
    y_bot, y_top = ys[0], ys[-1]
    mids = [y for y in ys[1:-1] if 12.0 <= (y - y_bot) <= h - 12.0]
    if not mids:
        return [base]

    def _span(y: float) -> tuple[float, float]:
        segs = by_y[y]
        return min(a for a, _ in segs), max(b for _, b in segs)

    y_mid = mids[0]
    x_t0, x_t1 = _span(y_bot)
    x_s0, x_s1 = _span(y_mid)
    lab0 = str(unit.get('label') or '').strip()

    def _piece(x0: float, x1: float, y0: float, y1: float, h_class: int) -> dict:
        piece = dict(unit)
        h_body = max(20.0, y1 - y0)
        widths = _n4_widths_in_band(msp, x0, x1 + 2, y0, h_body)
        piece.update({
            'origin': (x0, y0),
            'body_end_x': x1,
            'h_body': h_body,
            'x_band': (x0 - 8.0, x1 + 8.0),
            'widths': widths,
            'h_class': h_class,
            'label': ('%s · %d' % (lab0, h_class)).strip(' ·'),
        })
        return piece

    pieces = [
        _piece(x_t0, x_t1, y_bot, y_top, int(round(y_top - y_bot))),
        _piece(x_s0, x_s1, y_mid, y_top, int(round(y_top - y_mid))),
    ]
    pieces.sort(key=lambda u: float(u['origin'][0]))
    return pieces


def _n2_recorte_path(viga: str) -> Path | None:
    conn = sqlite3.connect(f'file:{DB_PADRAO}?mode=ro', uri=True)
    row = conn.execute(
        """
        SELECT recorte_path FROM reverse_eng_recortes
         WHERE UPPER(elemento_id)=? AND UPPER(classe)='LV'
         ORDER BY id DESC LIMIT 1
        """,
        (str(viga).upper(),),
    ).fetchone()
    if not row or not row[0]:
        return None
    p = Path(str(row[0]))
    return p if p.exists() else None


def _n2_split_unit(fu: dict) -> list[dict]:
    """Parte N2 por divergencia de altura e por abertura de viga."""
    from gerar_lv_dxf_stog import (
        split_face_unit_for_tags, _face_unit_height_class, _panel_w,
    )
    out = []
    for piece in split_face_unit_for_tags(fu):
        bb = piece.get('bbox') or {}
        x0 = float(bb.get('x_left') or 0.0)
        x1 = float(bb.get('x_right') or x0 + 100.0)
        y0 = float(bb.get('y_bot') or 0.0)
        h = float(piece.get('h_body') or 0.0)
        pans = piece.get('panels') or piece.get('segments') or []
        ws = [_panel_w(p) for p in pans if _panel_w(p) > 0]
        hc = _face_unit_height_class(h)
        lab = str(piece.get('label') or '').strip()
        out.append({
            'label': lab, 'side': str(piece.get('side') or '').upper(),
            'h_class': hc,
            'origin': (x0, y0), 'body_end_x': x1,
            'h_body': max(20.0, h) if h else 20.0,
            'x_band': (x0 - 8.0, x1 + 8.0),
            'widths': ws,
        })
    return out


def _n2_units_from_entry(entry: dict | None, side: str) -> list[dict]:
    out: list[dict] = []
    for fu in (entry or {}).get('face_units') or []:
        if str(fu.get('side') or '').upper() != str(side).upper():
            continue
        out.extend(_n2_split_unit(fu))
    return out


def _n4_units(path: Path, side: str) -> list[dict]:
    try:
        raw = list(split_n4_view(path, side))
    except Exception:
        return []
    try:
        msp = _doc(str(path)).modelspace()
    except Exception:
        for u in raw:
            u['h_class'] = _n4_height_class(u.get('h_body') or 0)
        return raw
    out: list[dict] = []
    for unit in raw:
        out.extend(_split_n4_degrau(msp, unit))
    return out


def _n4_clip(unit: dict) -> tuple[float, float, float, float]:
    ox, yb = unit.get('origin') or (0.0, 0.0)
    xband = unit.get('x_band') or (ox, ox + 100)
    end = float(unit.get('body_end_x') or xband[1])
    h = float(unit.get('h_body') or 100)
    pad = 60.0
    x0 = min(float(xband[0]), float(ox)) - pad
    x1 = max(end, float(xband[1])) + pad
    return (x0, float(yb) - pad, x1, float(yb) + h + pad)


def _union_clips(clips: list) -> tuple[float, float, float, float] | None:
    if not clips:
        return None
    return (
        min(c[0] for c in clips), min(c[1] for c in clips),
        max(c[2] for c in clips), max(c[3] for c in clips),
    )


def _bloco(titulo: str, caminho: Path | None, alt: float = 4.2,
           janela=None) -> str:
    svg = _svg(str(caminho), janela=janela, altura=alt) if (
        caminho and caminho.exists()) else ''
    nome = caminho.name if caminho else '(ausente)'
    return (
        '<div class="rot">%s <span class="arq">%s</span></div>'
        '<div class="desenho">%s</div>'
        % (_html.escape(titulo), _html.escape(nome), _svg_tag(svg))
    )


def _n3_face_bbox(caminho: str) -> tuple[float, float, float, float] | None:
    try:
        doc = _doc(str(caminho))
    except Exception:
        return None
    xs, ys = [], []
    for e in doc.modelspace():
        if e.dxftype() != 'LINE':
            continue
        if str(e.dxf.layer) not in ('Painéis', 'Paineis'):
            continue
        xs += [float(e.dxf.start.x), float(e.dxf.end.x)]
        ys += [float(e.dxf.start.y), float(e.dxf.end.y)]
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _n3_clip_seg(caminho: str, panels: list, seg_index: int,
                 pad: float = 30.0) -> tuple[float, float, float, float] | None:
    """Recorte da face N3 no trecho do segmento estrutural.

    O DXF N3 e uma faixa esquerda->direita. Mapeia a soma das larguras dos
    paineis daquele structural_segment_index para X no desenho, com 30 cm
    de folga — senão Todos/S1/S2 saem o mesmo PNG.
    """
    bb = _n3_face_bbox(caminho)
    if not bb:
        return None
    x0, y0, x1, y1 = bb
    total = sum(float(p.get('width') or 0) for p in panels) or 1.0
    acc = 0.0
    start = end = None
    for p in panels:
        w = float(p.get('width') or 0)
        if int(p.get('structural_segment_index') or 0) == int(seg_index):
            if start is None:
                start = acc
            end = acc + w
        acc += w
    if start is None or end is None or end <= start:
        return None
    span = x1 - x0
    xa = x0 + span * (start / total) - pad
    xb = x0 + span * (end / total) + pad
    return (xa, y0 - pad, xb, y1 + pad)


def _achar_dxf(nome: str, *dirs: Path) -> Path | None:
    for d in dirs:
        if not d:
            continue
        p = Path(d) / nome
        if p.exists():
            return p
    return None


def _tab_ficha(pares: list[tuple[str, object]]) -> str:
    linhas = ''.join(
        f'<tr><th>{_html.escape(str(k))}</th>'
        f'<td>{_html.escape(str(v))}</td></tr>' for k, v in pares)
    return f'<table class="ficha">{linhas}</table>'


# ───────────────────────────── html ─────────────────────────────

CSS = """
*{box-sizing:border-box}
/* `display:flex` em `.barra` vence o `display:none` que o atributo `hidden`
   aplica pelo user-agent — sem este `!important` TODAS as barras de nivel 3
   aparecem de uma vez. */
[hidden]{display:none!important}
body{margin:0;background:#0d0d0d;color:#d8d8d8;
     font:13px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace}
h1{font-size:15px;margin:0;padding:12px 16px;border-bottom:1px solid #262626;
   color:#7fd1b9;letter-spacing:.4px}
.aviso{padding:8px 16px;background:#1a1408;border-bottom:1px solid #3a2d10;
       color:#e0b060;font-size:12px}
.barra{display:flex;flex-wrap:wrap;gap:6px;padding:9px 16px;
       border-bottom:1px solid #262626}
.barra.n2{background:#111}
.barra.n3{background:#141414}
.barra.n4{background:#181818}
button.aba{background:#1b1b1b;border:1px solid #303030;color:#bbb;
           padding:5px 11px;border-radius:4px;cursor:pointer;font:inherit}
button.aba:hover{background:#242424;color:#eee}
button.aba.on{background:#17392f;border-color:#2f7a63;color:#8fe0c4}
.painel{padding:14px 16px}
.desenho{position:relative;background:#0d0d0d;border:1px solid #262626;
         border-radius:6px;overflow:hidden;margin-bottom:12px;height:420px;
         cursor:grab;touch-action:none;user-select:none}
.desenho.dragging{cursor:grabbing}
.desenho img,.desenho svg{display:block;width:100%;height:100%;
         background:#0d0d0d}
.desenho .pz-reset{position:absolute;top:8px;right:8px;z-index:2;
         background:#1b1b1b;border:1px solid #303030;color:#bbb;
         padding:3px 8px;border-radius:4px;cursor:pointer;font:inherit;
         font-size:11px}
.desenho .pz-reset:hover{color:#eee;border-color:#2f7a63}
.rot{padding:6px 10px;color:#7fd1b9;font-size:12px}
.arq{color:#5f5f5f;margin-left:8px}
.vazio{padding:38px;text-align:center;color:#8a6b4a}
table.ficha{border-collapse:collapse;width:100%;max-width:760px}
table.ficha th{text-align:left;padding:4px 10px 4px 0;color:#8a8a8a;
               font-weight:400;white-space:nowrap;vertical-align:top;width:220px}
table.ficha td{padding:4px 0;color:#e2e2e2}
table.ficha tr+tr th,table.ficha tr+tr td{border-top:1px solid #1e1e1e}
.legenda{padding:6px 16px 14px;color:#6f6f6f;font-size:11.5px}
"""

JS = """
/* VIGA -> CAMADA -> LADO A|B -> SEGMENTOS daquele lado. */
var estado = {viga: null, lado: null, seg: null, cam: null};

var CAMADAS_OK = {
  'SA-Para':1,'SA-Passa':1,'N2-Segmentos':1,
  'N3-Para':1,'N3-Passa':1,
  'N3-Corte':1,'N4-Corte':1,'N4-Segmentos':1
};
function _kind(s){
  if (CAMADAS_OK[s]) { return 'cam'; }
  if (s === 'A' || s === 'B') { return 'lado'; }
  return 'seg';
}
function _folhas(){
  return document.querySelectorAll('[data-folha]');
}
function _ladosDe(viga, cam){
  var out = [];
  var seen = {};
  _folhas().forEach(function(el){
    var p = (el.getAttribute('data-folha') || '').split('|');
    if (p.length < 4 || p[0] !== viga) { return; }
    if (cam && p[3] !== cam) { return; }
    if (p[1] && !seen[p[1]]) { seen[p[1]] = 1; out.push(p[1]); }
  });
  return out;
}
function _segmentosDe(viga, lado, cam){
  var out = [];
  var seen = {};
  _folhas().forEach(function(el){
    var p = (el.getAttribute('data-folha') || '').split('|');
    if (p.length < 4 || p[0] !== viga) { return; }
    if (lado && p[1] !== lado) { return; }
    if (cam && p[3] !== cam) { return; }
    if (p[2] && !seen[p[2]]) { seen[p[2]] = 1; out.push(p[2]); }
  });
  return out;
}
function _folha(viga, lado, seg, cam){
  return document.querySelector(
    '[data-folha="' + viga + '|' + lado + '|' + seg + '|' + cam + '"]');
}
function _primeiraCamada(viga){
  var g = document.querySelector('[data-folha^="' + viga + '|"]');
  return g ? g.getAttribute('data-folha').split('|')[3] : null;
}
function _pick(lista, atual, prefer){
  if (atual && lista.indexOf(atual) >= 0) { return atual; }
  if (prefer && lista.indexOf(prefer) >= 0) { return prefer; }
  return lista[0] || null;
}

function mostrar(parte){
  var p = String(parte || '').split('|');
  if (p[0]) { estado.viga = p[0]; }
  if (p.length === 2) {
    var k = _kind(p[1]);
    if (k === 'cam') { estado.cam = p[1]; }
    else if (k === 'lado') { estado.lado = p[1]; }
    else { estado.seg = p[1]; }
  } else if (p.length === 3) {
    if (_kind(p[2]) === 'cam') { estado.lado = p[1]; estado.cam = p[2]; }
    else { estado.lado = p[1]; estado.seg = p[2]; }
  } else if (p.length >= 4) {
    estado.viga = p[0]; estado.lado = p[1]; estado.seg = p[2]; estado.cam = p[3];
  }

  if (!estado.cam || !document.querySelector(
      '[data-folha^="' + estado.viga + '|"][data-folha$="|' + estado.cam + '"]')) {
    estado.cam = _primeiraCamada(estado.viga);
  }
  var lados = _ladosDe(estado.viga, estado.cam);
  estado.lado = _pick(lados, estado.lado, 'A');
  var segs = _segmentosDe(estado.viga, estado.lado, estado.cam);
  estado.seg = _pick(segs, estado.seg, 'Todos');
  if (!estado.cam || !estado.lado || !estado.seg) { return; }
  if (!_folha(estado.viga, estado.lado, estado.seg, estado.cam)) {
    estado.seg = _pick(segs, 'Todos', segs[0]);
  }

  var chaveFolha = estado.viga + '|' + estado.lado + '|' + estado.seg + '|' + estado.cam;
  var chaveCam = estado.viga + '|' + estado.cam;
  var chaveLado = estado.viga + '|' + estado.lado;
  var chaveSeg = estado.viga + '|' + estado.seg;

  document.querySelectorAll('button[data-nivel]').forEach(function(b){
    var k = b.getAttribute('data-chave');
    var nivel = b.getAttribute('data-nivel');
    if (nivel === '3') {
      var sp = (k || '').split('|');
      b.hidden = sp[0] !== estado.viga || lados.indexOf(sp[1]) < 0;
    }
    if (nivel === '4') {
      var sp = (k || '').split('|');
      b.hidden = sp[0] !== estado.viga || segs.indexOf(sp[1]) < 0;
    }
    b.classList.toggle(
      'on', k === estado.viga || k === chaveCam || k === chaveLado
        || k === chaveSeg || k === chaveFolha);
  });
  document.querySelectorAll('[data-grupo]').forEach(function(el){
    el.hidden = el.getAttribute('data-grupo') !== estado.viga;
  });
  var barraLado = document.querySelector(
    '[data-grupo="' + estado.viga + '"].barra.n3');
  if (barraLado) {
    barraLado.hidden = lados.length < 2;
  }
  document.querySelectorAll('[data-folha]').forEach(function(el){
    el.hidden = el.getAttribute('data-folha') !== chaveFolha;
  });
  var vis = document.querySelector('[data-folha="' + chaveFolha + '"]');
  if (vis) {
    vis.querySelectorAll('.desenho').forEach(_prepDesenho);
  }
  try { localStorage.setItem('lv_debug_aba', chaveFolha); } catch(e){}
}

function _prepDesenho(box){
  if (!box || box.dataset.pzInit === '1') { return; }
  var img = box.querySelector('img');
  if (!img) {
    var svg0 = box.querySelector('svg');
    if (svg0) { _initPz(box, svg0); }
    return;
  }
  function wrap(){
    if (box.dataset.pzInit === '1') { return; }
    var w = img.naturalWidth || 1144;
    var h = img.naturalHeight || 436;
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    var image = document.createElementNS('http://www.w3.org/2000/svg', 'image');
    image.setAttribute('href', img.getAttribute('src'));
    image.setAttribute('width', String(w));
    image.setAttribute('height', String(h));
    svg.appendChild(image);
    img.replaceWith(svg);
    _initPz(box, svg);
  }
  if (img.complete && img.naturalWidth) { wrap(); }
  else {
    img.loading = 'eager';
    img.addEventListener('load', wrap, {once: true});
  }
}

function _initPz(box, svg){
  if (!svg || !svg.viewBox || !svg.viewBox.baseVal || !svg.viewBox.baseVal.width) {
    return;
  }
  box.dataset.pzInit = '1';
  var base = svg.viewBox.baseVal;
  var home = {x: base.x, y: base.y, w: base.width, h: base.height};
  var view = {x: home.x, y: home.y, w: home.w, h: home.h};
  var dragging = false, last = null;
  function apply(){
    svg.setAttribute('viewBox', [view.x, view.y, view.w, view.h].join(' '));
  }
  function reset(){
    view = {x: home.x, y: home.y, w: home.w, h: home.h};
    apply();
  }
  function point(event){
    var rect = svg.getBoundingClientRect();
    if (!rect.width || !rect.height) {
      return {x: view.x + view.w / 2, y: view.y + view.h / 2};
    }
    return {
      x: view.x + (event.clientX - rect.left) / rect.width * view.w,
      y: view.y + (event.clientY - rect.top) / rect.height * view.h
    };
  }
  if (!box.querySelector('.pz-reset')) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pz-reset';
    btn.textContent = 'reset zoom';
    btn.addEventListener('click', function(e){ e.stopPropagation(); reset(); });
    box.appendChild(btn);
  }
  box.addEventListener('wheel', function(event){
    event.preventDefault();
    var anchor = point(event);
    var factor = event.deltaY < 0 ? 0.88 : 1.14;
    var width = Math.max(home.w * 0.03, Math.min(home.w * 4.5, view.w * factor));
    var height = width * home.h / home.w;
    var rx = (anchor.x - view.x) / view.w;
    var ry = (anchor.y - view.y) / view.h;
    view.x = anchor.x - rx * width;
    view.y = anchor.y - ry * height;
    view.w = width;
    view.h = height;
    apply();
  }, {passive: false});
  box.addEventListener('mousedown', function(event){
    if (event.button !== 0 && event.button !== 1) { return; }
    if (event.target && event.target.closest && event.target.closest('button')) {
      return;
    }
    event.preventDefault();
    dragging = true;
    last = {x: event.clientX, y: event.clientY};
    box.classList.add('dragging');
  });
  window.addEventListener('mousemove', function(event){
    if (!dragging || !last) { return; }
    var rect = svg.getBoundingClientRect();
    if (!rect.width) { return; }
    view.x -= (event.clientX - last.x) / rect.width * view.w;
    view.y -= (event.clientY - last.y) / rect.height * view.h;
    last = {x: event.clientX, y: event.clientY};
    apply();
  });
  window.addEventListener('mouseup', function(){
    dragging = false;
    last = null;
    box.classList.remove('dragging');
  });
  box.addEventListener('dblclick', function(event){
    if (event.target && event.target.closest && event.target.closest('button')) {
      return;
    }
    reset();
  });
}

window.addEventListener('DOMContentLoaded', function(){
  var inicial = null;
  try { inicial = localStorage.getItem('lv_debug_aba'); } catch(e){}
  var primeira = document.querySelector('[data-folha]');
  if (!inicial || !document.querySelector('[data-folha="' + inicial + '"]')) {
    inicial = primeira ? primeira.getAttribute('data-folha') : '';
  }
  if (inicial) { mostrar(inicial); }
});
"""


def montar(dados: list[dict], destino: Path) -> Path:
    partes = [
        '<!doctype html><meta charset="utf-8">',
        '<title>LV — depuracao SA x N3 x N4</title>',
        f'<style>{CSS}</style>',
        '<h1>Laterais de viga — depuracao por segmento</h1>',
        '<div class="aviso">O <b>N4</b> e a referencia (aprovado pelo dono). '
        'O <b>N3</b> sai do N1/SA pelo mesmo caminho do headless, nos dois '
        'comportamentos. O quadro <b>SA</b> mostra o recorte do DXF '
        '<b>estrutural</b> que o interpretador leu — nao e desenho de '
        'forma. N4 · Segmentos usa o DXF <b>validado</b> '
        '(<code>LV_preview_*_A.dxf</code>), recortado por unidade — '
        'nao a faixa VIEW. Viewer: <b>roda</b> zoom, <b>arrastar</b> pan, '
        '<b>duplo clique</b> reset. Sub-aba <b>Todos</b> mostra a viga '
        'inteira.</div>',
    ]

    partes.append('<div class="barra">')
    for d in dados:
        v = d["viga"]
        partes.append(
            '<button class="aba" data-nivel="1" data-chave="%s" '
            'onclick="mostrar(\'%s\')">%s</button>' % (v, v, v))
    partes.append('</div>')

    CAMADAS = ('SA-Para', 'SA-Passa', 'N2-Segmentos',
               'N3-Para', 'N3-Passa',
               'N3-Corte', 'N4-Corte', 'N4-Segmentos')

    folhas = []
    for d in dados:
        viga, ct = d['viga'], d['contratos']
        n3, n4d = Path(d['n3_dir']), Path(d['n4_dir'])

        n3_dirs = (n3, ARETE / 'tmp' / 'sa_n3_nova_3h9qktrx' / 'dxf',
                   ARETE / 'tmp' / 'lv_debug_n3_v302' / 'dxf')

        def _dxf(nome: str, *mais: Path) -> Path | None:
            return _achar_dxf(nome, *mais, *n3_dirs, n4d)

        n4_a = _dxf('LV_preview_%s_A.dxf' % viga, n4d)
        n4_por_lado: dict[str, list] = {'A': [], 'B': []}
        if n4_a and n4_a.exists():
            for side in ('A', 'B'):
                n4_por_lado[side] = _n4_units(n4_a, side)

        from arete.gerar_lv_n4_fichas import _entry_from_live_recorte
        n2_path = _n2_recorte_path(viga)
        try:
            n2_entry = _entry_from_live_recorte(viga)
        except Exception:
            n2_entry = {}
        n2_por_lado = {
            s: _n2_units_from_entry(n2_entry, s) for s in ('A', 'B')
        }

        segs_por = {
            c: {s: (ct.get(c) or {}).get(s, {}).get('structural_segments') or []
                for s in ('A', 'B')}
            for c in ('Para', 'Passa')
        }
        n_seg_max = max(
            (len(segs_por[c][s]) for c in segs_por for s in ('A', 'B')),
            default=0)
        n4_max = max((len(n4_por_lado[s]) for s in ('A', 'B')), default=0)
        n2_max = max((len(n2_por_lado[s]) for s in ('A', 'B')), default=0)
        n4_max = max(n4_max, n2_max)

        partes.append('<div class="barra n2" data-grupo="%s" hidden>' % viga)
        for cam in CAMADAS:
            ch = '%s|%s' % (viga, cam)
            partes.append(
                '<button class="aba" data-nivel="2" data-chave="%s" '
                'onclick="mostrar(\'%s\')">%s</button>'
                % (ch, ch, cam.replace('-', ' · ')))
        partes.append('</div>')

        partes.append('<div class="barra n3" data-grupo="%s" hidden>' % viga)
        for lado in ('A', 'B'):
            ch = '%s|%s' % (viga, lado)
            partes.append(
                '<button class="aba" data-nivel="3" data-chave="%s" '
                'onclick="mostrar(\'%s\')">%s</button>' % (ch, ch, lado))
        partes.append('</div>')

        partes.append('<div class="barra n4" data-grupo="%s" hidden>' % viga)
        partes.append(
            '<button class="aba" data-nivel="4" data-chave="%s|Todos" '
            'onclick="mostrar(\'%s|Todos\')">Todos</button>' % (viga, viga))
        for i in range(1, n_seg_max + 1):
            ch = '%s|S%d' % (viga, i)
            partes.append(
                '<button class="aba" data-nivel="4" data-chave="%s" '
                'onclick="mostrar(\'%s\')">S%d</button>' % (ch, ch, i))
        for j in range(1, n4_max + 1):
            ch = '%s|%d' % (viga, j)
            partes.append(
                '<button class="aba" data-nivel="4" data-chave="%s" '
                'onclick="mostrar(\'%s\')">%d</button>' % (ch, ch, j))
        partes.append('</div>')

        def _folha_html(chave_folha: str, corpo: str) -> None:
            folhas.append(
                '<div class="painel" data-folha="%s" hidden>%s</div>'
                % (chave_folha, corpo))

        def _contrato(comp: str, lado: str) -> dict:
            return (ct.get(comp) or {}).get(lado) or {}

        def _n3_extra(comp: str, lado: str, i: int | None) -> str:
            c = _contrato(comp, lado)
            segs = segs_por[comp][lado]
            if i is None:
                return _tab_ficha([
                    ('lado', lado),
                    ('comportamento', comp),
                    ('segmentos deste lado', len(segs)),
                    ('paineis na face', len(c.get('panels') or [])),
                    ('total da face', '%.1f cm' % float(c.get('total_length') or 0)),
                    ('altura da face', '%.1f cm' % float(c.get('total_height') or 0)),
                ])
            idx = int(segs[i - 1].get('segment_index') or i)
            meus = [p for p in (c.get('panels') or [])
                    if int(p.get('structural_segment_index') or 0) == idx]
            return _tab_ficha([
                ('lado', lado),
                ('comportamento', comp),
                ('paineis DESTE segmento (S%d)' % i,
                 ', '.join('%.1f' % float(p['width']) for p in meus)
                 or '(nenhum)'),
                ('altura da face', '%.1f cm' % float(c.get('total_height') or 0)),
            ])

        for lado in ('A', 'B'):
            for comp in ('Para', 'Passa'):
                segs = segs_por[comp][lado]
                c = _contrato(comp, lado)
                tags_all = _tags_sa(segs)
                svg_todos = _svg(
                    DXF_ESTRUTURAL, _janela_todos(segs),
                    tags=tags_all, altura=5.0)
                _folha_html(
                    '%s|%s|Todos|SA-%s' % (viga, lado, comp),
                    '<div class="desenho">%s</div>%s'
                    '<div class="legenda">SA lado %s · Todos — tags S1..S%d '
                    'como na interpretacao VPS.</div>'
                    % (_svg_tag(svg_todos), _tab_ficha([
                        ('lado', lado), ('comportamento', comp),
                        ('segmentos', len(segs)),
                        ('secao (rotulo da viga)', d['rotulo_dim']),
                    ]), lado, len(segs)))
                for i, seg in enumerate(segs, 1):
                    pts = seg.get('points') or []
                    svg = _svg(
                        DXF_ESTRUTURAL, _janela_do_segmento(pts),
                        tags=_tags_sa(segs, destaque=i))
                    idx = int(seg.get('segment_index') or i)
                    meus = [p for p in (c.get('panels') or [])
                            if int(p.get('structural_segment_index') or 0) == idx]
                    _folha_html(
                        '%s|%s|S%d|SA-%s' % (viga, lado, i, comp),
                        '<div class="desenho">%s</div>%s'
                        '<div class="legenda">SA lado %s · S%d de %d com tag.'
                        '</div>' % (_svg_tag(svg), _tab_ficha([
                            ('lado', lado),
                            ('viga · segmento',
                             '%s.%s · S%d de %d' % (viga, lado, i, len(segs))),
                            ('comportamento', comp),
                            ('comprimento estrutural (N1)',
                             '%.1f cm' % float(seg.get('width') or 0)),
                            ('paineis que o N3 poe aqui',
                             ', '.join('%.1f' % float(p['width']) for p in meus)
                             or '(nenhum)'),
                            ('secao (rotulo da viga)', d['rotulo_dim']),
                        ]), lado, i, len(segs)))

            for comp in ('Para', 'Passa'):
                cam = 'N3-%s' % comp
                path = _dxf('LV_preview_%s_%s_VIEW_%s.dxf' % (viga, comp, lado))
                vista = _bloco('N3 %s · lado %s' % (comp, lado), path)
                _folha_html(
                    '%s|%s|Todos|%s' % (viga, lado, cam),
                    '%s%s<div class="legenda">N3 %s lado %s — face inteira.'
                    '</div>' % (vista, _n3_extra(comp, lado, None), comp, lado))
                segs = segs_por[comp][lado]
                c = _contrato(comp, lado)
                pans = c.get('panels') or []
                for i, seg in enumerate(segs, 1):
                    idx = int(seg.get('segment_index') or i)
                    clip = _n3_clip_seg(str(path), pans, idx) if path else None
                    cx = ((clip[0] + clip[2]) / 2) if clip else 0
                    cy = ((clip[1] + clip[3]) / 2) if clip else 0
                    png = _svg(
                        str(path), janela=clip, altura=4.2,
                        tags=[('S%d' % i, cx, cy, True)]) if path else ''
                    titulo = 'N3 %s · lado %s · S%d' % (comp, lado, i)
                    _folha_html(
                        '%s|%s|S%d|%s' % (viga, lado, i, cam),
                        '<div class="rot">%s <span class="arq">%s</span></div>'
                        '<div class="desenho">%s</div>%s'
                        '<div class="legenda">N3 %s lado %s · S%d recortado '
                        'no trecho dos paineis deste segmento (+30 cm).'
                        '</div>' % (
                            _html.escape(titulo),
                            path.name if path else '(ausente)',
                            _svg_tag(png), _n3_extra(comp, lado, i),
                            comp, lado, i))

            units = n4_por_lado[lado]
            n4_nome = n4_a.name if n4_a else 'LV_preview_%s_A.dxf' % viga
            clip_todos = _union_clips([_n4_clip(u) for u in units])
            png_todos = (
                _svg(str(n4_a), janela=clip_todos, altura=5.2,
                     tags=_tags_n4(units))
                if n4_a and clip_todos else '')
            _folha_html(
                '%s|%s|Todos|N4-Segmentos' % (viga, lado),
                '<div class="rot">N4 validado · lado %s · Todos '
                '<span class="arq">%s</span></div>'
                '<div class="desenho">%s</div>%s'
                '<div class="legenda">N4 que voce validou, lado %s '
                '(%d segmentos). Escolha 1, 2… para ver um de cada vez.'
                '</div>' % (
                    lado, _html.escape(n4_nome), _svg_tag(png_todos),
                    _tab_ficha([
                        ('lado', lado),
                        ('segmentos N4 deste lado', len(units)),
                        ('alturas (cm)', ', '.join(
                            str(u.get('h_class')
                                or _n4_height_class(u.get('h_body') or 0))
                            for u in units)),
                        ('rotulos', ', '.join(
                            str(u.get('label') or '') for u in units)),
                        ('arquivo', n4_nome),
                    ]), lado, len(units)))
            for j, unit in enumerate(units, 1):
                clip = _n4_clip(unit)
                png = _svg(
                    str(n4_a), janela=clip, altura=4.2,
                    tags=_tags_n4(units, destaque=j)) if n4_a else ''
                lab = str(unit.get('label') or ('%s%d' % (lado, j)))
                _folha_html(
                    '%s|%s|%d|N4-Segmentos' % (viga, lado, j),
                    '<div class="rot">N4 validado · %s · %s '
                    '<span class="arq">%s</span></div>'
                    '<div class="desenho">%s</div>%s'
                    '<div class="legenda">Segmento %d de %d do lado %s '
                    'no DXF N4 aprovado (revisao granular).'
                    '</div>' % (
                        lado, _html.escape(lab), _html.escape(n4_nome),
                        _svg_tag(png),
                        _tab_ficha([
                            ('unidade N4', '%s · %d/%d · %s'
                             % (lado, j, len(units), lab)),
                            ('altura (cm)', unit.get('h_class')
                             or _n4_height_class(unit.get('h_body') or 0)),
                            ('h_body', '%.1f cm' % float(
                                unit.get('h_body') or 0)),
                            ('larguras', ', '.join(
                                '%.1f' % w for w in (unit.get('widths') or []))),
                        ]), j, len(units), lado))

            folhas.extend(_n2_lado_painels(
                viga, lado, n2_path, n2_por_lado[lado],
                n4_count=len(n4_por_lado[lado])))

        extra_corte = _tab_ficha([
            ('secao medida no N2', d['n4'].get('h_section_all')),
            ('arquivo N4', 'LV_preview_%s_CORTE.dxf' % viga),
        ])
        _folha_html(
            '%s|A|Todos|N3-Corte' % viga,
            '%s%s<div class="legenda">Corte N3 (Para e Passa).'
            '</div>' % (
                _bloco('N3 Para · corte',
                       _dxf('LV_preview_%s_Para_CORTE.dxf' % viga), 3.0)
                + _bloco('N3 Passa · corte',
                         _dxf('LV_preview_%s_Passa_CORTE.dxf' % viga), 3.0),
                extra_corte))
        _folha_html(
            '%s|A|Todos|N4-Corte' % viga,
            '%s%s<div class="legenda">Corte N4 validado.</div>' % (
                _bloco('N4 · corte',
                       _dxf('LV_preview_%s_CORTE.dxf' % viga, n4d), 3.0),
                extra_corte))

    partes.extend(folhas)
    partes.append('<script>%s</script>' % JS)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text('\n'.join(partes), encoding='utf-8')
    return destino


def _painel(chave: str, corpo: str) -> str:
    return '<div class="painel" data-folha="%s" hidden>%s</div>' % (
        chave, corpo)


def _n4_lado_painels(viga: str, lado: str, n4_a: Path,
                     units: list) -> list[str]:
    n4_nome = n4_a.name if n4_a else 'LV_preview_%s_A.dxf' % viga
    out = []
    clip_todos = _union_clips([_n4_clip(u) for u in units])
    png_todos = (
        _svg(str(n4_a), janela=clip_todos, altura=5.2, tags=_tags_n4(units))
        if n4_a and n4_a.exists() and clip_todos else '')
    out.append(_painel(
        '%s|%s|Todos|N4-Segmentos' % (viga, lado),
        '<div class="rot">N4 validado · lado %s · Todos '
        '<span class="arq">%s</span></div>'
        '<div class="desenho">%s</div>%s'
        '<div class="legenda">N4 fechado (n4_AQ), lado %s '
        '(%d segmentos). Altura que diverge e abertura de viga '
        'viram dois segmentos.</div>' % (
            lado, _html.escape(n4_nome), _svg_tag(png_todos),
            _tab_ficha([
                ('lado', lado),
                ('segmentos N4 deste lado', len(units)),
                ('alturas (cm)', ', '.join(
                    str(u.get('h_class')
                        or _n4_height_class(u.get('h_body') or 0))
                    for u in units)),
                ('rotulos', ', '.join(
                    str(u.get('label') or '') for u in units)),
                ('arquivo', n4_nome),
            ]), lado, len(units))))
    for j, unit in enumerate(units, 1):
        clip = _n4_clip(unit)
        png = _svg(
            str(n4_a), janela=clip, altura=4.2,
            tags=_tags_n4(units, destaque=j)) if n4_a and n4_a.exists() else ''
        lab = str(unit.get('label') or ('%s%d' % (lado, j)))
        out.append(_painel(
            '%s|%s|%d|N4-Segmentos' % (viga, lado, j),
            '<div class="rot">N4 validado · %s · %s '
            '<span class="arq">%s</span></div>'
            '<div class="desenho">%s</div>%s'
            '<div class="legenda">Segmento %d de %d do lado %s '
            'no DXF N4 fechado (n4_AQ).'
            '</div>' % (
                lado, _html.escape(lab), _html.escape(n4_nome),
                _svg_tag(png),
                _tab_ficha([
                    ('unidade N4', '%s · %d/%d · %s'
                     % (lado, j, len(units), lab)),
                    ('altura (cm)', unit.get('h_class')
                     or _n4_height_class(unit.get('h_body') or 0)),
                    ('h_body', '%.1f cm' % float(unit.get('h_body') or 0)),
                    ('larguras', ', '.join(
                        '%.1f' % w for w in (unit.get('widths') or []))),
                ]), j, len(units), lado)))
    return out


def _n2_lado_painels(viga: str, lado: str, recorte: Path | None,
                     units: list, n4_count: int = 0) -> list[str]:
    nome = recorte.name if recorte else '(recorte N2 ausente)'
    n2n, n4n = len(units), int(n4_count or 0)
    faltam = max(0, n2n - n4n)
    extra = max(0, n4n - n2n)
    if faltam:
        veredito = 'N4 tem %d segmento(s) a menos que o N2 humano' % faltam
    elif extra:
        veredito = 'N4 tem %d segmento(s) a mais que o N2 humano' % extra
    else:
        veredito = 'N2 e N4 tem a mesma quantidade neste lado'
    out = []
    clip_todos = _union_clips([_n4_clip(u) for u in units])
    png_todos = (
        _svg(str(recorte), janela=clip_todos, altura=5.2, tags=_tags_n4(units))
        if recorte and recorte.exists() and clip_todos else '')
    out.append(_painel(
        '%s|%s|Todos|N2-Segmentos' % (viga, lado),
        '<div class="rot">N2 humano · lado %s · Todos '
        '<span class="arq">%s</span></div>'
        '<div class="desenho">%s</div>%s'
        '<div class="legenda">Recorte STOG que voce desenhou. '
        'Painel 59 e 124 no mesmo rotulo viram dois segmentos, '
        'igual no N4. %s.</div>' % (
            lado, _html.escape(nome), _svg_tag(png_todos),
            _tab_ficha([
                ('lado', lado),
                ('segmentos N2 (humano)', n2n),
                ('segmentos N4', n4n),
                ('veredito', veredito),
                ('alturas (cm)', ', '.join(
                    str(u.get('h_class')
                        or _n4_height_class(u.get('h_body') or 0))
                    for u in units)),
                ('rotulos', ', '.join(
                    str(u.get('label') or '') for u in units)),
                ('arquivo', nome),
            ]), veredito)))
    for j, unit in enumerate(units, 1):
        clip = _n4_clip(unit)
        png = _svg(
            str(recorte), janela=clip, altura=4.2,
            tags=_tags_n4(units, destaque=j)
        ) if recorte and recorte.exists() else ''
        lab = str(unit.get('label') or ('%s%d' % (lado, j)))
        out.append(_painel(
            '%s|%s|%d|N2-Segmentos' % (viga, lado, j),
            '<div class="rot">N2 humano · %s · %s '
            '<span class="arq">%s</span></div>'
            '<div class="desenho">%s</div>%s'
            '<div class="legenda">Segmento %d de %d do lado %s '
            'no recorte N2 humano.'
            '</div>' % (
                lado, _html.escape(lab), _html.escape(nome),
                _svg_tag(png),
                _tab_ficha([
                    ('unidade N2', '%s · %d/%d · %s'
                     % (lado, j, n2n, lab)),
                    ('altura (cm)', unit.get('h_class')
                     or _n4_height_class(unit.get('h_body') or 0)),
                    ('h_body', '%.1f cm' % float(unit.get('h_body') or 0)),
                    ('larguras', ', '.join(
                        '%.1f' % w for w in (unit.get('widths') or []))),
                    ('N4 neste lado', n4n),
                ]), j, n2n, lado)))
    return out


def patch_n2(html_path: Path) -> Path:
    """Injeta folhas N2 no HTML existente — sem rerender de SA/N3/N4."""
    from arete.gerar_lv_n4_fichas import _entry_from_live_recorte

    html = html_path.read_text(encoding='utf-8')
    if "'N2-Segmentos':1" not in html and '"N2-Segmentos":1' not in html:
        html = html.replace(
            "'SA-Passa':1,'N3-Para':1",
            "'SA-Passa':1,'N2-Segmentos':1,'N3-Para':1",
        )
        html = html.replace(
            '"SA-Passa":1,"N3-Para":1',
            '"SA-Passa":1,"N2-Segmentos":1,"N3-Para":1',
        )
    if 'N2 · Segmentos' not in html:
        html = re.sub(
            r'(<button class="aba" data-nivel="2" '
            r'data-chave="(V30[1-4])\|SA-Passa"[^>]*>SA · Passa</button>\n)',
            lambda m: m.group(1) + (
                '<button class="aba" data-nivel="2" '
                'data-chave="%s|N2-Segmentos" '
                'onclick="mostrar(\'%s|N2-Segmentos\')">'
                'N2 · Segmentos</button>\n' % (m.group(2), m.group(2))),
            html)

    kept = []
    dropped = 0
    n2_folha_re = re.compile(
        r'data-folha="V30[1-4]\|[AB]\|[^"]+\|N2-Segmentos"')
    for line in html.split('\n'):
        if n2_folha_re.search(line):
            dropped += 1
            continue
        kept.append(line)
    html = '\n'.join(kept)
    print('drop N2 folhas', dropped)

    new_folhas: list[str] = []
    n2_max: dict[str, int] = {}
    for viga in VIGAS:
        recorte = _n2_recorte_path(viga)
        try:
            entry = _entry_from_live_recorte(viga)
        except Exception:
            entry = {}
        n4_a = N4_APROVADO / ('LV_preview_%s_A.dxf' % viga)
        print('N2', viga, recorte.name if recorte else 'AUSENTE')
        por = {}
        for lado in ('A', 'B'):
            units = _n2_units_from_entry(entry, lado)
            n4n = len(_n4_units(n4_a, lado)) if n4_a.exists() else 0
            por[lado] = units
            print(' ', lado, 'N2=', len(units), 'N4=', n4n,
                  'h=', [u.get('h_class') for u in units])
            new_folhas.extend(
                _n2_lado_painels(viga, lado, recorte, units, n4_count=n4n))
        n2_max[viga] = max((len(por[s]) for s in ('A', 'B')), default=0)

    if '<script>' not in html:
        raise RuntimeError('HTML sem <script> — nao sei onde inserir N2')
    html = html.replace('<script>', '\n'.join(new_folhas) + '\n<script>', 1)

    def _botoes_num(viga: str, nmax: int) -> str:
        return ''.join(
            '<button class="aba" data-nivel="4" data-chave="%s|%d" '
            'onclick="mostrar(\'%s|%d\')">%d</button>\n'
            % (viga, j, viga, j, j)
            for j in range(1, nmax + 1))

    for viga, nmax in n2_max.items():
        existentes = [
            int(m) for m in re.findall(
                r'data-chave="%s\|(\d+)"' % viga, html)
        ]
        nmax = max([nmax] + existentes)
        html = re.sub(
            r'<button class="aba" data-nivel="4" data-chave="%s\|\d+"'
            r'[^>]*>\d+</button>\n?' % viga,
            '', html)
        html = re.sub(
            r'(<button class="aba" data-nivel="4" data-chave="%s\|Todos"'
            r'[^>]*>Todos</button>\n)' % viga,
            lambda m, v=viga, n=nmax: m.group(1) + _botoes_num(v, n),
            html, count=1)

    html_path.write_text(html, encoding='utf-8')
    print('HTML', html_path, 'n2_max', n2_max)
    return html_path


def patch_n4(html_path: Path, n4_dir: Path) -> Path:
    """Troca so as folhas N4 no HTML ja gerado — sem rerender de SA/N3."""
    html = html_path.read_text(encoding='utf-8')
    kept = []
    dropped = 0
    n4_folha_re = re.compile(
        r'data-folha="V30[1-4]\|[AB]\|[^"]+\|N4-(?:Segmentos|Corte)"')
    for line in html.split('\n'):
        if n4_folha_re.search(line):
            dropped += 1
            continue
        kept.append(line)
    html = '\n'.join(kept)
    print('drop N4 folhas', dropped)

    new_folhas: list[str] = []
    n4_max: dict[str, int] = {}
    for viga in VIGAS:
        n4_a = n4_dir / ('LV_preview_%s_A.dxf' % viga)
        n4_corte = n4_dir / ('LV_preview_%s_CORTE.dxf' % viga)
        print('N4', viga, 'dxf', n4_a.name if n4_a.exists() else 'AUSENTE')
        por_lado = {}
        for lado in ('A', 'B'):
            units = _n4_units(n4_a, lado) if n4_a.exists() else []
            por_lado[lado] = units
            print(' ', lado, 'n=', len(units),
                  'h=', [u.get('h_class') for u in units])
            new_folhas.extend(_n4_lado_painels(viga, lado, n4_a, units))
        n4_max[viga] = max((len(por_lado[s]) for s in ('A', 'B')), default=0)
        new_folhas.append(_painel(
            '%s|A|Todos|N4-Corte' % viga,
            '%s%s<div class="legenda">Corte N4 recem revisado (n4_AN).'
            '</div>' % (
                _bloco('N4 · corte', n4_corte if n4_corte.exists() else None,
                       3.0),
                _tab_ficha([
                    ('arquivo N4', n4_corte.name if n4_corte.exists()
                     else 'ausente'),
                    ('pasta', str(n4_dir)),
                ]))))

    if '<script>' not in html:
        raise RuntimeError('HTML sem <script> — nao sei onde inserir N4')
    html = html.replace('<script>', '\n'.join(new_folhas) + '\n<script>', 1)

    def _botoes_num(viga: str, nmax: int) -> str:
        return ''.join(
            '<button class="aba" data-nivel="4" data-chave="%s|%d" '
            'onclick="mostrar(\'%s|%d\')">%d</button>\n'
            % (viga, j, viga, j, j)
            for j in range(1, nmax + 1))

    for viga, nmax in n4_max.items():
        html = re.sub(
            r'<button class="aba" data-nivel="4" data-chave="%s\|\d+"'
            r'[^>]*>\d+</button>\n?' % viga,
            '', html)
        html = re.sub(
            r'(<button class="aba" data-nivel="4" data-chave="%s\|Todos"'
            r'[^>]*>Todos</button>\n)' % viga,
            lambda m, v=viga, n=nmax: m.group(1) + _botoes_num(v, n),
            html, count=1)

    html_path.write_text(html, encoding='utf-8')
    print('HTML', html_path, 'n4_max', n4_max)
    return html_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=DB_PADRAO)
    ap.add_argument('--n3')
    ap.add_argument('--n4', default=str(N4_APROVADO))
    ap.add_argument('--out', required=True)
    ap.add_argument('--patch-n4', action='store_true',
                    help='so re-renderiza folhas N4 no HTML existente')
    ap.add_argument('--patch-n2', action='store_true',
                    help='injeta folhas N2 (recorte humano) no HTML existente')
    a = ap.parse_args()
    n4 = Path(a.n4)
    if a.patch_n2:
        patch_n2(Path(a.out))
        return 0
    if a.patch_n4:
        patch_n4(Path(a.out), n4)
        return 0
    if not a.n3:
        ap.error('--n3 e obrigatorio sem --patch-n4')
    dados = _coletar(a.db, Path(a.n3), n4)
    destino = montar(dados, Path(a.out))
    print('HTML', destino)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
