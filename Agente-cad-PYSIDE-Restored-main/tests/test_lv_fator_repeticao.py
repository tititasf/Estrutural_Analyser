# -*- coding: utf-8 -*-
"""Fator de repeticao "NX" nas laterais LV.

Duas pontas do mesmo assunto:

  N4 (vem do N2) — o desenho humano ja' traz o marcador escrito ("7X"), e o
  motor so' precisa LER. Coberto pelos casos de leitura no fim do arquivo.

  N3 (vem do N1) — la' chega a lista REAL de segmentos e o desenho tem de ser
  montado ja' comprimido. Regra do dono (2026-09-19):

    - a sequencia comeca a partir do SEGUNDO painel;
    - so' entram paineis COMPLETOS (244) e todos iguais entre si;
    - o PRIMEIRO e o ULTIMO painel nunca entram no multiplicador;
    - com menos de 2 paineis na sequencia nao ha' multiplicador.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import gerar_lv_dxf_stog as lv  # noqa: E402


def _c(larguras):
    return lv.comprimir_paineis_repetidos(larguras)


def test_tres_paineis_iguais_nao_tem_multiplicador():
    """Sobra 1 painel no meio — o dono: "se forem 3 nao existe multiplicador"."""
    assert _c([244, 244, 244]) == [(244.0, 1), (244.0, 1), (244.0, 1)]


def test_quatro_paineis_iguais_viram_244x2():
    """"4 paineis sim: 244 244x2 244"."""
    assert _c([244, 244, 244, 244]) == [(244.0, 1), (244.0, 2), (244.0, 1)]


def test_pontas_de_qualquer_largura_nao_entram_no_fator():
    """"80(qualquer valor de painel) 244x2 122(qualquer valor de painel)"."""
    assert _c([80, 244, 244, 122]) == [(80.0, 1), (244.0, 2), (122.0, 1)]


def test_sequencia_quebrada_nao_tem_multiplicador():
    """"mas se for 244 244 80 244 ai nao" — a sequencia interna quebra."""
    assert _c([244, 244, 80, 244]) == [
        (244.0, 1), (244.0, 1), (80.0, 1), (244.0, 1),
    ]


def test_caso_real_da_v303_b():
    """A V303.B soma 244 + 7x244 + 66,5 + 244 = 2262,5 (confirmado pelo dono).

    A lista REAL de segmentos que o N1 entregaria e a compressao que o N2
    desenha — 244 | 244x7 | 66,5 | 244 — tem de bater.
    """
    reais = [244] * 8 + [66.5, 244]
    assert _c(reais) == [(244.0, 1), (244.0, 7), (66.5, 1), (244.0, 1)]
    total = sum(w * f for w, f in _c(reais))
    assert abs(total - 2262.5) < 0.05, f"total {total}, esperado 2262,5"


def test_sequencia_longa_para_no_penultimo():
    """O ULTIMO painel nunca entra: 6 iguais viram 244 | 244x4 | 244."""
    assert _c([244] * 6) == [(244.0, 1), (244.0, 4), (244.0, 1)]


def test_painel_incompleto_no_meio_nao_multiplica():
    """So' painel COMPLETO entra na sequencia."""
    assert _c([244, 170, 170, 244]) == [
        (244.0, 1), (170.0, 1), (170.0, 1), (244.0, 1),
    ]


def test_lista_curta_e_inerte():
    assert _c([]) == []
    assert _c([244]) == [(244.0, 1)]
    assert _c([244, 244]) == [(244.0, 1), (244.0, 1)]


def test_soma_com_fator_preserva_o_total_real():
    """Comprimir nao pode mudar a soma — e' so' representacao."""
    for reais in ([244] * 8 + [66.5, 244], [80, 244, 244, 122], [244] * 6):
        assert abs(sum(w * f for w, f in _c(reais)) - sum(reais)) < 0.05
