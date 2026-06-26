# Story CAD-6.6 — Gerador DXF Headless para Vigas (ezdxf)

**Epic:** 6 — Robô-Driven DXF Generation + Comparação
**Sprint:** 3
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Criar `scripts/gerar_dxf_vigas.py` — motor headless puro Python (ezdxf) que replica
o output dos robôs Robo_Laterais_de_Vigas + Robo_Fundos_de_Vigas.

## Contexto Técnico

**Input Laterais:** `Fase-4_Sincronizacao/JSON_Vigas_Laterais/V{n}_A.json` e `V{n}_B.json`
- `total_width`: b da viga (espessura) em cm
- `total_height`: h da viga (altura lateral) em cm
- `panels[i].width`: largura de cada painel (120cm standard, último = resto)
- `panels[i].height1` = altura do painel = h da viga

**Input Fundo:** `Fase-4_Sincronizacao/JSON_Vigas_Fundo/V{n}_fundo.json`
- `total_width`: b da viga em cm
- `total_height`: altura do fundo (pode ser h ou b dependendo do dado)
- `panels[i].width`: largura de cada painel horizontal

**Layout por viga:**
- Lateral A dispostos horizontalmente (painel 1, 2, 3... da esquerda para direita)
- Lateral B abaixo da A (com gap)
- Fundo abaixo da B
- Cada painel = retangulo LWPOLYLINE na layer "Paineis"

## Acceptance Criteria

- [x] **AC-1:** Script `scripts/gerar_dxf_vigas.py` criado
- [x] **AC-2:** 1 DXF por viga com 3 vistas (Lateral A, Lateral B, Fundo)
- [x] **AC-3:** Painéis LWPOLYLINE na layer `Paineis` com dimensões corretas
- [x] **AC-4:** Labels MTEXT com ID da viga + dimensões b/h
- [x] **AC-5:** Output em `Fase-5_Geracao_Scripts/DXF_Vigas/V{n}.dxf` (33 arquivos)
- [x] **AC-6:** Relatório com totais e dimensões

## Arquivos

- `scripts/gerar_dxf_vigas.py`
- `DADOS-OBRAS/Obra_TREINO_21/Fase-5_Geracao_Scripts/DXF_Vigas/` (output)

---

*Story CAD-6.6 | Sprint 3 | DXF Vigas Generation | CAD-ANALYZER v3.0*
