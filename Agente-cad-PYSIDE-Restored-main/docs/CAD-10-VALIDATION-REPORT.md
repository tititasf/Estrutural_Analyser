# CAD-10 Validation Report -- 2026-05-19

## Resultado Geral: PASS

Todas as fases de validacao completadas com sucesso. Zero regressoes, zero erros de importacao, campos corretamente mapeados e persistidos.

---

## Fase 1: Testes unitarios

- **70/70 passaram** (0 falhas)
- Suites: `test_cad103_ui_integration` (5), `test_field_mapping` (25), `test_comparison_engine_v2` (14), `test_motor_fase4` (16) + 10 comparison engine
- **Correcao aplicada:** 7 testes em `test_field_mapping.py` estavam desatualizados -- referenciavam o formato antigo `sides_data[face]['h1']` e `p_sA_h1`. Atualizados para o formato CAD-10: `flat['p_sA_c_h1']` e inverse `p_sA_c_h1`
- **Nota:** `test_fundo_multi_project_bug.py` causa access violation (crash do PySide6 no import de fundo_pyside.py). Excluido da suite -- pre-existente, nao relacionado ao CAD-10

## Fase 2: Validacao headless UI

| Check | Resultado |
|-------|-----------|
| `_get_initial_value('p_sA_c_h2')` retorna 260.0 | PASS |
| `_get_initial_value('grade_1')` retorna 88.0 | PASS |
| `_get_initial_value('altura')` retorna 280.0 | PASS |
| `_get_initial_value('p_sA_l1_h')` via sides_data fallback | PASS |
| Grupo "Dimensional/Geometria" condicionado em `PILAR` | PASS |
| Grupo "Assembly" condicionado em `PILAR` | PASS |
| Grupo "Chapa/Forma" presente para faces de pilar | PASS |
| Grupo "Pontaletes/Escoras" presente para laje | PASS |
| Grupo "Calculo/Metricas" presente para laje | PASS |
| Dimensional em UI principal (nao em metodo pilar-only) | PASS |

## Fase 3: E2E Obra_TREINO_1

| Tipo | Importados | No DB | Campos OK | Erros |
|------|-----------|-------|-----------|-------|
| Pilares | 35 | 35/35 | 35/35 (altura, grade_1, p_sA-D_c_h2, dim) | 0 |
| Vigas | 93 (62 A+B, 31 fundo) | 62 unicos | 62/62 (seg_comprimento) | 0 |
| Lajes | 23 | 23/23 | 23/23 (pont_total, laje_linhas_v_count) | 0 |

- **Tempo de importacao:** ~2.6s para 151 arquivos JSON
- **Conflitos:** 0 (primeira importacao, sem dados pre-existentes)
- **Nota sobre vigas:** 93 JSONs importados produzem 62 beams unicos no DB porque faces A e B da mesma viga sao merge em um unico registro

## Fase 4: ComparisonService

| Metrica | Pilar P1 | Laje L101 |
|---------|----------|-----------|
| has_fase4 | True | True |
| build_rows | 90 rows | 22 rows |
| field `p_sA_c_h2` presente | True | N/A |
| field `grade_1` presente | True | N/A |
| field `altura` presente | True | N/A |
| completude_pct | 43.3% | 95.5% |
| match_pct | 100.0% | -- |

- A completude de pilar e 43.3% porque o pilar tem 8 faces x ~8 campos = ~64 campos potenciais, mas faces E-H tipicamente tem larg=0 (pilar retangular). Os 39 campos preenchidos tem 100% de match com o DB.
- A laje L101 tem 95.5% de completude (21/22 campos preenchidos pelo Fase-4).

## Fase 5: Gaps corrigidos

| Arquivo | Gap | Correcao |
|---------|-----|----------|
| `tests/test_field_mapping.py` | 7 testes referenciavam formato antigo `sides_data[face]['h1']` e `p_sA_h1` sem `_c_` | Atualizado para `flat['p_sA_c_h1']` e `map_detail_to_fase4('p_sA_c_h1', ...)` |
| `src/core/services/comparison_service.py` | `_label('p_sA_c_h1')` retornava `"Face  - C_H1"` (face vazia, key crua) | Corrigido parser: face agora extraido corretamente, key traduzido para legivel ("Chapa H1", "Laje H", etc.) |

## Fase 6: Regressoes

- **0 falhas** em 70 testes apos todas as correcoes

## Campos cobertos por tipo

### Pilar (flat fields via Fase4Importer)

| Grupo | Campos |
|-------|--------|
| Identificacao | `name`, `id_item`, `dim` |
| Dimensional | `altura`, `nivel_chegada`, `nivel_saida`, `pavimento`, `modo_distribuicao` |
| Assembly | `grade_1`, `grade_2`, `grade_3`, `distancia_1`, `distancia_2`, `par_1_2`..`par_8_9` |
| Chapa por face (A-H) | `p_s{face}_c_h1`..`p_s{face}_c_h5`, `p_s{face}_c_larg1`..`p_s{face}_c_larg3` |
| Laje adjacente | `p_s{face}_l1_h`, `p_s{face}_l1_p` (via sides_data) |

### Viga Lateral (flat fields)

| Grupo | Campos |
|-------|--------|
| Identificacao | `name`, `id_item`, `dim`, `floor`, `side` |
| Dimensional | `total_width`, `total_height` |
| Segmentos | `viga_{a|b}_seg_{n}_comprimento_total`, `_h1`, `_h2`, `_dim`, `_exists` |
| Grades | `viga_{a|b}_seg_{n}_mode_h1_grade`, `_mode_h2_grade` |
| Aberturas | `viga_{a|b}_seg_{n}_has_hole`, `_hole_width`, `_hole_height`, `_hole_position` |
| Pilares | `viga_{a|b}_pilar_esq_width`, `_pilar_dir_width` |

### Viga Fundo (flat fields)

| Grupo | Campos |
|-------|--------|
| Identificacao | `name`, `id_item`, `floor` |
| Dimensional | `total_width`, `total_height`, `dim` |
| Segmentos | `viga_fundo_seg_1_largura`, `_comprimento`, `_exists` |
| Paineis | `viga_fundo_seg_{n}_painel_w`, `_painel_h1`, `_painel_h2` |

### Laje (flat + links)

| Grupo | Campos |
|-------|--------|
| Identificacao | `name`, `id_item`, `type` |
| Dimensao | `laje_dim` (via links), `area`, `laje_nivel` (via links) |
| Calculo | `modo_selecionado`, `laje_linhas_v_count`, `laje_linhas_h_count`, `unioes_nos_bordes`, `observacoes` |
| Pontaletes | `pont_total`, `pont_meio`, `pont_linhas`, `pont_colunas`, `pont_tipo`, `pont_altura_pav`, `pont_comp_cm`, `pont_larg_cm` |
| Geometria | `points` (coordenadas), `laje_obstaculos` |

---

## Arquivos modificados

1. `tests/test_field_mapping.py` -- 7 testes atualizados para formato `p_s{face}_c_h{n}` (flat)
2. `src/core/services/comparison_service.py` -- `_label()` corrigido para parsear `p_s{face}_c_{key}` corretamente

## Nota sobre testes pre-existentes excluidos

- `test_fundo_multi_project_bug.py` -- Crash (access violation) no import de PySide6 widget. Problema pre-existente nao relacionado ao CAD-10.
- Demais test files com dependencia PySide6 (theme, ui_visual, etc.) nao foram executados por requererem display.
