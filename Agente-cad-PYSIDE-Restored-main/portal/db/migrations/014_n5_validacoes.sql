-- Aprovação humana granular do artefato N5 efetivamente gerado.
-- A chave é o release: uma nova geração volta automaticamente a "pendente".
CREATE TABLE IF NOT EXISTS portal_n5_validacoes (
    release_id     TEXT PRIMARY KEY REFERENCES portal_n5_releases(id) ON DELETE CASCADE,
    obra_id        TEXT NOT NULL REFERENCES portal_obras(id),
    classe         TEXT NOT NULL CHECK (classe IN ('PL','LV','FV','LJ')),
    pavimento      TEXT NOT NULL,
    aprovado_por   TEXT NOT NULL REFERENCES portal_membros(id),
    aprovado_em    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_n5_validacoes_obra_pav
    ON portal_n5_validacoes(obra_id, pavimento, classe);
