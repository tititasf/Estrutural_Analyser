# -*- coding: utf-8 -*-
"""Degrau de laje por trecho (LV) — teste positivo + de controle.

Regra (docs/LV-COMPREENDER-INTERPRETACAO-FICHAS-N2-N4.md §3.4.1): a laje pode
ter altura diferente por TRECHO da mesma face, com o topo PLANO. Onde ha'
painel de fechamento no topo a laje e' mais baixa e o painel completa a
altura; fora dele a laje sobe sozinha ate' o mesmo topo.

`laje_sup` escalar nao expressa isso — ele carrega so' o valor de BAIXO do
painel, e o N4 o aplicava na face inteira, deixando o lado sem painel
rebaixado pela espessura dele. O campo `laje_sup_trechos` corrige isso.

Medido no N2 da V13 face A (415 de largura): cota "15" a direita, cota "200"
sobre o trecho esquerdo e cota "3" na borda -> laje 15 nos 215 da direita,
laje 12 + painel 3 nos 200 da esquerda. A fronteira (x=200) NAO cai em divisa
de painel (244/63/108), por isso o trecho tem x proprio e o retangulo do
painel e' partido nela.
"""
from __future__ import annotations

import pathlib
import sys

import ezdxf
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import gerar_lv_dxf_stog as lv  # noqa: E402


def _msp():
    return ezdxf.new(setup=True).modelspace()


def _horizontais(msp, y_min=0.0):
    out = []
    for e in msp:
        if e.dxftype() != "LINE":
            continue
        a, b = e.dxf.start, e.dxf.end
        if abs(a.y - b.y) > 0.05 or a.y < y_min:
            continue
        x1, x2 = sorted((a.x, b.x))
        out.append((round(a.y, 1), round(x1, 1), round(x2, 1)))
    return sorted(set(out))


PANEIS_V13 = [
    {"width": 244.0, "height1": 44.0},
    {"width": 63.0, "height1": 44.0},
    {"width": 108.0, "height1": 44.0},
]
TRECHOS_V13 = [
    {"x0": 0.0, "x1": 200.0, "altura": 12.3},
    {"x0": 200.0, "x1": 415.0, "altura": 15.3},
]


def test_degrau_deixa_o_topo_da_laje_plano():
    """Positivo: com trechos, os dois lados chegam a mesma altura."""
    msp = _msp()
    lv._draw_panel_frame_n2(
        msp, 0.0, 0.0, 44.0, PANEIS_V13,
        marco_laje_sup=True, laje_sup=12.3, laje_trechos=TRECHOS_V13,
    )
    hs = _horizontais(msp, y_min=44.0)
    topos = {y for y, _x1, _x2 in hs if y > 44.5}
    assert topos, "nenhuma horizontal acima do corpo"
    # O trecho baixo (12.3) e o alto (15.3) existem, e o topo alto e' unico:
    # 44 + 15.3 = 59.3 fecha os dois lados.
    assert any(abs(y - 59.3) <= 0.15 for y in topos), (
        f"topo plano em 59.3 ausente; alturas vistas: {sorted(topos)}"
    )


def test_laje_e_uma_hachura_so_com_topo_continuo():
    """A fronteira do degrau NAO parte a laje em dois retangulos.

    Este teste afirmava o contrario ("a fronteira x=200 parte o retangulo").
    A medicao do N2 derrubou isso (2026-09-18): a hachura AR-CONC e' SEMPRE
    UMA por unidade —

        V13.A        415 de largura, +44..+59, uma so'
        V302.B       401,5 de largura, +44..+59, uma so'
        V302.A       470 de largura, fundo em dois niveis (43 e 45), uma so'
        CONT.V302.A  976 de largura, uma so'

    Onde ha' painel de fechamento ele ocupa os centimetros de CIMA dessa
    faixa, sobreposto a ela (V302.B: ANSI31 de +56 a +59 sobre a AR-CONC de
    +44 a +59). A altura menor que o N2 escreve ali — 12 contra 15 — e' a
    laje visivel sob o painel: assunto de cota, nao de desenho.

    Apontado pelo dono no SEGMENTO 6B: "essa divisao entre os dois hatchs
    nao precisa".
    """
    msp = _msp()
    lv._draw_panel_frame_n2(
        msp, 0.0, 0.0, 44.0, PANEIS_V13,
        marco_laje_sup=True, laje_sup=12.3, laje_trechos=TRECHOS_V13,
    )
    hachuras = [e for e in msp if e.dxftype() == "HATCH"
                and e.dxf.pattern_name == "AR-CONC"]
    assert len(hachuras) == 1, (
        f"laje saiu em {len(hachuras)} hachuras; o N2 tem uma so'"
    )
    largura = sum(p['width'] for p in PANEIS_V13)
    topos = _horizontais(msp, y_min=44.5)
    assert any(abs(x1) <= 0.15 and abs(x2 - largura) <= 0.15
               for _y, x1, x2 in topos), (
        f"o topo da laje nao e' continuo de 0 a {largura}: {topos}"
    )


def test_controle_sem_trechos_desenha_igual_ao_de_antes():
    """Controle: viga sem degrau nao pode mudar nada.

    Este e' o teste que impede a regra de vazar para quem nao tem degrau —
    medido na V301, que tem laje 15 uniforme e saiu byte a byte igual.
    """
    msp_sem = _msp()
    lv._draw_panel_frame_n2(
        msp_sem, 0.0, 0.0, 44.0, PANEIS_V13,
        marco_laje_sup=True, laje_sup=12.3,
    )
    msp_vazio = _msp()
    lv._draw_panel_frame_n2(
        msp_vazio, 0.0, 0.0, 44.0, PANEIS_V13,
        marco_laje_sup=True, laje_sup=12.3, laje_trechos=[],
    )
    assert _horizontais(msp_sem) == _horizontais(msp_vazio), (
        "lista de trechos vazia alterou o desenho — deveria ser inerte"
    )
    topos = {y for y, _x1, _x2 in _horizontais(msp_sem, y_min=44.5)}
    assert not any(abs(y - 59.3) <= 0.15 for y in topos), (
        "sem trechos apareceu topo de degrau (59.3) — regra vazou"
    )


@pytest.mark.parametrize("trechos", [None, [], [{"x0": 0, "x1": 100, "altura": 0}]])
def test_controle_campo_ausente_ou_sem_altura_e_inerte(trechos):
    """Campo ausente, vazio ou com altura zero cai no caminho antigo."""
    ref = _msp()
    lv._draw_panel_frame_n2(
        ref, 0.0, 0.0, 44.0, PANEIS_V13, marco_laje_sup=True, laje_sup=12.3,
    )
    got = _msp()
    lv._draw_panel_frame_n2(
        got, 0.0, 0.0, 44.0, PANEIS_V13,
        marco_laje_sup=True, laje_sup=12.3, laje_trechos=trechos,
    )
    assert _horizontais(ref) == _horizontais(got)
