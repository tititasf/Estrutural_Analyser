# Story CAD-6.5 — Gerador DXF Headless para Pilares (ezdxf)

**Epic:** 6 — Robô-Driven DXF Generation + Comparação
**Sprint:** 3
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Criar `scripts/gerar_dxf_pilares.py` — motor headless puro Python (ezdxf) que replica
o output do Robo_Pilares para cada pilar do 12 PAV, usando os JSONs da Fase 4.

## Contexto Técnico

**Input:** `Fase-4_Sincronizacao/JSON_Pilares/P{n}.json`
- comprimento, largura (cm) — seção do pilar (B x H)
- altura=280cm
- h1_A..h5_A, h1_B..h5_B, h1_C..h5_C, h1_D..h5_D — distribuição de painéis por face
- (h4, h5 usualmente = 0)

**Estrutura do DXF STOG PL (auditada):**
- Layer `Painéis`: LWPOLYLINE — painéis retangulares (formas de madeira)
- Layer `Cota Seção (2x)`: DIMENSION — B/H do pilar
- Layer `Texto Seção`: MTEXT — labels P{n}.A, P{n}.B, etc.
- Layer `NOMENCLATURA`: MTEXT — header "12° PAVIMENTO - PD: X.XX"
- Layer `COTA`: DIMENSION + LINE — dimensões dos painéis (comprimento, altura parcial)
- Layer `Hachura`: HATCH — padrão de madeira nos painéis

**Layout de geração (simplificado):**
- 4 faces A, B, C, D dispostas horizontalmente com gap de 30cm
- Cada face = coluna de retângulos empilhados (h1, h2, h3, h4, h5 do JSON)
- Face A e C: largura = comprimento do pilar; Face B e D: largura = largura do pilar
- Origem em (0, 0), faces dispostas da esquerda para a direita

## Acceptance Criteria

- [x] **AC-1:** Script `scripts/gerar_dxf_pilares.py` criado
- [x] **AC-2:** Gera 1 DXF por pilar com 4 faces (A, B, C, D) com painéis corretos
- [x] **AC-3:** Panels LWPOLYLINE na layer `Paineis`, labels MTEXT na layer `Texto Secao`
- [x] **AC-4:** B x H como MTEXT na layer `Cota Secao (2x)` + NOMENCLATURA header
- [x] **AC-5:** Output em `Fase-5_Geracao_Scripts/DXF_Pilares/P{n}.dxf` (40 arquivos)
- [x] **AC-6:** Relatório `_relatorio.json` com totais, b/h, n_paineis por pilar

## Arquivos

- `scripts/gerar_dxf_pilares.py`
- `DADOS-OBRAS/Obra_TREINO_21/Fase-5_Geracao_Scripts/DXF_Pilares/` (output)

---

*Story CAD-6.5 | Sprint 3 | DXF Generation Headless | CAD-ANALYZER v3.0*
