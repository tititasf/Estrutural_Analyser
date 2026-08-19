-- Fila QA agêntica persistente + auditoria de fallback por tentativa.

CREATE TABLE IF NOT EXISTS portal_job_meta (
    job_id      TEXT PRIMARY KEY REFERENCES portal_jobs(id) ON DELETE CASCADE,
    meta_json   TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS portal_qa_rounds (
    id             TEXT PRIMARY KEY,
    job_id         TEXT NOT NULL UNIQUE REFERENCES portal_jobs(id),
    obra_id        TEXT NOT NULL REFERENCES portal_obras(id),
    membro_id      TEXT NOT NULL REFERENCES portal_membros(id),
    classe         TEXT NOT NULL CHECK (classe IN ('PIL','LAJ','FV','LV')),
    pavimento      TEXT NOT NULL,
    layer          TEXT NOT NULL CHECK (layer IN ('L1','L2','L3')),
    status         TEXT NOT NULL DEFAULT 'queued'
                   CHECK (status IN ('queued','running','completed','partial_failed','failed')),
    criado_em      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    iniciado_em    TEXT,
    finalizado_em  TEXT,
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS portal_qa_items (
    id              TEXT PRIMARY KEY,
    round_id        TEXT NOT NULL REFERENCES portal_qa_rounds(id) ON DELETE CASCADE,
    item_id         TEXT NOT NULL,
    ordinal         INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued','running','completed','failed')),
    provider        TEXT,
    model           TEXT,
    verdict         TEXT CHECK (verdict IS NULL OR verdict IN ('validou','invalidou')),
    note            TEXT,
    suggestion_json TEXT,
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(round_id, item_id)
);

CREATE TABLE IF NOT EXISTS portal_qa_attempts (
    id                 TEXT PRIMARY KEY,
    qa_item_id         TEXT NOT NULL REFERENCES portal_qa_items(id) ON DELETE CASCADE,
    ordinal            INTEGER NOT NULL,
    provider           TEXT NOT NULL,
    model_requested    TEXT NOT NULL,
    effort_requested   TEXT,
    model_reported     TEXT,
    status             TEXT NOT NULL CHECK (status IN ('completed','technical_failure')),
    failure_category   TEXT,
    error              TEXT,
    duration_s         REAL NOT NULL,
    criado_em          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE(qa_item_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_qa_rounds_obra ON portal_qa_rounds(obra_id, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_qa_items_round ON portal_qa_items(round_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_qa_attempts_item ON portal_qa_attempts(qa_item_id, ordinal);

