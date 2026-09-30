# STORY RAG-1.2 - Indexacao T1 Auditada

## Status
Auditada em 2026-06-27. Nao aplicada por ausencia de candidatos T1/T2 pendentes.

## Objetivo
Indexar somente `reverse_eng_fichas` T1/T2 ainda nao indexadas no FAISS, sem bulk dump
e sem indexar T0.

## Execucao
Comando:

```powershell
python scripts\indexar_validados.py --dry-run
```

Resultado:

```text
[reverse_eng_fichas] candidatos T1/T2 nao indexados: 0 by_class={}
[dry-run] Nenhuma escrita realizada. Use --apply apos validacao humana.
```

Consulta direta:

```text
approved_unindexed = 0
```

## Decisao
Nao executar `--apply` neste momento. O gate correto e aguardar uma validacao humana real
criar item T1/T2 ainda nao indexado.

## Validacao
```powershell
python -m pytest tests\test_indexar_validados.py tests\test_rag_tier.py tests\test_rag_tier_synthetic_guard.py
```

Resultado: 12 passed.

## Nao Fazer
- Nao forcar indexacao manual.
- Nao mudar status de ficha para criar candidato artificial.
- Nao indexar `draft`, `extracted`, CLI/synthetic ou qualquer T0.
