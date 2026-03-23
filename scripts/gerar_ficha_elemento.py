"""
Gerador de Ficha Técnica Completa — CAD-ANALYZER v2.0
Ficha profissional com: seção transversal, vizinhança, confidence map,
DXF layer inventory, issues, múltiplos exemplos comparativos.

Uso:
    python gerar_ficha_elemento.py --obra Obra_TREINO_1 --tipo pilar --nome P11
    python gerar_ficha_elemento.py --todos
    python gerar_ficha_elemento.py --todos --obra Obra_TREINO_1
"""
import sys, os, argparse, json, re, math, sqlite3
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False
    print("ERRO: pip install ezdxf"); sys.exit(1)

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyArrowPatch, Rectangle, Polygon as MplPoly
    from matplotlib.gridspec import GridSpec
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, HRFlowable, KeepTogether, PageBreak
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    HAS_RL = True
except ImportError:
    HAS_RL = False
    print("AVISO: pip install reportlab")

DB_PATH   = Path(__file__).parent.parent / 'project_data.vision'
DADOS_DIR = Path(__file__).parent.parent / 'DADOS-OBRAS'
OUT_DIR   = Path(__file__).parent.parent / 'docs' / 'fichas' / 'elementos'

# ── Cores tema ────────────────────────────────────────────────────────────────
DARK_BG   = '#0d1117'
DARK_CARD = '#161b22'
DARK_LINE = '#21262d'
CYAN      = '#58a6ff'
YELLOW    = '#e3b341'
GREEN     = '#3fb950'
RED       = '#f85149'
ORANGE    = '#d29922'
PURPLE    = '#a371f7'
GRAY      = '#8b949e'
WHITE     = '#e6edf3'

LAYER_COLOR_MAP = {
    'paineis':        ('#58a6ff', 'Painéis de forma (retangulares)'),
    'texto secao':    ('#e3b341', 'Textos de seção (P11.A, V101_A...)'),
    'cota secao':     ('#ff9f43', 'Cotas de dimensão (B=46cm H=56cm)'),
    'nomenclatura':   ('#3fb950', 'Nome do elemento (TÉRREO - P11)'),
    'sarrafos':       ('#a8d8a8', 'Sarrafos de madeira'),
    'garfos':         ('#f85149', 'Garfos metálicos'),
    'contorno':       ('#79c0ff', 'Contorno/planta (lajes)'),
    'fundo':          ('#58a6ff', 'Fundo da forma'),
    'lateral':        ('#79c0ff', 'Face lateral'),
    '0':              ('#586069', 'Layer padrão'),
}

# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn():
    return sqlite3.connect(str(DB_PATH))


def carregar_pilar(obra: str, nome: str) -> dict:
    conn = _conn()
    r = conn.execute('''
        SELECT pl.name, pl.type, pl.area, pl.points_json, pl.sides_data_json,
               pl.links_json, pl.conf_map_json, pl.issues_json,
               pl.validated_fields_json, p.name as pav, p.dxf_path
        FROM pillars pl JOIN projects p ON pl.project_id=p.id
        WHERE p.work_name=? AND pl.name=? LIMIT 1
    ''', (obra, nome)).fetchone()
    conn.close()
    if not r: return {}
    lk = json.loads(r[5] or '{}')
    cf = json.loads(r[6] or '{}')
    pts = json.loads(r[3] or '[]')

    # Extrair dim
    dim_txt = ''
    if lk.get('dim', {}).get('label'):
        dim_txt = lk['dim']['label'][0].get('text', '')
    if not dim_txt and r[1]:
        dim_txt = r[1]

    # Calcular B e H reais da geometria
    b_mm = h_mm = 0.0
    if pts and len(pts) >= 2:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        b_mm = round(max(xs) - min(xs), 1)
        h_mm = round(max(ys) - min(ys), 1)

    return {
        'nome': r[0], 'tipo': r[1] or 'Pilar', 'area': r[2] or 0,
        'pontos': pts,
        'b_mm': b_mm, 'h_mm': h_mm,
        'sides': json.loads(r[4] or '{}'),
        'links': lk,
        'conf_map': cf,
        'issues': json.loads(r[7] or '[]'),
        'validated': json.loads(r[8] or '[]'),
        'dim': dim_txt, 'pavimento': r[9],
        'dxf_source': r[10],
    }


def carregar_viga(obra: str, nome: str) -> dict:
    conn = _conn()
    r = conn.execute('''
        SELECT b.name, b.data_json, b.sides_data_json,
               b.validated_fields_json, b.issues_json, b.validated_fields_json,
               b.seg_a_laje_inf, b.seg_b_laje_inf,
               p.name as pav
        FROM beams b JOIN projects p ON b.project_id=p.id
        WHERE p.work_name=? AND b.name=? LIMIT 1
    ''', (obra, nome)).fetchone()
    conn.close()
    if not r: return {}
    dj = json.loads(r[1] or '{}')
    f  = dj.get('fields', {})
    lk = dj.get('links', {})
    cm = dj.get('confidence_map', {}) or json.loads(r[3] or '{}')
    geom = dj.get('geometry', {})

    # apoios
    apoios_ini = [a.get('text','?') for a in lk.get('apoios', {}).get('inicio', [])]
    apoios_fim = [a.get('text','?') for a in lk.get('apoios', {}).get('fim', [])]

    # Parsear dimensão b/h em mm
    dim = f.get('dimensao', '') or dj.get('dim', '')
    b_mm = h_mm = 0.0
    m = re.match(r'(\d+)\s*/\s*(\d+)', str(dim))
    if m:
        b_mm = float(m.group(1)) * 10
        h_mm = float(m.group(2)) * 10

    return {
        'nome': r[0], 'tipo': 'Viga',
        'dim': dim, 'b_mm': b_mm, 'h_mm': h_mm,
        'comprimento_a': f.get('comprimento_total_a', 0) or 0,
        'comprimento_b': f.get('comprimento_total_b', 0) or 0,
        'comprimento_fundo': f.get('comprimento_fundo', 0) or 0,
        'possui_corte': f.get('possui_corte', False),
        'altura_h1': f.get('altura_h1'),
        'altura_h2': f.get('altura_h2'),
        'laje_sup_a': f.get('laje_superior_a', '—'),
        'laje_sup_b': f.get('laje_superior_b', '—'),
        'nivel_a': f.get('nivel_lado_a'),
        'nivel_b': f.get('nivel_lado_b'),
        'apoios_ini': apoios_ini, 'apoios_fim': apoios_fim,
        'seg_a_laje_inf': r[6], 'seg_b_laje_inf': r[7],
        'geometry': geom,
        'links': lk,
        'conf_map': cm,
        'issues': json.loads(r[4] or '[]'),
        'validated': json.loads(r[5] or '[]'),
        'pavimento': r[8],
    }


def carregar_laje(obra: str, nome: str) -> dict:
    conn = _conn()
    r = conn.execute('''
        SELECT s.name, s.area, s.points_json, s.links_json,
               s.type, s.validated_fields_json, s.issues_json, s.validated_fields_json,
               p.name as pav
        FROM slabs s JOIN projects p ON s.project_id=p.id
        WHERE p.work_name=? AND s.name=? LIMIT 1
    ''', (obra, nome)).fetchone()
    conn.close()
    if not r: return {}
    lk = json.loads(r[3] or '{}')
    pts = json.loads(r[2] or '[]')

    dim_txt = ''
    if lk.get('laje_dim', {}).get('label'):
        dim_txt = lk['laje_dim']['label'][0].get('text', '')

    # Área real
    area_m2 = (r[1] or 0) / 1e6

    # Bounding box
    b_mm = h_mm = 0.0
    if pts:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        b_mm = round(max(xs) - min(xs), 1)
        h_mm = round(max(ys) - min(ys), 1)

    # Contorno / acrescimos / ilhas
    outline_segs = lk.get('laje_outline_segs', {}).get('contour', [])
    acrescimo   = lk.get('laje_outline_segs', {}).get('acrescimo_borda', [])
    islands     = lk.get('laje_outline_segs', {}).get('islands', [])

    return {
        'nome': r[0], 'tipo': r[4] or 'Laje',
        'area': r[1] or 0, 'area_m2': area_m2,
        'pontos': pts, 'b_mm': b_mm, 'h_mm': h_mm,
        'dim': dim_txt,
        'links': lk,
        'outline_segs': outline_segs,
        'acrescimo': acrescimo,
        'islands': islands,
        'conf_map': {},  # slabs table has no conf_map_json column
        'issues': json.loads(r[6] or '[]'),
        'validated': json.loads(r[7] or '[]'),
        'pavimento': r[8],
    }


def encontrar_dxf_gerado(obra: str, tipo: str, nome: str) -> Optional[Path]:
    tipo_map = {'pilar': 'DXF_Pilares', 'viga': 'DXF_Vigas', 'laje': 'DXF_Lajes'}
    pasta = DADOS_DIR / obra / 'Fase-5_Geracao_Scripts' / tipo_map.get(tipo, '')
    if pasta.exists():
        for fname in [f'{nome}.dxf', f'{nome}_A.dxf', f'{nome}_lateral.dxf']:
            p = pasta / fname
            if p.exists(): return p
    return None


def inventario_dxf(dxf_path: Path) -> dict:
    """Retorna inventário completo das entidades de um DXF."""
    inv = {'layers': {}, 'total': 0, 'texts': [], 'bbox': None}
    if not dxf_path or not dxf_path.exists():
        return inv
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        all_xs, all_ys = [], []
        for e in msp:
            t = e.dxftype()
            layer = getattr(e.dxf, 'layer', '0')
            inv['layers'].setdefault(layer, {'count': 0, 'types': {}})
            inv['layers'][layer]['count'] += 1
            inv['layers'][layer]['types'][t] = inv['layers'][layer]['types'].get(t, 0) + 1
            inv['total'] += 1

            if t == 'LWPOLYLINE':
                try:
                    pts = list(e.get_points('xy'))
                    all_xs.extend(p[0] for p in pts)
                    all_ys.extend(p[1] for p in pts)
                except Exception: pass

            elif t in ('TEXT', 'MTEXT'):
                try:
                    ip = e.dxf.insert
                    if t == 'TEXT':
                        txt = getattr(e.dxf, 'text', '') or ''
                    else:
                        txt = e.plain_text() if hasattr(e, 'plain_text') else ''
                        if not txt:
                            txt = re.sub(r'\\[A-Za-z][^;]*;', '', getattr(e.dxf, 'text', '') or '')
                    h = getattr(e.dxf, 'height', None) or getattr(e.dxf, 'char_height', None)
                    inv['texts'].append({
                        'layer': layer, 'text': txt.strip().replace('\n',' '),
                        'x': float(ip.x), 'y': float(ip.y), 'h': h,
                    })
                    all_xs.append(float(ip.x)); all_ys.append(float(ip.y))
                except Exception: pass

        if all_xs:
            inv['bbox'] = {
                'xmin': min(all_xs), 'xmax': max(all_xs),
                'ymin': min(all_ys), 'ymax': max(all_ys),
                'w': max(all_xs) - min(all_xs),
                'h': max(all_ys) - min(all_ys),
            }
    except Exception as ex:
        print(f"  [WARN] inventario_dxf: {ex}")
    return inv


# ── PNG: render DXF dark-theme ─────────────────────────────────────────────────

def renderizar_dxf_png(dxf_path: Path, out_png: Path, titulo: str = '') -> bool:
    if not HAS_MPL or not dxf_path or not dxf_path.exists():
        return False
    try:
        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.set_aspect('equal')
        ax.set_facecolor(DARK_BG)
        fig.patch.set_facecolor(DARK_CARD)

        all_xs, all_ys, texts = [], [], []
        bulge_segments = []

        for e in msp:
            etype = e.dxftype()
            layer = getattr(e.dxf, 'layer', '0').lower()
            clr_info = LAYER_COLOR_MAP.get(layer, ('#8b949e', ''))
            clr = clr_info[0] if isinstance(clr_info, tuple) else clr_info

            if etype == 'LWPOLYLINE':
                try:
                    pts_full = list(e.get_points('xyzsb'))
                    pts = [(p[0], p[1]) for p in pts_full]
                    if not pts: continue
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    all_xs.extend(xs); all_ys.extend(ys)
                    closed = bool(getattr(e.dxf, 'flags', 0) & 1)
                    if closed:
                        xs = xs + [xs[0]]; ys = ys + [ys[0]]
                    lw = 2.0 if layer in ('paineis', 'lateral', 'fundo', 'contorno') else 1.2
                    ax.plot(xs, ys, color=clr, linewidth=lw, solid_capstyle='round')
                    # Fill suave em polígonos fechados de painéis
                    if closed and layer in ('paineis', 'contorno'):
                        poly = MplPoly(list(zip(xs[:-1], ys[:-1])), closed=True,
                                       facecolor=clr, alpha=0.06, edgecolor='none')
                        ax.add_patch(poly)
                    # Bulges (arcos)
                    bulges = [p[4] for p in pts_full if len(p) > 4 and abs(p[4]) > 0.01]
                    if bulges:
                        bulge_segments.append({'pts': pts, 'clr': PURPLE})
                except Exception: pass

            elif etype in ('TEXT', 'MTEXT'):
                try:
                    ip = e.dxf.insert
                    if etype == 'TEXT':
                        txt = getattr(e.dxf, 'text', '') or ''
                    else:
                        txt = e.plain_text() if hasattr(e, 'plain_text') else ''
                        if not txt:
                            txt = re.sub(r'\\[A-Za-z][^;]*;', '', getattr(e.dxf, 'text', '') or '')
                    txt = txt.strip().replace('\n', ' ')[:80]
                    if txt:
                        texts.append((float(ip.x), float(ip.y), txt, clr))
                        all_xs.append(float(ip.x)); all_ys.append(float(ip.y))
                except Exception: pass

            elif etype == 'LINE':
                try:
                    s, en = e.dxf.start, e.dxf.end
                    all_xs.extend([s.x, en.x]); all_ys.extend([s.y, en.y])
                    ax.plot([s.x, en.x], [s.y, en.y], color=clr, linewidth=1.0)
                except Exception: pass

        if not all_xs:
            plt.close(fig); return False

        # Zoom automático
        xmin, xmax = min(all_xs), max(all_xs)
        ymin, ymax = min(all_ys), max(all_ys)
        pad_x = max((xmax - xmin) * 0.12, 20)
        pad_y = max((ymax - ymin) * 0.18, 30)
        ax.set_xlim(xmin - pad_x, xmax + pad_x)
        ax.set_ylim(ymin - pad_y, ymax + pad_y)

        # Textos escalados
        span = max(xmax - xmin, ymax - ymin, 1)
        fsize = max(6, min(11, span / 40))
        for (tx, ty, txt, clr) in texts:
            ax.text(tx, ty, txt, color=clr, fontsize=fsize,
                    ha='left', va='bottom', fontfamily='monospace', zorder=5,
                    bbox=dict(boxstyle='round,pad=0.15', facecolor=DARK_BG, alpha=0.8, edgecolor='none'))

        # Anotações de dimensão sobre o desenho
        w_total = xmax - xmin
        h_total = ymax - ymin
        if w_total > 0:
            ax.annotate('', xy=(xmax, ymin - pad_y * 0.6), xytext=(xmin, ymin - pad_y * 0.6),
                        arrowprops=dict(arrowstyle='<->', color=GRAY, lw=1.0))
            ax.text((xmin + xmax) / 2, ymin - pad_y * 0.65,
                    f'{w_total:.0f} mm', color=GRAY, fontsize=8, ha='center', va='top')
        if h_total > 0:
            ax.annotate('', xy=(xmax + pad_x * 0.6, ymax), xytext=(xmax + pad_x * 0.6, ymin),
                        arrowprops=dict(arrowstyle='<->', color=GRAY, lw=1.0))
            ax.text(xmax + pad_x * 0.65, (ymin + ymax) / 2,
                    f'{h_total:.0f} mm', color=GRAY, fontsize=8, ha='left', va='center', rotation=90)

        ax.grid(True, color=DARK_LINE, linewidth=0.3, alpha=0.7, zorder=0)
        ax.set_facecolor(DARK_BG)
        ax.tick_params(colors=GRAY, labelsize=7)
        for spine in ax.spines.values(): spine.set_color(DARK_LINE)

        ax.set_title(titulo or dxf_path.stem, color=WHITE, fontsize=13,
                     fontweight='bold', pad=12)
        ax.set_xlabel('X (mm)', color=GRAY, fontsize=8)
        ax.set_ylabel('Y (mm)', color=GRAY, fontsize=8)

        plt.tight_layout()
        fig.savefig(str(out_png), dpi=150, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        return True
    except Exception as ex:
        print(f"  [WARN] render png: {ex}")
        return False


# ── PNG: seção transversal (esquema geométrico) ────────────────────────────────

def renderizar_secao_transversal(dados: dict, tipo: str, out_png: Path) -> bool:
    """Desenha o esquema da seção transversal com cotas."""
    if not HAS_MPL: return False
    try:
        fig, axes = plt.subplots(1, 1, figsize=(7, 6))
        ax = axes
        ax.set_aspect('equal')
        ax.set_facecolor(DARK_BG)
        fig.patch.set_facecolor(DARK_CARD)

        if tipo == 'pilar':
            b = dados.get('b_mm', 0) or 190
            h = dados.get('h_mm', 0) or 460
            if b == 0: b = 190
            if h == 0: h = 460
            # Retângulo da seção
            rect = Rectangle((0, 0), b, h, linewidth=2, edgecolor=CYAN,
                              facecolor='#0d2135', zorder=2)
            ax.add_patch(rect)
            # Linhas de cota
            pad = max(b, h) * 0.18
            # Cota B (horizontal)
            ax.annotate('', xy=(b, -pad * 0.7), xytext=(0, -pad * 0.7),
                        arrowprops=dict(arrowstyle='<->', color=YELLOW, lw=1.5))
            ax.text(b / 2, -pad * 0.75, f'B = {b/10:.0f} cm', color=YELLOW,
                    fontsize=10, ha='center', va='top', fontweight='bold')
            # Cota H (vertical)
            ax.annotate('', xy=(b + pad * 0.7, h), xytext=(b + pad * 0.7, 0),
                        arrowprops=dict(arrowstyle='<->', color=YELLOW, lw=1.5))
            ax.text(b + pad * 0.75, h / 2, f'H = {h/10:.0f} cm', color=YELLOW,
                    fontsize=10, ha='left', va='center', fontweight='bold')
            # Área
            area_cm2 = (b / 10) * (h / 10)
            ax.text(b / 2, h / 2, f'A = {area_cm2:.0f} cm²', color=WHITE,
                    fontsize=11, ha='center', va='center', alpha=0.9, fontweight='bold')
            # Indicadores dos 4 lados
            sides_pos = {'A': (b / 2, h + pad * 0.2, 'top'),
                         'C': (b / 2, -pad * 0.1, 'bottom'),
                         'B': (b + pad * 0.1, h / 2, 'right'),
                         'D': (-pad * 0.1, h / 2, 'left')}
            sides = dados.get('sides', {})
            for lado, (sx, sy, align) in sides_pos.items():
                sd = sides.get(lado, {})
                lj = sd.get('l1_n', 'SEM LAJE')
                vn = sd.get('v_esq_n', '—')
                vd = sd.get('v_esq_d', '')
                cor = GREEN if lj != 'SEM LAJE' else GRAY
                txt = f'Lado {lado}\n{lj}\n{vn}'
                va_map = {'top': 'bottom', 'bottom': 'top', 'right': 'center', 'left': 'center'}
                ha_map = {'top': 'center', 'bottom': 'center', 'right': 'left', 'left': 'right'}
                ax.text(sx, sy, txt, color=cor, fontsize=7.5, ha=ha_map[align],
                        va=va_map[align], multialignment='center',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor=DARK_CARD, alpha=0.85,
                                  edgecolor=cor, linewidth=0.8))
            margin = max(b, h) * 0.55
            ax.set_xlim(-margin, b + margin)
            ax.set_ylim(-margin, h + margin)
            ax.set_title(f"Seção Transversal — {dados['nome']}", color=WHITE, fontsize=12, fontweight='bold')

        elif tipo == 'viga':
            b = dados.get('b_mm', 150) or 150
            h = dados.get('h_mm', 500) or 500
            L = (dados.get('comprimento_a') or 0) * 10  # cm → mm
            if L == 0: L = 5000
            # Seção transversal b×h
            rect = Rectangle((0, 0), b, h, linewidth=2, edgecolor=CYAN,
                              facecolor='#0d1a35', zorder=2)
            ax.add_patch(rect)
            pad = max(b, h) * 0.25
            ax.annotate('', xy=(b, -pad * 0.6), xytext=(0, -pad * 0.6),
                        arrowprops=dict(arrowstyle='<->', color=YELLOW, lw=1.5))
            ax.text(b / 2, -pad * 0.65, f'b = {b/10:.0f} cm', color=YELLOW,
                    fontsize=10, ha='center', va='top', fontweight='bold')
            ax.annotate('', xy=(b + pad * 0.6, h), xytext=(b + pad * 0.6, 0),
                        arrowprops=dict(arrowstyle='<->', color=YELLOW, lw=1.5))
            ax.text(b + pad * 0.65, h / 2, f'h = {h/10:.0f} cm', color=YELLOW,
                    fontsize=10, ha='left', va='center', fontweight='bold')
            # Lajes superiores
            lsup_a = dados.get('laje_sup_a', '—')
            lsup_b = dados.get('laje_sup_b', '—')
            ax.text(b / 2, h + pad * 0.2,
                    f'Laje sup A: {lsup_a}\nLaje sup B: {lsup_b}', color=GREEN,
                    fontsize=8, ha='center', va='bottom', multialignment='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=DARK_CARD, alpha=0.9, edgecolor=GREEN, lw=0.8))
            # Apoios
            apoios_ini = ', '.join(dados.get('apoios_ini', []) or ['—'])
            apoios_fim = ', '.join(dados.get('apoios_fim', []) or ['—'])
            ax.text(-pad * 0.5, h / 2, f'APOIO\n{apoios_ini}', color=ORANGE,
                    fontsize=8, ha='right', va='center', multialignment='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=DARK_CARD, alpha=0.9, edgecolor=ORANGE, lw=0.8))
            ax.text(b + pad * 1.8, h / 2, f'APOIO\n{apoios_fim}', color=ORANGE,
                    fontsize=8, ha='left', va='center', multialignment='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor=DARK_CARD, alpha=0.9, edgecolor=ORANGE, lw=0.8))
            ax.text(b / 2, h / 2, f'b={b/10:.0f}cm\nh={h/10:.0f}cm',
                    color=WHITE, fontsize=10, ha='center', va='center', fontweight='bold')
            margin = max(b, h) * 0.65
            ax.set_xlim(-margin, b + margin * 2.5)
            ax.set_ylim(-margin, h + margin)
            ax.set_title(f"Seção Transversal — {dados['nome']}", color=WHITE, fontsize=12, fontweight='bold')

        elif tipo == 'laje':
            pts = dados.get('pontos', [])
            if not pts:
                pts = [[0,0],[100,0],[100,100],[0,100]]
            # Normalizar para origem 0,0
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            xmin, ymin = min(xs), min(ys)
            pts_norm = [[p[0] - xmin, p[1] - ymin] for p in pts]
            xs_n = [p[0] for p in pts_norm]
            ys_n = [p[1] for p in pts_norm]
            b = max(xs_n) - min(xs_n)
            h = max(ys_n) - min(ys_n)
            # Polígono
            poly = MplPoly(pts_norm, closed=True, linewidth=2, edgecolor=CYAN,
                           facecolor='#0d2135', zorder=2)
            ax.add_patch(poly)
            # Centroide
            cx = sum(xs_n) / len(xs_n)
            cy = sum(ys_n) / len(ys_n)
            dim_txt = dados.get('dim', '')
            area_m2 = dados.get('area_m2', 0)
            ax.text(cx, cy,
                    f'{dados["nome"]}\n{dim_txt}\n{area_m2:.2f} m²',
                    color=WHITE, fontsize=10, ha='center', va='center',
                    fontweight='bold', multialignment='center',
                    bbox=dict(boxstyle='round,pad=0.4', facecolor=DARK_CARD, alpha=0.85,
                              edgecolor=GREEN, lw=0.8))
            # Cotas B e H
            pad = max(b, h) * 0.15
            ax.annotate('', xy=(b, -pad * 0.8), xytext=(0, -pad * 0.8),
                        arrowprops=dict(arrowstyle='<->', color=YELLOW, lw=1.5))
            ax.text(b / 2, -pad * 0.85, f'Δx = {b:.0f} mm', color=YELLOW,
                    fontsize=9, ha='center', va='top', fontweight='bold')
            ax.annotate('', xy=(b + pad * 0.8, h), xytext=(b + pad * 0.8, 0),
                        arrowprops=dict(arrowstyle='<->', color=YELLOW, lw=1.5))
            ax.text(b + pad * 0.85, h / 2, f'Δy = {h:.0f} mm', color=YELLOW,
                    fontsize=9, ha='left', va='center', fontweight='bold')
            # Pontos do contorno
            for i, (px, py) in enumerate(pts_norm):
                ax.plot(px, py, 'o', color=PURPLE, markersize=5, zorder=5)
                ax.text(px + pad * 0.05, py + pad * 0.05,
                        f'P{i+1}\n({pts[i][0]:.0f},{pts[i][1]:.0f})',
                        color=PURPLE, fontsize=6, ha='left', va='bottom')
            margin = max(b, h) * 0.30
            ax.set_xlim(-margin, b + margin * 3)
            ax.set_ylim(-margin, h + margin)
            ax.set_title(f"Planta (Contorno) — {dados['nome']}", color=WHITE, fontsize=12, fontweight='bold')

        ax.grid(True, color=DARK_LINE, linewidth=0.3, alpha=0.5, zorder=0)
        ax.tick_params(colors=GRAY, labelsize=7)
        for spine in ax.spines.values(): spine.set_color(DARK_LINE)
        ax.set_xlabel('X (mm)', color=GRAY, fontsize=8)
        ax.set_ylabel('Y (mm)', color=GRAY, fontsize=8)
        plt.tight_layout()
        fig.savefig(str(out_png), dpi=150, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        return True
    except Exception as ex:
        print(f"  [WARN] secao_transversal: {ex}")
        return False


# ── PNG: mapa de confiança visual ─────────────────────────────────────────────

def renderizar_confidence_map(conf_map: dict, issues: list, validated: list,
                               out_png: Path) -> bool:
    if not HAS_MPL or not conf_map: return False
    try:
        keys = list(conf_map.keys())
        vals = [float(conf_map[k]) for k in keys]
        n = len(keys)
        fig_h = max(4, n * 0.45)
        fig, ax = plt.subplots(figsize=(9, fig_h))
        ax.set_facecolor(DARK_BG)
        fig.patch.set_facecolor(DARK_CARD)

        y_pos = list(range(n))
        colors_bar = [GREEN if v >= 0.8 else ORANGE if v >= 0.5 else RED for v in vals]
        bars = ax.barh(y_pos, vals, color=colors_bar, height=0.65, edgecolor=DARK_LINE, linewidth=0.5)

        ax.set_yticks(y_pos)
        ax.set_yticklabels(keys, color=WHITE, fontsize=8.5)
        ax.set_xlim(0, 1.12)
        ax.set_xlabel('Confidence (0–1)', color=GRAY, fontsize=9)
        ax.axvline(0.8, color=GREEN, linestyle='--', linewidth=0.8, alpha=0.6, label='≥0.8 OK')
        ax.axvline(0.5, color=ORANGE, linestyle='--', linewidth=0.8, alpha=0.6, label='≥0.5 WARN')
        ax.legend(fontsize=8, facecolor=DARK_CARD, edgecolor=DARK_LINE, labelcolor=WHITE)

        for bar, v, key in zip(bars, vals, keys):
            val_label = f'{v:.2f}'
            if key in validated:
                val_label += ' ✓'
            ax.text(v + 0.01, bar.get_y() + bar.get_height() / 2, val_label,
                    va='center', ha='left', color=WHITE, fontsize=8)

        ax.set_title('Mapa de Confiança dos Campos', color=WHITE, fontsize=11, fontweight='bold')
        ax.tick_params(colors=GRAY, labelsize=8)
        for spine in ax.spines.values(): spine.set_color(DARK_LINE)
        ax.grid(axis='x', color=DARK_LINE, linewidth=0.3, alpha=0.5)

        plt.tight_layout()
        fig.savefig(str(out_png), dpi=130, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        return True
    except Exception as ex:
        print(f"  [WARN] confidence_map: {ex}")
        return False


# ── PDF builder ───────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    C_DARK  = rl_colors.HexColor('#0d1117')
    C_BLUE  = rl_colors.HexColor('#1f3b5a')
    C_CYAN  = rl_colors.HexColor('#58a6ff')
    C_GREEN = rl_colors.HexColor('#3fb950')
    C_WARN  = rl_colors.HexColor('#d29922')
    C_ERR   = rl_colors.HexColor('#f85149')
    C_GRAY  = rl_colors.HexColor('#8b949e')
    C_WHITE = rl_colors.HexColor('#e6edf3')
    C_BG    = rl_colors.HexColor('#161b22')

    st = {
        'h1':    ParagraphStyle('H1',   parent=base['Heading1'], fontSize=20,
                                 textColor=C_WHITE,   spaceAfter=4, spaceBefore=0,
                                 fontName='Helvetica-Bold'),
        'h2':    ParagraphStyle('H2',   parent=base['Heading2'], fontSize=14,
                                 textColor=C_CYAN,    spaceAfter=3, spaceBefore=8,
                                 fontName='Helvetica-Bold'),
        'h3':    ParagraphStyle('H3',   parent=base['Heading3'], fontSize=11,
                                 textColor=C_CYAN,    spaceAfter=2, spaceBefore=6,
                                 fontName='Helvetica-Bold'),
        'body':  ParagraphStyle('Body', parent=base['Normal'],   fontSize=9,
                                 textColor=C_WHITE,   leading=14),
        'mono':  ParagraphStyle('Mono', parent=base['Code'],     fontSize=8,
                                 fontName='Courier',  textColor=C_CYAN, leading=12),
        'label': ParagraphStyle('Lbl',  parent=base['Normal'],   fontSize=8,
                                 textColor=C_GRAY,    leading=11),
        'warn':  ParagraphStyle('Warn', parent=base['Normal'],   fontSize=9,
                                 textColor=C_WARN,    fontName='Helvetica-Bold'),
        'err':   ParagraphStyle('Err',  parent=base['Normal'],   fontSize=9,
                                 textColor=C_ERR,     fontName='Helvetica-Bold'),
        'ok':    ParagraphStyle('Ok',   parent=base['Normal'],   fontSize=9,
                                 textColor=C_GREEN,   fontName='Helvetica-Bold'),
    }
    return st


def _table_style_base(header_color=rl_colors.HexColor('#1f3b5a')):
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR',  (0, 0), (-1, 0), rl_colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 8.5),
        ('GRID',       (0, 0), (-1, -1), 0.4, rl_colors.HexColor('#21262d')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [rl_colors.HexColor('#0d1117'), rl_colors.HexColor('#161b22')]),
        ('TEXTCOLOR',  (0, 1), (-1, -1), rl_colors.HexColor('#e6edf3')),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('FONTNAME',   (0, 1), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR',  (0, 1), (0, -1), rl_colors.HexColor('#58a6ff')),
    ])


def _img_or_spacer(path: Optional[Path], w_cm, h_cm):
    if path and path.exists():
        return Image(str(path), width=w_cm * cm, height=h_cm * cm, kind='proportional')
    return Spacer(1, 3 * cm)


def gerar_pdf_pilar(dados: dict, obra: str,
                    png_dxf: Optional[Path], png_sec: Optional[Path],
                    png_conf: Optional[Path], inv: dict, out_pdf: Path):
    st = _styles()
    story = []
    nome = dados.get('nome', '?')
    pav  = dados.get('pavimento', '?')
    dim  = dados.get('dim', '—') or '—'
    tipo = dados.get('tipo', 'Pilar')
    b_mm = dados.get('b_mm', 0)
    h_mm = dados.get('h_mm', 0)
    area = dados.get('area', 0)
    issues = dados.get('issues', [])
    validated = dados.get('validated', [])
    conf = dados.get('conf_map', {})
    sides = dados.get('sides', {})

    # ── CABEÇALHO ───────────────────────────────────────────────────────────
    story.append(Paragraph(f"FICHA TÉCNICA COMPLETA — PILAR {nome}", st['h1']))
    story.append(Paragraph(
        f"<b>Obra:</b> {obra} &nbsp;|&nbsp; <b>Pavimento:</b> {pav} &nbsp;|&nbsp; "
        f"<b>Tipo:</b> {tipo} &nbsp;|&nbsp; CAD-ANALYZER v2.0", st['label']))
    story.append(HRFlowable(width="100%", thickness=2,
                             color=rl_colors.HexColor('#58a6ff'), spaceAfter=6))

    # ── DADOS TÉCNICOS ───────────────────────────────────────────────────────
    story.append(Paragraph("1. Dados Técnicos Principais", st['h2']))

    lk = dados.get('links', {})
    name_src = ''
    if lk.get('name', {}).get('label'):
        lb = lk['name']['label'][0]
        name_src = f"({lb.get('type','?')}, conf={lb.get('validated',False)})"
    dim_src = ''
    if lk.get('dim', {}).get('label'):
        lb = lk['dim']['label'][0]
        dim_src = lb.get('text', '')

    tabela = [
        ['Campo', 'Valor', 'Fonte / Detalhe'],
        ['Nome', nome, name_src or 'links_json.name'],
        ['Tipo', tipo, 'Classificação do extrator'],
        ['Pavimento', pav, 'projects.name'],
        ['Dimensão (DXF)', dim, 'links_json.dim → label[0].text'],
        ['B real (geometria)', f'{b_mm/10:.1f} cm ({b_mm:.0f} mm)', 'bbox(points_json) eje X'],
        ['H real (geometria)', f'{h_mm/10:.1f} cm ({h_mm:.0f} mm)', 'bbox(points_json) eje Y'],
        ['Área seção', f'{area:.0f} mm²  =  {area/100:.1f} cm²' if area else '—', 'area (DB)'],
        ['Vértices contorno', str(len(dados.get('pontos', []))), 'points_json length'],
        ['Conf. nome', f"{conf.get('name', 0):.2f}", 'conf_map_json.name'],
        ['Conf. dim',  f"{conf.get('dim', 0):.2f}", 'conf_map_json.dim'],
        ['Validado', 'SIM' if validated else 'NÃO', ', '.join(validated) or '—'],
        ['Tipo Forma', 'Cambotado (arcos)' if 'cambotado' in tipo.lower() else 'Retangular', 'Campo tipo'],
    ]
    t = Table(tabela, colWidths=[4.5 * cm, 5 * cm, 7.5 * cm])
    t.setStyle(_table_style_base())
    story.append(t)
    story.append(Spacer(1, 8))

    # ── ISSUES ────────────────────────────────────────────────────────────────
    if issues:
        story.append(Paragraph("⚠ Alertas / Issues Detectados", st['h3']))
        for iss in issues:
            story.append(Paragraph(f"• {iss}", st['warn']))
        story.append(Spacer(1, 6))

    # ── VISUALIZAÇÃO DXF ─────────────────────────────────────────────────────
    story.append(Paragraph("2. Visualização DXF Gerado (Robô Bolt)", st['h2']))
    if png_dxf and png_dxf.exists():
        story.append(Image(str(png_dxf), width=17 * cm, height=11 * cm, kind='proportional'))
    else:
        story.append(Paragraph("DXF Fase-5 não encontrado.", st['warn']))
    story.append(Spacer(1, 6))

    # ── INVENTÁRIO DXF ────────────────────────────────────────────────────────
    story.append(Paragraph("3. Inventário de Entidades no DXF", st['h2']))
    if inv.get('layers'):
        bbox = inv.get('bbox', {})
        story.append(Paragraph(
            f"Total de entidades: <b>{inv['total']}</b> &nbsp;|&nbsp; "
            f"Layers: <b>{len(inv['layers'])}</b> &nbsp;|&nbsp; "
            f"BBox: {bbox.get('w', 0):.0f} × {bbox.get('h', 0):.0f} mm",
            st['label']))
        inv_rows = [['Layer', 'Qtd.', 'Tipos', 'Cor', 'Descrição']]
        for layer_name, ldata in sorted(inv['layers'].items()):
            clr_info = LAYER_COLOR_MAP.get(layer_name.lower(), ('#8b949e', 'Layer personalizado'))
            clr_hex, descr = clr_info if isinstance(clr_info, tuple) else (clr_info, '')
            tipos_str = ', '.join(f"{k}×{v}" for k, v in ldata['types'].items())
            inv_rows.append([layer_name, str(ldata['count']), tipos_str, clr_hex, descr])
        ti = Table(inv_rows, colWidths=[3.5*cm, 1.5*cm, 4*cm, 2*cm, 6*cm])
        ti.setStyle(_table_style_base(rl_colors.HexColor('#1f3b5a')))
        story.append(ti)
        story.append(Spacer(1, 6))

        # Textos encontrados
        if inv.get('texts'):
            story.append(Paragraph("Textos no DXF:", st['h3']))
            txt_rows = [['Layer', 'Texto', 'X (mm)', 'Y (mm)', 'H']]
            for tx in inv['texts']:
                txt_rows.append([
                    tx['layer'], tx['text'][:50], f"{tx['x']:.0f}",
                    f"{tx['y']:.0f}", f"{tx['h'] or '—'}"
                ])
            tt = Table(txt_rows, colWidths=[3.5*cm, 7*cm, 2*cm, 2*cm, 1.5*cm])
            tt.setStyle(_table_style_base())
            story.append(tt)
    else:
        story.append(Paragraph("DXF não disponível.", st['label']))
    story.append(Spacer(1, 8))

    # ── SEÇÃO TRANSVERSAL ─────────────────────────────────────────────────────
    story.append(Paragraph("4. Diagrama de Seção Transversal + Vizinhança", st['h2']))
    if png_sec and png_sec.exists():
        story.append(Image(str(png_sec), width=15 * cm, height=12 * cm, kind='proportional'))
    story.append(Spacer(1, 6))

    # ── TABELA DE SIDES A/B/C/D ───────────────────────────────────────────────
    story.append(Paragraph("5. Vizinhança por Lado (A / B / C / D)", st['h2']))
    side_rows = [['Lado', 'Laje Adjacente (l1_n)', 'Viga Adjacente', 'Dim. Viga', 'Status']]
    for lado in ['A', 'B', 'C', 'D']:
        sd = sides.get(lado, {})
        lj  = sd.get('l1_n', 'SEM LAJE')
        vn  = sd.get('v_esq_n', '—')
        vd  = sd.get('v_esq_d', '—')
        status = 'OK' if lj not in ('SEM LAJE', '?', '') else 'SEM LAJE'
        side_rows.append([f'Lado {lado}', lj, vn, vd, status])
    ts = Table(side_rows, colWidths=[2*cm, 4.5*cm, 3.5*cm, 3.5*cm, 3.5*cm])
    ts.setStyle(_table_style_base())
    # Colorir linhas SEM LAJE
    for i, row in enumerate(side_rows[1:], start=1):
        if row[4] == 'SEM LAJE':
            ts.setStyle(TableStyle([('TEXTCOLOR', (4, i), (4, i), rl_colors.HexColor('#8b949e'))]))
        else:
            ts.setStyle(TableStyle([('TEXTCOLOR', (4, i), (4, i), rl_colors.HexColor('#3fb950'))]))
    story.append(ts)
    story.append(Spacer(1, 8))

    # Links detalhados por lado
    story.append(Paragraph("5.1 Links Detalhados por Lado (links_json)", st['h3']))
    lk_rows = [['Campo', 'Texto Detectado', 'Tipo', 'Posição (X,Y)', 'Role']]
    for field_key in ['p_sA_l1_n','p_sA_v_esq_n','p_sA_v_esq_d',
                       'p_sB_l1_n','p_sB_v_esq_n','p_sB_v_esq_d',
                       'p_sC_l1_n','p_sC_v_esq_n','p_sC_v_esq_d',
                       'p_sD_l1_n','p_sD_v_esq_n','p_sD_v_esq_d']:
        lkd = lk.get(field_key, {})
        for lb in (lkd.get('label') or [])[:1]:
            lk_rows.append([
                field_key,
                str(lb.get('text', '—'))[:30],
                lb.get('type', '—'),
                f"({lb.get('pos', ['?','?'])[0]:.0f}, {lb.get('pos', ['?','?'])[1]:.0f})" if lb.get('pos') else '—',
                lb.get('role', '—'),
            ])
    if len(lk_rows) > 1:
        tl = Table(lk_rows, colWidths=[4*cm, 3*cm, 2*cm, 3.5*cm, 4.5*cm])
        tl.setStyle(_table_style_base())
        story.append(tl)
    story.append(Spacer(1, 8))

    # ── CONFIDENCE MAP ────────────────────────────────────────────────────────
    story.append(Paragraph("6. Mapa de Confiança dos Campos (conf_map_json)", st['h2']))
    if png_conf and png_conf.exists():
        story.append(Image(str(png_conf), width=16 * cm, height=9 * cm, kind='proportional'))
    if conf:
        conf_rows = [['Campo', 'Score', 'Status']]
        for k, v in sorted(conf.items(), key=lambda x: -x[1]):
            status = '✓ OK' if v >= 0.8 else '⚠ ATENÇÃO' if v >= 0.5 else '✗ BAIXO'
            conf_rows.append([k, f'{float(v):.2f}', status])
        tc = Table(conf_rows, colWidths=[6*cm, 3*cm, 8*cm])
        tc.setStyle(_table_style_base())
        story.append(tc)
    story.append(Spacer(1, 8))

    # ── LEGENDA LAYERS ─────────────────────────────────────────────────────────
    story.append(Paragraph("7. Legenda de Layers DXF (padrão CAD-ANALYZER)", st['h2']))
    leg_rows = [['Layer', 'Cor (hex)', 'Conteúdo / Função']]
    for ln, (lc, ld) in LAYER_COLOR_MAP.items():
        leg_rows.append([ln, lc, ld])
    tleg = Table(leg_rows, colWidths=[3.5*cm, 2.5*cm, 11*cm])
    tleg.setStyle(_table_style_base())
    story.append(tleg)
    story.append(Spacer(1, 10))

    # ── RODAPÉ ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=rl_colors.HexColor('#21262d')))
    story.append(Paragraph(
        f"Diana Corporação Senciente  |  CAD-ANALYZER v2.0  |  "
        f"Obra: {obra}  |  Elemento: {nome}  |  2026",
        st['label']))

    doc = SimpleDocTemplate(str(out_pdf), pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            title=f"Ficha Pilar {nome} — {obra}",
                            author="CAD-ANALYZER v2.0")
    doc.build(story)


def gerar_pdf_viga(dados: dict, obra: str,
                   png_dxf: Optional[Path], png_sec: Optional[Path],
                   png_conf: Optional[Path], inv: dict, out_pdf: Path):
    st = _styles()
    story = []
    nome = dados.get('nome', '?')
    pav  = dados.get('pavimento', '?')
    dim  = dados.get('dim', '—') or '—'
    b_mm = dados.get('b_mm', 0)
    h_mm = dados.get('h_mm', 0)
    conf = dados.get('conf_map', {})
    issues = dados.get('issues', [])
    validated = dados.get('validated', [])

    story.append(Paragraph(f"FICHA TÉCNICA COMPLETA — VIGA {nome}", st['h1']))
    story.append(Paragraph(
        f"<b>Obra:</b> {obra} &nbsp;|&nbsp; <b>Pavimento:</b> {pav} &nbsp;|&nbsp; CAD-ANALYZER v2.0",
        st['label']))
    story.append(HRFlowable(width="100%", thickness=2,
                             color=rl_colors.HexColor('#58a6ff'), spaceAfter=6))

    story.append(Paragraph("1. Dados Técnicos Principais", st['h2']))
    tabela = [
        ['Campo', 'Valor', 'Fonte / Detalhe'],
        ['Nome', nome, 'links_json.name.label[0].text'],
        ['Tipo', 'Viga', 'Classificação extrator'],
        ['Pavimento', pav, 'projects.name'],
        ['Dimensão (b/h)', dim, 'data_json.fields.dimensao'],
        ['Largura b', f'{b_mm/10:.1f} cm ({b_mm:.0f} mm)', 'parse dim regex \\d+/\\d+'],
        ['Altura h', f'{h_mm/10:.1f} cm ({h_mm:.0f} mm)', 'parse dim regex \\d+/\\d+'],
        ['Comprimento L (face A)', f'{dados.get("comprimento_a",0):.1f} cm', 'fields.comprimento_total_a'],
        ['Comprimento L (face B)', f'{dados.get("comprimento_b",0):.1f} cm', 'fields.comprimento_total_b'],
        ['Comprimento fundo', f'{dados.get("comprimento_fundo",0):.1f} cm', 'fields.comprimento_fundo'],
        ['Possui corte', 'SIM' if dados.get('possui_corte') else 'NÃO', 'fields.possui_corte'],
        ['Altura H1', f'{dados.get("altura_h1","—")} cm', 'fields.altura_h1'],
        ['Altura H2', f'{dados.get("altura_h2","—")} cm', 'fields.altura_h2 (se corte)'],
        ['Laje superior A', dados.get('laje_sup_a', '—'), 'fields.laje_superior_a'],
        ['Laje superior B', dados.get('laje_sup_b', '—'), 'fields.laje_superior_b'],
        ['Nível lado A', str(dados.get('nivel_a', '—')), 'fields.nivel_lado_a'],
        ['Nível lado B', str(dados.get('nivel_b', '—')), 'fields.nivel_lado_b'],
        ['Apoios (início)', ', '.join(dados.get('apoios_ini', []) or ['—']), 'links.apoios.inicio[].text'],
        ['Apoios (fim)',   ', '.join(dados.get('apoios_fim', []) or ['—']), 'links.apoios.fim[].text'],
        ['Laje inf seg A', dados.get('seg_a_laje_inf') or '—', 'beams.seg_a_laje_inf'],
        ['Laje inf seg B', dados.get('seg_b_laje_inf') or '—', 'beams.seg_b_laje_inf'],
        ['Conf. nome', f"{conf.get('name', 0):.2f}", 'confidence_map.name'],
        ['Conf. dim',  f"{conf.get('dim', 0):.2f}", 'confidence_map.dim'],
        ['Validado', 'SIM' if validated else 'NÃO', ', '.join(validated) or '—'],
    ]
    t = Table(tabela, colWidths=[4.5*cm, 5*cm, 7.5*cm])
    t.setStyle(_table_style_base())
    story.append(t)
    story.append(Spacer(1, 8))

    if issues:
        story.append(Paragraph("⚠ Alertas", st['h3']))
        for iss in issues:
            story.append(Paragraph(f"• {iss}", st['warn']))
        story.append(Spacer(1, 6))

    story.append(Paragraph("2. Visualização DXF Gerado (Robô Crane)", st['h2']))
    story.append(Paragraph(
        "Faces: A (lateral esquerda) | B (lateral direita) | Fundo — cada face segmentada em painéis.",
        st['label']))
    if png_dxf and png_dxf.exists():
        story.append(Image(str(png_dxf), width=17*cm, height=11*cm, kind='proportional'))
    else:
        story.append(Paragraph("DXF Fase-5 não encontrado.", st['warn']))
    story.append(Spacer(1, 6))

    story.append(Paragraph("3. Inventário de Entidades DXF", st['h2']))
    if inv.get('layers'):
        bbox = inv.get('bbox', {})
        story.append(Paragraph(
            f"Total: <b>{inv['total']}</b> entidades &nbsp;|&nbsp; "
            f"Layers: <b>{len(inv['layers'])}</b> &nbsp;|&nbsp; "
            f"BBox: {bbox.get('w',0):.0f} × {bbox.get('h',0):.0f} mm",
            st['label']))
        inv_rows = [['Layer', 'Qtd.', 'Tipos', 'Cor', 'Descrição']]
        for ln, ld in sorted(inv['layers'].items()):
            clr_info = LAYER_COLOR_MAP.get(ln.lower(), ('#8b949e', 'Layer personalizado'))
            clr_hex, descr = clr_info if isinstance(clr_info, tuple) else (clr_info, '')
            inv_rows.append([ln, str(ld['count']),
                             ', '.join(f"{k}×{v}" for k,v in ld['types'].items()),
                             clr_hex, descr])
        ti = Table(inv_rows, colWidths=[3.5*cm, 1.5*cm, 4*cm, 2*cm, 6*cm])
        ti.setStyle(_table_style_base())
        story.append(ti)
        story.append(Spacer(1, 6))
        if inv.get('texts'):
            story.append(Paragraph("Textos no DXF:", st['h3']))
            txt_rows = [['Layer', 'Texto', 'X (mm)', 'Y (mm)']]
            for tx in inv['texts']:
                txt_rows.append([tx['layer'], tx['text'][:60],
                                  f"{tx['x']:.0f}", f"{tx['y']:.0f}"])
            tt = Table(txt_rows, colWidths=[3.5*cm, 8.5*cm, 2*cm, 2*cm])
            tt.setStyle(_table_style_base())
            story.append(tt)
    story.append(Spacer(1, 8))

    story.append(Paragraph("4. Seção Transversal b × h + Conexões", st['h2']))
    if png_sec and png_sec.exists():
        story.append(Image(str(png_sec), width=15*cm, height=11*cm, kind='proportional'))
    story.append(Spacer(1, 6))

    story.append(Paragraph("5. Mapa de Confiança", st['h2']))
    if png_conf and png_conf.exists():
        story.append(Image(str(png_conf), width=16*cm, height=8*cm, kind='proportional'))
    if conf:
        conf_rows = [['Campo', 'Score', 'Status']]
        for k, v in sorted(conf.items(), key=lambda x: -x[1]):
            st_txt = '✓ OK' if v >= 0.8 else '⚠ ATENÇÃO' if v >= 0.5 else '✗ BAIXO'
            conf_rows.append([k, f'{float(v):.2f}', st_txt])
        tc = Table(conf_rows, colWidths=[6*cm, 3*cm, 8*cm])
        tc.setStyle(_table_style_base())
        story.append(tc)
    story.append(Spacer(1, 8))

    story.append(Paragraph("6. Legenda de Layers DXF", st['h2']))
    leg_rows = [['Layer', 'Cor', 'Conteúdo']]
    for ln, (lc, ld) in LAYER_COLOR_MAP.items():
        leg_rows.append([ln, lc, ld])
    tleg = Table(leg_rows, colWidths=[3.5*cm, 2.5*cm, 11*cm])
    tleg.setStyle(_table_style_base())
    story.append(tleg)
    story.append(Spacer(1, 10))

    story.append(HRFlowable(width="100%", thickness=1, color=rl_colors.HexColor('#21262d')))
    story.append(Paragraph(
        f"Diana Corporação Senciente  |  CAD-ANALYZER v2.0  |  Obra: {obra}  |  Elemento: {nome}  |  2026",
        st['label']))

    doc = SimpleDocTemplate(str(out_pdf), pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            title=f"Ficha Viga {nome} — {obra}")
    doc.build(story)


def gerar_pdf_laje(dados: dict, obra: str,
                   png_dxf: Optional[Path], png_sec: Optional[Path],
                   png_conf: Optional[Path], inv: dict, out_pdf: Path):
    st = _styles()
    story = []
    nome = dados.get('nome', '?')
    pav  = dados.get('pavimento', '?')
    dim  = dados.get('dim', '—') or '—'
    tipo = dados.get('tipo', 'Laje')
    b_mm = dados.get('b_mm', 0)
    h_mm = dados.get('h_mm', 0)
    conf = dados.get('conf_map', {})
    issues = dados.get('issues', [])
    validated = dados.get('validated', [])
    area_m2 = dados.get('area_m2', 0)
    pts = dados.get('pontos', [])

    story.append(Paragraph(f"FICHA TÉCNICA COMPLETA — LAJE {nome}", st['h1']))
    story.append(Paragraph(
        f"<b>Obra:</b> {obra} &nbsp;|&nbsp; <b>Pavimento:</b> {pav} &nbsp;|&nbsp; CAD-ANALYZER v2.0",
        st['label']))
    story.append(HRFlowable(width="100%", thickness=2,
                             color=rl_colors.HexColor('#58a6ff'), spaceAfter=6))

    story.append(Paragraph("1. Dados Técnicos Principais", st['h2']))
    tabela = [
        ['Campo', 'Valor', 'Fonte / Detalhe'],
        ['Nome', nome, 'links_json.name.label[0].text'],
        ['Tipo', tipo, 'slabs.type'],
        ['Pavimento', pav, 'projects.name'],
        ['Espessura (h=)', dim, 'links_json.laje_dim.label[0].text'],
        ['Δx (bounding box)', f'{b_mm:.0f} mm = {b_mm/10:.1f} cm', 'bbox(points_json) eje X'],
        ['Δy (bounding box)', f'{h_mm:.0f} mm = {h_mm/10:.1f} cm', 'bbox(points_json) eje Y'],
        ['Área (DB)', f'{dados.get("area",0):.0f} mm²', 'slabs.area (raw)'],
        ['Área (m²)', f'{area_m2:.4f} m²', 'area / 1e6'],
        ['Vértices contorno', str(len(pts)), 'points_json length'],
        ['Outline segs', str(len(dados.get('outline_segs', []))), 'laje_outline_segs.contour'],
        ['Acréscimo borda', str(len(dados.get('acrescimo', []))), 'laje_outline_segs.acrescimo_borda'],
        ['Ilhas (aberturas)', str(len(dados.get('islands', []))), 'laje_outline_segs.islands'],
        ['Conf. name', f"{conf.get('name',0):.2f}", 'conf_map_json.name'],
        ['Validado', 'SIM' if validated else 'NÃO', ', '.join(validated) or '—'],
    ]
    t = Table(tabela, colWidths=[4.5*cm, 5*cm, 7.5*cm])
    t.setStyle(_table_style_base())
    story.append(t)
    story.append(Spacer(1, 8))

    if issues:
        story.append(Paragraph("⚠ Alertas", st['h3']))
        for iss in issues:
            story.append(Paragraph(f"• {iss}", st['warn']))
        story.append(Spacer(1, 6))

    # Coordenadas dos pontos
    story.append(Paragraph("1.1 Pontos do Contorno (points_json)", st['h3']))
    pt_rows = [['#', 'X (mm)', 'Y (mm)', 'X (cm)', 'Y (cm)']]
    for i, p in enumerate(pts):
        pt_rows.append([str(i + 1), f'{p[0]:.2f}', f'{p[1]:.2f}',
                         f'{p[0]/10:.1f}', f'{p[1]/10:.1f}'])
    tp = Table(pt_rows, colWidths=[1*cm, 3.5*cm, 3.5*cm, 3.5*cm, 3.5*cm])
    tp.setStyle(_table_style_base())
    story.append(tp)
    story.append(Spacer(1, 8))

    story.append(Paragraph("2. Visualização DXF Gerado (Robô Slab)", st['h2']))
    if png_dxf and png_dxf.exists():
        story.append(Image(str(png_dxf), width=17*cm, height=11*cm, kind='proportional'))
    else:
        story.append(Paragraph("DXF Fase-5 não encontrado.", st['warn']))
    story.append(Spacer(1, 6))

    story.append(Paragraph("3. Planta do Contorno (escala proporcional)", st['h2']))
    if png_sec and png_sec.exists():
        story.append(Image(str(png_sec), width=15*cm, height=12*cm, kind='proportional'))
    story.append(Spacer(1, 6))

    story.append(Paragraph("4. Inventário de Entidades DXF", st['h2']))
    if inv.get('layers'):
        bbox = inv.get('bbox', {})
        story.append(Paragraph(
            f"Total: <b>{inv['total']}</b> &nbsp;|&nbsp; Layers: <b>{len(inv['layers'])}</b> "
            f"&nbsp;|&nbsp; BBox: {bbox.get('w',0):.0f} × {bbox.get('h',0):.0f} mm",
            st['label']))
        inv_rows = [['Layer', 'Qtd.', 'Tipos', 'Descrição']]
        for ln, ld in sorted(inv['layers'].items()):
            clr_info = LAYER_COLOR_MAP.get(ln.lower(), ('#8b949e', 'Layer personalizado'))
            descr = clr_info[1] if isinstance(clr_info, tuple) else ''
            inv_rows.append([ln, str(ld['count']),
                             ', '.join(f"{k}×{v}" for k,v in ld['types'].items()),
                             descr])
        ti = Table(inv_rows, colWidths=[3.5*cm, 1.5*cm, 4*cm, 8*cm])
        ti.setStyle(_table_style_base())
        story.append(ti)
        story.append(Spacer(1, 6))
        if inv.get('texts'):
            story.append(Paragraph("Textos no DXF:", st['h3']))
            txt_rows = [['Layer', 'Texto', 'X (mm)', 'Y (mm)']]
            for tx in inv['texts']:
                txt_rows.append([tx['layer'], tx['text'][:70],
                                  f"{tx['x']:.1f}", f"{tx['y']:.1f}"])
            tt = Table(txt_rows, colWidths=[3.5*cm, 9*cm, 2*cm, 2*cm])
            tt.setStyle(_table_style_base())
            story.append(tt)
    story.append(Spacer(1, 8))

    story.append(Paragraph("5. Mapa de Confiança", st['h2']))
    if png_conf and png_conf.exists():
        story.append(Image(str(png_conf), width=16*cm, height=6*cm, kind='proportional'))
    story.append(Spacer(1, 8))

    story.append(Paragraph("6. Legenda de Layers DXF", st['h2']))
    leg_rows = [['Layer', 'Cor', 'Conteúdo']]
    for ln, (lc, ld) in LAYER_COLOR_MAP.items():
        leg_rows.append([ln, lc, ld])
    tleg = Table(leg_rows, colWidths=[3.5*cm, 2.5*cm, 11*cm])
    tleg.setStyle(_table_style_base())
    story.append(tleg)
    story.append(Spacer(1, 10))

    story.append(HRFlowable(width="100%", thickness=1, color=rl_colors.HexColor('#21262d')))
    story.append(Paragraph(
        f"Diana Corporação Senciente  |  CAD-ANALYZER v2.0  |  Obra: {obra}  |  Elemento: {nome}  |  2026",
        st['label']))

    doc = SimpleDocTemplate(str(out_pdf), pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm,
                            title=f"Ficha Laje {nome} — {obra}")
    doc.build(story)


# ── Main ──────────────────────────────────────────────────────────────────────

def processar_elemento(obra: str, tipo: str, nome: str):
    print(f"\n[{tipo.upper()} {nome}] gerando ficha completa...")

    # Carregar dados do DB
    if tipo == 'pilar':
        dados = carregar_pilar(obra, nome)
    elif tipo == 'viga':
        dados = carregar_viga(obra, nome)
    else:
        dados = carregar_laje(obra, nome)

    if not dados:
        print(f"  [ERRO] {tipo} {nome} não encontrado em {obra}")
        return

    print(f"  DB: pav={dados.get('pavimento')} | dim={dados.get('dim','?')} | "
          f"b={dados.get('b_mm',0):.0f}mm h={dados.get('h_mm',0):.0f}mm")

    # DXF gerado
    dxf_gerado = encontrar_dxf_gerado(obra, tipo, nome)
    if dxf_gerado:
        print(f"  DXF Fase-5: {dxf_gerado.name} ({dxf_gerado.stat().st_size//1024}KB)")
    else:
        print(f"  [WARN] DXF Fase-5 não encontrado")

    # Inventário DXF
    inv = inventario_dxf(dxf_gerado)
    if inv.get('total'):
        print(f"  Inventário: {inv['total']} entidades em {len(inv['layers'])} layers")

    # Caminhos de saída
    slug = f"{obra}_{tipo}_{nome}".replace('/', '_')
    out_dxf  = OUT_DIR / f"ficha_{slug}.png"   # render DXF
    out_sec  = OUT_DIR / f"secao_{slug}.png"    # seção transversal
    out_conf = OUT_DIR / f"conf_{slug}.png"     # confidence map
    out_pdf  = OUT_DIR / f"ficha_{slug}.pdf"

    # 1. Render DXF → PNG
    png_dxf = None
    if dxf_gerado and HAS_MPL:
        ok = renderizar_dxf_png(
            dxf_gerado, out_dxf,
            titulo=f"{tipo.upper()} {nome} — {dados.get('pavimento', '')} | {dados.get('dim', '')}"
        )
        if ok:
            png_dxf = out_dxf
            print(f"  PNG DXF: {out_dxf.name} ({out_dxf.stat().st_size//1024}KB)")

    # 2. Seção transversal
    png_sec = None
    if HAS_MPL:
        ok2 = renderizar_secao_transversal(dados, tipo, out_sec)
        if ok2:
            png_sec = out_sec
            print(f"  PNG Seção: {out_sec.name} ({out_sec.stat().st_size//1024}KB)")

    # 3. Confidence map
    png_conf = None
    if HAS_MPL and dados.get('conf_map'):
        ok3 = renderizar_confidence_map(
            dados['conf_map'], dados.get('issues', []),
            dados.get('validated', []), out_conf
        )
        if ok3:
            png_conf = out_conf
            print(f"  PNG Conf: {out_conf.name} ({out_conf.stat().st_size//1024}KB)")

    # 4. PDF completo
    if not HAS_RL:
        print("  [SKIP] reportlab não instalado — PDF não gerado")
        return

    try:
        if tipo == 'pilar':
            gerar_pdf_pilar(dados, obra, png_dxf, png_sec, png_conf, inv, out_pdf)
        elif tipo == 'viga':
            gerar_pdf_viga(dados, obra, png_dxf, png_sec, png_conf, inv, out_pdf)
        else:
            gerar_pdf_laje(dados, obra, png_dxf, png_sec, png_conf, inv, out_pdf)
        print(f"  PDF: {out_pdf.name} ({out_pdf.stat().st_size//1024}KB)")
    except Exception as ex:
        print(f"  [ERRO PDF] {ex}")
        import traceback; traceback.print_exc()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obra',  default='Obra_TREINO_1')
    parser.add_argument('--tipo',  choices=['pilar', 'viga', 'laje'], default='pilar')
    parser.add_argument('--nome',  default='P11')
    parser.add_argument('--todos', action='store_true',
                        help='Gera ficha para P11 (pilar), V101 (viga), L101 (laje)')
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.todos:
        elementos = [('pilar', 'P11'), ('viga', 'V101'), ('laje', 'L101')]
    else:
        elementos = [(args.tipo, args.nome)]

    for tipo, nome in elementos:
        processar_elemento(args.obra, tipo, nome)

    print(f"\n[OK] Fichas em: {OUT_DIR}")


if __name__ == '__main__':
    main()
