# CAD-7.2 — Extração MEIO_PONT por Laje (Pontaletes e Meio Pontaletes)

**Epic:** CAD-7 — Assembly Layers (PL DXF)
**Status:** Done
**Data:** 2026-03-08
**Autor:** aios-dev

---

## Objetivo

Extrair contagem de PONTALETE e MEIO PONTALETE por laje a partir do DXF PL.
O layer `MEIO_PONT` contém 228 INSERTs distribuídos na planta baixa (view espacial),
não nas seções de pilares. Requer matching com geometria de lajes.

---

## Contexto

### Descoberta CAD-7.1

Durante a análise de `MEIO_PONT`:
- **228 INSERTs**: 120 PONTALETE + 108 MEIO PONTALETE
- **Coordenadas**: X=1020-6123, Y=8601-15717 (espaço planta baixa)
- **Distribuição**: spread nas faixas entre filas de pilares (entre lajes)
- **Nearest ao P1.A**: dist=651 (fora do raio 500) → não per-pilar

**Conclusão**: MEIO_PONT estão no espaço das lajes, não das seções de pilares.
Contagem por pilar não faz sentido — contagem por laje é o modelo correto.

### Prerequisitos

- `lajes_poligono.json` com coordenadas de vértices das lajes no DXF PL
- OU: usar bounding box dos pilares para delimitar faixas de laje

---

## Acceptance Criteria

- [ ] AC-1: Script `extrair_meioPont_pl.py` criado
- [ ] AC-2: Para cada laje, contar PONTALETE e MEIO_PONTALETE dentro do polígono
- [ ] AC-3: Output `lajes_meioPont.json` em Fase-3_Interpretacao_Extracao/Lajes/
- [ ] AC-4: Integração em motor_fase4.py — campo `pontaletes` em LajeFase4
- [ ] AC-5: Cobertura >= 80% das lajes com pelo menos 1 pontalete

---

## Approach Técnico

### Opção A: Polígonos das Lajes (preferida)

```python
# lajes_poligono.json: {L1: [[x1,y1],[x2,y2],...], ...}
from shapely.geometry import Point, Polygon

for insert in meio_pont_inserts:
    pt = Point(insert.dxf.insert.x, insert.dxf.insert.y)
    for laje_id, poly_pts in lajes_poligono.items():
        poly = Polygon(poly_pts)
        if poly.contains(pt):
            laje_counts[laje_id][insert.dxf.name] += 1  # PONTALETE ou MEIO PONTALETE
```

### Opção B: Grid de Pilares (fallback)

Usar bounding boxes de grupos de pilares para aproximar faixas de laje.

### Campos Extraídos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `pontalete` | int | Contagem INSERTs PONTALETE na laje |
| `meio_pontalete` | int | Contagem INSERTs MEIO PONTALETE na laje |
| `pontalete_total` | int | Total (proxy de suporte de cimbramento) |

---

## Prerequisitos para Implementação

1. Gerar `lajes_poligono.json` a partir do DXF PL (layer `LAJE` ou `Laje`)
   - Script: `extrair_poligonos_lajes_pl.py`
2. Ou usar coordenadas de `lajes.json` (Fase-3) se já tiverem vértices

---

## Uso Esperado

```bash
python scripts/extrair_meioPont_pl.py --obra DADOS-OBRAS/Obra_TREINO_21
# Output: Fase-3_Interpretacao_Extracao/Lajes/lajes_meioPont.json
```

---

*CAD-7.2 Backlog | 2026-03-08 | Sprint 5*
