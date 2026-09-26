---
id: RAG-1
title: "Regras semanticas seguras no semantic_rag_kb"
epic: CEREBRO-RAG-MULTIMODAL
status: In Progress
executor: "@dev"
quality_gate: "@qa"
priority: HIGH
dependencies: [RAG-0]
source_masterplan: "D:/Agente-cad-PYSIDE/MASTERPLAN-CEREBRO-RAG-MULTIMODAL-v1.0.md"
---

# RAG-1: Regras semanticas seguras no semantic_rag_kb

## Description

Materializar no SQLite `semantic_rag_kb` apenas o que ja e regra semantica existente
no `domain_knowledge` LanceDB (`doc_type=field_semantics`). Nao indexar instancias,
fichas F5/F7, recortes, N1/N2/N3/N4 em desenvolvimento.

## Scope

### IN Scope
- Script `scripts/populate_semantic_rag_kb.py`.
- Modo `--dry-run` para auditoria.
- Modo `--apply` idempotente para preencher `semantic_rag_kb`.
- Testes unitarios de inferencia de classe e payload.

### OUT of Scope
- Criar regra nova nao presente no `domain_knowledge`.
- Entrevistar dono para semantica faltante.
- Popular fichas/instancias no FAISS/Chroma.
- Hook de UI da Curadoria.

## Acceptance Criteria

- `python scripts/populate_semantic_rag_kb.py --dry-run` mostra >= 60 rows candidatas.
- `python scripts/populate_semantic_rag_kb.py --apply` popula `semantic_rag_kb`.
- `SELECT COUNT(*) FROM semantic_rag_kb WHERE obra_contexto='domain_knowledge:field_semantics'`
  retorna >= 60.
- Rodar `--apply` duas vezes nao duplica linhas.
- Payload de `regra_semantica` e JSON valido e contem `source_doc`, `section`, `text`.

## Nao Fazer

- Nao indexar `reverse_eng_fichas`.
- Nao indexar `fase3_fichas`.
- Nao criar semantica que nao exista em `domain_knowledge`.
- Nao apagar linhas de outro `obra_contexto`.

