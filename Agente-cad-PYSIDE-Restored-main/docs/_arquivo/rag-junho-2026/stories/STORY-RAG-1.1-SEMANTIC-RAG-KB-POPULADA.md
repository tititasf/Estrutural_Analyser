# STORY RAG-1.1 - semantic_rag_kb Populada

## Status
Concluida em 2026-06-27.

## Objetivo
Popular `semantic_rag_kb` a partir das regras semanticas existentes em
`domain_knowledge` (`doc_type=field_semantics`), sem indexar fichas N1/N2/N3/N4.

## Execucao
Comando dry-run:

```powershell
python scripts\populate_semantic_rag_kb.py --dry-run --sample 5
```

Comando aplicado:

```powershell
python scripts\populate_semantic_rag_kb.py --apply
```

## Resultado
- `domain_knowledge` lido: 217 registros.
- `semantic_rag_kb` populada: 109 regras.
- Distribuicao por classe:
  - `PIL`: 10
  - `LV`: 43
  - `FV`: 43
  - `LAJ`: 13

## Gate Anti-Contaminacao
- `reverse_eng_fichas`: 906 registros.
- `reverse_eng_fichas.rag_indexed != 0`: 0.
- `fase3_fichas`: 743 registros.
- `fase3_fichas.revisado != 0`: 0.

Conclusao: entraram regras semanticas, nao instancias draft.

## Validacao
```powershell
python -m pytest tests\test_populate_semantic_rag_kb.py tests\test_rag_tier_synthetic_guard.py tests\test_rag_validation_events.py
```

Resultado: 12 passed.

## Nao Fazer
- Nao usar esta story como permissao para indexar F5/F7 em bulk.
- Nao promover T0 para T1.
- Nao tratar regra semantica como validacao de item de obra.
