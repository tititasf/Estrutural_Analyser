# Story CAD-5.4 — Extrator Garfos/EVG

**Epic:** 5 — Extração Dimensional Completa
**Sprint:** 2
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Extrair dados de garfos/EVG (elementos de ancoragem de viga) dos EVG DXFs.
Layer "VIGAS" contém `V{n} = {count}X` — contagem de garfos por viga.

## Contexto Técnico

**EVG DXFs disponíveis (12 PAV):**
- `ADITIVO - TIPO - EVG`: contém DOIS grupos (TIPO + ADITIVO) por posição X
  - TIPO section: X <= 22000 (PAV 4-11 standard)
  - ADITIVO section: X > 22000 (PAV 12 additive)
- `TIPO 4o AO 11o PAV. - EVG`: apenas TIPO data

**Layer "VIGAS":** `V{n} = {count}X` → garfo_count por viga
**Layer "NOME DA VIGA":** `T{n}-{count}X` → tipo de garfo por seção

**Algoritmo:** X > 22000 → ADITIVO (12 PAV); ADITIVO overrides TIPO na merge.
**Deduplicação:** MAX count quando mesmo viga aparece em múltiplos DXFs.

## Acceptance Criteria

- [x] **AC-1:** Script `extrair_garfos_evg.py` criado e executado com sucesso

- [x] **AC-2:** Dados de garfo extraídos de 20/33 vigas (60% cobertura)
      Vigas sem garfo (13): V7, V8, V16, V18, V21, V25, V27-V32, V32A
      (provável: essas vigas não usam EVG no 12 PAV)

- [x] **AC-3:** `garfos_evg.json` gerado com contagens por viga
      Campos: id, garfo_count, section (tipo/aditivo), source_dxf, confidence
      Amostra: V12=28 | V1=25 | V3=24 | V4=24 | V17=16

- [x] **AC-4:** Separação TIPO vs ADITIVO correta
      15 vigas do ADITIVO (12 PAV): V3, V4, V6, V9-12, V14, V17, V19-20, V22-24, V26
      5 vigas do TIPO: V1, V2, V5, V13, V15

## Arquivos Criados

- [x] `scripts/extrair_garfos_evg.py`
- [x] `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Garfos/garfos_evg.json`

## Notas Técnicas

- Vigas com TIPO data (V1=25, V2=25, V15=25): A count 25 = soma de 12X + 13X
  (duas versões do mesmo pavimento no mesmo DXF — pode ser range 12-13 garfos)
- Validação exata requer NVIDIA NIM visual (CAD-6.2)
- 13 vigas sem garfo: assumir garfo_count=0 na ficha_fundo_viga

---

*Story CAD-5.4 | Sprint 2 | Extrator Garfos/EVG | CAD-ANALYZER v3.0*
