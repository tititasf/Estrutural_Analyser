#!/usr/bin/env python3
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import ezdxf, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

dxf = ezdxf.readfile(r'D:\Agente-cad-PYSIDE\ANALISE_LV\combined\combined_v10_ALL.dxf')
msp = dxf.modelspace()
fig, ax = plt.subplots(figsize=(28, 6), facecolor='black')
ax.set_facecolor('black')
ax.set_xlim(-100, 12*1600+100)
ax.set_ylim(-2200, 200)
ctx = RenderContext(dxf)
out = MatplotlibBackend(ax)
Frontend(ctx, out).draw_layout(msp, finalize=True)
out_path = r'D:\Agente-cad-PYSIDE\ANALISE_LV\preview_v10_row1.png'
fig.savefig(out_path, dpi=110, facecolor='black', bbox_inches='tight')
plt.close()
print(f'Salvo: {out_path}')
