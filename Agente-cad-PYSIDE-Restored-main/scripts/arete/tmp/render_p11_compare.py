"""One-off: renderiza N4 (gerado) vs N2 (recorte humano) do P11, zona CIMA,
lado a lado, para validar o desvio de colisão grade x parafuso (23|23|28|28)."""
import ezdxf
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

N4 = "scripts/arete/tmp/PIL_13_PAV_P11/Fase-6_Execucao_CAD/PL_preview_P11.dxf"
N2 = ("../DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/"
      "ALIMONTI - PARAISO - 13° PAV.- PL - R00/PIL_P11_motor_178111335224.dxf")

fig, axes = plt.subplots(1, 2, figsize=(16, 8))

configs = (
    (axes[0], N4, "N4 (gerado) - zona CIMA", (-150, 150), (-80, 160)),
    (axes[1], N2, "N2 (humano STOG) - zona CIMA", (7600, 7900), (10180, 10420)),
)
for ax, path, title, xlim, ylim in configs:
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    ctx = RenderContext(doc)
    out = MatplotlibBackend(ax)
    Frontend(ctx, out).draw_layout(msp, finalize=True)
    ax.set_title(title)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)

plt.tight_layout()
plt.savefig("scripts/arete/tmp/P11_cima_compare.png", dpi=150)
print("OK -> scripts/arete/tmp/P11_cima_compare.png")
