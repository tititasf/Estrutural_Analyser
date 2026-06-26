#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
"""
Zoom preciso nos cards reais de cada elemento do STOG.
Detecta a posicao real dos elementos via INSERT blocks ou LWPOLYLINE clusters.
"""
from pathlib import Path
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

STOG_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_21/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa")
OUT_DIR = Path("D:/Agente-cad-PYSIDE/validacao_visual")

def get_real_extents(doc, entity_types=None, layer_filter=None):
    """Coleta coordenadas de entidades para detectar a regiao com conteudo."""
    msp = doc.modelspace()
    xs, ys = [], []
    for e in msp:
        if entity_types and e.dxftype() not in entity_types:
            continue
        if layer_filter:
            try:
                lyr = e.dxf.layer
                if not any(f.upper() in lyr.upper() for f in layer_filter):
                    continue
            except: continue
        try:
            t = e.dxftype()
            if t == 'LWPOLYLINE':
                pts = list(e.get_points())
                xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
            elif t == 'LINE':
                xs += [e.dxf.start.x, e.dxf.end.x]
                ys += [e.dxf.start.y, e.dxf.end.y]
            elif t in ('TEXT','MTEXT','INSERT'):
                xs.append(e.dxf.insert.x); ys.append(e.dxf.insert.y)
            elif t == 'DIMENSION':
                xs.append(e.dxf.defpoint.x); ys.append(e.dxf.defpoint.y)
            elif t == 'HATCH':
                for path in e.paths:
                    for edge in getattr(path, 'edges', []):
                        if hasattr(edge, 'start'):
                            xs.append(edge.start.x); ys.append(edge.start.y)
        except: pass
    if not xs: return None
    return min(xs), max(xs), min(ys), max(ys)

def render_crop(doc, ax, title, xmin, xmax, ymin, ymax, padding_pct=0.02):
    pad_x = (xmax - xmin) * padding_pct
    pad_y = (ymax - ymin) * padding_pct
    try:
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        frontend = Frontend(ctx, out)
        frontend.draw_layout(doc.modelspace(), finalize=True)
        ax.set_xlim(xmin - pad_x, xmax + pad_x)
        ax.set_ylim(ymin - pad_y, ymax + pad_y)
        ax.set_aspect('equal')
        ax.set_title(title, fontsize=10, pad=5)
        ax.set_facecolor('#1e1e2e')
    except Exception as ex:
        ax.text(0.5, 0.5, f'Erro: {ex}', transform=ax.transAxes,
                ha='center', va='center', color='red')

# ─── PL: detectar 1 card de pilar (excluindo folha/carimbo) ──────────────────
print("=== PL ===")
doc_pl = ezdxf.readfile(str(STOG_DIR / "STOG - NIK SUNSET - 12° PAV.- FV - R00_R2018_ASCII_ODA.dxf"))

# Para FV: obter extents das LWPOLYLINES (paineis de madeira) que sao o conteudo real
ex = get_real_extents(doc_pl, entity_types={'LWPOLYLINE','LINE','HATCH','TEXT','MTEXT','DIMENSION'})
print(f"  FV extents: {ex}")
if ex:
    x0,x1,y0,y1 = ex
    # FV tem poucas vigas - mostrar tudo
    xrange = x1 - x0; yrange = y1 - y0
    # Pegar a regiao do primeiro card (parte superior da grade)
    # Estimativa: 3 colunas, pegar a 1a linha de cima
    cols = 3
    card_w = xrange / cols
    # Pegar a linha de baixo (y0) onde estao os cards reais
    card_h = yrange * 0.3  # primeiro terco
    crop_1card = (x0, x0 + card_w, y0, y0 + card_h)
    crop_all   = (x0, x1, y0, y1)
    print(f"  card estimado: {card_w:.0f} x {card_h:.0f}")

# ─── Renderizar cada STOG classe com zoom nos elementos reais ─────────────────

# ---- FV completo (poucas vigas, mais facil de ver) ----
print("Renderizando FV cards...")
fv_path = STOG_DIR / "STOG - NIK SUNSET - 12° PAV.- FV - R00_R2018_ASCII_ODA.dxf"
doc_fv = ezdxf.readfile(str(fv_path))
ex_fv = get_real_extents(doc_fv, entity_types={'LWPOLYLINE','LINE','HATCH','TEXT','MTEXT','DIMENSION'})
print(f"  FV real extents: {ex_fv}")

fig, ax = plt.subplots(figsize=(18, 10))
fig.patch.set_facecolor('#0d0d1a')
ax.set_facecolor('#1e1e2e')
if ex_fv:
    x0,x1,y0,y1 = ex_fv
    render_crop(doc_fv, ax,
        "VIGA FUNDO (FV) — Cards completos do STOG\n"
        "Cada card = 1 viga vista de baixo (fundo): compensado + sarrafos + travamento",
        x0, x1, y0, y1, padding_pct=0.01)
plt.tight_layout()
plt.savefig(str(OUT_DIR / "STOG_FV_cards_zoom.png"), dpi=150, bbox_inches='tight', facecolor='#0d0d1a')
plt.close()
print("  -> STOG_FV_cards_zoom.png")

# ---- PL: zoom na grade de pilares (excluindo capa/indice) ----
print("Renderizando PL zoom...")
pl_path = STOG_DIR / "STOG - NIK SUNSET - 12° PAVIMENTO - PL - R00_R2018_ASCII_ODA.dxf"
doc_pl = ezdxf.readfile(str(pl_path))
# Pilares tem HATCH (hachuras coloridas) — usar HATCH para encontrar regiao dos cards
ex_pl = get_real_extents(doc_pl, entity_types={'LWPOLYLINE','LINE','HATCH'})
print(f"  PL HATCH extents: {ex_pl}")
if ex_pl:
    x0,x1,y0,y1 = ex_pl
    # Os cards de pilares reais estao na parte do y mais alto (excluindo indice/capa no baixo)
    # Pegar os 2 primeiros cards da grade (canto superior esquerdo)
    xrange = x1-x0; yrange = y1-y0
    # ~4 colunas, ~9 linhas
    cw = xrange/4; ch = yrange/9
    # 1 card: top-left
    c1 = (x0, x0+cw*1.05, y1-ch*1.05, y1+ch*0.05)
    # 2x2 cards para contexto
    c4 = (x0, x0+cw*2.1, y1-ch*2.1, y1+ch*0.05)

fig, axes = plt.subplots(1, 2, figsize=(20, 10))
fig.patch.set_facecolor('#0d0d1a')
fig.suptitle("PILAR (PL) — Cards do STOG: secao transversal + paineis de forma\n"
             "Esq: 1 pilar isolado | Dir: contexto 2x2 pilares", fontsize=11, color='white')
if ex_pl:
    render_crop(doc_pl, axes[0], "1 Pilar — zoom total", *c1)
    render_crop(doc_pl, axes[1], "Grade 2x2 pilares — contexto", *c4)
plt.tight_layout()
plt.savefig(str(OUT_DIR / "STOG_PL_cards_zoom.png"), dpi=150, bbox_inches='tight', facecolor='#0d0d1a')
plt.close()
print("  -> STOG_PL_cards_zoom.png")

# ---- LV: zoom nos cards de vigas laterais ----
print("Renderizando LV zoom...")
lv_path = STOG_DIR / "STOG - NIK SUNSET - 12° PAVIMENTO - LV - R00_R2018_ASCII_ODA.dxf"
doc_lv = ezdxf.readfile(str(lv_path))
ex_lv = get_real_extents(doc_lv, entity_types={'LWPOLYLINE','LINE','HATCH'})
print(f"  LV HATCH extents: {ex_lv}")
if ex_lv:
    x0,x1,y0,y1 = ex_lv
    xrange=x1-x0; yrange=y1-y0
    # LV: ~3 colunas, ~11 linhas
    cw = xrange/3; ch = yrange/11
    c1 = (x0, x0+cw*1.05, y1-ch*1.05, y1+ch*0.05)
    c2 = (x0, x0+cw*2.1,  y1-ch*2.1,  y1+ch*0.05)

fig, axes = plt.subplots(1, 2, figsize=(22, 8))
fig.patch.set_facecolor('#0d0d1a')
fig.suptitle("VIGA LATERAL (LV) — Cards do STOG: Face A + Face B\n"
             "Cada card mostra a lateral da viga com sarrafos empilhados, altura total, cotas",
             fontsize=11, color='white')
if ex_lv:
    render_crop(doc_lv, axes[0], "1 Viga Lateral — Face A + B zoom", *c1)
    render_crop(doc_lv, axes[1], "2 Vigas Laterais — contexto", *c2)
plt.tight_layout()
plt.savefig(str(OUT_DIR / "STOG_LV_cards_zoom.png"), dpi=150, bbox_inches='tight', facecolor='#0d0d1a')
plt.close()
print("  -> STOG_LV_cards_zoom.png")

# ---- LJ: planta baixa completa (ja e o formato correto) ----
print("Renderizando LJ zoom...")
lj_path = STOG_DIR / "STOG - NIK SUNSET - 12° PAV.- LJ - R00_R2018_ASCII_ODA.dxf"
doc_lj = ezdxf.readfile(str(lj_path))
ex_lj = get_real_extents(doc_lj, entity_types={'LWPOLYLINE','LINE','HATCH'})
print(f"  LJ extents: {ex_lj}")

fig, ax = plt.subplots(figsize=(16, 10))
fig.patch.set_facecolor('#0d0d1a')
if ex_lj:
    x0,x1,y0,y1 = ex_lj
    render_crop(doc_lj, ax,
        "LAJE (LJ) — Planta baixa do pavimento STOG\n"
        "Vista de cima: posicao de cada laje no edificio + pontaletes + linhas de sarrafo",
        x0, x1, y0, y1, padding_pct=0.01)
plt.tight_layout()
plt.savefig(str(OUT_DIR / "STOG_LJ_zoom.png"), dpi=150, bbox_inches='tight', facecolor='#0d0d1a')
plt.close()
print("  -> STOG_LJ_zoom.png")

print("\nDone.")
