"""
Engenharia reversa: le um DXF de pilares (PL) real e extrai estrutura.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import ezdxf
from collections import Counter, defaultdict

DXF = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/ALIMONTI - PARAISO - 1° PAV.- PL - R00.dxf"

print(f"Lendo: {DXF}")
doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

# 1. Tipos de entidades
tipos = Counter(e.dxftype() for e in msp)
print("\n--- Entidades no modelspace ---")
for t, n in sorted(tipos.items(), key=lambda x: -x[1]):
    print(f"  {t:20s}: {n}")

# 2. Layers
layers = defaultdict(list)
for e in msp:
    if hasattr(e.dxf, 'layer'):
        layers[e.dxf.layer].append(e.dxftype())

print("\n--- Layers e seus tipos ---")
for layer in sorted(layers.keys()):
    c = Counter(layers[layer])
    print(f"  {layer:30s}: {dict(c)}")

# 3. Blocos INSERT
inserts = [e for e in msp if e.dxftype() == 'INSERT']
print(f"\n--- INSERTs ({len(inserts)} total) ---")
blocos = Counter(e.dxf.name for e in inserts)
for b, n in sorted(blocos.items(), key=lambda x: -x[1])[:30]:
    print(f"  {b:30s}: {n}x")

# 4. Textos (nomes dos pilares)
textos = [e for e in msp if e.dxftype() in ('TEXT', 'MTEXT')]
print(f"\n--- Textos ({len(textos)}) amostras ---")
for t in textos[:30]:
    txt = t.dxf.text if t.dxftype() == 'TEXT' else t.text
    pos = t.dxf.insert if hasattr(t.dxf, 'insert') else '?'
    layer = t.dxf.layer if hasattr(t.dxf, 'layer') else '?'
    print(f"  [{layer}] '{txt}' @ {pos}")

# 5. Dimensoes (DIMENSION)
dims = [e for e in msp if e.dxftype() == 'DIMENSION']
print(f"\n--- DIMENSIONs ({len(dims)}) amostras ---")
for d in dims[:10]:
    print(f"  layer={d.dxf.layer}  texto={getattr(d.dxf, 'text', '')}  "
          f"defpt={getattr(d.dxf, 'defpoint', '?')}")

# 6. LINEs por layer
lines = [e for e in msp if e.dxftype() == 'LINE']
print(f"\n--- LINEs por layer ({len(lines)} total) ---")
lines_by_layer = Counter(e.dxf.layer for e in lines)
for l, n in sorted(lines_by_layer.items(), key=lambda x: -x[1])[:15]:
    print(f"  {l:30s}: {n}")
