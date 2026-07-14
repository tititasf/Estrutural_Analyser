-- 009_titulo_campo_validado.sql — coluna aditiva `titulo` em
-- portal_validacoes_campo (2026-07-13, Fase 3.4). Necessária pra
-- sincronizar validação de campo de SEGMENTOS de viga (fundo/lateral):
-- o item_id de um segmento é um uid geométrico (`s.get("uid")`), mas o app
-- desktop precisa do TÍTULO ("V101 (segmento N)") pra regex-parsear e
-- resolver `{prefix}_seg_{idx}` — mesmo padrão já usado por
-- `_sincronizar_selo_verde_segmentos_drive` (main.py) pro selo booleano.
ALTER TABLE portal_validacoes_campo ADD COLUMN titulo TEXT;
