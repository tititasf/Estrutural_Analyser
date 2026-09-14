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


# V13 face A medida no recorte do DB: paineis 244/63/108 todos com 44 de
# altura (painel INTACTO) e a corrida de sarrafo comecando em 78 enquanto as
# outras comecam em 0 -> abertura de PILAR de 78, encostada na borda esquerda.
V13_A_PANEIS = [_p(244, 44), _p(63, 44), _p(108, 44)]
V13_A_SARR = [
    _sarr(0, 244, 10), _sarr(78, 244, 20), _sarr(0, 200, 30),
    _sarr(244, 307, 10), _sarr(307, 408, 10),
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


def test_abertura_no_meio_da_face_nao_conta():
    """O pilar fica na ponta da viga; interrupcao no meio nao e' pilar."""
    paineis = [_p(415, 44)]
    sarr = [_sarr(0, 415, 10), _sarr(0, 150, 20), _sarr(200, 415, 20)]
    ab = lv.classificar_aberturas_pilar(paineis, sarr)
    for ini, fim in ab:
        assert ini <= 4.0 or fim >= 411.0, (
            f"abertura {(ini, fim)} nao encosta em borda"
        )


def test_lado_direito_tambem_e_detectado():
    """V13 face B: abertura espelhada, 337..415."""
    sarr = [_sarr(0, 415, 10), _sarr(0, 337, 20), _sarr(0, 415, 30)]
    ab = lv.classificar_aberturas_pilar(V13_A_PANEIS, sarr)
    assert (337.0, 415.0) in ab, f"abertura a direita nao detectada: {ab}"


def test_sem_dados_nao_inventa():
    assert lv.classificar_aberturas_pilar([], []) == []
    assert lv.classificar_aberturas_pilar(V13_A_PANEIS, []) == []
    assert lv.classificar_aberturas_pilar([], V13_A_SARR) == []
