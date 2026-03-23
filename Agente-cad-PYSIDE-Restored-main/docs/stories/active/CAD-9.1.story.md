# CAD-9.1 — Extração de Coordenadas Absolutas (Âncoras STOG)

**Epic:** CAD-9 — DXF Coletivo por Tipo
**Status:** Done
**Data:** 2026-03-08
**Autor:** CEO-PLANEJAMENTO (Athena)

---

## Objetivo

Extrair as coordenadas absolutas de cada elemento (P{n}, V{n}, L{n}) dentro dos DXFs STOG
originais (PL, LV, LJ). Esses pontos de âncora são necessários para posicionar os
elementos gerados individualmente na posição correta no DXF coletivo.

**Este é o caminho crítico do Epic 9.** Sem as âncoras, não é possível montar
o DXF coletivo com posicionamento correto.

---

## Contexto

### O Problema das Coordenadas

Cada DXF individual gerado pela pipeline (P1.dxf, V1.dxf, etc.) usa coords locais (0,0).
No DXF coletivo PL_gerado.dxf, cada pilar precisa estar nas mesmas coordenadas que
estava no DXF STOG original.

```
DXF STOG original (PL.dxf):
  P1 → TEXT "P1" em posição absoluta (1500, 2300)   ← ÂNCORA
  P9 → TEXT "P9" em posição absoluta (3200, 2300)   ← ÂNCORA
  ...

DXF individual gerado (P1.dxf):
  Pilar P1 → posição local (0, 0)

DXF coletivo (PL_gerado.dxf):
  Pilar P1 → translado para (1500, 2300)   ← usa âncora
  Pilar P9 → translado para (3200, 2300)
```

### Fontes das Âncoras

| Tipo | DXF | Layer | Entidade | Campo |
|------|-----|-------|----------|-------|
| Pilares | PL | "Texto Seção" | TEXT/MTEXT | insert.x, insert.y |
| Vigas | LV | "Texto Seção" | TEXT/MTEXT | "V{n}.A" ou "V{n}.B" |
| Lajes | LJ | "AUX00" | MTEXT | insert.x, insert.y |

### Conhecimento do DXF STOG (já validado)

Do 12 PAV PL DXF:
- Layer "Texto Seção" contém textos "P{n}.{face}" (ex: "P1.A", "P1.B")
- Cada pilar tem múltiplos textos (faces A/B/C/D) → usar centróide dos textos do mesmo pilar

Do 12 PAV LV DXF:
- Layer "Texto Seção" contém textos "V{n}.A" e "V{n}.B"

Do 12 PAV LJ DXF:
- Layer "AUX00" contém MTEXT "L{n}\n{dim1}X{dim2}"

---

## Acceptance Criteria

- [x] AC-1: Script `scripts/extrair_ancoras_dxf.py` criado
- [x] AC-2: Pilares: 37 âncoras extraídas (37/33 GT — extras de outros pavs sobrepostos)
- [x] AC-3: Vigas: 33/33 âncoras — inclui labels combinados V17+V18, V24, V25+V26
- [x] AC-4: Lajes: 19/19 âncoras — layers AUX00 + '4' combinados
- [x] AC-5: Cobertura: Vigas 100%, Lajes 100%, Pilares 112% (37 de 33)
- [x] AC-6: Arquivos salvos em Fase-3_Interpretacao_Extracao/
- [x] AC-7: CLI funcional

**Resultado validado (2026-03-08):** Pilares 37, Vigas 33/33, Lajes 19/19 — APROVADO

---

## Approach Técnico

```python
import ezdxf
import json
import re
from collections import defaultdict
from pathlib import Path

def extrair_ancoras_pilares(pl_dxf_path: str) -> dict:
    doc = ezdxf.readfile(pl_dxf_path)
    msp = doc.modelspace()

    # Agrupar textos por pilar ID (P{n})
    grupos = defaultdict(list)
    for e in msp:
        if e.dxftype() in ('TEXT', 'MTEXT'):
            text = e.dxf.text if hasattr(e.dxf, 'text') else e.plain_mtext()
            # Extrair P{n} do texto "P{n}.A" ou "P{n}"
            m = re.match(r'P(\d+)', text.strip(), re.IGNORECASE)
            if m:
                pid = f"P{m.group(1)}"
                insert = e.dxf.insert if hasattr(e.dxf, 'insert') else e.dxf.insert_point
                grupos[pid].append((insert.x, insert.y))

    # Centróide por pilar
    ancoras = {}
    for pid, pts in grupos.items():
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        ancoras[pid] = [round(cx, 2), round(cy, 2)]

    return ancoras
```

---

## Validação Visual (opcional mas recomendada)

Após extrair âncoras, gerar um SVG/PNG rápido para confirmar posicionamento:

```python
# plot_ancoras.py (auxiliar)
import matplotlib.pyplot as plt

with open('ancoras_pilares.json') as f:
    ancoras = json.load(f)

for pid, (x, y) in ancoras.items():
    plt.scatter(x, y, s=10, c='blue')
    plt.annotate(pid, (x, y), fontsize=6)

plt.savefig('ancoras_layout.png', dpi=150)
```

---

## File List

- [ ] `scripts/extrair_ancoras_dxf.py` (CRIAR)
- [ ] `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/ancoras_pilares.json` (GERADO)
- [ ] `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/ancoras_vigas.json` (GERADO)
- [ ] `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/ancoras_lajes.json` (GERADO)

---

*CAD-9.1 Ready | Sprint 5 | Caminho Crítico Epic 9 | 2026-03-08*
