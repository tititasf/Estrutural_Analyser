# Resumo final da sessão QA

- Sessão: `20260714_012525_ad00cf8b_review_cycle_01`
- Modo: `global_read_only_review`
- Interpretado: 8 campos/vínculos em 1 item(ns).
- Ajustes propostos: 7 (nenhum é aplicado nesta auditoria read-only).
- Achados: 2; dúvidas humanas: 8.
- Itens com confiança média/baixa: 1.

## Score por item

- L318: **66.8/100** (baixa) — incertos=laje_nivel, laje_visao_corte, laje_vizinhas_niveis; achados=LAJ-CUT-SEMANTIC-HEIGHT-REPAIR, LAJ-PILLAR-NOT-TOUCHING

## Rastreabilidade

- Decisões: `decisoes.jsonl`; scores: `scores_itens.jsonl`; dúvidas: `perguntas.jsonl`; correções propostas: `fix_requests.md`.
- O ledger global append-only está em `../registro_sessoes.jsonl`.
