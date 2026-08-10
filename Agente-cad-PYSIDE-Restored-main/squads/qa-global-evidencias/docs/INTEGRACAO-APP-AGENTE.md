# Integração app ↔ agente QA Global

**Atualizado:** 2026-07-16 · squad v1.6+

## O que a app faz

| Superfície | Papel |
|---|---|
| Prefichas N1 HTML (LAJ/FV/LV/PIL) | **Apresentação** + checkbox humano; banner “≠ prova” |
| Aba **QA Global de Evidências** (module tab 9) | Abrir último dossiê/loop (`QaGlobalDossierPanel`) |
| Selos azul/rosa/laranja | Origens humanas vs `qa_agente` — ver `CONVENCAO-SELOS-VALIDACAO.md` |

A app **não** reexecuta o motor de prova do adaptador.

## O que o agente/CLI prova

| Entry | Prova |
|---|---|
| `qa_evidence_auditor.py review/discover/apply` | Decisões + dossiê + apply explícito |
| `qa_n1_field_probe` / `qa_profile_probe` | Checks declarados apenas |
| `qa_fv_lv_adapters` (via review FV/LV) | Geometria/contratos/aberturas |
| `g2v_harness` / `qa_g2v_visual_gate` | Materialização visual; veredito ainda humano/agente |
| `qa_loop_executor` | State/RESUME/session_metrics |
| `qa_rag_curation` | Candidatos T1; promote com humano |
| `qa_error_memory` | Recorrência por família |

## Source of truth

1. `CLASS_REGISTRY` + `data/authority_matrix.json` (CI: `qa_authority_matrix.py`)
2. `docs/LOOPING-CANONICO.md` + `MASTERPLAN-AGENTE-QA-GLOBAL.md`
3. Skill `qa-global-evidencias`

## O que **não** é prova

- Score estrutural 100/S da squad
- Arquivo HTML que “abriu”
- Checkbox marcado
- PASS de smoke/paridade/probe estendido a item/ficha

## Comandos de handoff

```powershell
python scripts/arete/qa_open_latest_dossier.py --project-id <id> --open
python scripts/arete/qa_fv_lv_golden_regression.py --project-id <id>
python scripts/arete/qa_g2v_visual_gate.py --pav 13_PAV
python scripts/arete/qa_error_memory.py recurrence --min-count 2
```
