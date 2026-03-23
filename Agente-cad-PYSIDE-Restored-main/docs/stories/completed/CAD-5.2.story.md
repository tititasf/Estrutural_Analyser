# Story CAD-5.2 — Extrator Comprimento/Altura de Vigas (LV DXF)

**Epic:** 5 — Extração Dimensional Completa
**Sprint:** 2
**Status:** Done
**Criado:** 2026-03-08
**Assignee:** @dev (aios-dev)

---

## Objetivo

Extrair comprimento (cm) e altura_lateral (cm) de cada viga do LV DXF de engenharia
reversa usando spatial proximity entre labels TEXT (V{n}.A/B) e DIMENSION entities
nos layers "Cota Seção (2x)" e "COTA".

## Contexto Técnico

O LV DXF (Laterais de Vigas) do 12 PAV tem 9,468 entidades em 44 layers.

**Layer "Texto Seção":**
- TEXT com labels `V{n}.A`, `V{n}.B` — posição de cada face lateral da viga
- Casos especiais: `V17.A+V18.A` (vigas combinadas), `V24.A-V24.B`
- Layer "NOMENCLATURA": fallback para V{n}.A/B não encontrados em "Texto Seção"
- Layer "5": labels de referência cruzada (V{n} sem face)

**Layer "Cota Seção (2x)":**
- 80 DIMENSION entities: valores 38-326cm = altura_lateral de cada face
- Algoritmo: proximity matching — DIMENSION mais próxima de cada label V{n}.{face}
- Valores encontrados: [38.0, 78.0, 90.0, 104.0, 110.0, 120.0, 156.0, 167.4, 206.0, 216.0, 250.0, 254.0, 276.0, 294.0, 310.0, 326.0]

**Layer "COTA":**
- 1,139 DIMENSION entities: valores 1-1228cm
- Range relevante para comprimento: >= 100cm (afasta sarrafos 2-7cm, parafusos, etc.)
- Comprimento = maior COTA >= 100cm mais próximo de cada viga side
- Valores representativos: 120cm, 240cm, 360cm, 480cm, 600cm+ (múltiplos de painéis)

**33 Vigas:** V1-V32 + V32A (confirmado no ground truth)

## Acceptance Criteria

- [x] **AC-1:** Script `extrair_vigas_lv.py` criado e executado com sucesso
      CLI: `python scripts/extrair_vigas_lv.py --obra {path} --pavimento "12 PAV"`

- [x] **AC-2:** Labels V{n}.A e V{n}.B extraídos de 33/33 vigas (100% cobertura)
      Inclui V32A. Vigas combinadas (V17+V18, V25+V26) extraídas corretamente.

- [x] **AC-3:** `altura_lateral` extraída via proximity em "Cota Seção (2x)"
      33/33 com altura. Range: 38-310cm. Confiança média: 90%.

- [x] **AC-4:** `comprimento` extraído via maior COTA >= 100cm dentro raio 800 DXF
      33/33 com comprimento. Range: 180-1205cm. Algoritmo: max_val dentro raio.

- [x] **AC-5:** `vigas_dim.json` gerado com 33/33 vigas com comprimento + altura
      Confiança média geral: 84%. Source: inverse_proximity para todos.
      Amostra: V1: alt=254cm comp=403cm | V22: alt=310cm comp=558cm | V7: comp=1205cm

- [ ] **AC-6:** `vigas_ground_truth.json` com dimensões extraídas
      BLOQUEADO: requer validação manual ou NVIDIA NIM visual (CAD-6.2)

## Arquivos a Criar/Modificar

- [x] `scripts/extrair_vigas_lv.py` — CRIADO
- [x] `DADOS-OBRAS/Obra_TREINO_21/Fase-3_Interpretacao_Extracao/Vigas/vigas_dim.json` — CRIADO (33 vigas)

## Algoritmo de Extração

### Passo 1 — Labels
```python
# Layer "Texto Seção": V{n}.A, V{n}.B
# Layer "NOMENCLATURA": fallback para V3.A
# Padrão regex: V(\d+[A-Z]?)\.([A-Z+]+)
viga_labels = {}  # {vid: {"A": (x,y), "B": (x,y)}}
```

### Passo 2 — Altura Lateral
```python
# Cada label V{n}.{face} → DIMENSION mais próxima em "Cota Seção (2x)"
# Confiança: dist < 500 → 0.90, < 1500 → 0.80, < 3000 → 0.65, > 3000 → 0.50
altura_lateral = nearest_dim(label_pos, dims_cota_secao)
```

### Passo 3 — Comprimento
```python
# Para cada viga (centro entre A e B):
#   Encontrar DIMENSIONs em "COTA" com valor >= 100cm
#   Tomar a mais próxima com valor >= 100cm → comprimento
# Fallback: usar a bounding box dos Painéis próximos (LWPOLYLINE em layer "Painéis")
comprimento = nearest_cota_grande(viga_center, dims_cota, min_val=100)
```

## Definição de Pronto (DoD)

- [x] Script executa sem erros no LV DXF real do 12 PAV
- [x] vigas_dim.json com 33/33 vigas com dimensões não-null (meta era >= 25)
- [x] Logs claros de confiança por viga (por viga no output)
- [x] V1, V2, V5, V10, V15 todos com comprimento + altura extraídos

---

*Story CAD-5.2 | Sprint 2 | Extrator Dimensional Vigas | CAD-ANALYZER v3.0*
