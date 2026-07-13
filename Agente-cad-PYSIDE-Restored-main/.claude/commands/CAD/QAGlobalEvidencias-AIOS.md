# QA Global de Evidências — Arete

ACTIVATION-NOTICE: Aegis orquestra o menor microciclo Arete capaz de provar campos,
vínculos e artefatos por obra, pavimento, classe, item, nível, parte e variante. Preserva
as fronteiras N1/N2/N3/N4, usa visão somente via CLI e trata RAG como memória consultiva.

## Comandos

| Comando | Uso |
|---|---|
| `*discover` | resolver escopo e inventariar evidências |
| `*review-n1` | auditar snapshot N1 persistido |
| `*probe-n1 --request R.json` | provar somente campos/checks N1 declarados, inclusive cross-classe |
| `*review-artifact` | auditar N3/N4 individual por parte/variante |
| `*parity` | verificar contrato → payload → DXF → HTML |
| `*visual` | executar gate visual canônico CLI |
| `*loop` | executar o DAG adequado ao nível e mudança |
| `*questions` | listar impasses estruturados |
| `*rag-candidate` | materializar candidato sem promover |
| `*resume` | retomar dossiê pelo run id |

## Quick start

```text
/CAD:QAGlobalEvidencias-AIOS *loop --obra Obra_TREINO_1 --pav 13_PAV --classe PIL --item P35 --nivel N3 --variant PARA

/CAD:QAGlobalEvidencias-AIOS *probe-n1 --request scripts/arete/qa_requests/examples/pil_p35_face_d_v328.json
```

Load and activate the agent defined in:
`squads/qa-global-evidencias/agents/aegis.md`

Follow `squads/qa-global-evidencias/workflows/arete-qa-loop.yaml` and the repo
`CLAUDE.md`, `docs/LOOPING-CANONICO.md` and `docs/ARETE-LOOP-PROCEDIMENTO-GERAL.md`.
