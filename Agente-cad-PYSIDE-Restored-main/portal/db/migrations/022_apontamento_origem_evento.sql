-- Apontamentos gerados por eventos do sistema (ex.: adoção humana de camada QA).
-- A chave única torna a criação idempotente: repetir o evento nunca duplica.
ALTER TABLE portal_apontamento_sessoes ADD COLUMN origem_evento TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_apont_sessao_origem_evento
    ON portal_apontamento_sessoes(origem_evento) WHERE origem_evento IS NOT NULL;
