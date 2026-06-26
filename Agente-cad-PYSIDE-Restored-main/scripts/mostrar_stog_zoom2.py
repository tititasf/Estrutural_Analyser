#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from pathlib import Path
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

STOG_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_21/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa")
OUT_DIR = Path("D:/Agente-cad-PYSIDE/validacao_visual")

def get_extents(doc, types=None):
    xs, ys = [], []
    for e in doc.modelspace():
        if types and e.dxftype() not in types:
            continue
        try:
            t = e.dxftype()
            if t == 'LWPOLYLINE':
                pts = list(e.get_points())
                xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
            elif t == 'LINE':
                xs += [e.dxf.start.x, e.dxf.end.x]; ys += [e.dxf.start.y, e.dxf.end.y]
            elif t in ('TEXT','MTEXT','INSERT'):
                xs.append(e.dxf.insert.x); ys.append(e.dxf.insert.y)
        except: pass
    if not xs: return None
    return min(xs), max(xs), min(ys), max(ys)

def render_crop(doc, ax, title, x0, x1, y0, y1, pad=0.02):
    px = (x1-x0)*pad; py = (y1-y0)*pad
    try:
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(doc.modelspace(), finalize=True)
        ax.set_xlim(x0-px, x1+px); ax.set_ylim(y0-py, y1+py)
        ax.set_aspect('equal'); ax.set_title(title, fontsize=9, color='white', pad=4)
        ax.set_facecolor('#1a1a2e')
    except Exception as ex:
        ax.text(0.5, 0.5, str(ex), transform=ax.transAxes, ha='center', va='center', color='red', fontsize=7)

# Use glob to handle special chars in filenames
files = {p.name[:40]: p for p in STOG_DIR.glob('*ODA.dxf')}
for k,v in files.items(): print(k[:50])

pl_file = next(STOG_DIR.glob('*12*PAVIMENTO*PL*ODA.dxf'), None)
lv_file = next(STOG_DIR.glob('*12*PAVIMENTO*LV*ODA.dxf'), None)
fv_file = next(STOG_DIR.glob('*12*FV*ODA.dxf'), None)
lj_file = next(STOG_DIR.glob('*12*LJ*ODA.dxf'), None)

print(f"PL: {pl_file}")
print(f"LV: {lv_file}")
print(f"FV: {fv_file}")
print(f"LJ: {lj_file}")

# ── FV: Viga Fundo cards ─────────────────────────────────────────────────────
print("\nFV zoom...")
doc = ezdxf.readfile(str(fv_file))
ex = get_extents(doc, {'LWPOLYLINE','LINE','HATCH','TEXT','MTEXT'})
print(f"  FV extents: {ex}")
if ex:
    x0,x1,y0,y1 = ex
    xr=x1-x0; yr=y1-y0
    cw=xr/3; ch=yr/3
    # 1 card (bottom-left, first viga)
    card1 = (x0, x0+cw, y0, y0+ch)

fig, axes = plt.subplots(1, 2, figsize=(22, 8), facecolor='#0a0a14')
fig.suptitle("VIGA FUNDO (FV) — STOG 12 PAV — NIK SUNSET\n"
             "Card: vista de baixo da viga | compensado + sarrafos de travamento + largura do fundo",
             color='white', fontsize=11)
render_crop(doc, axes[0], "1 Viga Fundo — zoom total", *card1)
render_crop(doc, axes[1], "Todos os cards FV", x0, x1, y0, y1)
plt.tight_layout()
plt.savefig(str(OUT_DIR/"STOG_FV_zoom_real.png"), dpi=150, bbox_inches='tight', facecolor='#0a0a14')
plt.close(); print("  -> STOG_FV_zoom_real.png")

# ── PL: Pilar cards ──────────────────────────────────────────────────────────
print("\nPL zoom...")
doc = ezdxf.readfile(str(pl_file))
ex = get_extents(doc, {'LWPOLYLINE','LINE','HATCH','TEXT','MTEXT'})
print(f"  PL extents: {ex}")
if ex:
    x0,x1,y0,y1 = ex
    xr=x1-x0; yr=y1-y0
    cw=xr/4; ch=yr/9
    # 1 card (top-right, ultimo pilar da primeira linha - geralmente mais completo)
    c1 = (x1-cw, x1, y1-ch, y1)
    # 2x2
    c4 = (x0, x0+cw*2, y1-ch*2, y1)

fig, axes = plt.subplots(1, 2, figsize=(22, 10), facecolor='#0a0a14')
fig.suptitle("PILAR (PL) — STOG 12 PAV — NIK SUNSET\n"
             "Card: secao transversal do pilar (B x H) + faces A/B/C/D + paineis + cotas + carimbo",
             color='white', fontsize=11)
render_crop(doc, axes[0], "1 Pilar isolado — zoom", *c1)
render_crop(doc, axes[1], "Grade 2x2 pilares — contexto", *c4)
plt.tight_layout()
plt.savefig(str(OUT_DIR/"STOG_PL_zoom_real.png"), dpi=150, bbox_inches='tight', facecolor='#0a0a14')
plt.close(); print("  -> STOG_PL_zoom_real.png")

# ── LV: Viga Lateral cards ───────────────────────────────────────────────────
print("\nLV zoom...")
doc = ezdxf.readfile(str(lv_file))
ex = get_extents(doc, {'LWPOLYLINE','LINE','HATCH','TEXT','MTEXT'})
print(f"  LV extents: {ex}")
if ex:
    x0,x1,y0,y1 = ex
    xr=x1-x0; yr=y1-y0
    cw=xr/3; ch=yr/11
    c1 = (x0, x0+cw, y1-ch, y1)
    c2 = (x0, x0+cw*1.5, y1-ch*3, y1)

fig, axes = plt.subplots(1, 2, figsize=(24, 8), facecolor='#0a0a14')
fig.suptitle("VIGA LATERAL (LV) — STOG 12 PAV — NIK SUNSET\n"
             "Card: Face A (frente) + Face B (tras) + altura lateral + sarrafos + escoras + REAP",
             color='white', fontsize=11)
render_crop(doc, axes[0], "1 Viga Lateral — Face A+B zoom", *c1)
render_crop(doc, axes[1], "3 Vigas Laterais — contexto de grade", *c2)
plt.tight_layout()
plt.savefig(str(OUT_DIR/"STOG_LV_zoom_real.png"), dpi=150, bbox_inches='tight', facecolor='#0a0a14')
plt.close(); print("  -> STOG_LV_zoom_real.png")

# ── LJ: Laje planta baixa ────────────────────────────────────────────────────
print("\nLJ zoom...")
doc = ezdxf.readfile(str(lj_file))
ex = get_extents(doc, {'LWPOLYLINE','LINE','HATCH'})
print(f"  LJ extents: {ex}")
if ex:
    x0,x1,y0,y1 = ex

fig, ax = plt.subplots(figsize=(16, 10), facecolor='#0a0a14')
fig.suptitle("LAJE (LJ) — STOG 12 PAV — NIK SUNSET\n"
             "Planta baixa do pavimento: posicao real de cada laje no edificio + pontaletes + sarrafos de apoio",
             color='white', fontsize=11)
if ex: render_crop(doc, ax, "Planta completa", x0,x1,y0,y1)
plt.tight_layout()
plt.savefig(str(OUT_DIR/"STOG_LJ_zoom_real.png"), dpi=150, bbox_inches='tight', facecolor='#0a0a14')
plt.close(); print("  -> STOG_LJ_zoom_real.png")

print("\nDone.")
