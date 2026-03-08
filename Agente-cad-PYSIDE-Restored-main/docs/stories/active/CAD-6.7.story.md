# Story CAD-6.7 — Gerador DXF Headless para Lajes (ezdxf)

**Epic:** 6 — Robô-Driven DXF Generation + Comparação
**Sprint:** 3
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Criar `scripts/gerar_dxf_lajes.py` — motor headless puro Python (ezdxf) que replica
o output do Robo_Lajes para cada laje do 12 PAV.

## Acceptance Criteria

- [x] **AC-1:** Script `scripts/gerar_dxf_lajes.py` criado
- [x] **AC-2:** 1 DXF por laje com contorno poligonal + painéis internos (planta baixa)
- [x] **AC-3:** Contorno LWPOLYLINE na layer `Contorno`, painéis na layer `Paineis`
- [x] **AC-4:** Divisórias `linhas_verticais` e `linhas_horizontais` geram painéis corretos
- [x] **AC-5:** Output em `Fase-5_Geracao_Scripts/DXF_Lajes/L{n}.dxf` (19 arquivos)
- [x] **AC-6:** Relatório com dimensões, área e contagem de painéis por laje

## Resultado

- 19 DXFs gerados | 0 erros
- L11: 2154.4×244cm (corredor longo) → 23 painéis verticais
- L18-L20: 244×46.9cm (faixas estreitas) → 4 painéis cada

## Arquivos

- `scripts/gerar_dxf_lajes.py`
- `DADOS-OBRAS/Obra_TREINO_21/Fase-5_Geracao_Scripts/DXF_Lajes/` (19 DXFs)

---

*Story CAD-6.7 | Sprint 3 | DXF Lajes Generation | CAD-ANALYZER v3.0*
