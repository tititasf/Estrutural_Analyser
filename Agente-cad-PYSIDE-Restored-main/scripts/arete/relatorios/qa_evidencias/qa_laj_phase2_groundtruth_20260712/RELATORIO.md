# RELATORIO — Fase 2 LAJ / ground truth RAG

## Resultado consolidado

- Escopo: `Obra_TREINO_1 / 13_PAV / LAJ` — 31 itens.
- Auditoria read-only: 248 decisões, 0 perguntas humanas, confiança alta em
  todos os itens.
- Curadoria aprovada: 8 candidatos T1 por família de campo, limitados a
  confirmações sem operação corretiva.
- Promoção: 8 registros em `semantic_rag_kb` com contexto
  `qa_groundtruth_t1:dd238e47-1dc6-4f63-a760-4e7ce19a7386` e 8 eventos
  `human_event_logs` de tier T1.

## Campos T1 promovidos

`name`, `laje_dim`, `laje_islands`, `laje_nivel`, `laje_outline_segs`,
`laje_pilares_apoio`, `laje_visao_corte`, `laje_vizinhas_niveis`.

Cada entrada mantém item, decisão, hash/evidência e o identificador da sessão.
Ela é memória **consultiva**: CAD/DB/ficha local continua obrigatório para
confirmar qualquer item futuro.

## Fora do T1

Os achados `LAJ-PILLAR-NOT-TOUCHING` e
`LAJ-NEIGHBOR-LEVEL-CONTAMINATION` foram preservados em `fix_requests.md`.
Não foram promovidos porque têm operações corretivas pendentes; devem passar por
microciclo universal e regressão antes de se tornarem T2.

## Evidências

- Dossiê: `qa_laj_phase2_groundtruth_20260712`.
- Candidatos aprovados: `rag_candidatos_t1_aprovacao/candidatos_t1.json`.
- Regra de visão de corte L318 verificada no microciclo:
  `qa_l318_post_microcycle_20260712`.
