# Dossiê QA — {run_id}

## Escopo

{scope_json}

Paths absolutos:

- Dossiê: `{out_dir_abs}`
- Decisões: `{out_dir_abs}/decisoes.jsonl`
- Achados: `{out_dir_abs}/achados.jsonl`
- Manifesto: `{out_dir_abs}/manifesto.json`
- Session metrics (se loop): `{loop_run_dir}/session_metrics.json`

## Grafo de proveniência

| Nó | Fonte | Path absoluto | SHA-256 | Autoridade | Consumidor |
|---|---|---|---|---|---|
| | | | | | |

Elo ausente → `PENDENTE` (não inventar).

## Decisões

| Campo/parte | Estado | Confiança | Path evidência | SHA-256 | Motivo |
|---|---|---|---|---|---|
| | | | | | |

Regra: cada linha de `CONFIRMAR` **exige** path + SHA (ou equivalente no manifesto do adaptador). Sem SHA → não promover a selo.

## Achados e microciclo

| Achado | Código | Família | Causa | Fix geral | Teste | Regressão | Visual |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

Ingerir recorrência: `python scripts/arete/qa_error_memory.py ingest --findings achados.jsonl`.

## Dúvidas humanas

Usar `structured-question-template.md`; omitir a seção quando não houver impasse real.

## Anti-super-selo

- [ ] PASS localizado ≠ item/ficha
- [ ] HTML/checkbox ≠ prova
- [ ] G2 numérico ≠ gate visual
- [ ] Checklist: `checklists/operational-anti-superselo-checklist.md`
