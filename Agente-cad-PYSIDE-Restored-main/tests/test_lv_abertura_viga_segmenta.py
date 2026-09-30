# -*- coding: utf-8 -*-
"""Abertura de VIGA recorta o painel e separa segmentos (LV).

Regra do dono (contrato §5.2.3): abertura de VIGA recorta o PAINEL — a de
PILAR so' recorta o sarrafo. Uma abertura de viga parte o painel em DOIS
segmentos, mesmo encostados; a fronteira fica na borda DIREITA da abertura, e
a abertura e a sobra pertencem ao segmento que vem ANTES.

Evidencia medida no N2 da V302.A (unidade 0..470, fundo em y=0.3):

    vertical   x=178.5  y 5.3 -> 43.3      borda esquerda da abertura
    horizontal y=5.3    x 178.5 -> 200.5   PISO da abertura = topo da sobra
    vertical   x=200.5  y 0.3 ->  5.3      borda direita da sobra

Corte em 200.5 -> segmentos de 200.5 e 269.5.
"""
from __future__ import annotations

import pathlib
import sys

import ezdxf

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import gerar_lv_dxf_stog as lv  # noqa: E402
import motor_reverso_lv as mrl  # noqa: E402


# ── extracao ─────────────────────────────────────────────────────────────
PAIR = {"x_left": 0.0, "x_right": 470.0, "y_bot": 0.0, "y_top": 43.0}
# (y, x_left, x_right) — como o extrator guarda em paineis_h
H_V302A = [
    (0.0, 0.0, 200.5), (0.0, 200.5, 360.0), (0.0, 360.0, 470.0),
    (5.0, 178.5, 200.5),                      # piso da abertura
    (43.0, 0.0, 178.5),                       # topo do seg.1, para em 178.5
    (45.0, 200.5, 360.0), (45.0, 360.0, 470.0),
]
# (x, y_bot, y_top) — como o extrator guarda em paineis_v
V_V302A = [
    (0.0, 0.0, 43.0),
    (178.5, 5.0, 43.0),                       # parede esquerda da abertura
    (200.5, 0.0, 5.0), (200.5, 0.0, 45.0),
    (360.0, 0.0, 45.0), (470.0, 0.0, 45.0),
]
SEGS_UNIFORMES = [
    {"largura_cm": 200.5, "height1": 43.0},
    {"largura_cm": 159.5, "height1": 43.0},
    {"largura_cm": 110.0, "height1": 43.0},
]


def test_detecta_a_abertura_com_sobra():
    ab = mrl._detectar_aberturas_viga(H_V302A, V_V302A, PAIR, SEGS_UNIFORMES)
    assert len(ab) == 1, f"esperava 1 abertura, veio {ab}"
    a = ab[0]
    assert (a["x_ini"], a["x_fim"]) == (178.5, 200.5)
    assert a["sobra_h"] == 5.0
    assert a["abertura_h"] == 38.0


def test_degrau_nao_e_abertura_de_viga():
    """Guarda: zona ja' rebaixada e' degrau, nao abertura.

    Sem ela a V301.A (paineis 244+50.5 com 44 contra 109 dos demais) tinha a
    faixa 0->294.5 lida como abertura e o desenho JA VALIDADO mudava. As duas
    faixas baixas sao adjacentes e precisam ser FUNDIDAS antes do teste — foi
    o que faltou na primeira versao da guarda.
    """
    pair = {"x_left": 0.0, "x_right": 445.7, "y_bot": 0.0, "y_top": 109.0}
    horiz = [
        (0.0, 0.0, 244.0), (0.0, 244.0, 294.5), (0.0, 294.5, 445.7),
        (65.0, 0.0, 294.5),                   # ombro do degrau
        (109.0, 294.5, 445.7),
    ]
    verts = [
        (0.0, 0.0, 65.0), (244.0, 0.0, 65.0),
        (294.5, 0.0, 109.0), (445.7, 0.0, 109.0),
    ]
    segs = [
        {"largura_cm": 244.0, "height1": 44.0},
        {"largura_cm": 50.5, "height1": 44.0},
        {"largura_cm": 151.2, "height1": 109.0},
    ]
    assert mrl._detectar_aberturas_viga(horiz, verts, pair, segs) == []


def test_sem_geometria_nao_inventa():
    assert mrl._detectar_aberturas_viga([], [], PAIR, SEGS_UNIFORMES) == []
    assert mrl._detectar_aberturas_viga(H_V302A, V_V302A, {}, SEGS_UNIFORMES) == []


# ── desenho ──────────────────────────────────────────────────────────────
# Alturas como o N2 da V302.A: seg.1 termina em 43 e seg.2/3 em 45.
PANEIS = [
    {"width": 200.5, "height1": 43.0},
    {"width": 159.5, "height1": 45.0},
    {"width": 110.0, "height1": 45.0},
]
PANEIS_LISOS = [dict(p, height1=43.0) for p in PANEIS]
ABERTURA = [{"x_ini": 178.5, "x_fim": 200.5, "sobra_h": 5.0, "abertura_h": 38.0}]


def _linhas(msp):
    H, V = [], []
    for e in msp:
        if e.dxftype() != "LINE" or "Pain" not in e.dxf.layer:
            continue
        a, b = e.dxf.start, e.dxf.end
        if abs(a.y - b.y) < 0.05:
            H.append((round(a.y, 1), round(min(a.x, b.x), 1), round(max(a.x, b.x), 1)))
        elif abs(a.x - b.x) < 0.05:
            V.append((round(a.x, 1), round(min(a.y, b.y), 1), round(max(a.y, b.y), 1)))
    return sorted(set(H)), sorted(set(V))


def test_desenho_recorta_o_topo_e_deixa_a_sobra():
    msp = ezdxf.new(setup=True).modelspace()
    lv._draw_panel_frame_n2(msp, 0.0, 0.0, 43.0, PANEIS, aberturas_viga=ABERTURA)
    H, V = _linhas(msp)
    assert (43.0, 0.0, 178.5) in H, f"topo do seg.1 deveria parar em 178.5; H={H}"
    assert not any(abs(y - 43.0) < 0.1 and x1 < 179 and x2 > 200
                   for y, x1, x2 in H), "topo atravessou a abertura"
    assert (5.0, 178.5, 200.5) in H, f"piso da abertura ausente; H={H}"
    assert (178.5, 5.0, 43.0) in V, f"parede da abertura ausente; V={V}"
    assert (0.0, 0.0, 470.0) in H, "fundo deveria seguir inteiro (sobra apoia nele)"


def test_altura_por_segmento_no_topo_e_nas_paredes():
    """O seg.2/3 tem 45 e o seg.1 tem 43 — o topo e as paredes acompanham."""
    msp = ezdxf.new(setup=True).modelspace()
    lv._draw_panel_frame_n2(msp, 0.0, 0.0, 43.0, PANEIS, aberturas_viga=ABERTURA)
    H, V = _linhas(msp)
    assert any(abs(y - 45.0) < 0.1 and x1 >= 200.0 for y, x1, _x2 in H), (
        f"topo do seg.2 deveria estar em 45; H={H}"
    )
    # a parede da direita tem de ALCANCAR 45, ainda que em mais de um pedaco
    topo_470 = max((y2 for x, _y1, y2 in V if abs(x - 470.0) < 0.1), default=0)
    assert abs(topo_470 - 45.0) < 0.1, f"parede em 470 parou em {topo_470}"


def test_controle_sem_abertura_desenha_igual_ao_de_antes():
    ref = ezdxf.new(setup=True).modelspace()
    lv._draw_panel_frame_n2(ref, 0.0, 0.0, 43.0, PANEIS_LISOS)
    got = ezdxf.new(setup=True).modelspace()
    lv._draw_panel_frame_n2(got, 0.0, 0.0, 43.0, PANEIS_LISOS, aberturas_viga=[])
    assert _linhas(ref) == _linhas(got)
    H, _ = _linhas(ref)
    assert (43.0, 0.0, 470.0) in H, "sem abertura o topo tem de sair inteiro"


def test_controle_altura_por_segmento_so_vale_com_abertura():
    """Sem abertura, as alturas por painel NAO podem partir o topo.

    E' o escopo que protege as vigas ja' validadas: medido, aplicar altura por
    segmento sem escopo mudava 42 de 120 unidades, as 17 da V301 inclusive.
    """
    msp = ezdxf.new(setup=True).modelspace()
    lv._draw_panel_frame_n2(msp, 0.0, 0.0, 43.0, PANEIS)  # alturas variadas
    H, _ = _linhas(msp)
    assert (43.0, 0.0, 470.0) in H, (
        f"sem abertura o topo tem de sair inteiro na altura da unidade; H={H}"
    )
