#!/usr/bin/env python3
"""
json_to_scr_lv.py
Gera arquivos SCR de laterais de viga (LV) a partir dos JSON Fase-4,
replicando a lógica exata do robô ALIMONTI gerador_script_viga.py.

JSON: Fase-4_Sincronizacao/JSON_Vigas_Laterais/V{n}_{side}.json
Output: Fase-5_Geracao_Scripts/SCR_Vigas_Laterais/

Uso:
  python scripts/json_to_scr_lv.py
  python scripts/json_to_scr_lv.py --obra D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1
"""
import sys
import argparse
import json
import math
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Posição inicial (normalizada — scr_to_dxf translada automaticamente)
X_INICIAL = 0.0
Y_INICIAL = 0.0


def soma_altura(val):
    """Soma alturas no formato 'N+N' ou float."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val)
    if '+' in s:
        return sum(float(p.strip()) for p in s.split('+') if p.strip())
    try:
        return float(s)
    except Exception:
        return 0.0


def get_sarrafo_specs(altura):
    """
    Retorna especificações dos sarrafos horizontais para painel sarrafeado.
    Reproduz exatamente get_linha_specs() do gerador_script_viga.py.
    """
    if altura < 15:
        layer = 'SARR_2.2x5'
        return layer, [(5, 'baixo'), (5, 'cima')]
    elif altura < 30:
        layer = 'SARR_2.2x7'
        return layer, [(7, 'baixo'), (7, 'cima')]
    elif altura < 80:
        layer = 'SARR_2.2x7'
        return layer, [(7, 'baixo'), (7, 'cima'), (3.5, 'centro_cima'), (3.5, 'centro_baixo')]
    else:
        layer = 'SARR_2.2x7'
        return layer, [
            (7, 'baixo'), (7, 'cima'),
            (3.5, 'centro_cima'), (3.5, 'centro_baixo'),
            (3.5, 'quarto_inf_cima'), (3.5, 'quarto_inf_baixo'),
            (3.5, 'quarto_sup_cima'), (3.5, 'quarto_sup_baixo'),
        ]


def sarrafo_y(posicao, tipo, y_base, altura):
    """Calcula posição y de um sarrafo horizontal dado posição e base."""
    if posicao == 'baixo':
        return y_base + tipo
    elif posicao == 'cima':
        return y_base + altura - tipo
    elif posicao == 'centro_cima':
        return y_base + altura / 2 + tipo
    elif posicao == 'centro_baixo':
        return y_base + altura / 2 - tipo
    elif posicao == 'quarto_inf_cima':
        return y_base + altura / 4 + tipo
    elif posicao == 'quarto_inf_baixo':
        return y_base + altura / 4 - tipo
    elif posicao == 'quarto_sup_cima':
        return y_base + 3 * altura / 4 + tipo
    elif posicao == 'quarto_sup_baixo':
        return y_base + 3 * altura / 4 - tipo
    return y_base


def gerar_scr_lv(dados):
    """
    Gera o conteúdo SCR de uma lateral de viga.
    Reproduz _gerar_conteudo_script() do gerador_script_viga.py.

    Campos em dados:
        nome            (str)  nome da face, ex: "V101_A"
        largura         (float) largura total da face
        altura_geral    (str/float) altura total
        paineis_larguras (list[float]) larguras individuais dos painéis
        paineis_alturas  (list[str/float]) altura1 por painel
        paineis_alturas2 (list[str/float]) altura2 por painel (0 se N/A)
        paineis_tipo1    (list[str]) "Sarrafeado" ou "Grade"
        paineis_tipo2    (list[str]) "Sarrafeado" ou "Grade"
        paineis_grade_altura1 (list[float]) grade_h1 por painel
        paineis_grade_altura2 (list[float]) grade_h2 por painel
        lajes_sup        (list[float]) laje sup por painel (0 se N/A)
        lajes_inf        (list[float]) laje inf por painel
        lajes_central_alt(list[float]) laje central por painel
        texto_esq       (str) label pilar esquerdo
        texto_dir       (str) label pilar direito
        numero          (str/int) numeração
        continuacao     (str) tipo de continuação
    """
    nome = dados.get('nome', 'SemNome')
    texto_esq = dados.get('texto_esq', '')
    texto_dir = dados.get('texto_dir', '')
    largura_total = float(dados.get('largura', 0))
    continuacao = str(dados.get('continuacao', 'Viga')).strip() or 'Viga'

    # Altura geral
    alt_geral_raw = str(dados.get('altura_geral', 0))
    altura_geral = soma_altura(alt_geral_raw)

    # Painéis individuais
    paineis_larguras_raw = dados.get('paineis_larguras', [])
    paineis_individuais = [float(x) for x in paineis_larguras_raw if float(x) > 0]

    if not paineis_individuais:
        # Criar painéis automáticos (máx 244cm)
        n = max(1, math.ceil(largura_total / 244))
        w = largura_total / n
        paineis_individuais = [w] * n
        paineis_individuais[-1] = largura_total - sum(paineis_individuais[:-1])

    n_paineis = len(paineis_individuais)

    # Posições acumuladas (= limites entre painéis)
    paineis_acum = []
    acc = 0
    for w in paineis_individuais:
        acc += w
        paineis_acum.append(acc)

    # Alturas por painel
    def get_list(key, default_val, n):
        lst = dados.get(key, None)
        if lst and isinstance(lst, list) and len(lst) >= n:
            return [soma_altura(x) for x in lst[:n]]
        return [default_val] * n

    alturas1       = get_list('paineis_alturas', altura_geral, n_paineis)
    alturas2       = get_list('paineis_alturas2', 0, n_paineis)
    tipo1_lst      = dados.get('paineis_tipo1', ['Sarrafeado'] * n_paineis)
    tipo2_lst      = dados.get('paineis_tipo2', ['Sarrafeado'] * n_paineis)
    grade_h1_lst   = get_list('paineis_grade_altura1', 7.0, n_paineis)
    grade_h2_lst   = get_list('paineis_grade_altura2', 7.0, n_paineis)
    lajes_sup_lst  = get_list('lajes_sup', 0, n_paineis)
    lajes_inf_lst  = get_list('lajes_inf', 0, n_paineis)
    lajes_cen_lst  = get_list('lajes_central_alt', 0, n_paineis)

    # Posição dos textos laterais
    h1_painel0 = alturas1[0] if alturas1 else altura_geral
    DESLOCAMENTO_Y = 80
    y_texto = Y_INICIAL - h1_painel0 + DESLOCAMENTO_Y

    x0 = X_INICIAL
    y0 = Y_INICIAL

    # ─── INÍCIO DO SCR ───────────────────────────────────────────
    script = f"""_ZOOM
C {x0+largura_total/2},{y0+altura_geral/2} 100
;
LAYER
S Painéis

;
; Linha lateral esquerda
_ZOOM
C {x0},{y0+altura_geral/2} 5
;
_PLINE
{x0},{y0}
{x0},{y0+altura_geral}

;
; Linha lateral direita
_ZOOM
C {x0+largura_total},{y0+altura_geral/2} 5
;
_PLINE
{x0+largura_total},{y0}
{x0+largura_total},{y0+altura_geral}

;
-LAYER
S 5

;
"""
    # Textos laterais (style standard)
    script += ";\n-style\nstandard\n\n0\n\n\n\n\n\n;\n"
    if texto_esq.strip():
        script += f"_ZOOM\nC {x0-5},{y_texto} 5\n;\n_TEXT\n{x0-5},{y_texto}\n8\n90\n{texto_esq}\n;\n"
    if texto_dir.strip():
        script += f"_ZOOM\nC {x0+largura_total+12},{y_texto} 5\n;\n_TEXT\n{x0+largura_total+12},{y_texto}\n8\n90\n{texto_dir}\n;\n"

    # Sarrafos verticais extremos (SARR_2.2x7, linhas verticais full-height)
    script += f"-LAYER\nS SARR_2.2x7\n\n;\n"
    script += f"""; Sarrafo Esquerdo
_ZOOM
C {x0+7},{y0+altura_geral/2} 5
;
_PLINE
{x0+7},{y0}
{x0+7},{y0+altura_geral}

;
; Sarrafo Direito
_ZOOM
C {x0+largura_total-7},{y0+altura_geral/2} 5
;
_PLINE
{x0+largura_total-7},{y0}
{x0+largura_total-7},{y0+altura_geral}

;
-LAYER
S Painéis

;
"""
    # Divisores verticais de painéis
    for i, pos in enumerate(paineis_acum):
        if pos > 0 and pos < largura_total:
            script += f"""; Linha Painel {i+1} (vertical)
_ZOOM
C {x0+pos},{y0+altura_geral/2} 5
;
_PLINE
{x0+pos},{y0}
{x0+pos},{y0+altura_geral}

;
"""
    script += f"-LAYER\nS Painéis\n\n;"

    # Linhas horizontais por painel (top + bottom)
    pos_prev = 0.0
    for i, (pw, pos) in enumerate(zip(paineis_individuais, paineis_acum)):
        script += f"""; Linha horizontal superior do Painel {i+1}
_ZOOM
C {x0+(pos_prev+pos)/2},{y0+altura_geral} 5
;
_PLINE
{x0+pos_prev},{y0+altura_geral}
{x0+pos},{y0+altura_geral}

;
; Linha horizontal inferior do Painel {i+1}
_ZOOM
C {x0+(pos_prev+pos)/2},{y0} 5
;
_PLINE
{x0+pos_prev},{y0}
{x0+pos},{y0}

;
"""
        pos_prev = pos

    # ─── POR PAINEL ─────────────────────────────────────────────
    x_painel = x0
    for i, pw in enumerate(paineis_individuais):
        h1_raw = dados.get('paineis_alturas', [altura_geral] * n_paineis)[i]
        h2_raw = dados.get('paineis_alturas2', ['0'] * n_paineis)[i]
        h1_partes = [float(p.strip()) for p in str(h1_raw).split('+') if p.strip()]
        h2_partes = [float(p.strip()) for p in str(h2_raw).split('+') if p.strip()]
        altura1 = sum(h1_partes) if h1_partes else 0.0
        altura2 = sum(h2_partes) if h2_partes else 0.0
        laje_sup = lajes_sup_lst[i]
        laje_inf = lajes_inf_lst[i]
        laje_central = lajes_cen_lst[i]
        tipo1 = tipo1_lst[i] if i < len(tipo1_lst) else 'Sarrafeado'
        tipo2 = tipo2_lst[i] if i < len(tipo2_lst) else 'Sarrafeado'
        grade_h1 = grade_h1_lst[i]
        grade_h2 = grade_h2_lst[i]

        script += f""";=====================================================================
; PAINEL {i+1}
; =====================================================================
; ===== PAINEL {i+1} ALTURA 1 =====
"""
        # Retângulo do painel (Altura 1)
        if altura1 > 0:
            y_base_a1 = y0
            y_topo_a1 = y0 + altura1
            script += f"""-LAYER
S Painéis

;
_ZOOM
C {(x_painel + x_painel+pw)/2},{(y_base_a1 + y_topo_a1)/2} 5
;
_PLINE
{x_painel},{y_base_a1}
{x_painel+pw},{y_base_a1}
{x_painel+pw},{y_topo_a1}
{x_painel},{y_topo_a1}
{x_painel},{y_base_a1}

;
"""
            # Linha extra divisão (N+N)
            if len(h1_partes) > 1:
                y_extra = y0 + h1_partes[0]
                script += f"""; Linha extra de divisão de Altura 1 (segmento)
_ZOOM
C {(x_painel+x_painel+pw)/2},{y_extra} 5
;
_PLINE
{x_painel},{y_extra}
{x_painel+pw},{y_extra}

;
"""
        script += f"""; ===== SARRAFOS/GRADES ALTURA 1 PAINEL {i+1} =====
"""
        # Sarrafos/Grade Altura 1
        if altura1 > 0:
            if tipo1 == 'Grade':
                # Grade: SARR_2.2x7 horizontal top + SARR_2.2x3.5 verticals
                altura_vert = grade_h1 - 2.2
                y_grade_top = y0 + altura1 - 2.2
                y_grade_bot = y_grade_top + 2.2  # = y0 + altura1
                x_grade_ini = x_painel + (15 if i == 0 else 0)
                x_grade_fim = x_painel + pw - (15 if i == n_paineis - 1 else 0)
                script += f"-LAYER\nS SARR_2.2x7\n\n;\n"
                script += f"_PLINE\n{x_grade_ini},{y_grade_top}\n{x_grade_fim},{y_grade_top}\n{x_grade_fim},{y_grade_bot}\n{x_grade_ini},{y_grade_bot}\nC\n;\n"
                script += f"-LAYER\nS SARR_2.2x3.5\n\n;\n"
                # Vertical esquerda
                script += f"_PLINE\n{x_grade_ini},{y_grade_bot-2.2}\n{x_grade_ini+3.5},{y_grade_bot-2.2}\n{x_grade_ini+3.5},{y_grade_bot-2.2-altura_vert}\n{x_grade_ini},{y_grade_bot-2.2-altura_vert}\nC\n;\n"
                # Vertical direita
                x_vert_dir = x_painel + pw - 3.5
                if i == n_paineis - 1:
                    x_vert_dir = x_painel + pw - 15 - 3.5
                script += f"_PLINE\n{x_vert_dir},{y_grade_bot-2.2}\n{x_vert_dir+3.5},{y_grade_bot-2.2}\n{x_vert_dir+3.5},{y_grade_bot-2.2-altura_vert}\n{x_vert_dir},{y_grade_bot-2.2-altura_vert}\nC\n;\n"
            else:
                # Sarrafeado: linhas horizontais
                layer_h, specs = get_sarrafo_specs(altura1)
                y_base_a1 = y0
                x_ini = x_painel + (7 if i == 0 else 0)
                x_fim = x_painel + pw - (7 if i == n_paineis - 1 else 0)
                for (tipo_offset, posicao) in specs:
                    yp = sarrafo_y(posicao, tipo_offset, y_base_a1, altura1)
                    script += f"-LAYER\nS {layer_h}\n\n;\n_ZOOM\nC {(x_ini+x_fim)/2},{yp} 5\n;\n_PLINE\n{x_ini},{yp}\n{x_fim},{yp}\n\n;\n"

        # Painel Altura 2
        script += f"""; ===== PAINEL {i+1} ALTURA 2 =====
"""
        if altura2 > 0:
            y_base_a2 = y0 + altura1 + laje_central
            y_topo_a2 = y_base_a2 + altura2
            script += f"""-LAYER
S Painéis

;
_ZOOM
C {(x_painel+x_painel+pw)/2},{(y_base_a2+y_topo_a2)/2} 5
;
_PLINE
{x_painel},{y_base_a2}
{x_painel+pw},{y_base_a2}
{x_painel+pw},{y_topo_a2}
{x_painel},{y_topo_a2}
{x_painel},{y_base_a2}

;
"""
            if len(h2_partes) > 1:
                y_extra2 = y_base_a2 + h2_partes[0]
                script += f"""; Linha extra de divisão de Altura 2 (segmento)
_ZOOM
C {(x_painel+x_painel+pw)/2},{y_extra2} 5
;
_PLINE
{x_painel},{y_extra2}
{x_painel+pw},{y_extra2}

;
"""
        else:
            script += "; Não há painel de Altura 2 neste painel\n"

        # Sarrafos Altura 2
        script += f"""; ===== SARRAFOS/GRADES ALTURA 2 PAINEL {i+1} =====
"""
        if altura2 > 0:
            if tipo2 == 'Grade':
                altura_vert2 = grade_h2 - 2.2
                y_base_a2 = y0 + altura1 + laje_central
                y_grade2_top = y_base_a2 + altura2 - 2.2
                y_grade2_bot = y_grade2_top + 2.2
                x_grade2_ini = x_painel + (15 if i == 0 else 0)
                x_grade2_fim = x_painel + pw - (15 if i == n_paineis - 1 else 0)
                script += f"-LAYER\nS SARR_2.2x7\n\n;\n"
                script += f"_PLINE\n{x_grade2_ini},{y_grade2_top}\n{x_grade2_fim},{y_grade2_top}\n{x_grade2_fim},{y_grade2_bot}\n{x_grade2_ini},{y_grade2_bot}\nC\n;\n"
                script += f"-LAYER\nS SARR_2.2x3.5\n\n;\n"
                script += f"_PLINE\n{x_grade2_ini},{y_grade2_bot-2.2}\n{x_grade2_ini+3.5},{y_grade2_bot-2.2}\n{x_grade2_ini+3.5},{y_grade2_bot-2.2-altura_vert2}\n{x_grade2_ini},{y_grade2_bot-2.2-altura_vert2}\nC\n;\n"
                x_vert2_dir = x_painel + pw - 3.5
                if i == n_paineis - 1:
                    x_vert2_dir = x_painel + pw - 15 - 3.5
                script += f"_PLINE\n{x_vert2_dir},{y_grade2_bot-2.2}\n{x_vert2_dir+3.5},{y_grade2_bot-2.2}\n{x_vert2_dir+3.5},{y_grade2_bot-2.2-altura_vert2}\n{x_vert2_dir},{y_grade2_bot-2.2-altura_vert2}\nC\n;\n"
            else:
                if altura2 > 0:
                    layer_h2, specs2 = get_sarrafo_specs(altura2)
                    y_base_a2 = y0 + altura1 + laje_central
                    x_ini2 = x_painel + (7 if i == 0 else 0)
                    x_fim2 = x_painel + pw - (7 if i == n_paineis - 1 else 0)
                    for (tipo_offset, posicao) in specs2:
                        yp = sarrafo_y(posicao, tipo_offset, y_base_a2, altura2)
                        script += f"-LAYER\nS {layer_h2}\n\n;\n_ZOOM\nC {(x_ini2+x_fim2)/2},{yp} 5\n;\n_PLINE\n{x_ini2},{yp}\n{x_fim2},{yp}\n\n;\n"
        else:
            script += "; Não há sarrafos de Altura 2 neste painel\n"

        # Lajes
        script += f"; ===== LAJES PAINEL {i+1} =====\n"
        if laje_sup > 0:
            y_laje_sup = y0 + altura1 + laje_central + altura2
            script += f"""; Laje Superior
-LAYER
S COTA

;
_ZOOM
C {(x_painel+x_painel+pw)/2},{y_laje_sup + laje_sup/2} 5
;
_PLINE
{x_painel},{y_laje_sup}
{x_painel+pw},{y_laje_sup}
{x_painel+pw},{y_laje_sup + laje_sup}
{x_painel},{y_laje_sup + laje_sup}
{x_painel},{y_laje_sup}

;
HHHH
{x_painel + pw/2},{y_laje_sup + laje_sup/2}
;
"""
        else:
            script += "; Não há laje superior neste painel\n"

        if laje_inf > 0:
            y_laje_inf = y0 - laje_inf
            script += f"""; Laje Inferior
-LAYER
S COTA

;
_PLINE
{x_painel},{y_laje_inf}
{x_painel+pw},{y_laje_inf}
{x_painel+pw},{y_laje_inf + laje_inf}
{x_painel},{y_laje_inf + laje_inf}
{x_painel},{y_laje_inf}

;
HHHH
{x_painel + pw/2},{y_laje_inf + laje_inf/2}
;
"""
        else:
            script += "; Não há laje inferior neste painel\n"

        if laje_central > 0:
            y_laje_central = y0 + altura1
            script += f"""; Laje Central
-LAYER
S COTA

;
_PLINE
{x_painel},{y_laje_central}
{x_painel+pw},{y_laje_central}
{x_painel+pw},{y_laje_central + laje_central}
{x_painel},{y_laje_central + laje_central}
{x_painel},{y_laje_central}

;
HHHH
{x_painel + pw/2},{y_laje_central + laje_central/2}
;
"""
        else:
            script += "; Não há laje central neste painel\n"

        x_painel += pw

    # ─── HOLES / ABERTURAS ───────────────────────────────────────
    holes = dados.get('holes', [])
    for hole in holes:
        if not hole.get('active', False):
            continue
        hpos  = float(hole.get('position', 0.0))
        hw    = float(hole.get('width',    0.0))
        hh    = float(hole.get('height',   0.0))
        hside = hole.get('side', 'ET')
        if hw <= 0 or hh <= 0:
            continue
        if hside == 'ET':
            x1h, x2h = x0, x0 + hw
            y1h, y2h = y0 + altura_geral - hpos - hh, y0 + altura_geral - hpos
        elif hside == 'EF':
            x1h, x2h = x0, x0 + hw
            y1h, y2h = y0 + hpos, y0 + hpos + hh
        elif hside == 'DT':
            x1h, x2h = x0 + largura_total - hw, x0 + largura_total
            y1h, y2h = y0 + altura_geral - hpos - hh, y0 + altura_geral - hpos
        else:  # DF
            x1h, x2h = x0 + largura_total - hw, x0 + largura_total
            y1h, y2h = y0 + hpos, y0 + hpos + hh
        script += f'-LAYER\nS COTA\n\n;\n'
        script += f'_PLINE\n{x1h},{y1h}\n{x2h},{y1h}\n{x2h},{y2h}\n{x1h},{y2h}\nC\n;\n'
        xmh = (x1h + x2h) / 2
        ymh = (y1h + y2h) / 2
        script += f'; Cotas abertura {hside}\n_DIMLINEAR\n{x1h},{y1h}\n{x2h},{y1h}\n{xmh},{y1h-8}\n;\n;\n'
        script += f'_DIMLINEAR\n{x1h},{y1h}\n{x1h},{y2h}\n{x1h-12},{ymh}\n;\n;\n'

    # ─── DETALHE PILAR (RECTANGLE) ───────────────────────────────
    det_esq = dados.get('detalhe_pilar_esq', [0.0, 0.0])
    det_dir = dados.get('detalhe_pilar_dir', [0.0, 0.0])
    if len(det_esq) >= 2 and float(det_esq[1]) > 0:
        dist_esq_p = float(det_esq[0])
        larg_esq_p = float(det_esq[1])
        h1_esq_p = alturas1[0] if alturas1 else altura_geral
        lc_esq_p = lajes_cen_lst[0] if lajes_cen_lst else 0
        h2_esq_p = alturas2[0] if alturas2 else 0
        xe1p = x0 + dist_esq_p
        xe2p = xe1p + larg_esq_p
        yp1  = y0
        yp2  = y0 + h1_esq_p + lc_esq_p + h2_esq_p
        script += f'-LAYER\nS COTA\n\n;\n'
        script += f'; Detalhe Pilar Esquerdo\nRECTANGLE\n{xe1p:.3f},{yp1:.3f}\n{xe2p:.3f},{yp2:.3f}\n;\n'
    if len(det_dir) >= 2 and float(det_dir[1]) > 0:
        dist_dir_p = float(det_dir[0])
        larg_dir_p = float(det_dir[1])
        h1_dir_p = alturas1[-1] if alturas1 else altura_geral
        lc_dir_p = lajes_cen_lst[-1] if lajes_cen_lst else 0
        h2_dir_p = alturas2[-1] if alturas2 else 0
        xe2p = x0 + largura_total - dist_dir_p
        xe1p = xe2p - larg_dir_p
        yp1  = y0
        yp2  = y0 + h1_dir_p + lc_dir_p + h2_dir_p
        script += f'-LAYER\nS COTA\n\n;\n'
        script += f'; Detalhe Pilar Direito\nRECTANGLE\n{xe1p:.3f},{yp1:.3f}\n{xe2p:.3f},{yp2:.3f}\n;\n'

    # ─── COTAS HORIZONTAIS ───────────────────────────────────────
    script += f"-LAYER\nS COTA\n\n;\n"
    maior_laje_inf = max([l for l in lajes_inf_lst if l > 0] or [0])
    y_cota_base = y0 - maior_laje_inf
    posicoes_paineis = [0.0] + [sum(paineis_individuais[:k+1]) for k in range(n_paineis)]
    for i in range(n_paineis):
        x_ini = x0 + posicoes_paineis[i]
        x_fim = x0 + posicoes_paineis[i+1]
        y_cota = y_cota_base - 20
        x_txt = (x_ini + x_fim) / 2
        script += f"; Cota horizontal painel {i+1}\n_DIMLINEAR\n{x_ini},{y_cota_base}\n{x_fim},{y_cota_base}\n{x_txt},{y_cota}\n;\n"
    # Cota total
    script += f"; Cota horizontal total\n_DIMLINEAR\n{x0},{y_cota_base}\n{x0+largura_total},{y_cota_base}\n{x0+largura_total/2},{y_cota_base-40}\n;\n"

    # ─── COTAS VERTICAIS (só se não for modo continuação) ────────
    continuacao_norm = continuacao.replace(' ', '').lower()
    eh_continuacao = continuacao_norm in ('obstaculo', 'vigacontinuacao')
    if not eh_continuacao:
        x_dir = x0 + largura_total
        for i in range(n_paineis):
            h1 = alturas1[i]
            h2 = alturas2[i]
            laje_inf = lajes_inf_lst[i]
            laje_cen = lajes_cen_lst[i]
            laje_sup = lajes_sup_lst[i]
            if h1 > 0:
                script += f"; Cota vertical painel {i+1} - Altura 1\n_DIMLINEAR\n{x_dir},{y0}\n{x_dir},{y0+h1}\n{x_dir+30},{(y0+y0+h1)/2}\n;\n"
            if h2 > 0:
                y2_ini = y0 + h1 + laje_cen
                y2_fim = y2_ini + h2
                script += f"; Cota vertical painel {i+1} - Altura 2\n_DIMLINEAR\n{x_dir},{y2_ini}\n{x_dir},{y2_fim}\n{x_dir+30},{(y2_ini+y2_fim)/2}\n;\n"
            if laje_inf > 0:
                script += f"; Cota vertical painel {i+1} - Laje Inferior\n_DIMLINEAR\n{x_dir},{y0-laje_inf}\n{x_dir},{y0}\n{x_dir+30},{y0-laje_inf/2}\n;\n"
            if laje_cen > 0:
                script += f"; Cota vertical painel {i+1} - Laje Central\n_DIMLINEAR\n{x_dir},{y0+h1}\n{x_dir},{y0+h1+laje_cen}\n{x_dir+30},{y0+h1+laje_cen/2}\n;\n"
            if laje_sup > 0:
                y_ls = y0 + h1 + laje_cen + h2
                script += f"; Cota vertical painel {i+1} - Laje Superior\n_DIMLINEAR\n{x_dir},{y_ls}\n{x_dir},{y_ls+laje_sup}\n{x_dir+30},{y_ls+laje_sup/2}\n;\n"

    # ─── NOMENCLATURA ────────────────────────────────────────────
    script += f"-LAYER\nS NOMENCLATURA\n\n;\n"
    y_nome = y0 + altura_geral + 8
    script += f"_ZOOM\nC {x0},{y_nome} 5\n;\n_TEXT\n{x0},{y_nome}\n16\n0\n{nome}\n;\n"
    script += f"; \"{continuacao}\"\n"

    return script


# ---------------------------------------------------------------------------
# Mapeamento JSON Fase-4 → dados do robô
# ---------------------------------------------------------------------------

def json_to_dados(jdata):
    """Converte nosso JSON Fase-4 LV para o formato dados do robô."""
    panels = jdata.get('panels', [])
    n = len(panels)

    largura_total = sum(float(p['width']) for p in panels)
    if largura_total == 0:
        largura_total = float(jdata.get('total_width', 0))

    # Laje central: pode ser global (jdata) ou por painel (panel.laje_central_alt)
    global_laje_cen_v = float(jdata.get('laje_central_alt', 0) or 0)
    lajes_cen_raw = [float(p.get('laje_central_alt', global_laje_cen_v) or 0) for p in panels]
    # Laje sup: pode ser global ou por painel
    global_laje_sup_v = float(jdata.get('laje_sup', 0) or 0)
    lajes_sup_raw = [float(p.get('laje_sup', global_laje_sup_v) or 0) for p in panels]

    paineis_larguras = [float(p['width']) for p in panels]
    paineis_alturas  = [str(p.get('height1', 0)) for p in panels]
    # height2: real apenas quando laje_central > 0 (evita usar cópia automática do height1)
    paineis_alturas2 = [
        str(p.get('height2', 0)) if lajes_cen_raw[i] > 0 else '0'
        for i, p in enumerate(panels)
    ]

    # Altura geral: max do total por painel (h1 + laje_central + h2 + laje_sup)
    per_panel_totals = []
    for i, p in enumerate(panels):
        h1 = soma_altura(str(p.get('height1', 0)))
        lc = lajes_cen_raw[i]
        h2 = soma_altura(str(p.get('height2', 0))) if lc > 0 else 0.0
        ls = lajes_sup_raw[i]
        per_panel_totals.append(h1 + lc + h2 + ls)
    if per_panel_totals and max(per_panel_totals) > 0:
        altura_geral = str(max(per_panel_totals))
    else:
        alt_raw = jdata.get('total_height', None)
        alt_raw = alt_raw if alt_raw is not None else max(
            (float(p.get('height1', 0)) for p in panels), default=0)
        altura_geral = str(alt_raw)

    # Grade vs sarrafeado (grade_h1 > 0 → Grade)
    def grade_type(val):
        try:
            return 'Grade' if float(val) > 0 else 'Sarrafeado'
        except Exception:
            return 'Sarrafeado'

    def grade_h(val):
        try:
            v = float(val)
            return v if v > 0 else 7.0
        except Exception:
            return 7.0

    paineis_tipo1       = [grade_type(p.get('grade_h1', 0)) for p in panels]
    paineis_tipo2       = [grade_type(p.get('grade_h2', 0)) for p in panels]
    paineis_grade_h1    = [grade_h(p.get('grade_h1', 7)) for p in panels]
    paineis_grade_h2    = [grade_h(p.get('grade_h2', 7)) for p in panels]

    # Lajes: lê do JSON se disponível
    lajes_sup = lajes_sup_raw
    lajes_inf = [float(p.get('laje_inf', 0) or 0) for p in panels]
    lajes_cen = lajes_cen_raw

    # Pilares
    pilar_labels = jdata.get('pilar_labels', [])
    texto_esq = pilar_labels[0] if pilar_labels else jdata.get('pillar_left', {}).get('label', '')
    texto_dir = pilar_labels[-1] if pilar_labels else jdata.get('pillar_right', {}).get('label', '')
    if not texto_esq:
        texto_esq = jdata.get('pilar_esq', jdata.get('name', ''))[:3]
    if not texto_dir:
        texto_dir = jdata.get('pilar_dir', jdata.get('name', ''))[:3]

    # ── Holes/Aberturas: mapeia para formato com side ──────────────────────
    sides = ['ET', 'EF', 'DT', 'DF']
    holes_raw_jdata = jdata.get('holes', [])
    holes = []
    for idx, h in enumerate(holes_raw_jdata[:4]):
        if h.get('active', False):
            holes.append({
                'active':   True,
                'side':     sides[idx],
                'position': float(h.get('position', 0.0)),
                'width':    float(h.get('width',    0.0)),
                'height':   float(h.get('height',   0.0)),
            })

    # ── Pilar detalhe (RECTANGLE no SCR) ───────────────────────────────────
    pl = jdata.get('pillar_left',  {})
    pr = jdata.get('pillar_right', {})
    detalhe_pilar_esq = [0.0, float(pl.get('width', 0) or 0)] if pl.get('active') else [0.0, 0.0]
    detalhe_pilar_dir = [0.0, float(pr.get('width', 0) or 0)] if pr.get('active') else [0.0, 0.0]

    return {
        'nome':                jdata.get('name', jdata.get('name', 'V?')),
        'numero':              jdata.get('number', ''),
        'largura':             largura_total,
        'altura_geral':        altura_geral,
        'paineis_larguras':    paineis_larguras,
        'paineis_alturas':     paineis_alturas,
        'paineis_alturas2':    paineis_alturas2,
        'paineis_tipo1':       paineis_tipo1,
        'paineis_tipo2':       paineis_tipo2,
        'paineis_grade_altura1': paineis_grade_h1,
        'paineis_grade_altura2': paineis_grade_h2,
        'lajes_sup':           lajes_sup,
        'lajes_inf':           lajes_inf,
        'lajes_central_alt':   lajes_cen,
        'texto_esq':           texto_esq,
        'texto_dir':           texto_dir,
        'continuacao':         jdata.get('continuacao', 'Viga'),
        'holes':               holes,
        'detalhe_pilar_esq':   detalhe_pilar_esq,
        'detalhe_pilar_dir':   detalhe_pilar_dir,
    }


def process_obra(obra_path: Path, out_dir: Path):
    """Processa todos os JSON LV de uma obra, gerando arquivos SCR."""
    json_dir = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Laterais'
    if not json_dir.exists():
        print(f"ERRO: {json_dir} nao existe")
        return 0

    jfiles = sorted(json_dir.glob('*.json'),
                    key=lambda p: (p.stem.split('_')[0], p.stem))
    if not jfiles:
        print(f"ERRO: Nenhum JSON em {json_dir}")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for jpath in jfiles:
        try:
            jdata = json.loads(jpath.read_text(encoding='utf-8', errors='replace'))
            dados = json_to_dados(jdata)
            scr_text = gerar_scr_lv(dados)
            # Cabeçalho compatível com Ordenador_VIGA
            largura = dados['largura']
            h = soma_altura(dados['altura_geral'])
            header = f"; (numeracao: {dados['numero'] or dados['nome']}, largura: {largura:.2f}, altura: {h:.2f}, continuacao: {dados['continuacao']})\n"
            scr_text = header + scr_text
            out_path = out_dir / f"{jpath.stem}.scr"
            out_path.write_text(scr_text, encoding='utf-16')
            print(f"  {jpath.stem}: w={largura:.0f}cm h={h:.0f}cm {len(jdata.get('panels',[]))} paineis")
            count += 1
        except Exception as e:
            import traceback
            print(f"  ERRO {jpath.name}: {e}")
            traceback.print_exc()
    return count


def main():
    parser = argparse.ArgumentParser(description='Gera SCR de laterais de viga a partir de JSON Fase-4')
    parser.add_argument('--obra', default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    parser.add_argument('--out', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    out_dir = Path(args.out) if args.out else \
        obra_path / 'Fase-5_Geracao_Scripts' / 'SCR_Vigas_Laterais'

    print(f"\n=== GERAR SCR VIGAS LATERAIS ===")
    print(f"  Obra : {obra_path.name}")
    print(f"  Out  : {out_dir}\n")

    count = process_obra(obra_path, out_dir)
    print(f"\n  Total: {count} arquivos SCR gerados")


if __name__ == '__main__':
    main()
