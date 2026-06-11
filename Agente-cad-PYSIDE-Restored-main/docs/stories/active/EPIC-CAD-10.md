# EPIC-CAD-10: Ficha Integrada de Interpretacao

## Status: COMPLETED (2026-05-19)
## Epic Owner: @pm (Morgan)
## Created: 2026-05-18

---

## 1. Problem Definition & Context

### 1.1 Problem Statement

O sistema CAD-ANALYZER possui dois mundos completamente desconectados:

- **Lado A (Pipeline headless)**: `pipeline_e2e.py` executa 10+ scripts que extraem dados de DXFs STOG e produzem JSONs granulares em `Fase-4_Sincronizacao/` com campos detalhados de formwork (h1-h5 por face, larguras, grades, parafusos, paineis, furos, pontaletes).

- **Lado B (App UI PySide6)**: A "Analise Geral" roda apenas `engenharia_reversa_dxf.py`, importando dados superficiais (b, h, altura, confidence). O `DetailCard` captura topologia (quais lajes/vigas se conectam a cada face do pilar) mas os campos sao preenchidos manualmente via vinculos no DXF.

**Consequencia**: O usuario faz trabalho duplo. O pipeline headless ja extrai 80%+ dos dados que o DetailCard precisa, mas esses dados nao fluem para a UI. O Comparison Engine (Tab 2) valida apenas scores visuais globais (NVIDIA NIM), sem comparacao campo-a-campo entre ground truth e interpretacao.

### 1.2 Target Users

- Projetistas estruturais que usam o app para conferir e validar fichas de pre-fabricados
- Operadores de producao que precisam de fichas completas para montagem de formas

### 1.3 Business Goals & Success Metrics

| Metrica | Baseline | Meta |
|---------|----------|------|
| Campos preenchidos automaticamente por item | 0% (manual) | >= 70% |
| Tempo medio para completar ficha de pilar | ~15 min (manual) | < 3 min |
| Campos com discrepancia GT vs Interpretado detectados | 0 (sem comparacao) | 100% |
| Taxa de correcoes realimentadas ao interpretador | 0% | >= 80% |

### 1.4 Competitive Analysis / Existing Solutions

Nao existe solucao equivalente no mercado para este dominio especifico (pre-fabricados de concreto com STOG). Este e um sistema proprietario.

---

## 2. Epic Goal

Conectar o pipeline headless (Fase-4) ao app UI (PySide6) para que a "Analise Geral" preencha automaticamente os campos das fichas, o Comparison Engine mostre diferencas campo-a-campo, e correcoes do usuario realimentem o interpretador.

---

## 3. Existing System Context

### 3.1 Technology Stack

- Python 3.14+, PySide6 (Qt6), ezdxf
- Pipeline: scripts headless (subprocess), JSON files como interface
- DB: SQLite local via `src/core/database.py`
- UI: `src/ui/widgets/detail_card.py` (2543 linhas), `src/ui/modules/comparison_engine.py` (734 linhas)

### 3.2 Codebase Architecture

```
D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/
  scripts/
    pipeline_e2e.py          # Orquestrador E2E (10 fases)
    motor_fase4.py           # Transforma Fase-3 -> Fase-4 JSONs
    engenharia_reversa_dxf.py # Extrai ground truth
    integrar_fichas_fase3.py  # Cria vigas.json + lajes.json
    validar_dxf_coletivo.py   # Score global
  src/
    core/
      database.py             # SQLite operations
    ui/
      widgets/
        detail_card.py         # Ficha por item (Pilar/Viga/Laje)
      modules/
        comparison_engine.py   # Tab 2 - Fase-8 Visual Validation
```

### 3.3 Data Flow (Current)

```
DXF STOG --> engenharia_reversa_dxf.py --> Fase-3 ground truth (b,h,altura)
                                               |
                                               v
                                          UI imports to DB (minimal fields)
                                               |
                                               v
                                          DetailCard (manual linking)

DXF STOG --> pipeline_e2e.py --> motor_fase4.py --> Fase-4 JSONs (rich data)
                                                        |
                                                        v
                                                   (DISCONNECTED from UI)
```

### 3.4 Data Flow (Target)

```
DXF STOG --> pipeline_e2e.py --> motor_fase4.py --> Fase-4 JSONs
                                                        |
                                  +---------------------+
                                  |                     |
                                  v                     v
                            field_mapping.py      DetailCard (auto-populate)
                                  |                     |
                                  v                     v
                            Comparison Panel    Correction feedback
                            (GT vs Fase-4       (back to Fase-4 JSONs)
                             vs UI DB)
```

### 3.5 Integration Points

| System A | System B | Connection Type |
|----------|----------|----------------|
| `motor_fase4.py` (PilarFase4) | `detail_card.py` (fields `p_sX_*`) | New: `field_mapping.py` |
| `Fase-4/JSON_Pilares/P{n}.json` | DB `sides_data` | New: `_import_fase4_to_db()` |
| `Fase-4/JSON_Vigas_Laterais/V{n}_A/B.json` | DB segments | New: `_import_fase4_to_db()` |
| `Fase-4/JSON_Lajes/L{n}.json` | DB laje fields | New: `_import_fase4_to_db()` |
| `detail_card.py` (corrections) | `Fase-4 JSONs` | New: `apply_correction.py` |

---

## 4. Semantic Field Mapping (Core Technical Analysis)

### 4.1 Pilar: Fase-4 JSON vs DetailCard

| Fase-4 JSON Field | DetailCard Field ID | Semantica |
|-------------------|--------------------|----|
| `h1_A` .. `h5_A` | `p_sA_l1_h`, `p_sA_l2_h` | Alturas de hachura por face -> altura de laje |
| `larg1_A` .. `larg3_A` | (nao mapeado diretamente) | Larguras de chapa por face |
| `grade_1`, `grade_2` | (nao mapeado) | Grades de pilar |
| `par_1_2` .. `par_8_9` | (nao mapeado) | Parafusos entre hachuras |
| `comprimento`, `largura` | `dim` | Dimensoes brutas |
| `altura` | (derivado de h1+h2+h3+h4+h5) | Altura total |
| `laje_A` | `p_sA_l1_n` | Nome da laje na face A |
| `posicao_laje_A` | `p_sA_l1_p` | Posicao da laje (Topo/Centro/Fundo) |

### 4.2 Viga: Fase-4 JSON vs DetailCard

| Fase-4 JSON Field | DetailCard Field ID | Semantica |
|-------------------|--------------------|----|
| `panels[i].width` | `viga_a_seg_{i}_comprimento_total` | Largura do painel = comprimento do segmento |
| `panels[i].height1` | `viga_a_seg_{i}_altura_h1` | Altura 1 do painel |
| `panels[i].height2` | `viga_a_seg_{i}_altura_h2` | Altura 2 do painel |
| `panels[i].grade_h1` | `viga_a_seg_{i}_grade_h1` | Grade na altura 1 |
| `holes[i].width/height` | `viga_a_seg_{i}_abertura_*` | Aberturas |
| `total_width` | (soma de panels widths) | Comprimento total da viga |
| `total_height` | (header `dim`) | Dimensao b x h |

### 4.3 Laje: Fase-4 JSON vs DetailCard

| Fase-4 JSON Field | DetailCard Field ID | Semantica |
|-------------------|--------------------|----|
| `comprimento`, `largura` | `laje_dim` | Dimensao da laje |
| `linhas_verticais`, `linhas_horizontais` | (nao mapeado) | Grid de pontaletes |
| `pontaletes.total` | (nao mapeado) | Total de pontaletes |
| `obstaculos` | `laje_islands` | Contorno de ilhas |
| `area_cm2` | (calculado) | Area em cm2 |
| `coordenadas` | `laje_outline_segs` | Contorno da laje |

---

## 5. Stories Breakdown

### Executor Assignment Table

| Story | Title | Executor | Quality Gate | Effort | Risk |
|-------|-------|----------|-------------|--------|------|
| CAD-10.1 | Mapper Fase-4 -> DetailCard | @dev | @architect | 5 pts (M) | LOW |
| CAD-10.2 | Upgrade _import_fase4_to_db() | @dev | @architect | 8 pts (L) | MEDIUM |
| CAD-10.3 | Upgrade "Analise Geral" button | @dev | @qa | 5 pts (M) | MEDIUM |
| CAD-10.4 | Comparison Panel na Ficha | @dev | @qa | 8 pts (L) | MEDIUM |
| CAD-10.5 | Comparison Engine Renovado | @dev | @architect | 13 pts (XL) | HIGH |
| CAD-10.6 | Realimentacao do Interpretador | @dev | @qa | 5 pts (M) | LOW |
| **TOTAL** | | | | **44 pts** | |

### Critical Path & Recommended Order

```
CAD-10.1 (Mapper) ─────────────────────────────────> CAD-10.2 (Import)
                                                          |
                                                          v
                                           CAD-10.3 (Analise Geral button)
                                                          |
                                                     +----+----+
                                                     |         |
                                                     v         v
                                            CAD-10.4       CAD-10.5
                                           (Comp Panel)  (Comp Engine)
                                                     |         |
                                                     +----+----+
                                                          |
                                                          v
                                                    CAD-10.6
                                                  (Realimentacao)
```

**Wave 1 (Foundation):** CAD-10.1 -> CAD-10.2
**Wave 2 (Integration):** CAD-10.3
**Wave 3 (Comparison - Parallel):** CAD-10.4 + CAD-10.5 (podem rodar em paralelo)
**Wave 4 (Feedback Loop):** CAD-10.6

### Sprint Allocation (2-week sprints)

| Sprint | Stories | Focus |
|--------|---------|-------|
| Sprint 1 | CAD-10.1, CAD-10.2 | Foundation: mapping + import |
| Sprint 2 | CAD-10.3, CAD-10.4 | Integration: button upgrade + comparison panel |
| Sprint 3 | CAD-10.5, CAD-10.6 | Comparison engine + feedback loop |

---

## 6. Compatibility Requirements

- [x] Existing pipeline_e2e.py remains unchanged (read-only consumer of its outputs)
- [x] DetailCard field IDs and existing link/validation mechanisms preserved
- [x] Database schema backward compatible (additive changes only)
- [x] motor_fase4.py output format unchanged
- [x] Comparison Engine (Tab 2) visual validation (NVIDIA NIM) remains functional
- [x] Existing manual linking workflow still works alongside auto-populate
- [x] Performance: auto-import must complete in < 5 seconds for typical obra (30 pilares, 60 vigas, 20 lajes)

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| Semantic mismatch between Fase-4 fields and DetailCard fields | MEDIUM | HIGH | CAD-10.1 creates explicit canonical mapping with unit tests for each field pair |
| Auto-populated values overwrite manual corrections | HIGH | HIGH | "Usar interpretacao existente" vs "Re-processar" option in CAD-10.3; merge strategy preserves validated_fields |
| Performance degradation with full pipeline in "Analise Geral" | MEDIUM | MEDIUM | Option to import existing Fase-4 without re-running pipeline; progress bar with cancel |
| Comparison panel adds UI complexity that confuses users | LOW | MEDIUM | Comparison is opt-in (button/tab), not forced. Default view unchanged |
| Correction feedback corrupts Fase-4 JSONs | LOW | HIGH | apply_correction.py creates backup before writing; correction_log.json for audit trail |

### Rollback Plan

- All new modules are additive (new files, not modifications to existing)
- field_mapping.py can be disabled by removing import
- _import_fase4_to_db() guarded by feature flag (config key `fase4_auto_import: true/false`)
- Comparison panel is a new tab/button, easily hidden

---

## 8. Quality Assurance Strategy

### Pre-Commit
- Schema validation for field_mapping.py against actual Fase-4 JSON samples
- Unit tests for each mapping function (pilar, viga, laje)

### Pre-PR
- Integration tests using real obra data (Obra_TREINO_1, Obra_TREINO_21)
- Comparison accuracy: auto-populated values match manual values from curated fichas

### Regression Prevention
- Existing `validar_dxf_coletivo.py` scores must not degrade
- Existing DetailCard manual workflow must remain functional
- Existing database schema must be backward compatible

---

## 9. Definition of Done

- [x] All 6 stories completed with acceptance criteria met
- [x] field_mapping.py covers 100% of mappable Fase-4 fields
- [x] Auto-import populates >= 70% of DetailCard fields for typical obra
- [x] Comparison panel shows accurate delta between GT, Fase-4, and DB
- [x] Corrections persist to Fase-4 JSON and correction_log.json
- [x] No regression in existing pipeline scores or manual workflow
- [x] 75 unit/integration tests pass (zero failures)

---

## 10. Out of Scope (Future)

- Machine learning model trained on correction_log.json (future CAD-11+)
- Cloud sync of correction data between workstations
- Real-time DXF watching (auto-trigger pipeline on file change)
- 3D visualization of pilar/viga assemblies
- Multi-pavimento simultaneous comparison

---

## 11. Story Files

| Story | File | Status |
|-------|------|--------|
| CAD-10.1 | `docs/stories/completed/CAD-10.1.story.md` | DONE |
| CAD-10.2 | `docs/stories/completed/CAD-10.2.story.md` | DONE |
| CAD-10.3 | `docs/stories/completed/CAD-10.3.story.md` | DONE |
| CAD-10.4 | `docs/stories/completed/CAD-10.4.story.md` | DONE |
| CAD-10.5 | `docs/stories/completed/CAD-10.5.story.md` | DONE |
| CAD-10.6 | `docs/stories/completed/CAD-10.6.story.md` | DONE |

---

*EPIC criado por @pm (Morgan) em 2026-05-18*
*Caminho base do projeto: D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main/*
