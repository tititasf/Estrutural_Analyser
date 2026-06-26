# Story CAD-6.2 — Extração total_width (B da Viga) do FV DXF

**Epic:** 6 — Robô-Driven DXF Generation + Comparação
**Sprint:** 3
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Extrair o `total_width` (espessura B da viga) do FV DXF para preencher o campo
que estava faltando nas fichas V{n}_A.json e V{n}_B.json.

## Contexto Técnico (descoberto em CAD-6.1)

**FV DXF (1118 entidades):**
- Layer "Painéis": 96 ents — LWPOLYLINE(9) + LINE(46) + **DIMENSION(41)**
  - DIMENSIONs amostradas: 244, 244, 122, **60**, 520, 154, 887, 244
  - val=60.0 em pos=[4082, 742] → **candidato ao B da viga**
- Layer "NOMENCLATURA": TEXT(5) → V19.C, V22.C, V12.C, V2.C
  - Labels V{n}.C = ancoragem para busca por proximidade
- Layer "COTA": DIMENSION(5) → 2.0, 7.0, 64.43, 63.28, 302.46

**Estratégia:**
1. Encontrar labels V{n}.C em "NOMENCLATURA" (posição do centróide de cada viga)
2. Procurar DIMENSION em "Painéis" com valor < 80cm próximo a cada label = B da viga
3. Fallback: usar "COTA" DIMENSIONs < 80cm
4. Fallback final: usar B=15cm (default — valor mais comum para vigas)

## Acceptance Criteria

- [x] **AC-1:** Script `extrair_largura_vigas_fv.py` criado e executado
- [x] **AC-2:** B extraído para 100% das 33 vigas (32 por proximidade FV-12PAV+FV-TIPO, 1 default)
- [x] **AC-3:** `vigas_largura.json` gerado com {vid: {largura_cm, confidence, source}}
- [x] **AC-4:** Script imprime tabela V{n} → B_cm por viga

## Arquivos

- `scripts/extrair_largura_vigas_fv.py`
- `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Vigas/vigas_largura.json`

---

*Story CAD-6.2 | Sprint 3 | Viga Width Extraction | CAD-ANALYZER v3.0*
