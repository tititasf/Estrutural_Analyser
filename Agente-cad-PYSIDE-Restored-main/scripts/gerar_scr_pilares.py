#!/usr/bin/env python3
"""
gerar_scr_pilares.py — Gera SCR AutoCAD para pilares a partir de JSON Fase-4
==============================================================================
Frente 1: SCR → AutoCAD = 100% fidelidade.

Gera 3 SCRs por pilar (mesmo formato do robô original):
  P{n}_CIMA.scr   — seção transversal
  P{n}_ABCD.scr   — painéis de fôrma (4 faces)
  P{n}_GRADES.scr  — grades com sarrafos e pontaletes

Uso:
  python scripts/gerar_scr_pilares.py --obra DADOS-OBRAS/Obra_TREINO_1 --pilar P11
  python scripts/gerar_scr_pilares.py --obra DADOS-OBRAS/Obra_TREINO_1 --all

Para executar no AutoCAD:
  1. Abrir MOLDE_PILARES ATUALIZADO2.dwg
  2. Digitar: FILEDIA 0 [Enter]
  3. Digitar: _SCRIPT [Enter]
  4. Digitar o path do SCR gerado [Enter]
"""
import sys, io, json, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path


def gerar_scr_cima(comp, larg, nome='P1'):
    """Gera SCR para vista CIMA (seção transversal) do pilar.
    comp/larg em cm (dimensões do concreto).
    """
    hc = comp / 2
    hl = larg / 2
    tc = 1.2   # chapa
    tm = 2.0   # madeira

    lines = []
    lines.append('FILEDIA')
    lines.append('0')

    # Usar layer hachura-chapa como layer inicial (existe no MOLDE template NOVA)
    lines.append('_LAYER')
    lines.append('S')
    lines.append('hachura-chapa')
    lines.append('')
    lines.append(';')

    # Zoom center
    lines.append('_ZOOM')
    lines.append(f'C 0,{larg/2:.1f} {max(comp,larg)*2}')
    lines.append(';')

    # Concreto core (PLINE fechada) — layer CONCRETO (ACI 251 no MOLDE)
    lines.append('_LAYER')
    lines.append('S')
    lines.append('CONCRETO')
    lines.append('')
    lines.append(';')
    lines.append('_PLINE')
    lines.append(f'{-hc:.1f},{-hl:.1f}')
    lines.append(f'{hc:.1f},{-hl:.1f}')
    lines.append(f'{hc:.1f},{hl:.1f}')
    lines.append(f'{-hc:.1f},{hl:.1f}')
    lines.append('C')
    lines.append(';')

    # Chapas (4 faces) — layer hachura-chapa (ACI 233 no MOLDE)
    lines.append('_LAYER')
    lines.append('S')
    lines.append('hachura-chapa')
    lines.append('')
    lines.append(';')
    # Face A (inferior)
    cx0 = -hc - tc
    for fy, fh in [(-hl-tc, tc), (hl, tc)]:  # A e C
        lines.append('_PLINE')
        lines.append(f'{cx0:.1f},{fy:.1f}')
        lines.append(f'{hc+tc:.1f},{fy:.1f}')
        lines.append(f'{hc+tc:.1f},{fy+fh:.1f}')
        lines.append(f'{cx0:.1f},{fy+fh:.1f}')
        lines.append('C')
        lines.append(';')
    for fx, fw in [(-hc-tc, tc), (hc, tc)]:  # B e D
        lines.append('_PLINE')
        lines.append(f'{fx:.1f},{-hl:.1f}')
        lines.append(f'{fx+fw:.1f},{-hl:.1f}')
        lines.append(f'{fx+fw:.1f},{hl:.1f}')
        lines.append(f'{fx:.1f},{hl:.1f}')
        lines.append('C')
        lines.append(';')

    # Madeira (4 faces externas)
    lines.append('_LAYER')
    lines.append('S')
    lines.append('Madeira')
    lines.append('')
    lines.append(';')
    ext = tc + tm
    for fy, fh in [(-hl-tc-tm, tm), (hl+tc, tm)]:
        lines.append('_PLINE')
        lines.append(f'{-hc-ext:.1f},{fy:.1f}')
        lines.append(f'{hc+ext:.1f},{fy:.1f}')
        lines.append(f'{hc+ext:.1f},{fy+fh:.1f}')
        lines.append(f'{-hc-ext:.1f},{fy+fh:.1f}')
        lines.append('C')
        lines.append(';')
    for fx, fw in [(-hc-tc-tm, tm), (hc+tc, tm)]:
        lines.append('_PLINE')
        lines.append(f'{fx:.1f},{-hl:.1f}')
        lines.append(f'{fx+fw:.1f},{-hl:.1f}')
        lines.append(f'{fx+fw:.1f},{hl:.1f}')
        lines.append(f'{fx:.1f},{hl:.1f}')
        lines.append('C')
        lines.append(';')

    # Perfis metalicos (gravatas) — layer Perfil Metalico (ACI 224 no MOLDE)
    lines.append('_LAYER')
    lines.append('S')
    lines.append('Perfil Metalico')
    lines.append('')
    lines.append(';')
    tp = 1.5
    gw = comp + 2*ext + 2*tp
    for gy in [-hl-tc-tm-tp, hl+tc+tm]:
        lines.append('_PLINE')
        lines.append(f'{-hc-ext-tp:.1f},{gy:.1f}')
        lines.append(f'{-hc-ext-tp+gw:.1f},{gy:.1f}')
        lines.append(f'{-hc-ext-tp+gw:.1f},{gy+tp:.1f}')
        lines.append(f'{-hc-ext-tp:.1f},{gy+tp:.1f}')
        lines.append('C')
        lines.append(';')

    # PONTALETE blocks (INSERT do bloco PONT do MOLDE — 15 entities)
    lines.append('_LAYER')
    lines.append('S')
    lines.append('PONTALETE')
    lines.append('')
    lines.append(';')
    pont_offset = ext + tp + 3
    for px, py in [
        (-hc-pont_offset, -hl-pont_offset),
        (hc+pont_offset-7, -hl-pont_offset),
        (-hc-pont_offset, hl+pont_offset-7),
        (hc+pont_offset-7, hl+pont_offset-7),
    ]:
        lines.append('_INSERT')
        lines.append('PONT')
        lines.append(f'{px:.1f},{py:.1f}')
        lines.append('1')   # X scale
        lines.append('1')   # Y scale
        lines.append('0')   # rotation
        lines.append(';')

    # Labels A/B/C/D — layer NOMENCLATURA (ACI 7 no MOLDE)
    lines.append('_LAYER')
    lines.append('S')
    lines.append('NOMENCLATURA')
    lines.append('')
    lines.append(';')
    offx = hc + ext + tp + 15
    offy = hl + ext + tp + 15
    for txt, x, y in [('A', 0, -offy), ('B', -offx, 0), ('C', 0, offy), ('D', offx, 0)]:
        lines.append('_TEXT')
        lines.append(f'{x:.1f},{y:.1f}')
        lines.append('5')
        lines.append('0')
        lines.append(txt)
        lines.append(';')

    # Nome do pilar — layer texto (ACI 7 no MOLDE)
    lines.append('_LAYER')
    lines.append('S')
    lines.append('texto')
    lines.append('')
    lines.append(';')
    lines.append('_TEXT')
    lines.append(f'0,{offy+10:.1f}')
    lines.append('8')
    lines.append('0')
    lines.append(f'{nome} ({comp:.0f}x{larg:.0f})')
    lines.append(';')

    # Cotas — dimstyle CIMA-NOVA-X2 (do MOLDE)
    lines.append('-DIMSTYLE')
    lines.append('restore')
    lines.append('CIMA-NOVA-X2')
    lines.append(';')
    lines.append('_LAYER')
    lines.append('S')
    lines.append('COTA')
    lines.append('')
    lines.append(';')
    # Cota horizontal (comprimento)
    lines.append('_DIMLINEAR')
    lines.append(f'{-hc:.1f},{-hl-ext-tp-5:.1f}')
    lines.append(f'{hc:.1f},{-hl-ext-tp-5:.1f}')
    lines.append(f'0,{-hl-ext-tp-15:.1f}')
    lines.append(';')
    # Cota vertical (largura)
    lines.append('_DIMLINEAR')
    lines.append(f'{hc+ext+tp+5:.1f},{-hl:.1f}')
    lines.append(f'{hc+ext+tp+5:.1f},{hl:.1f}')
    lines.append(f'{hc+ext+tp+15:.1f},0')
    lines.append(';')

    lines.append('_ZOOM')
    lines.append('E')
    lines.append(';')
    lines.append('FILEDIA')
    lines.append('1')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', required=True)
    parser.add_argument('--pilar', help='Nome do pilar (ex: P11)')
    parser.add_argument('--all', action='store_true', help='Todos os pilares')
    args = parser.parse_args()

    obra = Path(args.obra)
    json_dir = obra / 'Fase-4_Sincronizacao' / 'JSON_Pilares'
    out_dir = obra / 'Fase-6_Execucao_CAD' / 'SCR_Pilares'
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.pilar:
        files = [json_dir / f'{args.pilar}.json']
    elif args.all:
        files = sorted(json_dir.glob('P*.json'))
    else:
        files = sorted(json_dir.glob('P*.json'))[:5]

    for jf in files:
        if not jf.exists():
            print(f'  SKIP: {jf.name} nao encontrado')
            continue

        d = json.loads(jf.read_text(encoding='utf-8'))
        nome = jf.stem
        comp = float(d.get('comprimento', d.get('h', 0)))
        larg = float(d.get('largura', d.get('b', 0)))

        if comp <= 0 or larg <= 0:
            print(f'  SKIP: {nome} sem dimensoes (comp={comp}, larg={larg})')
            continue

        # Gerar CIMA SCR
        scr_cima = gerar_scr_cima(comp, larg, nome)
        scr_path = out_dir / f'{nome}_CIMA.scr'
        scr_path.write_text(scr_cima, encoding='ascii', errors='replace')
        print(f'  {nome}: {comp:.0f}x{larg:.0f}cm -> {scr_path.name} ({len(scr_cima.splitlines())} lines)')

    print(f'\nSCR salvos em: {out_dir}')
    print(f'Para executar no AutoCAD:')
    print(f'  1. Abrir template: MOLDE_PILARES ATUALIZADO2.dwg')
    print(f'  2. Command: FILEDIA 0')
    print(f'  3. Command: _SCRIPT')
    print(f'  4. Path: {out_dir / "P11_CIMA.scr"}')


if __name__ == '__main__':
    main()
