"""
Extrai dados de cada pilar do DXF real (PL) usando ezdxf.
Identifica nome, comprimento, largura, altura por pilar.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import ezdxf
import math
from collections import defaultdict

DXF = "D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1/Fase-1_Ingestao/Projetos_Finalizados_para_Engenharia_Reversa/ALIMONTI - PARAISO - 1° PAV.- PL - R00.dxf"

doc = ezdxf.readfile(DXF)
msp = doc.modelspace()

# ── 1. Coleta textos de NOMENCLATURA (nomes dos pilares) ──────────────────────
nomes = []
for e in msp:
    if e.dxftype() in ('TEXT', 'MTEXT') and e.dxf.layer == 'NOMENCLATURA':
        txt = e.dxf.text.strip() if e.dxftype() == 'TEXT' else e.text.strip()
        pos = e.dxf.insert
        nomes.append({'nome': txt, 'x': pos[0], 'y': pos[1]})

print(f"Pilares encontrados (NOMENCLATURA): {len(nomes)}")
for n in sorted(nomes, key=lambda x: x['nome'])[:20]:
    print(f"  {n['nome']:20s}  @ ({n['x']:.1f}, {n['y']:.1f})")

# ── 2. Coleta linhas do layer Painéis (contorno dos pilares) ─────────────────
paineis_lines = [e for e in msp if e.dxftype() == 'LINE' and e.dxf.layer == 'Painéis']
lwpolys = [e for e in msp if e.dxftype() == 'LWPOLYLINE' and e.dxf.layer == 'Painéis']
print(f"\nLayer Painéis: {len(paineis_lines)} LINEs + {len(lwpolys)} LWPOLYLINEs")

# ── 3. Para cada pilar, encontra as dimensões pelas cotas mais próximas ───────
dims = [e for e in msp if e.dxftype() == 'DIMENSION' and e.dxf.layer == 'COTA']
print(f"Cotas (COTA): {len(dims)}")

# ── 4. Pega textos de "Texto Seção" — contem comp x larg do pilar ─────────────
secoes = []
for e in msp:
    if e.dxftype() in ('TEXT', 'MTEXT') and e.dxf.layer in ('Texto Seção', 'TEXTO_GERAL', 'texto'):
        txt = e.dxf.text.strip() if e.dxftype() == 'TEXT' else e.text.strip()
        pos = e.dxf.insert if hasattr(e.dxf, 'insert') else None
        if txt:
            secoes.append({'texto': txt, 'pos': pos, 'layer': e.dxf.layer})

print(f"\nTextos Seção/Geral: {len(secoes)}")
for s in secoes[:40]:
    print(f"  [{s['layer']}] '{s['texto']}'  @ {s['pos']}")

# ── 5. Textos gerais — pode conter dados de altura, pavimento ─────────────────
print("\nTodos os textos únicos (amostra):")
todos = set()
for e in msp:
    if e.dxftype() == 'TEXT':
        t = e.dxf.text.strip()
        if t and t not in todos:
            todos.add(t)
for t in sorted(todos)[:60]:
    print(f"  '{t}'")
