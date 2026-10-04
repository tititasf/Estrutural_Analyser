-- Sessões compostas: um apontamento pode conter várias páginas e vários pontos.
-- A tabela original continua guardando cada ponto/captura para manter compatibilidade.
CREATE TABLE IF NOT EXISTS portal_apontamento_sessoes (
    id          TEXT PRIMARY KEY,
    obra_id     TEXT REFERENCES portal_obras(id),
    membro_id   TEXT NOT NULL REFERENCES portal_membros(id),
    titulo      TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS portal_apontamento_paginas (
    id             TEXT PRIMARY KEY,
    sessao_id      TEXT NOT NULL REFERENCES portal_apontamento_sessoes(id) ON DELETE CASCADE,
    ordem          INTEGER NOT NULL,
    pagina_url     TEXT NOT NULL,
    pagina_titulo  TEXT,
    UNIQUE(sessao_id, ordem)
);

ALTER TABLE portal_apontamentos_ui ADD COLUMN sessao_id TEXT REFERENCES portal_apontamento_sessoes(id) ON DELETE CASCADE;
ALTER TABLE portal_apontamentos_ui ADD COLUMN pagina_id TEXT REFERENCES portal_apontamento_paginas(id) ON DELETE CASCADE;
ALTER TABLE portal_apontamentos_ui ADD COLUMN ordem_ponto INTEGER;

CREATE INDEX IF NOT EXISTS idx_apont_ui_sessao_pagina
    ON portal_apontamentos_ui(sessao_id, pagina_id, ordem_ponto);
CREATE INDEX IF NOT EXISTS idx_apont_sessao_membro_data
    ON portal_apontamento_sessoes(membro_id, created_at DESC, id DESC);
