# RAG-5 - Snapshot RAG Local por Obra

## Objetivo

Gerar um contexto local da obra para ajudar interpretacao sem promover nada ao RAG global.

## Escopo

- Script `scripts/obra_rag_pipeline.py`.
- Gera `DADOS-OBRAS/{obra}/obra_rag/manifest.json`.
- Inclui projetos, documentos, F5/N2, recortes, recortes de obra e regras semanticas globais.
- Marca tiers locais, especialmente T0.
- Expoe `run_pipeline()` como contrato de compatibilidade para workers PySide existentes.
- O Diagnostic Hub atualiza o snapshot automaticamente apos interpretar uma obra.
- O Gerenciador de Projetos usa o comando "Atualizar Obra (DB + RAG Local)".
- A Curadoria le os manifests para mostrar cobertura local sem confundir com ensino global.

## Politica

- RAG por-obra pode conter T0 local porque serve para trabalho naquela obra.
- T0 local nunca vira verdade global automaticamente.
- O snapshot e read-only para o banco.
- `run_pipeline()` nunca executa indexacao global, promocao de tier ou triagem automatica.

## Fora de Escopo

- Nao criar embeddings.
- Nao escrever FAISS/Chroma.
- Nao atualizar `rag_indexed`.
- Nao validar/desvalidar fichas.

## Gate

- `--dry-run` nao escreve.
- `--apply` cria somente `obra_rag/manifest.json`.
- Manifest explicita `promotion_policy=never_auto_global`.
- Resultado de `run_pipeline()` explicita `scope=obra_local` e e aceito pelos workers da UI.
- Labels da UI dizem "RAG local" e nao prometem indexacao vetorial global.
