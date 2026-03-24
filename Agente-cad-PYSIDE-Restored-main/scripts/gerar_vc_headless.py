#!/usr/bin/env python3
"""
gerar_vc_headless.py — Gera 50 cenários Visão de Corte (VC) headless
=====================================================================
Baseado na anatomia SCR real (VC-1_V1.Aa_V1.Bb.scr — 527 linhas).
Layers: Painéis, SARRAFO_2_2X7, BARRA_ANCORAGEM, HACHURACONCRETO, COTA
Blocos: PAR_ESQ, PAR_FUNDO_ESQ, PAR_FUNDO_DIR, par_int_esq, par_int_dir
Comandos: _MLINE + _CMLSTYLE SAR3 + _CMLSCALE 4.400
"""
import os, json

X0 = 12270.59  # Centro X padrão (do SCR real)
Y0 = 2126.99   # Centro Y padrão
BASE_Y = 1920.59  # Y base dos painéis

def gerar_vc_scr(nome_vc, h_A, h_B, b_alma=19, laje_sup=0, laje_inf=0,
                  laje_central=0, tipo_A='Sarrafeado', tipo_B='Sarrafeado',
                  nome_viga='V1', x0=X0, y0=Y0):
    """Gera conteúdo SCR de Visão de Corte."""
    lines = []

    # Header
    h_total = max(h_A, h_B)
    lines.append(f'; (numeracao: {nome_vc}, largura: 200, altura: {h_total})')
    lines.append(';')
    lines.append('; --- VISAO DE CORTE ---')

    # Zoom
    lines.append('_ZOOM')
    lines.append(f'C {x0:.2f},{y0:.2f} {h_total + 100}')
    lines.append(';')

    base_y = y0 - h_total/2

    # Face A (esquerda) — painel base (4cm × h_A)
    pa_x = x0 - b_alma/2 - 20  # Painel A à esquerda do centro
    lines.append('-LAYER')
    lines.append(f'S Paineis')
    lines.append('')
    lines.append(';')
    lines.append('_PLINE')
    lines.append(f'{pa_x:.2f},{base_y:.2f}')
    lines.append(f'{pa_x+4:.2f},{base_y:.2f}')
    lines.append(f'{pa_x+4:.2f},{base_y+h_A:.2f}')
    lines.append(f'{pa_x:.2f},{base_y+h_A:.2f}')
    lines.append('C')
    lines.append(';')

    # Face B (direita) — painel base (4cm × h_B)
    pb_x = x0 + b_alma/2 + 16
    lines.append('_PLINE')
    lines.append(f'{pb_x:.2f},{base_y:.2f}')
    lines.append(f'{pb_x+4:.2f},{base_y:.2f}')
    lines.append(f'{pb_x+4:.2f},{base_y+h_B:.2f}')
    lines.append(f'{pb_x:.2f},{base_y+h_B:.2f}')
    lines.append('C')
    lines.append(';')

    # Sarrafos (MLINE + SAR3) — Face A
    def add_mline_sarrafo(x_start, x_end, y_pos):
        lines.append('-LAYER')
        lines.append('S SARRAFO_2_2X7')
        lines.append('')
        lines.append(';')
        lines.append('_CMLSTYLE')
        lines.append('SAR3')
        lines.append('_CMLJUST')
        lines.append('2')
        lines.append('_CMLSCALE')
        lines.append('4.400')
        lines.append('_MLINE')
        lines.append(f'{x_start:.2f},{y_pos:.2f}')
        lines.append(f'{x_end:.2f},{y_pos:.2f}')
        lines.append('')
        lines.append(';')

    # Sarrafos na base (ambas faces)
    sarr_a_x1 = pa_x - 8
    sarr_a_x2 = pa_x + 12
    sarr_b_x1 = pb_x - 8
    sarr_b_x2 = pb_x + 12

    # Sarrafos a cada ~90cm de altura
    sarr_positions = [base_y - 4.4]
    y_cur = base_y + 7
    while y_cur < base_y + min(h_A, h_B) - 7:
        sarr_positions.append(y_cur)
        y_cur += 90
    sarr_positions.append(base_y + min(h_A, h_B) - 7)

    for sy in sarr_positions:
        add_mline_sarrafo(sarr_a_x1, sarr_a_x2, sy)
        add_mline_sarrafo(sarr_b_x1, sarr_b_x2, sy)

    # Barra de ancoragem (conecta Face A e Face B)
    lines.append('-LAYER')
    lines.append('S BARRA_ANCORAGEM')
    lines.append('')
    lines.append(';')

    anc_y_positions = [base_y - 4 + 7, base_y + min(h_A, h_B) - 10]
    for ay in anc_y_positions:
        anc_x1 = pa_x + 4 + 10
        anc_x2 = pb_x - 10
        lines.append('_PLINE')
        lines.append(f'{anc_x1:.2f},{ay:.2f}')
        lines.append(f'{anc_x2:.2f},{ay:.2f}')
        lines.append(f'{anc_x2:.2f},{ay+2:.2f}')
        lines.append(f'{anc_x1:.2f},{ay+2:.2f}')
        lines.append('C')
        lines.append(';')

    # INSERT blocks
    for block, bx, by in [
        ('PAR_FUNDO_ESQ', anc_y_positions[0] if anc_y_positions else base_y, pa_x+4+10),
        ('PAR_FUNDO_DIR', anc_y_positions[0] if anc_y_positions else base_y, pb_x-10),
        ('PAR_ESQ', anc_y_positions[-1] if len(anc_y_positions) > 1 else base_y+h_A/2, pa_x-5),
        ('par_int_esq', base_y + h_A/2, pa_x+4+5),
        ('par_int_dir', base_y + h_B/2, pb_x-5),
    ]:
        lines.append(f'_INSERT')
        lines.append(block)
        lines.append(f'{by:.2f},{bx:.2f}')
        lines.append('1.0')
        lines.append('0')
        lines.append(';')

    # Hachura concreto entre faces
    lines.append('-LAYER')
    lines.append('S HACHURACONCRETO')
    lines.append('')
    lines.append(';')
    hc_x1 = pa_x + 4 + 2
    hc_x2 = pb_x - 2
    hc_y1 = base_y
    hc_y2 = base_y + min(h_A, h_B)
    lines.append('_PLINE')
    lines.append(f'{hc_x1:.2f},{hc_y1:.2f}')
    lines.append(f'{hc_x2:.2f},{hc_y1:.2f}')
    lines.append(f'{hc_x2:.2f},{hc_y2:.2f}')
    lines.append(f'{hc_x1:.2f},{hc_y2:.2f}')
    lines.append('C')
    lines.append(';')

    # Cotas verticais
    lines.append('-LAYER')
    lines.append('S COTA')
    lines.append('')
    lines.append(';')
    # Cota Face A
    lines.append('_DIMLINEAR')
    lines.append(f'{pa_x-15:.2f},{base_y:.2f}')
    lines.append(f'{pa_x-15:.2f},{base_y+h_A:.2f}')
    lines.append(f'{pa_x-25:.2f},{base_y+h_A/2:.2f}')
    lines.append(';')
    # Cota Face B
    lines.append('_DIMLINEAR')
    lines.append(f'{pb_x+20:.2f},{base_y:.2f}')
    lines.append(f'{pb_x+20:.2f},{base_y+h_B:.2f}')
    lines.append(f'{pb_x+30:.2f},{base_y+h_B/2:.2f}')
    lines.append(';')

    # Texto nome viga
    lines.append('_TEXT')
    lines.append('C')
    lines.append(f'{x0:.2f},{base_y+h_total+50:.2f}')
    lines.append('40.0')
    lines.append('0')
    lines.append(nome_viga)
    lines.append(';')

    # Dimensão (bxh)
    lines.append('_TEXT')
    lines.append('C')
    lines.append(f'{x0:.2f},{base_y+h_total+10:.2f}')
    lines.append('30.0')
    lines.append('0')
    lines.append(f'({b_alma}x{h_total:.0f})')
    lines.append(';')

    lines.append('; --- FIM VISAO DE CORTE ---')

    return '\r\n'.join(lines)


# 50 cenários VC
cenarios = []
for i, (h_A, h_B, b, ls, li, lc, tA, tB, nome) in enumerate([
    # Básicos simétricos
    (30, 30, 15, 0, 0, 0, 'S', 'S', 'V01'), (60, 60, 15, 0, 0, 0, 'S', 'S', 'V02'),
    (120, 120, 15, 0, 0, 0, 'S', 'S', 'V03'), (180, 180, 19, 0, 0, 0, 'S', 'S', 'V04'),
    (200, 200, 19, 0, 0, 0, 'S', 'S', 'V05'),
    # Assimétricos
    (60, 30, 15, 0, 0, 0, 'S', 'S', 'V06'), (120, 60, 15, 0, 0, 0, 'S', 'S', 'V07'),
    (180, 90, 19, 0, 0, 0, 'S', 'S', 'V08'), (200, 100, 19, 0, 0, 0, 'S', 'S', 'V09'),
    (120, 180, 15, 0, 0, 0, 'S', 'S', 'V10'),
    # Com laje sup
    (60, 60, 15, 7, 0, 0, 'S', 'S', 'V11'), (120, 120, 19, 7, 0, 0, 'S', 'S', 'V12'),
    (60, 60, 15, 0, 7, 0, 'S', 'S', 'V13'), (120, 120, 19, 7, 7, 0, 'S', 'S', 'V14'),
    (120, 120, 19, 7, 7, 15, 'S', 'S', 'V15'),
    # Grade mode
    (60, 60, 15, 0, 0, 0, 'G', 'G', 'V16'), (120, 120, 19, 0, 0, 0, 'G', 'G', 'V17'),
    (60, 60, 15, 0, 0, 0, 'G', 'S', 'V18'), (120, 120, 19, 0, 0, 0, 'S', 'G', 'V19'),
    (180, 180, 19, 7, 7, 0, 'G', 'G', 'V20'),
    # Variação b_alma
    (60, 60, 14, 0, 0, 0, 'S', 'S', 'V21'), (60, 60, 19, 0, 0, 0, 'S', 'S', 'V22'),
    (60, 60, 24, 0, 0, 0, 'S', 'S', 'V23'), (60, 60, 30, 0, 0, 0, 'S', 'S', 'V24'),
    (60, 60, 45, 0, 0, 0, 'S', 'S', 'V25'),
    # Extremos
    (10, 10, 14, 0, 0, 0, 'S', 'S', 'V26'), (200, 200, 45, 7, 7, 15, 'G', 'G', 'V27'),
    (15, 15, 14, 0, 0, 0, 'S', 'S', 'V28'), (25, 25, 15, 0, 0, 0, 'S', 'S', 'V29'),
    (80, 80, 19, 0, 0, 0, 'S', 'S', 'V30'),
    # Combinações diversas
    (60, 30, 19, 7, 0, 0, 'S', 'S', 'V31'), (120, 60, 24, 7, 7, 0, 'G', 'S', 'V32'),
    (180, 120, 19, 0, 7, 15, 'S', 'G', 'V33'), (60, 120, 15, 7, 7, 0, 'G', 'G', 'V34'),
    (90, 45, 19, 0, 0, 0, 'S', 'S', 'V35'),
    # Mais variações
    (40, 40, 15, 0, 0, 0, 'S', 'S', 'V36'), (50, 50, 19, 7, 0, 0, 'S', 'S', 'V37'),
    (70, 70, 19, 0, 7, 0, 'S', 'S', 'V38'), (100, 100, 24, 7, 7, 0, 'S', 'S', 'V39'),
    (150, 150, 30, 7, 7, 15, 'G', 'G', 'V40'),
    # Séries progressivas
    (30, 60, 15, 0, 0, 0, 'S', 'S', 'V41'), (60, 90, 19, 0, 0, 0, 'S', 'S', 'V42'),
    (90, 120, 19, 7, 0, 0, 'S', 'S', 'V43'), (120, 150, 24, 7, 7, 0, 'G', 'S', 'V44'),
    (150, 180, 30, 7, 7, 15, 'G', 'G', 'V45'),
    # Últimos
    (30, 180, 15, 0, 0, 0, 'S', 'S', 'V46'), (180, 30, 19, 0, 0, 0, 'S', 'S', 'V47'),
    (100, 60, 19, 7, 7, 0, 'S', 'G', 'V48'), (60, 100, 24, 7, 0, 15, 'G', 'S', 'V49'),
    (120, 120, 19, 7, 7, 15, 'G', 'G', 'V50'),
], start=1):
    cenarios.append({
        'nome_vc': f'VC-{i}', 'h_A': h_A, 'h_B': h_B, 'b_alma': b,
        'laje_sup': ls, 'laje_inf': li, 'laje_central': lc,
        'tipo_A': tA, 'tipo_B': tB, 'nome_viga': nome,
    })

out_dir = os.path.join(os.path.dirname(__file__), '..', '_ROBOS_ABAS', 'Robo_Laterais_de_Vigas', 'SCRIPTS', 'CENARIOS_VC_HEADLESS')
os.makedirs(out_dir, exist_ok=True)

results = []
for c in cenarios:
    scr = gerar_vc_scr(**c)
    fname = f"{c['nome_vc']}_{c['nome_viga']}.scr"
    fpath = os.path.join(out_dir, fname)
    with open(fpath, 'wb') as f:
        f.write(b'\xff\xfe')
        f.write(scr.encode('utf-16-le'))
    sz = os.path.getsize(fpath)
    results.append((c['nome_vc'], c['nome_viga'], c['h_A'], c['h_B'], c['b_alma'], sz, 'OK'))
    print(f"  {c['nome_vc']} ({c['nome_viga']}): h_A={c['h_A']} h_B={c['h_B']} b={c['b_alma']} -> {sz} bytes")

ok = sum(1 for r in results if r[6] == 'OK')
print(f"\n=== VC HEADLESS: {ok}/{len(results)} OK ===")

json.dump(results, open(os.path.join(out_dir, 'cenarios_vc_resumo.json'), 'w'), indent=2)
