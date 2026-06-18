"""Detalhe do N4 GRADES para P1, P3, P9, P11, P13, P15 — 2 linhas × 3 colunas."""
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

N4_DIR = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD"

ITEMS = ["P1", "P3", "P9", "P11", "P13", "P15"]

fig, axes = plt.subplots(2, 3, figsize=(18, 12))

for idx, item in enumerate(ITEMS):
    row, col = divmod(idx, 3)
    ax = axes[row][col]
    path = f"{N4_DIR}/PL_GRADES_preview_{item}.dxf"
    try:
        doc = ezdxf.readfile(path)
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(doc.modelspace(), finalize=True)

        # extrai cotas
        dims = sorted(e.get_measurement()
                      for e in doc.modelspace().query("DIMENSION")
                      if e.get_measurement() > 0)
        subtitle = " | ".join(f"{d:.1f}" for d in dims)
    except Exception as exc:
        subtitle = str(exc)
    ax.set_title(f"{item}   [{subtitle}]", fontsize=8)
    ax.set_xlim(-20, 250)
    ax.set_ylim(-55, 310)

plt.tight_layout()
out = "scripts/arete/tmp/grades_n4_detail.png"
plt.savefig(out, dpi=150)
print(f"OK -> {out}")
