# Resumo final da sessão QA

- Sessão: `run`
- Modo: `read_only_audit`
- Interpretado: 8 campos/vínculos em 1 item(ns).
- Ajustes propostos: 2 (nenhum é aplicado nesta auditoria read-only).
- Achados: 1; dúvidas humanas: 1.
- Itens com confiança média/baixa: 1.

## Score por item

- L1: **57.8/100** (baixa) — incertos=laje_nivel, laje_outline_segs, laje_pilares_apoio, laje_vizinhas_niveis; achados=LAJ-LEVEL-OUTLIER-CORRECTION

## Rastreabilidade

- Decisões: `decisoes.jsonl`; scores: `scores_itens.jsonl`; dúvidas: `perguntas.jsonl`; correções propostas: `fix_requests.md`.
- O ledger global append-only está em `../registro_sessoes.jsonl`.
