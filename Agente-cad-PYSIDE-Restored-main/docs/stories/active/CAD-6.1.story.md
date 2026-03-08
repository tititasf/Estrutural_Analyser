# Story CAD-6.1 — Audit Completo DXF + Field Mapping para Robôs

**Epic:** 6 — Robô-Driven DXF Generation + Comparação
**Sprint:** 3
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Criar script de auditoria que inspeciona **todos os DXFs STOG** (PL, LV, FV, LJ, EVG)
e produz um mapeamento definitivo: **campo do robô → layer DXF → entidade → método de extração**.

Esta story é o alicerce do Epic 6 — sem ela, CAD-6.2 a CAD-6.8 são suposições.

## Contexto Estratégico

O usuário clarificou: o objetivo é usar os robôs para gerar DXF unitário por elemento
e comparar com o original STOG. Para isso, precisamos saber EXATAMENTE o que cada
DXF STOG contém em cada layer, e como isso mapeia para os campos dos JSONs dos robôs.

**JSONs de Robô (formatos reais descobertos):**
- `P{n}.json`: comprimento, largura, h1-h5 por face A-H, larg1-3, grade, par — 8 faces, 104 campos
- `V{n}_A.json`: total_width (B), total_height (H), panels[6], holes[4]
- `L{n}.json`: coordenadas [[x,y],...], comprimento, largura, linhas_verticais/horizontais

**Gaps críticos (a confirmar via auditoria):**
- `total_width` das vigas — onde está no FV DXF?
- `coordenadas` das lajes — qual layer/entity type no LJ DXF?
- Layers de "Painéis", "PARAFUSOS", "GRADES" no PL DXF — contêm dados reais ou são só visual?

## Acceptance Criteria

- [x] **AC-1:** Script `audit_dxf_robot_fields.py` criado e executado com sucesso
      Inspeciona PL, LV, FV, LJ DXFs do 12 PAV
      Produz relatório completo de layers + entity counts por layer

- [x] **AC-2:** `DXF_ROBOT_FIELDMAP.json` gerado
      Audit_DXF/DXF_ROBOT_FIELDMAP.json + dxf_inspection_raw.json

- [x] **AC-3:** Responde: "O que está no FV DXF para largura_fundo das vigas?"
      Layer "Painéis" do FV DXF tem 41 DIMENSION entities — inclui B da viga (ex: val=60.0)
      Layer "NOMENCLATURA" tem V{n}.C labels — ancoragem para busca por proximidade
      Candidato: DIMENSION em "Painéis" com valor < 80cm próximo a V{n}.C = B da viga

- [x] **AC-4:** Responde: "Qual entity do LJ DXF forma o polígono real de cada laje?"
      Layer "1" tem 137 LWPOLYLINE — candidatos ao contorno da laje
      Layer "Pilares" tem 39 LWPOLYLINE = seções dos pilares (não é laje)
      Alternativa viável: usar AUX00 dims (dim1×dim2 em cm) para gerar coordenadas retangulares

- [x] **AC-5:** Responde: "Os dados de parafusos/grades do PL DXF são relevantes?"
      PL DXF NÃO TEM layers "PARAFUSOS" ou "GRADES" — 28 layers inspecionados
      Zeros são CORRETOS para parafusos e grades no motor_fase4.py ✅

- [x] **AC-6:** `DXF_AUDIT_REPORT.md` gerado — Audit_DXF/DXF_AUDIT_REPORT.md

## Output

```
scripts/audit_dxf_robot_fields.py
DXF_ROBOT_FIELDMAP.json        ← mapeamento machine-readable
DXF_AUDIT_REPORT.md            ← relatório humano-legível
```

## Notas Técnicas

**Layers conhecidos nos DXFs:**
- PL (6162 ents, 28 layers): "Cota Seção (2x)", "Texto Seção", "Painéis", "COTA", "PARAFUSOS"?, "GRADES"?
- LV (9468 ents, 44 layers): "Cota Seção (2x)", "Texto Seção", "COTA", "FUROS"?
- FV (1118 ents, 24 layers): "NOMENCLATURA", "GARFOS", "COTA"?, "Cota Seção (2x)"?
- LJ (3606 ents, 16 layers): "AUX00", polígono?

---

*Story CAD-6.1 | Sprint 3 | DXF Audit | CAD-ANALYZER v3.0*
