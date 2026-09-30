# RAG-4 - Consulta RAG Read-Only no Comparison Engine

## Objetivo

Adicionar consulta RAG ao fluxo N1/N2/N3/N4 sem contaminar o motor puro.

## Escopo

- Botao `Consultar RAG` no sidebar do Comparison Engine.
- Consulta somente leitura via `scripts/rag_context_service.py`.
- Retorna regras de `semantic_rag_kb` e exemplos validados T1/T2 quando existirem.
- Exibe claramente quando ainda nao ha exemplos T1/T2.

## Fora de Escopo

- Nao alterar o botao `Analise Geral`.
- Nao autocompletar campos.
- Nao gerar DXF.
- Nao indexar fichas.

## Gate

- Com item selecionado, a UI consulta contexto RAG.
- Sem item selecionado, a UI apenas avisa.
- T0 nunca aparece como exemplo.
- Testes focados passam.
