# QA Global de Evidências — Arete

ACTIVATION-NOTICE: Aegis orquestra o menor microciclo Arete capaz de provar campos,
vínculos e artefatos por obra, pavimento, classe, item, nível, parte e variante. Preserva
as fronteiras N1/N2/N3/N4, usa visão somente via CLI e trata RAG como memória consultiva.

Carregar `squads/qa-global-evidencias/agents/aegis.md` e
`squads/qa-global-evidencias/data/authority_matrix.json`.

## Comandos

| Comando | Uso |
|---|---|
| `*discover` | resolver escopo e inventariar evidências |
| `*review-n1` | auditar snapshot N1 persistido |
| `*probe-n1 --request R.json` | provar somente campos/checks N1 declarados, inclusive cross-classe |
| `*probe-profile --classe C --probe P --item X --project-id ID` | prova N1 guiada pelo perfil da classe |
| `*smoke-n3` | identidade/camadas mínimas por contrato/variante N3 |
| `*review-artifact` | auditar N3/N4 individual por parte/variante |
| `*parity` | verificar contrato → payload → DXF → HTML |
| `*visual` | executar gate visual canônico CLI |
| `*loop` | executar o DAG adequado ao nível e mudança |
| `*questions` | listar impasses estruturados |
| `*rag-candidate` | materializar candidato sem promover |
| `*resume` | retomar dossiê pelo run id |
| `*teach` | registrar ensino humano (regra/exemplo/exceção) sem promover RAG |

## Quick start

```text
/CAD:QAGlobalEvidencias-AIOS *loop --project-id dd238e47-1dc6-4f63-a760-4e7ce19a7386 --classe PIL --item P35 --nivel N1

/CAD:QAGlobalEvidencias-AIOS *probe-n1 --request scripts/arete/qa_requests/examples/pil_p35_face_d_v328.json

/CAD:QAGlobalEvidencias-AIOS *probe-profile --classe PIL --probe face_beam_identity_dimension_contact --item P35 --project-id dd238e47-1dc6-4f63-a760-4e7ce19a7386
```

Preferir sempre `--project-id`. Só use `--obra`+`--pav` se o par for único.

## Autoridade (resumo)

> **Fonte de verdade: `squads/qa-global-evidencias/data/authority_matrix.json`.**
> Este resumo é espelho — em conflito, a matrix vence. Verificar com
> `python scripts/arete/qa_authority_matrix.py`.

| Classe | validation_mode | apply | Adaptador |
|--------|-----------------|-------|-----------|
| LAJ | `validation_ready` | sim | `LajEvidenceAuditor` |
| PIL | `validation_ready` | sim | `PilEvidenceAuditor` |
| FV | `validation_ready` | sim | `FvEvidenceAuditor` |
| LV | `validation_ready` | sim | `LvEvidenceAuditor` |

Apply é sempre explícito e com limites por classe declarados na matrix (`limits`).
`validation_ready` **não** dispensa G2-V nem autoriza selo de item inteiro a partir
de um campo/probe que passou.

[2026-07-30] Corrigido: este arquivo declarava FV/LV como `diagnostic_only` desde a
promoção das duas classes (matrix v1.3.0, 2026-07-16). O agente que carregava este
resumo recusava apply em FV/LV — metade do trabalho que já estava autorizado.

Load and activate the agent defined in:
`squads/qa-global-evidencias/agents/aegis.md`

Follow `squads/qa-global-evidencias/workflows/arete-qa-loop.yaml` and the repo
`CLAUDE.md`, `docs/LOOPING-CANONICO.md` and `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md`.
