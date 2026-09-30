# STORY RAG-4.2A — Retrieval local seguro por obra

**Status:** Concluída em 2026-06-27.

## Entrega

- `obra_rag_query.py` consulta somente o manifest local da obra.
- Ranking lexical é determinístico e read-only.
- Todo resultado declara `scope=obra_local`, `is_global_truth=false` e seu tier.
- T0 local pode orientar o trabalho, mas nunca é promovido ao RAG global.
- `rag_context_service.py` combina contexto local rotulado com regras/exemplos globais T1+.

## Gate

`test_obra_rag_query.py`, `test_obra_rag_pipeline.py` e
`test_rag_context_service.py` aprovados.
