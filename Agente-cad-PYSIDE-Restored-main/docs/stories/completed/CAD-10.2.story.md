---
id: CAD-10.2
title: "Upgrade _import_fase4_to_db()"
epic: CAD-10
status: Done
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: [schema_validation, integration_test, code_review]
effort: 8
priority: HIGH
dependencies: [CAD-10.1]
---

# CAD-10.2: Upgrade _import_fase4_to_db()

## Description

Criar funcao `_import_fase4_to_db()` que le os JSONs ricos da Fase-4 (JSON_Pilares, JSON_Vigas_Laterais, JSON_Vigas_Fundo, JSON_Lajes), aplica o mapeamento canonico de CAD-10.1, e popula os registros do DB com campos completos — incluindo `sides_data` para pilares, segmentos para vigas, e dados estruturais para lajes.

## Problem / Need

Atualmente, a importacao para DB apos "Analise Geral" traz apenas dados superficiais de `engenharia_reversa_dxf.py`: `{b, h, altura, bh_confidence}` para pilares e `{b, h, comprimento}` para vigas. Os JSONs Fase-4 contem 10x mais dados (alturas por face, larguras, grades, parafusos, paineis, furos) que poderiam pre-popular 70%+ dos campos.

## Scope

### IN Scope
- Funcao `_import_fase4_to_db(obra_path, pavimento)` em `src/core/services/fase4_importer.py`
- Merge strategy: Fase-4 dados complementam (nao sobrescrevem) dados ja validados
- Populacao de `sides_data` para pilares com h1-h5, larg1-3 por face
- Populacao de segments para vigas com panels como segmentos
- Populacao de dados estruturais de lajes (pontaletes, grid)
- Confidence mapping: campos de Fase-4 recebem confidence score baseado na fonte
- Integration tests com obra real

### OUT of Scope
- Modificacoes no `motor_fase4.py` ou `pipeline_e2e.py`
- UI changes (CAD-10.3 e CAD-10.4)
- Alteracoes no schema do SQLite (usar campos existentes + JSON blobs)

## Acceptance Criteria

### AC1: Import de pilares com sides_data completo
**Given** `Fase-4/JSON_Pilares/P1.json` existe com campos h1_A..h5_H, larg1_A..D, grade_1/2, par_1_2..8_9
**When** `_import_fase4_to_db(obra, pav)` e executado
**Then** o registro P1 no DB contem:
- `sides_data.A.h1` = valor de `h1_A`
- `sides_data.A.h2` = valor de `h2_A`
- `sides_data.A.larg1` = valor de `larg1_A`
- Analogamente para faces B, C, D (e E-H se pilar nao retangular)
- `grade_1`, `grade_2` populados
- `par_1_2` .. `par_8_9` populados
- `distancia_1` populado

### AC2: Merge nao sobrescreve campos validados
**Given** P1 ja tem `p_sA_l1_h` no `validated_fields` com valor manual "250"
**And** Fase-4 JSON tem `h1_A = 244.0`
**When** import e executado
**Then** o campo `p_sA_l1_h` mantem valor "250" (validado manualmente)
**And** campo `fase4_h1_A = 244.0` e armazenado separadamente para comparacao
**And** um flag `has_conflict` e setado para este campo

### AC3: Import de vigas com segmentos
**Given** `Fase-4/JSON_Vigas_Laterais/V7_A.json` com `panels: [{width:120, height1:40, height2:0, grade_h1:"0", grade_h2:"0"}, ...]`
**When** import e executado
**Then** o registro V7 no DB contem:
- `viga_a_seg_1_comprimento_total` = panels[0].width
- `viga_a_seg_1_altura_h1` = panels[0].height1
- `viga_a_seg_1_grade_h1` = panels[0].grade_h1
- Numero de segmentos = numero de panels com width > 0
- Holes mapeadas como aberturas nos segmentos correspondentes

### AC4: Import de vigas de fundo
**Given** `Fase-4/JSON_Vigas_Fundo/V7_fundo.json` existe
**When** import e executado
**Then** o registro V7 no DB contem dados de `viga_fundo_seg_{i}_*` populados
**And** estrutura identica ao lado A/B

### AC5: Import de lajes com pontaletes
**Given** `Fase-4/JSON_Lajes/L1.json` com `comprimento`, `largura`, `pontaletes`, `linhas_verticais`, `linhas_horizontais`
**When** import e executado
**Then** o registro L1 no DB contem:
- `laje_dim` = `{comprimento}x{largura}`
- Pontaletes data armazenado em campo JSON blob
- Grid dimensions calculado

### AC6: Confidence mapping
**Given** campos importados de Fase-4
**When** import e executado
**Then** `confidence_map` do item e atualizado:
- Campos vindos de Fase-4 (motor_fase4.py) recebem confidence = 0.75
- Campos vindos de engenharia_reversa (ground truth) mantem confidence original
- Campos manuais (validated_fields) mantem confidence = 1.0
- Merge: max(existing_confidence, new_confidence)

### AC7: Batch import de obra completa
**Given** Obra_TREINO_21 com 30 pilares, 60 vigas, 20 lajes em Fase-4
**When** `_import_fase4_to_db(obra_treino_21, "12 PAV")` e executado
**Then** todos os itens sao importados
**And** tempo total < 5 segundos
**And** nenhum erro de schema ou tipo
**And** log reporta: "{N} pilares, {M} vigas, {K} lajes importados, {C} conflitos detectados"

### AC8: Idempotencia
**Given** import ja foi executado uma vez
**When** import e executado novamente
**Then** dados nao sao duplicados
**And** campos nao-validados sao atualizados com valores mais recentes
**And** campos validados permanecem inalterados
**And** log indica: "re-import: {N} atualizados, {V} preservados (validados)"

## Technical Notes

### Merge Strategy

```python
def merge_field(field_id, existing_value, fase4_value, is_validated):
    if is_validated:
        # Preservar valor manual, armazenar fase4 para comparacao
        return existing_value, {'fase4_value': fase4_value, 'has_conflict': existing_value != str(fase4_value)}
    else:
        # Usar valor Fase-4
        return str(fase4_value), None
```

### Database Access Pattern

Usar `src/core/database.py` existente. Os dados de pilar/viga/laje sao armazenados como JSON blobs no campo `data` de cada item. O `sides_data` e parte desse JSON blob. Nao e necessario alterar o schema SQLite.

## File List

| File | Action | Description |
|------|--------|-------------|
| `src/core/services/fase4_importer.py` | CREATE | Import logic |
| `src/core/services/__init__.py` | MODIFY | Export new module |
| `tests/test_fase4_importer.py` | CREATE | Integration tests |
| `tests/fixtures/fase4_import/` | CREATE | Test fixtures (obra mini) |

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-18 | @pm | Story created |
