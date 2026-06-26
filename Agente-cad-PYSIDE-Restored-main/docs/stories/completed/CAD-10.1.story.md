---
id: CAD-10.1
title: "Mapper Fase-4 -> DetailCard"
epic: CAD-10
status: Done
executor: "@dev"
quality_gate: "@architect"
quality_gate_tools: [pattern_validation, schema_validation, code_review]
effort: 5
priority: HIGH
dependencies: []
---

# CAD-10.1: Mapper Fase-4 -> DetailCard

## Description

Criar o modulo canonico de mapeamento entre os campos dos JSONs Fase-4 (produzidos pelo `motor_fase4.py`) e os field IDs do `DetailCard` (usados pela UI PySide6). Este modulo e a fundacao de todo o epic CAD-10 — sem ele, nenhum dado pode fluir automaticamente do pipeline para a UI.

## Problem / Need

O `motor_fase4.py` produz JSONs ricos com campos como `h1_A`, `h2_A`, `larg1_A`, `grade_1`, `par_1_2`, `panels[].width`, etc. O `DetailCard` usa field IDs como `p_sA_l1_h`, `viga_a_seg_1_comprimento_total`, `laje_dim`. Nao existe um mapeamento formal entre os dois mundos.

## Scope

### IN Scope
- Script `scripts/fase4_to_detail_mapper.py` para validar mapeamentos contra JSONs reais
- Modulo `src/core/field_mapping.py` com mapeamento canonico
- Funcoes: `map_pilar_fase4_to_detail(pilar_json) -> dict[field_id, value]`
- Funcoes: `map_viga_fase4_to_detail(viga_json, side) -> dict[field_id, value]`
- Funcoes: `map_laje_fase4_to_detail(laje_json) -> dict[field_id, value]`
- Funcao inversa: `map_detail_to_fase4(field_id, value) -> (json_key, value)`
- Unit tests com JSONs de amostra

### OUT of Scope
- Importacao para DB (CAD-10.2)
- Alteracoes no DetailCard (CAD-10.4)
- Alteracoes no motor_fase4.py

## Acceptance Criteria

### AC1: Mapeamento de Pilar completo
**Given** um JSON `Fase-4/JSON_Pilares/P1.json` com campos `h1_A..h5_H`, `larg1_A..D`, `grade_1`, `grade_2`, `par_1_2..par_8_9`, `distancia_1`, `comprimento`, `largura`, `altura`
**When** `map_pilar_fase4_to_detail(pilar_json)` e chamado
**Then** retorna dict com field IDs correspondentes do DetailCard:
- `dim` -> `{comprimento}x{largura}`
- `p_sA_l1_h` -> valor derivado de `h1_A` (ou soma h1+h2 conforme logica)
- Cada face A-H mapeada com os campos de laje (nome, altura, nivel, posicao)
- Campos de viga de contorno/chegada mapeados
- Resultado: pelo menos 15 field IDs populados por pilar

### AC2: Mapeamento de Viga completo
**Given** um JSON `Fase-4/JSON_Vigas_Laterais/V7_A.json` com `panels[]`, `holes[]`, `total_width`, `total_height`, `pillar_left`, `pillar_right`
**When** `map_viga_fase4_to_detail(viga_json, 'A')` e chamado
**Then** retorna dict com:
- `viga_a_seg_{i}_comprimento_total` para cada panel
- `viga_a_seg_{i}_altura_h1` e `_h2` para cada panel
- `viga_a_seg_{i}_grade_h1` e `_h2` para cada panel
- Aberturas mapeadas se `holes[i].active == True`
- Resultado: pelo menos 5 field IDs por segmento

### AC3: Mapeamento de Laje completo
**Given** um JSON `Fase-4/JSON_Lajes/L1.json` com `comprimento`, `largura`, `area_cm2`, `pontaletes`, `linhas_verticais`, `linhas_horizontais`, `obstaculos`
**When** `map_laje_fase4_to_detail(laje_json)` e chamado
**Then** retorna dict com:
- `laje_dim` -> `{comprimento}x{largura}`
- `laje_outline_segs` -> coordenadas do contorno
- `laje_islands` -> obstaculos como contorno de ilha
- Resultado: pelo menos 4 field IDs populados

### AC4: Mapeamento inverso funcional
**Given** um field_id do DetailCard (ex: `p_sA_l1_h`) e um valor (ex: `244.0`)
**When** `map_detail_to_fase4(field_id, value)` e chamado
**Then** retorna tupla `(json_key, transformed_value)` correta (ex: `('h1_A', 244.0)`)
- Funciona para campos de pilar, viga e laje
- Retorna `None` para field IDs sem mapeamento inverso

### AC5: Script de validacao contra dados reais
**Given** uma obra com Fase-4 completa (ex: Obra_TREINO_21)
**When** `python scripts/fase4_to_detail_mapper.py --obra DADOS-OBRAS/Obra_TREINO_21` e executado
**Then** gera relatorio mostrando:
- Total de campos mapeados vs nao mapeados por tipo (pilar/viga/laje)
- Campos Fase-4 sem correspondencia no DetailCard
- Campos DetailCard sem correspondencia no Fase-4
- Coverage score >= 70% para pilares, >= 60% para vigas, >= 50% para lajes

### AC6: Unit tests
**Given** JSONs de amostra em `tests/fixtures/fase4_samples/`
**When** `pytest tests/test_field_mapping.py` e executado
**Then** todos os testes passam:
- test_map_pilar_basic
- test_map_pilar_all_faces
- test_map_viga_with_panels
- test_map_viga_with_holes
- test_map_laje_basic
- test_map_inverse_pilar
- test_map_inverse_viga
- test_unmapped_fields_documented

## Technical Notes

### DetailCard Field ID Patterns (discovered from source)

**Pilar faces (A-H):**
- `p_s{side}_l{1,2}_n` — Nome da laje
- `p_s{side}_l{1,2}_h` — Altura/Espessura
- `p_s{side}_l{1,2}_v` — Nivel da laje
- `p_s{side}_l{1,2}_p` — Posicao (Topo/Centro/Fundo)
- `p_s{side}_l{1,2}_dist_c` — Distancia ao centro
- `p_s{side}_v_{esq,dir,ch1,ch2,ch3}_n` — Nome da viga
- `p_s{side}_v_{esq,dir,ch1,ch2,ch3}_d` — Dimensao da viga
- `p_s{side}_v_{esq,dir,ch1,ch2,ch3}_prof` — Profundidade

**Viga segmentos (A, B, Fundo):**
- `viga_{a,b,fundo}_seg_{i}_comprimento_total` — Comprimento
- `viga_{a,b,fundo}_seg_{i}_comp_total_passa` — Comprimento passa
- `viga_{a,b,fundo}_seg_{i}_tipo_comp` — Tipo (para/passa)
- `viga_{a,b,fundo}_seg_{i}_altura_h1` — Altura 1
- `viga_{a,b,fundo}_seg_{i}_altura_h2` — Altura 2

**Laje:**
- `laje_dim` — Dimensao
- `laje_nivel` — Nivel
- `laje_outline_segs` — Contorno
- `laje_islands` — Ilhas

### PilarFase4 Fields (from motor_fase4.py)

```python
# Per face A-H:
h1_{face}, h2_{face}, h3_{face}, h4_{face}, h5_{face}  # Hachura heights
larg1_{face}, larg2_{face}, larg3_{face}                # Widths
laje_{face}, posicao_laje_{face}                        # Slab reference
# Global:
grade_1, grade_2, grade_3
distancia_1, distancia_2
par_1_2 .. par_8_9                                      # Bolts
comprimento, largura, altura
```

## File List

| File | Action | Description |
|------|--------|-------------|
| `src/core/field_mapping.py` | CREATE | Canonical mapping module |
| `scripts/fase4_to_detail_mapper.py` | CREATE | Validation script |
| `tests/test_field_mapping.py` | CREATE | Unit tests |
| `tests/fixtures/fase4_samples/P1.json` | CREATE | Pilar sample |
| `tests/fixtures/fase4_samples/V7_A.json` | CREATE | Viga sample |
| `tests/fixtures/fase4_samples/L1.json` | CREATE | Laje sample |

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-18 | @pm | Story created |
