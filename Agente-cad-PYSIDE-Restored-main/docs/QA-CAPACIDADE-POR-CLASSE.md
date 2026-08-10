# Capacidade do agente por classe (paridade PIL / LAJ / FV / LV)

**Propósito:** deixar explícito o que o **QA Global de Evidências** garante de
forma **igual** para cada classe — robustez do agente, não avanço de domínio de obra.

**SoT machine-readable:** `squads/qa-global-evidencias/data/class_capability_matrix.json`  
**CI:** `python scripts/arete/qa_class_capability.py`

## Núcleo comum (todas as classes)

| Capacidade | Como |
|---|---|
| Escopo fail-closed | `--project-id` (ou obra+pav único) |
| Microciclos | discover → review/probe → parity/smoke → ficha → visual → loop |
| Vocabulário de autoridade | CONFIRMAR / TRILHA / PENDENTE / CORRIGIR / … |
| Anti-super-selo | checklist operacional + limites na authority matrix |
| Apresentação ≠ prova | banner HTML + painel QA Global |
| Handoff | dossiê com paths absolutos + session_metrics/RESUME |
| RAG | consultivo com tier; promote humano |
| Memória de erro | `qa_error_memory` por família/padrão de campo |

## Por classe (mesmo molde)

| | PIL | LAJ | FV | LV |
|---|---|---|---|---|
| Adaptador N1 | `PilEvidenceAuditor` | `LajEvidenceAuditor` | `FvEvidenceAuditor` | `LvEvidenceAuditor` |
| Profile JSON | `pil.json` | `laj.json` | `fv.json` | `lv.json` |
| Proveniência | `PROVENIENCIA-CAMPOS-PIL` | `…-LAJ` | `…-FV` | `…-LV` |
| Quadro pavimento | `qa_pil_quadro_*` | `qa_laj_quadro_*` | `qa_fv_quadro_*` | `qa_lv_quadro_*` |
| Golden N1 multi-item | `qa_class_golden_regression` | idem | idem | idem |
| G2-V prontidão | `qa_g2v_visual_gate` | idem | idem | idem |
| Disclaimer UI | pre_validation | preficha_laje | preficha_fundo | preficha_lateral |

## Comandos canônicos (paridade)

```powershell
# Capacidade / authority
python scripts/arete/qa_class_capability.py
python scripts/arete/qa_authority_matrix.py

# Golden N1 — todas as classes (paralelo)
python scripts/arete/qa_class_golden_regression.py --project-id <id> --write-baseline
python scripts/arete/qa_class_golden_regression.py --project-id <id>

# G2-V prontidão — todas as classes (paralelo)
python scripts/arete/qa_g2v_visual_gate.py --pav 13_PAV
```

## O que isto **não** promete

- Interpretação “pronta” de toda a obra  
- Selagem Arete sem veredito visual registrado  
- Que um item sem ficha HTML passe no G2-V (artefato ausente ≠ gap de paridade do agente)

## Evolução

Ao adicionar capacidade a uma classe, atualizar **a matrix das quatro** no mesmo
PR e rodar `qa_class_capability.py` + golden.

Baseline unificado: `scripts/arete/qa_requests/golden/classes_13pav_baseline.json`.
