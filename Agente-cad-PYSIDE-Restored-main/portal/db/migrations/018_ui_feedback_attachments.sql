CREATE TABLE IF NOT EXISTS portal_apontamento_anexos (
    id TEXT PRIMARY KEY,
    apontamento_id TEXT NOT NULL REFERENCES portal_apontamentos_ui(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    mime TEXT NOT NULL,
    blob BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_apontamento_anexos_ponto ON portal_apontamento_anexos(apontamento_id);
