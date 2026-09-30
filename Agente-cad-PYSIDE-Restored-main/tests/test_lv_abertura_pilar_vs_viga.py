# -*- coding: utf-8 -*-
"""Classificacao abertura de PILAR x abertura de VIGA (LV).

Regra do dono (2026-09-13) — o que distingue as duas e' O QUE CADA UMA
RECORTA:

    abertura de VIGA  -> produz vazio e RECORTE NO PAINEL;
    abertura de PILAR -> so' recorta o SARRAFO, o painel fica intacto.

So' a de PILAR leva tampa de ponta no sarrafo. O criterio anterior era
puramente geometrico ("a corrida que comeca muito depois das outras foi
interrompida") e nao sabia QUEM interrompeu: punha 24 tampas na V301, cujo N2
nao tem nenhuma vertical entre 5 e 9 cm, e acertava so' 3 das 4 da V13.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import gerar_lv_dxf_stog as lv  # noqa: E402


def _p(w, h):
    return {"width": float(w), "height1": float(h)}


def _sarr(x_left, x_right, y):
    return {"x_left": float(x_left), "x_right": float(x_right),
            "y_offset": float(y)}


# V13 face A, COPIADA do recorte do DB (nao estilizada): paineis 244/63/108
# todos com 44 (painel INTACTO). O pilar sobe do fundo e para as corridas de
# baixo em 78; a corrida de cima (y=37,3) passa POR CIMA dele e vai ate' 0.
# E' essa variacao por ALTURA que identifica o pilar.
V13_A_PANEIS = [_p(244, 44), _p(63, 44), _p(108, 44)]
V13_A_SARR = [
    _sarr(78, 244, 7.3), _sarr(244, 307, 7.3), _sarr(307, 408, 7.3),
    _sarr(78, 244, 18.3), _sarr(244, 307, 18.3), _sarr(307, 408, 18.3),
    _sarr(78, 244, 25.3), _sarr(244, 307, 25.3), _sarr(307, 408, 25.3),
    _sarr(0, 244, 37.3), _sarr(244, 307, 37.3), _sarr(307, 408, 37.3),
    _sarr(0, 200, 57.8),   # corrida do painel de fechamento, ACIMA do corpo
]


# A V13 tem painel de fechamento no topo cobrindo 0..200 — sem declara-lo a
# corrida `0->200` parece interrompida em 200 (ela acaba junto com o painel).
V13_A_TOPO = {"painel_sup_width": 200.0, "painel_sup_x_offset": 0.0}


def test_pilar_painel_intacto_vira_abertura():
    ab = lv.classificar_aberturas_pilar(V13_A_PANEIS, V13_A_SARR, **V13_A_TOPO)
    assert ab == [(0.0, 78.0)], f"esperado a abertura de 78, veio {ab}"


def test_viga_recorta_o_painel_entao_nao_e_pilar():
    """Mesmo x de interrupcao, mas com o painel REBAIXADO ali."""
    paineis = [_p(244, 44), _p(63, 109), _p(108, 109)]  # 1o painel rebaixado
    ab = lv.classificar_aberturas_pilar(paineis, V13_A_SARR, **V13_A_TOPO)
    assert ab == [], f"painel recortado e' abertura de VIGA, veio {ab}"


def test_divisa_entre_paineis_nao_e_abertura():
    """O sarrafo para na divisa por construcao — 244 e 307 nao sao abertura."""
    sarr = [_sarr(0, 244, 10), _sarr(244, 307, 10), _sarr(307, 415, 10)]
    ab = lv.classificar_aberturas_pilar(V13_A_PANEIS, sarr)
    assert ab == [], f"divisa de painel virou abertura: {ab}"


def test_borda_do_painel_de_fechamento_nao_e_abertura():
    """A corrida 0->200 acaba em 200 porque o painel de topo tem 200."""
    sarr = [_sarr(0, 415, 10), _sarr(0, 200, 30)]
    ab = lv.classificar_aberturas_pilar(
        V13_A_PANEIS, sarr, painel_sup_width=200.0, painel_sup_x_offset=0.0,
    )
    assert ab == [], f"borda do painel de fechamento virou abertura: {ab}"


def test_abertura_no_meio_da_face_conta():
    """O pilar NAO precisa ficar na ponta da viga.

    Medido em CONT.V302.A (4 paineis de 244, face de 976): as corridas de
    baixo cobrem [7,784] e [934,976]; a de cima (y=37,3) atravessa
    [732,976]. A abertura fica em 784..934 = 150, no MEIO da face -- e 150
    e' um valor escrito no N2. A regra antiga exigia encostar na borda e
    por isso nao achava esta; pior, montava o candidato A PARTIR da borda,
    o que tornava a propria condicao vazia.
    """
    paineis = [_p(244, 44), _p(244, 44), _p(244, 44), _p(244, 44)]
    sarr = []
    for y in (7.3, 18.8, 25.8):
        sarr += [_sarr(7, 244, y), _sarr(244, 488, y), _sarr(488, 732, y),
                 _sarr(732, 784, y), _sarr(934, 976, y)]
    sarr += [_sarr(7, 244, 37.3), _sarr(244, 488, 37.3),
             _sarr(488, 732, 37.3), _sarr(732, 976, 37.3)]
    ab = lv.classificar_aberturas_pilar(paineis, sarr)
    assert ab == [(784.0, 934.0)], f"esperada a abertura de 150, veio {ab}"


def test_lado_direito_tambem_e_detectado():
    """V13 face B, copiada do recorte: abertura espelhada, 337..415."""
    sarr = []
    for y in (7.4, 18.4, 25.4):
        sarr += [_sarr(7, 244, y), _sarr(244, 307, y), _sarr(307, 337, y)]
    sarr += [_sarr(7, 244, 37.4), _sarr(244, 307, 37.4),
             _sarr(307, 415, 37.4), _sarr(219, 415, 57.9)]
    ab = lv.classificar_aberturas_pilar(V13_A_PANEIS, sarr)
    assert (337.0, 415.0) in ab, f"abertura a direita nao detectada: {ab}"


def test_sem_dados_nao_inventa():
    assert lv.classificar_aberturas_pilar([], []) == []
    assert lv.classificar_aberturas_pilar(V13_A_PANEIS, []) == []
    assert lv.classificar_aberturas_pilar([], V13_A_SARR) == []
