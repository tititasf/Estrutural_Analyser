"""One-off: renderiza N4 (gerado) vs N2 (recorte humano) do P13, zona CIMA,
para investigar o bug "soma dos segmentos da cota de divisao != cota total"."""
import ezdxf
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

N4 = "../DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD/PL_CIMA_preview_P13.dxf"
N2 = ("../DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/"
      "ALIMONTI - PARAISO - 13° PAV.- PL - R00/PIL_P13_motor_178111335262.dxf")

fig, axes = plt.subplots(1, 2, figsize=(16, 8))

configs = (
    (axes[0], N4, "N4 (gerado) - zona CIMA - P13", None, None),
    (axes[1], N2, "N2 (humano STOG) - zona CIMA - P13", (4490, 4720), (9030, 9300)),
)
for ax, path, title, xlim, ylim in configs:
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True)
    ax.set_title(title)
    if xlim:
        ax.set_xlim(*xlim)
    if ylim:
        ax.set_ylim(*ylim)

plt.tight_layout()
plt.savefig("scripts/arete/tmp/P13_cima_compare.png", dpi=150)
print("OK -> scripts/arete/tmp/P13_cima_compare.png")
