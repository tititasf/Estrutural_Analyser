---
id: RAG-0
title: "Fundacao de confianca anti-contaminacao do RAG"
epic: CEREBRO-RAG-MULTIMODAL
status: In Progress
executor: "@dev"
quality_gate: "@qa"
priority: CRITICAL
dependencies: []
source_masterplan: "D:/Agente-cad-PYSIDE/MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md"
---

# RAG-0: Fundacao de confianca anti-contaminacao do RAG

## Description

Implementar a camada minima que impede contaminacao do RAG global antes de qualquer
indexacao incremental: tiers T0/T1/T2/TX, guarda de indexacao, filtro de consulta e
tombstone de revogacao humana.

## Scope

### IN Scope
- `scripts/rag_tier.py` com `get_tier`, `is_indexable`, tombstones e selftest.
- `scripts/rag_ingestor.py` recusando T0 antes de inserir em FAISS/metadados.
- `scripts/rag_query.py` filtrando por `min_tier='T1'` e excluindo revogados.
- Testes focados para tier, indexabilidade e revogacao.

### OUT of Scope
- Indexar fichas F5/F7 em massa.
- Hooks de UI no Diagnostic Reverse Hub ou Comparison Engine.
- Popular `semantic_rag_kb`.
- Rebuild fisico dos indices FAISS/Chroma.

## Acceptance Criteria

- `python scripts/rag_tier.py --selftest` passa.
- `pytest tests/test_rag_tier.py` passa.
- Uma ficha draft/extracted e classificada como T0 e nao indexavel.
- Uma ficha aprovada/validada e classificada como T1 e indexavel.
- Um item revogado e classificado como TX e nunca indexavel.
- Query global exclui metadados abaixo de T1 e IDs revogados.

## Nao Fazer

- Nao criar bulk index.
- Nao promover T0.
- Nao sobrescrever registros validados sem evento de revogacao.
- Nao depender de delete fisico do FAISS como unica protecao.

