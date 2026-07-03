---
title: "Story DOC - Reconciliacao Arete G0-G6, MCP e RAG"
date: 2026-07-02
status: in-progress
owner: documentation
---

# STORY-DOC - Reconciliacao Arete G0-G6, MCP e RAG

## Objetivo

Eliminar contradicoes documentais entre o procedimento Arete, a triagem JSONL,
o contrato de harmonizacao e o status do MCP, sem alterar implementacao, banco ou
indices.

## Criterios de aceite

- [ ] `MASTERPLAN-ARETE-QUALITY-GATES.md` e a fonte unica da nomenclatura G0-G6.
- [ ] Procedimento Arete declara escopo atual e dependencia G1/G2 antes de G5.
- [ ] Triagem usa um achado por causa, com `finding_id` e `run_id`.
- [ ] Modelo atual pragmatico e separado do event sourcing futuro.
- [ ] Banner MCP distingue captura T0 ativa de servidor/promocao inativos.
- [ ] JSONL completo nao e sincronizado diretamente em `n4_attention_feedback`.
- [ ] Modo atual `human-in-the-CLI` nao presume multiagente autonomo, mas preserva
  seguranca basica de concorrencia entre sessoes manuais.
- [ ] Referencias cruzadas permanecem validas.

