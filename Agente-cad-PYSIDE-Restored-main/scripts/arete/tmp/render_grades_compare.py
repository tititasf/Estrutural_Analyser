"""
Renderiza N4 GRADES (gerado) vs N2 (recorte humano) para P1 e P13.
Coordenadas N2 verificadas por inspeção de layers SARR_2.2x7.
"""
import ezdxf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

N2_DIR = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-2_Triagem/recortes_reversos/ALIMONTI - PARAISO - 13° PAV.- PL - R00"
N4_DIR = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-6_Execucao_CAD"

# N2: SARR_2.2x7 zona GRADES
# P1:  X=[5046,5659] Y=[12190,12450]
# P13: X=[5014,5663] Y=[8744,9004]

PAD = 40
CASOS = [
    ("P1",
     f"{N4_DIR}/PL_GRADES_preview_P1.dxf",
     f"{N2_DIR}/PIL_P1_motor_178111335049.dxf",
     (-20, 210), (-60, 310),
     (5046-PAD, 5659+PAD), (12190-60, 12450+PAD)),
    ("P13",
     f"{N4_DIR}/PL_GRADES_preview_P13.dxf",
     f"{N2_DIR}/PIL_P13_motor_178111335262.dxf",
     (-20, 230), (-60, 310),
     (5014-PAD, 5663+PAD), (8744-60, 9004+PAD)),
]


def extract_dims(dxf_path):
    doc = ezdxf.readfile(dxf_path)
    dims = []
    for e in doc.modelspace().query("DIMENSION"):
        m = e.get_measurement()
        try:
            txt = e.dxf.text
        except Exception:
            txt = ""
        dims.append((round(m, 1), txt))
    return sorted(dims)


def extract_n2_dims(dxf_path, x_min=4900):
    """Extrai cotas do N2 na zona GRADES (X > x_min)."""
    doc = ezdxf.readfile(dxf_path)
    dims = []
    for e in doc.modelspace().query("DIMENSION"):
        try:
            m = e.get_measurement()
            # tenta pegar posição da cota
            try:
                px = e.dxf.defpoint.x
            except Exception:
                px = 0
            if px > x_min:
                try:
                    txt = e.dxf.text
                except Exception:
                    txt = ""
                dims.append((round(m, 1), txt, round(px, 0)))
        except Exception:
            pass
    return sorted(dims)


fig, axes = plt.subplots(len(CASOS), 2, figsize=(18, 7 * len(CASOS)))

for row, (nome, n4_path, n2_path, xlim4, ylim4, xlim2, ylim2) in enumerate(CASOS):
    for col, (path, title, xlim, ylim) in enumerate([
        (n4_path, f"N4 GRADES {nome}", xlim4, ylim4),
        (n2_path, f"N2 recorte {nome} (zona GRADES)", xlim2, ylim2),
    ]):
        ax = axes[row][col]
        try:
            doc = ezdxf.readfile(path)
            ctx = RenderContext(doc)
            out = MatplotlibBackend(ax)
            Frontend(ctx, out).draw_layout(doc.modelspace(), finalize=True)
        except Exception as exc:
            ax.text(0.5, 0.5, str(exc), transform=ax.transAxes,
                    ha='center', va='center', color='red', fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)

    dims_n4 = extract_dims(n4_path)
    dims_n2 = extract_n2_dims(n2_path)
    print(f"\n[{nome}] N4 cotas: {dims_n4}")
    print(f"[{nome}] N2 cotas GRADES: {dims_n2}")

plt.tight_layout()
out_png = "scripts/arete/tmp/grades_compare.png"
plt.savefig(out_png, dpi=150)
print(f"\nOK -> {out_png}")
