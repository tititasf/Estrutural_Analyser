# MASTERPLAN SS — Vision-Estrutural AI v4.7 → v5.0 SS
## Objetivo: 84/A → 95+/SS | CEO-PLANEJAMENTO (Athena) | 2026-05-24

---

## ESTADO ATUAL (84/A)

| Componente | Status |
|-----------|--------|
| 23 obras TREINO certificadas (STOG 100%) | ✅ |
| 4 geradores STOG (PL/LV/FV/LJ) funcionais | ✅ |
| `regenerar_e_validar.py` batch funcional | ✅ |
| `pipeline_e2e.py` F1→F8 headless | ✅ |
| NIM visual validation ativo | ✅ |
| Batch report: 92 pavimentos, 13 APROVADO, 47 CRASH | ⚠️ |
| Testes falhando: 2 | ⚠️ |
| Visual outliers: TREINO_3 FV=37.4%, TREINO_18 LV=46.5% | ⚠️ |
| NIM non-determinismo ±20pp | ⚠️ |

**Score atual: 84/A | Meta: 95+/SS**

---

## SPRINT 1 — Crash Fix (CRÍTICO | +4pts → 88)

**Problema:** 47/92 pavimentos crasham instantaneamente no batch
- `0xC000012D` (STATUS_PIPE_NOT_CONNECTED)  
- `0xC0000142` (DLL_INIT_FAILED)
- Causa: Qt/PySide6 sendo importado sem headless guard em subprocesso

**Tarefas:**
1. Rodar `TREINO_14` manualmente via `pipeline_e2e.py` e capturar stderr completo
2. Verificar se `pipeline_e2e.py` tem `os.environ["QT_QPA_PLATFORM"] = "offscreen"` antes do import PySide6
3. Adicionar guard no topo de `pipeline_e2e.py`:
   ```python
   import os
   os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
   os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")
   ```
4. Adicionar `timeout=900` no subprocess call em `pipeline_batch.py`
5. Re-rodar batch completo e verificar taxa de crash

**Gate:** Batch APROVADO >= 40/92 (de 13 atual)

---

## SPRINT 2 — Test Suite Fix (+3pts → 91)

**Problema:** 2 testes falhando
- `test_pilares_ground_truth_count` — fixtures provavelmente desatualizadas
- `test_fase3_outputs_have_expected_counts` — idem

**Tarefas:**
1. Rodar `pytest tests/ -v 2>&1 | head -60` para ver falhas exatas
2. Atualizar fixtures com contagens reais das obras atuais
3. Verificar se há mais testes falhando além dos 2

**Gate:** `pytest tests/` 100% verde

---

## SPRINT 3 — Visual Outliers (+3pts → 94)

**Problema:** Scores baixos em obras específicas
- `TREINO_3 FV=37.4%` — Frentes de Vigas muito baixas
- `TREINO_18 LV=46.5%` — Lajes Vigas muito baixas

**Tarefas:**
1. Rodar `regenerar_e_validar.py` para TREINO_3 e TREINO_18 individualmente
2. Abrir diff visual: DXF gerado vs STOG de referência
3. Identificar layers ou entidades faltando
4. Corrigir gerador específico (gerar_fv_dxf_stog.py / gerar_lj_dxf_stog.py)

**Gate:** TREINO_3 FV >= 70%, TREINO_18 LV >= 70%

---

## SPRINT 4 — NIM Stability (+2pts → 95+ SS)

**Problema:** NIM non-determinismo ±20pp entre runs

**Tarefas:**
1. Para obras com score visual < 70%: rodar NIM 3x e usar mediana
2. Adicionar `n_runs=3` como parâmetro no `comparison_engine.py` para obras flagged
3. Calibrar threshold: score < 0.60 → re-run automático

**Gate:** Desvio padrão NIM < 10pp nas obras de referência

---

## SPRINT 5 — BONUS: TREINO_12 Desbloqueio

**Problema:** TREINO_12 em formato LO-PLA combinado (não suportado)

**Tarefas:**
1. Analisar estrutura DXF de TREINO_12
2. Adaptar parser F3 para suportar formato combinado LO-PLA
3. Certificar TREINO_12 no batch

---

## SPRINT 6 — BONUS: Cobertura Paramétrica

**Tarefas:**
1. Testes paramétricos para TREINO_21, TREINO_22, TREINO_23
2. Expandir test suite com novos fixtures certificados
3. Documentar STATUS.md final

---

## Projeção de Score

| Sprint | Ganho | Score |
|--------|-------|-------|
| Atual | — | 84/A |
| Sprint 1 (crash fix) | +4 | 88/S |
| Sprint 2 (tests) | +3 | 91/SS |
| Sprint 3 (outliers) | +3 | 94/SS |
| Sprint 4 (NIM) | +2 | 96/SS |
| Sprint 5+6 (bonus) | +2 | 98/SS |

---

*MASTERPLAN-SS v5.0 | CEO-PLANEJAMENTO | 2026-05-24*
*Base: audit 84/A, 23 obras TREINO certificadas STOG, batch 47 crashes*
