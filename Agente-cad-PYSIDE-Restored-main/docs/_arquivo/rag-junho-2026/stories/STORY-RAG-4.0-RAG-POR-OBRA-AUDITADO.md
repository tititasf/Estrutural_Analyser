# STORY RAG-4.0 - RAG por Obra Auditado

**Status:** Snapshot local automatico concluido em 2026-06-27; retrieval vetorial pendente.

## Objetivo

Comprovar a ligacao do botao `Atualizar Obra (DB + RAG Local)` e separar
snapshot local, consulta global T1+ e retrieval vetorial por obra.

## Comprovado

- O botao registra arquivos novos no DB e chama o pipeline local em background.
- O pipeline grava `DADOS-OBRAS/{obra}/obra_rag/manifest.json`.
- T0 pode aparecer no manifest apenas como contexto local.
- O pipeline nao escreve FAISS/Chroma global e nao promove T0 para T1.
- Selecionar uma obra atualiza o manifest em `QProcess` sem bloquear a UI.
- Trocas rapidas de obra enfileiram a ultima selecao enquanto um snapshot roda.
- `rag_context_service.py` consulta regras e exemplos globais com `min_tier=T1`.
- Comparison Engine possui acao read-only `Consultar RAG`.

## Execucao em Obra_TREINO_3

- projetos: 1
- documentos: 391
- fichas F5: 0
- recortes reversos: 2
- recortes de obra: 2
- regras semanticas: 109
- tiers promovidos: 0

## Pendencias

- Implementar retrieval vetorial no corpus local, alem do manifest JSON.
- Integrar consulta/sugestao no Structural Analyzer sem alterar `Analise Geral`.
- Executar smoke visual do botao e do indicador no aplicativo.

## Validacao

```powershell
python -m pytest tests\test_obra_rag_pipeline.py tests\test_rag_context_service.py
python scripts\obra_rag_pipeline.py --obra Obra_TREINO_3 --apply
```

Resultado: 8 testes aprovados na regressao RAG/Curadoria, compilacao da UI
aprovada e snapshot materializado.
