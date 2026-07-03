---
title: "Story DOC - Harmonizacao Arete, MCP e RAG"
date: 2026-07-02
status: done
owner: documentation
---

# STORY-DOC - Harmonizacao Arete, MCP e RAG

## Objetivo

Registrar o contrato arquitetural que separa diagnostico Arete, eventos MCP e
conhecimento RAG, preservando os gates humanos T0/T1/T2/TX e evitando duplicacao
entre JSONL, SQLite e indices vetoriais.

## Criterios de aceite

- [x] Explicar os gates independentes CROP, N2-N4, N1-N2 e N3-N4.
- [x] Definir quando um achado Arete pode se tornar T1 ou T2.
- [x] Diferenciar JSONL Arete, `human_event_logs`, `item_attention_notes` e
  `n4_attention_feedback`.
- [x] Definir HTML/SVG como evidencia derivada, nao fonte primaria.
- [x] Recomendar uso direto de DB/JSONL para ETL e MCP para agentes/UI/escritas.
- [x] Registrar inconsistencias atuais e requisitos antes da ativacao.
- [x] Proibir ingestao ou ativacao como efeito desta documentacao.

## Entrega

- `docs/ARETE-MCP-RAG-HARMONIZACAO.md`

