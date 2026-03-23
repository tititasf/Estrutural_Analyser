#!/usr/bin/env python3
"""
json_to_scr_fv.py
Gera SCR no formato do Robô FV (Robo_fundos_TASF_limpo_copy_22.py)
a partir dos JSONs Fase-4 de vigas fundo.

Replica EXATAMENTE a lógica de gerar_script() do robot:
  - Borda esquerda (Painéis)
  - Texto nome/obs (NOMENCLATURA)
  - Labels pilar esq/dir (layer "5", rot=90)
  - Sarrafos verticais externos (SARR_2.2x7, at x+7 e x+largura-7)
  - Linhas horizontais top/bottom por painel (Painéis)
  - Cotas por painel + total + altura (COTA)
  - Divisores verticais entre painéis + parede direita
  - Sarrafos horizontais internos (SARR_2.2x7 ou SARR_2.2x5)
"""
import json
from pathlib import Path

X_INICIAL = 0.0
Y_INICIAL = 0.0


# ---------------------------------------------------------------------------
# Funções que replicam o robot
# ---------------------------------------------------------------------------

def get_linha_specs(altura):
    """Replica get_linha_specs do Robo_fundos_TASF."""
    h = float(altura)
    if h <= 14.0:
        return 'SARR_2.2x5', [(5.0, 'baixo'), (5.0, 'cima')]
    elif h < 40.0:
        return 'SARR_2.2x7', [(7.0, 'baixo'), (7.0, 'cima')]
    elif h < 80.0:
        return 'SARR_2.2x7', [(7.0, 'baixo'), (7.0, 'cima'),
                               (3.5, 'centro_cima'), (3.5, 'centro_baixo')]
    else:
        return 'SARR_2.2x7', [(7.0, 'baixo'), (7.0, 'cima'),
                               (3.5, 'centro_cima'), (3.5, 'centro_baixo'),
                               (3.5, 'quarto_inf_cima'), (3.5, 'quarto_inf_baixo'),
                               (3.5, 'quarto_sup_cima'), (3.5, 'quarto_sup_baixo')]


def calcular_y(pos_spec, altura):
    """Replica calcular_y do robot."""
    tipo, posicao = pos_spec
    h = float(altura)
    t = float(tipo)
    if h <= 14.0:
        return 5.0 if posicao == 'baixo' else h - 5.0
    if posicao == 'baixo':          return 7.0
    elif posicao == 'cima':         return h - 7.0
    elif posicao == 'centro_cima':  return h / 2.0 + t
    elif posicao == 'centro_baixo': return h / 2.0 - t
    elif posicao == 'quarto_inf_cima':  return h / 4.0 + t
    elif posicao == 'quarto_inf_baixo': return h / 4.0 - t
    elif posicao == 'quarto_sup_cima':  return 3.0 * h / 4.0 + t
    elif posicao == 'quarto_sup_baixo': return 3.0 * h / 4.0 - t
    return 0.0


def gerar_scr_fv(dados):
    """
    Gera texto SCR para a face de fundo de uma viga.

    dados: dict com campos:
      nome          - nome da viga
      obs           - observações (pode ser '')
      texto_esquerda - label pilar esquerdo
      texto_direita  - label pilar direito
      largura       - comprimento total (cm)
      altura        - espessura da viga / profundidade do fundo (cm)
      paineis       - lista de larguras de painéis [w1, w2, ...] (float, > 0)
      sarrafo_esq   - bool (True = desenhar sarrafo vertical esq)
      sarrafo_dir   - bool (True = desenhar sarrafo vertical dir)
      chanfro_esq_w - float: recuo horizontal no lado esquerdo (0=sem chanfro)
      chanfro_esq_h - float: altura vertical onde o chanfro esq termina (0=sem)
      chanfro_dir_w - float: recuo horizontal no lado direito
      chanfro_dir_h - float: altura do chanfro direito
      holes         - list[dict] com {active, position, width, height, side}
                      side: 'ET'=esq-topo, 'EF'=esq-fundo, 'DT'=dir-topo, 'DF'=dir-fundo
    """
    x0 = X_INICIAL
    y0 = Y_INICIAL
    largura = float(dados['largura'])
    altura  = float(dados['altura'])
    nome       = dados.get('nome', 'SemNome')
    obs        = dados.get('obs', '')
    texto_esq  = dados.get('texto_esquerda', '')
    texto_dir  = dados.get('texto_direita', '')
    sarrafo_esq = dados.get('sarrafo_esq', True)
    sarrafo_dir = dados.get('sarrafo_dir', True)
    paineis = [float(p) for p in dados['paineis'] if float(p) > 0]

    # Chanfros (recuos de pilar)
    cew = float(dados.get('chanfro_esq_w', 0.0))   # recuo horizontal esq
    ceh = float(dados.get('chanfro_esq_h', 0.0))   # altura do chanfro esq
    cdw = float(dados.get('chanfro_dir_w', 0.0))   # recuo horizontal dir
    cdh = float(dados.get('chanfro_dir_h', 0.0))   # altura do chanfro dir

    # Aberturas/holes
    holes = dados.get('holes', [])

    lines = []
    W = lines.append

    # ---- Zoom inicial ----
    W(f'ZOOM\nC\n{x0},{y0+altura/2.0}\n5\n;')

    # ---- Borda esquerda (Painéis) ----
    W(f'-LAYER\nS Painéis\n\n;')
    if cew > 0 and ceh > 0:
        # Chanfro esq: diagonal de (x0+cew, y0) a (x0, y0+ceh), depois vertical até topo
        W(f'_PLINE\n{x0+cew},{y0}\n{x0},{y0+ceh}\n{x0},{y0+altura}\n\n;')
    else:
        W(f'_PLINE\n{x0},{y0}\n{x0},{y0+altura}\n\n;')

    # ---- Texto nome/obs (NOMENCLATURA) ----
    W(f'-LAYER\nS NOMENCLATURA\n\n;')
    W(f'-STYLE\nStandard\n\n0\n\n\n\n\n\n;')
    W(f'_TEXT\n{x0},{y0+altura+8.0}\n12\n0\n{nome}\n;')
    W(f'_TEXT\n{x0+50.0},{y0+altura+8.0}\n12\n0\n{obs}\n;')

    # ---- Labels pilar (layer "5") ----
    W(f'-LAYER\nS 5\n\n;')
    W(f'_TEXT\n{x0-5.0},{y0-45.0}\n8\n90\n{texto_esq}\n;')
    W(f'_TEXT\n{x0+largura+12.0},{y0-45.0}\n8\n90\n{texto_dir}\n;')

    # ---- Sarrafos verticais externos (SARR_2.2x7) ----
    W(f'-LAYER\nS SARR_2.2x7\n\n;')
    W(f'ZOOM\nC\n{x0+largura/2.0},{y0+altura/2.0}\n5\n;')

    # Ajustar posição X do sarrafo esq quando há chanfro
    sarr_esq_x = x0 + max(7.0, cew + 7.0) if cew > 0 else x0 + 7.0
    sarr_dir_x = x0 + largura - max(7.0, cdw + 7.0) if cdw > 0 else x0 + largura - 7.0

    if sarrafo_esq:
        W(f'_PLINE\n{sarr_esq_x},{y0}\n{sarr_esq_x},{y0+altura}\n\n;')
    if sarrafo_dir:
        W(f'_PLINE\n{sarr_dir_x},{y0}\n{sarr_dir_x},{y0+altura}\n\n;')

    # ---- Linhas horizontais top/bottom (Painéis) + Cotas ----
    W(f'-LAYER\nS Painéis\n\n;')

    # Posições acumuladas dos painéis
    posicoes_acumuladas = []   # posição X do fim de cada painel
    x_cur = x0
    for pw in paineis:
        x_cur += pw
        posicoes_acumuladas.append(x_cur)

    # Linhas horizontais por painel
    x_cur = x0
    for i, pw in enumerate(paineis):
        x_end = posicoes_acumuladas[i]
        W(f'_PLINE\n{x_cur},{y0+altura}\n{x_end},{y0+altura}\n\n;')
        W(f'_PLINE\n{x_cur},{y0}\n{x_end},{y0}\n\n;')
        x_cur = x_end

    # ---- Cotas (COTA) ----
    W(f'-LAYER\nS COTA\n\n;')

    if len(paineis) == 1:
        # 1 painel: cota total com ponto médio
        x_mid = x0 + paineis[0] / 2.0
        W(f'_DIMLINEAR\n{x0},{y0}\n{x0+paineis[0]},{y0}\n{x_mid},{y0-45}\n;\n;')
    else:
        # Cota do primeiro painel
        x_cur = x0
        x_end_0 = posicoes_acumuladas[0]
        # Robot usa: pos_0/2 + recuo_fundo_esq = x_end_0/2 quase
        W(f'_DIMLINEAR\n{x_cur},{y0}\n{x_end_0},{y0}\n{x_end_0/2.0},{y0-20}\n;\n;')

        # Cotas painéis intermediários (i=1 até n-2)
        for i in range(1, len(posicoes_acumuladas) - 1):
            x_ant = posicoes_acumuladas[i-1]
            x_now = posicoes_acumuladas[i]
            x_mid = (x_ant + x_now) / 2.0
            W(f'_DIMLINEAR\n{x_ant},{y0}\n{x_now},{y0}\n{x_mid},{y0-20}\n;\n;')

        # Último painel
        if len(paineis) > 1:
            x_ant = posicoes_acumuladas[-2]
            x_now = posicoes_acumuladas[-1]
            x_mid = (x_ant + x_now) / 2.0
            W(f'_DIMLINEAR\n{x_ant},{y0}\n{x_now},{y0}\n{x_mid},{y0-20}\n;\n;')

        # Cota total
        x_mid_total = x0 + largura / 2.0
        W(f'_DIMLINEAR\n{x0},{y0}\n{x0+largura},{y0}\n{x_mid_total},{y0-45}\n;\n;')

    # Cota de espessura (vertical, à direita)
    W(f'_DIMLINEAR\n{x0+largura},{y0}\n{x0+largura},{y0+altura}\n{x0+largura+30},{y0+altura/2.0+5}\n;\n;')

    # ---- Divisores verticais entre painéis + parede direita ----
    # Replica o loop de posicoes_verticais do robot
    # posicoes_verticais = [x_ini, x_ini+p1, x_ini+p1+p2, ...] (itera de 1 em diante)
    layer_sarr, _ = get_linha_specs(altura)
    W(f'-LAYER\nS {layer_sarr}\n\n;')

    # Posições verticais (divisores internos, robot: posicoes_verticais[1:])
    x_cur = x0
    for pw in paineis[:-1]:   # todos exceto o último (não gera linha após o último painel)
        x_cur += pw
        W(f'-LAYER\nS Painéis\n\n;')
        W(f'_PLINE\n{x_cur},{y0}\n{x_cur},{y0+altura}\n\n;')
        W(f'-LAYER\nS {layer_sarr}\n\n;')

    # Parede direita (com suporte a chanfro dir)
    W(f'-LAYER\nS Painéis\n\n;')
    if cdw > 0 and cdh > 0:
        W(f'_PLINE\n{x0+largura},{y0}\n{x0+largura},{y0+cdh}\n{x0+largura-cdw},{y0+altura}\n\n;')
    else:
        W(f'_PLINE\n{x0+largura},{y0}\n{x0+largura},{y0+altura}\n\n;')
    W(f'-LAYER\nS {layer_sarr}\n\n;')

    # ---- Sarrafos horizontais internos ----
    W(f'-LINETYPE\nS\ncontinuous\n\n;')
    W(f'ZOOM\nC\n{x0+largura/2.0},{y0+altura/2.0}\n5\n;')

    for pos_spec in get_linha_specs(altura)[1]:
        y_pos = calcular_y(pos_spec, altura)
        # Posições acumuladas para os sarrafos (igual robot)
        posicoes_sarrafos = posicoes_acumuladas  # mesma lista

        for i in range(len(paineis)):
            if i == 0:
                # Primeiro painel: considera chanfro esq
                x_inicio = x0 + max(7.0, cew + 7.0) + 14.0 if cew > 0 else x0 + 7.0 + 14.0
                x_fim    = posicoes_sarrafos[i]
            elif i == len(paineis) - 1:
                # Último painel: considera chanfro dir
                x_inicio = posicoes_sarrafos[i-1] + 14.0
                x_fim    = posicoes_sarrafos[i] - max(7.0, cdw + 7.0) if cdw > 0 else posicoes_sarrafos[i] - 7.0
            else:
                # Painel intermediário
                x_inicio = posicoes_sarrafos[i-1] + 14.0
                x_fim    = posicoes_sarrafos[i]

            if x_fim > x_inicio:
                W(f'_PLINE\n{x_inicio},{y0+y_pos}\n{x_fim},{y0+y_pos}\n\n;')

    # ---- Aberturas / Holes ----
    # Posições dos holes: ET=esq-topo, EF=esq-fundo, DT=dir-topo, DF=dir-fundo
    for hole in holes:
        if not hole.get('active', False):
            continue
        hpos  = float(hole.get('position', 0.0))   # distância da borda
        hw    = float(hole.get('width',    0.0))    # largura da abertura
        hh    = float(hole.get('height',   0.0))    # profundidade da abertura
        hside = hole.get('side', 'ET')              # ET EF DT DF
        if hw <= 0 or hh <= 0:
            continue

        W(f'-LAYER\nS Painéis\n\n;')
        if hside == 'ET':   # esquerda-topo
            x1, x2 = x0 + hpos, x0 + hpos + hw
            y1, y2 = y0 + altura - hh, y0 + altura
        elif hside == 'EF':  # esquerda-fundo
            x1, x2 = x0 + hpos, x0 + hpos + hw
            y1, y2 = y0, y0 + hh
        elif hside == 'DT':  # direita-topo
            x1, x2 = x0 + largura - hpos - hw, x0 + largura - hpos
            y1, y2 = y0 + altura - hh, y0 + altura
        else:                # DF: direita-fundo
            x1, x2 = x0 + largura - hpos - hw, x0 + largura - hpos
            y1, y2 = y0, y0 + hh

        # Retângulo da abertura (linha tracejada em layer COTA para visibilidade)
        W(f'-LAYER\nS COTA\n\n;')
        W(f'_PLINE\n{x1},{y1}\n{x2},{y1}\n{x2},{y2}\n{x1},{y2}\nC\n;')
        # Cotas da abertura
        xm = (x1 + x2) / 2
        ym = (y1 + y2) / 2
        W(f'_DIMLINEAR\n{x1},{y1}\n{x2},{y1}\n{xm},{y1-8}\n;\n;')
        W(f'_DIMLINEAR\n{x1},{y1}\n{x1},{y2}\n{x1-12},{ym}\n;\n;')

    return '\n'.join(lines)


def json_to_dados_fv(jdata):
    """
    Mapeia JSON Fase-4 FV → dados para gerar_scr_fv().

    Campos do JSON:
      panels[i].width    → larguras de painel
      total_width        → espessura (altura no robot)
      name               → nome
      pilar_labels       → lista de labels (opcional)
      pillar_left        → {active, width, length}  → chanfro esq
      pillar_right       → {active, width, length}  → chanfro dir
      holes              → [{active, width, height, position}, ...]
                           holes[0]=ET, [1]=EF, [2]=DT, [3]=DF
    """
    panels = jdata.get('panels', [])
    panel_widths = [float(p['width']) for p in panels if float(p.get('width', 0)) > 0]
    largura = sum(panel_widths)
    altura  = float(jdata.get('total_width', 15.0))
    nome    = jdata.get('name', 'SemNome')

    # Pilar labels (esq = primeiro, dir = último)
    pilar_labels = jdata.get('pilar_labels', [])
    texto_esq = pilar_labels[0]  if pilar_labels else ''
    texto_dir = pilar_labels[-1] if pilar_labels else ''

    # Chanfros de pilar
    pl = jdata.get('pillar_left', {})
    pr = jdata.get('pillar_right', {})
    cew = float(pl.get('width', 0.0))  if pl.get('active', False) else 0.0
    ceh = float(pl.get('length', 0.0)) if pl.get('active', False) else 0.0
    cdw = float(pr.get('width', 0.0))  if pr.get('active', False) else 0.0
    cdh = float(pr.get('length', 0.0)) if pr.get('active', False) else 0.0

    # Aberturas: holes[0]=ET, [1]=EF, [2]=DT, [3]=DF
    sides = ['ET', 'EF', 'DT', 'DF']
    holes_raw = jdata.get('holes', [])
    holes = []
    for idx, h in enumerate(holes_raw[:4]):
        if h.get('active', False):
            holes.append({
                'active':   True,
                'side':     sides[idx] if idx < len(sides) else 'ET',
                'position': float(h.get('position', 0.0)),
                'width':    float(h.get('width',    0.0)),
                'height':   float(h.get('height',   0.0)),
            })

    return {
        'nome':           nome,
        'obs':            '',
        'texto_esquerda': texto_esq,
        'texto_direita':  texto_dir,
        'largura':        largura,
        'altura':         altura,
        'paineis':        panel_widths,
        'sarrafo_esq':    True,
        'sarrafo_dir':    True,
        'chanfro_esq_w':  cew,
        'chanfro_esq_h':  ceh,
        'chanfro_dir_w':  cdw,
        'chanfro_dir_h':  cdh,
        'holes':          holes,
    }


# ---------------------------------------------------------------------------
# CLI standalone — gera SCRs individuais
# ---------------------------------------------------------------------------
def main():
    import argparse, sys
    parser = argparse.ArgumentParser(description='Gera SCR de vigas fundo a partir de JSON Fase-4')
    parser.add_argument('--obra', default='D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1')
    parser.add_argument('--out-dir', default=None)
    args = parser.parse_args()

    obra_path = Path(args.obra)
    json_dir  = obra_path / 'Fase-4_Sincronizacao' / 'JSON_Vigas_Fundo'
    out_dir   = Path(args.out_dir) if args.out_dir else \
                obra_path / 'Fase-5_Geracao_Scripts' / 'SCR_Vigas_Fundo'
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(json_dir.glob('V*_fundo.json'),
                   key=lambda p: int(''.join(filter(str.isdigit, p.stem.split('_')[0]))))
    if not files:
        print(f'ERRO: nenhum V*_fundo.json em {json_dir}')
        sys.exit(1)

    print(f'\n=== JSON -> SCR FV ===')
    print(f'  JSON : {json_dir}')
    print(f'  OUT  : {out_dir}')
    print(f'  Files: {len(files)}\n')

    ok = 0
    for jpath in files:
        try:
            jdata = json.loads(jpath.read_text(encoding='utf-8'))
            dados = json_to_dados_fv(jdata)
            scr   = gerar_scr_fv(dados)
            stem  = jpath.stem.replace('_fundo', '')
            out   = out_dir / f'{stem}.scr'
            out.write_text(scr, encoding='utf-8')
            ok += 1
            print(f'  {stem}: largura={dados["largura"]:.0f}cm espessura={dados["altura"]:.0f}cm '
                  f'{len(dados["paineis"])} painéis')
        except Exception as e:
            print(f'  ERRO {jpath.stem}: {e}')

    print(f'\n  {ok}/{len(files)} SCRs gerados -> {out_dir}')


if __name__ == '__main__':
    main()
