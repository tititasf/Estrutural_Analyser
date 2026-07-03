#!/usr/bin/env python3
"""Gera DXFs N4 (zonas ABCD/CIMA/GRADES) para os 12 casos didaticos da ficha
`interpretacao_abcd.html`, sem depender de nenhuma obra real / DB.

Chama as funcoes puras de scripts/gerar_pl_dxf_stog.py diretamente
(setup_doc + generate_pilar_zone), ignorando main()/guarded_saveas
(que tocam o project_data.vision) -- 100% standalone.

Uso:
  python scripts/arete/gen_casos_n4_standalone.py            # todos os casos
  python scripts/arete/gen_casos_n4_standalone.py --caso 1   # só um caso
"""
import sys
import argparse
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(_ROOT / 'scripts'))

import gerar_pl_dxf_stog as gen  # noqa: E402

OUT_DXF = Path(__file__).parent / 'tmp' / 'n4_casos_abcd' / 'dxf'
OUT_DXF.mkdir(parents=True, exist_ok=True)

ZONES = ['abcd', 'cima', 'grades']

# ── Referencia de niveis (pedido do usuario 2026-07-02) ────────────────────
# nivel_saida (absoluto, escala das cotas "N:" do resto da ficha) fixo em
# 850.00 para todos os 12 casos -- e o "chao" comum de referencia.
# Os niveis reais de laje/viga citados nos casos (quase todos "N: 852.19",
# alguns 852.12) ficam sempre entre 852.00 e 853.00 (variacao maxima de 1m
# entre todos os diagramas). A altura do pilar gerado = (nivel_topo -
# nivel_saida_ref) * 100, o que da paineis ABCD de ~2.19m, dentro do teto de
# 3m pedido.
NIVEL_SAIDA_REF = 850.00
NIVEL_TOPO_PADRAO = 852.19  # nivel dominante usado nos 12 casos (dentro de 852-853)
ALTURA_CM = round((NIVEL_TOPO_PADRAO - NIVEL_SAIDA_REF) * 100)  # = 219cm (~2.19m, <= 3m)

H1_CHAPA = 2.0   # faixa da chapa base (fixo)
H3_TOPO = 34.0   # secao extra de topo (fixo)
H2_MEIO = ALTURA_CM - H1_CHAPA - H3_TOPO  # ajustado p/ h1+h2+h3 == ALTURA_CM (fecha sem sobra)


def _base_pj(nome, numero, comprimento, largura, altura=ALTURA_CM):
    """Ficha minima igual ao fixture tests/fixtures/fase4_samples/P1.json,
    com h1-h5/larg1-3 default e laje_X=0 em todas as faces (sobrescrito
    depois por caso). h1+h2+h3 fecha exatamente em `altura` (antes havia um
    retangulo extra sem cota porque h1+h2+h3=280 do fixture original nao
    batia com a altura usada aqui)."""
    pj = {
        'numero': str(numero), 'nome': nome,
        'comprimento': comprimento, 'largura': largura, 'altura': altura,
        'pavimento': 'CASO_DIDATICO', 'nivel_chegada': 0.0, 'nivel_saida': altura,
        'modo_distribuicao': 'NOVA',
        'grade_1': comprimento, 'grade_2': 0.0, 'grade_3': 0.0,
        'distancia_1': 14.0, 'distancia_2': 0.0,
        'par_1_2': comprimento / 2, 'par_2_3': comprimento / 2,
        'par_3_4': 0.0, 'par_4_5': 0.0, 'par_5_6': 0.0,
        'par_6_7': 0.0, 'par_7_8': 0.0, 'par_8_9': 0.0,
    }
    for f in 'ABCDEFGH':
        larg1 = comprimento if f in ('A', 'B') else largura
        pj.update({
            f'h1_{f}': H1_CHAPA, f'h2_{f}': H2_MEIO, f'h3_{f}': H3_TOPO,
            f'h4_{f}': 0.0, f'h5_{f}': 0.0,
            f'larg1_{f}': larg1 if f in ('A', 'B', 'C', 'D') else 0.0,
            f'larg2_{f}': 0.0, f'larg3_{f}': 0.0,
            f'laje_{f}': 0.0, f'posicao_laje_{f}': 0.0,
        })
    return pj


# ── Os 12 casos didaticos --------------------------------------------------
# comprimento/largura extraidos do texto de cada caso (nao do rotulo do SVG,
# que usa ordens de eixo inconsistentes entre HORIZONTAL/VERTICAL).
# laje_{A..D} = espessura (cm) da laje citada na linha "Lajes:" daquela face
# no HTML; 0 quando a face e classificada como VIGA / Dentro do interior /
# Viga que passa integral (sem laje na propria face).
CASOS = {
    1:  dict(nome='P28_CASO1',  comprimento=80,  largura=30, laje=dict(A=14, B=14, C=0,  D=14)),
    2:  dict(nome='P_CASO2',    comprimento=80,  largura=30, laje=dict(A=14, B=14, C=14, D=0)),
    3:  dict(nome='P_CASO3',    comprimento=100, largura=19, laje=dict(A=14, B=14, C=14, D=14)),
    4:  dict(nome='P_CASO4',    comprimento=100, largura=19, laje=dict(A=0,  B=0,  C=0,  D=0)),
    5:  dict(nome='P15_CASO5',  comprimento=100, largura=19, laje=dict(A=14, B=14, C=0,  D=0)),
    6:  dict(nome='P16_CASO6',  comprimento=100, largura=19, laje=dict(A=0,  B=0,  C=14, D=14)),
    7:  dict(nome='P44_CASO7',  comprimento=50,  largura=19, laje=dict(A=0,  B=0,  C=0,  D=0)),
    8:  dict(nome='P44_CASO8',  comprimento=50,  largura=19, laje=dict(A=0,  B=0,  C=0,  D=0)),
    9:  dict(nome='P16_CASO9',  comprimento=100, largura=19, laje=dict(A=12, B=0,  C=0,  D=0)),
    10: dict(nome='P21_CASO10', comprimento=86,  largura=19, laje=dict(A=13, B=13, C=0,  D=0)),
    11: dict(nome='P4_CASO11',  comprimento=66,  largura=19, laje=dict(A=14, B=14, C=14, D=0)),
    12: dict(nome='P5_CASO12',  comprimento=66,  largura=19, laje=dict(A=14, B=14, C=0,  D=14)),
}


def build_pj(caso_num):
    c = CASOS[caso_num]
    pj = _base_pj(c['nome'], caso_num, c['comprimento'], c['largura'])
    for face, esp in c['laje'].items():
        pj[f'laje_{face}'] = float(esp)
    return pj


def gen_caso(caso_num):
    pj = build_pj(caso_num)
    paths = {}
    for zone in ZONES:
        doc = gen.setup_doc()
        msp = doc.modelspace()
        n = gen.generate_pilar_zone(msp, pj, zone, row_y=0)
        out_path = OUT_DXF / f'caso{caso_num}_{zone}.dxf'
        doc.saveas(str(out_path))
        paths[zone] = (out_path, n)
        print(f'caso {caso_num:>2} [{zone:7s}] -> {out_path.name}  ({n} entidades)')
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caso', type=int, default=None)
    args = ap.parse_args()
    casos = [args.caso] if args.caso else sorted(CASOS)
    for c in casos:
        gen_caso(c)


if __name__ == '__main__':
    main()
