-- Apontamentos visuais comunitarios da interface.
-- A captura fica no banco do portal (nunca no project_data.vision) e a listagem
-- comum nao transporta o BLOB; a imagem e' servida por rota autenticada propria.

CREATE TABLE IF NOT EXISTS portal_apontamentos_ui (
    id                TEXT PRIMARY KEY,
    obra_id           TEXT REFERENCES portal_obras(id),
    membro_id         TEXT NOT NULL REFERENCES portal_membros(id),
    texto             TEXT NOT NULL,
    pagina_url        TEXT NOT NULL,
    pagina_titulo     TEXT,
    seletor_elemento  TEXT,
    elemento_tag      TEXT,
    elemento_role     TEXT,
    elemento_texto    TEXT,
    elemento_json     TEXT NOT NULL DEFAULT '{}',
    clique_x          REAL NOT NULL,
    clique_y          REAL NOT NULL,
    pagina_x          REAL NOT NULL,
    pagina_y          REAL NOT NULL,
    viewport_largura  INTEGER NOT NULL,
    viewport_altura   INTEGER NOT NULL,
    captura_mime      TEXT,
    captura_blob      BLOB,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_apont_ui_obra_data
    ON portal_apontamentos_ui(obra_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_apont_ui_membro_data
    ON portal_apontamentos_ui(membro_id, created_at DESC, id DESC);
