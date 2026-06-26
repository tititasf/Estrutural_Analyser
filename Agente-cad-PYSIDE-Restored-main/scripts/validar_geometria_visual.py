#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
validar_geometria_visual.py — Comparação visual + estrutural STOG vs Gerado.

Para cada tipo (PL, LV, FV, LJ):
  1. Renderiza imagem lado a lado (STOG | Gerado)
  2. Compara layers presentes
  3. Compara entity types e contagens
  4. Compara extents (bounding box)
  5. Lista divergências

Output: /tmp/validacao_visual/ com PNGs + JSON de divergências
"""

import json
import sys
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

# ── Configuração ──────────────────────────────────────────────────────────────
OBRA_DIR = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_21")
STOG_DIR = OBRA_DIR / "Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa"
GERADO_DIR = OBRA_DIR / "Fase-6_Execucao_CAD"
OUT_DIR = Path("D:/Agente-cad-PYSIDE/validacao_visual")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAV = "12 PAV"

PARES = [
    ("PL", "STOG - NIK SUNSET - 12º PAVIMENTO - PL - R00_R2018_ASCII_ODA.dxf", "PL_gerado.dxf"),
    ("LV", "STOG - NIK SUNSET - 12º PAVIMENTO - LV - R00_R2018_ASCII_ODA.dxf", "LV_gerado.dxf"),
    ("FV", "STOG - NIK SUNSET - 12° PAV.- FV - R00_R2018_ASCII_ODA.dxf",       "FV_gerado.dxf"),
    ("LJ", "STOG - NIK SUNSET - 12° PAV.- LJ - R00_R2018_ASCII_ODA.dxf",       "LJ_gerado.dxf"),
]


def entity_summary(doc):
    """Conta entidades por tipo no modelspace."""
    msp = doc.modelspace()
    counts = {}
    for e in msp:
        t = e.dxftype()
        counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items()))


def layer_summary(doc):
    """Lista layers e contagem de entidades."""
    msp = doc.modelspace()
    layers = {}
    for e in msp:
        lyr = getattr(e.dxf, 'layer', '0')
        layers[lyr] = layers.get(lyr, 0) + 1
    return dict(sorted(layers.items(), key=lambda x: -x[1]))


def get_extents(doc):
    """Calcula bounding box do modelspace."""
    msp = doc.modelspace()
    xs, ys = [], []
    for e in msp:
        try:
            if e.dxftype() == 'LINE':
                xs += [e.dxf.start.x, e.dxf.end.x]
                ys += [e.dxf.start.y, e.dxf.end.y]
            elif e.dxftype() in ('TEXT', 'MTEXT', 'INSERT'):
                xs.append(e.dxf.insert.x)
                ys.append(e.dxf.insert.y)
            elif e.dxftype() == 'LWPOLYLINE':
                pts = list(e.get_points())
                xs += [p[0] for p in pts]
                ys += [p[1] for p in pts]
            elif e.dxftype() == 'DIMENSION':
                xs.append(e.dxf.defpoint.x)
                ys.append(e.dxf.defpoint.y)
        except Exception:
            pass
    if not xs:
        return None
    return {
        'xmin': min(xs), 'xmax': max(xs),
        'ymin': min(ys), 'ymax': max(ys),
        'width_cm': (max(xs) - min(xs)) / 1.0,
        'height_cm': (max(ys) - min(ys)) / 1.0,
    }


def render_dxf(doc, ax, title):
    """Renderiza DXF num eixo matplotlib."""
    try:
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        frontend = Frontend(ctx, out)
        frontend.draw_layout(doc.modelspace(), finalize=True)
        ax.set_title(title, fontsize=9, pad=4)
    except Exception as ex:
        ax.text(0.5, 0.5, f'Render error:\n{ex}', transform=ax.transAxes,
                ha='center', va='center', fontsize=8, color='red')
        ax.set_title(title, fontsize=9)


def compare_layers(stog_layers, gen_layers):
    """Compara layers: missing, extra, delta count."""
    stog_set = set(stog_layers.keys())
    gen_set = set(gen_layers.keys())
    missing = stog_set - gen_set      # no STOG mas não no gerado
    extra   = gen_set - stog_set      # no gerado mas não no STOG
    common  = stog_set & gen_set
    delta   = {l: (stog_layers[l], gen_layers[l]) for l in common
               if abs(stog_layers[l] - gen_layers[l]) / max(stog_layers[l], 1) > 0.20}
    return missing, extra, delta


def print_section(title):
    print(f"\n{'-'*60}")
    print(f"  {title}")
    print(f"{'-'*60}")


# ── Main ──────────────────────────────────────────────────────────────────────
all_results = {}

for tipo, stog_name, gen_name in PARES:
    stog_path = STOG_DIR / stog_name
    gen_path  = GERADO_DIR / gen_name

    print_section(f"{tipo}: {stog_name[:40]}...")

    if not stog_path.exists():
        print(f"  ⚠️  STOG não encontrado: {stog_path}")
        continue
    if not gen_path.exists():
        print(f"  ⚠️  Gerado não encontrado: {gen_path}")
        continue

    # Carregar
    print(f"  Carregando STOG ({stog_path.stat().st_size//1024}KB)...")
    doc_stog = ezdxf.readfile(str(stog_path))
    print(f"  Carregando Gerado ({gen_path.stat().st_size//1024}KB)...")
    doc_gen  = ezdxf.readfile(str(gen_path))

    # Summaries estruturais
    ent_stog = entity_summary(doc_stog)
    ent_gen  = entity_summary(doc_gen)
    lyr_stog = layer_summary(doc_stog)
    lyr_gen  = layer_summary(doc_gen)
    ext_stog = get_extents(doc_stog)
    ext_gen  = get_extents(doc_gen)

    # Comparação layers
    missing_layers, extra_layers, delta_layers = compare_layers(lyr_stog, lyr_gen)

    # Imprimir análise
    print(f"\n  [ENTITIES]")
    all_types = sorted(set(ent_stog) | set(ent_gen))
    for t in all_types:
        s = ent_stog.get(t, 0)
        g = ent_gen.get(t, 0)
        mark = "✅" if abs(s-g)/max(s,1) < 0.15 else ("⚠️" if abs(s-g)/max(s,1) < 0.50 else "❌")
        print(f"    {mark} {t:20s}  STOG={s:5d}  Gerado={g:5d}")

    print(f"\n  [LAYERS] STOG={len(lyr_stog)} | Gerado={len(lyr_gen)}")
    if missing_layers:
        print(f"    ❌ Layers no STOG ausentes no gerado: {sorted(missing_layers)}")
    if extra_layers:
        print(f"    ℹ️  Layers extras no gerado (não no STOG): {sorted(extra_layers)}")
    if delta_layers:
        print(f"    ⚠️  Layers com delta > 20%:")
        for l, (s, g) in delta_layers.items():
            print(f"       {l}: STOG={s} Gerado={g}")
    if not missing_layers and not extra_layers and not delta_layers:
        print(f"    ✅ Layers compatíveis")

    print(f"\n  [EXTENTS (bounding box)]")
    if ext_stog and ext_gen:
        dw = abs(ext_stog['width_cm'] - ext_gen['width_cm'])
        dh = abs(ext_stog['height_cm'] - ext_gen['height_cm'])
        print(f"    STOG:   {ext_stog['width_cm']:.0f} × {ext_stog['height_cm']:.0f} cm")
        print(f"    Gerado: {ext_gen['width_cm']:.0f} × {ext_gen['height_cm']:.0f} cm")
        print(f"    Delta W={dw:.0f}cm  H={dh:.0f}cm")
    else:
        print(f"    STOG extents: {ext_stog}")
        print(f"    Gerado extents: {ext_gen}")

    # Render visual lado a lado
    print(f"\n  [RENDER] Gerando imagem visual...")
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    fig.suptitle(f"STOG vs Gerado — {tipo} — Obra_TREINO_21 (12 PAV)", fontsize=12, fontweight='bold')

    render_dxf(doc_stog, axes[0], f"STOG ORIGINAL\n{stog_name[:50]}\n{sum(ent_stog.values())} entidades | {len(lyr_stog)} layers")
    render_dxf(doc_gen,  axes[1], f"PIPELINE GERADO\n{gen_name}\n{sum(ent_gen.values())} entidades | {len(lyr_gen)} layers")

    plt.tight_layout()
    out_img = OUT_DIR / f"{tipo}_comparacao.png"
    plt.savefig(str(out_img), dpi=120, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  ✅ Imagem salva: {out_img}")

    # Salvar dados
    all_results[tipo] = {
        'entities_stog': ent_stog,
        'entities_gen': ent_gen,
        'layers_stog_count': len(lyr_stog),
        'layers_gen_count': len(lyr_gen),
        'missing_layers': sorted(missing_layers),
        'extra_layers': sorted(extra_layers),
        'extents_stog': ext_stog,
        'extents_gen': ext_gen,
    }

# Salvar JSON completo
out_json = OUT_DIR / "comparacao_estrutural.json"
with open(str(out_json), 'w', encoding='utf-8') as f:
    json.dump(all_results, f, indent=2, ensure_ascii=False)

print(f"\n{'='*60}")
print(f"VALIDACAO CONCLUIDA")
print(f"  Imagens: {OUT_DIR}/*.png")
print(f"  Dados:   {out_json}")
print(f"{'='*60}\n")
