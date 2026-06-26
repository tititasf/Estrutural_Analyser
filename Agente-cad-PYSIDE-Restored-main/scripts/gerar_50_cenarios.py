#!/usr/bin/env python3
"""
gerar_50_cenarios.py — Gera 50+ cenários SCR de cada robô para base de dados sólida
=====================================================================================
Cenários cobrem: magro/gordo/alto/baixo, com/sem grade, com/sem laje,
com/sem abertura, pilar especial L, grades altas, sarrafeado vs grade.

Uso:
  python scripts/gerar_50_cenarios.py --tipo pilares
  python scripts/gerar_50_cenarios.py --tipo vigas
  python scripts/gerar_50_cenarios.py --tipo all
"""
import sys, io, os, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROBOT_ROOT = os.path.join(os.path.dirname(__file__), '..', '_ROBOS_ABAS', 'Robo_Pilares', 'pilares-atualizado-09-25')

def setup_paths():
    for d in ['src', 'src/interfaces', 'src/robots', 'src/utils', 'src/models']:
        p = os.path.join(ROBOT_ROOT, d)
        if p not in sys.path:
            sys.path.insert(0, p)

def make_pilar_dados(nome, comp, larg, altura=280, grade_1=0, grade_2=0,
                     laje_a=0, abert_esq=False, abert_dir=False,
                     h_custom=None):
    """Cria dict de dados para o robô de pilares."""
    d = {
        'interface_principal': None, 'pavimento': 'CENARIOS', 'nome': nome,
        'numero': nome.replace('P', ''), 'comprimento': comp, 'largura': larg,
        'altura': altura, 'nivel_saida': 0, 'nivel_chegada': altura,
        'nivel_diferencial': 0, 'pavimento_anterior': '',
        'parafuso_p1_p2': 62 if comp > 20 else 0,
        'parafuso_p2_p3': 61 if comp > 30 else 0,
        'parafuso_p3_p4': 61 if comp > 40 else 0,
        'parafuso_p4_p5': 62 if comp > 50 else 0,
        'parafuso_p5_p6': 0, 'parafuso_p6_p7': 0,
        'parafuso_p7_p8': 0, 'parafuso_p8_p9': 0,
        'grades_grupo1': {
            'grade_1': grade_1, 'distancia_1': 14 if grade_1 > 0 else 0,
            'grade_2': grade_2, 'distancia_2': 0, 'grade_3': 0,
        },
    }
    # Calculate h1-h5
    if h_custom:
        h1, h2, h3, h4, h5 = h_custom
    else:
        h_rem = altura
        h1 = min(2.0, h_rem); h_rem -= h1
        h2 = min(244.0, h_rem); h_rem -= h2
        h3 = min(244.0, h_rem); h_rem -= h3
        h4 = min(244.0, h_rem); h_rem -= h4
        h5 = max(0, h_rem)

    for face in 'ABCDEFGH':
        d[f'laje_{face}'] = laje_a if face == 'A' else 0.0
        d[f'posicao_laje_{face}'] = 3 if laje_a > 0 and face == 'A' else 0
        for i in range(1, 4):
            w = comp if face in 'AC' and i == 1 else (larg if face in 'BD' and i == 1 else 0.0)
            d[f'larg{i}_{face}'] = w
        d[f'h1_{face}'] = h1; d[f'h2_{face}'] = h2; d[f'h3_{face}'] = h3
        d[f'h4_{face}'] = h4; d[f'h5_{face}'] = h5
        for h in range(2, 6):
            for l in range(1, 4):
                d[f'hachura_l{l}_h{h}_{face}'] = ''

    for s in ['esq', 'dir']:
        for n in ['1', '2']:
            for f in ['A', 'B']:
                for k in ['distancia', 'largura', 'profundidade', 'posicao']:
                    val = 0
                    if abert_esq and s == 'esq' and n == '1' and f == 'A':
                        val = {'distancia': 50, 'largura': 30, 'profundidade': 5, 'posicao': 1}.get(k, 0)
                    if abert_dir and s == 'dir' and n == '1' and f == 'A':
                        val = {'distancia': 50, 'largura': 25, 'profundidade': 5, 'posicao': 1}.get(k, 0)
                    d[f'{k}_{s}_{n}_{f}'] = val
    return d


# ── 50 CENÁRIOS DE PILARES ──────────────────────────────────────────────
CENARIOS_PILARES = [
    # Básicos (variação de dimensão)
    ("P01", 14, 14, 280, 0, 0, "Minimo 14x14"),
    ("P02", 19, 14, 280, 0, 0, "Fino 19x14"),
    ("P03", 19, 19, 280, 0, 0, "Quadrado pequeno 19x19"),
    ("P04", 24, 19, 280, 0, 0, "Retangular 24x19"),
    ("P05", 30, 19, 280, 0, 0, "30x19"),
    ("P06", 30, 30, 280, 0, 0, "Quadrado medio 30x30"),
    ("P07", 40, 19, 280, 0, 0, "Largo fino 40x19"),
    ("P08", 40, 30, 280, 0, 0, "40x30"),
    ("P09", 40, 40, 280, 0, 0, "Quadrado 40x40"),
    ("P10", 50, 19, 280, 0, 0, "Muito largo 50x19"),
    ("P11", 56, 46, 280, 136, 136, "Referencia P11 56x46 c/ grades"),
    ("P12", 60, 19, 280, 0, 0, "60x19"),
    ("P13", 60, 40, 280, 0, 0, "60x40"),
    ("P14", 60, 60, 280, 0, 0, "Quadrado grande 60x60"),
    ("P15", 70, 19, 280, 0, 0, "70x19"),
    ("P16", 80, 19, 280, 0, 0, "80x19"),
    ("P17", 80, 40, 280, 0, 0, "80x40"),
    ("P18", 90, 19, 280, 0, 0, "90x19"),
    ("P19", 90, 90, 280, 136, 136, "Gordo 90x90 c/ grades"),
    ("P20", 100, 19, 280, 0, 0, "100x19 (parede)"),
    # Alturas variadas
    ("P21", 40, 30, 150, 0, 0, "Baixo h=150"),
    ("P22", 40, 30, 200, 0, 0, "Medio-baixo h=200"),
    ("P23", 40, 30, 280, 0, 0, "Padrao h=280"),
    ("P24", 40, 30, 350, 0, 0, "Alto h=350"),
    ("P25", 40, 30, 400, 115, 115, "Muito alto h=400 c/ grades"),
    ("P26", 40, 30, 500, 115, 115, "Extra alto h=500 c/ grades"),
    ("P27", 40, 30, 600, 115, 115, "Maximo h=600 c/ grades"),
    # Com grades
    ("P28", 30, 30, 280, 80, 0, "Grade 1 curta (80cm)"),
    ("P29", 30, 30, 280, 115, 0, "Grade 1 media (115cm)"),
    ("P30", 30, 30, 280, 136, 0, "Grade 1 longa (136cm)"),
    ("P31", 30, 30, 280, 136, 136, "Grade 1+2 (136+136)"),
    ("P32", 50, 40, 280, 200, 200, "Grades grandes (200cm)"),
    ("P33", 60, 60, 280, 115, 115, "Gordo c/ grades medias"),
    # Com laje
    ("P34", 40, 30, 280, 0, 0, "Com laje A=10"),
    ("P35", 40, 30, 280, 0, 0, "Com laje A=15"),
    ("P36", 40, 30, 280, 136, 136, "Laje + grades"),
    ("P37", 60, 40, 280, 136, 136, "Largo + laje + grades"),
    # Com aberturas
    ("P38", 40, 30, 280, 0, 0, "Abertura esquerda"),
    ("P39", 40, 30, 280, 0, 0, "Abertura direita"),
    ("P40", 40, 30, 280, 0, 0, "Abertura ambos lados"),
    ("P41", 56, 46, 280, 136, 136, "Referencia + abertura esq"),
    ("P42", 56, 46, 280, 136, 136, "Referencia + abertura dir"),
    # Combinações
    ("P43", 90, 90, 350, 200, 200, "Gordo alto c/ grades grandes"),
    ("P44", 19, 14, 150, 0, 0, "Minimo tudo"),
    ("P45", 100, 90, 600, 200, 200, "Maximo tudo"),
    ("P46", 80, 60, 280, 136, 136, "Grande c/ grades"),
    ("P47", 50, 25, 280, 115, 0, "Assimetrico com grade 1"),
    ("P48", 70, 19, 400, 136, 136, "Parede alta c/ grades"),
    ("P49", 30, 30, 280, 80, 80, "Quadrado c/ grades curtas"),
    ("P50", 56, 46, 280, 136, 136, "P11 clone (controle)"),
]


def gerar_cenarios_pilares():
    """Gera SCR CIMA para todos os 50 cenários."""
    setup_paths()
    os.chdir(ROBOT_ROOT)

    from CIMA_FUNCIONAL_EXCEL import preencher_campos_diretamente_e_gerar_scripts

    resultados = []
    for nome, comp, larg, alt, g1, g2, desc in CENARIOS_PILARES:
        laje_a = 10 if nome in ('P34',) else (15 if nome in ('P35', 'P36', 'P37') else 0)
        abert_esq = nome in ('P38', 'P40', 'P41')
        abert_dir = nome in ('P39', 'P40', 'P42')

        dados = make_pilar_dados(nome, comp, larg, alt, g1, g2, laje_a, abert_esq, abert_dir)

        try:
            preencher_campos_diretamente_e_gerar_scripts(dados)
            scr_path = f'SCRIPTS_ROBOS/CENARIOS_CIMA/{nome}_CIMA.scr'
            sz = os.path.getsize(scr_path) if os.path.exists(scr_path) else 0
            status = 'OK' if sz > 100 else 'FAIL'
            resultados.append((nome, desc, comp, larg, alt, g1, sz, status))
            print(f"  {nome}: {comp}x{larg} h={alt} g={g1} -> {sz} bytes [{status}]")
        except Exception as e:
            resultados.append((nome, desc, comp, larg, alt, g1, 0, f'ERR:{str(e)[:30]}'))
            print(f"  {nome}: ERRO {str(e)[:50]}")

    # Salvar resumo
    with open('SCRIPTS_ROBOS/cenarios_pilares_resumo.json', 'w') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)

    ok = sum(1 for r in resultados if r[7] == 'OK')
    print(f"\n=== RESUMO: {ok}/{len(resultados)} cenários OK ===")
    return resultados


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--tipo', choices=['pilares', 'vigas', 'fv', 'lajes', 'all'], default='pilares')
    args = parser.parse_args()

    if args.tipo in ('pilares', 'all'):
        gerar_cenarios_pilares()
