# Golden cross-obra (scaffold)

O baseline atual `fv_lv_13pav_baseline.json` cobre **Obra_TREINO_1 / 13_PAV**.

Para outra obra:

```powershell
python scripts/arete/qa_fv_lv_golden_regression.py `
  --project-id <OUTRO_PROJECT_ID> `
  --baseline scripts/arete/qa_requests/golden/fv_lv_<obra>_<pav>_baseline.json `
  --write-baseline

python scripts/arete/qa_fv_lv_golden_regression.py `
  --project-id <OUTRO_PROJECT_ID> `
  --baseline scripts/arete/qa_requests/golden/fv_lv_<obra>_<pav>_baseline.json
```

Critério: **mesma família de campos** deve generalizar; se CONFIRMAR cair por obra,
é gap de adaptador — não hardcode de item.
