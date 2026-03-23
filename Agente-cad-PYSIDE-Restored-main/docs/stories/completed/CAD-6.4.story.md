# Story CAD-6.4 — Integração Completa: vigas.json e lajes.json com todos os elementos

**Epic:** 6 — Robô-Driven DXF Generation + Comparação
**Sprint:** 3
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Atualizar `vigas.json` e `lajes.json` com TODOS os 33 vigas e 20 lajes do 12 PAV,
integrando os dados das fontes Fase 3 para que o `motor_fase4.py` gere todos os JSONs.

## Problema Atual

- `vigas.json`: apenas 4 vigas (V1-V4)
- `lajes.json`: apenas 3 lajes (L1-L3)
- `motor_fase4.py` gera output incompleto por isso

## Fontes de Dados

**Vigas:**
- `vigas_dim.json` — 33 vigas: comprimento + altura_lateral (= h da viga)
- `vigas_largura.json` — 33 vigas: largura_cm (= b da viga)

**Lajes:**
- `lajes_poligono.json` — 19 lajes: coordenadas + comprimento + largura (CAD-6.3)

## Acceptance Criteria

- [x] **AC-1:** Script `integrar_fichas_fase3.py` criado
- [x] **AC-2:** `vigas.json` atualizado com 33 vigas (b + h + comprimento)
- [x] **AC-3:** `lajes.json` atualizado com 19+ lajes (comprimento + largura + coordenadas)
- [x] **AC-4:** motor_fase4.py gera 33 vigas + 19 lajes + 34 pilares ao ser re-executado

## Arquivos

- `scripts/integrar_fichas_fase3.py`
- `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Vigas/vigas.json` (atualizado)
- `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Lajes/lajes.json` (atualizado)

---

*Story CAD-6.4 | Sprint 3 | Integração Fase 3 | CAD-ANALYZER v3.0*
