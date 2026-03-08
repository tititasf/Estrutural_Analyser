# Story CAD-6.3 — Extração `coordenadas` das Lajes (LJ DXF)

**Epic:** 6 — Robô-Driven DXF Generation + Comparação
**Sprint:** 3
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Extrair o polígono real (`coordenadas`) de cada laje a partir dos DXFs STOG.
O campo `coordenadas` é a lista de pontos [[x,y],...] do contorno da laje,
necessário para o Robo_Lajes gerar o DXF unitário correto.

## Contexto Técnico (descoberto em CAD-6.1)

**Fontes identificadas:**
- **LV DXF layer "Laje_Perimetro"**: 24 LWPOLYLINE — candidatos diretos ao polígono real
- **LJ DXF layer "1"**: 137 LWPOLYLINE — inclui polígonos de laje + outros elementos
- **LJ DXF layer "AUX00"**: 60 MTEXT "L{n}\n{dim1}X{dim2}" — painéis de cada laje
- **LJ DXF layer "Pilares"**: 39 LWPOLYLINE = seções de pilares (IGNORAR)

**Estratégia:**
1. Ler LV DXF "Laje_Perimetro" → 24 LWPOLYLINE como polígonos de laje
2. Ler AUX00 do LJ DXF → label L{n} com posição → match por proximidade ao polígono
3. Normalizar coordenadas para espaço local (0,0 como origem)
4. Fallback: LWPOLYLINE layer "1" com maior área próximo ao label
5. Fallback final: retângulo dim1×dim2 da AUX00

## Acceptance Criteria

- [x] **AC-1:** Script `extrair_poligono_lajes.py` criado e executado
- [x] **AC-2:** Polígono extraído para >= 15 das 20 lajes do 12 PAV
- [x] **AC-3:** `lajes_poligono.json` gerado com {lid: {coordenadas, comprimento, largura, confidence, source}}
- [x] **AC-4:** coordenadas em espaço local (min_x=0, min_y=0)

## Arquivos

- `scripts/extrair_poligono_lajes.py`
- `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Lajes/lajes_poligono.json`

---

*Story CAD-6.3 | Sprint 3 | Laje Polygon Extraction | CAD-ANALYZER v3.0*
