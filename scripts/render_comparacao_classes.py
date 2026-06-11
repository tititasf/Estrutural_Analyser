#!/usr/bin/env python3
"""
render_comparacao_classes.py — Renderiza comparação visual STOG Source vs LV Gerado.
Usa renderer direto (LINE/LWPOLYLINE/TEXT por bbox) — rápido para DXFs grandes.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json, argparse, re, math
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D


# ── Exemplos de classe para TREINO_11 ──────────────────────────────────────
EXEMPLOS = [
    # (viga, classe, campo, desc_curta)
    ('V402',  'MATCH',       'b',          'b=14cm: fwd=14 rev=14 Δ=0'),
    ('V402',  'AUSENTE_FWD', 'h',          'h: fwd=40 rev=128 (forma+laje vs estrutural)'),
    ('V506A', 'AUSENTE_REV', 'b',          'b: fwd=30 rev=0 (FV ausente no source)'),
    ('V506A', 'DELTA_SMALL', 'comprimento','comp: fwd=246 rev=233 Δ=13cm (5%)'),
    ('V402',  'REV_ONLY',    'comprimento','comp: fwd=None rev=247 (só no reverso)'),
]

PAV_LV_T11 = {
    '1PV': 'Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/NOVA-SCHWARTZ-GWT-1PV-LV-R00_R2018_ASCII_ODA.dxf',
    '2PV': 'Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/NOVA-SCHWARTZ-GWT-2PV-LV-R00_R2018_ASCII_ODA.dxf',
}
VIGA_PAV = {'V402': '1PV', 'V506A': '2PV', 'V506': '2PV'}

CLASS_COLOR = {
    'MATCH':        '#27ae60',
    'AUSENTE_FWD':  '#2980b9',
    'AUSENTE_REV':  '#c0392b',
    'DELTA_SMALL':  '#e67e22',
    'REV_ONLY':     '#8e44ad',
    'AUSENTE_AMBOS':'#7f8c8d',
}


def find_viga_center(dxf_path: str, viga_id: str):
    """Retorna (cx, cy) do centro das seções da viga no DXF."""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        pts = []
        for e in msp:
            if e.dxftype() not in ('TEXT', 'MTEXT'): continue
            lay = str(e.dxf.layer)
            if not (('Texto' in lay and 'Se' in lay) or lay == 'NOMENCLATURA'): continue
            try:
                txt = e.plain_text().strip() if e.dxftype() == 'MTEXT' else e.dxf.text.strip()
            except Exception:
                continue
            if re.search(rf'(?<![A-Z]){re.escape(viga_id)}[._][AB]', txt, re.IGNORECASE):
                pts.append((float(e.dxf.insert[0]), float(e.dxf.insert[1])))
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    except Exception as ex:
        print(f'  WARN {viga_id} in {Path(dxf_path).name}: {ex}')
    return None


def render_crop_fast(ax, dxf_path: str, cx: float, cy: float, half: float, title: str):
    """Renderiza crop direto (LINE + LWPOLYLINE + TEXT/MTEXT) sem Frontend completo."""
    x0, x1 = cx - half, cx + half
    y0, y1 = cy - half, cy + half

    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
    except Exception as ex:
        ax.set_title(f'{title}\nERRO leitura: {ex}', fontsize=7, color='red')
        ax.axis('off')
        return

    def in_box(x, y):
        return x0 <= x <= x1 and y0 <= y <= y1

    ax.set_facecolor('#1a1a2e')

    for e in msp:
        t = e.dxftype()
        try:
            if t == 'LINE':
                sx, sy = float(e.dxf.start[0]), float(e.dxf.start[1])
                ex_, ey = float(e.dxf.end[0]),   float(e.dxf.end[1])
                if not (in_box(sx, sy) or in_box(ex_, ey)):
                    continue
                color = '#4ecdc4' if str(e.dxf.layer) == 'COTA' else '#aecbf7'
                ax.plot([sx, ex_], [sy, ey], color=color, lw=0.5, solid_capstyle='round')

            elif t == 'LWPOLYLINE':
                pts = [(p[0], p[1]) for p in e.get_points()]
                if not pts: continue
                cx_ = sum(p[0] for p in pts) / len(pts)
                cy_ = sum(p[1] for p in pts) / len(pts)
                if not in_box(cx_, cy_): continue
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if e.is_closed:
                    xs.append(xs[0]); ys.append(ys[0])
                lay = str(e.dxf.layer)
                color = '#f9ca24' if 'Pain' in lay else '#aecbf7'
                ax.plot(xs, ys, color=color, lw=0.6)

            elif t in ('TEXT', 'MTEXT'):
                ix, iy = float(e.dxf.insert[0]), float(e.dxf.insert[1])
                if not in_box(ix, iy): continue
                try:
                    txt = e.plain_text().strip() if t == 'MTEXT' else e.dxf.text.strip()
                except Exception:
                    continue
                if not txt or len(txt) > 80: continue
                lay = str(e.dxf.layer)
                color = '#ff6b6b' if lay == 'NOMENCLATURA' else '#ffeaa7'
                size = 6 if lay == 'NOMENCLATURA' else 5
                ax.text(ix, iy, txt, fontsize=size, color=color,
                        ha='left', va='bottom', clip_on=True)

            elif t == 'DIMENSION':
                try:
                    dp  = (float(e.dxf.defpoint[0]),  float(e.dxf.defpoint[1]))
                    dp2 = (float(e.dxf.defpoint2[0]), float(e.dxf.defpoint2[1]))
                    if not (in_box(*dp) or in_box(*dp2)): continue
                    ax.plot([dp[0], dp2[0]], [dp[1], dp2[1]],
                            color='#a29bfe', lw=0.4, ls='--')
                    try:
                        v = e.dxf.actual_measurement
                        if v:
                            mx = (dp[0] + dp2[0]) / 2
                            my = (dp[1] + dp2[1]) / 2
                            ax.text(mx, my, f'{v:.0f}', fontsize=4, color='#a29bfe',
                                    ha='center', va='center', clip_on=True)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            continue

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=7, color='white', pad=4, loc='center')
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra', default='DADOS-OBRAS/Obra_TREINO_11')
    parser.add_argument('--half', type=float, default=1200,
                        help='Metade do tamanho do crop em unidades DXF (default 1200)')
    parser.add_argument('--output', default=None)
    args = parser.parse_args()

    obra_dir = Path(args.obra)
    out_path = Path(args.output) if args.output else \
               obra_dir / 'Fase-8_Revisao_Entrega/comparacao_classes.png'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    gerado_dxf = str(obra_dir / 'Fase-6_Execucao_CAD/LV_gerado.dxf')

    n = len(EXEMPLOS)
    fig, axes = plt.subplots(n, 2, figsize=(16, n * 4.5))
    fig.patch.set_facecolor('#0d0d1a')
    fig.suptitle(f'Comparação LV: STOG Source vs Gerado  —  {obra_dir.name}',
                 fontsize=12, color='white', y=1.005)

    HALF = args.half

    for i, (viga, cls, campo, desc) in enumerate(EXEMPLOS):
        ax_src = axes[i][0]
        ax_gen = axes[i][1]
        color = CLASS_COLOR.get(cls, '#888')
        ax_src.set_facecolor('#1a1a2e')
        ax_gen.set_facecolor('#1a1a2e')

        # Borda colorida
        for ax in (ax_src, ax_gen):
            for spine in ax.spines.values():
                spine.set_edgecolor(color)
                spine.set_linewidth(2.5)
                spine.set_visible(True)

        # Rótulo da classe
        lbl = f'{cls}\n{viga}.{campo}'
        ax_src.set_ylabel(lbl, fontsize=8, color=color, rotation=0,
                          labelpad=110, va='center', fontweight='bold')

        # ── Source DXF ─────────────────────────────────────────────────
        pav = VIGA_PAV.get(viga, '1PV')
        src_rel = PAV_LV_T11.get(pav)
        if src_rel:
            src_path = str(obra_dir / src_rel)
            print(f'  [{i+1}/{n}] {cls} {viga} — source {pav}...')
            ctr = find_viga_center(src_path, viga)
            if ctr:
                render_crop_fast(ax_src, src_path, ctr[0], ctr[1], HALF,
                                 f'SOURCE  {pav}-LV   {viga}   {desc}')
            else:
                ax_src.set_title(f'SOURCE {pav}: {viga} nao localizado', color='white', fontsize=8)
        else:
            ax_src.set_title('SOURCE: pavimento nao mapeado', color='white', fontsize=8)

        # ── Gerado DXF ─────────────────────────────────────────────────
        print(f'  [{i+1}/{n}] {cls} {viga} — gerado...')
        ctr_gen = find_viga_center(gerado_dxf, viga)
        if ctr_gen:
            render_crop_fast(ax_gen, gerado_dxf, ctr_gen[0], ctr_gen[1], HALF,
                             f'GERADO         {viga}   {desc}')
        else:
            ax_gen.set_title(f'GERADO: {viga} nao encontrado', color='white', fontsize=8)
            ax_gen.set_facecolor('#1a1a2e')

    plt.tight_layout(rect=[0, 0, 1, 1])
    fig.savefig(str(out_path), dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    print(f'\nSalvo em: {out_path}')


if __name__ == '__main__':
    main()
